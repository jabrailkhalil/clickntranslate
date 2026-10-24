"""The language grid stays inside the app and never loses the current work."""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QSignalSpy, QTest

import main
from interface_language_picker import InterfaceLanguagePicker
from test_desktop_ux import app, window


def settle(app):
    for _ in range(5):
        app.processEvents()


def test_picker_preserves_home_draft_size_and_language_pair(window, app):
    window.text_input.setPlainText('Unfinished draft')
    original = window.main_text_section
    pair = window._configured_main_translation_pair()
    settle(app)
    before = window.size()
    window.show_interface_language_menu()
    picker = window._interface_language_picker
    settle(app)
    assert window.size() == before
    assert not original.isVisible()
    assert picker.isVisible()
    assert window.flag_button.isChecked()
    assert window.flag_button.isCheckable()
    assert picker.parentWidget().parentWidget() == original.parentWidget()
    assert picker.pager.isVisible() == (len(main.INTERFACE_LANGUAGE_OPTIONS) > 10)
    window.show_interface_language_menu()  # Flag toggles the same view.
    settle(app)
    assert window._interface_language_picker is None
    assert not window.flag_button.isChecked()
    assert window.main_text_section is original and original.isVisible()
    assert window.text_input.toPlainText() == 'Unfinished draft'
    assert window._configured_main_translation_pair() == pair
    assert window.size() == before


def test_picker_escape_restores_settings_tab_without_navigation(window, app):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(1)
    window.show_interface_language_menu()
    picker = window._interface_language_picker
    QTest.keyClick(picker, QtCore.Qt.Key_Escape)
    settle(app)
    assert window._interface_language_picker is None
    assert window.settings_window is settings and settings.isVisible()
    assert settings.settings_pages.currentIndex() == 1


def test_selecting_language_from_settings_preserves_current_tab(window, app):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(1)
    window.show_interface_language_menu()
    window._interface_language_picker.buttons['es'].click()
    settle(app)
    assert window.settings_window is settings
    assert window.current_interface_language == 'es'
    assert settings.settings_pages.currentIndex() == 1
    assert not window.flag_button.isChecked()


def test_picker_pages_open_on_current_language_and_have_bounded_arrows(app):
    options = [dict(code=str(i), name=f'Language {i}', icon='icons/American_flag.png') for i in range(23)]
    picker = InterfaceLanguagePicker(options, '21', main.resource_path)
    picker.resize(670, 160)
    picker.show()
    try:
        assert picker.pages.count() == 3
        assert picker.pages.currentIndex() == 2
        assert not picker.pager.increase.isEnabled()
        picker.pager.decrease.click()
        assert picker.pages.currentIndex() == 1
        picker.pager.decrease.click()
        assert picker.pages.currentIndex() == 0
        assert not picker.pager.decrease.isEnabled()
        assert len(picker.buttons) == 23
        received = QSignalSpy(picker.languageSelected)
        picker.buttons['1'].click()
        assert list(received) == [['1']]
        QTest.keyClick(picker.pager.increase, QtCore.Qt.Key_End)
        assert picker.pages.currentIndex() == 2
        QTest.keyClick(picker.pager.decrease, QtCore.Qt.Key_Home)
        assert picker.pages.currentIndex() == 0
    finally:
        picker.close()
        picker.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
def test_picker_theme_corners_and_selection(window, app, theme):
    if window.current_theme != theme:
        window.toggle_theme()
    window.text_input.setPlainText('Keep this text')
    window.show_interface_language_menu()
    picker = window._interface_language_picker
    settle(app)
    area = picker.choices
    assert not area.mask().contains(QtCore.QPoint(0, area.height()-1))
    assert not area.mask().contains(QtCore.QPoint(area.width()-1, area.height()-1))
    window.toggle_theme()
    assert ('#f8f5fb' if theme == 'Темная' else '#121116') in picker.styleSheet()
    language = 'ar' if window.current_interface_language != 'ar' else 'en'
    picker.buttons[language].click()
    settle(app)
    assert window._interface_language_picker is None
    assert window.current_interface_language == language
    assert window.text_input.toPlainText() == 'Keep this text'
    window.set_interface_language('en')


def test_navigating_away_closes_picker_cleanly(window, app):
    window.show_interface_language_menu()
    window.show_settings()
    settle(app)
    assert window._interface_language_picker is None
    assert window.settings_window.isVisible()
    window.show_interface_language_menu()
    window.show_main_screen()
    settle(app)
    assert window._interface_language_picker is None
    assert window.main_text_section.isVisible()


@pytest.mark.parametrize('locale', list(main.INTERFACE_LANGUAGE_BY_CODE))
def test_picker_fits_at_all_interface_scales_in_both_themes(window, app, locale):
    window.set_interface_language(locale)
    for dark in (True, False):
        if (window.current_theme != 'Светлая') != dark:
            window.toggle_theme()
        for scale in (80, 100, 125, 150, 200):
            window.set_ui_scale_percent(scale)
            settle(app)
            original_size = window.size()
            window.show_interface_language_menu()
            picker = window._interface_language_picker
            settle(app)
            assert window.size() == original_size
            assert picker.pages.currentIndex() == list(main.INTERFACE_LANGUAGE_BY_CODE).index(locale) // 10
            assert picker.buttons[locale].isVisible()
            assert picker.title.fontMetrics().horizontalAdvance(picker.title.text()) <= picker.title.width()
            for page in ('0', '1'):
                picker.pager.setValue(page)
                settle(app)
                for label in picker.name_labels.values():
                    if label.isVisible():
                        assert label.fontMetrics().horizontalAdvance(label.text()) <= label.width()+1
                # A cell has no rounded tile border; the panel owns the frame.
                for button in picker.buttons.values():
                    assert 'border-radius:0' in button.styleSheet()
            picker.close_button.click()
            settle(app)
            assert not window.flag_button.isChecked()
            assert window.main_text_section.isVisible()
            assert window.size() == original_size
    window.set_interface_language('en')
