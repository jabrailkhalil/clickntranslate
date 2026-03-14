"""
Cache Manager for Click'n'Translate
Manages all cached data: history, translation cache, temp files.
Provides cleanup, size limits, and statistics.
"""

import os
import json
import time
import shutil
import datetime
import threading

# Default limits
MAX_COPY_HISTORY = 500          # max records in copy history
MAX_TRANSLATION_HISTORY = 500   # max records in translation history
MAX_TRANSLATION_CACHE = 1000    # max cached translations
MAX_TEXT_LENGTH = 5000           # max chars per history record text
CACHE_DIR_NAME = "cache"        # subfolder for cache files
TRANSLATION_CACHE_FILE = "translation_cache.json"

_cache_lock = threading.Lock()


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
    if os.path.exists(pycache_dir):
        total = 0
        for f in os.listdir(pycache_dir):
            fp = os.path.join(pycache_dir, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
        stats["pycache"]["size_bytes"] = total

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


def clear_all_cache(data_dir):
    """
    Clear all cache data:
    - Empty copy_history.json
    - Empty translation_history.json
    - Delete translation cache
    - Delete __pycache__
    Returns total bytes freed.
    """
    freed = 0

    with _cache_lock:
        # Copy history
        ch_path = os.path.join(data_dir, "copy_history.json")
        if os.path.exists(ch_path):
            freed += os.path.getsize(ch_path)
            with open(ch_path, "w", encoding="utf-8") as f:
                json.dump([], f)

        # Translation history
        th_path = os.path.join(data_dir, "translation_history.json")
        if os.path.exists(th_path):
            freed += os.path.getsize(th_path)
            with open(th_path, "w", encoding="utf-8") as f:
                json.dump([], f)

        # Translation cache dir
        cache_dir = os.path.join(data_dir, CACHE_DIR_NAME)
        if os.path.exists(cache_dir):
            for f in os.listdir(cache_dir):
                fp = os.path.join(cache_dir, f)
                if os.path.isfile(fp):
                    freed += os.path.getsize(fp)
                    os.remove(fp)

        # __pycache__
        pycache_dir = os.path.join(os.path.dirname(data_dir), "__pycache__")
        if os.path.exists(pycache_dir):
            for f in os.listdir(pycache_dir):
                fp = os.path.join(pycache_dir, f)
                if os.path.isfile(fp):
                    freed += os.path.getsize(fp)
            shutil.rmtree(pycache_dir, ignore_errors=True)

    return freed


# --- Translation Cache (avoid re-translating same text) ---

_translation_cache = None  # lazy loaded


def _get_cache_path(data_dir):
    cache_dir = get_cache_dir(data_dir)
    return os.path.join(cache_dir, TRANSLATION_CACHE_FILE)


def _load_translation_cache(data_dir):
    global _translation_cache
    if _translation_cache is not None:
        return _translation_cache
    path = _get_cache_path(data_dir)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                _translation_cache = json.load(f)
        except Exception:
            _translation_cache = {}
    else:
        _translation_cache = {}
    return _translation_cache


def get_cached_translation(data_dir, text, source_code, target_code):
    """Look up a cached translation. Returns translated text or None."""
    cache = _load_translation_cache(data_dir)
    key = f"{source_code}:{target_code}:{text}"
    entry = cache.get(key)
    if entry:
        # Update access time
        entry["accessed"] = time.time()
        return entry["translated"]
    return None


def save_cached_translation(data_dir, text, source_code, target_code, translated):
    """Save a translation to cache. Trims cache if over limit."""
    if not translated or len(text) > MAX_TEXT_LENGTH:
        return
    cache = _load_translation_cache(data_dir)
    key = f"{source_code}:{target_code}:{text}"
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
        try:
            path = _get_cache_path(data_dir)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass


def invalidate_translation_cache():
    """Force reload of translation cache on next access."""
    global _translation_cache
    _translation_cache = None
