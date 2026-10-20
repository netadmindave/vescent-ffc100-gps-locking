"""Simulated bench: every instrument answers its real command set.

``vescentcomb.sim.install()`` swaps the discovery hooks so the GUI and scripts run unchanged
without hardware (``python -m vescentcomb.gui --sim``). The shell's world is empty; each loaded
add-on's ``sim.py`` adds its instruments (see ``vescentcomb/docs/ADDON_GUIDE.md`` §9).
"""
from .world import World, install, uninstall, get_world  # noqa: F401
