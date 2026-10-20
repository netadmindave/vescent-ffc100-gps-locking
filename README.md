# Vescent FFC-100 GPS locking

Locks a **Vescent FFC-100** fiber frequency comb to GPS: f_rep through a **SLICE-OPL** referenced to a GPS-disciplined
10 MHz, and f_ceo with a **SLICE-FPGA-II** — as one guarded sequence, with a watchdog that keeps both locks.

Part of a three-application bench for comb-referenced heterodyne measurements (CREOL, UCF):

| Repository | Application |
|---|---|
| **Vescent FFC-100 GPS locking** (this) | comb and its locks (`vescent-comb`) |
| Tunable Laser Stabilization | locks a tunable laser to the comb (`laser-lock`) |
| Lab Tools Management | the other bench instruments (`lab-tools`) |

## Features

* One-button comb lock: pre-checks → f_ceo lock (phase < 1.5 rad) → cavity walk → OPL #1 and slow servo.
* Every step re-checks every lock made so far; faults are recovered and the sequence retried.
* Watchdog relocks after a lasting fault (at most 6 per hour).
* Pages for the FFC-100, SLICE-FPGA-II (profile vs box, input spectrum, baseband IQ, DAC0 monitor) and OPL #1
  (including servo auto-tune).
* Publishes the comb state in `comb_status.json` for Tunable Laser Stabilization.
* Command-line tool and Python API; a full simulator for trying everything without hardware.

## Quick start

```bat
python -m pip install -e .
vescent-comb            (or: vescent-comb --sim)
vescent-comb-cli status
```

## Documentation

* [Installation](docs/installation.md) · [User guide](docs/user-guide.md) · [Configuration](docs/configuration.md)
* [Command-line tool](docs/cli.md) · [Python API guide](docs/api.md) · [API reference](docs/api-reference.md)
* [Instruments](docs/instruments.md) · [Architecture](docs/architecture.md) · [Troubleshooting](docs/troubleshooting.md)
* [Development](docs/development.md) · [Changelog](CHANGELOG.md)

## License

BSD 3-Clause — see [LICENSE](LICENSE) and [NOTICE](NOTICE.md) (third-party names; SLICE-FPGA-II code origin).
