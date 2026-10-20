"""Reusable Overview building blocks for add-ons.

``RoleCard`` shows a role's poll values in a two-column grid with a status pill. Subclass it and
override ``transform(d) -> (d, pill_text, pill_state)`` to derive display values; set ``FIELDS``
to ``[(key, caption, format), …]``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import widgets as W


class OverviewPanel(W.Panel):
    """Base for anything placed on the Overview page by an add-on."""

    def __init__(self, hub, settings, main=None, title: str = "", right=None):
        super().__init__(title, right)
        self.hub, self.settings, self.main = hub, settings, main
        hub.polled.connect(self.on_poll)
        hub.devices_changed.connect(self.on_devices_changed)

    def on_poll(self, role: str, d: Dict[str, Any]) -> None:
        pass

    def on_devices_changed(self) -> None:
        pass


class RoleCard(OverviewPanel):
    ROLE = ""
    TITLE = ""
    FIELDS: List[Tuple[str, str, str]] = []
    OPEN_PAGE: Optional[str] = None          # page key for the "Open" button (defaults to ROLE)

    def __init__(self, hub, settings, main=None):
        self.pill = W.Pill("not connected")
        super().__init__(hub, settings, main, self.TITLE, self.pill)
        self.reads = {}
        items = []
        for key, cap, fmt in self.FIELDS:
            r = W.Readout(cap)
            self.reads[key] = (r, fmt)
            items.append(r)
        self.add(W.grid(items, 2))
        target = self.OPEN_PAGE or self.ROLE
        self.add(W.hbox(W.button("Open", slot=lambda: main and main.show_page(target)), None))
        self.on_devices_changed()

    def transform(self, d: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str]:
        return d, "connected", "ok"

    def on_devices_changed(self):
        if not self.hub.has(self.ROLE):
            self.pill.set("not connected", "idle")
            for r, _ in self.reads.values():
                r.set(None)

    def on_poll(self, role, d):
        if role != self.ROLE:
            return
        d, text, state = self.transform(dict(d))
        self.pill.set(text, state)
        for key, (r, fmt) in self.reads.items():
            r.set(d.get(key), fmt)
