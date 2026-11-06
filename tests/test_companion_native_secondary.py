"""Opt-in native companion checks; never show QA windows on the main monitor."""
import math
import sys
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from assistant_art import MASCOTS
from assistant_sprites import look_index
from desktop_assistant import ACTION_METHODS, DesktopAssistant


@pytest.fixture
def secondary_companion():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if sys.platform != 'win32' or app.platformName().split(':')[0] != 'windows':
        pytest.skip('Select the native Windows Qt backend explicitly')
    screen = next((s for s in app.screens() if s is not app.primaryScreen()), None)
    if screen is None:
        pytest.skip('A secondary monitor is required; do not use the primary')
    bounds = screen.availableGeometry()
    if bounds.width() < 800 or bounds.height() < 600:
        pytest.skip('Secondary monitor is too small for this native check')
    owner = QtWidgets.QWidget()
    owner.winId()
    owner.windowHandle().setScreen(screen)
    owner.move(bounds.center())
    owner.resize(200, 90)
    owner.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
    owner.show()
    owner.config = {'desktop_assistant_enabled': False, 'desktop_assistant_appearance': 'animated'}
    owner.current_interface_language = 'en'
    owner.current_theme = 'Темная'
    owner.save_config = mock.Mock()
    for name in (*ACTION_METHODS.values(), 'show_window_from_tray', 'open_text_translation', 'show_settings'):
        setattr(owner, name, mock.Mock())
    helper = DesktopAssistant(owner)
    helper.anchor.winId()
    helper.anchor.windowHandle().setScreen(screen)
    helper.anchor.move(bounds.center())
    owner.config['desktop_assistant_enabled'] = True
    helper.refresh()
    app.processEvents()
    QTest.qWait(100)
    assert helper.anchor.windowHandle().screen() is screen
    assert bounds.contains(helper.anchor.frameGeometry())
    try:
        yield app, helper, screen, bounds
    finally:
        helper.dispose()
        owner.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()


@pytest.mark.parametrize('language,dark', (('en', True), ('ar', False)))
@pytest.mark.parametrize('factor', (1., 1.37, 2.))
def test_gaze_and_full_menu_render_on_secondary(secondary_companion, language, dark, factor, tmp_path):
    app, helper, screen, bounds = secondary_companion
    helper.owner.current_interface_language = language
    helper.owner.current_theme = 'Темная' if dark else 'Светлая'
    for index, mascot in enumerate(MASCOTS):
        helper.owner.config['desktop_assistant_mascot'] = mascot
        helper.refresh()
        helper._context = (*helper._context[:2], factor, *helper._context[3:])
        if helper.menu is not None:
            helper.menu.close()
            helper.menu.deleteLater()
            helper.menu = None
        # Exercise placement above and below, without moving the real pointer.
        anchor = helper.anchor
        anchor.move(bounds.center().x(), bounds.top()+12 if index % 2 else bounds.bottom()-anchor.height()-12)
        assert bounds.contains(anchor.frameGeometry())
        anchor._hover = True
        for point, direction in ((QtCore.QPointF(2, anchor.height()*.44), 12),
                                 (QtCore.QPointF(anchor.width()-2, anchor.height()*.44), 4)):
            event = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, point, QtCore.Qt.NoButton,
                                     QtCore.Qt.NoButton, QtCore.Qt.NoModifier)
            app.sendEvent(anchor, event)
            assert look_index(anchor._gaze_angle) == direction
        helper.toggle_menu()
        QTest.qWait(20)
        menu = helper.menu
        assert menu.isVisible()
        assert menu.windowHandle().screen() is screen
        assert bounds.contains(menu.frameGeometry())
        assert menu.content.rect().contains(menu.scroll.geometry())
        assert not menu.scroll.geometry().intersects(menu.footer.geometry())
        assert menu.scroll.horizontalScrollBar().maximum() == 0
        eye = anchor.geometry().topLeft()+QtCore.QPoint(anchor.width()//2, round(anchor.height()*.44))
        offset = menu.geometry().center()-eye
        expected = math.degrees(math.atan2(offset.x(), -offset.y())) % 360
        assert look_index(anchor._menu_gaze_angle) == look_index(expected)
        for widget, name in ((anchor, 'hero'), (menu, 'menu')):
            image = widget.grab().toImage()
            assert image.hasAlphaChannel()
            for x, y in ((0, 0), (image.width()-1, 0), (0, image.height()-1),
                         (image.width()-1, image.height()-1)):
                assert image.pixelColor(x, y).alpha() <= 8
            assert image.save(str(tmp_path / f'{mascot}-{name}.png'))
        before = anchor.grab().toImage()
        app.sendEvent(anchor, QtCore.QEvent(QtCore.QEvent.Leave))
        assert anchor.grab().toImage() == before
        QTest.keyClick(menu, QtCore.Qt.Key_Escape)
        assert not menu.isVisible()
        assert anchor._menu_gaze_angle is None
    helper.owner.save_config.assert_not_called()


def test_palette_click_keeps_foreground_and_outside_click_keeps_palette(secondary_companion, tmp_path):
    import ctypes
    from ctypes import wintypes
    import game_mode
    app, helper, screen, bounds = secondary_companion
    api = ctypes.WinDLL('user32', use_last_error=True)
    api.GetForegroundWindow.restype = wintypes.HWND
    api.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    api.SendMessageW.restype = ctypes.c_ssize_t
    before = int(api.GetForegroundWindow() or 0)
    if not before or game_mode._window_belongs_to_this_process(before):
        pytest.skip('An external foreground target is required; never activate another app for this test')
    helper.toggle_menu()
    menu = helper.menu
    QTest.qWait(30)
    assert menu.windowType() == QtCore.Qt.Tool
    assert menu.windowFlags() & QtCore.Qt.WindowDoesNotAcceptFocus
    import window_layer
    _, get_style = window_layer._windows_api()
    assert get_style(int(menu.winId()), -20) & 0x08000000  # WS_EX_NOACTIVATE.
    assert menu.windowHandle().screen() is screen
    assert int(api.GetForegroundWindow() or 0) == before
    # Send only to our own test window. No global pointer or keyboard input.
    result = api.SendMessageW(int(menu.winId()), 0x0021, int(menu.winId()), (0x0201 << 16) | 1)
    assert result == 3  # MA_NOACTIVATE: deliver the press without taking focus.
    point = menu.buttons['selection'].mapTo(menu, menu.buttons['selection'].rect().center())
    coordinates = (point.y() << 16) | (point.x() & 0xffff)
    # Exercise Qt's native mouse dispatcher too, rather than bypassing it
    # with a QMouseEvent delivered directly to the QPushButton.
    api.SendMessageW(int(menu.winId()), 0x0201, 1, coordinates)  # WM_LBUTTONDOWN.
    api.SendMessageW(int(menu.winId()), 0x0202, 0, coordinates)  # WM_LBUTTONUP.
    assert menu.isVisible()
    assert int(api.GetForegroundWindow() or 0) == before
    QTest.qWait(230)
    helper.owner.launch_translate_selection.assert_called_once_with(expected_target=before)
    assert menu.isVisible()
    assert int(api.GetForegroundWindow() or 0) == before
    app.sendEvent(menu, QtCore.QEvent(QtCore.QEvent.WindowDeactivate))
    QTest.mouseClick(helper.owner, QtCore.Qt.LeftButton)
    assert menu.isVisible()
    menu.set_status('Select text in another app, then try again.', error=True)
    QTest.qWait(20)
    assert bounds.contains(menu.frameGeometry())
    assert menu.scroll.verticalScrollBar().maximum() == 0, (
        menu.scroll.viewport().size(), menu.action_surface.size(), menu.action_surface.contentsMargins(),
        menu.action_surface.heightForWidth(menu.action_surface.width()), menu.action_surface.minimumSizeHint())
    assert menu.grab().save(str(tmp_path / 'persistent-palette-status.png'))
    helper.toggle_menu()
    assert not menu.isVisible()
    # Keyboard access can explicitly remove the native no-activation style;
    # merely changing this mode on a hidden window must not activate it.
    menu.set_keyboard_enabled(True)
    assert not get_style(int(menu.winId()), -20) & 0x08000000
    assert int(api.GetForegroundWindow() or 0) == before
    menu.set_keyboard_enabled(False)
    assert get_style(int(menu.winId()), -20) & 0x08000000
