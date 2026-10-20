"""Auto-saved settings file.

Everything the GUI (or a script) wants to remember between sessions lives in
one JSON file. Writes are debounced (default 1 s after the last change),
atomic (write to a temp file, then replace) and keep one ``.bak`` copy.

Layout
------
``roles``      role -> {kind, serial, model, address} (devices matched by serial)
``ui``         GUI state restored directly (window geometry, page, field values,
               lock-sequence parameters, scan ranges, slider positions...)
``devices``    role -> last-read device snapshot. Used for "Restore last
               session" and the FPGA box-vs-profile diff. Never written to the
               hardware automatically.

Outputs, emission and servo-enable states are *never* restored automatically.
"""
from __future__ import annotations

import atexit
import copy
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

SCHEMA_VERSION = 1
APP_NAME = "vescentcomb"


def default_settings_path() -> Path:
    env = os.environ.get("VESCENTCOMB_SETTINGS")
    if env:
        return Path(env)
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP_NAME / "settings.json"


def default_data_dir() -> Path:
    """Where recordings, scans and captures go unless the user picks a folder."""
    docs = Path.home() / "Documents"
    return (docs if docs.is_dir() else Path.home()) / "vescentcomb data"


def _default_data() -> Dict[str, Any]:
    return {"schema": SCHEMA_VERSION, "saved_at": None, "roles": {}, "ui": {}, "devices": {}}


class Settings:
    """Dotted-key settings store with debounced atomic autosave.

    >>> s = Settings("/tmp/x.json")
    >>> s.set("ui.lock.window_hz", 8)
    >>> s.get("ui.lock.window_hz")
    8
    """

    def __init__(self, path: Optional[os.PathLike] = None, autosave_delay: float = 1.0,
                 autosave: bool = True):
        self.path = Path(path) if path else default_settings_path()
        self.autosave_delay = autosave_delay
        self.autosave = autosave
        self._lock = threading.RLock()
        self._timer: Optional[threading.Timer] = None
        self._dirty = False
        self._listeners: List[Callable[[str, Any], None]] = []
        self.data = _default_data()
        self.load()
        atexit.register(self.flush)

    # -- persistence ------------------------------------------------------------
    def load(self) -> None:
        with self._lock:
            for candidate in (self.path, self.path.with_suffix(".json.bak")):
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data = _default_data()
                        data.update(loaded)
                        self.data = data
                        return
                except FileNotFoundError:
                    continue
                except (json.JSONDecodeError, OSError):
                    continue  # corrupt -> try the backup, else defaults
            self.data = _default_data()

    def save(self) -> Path:
        """Write now (atomic). Returns the path written."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self.data["schema"] = SCHEMA_VERSION
            self.data["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, sort_keys=True, default=_json_default)
                f.flush()
                os.fsync(f.fileno())
            if self.path.exists():
                try:
                    os.replace(self.path, self.path.with_suffix(".json.bak"))
                except OSError:
                    pass
            os.replace(tmp, self.path)
            self._dirty = False
            return self.path

    def flush(self) -> None:
        """Save if anything changed since the last write."""
        with self._lock:
            if self._dirty:
                try:
                    self.save()
                except OSError:
                    pass

    def _schedule(self) -> None:
        if not self.autosave:
            return
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.autosave_delay, self.flush)
            self._timer.daemon = True
            self._timer.start()

    # -- access ---------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self.data
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return copy.deepcopy(node)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            parts = key.split(".")
            node = self.data
            for part in parts[:-1]:
                nxt = node.get(part)
                if not isinstance(nxt, dict):
                    nxt = {}
                    node[part] = nxt
                node = nxt
            if node.get(parts[-1]) == value:
                return
            node[parts[-1]] = copy.deepcopy(value)
            self._dirty = True
        for cb in list(self._listeners):
            try:
                cb(key, value)
            except Exception:
                pass
        self._schedule()

    def update(self, key: str, values: Dict[str, Any]) -> None:
        for k, v in values.items():
            self.set(f"{key}.{k}", v)

    def delete(self, key: str) -> None:
        with self._lock:
            parts = key.split(".")
            node = self.data
            for part in parts[:-1]:
                node = node.get(part, {})
                if not isinstance(node, dict):
                    return
            if parts[-1] in node:
                del node[parts[-1]]
                self._dirty = True
        self._schedule()

    def on_change(self, cb: Callable[[str, Any], None]) -> None:
        self._listeners.append(cb)

    # -- convenience for roles / device snapshots ------------------------------
    def role(self, role: str) -> Dict[str, Any]:
        return self.get(f"roles.{role}", {}) or {}

    def set_role(self, role: str, kind: str, serial: str, model: str = "", address: str = "") -> None:
        self.set(f"roles.{role}", {"kind": kind, "serial": serial, "model": model,
                                   "address": address})

    def save_device_state(self, role: str, snapshot: Dict[str, Any]) -> None:
        self.set(f"devices.{role}", {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                     "state": snapshot})

    def device_state(self, role: str) -> Dict[str, Any]:
        return (self.get(f"devices.{role}", {}) or {}).get("state", {})


def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    if isinstance(o, (set, tuple)):
        return list(o)
    if isinstance(o, Path):
        return str(o)
    return str(o)
