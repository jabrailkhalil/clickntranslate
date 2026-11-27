"""Publish complete UTF-8 files without truncating an existing user document."""
import json
import os
import tempfile
import time


def _replace_complete_file(source, target):
    for attempt in range(8):
        try:
            os.replace(source, target)
            return
        except OSError as error:
            # AV/indexers and readers can briefly deny replacement on Windows.
            # Retry the same complete temporary file; permanent errors still
            # propagate, and at most 0.45 seconds are spent waiting.
            if (os.name != 'nt' or getattr(error, 'winerror', None) not in (5, 32, 33)
                    or attempt == 7):
                raise
            time.sleep(min(0.01 * 2 ** attempt, 0.1))


def write_text(path, text):
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=parent,
                                         prefix='.cnt-save-', suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory replacement stays on the same filesystem.
        _replace_complete_file(temporary, path)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def write_json(path, payload, *, indent=None):
    # Serialization failures must also leave the previous file intact.
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=indent))
