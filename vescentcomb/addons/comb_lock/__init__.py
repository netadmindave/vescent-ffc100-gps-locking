"""Comb lock module — FFC-100, comb OPL (#1, f_rep → GPS), SLICE-FPGA-II and the GPS lock process.

Scripting::

    import vescentcomb
    comb = vescentcomb.addon("comb_lock")
    with comb.FFC100.find() as ffc:
        print(ffc.cav_temp())
"""
from __future__ import annotations

import re

from .ffc100 import FFC100
from .sliceopl import SliceOPL
from .slicefpga import SliceFPGA, discover as discover_fpga
from .gps_lock import LockParams, LockSequence
from .autotune import AutoTuner, TuneConfig

SECTION = "COMB LOCK"


# ---- discovery ---------------------------------------------------------------------------------
def _vescent_port(info) -> bool:
    """Any USB-serial port except FTDI (the WB-SG2 owns those). The Vescent boxes enumerate differently
    on different PCs, so the VID is not relied on."""
    return info.usb_family != "ftdi"


def _classify(reply: str):
    u = reply.upper()
    if "OPL" in u:
        return "sliceopl"
    if "FFC" in u or "COMB" in u:
        return "ffc100"
    return None


def _probe_vescent(info, opts):
    """*IDN? with CR (SLICE-OPL), then CR LF (FFC-100).

    Like the original ffc100.py: open, wait for the box to settle (opening the port can reset its
    MCU), flush, then ask with a 1.5 s reply window."""
    import time
    from vescentcomb.discovery import Found, split_idn, with_serial
    from vescentcomb.core.serialio import SerialLine
    timeout = max(opts.serial_timeout, 1.5)

    def ask(ser, eol):
        time.sleep(0.3)
        ser.reset_input_buffer()
        return SerialLine(ser=ser, eol=eol, quiet=0.05).query("*IDN?", timeout=timeout)

    for eol, how in (("\r", "*IDN? (CR)"), ("\r\n", "*IDN? (CR LF)")):
        reply = with_serial(info.device, 115200, timeout, lambda s, e=eol: ask(s, e)) or ""
        kind = _classify(reply)
        if kind is None and "VESCENT" in reply.upper():
            kind = "sliceopl" if eol == "\r" else "ffc100"
        if kind:
            p = split_idn(reply)
            return Found(kind, info.device, "USB serial", model=p[1] if len(p) > 1 else kind,
                         serial=p[2] if len(p) > 2 else info.serial_number,
                         firmware=" / ".join(p[3:5]) if len(p) > 3 else "", how=how, raw=reply,
                         extra={"usb_serial": info.serial_number})
    return None


def _scan_fpga(opts):
    from vescentcomb.discovery import HOOKS, Found
    found = HOOKS.get("slicefpga.discover", discover_fpga)() or []
    return [Found("slicefpga", u["host"], "Ethernet", model="SLICE-FPGA-II", serial=u.get("mac", ""),
                  how="UDP 1952 → 1953") for u in found]


def _open_fpga(found):
    from vescentcomb.discovery import HOOKS
    factory = HOOKS.get("slicefpga.impl_factory")
    return SliceFPGA(found.address, impl=factory(found.address) if factory else None, mac=found.serial)


# ---- lock-chain pills (pure Python, called with each poll) ---------------------------------------
def _beat_err(d, settings):
    b, t = d.get("beatnote"), d.get("target_beatnote")
    off = settings.get("ui.lock.counter_offset_hz", 31.0)
    return (t - off / 1e6 - b) * 1e6 if isinstance(b, float) and isinstance(t, float) and b > 1 else None


def _pill_gps(d, settings):
    ref = d.get("reference")
    ok = isinstance(ref, float) and abs(ref - 10.0) < 0.01
    return ("ref OK", "ok") if ok else ("no ref", "bad")


def _pill_frep(d, settings):
    err = _beat_err(d, settings)
    win = settings.get("ui.lock.window_hz", 8.0)
    if d.get("servo_on") and err is not None and abs(err) < 10 * win:
        return "locked", "ok"
    return ("servo on · off target", "warn") if d.get("servo_on") else ("servo off", "idle")


def _pill_ffc(d, settings):
    return ("mode-locked", "ok") if d.get("mode_locked") else ("not mode-locked", "bad")


def _pill_ceo(d, settings):
    return ("locked", "ok") if d.get("ceo_locked") else ("open", "warn")


# ---- registration --------------------------------------------------------------------------------
def register(api):
    api.add_device("ffc100", FFC100, "Vescent FFC-100")
    api.add_device("sliceopl", SliceOPL, "Vescent SLICE-OPL")
    api.add_device("slicefpga", SliceFPGA, "Vescent SLICE-FPGA-II")

    api.add_role("ffc", "FFC-100 comb", ["ffc100"], order=10)
    api.add_role("fpga", "SLICE-FPGA-II", ["slicefpga"], order=11)
    api.add_role("opl1", "OPL #1 · f_rep → GPS", ["sliceopl"], capabilities=("opl",), order=12)

    api.add_serial_probe("Vescent *IDN?", _vescent_port, _probe_vescent, priority=60)
    api.add_scanner("slicefpga", "SLICE-FPGA-II UDP discovery (port 1952)", _scan_fpga)
    api.add_opener("ffc100", api.serial_opener(FFC100, 115200, 2.0))
    api.add_opener("sliceopl", api.serial_opener(SliceOPL, 115200, 1.0))
    api.add_opener("slicefpga", _open_fpga)

    api.add_page("combseq", "Comb lock sequence", "pages.lock_sequence:LockSequencePage", section=SECTION, order=10)
    api.add_page("ffc", "FFC-100 comb", "pages.ffc:FFCPage", role="ffc", section=SECTION, order=11)
    api.add_page("fpga", "SLICE-FPGA-II", "pages.fpga:FPGAPage", role="fpga", section=SECTION, order=12)
    api.add_page("opl1", "SLICE-OPL #1 · GPS", "pages.opl:OPLPage", role="opl1", section=SECTION, order=13)

    api.add_overview_panel("ffc", "overview:FFCCard", order=10)
    api.add_overview_panel("fpga", "overview:FPGACard", order=11)
    api.add_overview_panel("opl1", "overview:OPL1Card", order=12)
    api.add_overview_panel("comb_trends", "overview:CombTrends", span="wide", order=50)

    api.add_chain_pill("gps", "GPS 10 MHz", "opl1", _pill_gps, order=10)
    api.add_chain_pill("ffc", "FFC-100", "ffc", _pill_ffc, order=11)
    api.add_chain_pill("ceo", "f_ceo · FPGA", "fpga", _pill_ceo, order=12)
    api.add_chain_pill("frep", "f_rep → GPS · OPL #1", "opl1", _pill_frep, order=13)

    api.add_reference("opl1", "REF IN (GPS 10 MHz)", "always", status=_ref_ok,
                      detail=lambda d: f"READREF? {_ref_text(d)}", note="reference measured by the OPL")
    api.add_reference("fpga", "external clock (20 MHz from GPS)", "status",
                      status=lambda d: (d.get("clock_source") == "external") if d.get("clock_source") else None,
                      detail=lambda d: f"clock {str(d.get('clock_source') or '?')}"
                                       + (f" · {d['ext_clk_hz'] / 1e6:.6f} MHz" if isinstance(d.get("ext_clk_hz"),
                                                                                             (int, float)) else ""))
    api.add_sim("sim:install")


def _ref_ok(d):
    r = d.get("reference")
    return None if not isinstance(r, (int, float)) else abs(r - 10.0) < 0.01


def _ref_text(d):
    from vescentcomb.core.units import eng
    r = d.get("reference")
    return eng(r * 1e6, "Hz", 9) if isinstance(r, (int, float)) else "—"
