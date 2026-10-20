# Architecture

```
vescentcomb/
  core/        Device base class, serial and VISA I/O (thread-safe), declarative options (Opt), units
  addonkit/    add-on registry: devices, roles, pages, windows, probes, references, simulators
  addons/      the instrument and process modules (built in: `comb_lock`)
  gui/         main window, Devices dialog, one worker thread per instrument, plots, widgets, log
  sim/         simulator world: every instrument model answers the real command set
  discovery.py scanning, probing, role assignment by serial number
  datafile.py  CSV with metadata header
  cli.py       command-line tool
```

**One worker thread per instrument.** Every instrument call runs on its own worker; results come back to the
GUI through Qt signals. A slow or hung instrument never freezes the window, and helpers that need several
commands run as one transaction under the instrument's I/O lock.

**Declarative options.** Each driver lists its settings as `Opt` entries (key, label, group, kind, query,
write, choices, unit, range). The Setup tabs, `get`/`set` in the CLI and `read_option`/`write_option` in
scripts all come from that one list; every write is read back.

**Add-ons.** Instruments and processes register through `register(api)`: `add_device`, `add_role`,
`add_page`, `add_window`, `add_serial_probe`, `add_visa_classifier`, `add_visa_probe`, `add_opener`,
`add_reference`, `add_summary`, `on_connect`, `add_sim`. This application has one built-in module (`comb_lock`) and no add-on manager.

**Simulator.** `--sim` replaces serial ports, VISA and Bluetooth with models that speak each instrument's real
protocol, so the whole application and all tests run without hardware.

**Closing leaves instruments as they are.** Nothing is switched off, reset or preset on exit; the application can
reconnect later and carry on.
