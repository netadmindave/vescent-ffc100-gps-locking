"""Auto-tune an OPL servo filter.

A phase-locked beat is a coherent carrier: its FWHM on an analyzer is just the
RBW, so the tuner scores what the loop actually changes instead:

* ``phase_scope``   — integrated residual phase from a scope capture (rad, lower better)
* ``pedestal_sa``   — carrier-to-pedestal ratio on the 8563E (dB, higher better)
* ``bump_sa``       — servo-bump height relative to carrier (dB, lower better)
* ``adev_counter``  — Allan deviation of the OPL counter at τ0 (lower better)

Target beat and dividers are never changed (they set the lock point). Gain moves
are ramped in ≤ ``max_gain_step_db`` steps and the starting settings are restored
if the lock is lost or the run is stopped.
"""
from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from vescentcomb import dsp as sig

METRICS = {
    # the comb app tunes OPL #1 from its own counter (no scope / analyzer in this application)
    "adev_counter": ("Most stable beat (Allan deviation, τ = 1 s)", "", +1),
}
# instrument each metric needs: (capability or None, label shown in "Optimise for")
NEEDS = {
    "phase_scope": ("scope", "scope"),
    "pedestal_sa": ("spectrum", "spectrum analyzer"),
    "bump_sa": ("spectrum", "spectrum analyzer"),
    "adev_counter": (None, "OPL counter only"),
}


@dataclass
class TuneConfig:
    metric: str = "adev_counter"
    gains_db: List[float] = field(default_factory=lambda: list(np.arange(-60.0, -39.0, 1.0)))
    int_corners_hz: List[float] = field(default_factory=lambda: [50.0, 100.0, 200.0, 500.0, 1000.0])
    diff_corners_hz: Optional[List[float]] = None
    gain_clamp: Optional[List[bool]] = None
    strategy: str = "coordinate"       # coordinate | grid
    dwell_s: float = 5.0
    averages: int = 4
    max_trials: int = 60
    max_gain_step_db: float = 2.0
    revert_on_loss: bool = True
    scope_channel: int = 1
    band_hz: tuple = (10.0, 1e6)

    def as_dict(self):
        d = asdict(self)
        d["gains_db"] = [float(x) for x in self.gains_db]
        return d

    @classmethod
    def from_dict(cls, d):
        c = cls()
        for k, v in (d or {}).items():
            if hasattr(c, k):
                setattr(c, k, v)
        return c


@dataclass
class Trial:
    gain_db: float
    int_hz: float
    diff_hz: Optional[float]
    clamp: Optional[bool]
    score: float
    locked: bool

    def as_dict(self):
        return asdict(self)


class AutoTuner:
    def __init__(self, opl, cfg: TuneConfig, scope=None, sa=None,
                 on_trial: Optional[Callable[[Trial, int, int], None]] = None,
                 on_log: Optional[Callable[[str], None]] = None):
        self.opl, self.cfg, self.scope, self.sa = opl, cfg, scope, sa
        self.on_trial = on_trial or (lambda t, i, n: None)
        self.on_log = on_log or (lambda m: None)
        self.trials: List[Trial] = []
        self.start: Dict[str, Any] = {}
        self.best: Optional[Trial] = None
        self._stop = threading.Event()
        self.thread: Optional[threading.Thread] = None

    # ---- control -----------------------------------------------------------------------
    def start_thread(self):
        self.thread = threading.Thread(target=self.run, daemon=True, name="AutoTuner")
        self.thread.start()
        return self.thread

    def stop(self):
        self._stop.set()

    def estimate_trials(self) -> int:
        c = self.cfg
        dims = [len(c.gains_db), len(c.int_corners_hz), len(c.diff_corners_hz or [None]),
                len(c.gain_clamp or [None])]
        n = int(np.prod(dims)) if c.strategy == "grid" else sum(dims) + 4
        return min(n, c.max_trials)

    # ---- device helpers ----------------------------------------------------------------
    def _read_start(self):
        o = self.opl
        self.start = {"gain": o.get_pll_gain(), "int": o.get_integrator_corner(),
                      "diff": o.get_diff_corner(), "clamp": o._on(o.get_gain_clamp())}

    def _ramp_gain(self, target: float):
        cur = self.opl.get_pll_gain()
        cur = float(cur) if isinstance(cur, float) else target
        while abs(target - cur) > 1e-9:
            if self._stop.is_set():
                return
            stepv = max(-self.cfg.max_gain_step_db, min(self.cfg.max_gain_step_db, target - cur))
            cur += stepv
            self.opl.set_pll_gain(cur)
            time.sleep(0.2)

    def _apply(self, gain, int_hz, diff_hz, clamp):
        if int_hz is not None:
            self.opl.set_integrator_corner(int_hz)
        if diff_hz is not None:
            self.opl.set_diff_corner(diff_hz)
        if clamp is not None:
            self.opl.set_gain_clamp(clamp)
        self._ramp_gain(gain)

    def revert(self):
        s = self.start
        if not s:
            return
        try:
            self.opl.set_integrator_corner(s["int"])
            self.opl.set_diff_corner(s["diff"])
            self.opl.set_gain_clamp(s["clamp"])
            self._stop.clear()
            self._ramp_gain(s["gain"])
        except Exception as e:
            self.on_log(f"revert failed: {e}")

    def locked(self) -> bool:
        o = self.opl
        if not o.servo_on():
            return False
        err = o.read_voltage("error")
        out = o.read_voltage("pll_out")
        lo, hi = o.get_pll_min(), o.get_pll_max()
        rng = o.get_lock_range()
        if not all(isinstance(x, float) for x in (err, out, lo, hi)):
            return False
        margin = 0.05 * (hi - lo)
        return abs(err) < (rng if isinstance(rng, float) else 0.1) and lo + margin < out < hi - margin

    # ---- metrics ------------------------------------------------------------------------
    def measure(self) -> float:
        m, c = self.cfg.metric, self.cfg
        vals = []
        for _ in range(max(1, c.averages)):
            if m == "phase_scope":
                t, v = self.scope.capture(c.scope_channel)        # any "scope" capability add-on
                vals.append(sig.integrated_phase_rms(v, float(t[1] - t[0]), band=c.band_hz))
            elif m in ("pedestal_sa", "bump_sa"):
                f, p = self.sa.sweep_and_fetch()
                f0 = float(f[int(np.argmax(p))])
                if m == "pedestal_sa":
                    vals.append(sig.carrier_to_pedestal_db(f, p, f0, 3 * (f[1] - f[0]), (f[-1] - f[0]) / 2))
                else:
                    vals.append(sig.servo_bump_db(f, p, f0))
            elif m == "adev_counter":
                ys = []
                for _ in range(20):
                    b = self.opl.read_beatnote()
                    ys.append(b)
                    time.sleep(0.2)
                y = (np.array(ys) - np.mean(ys)) / np.mean(ys)
                ad = sig.overlapping_adev(y, 0.2, (5,))
                vals.append(ad[0][1] if ad else float("nan"))
        return float(np.nanmean(vals))

    def _better(self, a: float, b: float) -> bool:
        sign = METRICS[self.cfg.metric][2]
        return (a * sign) < (b * sign)

    # ---- search ---------------------------------------------------------------------------
    def _trial(self, gain, int_hz, diff_hz, clamp, i, n) -> Trial:
        self._apply(gain, int_hz, diff_hz, clamp)
        time.sleep(self.cfg.dwell_s)
        ok = self.locked()
        score = self.measure() if ok else float("nan")
        tr = Trial(float(gain), float(int_hz), diff_hz, clamp, score, ok)
        self.trials.append(tr)
        if ok and (self.best is None or self._better(score, self.best.score)):
            self.best = tr
        self.on_trial(tr, i, n)
        if not ok:
            self.on_log(f"lock lost at gain {gain:g} dB, int {int_hz:g} Hz")
            if self.cfg.revert_on_loss:
                self.revert()
                time.sleep(self.cfg.dwell_s)
        return tr

    def run(self) -> Optional[Trial]:
        c = self.cfg
        self._read_start()
        if not self.locked():
            self.on_log("OPL is not locked — auto-tune needs a working lock to start from")
            return None
        n = self.estimate_trials()
        i = 0
        try:
            if c.strategy == "grid":
                for g, ic, dc, cl in itertools.product(c.gains_db, c.int_corners_hz,
                                                       c.diff_corners_hz or [None], c.gain_clamp or [None]):
                    if self._stop.is_set() or i >= c.max_trials:
                        break
                    i += 1
                    self._trial(g, ic, dc, cl, i, n)
            else:
                g0 = float(self.start["gain"])
                ic0 = float(self.start["int"])
                # 1) gain sweep at the current corner, nearest-first so moves stay small
                for g in sorted(c.gains_db, key=lambda x: abs(x - g0)):
                    if self._stop.is_set() or i >= c.max_trials:
                        break
                    i += 1
                    self._trial(g, ic0, None, None, i, n)
                gbest = self.best.gain_db if self.best else g0
                # 2) integrator corner at the best gain
                for ic in c.int_corners_hz:
                    if self._stop.is_set() or i >= c.max_trials:
                        break
                    i += 1
                    self._trial(gbest, ic, None, None, i, n)
                # 3) refine gain ±2 dB around the best point
                if self.best:
                    for g in np.arange(self.best.gain_db - 2, self.best.gain_db + 2.01, 1.0):
                        if self._stop.is_set() or i >= c.max_trials:
                            break
                        i += 1
                        self._trial(float(g), self.best.int_hz, None, None, i, n)
        finally:
            if self._stop.is_set():
                self.on_log("stopped — reverting to start settings")
                self.revert()
        return self.best

    def apply_best(self):
        if self.best is None:
            return
        b = self.best
        self._stop.clear()
        self._apply(b.gain_db, b.int_hz, b.diff_hz, b.clamp)
