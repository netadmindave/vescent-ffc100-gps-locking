# Fake monitor-tcp server: speaks the RP_PLL wire protocol well enough for the GUI / new module to run,
# and records every register write so two clients can be compared register-for-register.
import socket, struct, threading, time
import numpy as np

WR, RD, BUF, WF, SH, RB = 0xABCD1233, 0xABCD1234, 0xABCD1235, 0xABCD1237, 0xABCD1238, 0xABCD1239
BASE, AXI = 0x40000000, 0x80000000

regs = {}            # absolute address -> last written uint32
writes = []          # (absolute address, uint32) in order
shell = []           # shell commands received
stats = {'bytes_in': 0, 'bytes_out': 0, 'cmds': 0}
lock = threading.Lock()
_t0 = time.time()

# read-only / live registers
CLKW_STATUS = AXI + 0x0002_0000 + 0x04
ZDTC_N      = BASE + 0x30 * 4


def mark():
    """Return an index into `writes` (use with since())."""
    return len(writes)


def since(i):
    return writes[i:]


def state():
    return dict(regs)


def reset():
    with lock:
        regs.clear(); writes.clear(); shell.clear()


def _read(a):
    if a == CLKW_STATUS:
        return 1
    if a == ZDTC_N:
        return int((time.time() - _t0) * 2) & 0xFFFFFFFF   # new counter sample every 0.5 s
    return regs.get(a, 0)


def _recvall(c, n):
    b = b''
    while len(b) < n:
        x = c.recv(n - len(b))
        if not x:
            return None
        b += x
    return b


def _handle(c):
    rng = np.random.default_rng(0)
    while True:
        h = _recvall(c, 12)
        if h is None:
            return
        magic, a, d = struct.unpack('=III', h)
        stats['cmds'] += 1; stats['bytes_in'] += 12
        if magic == WR:
            with lock:
                regs[a] = d; writes.append((a, d))
                if BASE <= a < BASE + (1 << 20):          # dpll_wrapper keeps a RAM shadow readable at +(2<<20)
                    regs[a + (2 << 20)] = d
        elif magic == RD:
            c.sendall(struct.pack('=I', _read(a) & 0xFFFFFFFF)); stats['bytes_out'] += 4
        elif magic == BUF:
            arr = (rng.standard_normal(d) * 2000).astype(np.int16)
            if d > 8:
                arr[8] = np.int16(-22385)   # 0xA88F sync word expected by the ADC framing
            data = arr.tobytes()
            c.sendall(data); stats['bytes_out'] += len(data)
        elif magic == WF:
            _recvall(c, a); _recvall(c, d)
        elif magic == SH:
            shell.append(_recvall(c, a))
        elif magic == RB:
            pass
        else:
            print('fake_rp: unknown magic', hex(magic)); return


_server = {}


def serve(port=5000):
    if port in _server:
        return
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', port)); s.listen(5)
    _server[port] = s

    def loop():
        while True:
            c, _ = s.accept()
            threading.Thread(target=_handle, args=(c,), daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
