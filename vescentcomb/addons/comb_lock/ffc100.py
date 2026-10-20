"""Vescent FFC-100 fiber frequency comb (USB serial, CR LF, ASCII).

Command tokens were found empirically on SN 000046, fw S-V1.205. Public method
names match the original ``ffc100.py`` so existing notebooks keep working.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional, Tuple

from vescentcomb.core.base import Device, DeviceError, Identity, SafetyError
from vescentcomb.core.serialio import SerialLine


class FFC100(Device):
    KIND = "ffc100"
    LABEL = "Vescent FFC-100 comb"
    STATE = {0: "OFF", 1: "STANDBY", 2: "LASER ON"}
    # PZTMOMD codes as the FFC-100 front panel uses them (bench check: 0 turned the PZT off, 1 gave ×1)
    PZT_MODE = {0: "off", 1: "full range ×1", 2: "full range ×10"}
    RESTORABLE = ("cav_setpoint", "pzt_mode", "dc_bias_setpoint",
                  "slow_servo_gain", "slow_servo_offset")
    #: cavity setpoint guard band (deg C). Writes outside are refused.
    CAV_SETPOINT_RANGE = (15.0, 45.0)

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200,
                 timeout: float = 2.0, ser=None):
        super().__init__()
        self.line = SerialLine(port, baudrate, timeout, eol="\r\n", ser=ser)
        self.address = self.line.port

    # ---- low level -------------------------------------------------------------
    @property
    def ser(self):  # backwards compatibility with the notebook driver
        return self.line.ser

    def close(self) -> None:
        self.line.close()

    def query(self, cmd: str) -> str:
        return self.line.query(cmd)

    @staticmethod
    def value(raw: str, cmd: str) -> str:
        tok = cmd.split()[0]
        s = raw.strip()
        for t in (tok, tok.rstrip("?")):      # replies may echo 'TOKEN?' or 'TOKEN'
            if t and s.lower().startswith(t.lower()):
                s = s[len(t):].strip()
                break
        return s

    _NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

    @staticmethod
    def _reject(raw: str) -> bool:
        return raw.strip().lower() == "invalid command"

    def query_value(self, cmd: str) -> str:
        raw = self.query(cmd)
        if self._reject(raw):
            raise DeviceError(f"{cmd!r} rejected: {raw!r}")
        return self.value(raw, cmd)

    def query_float(self, cmd: str) -> Optional[float]:
        m = self._NUM.findall(self.query_value(cmd))
        return float(m[-1]) if m else None

    def query_int(self, cmd: str) -> Optional[int]:
        m = self._NUM.findall(self.query_value(cmd))
        return int(float(m[-1])) if m else None

    # ---- identity ---------------------------------------------------------------
    def idn(self) -> str:
        return self.query("*IDN?")

    def version(self) -> str:
        return self.query_value("#VERSION")

    def identify(self) -> Identity:
        raw = self.idn()
        parts = [p.strip() for p in raw.split(",")]
        serial = parts[2] if len(parts) > 2 else ""
        model = parts[1] if len(parts) > 1 else "FFC-100"
        fw = parts[3] if len(parts) > 3 else ""
        return Identity(self.KIND, model=model, serial=serial, firmware=fw, raw=raw)

    # ---- laser state ------------------------------------------------------------
    def get_state(self) -> Optional[int]:
        return self.query_int("MSTRCTL?")

    def get_state_name(self) -> str:
        return self.STATE.get(self.get_state(), "?")

    def set_state(self, n: int, force: bool = False) -> str:
        n = int(n)
        cur = self.get_state()
        if n == 2 and cur != 1 and not force:
            raise SafetyError(f"Refusing LASER ON from {self.STATE.get(cur)}; STANDBY first.")
        if n == 0 and cur == 2 and not force:
            raise SafetyError("Refusing abrupt OFF while lasing; go to STANDBY first.")
        return self.query(f"MSTRCTL {n}")

    def standby(self) -> str:
        return self.set_state(1)

    def laser_on(self) -> str:
        return self.set_state(2)

    def shutdown(self, wait_s: float = 0.5) -> str:
        """LASER ON -> STANDBY -> OFF, never a direct OFF while lasing."""
        if self.get_state() == 2:
            self.set_state(1)
            time.sleep(wait_s)
        return self.set_state(0)

    # ---- pump currents (read-only) -----------------------------------------------
    def osc_current(self): return self.query_float("OSCCURR?")
    def amp_current(self): return self.query_float("AMPCURR?")

    # ---- temperatures ----------------------------------------------------------------
    def osc_temp(self): return self.query_float("OSCTEMP?")
    def osc_temp_error(self): return self.query_float("OSCTERR?")
    def amp_temp(self): return self.query_float("AMPTEMP?")
    def amp_temp_error(self): return self.query_float("AMPTERR?")
    def cav_temp(self): return self.query_float("CAVTEMP?")
    def cav_temp_error(self): return self.query_float("CAVTERR?")

    # ---- cavity setpoint (main f_rep tuning knob) ---------------------------------
    def cav_setpoint(self): return self.query_float("CATSETP?")

    def set_cav_setpoint(self, deg_c: float) -> str:
        lo, hi = self.CAV_SETPOINT_RANGE
        if not (lo <= float(deg_c) <= hi):
            raise SafetyError(f"cavity setpoint {deg_c} °C outside guard band {lo}–{hi} °C")
        return self.query(f"CATSETP {float(deg_c)}")

    # ---- PZT ------------------------------------------------------------------------
    def pzt_mode(self) -> Tuple[Optional[int], str]:
        c = self.query_int("PZTMOMD?")
        return c, self.PZT_MODE.get(c, "?")

    def set_pzt_mode(self, code) -> str:
        if isinstance(code, (list, tuple)):
            code = code[0]
        code = int(code)
        if code not in self.PZT_MODE:
            raise ValueError("PZTMOMD code must be 0 (off), 1 (×1) or 2 (×10)")
        return self.query(f"PZTMOMD {code}")

    def set_pzt_gain(self, x10: bool) -> str:
        return self.set_pzt_mode(2 if x10 else 1)

    def dc_bias_setpoint(self): return self.query_float("CADCBSP?")

    def set_dc_bias_setpoint(self, volts: float) -> str:
        """Keep at 0 V while a SLICE is locking — bias adds onto the PZT output."""
        return self.query(f"CADCBSP {float(volts)}")

    def pzt_output_voltage(self): return self.query_float("CADCBV?")

    # ---- mode lock --------------------------------------------------------------------
    def mode_locked(self) -> bool:
        """MODELOK? ON *and* the laser is on (MSTRCTL 2): with the laser off the comb can still
        report the last MODELOK state."""
        if self.query_value("MODELOK?").strip().lower() not in ("on", "1"):
            return False
        return self.get_state() == 2

    # ---- slow servo ---------------------------------------------------------------------
    def slow_servo(self) -> str: return self.query_value("SLSRVEN?")
    def slow_servo_on(self) -> bool:
        return self.slow_servo().strip().lower() in ("1", "on")
    def set_slow_servo(self, on: bool) -> str: return self.query(f"SLSRVEN {1 if on else 0}")
    def slow_servo_gain(self): return self.query_float("SLSRVGN?")
    def set_slow_servo_gain(self, db: float) -> str: return self.query(f"SLSRVGN {float(db)}")
    def slow_servo_offset(self): return self.query_float("SLSRVOS?")
    def set_slow_servo_offset(self, v: float) -> str: return self.query(f"SLSRVOS {float(v)}")

    # ---- snapshot / poll -------------------------------------------------------------
    def poll(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self.get_state_name(),
                "mode_locked": self.mode_locked(),
                "cav_temp": self.cav_temp(),
                "cav_setpoint": self.cav_setpoint(),
                "pzt_output": self.pzt_output_voltage(),
                "slow_servo_on": self.slow_servo_on(),
            }

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            code, _ = self.pzt_mode()
            return {
                "idn": self.idn(),
                "state": self.get_state_name(),
                "mode_locked": self.mode_locked(),
                "osc_current": self.osc_current(),
                "amp_current": self.amp_current(),
                "osc_temp": self.osc_temp(), "osc_temp_error": self.osc_temp_error(),
                "amp_temp": self.amp_temp(), "amp_temp_error": self.amp_temp_error(),
                "cav_temp": self.cav_temp(), "cav_temp_error": self.cav_temp_error(),
                "cav_setpoint": self.cav_setpoint(),
                "pzt_mode": code,
                "dc_bias_setpoint": self.dc_bias_setpoint(),
                "pzt_output": self.pzt_output_voltage(),
                "slow_servo_on": self.slow_servo_on(),
                "slow_servo_gain": self.slow_servo_gain(),
                "slow_servo_offset": self.slow_servo_offset(),
            }

    # restore() uses set_<key>; map the two whose names differ
    def _setter_for(self, key):
        return {"cav_setpoint": self.set_cav_setpoint,
                "pzt_mode": self.set_pzt_mode,
                "dc_bias_setpoint": self.set_dc_bias_setpoint,
                "slow_servo_gain": self.set_slow_servo_gain,
                "slow_servo_offset": self.set_slow_servo_offset}.get(key)

    def safe_state(self) -> None:
        """The comb is left as it is: shutting it down is a deliberate act."""
