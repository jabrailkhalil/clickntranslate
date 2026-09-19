import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets, sip
from PyQt5.QtTest import QTest

from assistant_text import ASSISTANT_TEXT, assistant_text
from desktop_assistant import (DesktopAssistant, AssistantMenu, ACTION_METHODS,
                               clamp_position, normalized_position)
import mode_coordinator
from qt_layout_test_support import ensure_layout_fonts


@pytest.fixture(scope='module')
def app():
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ensure_layout_fonts(application)
    application.setQuitOnLastWindowClosed(False)
    return application


@pytest.fixture
def companion(app):
    owner = QtWidgets.QWidget()
    owner.config = {'desktop_assistant_enabled': True, 'translator_engine': 'DeepL'}
    owner.current_interface_language = 'ru'
    owner.current_theme = 'Темная'
    owner.save_config = mock.Mock()
    for name in (*ACTION_METHODS.values(), 'show_window_from_tray', 'show_main_screen', 'show_settings'):
        setattr(owner, name, mock.Mock())
    helper = DesktopAssistant(owner)
    yield helper
    helper.dispose()
    mode_coordinator.stop_active_mode()
    owner.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


def test_movie_and_capture_lifecycle_do_not_leave_the_companion_in_ocr(companion, app):
    assert companion.anchor.movie.isValid()
    assert companion.anchor.isVisible()
    assert companion.anchor.movie.state() == QtGui.QMovie.Running
    companion.toggle_menu()
    assert companion.menu.isVisible()
    mode_coordinator.request_mode('capture:translate', lambda: None)
    # Synchronous: already hidden when request_mode returns to the grabber.
    assert not companion.anchor.isVisible()
    assert not companion.menu.isVisible()
    assert companion.anchor.movie.state() == QtGui.QMovie.Paused
    mode_coordinator.request_mode('game', lambda: None)
    mode_coordinator.release_mode('capture:translate')
    assert not companion.anchor.isVisible()
    mode_coordinator.release_mode('game')
    assert companion.anchor.isVisible()
    assert companion.anchor.movie.state() == QtGui.QMovie.Running


@pytest.mark.parametrize('action', tuple(ACTION_METHODS) + ('text', 'settings'))
def test_actions_reuse_existing_workflows_and_preserve_provider(companion, action):
    companion.request_action(action)
    assert not companion.anchor.isVisible()
    companion.request_action(action)  # Ignore a duplicate click during dispatch.
    QTest.qWait(220)
    method = {'text': 'show_main_screen', 'settings': 'show_settings'}.get(action, ACTION_METHODS.get(action))
    getattr(companion.owner, method).assert_called_once_with()
    assert companion.owner.config['translator_engine'] == 'DeepL'
    QTest.qWait(370)
    assert companion.anchor.isVisible()


def test_disable_cancels_a_queued_capture(companion):
    companion.request_action('screen')
    companion.dispose()
    QTest.qWait(220)
    companion.owner.launch_fullscreen_translate.assert_not_called()


def test_newer_hotkey_is_not_replaced_by_a_pending_menu_click(companion):
    companion.request_action('screen')
    mode_coordinator.request_mode('game', lambda: None)
    QTest.qWait(220)
    companion.owner.launch_fullscreen_translate.assert_not_called()
    assert mode_coordinator.active_mode() == 'game'


def test_modal_dialog_blocks_assistant_actions(companion, app):
    dialog = QtWidgets.QDialog()
    dialog.setModal(True)
    dialog.show()
    app.processEvents()
    try:
        companion.toggle_menu()
        companion.request_action('screen')
        assert companion.menu is None
        assert not companion._dispatch_timer.isActive()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_theme_and_language_change_replace_the_menu_immediately(companion):
    companion.toggle_menu()
    old_menu = companion.menu
    companion.owner.current_theme = 'Светлая'
    companion.owner.current_interface_language = 'de'
    companion.refresh()
    assert not old_menu.isVisible()
    companion.toggle_menu()
    assert companion.menu.windowTitle() == assistant_text('de', 'title')
    assert '#f7f3fa' in companion.menu.styleSheet()
    assert not companion.anchor.dark


def test_drag_saves_relative_position_without_opening_actions(companion):
    start = companion.anchor.pos()
    press = QtCore.QPoint(42, 42)
    global_press = companion.anchor.mapToGlobal(press)
    companion.anchor.mousePressEvent(QtGui.QMouseEvent(QtCore.QEvent.MouseButtonPress,
        press, global_press, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier))
    target = global_press - QtCore.QPoint(80, 60)
    companion.anchor.mouseMoveEvent(QtGui.QMouseEvent(QtCore.QEvent.MouseMove,
        press, target, QtCore.Qt.NoButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier))
    companion.anchor.mouseReleaseEvent(QtGui.QMouseEvent(QtCore.QEvent.MouseButtonRelease,
        press, target, QtCore.Qt.LeftButton, QtCore.Qt.NoButton, QtCore.Qt.NoModifier))
    assert companion.anchor.pos() != start
    assert companion.menu is None
    assert normalized_position(companion.owner.config['desktop_assistant_position']) is not None
    companion.owner.save_config.assert_called_once()
    saved = companion.anchor.pos()
    companion.anchor.move(0, 0)
    companion.restore_position()
    assert companion.anchor.pos() == saved


@pytest.mark.parametrize('value', [None, {}, 'bad', {'screen': 'x', 'x': float('nan'), 'y': 1},
                                  {'screen': 'x', 'x': [], 'y': 1}])
def test_invalid_positions_fall_back_to_a_visible_anchor(value):
    assert normalized_position(value) is None


def test_negative_monitor_and_tiny_monitor_clamping():
    size = QtCore.QSize(84, 84)
    bounds = QtCore.QRect(-1920, -1080, 1920, 1040)
    for point in (QtCore.QPoint(-9999, -9999), QtCore.QPoint(9999, 9999)):
        assert bounds.contains(QtCore.QRect(clamp_position(point, size, bounds), size))
    assert clamp_position(QtCore.QPoint(99, 99), size, QtCore.QRect(0, 0, 40, 40)) == QtCore.QPoint(0, 0)


def test_settings_toggle_theme_scale_and_hide_stay_in_sync(app, tmp_path):
    import main
    import portable_paths
    from ui_scaling import MainWindowScaleController
    with mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True), \
            mock.patch.object(portable_paths, 'portable_base_dir', return_value=str(tmp_path)), \
            mock.patch.object(main, 'get_cached_config', return_value=dict(main.DEFAULT_CONFIG)), \
            mock.patch.object(main.DarkThemeApp, 'save_config'), \
            mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False), \
            mock.patch.object(MainWindowScaleController, 'available_geometry', return_value=QtCore.QRect(0, 0, 2560, 1440)):
        window = main.DarkThemeApp()
        try:
            window.show()
            window.show_settings()
            app.processEvents()
            checkbox = window.settings_window.desktop_assistant_checkbox
            original_size = window.size()
            assert not checkbox.isChecked()
            checkbox.click()
            helper = window._desktop_assistant
            assert helper.anchor.isVisible()
            assert window.config['desktop_assistant_enabled'] is True
            assert window.size() == original_size
            anchor_size = helper.anchor.size()
            window.set_ui_scale_percent(200)
            window.toggle_theme()
            app.processEvents()
            assert helper.anchor.size() == anchor_size
            assert helper.anchor.dark == (window.current_theme != 'Светлая')
            window.set_interface_language('ru')
            helper.request_action('hide')
            assert window._desktop_assistant is None
            assert not window.settings_window.desktop_assistant_checkbox.isChecked()
            assert window.config['desktop_assistant_enabled'] is False
        finally:
            window.force_quit = True
            window.close()
            window.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('language', tuple(ASSISTANT_TEXT))
@pytest.mark.parametrize('dark', (True, False))
def test_menu_buttons_are_readable_and_reachable_on_small_screens(app, language, dark):
    menu = AssistantMenu(language, dark)
    try:
        bounds = QtCore.QRect(0, 0, 640, 480)
        menu.open_beside(QtCore.QRect(550, 380, 84, 84), bounds)
        for _ in range(4):
            app.processEvents()
        assert bounds.contains(menu.geometry())
        for key, button in menu.buttons.items():
            for label in button.findChildren(QtWidgets.QLabel):
                required = label.heightForWidth(label.width())
                assert required <= label.height(), (language, key, label.text(), required, label.height())
            assert button.width() > 0
        requested = []
        menu.action_requested.connect(requested.append)
        menu.buttons['screen'].click()
        assert requested == ['screen']
        menu.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier))
        assert not menu.isVisible()
    finally:
        menu.close()
        menu.deleteLater()


def test_repeated_enable_appearance_changes_capture_and_dispose_release_widgets(companion, app):
    owner = companion.owner
    companion.dispose()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    listeners = len(mode_coordinator._listeners)
    for cycle in range(6):
        helper = DesktopAssistant(owner)
        discarded = []
        for index, language in enumerate(ASSISTANT_TEXT):
            owner.current_interface_language = language
            owner.current_theme = 'Светлая' if index % 2 else 'Темная'
            helper.refresh()
            helper.toggle_menu()
            assert helper.menu.isVisible()
            assert helper.anchor.size() == QtCore.QSize(84, 84)
            discarded.append(helper.menu)
            name = f'qa-capture-{cycle}-{index}'
            assert mode_coordinator.request_mode(name, lambda: None)
            assert not helper.anchor.isVisible() and not helper.menu.isVisible()
            assert helper.anchor.movie.state() != QtGui.QMovie.Running
            mode_coordinator.release_mode(name)
            assert helper.anchor.isVisible()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        helper.request_action('screen')
        anchor = helper.anchor
        helper.dispose()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()
        assert sip.isdeleted(anchor) and sip.isdeleted(helper)
        assert all(sip.isdeleted(menu) for menu in discarded)
        assert len(mode_coordinator._listeners) == listeners
    QTest.qWait(220)
    owner.launch_fullscreen_translate.assert_not_called()
