"""Vescent SLICE-OPL offset phase lock (USB serial, CR, ASCII).

Based on the SLICE-OPL Serial API Guide Rev 01 (SC 1.242 / OPL 1.27). Method
names match the original ``sliceopl.py``. Two units are on the bench, so every
unit is identified by the serial number in its *IDN? reply.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from vescentcomb.core.base import Device, Identity, SafetyError
from vescentcomb.core.serialio import SerialLine

INTEGRATOR_CORNERS_HZ = (0, 50, 100, 200, 500, 1e3, 2e3, 5e3, 10e3, 20e3, 50e3,
                         100e3, 200e3, 500e3, 1e6, 2e6, 5e6)
RAIL_V = 12.0


class SliceOPL(Device):
    KIND = "sliceopl"
    LABEL = "Vescent SLICE-OPL"
    RESTORABLE = ("target_beatnote", "pll_invert", "pll_gain", "integrator_corner",
                  "diff_corner", "gain_clamp", "pll_bias", "pll_min", "pll_max",
                  "lock_range", "aux_invert", "aux_target", "aux_gain", "aux_bias",
                  "aux_min", "aux_max", "bn_max", "n1", "n2", "ext_ref_bw",
                  "pfd_uses_dds", "dds_internal", "dds_ref_freq", "m1", "m2")

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200,
                 timeout: float = 1.0, ser=None):
        super().__init__()
        self.line = SerialLine(port, baudrate, timeout, eol="\r", ser=ser)
        self.address = self.line.port

    @property
    def ser(self):
        return self.line.ser

    def close(self) -> None:
        self.line.close()

    # ---- low level ---------------------------------------------------------------
    def query(self, cmd: str) -> str:
        return self.line.query(cmd)

    def command(self, cmd: str) -> str:
        return self.line.query(cmd)

    def query_value(self, cmd: str) -> str:
        resp = self.query(cmd).replace("\r", " ").replace("\n", " ")
        toks = resp.split()
        return toks[-1] if toks else ""

    def query_float(self, cmd: str):
        v = self.query_value(cmd)
        try:
            return float(v)
        except ValueError:
            return v

    def query_int(self, cmd: str):
        v = self.query_value(cmd)
        try:
            return int(float(v))
        except ValueError:
            return v

    @staticmethod
    def _on(v) -> bool:
        return str(v).strip().lower() in ("on", "1", "true")

    # ================= GLOBAL =================
    def idn(self) -> str:
        return self.query("*IDN?")

    def identify(self) -> Identity:
        raw = self.idn()
        parts = [p.strip() for p in raw.replace("\r", ",").replace("\n", ",").split(",") if p.strip()]
        model = parts[1] if len(parts) > 1 else "SLICE-OPL"
        serial = parts[2] if len(parts) > 2 else ""
        fw = " / ".join(parts[3:5]) if len(parts) > 3 else ""
        return Identity(self.KIND, model=model, serial=serial, firmware=fw, raw=raw)

    def reset(self) -> str:
        return self.command("*RST")

    def get_backlight(self): return self.query_int("#SCBKLT?")
    def set_backlight(self, level): return self.command(f"#SCBKLT {int(level)}")
    def get_volume(self): return self.query_int("#SCVOL?")
    def set_volume(self, level): return self.command(f"#SCVOL {int(level)}")

    def flash_identify(self, cycles: int = 3, period_s: float = 0.4) -> None:
        """Blink the front-panel backlight so you can see which box this is."""
        orig = self.get_backlight()
        try:
            for _ in range(cycles):
                self.set_backlight(0)
                time.sleep(period_s / 2)
                self.set_backlight(100)
                time.sleep(period_s / 2)
        finally:
            if isinstance(orig, int):
                self.set_backlight(orig)

    # ============ GENERAL OPERATION ============
    def get_servo(self): return self.query_value("SERVO?")
    def servo_on(self) -> bool: return self._on(self.get_servo())
    def set_servo(self, on): return self.command(f"SERVO {'ON' if on else 'OFF'}")

    def get_target_beatnote(self): return self.query_float("BNTGT?")

    def set_target_beatnote(self, mhz):
        mhz = float(mhz)
        if not (10.0 <= mhz <= 20000.0):
            raise SafetyError("target beat note must be 10–20000 MHz")
        return self.command(f"BNTGT {mhz}")

    ADC = {"error": 1, "error_8x": 2, "integrator": 3, "pll_out": 4, "aux_out": 5,
           "vga_in": 6, "vga_out": 7, "ground": 8}

    def read_voltage(self, channel):
        ch = self.ADC.get(channel, channel)
        return self.query_float(f"READVOLT {int(ch)}")

    def read_all_voltages(self) -> Dict[str, Any]:
        return {name: self.read_voltage(name) for name in self.ADC}

    # ============ PLL SERVO FILTER ============
    def get_pll_invert(self): return self.query_value("PLLINVT?")
    def set_pll_invert(self, on): return self.command(f"PLLINVT {'ON' if self._on(on) or on is True else 'OFF'}")
    def get_pll_gain(self): return self.query_float("PLLGAIN?")
    def set_pll_gain(self, db): return self.command(f"PLLGAIN {float(db)}")
    def get_integrator_corner(self): return self.query_float("INT?")

    def set_integrator_corner(self, hz):
        hz = float(hz)
        if hz not in INTEGRATOR_CORNERS_HZ:
            hz = min(INTEGRATOR_CORNERS_HZ, key=lambda c: abs(c - hz))
        return self.command(f"INT {hz}")

    def get_diff_corner(self): return self.query_float("DIFF?")
    def set_diff_corner(self, hz): return self.command(f"DIFF {float(hz)}")
    def get_gain_clamp(self): return self.query_value("GAINLIM?")
    def set_gain_clamp(self, on): return self.command(f"GAINLIM {'ON' if self._on(on) or on is True else 'OFF'}")
    def get_pll_bias(self): return self.query_float("PLLBIAS?")

    def set_pll_bias(self, volts):
        v = float(volts)
        if abs(v) > RAIL_V:
            raise SafetyError(f"PLL bias {v} V outside ±{RAIL_V} V")
        return self.command(f"PLLBIAS {v}")

    def get_pll_max(self): return self.query_float("PLLMAX?")

    def set_pll_max(self, volts):
        v = float(volts)
        mn = self.get_pll_min()
        if abs(v) > RAIL_V:
            raise SafetyError(f"PLLMAX {v} V outside ±{RAIL_V} V")
        if isinstance(mn, float) and v <= mn:
            raise SafetyError(f"PLLMAX {v} V must be above PLLMIN {mn} V")
        return self.command(f"PLLMAX {v}")

    def get_pll_min(self): return self.query_float("PLLMIN?")

    def set_pll_min(self, volts):
        v = float(volts)
        mx = self.get_pll_max()
        if abs(v) > RAIL_V:
            raise SafetyError(f"PLLMIN {v} V outside ±{RAIL_V} V")
        if isinstance(mx, float) and v >= mx:
            raise SafetyError(f"PLLMIN {v} V must be below PLLMAX {mx} V")
        return self.command(f"PLLMIN {v}")

    def set_pll_limits(self, vmin: float, vmax: float, bias: Optional[float] = None) -> None:
        """Set min/max (and optionally bias) in an order that never violates min<max."""
        if not (-RAIL_V <= vmin < vmax <= RAIL_V):
            raise SafetyError(f"need -{RAIL_V} ≤ min < max ≤ {RAIL_V} V")
        cur_max = self.get_pll_max()
        if isinstance(cur_max, float) and vmin >= cur_max:
            self.set_pll_max(vmax)
            self.set_pll_min(vmin)
        else:
            self.set_pll_min(vmin)
            self.set_pll_max(vmax)
        if bias is not None:
            if not (vmin <= bias <= vmax):
                raise SafetyError("bias must lie between min and max")
            self.set_pll_bias(bias)

    def get_lock_range(self): return self.query_float("LOCKRNG?")
    def set_lock_range(self, volts): return self.command(f"LOCKRNG {float(volts)}")

    # ============ AUX SERVO FILTER ============
    def get_aux_enabled(self): return self.query_value("AUXEN?")
    def set_aux_enabled(self, on): return self.command(f"AUXEN {'ON' if on else 'OFF'}")
    def get_aux_invert(self): return self.query_value("AUXINVT?")
    def set_aux_invert(self, on): return self.command(f"AUXINVT {'ON' if self._on(on) or on is True else 'OFF'}")
    def get_aux_target(self): return self.query_float("AUXTGT?")
    def set_aux_target(self, volts): return self.command(f"AUXTGT {float(volts)}")
    def get_aux_gain(self): return self.query_float("AUXGAIN?")
    def set_aux_gain(self, g): return self.command(f"AUXGAIN {float(g)}")
    def get_aux_bias(self): return self.query_float("AUXBIAS?")
    def set_aux_bias(self, volts): return self.command(f"AUXBIAS {float(volts)}")
    def get_aux_max(self): return self.query_float("AUXMAX?")
    def set_aux_max(self, volts): return self.command(f"AUXMAX {float(volts)}")
    def get_aux_min(self): return self.query_float("AUXMIN?")
    def set_aux_min(self, volts): return self.command(f"AUXMIN {float(volts)}")

    # ================= SWEEP =================
    def get_ramp(self): return self.query_value("RAMP?")
    def set_ramp(self, on): return self.command(f"RAMP {'ON' if on else 'OFF'}")
    def get_ramp_channel(self): return self.query_int("RAMPCH?")
    def set_ramp_channel(self, ch): return self.command(f"RAMPCH {int(ch)}")
    def get_ramp_points(self): return self.query_int("RAMPNUM?")
    def set_ramp_points(self, n): return self.command(f"RAMPNUM {int(n)}")
    def get_ramp_freq(self): return self.query_float("RAMPFRQ?")
    def set_ramp_freq(self, hz): return self.command(f"RAMPFRQ {float(hz)}")
    def get_ramp_range(self): return self.query_float("RAMPSWP?")
    def set_ramp_range(self, volts): return self.command(f"RAMPSWP {float(volts)}")
    def get_ramp_adc_gain(self): return self.query_int("RAMPADC?")
    def set_ramp_adc_gain(self, mode): return self.command(f"RAMPADC {int(mode)}")

    # ============ BEAT NOTE INPUT ============
    def get_bn_max(self): return self.query_float("BNMAX?")
    def set_bn_max(self, mhz): return self.command(f"BNMAX {float(mhz)}")
    def get_n1(self): return self.query_int("N1DIV?")
    def set_n1(self, val): return self.command(f"N1DIV {int(val)}")
    def get_n2(self): return self.query_int("N2DIV?")
    def set_n2(self, val): return self.command(f"N2DIV {int(val)}")
    def read_beatnote(self): return self.query_float("READBN?")

    # ============ REFERENCE SOURCE ============
    def read_reference(self): return self.query_float("READREF?")
    def get_ext_ref_bw(self): return self.query_float("EREFBWL?")
    def set_ext_ref_bw(self, mhz): return self.command(f"EREFBWL {float(mhz)}")
    def get_pfd_uses_dds(self): return self.query_value("PFDDDS?")
    def set_pfd_uses_dds(self, on): return self.command(f"PFDDDS {'ON' if self._on(on) or on is True else 'OFF'}")
    def get_dds_internal(self): return self.query_value("DDSINT?")
    def set_dds_internal(self, on): return self.command(f"DDSINT {'ON' if self._on(on) or on is True else 'OFF'}")
    def get_dds_ref_freq(self): return self.query_float("DDSREFF?")
    def set_dds_ref_freq(self, mhz): return self.command(f"DDSREFF {float(mhz)}")
    def get_m1(self): return self.query_int("M1DIV?")
    def set_m1(self, val): return self.command(f"M1DIV {int(val)}")
    def get_m2(self): return self.query_int("M2DIV?")
    def set_m2(self, val): return self.command(f"M2DIV {int(val)}")
    def dds_auto(self): return self.command("DDSAUTO")

    # ============ EXTERNAL I/O / TRIGGER ============
    def get_rear_mux(self): return self.query_int("MUXO?")
    def set_rear_mux(self, val): return self.command(f"MUXO {int(val)}")
    def get_front_out1(self): return self.query_value("FP1EN?")
    def set_front_out1(self, on): return self.command(f"FP1EN {'ON' if on else 'OFF'}")
    def get_front_out2(self): return self.query_value("FP2EN?")
    def set_front_out2(self, on): return self.command(f"FP2EN {'ON' if on else 'OFF'}")
    def get_front_out2_mux(self): return self.query_int("FPMUXO?")
    def set_front_out2_mux(self, val): return self.command(f"FPMUXO {int(val)}")
    def get_front_in_a(self): return self.query_value("FPAINEN?")
    def set_front_in_a(self, on): return self.command(f"FPAINEN {'ON' if on else 'OFF'}")
    def get_front_in_b(self): return self.query_value("FPBINEN?")
    def set_front_in_b(self, on): return self.command(f"FPBINEN {'ON' if on else 'OFF'}")
    def get_trigger_in(self): return self.query_int("TRIGI?")
    def set_trigger_in(self, mode): return self.command(f"TRIGI {int(mode)}")
    def get_trigger_out(self): return self.query_int("TRIGO?")
    def set_trigger_out(self, mode): return self.command(f"TRIGO {int(mode)}")

    # ================= ADVANCED =================
    def integrator_hold(self, on): return self.command(f"HOLD {'ON' if on else 'OFF'}")
    def get_integrator_hold(self): return self.query_value("HOLD?")
    def disable_cp(self): return self.command("NOCP")
    def get_dds_freq(self): return self.query_float("DDSFREQ?")
    def set_dds_freq(self, mhz): return self.command(f"DDSFREQ {float(mhz)}")
    def get_dds_raw(self): return self.query_int("DDSRAW?")
    def set_dds_raw(self, raw): return self.command(f"DDSRAW {int(raw)}")

    # ---- derived ----------------------------------------------------------------
    def beat_error_hz(self, counter_offset_mhz: float = 0.0) -> Optional[float]:
        """(target - offset - measured) in Hz. Positive = beat is LOW."""
        t = self.get_target_beatnote()
        b = self.read_beatnote()
        if not isinstance(t, float) or not isinstance(b, float):
            return None
        return (t - counter_offset_mhz - b) * 1e6

    def has_beat(self, min_mhz: float = 1.0) -> bool:
        b = self.read_beatnote()
        return isinstance(b, float) and b > min_mhz

    # ---- snapshot / poll ----------------------------------------------------------
    def poll(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "servo_on": self.servo_on(),
                "target_beatnote": self.get_target_beatnote(),
                "beatnote": self.read_beatnote(),
                "reference": self.read_reference(),
                "error_v": self.read_voltage("error"),
                "pll_out_v": self.read_voltage("pll_out"),
                "pll_min": self.get_pll_min(),
                "pll_max": self.get_pll_max(),
                "hold": self._on(self.get_integrator_hold()),
            }

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            g = {
                "target_beatnote": self.get_target_beatnote(),
                "pll_invert": self._on(self.get_pll_invert()),
                "pll_gain": self.get_pll_gain(),
                "integrator_corner": self.get_integrator_corner(),
                "diff_corner": self.get_diff_corner(),
                "gain_clamp": self._on(self.get_gain_clamp()),
                "pll_bias": self.get_pll_bias(),
                "pll_min": self.get_pll_min(),
                "pll_max": self.get_pll_max(),
                "lock_range": self.get_lock_range(),
                "aux_enabled": self._on(self.get_aux_enabled()),
                "aux_invert": self._on(self.get_aux_invert()),
                "aux_target": self.get_aux_target(),
                "aux_gain": self.get_aux_gain(),
                "aux_bias": self.get_aux_bias(),
                "aux_min": self.get_aux_min(),
                "aux_max": self.get_aux_max(),
                "ramp": self._on(self.get_ramp()),
                "bn_max": self.get_bn_max(),
                "n1": self.get_n1(), "n2": self.get_n2(),
                "ext_ref_bw": self.get_ext_ref_bw(),
                "pfd_uses_dds": self._on(self.get_pfd_uses_dds()),
                "dds_internal": self._on(self.get_dds_internal()),
                "dds_ref_freq": self.get_dds_ref_freq(),
                "m1": self.get_m1(), "m2": self.get_m2(),
                "servo_on": self.servo_on(),
            }
            return g

    def _setter_for(self, key):
        fn = getattr(self, f"set_{key}", None)
        return fn

    def safe_state(self) -> None:
        """Servo state is left alone: dropping a lock on disconnect would be worse."""
