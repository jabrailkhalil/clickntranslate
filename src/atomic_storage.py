"""Publish complete UTF-8 files without truncating an existing user document."""
import json
import os
import tempfile


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
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def write_json(path, payload, *, indent=None):
    # Serialization failures must also leave the previous file intact.
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=indent))
