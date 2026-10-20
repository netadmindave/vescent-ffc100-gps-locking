"""Serial helpers: an ASCII line transport and a port lister."""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import List, Optional

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # pragma: no cover - pyserial is a hard dependency
    serial = None


@dataclass
class PortInfo:
    device: str
    description: str = ""
    hwid: str = ""
    vid: Optional[int] = None
    pid: Optional[int] = None
    serial_number: str = ""
    manufacturer: str = ""

    @property
    def is_bluetooth(self) -> bool:
        d = (self.description or "").lower()
        h = (self.hwid or "").upper()
        return "bluetooth" in d or h.startswith("BTHENUM") or "RFCOMM" in self.device.upper()

    @property
    def usb_family(self) -> str:
        """Rough chip family from the USB vendor ID."""
        return {0x10C4: "cp210x", 0x0403: "ftdi", 0x067B: "prolific",
                0x1A86: "ch34x", 0x0483: "stm32"}.get(self.vid or -1, "cdc" if self.vid else "")


def list_serial_ports() -> List[PortInfo]:
    if serial is None:
        return []
    out = []
    for p in serial.tools.list_ports.comports():
        out.append(PortInfo(device=p.device, description=p.description or "",
                            hwid=p.hwid or "", vid=p.vid, pid=p.pid,
                            serial_number=p.serial_number or "",
                            manufacturer=p.manufacturer or ""))
    return out


class SerialLine:
    """Thread-safe ASCII command/response transport.

    ``eol`` is appended to every command ("\\r" for the SLICE-OPL,
    "\\r\\n" for the FFC-100). Replies are read until the line goes quiet,
    which copes with devices that echo and send multi-line responses.
    """

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200,
                 timeout: float = 1.0, eol: str = "\r", quiet: float = 0.05,
                 ser=None):
        if ser is None:
            if serial is None:
                raise ImportError("pyserial is required: pip install pyserial")
            ser = serial.Serial(port=port, baudrate=baudrate,
                                bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE, timeout=timeout,
                                xonxoff=False, rtscts=False, dsrdtr=False)
            time.sleep(0.1)
        self.ser = ser
        self.port = port or getattr(ser, "port", "") or ""
        self.eol = eol
        self.quiet = quiet
        self.lock = threading.RLock()
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

    @property
    def timeout(self) -> float:
        return getattr(self.ser, "timeout", None) or 1.0

    def write(self, cmd: str) -> None:
        with self.lock:
            self.ser.reset_input_buffer()
            self.ser.write((cmd.strip() + self.eol).encode("ascii"))
            self.ser.flush()

    def read(self, timeout: Optional[float] = None) -> str:
        """Wait for the reply to begin, then drain until the line goes quiet."""
        with self.lock:
            deadline = time.time() + (timeout if timeout is not None else self.timeout)
            while self.ser.in_waiting == 0 and time.time() < deadline:
                time.sleep(0.005)
            data = b""
            while True:
                n = self.ser.in_waiting
                if n:
                    data += self.ser.read(n)
                    time.sleep(self.quiet)
                else:
                    break
            return data.decode("ascii", errors="replace").strip()

    def query(self, cmd: str, timeout: Optional[float] = None) -> str:
        with self.lock:
            self.write(cmd)
            return self.read(timeout)

    def close(self) -> None:
        try:
            if self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    @property
    def is_open(self) -> bool:
        return bool(getattr(self.ser, "is_open", False))
