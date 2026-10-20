"""Modern-Python (3.9+, NumPy 2, no Qt) control package for the Vescent SLICE-FPGA-II."""
from .controller import SliceFPGA, SliceConfig, discover, pll_multipliers, DEFAULT_CONFIG, CONFIG_DIR
from .monitor import Monitor, Watchdog
from .rp_pll import CommsError

__all__ = ['SliceFPGA', 'SliceConfig', 'discover', 'pll_multipliers', 'Monitor', 'Watchdog', 'CommsError',
           'DEFAULT_CONFIG', 'CONFIG_DIR']
__version__ = '1.0.0'
