"""Common base for every instrument driver.

Rules every driver follows
--------------------------
* ``with Driver(...) as d:`` always leaves the instrument in its *safe state*
  on exit (laser outputs off, emission off, nothing else touched).
* ``find()`` locates the instrument by itself (USB ID, *IDN?, serial number).
* ``identify()`` returns an :class:`Identity` (model, serial, firmware).
* ``snapshot()`` reads settings and never changes anything.
* ``restore(snapshot)`` writes back only the keys listed in ``RESTORABLE`` —
  never output / emission / servo-enable states.
* Hard limits (wavelength ranges, voltage rails, rep-rate caps, the FFC-100
  no-direct-OFF rule) live in the driver, so scripts cannot skip them.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, Iterable, Optional

from .options import Opt, OptionsMixin  # noqa: F401  (re-exported for drivers)


class DeviceError(RuntimeError):
    """Instrument did not respond, rejected a command, or returned garbage."""


class SafetyError(DeviceError):
    """A request was refused because it would violate a hard safety rule."""


@dataclass
class Identity:
    kind: str                       # driver kind, e.g. "sliceopl"
    model: str = ""
    serial: str = ""
    firmware: str = ""
    raw: str = ""                   # raw identity string as received
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def key(self) -> str:
        """Stable key used to match a physical unit to a role."""
        return f"{self.kind}:{self.serial or self.model}"


class Device(OptionsMixin):
    """Base class. Subclasses set ``KIND`` and implement the hooks below.

    ``OPTIONS`` (see :mod:`vescentcomb.core.options`) lists every setting the GUI shows on the
    instrument's Setup tab; ``REFERENCE`` describes its 10 MHz reference input, if any."""

    KIND: str = "generic"
    LABEL: str = "Generic device"
    #: snapshot keys that ``restore()`` may write back. Outputs never appear here.
    RESTORABLE: tuple = ()
    #: 10 MHz reference: None (no input), or the key of a bool option that enables it,
    #: or "auto" (switches by itself when a reference is present).
    REFERENCE: Optional[str] = None

    def __init__(self) -> None:
        # One lock per device: the GUI worker thread and scripts may share it.
        self._lock = threading.RLock()
        self.address: str = ""

    # -- context manager: always end safe ------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            self.safe_state()
        finally:
            self.close()
        return False

    # -- hooks ------------------------------------------------------------------
    def close(self) -> None:  # pragma: no cover - overridden
        pass

    def safe_state(self) -> None:
        """Put the instrument in a state that is safe to walk away from.

        Default: do nothing (instruments with no hazardous output)."""

    def identify(self) -> Identity:  # pragma: no cover - overridden
        return Identity(kind=self.KIND)

    def snapshot(self) -> Dict[str, Any]:  # pragma: no cover - overridden
        return {}

    def poll(self) -> Dict[str, Any]:
        """Fast status read used by the GUI at ~1 Hz. Defaults to snapshot()."""
        return self.snapshot()

    # -- restore ------------------------------------------------------------
    def _setter_for(self, key: str) -> Optional[Callable[[Any], Any]]:
        return getattr(self, f"set_{key}", None)

    def restore(self, snap: Dict[str, Any], keys: Optional[Iterable[str]] = None) -> Dict[str, str]:
        """Write back restorable settings from a snapshot.

        Returns ``{key: "ok" | "skipped: reason" | "error: ..."}``."""
        out: Dict[str, str] = {}
        allowed = set(self.RESTORABLE)
        wanted = list(keys) if keys is not None else [k for k in snap if k in allowed]
        for k in wanted:
            if k not in allowed:
                out[k] = "skipped: not restorable"
                continue
            fn = self._setter_for(k)
            if fn is None:
                out[k] = "skipped: no setter"
                continue
            try:
                fn(snap[k])
                out[k] = "ok"
            except Exception as e:  # keep going, report per key
                out[k] = f"error: {e}"
        return out

    def diff(self, saved: Dict[str, Any], keys: Optional[Iterable[str]] = None,
             rel_tol: float = 1e-9) -> Dict[str, tuple]:
        """Compare live settings against a saved snapshot -> {key: (live, saved)}."""
        live = self.snapshot()
        keys = list(keys) if keys is not None else [k for k in saved if k in self.RESTORABLE]
        d = {}
        for k in keys:
            a, b = live.get(k), saved.get(k)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if abs(a - b) <= rel_tol * max(abs(a), abs(b), 1e-30):
                    continue
            elif a == b:
                continue
            d[k] = (a, b)
        return d

    # -- discovery ------------------------------------------------------------
    @classmethod
    def find(cls, serial: Optional[str] = None, **kw):
        """Locate this instrument (by USB ID / *IDN? / serial) and open it."""
        from .. import discovery
        return discovery.open_one(cls.KIND, serial=serial, **kw)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.address}>"
