import json
import os
import re
from datetime import datetime

from atomic_storage import write_json, write_text


def translations_dir(data_dir):
    path = os.path.join(data_dir, "translations")
    os.makedirs(path, exist_ok=True)
    return path


def default_output_paths(data_dir, source_file_name):
    base = _safe_base_name(source_file_name)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = translations_dir(data_dir)
    prefix = f"{base}_{stamp}"
    return {
        "txt": os.path.join(root, prefix + ".txt"),
        "md": os.path.join(root, prefix + ".md"),
        "session": os.path.join(root, prefix + ".json"),
    }


def save_text(path, text):
    write_text(path, str(text or ""))
    return path


def save_session(path, session):
    payload = dict(session or {})
    payload.setdefault("saved_at", datetime.now().isoformat(timespec="seconds"))
    write_json(path, payload, indent=2)
    return path


def load_session(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Invalid translation session file.")
    for field in ('original_text', 'translated_text', 'source_file_name', 'source_path',
                  'detected_language', 'source_language', 'target_language', 'provider_engine', 'provider'):
        if field in payload and not isinstance(payload[field], str):
            raise ValueError(f"Invalid translation session field: {field}.")
    return payload


def _safe_base_name(file_name):
    base = os.path.splitext(os.path.basename(file_name or "translation"))[0]
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("._")
    return base or "translation"
