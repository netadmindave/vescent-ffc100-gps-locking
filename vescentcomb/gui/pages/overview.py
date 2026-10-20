"""Overview: panels contributed by the add-ons, the bench-instrument table and the event log."""
from __future__ import annotations

from PySide6.QtWidgets import QGridLayout

from ...addonkit import REGISTRY
from .. import theme as T
from .. import widgets as W
from ..page_base import Page


class OverviewPage(Page):
    TITLE = "Overview"

    def __init__(self, hub, settings, main=None):
        super().__init__(hub, settings, main)
        buttons = []
        if any(p.key == "combseq" for p in REGISTRY.pages):
            buttons.append(W.button("Comb lock sequence", "primary", lambda: main and main.show_page("combseq")))
        if any(p.key == "laserlock" for p in REGISTRY.pages):
            buttons.append(W.button("Laser lock", slot=lambda: main and main.show_page("laserlock")))
        mods = [a.name for a in REGISTRY.addons.values() if a.type == "module"]
        n_tools = sum(1 for a in REGISTRY.addons.values() if a.type != "module")
        self.header("Overview", "FFC-100 · GPS OPL #1 · SLICE-FPGA-II at a glance", buttons=buttons)
        self.sub.setWordWrap(True)
        if not REGISTRY.addons:
            self.v.addWidget(W.label("No add-ons are enabled. Settings → Add-ons… lists the modules and tools found "
                                     "in your add-on folders; tick the ones this bench uses.", "hint"))

        self.panels = []
        cards = sorted((s for s in REGISTRY.overview if s.label == "card"), key=lambda s: s.order)
        if cards:
            g = QGridLayout()
            g.setSpacing(14)
            self.v.addLayout(g)
            for i, spec in enumerate(cards):
                w = self._make(spec)
                if w is not None:
                    g.addWidget(w, i // 3, i % 3)
            for c in range(3):
                g.setColumnStretch(c, 1)
        for spec in sorted((s for s in REGISTRY.overview if s.label != "card"), key=lambda s: s.order):
            w = self._make(spec)
            if w is not None:
                self.v.addWidget(w)

        if REGISTRY.references:
            from ..reference_panel import ReferencePanel
            self.ref_panel = ReferencePanel(hub, settings, main)
            self.v.addWidget(self.ref_panel)

        self.bench = [r for r, s in sorted(REGISTRY.roles.items(), key=lambda x: x[1].order) if s.bench_row]
        self.row_of = {r: i for i, r in enumerate(self.bench)}
        if self.bench:
            p = W.Panel("Bench instruments")
            self.t_inst = W.table(["Instrument", "Unit", "Status", "Now", ""], len(self.bench))
            self.t_inst.setMinimumHeight(30 * len(self.bench) + 30)
            win_for = {w.role: w.key for w in REGISTRY.windows}
            for r, role in enumerate(self.bench):
                W.set_row(self.t_inst, r, [REGISTRY.role_label(role), "—", "not connected", "", ""], {2: T.MUTED})
                if role in win_for:
                    self.t_inst.setCellWidget(r, 4, W.button("Open ↗", slot=lambda k=win_for[role]: main and main.open_window(k)))
            p.add(self.t_inst)
            self.v.addWidget(p)

        p = W.Panel("Event log")
        self.log = W.LogView()
        self.log.setMinimumHeight(200)
        p.add(self.log)
        self.v.addWidget(p)
        hub.log.connect(self.log.add)
        self.v.addStretch(1)
        self.on_devices_changed()

    def _make(self, spec):
        try:
            w = spec.get()(self.hub, self.settings, self.main)
            self.panels.append(w)
            return w
        except Exception as e:
            self.hub.emit_log("ADDON", f"{spec.addon}: overview panel {spec.key} failed: {e}")
            return None

    def on_devices_changed(self):
        for role in self.bench:
            r = self.row_of[role]
            f = self.hub.found.get(role)
            label = REGISTRY.role_label(role)
            if self.hub.has(role):
                addr = f.address if f and len(f.address) <= 22 else ("…" + f.address[-20:] if f else "")
                W.set_row(self.t_inst, r, [label, f"{f.model} · {addr}" if f else "", "connected", "", ""], {2: T.OK})
            else:
                W.set_row(self.t_inst, r, [label, "—", "not connected", "", ""], {2: T.MUTED})

    def on_poll(self, role, d):
        if role in self.row_of:
            fn = REGISTRY.summaries.get(role)
            it = self.t_inst.item(self.row_of[role], 3)
            if fn and it is not None:
                try:
                    it.setText(fn(d))
                except Exception:
                    pass
