# Python API guide

Everything the GUI does is available to scripts. The full list of modules, classes and methods is in
[api-reference.md](api-reference.md); this page shows the imports you need and the common tasks.

## Imports

```python
from vescentcomb import discovery              # find, open and connect instruments
from vescentcomb.settings import Settings      # the application's settings file
from vescentcomb.addonkit import load, REGISTRY
comb = load("comb_lock")                       # the comb module: drivers, lock sequence, watchdog
from vescentcomb import sim                    # simulator (sim.install())
from vescentcomb.datafile import write_csv, read_csv
from vescentcomb.core.units import eng         # engineering formatting
```

`comb` exposes the drivers (`comb.FFC100`, `comb.SliceFPGA`, `comb.SliceOPL`), the lock (`comb.LockSequence`,
`comb.LockParams`) and the auto-tune (`comb.AutoTuner`, `comb.TuneConfig`). The watchdog and the lock check are in
`gps_lock`: `from vescentcomb_addons.comb_lock.gps_lock import LockWatchdog, lock_problems`.

## Connect

```python
with discovery.connect_all() as bench:          # saved roles first, then a scan; closes on exit
    ffc, fpga, opl1 = bench.devices["ffc"], bench.devices["fpga"], bench.devices["opl1"]
    print(ffc.identify(), opl1.poll())
```

`connect_all(settings=None, roles=None, remember=True)` — `roles=["ffc"]` opens just those.

## Read and write settings

```python
print([o.key for o in opl1.options()])          # every setting this driver knows
opl1.read_option("pll_gain_db")
opl1.write_option("pll_gain_db", -50)           # returns the read-back value
```

## Run the comb lock

```python
p = comb.LockParams(relock_tries=5, fceo_max_phase_rad=1.2)
seq = comb.LockSequence(bench.devices, p, Settings().get("profiles.fpga", {}),
                        on_step=lambda s: print(s.id, s.status, s.detail), ask=lambda q, rows=None: True)
ok = seq.run()                                 # or seq.start() for a background thread; seq.stop()
```

## Check the locks

```python
from vescentcomb_addons.comb_lock.gps_lock import lock_problems
problems = lock_problems(bench.devices, comb.LockParams(), {"fceo": True, "opl1": True, "slow": True})
print("locked" if not problems else problems)
```

## Simulator

```python
from vescentcomb import sim
sim.install()                                  # before connect_all(): every instrument is simulated
```
