"""Requirement checks and pip installs for add-ons."""
from __future__ import annotations

import re
import subprocess
import sys
from typing import Callable, List, Optional, Tuple

try:
    from importlib import metadata as _md
except ImportError:  # pragma: no cover
    import importlib_metadata as _md  # type: ignore

try:
    from packaging.requirements import Requirement as _Req
except Exception:  # pragma: no cover - packaging ships with pip almost everywhere
    _Req = None

_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def is_satisfied(req: str) -> bool:
    """True when the distribution is installed (and the version matches, when packaging is available)."""
    if _Req is not None:
        try:
            r = _Req(req)
        except Exception:
            return False
        if r.marker is not None and not r.marker.evaluate():
            return True                                # not needed on this platform
        try:
            ver = _md.version(r.name)
        except _md.PackageNotFoundError:
            return False
        return (not r.specifier) or r.specifier.contains(ver, prereleases=True)
    m = _NAME.match(req)
    if not m:
        return False
    try:
        _md.version(m.group(1))
        return True
    except _md.PackageNotFoundError:
        return False


def missing(reqs: List[str]) -> List[str]:
    return [r for r in reqs if not is_satisfied(r)]


def pip_command(reqs: List[str]) -> List[str]:
    return [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *reqs]


def pip_install(reqs: List[str], log: Optional[Callable[[str], None]] = None,
                timeout: float = 900) -> Tuple[bool, str]:
    """Install with the same Python that runs vescentcomb. Returns (ok, combined output)."""
    if not reqs:
        return True, ""
    say = log or (lambda m: None)
    say("pip install " + " ".join(reqs))
    try:
        p = subprocess.run(pip_command(reqs), capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return False, str(e)
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.splitlines()[-15:]:
        say(line)
    if p.returncode == 0:
        try:
            _md.distributions.cache_clear()  # type: ignore[attr-defined]
        except Exception:
            pass
        import importlib
        importlib.invalidate_caches()
    return p.returncode == 0, out
