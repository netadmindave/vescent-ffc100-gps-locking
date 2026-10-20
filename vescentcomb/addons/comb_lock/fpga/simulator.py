"""
A software stand-in for the SLICE-FPGA-II ``monitor-tcp`` server, for dry-running the notebook
without hardware. It speaks the same TCP protocol, remembers register writes (including the
read-back RAM shadow), reports a locked PLL clock, and returns plausible data:

  ADC0/ADC1   : a beat tone at |DDC reference| + noise, with the 0xA88F framing word
  DDC0/DDC1   : small frequency-noise samples
  counters    : a new zero-dead-time sample every 0.5 s with ~mHz scatter when locked
  DAC outputs : a slow random walk when locked

It is not a model of the loop physics; it exists to exercise the code paths.
"""
from __future__ import annotations

import socket
import struct
import threading
import time

import numpy as np

WR, RD, BUF, WF, SH, RB = 0xABCD1233, 0xABCD1234, 0xABCD1235, 0xABCD1237, 0xABCD1238, 0xABCD1239
BASE, AXI = 0x40000000, 0x80000000


class SliceSimulator:
    def __init__(self, port: int = 50000, host: str = '127.0.0.1'):
        self.host, self.port = host, port
        self.regs: dict[int, int] = {}
        self.writes: list[tuple[int, int]] = []
        self.lock = threading.Lock()
        self.rng = np.random.default_rng(1)
        self.t0 = time.time()
        self.dac_walk = [0.0, 0.0, 0.0]
        self._srv = None
        self.counter_rate = 2.0                         # zero-dead-time counter samples per second

    # register helpers
    def _bus(self, addr):
        return self.regs.get(BASE + 4 * addr, 0)

    def _ref_hz(self, ch):
        lsb, msb = (0x8000, 0x8001) if ch == 0 else (0x8010, 0x8011)
        v = (self._bus(msb) << 32) + self._bus(lsb)
        if v > (1 << 47) - 1:
            v -= 1 << 48
        return v / 2 ** 48 * self.fs()

    def fs(self):
        m = (self.regs.get(AXI + 0x20200, 0x501) >> 8) & 0xFF
        d = self.regs.get(AXI + 0x20208, 8) & 0xFF
        ext = not (self.regs.get(AXI + 0x30000, 1) & 1)
        return (20e6 if ext else 200e6) * m / d if m and d else 125e6

    def locked(self, ch):
        return bool(self._bus(0x7000 if ch == 0 else 0x7010) & 1)

    def _read(self, a):
        if a == AXI + 0x20004:
            return 1                                    # clock wizard locked
        n = int((time.time() - self.t0) * self.counter_rate)
        if a == BASE + 0x30 * 4:
            return n & 0xFFFFFFFF
        if a in (BASE + 0x31 * 4, BASE + 0x32 * 4, BASE + 0x33 * 4, BASE + 0x34 * 4):
            ch = 0 if a < BASE + 0x33 * 4 else 1
            if getattr(self, '_cnt_n', None) != (n, ch):        # one value per counter sample, both halves consistent
                Nc = 125e6
                hz = self.rng.normal(0, 2e-3) if self.locked(ch) else self.rng.normal(3e5, 1e4)
                self._cnt_raw = int(hz / (125e6 / 2 ** 10 / (Nc * (Nc + 1)))) & 0xFFFFFFFFFFFFFFFF
                self._cnt_n = (n, ch)
            raw = self._cnt_raw
            return raw & 0xFFFFFFFF if a in (BASE + 0x31 * 4, BASE + 0x33 * 4) else raw >> 32
        if a in (BASE + 0x35 * 4, BASE + 0x36 * 4, BASE + 0x37 * 4):
            d = (a - BASE - 0x35 * 4) // 4
            if self.locked(0 if d == 0 else 1):
                self.dac_walk[d] += self.rng.normal(0, 30)
            v = int(np.clip(self.dac_walk[d], -30000, 30000)) + (30000 if d == 2 else 0)
            return v & 0xFFFFFFFF
        if a == AXI + 0x40000 or a == AXI + 0x40008 or a == AXI + 0x50000:
            # digital_clock_freq_counter: report ~20 MHz (internal 200 MHz reference), consistent index byte
            # inverse of SuperLaserLand.getExtClockFreq(): f = raw * f_ref / gain, gain = N(N+1) (triangular) or N
            ext = not (self.regs.get(AXI + 0x30000, 1) & 1)
            f = 20e6 * (1 + 3e-6) if ext else 0.0     # internal Zynq 200 MHz is not GPS-disciplined: a few ppm off
            N = 200e6
            gain = N * (N + 1) if self._bus(0x8501) & 1 else N
            raw = int(round(f * gain / 200e6))
            idx = (n & 0xFF) << 24
            if a == AXI + 0x40000:
                return idx | (raw & 0xFFFFFF)
            if a == AXI + 0x40008:
                return idx | ((raw >> 24) & 0xFFFFFF)
            return idx | ((raw >> 48) & 0xFFFF)
        return self.regs.get(a, 0)

    def _buffer(self, nsamp):
        mux = self._bus(0x3)
        k = np.arange(nsamp)
        if mux in (0, 1):
            f = abs(self._ref_hz(mux)) or 21.4e6
            x = 8000 * np.cos(2 * np.pi * f / self.fs() * k + self.rng.uniform(0, 6.28)) + self.rng.normal(0, 300, nsamp)
        elif mux in (2, 3):
            x = self.rng.normal(0, 40, nsamp)
        elif mux in (6, 7, 8):
            d = mux - 6
            x = -self.dac_walk[d] + self.rng.normal(0, 5, nsamp) + (30000 if d == 2 else 0)
        else:
            x = self.rng.normal(0, 100, nsamp)
        arr = np.clip(x, -32768, 32767).astype(np.int16) if mux != 8 else np.clip(x, 0, 65535).astype(np.uint16).view(np.int16)
        if mux in (0, 1) and nsamp > 8:
            arr[6], arr[7], arr[8] = 20000, 0, np.int16(-22385)
        return arr.tobytes()

    def _handle(self, c):
        def recvall(n):
            b = b''
            while len(b) < n:
                x = c.recv(n - len(b))
                if not x:
                    return None
                b += x
            return b
        with c:
            while True:
                h = recvall(12)
                if h is None:
                    return
                magic, a, d = struct.unpack('=III', h)
                if magic == WR:
                    with self.lock:
                        self.regs[a] = d; self.writes.append((a, d))
                        if BASE <= a < BASE + (1 << 20):
                            self.regs[a + (2 << 20)] = d
                elif magic == RD:
                    c.sendall(struct.pack('=I', self._read(a) & 0xFFFFFFFF))
                elif magic == BUF:
                    c.sendall(self._buffer(d))
                elif magic == WF:
                    recvall(a); recvall(d)
                elif magic == SH:
                    recvall(a)
                elif magic == RB:
                    pass
                else:
                    return

    def start(self):
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port)); s.listen(5)
        self._srv = s

        def loop():
            while True:
                try:
                    c, _ = s.accept()
                except OSError:
                    return
                threading.Thread(target=self._handle, args=(c,), daemon=True).start()
        threading.Thread(target=loop, daemon=True).start()
        return self

    def stop(self):
        if self._srv:
            self._srv.close()
