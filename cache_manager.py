"""
Cache Manager for Click'n'Translate
Manages histories and disposable translation cache data.
Provides cleanup, size limits, and statistics.
"""

import os
import json
import time
import shutil
import datetime
import threading
import hashlib

# Default limits
MAX_COPY_HISTORY = 500          # max records in copy history
MAX_TRANSLATION_HISTORY = 500   # max records in translation history
MAX_TRANSLATION_CACHE = 1000    # max cached translations
MAX_TEXT_LENGTH = 5000           # max chars per history record text
CACHE_DIR_NAME = "cache"        # subfolder for cache files
TRANSLATION_CACHE_FILE = "translation_cache.json"

_cache_lock = threading.Lock()


def _tree_size(path):
    """Return the current size of a file or directory tree."""
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    if os.path.isdir(path):
        for root, _dirs, files in os.walk(path):
            for filename in files:
                try:
                    total += os.path.getsize(os.path.join(root, filename))
                except OSError:
                    pass
    return total


def get_cache_dir(data_dir):
    """Get or create the cache directory inside data_dir."""
    cache_dir = os.path.join(data_dir, CACHE_DIR_NAME)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_cache_stats(data_dir):
    """Return cache statistics: file sizes, record counts, total size."""
    stats = {
        "copy_history": {"records": 0, "size_bytes": 0},
        "translation_history": {"records": 0, "size_bytes": 0},
        "translation_cache": {"records": 0, "size_bytes": 0},
        "pycache": {"size_bytes": 0},
        "logs": {"size_bytes": 0},
        "temp": {"size_bytes": 0},
        "cache_bytes": 0,
        "total_bytes": 0,
    }

    # Copy history
    ch_path = os.path.join(data_dir, "copy_history.json")
    if os.path.exists(ch_path):
        stats["copy_history"]["size_bytes"] = os.path.getsize(ch_path)
        try:
            with open(ch_path, "r", encoding="utf-8") as f:
                records = json.load(f)
                stats["copy_history"]["records"] = len(records)
        except Exception:
            pass

    # Translation history
    th_path = os.path.join(data_dir, "translation_history.json")
    if os.path.exists(th_path):
        stats["translation_history"]["size_bytes"] = os.path.getsize(th_path)
        try:
            with open(th_path, "r", encoding="utf-8") as f:
                records = json.load(f)
                stats["translation_history"]["records"] = len(records)
        except Exception:
            pass

    # Translation cache
    cache_dir = os.path.join(data_dir, CACHE_DIR_NAME)
    tc_path = os.path.join(cache_dir, TRANSLATION_CACHE_FILE)
    if os.path.exists(tc_path):
        stats["translation_cache"]["size_bytes"] = os.path.getsize(tc_path)
        try:
            with open(tc_path, "r", encoding="utf-8") as f:
                records = json.load(f)
                stats["translation_cache"]["records"] = len(records)
        except Exception:
            pass

    # __pycache__
    pycache_dir = os.path.join(os.path.dirname(data_dir), "__pycache__")
    stats["pycache"]["size_bytes"] = _tree_size(pycache_dir)
    stats["logs"]["size_bytes"] = _tree_size(os.path.join(data_dir, "logs"))
    stats["temp"]["size_bytes"] = _tree_size(
        os.path.join(os.path.dirname(data_dir), "temp")
    )

    stats["cache_bytes"] = (
        stats["translation_cache"]["size_bytes"]
        + stats["pycache"]["size_bytes"]
        + stats["logs"]["size_bytes"]
        + stats["temp"]["size_bytes"]
    )
    stats["total_bytes"] = sum(
        v.get("size_bytes", 0) for v in stats.values() if isinstance(v, dict)
    )

    return stats


def format_size(size_bytes):
    """Format bytes to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _trim_list(records, max_count):
    """Keep only the last max_count records."""
    if len(records) > max_count:
        return records[-max_count:]
    return records


def _deduplicate_consecutive(records, key="text"):
    """Remove consecutive duplicate entries by key."""
    if not records:
        return records
    result = [records[0]]
    for r in records[1:]:
        if r.get(key) != result[-1].get(key):
            result.append(r)
    return result


def _truncate_texts(records, max_length=MAX_TEXT_LENGTH, key="text"):
    """Truncate long text entries."""
    for r in records:
        if key in r and len(r[key]) > max_length:
            r[key] = r[key][:max_length] + "..."
    return records


def cleanup_history(data_dir, max_copy=MAX_COPY_HISTORY,
                    max_translation=MAX_TRANSLATION_HISTORY):
    """
    Clean up history files:
    - Trim to max records
    - Remove consecutive duplicates
    - Truncate overly long texts
    Returns dict with counts of removed records.
    """
    removed = {"copy_history": 0, "translation_history": 0}

    with _cache_lock:
        # Copy history
        ch_path = os.path.join(data_dir, "copy_history.json")
        if os.path.exists(ch_path):
            try:
                with open(ch_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                original_count = len(records)
                records = _deduplicate_consecutive(records, "text")
                records = _truncate_texts(records, MAX_TEXT_LENGTH, "text")
                records = _trim_list(records, max_copy)
                removed["copy_history"] = original_count - len(records)
                with open(ch_path, "w", encoding="utf-8") as f:
                    json.dump(records, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # Translation history
        th_path = os.path.join(data_dir, "translation_history.json")
        if os.path.exists(th_path):
            try:
                with open(th_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                original_count = len(records)
                records = _deduplicate_consecutive(records, "original")
                records = _truncate_texts(records, MAX_TEXT_LENGTH, "original")
                records = _truncate_texts(records, MAX_TEXT_LENGTH, "translated")
                records = _trim_list(records, max_translation)
                removed["translation_history"] = original_count - len(records)
                with open(th_path, "w", encoding="utf-8") as f:
                    json.dump(records, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    return removed


def clear_all_cache(data_dir, portable_root=None):
    """
    Clear disposable cache data without deleting user history or settings:
    - Delete the complete translation cache directory
    - Delete diagnostic logs and OCR debug artifacts
    - Delete the app's temporary directory and __pycache__
    Settings, histories and installed OCR/translation packages are preserved.
    Returns total bytes freed.
    """
    freed = 0
    cache_id = os.path.abspath(data_dir)
    portable_root = os.path.abspath(portable_root or os.path.dirname(cache_id))

    def safe_cache_target(path, owner):
        resolved = os.path.abspath(path)
        owner = os.path.abspath(owner)
        try:
            if os.path.commonpath([resolved, owner]) != owner or resolved == owner:
                raise ValueError(f"Unsafe cache target: {resolved}")
        except ValueError as exc:
            raise ValueError(f"Unsafe cache target: {resolved}") from exc
        return resolved

    targets = (
        safe_cache_target(os.path.join(cache_id, CACHE_DIR_NAME), cache_id),
        safe_cache_target(os.path.join(cache_id, "logs"), cache_id),
        safe_cache_target(os.path.join(portable_root, "temp"), portable_root),
        safe_cache_target(os.path.join(portable_root, "__pycache__"), portable_root),
    )

    with _cache_lock:
        # Invalidate first so an already queued asynchronous write cannot
        # recreate a cache that the user has just cleared.
        _translation_caches.pop(cache_id, None)

        for target in targets:
            before = _tree_size(target)
            try:
                if os.path.isdir(target):
                    shutil.rmtree(target)
                elif os.path.exists(target):
                    os.remove(target)
            except OSError:
                # Count only bytes that were actually removed. A live file
                # handle can keep one log locked while the rest is cleared.
                pass
            freed += max(0, before - _tree_size(target))

    return freed


# --- Translation Cache (avoid re-translating same text) ---

_translation_caches = {}  # lazy loaded per data_dir


def _get_cache_path(data_dir):
    cache_dir = get_cache_dir(data_dir)
    return os.path.join(cache_dir, TRANSLATION_CACHE_FILE)


def _load_translation_cache(data_dir):
    cache_id = os.path.abspath(data_dir)
    if cache_id in _translation_caches:
        return _translation_caches[cache_id]
    path = _get_cache_path(data_dir)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                _translation_caches[cache_id] = json.load(f)
        except Exception:
            _translation_caches[cache_id] = {}
    else:
        _translation_caches[cache_id] = {}
    return _translation_caches[cache_id]


def _translation_cache_key(text, source_code, target_code, engine=None):
    text_digest = hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()
    if engine:
        return f"{engine}:{source_code}:{target_code}:{text_digest}"
    return f"{source_code}:{target_code}:{text_digest}"


def _legacy_translation_cache_key(text, source_code, target_code, engine=None):
    if engine:
        return f"{engine}:{source_code}:{target_code}:{text}"
    return f"{source_code}:{target_code}:{text}"


def get_cached_translation(data_dir, text, source_code, target_code, engine=None):
    """Look up a cached translation. Returns translated text or None."""
    cache = _load_translation_cache(data_dir)
    keys = [_translation_cache_key(text, source_code, target_code, engine)]
    if engine and engine != "hymt":
        keys.append(_translation_cache_key(text, source_code, target_code))
    keys.append(_legacy_translation_cache_key(text, source_code, target_code, engine))
    if engine and engine != "hymt":
        keys.append(_legacy_translation_cache_key(text, source_code, target_code))
    entry = None
    for key in keys:
        entry = cache.get(key)
        if entry:
            break
    if entry:
        # Update access time
        entry["accessed"] = time.time()
        return entry["translated"]
    return None


def save_cached_translation(data_dir, text, source_code, target_code, translated, engine=None):
    """Save a translation to cache. Trims cache if over limit."""
    if not translated or len(text) > MAX_TEXT_LENGTH:
        return
    cache = _load_translation_cache(data_dir)
    key = _translation_cache_key(text, source_code, target_code, engine)
    cache[key] = {
        "translated": translated,
        "created": time.time(),
        "accessed": time.time(),
    }
    # Trim by LRU if over limit
    if len(cache) > MAX_TRANSLATION_CACHE:
        sorted_keys = sorted(cache.keys(), key=lambda k: cache[k].get("accessed", 0))
        to_remove = len(cache) - MAX_TRANSLATION_CACHE
        for k in sorted_keys[:to_remove]:
            del cache[k]
    # Save async
    threading.Thread(
        target=_save_translation_cache, args=(data_dir, cache), daemon=True
    ).start()


def _save_translation_cache(data_dir, cache):
    with _cache_lock:
        cache_id = os.path.abspath(data_dir)
        if _translation_caches.get(cache_id) is not cache:
            return
        try:
            path = _get_cache_path(data_dir)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass


def invalidate_translation_cache():
    """Force reload of translation cache on next access."""
    with _cache_lock:
        _translation_caches.clear()
