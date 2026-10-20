"""Plot widget used everywhere in the GUI.

* Always auto-ranges to the data.
* The mouse wheel scrolls the page as usual; **Ctrl + wheel** zooms (over an axis: that axis only).
  Ctrl + drag pans. Double-click (or the small "A" button) returns to auto-range.
* Axes in SI base units (Hz, s, V, W, m) get automatic SI prefixes (kHz, µs, mV, nW …).
* Right-click: save PNG, save CSV (with the bench-state header), copy image, auto-range.
"""
from __future__ import annotations

import os
import time
from typing import List, Optional, Tuple

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QFileDialog, QMenu

from . import theme as T

SI_UNITS = {"Hz", "s", "V", "W", "m", "A", "F", "Ω", "Hz/√Hz", "V/div", "s/div", "Sa/s", "pts"}
_LOG_LIKE = {"dBm", "dB", "dBc", "dBc/Hz", "dBV", "dBm/nm", "deg", "°C", "%", "rad", "cycles"}


def _split_label(text: str) -> Tuple[str, str]:
    """'Frequency (Hz)' → ('Frequency', 'Hz'); 'Hz' → ('', 'Hz'); 'dBm' → ('dBm', '')."""
    t = (text or "").strip()
    if t.endswith(")") and "(" in t:
        name, unit = t[:-1].rsplit("(", 1)
        unit = unit.strip()
        if unit in SI_UNITS:
            return name.strip(), unit
        return t, ""
    if t in SI_UNITS:
        return "", t
    return t, ""


class BenchViewBox(pg.ViewBox):
    """Wheel and drag only act with Ctrl held; double-click re-enables auto-range."""

    def wheelEvent(self, ev, axis=None):
        if ev.modifiers() & Qt.ControlModifier:
            super().wheelEvent(ev, axis)
        else:
            ev.ignore()

    def mouseDragEvent(self, ev, axis=None):
        if ev.modifiers() & Qt.ControlModifier:
            super().mouseDragEvent(ev, axis)
        else:
            ev.ignore()

    def mouseDoubleClickEvent(self, ev):
        self.enableAutoRange()
        ev.accept()

    def raiseContextMenu(self, ev):      # our own menu lives on the widget
        ev.ignore()


class BenchPlot(pg.PlotWidget):
    def __init__(self, height: int = 170, ylabel: str = "", xlabel: str = "", title: str = ""):
        super().__init__(viewBox=BenchViewBox())
        self.setMinimumHeight(height)
        self.export_name = title or (ylabel or "plot")
        pi = self.getPlotItem()
        pi.showGrid(x=True, y=True, alpha=0.15)
        vb = pi.getViewBox()
        vb.setDefaultPadding(0.03)
        vb.enableAutoRange()
        pi.setMenuEnabled(False)
        for ax in ("left", "bottom"):
            a = pi.getAxis(ax)
            a.setPen(pg.mkPen(T.LINE))
            a.setTextPen(pg.mkPen(T.MUTED))
        self.set_labels(ylabel, xlabel)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.setToolTip("Ctrl + wheel to zoom, Ctrl + drag to pan, double-click for auto-range. Right-click to save.")

    # ---- axes ------------------------------------------------------------------------------------
    def set_labels(self, ylabel: str = "", xlabel: str = "") -> None:
        for ax, text in (("left", ylabel), ("bottom", xlabel)):
            name, unit = _split_label(text)
            a = self.getPlotItem().getAxis(ax)
            a.enableAutoSIPrefix(bool(unit))
            if unit:
                self.setLabel(ax, name, units=unit)
            elif text:
                self.setLabel(ax, text)

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            super().wheelEvent(ev)
        else:
            ev.ignore()                  # let the scroll area under the plot scroll the page

    # ---- export ----------------------------------------------------------------------------------
    def _curves(self) -> List[Tuple[str, np.ndarray, np.ndarray]]:
        out = []
        for i, it in enumerate(self.getPlotItem().listDataItems()):
            try:
                x, y = it.getData()
            except Exception:
                continue
            if x is None or y is None or len(x) == 0:
                continue
            name = it.name() or f"trace{i + 1}"
            out.append((name, np.asarray(x, float), np.asarray(y, float)))
        return out

    def _axis_text(self, ax: str) -> str:
        a = self.getPlotItem().getAxis(ax)
        name = (a.labelText or "").strip()
        unit = (a.labelUnits or "").strip()
        return f"{name} ({unit})" if unit else name

    def _default_path(self, ext: str) -> str:
        from ..settings import default_data_dir
        d = None
        try:
            from PySide6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                s = getattr(w, "settings", None)
                if s is not None and s.get("ui.data_dir"):
                    d = s.get("ui.data_dir")
                    break
        except Exception:
            pass
        d = os.path.join(d or str(default_data_dir()), "plots")
        os.makedirs(d, exist_ok=True)
        stem = "".join(c if c.isalnum() else "_" for c in self.export_name).strip("_") or "plot"
        return os.path.join(d, f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}.{ext}")

    def save_png(self, path: Optional[str] = None) -> Optional[str]:
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Save plot image", self._default_path("png"), "PNG (*.png)")
        if not path:
            return None
        self.grab().save(path, "PNG")
        return path

    def save_csv(self, path: Optional[str] = None) -> Optional[str]:
        from ..datafile import write_csv
        curves = self._curves()
        if not curves:
            return None
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Save plot data", self._default_path("csv"), "CSV (*.csv)")
        if not path:
            return None
        xname = self._axis_text("bottom") or "x"
        yname = self._axis_text("left") or "y"
        same_x = all(len(c[1]) == len(curves[0][1]) and np.allclose(c[1], curves[0][1], equal_nan=True)
                     for c in curves)
        if same_x:
            header = [xname] + [f"{c[0]} · {yname}" if len(curves) > 1 else yname for c in curves]
            cols = [curves[0][1]] + [c[2] for c in curves]
        else:                                    # different x per curve: x/y column pairs, padded
            n = max(len(c[1]) for c in curves)
            header, cols = [], []
            for name, x, y in curves:
                pad = lambda a: np.concatenate([a, np.full(n - len(a), np.nan)])
                header += [f"{name} · {xname}", f"{name} · {yname}"]
                cols += [pad(x), pad(y)]
        write_csv(path, header, columns=cols, kind=f"plot · {self.export_name}",
                  meta={"plot_x_axis": xname, "plot_y_axis": yname, "plot_curves": [c[0] for c in curves]})
        return path

    def _menu(self, pos):
        m = QMenu(self)
        m.addAction("Save image (PNG)…", self.save_png)
        a = m.addAction("Save data (CSV)…", self.save_csv)
        a.setEnabled(bool(self._curves()))
        m.addAction("Copy image", lambda: QGuiApplication.clipboard().setPixmap(self.grab()))
        m.addSeparator()
        m.addAction("Auto-range", lambda: self.getPlotItem().getViewBox().enableAutoRange())
        m.exec(self.mapToGlobal(pos))
