"""vescentcomb add-on system.

* ``manifest`` — reads ``addon.toml`` (no code import)
* ``registry`` — what loaded add-ons contribute (roles, drivers, probes, pages, windows …)
* ``api``      — ``AddonAPI``, handed to each add-on's ``register(api)``
* ``loader``   — scans folders, auto-installs requirements on first load, imports add-ons
* ``installer``— requirement checks and pip installs

The design guide is ``vescentcomb/docs/ADDON_GUIDE.md``.
"""
from .api import AddonAPI
from .loader import (BUILTIN_DIR, GUIDE_PATH, TEMPLATE_DIR, addon_dirs, create_from_template, default_user_dir,
                     ensure_loaded, last_scan, load, load_enabled, reset, scan, user_dirs)
from .manifest import AddonInfo, read_manifest
from .registry import REGISTRY

__all__ = ["AddonAPI", "AddonInfo", "REGISTRY", "BUILTIN_DIR", "GUIDE_PATH", "TEMPLATE_DIR", "addon_dirs",
           "create_from_template", "default_user_dir", "ensure_loaded", "last_scan", "load", "load_enabled",
           "read_manifest", "reset", "scan", "user_dirs"]
