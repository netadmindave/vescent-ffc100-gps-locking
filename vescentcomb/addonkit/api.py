"""The object every add-on's ``register(api)`` receives.

Everything an add-on can contribute goes through these methods. GUI classes are given as
``"module:Class"`` strings so a script that never opens the GUI never imports Qt.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .registry import (REGISTRY, ChainSpec, DriverSpec, RoleSpec, Scanner, SerialProbe, UISpec,
                       VisaSilentProbe, resolve)


class AddonAPI:
    def __init__(self, info, registry=REGISTRY):
        self.info = info
        self.id = info.id
        self.package = info.module_name
        self.r = registry

    # ---- instruments ---------------------------------------------------------------------------
    def add_device(self, kind: str, cls, label: str = "") -> None:
        """An instrument driver class (subclass of vescentcomb.Device)."""
        self.r.drivers[kind] = DriverSpec(kind, cls, label or kind, self.id, self.package)

    def add_role(self, role: str, label: str, kinds: Iterable[str], capabilities: Iterable[str] = (),
                 poll_s: Any = 1.0, bench_row: bool = False, order: int = 100) -> None:
        """A job on the bench ("opl2", "scope", "sa"…). Calling it again for an existing role adds kinds,
        so a second add-on can plug a new instrument model into a role another add-on owns."""
        if role in self.r.roles:
            spec = self.r.roles[role]
            for k in kinds:
                if k not in spec.kinds:
                    spec.kinds.append(k)
            spec.capabilities = tuple(dict.fromkeys(spec.capabilities + tuple(capabilities)))
            return
        self.r.roles[role] = RoleSpec(role, label, list(kinds), self.id, tuple(capabilities), poll_s,
                                      bench_row, order)

    def add_serial_probe(self, name: str, match: Callable, probe: Callable, exclusive: bool = False,
                         priority: int = 50) -> None:
        """Identify a USB-serial port. ``match(PortInfo)`` decides from VID/PID only (no bytes sent)."""
        self.r.serial_probes.append(SerialProbe(name, match, probe, exclusive, priority, self.id))
        self.r.serial_probes.sort(key=lambda p: p.priority)

    def add_visa_classifier(self, fn: Callable[[str], Optional[str]]) -> None:
        """``fn(idn_string) -> kind | None`` for instruments that answer *IDN?."""
        self.r.visa_classifiers.append((fn, self.id))

    def add_visa_probe(self, name: str, probe: Callable, priority: int = 50) -> None:
        """For GPIB instruments that do NOT answer *IDN? (``probe(inst, resource, bus, opts)``)."""
        self.r.visa_probes.append(VisaSilentProbe(name, probe, priority, self.id))
        self.r.visa_probes.sort(key=lambda p: p.priority)

    def add_scanner(self, name: str, label: str, scan: Callable) -> None:
        """Anything that isn't serial or VISA (Ethernet discovery, a drive, …)."""
        self.r.scanners.append(Scanner(name, label, scan, self.id))

    def add_opener(self, kind: str, fn: Callable) -> None:
        """How to open a found instrument. Serial instruments use ``serial_opener``; VISA ones need none."""
        self.r.openers[kind] = fn

    def on_connect(self, kind: str, fn: Callable[[Any, Any], None]) -> None:
        """Called with (device, settings) right after the GUI opens an instrument of this kind."""
        self.r.on_connect.setdefault(kind, []).append(fn)

    def add_safe_standby(self, role: str, description: str) -> None:
        """Safe standby / quit call ``safe_state()`` on this role (laser output off, emission off …)."""
        self.r.safe_standby.append((role, description))

    # ---- GUI ---------------------------------------------------------------------------------------
    def add_page(self, key: str, label: str, cls, role: Optional[str] = None, section: str = "",
                 order: int = 100) -> None:
        """A page in the main window's navigation (``cls`` subclasses vescentcomb.gui.page_base.Page)."""
        self.r.pages.append(UISpec(key, label, cls, role, section or self.info.name, order, self.id, self.package))

    def add_window(self, key: str, label: str, cls, role: Optional[str] = None, order: int = 100) -> None:
        """A separate instrument window (``cls`` subclasses vescentcomb.gui.windows.base.InstrumentWindow)."""
        self.r.windows.append(UISpec(key, label, cls, role, "INSTRUMENTS", order, self.id, self.package))

    def add_overview_panel(self, key: str, cls, span: str = "card", order: int = 100) -> None:
        """A panel on the Overview page. ``span`` is "card" (one grid cell) or "wide" (full row)."""
        self.r.overview.append(UISpec(key, span, cls, None, "", order, self.id, self.package))

    def add_chain_pill(self, key: str, caption: str, role: str, update: Callable, order: int = 100) -> None:
        """A status pill in the top lock-chain bar, updated from ``role``'s polls."""
        self.r.chain.append(ChainSpec(key, caption, role, update, order, self.id))
        self.r.chain.sort(key=lambda c: c.order)

    def add_summary(self, role: str, fn: Callable[[Dict[str, Any]], str]) -> None:
        """One-line live summary for the Overview "Bench instruments" table."""
        self.r.summaries[role] = fn

    def add_reference(self, role: str, input: str, mode: str = "switch", status=None, option: Optional[str] = None,
                      detail=None, note: str = "") -> None:
        """Declare how ``role`` uses the 10 MHz (GPS) reference, for the Overview reference list.

        ``mode``: "switch" (the GUI can turn it on/off through bool option ``option``), "auto"
        (the instrument switches by itself when it sees a reference), "always" (hard-wired) or
        "status" (read-only). ``status(poll) -> True/False/None`` says whether it is in use now."""
        from .registry import RefSpec
        self.r.references = [x for x in self.r.references if x.role != role]
        self.r.references.append(RefSpec(role, input, mode, status, option, detail, note, self.id))

    def add_menu_action(self, menu: str, label: str, fn: Callable[[Any], None]) -> None:
        """An entry in the main menu bar; ``fn(main_window)``."""
        self.r.menu_actions.append((menu, label, fn, self.id))

    # ---- simulator -----------------------------------------------------------------------------------
    def add_sim(self, fn) -> None:
        """``fn(world)`` adds this add-on's simulated instruments (``"sim:install"`` string is fine)."""
        self.r.sim_hooks.append((fn if callable(fn) else (lambda w, s=fn: resolve(s, self.package)(w)), self.id))

    # ---- helpers ---------------------------------------------------------------------------------------
    def resolve(self, spec):
        return resolve(spec, self.package)

    @staticmethod
    def serial_opener(cls, baudrate: int = 115200, timeout: float = 1.0, **kw) -> Callable:
        """Opener for drivers whose constructor takes ``(port, ser=...)``."""
        def open_(found):
            from ..discovery import HOOKS
            extra = {k: (v(found) if callable(v) else v) for k, v in kw.items()}
            c = resolve(cls, "") if isinstance(cls, str) else cls
            return c(found.address, ser=HOOKS.serial_factory(found.address, baudrate, timeout), **extra)
        return open_
