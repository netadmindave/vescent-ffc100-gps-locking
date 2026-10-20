"""FFC-100 comb page."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QWidget

from vescentcomb.gui import theme as T
from vescentcomb.gui import widgets as W
from vescentcomb.gui.page_base import Page


class FFCPage(Page):
    TITLE = "FFC-100 comb"
    ROLE = "ffc"

    def __init__(self, hub, settings, main=None):
        super().__init__(hub, settings, main)
        self.pill_ml = W.Pill("—")
        self.pill_state = W.Pill("—")
        self.header("FFC-100 fiber frequency comb", "not connected", [self.pill_ml, self.pill_state],
                    [W.button("Restore last session…", slot=self.restore_last_session),
                     W.button("Snapshot → CSV", slot=self.save_snapshot_csv)])
        g = QGridLayout()
        g.setSpacing(14)
        self.v.addLayout(g)

        # laser state ----------------------------------------------------------------------
        p = W.Panel("Laser state · MSTRCTL")
        self.state_boxes = {}
        row = QHBoxLayout()
        for i, name in enumerate(("OFF", "STANDBY", "LASER ON")):
            b = QLabel(name)
            b.setAlignment(Qt.AlignCenter)
            self.state_boxes[name] = b
            row.addWidget(b, 1)
            if i < 2:
                row.addWidget(W.label("→"))
        p.add(row)
        self.b_standby = W.button("Standby", slot=self.do_standby)
        self.b_on = W.button("Laser on", slot=self.do_laser_on)
        self.b_shutdown = W.button("Shut down (standby → off)", "danger", self.do_shutdown)
        p.add(W.hbox(self.b_standby, self.b_on, self.b_shutdown, None))
        p.add(W.label("OFF is never sent while lasing. Shut down goes to STANDBY, waits, then OFF. "
                      "Laser on is only offered from STANDBY.", "hint"))
        g.addWidget(p, 0, 0)

        # cavity setpoint ---------------------------------------------------------------------
        p = W.Panel("Cavity setpoint · f_rep tuning")
        self.r_set = W.Readout("Setpoint", big=True, unit="°C")
        self.r_cav = W.Readout("Actual (CAVTEMP?)", big=True, unit="°C")
        p.add(W.hbox(self.r_set, self.r_cav, None))
        steps = QHBoxLayout()
        for d in (-0.1, -0.01, -0.001, 0.001, 0.01, 0.1):
            steps.addWidget(W.button(f"{d:+g}", slot=lambda d=d: self.nudge(d)))
        p.add(steps)
        self.e_set = W.dspin(31.0, 15, 45, 4, 0.001, "°C")
        p.add(W.hbox(W.field("New setpoint", self.e_set), W.button("Apply", "primary", self.apply_setpoint)))
        self.warn_slow = W.label("Slow servo is ON — manual setpoint changes will fight the OPL lock. "
                                 "Turn the slow servo off first.", "hint")
        self.warn_slow.hide()
        p.add(self.warn_slow)
        g.addWidget(p, 0, 1)

        # temperatures ---------------------------------------------------------------------------
        p = W.Panel("Temperatures · read only")
        self.t_temps = W.table(["Stage", "Actual (°C)", "Error"], 3)
        self.t_temps.setMaximumHeight(130)
        p.add(self.t_temps)
        g.addWidget(p, 1, 0)

        # currents ---------------------------------------------------------------------------------
        p = W.Panel("Pump currents · OSCCURR? / AMPCURR?")
        self.r_osc = W.Readout("Oscillator", big=True, unit="mA")
        self.r_amp = W.Readout("Amplifier", big=True, unit="mA")
        p.add(W.hbox(self.r_osc, self.r_amp, None))
        self.l_minmax = W.label("session min / max: —", "mono")
        p.add(self.l_minmax)
        self.cur_minmax = {}
        g.addWidget(p, 1, 1)

        # PZT ----------------------------------------------------------------------------------------
        p = W.Panel("PZT · PZTMOMD · CADCBSP · CADCBV?")
        self.seg_gain = W.Seg(["Off", "Full range ×1", "Full range ×10"])
        self.seg_gain.changed.connect(lambda i: self.set_pzt())
        self.l_pztcode = W.label("PZTMOMD ?", "mono")
        self.r_pzt = W.Readout("PZT output", unit="V")
        p.add(W.hbox(W.field("PZT", self.seg_gain), self.l_pztcode, self.r_pzt, None))
        self.e_bias = W.dspin(0.0, -10, 10, 3, 0.01, "V")
        p.add(W.hbox(W.field("DC bias setpoint", self.e_bias), W.button("Apply", slot=self.apply_bias)))
        p.add(W.label("Keep DC bias at 0 V while a SLICE is locking — it adds straight onto the PZT output.", "hint"))
        g.addWidget(p, 2, 0)

        # slow servo ------------------------------------------------------------------------------------
        self.pill_slow = W.Pill("—")
        p = W.Panel("Slow servo", self.pill_slow)
        self.seg_slow = W.Seg(["Off", "On"])
        self.seg_slow.changed.connect(self.set_slow)
        p.add(W.hbox(self.seg_slow, None))
        self.e_sgain = W.dspin(0, -100, 100, 2, 0.5, "dB")
        self.e_soff = W.dspin(0, -10, 10, 3, 0.01, "V")
        p.add(W.grid([W.field("Gain · SLSRVGN", self.e_sgain), W.field("Offset · SLSRVOS", self.e_soff)], 2))
        self.l_read = W.label("not read yet", "mono")
        p.add(W.hbox(W.button("Apply", "primary", self.apply_slow), W.button("Re-read", slot=self.reread),
                     self.l_read, None))
        p.add(W.label("Gain and offset are read from the comb on connect and after every write; "
                      "edits stay staged until Apply.", "lbl", wrap=True))
        g.addWidget(p, 2, 1)
        g.setColumnStretch(0, 1)
        g.setColumnStretch(1, 1)

        # trend -----------------------------------------------------------------------------------------
        p = W.Panel("Trend · cavity, setpoint (°C) and PZT out (V)")
        self.plot = W.plot(170)
        self.c_cav = self.plot.plot(pen=W.pen(T.PLOT2))
        self.c_set = self.plot.plot(pen=W.pen(T.MUTED, 1, True))
        self.hist = W.History()
        p.add(self.plot)
        self.v.addWidget(p)
        self.v.addStretch(1)
        self._paint_state(None)

    # ---- device events -----------------------------------------------------------------------------
    def on_devices_changed(self):
        if self.connected:
            f = self.hub.found.get(self.ROLE)
            self.sub.setText(f"{f.address} · SN {f.serial} · {f.firmware}" if f else "connected")
            self.reread()
        else:
            self.sub.setText("not connected")

    def reread(self):
        def done(s):
            self.e_set.setValue(s.get("cav_setpoint") or 0)
            self.e_bias.setValue(s.get("dc_bias_setpoint") or 0)
            self.e_sgain.setValue(s.get("slow_servo_gain") or 0)
            self.e_soff.setValue(s.get("slow_servo_offset") or 0)
            code = s.get("pzt_mode")
            if code in (0, 1, 2):
                self.seg_gain.set_index(code)
            self.l_pztcode.setText(f"PZTMOMD {code if code is not None else '?'}")
            import time
            self.l_read.setText(f"read from comb {time.strftime('%H:%M:%S')}")
            temps = [("Oscillator", s.get("osc_temp"), s.get("osc_temp_error")),
                     ("Amplifier", s.get("amp_temp"), s.get("amp_temp_error")),
                     ("Cavity", s.get("cav_temp"), s.get("cav_temp_error"))]
            for r, (n, a, e) in enumerate(temps):
                W.set_row(self.t_temps, r, [n, W.fmt_num(a, "{:.4f}"), W.fmt_num(e, "{:+.4f}")])
            self.settings.save_device_state(self.ROLE, {k: v for k, v in s.items() if k != "idn"})
        self.call(lambda d: d.snapshot(), done)

    def on_poll(self, role, d):
        if role != self.ROLE:
            return
        self._paint_state(d.get("state"))
        ml = d.get("mode_locked")
        self.pill_ml.set("Mode-locked" if ml else "Not mode-locked", "ok" if ml else "bad")
        self.r_set.set(d.get("cav_setpoint"), "{:.4f}")
        self.r_cav.set(d.get("cav_temp"), "{:.4f}")
        self.r_pzt.set(d.get("pzt_output"), "{:.2f}")
        slow = d.get("slow_servo_on")
        self.pill_slow.set("On" if slow else "Off", "ok" if slow else "idle")
        self.seg_slow.set_index(1 if slow else 0)
        self.warn_slow.setVisible(False)          # v0.4: no warnings
        self.hist.add(cav=d.get("cav_temp"), set=d.get("cav_setpoint"))
        t, y = self.hist.series("cav")
        self.c_cav.setData(t, y)
        t, y = self.hist.series("set")
        self.c_set.setData(t, y)
        # currents are cheap to fetch alongside
        self.call(lambda dev: (dev.osc_current(), dev.amp_current()), self._currents)

    def _currents(self, ca):
        osc, amp = ca
        self.r_osc.set(osc, "{:.1f}")
        self.r_amp.set(amp, "{:.1f}")
        for k, v in (("osc", osc), ("amp", amp)):
            if isinstance(v, float):
                lo, hi = self.cur_minmax.get(k, (v, v))
                self.cur_minmax[k] = (min(lo, v), max(hi, v))
        if self.cur_minmax:
            self.l_minmax.setText("session min/max: " + " · ".join(
                f"{k} {lo:.1f}–{hi:.1f}" for k, (lo, hi) in self.cur_minmax.items()))

    def _paint_state(self, state):
        for name, lab in self.state_boxes.items():
            on = (name == state)
            lab.setStyleSheet(f"padding:9px; border-radius:6px; font-weight:600; letter-spacing:1px;"
                              f"background:{T.OK_BG if on else '#1A1F26'}; color:{T.OK if on else T.DIM};")
        self.pill_state.set(state or "—", "ok" if state == "LASER ON" else "idle")
        self.b_on.setEnabled(state == "STANDBY")
        self.b_standby.setEnabled(state in ("OFF", "LASER ON"))

    # ---- actions ------------------------------------------------------------------------------------
    def do_standby(self):
        self.call(lambda d: d.standby(), log="MSTRCTL 1 (standby)")

    def do_laser_on(self):
        if W.confirm(self, "Laser on", "Switch the comb from STANDBY to LASER ON?", "Laser on"):
            self.call(lambda d: d.laser_on(), log="MSTRCTL 2 (laser on)")

    def do_shutdown(self):
        if W.confirm(self, "Shut down comb", "Go to STANDBY, wait, then OFF?", "Shut down", danger=True):
            self.call(lambda d: d.shutdown(), log="shutdown: standby → off")

    def nudge(self, d):
        if self.hub.last(self.ROLE).get("slow_servo_on") and not W.confirm(
                self, "Slow servo is on", "Changing the setpoint will fight the lock. Continue?"):
            return
        self.call(lambda dev: dev.set_cav_setpoint(dev.cav_setpoint() + d),
                  lambda r: self.remember_state(), log=f"CATSETP {d:+g} °C")

    def apply_setpoint(self):
        v = self.e_set.value()
        self.call(lambda dev: dev.set_cav_setpoint(v), lambda r: self.remember_state(),
                  log=f"CATSETP {v:.4f}")

    def set_pzt(self):
        code = max(0, self.seg_gain.index())
        self.call(lambda d: d.set_pzt_mode(code), lambda r: (self.remember_state(), self.reread()),
                  log=f"PZTMOMD {code} ({['off', '×1', '×10'][code]})")

    def apply_bias(self):
        v = self.e_bias.value()
        if abs(v) > 1e-9 and not W.confirm(self, "DC bias", "Non-zero DC bias adds onto the PZT output "
                                           "while a SLICE is locking. Apply anyway?"):
            return
        self.call(lambda d: d.set_dc_bias_setpoint(v), lambda r: self.remember_state(), log=f"CADCBSP {v}")

    def set_slow(self, i):
        self.call(lambda d: d.set_slow_servo(i == 1), log=f"SLSRVEN {i}")

    def apply_slow(self):
        g, o = self.e_sgain.value(), self.e_soff.value()
        self.call(lambda d: (d.set_slow_servo_gain(g), d.set_slow_servo_offset(o)),
                  lambda r: self.reread(), log=f"SLSRVGN {g} · SLSRVOS {o}")
