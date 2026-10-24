"""Serialize history mutations and publish each complete JSON atomically."""
from contextlib import contextmanager
import json
import os
import sys
import threading

from atomic_storage import write_json


_locks = {}
_locks_guard = threading.Lock()


@contextmanager
def _history_lock(path):
    # Lock a stable sidecar: replacing the JSON must not replace its lock inode.
    key = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    with _locks_guard:
        thread_lock = _locks.setdefault(key, threading.RLock())
    with thread_lock:
        os.makedirs(os.path.dirname(key), exist_ok=True)
        with open(key + '.lock', 'a+b') as stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b'\0')
                stream.flush()
            stream.seek(0)
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def read_records(path):
    """Read a complete snapshot without initializing a missing history file."""
    try:
        with open(path, 'r', encoding='utf-8') as stream:
            records = json.load(stream)
    except FileNotFoundError:
        return []
    if not isinstance(records, list):
        raise ValueError('History must be a JSON list')
    return records


def update_records(path, update):
    """Apply an update to the latest list; a None result leaves it untouched.

    Invalid existing files raise before publication so callers can report the
    failure without replacing damaged but potentially recoverable user data.
    """
    with _history_lock(path):
        records = read_records(path)
        updated = update(records)
        if updated is None:
            return False
        if not isinstance(updated, list):
            raise ValueError('Updated history must be a JSON list')
        write_json(path, updated, indent=4)
        return True


def append_record(path, record, *, deduplicate_field=None, limit=500):
    def append(records):
        if (deduplicate_field is not None and records and isinstance(records[-1], dict)
                and records[-1].get(deduplicate_field) == record.get(deduplicate_field)):
            return None
        return (records + [record])[-limit:]
    return update_records(path, append)
