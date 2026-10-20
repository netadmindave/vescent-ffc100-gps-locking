"""Base class for main-window pages."""
from __future__ import annotations

import csv
import os
import time
from typing import Any, Dict, Optional

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from . import widgets as W


class Page(QWidget):
    """A scrollable page bound to one or more roles. Subclasses build ``self.content``."""
    TITLE = ""
    ROLE: Optional[str] = None

    def __init__(self, hub, settings, main=None):
        super().__init__()
        self.hub, self.settings, self.main = hub, settings, main
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        inner.setObjectName("root")
        self.v = QVBoxLayout(inner)
        self.v.setContentsMargins(22, 18, 22, 22)
        self.v.setSpacing(14)
        outer.addWidget(W.scroll(inner))
        hub.polled.connect(self._polled)
        hub.devices_changed.connect(self.on_devices_changed)

    # header helper --------------------------------------------------------------------------
    def header(self, title: str, sub: str = "", pills=(), buttons=()):
        h = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(W.label(title, "h1"))
        for p in pills:
            row.addWidget(p)
        row.addStretch(1)
        left.addLayout(row)
        self.sub = W.label(sub, "mono")
        left.addWidget(self.sub)
        h.addLayout(left, 1)
        for b in buttons:
            h.addWidget(b)
        self.v.addLayout(h)

    # hooks ----------------------------------------------------------------------------------------
    def _polled(self, role: str, data: dict):
        self.on_poll(role, data)

    def on_poll(self, role: str, data: dict):
        pass

    def on_devices_changed(self):
        pass

    def call(self, fn, on_done=None, log=None, role=None):
        return self.hub.call(role or self.ROLE, fn, on_done, log=log)

    @property
    def connected(self) -> bool:
        return self.ROLE is not None and self.hub.has(self.ROLE)

    # snapshot / restore ----------------------------------------------------------------------------
    def save_snapshot_csv(self, role: Optional[str] = None):
        role = role or self.ROLE

        def done(snap):
            path, _ = QFileDialog.getSaveFileName(self, "Save snapshot",
                                                  f"{role}_snapshot_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                                                  "CSV (*.csv)")
            if not path:
                return
            from ..datafile import write_csv
            write_csv(path, ["setting", "value"], rows=list(snap.items()), kind=f"snapshot · {role}")
            self.hub.emit_log(role.upper(), f"snapshot → {path}")
        self.hub.call(role, lambda d: d.snapshot(), done)

    def remember_state(self, role: Optional[str] = None):
        """Read the device snapshot and store it as 'last session' in the settings file."""
        role = role or self.ROLE
        self.hub.call(role, lambda d: d.snapshot(),
                      lambda snap: self.settings.save_device_state(role, _plain(snap)))

    def restore_last_session(self, role: Optional[str] = None):
        role = role or self.ROLE
        saved = self.settings.device_state(role)
        if not saved:
            self.hub.emit_log(role.upper(), "no saved session for this device yet")
            return

        def got_diff(d):
            if not d:
                self.hub.emit_log(role.upper(), "device already matches the last session")
                return
            rows = [(k, live, sv) for k, (live, sv) in d.items()]
            dlg = W.DiffDialog(self, "Restore last session",
                               "These settings differ from the last session. Outputs, emission and "
                               "servo states are never restored.", [(k, a, b, "") for k, a, b in rows])
            if dlg.exec():
                keys = dlg.selected()
                self.hub.call(role, lambda dev: dev.restore(saved, keys),
                              lambda res: self.hub.emit_log(role.upper(), f"restored: {res}"))
        self.hub.call(role, lambda dev: dev.diff(saved), got_diff)


def _plain(d: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in d.items():
        if isinstance(v, (int, float, str, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, tuple)):
            out[k] = list(v)
        elif isinstance(v, dict):
            out[k] = _plain(v)
        else:
            out[k] = str(v)
    return out
