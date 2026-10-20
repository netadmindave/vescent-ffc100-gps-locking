# Development

```bat
python -m pip install -e .[test]
python -m pytest                       (all tests run against the simulator)
set QT_QPA_PLATFORM=offscreen          (headless)
```

* Tests live in `tests/` (application-wide) and `vescentcomb/addons/<id>/tests/` (per module).
* Every instrument model is in its add-on's `sim.py`; extend the model when you add a command, then test it.
* Instrument knowledge confirmed on real hardware is recorded in the driver docstrings ("bench-verified");
  anything only from a manual is marked so. Keep that distinction when you add commands.
* Patches: change only the files that need changing; tests should stay quick and targeted.
