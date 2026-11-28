"""Serialize history mutations and publish each complete JSON atomically."""
from contextlib import contextmanager
from dataclasses import dataclass
import errno
from functools import partial
from itertools import count
import json
import logging
import os
import sys
import threading
import time

from atomic_storage import write_json
from background_tasks import IdleExecutor


_locks = {}
_locks_guard = threading.Lock()
_requests = count()
_last_clear = {}
_LOCK_TIMEOUT = 3.0
_admission = threading.RLock()
# The interpreter drains accepted local saves on ordinary shutdown. No thread
# is created before the first save or kept waiting after the queue is empty.
_writer = IdleExecutor(workers=1, pending=0, idle_seconds=0, thread_name='History-save', daemon=False)


@dataclass(frozen=True)
class _HistoryRequest:
    order: int
    lock_deadline: float


def _new_request():
    with _admission:
        # A burst of queued writes shares roughly one lock-wait budget.
        return _HistoryRequest(next(_requests), time.monotonic() + _LOCK_TIMEOUT)


def queue_write(callback, *args):
    """Queue a local save in submission order and return whether it was accepted."""
    with _admission:
        accepted = _writer.submit(partial(callback, *args, submitted=_new_request()))
    if not accepted:
        logging.getLogger('clickntranslate.history').warning(
            'History save skipped because the background worker could not start.')
    return accepted


def _acquire_file_lock(acquire, deadline):
    while True:
        try:
            acquire()
            return
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('History file is busy') from error
            time.sleep(min(.025, remaining))


@contextmanager
def _history_lock(path, deadline):
    # Lock a stable sidecar: replacing the JSON must not replace its lock inode.
    key = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    with _locks_guard:
        thread_lock = _locks.setdefault(key, threading.RLock())
    if not thread_lock.acquire(timeout=max(0.0, deadline - time.monotonic())):
        raise TimeoutError('History file is busy')
    try:
        os.makedirs(os.path.dirname(key), exist_ok=True)
        with open(key + '.lock', 'a+b') as stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b'\0')
                stream.flush()
            stream.seek(0)
            if sys.platform == 'win32':
                import msvcrt
                _acquire_file_lock(lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1), deadline)
                try:
                    yield key
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                _acquire_file_lock(lambda: fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB), deadline)
                try:
                    yield key
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        thread_lock.release()


def read_records(path):
    """Read a complete snapshot without initializing a missing history file."""
    try:
        with open(path, 'rb') as stream:
            records = json.load(stream)
    except FileNotFoundError:
        return []
    if not isinstance(records, list):
        raise ValueError('History must be a JSON list')
    return records


def update_records(path, update, *, submitted=None, discard_older=False):
    """Apply an update to the latest list; a None result leaves it untouched.

    Invalid existing files raise before publication so callers can report the
    failure without replacing damaged but potentially recoverable user data.
    A clear also retires work queued before the successful replacement.
    """
    if discard_older:
        submitted = _new_request()
    deadline = submitted.lock_deadline if submitted is not None else time.monotonic() + _LOCK_TIMEOUT
    with _history_lock(path, deadline) as key:
        if submitted is not None and submitted.order < _last_clear.get(key, -1):
            return False
        records = read_records(path)
        updated = update(records)
        if updated is None:
            return False
        if not isinstance(updated, list):
            raise ValueError('Updated history must be a JSON list')
        write_json(path, updated, indent=4)
        if discard_older:
            # Set the cutoff only once the user's clear has reached disk.
            _last_clear[key] = submitted.order
        return True


def append_record(path, record, *, deduplicate_field=None, limit=500, submitted=None):
    def append(records):
        if (deduplicate_field is not None and records and isinstance(records[-1], dict)
                and records[-1].get(deduplicate_field) == record.get(deduplicate_field)):
            return None
        return (records + [record])[-limit:]
    return update_records(path, append, submitted=submitted)
