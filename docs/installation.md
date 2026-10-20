# Installation

Vescent FFC-100 GPS locking is a Windows desktop application (PySide6 / Qt) written in Python. It also runs on Linux and macOS
for development and with the simulator, but the instrument drivers are tested on Windows.

## Requirements

* Windows 10 or 11
* Python 3.11 or newer (developed on 3.14) — Anaconda or a plain python.org install both work
* A VISA library for GPIB / USB-TMC instruments: Keysight IO Libraries Suite (IVI VISA) or NI-VISA
* Ethernet to the SLICE-FPGA-II (static 192.168.0.x address on the PC)
* USB to the FFC-100 and SLICE-OPL #1 (Vescent USB-serial)

The Python dependencies (numpy, scipy, PySide6, pyqtgraph, pyserial, pyvisa) are installed
automatically.

## Install

```bat
git clone https://github.com/netadmindave/vescent-ffc100-gps-locking.git
cd vescent-ffc100-gps-locking
python -m pip install -e .
```

`-e` (editable) means updates you pull or unzip into the folder take effect without reinstalling.
For the test suite: `python -m pip install -e .[test]`.

## Launch

```bat
vescent-comb                 the application
vescent-comb --sim           against the built-in simulator (no hardware)
vescent-comb-cli -h              the command-line tool (see docs/cli.md)
```

`python -m vescentcomb.gui.app` works too.

### Windows launcher (Anaconda)

`launch_apps.bat` (in the folder above the three application folders) activates your conda environment and
offers a menu for all three applications, without console windows. Set `CONDA_ENV` at the top of the file to the
environment you installed into. Its option **4** runs `pip install -e .` in each application folder; **D**
starts an application with a console window, to see why it won't start.

## Check the install

```bat
python -m pytest            (needs the [test] extra; everything runs against the simulator)
vescent-comb --sim
```
