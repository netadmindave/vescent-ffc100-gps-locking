"""Setup tab built from a driver's ``OPTIONS`` table (see vescentcomb.core.options).

Every option is shown in its group: dropdowns for discrete values, checkboxes for on/off,
SI-aware number fields, buttons for actions and plain read-outs for read-only values.
A change is written immediately and read back; "Read all" refreshes everything.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from ..core.options import Opt
from ..core.units import eng
from . import theme as T
from . import widgets as W
from .plots import SI_UNITS


class OptionsPanel(QWidget):
    def __init__(self, hub, role: str, columns: int = 2, intro: str = "", groups: Optional[List[str]] = None,
                 exclude_groups: Optional[List[str]] = None):
        super().__init__()
        self.hub, self.role, self.columns = hub, role, columns
        self.only, self.exclude = groups, set(exclude_groups or [])
        self.opts: Dict[str, Opt] = {}
        self.editors: Dict[str, QWidget] = {}
        self.status: Dict[str, QLabel] = {}
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(0, 0, 0, 0)
        self.v.setSpacing(12)
        self.pill = W.Pill("not read")
        top = W.hbox(W.button("Read all from instrument", "primary", self.read_all), self.pill, None)
        self.v.addLayout(top)
        if intro:
            self.v.addWidget(W.label(intro, "hint"))
        self.body = QWidget()
        self.grid = QGridLayout(self.body)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self.v.addWidget(self.body)
        self.v.addStretch(1)
        self._built_for = None
        hub.devices_changed.connect(self.refresh)
        self.refresh()

    # ---- build ---------------------------------------------------------------------------------
    def refresh(self):
        dev = self.hub.device(self.role)
        if dev is None:
            self.pill.set("not connected", "idle")
            return
        if self._built_for is dev:
            return
        self._built_for = dev
        self.hub.call(self.role, lambda d: d.options(), self._build)

    def _clear(self):
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.opts.clear()
        self.editors.clear()
        self.status.clear()

    def _build(self, opts: List[Opt]):
        self._clear()
        groups: Dict[str, List[Opt]] = {}
        for o in opts:
            if (self.only and o.group not in self.only) or o.group in self.exclude:
                continue
            groups.setdefault(o.group, []).append(o)
        for i, (name, items) in enumerate(groups.items()):
            p = W.Panel(name)
            g = QGridLayout()
            g.setHorizontalSpacing(10)
            g.setVerticalSpacing(6)
            g.setColumnStretch(1, 1)
            for r, o in enumerate(items):
                self.opts[o.key] = o
                lab = W.label("" if o.kind == "action" else o.label)
                if o.tip:
                    lab.setToolTip(o.tip)
                ed = self._editor(o)
                if o.tip:
                    ed.setToolTip(o.tip)
                st = QLabel("")
                st.setStyleSheet(f"color:{T.DIM}; font-size:11px;")
                st.setMinimumWidth(14)
                self.editors[o.key], self.status[o.key] = ed, st
                g.addWidget(lab, r, 0)
                g.addWidget(ed, r, 1)
                g.addWidget(st, r, 2)
            p.add(g)
            self.grid.addWidget(p, i // self.columns, i % self.columns, Qt.AlignTop)
        for c in range(self.columns):
            self.grid.setColumnStretch(c, 1)
        self.pill.set(f"{len(self.opts)} options · read when shown", "idle")
        self._pending_read = True
        if self.isVisible():
            self._pending_read = False
            self.read_all()

    def showEvent(self, e):
        """Options are read the first time the tab is actually shown, not when the window opens
        (some instruments flag an error for every setting they don't support)."""
        super().showEvent(e)
        if getattr(self, "_pending_read", False):
            self._pending_read = False
            self.read_all()

    def _editor(self, o: Opt) -> QWidget:
        k = o.key
        if o.kind == "action":
            return W.button(o.label, slot=lambda: self.write(k, None))
        if o.readonly:
            l = W.label("—", "mono")
            l.setTextInteractionFlags(Qt.TextSelectableByMouse)
            return l
        if o.kind == "choice":
            c = W.combo(o.pairs())
            c.activated.connect(lambda i, c=c: self.write(k, c.itemData(i)))
            return c
        if o.kind == "bool":
            b = QCheckBox("on")
            b.clicked.connect(lambda on: self.write(k, bool(on)))
            return b
        if o.kind in ("number", "int"):
            e = W.EngEdit(0.0, o.unit) if o.unit in SI_UNITS else W.NumEdit(0.0, o.unit)
            e.editingFinished.connect(lambda e=e: self._num_done(k, e))
            return e
        e = QLineEdit()
        e.editingFinished.connect(lambda e=e: self.write(k, e.text()))
        return e

    def _num_done(self, key, e):
        v = e.value()
        if getattr(e, "_last_shown", None) is not None and v == e._last_shown:
            return
        self.write(key, int(v) if self.opts[key].kind == "int" else v)

    # ---- I/O -------------------------------------------------------------------------------------
    def write(self, key: str, value: Any):
        o = self.opts[key]
        self.status[key].setText("…")
        shown = "" if o.kind == "action" else f" = {self._fmt(o, value)}"

        def err(e):
            self.status[key].setText("✕")
            self.status[key].setToolTip(str(e))
            self.read_one(key)
        self.hub.call(self.role, lambda d: d.write_option(key, value), lambda v: self._show(key, v, "✓"),
                      on_error=err, log=f"{o.label}{shown}")

    def read_one(self, key: str):
        self.hub.call(self.role, lambda d: d.read_option(key), lambda v: self._show(key, v))

    def read_all(self):
        if not self.opts or not self.hub.has(self.role):
            return
        self.pill.set("reading…", "warn")
        self.hub.call(self.role, lambda d: d.read_options(list(self.opts)), self._show_all)

    def _show_all(self, vals: Dict[str, Any]):
        errs = vals.pop("_errors", {}) if isinstance(vals, dict) else {}
        for k, v in vals.items():
            self._show(k, v)
        n = sum(1 for v in vals.values() if v is None)
        self.pill.set(f"read {len(vals)}" + (f" · {n} no reply" if n else ""), "warn" if n else "ok")
        for k, e in errs.items():
            if k in self.status:
                self.status[k].setText("?")
                self.status[k].setToolTip(e)

    @staticmethod
    def _fmt(o: Opt, v: Any) -> str:
        if v is None:
            return "—"
        if o.kind == "choice":
            for lab, val in o.pairs():
                if val == v:
                    return lab
            return str(v)
        if o.kind == "bool":
            return "on" if v else "off"
        if o.kind in ("number", "int") and isinstance(v, (int, float)):
            return eng(float(v), o.unit, 6) if o.unit in SI_UNITS else f"{v:g} {o.unit}".strip()
        return str(v)

    def _show(self, key: str, v: Any, mark: str = ""):
        ed, o = self.editors.get(key), self.opts.get(key)
        if ed is None or o is None:
            return
        self.status[key].setText(mark if v is not None else "?")
        self.status[key].setToolTip("" if v is not None else "no reply from the instrument")
        if v is None or o.kind == "action":
            return
        ed.blockSignals(True)
        try:
            if isinstance(ed, QLabel):
                ed.setText(self._fmt(o, v))
            elif isinstance(ed, QComboBox):
                i = ed.findData(v)
                if i < 0:
                    W.set_combo_data(ed, v)
                else:
                    ed.setCurrentIndex(i)
            elif isinstance(ed, QCheckBox):
                ed.setChecked(bool(v))
            elif isinstance(ed, W.EngEdit):
                ed.setValue(float(v))
                ed._last_shown = ed.value()
            elif hasattr(ed, "setValue"):
                ed.setValue(float(v))
                ed._last_shown = ed.value()
            elif isinstance(ed, QLineEdit):
                ed.setText(str(v))
        finally:
            ed.blockSignals(False)
