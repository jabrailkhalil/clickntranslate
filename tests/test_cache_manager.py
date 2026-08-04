import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cache_manager  # noqa: E402


def test_clear_cache_preserves_settings_histories_and_language_packages():
    with tempfile.TemporaryDirectory(prefix="cnt_cache_clear_") as root:
        root_path = Path(root)
        data_dir = root_path / "data"
        cache_dir = data_dir / "cache"
        logs_dir = data_dir / "logs" / "ocr_artifacts"
        temp_dir = root_path / "temp" / "update"
        pycache_dir = root_path / "__pycache__"
        model_dir = root_path / "ocr" / "easyocr" / "models"
        cache_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)
        temp_dir.mkdir(parents=True)
        pycache_dir.mkdir()
        model_dir.mkdir(parents=True)

        config = data_dir / "config.json"
        copy_history = data_dir / "copy_history.json"
        translation_history = data_dir / "translation_history.json"
        translation_cache = cache_dir / "translation_cache.json"
        config.write_text('{"language": "ru"}', encoding="utf-8")
        copy_history.write_text('[{"text": "copy"}]', encoding="utf-8")
        translation_history.write_text('[{"original": "a", "translated": "b"}]', encoding="utf-8")
        translation_cache.write_text('{"cached": {}}', encoding="utf-8")
        (pycache_dir / "module.pyc").write_bytes(b"compiled")
        log = logs_dir / "ocr_debug.png"
        log.write_bytes(b"diagnostic")
        temporary = temp_dir / "download.tmp"
        temporary.write_bytes(b"temporary")
        model = model_dir / "model.pth"
        model.write_bytes(b"model")

        expected_freed = sum(
            path.stat().st_size
            for path in (translation_cache, pycache_dir / "module.pyc", log, temporary)
        )
        freed = cache_manager.clear_all_cache(str(data_dir), str(root_path))

        assert freed == expected_freed
        assert json.loads(config.read_text(encoding="utf-8")) == {"language": "ru"}
        assert json.loads(copy_history.read_text(encoding="utf-8"))[0]["text"] == "copy"
        assert json.loads(translation_history.read_text(encoding="utf-8"))[0]["translated"] == "b"
        assert model.read_bytes() == b"model"
        assert not translation_cache.exists()
        assert not (data_dir / "logs").exists()
        assert not (root_path / "temp").exists()
        assert not pycache_dir.exists()


def test_stale_async_cache_write_cannot_recreate_cleared_cache():
    with tempfile.TemporaryDirectory(prefix="cnt_cache_race_") as root:
        data_dir = os.path.join(root, "data")
        cache = cache_manager._load_translation_cache(data_dir)
        cache["entry"] = {"translated": "old"}

        cache_manager.clear_all_cache(data_dir)
        cache_manager._save_translation_cache(data_dir, cache)

        assert not Path(data_dir, "cache", "translation_cache.json").exists()
        assert cache_manager.get_cached_translation(data_dir, "x", "en", "ru") is None


def test_cache_stats_separate_disposable_cache_from_user_history():
    with tempfile.TemporaryDirectory(prefix="cnt_cache_stats_") as root:
        data_dir = Path(root, "data")
        cache_dir = data_dir / "cache"
        cache_dir.mkdir(parents=True)
        (data_dir / "copy_history.json").write_text('[{"text": "kept"}]', encoding="utf-8")
        (cache_dir / "translation_cache.json").write_text("{}", encoding="utf-8")

        stats = cache_manager.get_cache_stats(str(data_dir))

        assert stats["cache_bytes"] == stats["translation_cache"]["size_bytes"]
        assert stats["total_bytes"] > stats["cache_bytes"]
