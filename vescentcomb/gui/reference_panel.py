"""Overview panel: which instruments use the 10 MHz (GPS) reference, and whether it is on."""
from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QCheckBox

from ..addonkit import REGISTRY
from . import theme as T
from . import widgets as W

MODE_TEXT = {"switch": "set from here", "auto": "switches by itself", "always": "hard-wired", "status": "read-only"}


def reference_state(hub) -> Dict[str, Any]:
    """{role: {input, mode, in_use}} for every declared reference user (used in data-file headers)."""
    out = {}
    for spec in REGISTRY.references:
        d = hub.last(spec.role) if hub.has(spec.role) else {}
        try:
            use = spec.status(d) if (spec.status and d) else None
        except Exception:
            use = None
        out[spec.role] = {"input": spec.input, "mode": spec.mode, "connected": hub.has(spec.role), "in_use": use}
    return out


class ReferencePanel(W.Panel):
    def __init__(self, hub, settings, main=None):
        self.pill = W.Pill("—")
        super().__init__("10 MHz reference · GPS", self.pill)
        self.hub, self.settings, self.main = hub, settings, main
        self.t = W.table(["Instrument", "Reference input", "How", "Using GPS 10 MHz", "Detail", "Enable"], 0)
        self.add(self.t)
        self.add(W.label("Instruments that need telling are switched with the Enable box (written to the "
                         "instrument and read back). Instruments marked “switches by itself” follow the signal "
                         "at their input.", "hint"))
        self.rows: Dict[str, int] = {}
        self.boxes: Dict[str, QCheckBox] = {}
        hub.devices_changed.connect(self.rebuild)
        hub.polled.connect(self.on_poll)
        self.rebuild()

    def rebuild(self):
        specs = {s.role: s for s in REGISTRY.references}
        roles = [r for r, _ in sorted(REGISTRY.roles.items(), key=lambda x: x[1].order)
                 if r in specs or self.hub.has(r)]
        self.t.setRowCount(len(roles))
        self.rows.clear()
        self.boxes.clear()
        for i, role in enumerate(roles):
            self.rows[role] = i
            s = specs.get(role)
            con = self.hub.has(role)
            if s is None:
                W.set_row(self.t, i, [REGISTRY.role_label(role), "none", "—", "n/a", "no 10 MHz input", ""],
                          {3: T.DIM})
                self.t.setCellWidget(i, 5, None)
                continue
            W.set_row(self.t, i, [REGISTRY.role_label(role), s.input, MODE_TEXT.get(s.mode, s.mode),
                                  "…" if con else "not connected", s.note, ""], {3: T.MUTED})
            if s.mode == "switch" and s.option:
                cb = QCheckBox()
                cb.setEnabled(con)
                cb.clicked.connect(lambda on, role=role, opt=s.option: self.set_ref(role, opt, on))
                self.boxes[role] = cb
                self.t.setCellWidget(i, 5, cb)
            else:
                self.t.setCellWidget(i, 5, None)
        self.t.resizeRowsToContents()
        self.t.setMinimumHeight(sum(self.t.rowHeight(i) for i in range(len(roles))) + 40)
        self._summary()

    def set_ref(self, role, opt, on):
        self.hub.call(role, lambda d: d.write_option(opt, bool(on)),
                      lambda v: self.hub.emit_log("REF", f"{REGISTRY.role_label(role)}: external 10 MHz "
                                                         f"{'ON' if v else 'OFF'} (read back)"))

    def on_poll(self, role, d):
        if role not in self.rows:
            return
        s = next((x for x in REGISTRY.references if x.role == role), None)
        if s is None:
            return
        try:
            use = s.status(d) if s.status else None
        except Exception:
            use = None
        try:
            det = s.detail(d) if s.detail else s.note
        except Exception:
            det = s.note
        r = self.rows[role]
        txt, col = ({True: ("yes", T.OK), False: ("no", T.WARN), None: ("unknown", T.MUTED)})[use]
        W.set_row(self.t, r, [REGISTRY.role_label(role), s.input, MODE_TEXT.get(s.mode, s.mode), txt, det, ""],
                  {3: col})
        cb = self.boxes.get(role)
        if cb is not None and use is not None:
            cb.blockSignals(True)
            cb.setChecked(bool(use))
            cb.setEnabled(True)
            cb.blockSignals(False)
        self._summary()

    def _summary(self):
        st = reference_state(self.hub)
        users = [v for v in st.values() if v["connected"]]
        on = sum(1 for v in users if v["in_use"])
        if not users:
            self.pill.set("no reference users connected", "idle")
        else:
            off = [r for r, v in st.items() if v["connected"] and v["in_use"] is False]
            self.pill.set(f"{on}/{len(users)} on GPS", "ok" if not off else "warn")
