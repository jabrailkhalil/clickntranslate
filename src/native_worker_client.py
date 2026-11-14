"""One demand-started OCR process, with bounded output and no idle polling.

Importing this module creates no thread, timer, process or model. The child
expires itself after five idle minutes; active workflows can pin it. Older
component adapters continue to use the cancellable one-shot path.
"""
import atexit
import json
import os
import queue
import subprocess
import threading
import time

PROTOCOL = 2
MAX_RESPONSE = 16 * 1024 * 1024


class WorkerCancelled(InterruptedError):
    pass


class WorkerBusy(RuntimeError):
    """A different model is active; use an independent one-shot request."""


def check_cancel(callback):
    if callback is not None and callback():
        raise WorkerCancelled('OCR canceled')


class NativeWorkerClient:
    def __init__(self):
        self._lock = threading.Lock()
        self._process = None
        self._identity = None
        self._responses = None
        self._reader = None
        self._sequence = 0
        self._shutdown = threading.Event()
        self._job_close = None
        self.last_memory_bytes = None
        self._isolation_unavailable = False
        self._engine = None
        self._has_model = False
        self._activity_lock = threading.Lock()
        self._activities = {}

    def activity(self, owner, engine=None):
        """Update ownership without I/O, threads, or loading any model."""
        with self._activity_lock:
            if engine is None:
                return self._activities.pop(owner, None) is not None
            engine = str(engine).lower()
            changed = self._activities.get(owner) != engine
            self._activities[owner] = engine
            return changed

    def is_pinned(self, engine):
        with self._activity_lock:
            return engine is not None and engine in self._activities.values()

    def _send_policy(self):
        if self._process is not None and self._process.poll() is None and self._has_model:
            data = {'control': 'retention', 'pinned': self.is_pinned(self._engine)}
            self._process.stdin.write(json.dumps(data).encode('utf-8') + b'\n')
            self._process.stdin.flush()

    def refresh_policy(self, selected_engine=None):
        """Called by the readiness worker, never synchronously by the GUI."""
        with self._lock:
            if (selected_engine is not None and selected_engine != self._engine
                    and not self.is_pinned(self._engine)):
                self._stop()
                return
            try:
                self._send_policy()
            except (OSError, ValueError):
                self._stop()

    def retire_engine(self, engine):
        with self._lock:
            if self._engine == str(engine).lower():
                self._stop()

    def _stop(self):
        process, self._process = self._process, None
        self._identity = None
        self._engine = None
        self._has_model = False
        if process is None:
            return
        try:
            if process.poll() is None:
                process.kill()
            # Reap before releasing leases or deleting input images.
            process.wait(timeout=10)
        finally:
            if self._job_close is not None:
                self._job_close()
                self._job_close = None
            if process.stdin:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            # Thread.start() may fail after the reader has been assigned.
            # Cleanup must preserve that error and still close both pipes.
            if self._reader is not None and self._reader.is_alive():
                self._reader.join(timeout=2)
            if process.stdout:
                process.stdout.close()
            self._reader = self._responses = None

    def close(self):
        with self._lock:
            self._stop()

    def shutdown(self):
        self._shutdown.set()
        self.close()

    def _read(self, responses, deadline, cancel):
        while True:
            check_cancel(cancel)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('OCR worker timed out')
            try:
                result = responses.get(timeout=min(.05, remaining))
            except queue.Empty:
                continue
            if isinstance(result, Exception):
                raise result
            return result

    def _start(self, command, identity, environment, deadline, cancel, on_exit, engine):
        responses = queue.Queue(maxsize=2)
        process = subprocess.Popen([*command, '--serve'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), close_fds=True)
        self._process, self._responses, self._identity = process, responses, identity
        self._engine = engine
        from worker_lease import owned_job, WorkerIsolationUnavailable
        try:
            self._job_close = owned_job(process)
        except WorkerIsolationUnavailable:
            self._isolation_unavailable = True
            raise

        def read_responses():
            try:
                while True:
                    line = process.stdout.readline(MAX_RESPONSE + 1)
                    if not line:
                        raise EOFError('OCR worker exited')
                    if len(line) > MAX_RESPONSE or not line.endswith(b'\n'):
                        raise ValueError('OCR response exceeds the protocol limit')
                    result = json.loads(line)
                    if not isinstance(result, dict):
                        raise ValueError('Invalid OCR response')
                    responses.put_nowait(result)
            except Exception as error:
                try:
                    responses.put_nowait(error)
                except queue.Full:
                    pass
            finally:
                if on_exit is not None:
                    try:
                        on_exit()
                    except Exception:
                        import logging
                        logging.exception('OCR retirement maintenance failed')

        self._reader = threading.Thread(target=read_responses, name='OCR-response', daemon=True)
        self._reader.start()
        ready = self._read(responses, deadline, cancel)
        if ready.get('protocol') != PROTOCOL:
            raise ValueError('Unsupported OCR worker protocol')

    def request(self, command, identity, request_path, *, environment=None, timeout=1800, cancel=None,
                fallback_for_other_model=False, on_exit=None, engine=None, prepare_only=False,
                background=False):
        # At most one active model. Waiters retain no processes or decoded
        # model copies; cancellation works while waiting as well as computing.
        requested_cancel = cancel
        if self._isolation_unavailable:
            from worker_lease import WorkerIsolationUnavailable
            raise WorkerIsolationUnavailable('Use one-shot OCR in this host')
        cancel = lambda: self._shutdown.is_set() or (requested_cancel is not None and requested_cancel())
        deadline = time.monotonic() + timeout
        if background and self._lock.locked():
            check_cancel(cancel)
            raise WorkerBusy('Foreground OCR has priority')
        if fallback_for_other_model and self._lock.locked() and self._identity != identity:
            check_cancel(cancel)
            raise WorkerBusy('A different OCR model is active')
        while not self._lock.acquire(timeout=.05):
            check_cancel(cancel)
            if background:
                raise WorkerBusy('Foreground OCR has priority')
            if fallback_for_other_model and self._identity != identity:
                raise WorkerBusy('A different OCR model is active')
            if time.monotonic() >= deadline:
                raise TimeoutError('OCR queue timed out')
        try:
            check_cancel(cancel)
        except BaseException:
            # No request was sent; this caller does not own the retained model.
            self._lock.release()
            raise
        try:
            if (self._process is not None and self._process.poll() is None
                    and self._identity != identity and self.is_pinned(self._engine)
                    and (background or fallback_for_other_model)):
                raise WorkerBusy('An active OCR workflow owns the current model')
            if (self._process is not None and
                    (self._identity != identity or self._process.poll() is not None)):
                self._stop()
            if prepare_only and self._has_model:
                self._send_policy()
                return {'prepared': True, 'available': True, 'error': ''}
            for attempt in range(2):
                try:
                    if self._process is None:
                        self._start(command, identity, environment, deadline, cancel, on_exit, engine)
                    self._sequence += 1
                    sequence = self._sequence
                    data = json.dumps({'id': sequence, 'path': os.fspath(request_path),
                                       'pinned': self.is_pinned(engine)}).encode('utf-8')
                    self._process.stdin.write(data + b'\n')
                    self._process.stdin.flush()
                    result = self._read(self._responses, deadline, cancel)
                    if type(result.get('id')) is not int or result['id'] != sequence:
                        raise ValueError('Mismatched OCR response')
                    if (not isinstance(result.get('result'), dict)
                            or type(result.get('retain', False)) is not bool):
                        raise ValueError('Invalid OCR response')
                    self.last_memory_bytes = result.get('resident_bytes')
                    self._has_model = result.get('retain', False)
                    if not self._has_model:
                        self._stop()
                        if prepare_only:
                            return {'prepared': False, 'available': False, 'error': result['result'].get('error', '')}
                    return result['result']
                except (EOFError, BrokenPipeError):
                    # The child may reach its idle deadline just before send.
                    # Recognition is read-only, so retrying this race is safe.
                    self._stop()
                    if attempt:
                        raise
        except WorkerBusy:
            # Declining optional preparation must not retire the model owned
            # by a running game/session. Foreground callers can use one-shot.
            raise
        except BaseException:
            self._stop()
            raise
        finally:
            self._lock.release()


OCR_CLIENT = NativeWorkerClient()
atexit.register(OCR_CLIENT.shutdown)
