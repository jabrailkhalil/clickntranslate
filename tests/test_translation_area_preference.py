"""Mode permissions gate the contextual switch without losing its local state."""
import copy
import json
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import main
import ocr
from atomic_storage import write_json
from capture_regions import encode_area, memory_control_modes
from capture_memory_settings import text as memory_text
from test_desktop_ux import app, window
from test_capture_region_memory import capture


_REAL_OCR_CONFIG_WRITE = ocr._write_ocr_config_updates


@pytest.fixture
def memory_context(window, capture, tmp_path, monkeypatch):
    config, _writes, captures, create = capture
    config.update(copy.deepcopy(window.config))
    config.update(ocr_engine='Windows', translator_engine='Google',
                  last_ocr_language='en', ocr_translate_source_language='en',
                  ocr_translate_target_language='ru', remember_translate_area=False,
                  capture_area_memory_modes=None,
                  last_translate_area=None, remember_copy_area=True)
    area = encode_area(QtCore.QRect(-1100, 200, 300, 140), QtWidgets.QApplication.primaryScreen())
    assert area is not None
    config['last_copy_area'] = copy.deepcopy(area)
    window.config = config
    path = tmp_path / 'config.json'
    monkeypatch.setattr(ocr, 'get_data_file', lambda name: str(tmp_path / name))
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', _REAL_OCR_CONFIG_WRITE)
    monkeypatch.setattr(ocr, '_ocr_config_cache', None)
    monkeypatch.setattr(ocr, '_ocr_config_mtime', 0)
    monkeypatch.setattr(main, '_main_window_ref', window)
    save = mock.Mock(side_effect=lambda **_kwargs: write_json(path, config, indent=2))
    monkeypatch.setattr(window, 'save_config', save)
    save()
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(1)
    QtWidgets.QApplication.processEvents()
    return SimpleNamespace(window=window, settings=settings,
                           control=settings.capture_memory_modes,
                           config=config, captures=captures, create=create,
                           path=path, save=save, area=area)


def test_settings_toggle_uses_existing_preference_and_clears_only_translation_area(memory_context):
    context = memory_context
    copy_area = copy.deepcopy(context.config['last_copy_area'])
    assert not context.control.is_mode_checked('translate')
    context.control.toggle_mode('translate')
    assert context.config['remember_translate_area'] is True
    context.config['last_translate_area'] = copy.deepcopy(context.area)
    context.save()
    context.control.toggle_mode('translate')
    assert context.config['remember_translate_area'] is False
    assert context.config['last_translate_area'] is None
    assert context.config['remember_copy_area'] is True
    assert context.config['last_copy_area'] == copy_area
    stored = json.loads(context.path.read_text(encoding='utf-8'))
    assert stored['remember_translate_area'] is False
    assert stored['last_translate_area'] is None
    assert stored['last_copy_area'] == copy_area


def test_settings_preference_is_used_by_next_capture_without_starting_ocr(memory_context):
    context = memory_context
    context.control.toggle_mode('translate')
    overlay = context.create('translate')
    assert overlay.remember_area_checkbox.isChecked()
    assert overlay.remember_area_checkbox.isVisible()
    assert context.captures == []
    overlay.close()
    context.control.toggle_mode('translate')
    overlay = context.create('translate')
    assert not overlay.remember_area_checkbox.isChecked()
    assert not overlay.remember_area_checkbox.isVisible()
    assert not overlay.memory_panel.isVisible()
    assert not overlay.capture_separator.isVisible()
    assert overlay._preview_rect is None
    assert context.captures == []


def test_contextual_toggle_updates_cached_settings_without_a_refresh_save(memory_context, app):
    context = memory_context
    context.control.toggle_mode('translate')
    context.config['last_translate_area'] = copy.deepcopy(context.area)
    context.save()
    overlay = context.create('translate')
    assert overlay.remember_area_checkbox.isChecked()
    assert overlay._preview_rect is not None
    overlay.remember_area_checkbox.click()
    assert context.config['remember_translate_area'] is False
    assert context.config['last_translate_area'] is None
    assert context.config['remember_copy_area'] is True
    overlay.close()
    save_count = context.save.call_count
    context.window.show_settings()
    assert context.window.settings_window is context.settings
    context.settings._set_settings_page(1)
    app.processEvents()
    # The mode still exposes its switch, even when memory was turned off there.
    assert context.control.is_mode_checked('translate')
    overlay = context.create('translate')
    assert overlay.remember_area_checkbox.isVisible()
    assert not overlay.remember_area_checkbox.isChecked()
    overlay.remember_area_checkbox.click()
    assert context.config['remember_translate_area'] is True
    assert context.save.call_count == save_count
    assert context.captures == []


@pytest.mark.parametrize('locale', ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id'))
def test_preference_survives_interface_language_and_theme_rebuilds(memory_context, app, locale):
    context = memory_context
    context.control.toggle_mode('translate')
    for theme in ('Темная', 'Светлая'):
        context.window.set_interface_language(locale)
        if context.window.current_theme != theme:
            context.window.toggle_theme()
        context.window.show_settings()
        context.window.settings_window._set_settings_page(1)
        app.processEvents()
        control = context.window.settings_window.capture_memory_modes
        assert control.is_mode_checked('translate')
        assert control.accessibleName() == memory_text(locale, 'label')
        assert control.toolTip()
        assert control.fontMetrics().horizontalAdvance(control.summary_text()) <= control.available_text_width()
        assert context.config['remember_translate_area'] is True
        assert context.config['remember_copy_area'] is True


def test_disabling_memory_does_not_resolve_an_unavailable_monitor(memory_context, monkeypatch):
    context = memory_context
    context.control.toggle_mode('translate')
    context.config['last_translate_area'] = copy.deepcopy(context.area)
    context.config['last_translate_area']['screen']['name'] = 'disconnected monitor'
    with mock.patch('capture_regions.resolve_area', side_effect=AssertionError('Settings must not access a screen')):
        context.control.toggle_mode('translate')
    assert context.config['last_translate_area'] is None
    assert context.config['last_copy_area'] == context.area
    assert context.captures == []
