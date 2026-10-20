"""Small unit helpers shared by drivers and the GUI."""
from __future__ import annotations

import math

C_LIGHT = 299_792_458.0  # m/s


def nm_to_thz(nm: float) -> float:
    return C_LIGHT / (nm * 1e-9) / 1e12


def thz_to_nm(thz: float) -> float:
    return C_LIGHT / (thz * 1e12) / 1e-9


def dbm_to_w(dbm: float) -> float:
    return 10 ** (dbm / 10.0) * 1e-3


def w_to_dbm(w: float) -> float:
    return 10.0 * math.log10(max(w, 1e-30) / 1e-3)


def eng(value: float, unit: str = "", digits: int = 4) -> str:
    """Engineering notation in powers of three: eng(2.5e7,'Hz') -> '25 MHz'."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if value == 0:
        return f"0 {unit}".strip()
    prefixes = {-15: "f", -12: "p", -9: "n", -6: "µ", -3: "m", 0: "", 3: "k",
                6: "M", 9: "G", 12: "T"}
    exp = int(math.floor(math.log10(abs(value)) / 3) * 3)
    exp = max(-15, min(12, exp))
    scaled = value / 10 ** exp
    return f"{scaled:.{digits}g} {prefixes[exp]}{unit}".strip()


def snap_125(val: float) -> float:
    """Nearest value on the 1-2-5 sequence."""
    exp = math.floor(math.log10(val))
    best = None
    for m in (1, 2, 5):
        for e in (exp - 1, exp, exp + 1):
            c = m * 10 ** e
            if best is None or abs(c - val) < abs(best - val):
                best = c
    return best


def first_125_below(val: float) -> float:
    """Largest 1-2-5 step strictly below val."""
    exp = math.floor(math.log10(val))
    for m in (5, 2, 1):
        c = m * 10 ** exp
        if c < val:
            return c
    return 5 * 10 ** (exp - 1)


def seq_125(lo: float, hi: float):
    """Every 1-2-5 value from lo to hi inclusive (scope V/div and s/div steps)."""
    out = []
    e = math.floor(math.log10(lo)) - 1
    while True:
        for m in (1, 2, 5):
            v = round(m * 10 ** e, 15)
            if v > hi * (1 + 1e-9):
                return out
            if v >= lo * (1 - 1e-9):
                out.append(v)
        e += 1


def ceil_125(val: float) -> float:
    """Smallest 1-2-5 value ≥ val."""
    exp = math.floor(math.log10(val))
    for e in (exp, exp + 1):
        for m in (1, 2, 5):
            c = m * 10 ** e
            if c >= val * (1 - 1e-9):
                return c
    return 10 ** (exp + 1)


def snap_to_grid(value: float, step: float, origin: float = 0.0) -> float:
    """Nearest multiple of ``step`` (rounding up or down, whichever is closer)."""
    if not step:
        return value
    n = round((value - origin) / step)
    digits = max(0, -int(math.floor(math.log10(step))) + 3)
    return round(origin + n * step, digits)
