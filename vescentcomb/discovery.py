"""Find every instrument, identify it, and match it to its role by serial number.

This engine knows no instruments itself: every probe, role and driver comes from an add-on
(see ``vescentcomb/docs/ADDON_GUIDE.md``). The rules it enforces for all of them:

Serial ports
    * USB VID/PID and serial number are read first — no bytes sent.
    * Bluetooth virtual ports are skipped (they can hang for seconds).
    * Each port is offered to the add-on probes whose ``match(PortInfo)`` accepts it, in
      priority order. The first probe that recognises it wins. An *exclusive* probe that
      matched but got no answer stops the others talking to that port (protects instruments
      that crash on foreign commands, like the WB-SG2 on FTDI).
GPIB / USB-TMC (VISA) — only when an add-on registered a VISA classifier or probe
    Every address on every board is re-probed each start, because adapter numbers change with
    USB plug order. ``*IDN?`` (300 ms) is classified by the add-ons' classifiers; on timeout a
    device clear, then each add-on's silent probe (``ID?`` for HP 8563E, status-byte read for the
    SWS17101 …) with a clear between them.
Other buses
    Add-on scanners (the SLICE-FPGA-II UDP broadcast, …).

Roles follow model + serial, so a moved instrument is picked up and flagged (status ``moved``).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from .core.base import Device, DeviceError
from .core import serialio, visaio
from .addonkit.registry import REGISTRY


class _RolesView:
    """Read-only, live view of the registered roles: ``ROLES[role] -> (label, kinds)``."""

    def _d(self):
        return {r: (s.label, tuple(s.kinds)) for r, s in sorted(REGISTRY.roles.items(), key=lambda x: x[1].order)}

    def __getitem__(self, k): return self._d()[k]
    def __contains__(self, k): return k in REGISTRY.roles
    def __iter__(self): return iter(self._d())
    def __len__(self): return len(REGISTRY.roles)
    def items(self): return self._d().items()
    def keys(self): return self._d().keys()
    def values(self): return self._d().values()
    def get(self, k, default=None): return self._d().get(k, default)


ROLES = _RolesView()


@dataclass
class Found:
    kind: str
    address: str
    bus: str
    model: str = ""
    serial: str = ""
    firmware: str = ""
    how: str = ""
    raw: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)
    role: str = ""
    status: str = "new"            # matched | moved | new | unknown | skipped | missing
    previous_address: str = ""

    @property
    def label(self) -> str:
        sn = f" · SN {self.serial}" if self.serial else ""
        return f"{self.model or self.kind}{sn} · {self.address}"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScanOptions:
    skip_bluetooth: bool = True
    serial: bool = True
    visa: bool = True
    serial_timeout: float = 0.5
    visa_timeout_ms: int = 300
    probe_exclusive_ports: bool = False   # let other probes talk to ports an exclusive probe claimed
    exclude: tuple = ()                   # addresses already open in this session (not re-probed)
    scanners: Dict[str, bool] = field(default_factory=dict)   # add-on scanner name -> on/off


@dataclass
class ScanResult:
    found: List[Found] = field(default_factory=list)
    skipped: List[Found] = field(default_factory=list)
    unknown: List[Found] = field(default_factory=list)
    duration_s: float = 0.0
    assignments: Dict[str, Found] = field(default_factory=dict)
    missing: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def by_kind(self, kind: str) -> List[Found]:
        return [f for f in self.found if f.kind == kind]


class Hooks:
    """Indirection points so the simulator (or tests) can stand in for hardware.

    Add-ons that need their own hook (e.g. the FPGA's UDP discovery) read it with
    ``HOOKS.get("name", default)``; the simulator sets it with ``HOOKS.set("name", fn)``."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.port_lister: Callable[[], List[serialio.PortInfo]] = serialio.list_serial_ports
        self.serial_factory: Callable[..., Any] = _real_serial
        self.resource_manager: Callable[[], Any] = visaio.resource_manager
        self.simulated = False
        self._extra: Dict[str, Any] = {}

    def get(self, name: str, default=None):
        return self._extra.get(name, default)

    def set(self, name: str, value) -> None:
        self._extra[name] = value


def _real_serial(port: str, baudrate: int = 115200, timeout: float = 1.0):
    import serial
    return serial.Serial(port=port, baudrate=baudrate, timeout=timeout)


HOOKS = Hooks()


def _ensure_addons():
    from .addonkit import ensure_loaded
    ensure_loaded()


# ------------------------------------------------------------------------------------------
# helpers add-on probes use

def with_serial(port: str, baudrate: int, timeout: float, fn):
    """Open ``port`` through the hook, run ``fn(ser)``, always close. Exceptions -> None."""
    ser = None
    try:
        ser = HOOKS.serial_factory(port, baudrate, timeout)
        return fn(ser)
    except Exception:
        return None
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass


def idn_query(port: str, eol: str, timeout: float, baudrate: int = 115200, quiet: float = 0.05) -> str:
    """``*IDN?`` on a serial port with the given line ending ('' on no reply)."""
    r = with_serial(port, baudrate, timeout,
                    lambda ser: serialio.SerialLine(ser=ser, eol=eol, quiet=quiet).query("*IDN?", timeout=timeout))
    return r or ""


def split_idn(idn: str) -> List[str]:
    s = idn.strip()
    if s.upper().startswith("*IDN "):
        s = s[5:]
    return [p.strip() for p in s.replace("\r", ",").replace("\n", ",").split(",") if p.strip()]


# ------------------------------------------------------------------------------------------
# serial

def scan_serial(opts: ScanOptions) -> Tuple[List[Found], List[Found], List[Found]]:
    found, skipped, unknown = [], [], []
    for info in HOOKS.port_lister():
        if info.device in opts.exclude:
            continue
        if opts.skip_bluetooth and info.is_bluetooth:
            skipped.append(Found("skipped", info.device, "Bluetooth", how="skipped",
                                 status="skipped", raw=info.description))
            continue
        result, claimed, tried = None, None, []
        for p in REGISTRY.serial_probes:
            try:
                if not p.match(info):
                    continue
            except Exception:
                continue
            tried.append(p.name)
            try:
                result = p.probe(info, opts)
            except Exception:
                result = None
            if result is not None:
                break
            if p.exclusive and not opts.probe_exclusive_ports:
                claimed = p.name
                break
        if result is not None and info.serial_number:
            result.extra.setdefault("usb_serial", info.serial_number)
        if result is None:
            unknown.append(Found("unknown", info.device, info.usb_family or "serial",
                                 how=(f"{claimed}: no reply (port left alone)" if claimed else
                                      ("no reply to " + ", ".join(tried) if tried else "no add-on probes this port")),
                                 status="unknown", raw=info.description))
        elif result.kind == "unknown":
            unknown.append(result)
        else:
            found.append(result)
    return found, skipped, unknown


# ------------------------------------------------------------------------------------------
# VISA

def classify_idn(idn: str) -> Optional[str]:
    for fn, _ in REGISTRY.visa_classifiers:
        try:
            k = fn(idn)
        except Exception:
            k = None
        if k:
            return k
    return None


def probe_visa_resource(rm, res: str, opts: ScanOptions) -> Found:
    bus = "GPIB" if res.upper().startswith("GPIB") else ("USB-TMC" if res.upper().startswith("USB") else "VISA")
    try:
        inst = rm.open_resource(res)
    except Exception as e:
        return Found("unknown", res, bus, how=f"open failed: {e}", status="unknown")

    def clear():
        try:
            inst.clear()
        except Exception:
            pass
    try:
        inst.timeout = opts.visa_timeout_ms
        try:
            inst.read_termination = "\n"
            inst.write_termination = "\n"
        except Exception:
            pass
        idn = None
        try:
            idn = inst.query("*IDN?").strip()
        except Exception:
            clear()
        if idn:
            kind = classify_idn(idn)
            p = split_idn(idn)
            model = p[1] if len(p) > 1 else idn
            serial = p[2] if len(p) > 2 else ""
            if kind is None:
                return Found("unknown", res, bus, model=model, serial=serial, how="*IDN?", raw=idn, status="unknown")
            if not serial and res.upper().startswith("USB") and len(res.split("::")) > 3:
                serial = res.split("::")[3]
            return Found(kind, res, bus, model=model, serial=serial, firmware=p[3] if len(p) > 3 else "",
                         how="*IDN?", raw=idn)
        tried = ["*IDN?"]
        for probe in REGISTRY.visa_probes:
            tried.append(probe.name)
            try:
                f = probe.probe(inst, res, bus, opts)
            except Exception:
                f = None
            if f is not None:
                return f
            clear()
        return Found("unknown", res, bus, how=", ".join(tried) + ": no reply", status="unknown")
    finally:
        try:
            inst.close()
        except Exception:
            pass


def scan_visa(opts: ScanOptions) -> Tuple[List[Found], List[Found]]:
    found, unknown = [], []
    if not REGISTRY.visa_classifiers and not REGISTRY.visa_probes:
        return found, unknown                       # no VISA add-ons: pyvisa not needed
    try:
        rm = HOOKS.resource_manager()
        resources = rm.list_resources("?*::INSTR")
    except Exception:
        return found, unknown
    for res in resources:
        if res.upper().startswith("ASRL") or res in opts.exclude:
            continue  # serial ports are handled by scan_serial; open ones are not re-probed
        f = probe_visa_resource(rm, res, opts)
        (found if f.kind != "unknown" else unknown).append(f)
    return found, unknown


# ------------------------------------------------------------------------------------------

def scan_all(opts: Optional[ScanOptions] = None,
             progress: Optional[Callable[[str], None]] = None,
             already_open: Optional[List[Found]] = None) -> ScanResult:
    """``already_open``: Found records of devices this session has open; they are
    listed without being probed again (an open COM port cannot be re-opened)."""
    _ensure_addons()
    opts = opts or ScanOptions()
    if already_open:
        opts.exclude = tuple(opts.exclude) + tuple(f.address for f in already_open)
    t0 = time.time()
    res = ScanResult()
    for f in already_open or []:
        f.how = "already connected"
        res.found.append(f)
    say = progress or (lambda m: None)
    if opts.serial and REGISTRY.serial_probes:
        say("Probing serial ports…")
        f, s, u = scan_serial(opts)
        res.found += f; res.skipped += s; res.unknown += u
    if opts.visa:
        say("Probing GPIB / USB-TMC…")
        f, u = scan_visa(opts)
        res.found += f; res.unknown += u
    for sc in REGISTRY.scanners:
        if not opts.scanners.get(sc.name, True):
            continue
        say(sc.label + "…")
        try:
            res.found += [f for f in (sc.scan(opts) or []) if f.address not in opts.exclude]
        except Exception as e:
            res.unknown.append(Found("unknown", sc.name, "scanner", how=f"{sc.label}: {e}", status="unknown"))
    res.duration_s = time.time() - t0
    return res


def assign_roles(result: ScanResult, saved_roles: Optional[Dict[str, Dict[str, Any]]] = None) -> ScanResult:
    """Match found devices to roles: by (kind, serial) first, then by kind."""
    saved_roles = saved_roles or {}
    taken = set()
    assignments: Dict[str, Found] = {}

    def key(f: Found):
        return id(f)

    def matches_saved(f: Found, saved: Dict[str, Any]) -> bool:
        if f.kind != saved.get("kind"):
            return False
        s_ser, f_ser = str(saved.get("serial") or ""), str(f.serial or "")
        if s_ser and f_ser and s_ser not in ("0",):
            return s_ser == f_ser
        return (saved.get("model") or "") == (f.model or "") or not s_ser

    # pass 1: exact serial matches against the saved profile
    for role, (label, kinds) in ROLES.items():
        saved = saved_roles.get(role)
        if not saved:
            continue
        for f in result.found:
            if key(f) in taken or f.kind not in kinds:
                continue
            if matches_saved(f, saved):
                f.role = role
                prev = saved.get("address", "")
                if prev and prev != f.address:
                    f.status, f.previous_address = "moved", prev
                else:
                    f.status = "matched"
                taken.add(key(f))
                assignments[role] = f
                break
        else:
            result.missing[role] = saved

    # pass 2: fill empty roles with unassigned devices of the right kind
    for role, (label, kinds) in ROLES.items():
        if role in assignments:
            continue
        for f in result.found:
            if key(f) in taken or f.kind not in kinds:
                continue
            f.role = role
            f.status = "new"
            taken.add(key(f))
            assignments[role] = f
            result.missing.pop(role, None)
            break

    for f in result.found:
        if key(f) not in taken:
            f.status = "available"
    result.assignments = assignments
    return result


def remember_roles(result: ScanResult, settings) -> None:
    for role, f in result.assignments.items():
        settings.set_role(role, f.kind, f.serial, f.model, f.address)


# ------------------------------------------------------------------------------------------
# opening

def open_found(f: Found) -> Any:
    """Open a found instrument with its add-on's opener (VISA instruments need none)."""
    _ensure_addons()
    kind = f.kind
    if kind in REGISTRY.openers:
        return REGISTRY.openers[kind](f)
    cls = REGISTRY.driver(kind)
    inst = HOOKS.resource_manager().open_resource(f.address)
    return cls(f.address, inst=inst)


def reopen(f: Found) -> Any:
    """Open ``f`` again after it dropped off the bus (auto-reconnect).

    Tries the last address first. A serial instrument whose COM port number changed after
    being unplugged is found again by its USB serial number, without probing other ports."""
    try:
        return open_found(f)
    except Exception as first:
        err = first
    usb_sn = (f.extra or {}).get("usb_serial")
    if f.bus not in ("GPIB", "USB", "TCPIP", "LAN", "VISA") and usb_sn:
        for info in HOOKS.port_lister():
            if info.serial_number == usb_sn and info.device != f.address:
                g = Found(**{**f.as_dict(), "address": info.device})
                dev = open_found(g)
                f.previous_address, f.address = f.address, info.device
                return dev
    raise err


def open_one(kind: str, serial: Optional[str] = None, opts: Optional[ScanOptions] = None):
    """Scan and open the first instrument of ``kind`` (optionally with ``serial``)."""
    opts = opts or ScanOptions()
    res = scan_all(opts)
    for f in res.found:
        if f.kind == kind and (serial is None or f.serial == serial):
            return open_found(f)
    raise DeviceError(f"no {kind} found" + (f" with serial {serial}" if serial else ""))


class Bench:
    """Connected devices by role. ``bench.opl1``, ``bench.laser`` …"""

    def __init__(self, devices: Dict[str, Any], scan: ScanResult, errors: Dict[str, str]):
        self.devices = devices
        self.scan = scan
        self.errors = errors

    def __getattr__(self, role):
        devs = self.__dict__.get("devices", {})
        if role in devs:
            return devs[role]
        if role in ROLES:
            raise DeviceError(f"role {role!r} not connected "
                              f"({self.__dict__.get('errors', {}).get(role, 'not found')})")
        raise AttributeError(role)

    def __contains__(self, role):
        return role in self.devices

    def close(self) -> None:
        """Safe state + close for every device."""
        for dev in self.devices.values():
            try:
                dev.safe_state()
            except Exception:
                pass
            try:
                dev.close()
            except Exception:
                pass
        self.devices.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def connect_all(settings=None, opts: Optional[ScanOptions] = None, roles=None,
                remember: bool = True, progress=None) -> Bench:
    """Scan, match roles (by serial, from the settings file), open everything.

    Loads the add-ons enabled in the settings file first (installing their requirements on
    first use), so scripts get every instrument the GUI would."""
    if settings is None:
        from .settings import Settings
        settings = Settings()
    from .addonkit import ensure_loaded
    ensure_loaded(settings)
    res = assign_roles(scan_all(opts, progress), settings.get("roles", {}))
    devices, errors = {}, {}
    for role, f in res.assignments.items():
        if roles and role not in roles:
            continue
        try:
            devices[role] = open_found(f)
        except Exception as e:
            errors[role] = str(e)
    if remember:
        remember_roles(res, settings)
    return Bench(devices, res, errors)
