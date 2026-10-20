"""Add-on manifests (``addon.toml``) — read without importing any add-on code."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

MANIFEST = "addon.toml"
ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")

try:  # Python 3.11+
    import tomllib as _toml
except ImportError:  # pragma: no cover
    try:
        import tomli as _toml  # type: ignore
    except ImportError:
        _toml = None


def _strip_comment(line: str) -> str:
    q = False
    for i, ch in enumerate(line):
        if ch == '"':
            q = not q
        elif ch == "#" and not q:
            return line[:i]
    return line


def _mini_toml(text: str) -> Dict[str, Any]:
    """Tiny TOML subset (key = "str" | number | true/false | [list]) for Pythons without tomllib."""
    out: Dict[str, Any] = {}
    buf = ""
    for raw in text.splitlines():
        line = _strip_comment(raw).strip()
        if not line and not buf:
            continue
        if line.startswith("[") and not buf:          # [table] headers are not used in addon.toml
            continue
        buf = f"{buf} {line}".strip()
        if buf.count("[") > buf.count("]") or buf.count('"""') % 2:
            continue
        if "=" in buf:
            k, v = buf.split("=", 1)
            out[k.strip()] = _mini_value(v.strip())
        buf = ""
    return out


def _mini_value(v: str):
    if v.startswith("["):
        items = re.findall(r'"((?:[^"\\]|\\.)*)"|([^,\[\]\s]+)', v[1:-1])
        return [a if a or not b else _mini_value(b) for a, b in items if a or b]
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def load_toml(path: Path) -> Dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    if _toml is not None:
        return _toml.loads(text)
    return _mini_toml(text)


@dataclass
class AddonInfo:
    """Everything the manager shows about one add-on folder."""
    id: str
    name: str
    path: Path
    version: str = "0.0.0"
    type: str = "tool"                      # "module" (bundle of instruments + process) or "tool"
    category: str = "Instruments"
    description: str = ""
    author: str = ""
    requires: List[str] = field(default_factory=list)     # pip requirements, auto-installed
    depends: List[str] = field(default_factory=list)      # other add-on ids
    optional: List[str] = field(default_factory=list)     # add-ons used when present (documentation)
    vescentcomb: str = ""                                    # minimum core version, e.g. ">=0.3"
    entry: str = "register"                               # function in the package __init__
    default_enabled: bool = True
    builtin: bool = False
    # runtime state, filled by the loader
    enabled: bool = False
    state: str = "not loaded"   # not loaded | loaded | disabled | error | needs install | missing dependency
    error: str = ""
    missing: List[str] = field(default_factory=list)
    overrides_builtin: bool = False

    @property
    def module_name(self) -> str:
        return f"vescentcomb_addons.{self.id}"

    @property
    def label(self) -> str:
        return f"{self.name} ({self.id} {self.version})"


def read_manifest(folder: Path, builtin: bool = False) -> Optional[AddonInfo]:
    folder = Path(folder)
    mf = folder / MANIFEST
    if not mf.is_file() or not (folder / "__init__.py").is_file():
        return None
    try:
        d = load_toml(mf)
    except Exception as e:
        return AddonInfo(id=folder.name, name=folder.name, path=folder, state="error",
                         error=f"addon.toml: {e}", builtin=builtin)
    aid = str(d.get("id") or folder.name)
    info = AddonInfo(
        id=aid, name=str(d.get("name", aid)), path=folder, version=str(d.get("version", "0.0.0")),
        type=str(d.get("type", "tool")), category=str(d.get("category", "Instruments")),
        description=str(d.get("description", "")).strip(), author=str(d.get("author", "")),
        requires=[str(x) for x in d.get("requires", [])], depends=[str(x) for x in d.get("depends", [])],
        optional=[str(x) for x in d.get("optional", [])], vescentcomb=str(d.get("vescentcomb", "")),
        entry=str(d.get("entry", "register")), default_enabled=bool(d.get("default_enabled", True)),
        builtin=builtin)
    if not ID_RE.match(aid):
        info.state, info.error = "error", f"id {aid!r} must be lower-case letters, digits and _"
    elif aid != folder.name:
        info.state, info.error = "error", f"id {aid!r} must match the folder name {folder.name!r}"
    return info
