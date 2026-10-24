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
    assert original.isVisible()
    assert picker.isVisible()
    assert window.flag_button.isChecked()
    assert window.flag_button.isCheckable()
    assert picker.parentWidget() == original.parentWidget()
    assert picker.next_button.isVisible() == (len(main.INTERFACE_LANGUAGE_OPTIONS) > 10)
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
    assert window.flag_button.isChecked()
    assert window._interface_language_picker is not None
    window._close_interface_language_picker()


def test_picker_pages_open_on_current_language_and_have_bounded_arrows(app):
    options = [dict(code=str(i), name=f'Language {i}', icon='icons/American_flag.png') for i in range(23)]
    picker = InterfaceLanguagePicker(options, '21', main.resource_path)
    picker.resize(670, 160)
    picker.show()
    try:
        assert picker.pages.count() == 3
        assert picker.pages.currentIndex() == 2
        assert not picker.next_button.isEnabled()
        picker.previous_button.click()
        assert picker.pages.currentIndex() == 1
        picker.previous_button.click()
        assert picker.pages.currentIndex() == 0
        assert not picker.previous_button.isEnabled()
        assert len(picker.buttons) == 23
        received = QSignalSpy(picker.languageSelected)
        picker.buttons['1'].click()
        assert list(received) == [['1']]
        QTest.keyClick(picker.buttons['1'], QtCore.Qt.Key_End)
        assert picker.pages.currentIndex() == 2
        QTest.keyClick(picker.buttons['22'], QtCore.Qt.Key_Home)
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
    assert window._interface_language_picker is picker
    assert picker.isVisible()
    assert window.current_interface_language == language
    assert window.text_input.toPlainText() == 'Keep this text'
    picker.close_button.click()
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


@pytest.mark.parametrize('page', [None, 0, 1, 2, 3])
def test_live_selection_never_uses_an_unlaid_out_home_panel_size(window, app, page):
    if page is not None:
        window.show_settings()
        window.settings_window._set_settings_page(page)
    settle(app)
    window.show_interface_language_menu()
    picker = window._interface_language_picker
    before = QtCore.QRect(picker.geometry())
    for locale in ('es', 'ar', 'pt', 'hi', 'en', 'ru'):
        picker.buttons[locale].click()
        # Check the first frame too, not just the eventual settled layout.
        assert picker.geometry() == before
        settle(app)
        assert picker.geometry() == before
        assert picker.height() == picker.PANEL_HEIGHT
        assert picker.title.isVisible() and picker.close_button.isVisible()
        assert picker.y() >= window.main_layout.contentsMargins().top()


@pytest.mark.parametrize('locale', ['en', 'ar', 'hi'])
def test_keyboard_navigation_applies_only_on_enter_and_keeps_focus_inside(window, app, locale):
    window.set_interface_language(locale)
    window.show_interface_language_menu()
    settle(app)
    picker = window._interface_language_picker
    assert picker.buttons[locale].hasFocus()
    QTest.keyClick(picker.buttons[locale], QtCore.Qt.Key_Home)
    assert picker.buttons['en'].hasFocus()
    QTest.keyClick(picker.buttons['en'], QtCore.Qt.Key_Right)
    assert picker.buttons['ru'].hasFocus()
    assert window.current_interface_language == locale
    QTest.keyClick(picker.buttons['ru'], QtCore.Qt.Key_Return)
    settle(app)
    assert window.current_interface_language == 'ru'
    assert picker.buttons['ru'].hasFocus()
    assert picker.buttons['ru'].property('keyboardFocus')
    QTest.keyClick(picker.buttons['ru'], QtCore.Qt.Key_Down)
    assert picker.buttons['pt'].hasFocus()
    QTest.keyClick(picker.buttons['pt'], QtCore.Qt.Key_Up)
    assert picker.buttons['ru'].hasFocus()
    for _ in range(16):
        focused = picker.focusWidget()
        assert focused is not None and picker.isAncestorOf(focused)
        QTest.keyClick(focused, QtCore.Qt.Key_Tab)
    for _ in range(16):
        focused = picker.focusWidget()
        assert focused is not None and picker.isAncestorOf(focused)
        QTest.keyClick(focused, QtCore.Qt.Key_Backtab)
    QTest.keyClick(picker.focusWidget(), QtCore.Qt.Key_End)
    assert picker.buttons['id'].hasFocus() and picker.pages.currentIndex() == 1
    QTest.keyClick(picker.buttons['id'], QtCore.Qt.Key_Right)
    assert picker.buttons['id'].hasFocus()  # No empty-cell or off-page focus.
    QTest.keyClick(picker.buttons['id'], QtCore.Qt.Key_PageUp)
    assert picker.buttons['ru'].hasFocus() and picker.pages.currentIndex() == 0
    QTest.keyClick(picker.buttons['ru'], QtCore.Qt.Key_PageDown)
    assert picker.buttons['id'].hasFocus() and picker.pages.currentIndex() == 1
    QTest.keyClick(picker.buttons['id'], QtCore.Qt.Key_Escape)
    settle(app)
    assert window._interface_language_picker is None


def test_arrows_cross_pages_at_visual_grid_edges_without_selecting(window, app):
    window.show_interface_language_menu()
    settle(app)
    picker = window._interface_language_picker
    initial = window.current_interface_language
    QTest.keyClick(picker.buttons['fr'], QtCore.Qt.Key_Right)
    assert picker.pages.currentIndex() == 1 and picker.buttons['hi'].hasFocus()
    QTest.keyClick(picker.buttons['hi'], QtCore.Qt.Key_Left)
    assert picker.pages.currentIndex() == 0 and picker.buttons['fr'].hasFocus()
    assert window.current_interface_language == initial


def test_real_proxy_mouse_release_leaves_language_ready_for_keyboard(window, app):
    settle(app)
    controller = window._ui_scale_controller
    view = controller.view
    QTest.mouseClick(view.viewport(), QtCore.Qt.LeftButton,
                     pos=controller.map_widget_to_view(window.flag_button))
    settle(app)
    picker = window._interface_language_picker
    assert picker.buttons[window.current_interface_language].hasFocus()
    QTest.mouseClick(view.viewport(), QtCore.Qt.LeftButton,
                     pos=controller.map_widget_to_view(picker.buttons['es']))
    settle(app)
    assert picker.buttons['es'].hasFocus()
    # Dispatch at the real graphics view, rather than directly at a button.
    QTest.keyClick(view.viewport(), QtCore.Qt.Key_Right)
    settle(app)
    assert picker.buttons['de'].hasFocus()
    QTest.keyClick(view.viewport(), QtCore.Qt.Key_Return)
    settle(app)
    assert window.current_interface_language == 'de'
    assert picker.height() == picker.PANEL_HEIGHT and picker.y() > 0


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
            for page in (0, 1):
                picker.set_page(page)
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
