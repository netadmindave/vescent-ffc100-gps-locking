"""Run the comb lock sequence (f_ceo, then f_rep -> GPS) from a script — same steps as the GUI.

    python examples/02_gps_lock.py [--sim] [--dry-run]
"""
import sys

from _common import maybe_sim

from vescentcomb import discovery
import vescentcomb
from vescentcomb.settings import Settings

comb = vescentcomb.addon("comb_lock")
LockParams, LockSequence = comb.LockParams, comb.LockSequence

sim = maybe_sim()
settings = Settings()
params = LockParams(dry_run="--dry-run" in sys.argv)
if sim:
    params.poll_s, params.confirm_dwell_s, params.post_servo_wait_s = 0.05, 0.2, 0.2


def ask(question, rows=None):
    for r in rows or []:
        print("   ", r)
    return input(question + " [y/N] ").strip().lower() == "y"


with discovery.connect_all(settings) as bench:
    seq = LockSequence(bench.devices, params,
                       fpga_profile=settings.get("profiles.fpga"),
                       on_log=print, ask=(lambda q, rows=None: True) if sim else ask)
    ok = seq.run()
    for st in seq.steps.values():
        print(f"{st.status:6s} {st.title}: {st.detail}")
    print("LOCKED" if ok else "not locked")
    # leaving the with-block puts each device in its safe state and closes the ports;
    # the comb, FPGA loops and OPL servos are left running.
