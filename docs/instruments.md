# Instruments

| Role | Instrument | Connection | Notes (bench-verified unless marked) |
|---|---|---|---|
| `ffc` | Vescent FFC-100 | USB-serial (non-FTDI), `*IDN?` with CR LF | `PZTMOMD` 0/1/2 = Off/×1/×10 (inferred); mode-locked needs `MODELOK?` ON and `MSTRCTL?` = 2; `CADCBV?` meaning unknown |
| `fpga` | Vescent SLICE-FPGA-II | Ethernet, static 192.168.0.x | good f_ceo lock: integrated phase < 1.5 rad; DAC0 ≈ ±10 V, center 0 V |
| `opl1` | Vescent SLICE-OPL #1 | USB-serial, `*IDN?` with CR | f_rep → GPS 10 MHz; told apart from OPL #2 by serial number |

**Still to verify on the bench:** the PZTMOMD mapping, what `CADCBV?` reads, and the watchdog / DAC0 thresholds.
