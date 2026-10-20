"""Declarative instrument options.

A driver lists every setting it can read or write as an :class:`Opt`. The GUI renders the
list as a "Setup" tab (one group box per ``group``), and scripts can use the same table::

    sa.read_options()                 # {"fref": "EXT", "scale": "LG", ...}
    sa.write_option("fref", "EXT")    # writes, then reads back

``get`` / ``set`` are either SCPI strings (``"FREF?"`` / ``"FREF {v}"``) sent through the
driver's ``option_query`` / ``option_write``, or callables ``get(dev)`` / ``set(dev, value)``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

Getter = Union[str, Callable[[Any], Any], None]
Setter = Union[str, Callable[[Any, Any], Any], None]

_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


@dataclass
class Opt:
    key: str
    label: str
    group: str = "General"
    kind: str = "number"                 # number | int | choice | bool | text | action
    get: Getter = None
    set: Setter = None
    choices: Sequence = ()               # values, or (label, value) pairs
    unit: str = ""                       # SI base unit for number fields (Hz, s, V, W, m, dB, dBm …)
    lo: Optional[float] = None
    hi: Optional[float] = None
    tip: str = ""
    bools: Tuple[str, str] = ("ON", "OFF")   # what a bool writes for True / False
    parse: Optional[Callable[[str], Any]] = None
    scale: float = 1.0                   # value on the bus = value in the GUI × scale (e.g. nm → m: 1e-9)
    indexed: bool = False                # choice replies are an index into ``choices`` (0, 1, 2 …)

    # ---- helpers ----------------------------------------------------------------------------
    @property
    def readonly(self) -> bool:
        return self.set is None and self.kind != "action"

    def pairs(self) -> List[Tuple[str, Any]]:
        out = []
        for c in self.choices:
            out.append((str(c[0]), c[1]) if isinstance(c, tuple) else (str(c), c))
        return out

    def convert(self, raw: Any) -> Any:
        """Instrument reply → Python value of this option's kind."""
        if raw is None:
            return None
        if self.parse is not None:
            return self.parse(raw)
        if not isinstance(raw, str):
            v = raw
        else:
            v = raw.strip()
            if len(v) >= 2 and v[0] == v[-1] == '"':
                v = v[1:-1]
        if self.kind == "bool":
            if isinstance(v, bool):
                return v
            s = str(v).upper()
            if s in ("1", "+1", "ON", "TRUE", "YES", "EXT"):
                return True
            if s in ("0", "+0", "OFF", "FALSE", "NO", "INT"):
                return False
            try:
                return float(s) != 0
            except ValueError:
                return None
        if self.kind in ("number", "int"):
            if isinstance(v, (int, float)):
                x = float(v)
            else:
                m = _NUM.search(str(v))
                if not m:
                    return None
                x = float(m.group(0))
            x /= self.scale
            return int(round(x)) if self.kind == "int" else x
        if self.kind == "choice":
            vals = [val for _, val in self.pairs()]
            if self.indexed:
                try:
                    i = int(float(str(v)))
                    if 0 <= i < len(vals) and str(v).strip().lstrip("+-").replace(".", "").isdigit():
                        return vals[i]
                except ValueError:
                    pass
            return match_choice(v, vals)
        return v

    def encode(self, value: Any) -> str:
        """Python value → text substituted for ``{v}`` in a SCPI ``set`` string."""
        if self.kind == "bool":
            return self.bools[0] if value else self.bools[1]
        if self.kind in ("number", "int"):
            x = float(value) * self.scale
            return str(int(round(x))) if self.kind == "int" else f"{x:.10g}"
        return str(value)


def _short(s: str) -> str:
    """SCPI short form: the upper-case letters of 'LOGarithmic' → 'LOG'."""
    up = "".join(ch for ch in s if ch.isupper() or ch.isdigit())
    return up if up else s.upper()


def match_choice(raw: Any, values: Iterable[Any]) -> Any:
    """Map an instrument reply onto one of ``values`` (exact, numeric, or SCPI short/long form)."""
    values = list(values)
    if raw in values:
        return raw
    s = str(raw).strip().strip('"').upper()
    for v in values:
        if str(v).upper() == s:
            return v
    try:
        x = float(s)
        for v in values:
            try:
                if abs(float(v) - x) <= 1e-9 * max(1.0, abs(x)):
                    return v
            except (TypeError, ValueError):
                continue
    except ValueError:
        pass
    for v in values:
        sv = str(v)
        su = sv.upper()
        if s and (su.startswith(s) or s.startswith(su) or _short(sv) == s or s.startswith(_short(sv))):
            return v
    return raw


class OptionsMixin:
    """Mixed into :class:`vescentcomb.core.base.Device`. Override ``options()`` for dynamic tables."""

    OPTIONS: Sequence[Opt] = ()

    def options(self) -> List[Opt]:
        return list(self.OPTIONS)

    def option(self, key: str) -> Opt:
        for o in self.options():
            if o.key == key:
                return o
        raise KeyError(f"{type(self).__name__} has no option '{key}'")

    # transport (SCPI drivers inherit these; others override or use callables)
    def option_query(self, cmd: str) -> Optional[str]:
        io = getattr(self, "io", None)
        if io is None:
            raise NotImplementedError("option_query needs an io attribute or an override")
        if hasattr(io, "try_query"):
            return io.try_query(cmd, 3000)
        return io.query(cmd)

    def option_write(self, cmd: str) -> None:
        io = getattr(self, "io", None)
        if io is None:
            raise NotImplementedError("option_write needs an io attribute or an override")
        io.write(cmd)

    # public API
    def read_option(self, key: str) -> Any:
        o = self.option(key)
        if o.get is None:
            return None
        raw = o.get(self) if callable(o.get) else self.option_query(o.get)
        return o.convert(raw)

    def write_option(self, key: str, value: Any = None, readback: bool = True) -> Any:
        o = self.option(key)
        if o.kind != "action":
            if o.set is None:
                raise ValueError(f"option '{key}' is read-only")
            if o.kind in ("number", "int") and value is not None:
                if o.lo is not None and float(value) < o.lo:
                    raise ValueError(f"{o.label}: {value} below {o.lo}")
                if o.hi is not None and float(value) > o.hi:
                    raise ValueError(f"{o.label}: {value} above {o.hi}")
        if callable(o.set):
            o.set(self, value)
        elif isinstance(o.set, str):
            self.option_write(o.set.format(v=o.encode(value) if o.kind != "action" else ""))
        if o.kind == "action" or not readback or o.get is None:
            return value
        try:
            return self.read_option(key)
        except Exception:
            return value

    def read_options(self, keys: Optional[Iterable[str]] = None, group: Optional[str] = None) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        want = set(keys) if keys is not None else None
        for o in self.options():
            if o.get is None or (want is not None and o.key not in want) or (group and o.group != group):
                continue
            try:
                out[o.key] = self.read_option(o.key)
            except Exception as e:          # keep going; one unsupported query must not hide the rest
                out[o.key] = None
                out.setdefault("_errors", {})[o.key] = str(e)
        return out
