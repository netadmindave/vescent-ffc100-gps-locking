"""Comb status file: what the Laser Lock application reads to know the comb is locked.

Written next to the settings file (``comb_status.json``) at most once a second from the
polled FFC-100, OPL #1 and SLICE-FPGA-II readings. Atomic replace, plain JSON.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

FILENAME = "comb_status.json"


def _num(x):
    return x if isinstance(x, (int, float)) and x == x else None


class StatusWriter:
    def __init__(self, hub, settings, period_s: float = 1.0):
        self.hub, self.period_s = hub, period_s
        self.path = os.path.join(os.path.dirname(str(settings.path)), FILENAME)
        self._t = 0.0
        hub.polled.connect(self._on_poll)

    def snapshot(self) -> Dict[str, Any]:
        from . import __version__
        h = self.hub
        ffc, o1, fp = h.last("ffc"), h.last("opl1"), h.last("fpga")
        have = {r: h.has(r) for r in ("ffc", "opl1", "fpga")}
        beat = _num(o1.get("beatnote"))
        frep_ok = bool(have["opl1"] and o1.get("servo_on") and beat is not None and beat > 1)
        ceo_ok = bool(fp.get("ceo_locked")) if have["fpga"] else None
        ml = bool(ffc.get("mode_locked")) if have["ffc"] else None
        return {
            "app": "vescentcomb", "version": __version__, "t": time.time(),
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "connected": have,
            "ffc": {"mode_locked": ml, "slow_servo_on": ffc.get("slow_servo_on"), "state": ffc.get("state")},
            "opl1": {"servo_on": o1.get("servo_on"), "beatnote_mhz": beat,
                     "target_beatnote_mhz": _num(o1.get("target_beatnote")),
                     "reference_mhz": _num(o1.get("reference")), "frep_locked": frep_ok},
            "fpga": {"ceo_locked": ceo_ok, "ceo_ref_hz": _num(fp.get("ceo_ref_hz")),
                     "ceo_phase_rad": _num(fp.get("ceo_phase_rad")), "ceo_err_hz": _num(fp.get("ceo_err_hz")),
                     "dac0_off_center": _num(fp.get("dac0_off_center"))},
            "comb_locked": bool(ml and frep_ok and (ceo_ok is not False)),
        }

    def write(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.snapshot(), f, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def _on_poll(self, role, d):
        if role in ("ffc", "opl1", "fpga") and time.time() - self._t >= self.period_s:
            self._t = time.time()
            self.write()
