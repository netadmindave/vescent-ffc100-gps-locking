"""Headless GUI smoke test: build, connect to the simulator, restart, check state came back."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from vescentcomb import discovery  # noqa: E402
from vescentcomb.settings import Settings  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from vescentcomb.gui import theme
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    a.setStyleSheet(theme.QSS)
    return a


def _pump(app, sec):
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(int(sec * 1000), loop.quit)
    loop.exec()


def test_gui_builds_connects_and_restores(app, world, tmp_path, monkeypatch):
    from vescentcomb.gui import widgets as W
    from vescentcomb.gui.main_window import MainWindow
    monkeypatch.setattr(W, "confirm", lambda *a, **k: True)

    path = tmp_path / "settings.json"
    s = Settings(path, autosave_delay=0.05)
    win = MainWindow(s, simulated=True)
    win.show()
    res = discovery.assign_roles(discovery.scan_all(), s.get("roles", {}))
    win.connect_found(res.assignments, res)
    _pump(app, 2.0)
    from vescentcomb.addonkit import REGISTRY
    assert {"overview", "combseq", "ffc", "fpga", "opl1"} <= set(win.pages)
    for key in win.pages:
        win.show_page(key)
        _pump(app, 0.2)
    for spec in REGISTRY.windows:
        win.open_window(spec.key)
        _pump(app, 0.3)
    assert set(win.windows) == {w.key for w in REGISTRY.windows}
    assert [c.key for c in REGISTRY.chain] == ["gps", "ffc", "ceo", "frep"]
    win.show_page("fpga")
    fp = win.pages["fpga"]
    fp.refresh_iq(); fp.refresh_spectrum(); _pump(app, 1.0)
    x = fp.c_iq.getData()[0]; assert x is not None and len(x) > 10
    lk = win.pages["combseq"]
    lk.ck_wd.setChecked(True); _pump(app, 0.2); assert lk.wd is not None and lk.wd.running
    lk.ck_wd.setChecked(False)
    win.comb_status.write()
    import json
    st = json.load(open(win.comb_status.path))
    assert st["app"] == "vescentcomb" and st["connected"]["opl1"] and "comb_locked" in st
    win.close()
    _pump(app, 0.3)

    s2 = Settings(path)
    assert s2.get("ui.main.page") == "fpga"
    assert s2.get("roles.opl1.serial") == "OPL-0001"

    win2 = MainWindow(s2, simulated=True)
    win2.close()


def test_plot_wheel_needs_ctrl_and_exports(app, tmp_path):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from vescentcomb import datafile
    from vescentcomb.gui import widgets as W
    p = W.plot(200, "Power (W)", "Frequency (Hz)", title="t")
    p.resize(400, 300)
    p.show()
    p.plot([1e6, 2e6, 3e6], [1e-6, 3e-6, 2e-6], name="a")
    _pump(app, 0.2)
    vb = p.getPlotItem().getViewBox()
    before = vb.viewRange()
    ev = QWheelEvent(QPointF(200, 150), QPointF(200, 150), QPoint(0, 0), QPoint(0, 120), Qt.NoButton,
                     Qt.NoModifier, Qt.NoScrollPhase, False)
    p.wheelEvent(ev)
    assert not ev.isAccepted() and vb.viewRange() == before and vb.autoRangeEnabled()[0]
    assert p.getPlotItem().getAxis("bottom").labelUnits == "Hz"          # SI prefixes come from the unit
    path = p.save_csv(str(tmp_path / "plot.csv"))
    meta = datafile.read_header(path)
    assert meta["plot_curves"] == ["a"] and meta["columns"] == ["Frequency (Hz)", "Power (W)"]
    assert p.save_png(str(tmp_path / "plot.png")) and (tmp_path / "plot.png").stat().st_size > 1000
