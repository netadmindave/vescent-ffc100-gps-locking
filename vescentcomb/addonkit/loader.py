"""Find add-on folders, check/install their requirements, import them and call ``register(api)``.

Add-ons live in folders scanned in this order (first one wins when two folders hold the same id,
so a copy in your own folder overrides the built-in one):

    1. the folders listed in settings ``addons.dirs`` (default: Documents/vescentcomb addons)
    2. the built-in folder ``vescentcomb/addons``

Every add-on is importable as ``vescentcomb_addons.<id>`` once the loader has run.
"""
from __future__ import annotations

import importlib
import shutil
import sys
import time
import traceback
import types
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from . import installer as _inst
from .api import AddonAPI
from .manifest import ID_RE, AddonInfo, read_manifest
from .registry import REGISTRY

PKG_DIR = Path(__file__).resolve().parent.parent
BUILTIN_DIR = PKG_DIR / "addons"
TEMPLATE_DIR = PKG_DIR / "addon_template"
GUIDE_PATH = PKG_DIR / "docs" / "ADDON_GUIDE.md"
NAMESPACE = "vescentcomb_addons"

_LAST_SCAN: Dict[str, AddonInfo] = {}
_STATE = {"loaded_once": False}


def default_user_dir() -> Path:
    docs = Path.home() / "Documents"
    return (docs if docs.is_dir() else Path.home()) / "vescentcomb addons"


def user_dirs(settings=None) -> List[Path]:
    return []                       # stand-alone app: built-in module only, no user add-on folders


def addon_dirs(settings=None) -> List[Path]:
    out = [d for d in user_dirs(settings) if d.is_dir()]
    out.append(BUILTIN_DIR)
    return out


def _ensure_namespace(dirs: Iterable[Path]) -> None:
    mod = sys.modules.get(NAMESPACE)
    if mod is None:
        mod = types.ModuleType(NAMESPACE)
        mod.__doc__ = "Namespace for vescentcomb add-ons (one sub-package per add-on folder)."
        sys.modules[NAMESPACE] = mod
    mod.__path__ = [str(d) for d in dirs]


def _core_version_ok(spec: str) -> bool:
    if not spec:
        return True
    from .. import __version__
    try:
        from packaging.specifiers import SpecifierSet
        return __version__ in SpecifierSet(spec)
    except Exception:
        return True


def scan(settings=None) -> Dict[str, AddonInfo]:
    """Read every manifest (no add-on code is imported). Returns {id: AddonInfo} in display order."""
    found: Dict[str, AddonInfo] = {}
    for d in addon_dirs(settings):
        builtin = d.resolve() == BUILTIN_DIR.resolve()
        if not d.is_dir():
            continue
        for sub in sorted(p for p in d.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
            info = read_manifest(sub, builtin)
            if info is None:
                continue
            if info.id in found:
                if builtin:
                    found[info.id].overrides_builtin = True
                continue
            loaded = REGISTRY.addons.get(info.id)
            if loaded is not None:
                info.state, info.error = loaded.state, loaded.error
            en = settings.get(f"addons.enabled.{info.id}") if settings is not None else None
            info.enabled = True
            if info.state == "not loaded" and not info.enabled:
                info.state = "disabled"
            info.missing = _inst.missing(info.requires) if info.state != "error" else []
            found[info.id] = info
    _LAST_SCAN.clear()
    _LAST_SCAN.update(found)
    return found


def _topo(infos: Dict[str, AddonInfo], ids: Iterable[str]) -> List[AddonInfo]:
    out: List[AddonInfo] = []
    seen = set()

    def visit(i, stack=()):
        if i in seen or i not in infos:
            return
        if i in stack:
            return                                         # cycle: load in file order
        for d in infos[i].depends:
            visit(d, stack + (i,))
        seen.add(i)
        out.append(infos[i])
    for i in ids:
        visit(i)
    return out


def _rollback(addon_id: str) -> None:
    r = REGISTRY
    r.roles = {k: v for k, v in r.roles.items() if v.addon != addon_id}
    r.drivers = {k: v for k, v in r.drivers.items() if v.addon != addon_id}
    for name in ("serial_probes", "visa_probes", "scanners", "pages", "windows", "overview", "chain", "references"):
        setattr(r, name, [x for x in getattr(r, name) if x.addon != addon_id])
    r.visa_classifiers = [x for x in r.visa_classifiers if x[1] != addon_id]
    r.sim_hooks = [x for x in r.sim_hooks if x[1] != addon_id]
    r.menu_actions = [x for x in r.menu_actions if x[3] != addon_id]


def _default_installer(reqs: List[str], info: AddonInfo, log: Callable[[str], None]) -> bool:
    log(f"[{info.id}] first load: installing {', '.join(reqs)}")
    ok, _ = _inst.pip_install(reqs, log)
    return ok


def load_one(info: AddonInfo, settings=None, auto_install: bool = True, installer=None,
             log: Optional[Callable[[str], None]] = None) -> AddonInfo:
    say = log or (lambda m: None)
    if info.id in REGISTRY.addons:
        return REGISTRY.addons[info.id]
    if info.state == "error" and info.error.startswith(("addon.toml", "id ")):
        return info
    if not _core_version_ok(info.vescentcomb):
        from .. import __version__
        info.state, info.error = "error", f"needs vescentcomb {info.vescentcomb} (this is {__version__})"
        return info
    for dep in info.depends:
        if dep not in REGISTRY.addons:
            info.state, info.error = "missing dependency", f"needs add-on '{dep}' enabled and loaded"
            return info
    miss = _inst.missing(info.requires)
    if miss and auto_install:
        ok = (installer or (lambda r, i: _default_installer(r, i, say)))(miss, info)
        miss = _inst.missing(info.requires) if ok else miss
    if miss:
        info.state, info.missing = "needs install", miss
        info.error = "missing Python packages: " + ", ".join(miss)
        return info
    try:
        mod = importlib.import_module(info.module_name)
        fn = getattr(mod, info.entry, None)
        if not callable(fn):
            raise AttributeError(f"{info.module_name} has no function {info.entry}(api)")
        fn(AddonAPI(info))
    except Exception:
        _rollback(info.id)
        info.state, info.error = "error", traceback.format_exc(limit=6)
        say(f"[{info.id}] failed to load:\n{info.error}")
        return info
    info.state, info.error, info.missing = "loaded", "", []
    REGISTRY.addons[info.id] = info
    if settings is not None and settings.get(f"addons.installed.{info.id}.version") != info.version:
        settings.set(f"addons.installed.{info.id}", {"version": info.version,
                                                     "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return info


def load_enabled(settings=None, auto_install: Optional[bool] = None, installer=None, log=None,
                 include_all: bool = False, only: Optional[Iterable[str]] = None) -> Dict[str, AddonInfo]:
    """Load every enabled add-on (dependencies first). ``include_all`` ignores the checkboxes."""
    infos = scan(settings)
    _ensure_namespace(addon_dirs(settings))
    _STATE["loaded_once"] = True
    if auto_install is None:
        auto_install = settings.get("addons.auto_install", True) if settings is not None else True
    if only is not None:
        ids = list(only)
    elif include_all:
        ids = [i for i, a in infos.items() if a.state != "error"]
    else:
        ids = [i for i, a in infos.items() if a.state != "error"]     # the built-in module is always on
    for info in _topo(infos, ids):
        if True:
            load_one(info, settings, auto_install, installer, log)
    return infos


def ensure_loaded(settings=None, **kw) -> None:
    """Load the enabled add-ons once per process (scripts get this through discovery).
    Without ``settings`` the user's settings file decides which add-ons are on, as in the GUI."""
    if _STATE["loaded_once"] or REGISTRY.addons:
        return
    if settings is None:
        from ..settings import Settings
        settings = Settings()
    load_enabled(settings, **kw)


def load(addon_id: str, settings=None, auto_install: bool = True, log=print):
    """Load one add-on (and what it depends on) even if it is unchecked; return its package."""
    infos = scan(settings)
    _ensure_namespace(addon_dirs(settings))
    _STATE["loaded_once"] = True
    if addon_id not in infos:
        raise KeyError(f"no add-on '{addon_id}' in {', '.join(str(d) for d in addon_dirs(settings))}")
    for info in _topo(infos, [addon_id]):
        load_one(info, settings, auto_install, None, log)
    info = REGISTRY.addons.get(addon_id) or infos[addon_id]
    if info.state != "loaded":
        raise RuntimeError(f"add-on '{addon_id}' did not load: {info.error}")
    return sys.modules[info.module_name]


def reset() -> None:
    """Forget every loaded add-on (tests, or before a reload)."""
    REGISTRY.clear()
    _STATE["loaded_once"] = False
    for name in [m for m in sys.modules if m == NAMESPACE or m.startswith(NAMESPACE + ".")]:
        del sys.modules[name]
    _LAST_SCAN.clear()


def last_scan() -> Dict[str, AddonInfo]:
    return dict(_LAST_SCAN)


# ---- template --------------------------------------------------------------------------------------
TEXT_SUFFIXES = {".py", ".toml", ".md", ".txt"}


def create_from_template(dest_dir: Path, addon_id: str, name: str, cls_name: str = "",
                         role: str = "", kind: str = "") -> Path:
    """Copy the template add-on to ``dest_dir/addon_id`` with names filled in."""
    if not ID_RE.match(addon_id):
        raise ValueError("id must be lower-case letters, digits and _ (2–41 characters), starting with a letter")
    dest = Path(dest_dir) / addon_id
    if dest.exists():
        raise FileExistsError(f"{dest} already exists")
    cls_name = cls_name or "".join(p.capitalize() for p in addon_id.split("_"))
    tokens = {"__ADDON_ID__": addon_id, "__ADDON_NAME__": name, "__CLASS__": cls_name,
              "__ROLE__": role or addon_id, "__KIND__": kind or addon_id}
    src = TEMPLATE_DIR / "template_addon"
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for p in sorted(dest.rglob("*"), key=lambda x: -len(x.parts)):
        name = p.name
        for k, v in tokens.items():
            name = name.replace(k, v)
        if name != p.name:
            p.rename(p.with_name(name))
    for p in dest.rglob("*"):
        if p.is_file() and p.suffix in TEXT_SUFFIXES:
            t = p.read_text(encoding="utf-8")
            for k, v in tokens.items():
                t = t.replace(k, v)
            p.write_text(t, encoding="utf-8")
    return dest
