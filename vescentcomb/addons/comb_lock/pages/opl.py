"""SLICE-OPL page. The comb lock module uses it for OPL #1; other modules subclass it
(``OPL2Page`` in laser_lock adds the beat-check tab and the Brimrose limits note)."""
from __future__ import annotations

import threading

import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QProgressBar, QTabWidget, QVBoxLayout,
                               QWidget, QLineEdit)

from ..sliceopl import INTEGRATOR_CORNERS_HZ
from ..autotune import AutoTuner, METRICS, NEEDS, TuneConfig
from vescentcomb.addonkit import REGISTRY
from vescentcomb.gui import theme as T
from vescentcomb.gui import widgets as W
from vescentcomb.gui.page_base import Page

CORNERS = [("off", 0.0)] + [(f"{c/1e3:g} kHz" if c >= 1e3 else f"{c:g} Hz", float(c))
                            for c in INTEGRATOR_CORNERS_HZ if c]
DIFFS = [("off", 0.0), ("10 kHz", 1e4), ("100 kHz", 1e5), ("1 MHz", 1e6)]


class _Bridge(QObject):
    trial = Signal(object, int, int)
    log = Signal(str)
    finished = Signal(object)


class OPLPage(Page):
    ROLE = "opl1"
    TITLE_TEXT = "SLICE-OPL #1 · f_rep → GPS"
    LOCK_HINT = ""                    # extra note under the lock panel (subclasses)
    DEFAULT_SCOPE_CH = 1

    def __init__(self, hub, settings, main=None, role: str = None):
        if role:
            self.ROLE = role
        super().__init__(hub, settings, main)
        title = self.TITLE_TEXT
        self.pill_servo = W.Pill("—")
        self.pill_beat = W.Pill("—")
        self.c_unit = QComboBox()
        self.c_unit.setMinimumWidth(300)
        self.c_unit.activated.connect(self.choose_unit)
        self.header(title, "", [self.pill_servo, self.pill_beat],
                    [W.button("Restore last session…", slot=self.restore_last_session),
                     W.button("Read all settings", slot=self.reread),
                     W.button("Snapshot → CSV", slot=self.save_snapshot_csv)])
        self.v.addLayout(W.hbox(self.c_unit, W.button("Identify", slot=self.identify,
                                                      tip="Flash this unit's backlight"), None))
        self.bridge = _Bridge()
        self.bridge.trial.connect(self._on_trial)
        self.bridge.log.connect(lambda m: self.hub.emit_log(self.ROLE.upper(), m))
        self.bridge.finished.connect(self._tune_done)
        self.snap = {}

        self.tabs = QTabWidget()
        self.v.addWidget(self.tabs)
        self.tabs.addTab(self._lock_tab(), "Lock && filter")
        for w, label in self.extra_tabs():
            self.tabs.addTab(w, label)
        self.tabs.addTab(self._ref_tab(), "Reference && beat input")
        self.tabs.addTab(self._aux_tab(), "Aux servo && sweep")
        self.tabs.addTab(self._io_tab(), "I/O && advanced")
        self.tabs.addTab(self._tune_tab(), "Auto-tune")
        self.v.addStretch(1)
        self.tuner = None

    def extra_tabs(self):
        """Subclasses return [(QWidget, label), …] to insert after the first tab."""
        return []

    # ---------------------------------------------------------------------------------- tabs
    def _lock_tab(self):
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 10, 0, 0)
        g.setSpacing(14)
        self.seg_servo = W.Seg(["Servo off", "Servo on"])
        self.seg_servo.changed.connect(self.set_servo)
        p = W.Panel("Lock", self.seg_servo)
        self.r_meas = W.Readout("Measured · READBN?")
        self.r_err = W.Readout("Error vs target")
        self.r_ref = W.Readout("Reference · READREF?")
        p.add(W.hbox(self.r_meas, self.r_err, self.r_ref, None))
        self.e_target = W.dspin(100.0, 10, 20000, 6, 0.001, "MHz")
        p.add(W.hbox(W.field("Target beat · BNTGT (DDS ref only)", self.e_target),
                     W.button("Set", "primary", self.set_target)))
        self.l_pll = W.label("PLL out", "lbl")
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        p.add(self.l_pll)
        p.add(self.bar)
        self.ck_hold = QCheckBox("Integrator hold")
        self.ck_hold.clicked.connect(lambda b: self.call(lambda d: d.integrator_hold(b), log=f"HOLD {b}"))
        self.l_err = W.label("", "mono")
        p.add(W.hbox(self.ck_hold, self.l_err, None))
        p.add(W.label("The OPL counter is approximate (~4×10⁻⁷). For a precise beat value, count BEAT OUT "
                      "on an external counter clocked from the same GPS reference.", "info"))
        if self.LOCK_HINT:
            p.add(W.label(self.LOCK_HINT, "hint"))
        g.addWidget(p, 0, 0)

        p = W.Panel("PLL servo filter")
        self.f_gain = W.dspin(0, -100, 100, 1, 0.5, "dB")
        self.f_int = W.combo(CORNERS)
        self.f_diff = W.combo(DIFFS)
        self.f_bias = W.dspin(0, -12, 12, 2, 0.1, "V")
        self.f_min = W.dspin(0, -12, 12, 2, 0.1, "V")
        self.f_max = W.dspin(10, -12, 12, 2, 0.1, "V")
        self.f_rng = W.dspin(0.1, 0, 12, 3, 0.01, "V")
        self.f_inv = QCheckBox("Invert")
        self.f_clamp = QCheckBox("20 dB gain clamp")
        p.add(W.grid([W.field("Gain", self.f_gain), W.field("Integrator corner", self.f_int),
                      W.field("Derivative corner", self.f_diff), W.field("Bias", self.f_bias),
                      W.field("Min (≥ −12 V)", self.f_min), W.field("Max (≤ +12 V)", self.f_max),
                      W.field("Lock range", self.f_rng)], 3))
        p.add(W.hbox(self.f_inv, self.f_clamp, None))
        p.add(W.hbox(W.button("Apply changes", "primary", self.apply_filter), None))
        p.add(W.label("Edits are staged; changed fields are outlined until Apply, then read back.", "lbl", wrap=True))
        for fw in (self.f_gain, self.f_bias, self.f_min, self.f_max, self.f_rng):
            fw.valueChanged.connect(lambda *_, fw=fw: W.mark_changed(fw, True))
        for fw in (self.f_int, self.f_diff):
            fw.currentIndexChanged.connect(lambda *_, fw=fw: W.mark_changed(fw, True))
        g.addWidget(p, 0, 1)

        p = W.Panel("ADC monitors · READVOLT", W.button("Refresh", slot=self.read_adcs))
        self.t_adc = W.table(["Ch", "Signal", "Volts"], 8)
        self.t_adc.setMinimumHeight(250)
        p.add(self.t_adc)
        g.addWidget(p, 1, 0)

        p = W.Panel("Beat error (Hz) and PLL out (V)")
        self.plot = W.plot(220)
        self.c_err = self.plot.plot(pen=W.pen(T.PLOT1))
        self.c_out = self.plot.plot(pen=W.pen(T.PLOT2))
        self.hist = W.History()
        p.add(self.plot)
        g.addWidget(p, 1, 1)
        g.setColumnStretch(0, 1)
        g.setColumnStretch(1, 1)
        return w

    def _ref_tab(self):
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 10, 0, 0)
        g.setSpacing(14)
        p = W.Panel("Reference source", W.button("DDS auto-config", slot=lambda: self.call(lambda d: d.dds_auto(), log="DDSAUTO")))
        self.r_pfd = W.Seg(["DDS", "Rear Ref In"])
        self.r_ddsint = W.Seg(["Internal", "External Ref In"])
        self.r_ddsref = W.combo([7.5, 8.0, 10.0, 12.0, 12.5])
        self.r_m1 = W.combo([1, 2, 4, 8, 16])
        self.r_m2 = W.ispin(1, 1, 16383)
        self.r_bw = W.combo([12.0, 40.0, 125.0, 300.0])
        p.add(W.grid([W.field("PFD reference", self.r_pfd), W.field("DDS clock", self.r_ddsint)], 2))
        p.add(W.grid([W.field("DDS ref freq (MHz)", self.r_ddsref), W.field("M1 divider", self.r_m1),
                      W.field("M2 divider", self.r_m2), W.field("Ext ref LPF (MHz)", self.r_bw)], 2))
        p.add(W.hbox(W.button("Apply", "primary", self.apply_ref), None))
        g.addWidget(p, 0, 0)
        p = W.Panel("Beat-note input")
        self.b_max = W.combo([1000.0, 3000.0, 12000.0])
        self.b_n1 = W.combo([1, 2, 4, 8, 16, 32, 64])
        self.b_n2 = W.ispin(1, 1, 8191)
        p.add(W.grid([W.field("Path / max (MHz)", self.b_max), W.field("N1 divider", self.b_n1),
                      W.field("N2 divider (1–8191)", self.b_n2)], 3))
        p.add(W.label("N1 choices change with the path: low/mid 1–16, high 4–64.", "lbl"))
        p.add(W.hbox(W.button("Apply", "primary", self.apply_beatin), None))
        g.addWidget(p, 0, 1)
        return w

    def _aux_tab(self):
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 10, 0, 0)
        g.setSpacing(14)
        self.a_en = W.Seg(["Off", "On"])
        p = W.Panel("AUX servo", self.a_en)
        self.a_tgt = W.dspin(5, -12, 12, 2, 0.1, "V")
        self.a_gain = W.dspin(1, 0, 47.62, 2, 0.1)
        self.a_bias = W.dspin(0, -12, 12, 2, 0.1, "V")
        self.a_min = W.dspin(0, -12, 12, 2, 0.1, "V")
        self.a_max = W.dspin(10, -12, 12, 2, 0.1, "V")
        self.a_inv = QCheckBox("Invert")
        p.add(W.grid([W.field("Target PLL out", self.a_tgt), W.field("Gain (0–47.62)", self.a_gain),
                      W.field("Bias", self.a_bias), W.field("Min", self.a_min), W.field("Max", self.a_max)], 3))
        p.add(self.a_inv)
        p.add(W.hbox(W.button("Apply", "primary", self.apply_aux), None))
        g.addWidget(p, 0, 0)
        self.s_en = W.Seg(["Off", "On"])
        p = W.Panel("Sweep / ramp", self.s_en)
        self.s_ch = W.combo([("Main servo", 0), ("Aux servo", 1)])
        self.s_n = W.ispin(200, 1, 1023)
        self.s_f = W.dspin(10, 0.1, 60, 2, 1, "Hz")
        self.s_rng = W.dspin(1, 0, 20, 2, 0.1, "V")
        self.s_adc = W.combo([("Normal ×1", 128), ("High ×8", 64)])
        p.add(W.grid([W.field("Channel", self.s_ch), W.field("Points (1–1023)", self.s_n),
                      W.field("Freq", self.s_f), W.field("Range", self.s_rng), W.field("ADC gain", self.s_adc)], 3))
        p.add(W.hbox(W.button("Apply", "primary", self.apply_sweep), None))
        g.addWidget(p, 0, 1)
        return w

    def _io_tab(self):
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 10, 0, 0)
        g.setSpacing(14)
        p = W.Panel("Outputs & inputs")
        self.io_mux = W.combo([("off", 0), ("error", 1), ("divided BN", 2), ("DDS ref", 3), ("DDS out", 4)])
        self.io_fp2 = W.combo([("PLL out", 1), ("Aux out", 2), ("error", 3), ("ground", 4), ("off", 0)])
        self.io_trig = W.combo([("none", 0), ("toggle servo", 1), ("toggle S/H", 2)])
        p.add(W.grid([W.field("Rear MUX", self.io_mux), W.field("Front out 2 source", self.io_fp2),
                      W.field("Trigger in", self.io_trig)], 3))
        self.io_checks = {k: QCheckBox(t) for k, t in (("fp1", "Front out 1 (ramp)"), ("fp2", "Front out 2"),
                                                       ("trigo", "Ramp-synced trigger out"),
                                                       ("ina", "Add In A → PLL out"), ("inb", "Add In B → Aux out"))}
        p.add(W.grid(list(self.io_checks.values()), 3))
        p.add(W.hbox(W.button("Apply", "primary", self.apply_io), None))
        g.addWidget(p, 0, 0)
        p = W.Panel("Advanced")
        p.add(W.hbox(W.button("Disable charge pump (NOCP)", slot=lambda: self.call(lambda d: d.disable_cp(), log="NOCP")),
                     W.button("Reboot OPL (*RST)…", "danger", self.reboot), None))
        self.e_raw = QLineEdit("PLLGAIN?")
        self.l_raw = W.label("", "mono")
        p.add(W.label("Raw console: send any token and see the reply.", "lbl"))
        p.add(W.hbox(self.e_raw, W.button("Send", slot=self.send_raw)))
        p.add(self.l_raw)
        g.addWidget(p, 0, 1)
        return w

    def _tune_tab(self):
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 10, 0, 0)
        g.setSpacing(14)
        g.addWidget(W.label("A phase-locked beat is a coherent carrier, so its width on an analyzer is just the "
                            "RBW. The tuner scores what the loop actually changes: noise pedestal, servo-bump height "
                            "and residual phase noise. Target and dividers are never changed.", "info"), 0, 0, 1, 2)
        key = f"ui.{self.ROLE}.tune"
        self.pill_tune = W.Pill("idle")
        p = W.Panel("Auto-tune servo filter", self.pill_tune)
        self.t_metric = W.bind(self.settings, f"{key}.metric", W.combo([(f"{v[0]} — needs {NEEDS[k][1]}", k)
                                                                     for k, v in METRICS.items()]),
                               "adev_counter")
        self.t_metric.currentIndexChanged.connect(lambda i: self._metric_needs())
        p.add(W.field("Optimise for", self.t_metric))
        self.t_ch = W.bind(self.settings, f"{key}.scope_ch", W.combo([("CH1", 1), ("CH2", 2), ("CH3", 3), ("CH4", 4)]),
                           self.DEFAULT_SCOPE_CH)
        self.t_scope = W.combo([])
        self.t_sa = W.combo([])
        for combo, k in ((self.t_scope, "scope_role"), (self.t_sa, "sa_role")):
            combo.currentIndexChanged.connect(
                lambda i, c=combo, k=k: self.settings.set(f"ui.{self.ROLE}.tune.{k}", c.itemData(i)))
        self.t_dwell = W.bind(self.settings, f"{key}.dwell", W.dspin(5, 0, 120, 1, 1, "s"), 5)
        self.t_avg = W.bind(self.settings, f"{key}.avg", W.ispin(4, 1, 64), 4)
        self.t_gmin = W.bind(self.settings, f"{key}.gmin", W.dspin(-60, -100, 100, 1, 1, "dB"), -60)
        self.t_gmax = W.bind(self.settings, f"{key}.gmax", W.dspin(-40, -100, 100, 1, 1, "dB"), -40)
        self.t_gstep = W.bind(self.settings, f"{key}.gstep", W.dspin(1, 0.1, 10, 1, 0.5, "dB"), 1)
        self.t_max = W.bind(self.settings, f"{key}.max_trials", W.ispin(60, 1, 1000), 60)
        self.t_strat = W.bind(self.settings, f"{key}.strategy", W.combo([("One at a time, then refine", "coordinate"),
                                                                         ("Full grid", "grid")]), "coordinate")
        p.add(W.grid([W.field("Dwell per trial", self.t_dwell),
                      W.field("Averages", self.t_avg), W.field("Gain from", self.t_gmin),
                      W.field("Gain to", self.t_gmax), W.field("Gain step", self.t_gstep),
                      W.field("Strategy", self.t_strat), W.field("Max trials", self.t_max)], 3))
        self.t_ints = W.bind(self.settings, f"{key}.ints", QLineEdit("50, 100, 200, 500, 1000"), "50, 100, 200, 500, 1000")
        p.add(W.field("Integrator corners to try (Hz)", self.t_ints))
        self.t_diff = W.bind(self.settings, f"{key}.use_diff", QCheckBox("Also try derivative corner (off, 10 k, 100 kHz)"), False)
        self.t_clamp = W.bind(self.settings, f"{key}.use_clamp", QCheckBox("Also try 20 dB gain clamp"), False)
        self.t_step2 = W.bind(self.settings, f"{key}.step2", QCheckBox("Move gain by at most 2 dB per step"), True)
        self.t_revert = W.bind(self.settings, f"{key}.revert", QCheckBox("Revert to starting settings if lock is lost"), True)
        for c in (self.t_diff, self.t_clamp, self.t_step2, self.t_revert):
            p.add(c)
        self.b_tune = W.button("Start auto-tune", "primary", self.start_tune)
        self.b_tstop = W.button("Stop", slot=self.stop_tune)
        self.b_best = W.button("Apply best", slot=lambda: self.tuner and self.call(lambda d: self.tuner.apply_best()))
        self.b_revert = W.button("Revert to start", slot=lambda: self.tuner and self.call(lambda d: self.tuner.revert()))
        self.l_est = W.label("", "lbl")
        p.add(W.hbox(self.b_tune, self.b_tstop, self.b_best, self.b_revert, self.l_est, None))
        g.addWidget(p, 1, 0)

        p = W.Panel("Results · score vs PLL gain")
        self.tplot = W.plot(220, "", "PLL gain (dB)")
        self.tplot.addLegend(offset=(10, 10))
        self.tune_curves = {}
        p.add(self.tplot)
        self.t_res = W.table(["Gain", "Int.", "Diff.", "Score", "Lock"], 0)
        self.t_res.setMinimumHeight(170)
        p.add(self.t_res)
        g.addWidget(p, 1, 1)
        g.setColumnStretch(0, 1)
        g.setColumnStretch(1, 1)
        return w

    # ------------------------------------------------------------------------------------ data
    def on_devices_changed(self):
        self._fill_instrument_choices()
        self.c_unit.clear()
        scan = self.hub.scan
        mine = self.hub.found.get(self.ROLE)
        if scan:
            for f in scan.by_kind("sliceopl"):
                self.c_unit.addItem(f"SLICE-OPL · SN {f.serial} · {f.address}", f.serial)
            if mine:
                W.set_combo_data(self.c_unit, mine.serial)
        if self.connected:
            self.sub.setText(f"{mine.address} · 115200 · {mine.firmware}" if mine else "connected")
            self.reread()
        else:
            self.sub.setText("not connected")

    def _fill_instrument_choices(self):
        for combo, cap, key in ((self.t_scope, "scope", "scope_role"), (self.t_sa, "spectrum", "sa_role")):
            combo.blockSignals(True)
            combo.clear()
            roles = REGISTRY.roles_with(cap)
            for r in roles:
                f = self.hub.found.get(r)
                tag = "" if self.hub.has(r) else " — not connected"
                combo.addItem(f"{REGISTRY.role_label(r)}{(' · ' + f.model) if f else ''}{tag}", r)
            if not roles:
                combo.addItem(f"no {cap} add-on installed", None)
            W.set_combo_data(combo, self.settings.get(f"ui.{self.ROLE}.tune.{key}"))
            combo.blockSignals(False)
        self._metric_needs()

    def _metric_needs(self):
        """"Optimise for" shows which instrument each choice needs and whether it is connected;
        only the picker that choice uses is enabled."""
        have = {"scope": any(self.hub.has(r) for r in REGISTRY.roles_with("scope")),
                "spectrum": any(self.hub.has(r) for r in REGISTRY.roles_with("spectrum")), None: True}
        for i in range(self.t_metric.count()):
            k = self.t_metric.itemData(i)
            if k not in METRICS:
                continue
            cap, lab = NEEDS[k]
            tag = "" if cap is None else (" ✓" if have[cap] else " (not connected)")
            self.t_metric.setItemText(i, f"{METRICS[k][0]} — needs {lab}{tag}")
        cap = NEEDS.get(self.t_metric.currentData(), (None, ""))[0]
        self.t_scope.setEnabled(cap == "scope")
        self.t_ch.setEnabled(cap == "scope")
        self.t_sa.setEnabled(cap == "spectrum")

    def choose_unit(self, i):
        serial = self.c_unit.itemData(i)
        if self.main:
            self.main.assign_unit(self.ROLE, "sliceopl", serial)

    def identify(self):
        self.call(lambda d: d.flash_identify(), log="backlight flashed")

    def reread(self):
        self.call(lambda d: d.snapshot(), self._fill)

    def _fill(self, s):
        self.snap = s
        self.e_target.setValue(s.get("target_beatnote") or 0)
        for w, k in ((self.f_gain, "pll_gain"), (self.f_bias, "pll_bias"), (self.f_min, "pll_min"),
                     (self.f_max, "pll_max"), (self.f_rng, "lock_range"), (self.a_tgt, "aux_target"),
                     (self.a_gain, "aux_gain"), (self.a_bias, "aux_bias"), (self.a_min, "aux_min"),
                     (self.a_max, "aux_max")):
            if isinstance(s.get(k), (int, float)):
                w.blockSignals(True)
                w.setValue(float(s[k]))
                w.blockSignals(False)
                W.mark_changed(w, False)
        for c, k in ((self.f_int, "integrator_corner"), (self.f_diff, "diff_corner")):
            c.blockSignals(True)
            W.set_combo_data(c, float(s.get(k) or 0))
            c.blockSignals(False)
            W.mark_changed(c, False)
        self.f_inv.setChecked(bool(s.get("pll_invert")))
        self.f_clamp.setChecked(bool(s.get("gain_clamp")))
        self.a_inv.setChecked(bool(s.get("aux_invert")))
        self.a_en.set_index(1 if s.get("aux_enabled") else 0)
        self.s_en.set_index(1 if s.get("ramp") else 0)
        self.r_pfd.set_index(0 if s.get("pfd_uses_dds") else 1)
        self.r_ddsint.set_index(0 if s.get("dds_internal") else 1)
        W.set_combo_data(self.r_ddsref, s.get("dds_ref_freq"))
        W.set_combo_data(self.r_m1, s.get("m1"))
        if isinstance(s.get("m2"), int):
            self.r_m2.setValue(s["m2"])
        W.set_combo_data(self.r_bw, s.get("ext_ref_bw"))
        W.set_combo_data(self.b_max, s.get("bn_max"))
        W.set_combo_data(self.b_n1, s.get("n1"))
        if isinstance(s.get("n2"), int):
            self.b_n2.setValue(s["n2"])
        self.settings.save_device_state(self.ROLE, {k: v for k, v in s.items()
                                                    if isinstance(v, (int, float, str, bool))})
        self.read_adcs()

    def read_adcs(self):
        def done(vals):
            for r, (name, v) in enumerate(vals.items()):
                W.set_row(self.t_adc, r, [r + 1, name.replace("_", " "), W.fmt_num(v, "{:.4f}")])
        self.call(lambda d: d.read_all_voltages(), done)

    def on_poll(self, role, d):
        if role != self.ROLE:
            return
        servo = d.get("servo_on")
        self.pill_servo.set("Servo on" if servo else "Servo off", "ok" if servo else "idle")
        self.seg_servo.set_index(1 if servo else 0)
        b, t = d.get("beatnote"), d.get("target_beatnote")
        has = isinstance(b, float) and b > 1.0
        self.pill_beat.set("Beat present" if has else "No beat on counter", "ok" if has else "warn")
        self.r_meas.set(b if has else "no beat", "si:Hz:1e6:10", None if has else T.WARN)
        off = self.settings.get("ui.lock.counter_offset_hz", 31.0) if self.ROLE == "opl1" else 0.0
        err = (t - off / 1e6 - b) * 1e6 if has and isinstance(t, float) else None
        win = self.settings.get("ui.lock.window_hz", 8.0)
        self.r_err.set(err, "si:Hz:1:4:+", T.OK if err is not None and abs(err) <= win else T.WARN)
        self.r_ref.set(d.get("reference"), "si:Hz:1e6:10")
        lo, hi, out = d.get("pll_min"), d.get("pll_max"), d.get("pll_out_v")
        if all(isinstance(x, float) for x in (lo, hi, out)) and hi > lo:
            self.bar.setValue(int(1000 * (out - lo) / (hi - lo)))
            self.l_pll.setText(f"PLL out {out:.2f} V in [PLLMIN {lo:.1f}, PLLMAX {hi:.1f}] · OPL range ±12 V")
        self.l_err.setText(f"error {W.fmt_num(d.get('error_v'), '{:.3f}')} V")
        self.ck_hold.setChecked(bool(d.get("hold")))
        self.hist.add(err=err, out=out)
        tt, y = self.hist.series("err")
        self.c_err.setData(tt, y)
        tt, y = self.hist.series("out")
        self.c_out.setData(tt, y)
        self._has_beat = has

    # --------------------------------------------------------------------------------- actions
    def set_servo(self, i):
        if i == 1 and not getattr(self, "_has_beat", True):
            if not W.confirm(self, "No beat", "The counter shows no beat. Turn the servo on anyway?"):
                self.seg_servo.set_index(0)
                return
        self.call(lambda d: d.set_servo(i == 1), log=f"SERVO {'ON' if i else 'OFF'}")

    def set_target(self):
        v = self.e_target.value()
        self.call(lambda d: d.set_target_beatnote(v), lambda r: self.remember_state(), log=f"BNTGT {v}")

    def apply_filter(self):
        g, i, df = self.f_gain.value(), self.f_int.currentData(), self.f_diff.currentData()
        b, lo, hi, rng = self.f_bias.value(), self.f_min.value(), self.f_max.value(), self.f_rng.value()
        inv, cl = self.f_inv.isChecked(), self.f_clamp.isChecked()

        def work(d):
            d.set_pll_limits(lo, hi, b)
            d.set_pll_gain(g)
            d.set_integrator_corner(i)
            d.set_diff_corner(df)
            d.set_lock_range(rng)
            d.set_pll_invert(inv)
            d.set_gain_clamp(cl)
            return d.snapshot()
        self.call(work, self._fill, log=f"filter: gain {g} dB, int {i} Hz, min {lo} max {hi} bias {b}")

    def apply_ref(self):
        pfd, ddsint = self.r_pfd.index() == 0, self.r_ddsint.index() == 0
        ref, m1, m2, bw = self.r_ddsref.currentData(), self.r_m1.currentData(), self.r_m2.value(), self.r_bw.currentData()
        self.call(lambda d: (d.set_pfd_uses_dds(pfd), d.set_dds_internal(ddsint), d.set_dds_ref_freq(ref),
                             d.set_m1(m1), d.set_m2(m2), d.set_ext_ref_bw(bw)), lambda r: self.reread(),
                  log="reference settings written")

    def apply_beatin(self):
        mx, n1, n2 = self.b_max.currentData(), self.b_n1.currentData(), self.b_n2.value()
        self.call(lambda d: (d.set_bn_max(mx), d.set_n1(n1), d.set_n2(n2)), lambda r: self.reread(),
                  log=f"beat input: path {mx}, N1 {n1}, N2 {n2}")

    def apply_aux(self):
        vals = (self.a_en.index() == 1, self.a_inv.isChecked(), self.a_tgt.value(), self.a_gain.value(),
                self.a_bias.value(), self.a_min.value(), self.a_max.value())

        def work(d):
            en, inv, tgt, g, b, lo, hi = vals
            d.set_aux_invert(inv); d.set_aux_target(tgt); d.set_aux_gain(g); d.set_aux_bias(b)
            d.set_aux_min(lo); d.set_aux_max(hi); d.set_aux_enabled(en)
        self.call(work, lambda r: self.reread(), log="aux servo written")

    def apply_sweep(self):
        vals = (self.s_en.index() == 1, self.s_ch.currentData(), self.s_n.value(), self.s_f.value(),
                self.s_rng.value(), self.s_adc.currentData())

        def work(d):
            en, ch, n, f, r, a = vals
            d.set_ramp_channel(ch); d.set_ramp_points(n); d.set_ramp_freq(f); d.set_ramp_range(r)
            d.set_ramp_adc_gain(a); d.set_ramp(en)
        self.call(work, log="sweep written")

    def apply_io(self):
        c = {k: b.isChecked() for k, b in self.io_checks.items()}
        mux, fp2, trig = self.io_mux.currentData(), self.io_fp2.currentData(), self.io_trig.currentData()

        def work(d):
            d.set_rear_mux(mux); d.set_front_out2_mux(fp2); d.set_trigger_in(trig)
            d.set_front_out1(c["fp1"]); d.set_front_out2(c["fp2"]); d.set_trigger_out(1 if c["trigo"] else 0)
            d.set_front_in_a(c["ina"]); d.set_front_in_b(c["inb"])
        self.call(work, log="I/O written")

    def reboot(self):
        if W.confirm(self, "Reboot OPL", "Reboot this SLICE-OPL? Any lock will drop.", "Reboot", True):
            self.call(lambda d: d.reset(), log="*RST")

    def send_raw(self):
        cmd = self.e_raw.text().strip()
        if cmd:
            self.call(lambda d: d.query(cmd), lambda r: self.l_raw.setText(f"{cmd} → {r}"))

    # ------------------------------------------------------------------------------- auto-tune
    def _tune_cfg(self) -> TuneConfig:
        gains = list(np.arange(self.t_gmin.value(), self.t_gmax.value() + 1e-9, self.t_gstep.value()))
        try:
            ints = [float(x) for x in self.t_ints.text().replace(";", ",").split(",") if x.strip()]
        except ValueError:
            ints = [50.0, 100.0, 200.0, 500.0, 1000.0]
        return TuneConfig(metric=self.t_metric.currentData(), gains_db=gains, int_corners_hz=ints,
                          diff_corners_hz=[0.0, 1e4, 1e5] if self.t_diff.isChecked() else None,
                          gain_clamp=[False, True] if self.t_clamp.isChecked() else None,
                          strategy=self.t_strat.currentData(), dwell_s=self.t_dwell.value(),
                          averages=self.t_avg.value(), max_trials=self.t_max.value(),
                          max_gain_step_db=2.0 if self.t_step2.isChecked() else 100.0,
                          revert_on_loss=self.t_revert.isChecked(), scope_channel=self.t_ch.currentData())

    def start_tune(self):
        cfg = self._tune_cfg()
        scope_role, sa_role = self.t_scope.currentData(), self.t_sa.currentData()
        need = (scope_role, "scope") if cfg.metric == "phase_scope" else \
            ((sa_role, "spectrum analyzer") if cfg.metric.endswith("_sa") else None)
        if need and not (need[0] and self.hub.has(need[0])):
            W.notice(self, "Auto-tune", f"This metric needs a {need[1]} add-on installed and its instrument "
                     "connected (Devices…).")
            return
        opl = self.hub.device(self.ROLE)
        self.tuner = AutoTuner(opl, cfg, scope=self.hub.device(scope_role) if scope_role else None,
                               sa=self.hub.device(sa_role) if sa_role else None,
                               on_trial=lambda t, i, n: self.bridge.trial.emit(t, i, n),
                               on_log=lambda m: self.bridge.log.emit(m))
        n = self.tuner.estimate_trials()
        if not W.confirm(self, "Auto-tune", f"Run about {n} trials (~{n * (cfg.dwell_s + 2) / 60:.1f} min)? "
                         "The servo filter will be changed while locked.", "Start"):
            return
        self.t_res.setRowCount(0)
        self.tplot.clear()
        self.tune_curves = {}
        self.pill_tune.set("running", "warn")
        self.l_est.setText(f"0 / {n}")

        def run():
            best = self.tuner.run()
            self.bridge.finished.emit(best)
        threading.Thread(target=run, daemon=True).start()

    def stop_tune(self):
        if self.tuner:
            self.tuner.stop()

    def _on_trial(self, t, i, n):
        self.l_est.setText(f"{i} / {n}")
        r = self.t_res.rowCount()
        W.set_row(self.t_res, r, [f"{t.gain_db:g} dB", f"{t.int_hz:g} Hz", t.diff_hz if t.diff_hz is not None else "—",
                                  W.fmt_num(t.score, "{:.4g}"), "held" if t.locked else "LOST"],
                  {4: T.OK if t.locked else T.BAD})
        colors = [T.PLOT1, T.PLOT3, T.PLOT2, "#E35FD0", "#B3BCC7"]
        key = t.int_hz
        if key not in self.tune_curves:
            c = colors[len(self.tune_curves) % len(colors)]
            self.tune_curves[key] = (self.tplot.plot([], [], pen=None, symbol="o", symbolSize=6,
                                                     symbolBrush=c, name=f"{key:g} Hz"), [], [])
        item, xs, ys = self.tune_curves[key]
        if t.locked:
            xs.append(t.gain_db)
            ys.append(t.score)
            order = np.argsort(xs)
            item.setData(np.array(xs)[order], np.array(ys)[order])

    def _tune_done(self, best):
        if best is None:
            self.pill_tune.set("no result", "bad")
        else:
            self.pill_tune.set(f"best {best.gain_db:g} dB · {best.int_hz:g} Hz", "ok")
            self.hub.emit_log(self.ROLE.upper(), f"auto-tune best: gain {best.gain_db:g} dB, int {best.int_hz:g} Hz, "
                                                 f"score {best.score:.4g}")
            self.settings.set(f"ui.{self.ROLE}.tune.last_best", best.as_dict())
        self.reread()
