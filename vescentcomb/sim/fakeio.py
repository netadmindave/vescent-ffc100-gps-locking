"""Byte-level fake serial port and fake VISA resource manager."""
from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

import numpy as np

try:
    from pyvisa.errors import VisaIOError as _VisaIOError

    def visa_timeout():
        return _VisaIOError(-1073807339)
except ImportError:  # pragma: no cover
    class _VisaIOError(Exception):
        pass

    def visa_timeout():
        return _VisaIOError("timeout")


class FakeSerial:
    """Implements the subset of pyserial the drivers use.

    ``handler(bytes) -> bytes`` is called for each complete request. Text
    devices split on a terminator; binary devices (Interbus) on a frame end.
    """

    def __init__(self, port: str, handler: Callable[[bytes], bytes], terminator: bytes = b"\r",
                 baudrate: int = 115200, timeout: float = 1.0, expected_baud: Optional[int] = None,
                 serial_number: str = "", strip_lf: bool = True):
        self.port = port
        self.handler = handler
        self.terminator = terminator
        self.baudrate = baudrate
        self.timeout = timeout
        self.expected_baud = expected_baud
        self.serial_number = serial_number
        self.strip_lf = strip_lf
        self.is_open = True
        self._rx = bytearray()     # host -> device
        self._tx = bytearray()     # device -> host
        self._lock = threading.Lock()

    # pyserial API --------------------------------------------------------------------
    @property
    def in_waiting(self) -> int:
        return len(self._tx)

    def write(self, data: bytes) -> int:
        if self.expected_baud and self.baudrate != self.expected_baud:
            return len(data)  # wrong baud: device sees garbage, says nothing
        with self._lock:
            self._rx += data
            while True:
                idx = self._rx.find(self.terminator)
                if idx < 0:
                    break
                frame = bytes(self._rx[: idx + len(self.terminator)])
                del self._rx[: idx + len(self.terminator)]
                if self.strip_lf and self._rx[:1] == b"\n":
                    del self._rx[:1]
                reply = self.handler(frame)
                if reply:
                    self._tx += reply
        return len(data)

    def read(self, n: int = 1) -> bytes:
        with self._lock:
            out = bytes(self._tx[:n])
            del self._tx[:n]
            return out

    def read_until(self, expected: bytes = b"\n", size: Optional[int] = None) -> bytes:
        with self._lock:
            idx = self._tx.find(expected)
            if idx < 0:
                out = bytes(self._tx)
                self._tx.clear()
                return out
            out = bytes(self._tx[: idx + len(expected)])
            del self._tx[: idx + len(expected)]
            return out

    def flush(self): pass
    def reset_input_buffer(self): self._tx.clear()
    def reset_output_buffer(self): self._rx.clear()

    def close(self):
        self.is_open = False


class TextDevice:
    """Base for ASCII command/response simulators."""
    eol = "\r\n"

    def __call__(self, frame: bytes) -> bytes:
        cmd = frame.decode("ascii", "replace").strip()
        if not cmd:
            return b""
        reply = self.handle(cmd)
        if reply is None:
            return b""
        return (reply + self.eol).encode("ascii")

    def handle(self, cmd: str) -> Optional[str]:  # pragma: no cover
        raise NotImplementedError


# ------------------------------------------------------------------------------------------

class FakeResource:
    def __init__(self, name: str, model):
        self.resource_name = name
        self.model = model
        self.timeout = 2000
        self.read_termination = "\n"
        self.write_termination = "\n"
        self.chunk_size = 20480
        self._pending: List[str] = []

    def write(self, cmd: str):
        r = self.model.handle(cmd.strip())
        if r is not None:
            self._pending.append(r)

    def read(self) -> str:
        if not self._pending:
            raise visa_timeout()
        r = self._pending.pop(0)
        return r.decode("latin-1") if isinstance(r, bytes) else r

    def query(self, cmd: str) -> str:
        self._pending.clear()
        self.write(cmd)
        return self.read()

    def read_raw(self) -> bytes:
        if not self._pending:
            raise visa_timeout()
        r = self._pending.pop(0)
        return r if isinstance(r, bytes) else r.encode()

    def read_stb(self) -> int:
        return 0x01 if self._pending else 0x00

    def query_binary_values(self, cmd, datatype="B", is_big_endian=False, container=list, **kw):
        data = self.model.binary(cmd.strip())
        if data is None:
            raise visa_timeout()
        return container(data) if container is not np.array else np.asarray(data)

    def clear(self):
        self._pending.clear()

    def close(self):
        pass


class FakeResourceManager:
    def __init__(self, models: Dict[str, object]):
        self.models = models

    def list_resources(self, query: str = "?*::INSTR"):
        return tuple(self.models.keys())

    def open_resource(self, name: str, **kw):
        if name not in self.models:
            raise visa_timeout()
        return FakeResource(name, self.models[name])

    def close(self):
        pass
