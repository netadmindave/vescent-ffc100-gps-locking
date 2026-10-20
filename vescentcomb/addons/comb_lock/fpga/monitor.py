"""
Background monitoring / logging / watchdog for a SliceFPGA, designed to run for days from a notebook.

* fixed-size ring buffer (collections.deque) -> memory does not grow
* CSV written line-by-line and flushed, one file per run (optionally rotated daily)
* plots are drawn on demand with matplotlib and closed (no persistent plot objects)
* survives a dropped TCP connection: it keeps retrying, it never writes to the box while reconnecting
"""
from __future__ import annotations

import csv
import logging
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

from .rp_pll import CommsError

log = logging.getLogger(__name__)

FIELDS = ['iso_time', 'unix_time', 'sample_n', 'ceo_err_Hz', 'opt_err_Hz',
          'dac0_V', 'dac1_V', 'dac2_V', 'dac0_frac', 'dac1_frac', 'dac2_frac', 'ceo_locked', 'event']


class Watchdog:
    """Relock policy evaluated on every new counter sample.

    A channel is 'railed' when its DAC output is within `rail_margin` (fraction of the DAC range) of a limit,
    or the counter error exceeds `max_err_Hz`, for `n_bad` consecutive samples.
    action: 'log'    -> just record the event
            'unlock' -> open the loop (GUI 'Auto Unlock')
            'relock' -> unlock (DAC offset ramped to the last good operating point) then lock again,
                        at most `max_relocks` times per `window_s`
    """

    def __init__(self, channel='ceo', action='relock', rail_margin=0.05, max_err_Hz=None, n_bad=2,
                 max_relocks=5, window_s=3600.0, settle_s=1.0):
        self.channel, self.action = channel, action
        self.rail_margin, self.max_err_Hz, self.n_bad = rail_margin, max_err_Hz, n_bad
        self.max_relocks, self.window_s, self.settle_s = max_relocks, window_s, settle_s
        self._bad = 0
        self.relock_times = deque()
        self.last_good_frac = None

    def check(self, fpga, s) -> str:
        d = 'dac0_frac' if self.channel in ('ceo', 0) else 'dac1_frac'
        err = s['ceo_err_Hz'] if self.channel in ('ceo', 0) else s['opt_err_Hz']
        frac = s[d]
        bad = not (self.rail_margin < frac < 1 - self.rail_margin)
        if self.max_err_Hz is not None and abs(err) > self.max_err_Hz:
            bad = True
        if not bad:
            self._bad = 0
            self.last_good_frac = frac
            return ''
        self._bad += 1
        if self._bad < self.n_bad:
            return ''
        self._bad = 0
        if self.action == 'log':
            return f'{self.channel} out of range (dac frac {frac:.3f}, err {err:.3g} Hz)'
        if self.action == 'unlock':
            fpga.unlock(self.channel, ramp=False)
            return f'{self.channel} railed -> unlocked'
        now = time.time()
        while self.relock_times and now - self.relock_times[0] > self.window_s:
            self.relock_times.popleft()
        if len(self.relock_times) >= self.max_relocks:
            fpga.unlock(self.channel, ramp=False)
            self.action = 'log'
            return f'{self.channel}: {self.max_relocks} relocks in {self.window_s:.0f} s -> left UNLOCKED, watchdog set to log-only'
        self.relock_times.append(now)
        fpga.unlock(self.channel, ramp=False)
        if self.last_good_frac is not None:          # put the manual offset back where the lock last sat
            dac = 0 if self.channel in ('ceo', 0) else 1
            with fpga.io:
                fpga._apply_slider(dac, self.last_good_frac * fpga.SLIDER_FULL_SCALE)
        time.sleep(self.settle_s)
        fpga.lock(self.channel)
        return f'{self.channel} railed -> relocked ({len(self.relock_times)} in window)'


class Monitor:
    """Poll the frequency counters + DAC outputs in a background thread.

    >>> mon = Monitor(fpga, csv_dir='logs', watchdog=Watchdog('ceo'))
    >>> mon.start();  ...;  mon.plot();  mon.stop()
    """

    def __init__(self, fpga, csv_dir: str | Path | None = 'slice_logs', period_s: float = 0.25,
                 history: int = 20000, watchdog: Watchdog | None = None, reconnect: bool = True,
                 rotate_daily: bool = True):
        self.fpga, self.period_s, self.watchdog, self.reconnect = fpga, period_s, watchdog, reconnect
        self.buf = deque(maxlen=history)
        self.events = deque(maxlen=1000)
        self.csv_dir = Path(csv_dir) if csv_dir else None
        self.rotate_daily = rotate_daily
        self._thread = None
        self._stop = threading.Event()
        self._fh = self._writer = None
        self._day = None
        self.csv_path = None
        self.n_samples = 0
        self.n_errors = 0

    # -------------------------------------------------------------- csv
    def _open_csv(self):
        if self.csv_dir is None:
            return
        day = time.strftime('%Y%m%d')
        if self._fh and (not self.rotate_daily or day == self._day):
            return
        if self._fh:
            self._fh.close()
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.csv_dir / f'slice_fpga_{time.strftime("%Y%m%d_%H%M%S")}.csv'
        self._fh = open(self.csv_path, 'w', newline='')
        self._writer = csv.DictWriter(self._fh, FIELDS)
        self._writer.writeheader()
        self._day = day

    def _write(self, row):
        if self._writer:
            self._writer.writerow({k: row.get(k, '') for k in FIELDS})
            self._fh.flush()

    def _event(self, msg):
        t = time.time()
        self.events.append((t, msg))
        log.warning(msg)
        self._write({'iso_time': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(t)), 'unix_time': f'{t:.3f}', 'event': msg})

    # -------------------------------------------------------------- thread
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._open_csv()
        self._thread = threading.Thread(target=self._run, name='SliceFPGA-monitor', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._fh:
            self._fh.close()
            self._fh = self._writer = None

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def _run(self):
        locked = None
        while not self._stop.is_set():
            t_next = time.time() + self.period_s
            try:
                if not self.fpga.connected:
                    if not self.reconnect or not self.fpga.reconnect(attempts=1, delay=0):
                        self._stop.wait(5.0)
                        continue
                    self._event('reconnected')
                s = self.fpga.read_counters()
                if s['new']:
                    if locked is None or s['n'] % 20 == 0:
                        locked = self.fpga.is_locked('ceo')
                    s['ceo_locked'] = int(locked)
                    if s['dropped']:
                        self._event(f"{s['dropped']} counter sample(s) missed")
                    self.buf.append(s)
                    self.n_samples += 1
                    self._open_csv()
                    self._write({'iso_time': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(s['t'])),
                                 'unix_time': f"{s['t']:.3f}", 'sample_n': s['n'],
                                 **{k: f'{s[k]:.9g}' for k in ('ceo_err_Hz', 'opt_err_Hz', 'dac0_V', 'dac1_V', 'dac2_V',
                                                               'dac0_frac', 'dac1_frac', 'dac2_frac')},
                                 'ceo_locked': s['ceo_locked']})
                    if self.watchdog and locked:
                        msg = self.watchdog.check(self.fpga, s)
                        if msg:
                            self._event(msg)
                            locked = None
            except CommsError as e:
                self.n_errors += 1
                self._event(f'comms error: {e}')
            except Exception as e:  # keep the logger alive whatever happens
                self.n_errors += 1
                self._event(f'monitor error: {e!r}')
            self._stop.wait(max(0.0, t_next - time.time()))

    # -------------------------------------------------------------- analysis
    def frame(self):
        """History as a pandas DataFrame (index = local time)."""
        import datetime as _dt
        import pandas as pd
        df = pd.DataFrame(list(self.buf))
        if len(df):
            df.index = pd.DatetimeIndex([_dt.datetime.fromtimestamp(t) for t in df['t']], name='local_time')
        return df

    def summary(self, last_s: float | None = 60) -> dict:
        rows = [r for r in self.buf if last_s is None or r['t'] > time.time() - last_s]
        if not rows:
            return {}
        e = np.array([r['ceo_err_Hz'] for r in rows])
        return {'n': len(rows), 'ceo_err_mean_Hz': float(e.mean()), 'ceo_err_std_Hz': float(e.std()),
                'dac0_frac_last': rows[-1]['dac0_frac'], 'events': len(self.events), 'comms_errors': self.n_errors}

    def plot(self, last_s: float | None = 600):
        import matplotlib.pyplot as plt
        rows = [r for r in self.buf if last_s is None or r['t'] > time.time() - last_s]
        if not rows:
            print('no data yet')
            return
        t = np.array([r['t'] for r in rows]); t = t - t[-1]
        fig, ax = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
        e = np.array([r['ceo_err_Hz'] for r in rows])
        ax[0].plot(t, e, '.-', ms=3); ax[0].set_ylabel('CEO error [Hz]')
        ax[0].set_title(f'CEO lock: mean {e.mean():.4g} Hz, std {1e3*e.std():.3g} mHz  (N={len(e)})')
        ax[1].plot(t, [r['opt_err_Hz'] for r in rows], '.-', ms=3); ax[1].set_ylabel('Optical error [Hz]')
        for d in range(3):
            ax[2].plot(t, [r[f'dac{d}_frac'] for r in rows], label=f'DAC{d}')
        m = self.watchdog.rail_margin if self.watchdog else 0.05
        for y in (m, 1 - m):
            ax[2].axhline(y, ls='--', c='0.5', lw=0.8)
        ax[2].set_ylim(-0.05, 1.05); ax[2].set_ylabel('DAC (fraction of range)'); ax[2].legend(loc='upper left')
        ax[2].set_xlabel('time [s] (0 = now)')
        for tt, _ in self.events:
            if not last_s or tt > time.time() - last_s:
                for a in ax:
                    a.axvline(tt - rows[-1]['t'], c='r', lw=0.8, alpha=0.6)
        fig.tight_layout()
        plt.show()
        plt.close(fig)
