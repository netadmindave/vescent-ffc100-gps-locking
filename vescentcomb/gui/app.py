"""Entry point: ``python -m vescentcomb.gui [--sim] [--settings PATH] [--no-scan]``.

Startup order: settings → add-ons (requirements installed on first load) → simulator (if --sim) → window."""
from __future__ import annotations

import argparse
import os
import sys


def install_wheel_guard(app):
    """Number fields and dropdowns never change with the mouse wheel; the wheel scrolls the page instead."""
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtWidgets import QAbstractScrollArea, QAbstractSpinBox, QComboBox

    class _WheelGuard(QObject):
        def eventFilter(self, obj, ev):
            if ev.type() == QEvent.Wheel and isinstance(obj, (QAbstractSpinBox, QComboBox)):
                w = obj.parentWidget()
                while w is not None and not isinstance(w, QAbstractScrollArea):
                    w = w.parentWidget()
                if w is not None:
                    from PySide6.QtWidgets import QApplication
                    QApplication.sendEvent(w.verticalScrollBar(), ev)
                return True                      # swallow: the value never changes
            return False

    app._wheel_guard = _WheelGuard(app)
    app.installEventFilter(app._wheel_guard)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="vescentcomb-gui", description="Comb Control GUI")
    ap.add_argument("--sim", action="store_true", help="run against the simulated bench (no hardware)")
    ap.add_argument("--settings", help="settings file (default: per-user app data folder)")
    ap.add_argument("--no-scan", action="store_true", help="don't open the device finder at startup")
    ap.add_argument("--data-dir", help="where recordings and scans are saved")
    args = ap.parse_args(argv)

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from ..settings import Settings, default_data_dir
    from . import theme
    from .main_window import MainWindow

    settings = Settings(args.settings)
    from .log_window import install as _install_logs
    _install_logs(os.path.dirname(str(settings.path)))
    if args.data_dir:
        settings.set("ui.data_dir", os.path.abspath(args.data_dir))
    elif not settings.get("ui.data_dir"):
        settings.set("ui.data_dir", str(default_data_dir()))

    app = QApplication.instance() or QApplication(sys.argv)
    install_wheel_guard(app)
    app.setApplicationName("Vescent Comb Control")
    app.setStyle("Fusion")
    app.setStyleSheet(theme.QSS)

    # the comb module (built in)
    from .. import addonkit
    infos = addonkit.load_enabled(settings, auto_install=False)
    failed = [a for a in infos.values() if a.state != "loaded"]
    if args.sim:
        from .. import sim
        sim.install(settings=settings)
    win = MainWindow(settings, simulated=args.sim)
    for a in failed:
        win.hub.emit_log("ADDON", f"{a.name}: {a.state} — {(a.error or '').strip().splitlines()[-1] if a.error else ''}")
    win.show()
    if not args.no_scan:
        QTimer.singleShot(200, win.startup)
    rc = app.exec()
    settings.flush()
    # Exit now: a worker thread still waiting on a slow GPIB/USB call (or VISA's own exit handlers)
    # must not keep the process hanging. Instruments are left exactly as they are.
    try:
        import logging
        logging.shutdown()
        sys.stdout.flush()
    except Exception:
        pass
    os._exit(rc)


if __name__ == "__main__":
    raise SystemExit(main())
