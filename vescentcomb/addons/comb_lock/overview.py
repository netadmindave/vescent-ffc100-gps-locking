"""Comb-lock cards and trends for the Overview page."""
from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QHBoxLayout, QWidget

from vescentcomb.gui import theme as T
from vescentcomb.gui import widgets as W
from vescentcomb.gui.cards import OverviewPanel, RoleCard


class FFCCard(RoleCard):
    ROLE, TITLE = "ffc", "FFC-100 comb"
    FIELDS = [("state", "State", "{}"), ("slow_servo_on", "Slow servo", "{}"),
              ("cav_temp", "Cavity temp (°C)", "{:.4f}"), ("cav_setpoint", "Setpoint (°C)", "{:.4f}"),
              ("cav_err", "Cavity error", "si:K:1e-3:3"), ("pzt_output", "PZT output", "si:V:1:4")]

    def transform(self, d):
        ml = d.get("mode_locked")
        if isinstance(d.get("cav_temp"), float) and isinstance(d.get("cav_setpoint"), float):
            d["cav_err"] = (d["cav_temp"] - d["cav_setpoint"]) * 1e3
        d["slow_servo_on"] = "ON" if d.get("slow_servo_on") else "off"
        return d, ("Mode-locked" if ml else "Not mode-locked"), ("ok" if ml else "bad")


class FPGACard(RoleCard):
    ROLE, TITLE = "fpga", "SLICE-FPGA-II"
    FIELDS = [("clock_source", "Clock", "{}"), ("ceo_ref", "f_ceo reference", "si:Hz:1e6:7"),
              ("ceo_phase_rad", "Integrated phase (rad)", "{:.2f}"), ("optical_locked", "Optical loop", "{}")]

    def transform(self, d):
        ceo = d.get("ceo_locked")
        ref = d.get("ceo_ref_hz")
        d["ceo_ref"] = abs(ref) / 1e6 if isinstance(ref, (int, float)) else None
        d["optical_locked"] = "locked" if d.get("optical_locked") else "open"
        d["clock_source"] = str(d.get("clock_source") or "—").upper()
        return d, ("f_ceo locked" if ceo else "f_ceo open"), ("ok" if ceo else "warn")


class OPL1Card(RoleCard):
    ROLE, TITLE = "opl1", "SLICE-OPL #1 · f_rep → GPS"
    FIELDS = [("target_beatnote", "Target beat", "si:Hz:1e6:9"), ("err_hz", "Beat error", "si:Hz:1:4"),
              ("error_v", "Error voltage", "si:V:1:4"), ("pll_out_v", "PLL out", "si:V:1:4"),
              ("reference", "Reference", "si:Hz:1e6:9"), ("hold", "Integrator hold", "{}")]

    def transform(self, d):
        servo = d.get("servo_on")
        b, t = d.get("beatnote"), d.get("target_beatnote")
        off = self.settings.get("ui.lock.counter_offset_hz", 31.0)
        if isinstance(b, float) and isinstance(t, float) and b > 1:
            d["err_hz"] = (t - off / 1e6 - b) * 1e6
        d["hold"] = "ON" if d.get("hold") else "off"
        return d, ("Servo on" if servo else "Servo off"), ("ok" if servo else "idle")


class CombTrends(OverviewPanel):
    """f_rep beat error with the lock window, and cavity temperature against setpoint."""

    def __init__(self, hub, settings, main=None):
        super().__init__(hub, settings, main, "Comb lock trends")
        row = QHBoxLayout()
        row.setSpacing(14)
        left = QWidget(); lv = W.vbox(margins=(0, 0, 0, 0)); left.setLayout(lv)
        lv.addWidget(W.label("f_rep beat error vs GPS (Hz) · window shaded", "lbl"))
        self.p_beat = W.plot(190, "Hz", "minutes")
        self.p_beat.setMaximumHeight(230)
        self.win = pg.LinearRegionItem(values=(-8, 8), orientation="horizontal", movable=False,
                                       brush=pg.mkBrush(24, 57, 46, 140), pen=pg.mkPen(T.OK))
        self.p_beat.addItem(self.win, ignoreBounds=True)
        self.c_beat = self.p_beat.plot(pen=W.pen(T.PLOT1))
        lv.addWidget(self.p_beat)
        right = QWidget(); rv = W.vbox(margins=(0, 0, 0, 0)); right.setLayout(rv)
        rv.addWidget(W.label("Cavity temperature (°C) · setpoint dashed", "lbl"))
        self.p_cav = W.plot(190, "°C", "minutes")
        self.p_cav.setMaximumHeight(230)
        self.c_cav = self.p_cav.plot(pen=W.pen(T.PLOT2))
        self.c_set = self.p_cav.plot(pen=W.pen(T.MUTED, 1, True))
        rv.addWidget(self.p_cav)
        row.addWidget(left)
        row.addWidget(right)
        self.add(row)
        self.hist = W.History()

    def on_poll(self, role, d):
        if role == "ffc":
            self.hist.add(cav=d.get("cav_temp"), set=d.get("cav_setpoint"))
            t, y = self.hist.series("cav"); self.c_cav.setData(t, y)
            t, y = self.hist.series("set"); self.c_set.setData(t, y)
        elif role == "opl1":
            b, t = d.get("beatnote"), d.get("target_beatnote")
            off = self.settings.get("ui.lock.counter_offset_hz", 31.0)
            err = (t - off / 1e6 - b) * 1e6 if isinstance(b, float) and isinstance(t, float) and b > 1 else None
            self.hist.add(err=err)
            tt, y = self.hist.series("err"); self.c_beat.setData(tt, y)
            w = self.settings.get("ui.lock.window_hz", 8.0)
            self.win.setRegion((-w, w))
