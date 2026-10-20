"""Data files with the bench state in a header.

Every CSV vescentcomb writes starts with ``#`` comment lines that record when, with which
software, what the instruments were set to, which loops were locked and which instruments
were on the 10 MHz reference. The data columns follow, so the file still opens directly in
Excel, and in Python::

    import pandas as pd
    df = pd.read_csv(path, comment="#")
    meta = vescentcomb.datafile.read_header(path)      # the header back as a dict

The GUI registers a *provider* (``set_provider``) that returns the live bench state; scripts
can pass their own ``meta`` dict, or call ``bench_metadata(bench)``.
"""
from __future__ import annotations

import csv
import json
import os
import platform
import socket
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

_PROVIDER: Optional[Callable[[], Dict[str, Any]]] = None


def set_provider(fn: Optional[Callable[[], Dict[str, Any]]]) -> None:
    """Register a function returning the current bench state (the GUI does this)."""
    global _PROVIDER
    _PROVIDER = fn


def _jsonable(v: Any) -> Any:
    if isinstance(v, (str, int, bool)) or v is None:
        return v
    if isinstance(v, float):
        return v if v == v else None
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        if len(v) > 64:                       # arrays don't belong in a header
            return f"<{len(v)} values>"
        return [_jsonable(x) for x in v]
    try:
        import numpy as np
        if isinstance(v, np.generic):
            return _jsonable(v.item())
        if isinstance(v, np.ndarray):
            return f"<array {v.shape}>"
    except ImportError:
        pass
    return str(v)


def base_metadata(kind: str = "") -> Dict[str, Any]:
    from . import __version__
    return {
        "file_type": kind or "data",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "created_unix": round(time.time(), 3),
        "software": f"vescentcomb {__version__}",
        "python": platform.python_version(),
        "host": socket.gethostname(),
    }


def current_metadata(kind: str = "", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    meta = base_metadata(kind)
    if _PROVIDER is not None:
        try:
            meta.update(_PROVIDER() or {})
        except Exception as e:                # a header problem must never lose the data
            meta["metadata_error"] = str(e)
    if extra:
        meta.update(extra)
    return meta


def header_lines(meta: Dict[str, Any]) -> List[str]:
    """``# key: value`` lines; nested values are JSON on one line."""
    out = ["# vescentcomb data file — lines starting with # are metadata; read with pandas.read_csv(path, comment='#')"]
    for k, v in meta.items():
        v = _jsonable(v)
        s = json.dumps(v, ensure_ascii=False, separators=(", ", ": ")) if isinstance(v, (dict, list)) else str(v)
        out.append(f"# {k}: {s}")
    out.append("#")
    return out


def write_csv(path: str, header: Sequence[str], columns: Optional[Sequence[Iterable]] = None,
              rows: Optional[Iterable[Sequence]] = None, kind: str = "", meta: Optional[Dict[str, Any]] = None,
              fmt: str = "{:.10g}") -> str:
    """Write a CSV with the metadata header. Give ``columns`` (one iterable per column) or ``rows``."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    m = current_metadata(kind, meta)
    m["columns"] = list(header)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        for line in header_lines(m):
            fh.write(line + "\n")
        w = csv.writer(fh)
        w.writerow(list(header))
        it = zip(*columns) if columns is not None else (rows or [])
        for row in it:
            w.writerow([fmt.format(x) if isinstance(x, float) else x for x in row])
    return path


class CSVLog:
    """Append-mode CSV (REC logs, scans): header written once when the file is created."""

    def __init__(self, path: str, kind: str = "log", meta: Optional[Dict[str, Any]] = None):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        new = not os.path.exists(path) or os.path.getsize(path) == 0
        self.fh = open(path, "a", newline="", encoding="utf-8")
        self.writer = None
        self.fields: List[str] = []
        self._meta = (kind, meta)
        self._new = new

    def write(self, row: Dict[str, Any]) -> None:
        if self.writer is None:
            self.fields = list(row.keys())
            if self._new:
                m = current_metadata(*self._meta)
                m["columns"] = self.fields
                for line in header_lines(m):
                    self.fh.write(line + "\n")
            self.writer = csv.DictWriter(self.fh, self.fields, extrasaction="ignore")
            if self._new:
                self.writer.writeheader()
        self.writer.writerow(row)
        self.fh.flush()

    def close(self) -> None:
        try:
            self.fh.close()
        except Exception:
            pass


def read_header(path: str) -> Dict[str, Any]:
    """The ``# key: value`` header of a vescentcomb CSV back as a dict."""
    out: Dict[str, Any] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.startswith("#"):
                break
            body = line[1:].strip()
            if ": " not in body or body.startswith("vescentcomb data file"):
                continue
            k, v = body.split(": ", 1)
            try:
                out[k] = json.loads(v)
            except ValueError:
                out[k] = v
    return out


def bench_metadata(bench) -> Dict[str, Any]:
    """Metadata for scripts: every open device's snapshot (read-only) under ``instruments``."""
    inst = {}
    for role, dev in getattr(bench, "devices", {}).items():
        try:
            inst[role] = dev.snapshot()
        except Exception as e:
            inst[role] = {"error": str(e)}
    return {"instruments": inst}
