"""Simulator for this add-on: models answer the same commands as the real instrument."""
from __future__ import annotations

import math
import re
import struct
import time
from typing import Any, Dict, Optional

import numpy as np

from vescentcomb.core.serialio import PortInfo
from vescentcomb.sim.base import RNG, SCPIModel, TextDevice, null_generator, num as _num


class FFCModel(TextDevice):
    eol = "\r\n"

    def __init__(self, world):
        self.w = world
        self.state = 2
        self.cav_set = 31.1320
        self._cav = 31.1320
        self._t = time.time()
        self.pzt_mode = 2
        self.dc_bias = 0.0
        self.slow_en = 0
        self.slow_gain = -20.0
        self.slow_off = 0.0

    def cav_temp(self) -> float:
        now = time.time()
        dt = (now - self._t) * self.w.speed
        self._t = now
        tau = self.w.cavity_tau_s
        self._cav += (self.cav_set - self._cav) * (1 - math.exp(-dt / tau))
        return self._cav

    def handle(self, cmd: str) -> Optional[str]:
        c = cmd.upper()
        tok = c.split()[0]
        arg = cmd.split()[1] if len(cmd.split()) > 1 else None
        T = self.cav_temp()
        if tok == "*IDN?":
            return "Vescent Photonics,FFC-100,000046,S-V1.205"
        if tok == "#VERSION":
            return "#VERSION S-V1.205"
        if tok == "MSTRCTL?":
            return f"MSTRCTL {self.state}"
        if tok == "MSTRCTL":
            self.state = int(_num(arg)); return "OK"
        if tok == "MODELOK?":
            return "MODELOK ON" if self.state == 2 else "MODELOK OFF"
        table = {"OSCCURR?": 412.0 + RNG.normal(0, 0.2), "AMPCURR?": 1180.0 + RNG.normal(0, 0.5),
                 "OSCTEMP?": 25.003, "OSCTERR?": 0.003, "AMPTEMP?": 24.998, "AMPTERR?": -0.002,
                 "CAVTEMP?": T + RNG.normal(0, 0.00005), "CAVTERR?": T - self.cav_set,
                 "CATSETP?": self.cav_set, "CADCBSP?": self.dc_bias,
                 "CADCBV?": self.w.pzt_out(), "SLSRVGN?": self.slow_gain, "SLSRVOS?": self.slow_off}
        if tok in table:
            return f"{tok[:-1]} {table[tok]:.6f}"
        if tok == "CATSETP":
            self.cav_set = _num(arg); return "OK"
        if tok == "PZTMOMD?":
            return f"PZTMOMD {self.pzt_mode}"
        if tok == "PZTMOMD":
            self.pzt_mode = int(_num(arg)); return "OK"
        if tok == "CADCBSP":
            self.dc_bias = _num(arg); return "OK"
        if tok == "SLSRVEN?":
            return f"SLSRVEN {'ON' if self.slow_en else 'OFF'}"
        if tok == "SLSRVEN":
            self.slow_en = int(_num(arg)); return "OK"
        if tok == "SLSRVGN":
            self.slow_gain = _num(arg); return "OK"
        if tok == "SLSRVOS":
            self.slow_off = _num(arg); return "OK"
        return "Invalid Command"

class OPLModel(TextDevice):
    eol = "\r\n"
    COUNTER_LOW_HZ = 31.0   # the OPL counter reads ~31 Hz low (approximate counter)

    def __init__(self, world, serial: str, target_mhz: float, has_beat: bool = True,
                 pll=(0.0, 10.0, 5.0)):
        self.w = world
        self.serial = serial
        self.p: Dict[str, Any] = {
            "SERVO": "OFF", "BNTGT": target_mhz, "PLLINVT": "OFF", "PLLGAIN": -55.0,
            "INT": 100.0, "DIFF": 0.0, "GAINLIM": "OFF", "PLLBIAS": pll[2], "PLLMAX": pll[1],
            "PLLMIN": pll[0], "LOCKRNG": 0.1, "AUXEN": "OFF", "AUXINVT": "OFF", "AUXTGT": 5.0,
            "AUXGAIN": 1.0, "AUXBIAS": 0.0, "AUXMAX": 10.0, "AUXMIN": 0.0, "RAMP": "OFF",
            "RAMPCH": 0, "RAMPNUM": 200, "RAMPFRQ": 10.0, "RAMPSWP": 1.0, "RAMPADC": 128,
            "BNMAX": 1000.0, "N1DIV": 1, "N2DIV": 100, "EREFBWL": 12.0, "PFDDDS": "ON",
            "DDSINT": "OFF", "DDSREFF": 10.0, "M1DIV": 1, "M2DIV": 1, "MUXO": 0, "FP1EN": "OFF",
            "FP2EN": "OFF", "FPMUXO": 1, "FPAINEN": "OFF", "FPBINEN": "OFF", "TRIGI": 0,
            "TRIGO": 0, "HOLD": "OFF", "DDSFREQ": 10.0, "DDSRAW": 0,
            "#SCBKLT": 80, "#SCVOL": 20,
        }
        self.has_beat = has_beat
        self.locked = False

    # physics -------------------------------------------------------------------------
    def true_beat_hz(self) -> float:
        tgt = self.p["BNTGT"] * 1e6
        if not self.has_beat:
            return 0.0
        if self.locked:
            return tgt
        return tgt + self.w.beat_offset_hz(self)

    def servo_quality(self):
        """Lock lost above about -43 dB gain (used by the auto-tune simulation)."""
        return self.p["PLLGAIN"] <= -43.0

    def update_lock(self):
        if self.p["SERVO"] != "ON" or not self.has_beat:
            self.locked = False
            return
        if not self.locked:
            off = abs(self.w.beat_offset_hz(self))
            self.locked = off < getattr(self, "CAPTURE_HZ", 300.0) and self.servo_quality()
        elif not self.servo_quality():
            self.locked = False

    def handle(self, cmd: str) -> Optional[str]:
        self.update_lock()
        parts = cmd.split()
        tok = parts[0].upper()
        arg = parts[1] if len(parts) > 1 else None
        if tok == "*IDN?":
            return f"Vescent Photonics,SLICE-OPL,{self.serial},SC 1.242,OPL 1.27"
        if tok == "*RST":
            return "OK"
        if tok == "READBN?":
            if not self.has_beat:
                return "READBN 0.000000"
            b = self.true_beat_hz() - self.COUNTER_LOW_HZ + RNG.normal(0, 2.0)
            return f"READBN {b / 1e6:.6f}"
        if tok == "READREF?":
            return "READREF 10.000000"
        if tok == "READVOLT":
            ch = int(_num(arg or "1"))
            lo, hi = self.p["PLLMIN"], self.p["PLLMAX"]
            if self.locked:
                err, out = RNG.normal(0.012, 0.002), self.p["PLLBIAS"] + 0.21
            elif self.p["SERVO"] == "ON":
                err, out = 2.5, hi
            else:
                err, out = RNG.normal(0, 0.3), self.p["PLLBIAS"]
            vals = {1: err, 2: err * 8, 3: out - self.p["PLLBIAS"], 4: out, 5: 0.0,
                    6: 0.3, 7: 0.9, 8: 0.0}
            return f"READVOLT {vals.get(ch, 0.0):.4f}"
        if tok == "NOCP":
            self.p["HOLD"] = "ON"; return "OK"
        if tok == "DDSAUTO":
            return "OK"
        if tok.endswith("?"):
            key = tok[:-1]
            if key in self.p:
                return f"{key} {self.p[key]}"
            return "ERR"
        if tok in self.p:
            v = arg
            if isinstance(self.p[tok], (int, float)) and not isinstance(self.p[tok], bool):
                v = type(self.p[tok])(float(arg))
            else:
                v = str(arg).upper()
            self.p[tok] = v
            if tok == "SERVO":
                self.update_lock()
            return "OK"
        return "ERR"

def make_fpga_simulator():
    """The package's own SLICE-FPGA-II stand-in (real TCP protocol on 127.0.0.1), with in-loop
    frequency noise scaled so a locked f_ceo integrates to ~0.4 rad like the real box."""
    import socket
    from .fpga.simulator import SliceSimulator

    class BenchSliceSimulator(SliceSimulator):
        def _buffer(self, nsamp):
            mux = self._bus(0x3)
            if mux in (2, 3):                       # DDC0 / DDC1 instantaneous frequency
                sigma = 8.0 if self.locked(mux - 2) else 400.0
                x = self.rng.normal(0, sigma, nsamp)
                return np.clip(x, -32768, 32767).astype(np.int16).tobytes()
            return super()._buffer(nsamp)

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return BenchSliceSimulator(port=port).start()



BEAT_HZ_PER_C = 3000.0      # Hz of OPL #1 beat per °C of cavity temperature (notebook run: ~15 Hz per 5 mK)


def install(world) -> None:
    """FFC-100 on COM3, OPL #1 on COM4, SLICE-FPGA-II (the package's own TCP stand-in)."""
    from vescentcomb.discovery import HOOKS
    world.BEAT_HZ_PER_C = BEAT_HZ_PER_C
    world.ffc = FFCModel(world)
    # temperature at which the OPL #1 beat equals its target: start ~931 Hz high, like the notebook run
    world.t_lock = world.ffc.cav_set + 931.0 / BEAT_HZ_PER_C
    world.opl1 = OPLModel(world, "OPL-0001", 100.0, has_beat=True, pll=(0.0, 10.0, 5.0))
    world.models.update(ffc=world.ffc, opl1=world.opl1)

    base_offset = world.beat_offset_hz

    def beat_offset_hz(opl):
        if opl is world.opl1:
            return BEAT_HZ_PER_C * (world.t_lock - world.ffc.cav_temp())
        return base_offset(opl)

    def beat_phase_rms():
        g, corner = world.opl1.p["PLLGAIN"], world.opl1.p["INT"]
        base = {100.0: 0.35, 200.0: 0.31, 500.0: 0.40}.get(corner, 0.45)
        return base + 0.006 * (g + 52) ** 2 if world.opl1.locked else 6.0

    world.beat_offset_hz = beat_offset_hz
    world.beat_phase_rms = beat_phase_rms
    world.pzt_out = lambda: 30.4 if world.opl1.locked else 30.0
    world.add_rf_line(lambda: [(100e6, -20.0)])
    world.add_serial(PortInfo("COM3", "USB Serial Device (COM3)", "USB VID:PID=1FC9:0083 SER=FFC000046",
                              0x1FC9, 0x0083, "FFC000046"), world.ffc, b"\r")
    world.add_serial(PortInfo("COM4", "USB Serial Device (COM4)", "USB VID:PID=1FC9:0084 SER=OPL0001",
                              0x1FC9, 0x0084, "OPL0001"), world.opl1, b"\r")

    # SLICE-FPGA-II: config pushed, 20 MHz external clock, f_ceo locked — like the running box
    world.fpga_sim = make_fpga_simulator()
    world.on_uninstall(world.fpga_sim.stop)
    from .fpga import SliceFPGA
    box = SliceFPGA("127.0.0.1", world.fpga_sim.port)
    box.push_config(clock=("external", 20e6))
    box.lock("ceo")
    box.close()
    HOOKS.set("slicefpga.discover", lambda: [{"host": "192.168.0.150", "mac": "00:26:32:f0:a9:6b"}])
    HOOKS.set("slicefpga.impl_factory", lambda host: SliceFPGA("127.0.0.1", world.fpga_sim.port))
