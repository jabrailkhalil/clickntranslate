"""Prepare only an explicitly selected OCR; coalesce changes off the GUI.

Importing this module creates no process, thread, timer or model. Active OCR
workflows own retention tokens; text/API translation does not pin OCR.
"""
import atexit
import logging
import sys
import threading
from contextlib import contextmanager


class ReadinessService:
    def __init__(self, client, prepare):
        self.client = client
        self.prepare = prepare
        self._lock = threading.Lock()
        self._submission_lock = threading.RLock()
        self._selection = None
        self._revision = 0
        self._pending_prepare = False
        self._pending_policy = False
        self._cancel = threading.Event()
        self._running = False
        self._closed = False
        self._retired = set()
        self.idle = threading.Event()
        self.idle.set()

    def _reserve_worker(self):
        if self._running or self._closed:
            return False
        self._running = True
        self.idle.clear()
        return True

    def _start(self, needed):
        if needed:
            try:
                threading.Thread(target=self._run, name='OCR-readiness', daemon=True).start()
            except (OSError, RuntimeError):
                with self._lock:
                    self._running = False
                    self.idle.set()
                # Keep pending work available for a later explicit request.
                # Optional preparation must not abort the GUI action.
                logging.getLogger(__name__).debug('OCR readiness launch failed', exc_info=True)

    def select(self, engine, language):
        selection = (str(engine).lower(), str(language or 'en'))
        # Serialize only admission: a newer selection must not return while
        # the reserved thread can still fail to start. _run never takes this
        # lock, so preparation and policy I/O remain outside the transaction.
        with self._submission_lock:
            with self._lock:
                if self._closed:
                    return
                if selection != self._selection:
                    self._cancel.set()
                    self._cancel = threading.Event()
                    self._selection = selection
                    self._revision += 1
                    self._pending_prepare = self._pending_policy = True
                elif not (self._pending_prepare or self._pending_policy):
                    return
                start = self._reserve_worker()
            self._start(start)

    def activity(self, owner, engine=None):
        with self._submission_lock:
            with self._lock:
                if self._closed:
                    return
                if self.client.activity(owner, engine):
                    self._pending_policy = True
                if not self._pending_policy:
                    return
                start = self._reserve_worker()
            self._start(start)

    def invalidate(self, engine):
        with self._submission_lock:
            with self._lock:
                if self._closed:
                    return
                if self._selection is not None and self._selection[0] == str(engine).lower():
                    self._cancel.set()
                    self._selection = ('', '')
                    self._revision += 1
                    self._pending_prepare = False
                self._pending_policy = True
                self._retired.add(str(engine).lower())
                start = self._reserve_worker()
            self._start(start)

    def _run(self):
        while True:
            with self._lock:
                if self._closed or not (self._pending_prepare or self._pending_policy):
                    self._running = False
                    self.idle.set()
                    return
                selection = self._selection
                retired, self._retired = self._retired, set()
                revision = self._revision
                prepare = self._pending_prepare
                self._pending_prepare = self._pending_policy = False
                cancel = self._cancel
            try:
                for engine in retired:
                    self.client.retire_engine(engine)
                # Release an idle previous engine, but never stop a currently
                # owned OCR workflow just because a different tab was selected.
                selected_engine = selection[0] if selection else None
                self.client.refresh_policy(selected_engine)
                if prepare and selected_engine is not None and not cancel.is_set():
                    self.prepare(*selection, cancel.is_set)
                with self._lock:
                    current = revision == self._revision and not self._closed
                if current:
                    self.client.refresh_policy(selected_engine)
            except InterruptedError:
                pass
            except Exception:
                # Preparation is optional; the actual OCR action still owns
                # localized error reporting and the compatible one-shot path.
                logging.getLogger(__name__).debug('Selected OCR preparation failed', exc_info=True)

    def shutdown(self):
        with self._lock:
            self._closed = True
            self._cancel.set()
        self.client.shutdown()
        self.idle.wait(2)


def _prepare(engine, language, cancel):
    from ocr import prepare_selected_ocr
    return prepare_selected_ocr(engine, language, cancel_check=cancel)


from native_worker_client import OCR_CLIENT

SERVICE = ReadinessService(OCR_CLIENT, _prepare)
atexit.register(SERVICE.shutdown)


def _automatic_enabled():
    # Layout/locale tests must not spawn native engines while constructing UI.
    for name in ('main', '__main__'):
        if getattr(sys.modules.get(name), 'LAYOUT_EDITOR_MODE', False):
            return False
    return True


def selected(config, language=None):
    if _automatic_enabled():
        source = language or config.get('last_ocr_language') or config.get('ocr_translate_source_language') or 'en'
        SERVICE.select(config.get('ocr_engine', ''), source)


def begin_activity(owner, engine):
    if _automatic_enabled():
        SERVICE.activity(owner, engine)


def end_activity(owner):
    if _automatic_enabled():
        SERVICE.activity(owner)


def invalidate(engine):
    if _automatic_enabled():
        SERVICE.invalidate(engine)


@contextmanager
def activity(owner, engine):
    begin_activity(owner, engine)
    try:
        yield
    finally:
        end_activity(owner)
