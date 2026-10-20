"""Shared bit for the examples: add --sim to run without hardware."""
import sys


def maybe_sim():
    if "--sim" in sys.argv:
        from vescentcomb import sim
        sim.install(speed=60)
        print("(simulated bench)")
        return True
    return False
