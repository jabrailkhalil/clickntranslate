"""Whole-input replacement is opt-in and keeps the normal selection action intact."""
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore

import main
import platform_support
import translater
from test_translation_result_ui import _SelectionHarness, _immediate_thread
from test_desktop_ux import app, window


@pytest.mark.parametrize('enabled,replace,selected', [(False, True, False), (True, True, True), (True, False, False)])
def test_select_all_runs_only_for_enabled_replacement(enabled, replace, selected):
    harness = _SelectionHarness({'replace_selection_select_all': enabled})
    order = []
    with (mock.patch.multiple(platform_support, IS_WINDOWS=True, IS_MAC=False, IS_LINUX=False),
          mock.patch.object(main.ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(keybd_event=mock.Mock())), create=True),
          mock.patch.object(main.threading, 'Thread', _immediate_thread),
          mock.patch.object(main.time, 'sleep'),
          mock.patch.object(main, '_windows_foreground_window', return_value=42),
          mock.patch.object(main, 'select_all_text_in_foreground', side_effect=lambda target: order.append(('all', target)) or True) as select_all,
          mock.patch.object(main, 'simulate_copy', side_effect=lambda: order.append(('copy',))),
          mock.patch.object(main.pyperclip, 'paste', return_value='Chat draft'),
          mock.patch.object(platform_support, 'copy_text'),
          mock.patch.object(translater, 'translate_text', return_value='Translated draft'),
          mock.patch.object(main, 'replace_selected_text_in_foreground', return_value=(True, 'replaced')) as replacement,
          mock.patch.object(main, 'save_translation_history')):
        harness._launch_translate_selection(replace_selection=replace)
    assert select_all.call_count == int(selected)
    assert order == ([('all', 42)] if selected else []) + [('copy',)]
    assert replacement.call_count == int(replace)
    if replace:
        replacement.assert_called_once_with('Chat draft', 'Translated draft', 42)
        assert not harness.shown_dialogs


def test_focus_change_before_select_all_aborts_before_clipboard_or_translation():
    harness = _SelectionHarness({'replace_selection_select_all': True})
    with (mock.patch.multiple(platform_support, IS_WINDOWS=True, IS_MAC=False, IS_LINUX=False),
          mock.patch.object(main.ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(keybd_event=mock.Mock())), create=True),
          mock.patch.object(main.threading, 'Thread', _immediate_thread),
          mock.patch.object(main.time, 'sleep'),
          mock.patch.object(main, '_windows_foreground_window', return_value=42),
          mock.patch.object(main, 'select_all_text_in_foreground', return_value=False),
          mock.patch.object(main.pyperclip, 'paste', return_value='Previous clipboard'),
          mock.patch.object(platform_support, 'copy_text') as clipboard,
          mock.patch.object(main, 'simulate_copy') as copy,
          mock.patch.object(translater, 'translate_text') as translate):
        harness.launch_translate_replace_selection()
    clipboard.assert_not_called()
    copy.assert_not_called()
    translate.assert_not_called()


@pytest.mark.parametrize('foreground,success', [([42, 42], True), ([99], False), ([42, 99], False)])
def test_windows_select_all_validates_target_and_releases_both_keys(foreground, success):
    keys = mock.Mock()
    with (mock.patch.multiple(platform_support, IS_WINDOWS=True, IS_MAC=False),
          mock.patch.object(main, '_windows_foreground_window', side_effect=foreground),
          mock.patch.object(main.ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(keybd_event=keys)), create=True),
          mock.patch.object(main.time, 'sleep')):
        assert main.select_all_text_in_foreground(42) == success
    expected = [] if foreground[0] != 42 else [mock.call(0x11, 0, 0, 0), mock.call(0x41, 0, 0, 0),
                                             mock.call(0x41, 0, 2, 0), mock.call(0x11, 0, 2, 0)]
    assert keys.call_args_list == expected


@pytest.mark.parametrize('language', ['ru', 'en', 'es', 'de', 'fr', 'zh'])
def test_checkbox_saves_and_fits_translation_page(window, app, language):
    window.set_interface_language(language)
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(1)
    app.processEvents()
    box = settings.replace_select_all_checkbox
    assert not box.isChecked()
    assert box.toolTip() and box.accessibleDescription()
    box.setChecked(True)
    assert window.config['replace_selection_select_all'] is True
    assert box.width() >= box.sizeHint().width()
    origin = box.mapTo(settings, QtCore.QPoint())
    panel = settings.ocr_languages_btn.mapTo(settings, QtCore.QPoint())
    assert origin.y() + box.height() < panel.y()


def test_select_all_is_off_for_existing_profiles():
    assert main.DEFAULT_CONFIG['replace_selection_select_all'] is False
    migrated, _ = main.merge_config_defaults({})
    assert migrated['replace_selection_select_all'] is False
