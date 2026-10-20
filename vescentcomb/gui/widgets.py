"""Small reusable widgets + helpers that persist field values to the settings file."""
from __future__ import annotations

import collections
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QSlider, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QScrollArea,
)

from . import theme as T

pg.setConfigOptions(antialias=True, background=T.INPUT, foreground=T.MUTED)


# ---- labels ------------------------------------------------------------------------------------
def label(text: str = "", kind: str = "lbl", wrap: bool = False) -> QLabel:
    w = QLabel(text)
    w.setObjectName(kind)
    w.setWordWrap(wrap)
    if kind in ("hint", "info"):
        w.setWordWrap(True)
    return w


def button(text: str, kind: str = "", slot: Optional[Callable] = None, tip: str = "") -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setProperty("kind", kind)
    if slot:
        b.clicked.connect(lambda *_: slot())
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    return b


class Pill(QLabel):
    def __init__(self, text: str = "", state: str = "idle"):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.set(text, state)

    def set(self, text: str, state: str = "idle"):
        bg, fg = T.PILL.get(state, T.PILL["idle"])
        self.setText(f"●  {text.upper()}" if state != "idle" else text.upper())
        self.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:10px; padding:3px 10px;"
                           f"font-size:11px; font-weight:600; letter-spacing:1px;")


class Panel(QFrame):
    """Rounded card with a title row; add widgets to ``.body``."""

    def __init__(self, title: str = "", right: Optional[QWidget] = None):
        super().__init__()
        self.setObjectName("panel")
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 14)
        v.setSpacing(10)
        if title or right:
            h = QHBoxLayout()
            t = QLabel(title.upper())
            t.setObjectName("panelTitle")
            self.title_label = t
            h.addWidget(t)
            h.addStretch(1)
            self.head = h
            if right is not None:
                h.addWidget(right)
            v.addLayout(h)
        self.body = v
        v.addStretch(1)          # content stays at the top; add() inserts above this

    def add(self, w):
        i = self.body.count() - 1
        if isinstance(w, QWidget):
            self.body.insertWidget(i, w)
        else:
            self.body.insertLayout(i, w)
        return w

    def set_title(self, text: str):
        self.title_label.setText(text)

    def add_right(self, w: QWidget):
        self.head.addWidget(w)
        return w


class Readout(QWidget):
    """Caption over a monospaced value."""

    def __init__(self, caption: str, value: str = "—", big: bool = False, unit: str = ""):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.cap = label(caption)
        self.val = QLabel(value)
        self.val.setObjectName("big" if big else "ro")
        self.unit = unit
        v.addWidget(self.cap)
        v.addWidget(self.val)

    def set_si(self, value: Any, unit: Optional[str] = None, digits: int = 6, color: Optional[str] = None):
        """Value in SI notation with a prefix (12.5 MHz, 340 µW, 2.1 ns)."""
        from ..core.units import eng
        u = self.unit if unit is None else unit
        s = "—" if not isinstance(value, (int, float)) else eng(float(value), u, digits)
        self.val.setText(s)
        self.val.setStyleSheet(f"color:{color};" if color else "")

    def set(self, value: Any, fmt: str = "{}", color: Optional[str] = None):
        """``fmt`` is a format string, or ``"si:<unit>[:<scale>[:<digits>]]"`` for SI notation
        (value × scale shown with a prefix, e.g. "si:Hz:1e6" for a value given in MHz)."""
        if isinstance(fmt, str) and fmt.startswith("si:") and isinstance(value, (int, float)) \
                and not isinstance(value, bool):
            from ..core.units import eng
            parts = fmt.split(":")
            unit = parts[1] if len(parts) > 1 else ""
            scale = float(parts[2]) if len(parts) > 2 and parts[2] else 1.0
            digits = int(parts[3]) if len(parts) > 3 else 6
            v = float(value) * scale
            s = ("+" if fmt.endswith(":+") and v >= 0 else "") + eng(v, unit, digits)
            self.val.setText(s)
            self.val.setStyleSheet(f"color:{color};" if color else "")
            return
        if isinstance(fmt, str) and fmt.startswith("si:"):
            fmt = "{}"
        if value is None or value == "":
            s = "—"
        else:
            try:
                s = fmt.format(value)
            except (ValueError, TypeError):
                s = str(value)
        self.val.setText(f"{s} {self.unit}".strip() if s != "—" else s)
        self.val.setStyleSheet(f"color:{color};" if color else "")


class Seg(QWidget):
    """Segmented button group. ``changed`` emits the selected index."""
    changed = Signal(int)

    def __init__(self, options: Sequence[str], current: int = 0):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = []
        for i, o in enumerate(options):
            b = QPushButton(o)
            b.setCheckable(True)
            b.setProperty("seg", True)
            b.setCursor(Qt.PointingHandCursor)
            self.group.addButton(b, i)
            h.addWidget(b)
            self.buttons.append(b)
        if self.buttons:
            self.buttons[min(current, len(self.buttons) - 1)].setChecked(True)
        self.group.idClicked.connect(self.changed)
        self.setStyleSheet("QWidget{border:1px solid #3A4350; border-radius:6px;}")

    def index(self) -> int:
        return self.group.checkedId()

    def set_index(self, i: int, emit: bool = False):
        if i is None or i < 0 or i >= len(self.buttons):
            return
        self.buttons[i].setChecked(True)
        if emit:
            self.changed.emit(i)


def field(caption: str, widget: QWidget) -> QWidget:
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(3)
    v.addWidget(label(caption))
    v.addWidget(widget)
    return w


def grid(items: Sequence[QWidget], cols: int = 3, spacing: int = 10) -> QGridLayout:
    g = QGridLayout()
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(spacing)
    for i, w in enumerate(items):
        g.addWidget(w, i // cols, i % cols)
    for c in range(cols):
        g.setColumnStretch(c, 1)
    return g


def hbox(*items, stretch_end: bool = False, spacing: int = 8) -> QHBoxLayout:
    h = QHBoxLayout()
    h.setSpacing(spacing)
    for it in items:
        if it is None:
            h.addStretch(1)
        elif isinstance(it, QWidget):
            h.addWidget(it)
        else:
            h.addLayout(it)
    if stretch_end:
        h.addStretch(1)
    return h


def vbox(*items, spacing: int = 10, margins=(0, 0, 0, 0)) -> QVBoxLayout:
    v = QVBoxLayout()
    v.setSpacing(spacing)
    v.setContentsMargins(*margins)
    for it in items:
        if it is None:
            v.addStretch(1)
        elif isinstance(it, QWidget):
            v.addWidget(it)
        else:
            v.addLayout(it)
    return v


class EngEdit(QLineEdit):
    """Number entry that accepts SI suffixes (20n, 1.5u, 2e-6) and shows engineering notation."""
    _SI = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6, "G": 1e9}

    def __init__(self, value: float = 0.0, unit: str = ""):
        super().__init__()
        self.unit = unit
        self._v = value
        self.setValue(value)
        self.editingFinished.connect(self._parse)

    def _parse(self):
        t = self.text().strip().replace(self.unit, "").strip() if self.unit else self.text().strip()
        mult = 1.0
        if t and t[-1] in self._SI and not t[-1].isdigit():
            mult = self._SI[t[-1]]
            t = t[:-1]
        try:
            self._v = float(t) * mult
        except ValueError:
            pass
        self.setValue(self._v)

    def value(self) -> float:
        self._parse()
        return self._v

    def setValue(self, v: float):
        from ..core.units import eng
        self._v = float(v)
        self.setText(eng(self._v, self.unit, 6))


class NumEdit(EngEdit):
    """Plain number entry (no SI prefix on display) for dB, ratios, counts … Shows up to 7 significant digits."""

    def setValue(self, v: float):
        self._v = float(v)
        self.setText(f"{self._v:.7g} {self.unit}".strip())


def dspin(value: float = 0.0, lo: float = -1e12, hi: float = 1e12, decimals: int = 4,
          step: float = 0.1, suffix: str = "") -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setValue(value)
    s.setKeyboardTracking(False)
    if suffix:
        s.setSuffix(f" {suffix}")
    s.setButtonSymbols(QDoubleSpinBox.NoButtons)
    return s


def ispin(value: int = 0, lo: int = 0, hi: int = 10**9, suffix: str = "") -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    s.setKeyboardTracking(False)
    if suffix:
        s.setSuffix(f" {suffix}")
    s.setButtonSymbols(QSpinBox.NoButtons)
    return s


def combo(items: Iterable, current: Any = None) -> QComboBox:
    c = QComboBox()
    for it in items:
        if isinstance(it, tuple):
            c.addItem(str(it[0]), it[1])
        else:
            c.addItem(str(it), it)
    if current is not None:
        i = c.findData(current)
        if i < 0:
            i = c.findText(str(current))
        if i >= 0:
            c.setCurrentIndex(i)
    return c


def set_combo_data(c: QComboBox, value: Any) -> None:
    for i in range(c.count()):
        d = c.itemData(i)
        try:
            if d == value or (isinstance(d, (int, float)) and isinstance(value, (int, float))
                              and abs(float(d) - float(value)) < 1e-9):
                c.setCurrentIndex(i)
                return
        except Exception:
            continue


def mark_changed(w: QWidget, changed: bool) -> None:
    w.setProperty("changed", changed)
    w.style().unpolish(w)
    w.style().polish(w)


def scroll(widget: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setWidget(widget)
    return sa


# ---- settings binding ------------------------------------------------------------------------
def bind(settings, key: str, w: QWidget, default: Any = None) -> QWidget:
    """Load the saved value into ``w`` and save every change (autosaved settings file)."""
    val = settings.get(key, default)
    if isinstance(w, EngEdit):
        if isinstance(val, (int, float)):
            w.setValue(float(val))
        w.editingFinished.connect(lambda: settings.set(key, w.value()))
    elif isinstance(w, QLineEdit):
        if val is not None:
            w.setText(str(val))
        w.editingFinished.connect(lambda: settings.set(key, w.text()))
    elif isinstance(w, (QDoubleSpinBox, QSpinBox)):
        if val is not None:
            try:
                w.setValue(val)
            except TypeError:
                pass
        w.valueChanged.connect(lambda v: settings.set(key, v))
    elif isinstance(w, QComboBox):
        if val is not None:
            set_combo_data(w, val)
        w.currentIndexChanged.connect(lambda i: settings.set(key, w.itemData(i)))
    elif isinstance(w, QCheckBox):
        if val is not None:
            w.setChecked(bool(val))
        w.toggled.connect(lambda b: settings.set(key, b))
    elif isinstance(w, QSlider):
        if val is not None:
            w.setValue(int(val))
        w.valueChanged.connect(lambda v: settings.set(key, v))
    elif isinstance(w, Seg):
        if val is not None:
            w.set_index(int(val))
        w.changed.connect(lambda i: settings.set(key, i))
    return w


# ---- plots ----------------------------------------------------------------------------------------
def plot(height: int = 170, ylabel: str = "", xlabel: str = "", title: str = ""):
    """Bench plot: auto-range, Ctrl+wheel zoom, SI-prefixed axes for SI units, right-click export.

    Give axis labels as a bare SI unit ("Hz", "s", "V", "W") or "Name (unit)" to get automatic
    prefixes (kHz, µs, mV …); feed the data in base units."""
    from .plots import BenchPlot
    return BenchPlot(height, ylabel, xlabel, title)


def pen(color: str, width: float = 1.5, dash: bool = False):
    return pg.mkPen(color, width=width, style=Qt.DashLine if dash else Qt.SolidLine)


class History:
    """Rolling time series for trend plots."""

    def __init__(self, maxlen: int = 3600):
        self.t = collections.deque(maxlen=maxlen)
        self.y: Dict[str, collections.deque] = {}
        self.maxlen = maxlen

    def add(self, **vals):
        self.t.append(time.time())
        for k, v in vals.items():
            self.y.setdefault(k, collections.deque([float("nan")] * (len(self.t) - 1), maxlen=self.maxlen))
            self.y[k].append(float(v) if isinstance(v, (int, float)) and v is not None else float("nan"))
        for k in self.y:
            if len(self.y[k]) < len(self.t):
                self.y[k].append(float("nan"))

    def series(self, key: str):
        import numpy as np
        if not self.t:
            return np.array([]), np.array([])
        t = np.array(self.t) - self.t[-1]
        return t / 60.0, np.array(self.y.get(key, [float("nan")] * len(self.t)))


# ---- tables ------------------------------------------------------------------------------------
def table(headers: Sequence[str], rows: int = 0, stretch_last: bool = True) -> QTableWidget:
    t = QTableWidget(rows, len(headers))
    t.setHorizontalHeaderLabels(list(headers))
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch if stretch_last else QHeaderView.ResizeToContents)
    t.setShowGrid(False)
    t.setAlternatingRowColors(False)
    return t


def set_row(t: QTableWidget, r: int, values: Sequence[Any], colors: Optional[Dict[int, str]] = None):
    if t.rowCount() <= r:
        t.setRowCount(r + 1)
    for c, v in enumerate(values):
        it = QTableWidgetItem("" if v is None else str(v))
        if colors and c in colors:
            it.setForeground(pg.mkColor(colors[c]))
        t.setItem(r, c, it)


# ---- step list (sequence pages) ----------------------------------------------------------------
class StepRow(QWidget):
    def __init__(self, num: int, title: str):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(4, 6, 4, 6)
        h.setSpacing(10)
        self.num = QLabel(str(num))
        self.num.setFixedSize(26, 26)
        self.num.setAlignment(Qt.AlignCenter)
        h.addWidget(self.num, 0, Qt.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(1)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-size:14px; font-weight:500;")
        self.detail = label("", "lbl", wrap=True)
        v.addWidget(self.title)
        v.addWidget(self.detail)
        h.addLayout(v, 1)
        self.n = num
        self.set("wait")

    def set(self, status: str, detail: str = ""):
        col = {"done": (T.OK_BG, T.OK, "✓"), "run": (T.WARN_BG, T.WARN, str(self.n)),
               "fail": (T.BAD_BG, T.BAD, "✕"), "skip": ("#1A1F26", T.DIM, "–"),
               "wait": (T.IDLE_BG, T.MUTED, str(self.n))}[status]
        self.num.setText(col[2])
        self.num.setStyleSheet(f"background:{col[0]}; color:{col[1]}; border-radius:13px; font-weight:600;")
        self.setStyleSheet("background:#1C1A14; border-radius:6px;" if status == "run" else "")
        if detail:
            self.detail.setText(detail)


# ---- dialogs ------------------------------------------------------------------------------------
#: Confirmation dialogs are off unless Settings → "Ask before actions" is ticked.
CONFIRM = {"on": False}


def confirm(parent, title: str, text: str, ok_text: str = "Continue", danger: bool = False) -> bool:
    """Yes/no question. Returns True straight away when confirmations are switched off."""
    if not CONFIRM["on"]:
        return True
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Warning if danger else QMessageBox.Question)
    ok = box.addButton(ok_text, QMessageBox.AcceptRole)
    box.addButton("Cancel", QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is ok


def notice(parent, title: str, text: str) -> None:
    """Information the user asked for (always shown)."""
    QMessageBox.information(parent, title, text)


def confirm_checks(parent, title: str, text: str, checks: Sequence[str], ok_text: str = "Turn on") -> bool:
    """Confirmation that needs every checkbox ticked. Skipped when confirmations are off."""
    if not CONFIRM["on"]:
        return True
    d = QDialog(parent)
    d.setWindowTitle(title)
    v = QVBoxLayout(d)
    v.addWidget(label(text, "info"))
    boxes = [QCheckBox(c) for c in checks]
    for b in boxes:
        v.addWidget(b)
    bb = QDialogButtonBox()
    okb = bb.addButton(ok_text, QDialogButtonBox.AcceptRole)
    okb.setProperty("kind", "danger")
    okb.setEnabled(False)
    bb.addButton("Cancel", QDialogButtonBox.RejectRole)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    for b in boxes:
        b.toggled.connect(lambda *_: okb.setEnabled(all(x.isChecked() for x in boxes)))
    v.addWidget(bb)
    return d.exec() == QDialog.Accepted


class DiffDialog(QDialog):
    """Rows (key, live, saved [, note]) with a checkbox each. ``selected()`` → keys."""

    def __init__(self, parent, title: str, intro: str, rows: List[Tuple], ok_text: str = "Write checked"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(620)
        v = QVBoxLayout(self)
        v.addWidget(label(intro, "info"))
        self.t = table(["Write", "Setting", "Device now", "Saved", "Note"], len(rows))
        self.checks = []
        for r, row in enumerate(rows):
            cb = QCheckBox()
            cb.setChecked(True)
            self.checks.append((cb, row[0]))
            self.t.setCellWidget(r, 0, cb)
            set_row(self.t, r, [""] + [str(x) for x in row], {2: T.WARN})
        v.addWidget(self.t)
        bb = QDialogButtonBox()
        b = bb.addButton(ok_text, QDialogButtonBox.AcceptRole)
        b.setProperty("kind", "primary")
        bb.addButton("Cancel", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def selected(self) -> List[str]:
        return [k for cb, k in self.checks if cb.isChecked()]


class LogView(QPlainTextEdit):
    def __init__(self, max_lines: int = 2000):
        super().__init__()
        self.setReadOnly(True)
        self.setMaximumBlockCount(max_lines)
        self.setStyleSheet(f"font-family:{T.FONT_MONO}; font-size:12px; color:#C5CCD5;"
                           f"background:{T.PANEL}; border:1px solid {T.LINE}; border-radius:6px;")

    def add(self, tag: str, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.appendHtml(f'<span style="color:#7F8A97">{ts}</span>&nbsp;&nbsp;'
                        f'<span style="color:#8FB8FF">{tag:<6}</span> {msg}')


def fmt_num(v, f: str = "{:.4f}") -> str:
    if v is None or not isinstance(v, (int, float)):
        return "—" if v is None else str(v)
    try:
        return f.format(v)
    except (ValueError, TypeError):
        return str(v)
