"""A scene popup's accepting Enter must not reopen its parent combo."""
import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import keyboard_navigation as keyboard
import main
import ocr
from settings_sections import PAGE_DYNAMIC, PAGE_TRANSLATION
from test_desktop_ux import app, window
from test_popup_host_scaling import option_code


def _settle(app):
    for _ in range(4):
        app.processEvents()
    QTest.qWait(15)
    app.processEvents()


@pytest.fixture
def embedded_picker(window, app, monkeypatch):
    assert app.platformName().split(':')[0] == 'offscreen', 'Never send desktop input'
    keyboard.install_keyboard_navigation(app)
    codes = [language.code for language in main.APP_LANGUAGES]
    monkeypatch.setattr(ocr, 'installed_ocr_language_codes', lambda **_kwargs: codes)
    monkeypatch.setattr(ocr, '_translation_targets_for_source', lambda *_args, **_kwargs: codes)

    def create(place, locale='en', percent=137):
        window.set_interface_language(locale)
        window.set_ui_scale_percent(percent)
        if place == 'main':
            window.show_main_screen()
            combo = window.target_lang
        else:
            window.show_settings()
            settings = window.settings_window
            settings._set_settings_page(PAGE_TRANSLATION if place in ('result', 'memory') else PAGE_DYNAMIC)
            if place == 'result':
                combo = settings.result_window_control
            elif place == 'memory':
                combo = settings.capture_memory_modes
            else:
                settings._populate_game_language_controls(fast=False)
                combo = settings.game_target_combo
        _settle(app)
        assert combo.isVisible()
        # The same automatic proxy can survive a later native bypass request.
        QtWidgets.QComboBox.showPopup(combo)
        _settle(app)
        QtWidgets.QComboBox.hidePopup(combo)
        _settle(app)
        assert combo.view().window().graphicsProxyWidget() is not None
        controller = window._ui_scale_controller
        QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton,
                         pos=controller.map_widget_to_view(combo))
        _settle(app)
        assert combo.view().window().isVisible()
        assert app.activePopupWidget() is None
        return combo, controller.view.viewport()

    yield create
    opened = getattr(app, '_cnt_open_combo', lambda: None)()
    if opened is not None:
        opened.hidePopup()
    app._keyboard_navigation.keyboard = False
    app._keyboard_navigation._hide_ring()


@pytest.mark.parametrize('place', ('main', 'dynamic'))
@pytest.mark.parametrize('locale', ('en', 'ar'))
@pytest.mark.parametrize('percent', (80, 137, 200))
@pytest.mark.parametrize('key', (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter))
def test_accepting_scene_popup_key_closes_once_and_next_physical_press_reopens(
        window, app, embedded_picker, place, locale, percent, key):
    combo, viewport = embedded_picker(place, locale, percent)
    popup, view = combo.view().window(), combo.view()
    QTest.keyClick(viewport, QtCore.Qt.Key_Down)
    QTest.keyClick(viewport, QtCore.Qt.Key_End)
    _settle(app)
    last = combo.count() - 1
    assert view.currentIndex().row() == last
    QTest.keyPress(viewport, key)
    _settle(app)
    assert combo.currentIndex() == last
    assert not popup.isVisible()
    QTest.keyRelease(viewport, key)
    _settle(app)
    assert not popup.isVisible()

    # No debounce: the very next complete key action opens the field normally.
    QTest.keyPress(viewport, key)
    _settle(app)
    assert popup.isVisible()
    QTest.keyRelease(viewport, key)
    QTest.keyClicks(viewport, 'Vietnamese')
    _settle(app)
    search = combo._language_search
    assert search.text() == 'Vietnamese'
    visible = [row for row in range(combo.count()) if not view.isRowHidden(row)]
    assert len(visible) == 1 and option_code(combo, visible[0], locale) == 'vi'
    QTest.keyClick(viewport, key)
    _settle(app)
    assert option_code(combo, combo.currentIndex(), locale) == 'vi'
    assert not popup.isVisible()
    QTest.keyClick(viewport, key)
    _settle(app)
    assert popup.isVisible()
    QTest.keyClick(viewport, QtCore.Qt.Key_Escape)
    _settle(app)
    assert not popup.isVisible()
    if place == 'dynamic':
        assert window.settings_window.settings_pages.currentIndex() == PAGE_DYNAMIC
        QTest.keyClick(viewport, QtCore.Qt.Key_Escape)
        _settle(app)
        assert window.settings_window is None


@pytest.mark.parametrize('place', ('result', 'memory'))
@pytest.mark.parametrize('key', (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Space))
@pytest.mark.parametrize('locale', ('en', 'ar'))
def test_checkable_modes_toggle_once_per_press_and_keep_the_scene_popup_open(window, app, embedded_picker, place, key, locale):
    combo, viewport = embedded_picker(place, locale)
    popup = combo.view().window()
    QTest.keyClick(viewport, QtCore.Qt.Key_Home)
    mode = combo._modes[0]
    original = combo.is_mode_checked(mode)
    for expected in (not original, original):
        QTest.keyPress(viewport, key)
        _settle(app)
        assert combo.is_mode_checked(mode) == expected
        assert popup.isVisible()
        QTest.keyRelease(viewport, key)
        _settle(app)
        assert combo.is_mode_checked(mode) == expected
        assert popup.isVisible()
    QTest.keyClick(viewport, QtCore.Qt.Key_Escape)
    _settle(app)
    assert not popup.isVisible()
    assert window.settings_window.settings_pages.currentIndex() == PAGE_TRANSLATION
    QTest.keyClick(viewport, QtCore.Qt.Key_Escape)
    _settle(app)
    assert window.settings_window is None


def test_scene_popup_key_lifecycle_is_cleared_when_the_application_deactivates(app, embedded_picker):
    combo, viewport = embedded_picker('main')
    QTest.keyClick(viewport, QtCore.Qt.Key_Down)
    _settle(app)
    QTest.keyPress(viewport, QtCore.Qt.Key_Return)
    _settle(app)
    assert not combo.view().window().isVisible()
    # A key released in another application never reaches this QApplication.
    app.sendEvent(app, QtCore.QEvent(QtCore.QEvent.ApplicationDeactivate))
    QTest.keyPress(viewport, QtCore.Qt.Key_Return)
    _settle(app)
    assert combo.view().window().isVisible()
    QTest.keyRelease(viewport, QtCore.Qt.Key_Return)


def test_accepting_popup_key_from_the_actual_native_focus_view_does_not_reopen(app, embedded_picker):
    combo, viewport = embedded_picker('main')
    receiver = app.focusWidget()
    assert receiver is viewport.parentWidget()
    QTest.keyClick(receiver, QtCore.Qt.Key_Down)
    QTest.keyClick(receiver, QtCore.Qt.Key_End)
    _settle(app)
    QTest.keyPress(receiver, QtCore.Qt.Key_Return)
    _settle(app)
    assert combo.currentIndex() == combo.count() - 1
    assert not combo.view().window().isVisible()
    QTest.keyRelease(receiver, QtCore.Qt.Key_Return)
    QTest.keyClick(receiver, QtCore.Qt.Key_Return)
    _settle(app)
    assert combo.view().window().isVisible()
    QTest.keyClick(receiver, QtCore.Qt.Key_Escape)
    _settle(app)
    assert not combo.view().window().isVisible()
