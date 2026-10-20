# User guide

## Main window

The left bar lists the pages; the chain pills at the top show GPS → FFC → f_ceo → f_rep at a glance. **Devices…**
assigns instruments; **Logs…** shows the log; **Settings** holds application options ("Ask before actions"
brings back confirmation dialogs; by default there are none).

## Overview

Each instrument's connection and key readings, and the 10 MHz reference panel.

## Comb lock sequence

The **Run** button performs, in order:

1. **Pre-checks** — comb mode-locked (`MODELOK?` ON *and* laser state LASER ON) and GPS 10 MHz present at OPL #1.
2. **Attach the FPGA read-only.**
3. **Fix profile differences** — only settings that differ from your saved profile are written.
4. **Lock f_ceo** — locked when the integrated phase is below the limit (1.5 rad by default).
5. **Check OPL #1.**
6. **Cavity walk** — steps the cavity setpoint until the f_rep beat error is inside the window.
7. **Confirm** — the error stays inside the window for the dwell time.
8. **OPL #1 servo on**, then **9. FFC slow servo on**.

After every step and every cavity move, all locks made so far are re-checked (mode lock; f_ceo lock, phase and
DAC0 within 15 % of its range from 0 V; OPL #1 servo; slow servo). On a fault the sequence recovers and retries
(3 tries, 10 s apart). DAC0 too far from center unlocks f_ceo and OPL #1, sets DAC0 to 0 V and restarts.

**Pause / Stop** act between actions; every wait has a timeout; **Dry run** checks without writing.

**Watchdog** (checkbox): every 5 s; acts on a problem lasting 10 s (DAC0 at once); at most 6 relocks per hour;
holds off while you run the sequence.

## FFC-100 page

Laser state, mode lock, temperatures, PZT mode **Off / ×1 / ×10** (`PZTMOMD 0/1/2`, read back beside the buttons),
slow servo, cavity setpoint.

## SLICE-FPGA-II page

* **⬇ Write profile → box (ticked rows)** sends your profile values to the FPGA; **⬆ Save box → profile** copies
  what the box runs into the profile on this PC (nothing is sent).
* **Input spectrum** and **baseband IQ** plots, each with Refresh and "Auto-refresh every 5 s".
* **Monitor**: DAC0 distance from center as % of range.

## SLICE-OPL #1 page

Target, dividers, servo, filter, limits, AUX servo and sweep; **Identify** flashes the backlight (the two OPLs
look alike). **Auto-tune** optimises the servo filter for the lowest Allan deviation of the counter.

## Devices dialog

Roles on the left, scan results on the right; **Rescan** probes every port. Vescent USB-serial ports are probed
with `*IDN?` (CR for the OPL, CR LF for the FFC-100); FTDI ports are left alone (WB-SG2).
