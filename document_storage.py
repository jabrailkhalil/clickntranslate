import json
import os
import re
from datetime import datetime


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
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(text or ""))
    return path


def save_session(path, session):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    payload = dict(session or {})
    payload.setdefault("saved_at", datetime.now().isoformat(timespec="seconds"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def load_session(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Invalid translation session file.")
    return payload


def _safe_base_name(file_name):
    base = os.path.splitext(os.path.basename(file_name or "translation"))[0]
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("._")
    return base or "translation"
