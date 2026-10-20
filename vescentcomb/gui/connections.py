"""Startup dialog: scan, show what was found, assign roles (by serial), connect."""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout,
                               QWidget)

from .. import discovery
from ..discovery import ROLES, ScanOptions
from ..addonkit import REGISTRY
from . import theme as T
from . import widgets as W

STATUS = {"matched": ("Matched", "ok"), "moved": ("Moved", "warn"), "new": ("New", "ok"),
          "available": ("Available", "idle"), "unknown": ("Unknown", "warn"), "skipped": ("Skipped", "idle"),
          "missing": ("Missing", "bad")}


class _Bridge(QObject):
    done = Signal(object)
    progress = Signal(str)
    visa = Signal(object)


class ConnectionsDialog(QDialog):
    def __init__(self, parent, settings, simulated: bool = False, already_open=None, identify_hook=None,
                 failed=None, connected=None):
        super().__init__(parent)
        self.failed = dict(failed or {})            # role -> error text (saved device did not answer)
        self.connected = dict(connected or {})      # role -> Found already open in the app
        self.already_open = list(already_open or [])
        self.identify_hook = identify_hook
        self.settings = settings
        self.simulated = simulated
        self.setWindowTitle("Find and assign devices")
        self.setMinimumSize(1100, 760)
        self.result_scan = None
        self.want_sim = False
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(12)
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.addWidget(W.label("Find and assign devices", "h1"))
        col.addWidget(W.label("Saved devices connect at startup without a scan. Press Rescan to probe every port; "
                              "or pick a free port for a role from its list (\u201cport → as model\u201d)."
                              + ("  ·  SIMULATED BENCH" if simulated else ""), "lbl", wrap=True))
        head.addLayout(col, 1)
        self.pill = W.Pill("not scanned · saved settings")
        head.addWidget(self.pill)
        head.addWidget(W.button("Rescan", slot=self.rescan))
        v.addLayout(head)

        k = "ui.scan"
        self.o_bt = W.bind(settings, f"{k}.skip_bt", QCheckBox("Skip Bluetooth serial ports"), True)
        self.o_visa = W.bind(settings, f"{k}.visa", QCheckBox("Re-probe every GPIB board and address"), True)
        self.o_scan = {sc.name: W.bind(settings, f"{k}.scanner.{sc.name}", QCheckBox(sc.label), True)
                       for sc in REGISTRY.scanners}
        self.o_ftdi = W.bind(settings, f"{k}.probe_exclusive", QCheckBox("Let every probe try ports an exclusive probe "
                                                                      "claimed"), False)
        self.o_quiet = W.bind(settings, f"{k}.only_on_change", QCheckBox("Show this dialog only when something changed"), False)
        v.addLayout(W.hbox(self.o_bt, self.o_visa, *self.o_scan.values(), self.o_ftdi, self.o_quiet, None))
        if not REGISTRY.roles:
            v.addWidget(W.label("No add-ons are enabled, so there is nothing to look for. Settings → Add-ons… to "
                                "turn modules and tools on.", "hint"))

        p = W.Panel("Role assignments · saved by serial number")
        self.role_combo = {}
        self.role_btn, self.role_status, self.role_rbtn, self.role_dbtn = {}, {}, {}, {}
        items = []
        for role, (label, kinds) in ROLES.items():
            c = QComboBox()
            c.setMinimumWidth(260)
            c.setMinimumContentsLength(30)
            c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.role_combo[role] = c
            row = QWidget()                                # dropdown on its own line, buttons underneath:
            rv = QVBoxLayout(row)                          # nothing can overlap at any window width
            rv.setContentsMargins(0, 0, 0, 0)
            rv.setSpacing(6)
            rv.addWidget(c)
            h = QHBoxLayout()
            h.setContentsMargins(0, 0, 0, 0)
            rv.addLayout(h)
            if "opl" in REGISTRY.roles[role].capabilities:
                ib = W.button("Identify", slot=lambda r=role: self.identify(r), tip="Flash this OPL's backlight")
                ib.setMinimumWidth(ib.sizeHint().width())
                h.addWidget(ib)
            b = W.button("Connect", "primary", slot=lambda r=role: self.connect_one(r),
                         tip="Connect this device now, using the entry selected on the left")
            rb = W.button("Reconnect", slot=lambda r=role: self.reconnect_one(r),
                          tip="Close and reopen this device (the instrument itself is not changed)")
            db = W.button("Disconnect", slot=lambda r=role: self.disconnect_one(r),
                          tip="Stop talking to this device; it keeps running as it is")
            self.role_btn[role] = b
            self.role_rbtn[role], self.role_dbtn[role] = rb, db
            for x in (b, rb, db):
                x.setMinimumWidth(x.sizeHint().width())       # buttons never shrink under the list
                h.addWidget(x)
            st = W.label("", "lbl")
            self.role_status[role] = st
            h.addWidget(st, 1)
            items.append(W.field(label, row))
        p.add(W.grid(items, 1))                            # one device per row: nothing overlaps
        if "opl1" in self.role_combo and "opl2" in self.role_combo:
            p.add(W.hbox(W.button("⇄ Swap OPL #1 and #2", slot=self.swap_opls),
                         W.label("Identify flashes the OPL's front-panel backlight so you can see which box is which.",
                                 "lbl"), None))
        v.addWidget(p)

        p = W.Panel("What the scan found")
        self.l_count = W.label("", "lbl")
        p.add_right(self.l_count)
        self.t = W.table(["Port", "Bus", "Identified as", "How", "Serial", "Role", "Status"], 0)
        self.t.setMinimumHeight(260)
        p.add(self.t)
        p.add(W.label("Serial: USB ID and serial number first (no bytes sent); CP210x → read-only Interbus (SuperK); "
                      "FTDI → only the WB-SG2's $A*; other CDC → *IDN? with CR (OPL), then CR LF (FFC-100). "
                      "GPIB: *IDN? (300 ms), then ID?/SER? (HP 85xx), then the SWS status-byte read; device clear "
                      "after any timeout.", "lbl", wrap=True))
        v.addWidget(p, 1)

        foot = QHBoxLayout()
        self.ck_remember = QCheckBox("Remember these assignments")
        self.ck_remember.setChecked(True)
        foot.addWidget(self.ck_remember)
        foot.addStretch(1)
        if not simulated:
            foot.addWidget(W.button("Open offline (simulator)", slot=self.offline))
        foot.addWidget(W.button("Skip (connect nothing)", slot=self.reject))
        self.b_connect = W.button("Connect all", "primary", self.accept)
        foot.addWidget(self.b_connect)
        v.addLayout(foot)
        self.bridge = _Bridge()
        self.bridge.done.connect(self._scanned)
        self.bridge.progress.connect(lambda m: self.pill.set(m, "idle"))
        self.bridge.visa.connect(self._visa_listed)
        self._fill_saved()
        for role in self.role_combo:
            self._show_state(role, role in self.connected)
        if self.failed:
            self.pill.set(f"{len(self.failed)} saved device(s) not answering — pick a port or Rescan", "warn")

    # --------------------------------------------------------------------------------------------
    def options(self) -> ScanOptions:
        return ScanOptions(skip_bluetooth=self.o_bt.isChecked(), visa=self.o_visa.isChecked(),
                           scanners={n: c.isChecked() for n, c in self.o_scan.items()},
                           probe_exclusive_ports=self.o_ftdi.isChecked())

    def rescan(self):
        self.pill.set("scanning…", "warn")
        self.b_connect.setEnabled(False)
        opts = self.options()

        def run():
            try:
                res = discovery.scan_all(opts, progress=self.bridge.progress.emit,
                                         already_open=self.already_open)
                discovery.assign_roles(res, self.settings.get("roles", {}))
            except Exception as e:
                res = e
            self.bridge.done.emit(res)
        threading.Thread(target=run, daemon=True).start()

    def _scanned(self, res):
        self.b_connect.setEnabled(True)
        if isinstance(res, Exception):
            self.pill.set(f"scan failed: {res}", "bad")
            return
        self.result_scan = res
        self.pill.set(f"scan done · {res.duration_s:.1f} s", "ok")
        self._fill()

    # ---- role lists without a scan --------------------------------------------------------------
    def _serial_ports(self):
        if not hasattr(self, "_ports"):
            try:
                self._ports = [p for p in discovery.HOOKS.port_lister() if not p.is_bluetooth]
            except Exception:
                self._ports = []
        return self._ports

    def _visa_resources(self):
        """VISA addresses for the dropdowns. Listed in the background: a hung USB instrument can make
        list_resources() block until it is unplugged, and that must never freeze the window."""
        if hasattr(self, "_visa"):
            return self._visa
        if not getattr(self, "_visa_started", False):
            self._visa_started = True
            br = self.bridge

            def run():
                try:
                    rm = discovery.HOOKS.resource_manager()
                    out = [r for r in rm.list_resources() if not r.upper().startswith("ASRL")]
                except Exception:
                    out = []
                try:
                    br.visa.emit(out)
                except RuntimeError:                  # dialog already closed
                    pass
            threading.Thread(target=run, daemon=True, name="visa-list").start()
            self._visa_t0 = time.time()
            QTimer.singleShot(5000, self._visa_slow)
        return []

    def _visa_slow(self):
        if not hasattr(self, "_visa"):
            self.pill.set("VISA is not answering — a USB instrument may be hung: power-cycle or unplug it", "warn")

    def _visa_listed(self, res):
        self._visa = res
        if self.result_scan is None:                  # refill the saved/manual lists, keeping the choices
            keep = {r: c.currentData() for r, c in self.role_combo.items()}
            self._fill_saved()
            for r, d in keep.items():
                if d is not None:
                    W.set_combo_data(self.role_combo[r], d)
        if time.time() - getattr(self, "_visa_t0", 0) > 5:
            self.pill.set("VISA answered again", "ok")

    def _used_addresses(self, except_role):
        used = {f.address for r, f in self.connected.items() if r != except_role}
        for r, s in (self.settings.get("roles", {}) or {}).items():
            if r != except_role and r not in self.failed and isinstance(s, dict) and s.get("address"):
                used.add(s["address"])
        return used

    def _manual_items(self, role):
        """('COM7 · USB Serial Device → as Vescent SLICE-OPL', ('manual', kind, address, bus)) for every free
        port that could hold this role's instrument; matching ports first."""
        used = self._used_addresses(role)
        out, others = [], []
        for kind in REGISTRY.roles[role].kinds:
            spec = REGISTRY.drivers.get(kind)
            if spec is None:
                continue
            if kind in REGISTRY.openers:                  # serial (or network) instrument
                probes = [pr for pr in REGISTRY.serial_probes if pr.addon == spec.addon]
                if not probes:
                    continue                              # network instrument: only a scan finds it
                for info in self._serial_ports():
                    if info.device in used:
                        continue
                    try:
                        hit = any(pr.match(info) for pr in probes)
                    except Exception:
                        hit = False
                    item = (f"{info.device} · {info.description or info.usb_family} → as {spec.label}",
                            ("manual", kind, info.device, "USB serial"))
                    (out if hit else others).append(item)
            else:                                         # VISA instrument
                for res in self._visa_resources():
                    if res not in used:
                        out.append((f"{res} → as {spec.label}", ("manual", kind, res, res.split("::")[0])))
        return out + others

    def _add_manual(self, c, role):
        items = self._manual_items(role)
        if items:
            c.insertSeparator(c.count())
            for text, data in items:
                c.addItem(text, data)

    def _fill_saved(self):
        saved = self.settings.get("roles", {}) or {}
        for role, c in self.role_combo.items():
            c.blockSignals(True)
            c.clear()
            c.addItem("— not assigned —", None)
            cur = self.connected.get(role)
            s = saved.get(role)
            if cur is not None:
                c.addItem(f"connected: {cur.label}", ("found", cur))
                c.setCurrentIndex(c.count() - 1)
            elif isinstance(s, dict) and s.get("address") and s.get("kind") in REGISTRY.drivers:
                tag = "NOT ANSWERING" if role in self.failed else "saved"
                c.addItem(f"{tag}: {s.get('model') or s['kind']} · SN {s.get('serial') or '—'} · {s['address']}",
                          ("saved", role))
                if role not in self.failed:
                    c.setCurrentIndex(c.count() - 1)
                else:
                    c.setToolTip(self.failed[role])
            self._add_manual(c, role)
            c.blockSignals(False)

    def _fill(self):
        res = self.result_scan
        for role, (label, kinds) in ROLES.items():
            c = self.role_combo[role]
            c.blockSignals(True)
            c.clear()
            c.addItem("— not assigned —", None)
            for i, f in enumerate(res.found):
                if f.kind in kinds:
                    c.addItem(f.label, i)
            a = res.assignments.get(role)
            if a is not None:
                W.set_combo_data(c, res.found.index(a))
            elif role in res.missing:
                m = res.missing[role]
                c.addItem(f"MISSING: {m.get('model')} · SN {m.get('serial')}", None)
            if a is None:                                 # not found by the scan: offer the free ports
                found_addr = {f.address for f in res.found}
                for text, data in self._manual_items(role):
                    if data[2] not in found_addr:
                        if c.findData(data) < 0:
                            c.addItem(text, data)
            c.blockSignals(False)
        rows = res.found + res.unknown + res.skipped
        self.t.setRowCount(0)
        for r, f in enumerate(rows):
            st, kind = STATUS.get(f.status, (f.status, "idle"))
            if f.status == "moved":
                st = f"Moved · was {f.previous_address}"
            label = ROLES.get(f.role, ("",))[0] if f.role else "—"
            W.set_row(self.t, r, [f.address, f.bus, f.model or ("skipped" if f.status == "skipped" else "no reply"),
                                  f.how, f.serial or "—", label, st],
                      {6: {"ok": T.OK, "warn": T.WARN, "bad": T.BAD, "idle": T.MUTED}[kind]})
        ok = sum(1 for f in res.found)
        self.l_count.setText(f"{len(rows)} ports / addresses / drives checked · {ok} identified")

    def chosen(self):
        """role -> Found from the combo boxes (scanned, saved, already connected, or a port picked by hand)."""
        from .main_window import saved_found
        res = self.result_scan
        out = {}
        used = set()
        saved = self.settings.get("roles", {}) or {}
        for role, c in self.role_combo.items():
            d = c.currentData()
            if d is None:
                continue
            if isinstance(d, int):
                if res is None:
                    continue
                f = res.found[d]
            elif d[0] == "found":
                f = d[1]
            elif d[0] == "saved":
                f = saved_found(role, saved[role])
            else:                                         # ("manual", kind, address, bus)
                _, kind, addr, bus = d
                f = discovery.Found(kind, addr, bus, model=REGISTRY.drivers[kind].label, how="manual",
                                    status="new")
            if f.address in used:
                continue
            used.add(f.address)
            f.role = role
            out[role] = f
        return out

    def _show_state(self, role, connected: bool, text: str = ""):
        self.role_btn[role].setVisible(not connected)
        self.role_btn[role].setEnabled(True)
        self.role_rbtn[role].setVisible(connected)
        self.role_dbtn[role].setVisible(connected)
        self.role_rbtn[role].setEnabled(True)
        self.role_dbtn[role].setEnabled(True)
        self.role_status[role].setText(text)

    def disconnect_one(self, role):
        main = self.parent()
        if main is None or not hasattr(main, "disconnect_role"):
            return
        main.disconnect_role(role)
        self.connected.pop(role, None)
        self._show_state(role, False, "disconnected")

    def reconnect_one(self, role):
        main = self.parent()
        f = self.connected.get(role) or self.chosen().get(role)
        if main is None or f is None or not hasattr(main, "disconnect_role"):
            return
        ev = main.disconnect_role(role)
        self.connected.pop(role, None)
        for x in (self.role_rbtn[role], self.role_dbtn[role]):
            x.setEnabled(False)
        self.role_status[role].setText("reconnecting…")

        def done(res, role=role):
            try:
                self._done_one(role, f, res)
            except RuntimeError:
                pass
        main.connect_role(role, f, on_done=done, after=ev)

    def connect_one(self, role):
        f = self.chosen().get(role)
        main = self.parent()
        if f is None or main is None or not hasattr(main, "connect_role"):
            self.role_status[role].setText("pick a device first")
            return
        self.role_btn[role].setEnabled(False)
        self.role_status[role].setText("connecting…")

        def done(res, role=role):
            try:
                self._done_one(role, f, res)
            except RuntimeError:            # dialog already closed
                pass
        main.connect_role(role, f, on_done=done)

    def _done_one(self, role, f, res):
            f2, dev, err = res.get(role, (f, None, "not attempted"))
            if err:
                self._show_state(role, False, "failed")
                self.role_status[role].setToolTip(err)
            else:
                self.connected[role] = f2
                self._show_state(role, True, "")

    def swap_opls(self):
        a, b = self.role_combo["opl1"], self.role_combo["opl2"]
        ia, ib = a.currentIndex(), b.currentIndex()
        da, db = a.itemData(ia), b.itemData(ib)
        if self.result_scan is None:                      # saved/manual lists: swap the saved entries
            s = self.settings.get("roles", {}) or {}
            r1, r2 = s.get("opl1"), s.get("opl2")
            if r1 is not None:
                self.settings.set("roles.opl2", r1)
            if r2 is not None:
                self.settings.set("roles.opl1", r2)
            self.connected = {({"opl1": "opl2", "opl2": "opl1"}.get(r, r)): f for r, f in self.connected.items()}
            self._fill_saved()
            return
        W.set_combo_data(a, db)
        W.set_combo_data(b, da)

    def identify(self, role):
        f = self.chosen().get(role)
        if f is None:
            return
        if self.identify_hook and self.identify_hook(f):
            return

        def run():
            try:
                dev = discovery.open_found(f)
                dev.flash_identify()
                dev.close()
            except Exception as e:
                print("identify failed", e)
        threading.Thread(target=run, daemon=True).start()

    def offline(self):
        self.want_sim = True
        self.reject()
