import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import main
import ocr
import settings_window


def test_settings_change_invalidates_main_and_ocr_config_caches():
    main._config_cache = {"copy_translated_text": True}
    ocr._ocr_config_cache = {"copy_translated_text": True}
    ocr._ocr_config_mtime = 123

    settings_window._invalidate_main_config_cache()

    assert main._config_cache is None
    assert ocr._ocr_config_cache is None
    assert ocr._ocr_config_mtime == 0


def test_ocr_pair_write_updates_live_main_config_before_a_later_save():
    with tempfile.TemporaryDirectory() as temporary:
        config_path = Path(temporary) / "config.json"
        config_path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
        live_window = SimpleNamespace(config={"theme": "dark"})

        with mock.patch.object(ocr, "get_data_file", return_value=str(config_path)), \
                mock.patch.object(main, "_main_window_ref", live_window):
            assert ocr._write_ocr_config_updates({
                "fullscreen_translate_from": "zh",
                "fullscreen_translate_to": "en",
            })

        assert live_window.config["fullscreen_translate_from"] == "zh"
        assert live_window.config["fullscreen_translate_to"] == "en"
        stored = json.loads(config_path.read_text(encoding="utf-8"))
        assert stored["fullscreen_translate_from"] == "zh"
        assert stored["fullscreen_translate_to"] == "en"
