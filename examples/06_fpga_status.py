"""Attach to the SLICE-FPGA-II (read only) and print what it is running, plus the
f_ceo counter and integrated phase. Uses the comb lock module's FPGA package.

    python examples/06_fpga_status.py [--sim]
"""
from _common import maybe_sim

import vescentcomb

SliceFPGA = vescentcomb.addon("comb_lock").SliceFPGA

maybe_sim()
with SliceFPGA.find() as fpga:
    s = fpga.attach()                              # writes nothing
    for k in ("clock.source", "clock.fs_hz", "ceo.ref_freq_hz", "ceo.kp", "ceo.fi", "ceo.fii", "ceo.fd",
              "ceo.fdf", "ceo.locked", "optical.locked"):
        print(f"{k:18s} {s[k]}")
    print("counter error   ", fpga.read_counters()["ceo_err_Hz"], "Hz")
    print("integrated phase", fpga.integrated_phase("ceo"), "rad")
    lo, fc, hi = fpga.filter_band("ceo")
    print(f"DDC pass band    {lo/1e6:.2f}–{hi/1e6:.2f} MHz around {fc/1e6:.3f} MHz")
    # leaving the with-block disconnects; the loops keep running in the FPGA
