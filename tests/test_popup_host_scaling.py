"""Actual Qt popup hosts must apply the main canvas zoom exactly once.

The offscreen platform renders real native-widget and GraphicsProxy surfaces;
these checks do not exercise a physical Windows monitor or inject desktop input.
"""
import os
from pathlib import Path
import sys

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import main
import ocr
from languages import language_code_from_name
from test_desktop_ux import app, window
from ui_scaling import widget_global_rect


def settle(app):
    for _ in range(8):
        app.processEvents()
    QTest.qWait(20)
    app.processEvents()


def pixels(font):
    return font.pixelSize() if font.pixelSize() > 0 else QtGui.QFontInfo(font).pixelSize()


def surface_scale(widget):
    return widget_global_rect(widget).width() / max(1, widget.width())


def option_code(combo, row, locale):
    return combo.itemData(row) or language_code_from_name(combo.itemText(row), locale)


def row_height(combo):
    index = combo.model().index(0, combo.modelColumn())
    return combo.view().visualRect(index).height() * surface_scale(combo.view().window())


@pytest.fixture
def language_picker(window, app, monkeypatch):
    assert app.platformName().split(':')[0] == 'offscreen', 'Never open native desktop windows'
    codes = [language.code for language in main.APP_LANGUAGES]
    monkeypatch.setattr(ocr, 'installed_ocr_language_codes', lambda **_kwargs: codes)
    monkeypatch.setattr(ocr, '_translation_targets_for_source', lambda *_args, **_kwargs: codes)
    desktop = QtCore.QRect(0, 0, 3840, 2160)
    window._ui_scale_controller.available_geometry.return_value = desktop

    def create(place, locale, percent):
        window.set_interface_language(locale)
        window.set_ui_scale_percent(percent)
        window.move(10, 10)
        if place == 'dynamic':
            window.show_settings()
            settings = window.settings_window
            settings._set_settings_page(2)
            settings._populate_game_language_controls(fast=False)
            combo = settings.game_target_combo
        else:
            combo = window.target_lang
        monkeypatch.setattr(combo, '_available_screen_rect', lambda: QtCore.QRect(desktop))
        settle(app)
        return combo, desktop

    yield create
    opened = getattr(app, '_cnt_open_combo', lambda: None)()
    if opened is not None:
        opened.hidePopup()


def assert_popup_surface(combo, desktop, *, embedded, original_font, original_geometry):
    popup, view = combo.view().window(), combo.view()
    assert popup.isVisible()
    assert combo.font().key() == original_font.key()
    assert combo.geometry() == original_geometry
    assert popup.windowFlags() & QtCore.Qt.FramelessWindowHint
    assert popup.testAttribute(QtCore.Qt.WA_TranslucentBackground)
    if embedded:
        proxy = popup.graphicsProxyWidget()
        assert proxy is not None
        assert popup.testAttribute(QtCore.Qt.WA_DontShowOnScreen)
        root_proxy = combo.window().graphicsProxyWidget()
        bounds = proxy.mapRectToItem(root_proxy, proxy.boundingRect()).toAlignedRect()
        assert combo.window().rect().contains(bounds), (bounds, combo.window().rect())
    else:
        assert popup.graphicsProxyWidget() is None
        assert not popup.testAttribute(QtCore.Qt.WA_DontShowOnScreen)
        assert desktop.contains(popup.geometry()), (popup.geometry(), desktop)

    search = combo._language_search
    assert not search.isHidden()
    search_bounds = QtCore.QRect(search.mapTo(popup, QtCore.QPoint()), search.size())
    viewport_bounds = QtCore.QRect(view.viewport().mapTo(popup, QtCore.QPoint()), view.viewport().size())
    assert popup.rect().contains(search_bounds)
    assert popup.rect().contains(viewport_bounds)
    assert not search_bounds.intersects(viewport_bounds)
    assert search.fontMetrics().height() <= search.contentsRect().height()
    visible_row = next(row for row in range(combo.count()) if not view.isRowHidden(row))
    visible_index = combo.model().index(visible_row, combo.modelColumn())
    # Changing the host must not retain a search-field height measured using
    # the old stylesheet font after its text has already shrunk to match rows.
    assert search.height() <= view.visualRect(visible_index).height() * 1.25, (
        'search header is oversized for its option rows', search.height(), view.visualRect(visible_index))

    # Compare the actual presentation scales, rather than the requested bypass
    # flag: a retained proxy can still draw a popup carrying that native flag.
    expected = pixels(original_font) * surface_scale(combo)
    index = combo.model().index(0, combo.modelColumn())
    presented = {
        'painted row': pixels(combo.itemDelegate()._font(index)) * surface_scale(popup),
        'view measurement': pixels(view.font()) * surface_scale(popup),
        'search input': pixels(search.font()) * surface_scale(search),
    }
    for name, actual in presented.items():
        assert actual == pytest.approx(expected, abs=1.1), (name, actual, expected)
    assert view.visualRect(index).height() <= view.viewport().height()


def save_previews(window, combo, tmp_path, name, percent, opening):
    if percent not in (135, 137):
        return
    output = (Path(os.environ['XDG_DATA_HOME']).parent if os.environ.get('XDG_DATA_HOME')
              else tmp_path) / 'popup-host-renders'
    output.mkdir(parents=True, exist_ok=True)
    prefix = f'{name}-{percent}-{opening}'
    assert window.grab().save(str(output / (prefix+'-canvas.png')))
    assert combo.view().window().grab().save(str(output / (prefix+'-popup.png')))


def exercise_picker(window, combo, desktop, app, tmp_path, *, host, place, locale, percent, baseline_row=None):
    original_font = QtGui.QFont(combo.font())
    original_geometry = combo.geometry()
    popup = combo.view().window()
    for opening in (1, 2):
        combo.showPopup()
        settle(app)
        # Save the real surface before assertions so a failure remains visually
        # inspectable, including stale chrome after a host changes during Show.
        save_previews(window, combo, tmp_path, f'{host}-{place}-{locale}', percent, opening)
        assert_popup_surface(combo, desktop, embedded=host != 'native',
                             original_font=original_font, original_geometry=original_geometry)
        if sys.platform == 'win32' and host != 'late':
            assert popup.windowFlags() & QtCore.Qt.BypassGraphicsProxyWidget
        if baseline_row is not None:
            assert row_height(combo) == pytest.approx(baseline_row, abs=2.0)
        before = widget_global_rect(popup)
        current = combo.currentText()
        search = combo._language_search
        QTest.keyClicks(search, 'Vietnamese')
        settle(app)
        after = widget_global_rect(popup)
        assert after.topLeft() == before.topLeft()
        assert after.width() == before.width()
        assert after.height() < before.height()
        assert combo.currentText() == current
        rows = [row for row in range(combo.count()) if not combo.view().isRowHidden(row)]
        assert len(rows) == 1 and option_code(combo, rows[0], locale) == 'vi'
        assert_popup_surface(combo, desktop, embedded=host != 'native',
                             original_font=original_font, original_geometry=original_geometry)
        QTest.keyClick(search, QtCore.Qt.Key_Down)
        settle(app)
        assert option_code(combo, combo.view().currentIndex().row(), locale) == 'vi'
        QTest.keyClick(combo.view(), QtCore.Qt.Key_Return)
        settle(app)
        assert not popup.isVisible()
        assert option_code(combo, combo.currentIndex(), locale) == 'vi'
        assert combo.geometry() == original_geometry


@pytest.mark.parametrize('place', ('main', 'dynamic'))
@pytest.mark.parametrize('locale', ('en', 'ar'))
@pytest.mark.parametrize('percent', (80, 103, 135, 137, 200))
def test_retained_qt_popup_proxy_uses_the_canvas_zoom_once(window, app, language_picker, tmp_path, place, locale, percent):
    combo, desktop = language_picker(place, locale, percent)
    # Qt can create its automatic popup proxy before our custom show method.
    # A bypass flag applied afterwards must not count that proxy's zoom twice.
    QtWidgets.QComboBox.showPopup(combo)
    settle(app)
    popup = combo.view().window()
    assert popup.graphicsProxyWidget() is not None
    assert popup.testAttribute(QtCore.Qt.WA_DontShowOnScreen)
    baseline = row_height(combo)
    QtWidgets.QComboBox.hidePopup(combo)
    settle(app)
    assert popup.graphicsProxyWidget() is not None
    exercise_picker(window, combo, desktop, app, tmp_path, host='retained', place=place,
                    locale=locale, percent=percent, baseline_row=baseline)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows requests native popups outside the scaled canvas')
@pytest.mark.parametrize('place', ('main', 'dynamic'))
@pytest.mark.parametrize('locale', ('en', 'ar'))
@pytest.mark.parametrize('percent', (80, 103, 135, 137, 200))
def test_native_language_popup_uses_the_canvas_zoom_once(window, app, language_picker, tmp_path, place, locale, percent):
    combo, desktop = language_picker(place, locale, percent)
    exercise_picker(window, combo, desktop, app, tmp_path, host='native', place=place,
                    locale=locale, percent=percent)


@pytest.mark.skipif(sys.platform != 'win32', reason='Exercises a Windows bypass request followed by actual Qt embedding')
@pytest.mark.parametrize('place', ('main', 'dynamic'))
@pytest.mark.parametrize('locale', ('en', 'ar'))
@pytest.mark.parametrize('percent', (80, 103, 135, 137, 200))
def test_qt_embedding_during_show_remeasures_search_rows_and_popup_width(window, app, language_picker, monkeypatch, tmp_path, place, locale, percent):
    combo, desktop = language_picker(place, locale, percent)
    base_show = QtWidgets.QComboBox.showPopup
    attachments = []

    def platform_rehosts_after_base_show(control):
        popup = control.view().window()
        if control is not combo or popup.graphicsProxyWidget() is not None:
            return base_show(control)
        # This call occurs after DropDownCombo has measured its native host.
        # Let Qt show the native surface, then make Qt itself attach its popup
        # proxy before returning. No host predicate, scale/font helper or
        # production correction is mocked; both hosts are real Qt surfaces.
        base_show(control)
        assert popup.graphicsProxyWidget() is None
        popup.hide()
        popup.setWindowFlag(QtCore.Qt.BypassGraphicsProxyWidget, False)
        result = base_show(control)
        attachments.append(popup.graphicsProxyWidget())
        return result

    monkeypatch.setattr(QtWidgets.QComboBox, 'showPopup', platform_rehosts_after_base_show)
    exercise_picker(window, combo, desktop, app, tmp_path, host='late', place=place,
                    locale=locale, percent=percent)
    assert len(attachments) == 1 and attachments[0] is not None
