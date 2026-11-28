"""Publish complete UTF-8 files without truncating an existing user document."""
import errno
from itertools import count
import json
import os
import tempfile
import time


def read_cached_settings(path, cached, revision, *, default, prepare=None):
    """Reuse a valid configuration only while the same underlying file is current."""
    path = os.fspath(path)
    try:
        stat = os.stat(path)
        stamp = (path, stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        if cached is not None and stamp == revision:
            return cached, revision
        with open(path, 'r', encoding='utf-8-sig') as stream:
            values = json.load(stream)
        if not isinstance(values, dict):
            raise ValueError('Settings must be a JSON object')
        return (prepare(values) if prepare is not None else values), stamp
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError, RecursionError):
        # A transient invalid edit may retain the last valid settings for this
        # profile. Never reuse another portable directory's provider or API URL.
        if revision and revision[0] == path and cached is not None:
            return cached, revision
    return default(), None


def _replace_complete_file(source, target, *, overwrite=True):
    move = os.replace if overwrite else os.rename
    for attempt in range(8):
        try:
            move(source, target)
            return
        except OSError as error:
            # AV/indexers and readers can briefly deny replacement on Windows.
            # Retry the same complete temporary file; permanent errors still
            # propagate, and at most 0.45 seconds are spent waiting.
            if (os.name != 'nt' or getattr(error, 'winerror', None) not in (5, 32, 33)
                    or attempt == 7):
                raise
            time.sleep(min(0.01 * 2 ** attempt, 0.1))


def _publish_new_file(source, target):
    if os.name == 'nt':
        # Windows rename fails rather than replacing an existing destination.
        _replace_complete_file(source, target, overwrite=False)
        return
    try:
        os.link(source, target)
        return
    except OSError as error:
        if error.errno not in {errno.EPERM, errno.EOPNOTSUPP, errno.ENOSYS}:
            raise
    # Some portable drives lack hard links. Create exclusively and write
    # through that descriptor so another export can never be overwritten.
    import shutil
    with open(source, 'rb') as ready, open(target, 'xb') as created:
        try:
            shutil.copyfileobj(ready, created)
            created.flush()
            os.fsync(created.fileno())
        except BaseException:
            try:
                if os.path.samestat(os.stat(target, follow_symlinks=False), os.fstat(created.fileno())):
                    os.unlink(target)
            except OSError:
                pass
            raise


def _write_complete(path, write_content, *, unique):
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=parent,
                                         prefix='.cnt-save-', suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            write_content(stream.file)
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory replacement stays on the same filesystem.
        if unique:
            base, extension = os.path.splitext(path)
            for index in count(1):
                candidate = path if index == 1 else f'{base}_{index}{extension}'
                try:
                    _publish_new_file(temporary, candidate)
                except FileExistsError:
                    continue
                return candidate
        _replace_complete_file(temporary, path)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def write_text(path, text, *, unique=False):
    return _write_complete(path, lambda stream: stream.write(text), unique=unique)


def write_json(path, payload, *, indent=None, unique=False):
    if indent is None:
        # Compact caches use the JSON encoder's fast whole-value path.
        return write_text(path, json.dumps(payload, ensure_ascii=False), unique=unique)
    # Histories and document sessions can contain very large multilingual
    # records. Serialize them incrementally to the temporary file.
    def write_content(stream):
        json.dump(payload, stream, ensure_ascii=False, indent=indent)

    return _write_complete(path, write_content, unique=unique)
