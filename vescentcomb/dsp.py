"""Signal metrics shared by the beat check, auto-tune and frequency monitor."""
from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

import numpy as np


def peak_frequency_fft(v: np.ndarray, dt: float, fmin: float = 0.0,
                       fmax: Optional[float] = None) -> float:
    """Dominant frequency: Hann window + parabolic interpolation (from the notebook)."""
    n = len(v)
    x = (v - np.mean(v)) * np.hanning(n)
    s = np.abs(np.fft.rfft(x))
    f = np.fft.rfftfreq(n, dt)
    m = (f > max(fmin, 0)) & (f <= (fmax if fmax else f[-1]))
    if not m.any():
        return 0.0
    idx = np.where(m)[0]
    k = idx[int(np.argmax(s[idx]))]
    if 1 <= k < len(s) - 1:
        a, b, c = s[k - 1], s[k], s[k + 1]
        den = a - 2 * b + c
        d = 0.5 * (a - c) / den if den != 0 else 0.0
        return float(f[k] + d * (f[1] - f[0]))
    return float(f[k])


# ---- Ransom-kernel quick look (ported from the long-term monitor notebook) -----------------
_QL_M = 128


def _kern(x):
    s = np.sinc(x)
    with np.errstate(divide="ignore", invalid="ignore"):
        ds = np.where(x == 0, 0.0, (np.cos(np.pi * x) - s) / x)
    e = np.exp(-1j * np.pi * x)
    return e * s, e * (ds - 1j * np.pi * s)


def _A(F, r, kc, deriv=False):
    r = np.atleast_1d(np.asarray(r, float))
    ks = int(kc) + np.arange(-(_QL_M // 2), _QL_M // 2 + 1)
    kk, dk = _kern(r[:, None] - ks[None, :])
    Fk = F[ks]
    a = (Fk * kk).sum(1)
    return (a, (Fk * dk).sum(1)) if deriv else a


def quicklook(v: np.ndarray, dt: float, expected_hz: float, search_hz: float = 1e6):
    """Sub-bin frequency estimate. Returns (f_hz, sigma_f_hz, snr_db)."""
    from scipy.optimize import brentq
    N = len(v)
    df = 1.0 / (N * dt)
    F = np.fft.rfft(v - v.mean())
    P = np.abs(F) ** 2
    lo = max(int((expected_hz - search_hz) / df), _QL_M)
    hi = min(int((expected_hz + search_hz) / df), len(F) - _QL_M - 2)
    if hi <= lo:
        raise ValueError("search window empty — record too short for this carrier")
    kc = lo + int(np.argmax(P[lo:hi + 1]))
    rg = kc + np.arange(-1, 1 + 1e-12, 1 / 64)
    i = int(np.clip(np.argmax(np.abs(_A(F, rg, kc)) ** 2), 1, len(rg) - 2))

    def dP(r):
        a, d = _A(F, r, kc, True)
        return 2 * np.real(np.conj(a[0]) * d[0])

    a, b = rg[i - 1], rg[i + 1]
    r_hat = brentq(dP, a, b, xtol=1e-10) if dP(a) > 0 > dP(b) else rg[i]
    kn = np.arange(max(1, kc - 2000), min(len(F) - 1, kc + 2001))
    kn = kn[np.abs(kn - kc) > 5]
    pn = np.median(P[kn]) / np.log(2)
    pm = np.abs(_A(F, r_hat, kc)[0]) ** 2 / pn
    return float(r_hat * df), float((3.0 / (np.pi * np.sqrt(6 * pm))) / (N * dt)), float(10 * np.log10(pm))


# ---- phase-noise style metrics ---------------------------------------------------------------
def residual_phase(v: np.ndarray, dt: float, f0: Optional[float] = None,
                   lp_hz: Optional[float] = None) -> np.ndarray:
    """Demodulate at f0 and return the detrended, unwrapped phase (rad)."""
    if f0 is None:
        f0 = peak_frequency_fft(v, dt)
    n = len(v)
    t = np.arange(n) * dt
    z = (v - v.mean()) * np.exp(-2j * np.pi * f0 * t)
    Z = np.fft.fft(z)
    f = np.fft.fftfreq(n, dt)
    lp = lp_hz if lp_hz else min(f0 / 2, 0.25 / dt)
    Z[np.abs(f) > lp] = 0
    ph = np.unwrap(np.angle(np.fft.ifft(Z)))
    tt = np.arange(n)
    ph = ph - np.polyval(np.polyfit(tt, ph, 1), tt)
    return ph


def integrated_phase_rms(v: np.ndarray, dt: float, f0: Optional[float] = None,
                         band: Tuple[float, float] = (10.0, 1e6)) -> float:
    """RMS residual phase (rad) integrated over ``band`` (lower is better)."""
    ph = residual_phase(v, dt, f0)
    n = len(ph)
    S = np.fft.rfft(ph * np.hanning(n))
    f = np.fft.rfftfreq(n, dt)
    m = (f >= band[0]) & (f <= band[1])
    if not m.any():
        return float(np.std(ph))
    # Parseval with the Hann power correction (mean(w^2) = 3/8)
    p = (np.abs(S[m]) ** 2).sum() * 2 / (n ** 2 * 0.375)
    return float(np.sqrt(p))


def carrier_to_pedestal_db(f: np.ndarray, p_dbm: np.ndarray, f0: float,
                           exclude_hz: float, pedestal_hz: float) -> float:
    """Carrier minus median pedestal level within ±pedestal_hz (higher is better)."""
    near = np.abs(f - f0) <= exclude_hz
    carrier = float(np.max(p_dbm[near])) if near.any() else float(np.max(p_dbm))
    ped = (np.abs(f - f0) > exclude_hz) & (np.abs(f - f0) <= pedestal_hz)
    pedestal = float(np.median(p_dbm[ped])) if ped.any() else float(np.median(p_dbm))
    return carrier - pedestal


def servo_bump_db(f: np.ndarray, p_dbm: np.ndarray, f0: float, inner_hz: float = 10e3,
                  outer_hz: float = 1e6) -> float:
    """Highest point in the servo-bump annulus relative to the carrier (lower is better)."""
    near = np.abs(f - f0) <= inner_hz
    carrier = float(np.max(p_dbm[near])) if near.any() else float(np.max(p_dbm))
    ann = (np.abs(f - f0) > inner_hz) & (np.abs(f - f0) <= outer_hz)
    if not ann.any():
        return float("nan")
    return float(np.max(p_dbm[ann]) - carrier)


def overlapping_adev(y_frac: Sequence[float], tau0: float, ms: Iterable[int] = (1, 2, 4, 8, 16)):
    """Overlapping Allan deviation of fractional-frequency samples."""
    y = np.asarray(y_frac, float)
    x = np.concatenate(([0.0], np.cumsum(y) * tau0))
    out = []
    for m in ms:
        if len(x) < 2 * m + 1:
            break
        d = x[2 * m:] - 2 * x[m:-m] + x[:-2 * m]
        out.append((m * tau0, float(np.sqrt(np.mean(d ** 2) / (2 * (m * tau0) ** 2)))))
    return out


# ---- PC-side FFT for scope captures ----------------------------------------------------------------
_WINDOWS = {
    "hann": np.hanning,
    "rect": np.ones,
    "blackman": np.blackman,
    "flattop": lambda n: (0.21557895 - 0.41663158 * np.cos(2 * np.pi * np.arange(n) / (n - 1))
                          + 0.277263158 * np.cos(4 * np.pi * np.arange(n) / (n - 1))
                          - 0.083578947 * np.cos(6 * np.pi * np.arange(n) / (n - 1))
                          + 0.006947368 * np.cos(8 * np.pi * np.arange(n) / (n - 1))),
}
FFT_WINDOWS = ("hann", "blackman", "flattop", "rect")
FFT_UNITS = ("dBV", "dBm", "Vrms")


def amplitude_spectrum(v: np.ndarray, dt: float, window: str = "hann", unit: str = "dBV",
                       impedance: float = 50.0):
    """Single-sided amplitude spectrum of a real record.

    A sine of peak amplitude A reads A/√2 V rms at its bin (coherent gain corrected).
    ``unit``: "Vrms", "dBV" (dB re 1 V rms) or "dBm" (power into ``impedance``).
    Returns (f_Hz, values)."""
    v = np.asarray(v, float)
    n = len(v)
    if n < 4:
        return np.array([]), np.array([])
    w = _WINDOWS.get(window, np.hanning)(n)
    spec = np.fft.rfft((v - v.mean()) * w)
    vrms = np.abs(spec) * 2.0 / w.sum() / np.sqrt(2.0)
    vrms[0] /= 2.0
    f = np.fft.rfftfreq(n, dt)
    if unit == "Vrms":
        return f, vrms
    if unit == "dBm":
        return f, 10 * np.log10(np.maximum(vrms ** 2 / impedance, 1e-30) / 1e-3)
    return f, 20 * np.log10(np.maximum(vrms, 1e-15))
