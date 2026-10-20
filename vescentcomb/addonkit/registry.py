"""What the loaded add-ons contribute. The shell (discovery, GUI, simulator) reads only this."""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Callable, Dict, List, Optional, Tuple


def resolve(spec, package: str):
    """'module:Name' relative to an add-on package -> object (or pass objects through)."""
    if not isinstance(spec, str):
        return spec
    mod, _, name = spec.partition(":")
    m = import_module(f".{mod}" if not mod.startswith(".") else mod, package) if mod else import_module(package)
    return getattr(m, name) if name else m


@dataclass
class RoleSpec:
    role: str
    label: str
    kinds: List[str]
    addon: str = ""
    capabilities: Tuple[str, ...] = ()       # e.g. ("scope",) — lets other add-ons find it
    poll_s: Any = 1.0                        # float, or callable(settings) -> float
    bench_row: bool = False                  # list in the Overview "Bench instruments" table
    order: int = 100

    def poll_interval(self, settings) -> float:
        try:
            return float(self.poll_s(settings)) if callable(self.poll_s) else float(self.poll_s)
        except Exception:
            return 1.0


@dataclass
class DriverSpec:
    kind: str
    cls: Any                                 # class or 'module:Class'
    label: str
    addon: str = ""
    package: str = ""

    def get(self):
        if isinstance(self.cls, str):
            self.cls = resolve(self.cls, self.package)
        return self.cls


@dataclass
class SerialProbe:
    name: str
    match: Callable[[Any], bool]             # PortInfo -> bool (no bytes sent)
    probe: Callable[[Any, Any], Any]         # (PortInfo, ScanOptions) -> Found | None
    exclusive: bool = False                  # matched but silent -> don't let later probes talk to it
    priority: int = 50
    addon: str = ""


@dataclass
class VisaSilentProbe:
    name: str
    probe: Callable[..., Any]                # (inst, resource, bus, opts) -> Found | None
    priority: int = 50
    addon: str = ""


@dataclass
class Scanner:
    name: str                                # also the ScanOptions toggle key
    label: str                               # checkbox text in the device finder
    scan: Callable[[Any], List[Any]]         # ScanOptions -> [Found]
    addon: str = ""


@dataclass
class UISpec:
    key: str
    label: str
    cls: Any                                 # 'module:Class' (imported only when the GUI runs)
    role: Optional[str] = None
    section: str = ""
    order: int = 100
    addon: str = ""
    package: str = ""

    def get(self):
        if isinstance(self.cls, str):
            self.cls = resolve(self.cls, self.package)
        return self.cls


@dataclass
class ChainSpec:
    key: str
    caption: str
    role: str                                # updated from this role's polls
    update: Callable[[Dict[str, Any], Any], Optional[Tuple[str, str]]]   # (poll, settings) -> (text, state)
    order: int = 100
    addon: str = ""


@dataclass
class RefSpec:
    """How one instrument uses the shared 10 MHz (GPS) reference — shown in the Overview list."""
    role: str
    input: str                               # e.g. "rear 10 MHz REF IN"
    mode: str = "switch"                     # switch | auto | always | status
    status: Optional[Callable[[Dict[str, Any]], Optional[bool]]] = None    # poll -> using the reference?
    option: Optional[str] = None             # bool option key that turns it on/off (mode "switch")
    detail: Optional[Callable[[Dict[str, Any]], str]] = None               # poll -> short text
    note: str = ""
    addon: str = ""


@dataclass
class Registry:
    addons: Dict[str, Any] = field(default_factory=dict)          # id -> AddonInfo (loaded)
    roles: Dict[str, RoleSpec] = field(default_factory=dict)
    drivers: Dict[str, DriverSpec] = field(default_factory=dict)
    serial_probes: List[SerialProbe] = field(default_factory=list)
    visa_classifiers: List[Tuple[Callable[[str], Optional[str]], str]] = field(default_factory=list)
    visa_probes: List[VisaSilentProbe] = field(default_factory=list)
    scanners: List[Scanner] = field(default_factory=list)
    openers: Dict[str, Callable[[Any], Any]] = field(default_factory=dict)
    on_connect: Dict[str, List[Callable[[Any, Any], None]]] = field(default_factory=dict)
    pages: List[UISpec] = field(default_factory=list)
    windows: List[UISpec] = field(default_factory=list)
    overview: List[UISpec] = field(default_factory=list)
    chain: List[ChainSpec] = field(default_factory=list)
    safe_standby: List[Tuple[str, str]] = field(default_factory=list)     # (role, what it does)
    summaries: Dict[str, Callable[[Dict[str, Any]], str]] = field(default_factory=dict)
    sim_hooks: List[Tuple[Callable[[Any], None], str]] = field(default_factory=list)
    menu_actions: List[Tuple[str, str, Callable[[Any], None], str]] = field(default_factory=list)
    references: List[RefSpec] = field(default_factory=list)

    def clear(self):
        self.__init__()

    # ---- queries ---------------------------------------------------------------------------
    def roles_for_kind(self, kind: str) -> List[str]:
        return [r for r, s in self.roles.items() if kind in s.kinds]

    def roles_with(self, capability: str) -> List[str]:
        return [r for r, s in sorted(self.roles.items(), key=lambda x: x[1].order) if capability in s.capabilities]

    def driver(self, kind: str):
        if kind not in self.drivers:
            raise KeyError(f"no add-on provides instrument kind {kind!r} (is the add-on enabled?)")
        return self.drivers[kind].get()

    def role_label(self, role: str) -> str:
        s = self.roles.get(role)
        return s.label if s else role


REGISTRY = Registry()
