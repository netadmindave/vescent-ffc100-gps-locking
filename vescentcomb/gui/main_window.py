"""Main window shell: lock-chain bar, navigation, pages, status bar, instrument windows.

Everything instrument-specific comes from the add-on registry; this file knows no instrument."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Dict

from PySide6.QtCore import QByteArray, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import discovery
from ..settings import default_data_dir
from . import theme as T
from . import widgets as W
from .connections import ConnectionsDialog
from .pages.overview import OverviewPage
from .worker import Hub
from ..addonkit import REGISTRY


class ChainPill(QFrame):
    def __init__(self, caption: str):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(8)
        self.dot = QLabel("●")
        v = QVBoxLayout()
        v.setSpacing(0)
        self.cap = QLabel(caption)
        self.val = QLabel("—")
        v.addWidget(self.cap)
        v.addWidget(self.val)
        h.addWidget(self.dot)
        h.addLayout(v)
        self.set("—", "idle")

    def set(self, text: str, state: str):
        bg, fg = {"ok": (T.OK_BG, T.OK), "warn": ("#2A2112", T.WARN), "bad": (T.BAD_BG, T.BAD),
                  "idle": ("#1A1F26", T.IDLE)}[state]
        border = {"ok": "#1E5A45", "warn": "#5C4718", "bad": "#7A3038", "idle": "#3A4350"}[state]
        self.setStyleSheet(f"ChainPill{{background:{bg}; border:1px solid {border}; border-radius:6px;}}")
        self.dot.setStyleSheet(f"color:{fg}; font-size:10px;")
        self.cap.setStyleSheet(f"color:{fg}; font-size:11px; opacity:0.8;")
        self.val.setStyleSheet(f"color:{fg}; font-size:12px; font-weight:600;")
        self.val.setText(text.upper())


class _Signals(QObject):
    scanned = Signal(object)
    saved = Signal(object)
    opened = Signal(object)


def _bus_of(address: str) -> str:
    a = address.upper()
    if "::" in a:
        return a.split("::")[0].rstrip("0123456789") or "VISA"
    if a.count(".") == 3:
        return "LAN"
    return "USB serial"


def saved_found(role: str, s: dict):
    """A discovery.Found rebuilt from a saved role entry (no scan)."""
    f = discovery.Found(s["kind"], s["address"], _bus_of(s["address"]), model=s.get("model", ""),
                        serial=s.get("serial", ""), how="saved", status="matched")
    f.role = role
    return f


class MainWindow(QMainWindow):
    def __init__(self, settings, simulated: bool = False):
        super().__init__()
        self.settings = settings
        self.simulated = simulated
        self.hub = Hub(settings)
        self.chain_state = {}
        from .log_window import attach_hub, install as _install_logs
        _install_logs()
        attach_hub(self.hub)
        from ..comb_status import StatusWriter
        self.comb_status = StatusWriter(self.hub, settings)          # read by the Laser Lock application
        self.log_window = None
        from ..datafile import set_provider
        set_provider(self.metadata)
        self.setWindowTitle("Vescent Comb Control" + ("  [SIMULATED]" if simulated else ""))
        W.CONFIRM["on"] = bool(settings.get("ui.confirmations", False))
        self._build_menu()
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_topbar())
        mid = QHBoxLayout()
        mid.setSpacing(0)
        outer.addLayout(mid, 1)
        mid.addWidget(self._build_nav())
        self.stack = QStackedWidget()
        mid.addWidget(self.stack, 1)
        self.pages = {"overview": OverviewPage(self.hub, settings, self)}
        for spec in self.page_specs:
            try:
                self.pages[spec.key] = spec.get()(self.hub, settings, self)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.hub.emit_log("ADDON", f"{spec.addon}: page {spec.key} failed to build: {e}")
        for p in self.pages.values():
            self.stack.addWidget(p)
        self.windows: Dict[str, QMainWindow] = {}
        self._build_status()
        self.hub.polled.connect(self._on_poll)
        self.hub.state.connect(self._on_state)
        self.hub.devices_changed.connect(self._refresh_nav)
        self.hub.log.connect(self._last_log)
        self.sig = _Signals()
        self.sig.scanned.connect(self._auto_connect_result)
        self.sig.saved.connect(self._saved_result)
        self.sig.opened.connect(self._attach_opened)

        geo = settings.get("ui.main.geometry")
        if geo:
            self.restoreGeometry(QByteArray.fromHex(geo.encode()))
        else:
            self.resize(1500, 980)
        self.show_page(settings.get("ui.main.page", "overview"))
        self.rec_timer = QTimer(self)
        self.rec_timer.timeout.connect(self._rec_tick)
        self.rec_timer.start(1000)
        self._refresh_nav()

    # ---- construction -------------------------------------------------------------------------
    @property
    def page_specs(self):
        return sorted(REGISTRY.pages, key=lambda p: (p.order, p.key))

    @property
    def window_specs(self):
        return sorted(REGISTRY.windows, key=lambda w: (w.order, w.key))

    def _build_menu(self):
        mb = self.menuBar()
        m = mb.addMenu("File")
        m.addAction("Open data folder", self.open_data_folder)
        m.addAction("Change data folder…", self.change_data_folder)
        m.addAction("Open settings folder", lambda: self._open_path(os.path.dirname(self.settings.path)))
        m.addAction("Save settings now", lambda: self.hub.emit_log("SET", f"saved → {self.settings.save()}"))
        m.addSeparator()
        m.addAction("Quit", self.close)
        m = mb.addMenu("Devices")
        m.addAction("Find and assign devices…", self.open_finder)
        m.addAction("Disconnect all (leave instruments as they are)", lambda: self.hub.close_all(False))
        m.addSeparator()
        m.addAction("Logs…", self.open_logs)
        m = mb.addMenu("Pages")
        m.addAction("Overview", lambda: self.show_page("overview"))
        for spec in self.page_specs:
            m.addAction(spec.label, lambda k=spec.key: self.show_page(k))
        if REGISTRY.windows:
            m = mb.addMenu("Instruments")
            for spec in self.window_specs:
                m.addAction(spec.label.replace(" ↗", ""), lambda k=spec.key: self.open_window(k))
        menus = {}
        for menu, label, fn, _ in REGISTRY.menu_actions:
            menus.setdefault(menu, mb.addMenu(menu)).addAction(label, lambda fn=fn: fn(self))
        m = mb.addMenu("Settings")
        a = QAction("Ask before actions (confirmation dialogs)", self, checkable=True)
        a.setChecked(bool(self.settings.get("ui.confirmations", False)))
        a.toggled.connect(self._set_confirmations)
        m.addAction(a)
        a = QAction("Reconnect instruments automatically", self, checkable=True)
        a.setChecked(bool(self.settings.get("ui.auto_reconnect", True)))
        a.toggled.connect(lambda on: (self.settings.set("ui.auto_reconnect", on),
                                      [setattr(w, "auto_reconnect", on and w.reopen is not None)
                                       for w in self.hub.workers.values()]))
        m.addAction(a)
        m.addSeparator()
        m.addAction("Change data folder…", self.change_data_folder)
        m.addAction("Open settings folder", lambda: self._open_path(os.path.dirname(self.settings.path)))
        m = mb.addMenu("Help")
        m.addAction("Settings file location", lambda: W.notice(self, "Settings", f"Auto-saved to:\n{self.settings.path}"))

    def _build_topbar(self):
        bar = QFrame()
        bar.setStyleSheet(f"QFrame#tb{{background:{T.CHROME}; border-bottom:1px solid {T.LINE};}}")
        bar.setObjectName("tb")
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(6)
        self.chain = {}
        for i, spec in enumerate(REGISTRY.chain):
            if i:
                h.addWidget(W.label("›"))
            p = ChainPill(spec.caption)
            self.chain[spec.key] = p
            h.addWidget(p)
        h.addStretch(1)
        self.b_rec = QPushButton("● REC")
        self.b_rec.setCheckable(True)
        self.b_rec.toggled.connect(self.toggle_rec)
        self.b_rec.setToolTip("Record every device poll to CSV in the data folder")
        h.addWidget(self.b_rec)
        h.addWidget(W.button("Devices…", slot=self.open_finder))
        h.addWidget(W.button("Logs", slot=self.open_logs, tip="Everything the app logs, for troubleshooting"))
        return bar

    def _build_nav(self):
        self.nav = QListWidget()
        self.nav.setFixedWidth(236)
        self.nav.setStyleSheet(f"QListWidget{{background:{T.CHROME}; border:none; border-right:1px solid {T.LINE};"
                               f"padding:10px 6px; font-family:'IBM Plex Sans';}}"
                               f"QListWidget::item{{padding:8px 8px; border-radius:6px; margin:1px 0;}}"
                               f"QListWidget::item:selected{{background:#222A35; color:white;}}")
        self.nav_items = {}
        self.nav_rows = [("overview", "Overview", None, "page")]
        section = None
        for spec in self.page_specs:
            if spec.section != section:
                section = spec.section
                self.nav_rows.append((f"-{section}", section.upper(), None, "sep"))
            self.nav_rows.append((spec.key, spec.label, spec.role, "page"))
        if REGISTRY.windows:
            self.nav_rows.append(("-windows", "INSTRUMENT WINDOWS", None, "sep"))
            for spec in self.window_specs:
                self.nav_rows.append((spec.key, spec.label, spec.role, "window"))
        for key, label, role, kind in self.nav_rows:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, (key, kind))
            if kind == "sep":
                it.setFlags(Qt.NoItemFlags)
                it.setForeground(Qt.gray)
            self.nav.addItem(it)
            self.nav_items[key] = it
        self.nav.itemClicked.connect(self._nav_clicked)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.setWordWrap(True)
        return self.nav

    def _build_status(self):
        sb = self.statusBar()
        self.st_labels = {}
        for role in [r for r, _ in sorted(REGISTRY.roles.items(), key=lambda x: x[1].order)]:
            l = QLabel(f"○ {role}")
            self.st_labels[role] = l
            sb.addWidget(l)
        self.st_last = QLabel("")
        sb.addPermanentWidget(self.st_last)
        self.st_settings = QLabel(f"settings: {self.settings.path}")
        sb.addPermanentWidget(self.st_settings)

    # ---- navigation ------------------------------------------------------------------------------
    def _nav_clicked(self, it):
        key, kind = it.data(Qt.UserRole)
        if kind == "page":
            self.show_page(key)
        elif kind == "window":
            self.open_window(key)

    def show_page(self, key):
        if key not in self.pages:
            key = "overview"
        self.stack.setCurrentWidget(self.pages[key])
        self.nav.setCurrentItem(self.nav_items[key])
        self.settings.set("ui.main.page", key)

    def open_window(self, key):
        if key not in self.windows:
            spec = next((w for w in REGISTRY.windows if w.key == key), None)
            if spec is None:
                self.hub.emit_log("UI", f"no add-on provides the '{key}' window ")
                return
            self.windows[key] = spec.get()(self.hub, self.settings, self)
        w = self.windows[key]
        w.show()
        w.raise_()
        w.activateWindow()

    def _refresh_nav(self):
        for key, label, role, kind in self.nav_rows:
            if role is None:
                continue
            it = self.nav_items[key]
            f = self.hub.found.get(role)
            if self.hub.has(role) and f:
                addr = f.address.replace("::INSTR", "")
                addr = addr if len(addr) < 26 else "…" + addr[-24:]
                it.setText(f"{label}\n   {addr}"
                           + (f" · SN {f.serial}" if "opl" in REGISTRY.roles[role].capabilities else ""))
                it.setForeground(Qt.white)
            else:
                it.setText(f"{label}\n   not connected")
                it.setForeground(Qt.gray)
        for role, l in self.st_labels.items():
            f = self.hub.found.get(role)
            l.setText(f"{'●' if self.hub.has(role) else '○'} {role} {f.address if f and self.hub.has(role) else ''}")
            l.setStyleSheet(f"color:{T.OK if self.hub.has(role) else T.DIM};")

    # ---- connections -------------------------------------------------------------------------------
    def startup(self):
        """Connect the devices saved last time, at their saved addresses — no scan. Anything that does
        not answer is listed in the device finder with the free ports it could be on."""
        saved = {r: s for r, s in (self.settings.get("roles", {}) or {}).items()
                 if r in REGISTRY.roles and isinstance(s, dict) and s.get("address") and s.get("kind") in REGISTRY.drivers}
        if not saved:
            self.open_finder()
            return
        self.hub.emit_log("DEV", f"connecting {len(saved)} saved devices (no scan)…")

        def run():
            ok, failed = {}, {}
            for role, s in saved.items():
                f = saved_found(role, s)
                dev = None
                try:
                    dev = discovery.open_found(f)
                    ident = dev.identify()
                    if f.bus == "USB serial" and s.get("serial") and ident.serial and ident.serial != s["serial"]:
                        raise RuntimeError(f"{f.address} now answers as SN {ident.serial}, expected {s['serial']}")
                    ok[role] = (f, dev)
                except Exception as e:
                    if dev is not None:
                        try:
                            dev.close()
                        except Exception:
                            pass
                    failed[role] = (f, str(e))
            self.sig.saved.emit((ok, failed))
        threading.Thread(target=run, daemon=True).start()

    def _saved_result(self, r):
        ok, failed = r
        if ok:
            self.connect_found({role: f for role, (f, _) in ok.items()}, None, remember=False,
                               opened={role: dev for role, (_, dev) in ok.items()})
        for role, (f, err) in failed.items():
            self.hub.emit_log(role.upper(), f"saved device not answering at {f.address}: {err}")
        if failed:
            self.open_finder(failed={role: err for role, (_, err) in failed.items()})

    def _auto_connect_result(self, res):
        if isinstance(res, Exception) or res.missing or any(f.status != "matched" for f in res.assignments.values()):
            self.open_finder()
        else:
            self.connect_found(res.assignments, res)
            self.hub.emit_log("DEV", "all devices matched the saved roles — connected without asking")

    def open_finder(self, failed=None):
        """Device finder. It does not scan by itself: it shows the saved assignments and the free ports
        for each role; press Rescan to probe."""
        already = [self.hub.found[r] for r in self.hub.workers if r in self.hub.found]
        dlg = ConnectionsDialog(self, self.settings, self.simulated, already_open=already,
                                identify_hook=self._identify_open, failed=failed,
                                connected={r: self.hub.found[r] for r in self.hub.workers if r in self.hub.found})
        ok = dlg.exec()
        if dlg.want_sim:
            self.switch_to_sim()
            return
        if ok:
            chosen = dlg.chosen()
            self.connect_found(chosen, dlg.result_scan, remember=dlg.ck_remember.isChecked())

    def _identify_open(self, f):
        for role, found in self.hub.found.items():
            if found is f or (found.address == f.address and self.hub.has(role)):
                self.hub.call(role, lambda d: d.flash_identify(), log="backlight flashed")
                return True
        return False

    def connect_found(self, chosen, scan, remember=True, opened=None, only=False, on_done=None, after=None):
        """Connect ``chosen`` roles. Opening instruments (and their on-connect hooks) runs in a background
        thread, so a slow or hung port never freezes the window. ``only=True`` leaves other roles alone."""
        opened = dict(opened or {})
        if scan is not None:
            self.hub.scan = scan
        closing = []
        if not only:                       # close roles that are no longer wanted or point at a different unit
            for role in list(self.hub.workers):
                f = chosen.get(role)
                cur = self.hub.found.get(role)
                if f is None or cur is None or f.address != cur.address:
                    closing.append(self.hub.detach(role, safe=False, wait=False))
        closing = [e for e in closing + [after] if e is not None]
        if closing:                        # reopen only after those ports are released (in the background)
            after = threading.Event()

            def _all(evs=closing, ev=after):
                for e in evs:
                    e.wait(8.0)
                ev.set()
            threading.Thread(target=_all, daemon=True).start()
        todo = {}
        for role, f in chosen.items():
            if self.hub.has(role):
                self.hub.found[role] = f
            else:
                todo[role] = f
        if not todo:
            self.hub.devices_changed.emit()
            if on_done:
                on_done({})
            return

        def hooks_for(role, f):
            hooks = REGISTRY.on_connect.get(f.kind, [])

            def run_hooks(d, hooks=hooks, role=role):
                for fn in hooks:
                    try:
                        fn(d, self.settings)
                    except Exception as e:
                        self.hub.emit_log(role.upper(), f"on-connect hook failed: {e}")
            return run_hooks

        def run():
            if after is not None:
                after.wait(8.0)
            res = {}
            for role, f in todo.items():
                self.hub.emit_log(role.upper(), f"opening {f.address} …")
                try:
                    dev = opened.pop(role, None) or discovery.open_found(f)
                    if f.how == "manual" and not f.serial:      # picked by hand: learn its serial for next time
                        try:
                            ident = dev.identify()
                            f.serial, f.model = ident.serial or "", ident.model or f.model
                        except Exception:
                            pass
                    hooks_for(role, f)(dev)
                    res[role] = (f, dev, None)
                except Exception as e:
                    res[role] = (f, None, str(e))
            self.sig.opened.emit((res, remember, on_done))
        threading.Thread(target=run, daemon=True, name="connect").start()

    def _attach_opened(self, payload):
        res, remember, on_done = payload
        for role, (f, dev, err) in res.items():
            if err is not None:
                self.hub.emit_log(role.upper(), f"could not open {f.address}: {err}")
                continue
            if self.hub.has(role):                   # connected meanwhile by another path
                try:
                    dev.close()
                except Exception:
                    pass
                continue
            spec = REGISTRY.roles.get(role)
            poll = spec.poll_interval(self.settings) if spec else 1.0
            hooks = REGISTRY.on_connect.get(f.kind, [])

            def run_hooks(d, hooks=hooks, role=role):
                for fn in hooks:
                    try:
                        fn(d, self.settings)
                    except Exception as e:
                        self.hub.emit_log(role.upper(), f"on-connect hook failed: {e}")
            self.hub.attach(role, dev, f, poll, reopen=lambda f=f: discovery.reopen(f), on_reopen=run_hooks)
            self.hub.emit_log(role.upper(), f"connected {f.label} ({f.status})")
            if remember:
                self.settings.set_role(role, f.kind, f.serial, f.model, f.address)
        self.hub.devices_changed.emit()
        for spec in REGISTRY.windows:
            key = spec.key
            if self.settings.get(f"ui.windows.{key}.open") and self.hub.has(spec.role or ""):
                self.open_window(key)
        if on_done:
            on_done(res)

    def connect_role(self, role, f, on_done=None, after=None):
        """Connect one role now (the device finder's per-device Connect button). ``after``: an Event to
        wait for first (the previous connection closing), waited for in the background."""
        self.connect_found({role: f}, None, remember=True, only=True, on_done=on_done, after=after)

    def disconnect_role(self, role):
        """Close one role without touching the instrument; returns an Event set when it's closed."""
        ev = self.hub.detach(role, safe=False, wait=False)
        self.hub.emit_log(role.upper(), "disconnected (instrument left as it is)")
        return ev

    def assign_unit(self, role, kind, serial):
        """Point ``role`` at the unit with ``serial`` (OPL / laser dropdowns)."""
        scan = self.hub.scan
        if scan is None:
            return
        target = next((f for f in scan.found if f.kind == kind and f.serial == serial), None)
        if target is None:
            return
        cur = self.hub.found.get(role)
        if cur is not None and cur.address == target.address:
            return
        other = next((r for r, f in self.hub.found.items() if f.address == target.address and r != role), None)
        if not W.confirm(self, "Change unit", f"Use {target.label} as {REGISTRY.role_label(role)}?"
                         + (f"\nIt is currently {REGISTRY.role_label(other)}; the two will be swapped." if other else ""),
                         "Change"):
            return
        chosen = {r: f for r, f in self.hub.found.items() if self.hub.has(r)}
        if other and cur is not None:
            chosen[other] = cur
        chosen[role] = target
        for r in {role, other} - {None}:
            self.hub.detach(r, safe=False)
        self.connect_found(chosen, scan)

    def open_logs(self):
        from .log_window import LogWindow
        if self.log_window is None:
            self.log_window = LogWindow(self.settings)
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    def switch_to_sim(self):
        from .. import sim
        self.hub.close_all(False)
        sim.install()
        self.simulated = True
        self.setWindowTitle(self.windowTitle() + "  [SIMULATED]")
        self.open_finder()

    # ---- polls → lock chain -----------------------------------------------------------------------------
    def _on_poll(self, role, d):
        for spec in REGISTRY.chain:
            if spec.role != role:
                continue
            try:
                r = spec.update(d, self.settings)
            except Exception:
                r = None
            if r:
                self.chain[spec.key].set(*r)
                self.chain_state[spec.key] = {"caption": spec.caption, "text": r[0], "state": r[1]}

    def metadata(self):
        """Bench state written into the header of every data file (vescentcomb.datafile)."""
        from .reference_panel import reference_state
        inst = {}
        for role in list(self.hub.workers):
            f = self.hub.found.get(role)
            last = {k: v for k, v in self.hub.last(role).items()
                    if isinstance(v, (int, float, str, bool)) or v is None}
            inst[role] = {"model": getattr(f, "model", ""), "serial": getattr(f, "serial", ""),
                          "address": getattr(f, "address", ""), "last_poll": last}
        return {"simulated": self.simulated, "locks": dict(self.chain_state),
                "reference_10MHz": reference_state(self.hub), "instruments": inst,
                "settings_file": str(self.settings.path)}

    def _on_state(self, role, state, msg):
        l = self.st_labels.get(role)
        if l is None:
            return
        if state == "error":
            l.setStyleSheet(f"color:{T.BAD};")
            l.setToolTip(msg)
        elif state == "reconnecting":
            l.setStyleSheet(f"color:{T.WARN};")
            l.setToolTip(msg)
        elif state in ("ok", "reconnected"):
            l.setStyleSheet(f"color:{T.OK};")

    def _last_log(self, tag, msg):
        self.st_last.setText(f"{time.strftime('%H:%M:%S')} {tag}: {msg[:90]}")

    def after_lock_sequence(self):
        """Pages re-read their instruments after a sequence changed them."""
        for page in self.pages.values():
            if getattr(page, "ROLE", None) and self.hub.has(page.ROLE) and hasattr(page, "reread"):
                page.reread()

    # ---- top-bar actions -------------------------------------------------------------------------------
    def toggle_rec(self, on):
        if on:
            folder = os.path.join(self.settings.get("ui.data_dir") or str(default_data_dir()),
                                  time.strftime("%Y-%m-%d"), time.strftime("session_%H%M%S"))
            self.hub.start_logging(folder)
        else:
            self.hub.stop_logging()
            self.b_rec.setText("● REC")

    def _rec_tick(self):
        if self.hub.logging:
            el = int(time.time() - self.hub.log_t0)
            self.b_rec.setText(f"● REC {el//3600:02d}:{el%3600//60:02d}:{el%60:02d}")
            self.b_rec.setStyleSheet(f"color:{T.BAD}; background:#2A1719; border-color:#5A2228;")
        else:
            self.b_rec.setStyleSheet("")

    def safe_standby(self):
        items = REGISTRY.safe_standby
        if not items:
            self.hub.emit_log("SAFE", "no enabled add-on has an output that Safe standby switches off")
            return
        what = "\n".join(f"• {desc}" for _, desc in items)
        if not W.confirm(self, "Safe standby", f"{what}\n\nEverything else (the comb, the FPGA loops, the OPL servos) "
                         "is left as it is — shutting the comb down is a deliberate action on its own page.",
                         "Safe standby", True):
            return
        for role, _ in items:
            if self.hub.has(role):
                self.hub.call(role, lambda d: d.safe_state(), log="safe state")

    def _set_confirmations(self, on):
        self.settings.set("ui.confirmations", bool(on))
        W.CONFIRM["on"] = bool(on)

    def open_data_folder(self):
        self._open_path(self.settings.get("ui.data_dir") or str(default_data_dir()))

    def change_data_folder(self):
        from PySide6.QtWidgets import QFileDialog
        cur = self.settings.get("ui.data_dir") or str(default_data_dir())
        d = QFileDialog.getExistingDirectory(self, "Data folder", cur)
        if d:
            self.settings.set("ui.data_dir", d)
            self.hub.emit_log("SET", f"data folder → {d}")

    # ---- add-ons ----------------------------------------------------------------------------------------------
    def restart(self):
        """Close (instruments left exactly as they are) and start again."""
        from PySide6.QtCore import QProcess
        from PySide6.QtWidgets import QApplication
        args = ["-m", "vescentcomb.gui"] + [a for a in sys.argv[1:]]
        if self.simulated and "--sim" not in args:
            args.append("--sim")
        self._restarting = True
        self.settings.flush()
        if self.close():
            QProcess.startDetached(sys.executable, args)
            QApplication.instance().quit()

    @staticmethod
    def _open_path(path):
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            try:
                subprocess.Popen(["xdg-open", path])
            except OSError:
                pass

    # ---- close ----------------------------------------------------------------------------------------------
    def closeEvent(self, e):
        """Close and leave every instrument exactly as it is (outputs, locks, servos). The next start
        reconnects to the saved devices without changing them."""
        if not getattr(self, "_restarting", False) and not W.confirm(
                self, "Quit", "Close Vescent Comb Control? Every instrument is left as it is.", "Quit"):
            e.ignore()
            return
        self.settings.set("ui.main.geometry", bytes(self.saveGeometry().toHex()).decode())
        for key, w in list(self.windows.items()):
            open_ = w.isVisible()
            w.close()
            self.settings.set(f"ui.windows.{key}.open", open_)
        self.hub.close_all(safe=False)
        if self.log_window is not None:
            self.log_window.close()
        self.settings.flush()
        super().closeEvent(e)
