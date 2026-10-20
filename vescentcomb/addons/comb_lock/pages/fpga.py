"""SLICE-FPGA-II page: attach, box-vs-profile, f_ceo / optical loops, spectrum, phase noise,
monitor/watchdog, config file and firmware. Talks to the built-in ``fpga`` package (SliceFPGA_II_modern)."""
from __future__ import annotations

import os
import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QCheckBox, QFileDialog, QGridLayout

from ..slicefpga import DDC_FILTERS, LOCK_AFFECTING
from vescentcomb.settings import default_data_dir
from vescentcomb.gui import theme as T
from vescentcomb.gui import widgets as W
from vescentcomb.gui.page_base import Page

CEO_FIELDS = [("ceo.ref_freq_hz", "Reference (Hz)", 1), ("ceo.vco_gain", "VCO gain DAC0 (Hz/V)", 3),
              ("ceo.kp", "kp (dB)", 2), ("ceo.fi", "fi (Hz)", 1), ("ceo.fii", "fii (Hz)", 1),
              ("ceo.fd", "fd (Hz)", 1), ("ceo.fdf", "fdf (Hz)", 1)]
DDC_ITEMS = [(f"{name} ({i})", i) for i, name in DDC_FILTERS.items()]


def _config_dir():
    from .. import fpga
    return str(fpga.CONFIG_DIR)


class FPGAPage(Page):
    TITLE = "SLICE-FPGA-II"
    ROLE = "fpga"

    def __init__(self, hub, settings, main=None):
        super().__init__(hub, settings, main)
        self.pill_ceo = W.Pill("—")
        self.pill_opt = W.Pill("—")
        self.header("SLICE-FPGA-II", "not connected", [self.pill_ceo, self.pill_opt],
                    [W.button("Attach (keep box settings)", "primary", self.attach),
                     W.button("Save box → profile", slot=self.save_profile)])
        self.v.addWidget(W.label("Normal connect is Attach: it reads what the box is running and changes "
                                 "nothing. Settings below are read back from the FPGA registers. Push config "
                                 "(bottom right) rewrites every register and ramps the 100 V boost converter, "
                                 "so it only runs when you press it.", "info"))

        # box vs profile -----------------------------------------------------------------------
        self.pill_diff = W.Pill("no profile")
        p = W.Panel("Box vs profile (profile = your saved settings on this PC)", self.pill_diff)
        self.t_diff = W.table(["Write", "Setting", "On box now", "Profile", "Effect on lock"], 0)
        self.t_diff.setMinimumHeight(110)
        p.add(self.t_diff)
        self.b_write = W.button("⬇  Write profile → box  (ticked rows)", "primary", self.write_checked)
        self.b_save2 = W.button("⬆  Save box → profile  (overwrite profile)", slot=self.save_profile)
        self.b_cmp = W.button("⟳  Compare now", slot=self.compare)
        for b in (self.b_write, self.b_save2, self.b_cmp):
            b.setMinimumHeight(38)
            b.setStyleSheet("font-size:14px; font-weight:600; padding:6px 16px;")
        p.add(W.hbox(self.b_write, self.b_save2, self.b_cmp, None))
        p.add(W.label("Write profile → box sends the profile value of each ticked row to the SLICE-FPGA-II. "
                      "Save box → profile copies what the box runs now into the profile on this PC; "
                      "nothing is sent to the box.", "hint", wrap=True))
        self.v.addWidget(p)
        self.diff_rows = []

        g = QGridLayout()
        g.setSpacing(14)
        self.v.addLayout(g)

        # f_ceo loop ---------------------------------------------------------------------------------
        p = W.Panel("f_ceo loop (ADC 0 → DDC 0 → PLL 0 → DAC 0)")
        self.r_phase = W.Readout("Integrated phase noise", big=True, unit="rad (target < 1)")
        self.r_ctr = W.Readout("Counter error", big=True, unit="Hz")
        p.add(W.hbox(self.r_phase, self.r_ctr, None))
        self.b_ceo = W.button("Lock f_ceo", "primary", lambda: self.toggle_lock("ceo"))
        p.add(W.hbox(self.b_ceo, None))
        self.ceo_edits = {}
        items = []
        for key, cap, dec in CEO_FIELDS:
            e = W.dspin(0, -1e12, 1e12, dec, 1)
            self.ceo_edits[key] = e
            items.append(W.field(cap, e))
        self.seg_sign = W.Seg(["+", "−"])
        items.append(W.field("VCO sign", self.seg_sign))
        self.c_ddc = W.combo(DDC_ITEMS, 1)
        items.append(W.field("DDC filter", self.c_ddc))
        p.add(W.grid(items, 3))
        self.ck_kp = QCheckBox("P branch (chkKp)")
        self.ck_kd = QCheckBox("D branch (chkKd)")
        p.add(W.hbox(self.ck_kp, self.ck_kd, None))
        self.e_dac0 = W.dspin(0, -1, 1, 4, 0.001, "V")
        p.add(W.hbox(W.field("DAC 0 offset (lock centre)", self.e_dac0),
                     W.button("Set offset", slot=self.apply_dac0), None))
        p.add(W.hbox(W.button("Apply loop settings", "primary", self.apply_ceo),
                     W.button("Re-read", slot=self.reread), None))
        self.hint_ref = W.label("Reference is 21.4 MHz in the UCF config; other notes give f_ceo = 21.6 MHz. "
                                "Confirm before the first lock.", "hint")
        p.add(self.hint_ref)
        g.addWidget(p, 0, 0, 3, 1)

        # clock ----------------------------------------------------------------------------------------
        p = W.Panel("Clock")
        self.seg_clk = W.Seg(["External 20 MHz (GPS ×2)", "Internal 200 MHz"])
        self.seg_clk.changed.connect(self.set_clock)
        p.add(W.hbox(self.seg_clk, None))
        self.r_fs = W.Readout("fs")
        self.r_mmcm = W.Readout("MMCM")
        self.r_ext = W.Readout("Ext clk readout*")
        self.r_temp = W.Readout("Zynq temp")
        p.add(W.hbox(self.r_fs, self.r_mmcm, self.r_ext, self.r_temp, None))
        p.add(W.label("* measured against the undisciplined Zynq 200 MHz, so a ppm-level offset is expected.",
                      "lbl", wrap=True))
        g.addWidget(p, 0, 1)

        # optical ----------------------------------------------------------------------------------------
        p = W.Panel("Optical loop (ADC 1 → DAC 1 fast, DAC 2 slow)")
        self.e_opt_ref = W.dspin(0, 0, 1e9, 1, 1, "Hz")
        self.seg_osign = W.Seg(["+", "−"])
        p.add(W.grid([W.field("Reference", self.e_opt_ref), W.field("VCO sign", self.seg_osign)], 2))
        self.r_omode = W.Readout("Integrators")
        self.r_dac1 = W.Readout("DAC 1", unit="V")
        self.r_dac2 = W.Readout("DAC 2", unit="V")
        self.r_oerr = W.Readout("Counter error", unit="Hz")
        p.add(W.hbox(self.r_omode, self.r_dac1, self.r_dac2, self.r_oerr, None))
        self.b_opt = W.button("Lock optical", slot=lambda: self.toggle_lock("optical"))
        p.add(W.hbox(self.b_opt, W.button("Apply", slot=self.apply_opt), None))
        p.add(W.label("Needs FFC PZT gain ×10.", "lbl"))
        g.addWidget(p, 1, 1)

        # watchdog -----------------------------------------------------------------------------------------
        self.pill_dac0 = W.Pill("DAC0 —")
        p = W.Panel("Monitor", self.pill_dac0)
        self.ck_log = W.bind(settings, "ui.fpga.monitor_log", QCheckBox("Log counters to CSV (4 Hz)"), False)
        self.ck_log.toggled.connect(self.toggle_monitor)
        p.add(W.hbox(self.ck_log, None))
        self.r_dac0pos = W.Readout("DAC0 from center (0 V)", unit="% of range")
        p.add(W.hbox(self.r_dac0pos, None))
        p.add(W.label("The lock watchdog (f_ceo + GPS OPL #1, DAC0 recenter) is on the Comb lock sequence page.",
                      "lbl", wrap=True))
        self.l_mon = W.label("", "mono")
        p.add(self.l_mon)
        g.addWidget(p, 2, 1)

        # firmware & config ---------------------------------------------------------------------------------
        p = W.Panel("Config file & firmware")
        self.c_cfg = W.combo([])
        self._fill_configs()
        self.c_cfg.currentIndexChanged.connect(self._cfg_chosen)
        p.add(W.hbox(W.field("XML parameters used by Push config", self.c_cfg),
                     W.button("Browse…", slot=self.browse_config), None))
        p.add(W.hbox(W.button("Push config…", "danger", self.push_config),
                     W.button("Program FPGA…", "danger", self.program_fpga), None))
        p.add(W.label("Program FPGA reloads red_pitaya_top_extint_clk.bit (volatile); push config afterwards.",
                      "lbl", wrap=True))
        g.addWidget(p, 3, 0, 1, 2)
        g.setColumnStretch(0, 3)
        g.setColumnStretch(1, 2)

        # spectrum -------------------------------------------------------------------------------------------
        self.seg_adc = W.bind(settings, "ui.fpga.adc", W.Seg(["ADC 0 · f_ceo", "ADC 1 · f_opt"]), 0)
        p = W.Panel("Input spectrum with DDC pass band (−3 dB)", self.seg_adc)
        self.ck_spec = W.bind(settings, "ui.fpga.spec_auto5", QCheckBox("Auto-refresh every 5 s"), True)
        self.c_avg = W.bind(settings, "ui.fpga.spec_avg", W.combo([("Avg 1", 1), ("Avg 4", 4), ("Avg 16", 16)], 4), 4)
        p.add_right(W.button("Refresh", slot=self.refresh_spectrum))
        p.add_right(self.ck_spec)
        p.add_right(self.c_avg)
        self.spec = W.plot(230, "Level (dBFS)", "Frequency (Hz)", title="fpga_adc_spectrum")
        self.c_spec = self.spec.plot(pen=W.pen(T.PLOT1, 1.2))
        self.band = pg.LinearRegionItem(values=(17.9e6, 24.9e6), movable=False,
                                        brush=pg.mkBrush(90, 34, 40, 110), pen=pg.mkPen(T.BAD))
        self.ref_line = pg.InfiniteLine(21.4e6, pen=pg.mkPen("#FFFFFF", style=Qt.DashLine))
        self.spec.addItem(self.band, ignoreBounds=True)
        self.spec.addItem(self.ref_line, ignoreBounds=True)
        p.add(self.spec)
        self.l_spec = W.label("", "mono")
        p.add(self.l_spec)
        self.v.addWidget(p)
        self.seg_adc.changed.connect(lambda i: self.refresh_spectrum())

        # IQ ----------------------------------------------------------------------------------------------------
        self.seg_iq = W.bind(settings, "ui.fpga.iq_loop", W.Seg(["f_ceo", "optical"]), 0)
        p = W.Panel("Baseband IQ (input mixed down by the DDC reference)", self.seg_iq)
        self.ck_iq = W.bind(settings, "ui.fpga.iq_auto5", QCheckBox("Auto-refresh every 5 s"), True)
        p.add_right(W.button("Refresh", slot=self.refresh_iq))
        p.add_right(self.ck_iq)
        self.iq = W.plot(300, "Q (FS)", "I (FS)", title="fpga_iq")
        self.iq.setAspectLocked(True)
        self.c_iq = self.iq.plot(pen=None, symbol="o", symbolSize=2, symbolPen=None,
                                 symbolBrush=pg.mkBrush(T.PLOT1))
        p.add(self.iq)
        self.l_iq = W.label("A round circle = a clean beat near the reference (as in the Vescent GUI).", "mono")
        p.add(self.l_iq)
        self.v.addWidget(p)
        self.seg_iq.changed.connect(lambda i: self.refresh_iq())

        # phase noise ------------------------------------------------------------------------------------------
        self.seg_pn = W.Seg(["f_ceo", "optical"])
        p = W.Panel("In-loop phase noise S_φ (from DDC instantaneous frequency)", self.seg_pn)
        p.add_right(W.button("Measure", slot=self.measure_pn))
        self.pn = W.plot(200, "rad²/Hz", "Hz")
        self.pn.setLogMode(x=True, y=True)
        self.c_pn = self.pn.plot(pen=W.pen(T.PLOT2, 1.2))
        p.add(self.pn)
        self.l_pn = W.label("", "mono")
        p.add(self.l_pn)
        self.v.addWidget(p)

        # counter trend ---------------------------------------------------------------------------------------
        p = W.Panel("f_ceo counter error (Hz)")
        self.ctr_plot = W.plot(150)
        self.c_ctr = self.ctr_plot.plot(pen=W.pen(T.PLOT1))
        self.hist = W.History()
        p.add(self.ctr_plot)
        self.v.addWidget(p)
        self.v.addStretch(1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(5000)
        self.settings_box = {}

    # ---- config files --------------------------------------------------------------------------------
    def _fill_configs(self):
        self.c_cfg.blockSignals(True)
        self.c_cfg.clear()
        d = _config_dir()
        files = sorted(f for f in os.listdir(d) if f.lower().endswith(".xml") and "devices_data" not in f)
        for f in files:
            self.c_cfg.addItem(f, os.path.join(d, f))
        custom = self.settings.get("ui.fpga.custom_config")
        if custom and os.path.exists(custom):
            self.c_cfg.addItem(os.path.basename(custom) + "  (yours)", custom)
        want = self.settings.get("ui.fpga.config") or os.path.join(d, "UCF_FFC-100_Parameters.xml")
        W.set_combo_data(self.c_cfg, want)
        self.c_cfg.blockSignals(False)

    def _cfg_chosen(self, i):
        path = self.c_cfg.itemData(i)
        self.settings.set("ui.fpga.config", path)

    def browse_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Vescent XML parameter file", _config_dir(), "XML (*.xml)")
        if path:
            self.settings.set("ui.fpga.custom_config", path)
            self.settings.set("ui.fpga.config", path)
            self._fill_configs()

    # ---------------------------------------------------------------------------------------------------
    def on_devices_changed(self):
        if self.connected:
            f = self.hub.found.get(self.ROLE)
            self.sub.setText(f"{f.address}:5000 · MAC {f.serial}" if f else "connected")
            self.attach()
            if self.ck_log.isChecked():
                self.toggle_monitor(True)
        else:
            self.sub.setText("not connected")

    def attach(self):
        self.call(lambda d: d.attach(), self._got_settings, log="attached (read only)")

    def reread(self):
        self.call(lambda d: d.settings(), self._got_settings)

    def _got_settings(self, s):
        self.settings_box = s
        for key, _, _ in CEO_FIELDS:
            v = s.get(key)
            if isinstance(v, (int, float)):
                self.ceo_edits[key].setValue(float(v))
        self.seg_sign.set_index(0 if str(s.get("ceo.vco_sign", "+")) == "+" else 1)
        W.set_combo_data(self.c_ddc, s.get("ceo.ddc_filter", 1))
        self.ck_kp.setChecked(bool(s.get("ceo.chkKp", True)))
        self.ck_kd.setChecked(bool(s.get("ceo.chkKd", True)))
        lim = s.get("limits.dac0_v")
        if lim:
            self.e_dac0.setRange(float(lim[0]), float(lim[1]))
        if isinstance(s.get("ceo.dac0_offset_v"), (int, float)):
            self.e_dac0.setValue(s["ceo.dac0_offset_v"])
        if s.get("clock.source") in ("external", "internal"):
            self._clk_src = s.get("clock.source")
        self.seg_clk.set_index(0 if s.get("clock.source") == "external" else 1)
        fs = s.get("clock.fs_hz")
        if isinstance(fs, float):
            self.r_fs.set(fs, "si:Hz:1:10")
        fext = s.get("clock.f_ext_hz")
        if s.get("clock.source") == "external" and isinstance(fext, float):
            from ..fpga import pll_multipliers
            m, d0, _ = pll_multipliers(fext)
            self.r_mmcm.set(f"×{m} ÷{d0}")
        else:
            self.r_mmcm.set("×5 ÷8")
        if isinstance(s.get("optical.ref_freq_hz"), (int, float)):
            self.e_opt_ref.setValue(s["optical.ref_freq_hz"])
        self.seg_osign.set_index(0 if str(s.get("optical.vco_sign", "+")) == "+" else 1)
        ref = s.get("ceo.ref_freq_hz")
        self.hint_ref.setVisible(isinstance(ref, (int, float)) and abs(abs(ref) - 21.6e6) > 1e3)
        self.settings.save_device_state(self.ROLE, {k: v for k, v in s.items()
                                                    if isinstance(v, (int, float, str, bool))})
        self.compare()

    def compare(self):
        prof = self.settings.get("profiles.fpga", {})
        if not prof:
            self.pill_diff.set("no profile saved", "idle")
            self.t_diff.setRowCount(0)
            return

        def done(rows):
            self.diff_rows = rows
            self.t_diff.setRowCount(0)
            for r, row in enumerate(rows):
                cb = QCheckBox()
                cb.setChecked(not row["lock_affecting"])
                W.set_row(self.t_diff, r, ["", row["key"], row["box"], row["profile"],
                                          "drops lock — unlocks first" if row["lock_affecting"] else "safe while locked"],
                          {2: T.WARN, 4: T.WARN if row["lock_affecting"] else T.MUTED})
                self.t_diff.setCellWidget(r, 0, cb)
            n = len(rows)
            self.pill_diff.set(f"{n} differ" if n else "matches profile", "warn" if n else "ok")
        self.call(lambda d: d.compare(prof), done)

    def write_checked(self):
        rows = [row for r, row in enumerate(self.diff_rows)
                if self.t_diff.cellWidget(r, 0) and self.t_diff.cellWidget(r, 0).isChecked()]
        if not rows:
            return
        allow = any(r["lock_affecting"] for r in rows)
        if allow and not W.confirm(self, "Write FPGA settings",
                                   "Some checked settings would drop the lock. Unlock, write, and relock?",
                                   "Unlock, write, relock", danger=True):
            return
        self.call(lambda d: d.apply_differences(rows, allow_unlock=allow),
                  lambda res: (self.hub.emit_log("FPGA", f"written: {res}"), self.reread()))

    def save_profile(self):
        def done(s):
            keep = {k: v for k, v in s.items() if not k.endswith(".locked") and not k.startswith("limits.")
                    and k not in ("optical.mode", "clock.fs_hz") and isinstance(v, (int, float, str, bool))}
            self.settings.set("profiles.fpga", keep)
            self.hub.emit_log("FPGA", f"box saved as profile ({len(keep)} settings)")
            self.compare()
        self.call(lambda d: d.settings(), done)

    def push_config(self):
        path = self.c_cfg.currentData()
        name = os.path.basename(path or "")
        if W.confirm(self, "Push config", f"Push {name}?\n\nThis rewrites every register and ramps the on-board "
                     "100 V boost converter, then selects the external 20 MHz clock. Both loops end up "
                     "unlocked (as the XML's chkLock says).", "Push config", True):
            def work(d):
                if path:
                    d.load_config(path)
                return d.push_config(("external", 20e6), confirm=True)
            self.call(work, self._got_settings, log=f"push config {name}")

    def program_fpga(self):
        if W.confirm(self, "Program FPGA", "Reload the FPGA bitstream? Both locks drop and the config must be "
                     "pushed again afterwards.", "Program FPGA", True):
            self.call(lambda d: d.program_fpga(confirm=True), log="program FPGA")

    def toggle_lock(self, loop):
        locked = self.hub.last(self.ROLE).get(f"{loop}_locked")
        if locked:
            self.call(lambda d: d.unlock(loop), log=f"{loop} unlock")
        else:
            self.call(lambda d: d.lock_and_verify(loop), lambda r: self.hub.emit_log(
                "FPGA", f"{loop} lock: {'OK' if r[0] else 'FAILED'} · phase "
                        f"{'—' if r[1] is None else f'{r[1]:.2f} rad'}"))

    def apply_ceo(self):
        vals = {k: e.value() for k, e in self.ceo_edits.items()}
        vals["ceo.vco_sign"] = "+" if self.seg_sign.index() == 0 else "-"
        vals["ceo.ddc_filter"] = self.c_ddc.currentData()
        vals["ceo.chkKp"] = self.ck_kp.isChecked()
        vals["ceo.chkKd"] = self.ck_kd.isChecked()
        box = self.settings_box

        def differs(k, v):
            b = box.get(k)
            if isinstance(b, (int, float)) and isinstance(v, (int, float)) and not isinstance(v, bool):
                return abs(b - v) > 1e-6 * max(abs(b), abs(v), 1e-30)
            return b != v
        changed = {k: v for k, v in vals.items() if differs(k, v)}
        if not changed:
            return
        risky = [k for k in changed if k in LOCK_AFFECTING]
        allow = False
        if risky:
            if not W.confirm(self, "Lock-affecting change", f"{', '.join(risky)} would disturb the lock. "
                             "Unlock, write and relock?", "Write", True):
                return
            allow = True
        rows = [{"key": k, "box": box.get(k), "profile": v, "lock_affecting": k in LOCK_AFFECTING}
                for k, v in changed.items()]
        self.call(lambda d: d.apply_differences(rows, allow_unlock=allow),
                  lambda res: (self.hub.emit_log("FPGA", f"written: {res}"), self.reread()))

    def apply_dac0(self):
        v = self.e_dac0.value()
        self.call(lambda d: d.set_value("ceo.dac0_offset_v", v), lambda r: self.reread(),
                  log=f"DAC0 offset {v:+.4f} V")

    def apply_opt(self):
        vals = {"optical.ref_freq_hz": self.e_opt_ref.value(),
                "optical.vco_sign": "+" if self.seg_osign.index() == 0 else "-"}
        rows = [{"key": k, "box": self.settings_box.get(k), "profile": v, "lock_affecting": True}
                for k, v in vals.items() if self.settings_box.get(k) != v]
        if rows:
            self.call(lambda d: d.apply_differences(rows, allow_unlock=True), lambda r: self.reread())

    def set_clock(self, i):
        src = "external" if i == 0 else "internal"
        if src == getattr(self, "_clk_src", None):
            return                                  # already on this clock: touch nothing, keep the locks

        if not W.confirm(self, "Clock source", f"Switch to the {src} clock? Both loops unlock first.", "Switch", True):
            self.seg_clk.set_index(1 - i)
            return

        def work(d):
            cur = d.settings().get("clock.source")
            if cur == src:                          # box already there (GUI was stale): change nothing
                return d.settings()
            for loop in ("ceo", "optical"):
                if d.is_locked(loop):
                    d.unlock(loop)
            d.set_value("clock.source", src, allow_unlock=True)
            return d.settings()
        self.call(work, self._got_settings, log=f"clock → {src}")

    def toggle_monitor(self, on):
        if not self.connected:
            return
        if on:
            folder = os.path.join(self.settings.get("ui.data_dir") or str(default_data_dir()), "fpga_monitor")
            self.call(lambda d: d.start_monitor(folder),
                      lambda path: self.l_mon.setText(f"logging → {path or folder}"), log="monitor on")
        else:
            self.call(lambda d: d.stop_monitor(), lambda r: self.l_mon.setText(""), log="monitor off")

    def measure_pn(self):
        loop = "ceo" if self.seg_pn.index() == 0 else "optical"

        def work(d):
            f, _, sphi = d.frequency_noise(loop)
            return f, sphi, d.integrated_phase(loop)

        def done(r):
            f, sphi, ph = r
            m = (f > 0) & (sphi > 0) & np.isfinite(sphi)
            self.c_pn.setData(f[m], sphi[m])
            self.l_pn.setText(f"{loop}: integrated {('—' if ph is None else f'{ph:.3f} rad')} "
                              f"from {f[m][0]/1e3:.1f} kHz to 5 MHz · {m.sum()} bins")
        self.call(work, done)

    # ---- periodic -------------------------------------------------------------------------------------
    def on_poll(self, role, d):
        if role != self.ROLE:
            return
        ceo, opt = d.get("ceo_locked"), d.get("optical_locked")
        self.pill_ceo.set("f_ceo locked" if ceo else "f_ceo open", "ok" if ceo else "warn")
        self.pill_opt.set("optical locked" if opt else "optical open", "ok" if opt else "idle")
        self.b_ceo.setText("● Locked — click to unlock" if ceo else "Lock f_ceo")
        self.b_ceo.setProperty("kind", "ok" if ceo else "primary")
        self.b_ceo.style().unpolish(self.b_ceo); self.b_ceo.style().polish(self.b_ceo)
        self.b_opt.setText("Unlock optical" if opt else "Lock optical")
        ph = d.get("ceo_phase_rad")
        self.r_phase.set(ph, "{:.2f}", T.OK if isinstance(ph, float) and ph < 1.5 else T.WARN)
        err = d.get("ceo_err_hz")
        if isinstance(err, (int, float)):
            self.r_ctr.set(err, "{:+.3f}")
            self.hist.add(ctr=err)
            t, y = self.hist.series("ctr")
            self.c_ctr.setData(t, y)
        oerr = d.get("opt_err_hz")
        self.r_oerr.set(oerr, "{:+.1f}" if isinstance(oerr, (int, float)) and abs(oerr) < 1e4 else "{:+.3e}")
        self.r_omode.set(d.get("optical_mode"))
        self.r_dac1.set(d.get("dac1_v"), "{:.3f}")
        self.r_dac2.set(d.get("dac2_v"), "{:.3f}")
        if isinstance(d.get("ext_clk_hz"), float) and np.isfinite(d["ext_clk_hz"]):
            self.r_ext.set(d["ext_clk_hz"], "si:Hz:1:10")
        t = d.get("zynq_temp_c")
        self.r_temp.set(t if isinstance(t, float) and t > -100 else None, "{:.1f} °C")
        oc = d.get("dac0_off_center")
        if isinstance(oc, float) and np.isfinite(oc):
            lim = float(self.settings.get("ui.lock.dac0_max_pct", 15.0))
            self.r_dac0pos.set(100 * oc, "{:.1f}", T.OK if 100 * oc <= lim else T.WARN)
            self.pill_dac0.set(f"DAC0 {'centered' if 100 * oc <= lim else 'near rail'}",
                               "ok" if 100 * oc <= lim else "warn")

    def _tick(self):
        if not (self.connected and self.isVisible()):
            return
        if self.ck_spec.isChecked():
            self.refresh_spectrum()
        if self.ck_iq.isChecked():
            self.refresh_iq()

    def refresh_iq(self):
        if not self.connected:
            return
        loop = "ceo" if self.seg_iq.index() <= 0 else "optical"

        def done(r):
            i, q, fc = r
            self.c_iq.setData(i, q)
            from vescentcomb.core.units import eng
            rad = np.hypot(i, q)
            self.l_iq.setText(f"{loop} · reference {eng(fc, 'Hz', 6)} · |IQ| mean {np.mean(rad):.3f} FS, "
                              f"spread {np.std(rad) / max(np.mean(rad), 1e-12) * 100:.1f} % · {len(i)} points")
        self.call(lambda d: d.iq(loop), done)

    def refresh_spectrum(self):
        if not self.connected:
            return
        adc = max(0, self.seg_adc.index())
        loop = "ceo" if adc == 0 else "optical"
        avg = self.c_avg.currentData() or 1

        def work(d):
            f, p = d.spectrum(adc, 16384, avg)
            return f, p, d.filter_band(loop), d.fs

        def done(r):
            f, p, (lo, fc, hi), fs = r
            from vescentcomb.core.units import eng
            self.c_spec.setData(f, p)
            self.band.setRegion((lo, hi))
            self.ref_line.setValue(fc)
            i = int(np.argmax(p[5:])) + 5
            self.l_spec.setText(f"dBFS · fs {eng(fs, 'Hz', 7)} · pass band {eng(lo, 'Hz', 4)} – {eng(hi, 'Hz', 4)} · "
                                f"peak {p[i]:.1f} dBFS at {eng(f[i], 'Hz', 6)}")
        self.call(work, done)
