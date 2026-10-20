# Changelog

## 0.1.0 + patches 1–3
* Split from the original modular bench application (benchctl 0.4.0) as a stand-alone installation.
* Patch 1: comb lock sequence checks every lock after every step and cavity move; recover-and-retry; watchdog.
* Patch 2: Devices dialog — one row per role, no overlapping buttons.
* Patch 3: Devices dialog — VISA listing in the background (a hung USB instrument can't freeze the window).
* Command-line tool `vescent-comb-cli` (roles, scan, info, options, get, set, do, poll, status, params, lock).
