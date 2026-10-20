"""Base for separate instrument windows (scopes, analyzers, generators, meter, SuperK)."""
from __future__ import annotations

import os
import time

from PySide6.QtCore import QByteArray, QTimer
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from ...settings import default_data_dir
from .. import theme as T
from .. import widgets as W


class InstrumentWindow(QMainWindow):
    ROLE = ""
    TITLE = ""

    def __init__(self, hub, settings, main=None):
        super().__init__(None)
        self.hub, self.settings, self.main = hub, settings, main
        self.setWindowTitle(self.TITLE)
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        self.v = QVBoxLayout(root)
        self.v.setContentsMargins(0, 0, 0, 0)
        self.v.setSpacing(0)
        hub.polled.connect(self._polled)
        hub.devices_changed.connect(self.on_devices_changed)
        geo = settings.get(f"ui.windows.{self.ROLE}.geometry")
        if geo:
            try:
                self.restoreGeometry(QByteArray.fromHex(geo.encode()))
            except Exception:
                pass
        else:
            self.resize(1280, 860)
        # after the subclass has built its widgets: read the instrument once if it is connected
        QTimer.singleShot(0, self._initial_read)

    def _initial_read(self):
        if self.hub.has(self.ROLE):
            try:
                self.on_devices_changed()
            except Exception as e:  # never let a read error stop the window opening
                self.hub.emit_log(self.ROLE.upper(), f"initial read failed: {e}")

    # ---- shared chrome -------------------------------------------------------------------------
    def make_toolbar(self, items=()):
        """Top bar: buttons (text, kind, slot) or widgets, then a connection pill + address."""
        bar = QWidget()
        bar.setObjectName("chrome")
        bar.setStyleSheet(f"QWidget#chrome{{background:{T.CHROME}; border-bottom:1px solid {T.LINE};}}")
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 8, 12, 8)
        for it in items:
            if it is None:
                h.addSpacing(10)
            elif isinstance(it, tuple):
                h.addWidget(W.button(*it))
            else:
                h.addWidget(it)
        h.addStretch(1)
        self.conn_pill = W.Pill("not connected")
        self.conn_addr = W.label("", "mono")
        h.addWidget(self.conn_pill)
        h.addWidget(self.conn_addr)
        self.v.addWidget(bar)
        self.hub.devices_changed.connect(self._update_conn)
        self._update_conn()
        return h

    def make_body(self, margins=(16, 14, 16, 16)):
        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(*margins)
        bv.setSpacing(14)
        self.v.addWidget(W.scroll(body))
        return bv

    def add_tabs(self, main, setup_intro: str = "", extra=()):
        """Main controls in a "Control" tab and every driver option in a "Setup" tab."""
        from PySide6.QtWidgets import QTabWidget
        from ..options_panel import OptionsPanel
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        w = main if isinstance(main, QWidget) else QWidget()
        if not isinstance(main, QWidget):
            w.setLayout(main)
        tabs.addTab(w, "Control")
        for title, widget in extra:
            tabs.addTab(widget, title)
        self.options_panel = OptionsPanel(self.hub, self.ROLE, intro=setup_intro or
                                          "Every setting the instrument exposes over the bus. Changes are written "
                                          "immediately and read back.")
        holder = QWidget()
        hv = QVBoxLayout(holder)
        hv.setContentsMargins(16, 14, 16, 16)
        hv.addWidget(self.options_panel)
        tabs.addTab(W.scroll(holder), "Setup (all options)")
        self.tabs = tabs
        self.v.addWidget(tabs, 1)
        k = f"ui.windows.{self.ROLE}.tab"
        tabs.setCurrentIndex(int(self.settings.get(k, 0) or 0))
        tabs.currentChanged.connect(lambda i: self.settings.set(k, i))
        return tabs

    def _update_conn(self):
        if not hasattr(self, "conn_pill"):
            return
        f = self.hub.found.get(self.ROLE) if hasattr(self.hub, "found") else None
        if self.hub.has(self.ROLE):
            self.conn_pill.set("connected", "ok")
            self.conn_addr.setText(f"{f.model} · {f.address}" + (f" · SN {f.serial}" if f and f.serial else "")
                                   if f else "")
        else:
            self.conn_pill.set("not connected", "idle")
            self.conn_addr.setText("Devices… → assign this role")

    @property
    def connected(self) -> bool:
        return self.hub.has(self.ROLE)

    def data_path(self, stem: str, ext: str = "csv") -> str:
        d = os.path.join(self.settings.get("ui.data_dir") or str(default_data_dir()), self.ROLE)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}.{ext}")

    def save_columns(self, stem: str, header, columns, ask: bool = True, meta=None):
        """CSV with the bench-state header (see vescentcomb.datafile)."""
        from ...datafile import write_csv
        path = self.data_path(stem)
        if ask:
            path, _ = QFileDialog.getSaveFileName(self, "Save CSV", path, "CSV (*.csv)")
            if not path:
                return None
        write_csv(path, header, columns=columns, kind=f"{self.TITLE} · {stem}", meta=meta)
        self.hub.emit_log(self.ROLE.upper(), f"saved {path}")
        return path

    def _polled(self, role, d):
        if role == self.ROLE:
            self.on_poll(d)

    def on_poll(self, d):
        pass

    def on_devices_changed(self):
        pass

    def call(self, fn, on_done=None, log=None):
        return self.hub.call(self.ROLE, fn, on_done, log=log)

    def closeEvent(self, e):
        self.settings.set(f"ui.windows.{self.ROLE}.geometry", bytes(self.saveGeometry().toHex()).decode())
        self.settings.set(f"ui.windows.{self.ROLE}.open", False)
        super().closeEvent(e)

    def showEvent(self, e):
        self.settings.set(f"ui.windows.{self.ROLE}.open", True)
        super().showEvent(e)
