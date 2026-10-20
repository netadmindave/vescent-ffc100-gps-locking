"""
Replay the same actions with the new package that were recorded from the ORIGINAL Vescent GUI
(record_gui.py, Python 3.9 + PyQt5) and compare the FPGA register state after every step.

usage: python tests/verify_against_gui.py rec_gui_ucf.json
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), *['..'] * 5)))
import fake_slice_server as fake
from vescentcomb import addonkit
addonkit.load("comb_lock")
fake.serve(5000)
from vescentcomb_addons.comb_lock.fpga import SliceFPGA

rec = json.load(open(sys.argv[1]))
fpga = SliceFPGA('127.0.0.1', 5000)
fake.reset()

steps = [('push_defaults', lambda: fpga.push_config(clock='config')),
         ('ext_clock_20MHz', lambda: fpga.set_clock(True, 20e6)),
         ('ceo_lock', lambda: fpga.lock('ceo')),
         ('ceo_unlock', lambda: fpga.unlock('ceo')),
         ('opt_lock', lambda: fpga.lock('optical')),
         ('opt_unlock', lambda: fpga.unlock('optical'))]

BASE = 0x40000000
PLL1_GAINS = {hex(BASE + 4 * a) for a in range(0x7011, 0x7016)} | {hex(BASE + (2 << 20) + 4 * a) for a in range(0x7011, 0x7016)}
names = {0x7011: 'PLL1_gain_p', 0x7012: 'PLL1_gain_i', 0x7013: 'PLL1_gain_ii', 0x7014: 'PLL1_gain_d', 0x7015: 'PLL1_coef_d'}

ok = True
for name, fn in steps:
    i = fake.mark()
    fn()
    fpga.sl.dev.read_Zynq_register_uint32(0)          # barrier
    mine = {hex(a): v for a, v in fake.state().items()}
    gui = rec[name]['state']
    keys = sorted(set(mine) | set(gui))
    diff = [k for k in keys if mine.get(k) != gui.get(k)]
    expected = [k for k in diff if k in PLL1_GAINS and name in ('push_defaults', 'ext_clock_20MHz', 'ceo_lock', 'ceo_unlock')]
    unexpected = [k for k in diff if k not in expected]
    seq_gui = [(int(a, 16), d) for a, d in rec[name]['writes']]
    seq_me = list(fake.since(i))
    dedup = lambda q: [w for k, w in enumerate(q) if k == 0 or w != q[k - 1]]   # GUI writes some offsets twice (signal + explicit call)
    same_seq = 'identical order' if dedup(seq_gui) == dedup(seq_me) else 'different order/count'
    print(f'{name:16s} registers compared: {len(keys):3d}  identical: {len(keys)-len(diff):3d}  '
          f'known-benign diffs: {len(expected)}  UNEXPECTED: {len(unexpected)}   '
          f'writes GUI {len(seq_gui)} / new {len(seq_me)} ({same_seq})')
    for k in unexpected:
        print(f'      {k}: GUI={gui.get(k)} new={mine.get(k)}')
    ok &= not unexpected
print('\nPLL1 gain registers differ only while the optical lock is OFF: the GUI writes them with an un-initialised')
print('open-loop gain (kc=1) at push time; the new code uses the real kc. They converge at the first optical lock.')
print('\nRESULT:', 'MATCH' if ok else 'MISMATCH')
sys.exit(0 if ok else 1)
