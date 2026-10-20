# Drive the ORIGINAL Vescent GUI (Python 3.9, PyQt5, pyqtgraph 0.11) against the recording fake server
# and dump the register writes for each user action.
import sys, os, json, types, ctypes
CODE, OUT, SERIAL = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_slice_server as fake_rp; fake_rp.serve(5000)
sys.path.append(CODE); os.chdir(CODE)
import pyqtgraph  # noqa: F401  (must import before the windll stub)
ctypes.windll = types.SimpleNamespace(shell32=types.SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=lambda x: None))
import XEM_GUI3

ctrl = XEM_GUI3.controller(bManualStartupForTests=True)
try:
    ctrl.initial_config.close()
except Exception:
    pass
fake_rp.reset()
rec = {}

def step(name, fn):
    i = fake_rp.mark()
    fn()
    ctrl.sl.dev.read_Zynq_register_uint32(0)   # round-trip: server has processed all prior writes
    rec[name] = {'writes': [[hex(a), d] for a, d in fake_rp.since(i)], 'state': {hex(a): v for a, v in fake_rp.state().items()}}
    print(name, len(rec[name]['writes']), 'writes')

step('push_defaults', lambda: ctrl.pushDefaultValues(SERIAL, '127.0.0.1', 5000))

def ext_clock():
    ctrl.RP_Settings.qedit_extclk_target_freq.setText('20e6')
    ctrl.RP_Settings.manualSetClkSelect()
step('ext_clock_20MHz', ext_clock)

w0, w1 = ctrl.xem_gui_mainwindow, ctrl.xem_gui_mainwindow2
def lock(w, on):
    w.qchk_lock.setChecked(on); w.chkLockClickedEvent()
step('ceo_lock', lambda: lock(w0, True))
step('ceo_unlock', lambda: lock(w0, False))
step('opt_lock', lambda: lock(w1, True))
step('opt_unlock', lambda: lock(w1, False))

json.dump(rec, open(OUT, 'w'), indent=0)
