"""Comb lock sequence: f_ceo first on the SLICE-FPGA-II, then f_rep to GPS.

(Locking a laser to the comb is the Laser lock module's own sequence.)

The cavity walk is the logic from GPS Auto-Lock.ipynb with these changes:
* the f_ceo lock is established (or confirmed) FIRST, keeping the FPGA's own settings
  and fixing only what differs from the saved profile — after asking;
* the step table is editable and the fine 0.005 °C step is reachable (in the notebook
  the ``a < 100`` branch returned 0.01 before the 0.005 branch could be reached);
* hard limits on setpoint excursion and step count;
* every wait has a timeout; Pause / Stop are honoured between actions;
* dry run reads everything and reports the first move without writing.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple

STEP_IDS = ("pre", "fpga_attach", "fpga_diff", "fceo", "opl1_off", "walk", "confirm",
            "opl1_on", "slow_servo")
STEP_TITLES = {
    "pre": "Before start: comb mode-locked, GPS reference present",
    "fpga_attach": "Attach SLICE-FPGA-II (read only)",
    "fpga_diff": "Fix settings that differ from profile",
    "fceo": "Lock f_ceo",
    "opl1_off": "OPL #1 servo is off",
    "walk": "Walk cavity setpoint toward beat",
    "confirm": "Confirm inside window",
    "opl1_on": "OPL #1 servo ON",
    "slow_servo": "FFC slow servo ON",
}


@dataclass
class LockParams:
    counter_offset_hz: float = 31.0
    window_hz: float = 8.0
    cav_settle_mk: float = 1.0
    poll_s: float = 3.0
    confirm_dwell_s: float = 10.0
    post_servo_wait_s: float = 10.0
    max_excursion_c: float = 1.0
    max_steps: int = 200
    settle_timeout_s: float = 180.0
    step_table: List[Tuple[float, float]] = field(
        default_factory=lambda: [(300.0, 0.100), (100.0, 0.050), (20.0, 0.010), (0.0, 0.005)])
    fceo_max_phase_rad: float = 1.5
    fceo_retries: int = 3
    dac0_max_frac: float = 0.15        # DAC0 further than this fraction of its range from 0 V -> recenter
    check_pzt: bool = False            # also require the FFC PZT reading (CADCBV?) inside the range below
    pzt_min_v: float = 2.0
    pzt_max_v: float = 58.0
    relock_tries: int = 3              # lock-check failures: pause, relock, try again this many times
    relock_wait_s: float = 10.0
    ask_before_fpga_write: bool = True
    dry_run: bool = False

    def step_for(self, err_hz: float) -> float:
        a = abs(err_hz)
        for thresh, step in sorted(self.step_table, key=lambda r: -r[0]):
            if a >= thresh:
                return step
        return sorted(self.step_table, key=lambda r: r[0])[0][1]

    def as_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LockParams":
        p = cls()
        for k, v in (d or {}).items():
            if hasattr(p, k):
                if k == "step_table":
                    v = [tuple(r) for r in v]
                setattr(p, k, v)
        return p


@dataclass
class StepState:
    id: str
    title: str
    status: str = "wait"      # wait | run | done | skip | fail
    detail: str = ""


class Aborted(Exception):
    pass


class LockFault(Exception):
    """A lock that was good is no longer good (checked after every step)."""

    def __init__(self, problems: List[Tuple[str, str]], where: str):
        self.problems, self.where = problems, where
        super().__init__(f"after {where}: " + "; ".join(m for _, m in problems))


class LockSequence:
    """Run with ``seq.run()`` (blocking) or ``seq.start()`` (thread).

    ``devices`` is a dict with any of: ffc, fpga, opl1.
    Callbacks (all optional, called from the worker thread):
      on_step(StepState), on_log(str), on_sample(dict), ask(question, rows) -> bool
    """

    def __init__(self, devices: Dict[str, Any], params: Optional[LockParams] = None,
                 fpga_profile: Optional[Dict[str, Any]] = None,
                 on_step=None, on_log=None, on_sample=None, ask=None):
        self.d = devices
        self.p = params or LockParams()
        self.fpga_profile = fpga_profile or {}
        self.on_step = on_step or (lambda s: None)
        self.on_log = on_log or (lambda m: None)
        self.on_sample = on_sample or (lambda s: None)
        self.ask = ask or (lambda q, rows=None: True)
        self.steps = {sid: StepState(sid, STEP_TITLES[sid]) for sid in STEP_IDS}
        self._stop = threading.Event()
        self._pause = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.result: Optional[bool] = None
        self.t0 = 0.0
        self.n_steps = 0
        self.start_setpoint: Optional[float] = None

    # ---- control -----------------------------------------------------------------------
    def start(self) -> threading.Thread:
        self.thread = threading.Thread(target=self.run, daemon=True, name="LockSequence")
        self.thread.start()
        return self.thread

    def stop(self): self._stop.set(); self._pause.clear()
    def pause(self): self._pause.set()
    def resume(self): self._pause.clear()

    @property
    def paused(self): return self._pause.is_set()

    def thread_alive(self) -> bool:
        return self.result is None and self.t0 > 0

    def _checkpoint(self):
        while self._pause.is_set() and not self._stop.is_set():
            time.sleep(0.1)
        if self._stop.is_set():
            raise Aborted()

    def _sleep(self, s: float):
        t_end = time.time() + s
        while time.time() < t_end:
            self._checkpoint()
            time.sleep(min(0.1, max(0.0, t_end - time.time())))

    def _log(self, msg: str):
        self.on_log(f"{time.strftime('%H:%M:%S')}  {msg}")

    def _set(self, sid: str, status: str, detail: str = ""):
        st = self.steps[sid]
        st.status = status
        if detail:
            st.detail = detail
        self.on_step(st)

    # ---- the sequence ------------------------------------------------------------------
    def run(self) -> bool:
        self.t0 = time.time()
        try:
            attempt = 0
            while True:
                try:
                    ok = self._run()
                    if ok and not self.p.dry_run:
                        self._check("sequence end")
                    break
                except LockFault as f:
                    attempt += 1
                    for st in self.steps.values():
                        if st.status == "run":
                            self._set(st.id, "fail", "lock check failed")
                    if attempt > self.p.relock_tries:
                        self._log(f"lock check failed: {f} — giving up after {self.p.relock_tries} relocks")
                        ok = False
                        break
                    self._log(f"lock check failed: {f} — paused, relocking "
                              f"(try {attempt}/{self.p.relock_tries})")
                    self._recover(f)
                    self._sleep(self.p.relock_wait_s)
                    for st in self.steps.values():
                        st.status, st.detail = "wait", ""
                        self.on_step(st)
                    self._log("trying again")
        except Aborted:
            self._log("stopped by user")
            for st in self.steps.values():
                if st.status == "run":
                    self._set(st.id, "fail", "stopped")
            ok = False
        except Exception as e:  # report and stop safely
            self._log(f"error: {e}")
            for st in self.steps.values():
                if st.status == "run":
                    self._set(st.id, "fail", str(e))
            ok = False
        self.result = ok
        self._log("sequence finished OK" if ok else "sequence did not complete")
        return ok

    def _run(self) -> bool:
        ffc, opl1, fpga = self.d.get("ffc"), self.d.get("opl1"), self.d.get("fpga")
        dry = self.p.dry_run
        self._want = {"fceo": False, "opl1": False, "slow": False}
        if ffc is None or opl1 is None:
            raise RuntimeError("FFC-100 and OPL #1 must be connected")

        # 0. preconditions --------------------------------------------------------------
        self._set("pre", "run")
        if not ffc.mode_locked():
            self._set("pre", "fail", "FFC-100 is not mode-locked")
            return False
        ref = opl1.read_reference()
        if not isinstance(ref, float) or abs(ref - 10.0) > 0.01:
            self._set("pre", "fail", f"OPL #1 reference reads {ref} MHz (expected 10 MHz GPS)")
            return False
        self._set("pre", "done", "FFC-100 mode-locked ✓ · GPS 10 MHz present ✓")
        self._log(f"start · MODELOK ON · ref {ref:.6f} MHz" + (" · DRY RUN" if dry else ""))

        # 1-3. FPGA ------------------------------------------------------------------------
        if fpga is None:
            for sid in ("fpga_attach", "fpga_diff", "fceo"):
                self._set(sid, "skip", "SLICE-FPGA-II not connected")
            self._log("FPGA not connected — f_ceo steps skipped")
        else:
            self._checkpoint()
            self._set("fpga_attach", "run")
            fpga.attach()
            self._set("fpga_attach", "done", "read what the box is running · no writes")
            self._log("FPGA attached (read only)")

            self._set("fpga_diff", "run")
            if not self.fpga_profile:
                self._set("fpga_diff", "skip", "no profile saved yet (FPGA page → Save box as profile)")
            else:
                rows = fpga.compare(self.fpga_profile)
                if not rows:
                    self._set("fpga_diff", "done", "box matches profile")
                else:
                    desc = ", ".join(f"{r['key']} {r['box']} → {r['profile']}" for r in rows)
                    self._log(f"FPGA differs from profile: {desc}")
                    approved = (not self.p.ask_before_fpga_write) or self.ask(
                        f"{len(rows)} FPGA setting(s) differ from your profile. Write the profile values?",
                        rows)
                    if dry or not approved:
                        self._set("fpga_diff", "skip",
                                  f"{len(rows)} differ · " + ("dry run" if dry else "not approved"))
                    else:
                        lock_aff = any(r["lock_affecting"] for r in rows)
                        allow = (not lock_aff) or self.ask(
                            "Some of these would drop the lock. Unlock, write, and relock?", rows)
                        todo = rows if allow else [r for r in rows if not r["lock_affecting"]]
                        res = fpga.apply_differences(todo, allow_unlock=allow)
                        bad = {k: v for k, v in res.items() if v != "ok"}
                        self._set("fpga_diff", "done" if not bad else "fail",
                                  f"{len(todo)} written, read back " + ("OK" if not bad else str(bad)))
                        self._log(f"FPGA written: {res}")
                        if bad:
                            return False

            self._checkpoint()
            self._set("fceo", "run")
            if fpga.is_locked("ceo"):
                ph = fpga.integrated_phase("ceo")
                if ph is None or ph < self.p.fceo_max_phase_rad:
                    self._set("fceo", "done", f"already locked → kept · {ph:.2f} rad" if ph is not None
                              else "already locked → kept")
                else:
                    raise LockFault([("fceo", f"locked but integrated phase {ph:.2f} rad ≥ "
                                              f"{self.p.fceo_max_phase_rad:g} rad")], "f_ceo check")
            elif dry:
                self._set("fceo", "skip", "open · would lock (dry run)")
            else:
                ok, ph = fpga.lock_and_verify("ceo", self.p.fceo_max_phase_rad, self.p.fceo_retries)
                if not ok:
                    self._set("fceo", "fail", f"could not lock after {self.p.fceo_retries} tries "
                                              f"(phase {ph})")
                    return False
                self._set("fceo", "done", f"locked · {ph:.2f} rad" if ph is not None else "locked")
            self._log(f"f_ceo: {self.steps['fceo'].detail}")
            if self.steps["fceo"].status == "done":
                self._want["fceo"] = True
                self._check("f_ceo lock")

        # 4. OPL #1 servo state ----------------------------------------------------------------
        self._checkpoint()
        self._set("opl1_off", "run")
        if opl1.servo_on():
            self._set("opl1_off", "done", "servo already ON — nothing to do")
            for sid in ("walk", "confirm", "opl1_on"):
                self._set(sid, "skip", "OPL #1 already locked")
            self._want["opl1"] = True
            self._check("OPL #1 check")
            return self._slow_servo(ffc, dry)
        self._set("opl1_off", "done", "SERVO? → Off")
        self._check("OPL #1 check")

        # 5-6. cavity walk ---------------------------------------------------------------------
        if not self._walk(ffc, opl1):
            return False
        if dry:
            for sid in ("opl1_on", "slow_servo"):
                self._set(sid, "skip", "dry run")
            return True

        # 7. servo on ------------------------------------------------------------------------------
        self._checkpoint()
        self._set("opl1_on", "run")
        opl1.set_servo(True)
        self._sleep(self.p.post_servo_wait_s)
        if not opl1.servo_on():
            self._set("opl1_on", "fail", "servo did not report ON")
            return False
        err = opl1.beat_error_hz(self.p.counter_offset_hz / 1e6)
        self._set("opl1_on", "done", f"SERVO ON · error {err:+.1f} Hz" if err is not None else "SERVO ON")
        self._log("OPL #1 SERVO ON")
        self._want["opl1"] = True
        self._check("OPL #1 servo on")
        return self._slow_servo(ffc, dry)

    def _slow_servo(self, ffc, dry: bool) -> bool:
        # 8. slow servo ------------------------------------------------------------------------------
        self._checkpoint()
        self._set("slow_servo", "run")
        if ffc.slow_servo_on():
            self._set("slow_servo", "done", "already ON")
        elif dry:
            self._set("slow_servo", "skip", "off · would turn on (dry run)")
            return True
        else:
            ffc.set_slow_servo(True)
            time.sleep(0.2)
            if not ffc.slow_servo_on():
                self._set("slow_servo", "fail", "slow servo readback is not ON")
                return False
            self._set("slow_servo", "done", "SLSRVEN 1 · readback ON")
            self._log("FFC slow servo ON")
        self._want["slow"] = True
        self._check("slow servo on")
        return True

    # ---- lock checks -------------------------------------------------------------------------
    def _check(self, where: str) -> None:
        """Every lock established so far must still be good (see ``lock_problems``)."""
        if self.p.dry_run:
            return
        probs = lock_problems(self.d, self.p, getattr(self, "_want", {}))
        if probs:
            raise LockFault(probs, where)

    def _recover(self, f: LockFault) -> None:
        recover(self.d, self.p, {k for k, _ in f.problems}, self._log, self._sleep)

    # ---- cavity walk -----------------------------------------------------------------------
    def _wait_cavity(self, ffc) -> float:
        t_end = time.time() + self.p.settle_timeout_s
        while True:
            self._checkpoint()
            d_mk = abs(ffc.cav_temp() - ffc.cav_setpoint()) * 1e3
            if d_mk < self.p.cav_settle_mk:
                return d_mk
            if time.time() > t_end:
                raise RuntimeError(f"cavity did not settle within {self.p.settle_timeout_s:.0f} s "
                                   f"({d_mk:.2f} mK)")
            self._set("walk", "run", f"waiting for cavity to settle: {d_mk:.2f} mK "
                                     f"(need < {self.p.cav_settle_mk} mK)")
            time.sleep(min(self.p.poll_s, 1.0))

    def _walk(self, ffc, opl1) -> bool:
        p = self.p
        off_mhz = p.counter_offset_hz / 1e6
        self._set("walk", "run")
        self.start_setpoint = ffc.cav_setpoint()
        while True:
            self._checkpoint()
            err = opl1.beat_error_hz(off_mhz)
            sp = ffc.cav_setpoint()
            ct = ffc.cav_temp()
            self.on_sample({"t": time.time() - self.t0, "err_hz": err, "setpoint": sp,
                            "cav_temp": ct, "steps": self.n_steps})
            if err is None:
                self._set("walk", "fail", "no beat reading from OPL #1")
                return False
            if abs(err) <= p.window_hz:
                self._set("walk", "done", f"inside ±{p.window_hz:g} Hz after {self.n_steps} steps")
                self._set("confirm", "run", f"settling, then {p.confirm_dwell_s:g} s dwell")
                self._wait_cavity(ffc)
                self._sleep(p.confirm_dwell_s)
                err2 = opl1.beat_error_hz(off_mhz)
                self.on_sample({"t": time.time() - self.t0, "err_hz": err2, "setpoint": ffc.cav_setpoint(),
                                "cav_temp": ffc.cav_temp(), "steps": self.n_steps})
                if err2 is not None and abs(err2) <= p.window_hz:
                    self._set("confirm", "done", f"confirmed {err2:+.1f} Hz")
                    self._log(f"|error| ≤ {p.window_hz:g} Hz confirmed ({err2:+.1f} Hz)")
                    self._check("confirm")
                    return True
                self._set("confirm", "wait", f"drifted out ({err2:+.1f} Hz) — stepping again")
                self._set("walk", "run")
                continue
            step = p.step_for(err)
            direction = -1 if err > 0 else +1         # beat LOW -> setpoint down
            new_sp = sp + direction * step
            word = "LOW" if err > 0 else "HIGH"
            msg = f"beat {word} by {abs(err):.1f} Hz → setpoint {'+' if direction > 0 else '−'}{step:g} °C"
            if abs(new_sp - self.start_setpoint) > p.max_excursion_c:
                self._set("walk", "fail", f"would exceed ±{p.max_excursion_c} °C from start "
                                          f"({self.start_setpoint:.4f} °C)")
                return False
            if self.n_steps >= p.max_steps:
                self._set("walk", "fail", f"reached max {p.max_steps} steps")
                return False
            if p.dry_run:
                self._set("walk", "done", f"DRY RUN · would do: {msg}")
                self._log(f"dry run: {msg}")
                return True
            self._wait_cavity(ffc)
            ffc.set_cav_setpoint(new_sp)
            self.n_steps += 1
            self._set("walk", "run", msg)
            self._log(msg + f" ({sp:.4f} → {new_sp:.4f})")
            self._sleep(p.poll_s)
            self._check(f"cavity step {self.n_steps}")


# ---- shared by the sequence and the watchdog -----------------------------------------------------------
def lock_problems(d: Dict[str, Any], p: LockParams, want: Dict[str, bool]) -> List[Tuple[str, str]]:
    """What is wrong with the locks in ``want`` (fceo / opl1 / slow) right now. Empty list = all good.

    * comb mode-locked (always)
    * f_ceo locked, integrated phase < fceo_max_phase_rad, DAC0 within dac0_max_frac of range from 0 V
    * OPL #1 servo on; FFC slow servo on
    * (optional) FFC PZT reading inside pzt_min_v … pzt_max_v once OPL #1 is locked
    """
    ffc, opl1, fpga = d.get("ffc"), d.get("opl1"), d.get("fpga")
    probs: List[Tuple[str, str]] = []
    if ffc is not None and not ffc.mode_locked():
        probs.append(("modelock", "FFC-100 not mode-locked"))
    if fpga is not None and want.get("fceo"):
        if not fpga.is_locked("ceo"):
            probs.append(("fceo", "f_ceo lock lost"))
        else:
            ph = fpga.integrated_phase("ceo", max_age_s=5.0)
            if ph is not None and ph >= p.fceo_max_phase_rad:
                probs.append(("fceo", f"f_ceo phase {ph:.2f} rad ≥ {p.fceo_max_phase_rad:g} rad"))
            pos = fpga.dac_position(0)
            if pos["off_center"] > p.dac0_max_frac:
                probs.append(("dac0", f"DAC0 at {pos['v']:+.3f} V = {100 * pos['off_center']:.0f} % of range "
                                      f"from center (limit {100 * p.dac0_max_frac:.0f} %)"))
    if opl1 is not None and want.get("opl1") and not opl1.servo_on():
        probs.append(("opl1", "OPL #1 servo off"))
    if ffc is not None and want.get("slow") and not ffc.slow_servo_on():
        probs.append(("slow", "slow servo off"))
    if ffc is not None and p.check_pzt and want.get("opl1"):
        v = ffc.pzt_output_voltage()
        if v is not None and not (p.pzt_min_v <= v <= p.pzt_max_v):
            probs.append(("pzt", f"PZT {v:.2f} V outside {p.pzt_min_v:g}–{p.pzt_max_v:g} V"))
    return probs


def recover(d: Dict[str, Any], p: LockParams, kinds, log: Callable[[str], None],
            sleep: Callable[[float], None] = time.sleep) -> None:
    """Put things back so the lock sequence can run again.

    * DAC0 near a rail: unlock f_ceo, set DAC0 to center (0 V), and open OPL #1 + slow servo so
      the whole sequence restarts from a centered actuator.
    * f_ceo lost / noisy: unlock (the sequence relocks it).
    * OPL #1 or slow servo off, PZT out of range: slow servo off, OPL #1 servo off (the cavity walk redoes f_rep).
    * mode lock lost: wait for it (it is not changed remotely).
    """
    ffc, opl1, fpga = d.get("ffc"), d.get("opl1"), d.get("fpga")
    kinds = set(kinds)
    if "modelock" in kinds and ffc is not None:
        log("waiting for the comb to mode-lock again (not changed remotely)")
        t_end = time.time() + max(p.relock_wait_s, 30.0)
        while time.time() < t_end and not ffc.mode_locked():
            sleep(1.0)
    if kinds & {"dac0", "pzt", "opl1", "slow"}:
        if ffc is not None and ffc.slow_servo_on():
            ffc.set_slow_servo(False)
            log("slow servo OFF")
        if opl1 is not None and opl1.servo_on():
            opl1.set_servo(False)
            log("OPL #1 servo OFF")
    if fpga is not None and kinds & {"dac0", "fceo"}:
        if fpga.is_locked("ceo"):
            fpga.unlock("ceo", ramp=False)
            log("f_ceo unlocked")
        if "dac0" in kinds:
            fpga.set_dac0_center()
            log("DAC0 set to center (0 V)")


class LockWatchdog:
    """Watches the f_ceo lock and the GPS OPL #1 lock after the sequence has locked them.

    Every ``period_s`` it runs ``lock_problems``; a problem that lasts ``lost_s`` triggers
    ``recover`` and a full relock through ``run_sequence()`` (blocking, returns True on success).
    At most ``max_per_hour`` relocks; after that it only reports.
    """

    def __init__(self, devices: Dict[str, Any], params: Callable[[], LockParams],
                 run_sequence: Callable[[], bool], on_log=None, on_state=None,
                 period_s: float = 5.0, lost_s: float = 10.0, max_per_hour: int = 6):
        self.d, self.params, self.run_sequence = devices, params, run_sequence
        self.on_log = on_log or (lambda m: None)
        self.on_state = on_state or (lambda s, msg: None)
        self.period_s, self.lost_s, self.max_per_hour = period_s, lost_s, max_per_hour
        self.relocks: List[float] = []
        self._stop = threading.Event()
        self.hold = threading.Event()          # set while something else (a manual sequence) is running
        self.thread: Optional[threading.Thread] = None

    def start(self):
        self._stop.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True, name="LockWatchdog")
        self.thread.start()

    def stop(self):
        self._stop.set()

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive() and not self._stop.is_set()

    def _log(self, m):
        self.on_log(f"{time.strftime('%H:%M:%S')}  watchdog: {m}")

    def _want(self) -> Dict[str, bool]:
        return {"fceo": self.d.get("fpga") is not None, "opl1": True, "slow": True}

    def _loop(self):
        bad_since = None
        self.on_state("watching", "")
        while not self._stop.wait(self.period_s):
            if self.hold.is_set():
                bad_since = None
                continue
            p = self.params()
            try:
                probs = lock_problems(self.d, p, self._want())
            except Exception as e:
                self.on_state("error", str(e))
                continue
            if not probs:
                bad_since = None
                self.on_state("ok", "f_ceo and OPL #1 locked")
                continue
            msg = "; ".join(m for _, m in probs)
            bad_since = bad_since or time.time()
            dac0 = any(k == "dac0" for k, _ in probs)
            if not dac0 and time.time() - bad_since < self.lost_s:
                self.on_state("warn", msg)
                continue
            now = time.time()
            self.relocks = [t for t in self.relocks if now - t < 3600]
            if len(self.relocks) >= self.max_per_hour:
                self.on_state("error", f"{msg} · {self.max_per_hour} relocks this hour, not relocking")
                continue
            self.relocks.append(now)
            self._log(f"{msg} → relock {len(self.relocks)}/{self.max_per_hour} this hour")
            self.on_state("relocking", msg)
            try:
                recover(self.d, p, {k for k, _ in probs}, self._log,
                        lambda s: self._stop.wait(s))
                ok = self.run_sequence()
            except Exception as e:
                ok = False
                self._log(f"relock error: {e}")
            self._log("relocked" if ok else "relock failed")
            bad_since = None
