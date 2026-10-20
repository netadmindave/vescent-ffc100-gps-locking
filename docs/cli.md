# Command-line tool: `vescent-comb-cli`

Everything the application does with instruments, from a terminal or a script — no GUI needed.

* Instruments are opened from the roles the GUI saved (Devices… → "Remember these assignments"); nothing is
  scanned unless you run `scan`.
* An instrument another bench application has connected is refused (`in use by …`), never probed.
* Exiting leaves every instrument exactly as it is.
* `--sim` runs against the simulator; `--json` gives machine-readable output (exit code 0 = success,
  1 = error, 2 = not locked / lock failed).

## Quick reference

| Command | What it does |
|---|---|
| `vescent-comb-cli roles` | roles, saved instruments, and whether another app has them |
| `vescent-comb-cli scan [--save]` | probe every port; `--save` remembers the assignments |
| `vescent-comb-cli info ROLE` | identify the instrument and read it once |
| `vescent-comb-cli options ROLE [--group TEXT]` | list the instrument's settings (keys, kinds, choices, units) |
| `vescent-comb-cli get ROLE [KEY ...]` | read settings (all of them without keys) |
| `vescent-comb-cli set ROLE KEY VALUE` | write a setting; prints the read-back |
| `vescent-comb-cli do ROLE ACTION` | run an action setting |
| `vescent-comb-cli poll ROLE [--every S] [--count N] [--csv FILE]` | log readings (`--count 0` = until Ctrl+C) |
| `vescent-comb-cli status` | are f_ceo, OPL #1 and the slow servo locked? (exit 0 = yes, 2 = no) |
| `vescent-comb-cli params` | the lock parameters and their defaults (JSON) |
| `vescent-comb-cli lock [--params FILE] [--set K=V] [--dry-run] [--yes]` | run the comb lock sequence |

Values: `on`/`off`/`true`/`false`, numbers with SI suffixes (`10M`, `1.5m`, `2e-6`, `50MHz`), or a choice
(short or long form, e.g. `HANN` or `HANNing`).

## Examples

```bat
vescent-comb-cli roles
vescent-comb-cli status
vescent-comb-cli params > lock.json            (edit, then:)
vescent-comb-cli lock --params lock.json --yes
vescent-comb-cli lock --set relock_tries=5 --set fceo_max_phase_rad=1.2 --yes
vescent-comb-cli get fpga
vescent-comb-cli poll opl1 --every 1 --count 0 --csv opl1.csv
vescent-comb-cli --sim lock --yes                (try it on the simulator)
```

## Complete command reference (`vescent-comb-cli -h`)

```text
usage: vescent-comb-cli [-h] [--sim] [--settings SETTINGS] [--json]
                        {roles,scan,info,options,get,set,do,poll,lock,params,status}
                        ...

Vescent FFC-100 GPS locking (Vescent Comb) — command line. Instruments come
from the roles the GUI saved; nothing is scanned unless you ask.

positional arguments:
  {roles,scan,info,options,get,set,do,poll,lock,params,status}
    roles               list roles, their saved instruments and whether
                        another app has them
    scan                probe every port and show what was found
    info                identify an instrument and read it once
    options             list an instrument's settings
    get                 read settings (all of them if no keys are given)
    set                 write one setting; prints the read-back
    do                  run an action setting (e.g. a preset)
    poll                read an instrument repeatedly
    lock                run the lock sequence (blocking; Ctrl+C stops it)
    params              print the lock parameters with their defaults (JSON)
    status              is it locked right now? (exit code 0 = locked, 2 =
                        not)

options:
  -h, --help            show this help message and exit
  --sim                 use the simulated bench (no hardware)
  --settings SETTINGS   settings file (default: the GUI's)
  --json                machine-readable output
```

### `vescent-comb-cli roles`

```text
usage: vescent-comb-cli roles [-h]

options:
  -h, --help  show this help message and exit
```

### `vescent-comb-cli scan`

```text
usage: vescent-comb-cli scan [-h] [--save]

options:
  -h, --help  show this help message and exit
  --save      remember the role assignments (like the GUI)
```

### `vescent-comb-cli info`

```text
usage: vescent-comb-cli info [-h] role

positional arguments:
  role

options:
  -h, --help  show this help message and exit
```

### `vescent-comb-cli options`

```text
usage: vescent-comb-cli options [-h] [--group GROUP] role

positional arguments:
  role

options:
  -h, --help     show this help message and exit
  --group GROUP  only groups containing this text
```

### `vescent-comb-cli get`

```text
usage: vescent-comb-cli get [-h] role [keys ...]

positional arguments:
  role
  keys

options:
  -h, --help  show this help message and exit
```

### `vescent-comb-cli set`

```text
usage: vescent-comb-cli set [-h] role key value

positional arguments:
  role
  key
  value       on/off, a number (SI suffixes: 10M, 1.5m …) or a choice

options:
  -h, --help  show this help message and exit
```

### `vescent-comb-cli do`

```text
usage: vescent-comb-cli do [-h] role action

positional arguments:
  role
  action

options:
  -h, --help  show this help message and exit
```

### `vescent-comb-cli poll`

```text
usage: vescent-comb-cli poll [-h] [--every EVERY] [--count COUNT] [--csv CSV]
                             role

positional arguments:
  role

options:
  -h, --help     show this help message and exit
  --every EVERY  seconds between readings (default 1)
  --count COUNT  number of readings, 0 = until Ctrl+C (default 1)
  --csv CSV      also write the readings to this CSV file
```

### `vescent-comb-cli lock`

```text
usage: vescent-comb-cli lock [-h] [--params PARAMS] [--set KEY=VALUE]
                             [--dry-run] [--yes]

options:
  -h, --help       show this help message and exit
  --params PARAMS  JSON file with lock parameters (see: params)
  --set KEY=VALUE  override one parameter (repeatable)
  --dry-run        check everything, change nothing
  --yes            answer yes to every question
```

### `vescent-comb-cli params`

```text
usage: vescent-comb-cli params [-h]

options:
  -h, --help  show this help message and exit
```

### `vescent-comb-cli status`

```text
usage: vescent-comb-cli status [-h]

options:
  -h, --help  show this help message and exit
```
