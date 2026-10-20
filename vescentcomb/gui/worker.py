"""One worker thread per device: a job queue plus a ~1 Hz poll.

Every device call from the GUI goes through ``hub.call(role, fn, on_done)``; ``fn``
runs in that device's thread with the device as its only argument, and the result
comes back to the GUI thread through a queued Qt signal. A slow GPIB call never
freezes the window.
"""
from __future__ import annotations

import os
import queue
import threading
import time
import traceback
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QObject, Signal, Slot


class DeviceWorker(QObject):
    polled = Signal(str, dict)                    # role, data
    state = Signal(str, str, str)                 # role, ok|error|closed, message
    _done = Signal(object, object, object, object)  # on_done, on_error, result, exc

    #: consecutive poll failures before the worker tries to reopen the instrument
    FAILS_BEFORE_RECONNECT = 3
    #: seconds between reconnect attempts (the last value repeats)
    RECONNECT_BACKOFF = (2, 5, 10, 20, 30, 60)

    def __init__(self, role: str, device: Any, poll_s: float = 1.0,
                 reopen: Optional[Callable[[], Any]] = None, on_reopen: Optional[Callable[[Any], None]] = None):
        super().__init__()
        self.role = role
        self.device = device
        self.poll_s = poll_s
        self.reopen = reopen                 # () -> new device; None = no auto-reconnect
        self.on_reopen = on_reopen           # hooks to run on the new device (register formats …)
        self.auto_reconnect = reopen is not None
        self.fails = 0
        self.reconnecting = False
        self._next_try = 0.0
        self._tries = 0
        self.poll_enabled = True
        self.last: Dict[str, Any] = {}
        self.last_ok = 0.0
        self._q: "queue.Queue" = queue.Queue()
        self._running = True
        self._done.connect(self._deliver)
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"worker-{role}")
        self._thread.start()

    def call(self, fn: Callable[[Any], Any], on_done: Optional[Callable[[Any], None]] = None,
             on_error: Optional[Callable[[Exception], None]] = None) -> None:
        self._q.put((fn, on_done, on_error))

    def stop(self, safe: bool = True, timeout: float = 5.0, wait: bool = True) -> threading.Event:
        """Close the device in its own thread. Pending jobs are dropped first, so a backlog (or one slow
        call) doesn't hold up closing. ``wait=False`` returns at once with an Event set when it's closed."""
        done = threading.Event()
        self.poll_enabled = False
        self.auto_reconnect = False
        while True:                                    # drop queued jobs; the one running now finishes
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

        def _shutdown(dev):
            if safe:
                try:
                    dev.safe_state()
                except Exception:
                    pass
            try:
                dev.close()
            except Exception:
                pass
            done.set()

        self._q.put((_shutdown, None, None))
        self._q.put(None)
        if wait:
            done.wait(timeout)
            self._running = False
        return done

    @Slot(object, object, object, object)
    def _deliver(self, on_done, on_error, result, exc):
        if exc is not None:
            if on_error:
                on_error(exc)
            else:
                self.state.emit(self.role, "error", str(exc))
        elif on_done:
            on_done(result)

    def _emit(self, sig, *args) -> bool:
        """Emit unless the Qt side is already gone (app shutting down)."""
        try:
            sig.emit(*args)
            return True
        except RuntimeError:
            self._running = False
            return False

    # ---- auto-reconnect ------------------------------------------------------------------------
    def _start_reconnect(self, why) -> None:
        self.reconnecting = True
        self._tries = 0
        self._next_try = time.time()
        self._emit(self.state, self.role, "reconnecting", f"lost contact ({why}); reconnecting")
        try:
            self.device.close()
        except Exception:
            pass

    def _try_reconnect(self) -> None:
        if time.time() < self._next_try:
            return
        self._tries += 1
        try:
            dev = self.reopen()
            if self.on_reopen:
                self.on_reopen(dev)
            dev.poll() if hasattr(dev, "poll") else None
        except Exception as e:
            delay = self.RECONNECT_BACKOFF[min(self._tries - 1, len(self.RECONNECT_BACKOFF) - 1)]
            self._next_try = time.time() + delay
            self._emit(self.state, self.role, "reconnecting", f"attempt {self._tries} failed ({e}); next in {delay} s")
            return
        self.device = dev
        self.reconnecting = False
        self.fails = 0
        self._emit(self.state, self.role, "reconnected", f"reconnected after {self._tries} attempt(s)")

    def _loop(self):
        next_poll = time.time()
        while self._running:
            timeout = max(0.0, next_poll - time.time()) if self.poll_enabled else 0.5
            try:
                job = self._q.get(timeout=timeout)
            except queue.Empty:
                job = "poll"
            if job is None:
                break
            if job == "poll":
                if self.reconnecting:
                    self._try_reconnect()
                    next_poll = time.time() + min(self.poll_s, 1.0)
                    continue
                if not self.poll_enabled or not hasattr(self.device, "poll"):
                    next_poll = time.time() + self.poll_s
                    continue
                try:
                    data = self.device.poll()
                    self.last = data
                    self.last_ok = time.time()
                    ok = True
                except Exception as e:
                    ok, data = False, e
                if ok:
                    self.fails = 0
                    self._emit(self.polled, self.role, data) and self._emit(self.state, self.role, "ok", "")
                else:
                    self.fails += 1
                    self._emit(self.state, self.role, "error", f"poll: {data}")
                    if self.auto_reconnect and self.fails >= self.FAILS_BEFORE_RECONNECT:
                        self._start_reconnect(data)
                next_poll = time.time() + self.poll_s
                continue
            fn, on_done, on_error = job
            if self.reconnecting and getattr(fn, "__name__", "") != "_shutdown":
                self._emit(self._done, on_done, on_error, None,
                           ConnectionError(f"{self.role} is reconnecting; try again in a moment"))
                continue
            try:
                res = fn(self.device)
                self._emit(self._done, on_done, on_error, res, None)
            except Exception as e:
                traceback.print_exc()
                self._emit(self._done, on_done, on_error, None, e)
        self._emit(self.state, self.role, "closed", "")


class Hub(QObject):
    """All workers, the event log and the poll logger."""
    log = Signal(str, str)              # tag, message
    polled = Signal(str, dict)
    state = Signal(str, str, str)
    devices_changed = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.workers: Dict[str, DeviceWorker] = {}
        self.found: Dict[str, Any] = {}        # role -> discovery.Found
        self.scan = None
        self.logging = False
        self.log_dir = ""
        self.log_t0 = 0.0
        self._log_files: Dict[str, Any] = {}

    # ---- devices ----------------------------------------------------------------------
    def attach(self, role: str, device: Any, found=None, poll_s: float = 1.0,
               reopen=None, on_reopen=None) -> DeviceWorker:
        if role in self.workers:
            self.detach(role)
        if not self.settings.get("ui.auto_reconnect", True):
            reopen = None
        w = DeviceWorker(role, device, poll_s, reopen=reopen, on_reopen=on_reopen)
        w.polled.connect(self._on_poll)
        w.state.connect(self._on_state)
        self.workers[role] = w
        if found is not None:
            self.found[role] = found
        self.devices_changed.emit()
        return w

    def _on_state(self, role: str, state: str, msg: str):
        if state in ("reconnecting", "reconnected"):
            self.emit_log(role.upper(), msg)
            if state == "reconnected":
                self.devices_changed.emit()
        self.state.emit(role, state, msg)

    def detach(self, role: str, safe: bool = True, wait: bool = True):
        """Stop the role's worker. With ``wait=False`` the window never blocks: the returned Event is
        set once the instrument is closed."""
        w = self.workers.pop(role, None)
        ev = w.stop(safe, wait=wait) if w else None
        self.devices_changed.emit()
        return ev

    def close_all(self, safe: bool = True, timeout: float = 2.0):
        """Close every instrument in parallel and wait at most ``timeout`` seconds in total (worker
        threads are daemons, so one stuck on a slow port can't stop the app from exiting)."""
        events = [w.stop(safe, wait=False) for w in self.workers.values()]
        self.workers.clear()
        deadline = time.time() + timeout
        for ev in events:
            ev.wait(max(0.0, deadline - time.time()))
        self.devices_changed.emit()
        self.stop_logging()

    def has(self, role: str) -> bool:
        return role in self.workers

    def device(self, role: str):
        w = self.workers.get(role)
        return w.device if w else None

    def call(self, role: str, fn, on_done=None, on_error=None, log: Optional[str] = None):
        w = self.workers.get(role)
        if not w:
            self.emit_log(role.upper(), "not connected")
            return False

        def _err(e):
            self.emit_log(role.upper(), f"error: {e}")
            if on_error:
                on_error(e)

        def _ok(r):
            if log:
                self.emit_log(role.upper(), log)
            if on_done:
                on_done(r)

        w.call(fn, _ok, _err)
        return True

    def last(self, role: str) -> Dict[str, Any]:
        w = self.workers.get(role)
        return w.last if w else {}

    def emit_log(self, tag: str, msg: str):
        self.log.emit(tag, msg)

    # ---- data logging ---------------------------------------------------------------------
    def start_logging(self, folder: str):
        os.makedirs(folder, exist_ok=True)
        self.log_dir = folder
        self.log_t0 = time.time()
        self.logging = True
        self.emit_log("LOG", f"recording polls → {folder}")

    def stop_logging(self):
        self.logging = False
        for f, _ in self._log_files.values():
            f.close()
        self._log_files.clear()

    def _on_poll(self, role: str, data: dict):
        self.polled.emit(role, data)
        if not self.logging:
            return
        flat = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "elapsed_s": round(time.time() - self.log_t0, 3)}
        for k, v in data.items():
            if isinstance(v, (int, float, str, bool)) or v is None:
                flat[k] = v
        if role not in self._log_files:
            from ..datafile import CSVLog
            self._log_files[role] = (CSVLog(os.path.join(self.log_dir, f"{role}.csv"), kind=f"REC log · {role}"), None)
        self._log_files[role][0].write(flat)
