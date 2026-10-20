"""Lock sequence page: f_ceo first, then the GPS cavity walk, then (optionally) OPL #2."""
from __future__ import annotations

import threading

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QGridLayout, QHBoxLayout, QLabel, QTableWidgetItem,
                               QVBoxLayout, QWidget, QAbstractItemView)

from ..gps_lock import STEP_IDS, STEP_TITLES, LockParams, LockSequence, LockWatchdog
from vescentcomb.gui import theme as T
from vescentcomb.gui import widgets as W
from vescentcomb.gui.page_base import Page


class _Bridge(QObject):
    step = Signal(object)
    log = Signal(str)
    sample = Signal(dict)
    ask = Signal(str, object, object)     # question, rows, (event, holder)
    finished = Signal(bool)
    started = Signal()
    wd_state = Signal(str, str)


class LockSequencePage(Page):
    TITLE = "Comb lock sequence"

    def __init__(self, hub, settings, main=None):
        super().__init__(hub, settings, main)
        self.pill = W.Pill("idle")
        self.ck_dry = W.bind(settings, "ui.lock.dry_run", QCheckBox("Dry run (read only)"), False)
        self.b_pause = W.button("Pause", slot=self.pause)
        self.b_abort = W.button("Abort", "danger", self.abort)
        self.b_start = W.button("Start", "primary", self.start)
        self.ck_wd = QCheckBox("Watchdog: keep f_ceo + GPS OPL locked")
        self.ck_wd.setToolTip("After a successful lock, watch f_ceo (lock, phase, DAC0 centered) and OPL #1 "
                              "(servo, slow servo) and run the sequence again when one is lost.")
        self.pill_wd = W.Pill("watchdog off")
        self.header("Comb lock sequence", "Attaches to the SLICE-FPGA-II and locks f_ceo first (keeping the box's own "
                    "settings, fixing only what differs from your profile), then walks the FFC-100 cavity setpoint "
                    "until the f_rep beat is inside the window and closes OPL #1 and the FFC slow servo.",
                    [self.pill, self.pill_wd], [self.ck_wd, self.ck_dry, self.b_pause, self.b_abort, self.b_start])
        self.sub.setWordWrap(True)
        self.sub.setObjectName("lbl")

        row = QHBoxLayout()
        row.setSpacing(14)
        self.v.addLayout(row)
        # steps --------------------------------------------------------------------------------------
        p = W.Panel("Steps")
        self.l_elapsed = W.label("", "lbl")
        p.add_right(self.l_elapsed)
        self.rows = {}
        for i, sid in enumerate(STEP_IDS):
            r = W.StepRow(i, STEP_TITLES[sid])
            self.rows[sid] = r
            p.add(r)
        self.ck_ask = W.bind(settings, "ui.lock.ask_fpga", QCheckBox("Ask before writing any FPGA setting"), True)
        p.add(self.ck_ask)
        p.setMaximumWidth(460)
        row.addWidget(p, 2)

        right = QVBoxLayout()
        right.setSpacing(14)
        row.addLayout(right, 3)
        tiles = QHBoxLayout()
        self.t_err = W.Readout("Beat error (target − measured)", big=True, unit="Hz")
        self.t_cav = W.Readout("Cavity |T − setpoint|", big=True, unit="mK")
        self.t_sp = W.Readout("Cavity setpoint", big=True, unit="°C")
        self.t_steps = W.Readout("Steps taken", big=True)
        for t in (self.t_err, self.t_cav, self.t_sp, self.t_steps):
            f = W.Panel()
            f.add(t)
            tiles.addWidget(f)
        right.addLayout(tiles)

        p = W.Panel("Beat error during walk (Hz)")
        self.plot = W.plot(230, "Hz", "s")
        self.c_err = self.plot.plot(pen=W.pen(T.PLOT1, 1.6))
        self.win = pg.LinearRegionItem(values=(-8, 8), orientation="horizontal", movable=False,
                                       brush=pg.mkBrush(24, 57, 46, 140), pen=pg.mkPen(T.OK))
        self.plot.addItem(self.win)
        self.marks = self.plot.plot([], [], pen=None, symbol="t1", symbolSize=9, symbolBrush=T.WARN)
        p.add(self.plot)
        right.addWidget(p)

        prm = QHBoxLayout()
        prm.setSpacing(14)
        p = W.Panel("Parameters", W.button("Reset to defaults", slot=self.reset_params))
        d = LockParams()
        k = "ui.lock"
        self.e_off = W.bind(settings, f"{k}.counter_offset_hz", W.dspin(d.counter_offset_hz, -1e4, 1e4, 1, 1, "Hz"))
        self.e_win = W.bind(settings, f"{k}.window_hz", W.dspin(d.window_hz, 0.1, 1e5, 1, 1, "Hz"))
        self.e_settle = W.bind(settings, f"{k}.cav_settle_mk", W.dspin(d.cav_settle_mk, 0.01, 100, 2, 0.1, "mK"))
        self.e_poll = W.bind(settings, f"{k}.poll_s", W.dspin(d.poll_s, 0.05, 600, 2, 0.5, "s"))
        self.e_dwell = W.bind(settings, f"{k}.confirm_dwell_s", W.dspin(d.confirm_dwell_s, 0, 600, 1, 1, "s"))
        self.e_exc = W.bind(settings, f"{k}.max_excursion_c", W.dspin(d.max_excursion_c, 0.001, 10, 3, 0.1, "°C"))
        self.e_max = W.bind(settings, f"{k}.max_steps", W.ispin(d.max_steps, 1, 10000))
        self.e_post = W.bind(settings, f"{k}.post_servo_wait_s", W.dspin(d.post_servo_wait_s, 0, 600, 1, 1, "s"))
        self.e_phase = W.bind(settings, f"{k}.fceo_max_phase_rad", W.dspin(d.fceo_max_phase_rad, 0.1, 10, 2, 0.1, "rad"))
        self.e_pzlo = W.bind(settings, f"{k}.pzt_min_v", W.dspin(d.pzt_min_v, -200, 200, 2, 0.5, "V"))
        self.e_pzhi = W.bind(settings, f"{k}.pzt_max_v", W.dspin(d.pzt_max_v, -200, 200, 2, 0.5, "V"))
        self.e_rtry = W.bind(settings, f"{k}.relock_tries", W.ispin(d.relock_tries, 0, 20))
        self.e_rwait = W.bind(settings, f"{k}.relock_wait_s", W.dspin(d.relock_wait_s, 0, 600, 1, 1, "s"))
        self.e_dac0 = W.bind(settings, f"{k}.dac0_max_pct", W.dspin(100 * d.dac0_max_frac, 1, 50, 1, 1, "%"))
        self.ck_pzt = W.bind(settings, f"{k}.check_pzt", QCheckBox("check FFC PZT reading"), d.check_pzt)
        p.add(W.grid([W.field("Counter offset", self.e_off), W.field("Lock window ±", self.e_win),
                      W.field("Cavity settle tol.", self.e_settle), W.field("Poll interval", self.e_poll),
                      W.field("Confirm dwell", self.e_dwell), W.field("Max setpoint excursion", self.e_exc),
                      W.field("Max steps", self.e_max), W.field("Wait after servo on", self.e_post),
                      W.field("f_ceo lock: phase below", self.e_phase), W.field("Relock tries", self.e_rtry),
                      W.field("DAC0 max from center (of full range)", self.e_dac0),
                      W.field("Pause before retry", self.e_rwait),
                      W.field("FFC PZT valid from", self.e_pzlo), W.field("FFC PZT valid to", self.e_pzhi),
                      W.field("", self.ck_pzt)], 2))
        p.add(W.label("After every step (and every cavity move) the locks made so far are re-checked: comb "
                      "mode-locked, f_ceo locked below the phase limit with DAC0 near center, OPL #1 servo on, slow "
                      "servo on (and the PZT reading, if ticked). If one fails the sequence pauses, relocks and tries "
                      "again. DAC0 too far from center: f_ceo and OPL #1 are unlocked, DAC0 is set to 0 V and the "
                      "whole sequence restarts.", "lbl", wrap=True))
        prm.addWidget(p)
        p = W.Panel("Step size table", W.button("+ Row", slot=self.add_row))
        self.t_steps_tbl = W.table(["|error| at least (Hz)", "Setpoint step (°C)"], 0)
        self.t_steps_tbl.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.t_steps_tbl.itemChanged.connect(self._save_table)
        self.t_steps_tbl.setMinimumHeight(150)
        p.add(self.t_steps_tbl)
        p.add(W.label("Beat LOW (error > 0) → setpoint down · beat HIGH (error < 0) → setpoint up", "lbl", wrap=True))
        prm.addWidget(p)
        right.addLayout(prm)

        p = W.Panel("Sequence log", W.button("Save log…", slot=self.save_log))
        self.log = W.LogView()
        self.log.setMinimumHeight(160)
        p.add(self.log)
        right.addWidget(p)
        self.v.addStretch(1)

        self._load_table()
        self.bridge = _Bridge()
        self.bridge.step.connect(self._on_step)
        self.bridge.log.connect(self._on_log)
        self.bridge.sample.connect(self._on_sample)
        self.bridge.ask.connect(self._on_ask)
        self.bridge.finished.connect(self._on_finished)
        self.seq = None
        self.samples = []
        self.e_win.valueChanged.connect(lambda v: self.win.setRegion((-v, v)))
        self.win.setRegion((-self.e_win.value(), self.e_win.value()))
        self.b_pause.setEnabled(False)
        self.b_abort.setEnabled(False)
        self.wd = None
        self.bridge.started.connect(self._on_started)
        self.bridge.wd_state.connect(self._on_wd_state)
        self.ck_wd.toggled.connect(self._wd_toggled)
        if settings.get("ui.lock.watchdog", False):
            self.ck_wd.setChecked(True)

    # ---- params --------------------------------------------------------------------------------------
    def _load_table(self):
        rows = self.settings.get("ui.lock.step_table") or LockParams().step_table
        self.t_steps_tbl.blockSignals(True)
        self.t_steps_tbl.setRowCount(0)
        for r, (th, st) in enumerate(rows):
            self.t_steps_tbl.insertRow(r)
            self.t_steps_tbl.setItem(r, 0, QTableWidgetItem(f"{th:g}"))
            self.t_steps_tbl.setItem(r, 1, QTableWidgetItem(f"{st:g}"))
        self.t_steps_tbl.blockSignals(False)

    def _table(self):
        out = []
        for r in range(self.t_steps_tbl.rowCount()):
            try:
                out.append((float(self.t_steps_tbl.item(r, 0).text()), float(self.t_steps_tbl.item(r, 1).text())))
            except (AttributeError, ValueError):
                continue
        return out

    def _save_table(self, *_):
        t = self._table()
        if t:
            self.settings.set("ui.lock.step_table", [list(x) for x in t])

    def add_row(self):
        r = self.t_steps_tbl.rowCount()
        self.t_steps_tbl.insertRow(r)
        self.t_steps_tbl.setItem(r, 0, QTableWidgetItem("0"))
        self.t_steps_tbl.setItem(r, 1, QTableWidgetItem("0.005"))

    def reset_params(self):
        d = LockParams()
        for w, v in ((self.e_off, d.counter_offset_hz), (self.e_win, d.window_hz), (self.e_settle, d.cav_settle_mk),
                     (self.e_poll, d.poll_s), (self.e_dwell, d.confirm_dwell_s), (self.e_exc, d.max_excursion_c),
                     (self.e_max, d.max_steps), (self.e_post, d.post_servo_wait_s),
                     (self.e_phase, d.fceo_max_phase_rad), (self.e_pzlo, d.pzt_min_v), (self.e_pzhi, d.pzt_max_v),
                     (self.e_rtry, d.relock_tries), (self.e_rwait, d.relock_wait_s),
                     (self.e_dac0, 100 * d.dac0_max_frac)):
            w.setValue(v)
        self.settings.set("ui.lock.step_table", [list(x) for x in d.step_table])
        self._load_table()

    def params(self) -> LockParams:
        return LockParams(counter_offset_hz=self.e_off.value(), window_hz=self.e_win.value(),
                          cav_settle_mk=self.e_settle.value(), poll_s=self.e_poll.value(),
                          confirm_dwell_s=self.e_dwell.value(), post_servo_wait_s=self.e_post.value(),
                          max_excursion_c=self.e_exc.value(), max_steps=self.e_max.value(),
                          step_table=self._table() or LockParams().step_table,
                          fceo_max_phase_rad=self.e_phase.value(), pzt_min_v=self.e_pzlo.value(),
                          pzt_max_v=self.e_pzhi.value(), relock_tries=self.e_rtry.value(),
                          relock_wait_s=self.e_rwait.value(), dac0_max_frac=self.e_dac0.value() / 100.0,
                          check_pzt=self.ck_pzt.isChecked(),
                          ask_before_fpga_write=self.ck_ask.isChecked(),
                          dry_run=self.ck_dry.isChecked())

    # ---- run --------------------------------------------------------------------------------------------
    def _devices(self):
        return {r: self.hub.device(r) for r in ("ffc", "fpga", "opl1") if self.hub.has(r)}

    def _new_sequence(self, devs, params=None):
        self.seq = LockSequence(devs, params or self.params(), self.settings.get("profiles.fpga", {}),
                                on_step=self.bridge.step.emit, on_log=self.bridge.log.emit,
                                on_sample=self.bridge.sample.emit, ask=self._ask_blocking)
        return self.seq

    def start(self):
        devs = self._devices()
        if "ffc" not in devs or "opl1" not in devs:
            W.notice(self, "Lock sequence", "The FFC-100 and OPL #1 must be connected.")
            return
        if self.wd is not None:
            self.wd.hold.set()                     # a manual run: the watchdog waits
        self._new_sequence(devs)
        self._on_started()
        self.hub.emit_log("SEQ", "lock sequence started" + (" (dry run)" if self.ck_dry.isChecked() else ""))

        def run():
            ok = self.seq.run()
            self.bridge.finished.emit(ok)
        threading.Thread(target=run, daemon=True).start()

    def _on_started(self):
        for sid, r in self.rows.items():
            r.set("wait", " ")
        self.samples = []
        self.c_err.setData([], [])
        self.marks.setData([], [])
        self.pill.set("running", "warn")
        self.b_start.setEnabled(False)
        self.b_pause.setEnabled(True)
        self.b_abort.setEnabled(True)

    def _run_for_watchdog(self) -> bool:
        """Called from the watchdog thread: one full sequence, shown on this page."""
        p = self.params()
        p.dry_run = False
        p.ask_before_fpga_write = False
        seq = self._new_sequence(self.wd.d, p)
        self.bridge.started.emit()
        ok = seq.run()
        self.bridge.finished.emit(ok)
        return ok

    # ---- watchdog -----------------------------------------------------------------------------------------
    def _wd_toggled(self, on):
        self.settings.set("ui.lock.watchdog", bool(on))
        if not on:
            if self.wd is not None:
                self.wd.stop()
                self.wd = None
            self.pill_wd.set("watchdog off", "idle")
            return
        devs = self._devices()
        if "ffc" not in devs or "opl1" not in devs:
            self.pill_wd.set("watchdog: connect FFC + OPL #1", "warn")
            return
        if self.wd is None:
            self.wd = LockWatchdog(devs, self.params, self._run_for_watchdog,
                                   on_log=self.bridge.log.emit, on_state=self.bridge.wd_state.emit)
            if self.seq is not None and self.seq.thread_alive():
                self.wd.hold.set()
            self.wd.start()
            self.hub.emit_log("SEQ", "lock watchdog on")

    def _on_wd_state(self, st, msg):
        kind = {"ok": "ok", "watching": "idle", "warn": "warn", "relocking": "warn", "error": "bad"}.get(st, "idle")
        self.pill_wd.set(f"watchdog: {st}", kind)
        self.pill_wd.setToolTip(msg)

    def _ask_blocking(self, question, rows=None):
        ev = threading.Event()
        holder = {"ok": False}
        self.bridge.ask.emit(question, rows, (ev, holder))
        ev.wait()
        return holder["ok"]

    def _on_ask(self, question, rows, handle):
        ev, holder = handle
        if rows and not W.CONFIRM["on"]:
            holder["ok"] = True
        elif rows:
            dlg = W.DiffDialog(self, "Lock sequence", question,
                               [(r["key"], r["box"], r["profile"],
                                 "drops lock" if r["lock_affecting"] else "safe while locked") for r in rows],
                               "Write profile values")
            holder["ok"] = bool(dlg.exec())
        else:
            holder["ok"] = W.confirm(self, "Lock sequence", question)
        ev.set()

    def pause(self):
        if not self.seq:
            return
        if self.seq.paused:
            self.seq.resume()
            self.b_pause.setText("Pause")
            self.pill.set("running", "warn")
        else:
            self.seq.pause()
            self.b_pause.setText("Resume")
            self.pill.set("paused", "idle")

    def abort(self):
        if self.seq:
            self.seq.stop()

    def _on_step(self, st):
        self.rows[st.id].set(st.status, st.detail)
        n = list(STEP_IDS).index(st.id)
        if st.status == "run":
            self.pill.set(f"running · step {n} of {len(STEP_IDS) - 1}", "warn")

    def _on_log(self, m):
        self.log.appendPlainText(m)
        self.hub.emit_log("SEQ", m[10:] if len(m) > 10 else m)

    def _on_sample(self, s):
        self.samples.append(s)
        err = s.get("err_hz")
        self.t_err.set(err, "{:+.1f}", T.OK if err is not None and abs(err) <= self.e_win.value() else T.WARN)
        cav, sp = s.get("cav_temp"), s.get("setpoint")
        if isinstance(cav, float) and isinstance(sp, float):
            self.t_cav.set(abs(cav - sp) * 1e3, "{:.2f}")
        self.t_sp.set(sp, "{:.4f}")
        self.t_steps.set(s.get("steps"), "{} of max " + str(self.e_max.value()))
        t = np.array([x["t"] for x in self.samples])
        e = np.array([x["err_hz"] if x["err_hz"] is not None else np.nan for x in self.samples])
        self.c_err.setData(t, e)
        st = np.array([x["steps"] for x in self.samples])
        idx = np.where(np.diff(st, prepend=st[0]) > 0)[0]
        if len(idx):
            self.marks.setData(t[idx], e[idx])
        if self.seq:
            import time
            self.l_elapsed.setText(f"elapsed {time.time() - self.seq.t0:.0f} s")

    def _on_finished(self, ok):
        self.pill.set("finished" if ok else "stopped", "ok" if ok else "bad")
        self.b_start.setEnabled(True)
        self.b_pause.setEnabled(False)
        self.b_abort.setEnabled(False)
        self.b_pause.setText("Pause")
        self.settings.set("ui.lock.last_run", {"ok": ok, "steps": self.seq.n_steps if self.seq else 0})
        if self.wd is not None:
            self.wd.hold.clear()                   # watch again after a manual run
        if self.main:
            self.main.after_lock_sequence()

    def save_log(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Save log", "lock_sequence.log", "Log (*.log *.txt)")
        if path:
            with open(path, "w") as f:
                f.write(self.log.toPlainText())
