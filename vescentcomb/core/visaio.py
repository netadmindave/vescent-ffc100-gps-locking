"""VISA helpers: a shared resource manager and a thread-safe instrument wrapper."""
from __future__ import annotations

import threading
import time
from typing import Optional

try:
    import pyvisa
    VisaIOError = pyvisa.errors.VisaIOError
except ImportError:  # pragma: no cover
    pyvisa = None

    class VisaIOError(Exception):  # type: ignore
        pass

_RM = None
_RM_LOCK = threading.Lock()


def resource_manager(backend: Optional[str] = None):
    """One ResourceManager per process (opening several confuses NI-VISA)."""
    global _RM
    with _RM_LOCK:
        if _RM is None:
            if pyvisa is None:
                raise ImportError("pyvisa is required: pip install pyvisa")
            _RM = pyvisa.ResourceManager(backend) if backend else pyvisa.ResourceManager()
        return _RM


def set_resource_manager(rm) -> None:
    """Inject a resource manager (used by the simulator)."""
    global _RM
    with _RM_LOCK:
        _RM = rm


class VisaInstrument:
    """Thin wrapper adding a lock, safe queries and timeout scoping."""

    def __init__(self, resource: Optional[str] = None, inst=None, timeout_ms: int = 5000,
                 read_termination: Optional[str] = "\n", write_termination: str = "\n"):
        if inst is None:
            inst = resource_manager().open_resource(resource)
        self.inst = inst
        self.resource = resource or getattr(inst, "resource_name", "")
        self.inst.timeout = timeout_ms
        try:
            self.inst.read_termination = read_termination
            self.inst.write_termination = write_termination
        except Exception:
            pass
        self.default_timeout = timeout_ms
        self.lock = threading.RLock()

    # -- basic I/O -------------------------------------------------------------
    def write(self, cmd: str) -> None:
        with self.lock:
            self.inst.write(cmd)

    def read(self) -> str:
        with self.lock:
            return self.inst.read().strip()

    def query(self, cmd: str, timeout_ms: Optional[int] = None) -> str:
        with self.lock:
            old = self.inst.timeout
            if timeout_ms is not None:
                self.inst.timeout = timeout_ms
            try:
                return self.inst.query(cmd).strip()
            finally:
                self.inst.timeout = old

    def try_query(self, cmd: str, timeout_ms: Optional[int] = None) -> Optional[str]:
        """Query that returns None on timeout instead of raising."""
        try:
            return self.query(cmd, timeout_ms)
        except VisaIOError:
            return None

    def query_float(self, cmd: str, timeout_ms: Optional[int] = None) -> Optional[float]:
        r = self.try_query(cmd, timeout_ms)
        if r is None:
            return None
        try:
            return float(r)
        except ValueError:
            return None

    def read_raw(self) -> bytes:
        with self.lock:
            return self.inst.read_raw()

    def query_binary_values(self, cmd: str, **kw):
        with self.lock:
            return self.inst.query_binary_values(cmd, **kw)

    def read_stb(self) -> int:
        with self.lock:
            return self.inst.read_stb()

    def clear(self) -> None:
        with self.lock:
            try:
                self.inst.clear()
            except Exception:
                pass

    def set_timeout(self, ms: int) -> None:
        with self.lock:
            self.inst.timeout = ms

    def close(self) -> None:
        try:
            self.inst.close()
        except Exception:
            pass

    def sleep(self, s: float) -> None:
        time.sleep(s)
