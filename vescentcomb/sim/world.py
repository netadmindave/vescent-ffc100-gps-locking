"""The simulated bench. The shell provides an empty world; each add-on's ``sim.py`` fills it.

    world.add_serial(PortInfo(...), handler, terminator=b"\r", expected_baud=115200)
    world.add_visa("GPIB0::18::INSTR", model)
    world.add_rf_line(lambda: [(100e6, -20.0)])        # lines the simulated spectrum analyzer sees
    world.models["fgen"] = model                       # share a model with other add-ons' sims
    world.on_uninstall(fn)

Physics couplings between add-ons go through ``world.models`` and the overridable methods
below, so any subset of add-ons can be simulated.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from ..core import visaio
from ..core.serialio import PortInfo
from .. import discovery
from .base import SilentModel
from .fakeio import FakeResourceManager, FakeSerial

_WORLD: Optional["World"] = None


class World:
    def __init__(self, speed: float = 1.0, cavity_tau_s: float = 3.0):
        self.speed = speed
        self.cavity_tau_s = cavity_tau_s
        self._ports: List[PortInfo] = []
        self._serial: Dict[str, Tuple] = {}
        self.visa_models: Dict[str, object] = {"GPIB0::1::INSTR": SilentModel()}
        self._rf: List[Callable[[], List[Tuple[float, float]]]] = []
        self._cleanup: List[Callable[[], None]] = []
        self.models: Dict[str, object] = {}
        # two Bluetooth ports, so the "skip Bluetooth" path is always exercised
        for n in (5, 6):
            self._ports.append(PortInfo(f"COM{n}", f"Standard Serial over Bluetooth link (COM{n})",
                                        "BTHENUM\\{00%d}" % n, None, None, ""))

    # ---- what add-ons call ---------------------------------------------------------------------
    def add_serial(self, info: PortInfo, handler, terminator: bytes = b"\r", expected_baud: int = 115200,
                   strip_lf: bool = True) -> None:
        self._ports.append(info)
        self._serial[info.device] = (handler, terminator, expected_baud, strip_lf)

    def add_visa(self, resource: str, model) -> None:
        self.visa_models[resource] = model

    def add_rf_line(self, fn: Callable[[], List[Tuple[float, float]]]) -> None:
        self._rf.append(fn)

    def on_uninstall(self, fn: Callable[[], None]) -> None:
        self._cleanup.append(fn)

    # ---- couplings (overridden by add-on sims; safe defaults) ---------------------------------------
    def rf_lines(self) -> List[Tuple[float, float]]:
        out: List[Tuple[float, float]] = []
        for fn in self._rf:
            try:
                out += list(fn())
            except Exception:
                pass
        return out

    def beat_offset_hz(self, opl) -> float:
        return 1.8e6

    def beat_phase_rms(self) -> float:
        return 0.05

    def pzt_out(self) -> float:
        return 0.0

    # ---- plumbing ------------------------------------------------------------------------------------
    def ports(self) -> List[PortInfo]:
        return list(self._ports)

    def serial_factory(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        if port not in self._serial:
            raise OSError(f"could not open port {port}")
        handler, term, baud, strip = self._serial[port]
        return FakeSerial(port, handler, term, baudrate, timeout, expected_baud=baud, strip_lf=strip)


def install(speed: float = 1.0, cavity_tau_s: float = 3.0, settings=None) -> World:
    """Route discovery and drivers to a simulated bench built by the loaded add-ons."""
    global _WORLD
    from ..addonkit import REGISTRY, ensure_loaded
    if _WORLD is not None:
        uninstall()
    ensure_loaded(settings)
    _WORLD = World(speed, cavity_tau_s)
    h = discovery.HOOKS
    h.port_lister = _WORLD.ports
    h.serial_factory = _WORLD.serial_factory
    rm = FakeResourceManager(_WORLD.visa_models)
    h.resource_manager = lambda: rm
    visaio.set_resource_manager(rm)
    h.simulated = True
    for fn, addon in REGISTRY.sim_hooks:
        try:
            fn(_WORLD)
        except Exception as e:  # one broken sim must not stop the others
            import traceback
            print(f"[sim] {addon}: {e}\n{traceback.format_exc(limit=4)}")
    return _WORLD


def uninstall() -> None:
    global _WORLD
    if _WORLD is not None:
        for fn in _WORLD._cleanup:
            try:
                fn()
            except Exception:
                pass
    discovery.HOOKS.reset()
    visaio.set_resource_manager(None)
    _WORLD = None


def get_world() -> Optional[World]:
    return _WORLD
