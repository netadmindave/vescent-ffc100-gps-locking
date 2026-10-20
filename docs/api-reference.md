# API reference — `vescentcomb`

Generated from the source by importing every module: each public class, function and method with its signature and the first paragraph of its docstring. Built-in add-ons are listed under `vescentcomb_addons.<id>`, the name scripts import them by (after the add-on loader has run, e.g. via `vescentcomb.discovery.connect_all()` or `vescentcomb.addonkit.load_enabled()`).

## Modules

- [`vescentcomb.addonkit.api`](#vescentcomb-addonkit-api)
- [`vescentcomb.addonkit.installer`](#vescentcomb-addonkit-installer)
- [`vescentcomb.addonkit.loader`](#vescentcomb-addonkit-loader)
- [`vescentcomb.addonkit.manifest`](#vescentcomb-addonkit-manifest)
- [`vescentcomb.addonkit.registry`](#vescentcomb-addonkit-registry)
- [`vescentcomb.cli`](#vescentcomb-cli)
- [`vescentcomb.comb_status`](#vescentcomb-comb-status)
- [`vescentcomb.core.base`](#vescentcomb-core-base)
- [`vescentcomb.core.options`](#vescentcomb-core-options)
- [`vescentcomb.core.serialio`](#vescentcomb-core-serialio)
- [`vescentcomb.core.units`](#vescentcomb-core-units)
- [`vescentcomb.core.visaio`](#vescentcomb-core-visaio)
- [`vescentcomb.datafile`](#vescentcomb-datafile)
- [`vescentcomb.discovery`](#vescentcomb-discovery)
- [`vescentcomb.dsp`](#vescentcomb-dsp)
- [`vescentcomb.gui.app`](#vescentcomb-gui-app)
- [`vescentcomb.gui.cards`](#vescentcomb-gui-cards)
- [`vescentcomb.gui.connections`](#vescentcomb-gui-connections)
- [`vescentcomb.gui.log_window`](#vescentcomb-gui-log-window)
- [`vescentcomb.gui.main_window`](#vescentcomb-gui-main-window)
- [`vescentcomb.gui.options_panel`](#vescentcomb-gui-options-panel)
- [`vescentcomb.gui.page_base`](#vescentcomb-gui-page-base)
- [`vescentcomb.gui.pages.overview`](#vescentcomb-gui-pages-overview)
- [`vescentcomb.gui.plots`](#vescentcomb-gui-plots)
- [`vescentcomb.gui.reference_panel`](#vescentcomb-gui-reference-panel)
- [`vescentcomb.gui.theme`](#vescentcomb-gui-theme)
- [`vescentcomb.gui.widgets`](#vescentcomb-gui-widgets)
- [`vescentcomb.gui.windows.base`](#vescentcomb-gui-windows-base)
- [`vescentcomb.gui.worker`](#vescentcomb-gui-worker)
- [`vescentcomb.settings`](#vescentcomb-settings)
- [`vescentcomb.sim.base`](#vescentcomb-sim-base)
- [`vescentcomb.sim.fakeio`](#vescentcomb-sim-fakeio)
- [`vescentcomb.sim.world`](#vescentcomb-sim-world)
- [`vescentcomb_addons.comb_lock`](#vescentcomb-addons-comb-lock)
- [`vescentcomb_addons.comb_lock.autotune`](#vescentcomb-addons-comb-lock-autotune)
- [`vescentcomb_addons.comb_lock.ffc100`](#vescentcomb-addons-comb-lock-ffc100)
- [`vescentcomb_addons.comb_lock.fpga.controller`](#vescentcomb-addons-comb-lock-fpga-controller)
- [`vescentcomb_addons.comb_lock.fpga.monitor`](#vescentcomb-addons-comb-lock-fpga-monitor)
- [`vescentcomb_addons.comb_lock.fpga.pll_modules`](#vescentcomb-addons-comb-lock-fpga-pll-modules)
- [`vescentcomb_addons.comb_lock.fpga.rp_pll`](#vescentcomb-addons-comb-lock-fpga-rp-pll)
- [`vescentcomb_addons.comb_lock.fpga.simulator`](#vescentcomb-addons-comb-lock-fpga-simulator)
- [`vescentcomb_addons.comb_lock.fpga.superlaserland`](#vescentcomb-addons-comb-lock-fpga-superlaserland)
- [`vescentcomb_addons.comb_lock.gps_lock`](#vescentcomb-addons-comb-lock-gps-lock)
- [`vescentcomb_addons.comb_lock.overview`](#vescentcomb-addons-comb-lock-overview)
- [`vescentcomb_addons.comb_lock.pages.ffc`](#vescentcomb-addons-comb-lock-pages-ffc)
- [`vescentcomb_addons.comb_lock.pages.fpga`](#vescentcomb-addons-comb-lock-pages-fpga)
- [`vescentcomb_addons.comb_lock.pages.lock_sequence`](#vescentcomb-addons-comb-lock-pages-lock-sequence)
- [`vescentcomb_addons.comb_lock.pages.opl`](#vescentcomb-addons-comb-lock-pages-opl)
- [`vescentcomb_addons.comb_lock.sim`](#vescentcomb-addons-comb-lock-sim)
- [`vescentcomb_addons.comb_lock.slicefpga`](#vescentcomb-addons-comb-lock-slicefpga)
- [`vescentcomb_addons.comb_lock.sliceopl`](#vescentcomb-addons-comb-lock-sliceopl)

## `vescentcomb.addonkit.api`

The object every add-on's ``register(api)`` receives.

```python
from vescentcomb.addonkit import api
```

### class `AddonAPI(info, registry=Registry(addons={comb_lock: AddonInfo(id=comb_lock, name=Comb lock, path=PosixPath('/home/claude/w/vescentcomb/vescentcomb/addons/comb_lock'), version='1.1.0', type=module, category=Modules, description='FFC-100 comb, GPS OPL #1 (f_rep), SLICE-FPGA-II (f_ceo), the comb lock sequence and the lock watchdog.', author=Dave Smith, requires=['pyserial>=3.5', 'scipy>=1.7'], depends=[], optional=[], vescentcomb='', entry=register, default_enabled=True, builtin=True, enabled=True, state=loaded, error='', missing=[], overrides_builtin=False)}, roles={ffc: RoleSpec(role=ffc, label='FFC-100 comb', kinds=[ffc100], addon=comb_lock, capabilities=(), poll_s=1.0, bench_row=False, order=10), fpga: RoleSpec(role=fpga, label='SLICE-FPGA-II', kinds=[slicefpga], addon=comb_lock, capabilities=(), poll_s=1.0, bench_row=False, order=11), opl1: RoleSpec(role=opl1, label='OPL #1 · f_rep → GPS', kinds=[sliceopl], addon=comb_lock, capabilities=(opl,), poll_s=1.0, bench_row=False, order=12)}, drivers={ffc100: DriverSpec(kind=ffc100, cls=<class vescentcomb_addons.comb_lock.ffc100.FFC100>, label='Vescent FFC-100', addon=comb_lock, package=vescentcomb_addons.comb_lock), sliceopl: DriverSpec(kind=sliceopl, cls=<class vescentcomb_addons.comb_lock.sliceopl.SliceOPL>, label='Vescent SLICE-OPL', addon=comb_lock, package=vescentcomb_addons.comb_lock), slicefpga: DriverSpec(kind=slicefpga, cls=<class vescentcomb_addons.comb_lock.slicefpga.SliceFPGA>, label='Vescent SLICE-FPGA-II', addon=comb_lock, package=vescentcomb_addons.comb_lock)}, serial_probes=[SerialProbe(name='Vescent *IDN?', match=<function _vescent_port>, probe=<function _probe_vescent>, exclusive=False, priority=60, addon=comb_lock)], visa_classifiers=[], visa_probes=[], scanners=[Scanner(name=slicefpga, label='SLICE-FPGA-II UDP discovery (port 1952)', scan=<function _scan_fpga>, addon=comb_lock)], openers={ffc100: <function AddonAPI.serial_opener.<locals>.open_ at 0x7fcadcd463e0>, sliceopl: <function AddonAPI.serial_opener.<locals>.open_ at 0x7fcad7794400>, slicefpga: <function _open_fpga>}, on_connect={}, pages=[UISpec(key=combseq, label=Comb lock sequence, cls='pages.lock_sequence:LockSequencePage', role=None, section=COMB LOCK, order=10, addon=comb_lock, package=vescentcomb_addons.comb_lock), UISpec(key=ffc, label='FFC-100 comb', cls='pages.ffc:FFCPage', role=ffc, section=COMB LOCK, order=11, addon=comb_lock, package=vescentcomb_addons.comb_lock), UISpec(key=fpga, label='SLICE-FPGA-II', cls='pages.fpga:FPGAPage', role=fpga, section=COMB LOCK, order=12, addon=comb_lock, package=vescentcomb_addons.comb_lock), UISpec(key=opl1, label='SLICE-OPL #1 · GPS', cls='pages.opl:OPLPage', role=opl1, section=COMB LOCK, order=13, addon=comb_lock, package=vescentcomb_addons.comb_lock)], windows=[], overview=[UISpec(key=ffc, label=card, cls='overview:FFCCard', role=None, section='', order=10, addon=comb_lock, package=vescentcomb_addons.comb_lock), UISpec(key=fpga, label=card, cls='overview:FPGACard', role=None, section='', order=11, addon=comb_lock, package=vescentcomb_addons.comb_lock), UISpec(key=opl1, label=card, cls='overview:OPL1Card', role=None, section='', order=12, addon=comb_lock, package=vescentcomb_addons.comb_lock), UISpec(key=comb_trends, label=wide, cls='overview:CombTrends', role=None, section='', order=50, addon=comb_lock, package=vescentcomb_addons.comb_lock)], chain=[ChainSpec(key=gps, caption=GPS 10 MHz, role=opl1, update=<function _pill_gps>, order=10, addon=comb_lock), ChainSpec(key=ffc, caption='FFC-100', role=ffc, update=<function _pill_ffc>, order=11, addon=comb_lock), ChainSpec(key=ceo, caption='f_ceo · FPGA', role=fpga, update=<function _pill_ceo>, order=12, addon=comb_lock), ChainSpec(key=frep, caption='f_rep → GPS · OPL #1', role=opl1, update=<function _pill_frep>, order=13, addon=comb_lock)], safe_standby=[], summaries={}, sim_hooks=[(<function AddonAPI.add_sim.<locals>.<lambda> at 0x7fcad758a3e0>, comb_lock)], menu_actions=[], references=[RefSpec(role=opl1, input='REF IN (GPS 10 MHz)', mode=always, status=<function _ref_ok>, option=None, detail=<function register.<locals>.<lambda> at 0x7fcad758a200>, note=reference measured by the OPL, addon=comb_lock), RefSpec(role=fpga, input='external clock (20 MHz from GPS)', mode=status, status=<function register.<locals>.<lambda> at 0x7fcad758a2a0>, option=None, detail=<function register.<locals>.<lambda> at 0x7fcad758a340>, note='', addon=comb_lock)]))`

- `add_device(self, kind: str, cls, label: str = '') -> None` — An instrument driver class (subclass of vescentcomb.Device).
- `add_role(self, role: str, label: str, kinds: Iterable[str], capabilities: Iterable[str] = (), poll_s: Any = 1.0, bench_row: bool = False, order: int = 100) -> None` — A job on the bench ("opl2", "scope", "sa"…). Calling it again for an existing role adds kinds, so a second add-on can plug a new instrument model into a role another add-on owns.
- `add_serial_probe(self, name: str, match: Callable, probe: Callable, exclusive: bool = False, priority: int = 50) -> None` — Identify a USB-serial port. ``match(PortInfo)`` decides from VID/PID only (no bytes sent).
- `add_visa_classifier(self, fn: Callable[[str], Optional[str]]) -> None` — ``fn(idn_string) -> kind | None`` for instruments that answer *IDN?.
- `add_visa_probe(self, name: str, probe: Callable, priority: int = 50) -> None` — For GPIB instruments that do NOT answer *IDN? (``probe(inst, resource, bus, opts)``).
- `add_scanner(self, name: str, label: str, scan: Callable) -> None` — Anything that isn't serial or VISA (Ethernet discovery, a drive, …).
- `add_opener(self, kind: str, fn: Callable) -> None` — How to open a found instrument. Serial instruments use ``serial_opener``; VISA ones need none.
- `on_connect(self, kind: str, fn: Callable[[Any, Any], None]) -> None` — Called with (device, settings) right after the GUI opens an instrument of this kind.
- `add_safe_standby(self, role: str, description: str) -> None` — Safe standby / quit call ``safe_state()`` on this role (laser output off, emission off …).
- `add_page(self, key: str, label: str, cls, role: Optional[str] = None, section: str = '', order: int = 100) -> None` — A page in the main window's navigation (``cls`` subclasses vescentcomb.gui.page_base.Page).
- `add_window(self, key: str, label: str, cls, role: Optional[str] = None, order: int = 100) -> None` — A separate instrument window (``cls`` subclasses vescentcomb.gui.windows.base.InstrumentWindow).
- `add_overview_panel(self, key: str, cls, span: str = card, order: int = 100) -> None` — A panel on the Overview page. ``span`` is "card" (one grid cell) or "wide" (full row).
- `add_chain_pill(self, key: str, caption: str, role: str, update: Callable, order: int = 100) -> None` — A status pill in the top lock-chain bar, updated from ``role``'s polls.
- `add_summary(self, role: str, fn: Callable[[Dict[str, Any]], str]) -> None` — One-line live summary for the Overview "Bench instruments" table.
- `add_reference(self, role: str, input: str, mode: str = switch, status=None, option: Optional[str] = None, detail=None, note: str = '') -> None` — Declare how ``role`` uses the 10 MHz (GPS) reference, for the Overview reference list.
- `add_menu_action(self, menu: str, label: str, fn: Callable[[Any], None]) -> None` — An entry in the main menu bar; ``fn(main_window)``.
- `add_sim(self, fn) -> None` — ``fn(world)`` adds this add-on's simulated instruments (``"sim:install"`` string is fine).
- `resolve(self, spec)`
- static `serial_opener(cls, baudrate: int = 115200, timeout: float = 1.0, **kw) -> Callable` — Opener for drivers whose constructor takes ``(port, ser=...)``.

## `vescentcomb.addonkit.installer`

Requirement checks and pip installs for add-ons.

```python
from vescentcomb.addonkit import installer
```

### `is_satisfied(req: str) -> bool`

True when the distribution is installed (and the version matches, when packaging is available).

### `missing(reqs: List[str]) -> List[str]`

### `pip_command(reqs: List[str]) -> List[str]`

### `pip_install(reqs: List[str], log: Optional[Callable[[str], None]] = None, timeout: float = 900) -> Tuple[bool, str]`

Install with the same Python that runs vescentcomb. Returns (ok, combined output).

## `vescentcomb.addonkit.loader`

Find add-on folders, check/install their requirements, import them and call ``register(api)``.

```python
from vescentcomb.addonkit import loader
```

**Constants:** `NAMESPACE`

### `addon_dirs(settings=None) -> List[Path]`

### `create_from_template(dest_dir: Path, addon_id: str, name: str, cls_name: str = '', role: str = '', kind: str = '') -> Path`

Copy the template add-on to ``dest_dir/addon_id`` with names filled in.

### `default_user_dir() -> Path`

### `ensure_loaded(settings=None, **kw) -> None`

Load the enabled add-ons once per process (scripts get this through discovery). Without ``settings`` the user's settings file decides which add-ons are on, as in the GUI.

### `last_scan() -> Dict[str, AddonInfo]`

### `load(addon_id: str, settings=None, auto_install: bool = True, log=<built-in function print>)`

Load one add-on (and what it depends on) even if it is unchecked; return its package.

### `load_enabled(settings=None, auto_install: Optional[bool] = None, installer=None, log=None, include_all: bool = False, only: Optional[Iterable[str]] = None) -> Dict[str, AddonInfo]`

Load every enabled add-on (dependencies first). ``include_all`` ignores the checkboxes.

### `load_one(info: AddonInfo, settings=None, auto_install: bool = True, installer=None, log: Optional[Callable[[str], None]] = None) -> AddonInfo`

### `reset() -> None`

Forget every loaded add-on (tests, or before a reload).

### `scan(settings=None) -> Dict[str, AddonInfo]`

Read every manifest (no add-on code is imported). Returns {id: AddonInfo} in display order.

### `user_dirs(settings=None) -> List[Path]`

## `vescentcomb.addonkit.manifest`

Add-on manifests (``addon.toml``) — read without importing any add-on code.

```python
from vescentcomb.addonkit import manifest
```

**Constants:** `MANIFEST`

### class `AddonInfo(id: str, name: str, path: Path, version: str = '0.0.0', type: str = tool, category: str = Instruments, description: str = '', author: str = '', requires: List[str] = <factory>, depends: List[str] = <factory>, optional: List[str] = <factory>, vescentcomb: str = '', entry: str = register, default_enabled: bool = True, builtin: bool = False, enabled: bool = False, state: str = not loaded, error: str = '', missing: List[str] = <factory>, overrides_builtin: bool = False) -> None`

Everything the manager shows about one add-on folder.

- `module_name` *(property)*
- `label` *(property)*

### `load_toml(path: Path) -> Dict[str, Any]`

### `read_manifest(folder: Path, builtin: bool = False) -> Optional[AddonInfo]`

## `vescentcomb.addonkit.registry`

What the loaded add-ons contribute. The shell (discovery, GUI, simulator) reads only this.

```python
from vescentcomb.addonkit import registry
```

### class `ChainSpec(key: str, caption: str, role: str, update: Callable[[Dict[str, Any], Any], Optional[Tuple[str, str]]], order: int = 100, addon: str = '') -> None`


### class `DriverSpec(kind: str, cls: Any, label: str, addon: str = '', package: str = '') -> None`

- `get(self)`

### class `RefSpec(role: str, input: str, mode: str = switch, status: Optional[Callable[[Dict[str, Any]], Optional[bool]]] = None, option: Optional[str] = None, detail: Optional[Callable[[Dict[str, Any]], str]] = None, note: str = '', addon: str = '') -> None`

How one instrument uses the shared 10 MHz (GPS) reference — shown in the Overview list.


### class `Registry(addons: Dict[str, Any] = <factory>, roles: Dict[str, RoleSpec] = <factory>, drivers: Dict[str, DriverSpec] = <factory>, serial_probes: List[SerialProbe] = <factory>, visa_classifiers: List[Tuple[Callable[[str], Optional[str]], str]] = <factory>, visa_probes: List[VisaSilentProbe] = <factory>, scanners: List[Scanner] = <factory>, openers: Dict[str, Callable[[Any], Any]] = <factory>, on_connect: Dict[str, List[Callable[[Any, Any], None]]] = <factory>, pages: List[UISpec] = <factory>, windows: List[UISpec] = <factory>, overview: List[UISpec] = <factory>, chain: List[ChainSpec] = <factory>, safe_standby: List[Tuple[str, str]] = <factory>, summaries: Dict[str, Callable[[Dict[str, Any]], str]] = <factory>, sim_hooks: List[Tuple[Callable[[Any], None], str]] = <factory>, menu_actions: List[Tuple[str, str, Callable[[Any], None], str]] = <factory>, references: List[RefSpec] = <factory>) -> None`

- `clear(self)`
- `roles_for_kind(self, kind: str) -> List[str]`
- `roles_with(self, capability: str) -> List[str]`
- `driver(self, kind: str)`
- `role_label(self, role: str) -> str`

### class `RoleSpec(role: str, label: str, kinds: List[str], addon: str = '', capabilities: Tuple[str, ...] = (), poll_s: Any = 1.0, bench_row: bool = False, order: int = 100) -> None`

- `poll_interval(self, settings) -> float`

### class `Scanner(name: str, label: str, scan: Callable[[Any], List[Any]], addon: str = '') -> None`


### class `SerialProbe(name: str, match: Callable[[Any], bool], probe: Callable[[Any, Any], Any], exclusive: bool = False, priority: int = 50, addon: str = '') -> None`


### class `UISpec(key: str, label: str, cls: Any, role: Optional[str] = None, section: str = '', order: int = 100, addon: str = '', package: str = '') -> None`

- `get(self)`

### class `VisaSilentProbe(name: str, probe: Callable[..., Any], priority: int = 50, addon: str = '') -> None`


### `resolve(spec, package: str)`

'module:Name' relative to an add-on package -> object (or pass objects through).

## `vescentcomb.cli`

Vescent FFC-100 GPS locking (Vescent Comb) — command-line tool.

```python
from vescentcomb import cli
```

**Constants:** `COMMANDS`, `EXIT_ERROR`, `EXIT_FAILED`, `EXIT_OK`

### class `Ctx(args)`

- `out(self, obj, text: Optional[str] = None)`
- `found_for(self, role: str)` — The saved instrument for ``role`` (no scan); in --sim mode, or if nothing is saved, a scan.
- `open(self, role: str)`
- `close(self)`

### `build_parser(extra=None) -> argparse.ArgumentParser`

### `cmd_do(ctx, a)`

### `cmd_get(ctx, a)`

### `cmd_info(ctx, a)`

### `cmd_lock(ctx, a)`

### `cmd_options(ctx, a)`

### `cmd_params(ctx, a)`

### `cmd_poll(ctx, a)`

### `cmd_roles(ctx, a)`

### `cmd_scan(ctx, a)`

### `cmd_set(ctx, a)`

### `cmd_status(ctx, a)`

### `main(argv=None) -> int`

### `run(argv=None, extra_parsers=None, extra_commands=None) -> int`

## `vescentcomb.comb_status`

Comb status file: what the Laser Lock application reads to know the comb is locked.

```python
from vescentcomb import comb_status
```

**Constants:** `FILENAME`

### class `StatusWriter(hub, settings, period_s: float = 1.0)`

- `snapshot(self) -> Dict[str, Any]`
- `write(self)`

## `vescentcomb.core.base`

Common base for every instrument driver.

```python
from vescentcomb.core import base
```

### class `Device() -> None`

Base class. Subclasses set ``KIND`` and implement the hooks below.

- `close(self) -> None`
- `safe_state(self) -> None` — Put the instrument in a state that is safe to walk away from.
- `identify(self) -> Identity`
- `snapshot(self) -> Dict[str, Any]`
- `poll(self) -> Dict[str, Any]` — Fast status read used by the GUI at ~1 Hz. Defaults to snapshot().
- `restore(self, snap: Dict[str, Any], keys: Optional[Iterable[str]] = None) -> Dict[str, str]` — Write back restorable settings from a snapshot.
- `diff(self, saved: Dict[str, Any], keys: Optional[Iterable[str]] = None, rel_tol: float = 1e-09) -> Dict[str, tuple]` — Compare live settings against a saved snapshot -> {key: (live, saved)}.
- class `find(cls, serial: Optional[str] = None, **kw)` — Locate this instrument (by USB ID / *IDN? / serial) and open it.

### class `DeviceError(…)`

Instrument did not respond, rejected a command, or returned garbage.

### class `Identity(kind: str, model: str = '', serial: str = '', firmware: str = '', raw: str = '', extra: Dict[str, Any] = <factory>) -> None`

- `as_dict(self) -> Dict[str, Any]`
- `key` *(property)* — Stable key used to match a physical unit to a role.

### class `SafetyError(…)`

A request was refused because it would violate a hard safety rule.

## `vescentcomb.core.options`

Declarative instrument options.

```python
from vescentcomb.core import options
```

### class `Opt(key: str, label: str, group: str = General, kind: str = number, get: Getter = None, set: Setter = None, choices: Sequence = (), unit: str = '', lo: Optional[float] = None, hi: Optional[float] = None, tip: str = '', bools: Tuple[str, str] = (ON, OFF), parse: Optional[Callable[[str], Any]] = None, scale: float = 1.0, indexed: bool = False) -> None`

- `readonly` *(property)*
- `pairs(self) -> List[Tuple[str, Any]]`
- `convert(self, raw: Any) -> Any` — Instrument reply → Python value of this option's kind.
- `encode(self, value: Any) -> str` — Python value → text substituted for ``{v}`` in a SCPI ``set`` string.

### class `OptionsMixin()`

Mixed into :class:`vescentcomb.core.base.Device`. Override ``options()`` for dynamic tables.

- `options(self) -> List[Opt]`
- `option(self, key: str) -> Opt`
- `option_query(self, cmd: str) -> Optional[str]`
- `option_write(self, cmd: str) -> None`
- `read_option(self, key: str) -> Any`
- `write_option(self, key: str, value: Any = None, readback: bool = True) -> Any`
- `read_options(self, keys: Optional[Iterable[str]] = None, group: Optional[str] = None) -> Dict[str, Any]`

### `match_choice(raw: Any, values: Iterable[Any]) -> Any`

Map an instrument reply onto one of ``values`` (exact, numeric, or SCPI short/long form).

## `vescentcomb.core.serialio`

Serial helpers: an ASCII line transport and a port lister.

```python
from vescentcomb.core import serialio
```

### class `PortInfo(device: str, description: str = '', hwid: str = '', vid: Optional[int] = None, pid: Optional[int] = None, serial_number: str = '', manufacturer: str = '') -> None`

- `is_bluetooth` *(property)*
- `usb_family` *(property)* — Rough chip family from the USB vendor ID.

### class `SerialLine(port: Optional[str] = None, baudrate: int = 115200, timeout: float = 1.0, eol: str = '\r', quiet: float = 0.05, ser=None)`

Thread-safe ASCII command/response transport.

- `timeout` *(property)*
- `write(self, cmd: str) -> None`
- `read(self, timeout: Optional[float] = None) -> str` — Wait for the reply to begin, then drain until the line goes quiet.
- `query(self, cmd: str, timeout: Optional[float] = None) -> str`
- `close(self) -> None`
- `is_open` *(property)*

### `list_serial_ports() -> List[PortInfo]`

## `vescentcomb.core.units`

Small unit helpers shared by drivers and the GUI.

```python
from vescentcomb.core import units
```

**Constants:** `C_LIGHT`

### `ceil_125(val: float) -> float`

Smallest 1-2-5 value ≥ val.

### `dbm_to_w(dbm: float) -> float`

### `eng(value: float, unit: str = '', digits: int = 4) -> str`

Engineering notation in powers of three: eng(2.5e7,'Hz') -> '25 MHz'.

### `first_125_below(val: float) -> float`

Largest 1-2-5 step strictly below val.

### `nm_to_thz(nm: float) -> float`

### `seq_125(lo: float, hi: float)`

Every 1-2-5 value from lo to hi inclusive (scope V/div and s/div steps).

### `snap_125(val: float) -> float`

Nearest value on the 1-2-5 sequence.

### `snap_to_grid(value: float, step: float, origin: float = 0.0) -> float`

Nearest multiple of ``step`` (rounding up or down, whichever is closer).

### `thz_to_nm(thz: float) -> float`

### `w_to_dbm(w: float) -> float`

## `vescentcomb.core.visaio`

VISA helpers: a shared resource manager and a thread-safe instrument wrapper.

```python
from vescentcomb.core import visaio
```

### class `VisaInstrument(resource: Optional[str] = None, inst=None, timeout_ms: int = 5000, read_termination: Optional[str] = '\n', write_termination: str = '\n')`

Thin wrapper adding a lock, safe queries and timeout scoping.

- `write(self, cmd: str) -> None`
- `read(self) -> str`
- `query(self, cmd: str, timeout_ms: Optional[int] = None) -> str`
- `try_query(self, cmd: str, timeout_ms: Optional[int] = None) -> Optional[str]` — Query that returns None on timeout instead of raising.
- `query_float(self, cmd: str, timeout_ms: Optional[int] = None) -> Optional[float]`
- `read_raw(self) -> bytes`
- `query_binary_values(self, cmd: str, **kw)`
- `read_stb(self) -> int`
- `clear(self) -> None`
- `set_timeout(self, ms: int) -> None`
- `close(self) -> None`
- `sleep(self, s: float) -> None`

### `resource_manager(backend: Optional[str] = None)`

One ResourceManager per process (opening several confuses NI-VISA).

### `set_resource_manager(rm) -> None`

Inject a resource manager (used by the simulator).

## `vescentcomb.datafile`

Data files with the bench state in a header.

```python
from vescentcomb import datafile
```

### class `CSVLog(path: str, kind: str = log, meta: Optional[Dict[str, Any]] = None)`

Append-mode CSV (REC logs, scans): header written once when the file is created.

- `write(self, row: Dict[str, Any]) -> None`
- `close(self) -> None`

### `base_metadata(kind: str = '') -> Dict[str, Any]`

### `bench_metadata(bench) -> Dict[str, Any]`

Metadata for scripts: every open device's snapshot (read-only) under ``instruments``.

### `current_metadata(kind: str = '', extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`

### `header_lines(meta: Dict[str, Any]) -> List[str]`

``# key: value`` lines; nested values are JSON on one line.

### `read_header(path: str) -> Dict[str, Any]`

The ``# key: value`` header of a vescentcomb CSV back as a dict.

### `set_provider(fn: Optional[Callable[[], Dict[str, Any]]]) -> None`

Register a function returning the current bench state (the GUI does this).

### `write_csv(path: str, header: Sequence[str], columns: Optional[Sequence[Iterable]] = None, rows: Optional[Iterable[Sequence]] = None, kind: str = '', meta: Optional[Dict[str, Any]] = None, fmt: str = '{:.10g}') -> str`

Write a CSV with the metadata header. Give ``columns`` (one iterable per column) or ``rows``.

## `vescentcomb.discovery`

Find every instrument, identify it, and match it to its role by serial number.

```python
from vescentcomb import discovery
```

### class `Bench(devices: Dict[str, Any], scan: ScanResult, errors: Dict[str, str])`

Connected devices by role. ``bench.opl1``, ``bench.laser`` …

- `close(self) -> None` — Safe state + close for every device.

### class `Found(kind: str, address: str, bus: str, model: str = '', serial: str = '', firmware: str = '', how: str = '', raw: str = '', extra: Dict[str, Any] = <factory>, role: str = '', status: str = new, previous_address: str = '') -> None`

- `label` *(property)*
- `as_dict(self) -> Dict[str, Any]`

### class `Hooks()`

Indirection points so the simulator (or tests) can stand in for hardware.

- `reset(self)`
- `get(self, name: str, default=None)`
- `set(self, name: str, value) -> None`

### class `ScanOptions(skip_bluetooth: bool = True, serial: bool = True, visa: bool = True, serial_timeout: float = 0.5, visa_timeout_ms: int = 300, probe_exclusive_ports: bool = False, exclude: tuple = (), scanners: Dict[str, bool] = <factory>) -> None`


### class `ScanResult(found: List[Found] = <factory>, skipped: List[Found] = <factory>, unknown: List[Found] = <factory>, duration_s: float = 0.0, assignments: Dict[str, Found] = <factory>, missing: Dict[str, Dict[str, Any]] = <factory>) -> None`

- `by_kind(self, kind: str) -> List[Found]`

### `assign_roles(result: ScanResult, saved_roles: Optional[Dict[str, Dict[str, Any]]] = None) -> ScanResult`

Match found devices to roles: by (kind, serial) first, then by kind.

### `classify_idn(idn: str) -> Optional[str]`

### `connect_all(settings=None, opts: Optional[ScanOptions] = None, roles=None, remember: bool = True, progress=None) -> Bench`

Scan, match roles (by serial, from the settings file), open everything.

### `idn_query(port: str, eol: str, timeout: float, baudrate: int = 115200, quiet: float = 0.05) -> str`

``*IDN?`` on a serial port with the given line ending ('' on no reply).

### `open_found(f: Found) -> Any`

Open a found instrument with its add-on's opener (VISA instruments need none).

### `open_one(kind: str, serial: Optional[str] = None, opts: Optional[ScanOptions] = None)`

Scan and open the first instrument of ``kind`` (optionally with ``serial``).

### `probe_visa_resource(rm, res: str, opts: ScanOptions) -> Found`

### `remember_roles(result: ScanResult, settings) -> None`

### `reopen(f: Found) -> Any`

Open ``f`` again after it dropped off the bus (auto-reconnect).

### `scan_all(opts: Optional[ScanOptions] = None, progress: Optional[Callable[[str], None]] = None, already_open: Optional[List[Found]] = None) -> ScanResult`

``already_open``: Found records of devices this session has open; they are listed without being probed again (an open COM port cannot be re-opened).

### `scan_serial(opts: ScanOptions) -> Tuple[List[Found], List[Found], List[Found]]`

### `scan_visa(opts: ScanOptions) -> Tuple[List[Found], List[Found]]`

### `split_idn(idn: str) -> List[str]`

### `with_serial(port: str, baudrate: int, timeout: float, fn)`

Open ``port`` through the hook, run ``fn(ser)``, always close. Exceptions -> None.

## `vescentcomb.dsp`

Signal metrics shared by the beat check, auto-tune and frequency monitor.

```python
from vescentcomb import dsp
```

**Constants:** `FFT_UNITS`, `FFT_WINDOWS`

### `amplitude_spectrum(v: np.ndarray, dt: float, window: str = hann, unit: str = dBV, impedance: float = 50.0)`

Single-sided amplitude spectrum of a real record.

### `carrier_to_pedestal_db(f: np.ndarray, p_dbm: np.ndarray, f0: float, exclude_hz: float, pedestal_hz: float) -> float`

Carrier minus median pedestal level within ±pedestal_hz (higher is better).

### `integrated_phase_rms(v: np.ndarray, dt: float, f0: Optional[float] = None, band: Tuple[float, float] = (10.0, 1000000.0)) -> float`

RMS residual phase (rad) integrated over ``band`` (lower is better).

### `overlapping_adev(y_frac: Sequence[float], tau0: float, ms: Iterable[int] = (1, 2, 4, 8, 16))`

Overlapping Allan deviation of fractional-frequency samples.

### `peak_frequency_fft(v: np.ndarray, dt: float, fmin: float = 0.0, fmax: Optional[float] = None) -> float`

Dominant frequency: Hann window + parabolic interpolation (from the notebook).

### `quicklook(v: np.ndarray, dt: float, expected_hz: float, search_hz: float = 1000000.0)`

Sub-bin frequency estimate. Returns (f_hz, sigma_f_hz, snr_db).

### `residual_phase(v: np.ndarray, dt: float, f0: Optional[float] = None, lp_hz: Optional[float] = None) -> np.ndarray`

Demodulate at f0 and return the detrended, unwrapped phase (rad).

### `servo_bump_db(f: np.ndarray, p_dbm: np.ndarray, f0: float, inner_hz: float = 10000.0, outer_hz: float = 1000000.0) -> float`

Highest point in the servo-bump annulus relative to the carrier (lower is better).

## `vescentcomb.gui.app`

Entry point: ``python -m vescentcomb.gui [--sim] [--settings PATH] [--no-scan]``.

```python
from vescentcomb.gui import app
```

### `install_wheel_guard(app)`

Number fields and dropdowns never change with the mouse wheel; the wheel scrolls the page instead.

### `main(argv=None) -> int`

## `vescentcomb.gui.cards`

Reusable Overview building blocks for add-ons.

```python
from vescentcomb.gui import cards
```

### class `OverviewPanel(hub, settings, main=None, title: str = '', right=None)`

Base for anything placed on the Overview page by an add-on.

- `on_poll(self, role: str, d: Dict[str, Any]) -> None`
- `on_devices_changed(self) -> None`

### class `RoleCard(hub, settings, main=None)`

- `transform(self, d: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str]`
- `on_devices_changed(self)`
- `on_poll(self, role, d)`

## `vescentcomb.gui.connections`

Startup dialog: scan, show what was found, assign roles (by serial), connect.

```python
from vescentcomb.gui import connections
```

**Constants:** `STATUS`

### class `ConnectionsDialog(parent, settings, simulated: bool = False, already_open=None, identify_hook=None, failed=None, connected=None)`

- `options(self) -> ScanOptions`
- `rescan(self)`
- `chosen(self)` — role -> Found from the combo boxes (scanned, saved, already connected, or a port picked by hand).
- `disconnect_one(self, role)`
- `reconnect_one(self, role)`
- `connect_one(self, role)`
- `swap_opls(self)`
- `identify(self, role)`
- `offline(self)`

## `vescentcomb.gui.log_window`

Logs window: everything the app logs, for troubleshooting.

```python
from vescentcomb.gui import log_window
```

**Constants:** `COLORS`, `LEVELS`

### class `LogBuffer(maxlen: int = 20000)`

Process-wide log store (thread-safe enough: deque appends are atomic; Qt signal is queued).

- `open_file(self, folder: str)`
- `add(self, level: str, source: str, text: str)`

### class `LogWindow(settings=None)`

- `refill(self)`
- `copy(self)`
- `save(self)`

### `attach_hub(hub)`

Event log and device states from the GUI hub.

### `install(log_folder: str = '')`

Start capturing (call once, early).

## `vescentcomb.gui.main_window`

Main window shell: lock-chain bar, navigation, pages, status bar, instrument windows.

```python
from vescentcomb.gui import main_window
```

### class `ChainPill(caption: str)`

- `set(self, text: str, state: str)`

### class `MainWindow(settings, simulated: bool = False)`

- `page_specs` *(property)*
- `window_specs` *(property)*
- `show_page(self, key)`
- `open_window(self, key)`
- `startup(self)` — Connect the devices saved last time, at their saved addresses — no scan. Anything that does not answer is listed in the device finder with the free ports it could be on.
- `open_finder(self, failed=None)` — Device finder. It does not scan by itself: it shows the saved assignments and the free ports for each role; press Rescan to probe.
- `connect_found(self, chosen, scan, remember=True, opened=None, only=False, on_done=None, after=None)` — Connect ``chosen`` roles. Opening instruments (and their on-connect hooks) runs in a background thread, so a slow or hung port never freezes the window. ``only=True`` leaves other roles alone.
- `connect_role(self, role, f, on_done=None, after=None)` — Connect one role now (the device finder's per-device Connect button). ``after``: an Event to wait for first (the previous connection closing), waited for in the background.
- `disconnect_role(self, role)` — Close one role without touching the instrument; returns an Event set when it's closed.
- `assign_unit(self, role, kind, serial)` — Point ``role`` at the unit with ``serial`` (OPL / laser dropdowns).
- `open_logs(self)`
- `switch_to_sim(self)`
- `metadata(self)` — Bench state written into the header of every data file (vescentcomb.datafile).
- `after_lock_sequence(self)` — Pages re-read their instruments after a sequence changed them.
- `toggle_rec(self, on)`
- `safe_standby(self)`
- `open_data_folder(self)`
- `change_data_folder(self)`
- `restart(self)` — Close (instruments left exactly as they are) and start again.
- `closeEvent(self, e)` — Close and leave every instrument exactly as it is (outputs, locks, servos). The next start reconnects to the saved devices without changing them.

### `saved_found(role: str, s: dict)`

A discovery.Found rebuilt from a saved role entry (no scan).

## `vescentcomb.gui.options_panel`

Setup tab built from a driver's ``OPTIONS`` table (see vescentcomb.core.options).

```python
from vescentcomb.gui import options_panel
```

### class `OptionsPanel(hub, role: str, columns: int = 2, intro: str = '', groups: Optional[List[str]] = None, exclude_groups: Optional[List[str]] = None)`

- `refresh(self)`
- `showEvent(self, e)` — Options are read the first time the tab is actually shown, not when the window opens (some instruments flag an error for every setting they don't support).
- `write(self, key: str, value: Any)`
- `read_one(self, key: str)`
- `read_all(self)`

## `vescentcomb.gui.page_base`

Base class for main-window pages.

```python
from vescentcomb.gui import page_base
```

### class `Page(hub, settings, main=None)`

A scrollable page bound to one or more roles. Subclasses build ``self.content``.

- `header(self, title: str, sub: str = '', pills=(), buttons=())`
- `on_poll(self, role: str, data: dict)`
- `on_devices_changed(self)`
- `call(self, fn, on_done=None, log=None, role=None)`
- `connected` *(property)*
- `save_snapshot_csv(self, role: Optional[str] = None)`
- `remember_state(self, role: Optional[str] = None)` — Read the device snapshot and store it as 'last session' in the settings file.
- `restore_last_session(self, role: Optional[str] = None)`

## `vescentcomb.gui.pages.overview`

Overview: panels contributed by the add-ons, the bench-instrument table and the event log.

```python
from vescentcomb.gui.pages import overview
```

### class `OverviewPage(hub, settings, main=None)`

- `on_devices_changed(self)`
- `on_poll(self, role, d)`

## `vescentcomb.gui.plots`

Plot widget used everywhere in the GUI.

```python
from vescentcomb.gui import plots
```

### class `BenchPlot(height: int = 170, ylabel: str = '', xlabel: str = '', title: str = '')`

- `set_labels(self, ylabel: str = '', xlabel: str = '') -> None`
- `wheelEvent(self, ev)`
- `save_png(self, path: Optional[str] = None) -> Optional[str]`
- `save_csv(self, path: Optional[str] = None) -> Optional[str]`

### class `BenchViewBox(parent=None, border=None, lockAspect=False, enableMouse=True, invertY=False, enableMenu=True, name=None, invertX=False, defaultPadding=0.02)`

Wheel and drag only act with Ctrl held; double-click re-enables auto-range.

- `wheelEvent(self, ev, axis=None)`
- `mouseDragEvent(self, ev, axis=None)`
- `mouseDoubleClickEvent(self, ev)`
- `raiseContextMenu(self, ev)`

## `vescentcomb.gui.reference_panel`

Overview panel: which instruments use the 10 MHz (GPS) reference, and whether it is on.

```python
from vescentcomb.gui import reference_panel
```

**Constants:** `MODE_TEXT`

### class `ReferencePanel(hub, settings, main=None)`

- `rebuild(self)`
- `set_ref(self, role, opt, on)`
- `on_poll(self, role, d)`

### `reference_state(hub) -> Dict[str, Any]`

{role: {input, mode, in_use}} for every declared reference user (used in data-file headers).

## `vescentcomb.gui.theme`

Dark instrument theme (matches the mockups).

```python
from vescentcomb.gui import theme
```

**Constants:** `BAD`, `BAD_BG`, `BG`, `BLUE`, `BLUE_BTN`, `CHROME`, `DIM`, `FONT_MONO`, `FONT_SANS`, `IDLE`, `IDLE_BG`, `INPUT`, `LINE`, `LINE2`, `MUTED`, `OK`, `OK_BG`, `PANEL`, `PILL`, `PLOT1`, `PLOT2`, `PLOT3`, `TEXT`, `WARN`, `WARN_BG`

## `vescentcomb.gui.widgets`

Small reusable widgets + helpers that persist field values to the settings file.

```python
from vescentcomb.gui import widgets
```

**Constants:** `CONFIRM`

### class `DiffDialog(parent, title: str, intro: str, rows: List[Tuple], ok_text: str = Write checked)`

Rows (key, live, saved [, note]) with a checkbox each. ``selected()`` → keys.

- `selected(self) -> List[str]`

### class `EngEdit(value: float = 0.0, unit: str = '')`

Number entry that accepts SI suffixes (20n, 1.5u, 2e-6) and shows engineering notation.

- `value(self) -> float`
- `setValue(self, v: float)`

### class `History(maxlen: int = 3600)`

Rolling time series for trend plots.

- `add(self, **vals)`
- `series(self, key: str)`

### class `LogView(max_lines: int = 2000)`

- `add(self, tag: str, msg: str)`

### class `NumEdit(value: float = 0.0, unit: str = '')`

Plain number entry (no SI prefix on display) for dB, ratios, counts … Shows up to 7 significant digits.

- `setValue(self, v: float)`

### class `Panel(title: str = '', right: Optional[QWidget] = None)`

Rounded card with a title row; add widgets to ``.body``.

- `add(self, w)`
- `set_title(self, text: str)`
- `add_right(self, w: QWidget)`

### class `Pill(text: str = '', state: str = idle)`

- `set(self, text: str, state: str = idle)`

### class `Readout(caption: str, value: str = '—', big: bool = False, unit: str = '')`

Caption over a monospaced value.

- `set_si(self, value: Any, unit: Optional[str] = None, digits: int = 6, color: Optional[str] = None)` — Value in SI notation with a prefix (12.5 MHz, 340 µW, 2.1 ns).
- `set(self, value: Any, fmt: str = '{}', color: Optional[str] = None)` — ``fmt`` is a format string, or ``"si:<unit>[:<scale>[:<digits>]]"`` for SI notation (value × scale shown with a prefix, e.g. "si:Hz:1e6" for a value given in MHz).

### class `Seg(options: Sequence[str], current: int = 0)`

Segmented button group. ``changed`` emits the selected index.

- `index(self) -> int`
- `set_index(self, i: int, emit: bool = False)`

### class `StepRow(num: int, title: str)`

- `set(self, status: str, detail: str = '')`

### `bind(settings, key: str, w: QWidget, default: Any = None) -> QWidget`

Load the saved value into ``w`` and save every change (autosaved settings file).

### `button(text: str, kind: str = '', slot: Optional[Callable] = None, tip: str = '') -> QPushButton`

### `combo(items: Iterable, current: Any = None) -> QComboBox`

### `confirm(parent, title: str, text: str, ok_text: str = Continue, danger: bool = False) -> bool`

Yes/no question. Returns True straight away when confirmations are switched off.

### `confirm_checks(parent, title: str, text: str, checks: Sequence[str], ok_text: str = Turn on) -> bool`

Confirmation that needs every checkbox ticked. Skipped when confirmations are off.

### `dspin(value: float = 0.0, lo: float = -1000000000000.0, hi: float = 1000000000000.0, decimals: int = 4, step: float = 0.1, suffix: str = '') -> QDoubleSpinBox`

### `field(caption: str, widget: QWidget) -> QWidget`

### `fmt_num(v, f: str = '{:.4f}') -> str`

### `grid(items: Sequence[QWidget], cols: int = 3, spacing: int = 10) -> QGridLayout`

### `hbox(*items, stretch_end: bool = False, spacing: int = 8) -> QHBoxLayout`

### `ispin(value: int = 0, lo: int = 0, hi: int = 1000000000, suffix: str = '') -> QSpinBox`

### `label(text: str = '', kind: str = lbl, wrap: bool = False) -> QLabel`

### `mark_changed(w: QWidget, changed: bool) -> None`

### `notice(parent, title: str, text: str) -> None`

Information the user asked for (always shown).

### `pen(color: str, width: float = 1.5, dash: bool = False)`

### `plot(height: int = 170, ylabel: str = '', xlabel: str = '', title: str = '')`

Bench plot: auto-range, Ctrl+wheel zoom, SI-prefixed axes for SI units, right-click export.

### `scroll(widget: QWidget) -> QScrollArea`

### `set_combo_data(c: QComboBox, value: Any) -> None`

### `set_row(t: QTableWidget, r: int, values: Sequence[Any], colors: Optional[Dict[int, str]] = None)`

### `table(headers: Sequence[str], rows: int = 0, stretch_last: bool = True) -> QTableWidget`

### `vbox(*items, spacing: int = 10, margins=(0, 0, 0, 0)) -> QVBoxLayout`

## `vescentcomb.gui.windows.base`

Base for separate instrument windows (scopes, analyzers, generators, meter, SuperK).

```python
from vescentcomb.gui.windows import base
```

### class `InstrumentWindow(hub, settings, main=None)`

- `make_toolbar(self, items=())` — Top bar: buttons (text, kind, slot) or widgets, then a connection pill + address.
- `make_body(self, margins=(16, 14, 16, 16))`
- `add_tabs(self, main, setup_intro: str = '', extra=())` — Main controls in a "Control" tab and every driver option in a "Setup" tab.
- `connected` *(property)*
- `data_path(self, stem: str, ext: str = csv) -> str`
- `save_columns(self, stem: str, header, columns, ask: bool = True, meta=None)` — CSV with the bench-state header (see vescentcomb.datafile).
- `on_poll(self, d)`
- `on_devices_changed(self)`
- `call(self, fn, on_done=None, log=None)`
- `closeEvent(self, e)`
- `showEvent(self, e)`

## `vescentcomb.gui.worker`

One worker thread per device: a job queue plus a ~1 Hz poll.

```python
from vescentcomb.gui import worker
```

### class `DeviceWorker(role: str, device: Any, poll_s: float = 1.0, reopen: Optional[Callable[[], Any]] = None, on_reopen: Optional[Callable[[Any], None]] = None)`

- `call(self, fn: Callable[[Any], Any], on_done: Optional[Callable[[Any], None]] = None, on_error: Optional[Callable[[Exception], None]] = None) -> None`
- `stop(self, safe: bool = True, timeout: float = 5.0, wait: bool = True) -> threading.Event` — Close the device in its own thread. Pending jobs are dropped first, so a backlog (or one slow call) doesn't hold up closing. ``wait=False`` returns at once with an Event set when it's closed.

### class `Hub(settings)`

All workers, the event log and the poll logger.

- `attach(self, role: str, device: Any, found=None, poll_s: float = 1.0, reopen=None, on_reopen=None) -> DeviceWorker`
- `detach(self, role: str, safe: bool = True, wait: bool = True)` — Stop the role's worker. With ``wait=False`` the window never blocks: the returned Event is set once the instrument is closed.
- `close_all(self, safe: bool = True, timeout: float = 2.0)` — Close every instrument in parallel and wait at most ``timeout`` seconds in total (worker threads are daemons, so one stuck on a slow port can't stop the app from exiting).
- `has(self, role: str) -> bool`
- `device(self, role: str)`
- `call(self, role: str, fn, on_done=None, on_error=None, log: Optional[str] = None)`
- `last(self, role: str) -> Dict[str, Any]`
- `emit_log(self, tag: str, msg: str)`
- `start_logging(self, folder: str)`
- `stop_logging(self)`

## `vescentcomb.settings`

Auto-saved settings file.

```python
from vescentcomb import settings
```

**Constants:** `APP_NAME`, `SCHEMA_VERSION`

### class `Settings(path: Optional[os.PathLike] = None, autosave_delay: float = 1.0, autosave: bool = True)`

Dotted-key settings store with debounced atomic autosave.

- `load(self) -> None`
- `save(self) -> Path` — Write now (atomic). Returns the path written.
- `flush(self) -> None` — Save if anything changed since the last write.
- `get(self, key: str, default: Any = None) -> Any`
- `set(self, key: str, value: Any) -> None`
- `update(self, key: str, values: Dict[str, Any]) -> None`
- `delete(self, key: str) -> None`
- `on_change(self, cb: Callable[[str, Any], None]) -> None`
- `role(self, role: str) -> Dict[str, Any]`
- `set_role(self, role: str, kind: str, serial: str, model: str = '', address: str = '') -> None`
- `save_device_state(self, role: str, snapshot: Dict[str, Any]) -> None`
- `device_state(self, role: str) -> Dict[str, Any]`

### `default_data_dir() -> Path`

Where recordings, scans and captures go unless the user picks a folder.

### `default_settings_path() -> Path`

## `vescentcomb.sim.base`

Building blocks for simulated instruments (used by every add-on's ``sim.py``).

```python
from vescentcomb.sim import base
```

### class `OptionStore(defaults=None)`

Remembers ``HEADER value`` writes and answers ``HEADER?`` with them.

- static `key(header: str) -> str`
- `get(self, header, default=None)`
- `set(self, header, value)`
- `handle(self, cmd: str)`

### class `SCPIModel()`

Base for VISA models: ``handle(cmd) -> reply | None`` (bytes for binary blocks).

- `handle(self, cmd: str)`
- `binary(self, cmd)`

### class `SilentModel()`

A GPIB address that never answers (exercises the 'unknown' path).

### `null_generator()`

### `num(s: str) -> float`

First number in a command argument ('500MV' -> 500.0, '2.5E-6S' -> 2.5e-06).

## `vescentcomb.sim.fakeio`

Byte-level fake serial port and fake VISA resource manager.

```python
from vescentcomb.sim import fakeio
```

### class `FakeResource(name: str, model)`

- `write(self, cmd: str)`
- `read(self) -> str`
- `query(self, cmd: str) -> str`
- `read_raw(self) -> bytes`
- `read_stb(self) -> int`
- `query_binary_values(self, cmd, datatype=B, is_big_endian=False, container=<class list>, **kw)`
- `clear(self)`
- `close(self)`

### class `FakeResourceManager(models: Dict[str, object])`

- `list_resources(self, query: str = '?*::INSTR')`
- `open_resource(self, name: str, **kw)`
- `close(self)`

### class `FakeSerial(port: str, handler: Callable[[bytes], bytes], terminator: bytes = b'\r', baudrate: int = 115200, timeout: float = 1.0, expected_baud: Optional[int] = None, serial_number: str = '', strip_lf: bool = True)`

Implements the subset of pyserial the drivers use.

- `in_waiting` *(property)*
- `write(self, data: bytes) -> int`
- `read(self, n: int = 1) -> bytes`
- `read_until(self, expected: bytes = b'\n', size: Optional[int] = None) -> bytes`
- `flush(self)`
- `reset_input_buffer(self)`
- `reset_output_buffer(self)`
- `close(self)`

### class `TextDevice()`

Base for ASCII command/response simulators.

- `handle(self, cmd: str) -> Optional[str]`

### `visa_timeout()`

## `vescentcomb.sim.world`

The simulated bench. The shell provides an empty world; each add-on's ``sim.py`` fills it.

```python
from vescentcomb.sim import world
```

### class `World(speed: float = 1.0, cavity_tau_s: float = 3.0)`

- `add_serial(self, info: PortInfo, handler, terminator: bytes = b'\r', expected_baud: int = 115200, strip_lf: bool = True) -> None`
- `add_visa(self, resource: str, model) -> None`
- `add_rf_line(self, fn: Callable[[], List[Tuple[float, float]]]) -> None`
- `on_uninstall(self, fn: Callable[[], None]) -> None`
- `rf_lines(self) -> List[Tuple[float, float]]`
- `beat_offset_hz(self, opl) -> float`
- `beat_phase_rms(self) -> float`
- `pzt_out(self) -> float`
- `ports(self) -> List[PortInfo]`
- `serial_factory(self, port: str, baudrate: int = 115200, timeout: float = 1.0)`

### `get_world() -> Optional[World]`

### `install(speed: float = 1.0, cavity_tau_s: float = 3.0, settings=None) -> World`

Route discovery and drivers to a simulated bench built by the loaded add-ons.

### `uninstall() -> None`

## `vescentcomb_addons.comb_lock`

Comb lock module — FFC-100, comb OPL (#1, f_rep → GPS), SLICE-FPGA-II and the GPS lock process.

```python
from vescentcomb_addons import comb_lock
```

**Constants:** `SECTION`

### `register(api)`

## `vescentcomb_addons.comb_lock.autotune`

Auto-tune an OPL servo filter.

```python
from vescentcomb_addons.comb_lock import autotune
```

**Constants:** `METRICS`, `NEEDS`

### class `AutoTuner(opl, cfg: TuneConfig, scope=None, sa=None, on_trial: Optional[Callable[[Trial, int, int], None]] = None, on_log: Optional[Callable[[str], None]] = None)`

- `start_thread(self)`
- `stop(self)`
- `estimate_trials(self) -> int`
- `revert(self)`
- `locked(self) -> bool`
- `measure(self) -> float`
- `run(self) -> Optional[Trial]`
- `apply_best(self)`

### class `Trial(gain_db: float, int_hz: float, diff_hz: Optional[float], clamp: Optional[bool], score: float, locked: bool) -> None`

- `as_dict(self)`

### class `TuneConfig(metric: str = adev_counter, gains_db: List[float] = <factory>, int_corners_hz: List[float] = <factory>, diff_corners_hz: Optional[List[float]] = None, gain_clamp: Optional[List[bool]] = None, strategy: str = coordinate, dwell_s: float = 5.0, averages: int = 4, max_trials: int = 60, max_gain_step_db: float = 2.0, revert_on_loss: bool = True, scope_channel: int = 1, band_hz: tuple = (10.0, 1000000.0)) -> None`

- `as_dict(self)`
- class `from_dict(cls, d)`

## `vescentcomb_addons.comb_lock.ffc100`

Vescent FFC-100 fiber frequency comb (USB serial, CR LF, ASCII).

```python
from vescentcomb_addons.comb_lock import ffc100
```

### class `FFC100(port: Optional[str] = None, baudrate: int = 115200, timeout: float = 2.0, ser=None)`

- `ser` *(property)*
- `close(self) -> None`
- `query(self, cmd: str) -> str`
- static `value(raw: str, cmd: str) -> str`
- `query_value(self, cmd: str) -> str`
- `query_float(self, cmd: str) -> Optional[float]`
- `query_int(self, cmd: str) -> Optional[int]`
- `idn(self) -> str`
- `version(self) -> str`
- `identify(self) -> Identity`
- `get_state(self) -> Optional[int]`
- `get_state_name(self) -> str`
- `set_state(self, n: int, force: bool = False) -> str`
- `standby(self) -> str`
- `laser_on(self) -> str`
- `shutdown(self, wait_s: float = 0.5) -> str` — LASER ON -> STANDBY -> OFF, never a direct OFF while lasing.
- `osc_current(self)`
- `amp_current(self)`
- `osc_temp(self)`
- `osc_temp_error(self)`
- `amp_temp(self)`
- `amp_temp_error(self)`
- `cav_temp(self)`
- `cav_temp_error(self)`
- `cav_setpoint(self)`
- `set_cav_setpoint(self, deg_c: float) -> str`
- `pzt_mode(self) -> Tuple[Optional[int], str]`
- `set_pzt_mode(self, code) -> str`
- `set_pzt_gain(self, x10: bool) -> str`
- `dc_bias_setpoint(self)`
- `set_dc_bias_setpoint(self, volts: float) -> str` — Keep at 0 V while a SLICE is locking — bias adds onto the PZT output.
- `pzt_output_voltage(self)`
- `mode_locked(self) -> bool` — MODELOK? ON *and* the laser is on (MSTRCTL 2): with the laser off the comb can still report the last MODELOK state.
- `slow_servo(self) -> str`
- `slow_servo_on(self) -> bool`
- `set_slow_servo(self, on: bool) -> str`
- `slow_servo_gain(self)`
- `set_slow_servo_gain(self, db: float) -> str`
- `slow_servo_offset(self)`
- `set_slow_servo_offset(self, v: float) -> str`
- `poll(self) -> Dict[str, Any]`
- `snapshot(self) -> Dict[str, Any]`
- `safe_state(self) -> None` — The comb is left as it is: shutting it down is a deliberate act.

## `vescentcomb_addons.comb_lock.fpga.controller`

High-level, GUI-free control of the Vescent SLICE-FPGA-II.

```python
from vescentcomb_addons.comb_lock.fpga import controller
```

**Constants:** `CHANNELS`

### class `LoopGains(P: float, I: float, II: float, D: float, coef_d: float, lock: int) -> None`


### class `SliceConfig(path: str | os.PathLike = PosixPath('/home/claude/w/vescentcomb/vescentcomb/addons/comb_lock/fpga/configs/UCF_FFC-100_Parameters.xml'))`

The Vescent XML parameter file (e.g. UCF_FFC-100_Parameters.xml), editable in Python.

- `get(self, section: str, key: str) -> str`
- `getf(self, section, key) -> float`
- `getb(self, section, key) -> bool`
- `set(self, section: str, key: str, value)`
- `save(self, path: str | os.PathLike)`
- `copy(self) -> "SliceConfig"`
- `as_dict(self) -> dict`

### class `SliceFPGA(host: str = '192.168.0.150', port: int = 5000, config: str | os.PathLike | SliceConfig | None = None, connect: bool = True, timeout: float = 2.0)`

One SLICE-FPGA-II box.

- `connect(self)`
- `close(self)` — Drop the TCP connection. Nothing is written: the FPGA keeps running (and locked) on its own.
- `disconnect(self)` — Drop the TCP connection. Nothing is written: the FPGA keeps running (and locked) on its own.
- `connected` *(property)*
- `reconnect(self, attempts: int = 5, delay: float = 2.0) -> bool`
- `loop_gains(self, channel, lock: bool, kc: float | None = None) -> LoopGains` — LoopFiltersUI.getActualControllerDesign (gains normalised to the open-loop gain kc).
- `push_config(self, clock=config, slow_start_hv: bool = True)` — Equivalent of the GUI's "Push default values to Red Pitaya" for the loaded XML config.
- `set_clock(self, external: bool = True, f_ext: float = 20000000.0)` — Select the ADC clock. External: f_ext Hz on the EXT CLK input (20 MHz from the GPS 10 MHz doubler).
- `lock(self, channel=ceo)`
- `unlock(self, channel=ceo, ramp: bool = True)` — Locked -> unlocked, ramping the manual DAC offset to where the lock sat (as the GUI does).
- `is_locked(self, channel=ceo) -> bool` — Lock bit as stored in the FPGA (read back, so valid after re-attaching).
- `set_dac_offset(self, dac: int, volts: float)` — Manual DAC offset in the GUI's volts (relative to Output_limits); used when unlocked or as lock centre.
- `set_ref_freq(self, channel, f_hz: float, vco_sign: int | None = None)`
- `set_loop_filter(self, channel, **params)` — Change kp [dB], fi, fii, fd, fdf [Hz], chkKp, chkKd, chkKpCrossing and push (lock state preserved).
- `set_vco_gain(self, dac: int, hz_per_volt: float)`
- `attach(self, f_ext: float | None = 20000000.0)` — Read the state of a box that is already configured / locked. Writes nothing.
- `status(self) -> dict`
- `ext_clock_freq(self) -> float` — External clock frequency measured by the FPGA against its internal 200 MHz (not disciplined).
- `read_counters(self) -> dict` — One read of the zero-dead-time frequency counters (lock frequency error, Hz) and the DAC outputs.
- `capture(self, source: str = ADC0, n: int = 16384)` — Grab a block from the on-chip logger (max 32768 samples at fs).
- `frequency_noise(self, channel=ceo, n: int = 32768, decimate: int = 10)` — Frequency-noise PSD of the in-loop beat (as the GUI's phase-noise plot): returns f, S_nu [Hz^2/Hz], S_phi [rad^2/Hz].
- `snapshot(self) -> dict` — Everything needed to restore this lock later (config + GUI-side state). JSON-serialisable.
- `restore(self, snap: dict, relock: bool = True)`
- `program_fpga(self, bitfile: str | os.PathLike = PosixPath('/home/claude/w/vescentcomb/vescentcomb/addons/comb_lock/fpga/firmware/red_pitaya_top_extint_clk.bit'))` — Load a bitstream into the Zynq PL (volatile, like the GUI's 'Program FPGA'). Re-push config afterwards.

### `discover(broadcast: str = '192.168.0.255', timeout: float = 2.0, port: int = 1952)`

UDP broadcast discovery (UDPRedPitayaDiscovery.py). Returns list of (ip, mac).

### `pll_multipliers(f_ext: float, f_adc: float = 125000000.0, vco_limits=(600000000.0, 1600000000.0))`

Port of ConfigurationRPSettingsUI.getPLLmultipliers (same search, no printing).

## `vescentcomb_addons.comb_lock.fpga.monitor`

Background monitoring / logging / watchdog for a SliceFPGA, designed to run for days from a notebook.

```python
from vescentcomb_addons.comb_lock.fpga import monitor
```

### class `Monitor(fpga, csv_dir: str | Path | None = slice_logs, period_s: float = 0.25, history: int = 20000, watchdog: Watchdog | None = None, reconnect: bool = True, rotate_daily: bool = True)`

Poll the frequency counters + DAC outputs in a background thread.

- `start(self)`
- `stop(self)`
- `running` *(property)*
- `frame(self)` — History as a pandas DataFrame (index = local time).
- `summary(self, last_s: float | None = 60) -> dict`
- `plot(self, last_s: float | None = 600)`

### class `Watchdog(channel=ceo, action=relock, rail_margin=0.05, max_err_Hz=None, n_bad=2, max_relocks=5, window_s=3600.0, settle_s=1.0)`

Relock policy evaluated on every new counter sample.

- `check(self, fpga, s) -> str`

## `vescentcomb_addons.comb_lock.fpga.pll_modules`

Loop-filter (PLL) register modules, vendored unchanged from Vescent's SuperLaserLand2_JD2_PLL.py (JD Deschenes, 2013). Fixed-point scalings must match dpll_wrapper.v in the FPGA bitstream.

```python
from vescentcomb_addons.comb_lock.fpga import pll_modules
```

### class `Loop_filters_module(bus_base_address, N_DIVIDE_P, N_DIVIDE_I, N_DIVIDE_II, N_DIVIDE_D, N_DIVIDE_DF)`

- `get_p_limits(self)`
- `get_i_limits(self)`
- `get_ii_limits(self)`
- `get_d_limits(self)`
- `get_df_limits(self)`
- `get_current_gains(self)`
- `get_current_transfer_function(self, freq_axis, fs)`
- `set_pll_settings(self, sl, gain_p, gain_i, gain_ii, gain_d, coef_d, bLock)`
- `get_pll_settings(self, sl)`

### class `PLL0_module(sl)`


### class `PLL1_module(sl)`


### class `PLL2_module(sl)`


## `vescentcomb_addons.comb_lock.fpga.rp_pll`

Low-level TCP transport to the SLICE-FPGA-II (Red Pitaya / Zynq-7010) ``monitor-tcp`` server.

```python
from vescentcomb_addons.comb_lock.fpga import rp_pll
```

### class `CommsError(…)`

Socket-level failure talking to the box.

### class `CommsLoggeableError(…)`

Kept for API compatibility with the Vescent code.

### class `RP_PLL_device(controller=None, timeout: float = 2.0)`

- `OpenTCPConnection(self, HOST: str, PORT: int = 5000, valid_socket_for_general_comms: bool = True)`
- `CloseTCPConnection(self)`
- `recvall(self, count: int) -> bytes`
- `send(self, packet: bytes)`
- `read(self, n: int) -> bytes`
- static `validate_address(addr: int)`
- `write_Zynq_register_32bits(self, absolute_addr: int, data_32bits: int, bSigned: bool = False)`
- `read_Zynq_register_32bits(self, absolute_addr: int, bIsAXI: bool = False) -> bytes`
- `read_Zynq_buffer_int16(self, number_of_points: int) -> bytes`
- `write_Zynq_register_uint32(self, address_uint32, data_uint32)`
- `write_Zynq_register_int32(self, address_uint32, data_int32)`
- `write_Zynq_AXI_register_uint32(self, address_uint32, data_uint32)`
- `read_Zynq_register_uint32(self, address_uint32) -> int`
- `read_Zynq_register_int32(self, address_uint32) -> int`
- `read_Zynq_AXI_register_uint32(self, address_uint32) -> int`
- `read_Zynq_register_uint64(self, address_uint32_lsb, address_uint32_msb) -> np.ndarray`
- `read_Zynq_register_int64(self, address_uint32_lsb, address_uint32_msb) -> np.ndarray`
- `write_file_on_remote(self, strFilenameLocal: str, strFilenameRemote: str)`
- `send_shell_command(self, strCommand: str)`
- `send_reboot_command(self)`
- `SetWireInValue(self, endpoint, value_16bits)`
- `UpdateWireIns(self)`
- `GetWireOutValue(self, endpoint)`
- `UpdateWireOuts(self)`

## `vescentcomb_addons.comb_lock.fpga.simulator`

A software stand-in for the SLICE-FPGA-II ``monitor-tcp`` server, for dry-running the notebook without hardware. It speaks the same TCP protocol, remembers register writes (including the read-back RAM shadow), reports a locked PLL clock, and returns plausible data:

```python
from vescentcomb_addons.comb_lock.fpga import simulator
```

**Constants:** `AXI`, `BASE`, `BUF`, `RB`, `RD`, `SH`, `WF`, `WR`

### class `SliceSimulator(port: int = 50000, host: str = '127.0.0.1')`

- `fs(self)`
- `locked(self, ch)`
- `start(self)`
- `stop(self)`

## `vescentcomb_addons.comb_lock.fpga.superlaserland`

SLICE-FPGA-II register-level interface (Red Pitaya port of the NIST/JD Deschenes phase-lock box).

```python
from vescentcomb_addons.comb_lock.fpga import superlaserland
```

### class `SuperLaserLand_JD_RP(controller=None)`

- `openDevice(self, bConfigure=True, strSerial='', strFirmware=superlaserland.bit)`
- `resetFrontend(self)`
- `make_sure_path_exists(self, path)`
- `initSubModules(self)`
- `send_bus_cmd(self, bus_address, data1, data2)`
- `send_bus_cmd_32bits(self, bus_address, data_32bits)`
- `send_bus_cmd_16bits(self, bus_address, data_16bits)`
- `setup_write(self, selector, Num_samples)`
- `setup_ADC0_write(self, Num_samples)`
- `setup_ADC1_write(self, Num_samples)`
- `setup_DDC0_write(self, Num_samples)`
- `setup_DDC1_write(self, Num_samples)`
- `setup_counter_write(self, Num_samples)`
- `setup_DAC0_write(self, Num_samples)`
- `setup_DAC1_write(self, Num_samples)`
- `setup_DAC2_write(self, Num_samples)`
- `compute_integration_time_for_syst_ident(self, System_settling_time, first_modulation_frequency_in_hz)`
- `setup_system_identification(self, input_select, output_select, first_modulation_frequency_in_hz, last_modulation_frequency_in_hz, number_of_frequencies, System_settling_time, output_amplitude, bDither=False)`
- `setVNA_mode_register(self, trigger_dither, stop_flag, bSquareWave)`
- `trigger_write(self)`
- `trigger_system_identification(self)`
- `wait_for_write(self)`
- `get_system_identification_wait_time(self)`
- `wait_for_system_identification(self)`
- `read_raw_bytes_from_DDR2(self)`
- `extractBit(self, value, N_bit)`
- `readStatusFlags(self)`
- `readLEDs(self)`
- `readResidualsStreamingStatus(self)`
- `setResidualsStreamingSettings(self, data_delay, trigger_delay, boxcar_filter_size, rst_residuals_streaming)`
- `setResidualsStreamingResetMode(self, rst_residuals_streaming)`
- `read_raw_bytes_from_pipe(self, PipeAddress, Num_bytes_read)`
- `read_adc_samples_from_DDR2(self)`
- `read_ddc_samples_from_DDR2(self)`
- `read_counter_samples_from_DDR2(self)`
- `read_VNA_samples_from_DDR2(self)`
- `set_dac_offset(self, dac_number, offset)`
- `get_dac_offset(self, dac_number)`
- `set_pwm_settings(self, levels, value, bSendToFPGA=True)`
- `set_dac_limits(self, dac_number, limit_low, limit_high, bSendToFPGA=True)`
- `get_dac_limits(self, dac_number)`
- `get_ddc0_ref_freq_from_RAM(self)`
- `get_ddc0_ref_freq(self)`
- `set_ddc0_ref_freq(self, frequency_in_hz)`
- `get_ddc1_ref_freq_from_RAM(self)`
- `get_ddc1_ref_freq(self)`
- `set_ddc1_ref_freq(self, frequency_in_hz)`
- `getFreqDiscriminatorGain(self)`
- `convertPWMCountsToVolts(self, standard, levels, counts)`
- `convertPWMVoltsToCounts(self, standard, levels, volts)`
- `convertDACCountsToVolts(self, DAC_number, counts)`
- `convertDACVoltsToCounts(self, DAC_number, voltage)`
- `getDACGainInCountsPerVolts(self, DAC_number)`
- `getDACGainInVoltsPerCounts(self, DAC_number)`
- `convertADCCountsToVolts(self, ADC_number, counts)`
- `convertDDCCountsToHz(self, counts)`
- `setDitherLockInState(self, dac_number, bEnable)`
- `setDitherLockInSettings(self, dac_number)`
- `setupDitherLockIn(self, dac_number, modulation_period, N_periods, amplitude, mode_auto)`
- `get_Dither_Settings(self, dac_number)`
- `ditherRead(self, N_samples, dac_number=0)`
- `scaleDitherResultsToHz(self, results, dac_number)`
- `scaleDitherResultsToHzPerVolts(self, results, dac_number)`
- `set_integrator_settings(self, integrator_number, hold, flip_sign, lock, gain_in_bits)`
- `get_integrator_settings(self, integrator_number)`
- `frontend_DDC_processing(self, samples, ref_exp0, input_number)`
- `get_frontend_filter_response(self, frequency_axis, input_number)`
- `setCounterMode(self, bTriangular)`
- `getCounterMode(self)`
- `scaleCounterReadingsIntoHz(self, freq_counter_samples, f_ref=None, N_cycles_gate_time=None)`
- `new_freq_setting(self)`
- `read_dual_mode_counter(self, output_number)`
- `set_ddc_filter(self, adc_number, filter_select, angle_select=0)`
- `set_ddc_filter_select_register(self)`
- `get_ddc_filter_select(self)`
- `get_ddc_angle_select(self)`
- `set_mux_pll2(self, register_value)`
- `set_internal_VCO_offset(self, offset)`
- `get_internal_VCO_offset(self)`
- `set_internal_VCO_amplitude(self, amplitude)`
- `get_internal_VCO_amplitude(self)`
- `set_mux_vco(self, data)`
- `get_mux_vco(self)`
- `read_RAM_dpll_wrapper(self, addr)`
- `read_RAM_dpll_wrapper_signed(self, addr)`
- `read_pll2_mux(self)`
- `save_openLoop_gain(self, dac_number, value)`
- `get_openLoop_gain(self, dac_number)`
- `save_mode_auto(self, dac_number, mode)`
- `setFan(self, fanState)`
- `setTestOscillator(self, bEnable=1, bPolarity=1, oscillator_modulus=625, oscillator_modulus_active=62)`
- `setClockSelector(self, bExternalClock=0)`
- `read_clk_select(self)`
- `setADCclockPLL(self, f_source, bExternalClock, CLKFBOUT_MULT, CLKOUT0_DIVIDE, CLKOUT1_DIVIDE=100)`
- `readZynqXADC(self, xadc_channel=0)`
- `readZynqXADCsupply(self)`
- `readZynqTemperature(self)`
- `getExtClockFreq(self)`

### `print(*args, **kwargs)`

## `vescentcomb_addons.comb_lock.gps_lock`

Comb lock sequence: f_ceo first on the SLICE-FPGA-II, then f_rep to GPS.

```python
from vescentcomb_addons.comb_lock import gps_lock
```

**Constants:** `STEP_IDS`, `STEP_TITLES`

### class `Aborted(…)`

### class `LockFault(problems: List[Tuple[str, str]], where: str)`

A lock that was good is no longer good (checked after every step).


### class `LockParams(counter_offset_hz: float = 31.0, window_hz: float = 8.0, cav_settle_mk: float = 1.0, poll_s: float = 3.0, confirm_dwell_s: float = 10.0, post_servo_wait_s: float = 10.0, max_excursion_c: float = 1.0, max_steps: int = 200, settle_timeout_s: float = 180.0, step_table: List[Tuple[float, float]] = <factory>, fceo_max_phase_rad: float = 1.5, fceo_retries: int = 3, dac0_max_frac: float = 0.15, check_pzt: bool = False, pzt_min_v: float = 2.0, pzt_max_v: float = 58.0, relock_tries: int = 3, relock_wait_s: float = 10.0, ask_before_fpga_write: bool = True, dry_run: bool = False) -> None`

- `step_for(self, err_hz: float) -> float`
- `as_dict(self)`
- class `from_dict(cls, d: Dict[str, Any]) -> "LockParams"`

### class `LockSequence(devices: Dict[str, Any], params: Optional[LockParams] = None, fpga_profile: Optional[Dict[str, Any]] = None, on_step=None, on_log=None, on_sample=None, ask=None)`

Run with ``seq.run()`` (blocking) or ``seq.start()`` (thread).

- `start(self) -> threading.Thread`
- `stop(self)`
- `pause(self)`
- `resume(self)`
- `paused` *(property)*
- `thread_alive(self) -> bool`
- `run(self) -> bool`

### class `LockWatchdog(devices: Dict[str, Any], params: Callable[[], LockParams], run_sequence: Callable[[], bool], on_log=None, on_state=None, period_s: float = 5.0, lost_s: float = 10.0, max_per_hour: int = 6)`

Watches the f_ceo lock and the GPS OPL #1 lock after the sequence has locked them.

- `start(self)`
- `stop(self)`
- `running` *(property)*

### class `StepState(id: str, title: str, status: str = wait, detail: str = '') -> None`


### `lock_problems(d: Dict[str, Any], p: LockParams, want: Dict[str, bool]) -> List[Tuple[str, str]]`

What is wrong with the locks in ``want`` (fceo / opl1 / slow) right now. Empty list = all good.

### `recover(d: Dict[str, Any], p: LockParams, kinds, log: Callable[[str], None], sleep: Callable[[float], None] = <built-in function sleep>) -> None`

Put things back so the lock sequence can run again.

## `vescentcomb_addons.comb_lock.overview`

Comb-lock cards and trends for the Overview page.

```python
from vescentcomb_addons.comb_lock import overview
```

### class `CombTrends(hub, settings, main=None)`

f_rep beat error with the lock window, and cavity temperature against setpoint.

- `on_poll(self, role, d)`

### class `FFCCard(hub, settings, main=None)`

- `transform(self, d)`

### class `FPGACard(hub, settings, main=None)`

- `transform(self, d)`

### class `OPL1Card(hub, settings, main=None)`

- `transform(self, d)`

## `vescentcomb_addons.comb_lock.pages.ffc`

FFC-100 comb page.

```python
from vescentcomb_addons.comb_lock.pages import ffc
```

### class `FFCPage(hub, settings, main=None)`

- `on_devices_changed(self)`
- `reread(self)`
- `on_poll(self, role, d)`
- `do_standby(self)`
- `do_laser_on(self)`
- `do_shutdown(self)`
- `nudge(self, d)`
- `apply_setpoint(self)`
- `set_pzt(self)`
- `apply_bias(self)`
- `set_slow(self, i)`
- `apply_slow(self)`

## `vescentcomb_addons.comb_lock.pages.fpga`

SLICE-FPGA-II page: attach, box-vs-profile, f_ceo / optical loops, spectrum, phase noise, monitor/watchdog, config file and firmware. Talks to the built-in ``fpga`` package (SliceFPGA_II_modern).

```python
from vescentcomb_addons.comb_lock.pages import fpga
```

**Constants:** `DDC_FILTERS`, `LOCK_AFFECTING`

### class `FPGAPage(hub, settings, main=None)`

- `browse_config(self)`
- `on_devices_changed(self)`
- `attach(self)`
- `reread(self)`
- `compare(self)`
- `write_checked(self)`
- `save_profile(self)`
- `push_config(self)`
- `program_fpga(self)`
- `toggle_lock(self, loop)`
- `apply_ceo(self)`
- `apply_dac0(self)`
- `apply_opt(self)`
- `set_clock(self, i)`
- `toggle_monitor(self, on)`
- `measure_pn(self)`
- `on_poll(self, role, d)`
- `refresh_iq(self)`
- `refresh_spectrum(self)`

## `vescentcomb_addons.comb_lock.pages.lock_sequence`

Lock sequence page: f_ceo first, then the GPS cavity walk, then (optionally) OPL #2.

```python
from vescentcomb_addons.comb_lock.pages import lock_sequence
```

**Constants:** `STEP_IDS`, `STEP_TITLES`

### class `LockSequencePage(hub, settings, main=None)`

- `add_row(self)`
- `reset_params(self)`
- `params(self) -> LockParams`
- `start(self)`
- `pause(self)`
- `abort(self)`
- `save_log(self)`

## `vescentcomb_addons.comb_lock.pages.opl`

SLICE-OPL page. The comb lock module uses it for OPL #1; other modules subclass it (``OPL2Page`` in laser_lock adds the beat-check tab and the Brimrose limits note).

```python
from vescentcomb_addons.comb_lock.pages import opl
```

**Constants:** `INTEGRATOR_CORNERS_HZ`, `METRICS`, `NEEDS`

### class `OPLPage(hub, settings, main=None, role: str = None)`

- `extra_tabs(self)` — Subclasses return [(QWidget, label), …] to insert after the first tab.
- `on_devices_changed(self)`
- `choose_unit(self, i)`
- `identify(self)`
- `reread(self)`
- `read_adcs(self)`
- `on_poll(self, role, d)`
- `set_servo(self, i)`
- `set_target(self)`
- `apply_filter(self)`
- `apply_ref(self)`
- `apply_beatin(self)`
- `apply_aux(self)`
- `apply_sweep(self)`
- `apply_io(self)`
- `reboot(self)`
- `send_raw(self)`
- `start_tune(self)`
- `stop_tune(self)`

## `vescentcomb_addons.comb_lock.sim`

Simulator for this add-on: models answer the same commands as the real instrument.

```python
from vescentcomb_addons.comb_lock import sim
```

**Constants:** `BEAT_HZ_PER_C`

### class `FFCModel(world)`

- `cav_temp(self) -> float`
- `handle(self, cmd: str) -> Optional[str]`

### class `OPLModel(world, serial: str, target_mhz: float, has_beat: bool = True, pll=(0.0, 10.0, 5.0))`

- `true_beat_hz(self) -> float`
- `servo_quality(self)` — Lock lost above about -43 dB gain (used by the auto-tune simulation).
- `update_lock(self)`
- `handle(self, cmd: str) -> Optional[str]`

### `install(world) -> None`

FFC-100 on COM3, OPL #1 on COM4, SLICE-FPGA-II (the package's own TCP stand-in).

### `make_fpga_simulator()`

The package's own SLICE-FPGA-II stand-in (real TCP protocol on 127.0.0.1), with in-loop frequency noise scaled so a locked f_ceo integrates to ~0.4 rad like the real box.

## `vescentcomb_addons.comb_lock.slicefpga`

SLICE-FPGA-II (Red Pitaya / Zynq): Device wrapper around ``vescentcomb_addons.comb_lock.fpga``.

```python
from vescentcomb_addons.comb_lock import slicefpga
```

**Constants:** `CH`, `DDC_FILTERS`, `DEFAULT_HOST`, `LOCK_AFFECTING`, `LOOPS`, `LOOP_DAC`, `LOOP_KEYS`, `READ_ONLY`

### class `SliceFPGA(host: str = '192.168.0.150', impl=None, mac: str = '', port: int = 5000, config=None, f_ext: float = 20000000.0)`

- `attach(self) -> Dict[str, Any]` — Read-only reconnect: reads clock, references, DAC offsets, loop gains. Writes nothing.
- `push_config(self, clock=(external, 20000000.0), confirm: bool = False)` — Rewrites every register and ramps the 100 V boost converter. Unlocks both loops.
- `program_fpga(self, confirm: bool = False)` — Reload the bitstream (volatile). Config must be pushed again afterwards.
- `load_config(self, path: str) -> None` — Use another Vescent XML parameter file for the next push_config().
- `close(self) -> None`
- `safe_state(self) -> None` — Nothing to switch off: the loops are meant to keep running without the PC.
- `identify(self) -> Identity`
- `settings(self) -> Dict[str, Any]`
- `snapshot(self) -> Dict[str, Any]`
- `set_value(self, key: str, value: Any, allow_unlock: bool = False) -> None`
- `compare(self, profile: Dict[str, Any], rel_tol: float = 0.002) -> List[Dict[str, Any]]` — Box vs profile. Returns rows {key, box, profile, lock_affecting}. Unknown keys are skipped.
- `apply_differences(self, rows: List[Dict[str, Any]], allow_unlock: bool = False) -> Dict[str, str]` — Write the profile value for each row, then read back. Relocks what it unlocked.
- `lock(self, loop: str = ceo)`
- `unlock(self, loop: str = ceo, ramp: bool = True)` — ``ramp`` moves the manual DAC offset to where the lock sat (as the Vescent GUI does).
- `is_locked(self, loop: str = ceo) -> bool`
- `dac_position(self, dac: int = 0) -> Dict[str, float]` — DAC output now: volts, the output limits, and |V − 0 V| as a fraction of the full range (0 = centered, 0.5 = at a rail when the limits are symmetric).
- `set_dac0_center(self) -> None` — Manual DAC0 offset to 0 V (center), used before relocking f_ceo.
- `frequency_noise(self, loop: str = ceo)` — (f, S_nu [Hz²/Hz], S_phi [rad²/Hz]) of the in-loop beat, as the Vescent GUI plots it.
- `integrated_phase(self, loop: str = ceo, f_max: Optional[float] = None, max_age_s: float = 0.0) -> Optional[float]` — RMS phase (rad) of the in-loop beat, ∫S_phi from the first bin to f_max (default: Integration_limit in the XML, 5 MHz).
- `lock_and_verify(self, loop: str = ceo, max_phase_rad: float = 1.5, tries: int = 3, settle_s: float = 2.0) -> Tuple[bool, Optional[float]]` — Lock (if open), then check integrated phase. Retries; returns (ok, phase).
- `read_counters(self) -> Dict[str, Any]` — Zero-dead-time counters: ceo_err_Hz / opt_err_Hz are lock frequency errors.
- `status(self) -> Dict[str, Any]`
- `fs` *(property)*
- `spectrum(self, adc: int = 0, n: int = 16384, averages: int = 1) -> Tuple[np.ndarray, np.ndarray]` — ADC spectrum 0 – fs/2 in dBFS (Hann window, averaged).
- `iq(self, loop: str = ceo, n: int = 16384, max_points: int = 2000)` — Baseband IQ of the loop's input: ADC samples mixed with the DDC reference frequency, low-passed (boxcar ≈ 7 MHz) and decimated. Returns (I, Q, f_ref) in units of ADC full scale.
- `filter_band(self, loop: str = ceo, level_db: float = -3.0) -> Tuple[float, float, float]` — (low, centre, high) of the DDC pass band in Hz, from the firmware's filter model.
- `start_monitor(self, csv_dir: str, period_s: float = 0.25)`
- `stop_monitor(self)`
- `poll(self) -> Dict[str, Any]`

### `discover(timeout: float = 1.5) -> List[Dict[str, str]]`

UDP broadcast on 1952, replies on 1953 (the package's own discovery).

## `vescentcomb_addons.comb_lock.sliceopl`

Vescent SLICE-OPL offset phase lock (USB serial, CR, ASCII).

```python
from vescentcomb_addons.comb_lock import sliceopl
```

**Constants:** `INTEGRATOR_CORNERS_HZ`, `RAIL_V`

### class `SliceOPL(port: Optional[str] = None, baudrate: int = 115200, timeout: float = 1.0, ser=None)`

- `ser` *(property)*
- `close(self) -> None`
- `query(self, cmd: str) -> str`
- `command(self, cmd: str) -> str`
- `query_value(self, cmd: str) -> str`
- `query_float(self, cmd: str)`
- `query_int(self, cmd: str)`
- `idn(self) -> str`
- `identify(self) -> Identity`
- `reset(self) -> str`
- `get_backlight(self)`
- `set_backlight(self, level)`
- `get_volume(self)`
- `set_volume(self, level)`
- `flash_identify(self, cycles: int = 3, period_s: float = 0.4) -> None` — Blink the front-panel backlight so you can see which box this is.
- `get_servo(self)`
- `servo_on(self) -> bool`
- `set_servo(self, on)`
- `get_target_beatnote(self)`
- `set_target_beatnote(self, mhz)`
- `read_voltage(self, channel)`
- `read_all_voltages(self) -> Dict[str, Any]`
- `get_pll_invert(self)`
- `set_pll_invert(self, on)`
- `get_pll_gain(self)`
- `set_pll_gain(self, db)`
- `get_integrator_corner(self)`
- `set_integrator_corner(self, hz)`
- `get_diff_corner(self)`
- `set_diff_corner(self, hz)`
- `get_gain_clamp(self)`
- `set_gain_clamp(self, on)`
- `get_pll_bias(self)`
- `set_pll_bias(self, volts)`
- `get_pll_max(self)`
- `set_pll_max(self, volts)`
- `get_pll_min(self)`
- `set_pll_min(self, volts)`
- `set_pll_limits(self, vmin: float, vmax: float, bias: Optional[float] = None) -> None` — Set min/max (and optionally bias) in an order that never violates min<max.
- `get_lock_range(self)`
- `set_lock_range(self, volts)`
- `get_aux_enabled(self)`
- `set_aux_enabled(self, on)`
- `get_aux_invert(self)`
- `set_aux_invert(self, on)`
- `get_aux_target(self)`
- `set_aux_target(self, volts)`
- `get_aux_gain(self)`
- `set_aux_gain(self, g)`
- `get_aux_bias(self)`
- `set_aux_bias(self, volts)`
- `get_aux_max(self)`
- `set_aux_max(self, volts)`
- `get_aux_min(self)`
- `set_aux_min(self, volts)`
- `get_ramp(self)`
- `set_ramp(self, on)`
- `get_ramp_channel(self)`
- `set_ramp_channel(self, ch)`
- `get_ramp_points(self)`
- `set_ramp_points(self, n)`
- `get_ramp_freq(self)`
- `set_ramp_freq(self, hz)`
- `get_ramp_range(self)`
- `set_ramp_range(self, volts)`
- `get_ramp_adc_gain(self)`
- `set_ramp_adc_gain(self, mode)`
- `get_bn_max(self)`
- `set_bn_max(self, mhz)`
- `get_n1(self)`
- `set_n1(self, val)`
- `get_n2(self)`
- `set_n2(self, val)`
- `read_beatnote(self)`
- `read_reference(self)`
- `get_ext_ref_bw(self)`
- `set_ext_ref_bw(self, mhz)`
- `get_pfd_uses_dds(self)`
- `set_pfd_uses_dds(self, on)`
- `get_dds_internal(self)`
- `set_dds_internal(self, on)`
- `get_dds_ref_freq(self)`
- `set_dds_ref_freq(self, mhz)`
- `get_m1(self)`
- `set_m1(self, val)`
- `get_m2(self)`
- `set_m2(self, val)`
- `dds_auto(self)`
- `get_rear_mux(self)`
- `set_rear_mux(self, val)`
- `get_front_out1(self)`
- `set_front_out1(self, on)`
- `get_front_out2(self)`
- `set_front_out2(self, on)`
- `get_front_out2_mux(self)`
- `set_front_out2_mux(self, val)`
- `get_front_in_a(self)`
- `set_front_in_a(self, on)`
- `get_front_in_b(self)`
- `set_front_in_b(self, on)`
- `get_trigger_in(self)`
- `set_trigger_in(self, mode)`
- `get_trigger_out(self)`
- `set_trigger_out(self, mode)`
- `integrator_hold(self, on)`
- `get_integrator_hold(self)`
- `disable_cp(self)`
- `get_dds_freq(self)`
- `set_dds_freq(self, mhz)`
- `get_dds_raw(self)`
- `set_dds_raw(self, raw)`
- `beat_error_hz(self, counter_offset_mhz: float = 0.0) -> Optional[float]` — (target - offset - measured) in Hz. Positive = beat is LOW.
- `has_beat(self, min_mhz: float = 1.0) -> bool`
- `poll(self) -> Dict[str, Any]`
- `snapshot(self) -> Dict[str, Any]`
- `safe_state(self) -> None` — Servo state is left alone: dropping a lock on disconnect would be worse.

