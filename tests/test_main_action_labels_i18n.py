"""Every localized action name must describe what its icon actually does."""
import ast
from pathlib import Path
import re
from unittest import mock

import pytest
from PyQt5 import QtGui, QtWidgets

import main
import settings_window
from test_desktop_ux import app, window


LANGUAGES = ('en', 'ru', 'es', 'de', 'fr', 'zh')


def tooltip(button):
    text = QtGui.QTextDocument()
    text.setHtml(button.toolTip())
    return text.toPlainText()


@pytest.mark.parametrize('lang', LANGUAGES)
def test_main_close_and_home_actions_keep_distinct_localized_hints(window, app, lang):
    window.set_interface_language(lang)
    window.refresh_interface_language_ui()
    for show in (window.show_main_screen, window.show_settings, window.show_main_screen):
        show()
        app.processEvents()
        close = main.ui_text(lang, 'close')
        assert window.close_button.text() == '×'
        assert tooltip(window.close_button) == window.close_button.accessibleName() == close
        expected = main.ui_text(lang, 'back' if window.settings_window is not None else 'settings')
        assert tooltip(window.settings_button) == window.settings_button.accessibleName() == expected
        assert expected != close
    for button, key in ((window.flag_button, 'choose_interface_language'),
                        (window.theme_button, 'theme'), (window.minimize_button, 'minimize'),
                        (window.help_button, 'help')):
        assert tooltip(button) == button.accessibleName() == main.ui_text(lang, key)
    for button in (window.main_language_swap, window.hotkey_language_swap):
        assert tooltip(button) == button.accessibleName() == main.hotkey_language_text(lang, 'swap')


@pytest.mark.parametrize('lang', LANGUAGES)
def test_small_close_icons_and_dynamic_swap_are_localized(window, app, lang):
    window.set_interface_language(lang)
    popup = main.HotkeyLanguageDialog(window)
    try:
        close = popup.findChild(QtWidgets.QToolButton, 'hotkeyLanguageClose')
        assert tooltip(close) == close.accessibleName() == main.ui_text(lang, 'close')
        assert tooltip(popup.swap_button) == popup.swap_button.accessibleName() == main.hotkey_language_text(lang, 'swap')
    finally:
        popup.close()
        popup.deleteLater()
    window.show_settings()
    settings = window.settings_window
    button = settings.game_swap_button
    assert tooltip(button) == button.accessibleName() == settings_window.settings_text(lang, 'game_swap_languages')
    # These assertions concern labels; do not start deferred runtime/network probes.
    with mock.patch('settings_window.QtCore.QTimer.singleShot'):
        manager = settings_window.OcrLanguageManagerDialog(settings)
        try:
            assert tooltip(manager.title_close_btn) == manager.title_close_btn.accessibleName() == main.ui_text(lang, 'close')
        finally:
            manager.close()
            manager.deleteLater()
    progress = settings_window.TesseractInstallProgressDialog(settings, title='Tesseract')
    try:
        assert progress.background_button.text() == settings_window.language_manager_text(lang, 'continue_background')
    finally:
        progress.close()
        progress.deleteLater()


@pytest.mark.parametrize('lang', LANGUAGES)
def test_invalid_hotkeys_and_manual_engine_hints_use_selected_language(window, app, lang):
    window.set_interface_language(lang)
    window.show_settings()
    settings = window.settings_window
    settings.show_hotkeys_screen()
    field = settings.copy_hotkey_input
    for windows in (True, False):
        with (mock.patch.object(field, 'hotkeyText', return_value='Ctrl+K, Ctrl+C'),
              mock.patch.object(settings_window.platform_support, 'IS_WINDOWS', windows)):
            assert settings._checked_hotkey('copy_hotkey') is None
        assert settings.hotkey_hint_label.text() == settings_window.settings_text(lang, 'invalid_hotkey_format')
    command = 'sudo apt install tesseract-ocr'
    with (mock.patch.object(settings_window, 'QMessageBox') as message_box,
          mock.patch.object(settings_window.platform_support, 'tesseract_install_hint', return_value=command)):
        settings._show_linux_tesseract_hint(lang)
        message_box.return_value.setText.assert_called_once_with(
            settings_window.engine_text(lang, 'linux_tesseract_hint', command=command))
    with mock.patch.object(settings_window, 'QMessageBox') as message_box:
        settings._show_manual_hymt_hint(lang)
        actual = message_box.return_value.setText.call_args.args[0]
        expected_template = settings_window.ENGINE_TEXT[lang]['manual_hymt_hint']
        assert actual.startswith(expected_template.split('{model}')[0])
        assert settings_window.HYMT_MODEL_FILE in actual
        assert '{' not in actual


def test_document_language_change_refreshes_close_minimize_and_swap_hints(window, app):
    dialog = main.DocumentTranslationDialog(window)
    try:
        for lang in LANGUAGES:
            dialog.refresh_language(lang)
            assert tooltip(dialog.doc_close_button) == dialog.doc_close_button.accessibleName() == main.ui_text(lang, 'close')
            assert tooltip(dialog.doc_minimize_button) == dialog.doc_minimize_button.accessibleName() == main.ui_text(lang, 'minimize')
            assert tooltip(dialog.language_arrow) == dialog.language_arrow.accessibleName() == main.hotkey_language_text(lang, 'swap')
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize('filename', ['main.py', 'src/settings_window.py'])
def test_complete_six_language_dictionaries_preserve_format_fields(filename):
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / filename).read_text(encoding='utf-8-sig'))
    checked = 0
    def fields(value):
        if isinstance(value, str):
            return sorted(re.findall(r'(?<!\{)\{([A-Za-z_]\w*)(?:[!:][^{}]*)?\}(?!\})', value))
        if isinstance(value, (tuple, list)):
            return [fields(part) for part in value]
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        try:
            values = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        if not all(lang in values and isinstance(values[lang], dict) for lang in LANGUAGES):
            continue
        for lang in LANGUAGES:
            assert set(values[lang]) == set(values['en']), (filename, node.lineno, lang)
            for key, value in values['en'].items():
                assert fields(values[lang][key]) == fields(value), (filename, node.lineno, lang, key)
        checked += 1
    assert checked >= 9
