"""Logs window: everything the app logs, for troubleshooting.

Collects the event log (every device call, connect, error), device-state changes, Python
``logging`` records, uncaught exceptions and anything printed to stderr (worker tracebacks).
Capture starts when the app starts (``install()``), so the window shows history from launch.
Everything is also appended to ``vescentcomb.log`` next to the settings file.
"""
from __future__ import annotations

import collections
import logging
import os
import sys
import time
import traceback

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QCheckBox, QFileDialog, QLineEdit, QMainWindow, QPlainTextEdit, QVBoxLayout, QWidget

from . import theme as T
from . import widgets as W

LEVELS = ("INFO", "WARN", "ERROR", "DEBUG")


class _Bus(QObject):
    line = Signal(str, str, str, str)          # time, level, source, text


class LogBuffer:
    """Process-wide log store (thread-safe enough: deque appends are atomic; Qt signal is queued)."""

    def __init__(self, maxlen: int = 20000):
        self.lines = collections.deque(maxlen=maxlen)
        self.bus = _Bus()
        self.file = None

    def open_file(self, folder: str):
        try:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "vescentcomb.log")
            self._load_previous(path)
            if os.path.exists(path) and os.path.getsize(path) > 20_000_000:      # keep the file bounded
                os.replace(path, path + ".1")
            self.file = open(path, "a", encoding="utf-8", buffering=1)
            self.file.write(f"\n===== start {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        except Exception:
            self.file = None

    def _load_previous(self, path: str, n: int = 5000):
        """Earlier sessions' lines (the tail of vescentcomb.log), so the log survives a restart."""
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                tail = collections.deque(fh, maxlen=n)
        except OSError:
            return
        for line in tail:
            line = line.rstrip("\n")
            if line.startswith("====="):
                self.lines.append(("", "INFO", "session", line.strip("= ")))
                continue
            parts = line.split(None, 3)
            if len(parts) == 4 and parts[1] in LEVELS:
                self.lines.append((parts[0], parts[1], parts[2], parts[3]))
            elif line.strip():
                self.lines.append(("", "INFO", "", line))

    def add(self, level: str, source: str, text: str):
        ts = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
        for part in str(text).rstrip().splitlines() or [""]:
            self.lines.append((ts, level, source, part))
            if self.file is not None:
                try:
                    self.file.write(f"{ts} {level:<5} {source:<10} {part}\n")
                except Exception:
                    pass
            try:
                self.bus.line.emit(ts, level, source, part)
            except RuntimeError:
                pass


BUFFER = LogBuffer()


class _Handler(logging.Handler):
    def emit(self, record):
        lvl = {"WARNING": "WARN", "CRITICAL": "ERROR"}.get(record.levelname, record.levelname)
        BUFFER.add(lvl if lvl in LEVELS else "INFO", record.name[:10], self.format(record))


class _Stderr:
    """Tee: keeps the console output and copies it into the log (worker tracebacks land here)."""

    def __init__(self, orig):
        self.orig, self.buf = orig, ""

    def write(self, s):
        try:
            if self.orig is not None:
                self.orig.write(s)
        except Exception:
            pass
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if line.strip() and "This plugin does not support" not in line:
                BUFFER.add("ERROR" if ("Error" in line or "Traceback" in line) else "WARN", "stderr", line)

    def flush(self):
        try:
            if self.orig is not None:
                self.orig.flush()
        except Exception:
            pass


def install(log_folder: str = ""):
    """Start capturing (call once, early)."""
    if getattr(install, "_done", False):
        return
    install._done = True
    if log_folder:
        BUFFER.open_file(log_folder)
    h = _Handler()
    h.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(h)
    if root.level > logging.INFO or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)
    for noisy in ("pyvisa", "PIL", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    sys.stderr = _Stderr(sys.stderr)
    old_hook = sys.excepthook

    def hook(et, ev, tb):
        BUFFER.add("ERROR", "exception", "".join(traceback.format_exception(et, ev, tb)))
        if old_hook:
            old_hook(et, ev, tb)
    sys.excepthook = hook


def attach_hub(hub):
    """Event log and device states from the GUI hub."""
    hub.log.connect(lambda tag, msg: BUFFER.add("ERROR" if ("error" in msg.lower() or "failed" in msg.lower())
                                                else "INFO", tag, msg))
    hub.state.connect(lambda role, st, msg: BUFFER.add({"error": "ERROR", "reconnecting": "WARN"}.get(st, "DEBUG"),
                                                       role.upper(), f"state {st}" + (f": {msg}" if msg else ""))
                      if st != "ok" else None)


COLORS = {"INFO": "#C5CCD5", "WARN": "#E0B870", "ERROR": "#FF8A8A", "DEBUG": "#7F8A97"}


class LogWindow(QMainWindow):
    def __init__(self, settings=None):
        super().__init__(None)
        self.setWindowTitle("Logs — Comb Control")
        self.resize(1100, 700)
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(12, 10, 12, 12)
        self.ck = {lvl: QCheckBox(lvl) for lvl in LEVELS}
        for lvl, c in self.ck.items():
            c.setChecked(lvl != "DEBUG")
            c.toggled.connect(self.refill)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("filter: text or source (e.g. SCOPE, error, GPIB)")
        self.filter.textChanged.connect(self.refill)
        self.ck_follow = QCheckBox("Follow")
        self.ck_follow.setChecked(True)
        v.addLayout(W.hbox(*self.ck.values(), self.filter, self.ck_follow,
                           W.button("Copy all", slot=self.copy), W.button("Save…", slot=self.save),
                           W.button("Clear view", slot=lambda: self.view.clear())))
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(20000)
        self.view.setStyleSheet(f"font-family:{T.FONT_MONO}; font-size:12px; background:{T.PANEL};"
                                f"border:1px solid {T.LINE}; border-radius:6px;")
        v.addWidget(self.view, 1)
        path = getattr(BUFFER.file, "name", "")
        v.addWidget(W.label(f"Also written to {path}" if path else "", "lbl"))
        BUFFER.bus.line.connect(self._line)
        self.refill()

    def _ok(self, lvl, src, text):
        if not self.ck.get(lvl, self.ck["INFO"]).isChecked():
            return False
        f = self.filter.text().strip().lower()
        return not f or f in src.lower() or f in text.lower()

    @staticmethod
    def _html(ts, lvl, src, text):
        import html
        return (f'<span style="color:#7F8A97">{ts}</span>&nbsp;<span style="color:{COLORS.get(lvl)}">{lvl:<5}</span>'
                f'&nbsp;<span style="color:#8FB8FF">{html.escape(src)}</span>&nbsp;'
                f'<span style="color:{COLORS.get(lvl)}">{html.escape(text)}</span>')

    def _line(self, ts, lvl, src, text):
        if self._ok(lvl, src, text):
            self.view.appendHtml(self._html(ts, lvl, src, text))
            if self.ck_follow.isChecked():
                self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def refill(self):
        self.view.clear()
        for ts, lvl, src, text in list(BUFFER.lines):
            if self._ok(lvl, src, text):
                self.view.appendHtml(self._html(ts, lvl, src, text))

    def _text(self):
        return "\n".join(f"{ts} {lvl:<5} {src:<10} {t}" for ts, lvl, src, t in BUFFER.lines
                         if self._ok(lvl, src, t))

    def copy(self):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(self._text())

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save log", f"vescentcomb_log_{time.strftime('%Y%m%d_%H%M%S')}.txt",
                                              "Text (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._text())
