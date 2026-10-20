"""SLICE-FPGA-II (Red Pitaya / Zynq): Device wrapper around ``vescentcomb_addons.comb_lock.fpga``.

``vescentcomb_addons.comb_lock.fpga`` is the SliceFPGA_II_modern package (register-for-register port of
Vescent's GUI, verified with ``tests/fpga/verify_against_gui.py``). This module gives it
the same Device interface as every other instrument and adds what the GUI needs:

* ``settings()``  - what the box is *actually running*, read from the FPGA registers
  (loop-filter gains are converted back into the GUI's kp / fi / fii / fd / fdf units),
  as flat dotted keys such as ``ceo.kp``.
* ``compare(profile)`` / ``apply_differences(rows)`` - box vs saved profile.
* ``spectrum()``, ``filter_band()``, ``integrated_phase()`` for the FPGA page.

``attach()`` reads only. After it, the package's in-memory XML config is synced to the
box, so a later change of one setting (say kp) keeps every other setting as the box had it.
"""
from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from vescentcomb.core.base import Device, DeviceError, Identity, SafetyError

DEFAULT_HOST = "192.168.0.150"
LOOPS = ("ceo", "optical")
CH = {"ceo": 0, "optical": 1}
LOOP_DAC = {"ceo": 0, "optical": 1}
DDC_FILTERS = {0: "Wideband", 1: "Narrowband", 2: "Wideband FIR"}

#: settings the box reports; anything here can be saved in a profile
LOOP_KEYS = ("ref_freq_hz", "vco_sign", "vco_gain", "kp", "fi", "fii", "fd", "fdf",
             "chkKp", "chkKd", "ddc_filter")
#: writing these moves or drops the lock
LOCK_AFFECTING = ("clock.source", "clock.f_ext_hz",
                  "ceo.ref_freq_hz", "ceo.vco_sign", "ceo.ddc_filter",
                  "optical.ref_freq_hz", "optical.vco_sign", "optical.ddc_filter")
#: reported but never written from a profile
READ_ONLY = ("ceo.locked", "optical.locked", "optical.mode", "clock.fs_hz")


_trapz = getattr(np, "trapezoid", None) or np.trapz


def _r3(x: float) -> float:
    """The Vescent GUI's text-box rounding (3 significant figures)."""
    return float("{:.3e}".format(x)) if x else 0.0


def _package():
    from . import fpga
    return fpga


def discover(timeout: float = 1.5) -> List[Dict[str, str]]:
    """UDP broadcast on 1952, replies on 1953 (the package's own discovery)."""
    pkg = _package()
    seen: Dict[str, str] = {}
    for bc in ("192.168.0.255", "255.255.255.255"):
        try:
            for ip, text in pkg.discover(bc, timeout=timeout):
                m = re.search(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", text or "")
                seen.setdefault(ip, m.group(0).lower().replace("-", ":") if m else (text or "").strip())
        except OSError:
            continue
        if seen:
            break
    return [{"host": ip, "mac": mac} for ip, mac in sorted(seen.items())]


class SliceFPGA(Device):
    KIND = "slicefpga"
    LABEL = "Vescent SLICE-FPGA-II"

    def __init__(self, host: str = DEFAULT_HOST, impl=None, mac: str = "", port: int = 5000,
                 config=None, f_ext: float = 20e6):
        super().__init__()
        self.host, self.address, self.mac = host, host, mac
        self.f_ext = f_ext
        if impl is None:
            try:
                impl = _package().SliceFPGA(host, port, config=config)
            except Exception as e:
                raise DeviceError(f"cannot reach SLICE-FPGA-II at {host}:{port} ({e}). "
                                  "Check the PC has a static 192.168.0.x address.") from e
        self.impl = impl
        self.attached = False
        self._phase_cache: Dict[str, Tuple[float, Optional[float]]] = {}
        self.monitor = None

    # ---- connection ------------------------------------------------------------------------
    def attach(self) -> Dict[str, Any]:
        """Read-only reconnect: reads clock, references, DAC offsets, loop gains. Writes nothing."""
        self.impl.attach(f_ext=self.f_ext)
        self._sync_config_from_box()
        self.attached = True
        return self.settings()

    def push_config(self, clock=("external", 20e6), confirm: bool = False):
        """Rewrites every register and ramps the 100 V boost converter. Unlocks both loops."""
        if not confirm:
            raise SafetyError("push_config rewrites all registers and ramps the 100 V "
                              "boost converter - call with confirm=True")
        self.impl.push_config(clock=clock)
        self._sync_config_from_box()
        return self.settings()

    def program_fpga(self, confirm: bool = False):
        """Reload the bitstream (volatile). Config must be pushed again afterwards."""
        if not confirm:
            raise SafetyError("program_fpga reloads the FPGA and drops both locks - call with confirm=True")
        return self.impl.program_fpga()

    def load_config(self, path: str) -> None:
        """Use another Vescent XML parameter file for the next push_config()."""
        self.impl.config = _package().SliceConfig(path)

    def close(self) -> None:
        if self.monitor is not None:
            try:
                self.monitor.stop()
            except Exception:
                pass
            self.monitor = None
        try:
            self.impl.close()          # writes nothing: loops keep running in fabric
        except Exception:
            pass

    def safe_state(self) -> None:
        """Nothing to switch off: the loops are meant to keep running without the PC."""

    def identify(self) -> Identity:
        return Identity(self.KIND, model="SLICE-FPGA-II", serial=self.mac or self.host,
                        raw=f"{self.host} {self.mac}")

    # ---- reading the box ---------------------------------------------------------------------
    def _loop_from_box(self, loop: str) -> Dict[str, Any]:
        impl, sl = self.impl, self.impl.sl
        ch, dac = CH[loop], LOOP_DAC[loop]
        P, I, II, D, coef, lock = sl.pll[ch].get_pll_settings(sl)
        kc = impl.kc.get(ch) or 1.0
        fs = sl.fs
        cfg = impl.config
        sec = f"PLL{ch}_settings"
        cross = cfg.getb(sec, "chkKpCrossing")
        chk_kp, chk_kd = P != 0, D != 0
        if chk_kp:
            g = P
            kp = float("{:.3}".format(20 * math.log10(P * kc)))
        else:
            kp = cfg.getf(sec, "kp")
            g = 10 ** (kp / 20) / kc
        base = g if cross else 1.0 / kc
        fi = _r3(I / (base * 2 * math.pi / fs)) if base else 0.0
        fii = _r3(II / (base * fi * (2 * math.pi / fs) ** 2)) if (base and fi) else 0.0
        fd = _r3(base * fs / (2 * math.pi * D)) if D else cfg.getf(sec, "fd")
        fdf = _r3(coef * fs / (2 * math.pi))
        ref = (sl.get_ddc0_ref_freq_from_RAM() if ch == 0 else sl.get_ddc1_ref_freq_from_RAM())
        try:
            vco_gain = _r3(kc / (sl.getFreqDiscriminatorGain() * sl.getDACGainInVoltsPerCounts(dac)))
        except ZeroDivisionError:
            vco_gain = cfg.getf("VCO_gain", f"DAC{dac}")
        sl.get_ddc_filter_select()
        filt = sl.ddc0_filter_select if ch == 0 else sl.ddc1_filter_select
        out = {"ref_freq_hz": round(abs(ref), 3), "vco_sign": "+" if impl.vco_sign.get(ch, 1) > 0 else "-",
               "vco_gain": vco_gain, "kp": kp, "fi": fi, "fii": fii, "fd": fd, "fdf": fdf,
               "chkKp": chk_kp, "chkKd": chk_kd, "ddc_filter": int(filt), "locked": bool(lock & 1)}
        return {f"{loop}.{k}": v for k, v in out.items()}

    def _dac_offset_v(self, dac: int) -> float:
        cfg = self.impl.config
        lo = cfg.getf("Output_limits_low", f"DAC{dac}")
        hi = cfg.getf("Output_limits_high", f"DAC{dac}")
        return round(lo + (hi - lo) * self.impl.slider[dac] / self.impl.SLIDER_FULL_SCALE, 4)

    def settings(self) -> Dict[str, Any]:
        impl, sl = self.impl, self.impl.sl
        with impl.io:
            ext = not bool(sl.dev.read_Zynq_AXI_register_uint32(sl.clk_sel_base_addr) & 1)
            s: Dict[str, Any] = {"clock.source": "external" if ext else "internal",
                                 "clock.f_ext_hz": float(impl.f_ext or self.f_ext) if ext else None,
                                 "clock.fs_hz": float(sl.fs)}
            for loop in LOOPS:
                s.update(self._loop_from_box(loop))
            s["ceo.dac0_offset_v"] = self._dac_offset_v(0)
            s["optical.dac1_offset_v"] = self._dac_offset_v(1)
            s["optical.dac2_offset_v"] = self._dac_offset_v(2)
            s["optical.mode"] = impl.optical_mode
            cfg = impl.config
            for d in range(3):
                s[f"limits.dac{d}_v"] = (cfg.getf("Output_limits_low", f"DAC{d}"),
                                         cfg.getf("Output_limits_high", f"DAC{d}"))
        return s

    snapshot = settings

    def _sync_config_from_box(self) -> None:
        """Make the package's XML config match the box so single-setting writes keep the rest."""
        cfg = self.impl.config
        s = self.settings()
        for loop in LOOPS:
            ch, dac = CH[loop], LOOP_DAC[loop]
            sec = f"PLL{ch}_settings"
            for k in ("kp", "fi", "fii", "fd", "fdf"):
                cfg.set(sec, k, repr(float(s[f"{loop}.{k}"])))
            cfg.set(sec, "chkKp", str(bool(s[f"{loop}.chkKp"])))
            cfg.set(sec, "chkKd", str(bool(s[f"{loop}.chkKd"])))
            cfg.set("Reference_frequency", f"DDC{ch}", repr(float(s[f"{loop}.ref_freq_hz"])))
            cfg.set("VCO_gain", f"DAC{dac}", repr(float(s[f"{loop}.vco_gain"])))
            cfg.set("Filter_select", f"DAC{ch}", str(int(s[f"{loop}.ddc_filter"])))
        for dac, key in ((0, "ceo.dac0_offset_v"), (1, "optical.dac1_offset_v"), (2, "optical.dac2_offset_v")):
            cfg.set("Output_offset_in_volts", f"DAC{dac}", repr(float(s[key])))

    # ---- writing one setting -----------------------------------------------------------------
    def set_value(self, key: str, value: Any, allow_unlock: bool = False) -> None:
        if key in READ_ONLY or key.startswith("limits."):
            raise DeviceError(f"{key} is read-only")
        if key in LOCK_AFFECTING and not allow_unlock:
            for loop in LOOPS:
                if self.is_locked(loop):
                    raise SafetyError(f"writing {key} would disturb the {loop} lock; "
                                      "unlock first or pass allow_unlock=True")
        impl = self.impl
        sec, name = key.split(".", 1)
        if sec == "clock":
            if name == "source":
                ext = str(value) == "external"
                impl.set_clock(ext, float(impl.f_ext or self.f_ext))
            elif name == "f_ext_hz":
                self.f_ext = float(value)
                impl.set_clock(True, self.f_ext)
            return
        if name.endswith("_offset_v"):
            dac = int(name[3])
            impl.set_dac_offset(dac, float(value))
            return
        loop = sec
        ch, dac = CH[loop], LOOP_DAC[loop]
        if name in ("kp", "fi", "fii", "fd", "fdf"):
            impl.set_loop_filter(loop, **{name: float(value)})
        elif name in ("chkKp", "chkKd"):
            impl.set_loop_filter(loop, **{name: "True" if value else "False"})
        elif name == "vco_gain":
            impl.set_vco_gain(dac, float(value))
        elif name == "ref_freq_hz":
            impl.set_ref_freq(loop, abs(float(value)))
        elif name == "vco_sign":
            ref = float(impl.config.get("Reference_frequency", f"DDC{ch}"))
            impl.set_ref_freq(loop, abs(ref), vco_sign=+1 if str(value) in ("+", "1", "+1") else -1)
        elif name == "ddc_filter":
            sl = impl.sl
            angle = sl.ddc0_angle_select if ch == 0 else sl.ddc1_angle_select
            with impl.io:
                sl.set_ddc_filter(ch, int(value), angle)
            impl.config.set("Filter_select", f"DAC{ch}", str(int(value)))
        else:
            raise DeviceError(f"unknown FPGA setting {key}")

    @staticmethod
    def _same(have, want, rel_tol: float, key: str = "") -> bool:
        if key.endswith("_offset_v") and isinstance(have, (int, float)) and isinstance(want, (int, float)):
            return abs(have - want) <= 0.01          # the unlock ramp moves the offset to the lock point
        if isinstance(have, bool) or isinstance(want, bool):
            return bool(have) == bool(want)
        if isinstance(have, (int, float)) and isinstance(want, (int, float)):
            return abs(have - want) <= rel_tol * max(abs(have), abs(want), 1e-30)
        return have == want

    def compare(self, profile: Dict[str, Any], rel_tol: float = 2e-3) -> List[Dict[str, Any]]:
        """Box vs profile. Returns rows {key, box, profile, lock_affecting}. Unknown keys are skipped.

        rel_tol absorbs the fixed-point register rounding (a few parts in 10^4)."""
        box = self.settings()
        rows = []
        for k, want in profile.items():
            if k not in box or k in READ_ONLY or k.startswith("limits.") or want is None:
                continue
            have = box.get(k)
            if not self._same(have, want, rel_tol, k):
                rows.append({"key": k, "box": have, "profile": want,
                             "lock_affecting": k in LOCK_AFFECTING})
        return rows

    def apply_differences(self, rows: List[Dict[str, Any]], allow_unlock: bool = False) -> Dict[str, str]:
        """Write the profile value for each row, then read back. Relocks what it unlocked."""
        result: Dict[str, str] = {}
        relock = []
        if allow_unlock and any(r["lock_affecting"] for r in rows):
            for loop in LOOPS:
                if self.is_locked(loop):
                    self.unlock(loop)
                    relock.append(loop)
        for r in rows:
            try:
                self.set_value(r["key"], r["profile"], allow_unlock=allow_unlock)
                result[r["key"]] = "ok"
            except Exception as e:
                result[r["key"]] = f"error: {e}"
        after = self.settings()
        for r in rows:
            if result.get(r["key"]) == "ok" and not self._same(after.get(r["key"]), r["profile"], 2e-3, r["key"]):
                result[r["key"]] = f"readback {after.get(r['key'])!r}"
        for loop in relock:
            self.lock(loop)
        return result

    # ---- loops --------------------------------------------------------------------------------
    def lock(self, loop: str = "ceo"):
        if loop not in LOOPS:
            raise ValueError(f"loop must be one of {LOOPS}")
        self.impl.lock(loop)
        self._phase_cache.pop(loop, None)

    def unlock(self, loop: str = "ceo", ramp: bool = True):
        """``ramp`` moves the manual DAC offset to where the lock sat (as the Vescent GUI does)."""
        self.impl.unlock(loop, ramp=ramp)
        self._phase_cache.pop(loop, None)

    def is_locked(self, loop: str = "ceo") -> bool:
        with self.impl.io:
            return bool(self.impl.is_locked(loop))

    def dac_position(self, dac: int = 0) -> Dict[str, float]:
        """DAC output now: volts, the output limits, and |V − 0 V| as a fraction of the full range
        (0 = centered, 0.5 = at a rail when the limits are symmetric)."""
        sl = self.impl.sl
        with self.impl.io:
            c = self.impl._dac_current(dac)
        lo, hi = sl.DACs_limit_low[dac], sl.DACs_limit_high[dac]
        v = float(sl.convertDACCountsToVolts(dac, c))
        vl, vh = sorted((float(sl.convertDACCountsToVolts(dac, lo)), float(sl.convertDACCountsToVolts(dac, hi))))
        span = vh - vl
        return {"v": v, "lo_v": vl, "hi_v": vh, "off_center": abs(v) / span if span > 0 else float("nan")}

    def _dac0_off_center(self):
        try:
            return self.dac_position(0)["off_center"]
        except Exception:
            return None

    def set_dac0_center(self) -> None:
        """Manual DAC0 offset to 0 V (center), used before relocking f_ceo."""
        self.impl.set_dac_offset(0, 0.0)

    def frequency_noise(self, loop: str = "ceo"):
        """(f, S_nu [Hz²/Hz], S_phi [rad²/Hz]) of the in-loop beat, as the Vescent GUI plots it."""
        return self.impl.frequency_noise(loop)

    def integrated_phase(self, loop: str = "ceo", f_max: Optional[float] = None,
                         max_age_s: float = 0.0) -> Optional[float]:
        """RMS phase (rad) of the in-loop beat, ∫S_phi from the first bin to f_max
        (default: Integration_limit in the XML, 5 MHz)."""
        if max_age_s > 0:
            t, v = self._phase_cache.get(loop, (0.0, None))
            if time.time() - t < max_age_s:
                return v
        if f_max is None:
            try:
                f_max = self.impl.config.getf("Main_window_settings", "Integration_limit")
            except Exception:
                f_max = 5e6
        f, _, sphi = self.frequency_noise(loop)
        m = (f <= f_max) & np.isfinite(sphi)
        v = float(np.sqrt(_trapz(sphi[m], f[m]))) if m.sum() > 1 else None
        self._phase_cache[loop] = (time.time(), v)
        return v

    def lock_and_verify(self, loop: str = "ceo", max_phase_rad: float = 1.5,
                        tries: int = 3, settle_s: float = 2.0) -> Tuple[bool, Optional[float]]:
        """Lock (if open), then check integrated phase. Retries; returns (ok, phase)."""
        phase = None
        for _ in range(tries):
            if not self.is_locked(loop):
                self.lock(loop)
                time.sleep(settle_s)
            phase = self.integrated_phase(loop)
            if self.is_locked(loop) and (phase is None or phase < max_phase_rad):
                return True, phase
            self.unlock(loop)
            time.sleep(0.5)
        return False, phase

    def read_counters(self) -> Dict[str, Any]:
        """Zero-dead-time counters: ceo_err_Hz / opt_err_Hz are lock frequency errors."""
        return self.impl.read_counters()

    def status(self) -> Dict[str, Any]:
        return self.impl.status()

    # ---- spectrum -------------------------------------------------------------------------------
    @property
    def fs(self) -> float:
        return float(self.impl.sl.fs)

    def spectrum(self, adc: int = 0, n: int = 16384, averages: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """ADC spectrum 0 – fs/2 in dBFS (Hann window, averaged)."""
        acc = None
        x = None
        for _ in range(max(1, averages)):
            x, _ = self.impl.capture(f"ADC{adc}", n)
            x = np.asarray(x, dtype=float)
            x = x - x.mean()
            p = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
            acc = p if acc is None else acc + p
        p = acc / max(1, averages)
        full_scale = (np.sum(np.hanning(len(x))) * 32768.0 / 2) ** 2
        f = np.fft.rfftfreq(len(x), 1.0 / self.fs)
        return f, 10 * np.log10(np.maximum(p / full_scale, 1e-20))

    def iq(self, loop: str = "ceo", n: int = 16384, max_points: int = 2000):
        """Baseband IQ of the loop's input: ADC samples mixed with the DDC reference frequency,
        low-passed (boxcar ≈ 7 MHz) and decimated. Returns (I, Q, f_ref) in units of ADC full scale."""
        sl = self.impl.sl
        ch = CH[loop]
        x, _ = self.impl.capture(f"ADC{ch}", n)
        x = np.asarray(x, dtype=float)
        x = (x - x.mean()) / 32768.0
        with self.impl.io:
            fc = abs(sl.get_ddc0_ref_freq_from_RAM() if ch == 0 else sl.get_ddc1_ref_freq_from_RAM())
        fs = self.fs
        z = x * np.exp(-2j * np.pi * fc * np.arange(len(x)) / fs) * 2.0
        k = max(1, int(round(fs / 7e6)))
        z = np.convolve(z, np.ones(k) / k, mode="valid")[::k]
        if len(z) > max_points:
            z = z[:: int(np.ceil(len(z) / max_points))]
        return z.real, z.imag, float(fc)

    def filter_band(self, loop: str = "ceo", level_db: float = -3.0) -> Tuple[float, float, float]:
        """(low, centre, high) of the DDC pass band in Hz, from the firmware's filter model."""
        sl = self.impl.sl
        ch = CH[loop]
        with self.impl.io:
            sl.get_ddc_filter_select()
        fc = abs(sl.get_ddc0_ref_freq_from_RAM() if ch == 0 else sl.get_ddc1_ref_freq_from_RAM())
        fa = np.linspace(0, self.fs / 2, 4001)
        resp = np.asarray(sl.get_frontend_filter_response(fa, ch), dtype=float)
        resp = resp - resp[np.argmin(np.abs(fa - fc))]
        inside = resp >= level_db
        i0 = int(np.argmin(np.abs(fa - fc)))
        lo_i, hi_i = i0, i0
        while lo_i > 0 and inside[lo_i - 1]:
            lo_i -= 1
        while hi_i < len(fa) - 1 and inside[hi_i + 1]:
            hi_i += 1
        return float(fa[lo_i]), float(fc), float(fa[hi_i])

    # ---- background monitor (package's Monitor, CSV) -------------------------------------------------
    def start_monitor(self, csv_dir: str, period_s: float = 0.25):
        pkg = _package()
        if self.monitor is None:
            self.monitor = pkg.Monitor(self.impl, csv_dir=csv_dir, period_s=period_s)
            self.monitor.start()
        return getattr(self.monitor, "csv_path", None)

    def stop_monitor(self):
        if self.monitor is not None:
            self.monitor.stop()
            self.monitor = None

    # ---- poll ----------------------------------------------------------------------------------------
    def poll(self) -> Dict[str, Any]:
        st = self.impl.status()
        ctr = self.read_counters()
        ceo = bool(st.get("ceo_locked"))
        return {
            "ceo_locked": ceo,
            "optical_locked": bool(st.get("optical_locked")),
            "optical_mode": st.get("optical_mode"),
            "ceo_phase_rad": self.integrated_phase("ceo", max_age_s=5.0) if ceo else None,
            "clock_source": st.get("clock"),
            "fs_hz": st.get("fs_MHz", 0) * 1e6,
            "ext_clk_hz": st.get("ext_clk_measured_MHz", float("nan")) * 1e6,
            "ceo_ref_hz": abs(st.get("ddc0_ref_MHz", 0)) * 1e6,
            "opt_ref_hz": abs(st.get("ddc1_ref_MHz", 0)) * 1e6,
            "ceo_err_hz": ctr.get("ceo_err_Hz"),
            "opt_err_hz": ctr.get("opt_err_Hz"),
            "counter_new": ctr.get("new"),
            "zynq_temp_c": st.get("zynq_temp_C"),
            "dac0_off_center": self._dac0_off_center(),
            "dac0_v": st.get("dac0_now_V"), "dac1_v": st.get("dac1_now_V"), "dac2_v": st.get("dac2_now_V"),
            "dac0_frac": st.get("dac0_frac"), "dac1_frac": st.get("dac1_frac"), "dac2_frac": st.get("dac2_frac"),
        }
