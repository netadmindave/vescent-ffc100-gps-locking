# Troubleshooting

**An instrument shows "opened …, but the instrument didn't answer".** The VISA address or COM port opened but
nothing replied: check power, the cable and the address (GPIB address on the front panel). Opening an address
always succeeds in VISA, so only an answer counts as connected.

**"in use by …".** Another of the bench applications has that instrument connected. Disconnect it there
(or close that application). A claim left by a crashed application is ignored automatically.

**A VISA instrument hangs the bus (e.g. the Rigol after an interrupted transfer).** Power-cycle the instrument.
The application keeps working: scans run in the background and report "VISA is not answering".

**Nothing found in Devices → Rescan.** Check the instrument is on and that Keysight Connection Expert / NI MAX
sees it. Serial instruments: check Device Manager for the COM port.

**The app won't start from the launcher.** Use option **D** in `launch_apps.bat` to see the error in a console.
"No module named …" → run option **4** (install), or set `CONDA_ENV` to the environment you installed into.

**Where is the log?** Devices → Logs…, or `vescentcomb.log` next to the settings file.

**"Lock f_ceo" loops.** The FFC PZT-range check (`CADCBV?`) is off by default for this reason; leave it off until
you know what it reads when locked.

**Re-selecting the FPGA's external clock.** Doesn't unlock f_ceo (fixed); if it ever does, report it with the log.

**The comb status file.** `comb_status.json` next to the settings file is rewritten about once a second; Laser
Lock reads it. If Laser Lock says the comb app isn't running, check this file's time stamp.
