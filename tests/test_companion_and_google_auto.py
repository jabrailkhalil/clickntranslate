"""Interaction contracts for the personal desktop companion and Google Auto."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import main
import translater
import document_translation
from assistant_art import APPEARANCES, companion_art
from assistant_settings import assistant_preferences
from languages import AUTO_LANGUAGE_NAMES, language_code_from_name, language_display_name
from test_desktop_ux import app, window


def test_companion_tab_is_visually_third_and_focus_is_keyboard_only(window, app):
    window.show_assistant_settings()
    app.processEvents()
    tabs = window.settings_window.settings_page_tabs
    assert sorted(range(4), key=lambda i: tabs[i].x()) == [0, 1, 3, 2]
    page = window.settings_window.settings_assistant_page
    toggle = page.toggle
    toggle.focusInEvent(QtGui.QFocusEvent(QtCore.QEvent.FocusIn, QtCore.Qt.TabFocusReason))
    assert toggle._keyboard_focus
    QTest.mouseClick(toggle, QtCore.Qt.LeftButton)
    assert not toggle._keyboard_focus
    assert toggle.isChecked()


@pytest.mark.parametrize('appearance', ['orb', 'portrait', 'star', 'sleep_icon'])
def test_static_shortcut_stays_still_but_menu_and_home_work(window, app, appearance):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    page.toggle.click()
    helper = window._desktop_assistant
    page.appearance_buttons['walking'].click()
    page.appearance_buttons[appearance].click()
    assert window.config['desktop_assistant_appearance'] == appearance
    assert not page.motion_options.isEnabled()
    assert not helper.anchor._animation.isActive()
    assert helper.anchor.movie.state() != QtGui.QMovie.Running
    position, image = helper.anchor.pos(), helper.anchor.grab().toImage()
    helper.anchor._advance(2.)
    assert helper.anchor.pos() == position
    assert helper.anchor.grab().toImage() == image
    helper.toggle_menu()
    assert helper.menu.section_pages['translation_section'].isVisible()
    helper.menu.section_buttons['companion_section'].click()
    assert not helper.menu.buttons['walk'].isEnabled()
    assert helper.menu.buttons['home'].isEnabled()
    assert helper.menu.buttons['settings'].isEnabled()


def test_custom_image_cancel_preserves_selection_and_invalid_values_are_safe(window):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    page.toggle.click()
    with mock.patch.object(QtWidgets.QFileDialog, 'getOpenFileName', return_value=('', '')):
        page.appearance_buttons['custom'].click()
    assert page.appearance_buttons['orb'].isChecked()
    assert window.config['desktop_assistant_appearance'] == 'orb'
    values = assistant_preferences({'desktop_assistant_image': [], 'desktop_assistant_appearance': {}})
    assert values['desktop_assistant_image'] == '' and values['desktop_assistant_appearance'] == 'orb'
    assert not companion_art('custom', 'missing-file.png').isNull()


def test_custom_image_and_sleep_pose(window, tmp_path):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    page.toggle.click()
    custom = tmp_path / 'custom.png'
    companion_art('star').save(str(custom))
    with mock.patch.object(QtWidgets.QFileDialog, 'getOpenFileName', return_value=(str(custom), '')):
        page.appearance_buttons['custom'].click()
    assert window.config['desktop_assistant_image'] == str(custom)
    assert page.appearance_buttons['custom'].isChecked()
    page.appearance_buttons['portrait'].click()
    helper = window._desktop_assistant
    idle = helper.anchor.grab().toImage()
    page.appearance_buttons['sleep_icon'].click()
    sleeping = helper.anchor.grab().toImage()
    assert sleeping != idle
    assert not helper.anchor._animation.isActive()
    assert helper.anchor.movie.state() == QtGui.QMovie.Paused
    helper.request_action('walk')  # Static icons cannot start walking.
    assert not helper.anchor._animation.isActive()


@pytest.mark.parametrize('language', tuple(AUTO_LANGUAGE_NAMES))
def test_auto_language_localization(language):
    assert language_code_from_name(language_display_name('auto', language), language) == 'auto'


def test_main_auto_round_trip_and_ocr_separation(window):
    window.source_lang.setCurrentText(language_display_name('auto', window.current_interface_language))
    assert window.config['main_translation_source_language'] == 'auto'
    assert not window.main_language_swap.isEnabled()
    assert window.target_lang.findText(language_display_name('auto', window.current_interface_language)) == -1
    assert ('auto', 'en') in window._available_hotkey_translation_pairs('selection')
    assert window._set_hotkey_translation_pair('selection', 'auto', 'en')
    assert window._stored_hotkey_pair('selection') == ('auto', 'en')
    for mode in ('ocr', 'fullscreen', 'game'):
        assert not any(source == 'auto' for source, _ in window._available_hotkey_translation_pairs(mode))
    window.show_settings()
    window.show_main_screen()
    assert window._configured_main_translation_pair()[0] == 'auto'
    window.config['translator_engine'] = 'argos'
    window._restore_main_translation_languages()
    assert 'auto' not in window._main_translation_source_codes()
    assert window.config['main_translation_source_language'] != 'auto'


def test_google_request_passes_auto_to_provider_not_local_detector():
    response = mock.Mock(status_code=200)
    response.json.return_value = [[['Hello!', 'Привет!']], None, 'ru']
    session = mock.Mock()
    session.get.return_value = response
    with mock.patch.object(translater, '_get_http_session', return_value=session):
        assert translater.google_translate('Привет!', 'auto', 'en') == 'Hello!'
    assert session.get.call_args.kwargs['params']['sl'] == 'auto'
    assert session.get.call_args.kwargs['params']['tl'] == 'en'


@pytest.mark.parametrize('payload,expected', [([['Hello!', 'ru']], 'Hello!'), (['Hello!'], 'Hello!'), ([['', 'ru']], None), ([['Hello!']], None)])
def test_google_auto_fallback_response(payload, expected):
    limited = mock.Mock(status_code=429)
    fallback = mock.Mock(status_code=200)
    fallback.json.return_value = payload
    session = mock.Mock()
    session.get.side_effect = [limited, fallback]
    with mock.patch.object(translater, '_get_http_session', return_value=session):
        if expected is None:
            with pytest.raises(ValueError):
                translater.google_translate('Привет!', 'auto', 'en')
        else:
            assert translater.google_translate('Привет!', 'auto', 'en') == expected
    assert all(call.kwargs['params']['sl'] == 'auto' for call in session.get.call_args_list)


@pytest.mark.parametrize('appearance', ['orb', 'portrait', 'star', 'sleep_icon'])
def test_builtin_art_is_valid_with_transparent_background(app, appearance):
    pixmap = companion_art(appearance)
    assert not pixmap.isNull()
    assert pixmap.hasAlphaChannel()
    assert pixmap.toImage().pixelColor(0, 0).alpha() == 0


@pytest.mark.parametrize('language', ['ru', 'en', 'de', 'es', 'fr', 'zh'])
@pytest.mark.parametrize('selected_appearance', ['orb', 'walking'])
def test_companion_settings_and_menu_fit(window, app, language, selected_appearance):
    window.current_interface_language = language
    window.config['interface_language'] = language
    window.show_assistant_settings()
    settings = window.settings_window
    settings.update_language()
    settings._set_settings_page(3)
    page = settings.settings_assistant_page
    page.toggle.click()
    page.choose_appearance(selected_appearance)
    for percent in (100, 150, 200):
        window.set_ui_scale_percent(percent)
        for _ in range(4):
            app.processEvents()
        scroll = page.findChild(QtWidgets.QScrollArea)
        assert scroll.horizontalScrollBar().maximum() == 0
        assert scroll.verticalScrollBar().maximum() == 0, (language, percent, scroll.verticalScrollBar().maximum())
        for button in page.appearance_buttons.values():
            assert button.width() >= button.sizeHint().width()
    helper = window._desktop_assistant
    helper.toggle_menu()
    helper.menu.open_beside(QtCore.QRect(1100, 700, 88, 88), QtCore.QRect(0, 0, 2560, 1400))
    for section in ('translation_section', 'companion_section'):
        helper.menu.section_buttons[section].click()
        app.processEvents()
        for button in helper.menu.buttons.values():
            if button.isVisible():
                bounds = QtCore.QRect(button.mapTo(helper.menu, QtCore.QPoint()), button.size())
                assert helper.menu.rect().contains(bounds), (language, section, bounds)


def test_document_google_auto_is_kept_for_each_text_chunk():
    captured = []
    def translate(texts, source, target, **kwargs):
        captured.append((source, target))
        yield 0, 'Hello!', ''
    with (mock.patch.object(translater, 'iter_translate_texts', side_effect=translate),
          mock.patch.object(document_translation, 'detect_language_code', side_effect=AssertionError('Google detects the language'))):
        result, _ = document_translation.translate_document_text('Привет!', 'auto', 'en', provider_engine='google')
    assert result == 'Hello!'
    assert captured == [('auto', 'en')]


def test_document_auto_survives_language_refresh_and_session_round_trip(window, tmp_path):
    dialog = main.DocumentTranslationDialog(window)
    try:
        dialog.source_combo.setCurrentIndex(dialog.source_combo.findData('auto'))
        dialog.target_combo.setCurrentIndex(dialog.target_combo.findData('en'))
        assert dialog._source_code() == 'auto'
        assert not dialog.language_arrow.isEnabled()
        payload = dialog._session_payload()
        assert payload['source_language'] == 'auto'
        window.current_interface_language = 'ru'
        dialog.refresh_language('ru')
        assert dialog._source_code() == 'auto'
        filename = tmp_path / 'session.json'
        main.save_session(str(filename), payload)
        dialog._populate_provider_combo('argos')
        dialog._refresh_document_provider_languages()
        assert dialog.source_combo.findData('auto') == -1
        with mock.patch.object(QtWidgets.QFileDialog, 'getOpenFileName', return_value=(str(filename), '')):
            dialog.open_session()
        assert dialog._provider_engine() == 'google'
        assert dialog._source_code() == 'auto'
        assert dialog.target_combo.currentData() == 'en'
    finally:
        dialog.close()
        dialog.deleteLater()


def test_result_auto_preserved_but_never_saved_as_ocr_language(window):
    dialog = main.TranslationResultDialog(window, 'Hello!', auto_copy=False, source_text='Привет!',
                                          source_lang='auto', target_lang='en')
    try:
        assert dialog.source_code == 'auto'
        assert dialog.source_combo.currentData() == 'auto'
        assert not dialog.swap_button.isEnabled()
        window._remember_translation_result_pair('auto', 'en', 'ocr')
        assert window.config['ocr_translate_source_language'] != 'auto'
        window._remember_translation_result_pair('auto', 'en', 'main')
        assert window.config['main_translation_source_language'] == 'auto'
    finally:
        dialog.close()
        dialog.deleteLater()
