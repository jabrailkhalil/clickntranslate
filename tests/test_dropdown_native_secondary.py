"""Opt-in native Windows popup checks confined to a non-primary monitor.

No desktop input is injected. QTest sends events only to this test's Qt widgets.
Run through tools/run_regression_tests.py with the Windows platform explicitly.
"""
import os
from pathlib import Path
import sys
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import main
import ocr
from ui_scaling import MainWindowScaleController, widget_global_point, widget_global_rect


@pytest.fixture
def native_secondary():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if sys.platform != 'win32' or app.platformName().split(':', 1)[0] != 'windows':
        pytest.skip('Requires the explicitly selected native Windows Qt backend')
    screens = [screen for screen in app.screens() if screen is not app.primaryScreen()]
    if not screens:
        pytest.skip('No secondary monitor: never open test windows on the primary')
    screen = screens[0]
    bounds = screen.availableGeometry()
    if bounds.width() < 900 or bounds.height() < 600:
        pytest.skip('The secondary monitor is too small for this fixed-window check')
    config = dict(main.DEFAULT_CONFIG, interface_language='en',
                  hotkey_language_editor_mode='selection', show_update_info=False,
                  first_run_guide_pending=False, first_run_guide_completed=True,
                  desktop_assistant_enabled=False)
    with (mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True),
          mock.patch.object(main, 'get_cached_config', return_value=config),
          mock.patch.object(main.DarkThemeApp, 'save_config'),
          mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False),
          mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=['en', 'ru']),
          mock.patch.object(MainWindowScaleController, 'available_geometry', return_value=bounds)):
        window = main.DarkThemeApp()
        window.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        window.winId()
        window.windowHandle().setScreen(screen)
        window.set_ui_scale_percent(100)
        frame = window.frameGeometry()
        frame.moveCenter(bounds.center())
        window.move(frame.topLeft())
        assert window.windowHandle().screen() is screen
        assert bounds.contains(window.frameGeometry())
        window.show()
        QTest.qWait(30)
        assert window.windowHandle().screen() is screen
        assert bounds.contains(window.frameGeometry())
        try:
            yield app, window, screen, bounds
        finally:
            reference = getattr(app, '_cnt_open_combo', lambda: None)()
            if reference is not None:
                reference.hidePopup()
            window.force_quit = True
            window.close()
            window.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            app.processEvents()


def _assert_secondary_popup(combo, screen, bounds):
    popup = combo.view().window()
    assert popup.isVisible()
    assert popup.graphicsProxyWidget() is None
    assert popup.windowHandle() is not None
    assert popup.windowHandle().screen() is screen
    assert bounds.contains(popup.frameGeometry())
    return popup


def _save(popup, tmp_path, name):
    folder = Path(os.environ.get('CNT_DROPDOWN_NATIVE_IMAGES', str(tmp_path)))
    folder.mkdir(parents=True, exist_ok=True)
    assert popup.grab().save(str(folder / name))


def test_native_secondary_first_press_switches_popup_and_outside_press_closes(native_secondary, tmp_path):
    app, window, screen, bounds = native_secondary
    first, second = window.source_lang, window.target_lang
    # The other window must already exist. Creating a new native top-level
    # while a popup is open can close it independently of any pointer press.
    outside = QtWidgets.QWidget(None, QtCore.Qt.FramelessWindowHint)
    outside.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
    outside.resize(120, 70)
    outside.winId()
    outside.windowHandle().setScreen(screen)
    outside.move(bounds.topLeft() + QtCore.QPoint(12, 12))
    outside.show()
    app.processEvents()
    try:
        assert outside.windowHandle().screen() is screen
        assert bounds.contains(outside.frameGeometry())
        first.showPopup()
        QTest.qWait(30)
        old_popup = _assert_secondary_popup(first, screen, bounds)
        _save(old_popup, tmp_path, 'handoff-before.png')
        point = widget_global_point(second, second.rect().center())
        assert not widget_global_rect(old_popup).contains(point)
        # An actual native mouse grab addresses the old popup, not the next combo.
        QTest.mousePress(old_popup, QtCore.Qt.LeftButton, pos=old_popup.mapFromGlobal(point))
        assert not old_popup.isVisible()
        assert second.view().window().isVisible()
        app.processEvents()  # Let the native window report its screen association.
        new_popup = _assert_secondary_popup(second, screen, bounds)
        QTest.mouseRelease(new_popup, QtCore.Qt.LeftButton, pos=new_popup.mapFromGlobal(point))
        QTest.qWait(20)
        assert new_popup.isVisible()
        _save(new_popup, tmp_path, 'handoff-after.png')
        assert new_popup.isVisible()
        point = outside.mapToGlobal(outside.rect().center())
        assert not widget_global_rect(new_popup).contains(point)
        QTest.mousePress(new_popup, QtCore.Qt.LeftButton, pos=new_popup.mapFromGlobal(point))
        assert not new_popup.isVisible()  # Synchronous, before a timer/event turn.
        QTest.mouseRelease(outside, QtCore.Qt.LeftButton, pos=outside.rect().center())
    finally:
        outside.close()
        outside.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('language', ('en', 'ar'))
def test_native_secondary_filter_scroll_and_rounded_rendering(native_secondary, tmp_path, language):
    app, window, screen, bounds = native_secondary
    window.set_interface_language(language)
    window.set_ui_scale_percent(137)
    frame = window.frameGeometry()
    frame.moveCenter(bounds.center())
    window.move(frame.topLeft())
    app.processEvents()
    assert bounds.contains(window.frameGeometry())
    combo = window.hotkey_target_combo
    assert combo.count() >= 12
    combo.showPopup()
    QTest.qWait(30)
    popup = _assert_secondary_popup(combo, screen, bounds)
    before = QtCore.QRect(popup.geometry())
    search = combo._language_search
    input_before = QtCore.QRect(search.geometry())
    scrollbar = combo.view().verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(scrollbar.maximum())
    scroll_before = scrollbar.value()
    combo._queue_popup_layout()
    QTest.qWait(20)
    assert scrollbar.value() == scroll_before
    _save(popup, tmp_path, f'{language}-full.png')

    # QTest text events only target this test's search editor.
    QTest.keyClicks(search, 'Vietnamese')
    QTest.qWait(30)
    assert popup.geometry().topLeft() == before.topLeft()
    assert popup.width() == before.width()
    assert popup.height() < before.height()
    assert search.geometry() == input_before
    assert scrollbar.value() == 0
    _assert_secondary_popup(combo, screen, bounds)
    _save(popup, tmp_path, f'{language}-filtered.png')
    image = popup.grab().toImage()
    assert image.hasAlphaChannel()
    for x, y in ((0, 0), (image.width()-1, 0), (0, image.height()-1),
                 (image.width()-1, image.height()-1)):
        assert image.pixelColor(x, y).alpha() <= 8
    assert image.pixelColor(image.width()//2, 2).alpha() >= 240
    QTest.keyClick(search, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QTest.keyClick(search, QtCore.Qt.Key_Backspace)
    QTest.qWait(30)
    assert popup.geometry() == before
    assert search.geometry() == input_before
    combo.hidePopup()
