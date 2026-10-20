"""Comb lock module: drivers, FPGA package, comb lock sequence, OPL auto-tune (simulated bench)."""
import os
import subprocess
import sys

import numpy as np
import pytest

from vescentcomb import SafetyError

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = {"ceo.kp": -64.9, "ceo.fd": 1.15e5, "clock.source": "external"}


def _fast(**kw):
    from vescentcomb_addons.comb_lock import LockParams
    return LockParams(poll_s=0.05, confirm_dwell_s=0.2, post_servo_wait_s=0.2, **kw)


# ---- drivers -------------------------------------------------------------------------------------
def test_ffc_reads_and_guards(bench):
    assert bench.ffc.mode_locked()
    assert "cav_setpoint" in bench.ffc.snapshot()
    with pytest.raises((SafetyError, ValueError)):
        bench.ffc.set_cav_setpoint(80.0)          # outside 15–45 °C


def test_opl_limits_identity_and_restore(bench):
    o = bench.opl1
    assert o.identify().serial == "OPL-0001"
    o.set_pll_limits(-12.0, 12.0, 0.0)
    with pytest.raises((SafetyError, ValueError)):
        o.set_pll_limits(-13.0, 12.0, 0.0)
    o.set_servo(False)
    o.restore(dict(o.snapshot(), servo_on=True))
    assert not o.servo_on()


# ---- FPGA ----------------------------------------------------------------------------------------
def test_fpga_package_matches_vescent_gui_register_for_register():
    r = subprocess.run([sys.executable, os.path.join(HERE, "fpga", "verify_against_gui.py"),
                        os.path.join(HERE, "fpga", "rec_gui_ucf.json")], capture_output=True, text=True, timeout=300)
    assert "RESULT: MATCH" in r.stdout, r.stdout + r.stderr


def test_fpga_attach_reads_box_in_gui_units(bench):
    s = bench.fpga.attach()
    assert s["clock.source"] == "external" and s["clock.fs_hz"] == 125e6
    assert s["ceo.kp"] == -64.9 and s["ceo.fi"] == 4e4 and s["ceo.fd"] == 1.15e5
    assert s["ceo.ref_freq_hz"] == 21.4e6 and s["ceo.locked"]


def test_fpga_profile_diff_and_write(bench):
    f = bench.fpga
    prof = dict(f.attach(), **{"ceo.kp": -62.0, "ceo.ref_freq_hz": 21.6e6})
    rows = f.compare(prof)
    assert {r["key"] for r in rows} == {"ceo.kp", "ceo.ref_freq_hz"}
    with pytest.raises(SafetyError):
        f.set_value("ceo.ref_freq_hz", 21.6e6)    # lock-affecting while locked
    assert set(f.apply_differences(rows, allow_unlock=True).values()) == {"ok"}
    s = f.settings()
    assert s["ceo.kp"] == -62.0 and s["ceo.fi"] == 4e4 and s["ceo.locked"]
    assert f.compare(prof) == []


def test_fpga_spectrum_band_and_phase(bench):
    f = bench.fpga
    f.attach()
    lo, fc, hi = f.filter_band("ceo")
    assert lo < fc < hi and abs(fc - 21.4e6) < 1
    fr, p = f.spectrum(0, 16384, 2)
    assert abs(fr[np.argmax(p[5:]) + 5] - 21.4e6) < 50e3
    ok, ph = f.lock_and_verify("ceo", settle_s=0.05)
    assert ok and ph < 1.0


# ---- sequences -----------------------------------------------------------------------------------
def test_comb_lock_sequence_locks_opl1(bench):
    from vescentcomb_addons.comb_lock import LockSequence
    seq = LockSequence(bench.devices, _fast(), fpga_profile=PROFILE, ask=lambda q, rows=None: True)
    assert seq.run()
    assert bench.opl1.servo_on() and bench.ffc.slow_servo_on()
    assert abs(bench.opl1.beat_error_hz(31e-6)) < 8


def test_dry_run_changes_nothing(bench):
    from vescentcomb_addons.comb_lock import LockSequence
    t0 = bench.ffc.cav_setpoint()
    LockSequence(bench.devices, _fast(dry_run=True), fpga_profile=PROFILE).run()
    assert not bench.opl1.servo_on() and bench.ffc.cav_setpoint() == t0


def test_dac0_off_center_recenters_and_relocks(bench):
    """DAC0 beyond the limit -> f_ceo + OPL #1 unlocked, DAC0 to 0 V, sequence runs again."""
    from vescentcomb_addons.comb_lock import LockSequence
    from vescentcomb_addons.comb_lock.gps_lock import lock_problems
    seq = LockSequence(bench.devices, _fast(relock_wait_s=0.1), fpga_profile=PROFILE)
    assert seq.run()
    f = bench.fpga
    p = _fast(dac0_max_frac=-1.0)                     # any DAC0 position now counts as off center
    probs = lock_problems(bench.devices, p, {"fceo": True, "opl1": True, "slow": True})
    assert any(k == "dac0" for k, _ in probs)
    seq2 = LockSequence(bench.devices, _fast(dac0_max_frac=0.15, relock_wait_s=0.1), fpga_profile=PROFILE)
    from vescentcomb_addons.comb_lock.gps_lock import recover
    recover(bench.devices, seq2.p, {"dac0"}, print)
    assert not f.is_locked("ceo") and not bench.opl1.servo_on()
    assert abs(f.dac_position(0)["v"]) < 0.05
    assert seq2.run() and f.is_locked("ceo") and bench.opl1.servo_on()
