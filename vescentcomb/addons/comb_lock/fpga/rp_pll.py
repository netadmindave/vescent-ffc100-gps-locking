"""
Low-level TCP transport to the SLICE-FPGA-II (Red Pitaya / Zynq-7010) ``monitor-tcp`` server.

Re-implementation of Vescent's ``RP_PLL.py`` for modern Python (3.9+, NumPy 2):
  * identical wire format: 12-byte little-endian header ``struct('=III')`` = (magic, address, data)
  * every request/response pair is serialised by a lock, so a background monitor thread and the
    notebook can share one connection safely
  * no silent zero-filled reads: a failed transfer raises ``CommsError``
"""
from __future__ import annotations

import logging
import socket
import struct
import threading

import numpy as np

log = logging.getLogger(__name__)


class CommsError(Exception):
    """Socket-level failure talking to the box."""


class CommsLoggeableError(CommsError):
    """Kept for API compatibility with the Vescent code."""


class RP_PLL_device:
    MAGIC_BYTES_WRITE_REG = 0xABCD1233
    MAGIC_BYTES_READ_REG = 0xABCD1234
    MAGIC_BYTES_READ_BUFFER = 0xABCD1235
    MAGIC_BYTES_WRITE_FILE = 0xABCD1237
    MAGIC_BYTES_SHELL_COMMAND = 0xABCD1238
    MAGIC_BYTES_REBOOT_MONITOR = 0xABCD1239

    FPGA_BASE_ADDR = 0x40000000       # PS<->PL memory map, GP0 AXI master
    FPGA_BASE_ADDR_XADC = 0x80000000  # XADC / clock wizard / clock select, GP1 AXI master

    MAX_SAMPLES_READ_BUFFER = 2 ** 15  # size of ram_data_logger.vhd

    def __init__(self, controller=None, timeout: float = 2.0):
        self.sock: socket.socket | None = None
        self.valid_socket = False
        self.controller = controller
        self.timeout = timeout
        self.HOST = None
        self.PORT = None
        self.lock = threading.RLock()

    # ------------------------------------------------------------------ connection
    def OpenTCPConnection(self, HOST: str, PORT: int = 5000, valid_socket_for_general_comms: bool = True):
        self.CloseTCPConnection()
        self.HOST, self.PORT = HOST, PORT
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # avoids ~33 ms Nagle delay on Windows
        s.settimeout(self.timeout)
        try:
            s.connect((HOST, PORT))
        except OSError as e:
            s.close()
            self.valid_socket = False
            raise CommsError(f'Could not connect to {HOST}:{PORT}: {e}') from e
        self.sock = s
        self.valid_socket = valid_socket_for_general_comms
        log.info('Connected to %s:%d', HOST, PORT)

    def CloseTCPConnection(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.valid_socket = False

    def _fail(self, e: Exception):
        self.CloseTCPConnection()
        if self.controller is not None and hasattr(self.controller, 'socketErrorEvent'):
            self.controller.socketErrorEvent(e)
        raise CommsError(str(e)) from e

    def _require(self):
        if not self.valid_socket or self.sock is None:
            raise CommsError('Not connected')

    def recvall(self, count: int) -> bytes:
        buf = bytearray()
        while len(buf) < count:
            chunk = self.sock.recv(count - len(buf))
            if not chunk:
                raise CommsError('Connection closed by remote host')
            buf += chunk
        return bytes(buf)

    def send(self, packet: bytes):
        self._require()
        try:
            self.sock.sendall(packet)
        except OSError as e:
            self._fail(e)

    def read(self, n: int) -> bytes:
        self._require()
        try:
            return self.recvall(n)
        except (OSError, CommsError) as e:
            self._fail(e)

    # ------------------------------------------------------------------ registers
    @staticmethod
    def validate_address(addr: int):
        if addr % 4:
            raise ValueError(f'non-32-bit-aligned register access: 0x{addr:x}')

    def write_Zynq_register_32bits(self, absolute_addr: int, data_32bits: int, bSigned: bool = False):
        self.validate_address(absolute_addr)
        fmt = '=IIi' if bSigned else '=III'
        val = int(data_32bits) & 0xFFFFFFFF
        if bSigned and val >= 2 ** 31:
            val -= 2 ** 32
        with self.lock:
            self.send(struct.pack(fmt, self.MAGIC_BYTES_WRITE_REG, absolute_addr, val))

    def read_Zynq_register_32bits(self, absolute_addr: int, bIsAXI: bool = False) -> bytes:
        self.validate_address(absolute_addr)
        with self.lock:
            self.send(struct.pack('=III', self.MAGIC_BYTES_READ_REG, absolute_addr, 0))
            return self.read(4)

    def read_Zynq_buffer_int16(self, number_of_points: int) -> bytes:
        number_of_points = int(min(number_of_points, self.MAX_SAMPLES_READ_BUFFER))
        with self.lock:
            self.send(struct.pack('=III', self.MAGIC_BYTES_READ_BUFFER, self.FPGA_BASE_ADDR, number_of_points))
            return self.read(2 * number_of_points)

    def write_Zynq_register_uint32(self, address_uint32, data_uint32):
        self.write_Zynq_register_32bits(self.FPGA_BASE_ADDR + address_uint32, data_uint32, bSigned=False)

    def write_Zynq_register_int32(self, address_uint32, data_int32):
        self.write_Zynq_register_32bits(self.FPGA_BASE_ADDR + address_uint32, data_int32, bSigned=True)

    def write_Zynq_AXI_register_uint32(self, address_uint32, data_uint32):
        self.write_Zynq_register_32bits(self.FPGA_BASE_ADDR_XADC + address_uint32, data_uint32, bSigned=False)

    def read_Zynq_register_uint32(self, address_uint32) -> int:
        return struct.unpack('<I', self.read_Zynq_register_32bits(self.FPGA_BASE_ADDR + address_uint32))[0]

    def read_Zynq_register_int32(self, address_uint32) -> int:
        return struct.unpack('<i', self.read_Zynq_register_32bits(self.FPGA_BASE_ADDR + address_uint32))[0]

    def read_Zynq_AXI_register_uint32(self, address_uint32) -> int:
        return struct.unpack('<I', self.read_Zynq_register_32bits(self.FPGA_BASE_ADDR_XADC + address_uint32))[0]

    def read_Zynq_register_uint64(self, address_uint32_lsb, address_uint32_msb) -> np.ndarray:
        with self.lock:
            lsb = self.read_Zynq_register_uint32(address_uint32_lsb)
            msb = self.read_Zynq_register_uint32(address_uint32_msb)
        return np.array([lsb, msb], dtype=np.uint32).view(np.uint64)

    def read_Zynq_register_int64(self, address_uint32_lsb, address_uint32_msb) -> np.ndarray:
        with self.lock:
            lsb = self.read_Zynq_register_uint32(address_uint32_lsb)
            msb = self.read_Zynq_register_uint32(address_uint32_msb)
        return np.array([lsb, msb], dtype=np.uint32).view(np.int64)

    # ------------------------------------------------------------------ files / shell
    def write_file_on_remote(self, strFilenameLocal: str, strFilenameRemote: str):
        data = np.fromfile(strFilenameLocal, dtype=np.uint8).tobytes()
        name = strFilenameRemote.encode('ascii')
        with self.lock:
            self.send(struct.pack('=III', self.MAGIC_BYTES_WRITE_FILE, len(name), len(data)))
            self.send(name)
            self.send(data)

    def send_shell_command(self, strCommand: str):
        cmd = strCommand.encode('ascii')
        with self.lock:
            self.send(struct.pack('=III', self.MAGIC_BYTES_SHELL_COMMAND, len(cmd), 0))
            self.send(cmd)

    def send_reboot_command(self):
        with self.lock:
            self.send(struct.pack('=III', self.MAGIC_BYTES_REBOOT_MONITOR, 0, 0))

    # ------------------------------------------------------------------ Opal-Kelly-style shims used by SuperLaserLand
    def SetWireInValue(self, endpoint, value_16bits):
        if value_16bits < 0:
            self.write_Zynq_register_int32(endpoint * 4, value_16bits)
        else:
            self.write_Zynq_register_uint32(endpoint * 4, value_16bits)

    def UpdateWireIns(self):
        return

    def GetWireOutValue(self, endpoint):
        return self.read_Zynq_register_uint32(4 * endpoint) & 0xFFFF

    def UpdateWireOuts(self):
        return 0
