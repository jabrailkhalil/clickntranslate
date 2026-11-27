"""Small, lazy translation executor; idle threads and HTTP sessions expire."""
from collections import deque
import threading


class IdleExecutor:
    def __init__(self, workers=16, pending=32, idle_seconds=10, cleanup=None):
        self._jobs = deque()
        self._lock = threading.Lock()
        self._ready = threading.Condition(self._lock)
        self._submission_lock = threading.RLock()
        self._capacity = pending
        self._workers = 0
        self._outstanding = 0
        self._maximum = workers
        self._idle = idle_seconds
        self._cleanup = cleanup

    def submit(self, task):
        # Finish a worker launch or its rollback before another submitter can
        # rely on that reserved worker. Running jobs never take this lock.
        with self._submission_lock:
            return self._submit(task)

    def _submit(self, task):
        start_worker = False
        # A distinct entry lets a failed worker launch withdraw only this
        # submission, even if the same callback was submitted more than once.
        entry = (object(), task)
        with self._ready:
            if self._capacity > 0 and len(self._jobs) >= self._capacity:
                return False
            self._jobs.append(entry)
            self._outstanding += 1
            if self._workers < min(self._maximum, self._outstanding):
                self._workers += 1
                start_worker = True
            self._ready.notify()
        if start_worker:
            # Do not call an external thread factory while holding the queue
            # state lock (also permits deterministic executors in tests).
            try:
                threading.Thread(target=self._run, name='Translation-network', daemon=True).start()
            except Exception:
                import logging
                logging.exception('Could not start background translation worker')
                with self._ready:
                    self._workers -= 1
                    try:
                        self._jobs.remove(entry)
                    except ValueError:
                        # An existing worker already accepted this job while
                        # the attempted pool expansion failed.
                        return True
                    self._outstanding -= 1
                    return False
        return True

    def _run(self):
        try:
            while True:
                with self._ready:
                    if not self._ready.wait_for(lambda: bool(self._jobs), timeout=self._idle):
                        self._workers -= 1
                        return
                    _token, task = self._jobs.popleft()
                try:
                    task()
                except BaseException:
                    # Like a futures work item, one aborted callback must not
                    # kill a reserved worker and strand other accepted jobs.
                    # This handler is inside the worker, not the GUI thread.
                    import logging
                    logging.exception('Background translation failed')
                finally:
                    with self._lock:
                        self._outstanding -= 1
                    task = None
        finally:
            if self._cleanup:
                self._cleanup()


def _close_api_session():
    # No API import at startup or until a translation has actually run.
    from api_providers import close_thread_session
    close_thread_session()


TRANSLATION_EXECUTOR = IdleExecutor(cleanup=_close_api_session)
