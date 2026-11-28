import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import main
import ocr
import pytest
import settings_window
import translater


def test_settings_change_invalidates_main_and_ocr_config_caches():
    main._config_cache = {"copy_translated_text": True}
    ocr._ocr_config_cache = {"copy_translated_text": True}
    ocr._ocr_config_revision = 123

    settings_window._invalidate_main_config_cache()

    assert main._config_cache is None
    assert ocr._ocr_config_cache is None
    assert ocr._ocr_config_revision is None


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


@pytest.fixture(params=[
    (main, 'get_cached_config', '_config_cache', '_config_revision'),
    (ocr, 'get_cached_ocr_config', '_ocr_config_cache', '_ocr_config_revision'),
    (translater, 'get_cached_translator_config', '_translator_config_cache', '_translator_config_revision'),
], ids=['main', 'ocr', 'translator'])
def cached_reader(request, tmp_path, monkeypatch):
    module, read_name, cache_name, stamp_name = request.param
    path = tmp_path / 'config.json'
    monkeypatch.setattr(module, 'get_data_file', lambda _: str(path))
    monkeypatch.setattr(module, cache_name, None)
    monkeypatch.setattr(module, stamp_name, None)
    return path, getattr(module, read_name)


@pytest.mark.parametrize('time_delta', [0, -5_000_000_000], ids=['same-time', 'older-backup'])
def test_atomic_restore_reloads_settings_with_preserved_timestamps(cached_reader, time_delta):
    path, read = cached_reader
    path.write_text('{"translator_engine":"argos"}', encoding='utf-8')
    timestamp = path.stat().st_mtime_ns
    assert read()['translator_engine'] == 'argos'
    staged = path.with_suffix('.restore')
    staged.write_text('{"translator_engine":"deepl"}', encoding='utf-8')
    os.utime(staged, ns=(timestamp + time_delta, timestamp + time_delta))
    os.replace(staged, path)
    assert read()['translator_engine'] == 'deepl'
    assert read() is read()


def test_windows_utf8_bom_and_broken_non_object_do_not_break_workers(cached_reader):
    path, read = cached_reader
    path.write_text('{"translator_engine":"argos"}', encoding='utf-8-sig')
    assert read()['translator_engine'] == 'argos'
    path.write_text('[]', encoding='utf-8')
    assert read()['translator_engine'] == 'argos'
    path.write_text('{"translator_engine":"google"}', encoding='utf-8')
    assert read()['translator_engine'] == 'google'


def test_missing_profile_does_not_keep_previous_provider_settings(cached_reader):
    path, read = cached_reader
    path.write_text('{"private_custom_url":"https://example.invalid"}', encoding='utf-8')
    assert read()['private_custom_url'] == 'https://example.invalid'
    path.unlink()
    assert 'private_custom_url' not in read()


def test_ocr_can_update_a_windows_bom_configuration(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    path.write_text('{"interface_language":"ar"}', encoding='utf-8-sig')
    monkeypatch.setattr(ocr, 'get_data_file', lambda _: str(path))
    monkeypatch.setattr(main, '_main_window_ref', None)
    assert ocr._write_ocr_config_updates({'fullscreen_translate_to': 'ja'})
    assert json.loads(path.read_text(encoding='utf-8-sig')) == {
        'interface_language': 'ar', 'fullscreen_translate_to': 'ja'}
