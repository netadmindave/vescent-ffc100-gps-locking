"""
High-level, GUI-free control of the Vescent SLICE-FPGA-II.

This replaces the PyQt GUI (XEM_GUI3.py and its windows). Each method below is a port of the
GUI's own logic, so it writes the same register values:

    GUI action                               ->  SliceFPGA method
    -------------------------------------------------------------------------
    "Push default values to Red Pitaya"      ->  push_config()
    Settings tab, External clock + target    ->  set_clock(external=True, f_ext=20e6)
    CEO Lock tab, "Lock" checkbox on / off   ->  lock('ceo') / unlock('ceo')
    Optical Lock tab, "Lock" on / off        ->  lock('optical') / unlock('optical')
    "Connect with its current settings"      ->  attach()   (reads the box state, writes nothing)
    Counters tab                              ->  read_counters(), Monitor (monitor.py)

Channel 0 = 'ceo' (ADC0 -> DDC0 -> PLL0 -> DAC0)
Channel 1 = 'optical' (ADC1 -> DDC1 -> PLL1 -> DAC1 fast, integrators -> DAC2 slow)
"""
from __future__ import annotations

import copy
import logging
import math
import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .superlaserland import SuperLaserLand_JD_RP
from .rp_pll import CommsError

log = logging.getLogger(__name__)

PKG_DIR = Path(__file__).resolve().parent
CONFIG_DIR = PKG_DIR / 'configs'
DEFAULT_CONFIG = CONFIG_DIR / 'UCF_FFC-100_Parameters.xml'
CHANNELS = {'ceo': 0, 'optical': 1, 0: 0, 1: 1}


def _ch(channel) -> int:
    try:
        return CHANNELS[channel]
    except KeyError:
        raise ValueError("channel must be 'ceo'/0 or 'optical'/1") from None


# ----------------------------------------------------------------------------- configuration
class SliceConfig:
    """The Vescent XML parameter file (e.g. UCF_FFC-100_Parameters.xml), editable in Python."""

    def __init__(self, path: str | os.PathLike = DEFAULT_CONFIG):
        self.path = Path(path)
        self.tree = ET.parse(self.path)

    def get(self, section: str, key: str) -> str:
        el = self.tree.find(section)
        if el is None or key not in el.attrib:
            raise KeyError(f'{section}/{key} not in {self.path.name}')
        return el.attrib[key]

    def getf(self, section, key) -> float:
        return float(self.get(section, key))

    def getb(self, section, key) -> bool:
        return self.get(section, key).strip().lower() == 'true'

    def set(self, section: str, key: str, value):
        el = self.tree.find(section)
        if el is None:
            el = ET.SubElement(self.tree.getroot(), section)
        el.attrib[key] = value if isinstance(value, str) else repr(value) if isinstance(value, float) else str(value)

    def save(self, path: str | os.PathLike):
        self.tree.write(path)

    def copy(self) -> 'SliceConfig':
        c = copy.copy(self)
        c.tree = copy.deepcopy(self.tree)
        return c

    def as_dict(self) -> dict:
        return {el.tag: dict(el.attrib) for el in self.tree.getroot()}


# ----------------------------------------------------------------------------- clock synthesis
def pll_multipliers(f_ext: float, f_adc: float = 125e6, vco_limits=(600e6, 1600e6)):
    """Port of ConfigurationRPSettingsUI.getPLLmultipliers (same search, no printing).

    Returns (CLKFBOUT_MULT, CLKOUT0_DIVIDE, CLKOUT1_DIVIDE).  20 MHz -> (50, 8, 100): fs = 125 MHz exactly.
    """
    fref = 10e6
    best = [0, 0, 0]
    last_error = float('inf')
    mult = 1
    while mult < 64:
        mult += 1
        fmult = f_ext * mult
        d0 = round(f_ext * mult / f_adc)
        for n in [d for d in (d0 - 1, d0, d0 + 1) if d != 0]:
            fdiv = fmult / n
            ref10_divide = min(round(fmult / fref), 128)
            err = abs(f_adc - fdiv) + 0.01 * abs(fref - fmult / ref10_divide)
            if last_error > err and vco_limits[0] <= fmult <= vco_limits[1] and (f_adc - fdiv) >= 0:
                last_error = err
                best = [mult, n, ref10_divide]
    return tuple(best)


@dataclass
class LoopGains:
    P: float
    I: float
    II: float
    D: float
    coef_d: float
    lock: int


# ----------------------------------------------------------------------------- main class
class SliceFPGA:
    """One SLICE-FPGA-II box.

    >>> fpga = SliceFPGA('192.168.0.150')        # connects, nothing written
    >>> fpga.push_config(clock=('external', 20e6))
    >>> fpga.lock('ceo')
    """

    DEFAULT_IP = '192.168.0.150'
    SLIDER_FULL_SCALE = 1e6     # the GUI's DAC-offset slider units (0 = low limit, 1e6 = high limit)

    def __init__(self, host: str = DEFAULT_IP, port: int = 5000, config: str | os.PathLike | SliceConfig | None = None,
                 connect: bool = True, timeout: float = 2.0):
        self.host, self.port = host, port
        self.config = config if isinstance(config, SliceConfig) else SliceConfig(config or DEFAULT_CONFIG)
        self.sl = SuperLaserLand_JD_RP()
        self.sl.dev.timeout = timeout
        self.sl.openDevice()                      # builds the PLL sub-modules (no I/O)
        self.io = self.sl.dev.lock                # RLock shared with the transport
        # GUI state that is not stored in the FPGA
        self.vco_sign = {0: +1, 1: +1}            # GUI default "VCO sign +"  -> negative DDC reference
        self.slider = {0: 0, 1: 0, 2: 0}          # DAC offset in slider units (int, like the QSlider)
        self.kc = {0: 1.0, 1: 1.0, 2: 1.0}        # open-loop gain, counts/counts
        self.optical_mode = 'off'
        self.f_ext = None
        self.events = []                          # (time, message) log of actions
        if connect:
            self.connect()

    # ------------------------------------------------------------------ connection
    def connect(self):
        self.sl.dev.OpenTCPConnection(self.host, self.port)
        self._event(f'connected to {self.host}:{self.port}')

    def close(self):
        """Drop the TCP connection. Nothing is written: the FPGA keeps running (and locked) on its own."""
        self.sl.dev.CloseTCPConnection()
        self._event('disconnected')

    disconnect = close

    @property
    def connected(self) -> bool:
        return bool(self.sl.dev.valid_socket)

    def reconnect(self, attempts: int = 5, delay: float = 2.0) -> bool:
        for k in range(attempts):
            try:
                self.connect()
                return True
            except CommsError as e:
                log.warning('reconnect %d/%d failed: %s', k + 1, attempts, e)
                time.sleep(delay)
        return False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _event(self, msg):
        self.events.append((time.time(), msg))
        log.info(msg)

    # ------------------------------------------------------------------ helpers mirroring GUI widgets
    def _vco_gain_hz_per_v(self, dac: int) -> float:
        try:
            return float(self.config.get('VCO_gain', f'DAC{dac}'))
        except Exception:
            return 1e9

    def _compute_kc(self, dac: int) -> float:
        """XEM_GUI_MainWindow.setVCOGain_event: VCO gain in DAC counts -> DDC counts."""
        return self._vco_gain_hz_per_v(dac) * self.sl.getFreqDiscriminatorGain() * self.sl.getDACGainInVoltsPerCounts(dac)

    def _loop_settings(self, ch: int):
        """LoopFiltersUI.loadParameters + getSettings, including the GUI's text-box rounding."""
        s = f'PLL{ch}_settings'
        c = self.config
        kp = float('{:.3}'.format(c.getf(s, 'kp')))
        fi, fii, fd, fdf = (float('{:.3e}'.format(c.getf(s, k))) for k in ('fi', 'fii', 'fd', 'fdf'))
        bKp, bKd, bCross = c.getb(s, 'chkKp'), c.getb(s, 'chkKd'), c.getb(s, 'chkKpCrossing')
        return kp, fi, fii, fd, fdf, bKp, bKd, bCross

    def loop_gains(self, channel, lock: bool, kc: float | None = None) -> LoopGains:
        """LoopFiltersUI.getActualControllerDesign (gains normalised to the open-loop gain kc)."""
        ch = _ch(channel)
        kc = self.kc[ch] if kc is None else kc
        kp, fi, fii, fd, fdf, bKp, bKd, bCross = self._loop_settings(ch)
        if not bKp:
            kp = -120
        fs = self.sl.fs
        g = 10 ** (kp / 20) / kc
        base = g if bCross else 1 / kc
        P = g
        I = base * fi * (2 * np.pi / fs)
        II = base * fi * fii * (2 * np.pi / fs) ** 2
        D = 0.0 if fd == 0.0 else base * fs / (2 * np.pi * fd)
        coef = (2 * np.pi * fdf) / fs
        if not bKp:
            P = 0
        if not bKd:
            D = 0
        return LoopGains(P, I, II, D, coef, int(bool(lock)))

    def _write_loop(self, ch: int, lock: bool, kc=None):
        g = self.loop_gains(ch, lock, kc)
        self.sl.pll[ch].set_pll_settings(self.sl, g.P, g.I, g.II, g.D, g.coef_d, g.lock)
        return g

    def _slider_from_volts(self, dac: int, volts: float) -> int:
        lo = self.config.getf('Output_limits_low', f'DAC{dac}')
        hi = self.config.getf('Output_limits_high', f'DAC{dac}')
        return int((volts - lo) / (hi - lo) * self.SLIDER_FULL_SCALE)

    def _offset_counts(self, dac: int, slider: int) -> int:
        """SpectrumWidget.setDACOffset_event: slider units -> offset register counts (with op-amp inversion)."""
        lo, hi = self.sl.DACs_limit_low[dac], self.sl.DACs_limit_high[dac]
        counts = int(lo + float(hi - lo) * float(slider) / self.SLIDER_FULL_SCALE)
        if dac in (0, 1):
            counts = -counts
        else:
            counts = 65535 - counts
        return counts

    def _apply_slider(self, dac: int, slider: float):
        self.slider[dac] = int(slider)                     # QSlider.setValue truncates
        self.sl.set_dac_offset(dac, self._offset_counts(dac, self.slider[dac]))

    def _channel_dacs(self, ch: int):
        return (0,) if ch == 0 else (1, 2)

    def _set_ref_freq(self, ch: int):
        f = float(self.config.get('Reference_frequency', f'DDC{ch}'))
        if self.vco_sign[ch] > 0:
            f = -f
        (self.sl.set_ddc0_ref_freq if ch == 0 else self.sl.set_ddc1_ref_freq)(f)

    def _integrators(self, mode: str):
        """LoopFiltersUI_DAC1_and_DAC2.setIntegratorGainEvent (slow DAC2 path of the optical lock)."""
        c = self.config
        flip1, flip2 = int(c.getb('PLL2_settings', 'flip_acquisition')), int(c.getb('PLL2_settings', 'flip_lock'))
        g1, g2 = int(c.get('PLL2_settings', 'AcqGain')), int(c.get('PLL2_settings', 'LockGain'))
        lock1, lock2, hold1, hold2 = {'off': (0, 0, 0, 0), 'slow': (1, 1, 0, 1),
                                      'fast': (1, 1, 1, 1), 'both': (1, 1, 1, 0)}[mode]
        self.sl.set_integrator_settings(1, hold1, flip1, lock1, g1)
        self.sl.set_integrator_settings(2, hold2, flip2, lock2, g2)
        self.optical_mode = mode

    # ------------------------------------------------------------------ push configuration
    def push_config(self, clock='config', slow_start_hv: bool = True):
        """Equivalent of the GUI's "Push default values to Red Pitaya" for the loaded XML config.

        clock: 'config'  -> use Clock_select from the XML (UCF file: internal)
               ('external', 20e6) or 'external' -> then switch to the external clock (20 MHz default)
               'internal'
        Locks are left as the XML's chkLock says (False in the UCF file).
        """
        c = self.config
        with self.io:
            self.sl.resetFrontend()
            # SLLSystemParameters.sendToFPGA
            for k in range(3):
                lo, hi = c.getf('Output_limits_low', f'DAC{k}'), c.getf('Output_limits_high', f'DAC{k}')
                self.sl.set_dac_limits(k, self.sl.convertDACVoltsToCounts(k, lo), self.sl.convertDACVoltsToCounts(k, hi))
            std, lev, dflt = c.getf('PWM0_settings', 'standard'), int(c.get('PWM0_settings', 'levels')), c.getf('PWM0_settings', 'default')
            self.sl.set_pwm_settings(lev, self.sl.convertPWMVoltsToCounts(std, lev, dflt), True)

            # main windows: optical first, then CEO (same order as the GUI)
            for ch in (1, 0):
                for dac in self._channel_dacs(ch):
                    self.kc[dac] = self._compute_kc(dac)
                    self.slider[dac] = self._slider_from_volts(dac, c.getf('Output_offset_in_volts', f'DAC{dac}'))
                xml_lock = c.getb(f'PLL{ch}_settings', 'chkLock')
                if ch == 1:
                    mode = {0: 'off', 1: 'slow', 2: 'fast', 3: 'both'}[int(c.get('PLL2_settings', 'LoopFilter'))]
                    self._integrators(mode)
                self._set_ref_freq(ch)
                self._write_loop(ch, xml_lock)
                for dac in self._channel_dacs(ch):
                    self.sl.save_openLoop_gain(dac, self.kc[dac])
                for dac in self._channel_dacs(ch):
                    self.sl.set_dac_offset(dac, self._offset_counts(dac, self.slider[dac]))
                # chkLockClickedEvent on first push (unlocked branch, no ramp): automatic dither back on
                if self.sl.dither_mode_auto[ch] == 1:
                    self.sl.setDitherLockInState(ch, True)
                for dac in self._channel_dacs(ch):         # displayDAC(): read back the outputs once
                    self.capture(f'DAC{dac}', 256)
                if ch == 0 and slow_start_hv:
                    self._slow_start_hv_supply()

            # frequency-counter windows
            for ch in (0, 1):
                self.sl.setCounterMode(int(c.get('Triangular_averaging', f'DAC{ch}')) > 0)

            # Settings tab (ConfigRPSettingsUI.pushValues)
            vco_conn = int(c.get('VCO_settings', 'VCO_connection'))
            self.sl.set_mux_vco(vco_conn if vco_conn in (1, 2) else 0)
            pll2 = int(c.get('RP_settings', 'PLL2_connection'))
            self.sl.set_mux_pll2(pll2 if pll2 in (1, 2) else 0)
            amp = c.getf('VCO_settings', 'VCO_amplitude')
            self.sl.set_internal_VCO_amplitude(amp if -1 <= amp <= 1 else 0.5)
            self.sl.setFan(int(c.get('RP_settings', 'Fan_state')) > 0)
            ext_in_xml = int(c.get('RP_settings', 'Clock_select')) <= 0
            if ext_in_xml:
                self.set_clock(True, 200e6)        # GUI quirk: the XML path uses its default 200 MHz target
            else:
                self.set_clock(False)

            # DDC filter / angle (DisplayDividerAndResidualsStreamingSettingsWindow.ddcClicked)
            for ch in (0, 1):
                self.sl.set_ddc_filter(ch, int(c.get('Filter_select', f'DAC{ch}')), int(c.get('Angle_select', f'DAC{ch}')))

            # dither windows (DisplayDitherSettingsWindow.ditherClicked)
            for ch in (0, 1):
                self._push_dither(ch)

            if clock not in ('config', None):
                if clock == 'internal':
                    self.set_clock(False)
                else:
                    f = clock[1] if isinstance(clock, (tuple, list)) else 20e6
                    self.set_clock(True, f)
        self._event('pushed config ' + self.config.path.name)

    def _push_dither(self, ch: int):
        c, s = self.config, f'DAC{ch}'
        f_mod = float('{:.1e}'.format(c.getf('Dither_frequency', s)))
        t_int = float('{:.3f}'.format(c.getf('Dither_integration_time', s)))
        amp = float('{:.2e}'.format(c.getf('Dither_amplitude', s)))
        mode = c.getf('Dither_mode', s)
        out_amp = int((self.sl.DACs_limit_high[ch] - self.sl.DACs_limit_low[ch]) / 2. * amp) or 1
        mode_auto, enable = (1, 0) if mode not in (0, 1) else (0, int(mode == 1))
        period = round(self.sl.fs / f_mod)
        n_periods = np.ceil(t_int * self.sl.fs / period)
        self.sl.setupDitherLockIn(ch, period, n_periods, out_amp, mode_auto)
        if mode_auto == 0:
            self.sl.setDitherLockInState(ch, enable)

    def _slow_start_hv_supply(self):
        """XEM_GUI_MainWindow.slowStart100VSwitchingSupply: ramp the on-board 100 V boost converter (200 kHz PWM)."""
        f_sw, v_target, v_supply, t_ramp, n = 200e3, 100., 30., 100e-3, 10
        duty = (v_target - v_supply) / v_target
        modulus = int(round(self.sl.fs / f_sw))
        for k in range(n + 1):
            self.sl.setTestOscillator(bEnable=1, bPolarity=1, oscillator_modulus=modulus,
                                      oscillator_modulus_active=int(round(modulus * k / n * duty)))
            time.sleep(t_ramp / n)

    # ------------------------------------------------------------------ clock
    def set_clock(self, external: bool = True, f_ext: float = 20e6):
        """Select the ADC clock. External: f_ext Hz on the EXT CLK input (20 MHz from the GPS 10 MHz doubler)."""
        with self.io:
            if external:
                M, D0, D1 = pll_multipliers(f_ext)
                if M == 0:
                    raise ValueError(f'no valid MMCM setting for {f_ext/1e6} MHz')
                self.sl.setADCclockPLL(f_ext, True, M, D0, D1)
                self.f_ext = f_ext
            else:
                self.sl.setADCclockPLL(200e6, False, 5, 8)
                self.f_ext = None
            for ch in (0, 1):                   # setVCOFreq_event on both windows (fs may have changed)
                self._set_ref_freq(ch)
        self._event(f'clock: {"external %.6g MHz" % (f_ext/1e6) if external else "internal"}, fs = {self.sl.fs/1e6:.6f} MHz')

    # ------------------------------------------------------------------ lock / unlock
    def lock(self, channel='ceo'):
        ch = _ch(channel)
        with self.io:
            if self.sl.dither_mode_auto[ch] == 1:
                self.sl.setDitherLockInState(ch, False)
            if ch == 0:
                self._write_loop(0, True)
            else:
                self._write_loop(1, False)
                self._integrators('slow')       # grab the beat with the slow (DAC2) integrator
                time.sleep(0.2)
                self._write_loop(1, True)
                self._integrators('fast')
        self._event(f'lock {channel}')

    def unlock(self, channel='ceo', ramp: bool = True):
        """Locked -> unlocked, ramping the manual DAC offset to where the lock sat (as the GUI does)."""
        ch = _ch(channel)
        with self.io:
            if ramp and not self.sl.output_vco[ch]:
                dac = 0 if ch == 0 else 1
                samples, _ = self.capture(f'DAC{dac}', 10e3)
                mean_counts = float(np.mean(samples))
                lo, hi = self.sl.DACs_limit_low[dac], self.sl.DACs_limit_high[dac]
                target = (mean_counts - lo) / float(hi - lo) * self.SLIDER_FULL_SCALE
                for s in np.linspace(float(self.slider[dac]), target, 20):
                    self.slider[dac] = int(s)
                    for d in self._channel_dacs(ch):
                        self.sl.set_dac_offset(d, self._offset_counts(d, self.slider[d]))
                    time.sleep(0.1 / 20)
            if ch == 0:
                self._write_loop(0, False)
            else:
                self._write_loop(1, False)
                self._integrators('off')
            if self.sl.dither_mode_auto[ch] == 1:
                self.sl.setDitherLockInState(ch, True)
        self._event(f'unlock {channel}')

    def is_locked(self, channel='ceo') -> bool:
        """Lock bit as stored in the FPGA (read back, so valid after re-attaching)."""
        ch = _ch(channel)
        return bool(self.sl.read_RAM_dpll_wrapper(self.sl.pll[ch].bus_base_address) & 1)

    # ------------------------------------------------------------------ user-level setters
    def set_dac_offset(self, dac: int, volts: float):
        """Manual DAC offset in the GUI's volts (relative to Output_limits); used when unlocked or as lock centre."""
        with self.io:
            self._apply_slider(dac, self._slider_from_volts(dac, volts))
        self.config.set('Output_offset_in_volts', f'DAC{dac}', str(volts))

    def set_ref_freq(self, channel, f_hz: float, vco_sign: int | None = None):
        ch = _ch(channel)
        self.config.set('Reference_frequency', f'DDC{ch}', str(f_hz))
        if vco_sign is not None:
            self.vco_sign[ch] = 1 if vco_sign > 0 else -1
        with self.io:
            self._set_ref_freq(ch)

    def set_loop_filter(self, channel, **params):
        """Change kp [dB], fi, fii, fd, fdf [Hz], chkKp, chkKd, chkKpCrossing and push (lock state preserved)."""
        ch = _ch(channel)
        for k, v in params.items():
            self.config.set(f'PLL{ch}_settings', k, str(v))
        with self.io:
            locked = self.is_locked(ch)
            self._write_loop(ch, locked)

    def set_vco_gain(self, dac: int, hz_per_volt: float):
        self.config.set('VCO_gain', f'DAC{dac}', str(hz_per_volt))
        with self.io:
            self.kc[dac] = self._compute_kc(dac)
            self.sl.save_openLoop_gain(dac, self.kc[dac])
            ch = 0 if dac == 0 else 1
            self._write_loop(ch, self.is_locked(ch))

    # ------------------------------------------------------------------ attach to a running box (read only)
    def attach(self, f_ext: float | None = 20e6):
        """Read the state of a box that is already configured / locked. Writes nothing.

        f_ext: the external clock frequency, needed to compute fs if the box runs on the external clock.
        """
        sl = self.sl
        with self.io:
            ext = not bool(sl.dev.read_Zynq_AXI_register_uint32(sl.clk_sel_base_addr) & 1)
            mult = (sl.dev.read_Zynq_AXI_register_uint32(sl.clkw_base_addr + 0x200) >> 8) & 0xFF
            div = sl.dev.read_Zynq_AXI_register_uint32(sl.clkw_base_addr + 0x208) & 0xFF
            f_src = (f_ext or 20e6) if ext else 200e6
            if mult and div:
                sl.fs = f_src * mult / div
            self.f_ext = f_src if ext else None
            for d in range(3):
                sl.get_dac_limits(d)
                off = sl.get_dac_offset(d)
                inv = -off if d < 2 else 65535 - off
                lo, hi = sl.DACs_limit_low[d], sl.DACs_limit_high[d]
                self.slider[d] = int((inv - lo) * self.SLIDER_FULL_SCALE / float(hi - lo)) if hi != lo else 0
                self.kc[d] = sl.get_openLoop_gain(d) or self.kc[d]
            f0, f1 = sl.get_ddc0_ref_freq_from_RAM(), sl.get_ddc1_ref_freq_from_RAM()
            self.vco_sign = {0: 1 if f0 < 0 else -1, 1: 1 if f1 < 0 else -1}
            sl.getCounterMode()
            sl.get_ddc_filter_select(); sl.get_ddc_angle_select()
            for d in (0, 1):
                sl.get_Dither_Settings(d)
            hold1, _, lock1, _ = sl.get_integrator_settings(1)
            hold2 = sl.get_integrator_settings(2)[0]
            self.optical_mode = 'off' if not lock1 else {(0, 1): 'slow', (1, 1): 'fast', (1, 0): 'both'}.get((hold1, hold2), 'slow')
        self._event(f'attached: {"external" if ext else "internal"} clock, fs = {sl.fs/1e6:.6f} MHz, '
                    f'ref0 = {f0/1e6:.4f} MHz, ref1 = {f1/1e6:.4f} MHz')
        return self.status()

    # ------------------------------------------------------------------ readback / status
    def status(self) -> dict:
        sl = self.sl
        with self.io:
            vccint, vccaux, vbram = sl.readZynqXADCsupply()
            ext = not bool(sl.dev.read_Zynq_AXI_register_uint32(sl.clk_sel_base_addr) & 1)
            st = {
                'host': self.host,
                'clock': 'external' if ext else 'internal',
                'fs_MHz': sl.fs / 1e6,
                'ext_clk_measured_MHz': self.ext_clock_freq() / 1e6,
                'zynq_temp_C': sl.readZynqTemperature(),
                'Vccint': vccint, 'Vccaux': vccaux, 'Vbram': vbram,
                'ceo_locked': self.is_locked(0),
                'optical_locked': self.is_locked(1),
                'optical_mode': self.optical_mode,
                'ddc0_ref_MHz': sl.get_ddc0_ref_freq_from_RAM() / 1e6,
                'ddc1_ref_MHz': sl.get_ddc1_ref_freq_from_RAM() / 1e6,
            }
            for d in range(3):
                st[f'dac{d}_now_V'] = float(sl.convertDACCountsToVolts(d, self._dac_current(d)))
                st[f'dac{d}_frac'] = self._dac_fraction(d, self._dac_current(d))
        return st

    def ext_clock_freq(self) -> float:
        """External clock frequency measured by the FPGA against its internal 200 MHz (not disciplined)."""
        try:
            return float(self.sl.getExtClockFreq())
        except Exception:
            return float('nan')

    def _dac_current(self, d: int) -> int:
        addr = (self.sl.BUS_ADDR_DAC0_CURRENT, self.sl.BUS_ADDR_DAC1_CURRENT, self.sl.BUS_ADDR_DAC2_CURRENT)[d] * 4
        if d < 2:
            return self.sl.dev.read_Zynq_register_int32(addr)
        v = self.sl.dev.read_Zynq_register_uint32(addr)
        return v - 0xFFFF0000 if v > 0xFFFF0000 else v

    def _dac_fraction(self, d, counts) -> float:
        lo, hi = self.sl.DACs_limit_low[d], self.sl.DACs_limit_high[d]
        return float((counts - lo) / float(hi - lo)) if hi != lo else float('nan')

    def read_counters(self) -> dict:
        """One read of the zero-dead-time frequency counters (lock frequency error, Hz) and the DAC outputs.

        new=True when the counter produced a new gate since the previous call.
        """
        sl = self.sl
        with self.io:
            n = sl.dev.read_Zynq_register_uint32(sl.BUS_ADDR_ZERO_DEADTIME_SAMPLES_NUMBER * 4)   # latches the rest
            c0 = sl.dev.read_Zynq_register_int64(sl.BUS_ADDR_ZERO_DEADTIME_COUNTER0_LSBS * 4, sl.BUS_ADDR_ZERO_DEADTIME_COUNTER0_MSBS * 4)
            c1 = sl.dev.read_Zynq_register_int64(sl.BUS_ADDR_ZERO_DEADTIME_COUNTER1_LSBS * 4, sl.BUS_ADDR_ZERO_DEADTIME_COUNTER1_MSBS * 4)
            dacs = [self._dac_current(d) for d in range(3)]
        last = getattr(self, '_last_n', None)
        self._last_n = n
        out = {'t': time.time(), 'n': n, 'new': last is None or n != last,
               'dropped': max(0, (n - last - 1)) if last is not None else 0,
               'ceo_err_Hz': float(sl.scaleCounterReadingsIntoHz(c0)[0]),
               'opt_err_Hz': float(sl.scaleCounterReadingsIntoHz(c1)[0])}
        for d in range(3):
            out[f'dac{d}_V'] = float(sl.convertDACCountsToVolts(d, dacs[d]))
            out[f'dac{d}_frac'] = self._dac_fraction(d, dacs[d])
        return out

    # ------------------------------------------------------------------ data capture (on demand)
    def capture(self, source: str = 'ADC0', n: int = 2 ** 14):
        """Grab a block from the on-chip logger (max 32768 samples at fs).

        source: 'ADC0','ADC1' -> (samples_counts, ref_phasor); 'DAC0','DAC1','DAC2' -> (samples_counts, 1);
                'DDC0','DDC1' -> (instantaneous frequency error in Hz, None)
        """
        n = int(min(n, self.sl.dev.MAX_SAMPLES_READ_BUFFER))
        with self.io:
            self.sl.setup_write(self.sl.LOGGER_MUX[source], n)
            self.sl.trigger_write()
            self.sl.wait_for_write()
            if source.startswith('DDC'):
                return self.sl.read_ddc_samples_from_DDR2(), None
            return self.sl.read_adc_samples_from_DDR2()

    def frequency_noise(self, channel='ceo', n: int = 2 ** 15, decimate: int = 10):
        """Frequency-noise PSD of the in-loop beat (as the GUI's phase-noise plot): returns f, S_nu [Hz^2/Hz], S_phi [rad^2/Hz]."""
        from scipy.signal import decimate as _dec, detrend, welch
        ch = _ch(channel)
        inst, _ = self.capture(f'DDC{ch}', n)
        fs_new = self.sl.fs / decimate
        x = detrend(_dec(inst, decimate, zero_phase=False) - np.mean(inst))
        f, s = welch(x, fs_new, window='blackman', nperseg=2 ** int(np.floor(np.log2(len(x)))))
        with np.errstate(divide='ignore', invalid='ignore'):
            sphi = s / f ** 2
        return f[1:], s[1:], sphi[1:]

    # ------------------------------------------------------------------ snapshots
    def snapshot(self) -> dict:
        """Everything needed to restore this lock later (config + GUI-side state). JSON-serialisable."""
        return {'time': time.strftime('%Y-%m-%dT%H:%M:%S'), 'host': self.host,
                'config_xml': ET.tostring(self.config.tree.getroot(), encoding='unicode'),
                'vco_sign': self.vco_sign, 'slider': self.slider, 'f_ext': self.f_ext,
                'locked': {'ceo': self.is_locked(0), 'optical': self.is_locked(1)}}

    def restore(self, snap: dict, relock: bool = True):
        root = ET.fromstring(snap['config_xml'])
        self.config.tree = ET.ElementTree(root)
        self.vco_sign = {int(k): v for k, v in snap['vco_sign'].items()}
        clock = ('external', snap['f_ext']) if snap.get('f_ext') else 'internal'
        self.push_config(clock=clock)
        with self.io:
            for d, s in snap['slider'].items():
                self._apply_slider(int(d), s)
        if relock:
            for chname in ('ceo', 'optical'):
                if snap['locked'].get(chname):
                    self.lock(chname)

    # ------------------------------------------------------------------ firmware (rarely needed)
    def program_fpga(self, bitfile: str | os.PathLike = PKG_DIR / 'firmware' / 'red_pitaya_top_extint_clk.bit'):
        """Load a bitstream into the Zynq PL (volatile, like the GUI's 'Program FPGA'). Re-push config afterwards."""
        with self.io:
            self.sl.dev.write_file_on_remote(str(bitfile), '/opt/red_pitaya_top.bit')
            self.sl.dev.send_shell_command('cat /opt/red_pitaya_top.bit > /dev/xdevcfg')
        self._event(f'programmed {Path(bitfile).name}')


def discover(broadcast: str = '192.168.0.255', timeout: float = 2.0, port: int = 1952):
    """UDP broadcast discovery (UDPRedPitayaDiscovery.py). Returns list of (ip, mac)."""
    import select
    import socket
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind(('', port + 1))
    rx.setblocking(False)
    found = {}
    try:
        tx.sendto(b'', (broadcast, port))
        t0 = time.time()
        while time.time() - t0 < timeout:
            r, _, _ = select.select([rx], [], [], 0.1)
            if r:
                data, (ip, _) = rx.recvfrom(4096)
                found[ip] = data.decode('ascii', 'replace')
    finally:
        tx.close(); rx.close()
    return sorted(found.items())
