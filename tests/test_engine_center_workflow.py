"""Ready-only selection, stable engine pages and live settings translation."""
import copy
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import main
import settings_window
from settings_window import OcrLanguageManagerDialog, SettingsWindow
from engine_center import text, ACTIONS
from test_desktop_ux import app, window


def _manager(settings):
    with mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'):
        dialog = OcrLanguageManagerDialog(settings)
        dialog._initial_probe_timer.stop()
        dialog._initial_catalog_timer.stop()
        return dialog


def test_constructing_center_never_shows_orphan_action_windows(window, app):
    window.show_settings()
    shown = []
    class Watcher(QtCore.QObject):
        def eventFilter(self, obj, event):
            if event.type() == QtCore.QEvent.Show and isinstance(obj, QtWidgets.QPushButton) and obj.isWindow():
                shown.append(obj.text())
            return False
    watcher = Watcher()
    app.installEventFilter(watcher)
    dialog = _manager(window.settings_window)
    try:
        assert shown == []
        for table in (dialog.windows_table, dialog.tesseract_table, dialog.easyocr_table,
                      dialog.rapidocr_table, dialog.hymt_table, dialog.argos_table):
            if table is not None:
                assert all(not button.isWindow() for button in table._package_action_buttons)
    finally:
        app.removeEventFilter(watcher)
        dialog.close()


def test_ready_lists_hide_missing_packages_and_unconfigured_apis(window, app):
    window.show_settings()
    settings = window.settings_window
    window.config.update(api_providers={}, translator_engine='google', ocr_engine='Windows')
    with mock.patch.object(settings, '_find_available_tesseract_exe', return_value=''), \
         mock.patch.object(settings, '_rapidocr_runtime_installed', return_value=False), \
         mock.patch.object(settings, '_easyocr_runtime_installed', return_value=False), \
         mock.patch.object(settings, '_hymt_installed', return_value=False), \
         mock.patch('translater.argos_installed_translation_pairs_fast', return_value=set()):
        settings._refresh_ready_engine_choices()
    assert settings.ocr_engine_combo.findData('RapidOCR') == -1
    assert settings.ocr_engine_combo.findData('Tesseract') == -1
    assert settings.ocr_engine_combo.findData('EasyOCR') == -1
    assert settings.ocr_engine_combo.findData('OpenAI API') == -1
    assert settings.translator_combo.findData('argos') == -1
    assert settings.translator_combo.findData('openai') == -1
    assert settings.translator_combo.findData('google') >= 0
    assert settings.translator_combo._provider_categories == [('online', settings_window.TRANSLATOR_GROUP_TEXT['en']['online'])]


def test_center_can_activate_an_installed_engine_without_reinstalling(window, app):
    window.show_settings()
    settings = window.settings_window
    window.config['ocr_engine'] = 'Windows'
    dialog = _manager(settings)
    try:
        dialog._rapidocr_status_cache = (True, '')
        dialog.ocr_tabs.setCurrentWidget(dialog.rapidocr_table.parentWidget())
        dialog.show()
        app.processEvents()
        button = dialog.ocr_tabs._activate_button
        assert button.isEnabled()
        with mock.patch.object(settings, '_rapidocr_runtime_installed', return_value=True), \
             mock.patch.object(settings, 'start_rapidocr_install') as install:
            QTest.mouseClick(button, QtCore.Qt.LeftButton)
            assert window.config['ocr_engine'] == 'RapidOCR'
            assert settings.ocr_engine_combo.currentData() == 'RapidOCR'
            assert button.text() == text('en', 'active') and not button.isEnabled()
            install.assert_not_called()
    finally:
        dialog.close()


def test_center_can_activate_online_translation_without_downloading(window, app):
    window.show_settings()
    settings = window.settings_window
    dialog = _manager(settings)
    try:
        dialog.focus_translation_engine('mymemory')
        dialog.show()
        app.processEvents()
        assert dialog._active_engine_table() is None
        with mock.patch('requests.Session.request', side_effect=AssertionError('activation must be local')):
            dialog.translation_tabs._activate_button.click()
        assert window.config['translator_engine'] == 'mymemory'
        assert settings.translator_combo.currentData() == 'mymemory'
        assert dialog.translation_tabs._activate_button.text() == text('en', 'active')
    finally:
        dialog.close()


@pytest.mark.parametrize('percent', (80, 100, 125, 150, 200))
def test_global_dialog_scaling_keeps_center_size_when_switching_engine_pages(window, app, percent):
    from window_appearance import DialogAppearance
    manager = DialogAppearance(app, percent=percent, theme='Темная')
    window.show_settings()
    dialog = _manager(window.settings_window)
    try:
        dialog._easyocr_status_cache = (False, '')
        dialog.show()
        app.processEvents()
        manager.apply(dialog)
        size = dialog.size()
        for index in range(dialog.ocr_tabs.count()):
            dialog.ocr_tabs.setCurrentIndex(index)
            app.processEvents()
            manager.apply(dialog)
            assert dialog.size() == size
        dialog.show_api()
        app.processEvents()
        manager.apply(dialog)
        assert dialog.size() == size
    finally:
        dialog.close()
        app.removeEventFilter(manager)
        manager.deleteLater()


@pytest.mark.parametrize('theme', ('Темная', 'Светлая'))
def test_center_geometry_stays_fixed_through_installed_missing_and_api_pages(window, app, theme, tmp_path):
    window.current_theme = theme
    window.show_settings()
    dialog = _manager(window.settings_window)
    try:
        dialog._easyocr_status_cache = (False, '')
        dialog._rapidocr_status_cache = (True, '')
        dialog.show()
        size = dialog.size()
        for index in range(dialog.ocr_tabs.count()):
            dialog._engine_selectors[0].setCurrentIndex(index)
            app.processEvents()
            assert dialog.size() == size
            page = dialog.ocr_tabs.currentWidget()
            assert page.width() == dialog.ocr_tabs.contentsRect().width()
            assert dialog.rect().contains(QtCore.QRect(dialog.close_btn.mapTo(dialog, QtCore.QPoint()), dialog.close_btn.size()))
            assert dialog.grab().save(str(tmp_path/f'{theme}-{index}.png'))
        dialog.show_api()
        app.processEvents()
        assert dialog.size() == size
        assert dialog.api_page.isVisible()
        assert dialog.grab().save(str(tmp_path/f'{theme}-api.png'))
    finally:
        dialog.close()


def snapshot(settings):
    result = {}
    for name, value in settings.__dict__.items():
        if name.startswith('_'):
            continue
        if isinstance(value, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
            result[name] = (value.text(), value.toolTip(), value.accessibleName() or value.text(), value.accessibleDescription())
    for name, value in settings.settings_assistant_page.__dict__.items():
        if isinstance(value, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
            result['assistant.'+name] = (value.text(), value.toolTip(), value.accessibleName() or value.text(), value.accessibleDescription())
    return result


@pytest.mark.parametrize('locale', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
def test_relabel_matches_fresh_settings_without_rebuilding_or_saving_preferences(window, app, locale):
    window.set_interface_language('en')
    window.show_settings()
    settings = window.settings_window
    original = settings.settings_pages
    before = copy.deepcopy(window.config)
    with mock.patch.object(settings, 'init_ui', side_effect=AssertionError('must relabel existing controls')):
        window.set_interface_language(locale)
    app.processEvents()
    assert settings.settings_pages is original
    expected_config = copy.deepcopy(window.config)
    fresh = SettingsWindow(window)
    try:
        actual, expected = snapshot(settings), snapshot(fresh)
        differences = {key: (actual[key], value) for key, value in expected.items() if key in actual and actual[key] != value}
        if differences:
            import json
            from pathlib import Path
            folder = Path('.tmp/engine-center-rework')
            (folder/(locale+'-differences.json')).write_text(json.dumps(differences, ensure_ascii=False, indent=2), encoding='utf-8')
        assert differences == {}
        assert window.config == expected_config
        assert settings.result_window_control.checked_modes() == fresh.result_window_control.checked_modes()
        assert settings.capture_memory_modes.checked_modes() == fresh.capture_memory_modes.checked_modes()
        assert settings.game_source_combo.currentData() == fresh.game_source_combo.currentData()
        assert settings.game_target_combo.currentData() == fresh.game_target_combo.currentData()
    finally:
        fresh.close()
        fresh.deleteLater()


def test_live_language_change_follows_only_untouched_translation_pair(window, app):
    window.config.update(main.fresh_config('en'))
    window.set_interface_language('en')
    window.show_settings()
    settings = window.settings_window
    for language, expected in (('ar', ('en', 'ar')), ('ru', ('en', 'ru'))):
        window.set_interface_language(language)
        assert (settings.game_source_combo.currentData(), settings.game_target_combo.currentData()) == expected
    window.config.update(game_translate_source_language='fr', game_translate_target_language='de')
    settings._populate_game_language_controls(fast=True)
    window.set_interface_language('it')
    assert (settings.game_source_combo.currentData(), settings.game_target_combo.currentData()) == ('fr', 'de')


def test_unavailable_saved_translator_never_displays_google_as_selected(window, app):
    window.show_settings()
    settings = window.settings_window
    window.config['translator_engine'] = 'openai'
    with mock.patch.object(settings, '_ready_engine_inventory', return_value=({'Windows'}, {'google'})):
        settings._set_translator_combo_silently('openai')
    assert settings.translator_combo.currentIndex() == -1
    assert window.config['translator_engine'] == 'openai'
    settings._on_translator_changed(-1)
    assert window.config['translator_engine'] == 'openai'


def test_windows_platform_metadata_does_not_start_wmi():
    import sys
    import component_catalog
    if sys.platform != 'win32':
        pytest.skip('Native Windows metadata check')
    with mock.patch.object(component_catalog.platform, 'machine', side_effect=AssertionError('WMI path')), \
         mock.patch.object(component_catalog.platform, 'version', side_effect=AssertionError('WMI path')):
        value = component_catalog.current_platform()
    assert value['arch'] in {'x86_64', 'arm64', 'x86'}
    assert value['os_version'] == '.'.join(map(str, sys.getwindowsversion().platform_version))
