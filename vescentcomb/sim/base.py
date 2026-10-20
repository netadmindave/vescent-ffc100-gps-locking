"""Building blocks for simulated instruments (used by every add-on's ``sim.py``)."""
from __future__ import annotations

import re

import numpy as np

from .fakeio import FakeResource, FakeSerial, TextDevice, visa_timeout  # noqa: F401

RNG = np.random.default_rng(1)


def num(s: str) -> float:
    """First number in a command argument ('500MV' -> 500.0, '2.5E-6S' -> 2.5e-06)."""
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
    return float(m.group(0)) if m else 0.0


_num = num


class SCPIModel:
    """Base for VISA models: ``handle(cmd) -> reply | None`` (bytes for binary blocks)."""

    def handle(self, cmd: str):
        return None

    def binary(self, cmd):
        return None


class SilentModel(SCPIModel):
    """A GPIB address that never answers (exercises the 'unknown' path)."""


class _NullGenerator:
    """Stands in for the function generator when its add-on isn't loaded: no signal."""
    r = {30: "500"}

    def on(self, ch): return False
    def freq(self, ch): return 0.0
    def amp(self, ch): return 0.0
    def off(self, ch): return 0.0
    def wave(self, ch): return 0

    def signal(self, ch, t):
        return np.zeros_like(t)


def null_generator():
    return _NullGenerator()


class OptionStore:
    """Remembers ``HEADER value`` writes and answers ``HEADER?`` with them.

    Simulators use it as a catch-all so every option a driver exposes on its Setup tab can be
    written and read back without hand-coding each command::

        self.opt = OptionStore({"FREF": "INT", "AUNITS": "DBM"})
        ...
        return self.opt.handle(cmd)        # at the end of handle()
    """

    def __init__(self, defaults=None):
        self.values = {self.key(k): v for k, v in (defaults or {}).items()}

    @staticmethod
    def key(header: str) -> str:
        return header.strip().lstrip(":").upper()

    def get(self, header, default=None):
        return self.values.get(self.key(header), default)

    def set(self, header, value):
        self.values[self.key(header)] = value

    def handle(self, cmd: str):
        c = cmd.strip()
        if not c:
            return None
        head, _, arg = c.partition(" ")
        if head.endswith("?"):
            k = self.key(head[:-1])
            return str(self.values[k]) if k in self.values else None
        if arg:
            self.values[self.key(head)] = arg.strip()
        return None
