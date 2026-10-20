"""vescentcomb — Vescent comb and locking (FFC-100, GPS OPL #1, SLICE-FPGA-II, comb lock process).

A stand-alone application: the comb module is built in and always loaded (no add-on manager).

Scripting::

    from vescentcomb import discovery

    with discovery.connect_all() as bench:     # finds the FFC-100, OPL #1 and the SLICE-FPGA-II
        print(bench.opl1.servo_on(), bench.fpga.attach()["ceo.kp"])
"""

__version__ = "0.1.0"

from .core.base import Device, DeviceError, Identity, SafetyError  # noqa: F401
from .settings import Settings, default_settings_path              # noqa: F401
from . import datafile                                               # noqa: F401  (CSV with bench-state header)


def load_addons(settings=None, **kw):
    """Load the add-ons enabled in the settings file (installing requirements on first use)."""
    from .addonkit import load_enabled
    return load_enabled(settings if settings is not None else Settings(), **kw)


def addon(addon_id: str, settings=None):
    """Load one add-on (and its dependencies), even if it is unchecked, and return its package."""
    from .addonkit import load
    return load(addon_id, settings if settings is not None else Settings())
