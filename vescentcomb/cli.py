"""Vescent FFC-100 GPS locking (Vescent Comb) — command-line tool.

    vescent-comb-cli [--sim] [--settings FILE] [--json] COMMAND ...

Instruments are opened from the roles saved by the GUI (Devices… → "Remember these assignments"), so nothing
is scanned unless you ask. An instrument another app has connected is refused ("in use by …"), never probed.
Closing leaves every instrument exactly as it is.  Run ``vescent-comb-cli COMMAND -h`` for each command's options.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from typing import Any, Dict, List, Optional

EXIT_OK, EXIT_ERROR, EXIT_FAILED = 0, 1, 2


# ---- plumbing ----------------------------------------------------------------------------------------------
class Ctx:
    def __init__(self, args):
        from vescentcomb.settings import Settings
        self.args = args
        self.settings = Settings(args.settings) if args.settings else Settings()
        from vescentcomb.addonkit import ensure_loaded
        ensure_loaded(self.settings)
        if args.sim:
            from vescentcomb import sim
            sim.install(settings=self.settings)
        self.devices: Dict[str, Any] = {}

    def out(self, obj, text: Optional[str] = None):
        if self.args.json:
            print(json.dumps(obj, indent=2, default=_jsonable))
        else:
            print(text if text is not None else _pretty(obj))

    def found_for(self, role: str):
        """The saved instrument for ``role`` (no scan); in --sim mode, or if nothing is saved, a scan."""
        from vescentcomb import discovery
        from vescentcomb.addonkit import REGISTRY
        if role not in REGISTRY.roles:
            raise SystemExit(f"unknown role '{role}' (see: vescent-comb-cli roles)")
        s = (self.settings.get("roles", {}) or {}).get(role)
        if isinstance(s, dict) and s.get("address") and not self.args.sim:
            f = discovery.Found(s["kind"], s["address"], _bus_of(s["address"]), model=s.get("model", ""),
                                serial=s.get("serial", ""), how="saved", status="matched")
            f.role = role
            return f
        res = discovery.assign_roles(discovery.scan_all(), self.settings.get("roles", {}))
        f = res.assignments.get(role)
        if f is None:
            raise SystemExit(f"no instrument for role '{role}' (connect it in the GUI, or run: vescent-comb-cli scan --save)")
        return f

    def open(self, role: str):
        if role in self.devices:
            return self.devices[role]
        from vescentcomb import discovery
        f = self.found_for(role)
        dev = discovery.open_found(f)              # claims it: refused if another app has it
        self.devices[role] = dev
        return dev

    def close(self):
        claims = _claims()
        for role, d in self.devices.items():
            try:
                d.close()
            except Exception:
                pass
            if claims is not None:
                claims.release(getattr(d, "address", "") or "")
        self.devices.clear()


def _claims():
    """Cross-app instrument claims (Lab Tools and Laser Lock share instruments); None in apps without them."""
    try:
        from vescentcomb.core import claims
        return claims
    except ImportError:
        return None


def _bus_of(address: str) -> str:
    a = (address or "").upper()
    return "GPIB" if a.startswith("GPIB") else "USB-TMC" if a.startswith("USB") else \
        "VISA" if "::" in a else "BLE" if ":" in a and len(a) == 17 else "serial"


def _jsonable(o):
    try:
        import numpy as np
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.generic):
            return o.item()
    except ImportError:
        pass
    if isinstance(o, bytes):
        return o.hex()
    if hasattr(o, "__dict__"):
        return {k: v for k, v in vars(o).items() if not k.startswith("_")}
    return str(o)


def _pretty(obj) -> str:
    if isinstance(obj, dict):
        w = max((len(str(k)) for k in obj), default=0)
        return "\n".join(f"{str(k).ljust(w)}  {_short(v)}" for k, v in obj.items())
    if isinstance(obj, list):
        return "\n".join(_short(x) for x in obj)
    return str(obj)


def _short(v) -> str:
    s = json.dumps(v, default=_jsonable) if isinstance(v, (dict, list)) else str(v)
    return s if len(s) < 160 else s[:157] + "…"


def _value(text: str):
    """CLI text → Python value for an option: on/off/true/false, numbers (SI suffixes ok), else the text."""
    t = text.strip()
    if t.lower() in ("on", "true", "yes"):
        return True
    if t.lower() in ("off", "false", "no"):
        return False
    import re
    m = re.fullmatch(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([pnuµmkMG]?)[A-Za-z/%]*", t)
    if m:
        mult = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0, "k": 1e3, "M": 1e6, "G": 1e9}
        return float(m.group(1)) * mult[m.group(2)]
    return t


# ---- commands shared by every app --------------------------------------------------------------------------
def cmd_roles(ctx, a):
    from vescentcomb.addonkit import REGISTRY
    claims = _claims()
    saved = ctx.settings.get("roles", {}) or {}
    rows = []
    for role, spec in sorted(REGISTRY.roles.items(), key=lambda x: x[1].order):
        s = saved.get(role) or {}
        rows.append({"role": role, "label": spec.label, "kinds": spec.kinds, "address": s.get("address", ""),
                     "serial": s.get("serial", ""), "in_use_by": (claims.holder(s.get("address", "")) if claims else None) or ""})
    ctx.out(rows, "\n".join(f"{r['role']:<12} {r['label']:<44} {r['address'] or '— not saved —'}"
                            + (f"  (in use by {r['in_use_by']})" if r["in_use_by"] else "") for r in rows))


def cmd_scan(ctx, a):
    from vescentcomb import discovery
    res = discovery.assign_roles(discovery.scan_all(), ctx.settings.get("roles", {}))
    rows = [{"address": f.address, "bus": f.bus, "kind": f.kind, "model": f.model, "serial": f.serial,
             "role": f.role or "", "status": f.status, "how": f.how} for f in res.found + res.unknown + res.skipped]
    if a.save:
        discovery.remember_roles(res, ctx.settings)
        ctx.settings.flush()
    ctx.out(rows, "\n".join(f"{r['address']:<44} {r['model'] or r['status']:<22} {r['serial']:<16} {r['role']}"
                            for r in rows) + ("\n(assignments saved)" if a.save else ""))


def cmd_info(ctx, a):
    d = ctx.open(a.role)
    ident = d.identify()
    info = {"role": a.role, "address": getattr(d, "address", ""), "identity": _jsonable(ident)}
    try:
        info["reading"] = d.poll()
    except Exception as e:
        info["reading_error"] = str(e)
    ctx.out(info)


def cmd_options(ctx, a):
    d = ctx.open(a.role)
    rows = []
    for o in d.options():
        if a.group and a.group.lower() not in o.group.lower():
            continue
        rows.append({"key": o.key, "label": o.label, "group": o.group, "kind": o.kind,
                     "choices": list(o.choices) if o.choices else [], "unit": o.unit, "lo": o.lo, "hi": o.hi})
    ctx.out(rows, "\n".join(f"{r['key']:<34} {r['kind']:<7} {r['group']:<28} {r['label']}"
                            + (f"  [{'|'.join(map(str, r['choices']))[:60]}]" if r["choices"] else "")
                            + (f"  ({r['unit']})" if r["unit"] else "") for r in rows))


def cmd_get(ctx, a):
    d = ctx.open(a.role)
    vals = {k: d.read_option(k) for k in a.keys} if a.keys else d.read_options([o for o in d.options()
                                                                               if o.kind != "action"])
    ctx.out(vals)


def cmd_set(ctx, a):
    d = ctx.open(a.role)
    v = d.write_option(a.key, _value(a.value))
    ctx.out({a.key: v}, f"{a.key} = {v}  (read back)")


def cmd_do(ctx, a):
    d = ctx.open(a.role)
    d.write_option(a.action)
    ctx.out({"done": a.action}, f"done: {a.action}")


def cmd_poll(ctx, a):
    d = ctx.open(a.role)
    w = None
    fh = open(a.csv, "w", newline="", encoding="utf-8") if a.csv else None
    try:
        n = 0
        while a.count == 0 or n < a.count:
            r = d.poll()
            flat = {"t_unix": time.time(), **{k: v for k, v in r.items() if isinstance(v, (int, float, str, bool))
                                                or v is None}}
            if fh:
                if w is None:
                    w = csv.DictWriter(fh, fieldnames=list(flat), extrasaction="ignore")
                    w.writeheader()
                w.writerow(flat)
                fh.flush()
            ctx.out(flat, " · ".join(f"{k}={_short(v)}" for k, v in flat.items()))
            n += 1
            if a.count == 0 or n < a.count:
                time.sleep(a.every)
    except KeyboardInterrupt:
        pass
    finally:
        if fh:
            fh.close()


def build_parser(extra=None) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vescent-comb-cli", description="Vescent FFC-100 GPS locking (Vescent Comb) — command line. Instruments come from the "
                                 "roles the GUI saved; nothing is scanned unless you ask.")
    ap.add_argument("--sim", action="store_true", help="use the simulated bench (no hardware)")
    ap.add_argument("--settings", help="settings file (default: the GUI's)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("roles", help="list roles, their saved instruments and whether another app has them")
    p = sub.add_parser("scan", help="probe every port and show what was found")
    p.add_argument("--save", action="store_true", help="remember the role assignments (like the GUI)")
    p = sub.add_parser("info", help="identify an instrument and read it once")
    p.add_argument("role")
    p = sub.add_parser("options", help="list an instrument's settings")
    p.add_argument("role")
    p.add_argument("--group", help="only groups containing this text")
    p = sub.add_parser("get", help="read settings (all of them if no keys are given)")
    p.add_argument("role")
    p.add_argument("keys", nargs="*")
    p = sub.add_parser("set", help="write one setting; prints the read-back")
    p.add_argument("role")
    p.add_argument("key")
    p.add_argument("value", help="on/off, a number (SI suffixes: 10M, 1.5m …) or a choice")
    p = sub.add_parser("do", help="run an action setting (e.g. a preset)")
    p.add_argument("role")
    p.add_argument("action")
    p = sub.add_parser("poll", help="read an instrument repeatedly")
    p.add_argument("role")
    p.add_argument("--every", type=float, default=1.0, help="seconds between readings (default 1)")
    p.add_argument("--count", type=int, default=1, help="number of readings, 0 = until Ctrl+C (default 1)")
    p.add_argument("--csv", help="also write the readings to this CSV file")
    if extra:
        extra(sub)
    return ap


COMMANDS = {"roles": cmd_roles, "scan": cmd_scan, "info": cmd_info, "options": cmd_options, "get": cmd_get,
            "set": cmd_set, "do": cmd_do, "poll": cmd_poll}


def run(argv=None, extra_parsers=None, extra_commands=None) -> int:
    args = build_parser(extra_parsers).parse_args(argv)
    ctx = Ctx(args)
    try:
        fn = {**COMMANDS, **(extra_commands or {})}[args.cmd]
        r = fn(ctx, args)
        return r if isinstance(r, int) else EXIT_OK
    except SystemExit:
        raise
    except KeyError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return EXIT_ERROR
    finally:
        ctx.close()


# ---- lock commands -------------------------------------------------------------------------------------------
def _params(cls, a):
    """Defaults, then a JSON file (--params), then --set key=value overrides."""
    p = cls.from_dict(json.load(open(a.params, encoding="utf-8")) if a.params else {})
    for kv in a.set or []:
        if "=" not in kv:
            raise SystemExit(f"--set needs key=value, got {kv!r}")
        k, v = kv.split("=", 1)
        if not hasattr(p, k):
            raise SystemExit(f"unknown parameter {k!r}; see 'vescent-comb-cli params'")
        setattr(p, k, _value(v) if not isinstance(getattr(p, k), str) else v)
    if getattr(a, "dry_run", False):
        p.dry_run = True
    return p


def _asker(a):
    def ask(q, rows=None):
        if a.yes:
            print(f"? {q} → yes (--yes)")
            return True
        try:
            return input(f"? {q} [y/N] ").strip().lower() in ("y", "yes")
        except EOFError:
            return False
    return ask


def _printer(ctx):
    seen = {}

    def step(s):
        key = (s.status, s.detail)
        if seen.get(s.id) != key:
            seen[s.id] = key
            if not ctx.args.json:
                print(f"[{s.status:>4}] {s.title}" + (f" — {s.detail}" if s.detail else ""))
    return step


def _add_lock_parsers(sub, what):
    p = sub.add_parser("lock", help=f"run the {what} lock sequence (blocking; Ctrl+C stops it)")
    p.add_argument("--params", help="JSON file with lock parameters (see: params)")
    p.add_argument("--set", action="append", metavar="KEY=VALUE", help="override one parameter (repeatable)")
    p.add_argument("--dry-run", action="store_true", help="check everything, change nothing")
    p.add_argument("--yes", action="store_true", help="answer yes to every question")
    sub.add_parser("params", help="print the lock parameters with their defaults (JSON)")
    sub.add_parser("status", help="is it locked right now? (exit code 0 = locked, 2 = not)")


def _gl():
    from vescentcomb_addons.comb_lock import gps_lock
    return gps_lock


def cmd_params(ctx, a):
    ctx.out(_gl().LockParams().as_dict())


def cmd_lock(ctx, a):
    g = _gl()
    p = _params(g.LockParams, a)
    devs = {r: ctx.open(r) for r in ("ffc", "fpga", "opl1")}
    seq = g.LockSequence(devs, p, ctx.settings.get("profiles.fpga", {}), on_step=_printer(ctx),
                         on_log=lambda s: print(f"  {s}"), ask=_asker(a))
    try:
        ok = seq.run()
    except KeyboardInterrupt:
        seq.stop()
        print("stopped")
        return EXIT_FAILED
    ctx.out({"locked": bool(ok), "steps": {k: {"status": s.status, "detail": s.detail} for k, s in seq.steps.items()}},
            "COMB LOCKED" if ok else "comb NOT locked")
    return EXIT_OK if ok else EXIT_FAILED


def cmd_status(ctx, a):
    g = _gl()
    devs = {r: ctx.open(r) for r in ("ffc", "fpga", "opl1")}
    probs = g.lock_problems(devs, g.LockParams(), {"fceo": True, "opl1": True, "slow": True})
    ctx.out({"comb_locked": not probs, "problems": [{"what": w, "detail": d} for w, d in probs]},
            "COMB LOCKED" if not probs else "comb NOT locked:\n" + "\n".join(f"  {w}: {d}" for w, d in probs))
    return EXIT_OK if not probs else EXIT_FAILED


def main(argv=None) -> int:
    return run(argv, lambda sub: _add_lock_parsers(sub, "comb (GPS)"),
               {"lock": cmd_lock, "params": cmd_params, "status": cmd_status})


if __name__ == "__main__":
    sys.exit(main())
