"""Persistent companion actions with fake source windows, input and providers."""
import ctypes
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

from assistant_text import assistant_text
from desktop_assistant import ACTION_METHODS, DesktopAssistant
import game_mode
import mode_coordinator
import platform_support


class FakeOwner(QtWidgets.QWidget):
    _show_status_signal = QtCore.pyqtSignal(str)
    _selection_finished_signal = QtCore.pyqtSignal(bool)


@pytest.fixture
def palette(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    assert app.platformName().split(':')[0] == 'offscreen', 'These tests must not open native windows'
    mode_coordinator.stop_active_mode()
    native = SimpleNamespace(current=101, restore_allowed=True)
    native.foreground = mock.Mock(side_effect=lambda: native.current)

    def restore(handle):
        if native.restore_allowed:
            native.current = handle.value
        return native.restore_allowed

    native.restore = mock.Mock(side_effect=restore)
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(platform_support, 'IS_MAC', False)
    monkeypatch.setattr(platform_support, 'IS_LINUX', False)
    monkeypatch.setattr(game_mode, '_foreground_window', native.foreground)
    monkeypatch.setattr(game_mode, '_window_belongs_to_this_process', lambda handle: handle == 900)
    monkeypatch.setattr(ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(
        SetForegroundWindow=native.restore)), raising=False)
    owner = FakeOwner()
    owner.config = {'desktop_assistant_enabled': True}
    owner.current_interface_language = 'en'
    owner.current_theme = 'Темная'
    owner.save_config = mock.Mock()
    for name in (*ACTION_METHODS.values(), 'show_window_from_tray', 'open_text_translation', 'show_settings'):
        setattr(owner, name, mock.Mock(return_value=True))
    helper = DesktopAssistant(owner)
    helper.toggle_menu()
    assert helper.menu.isVisible()
    try:
        yield SimpleNamespace(app=app, helper=helper, owner=owner, native=native)
    finally:
        helper.dispose()
        mode_coordinator.stop_active_mode()
        owner.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()


def dispatch_now(helper):
    helper._dispatch_timer.stop()
    helper._dispatch()


@pytest.mark.parametrize('action', ('selection', 'replace'))
def test_fresh_external_source_is_used_instead_of_the_source_at_opening(palette, action):
    helper, native, owner = palette.helper, palette.native, palette.owner
    assert helper._selection_target == 101
    native.current = 202
    helper.menu.buttons[action].click()
    assert helper.menu.isVisible()
    assert helper.anchor.isVisible()
    dispatch_now(helper)
    getattr(owner, ACTION_METHODS[action]).assert_called_once_with(expected_target=202)
    native.restore.assert_not_called()  # The newly selected source already owns focus.
    owner._selection_finished_signal.emit(True)
    assert helper.menu.isVisible()
    assert not helper._selection_pending
    assert not helper._dispatching


@pytest.mark.parametrize('action', ('selection', 'replace'))
def test_failed_focus_handoff_keeps_the_panel_and_never_starts_translation(palette, action):
    helper, native, owner = palette.helper, palette.native, palette.owner
    native.current = 900  # Explicit keyboard activation gave our panel focus.
    native.restore_allowed = False
    helper.menu.buttons[action].click()
    native.restore.assert_called_once()
    assert native.restore.call_args.args[0].value == 101
    getattr(owner, ACTION_METHODS[action]).assert_not_called()
    assert not helper._dispatch_timer.isActive()
    assert not helper._selection_pending
    assert not helper._dispatching
    assert helper.menu.isVisible()
    assert helper.menu.activity_label.text() == assistant_text('en', 'selection_focus_lost')
    assert helper.menu.buttons[action].isEnabled()


def test_verified_keyboard_focus_handoff_starts_the_saved_source(palette):
    helper, native, owner = palette.helper, palette.native, palette.owner
    native.current = 900
    helper.menu.buttons['selection'].click()
    assert native.current == 101
    native.restore.assert_called_once()
    dispatch_now(helper)
    owner.launch_translate_selection.assert_called_once_with(expected_target=101)
    assert helper.menu.isVisible()


def test_keyboard_invocation_accepts_focus_without_changing_mouse_invocation(palette):
    helper = palette.helper
    helper.toggle_menu()
    helper.toggle_menu(keyboard=True)
    assert helper.menu.keyboard_enabled
    assert not helper.menu.windowFlags() & QtCore.Qt.WindowDoesNotAcceptFocus
    helper.toggle_menu()
    helper.toggle_menu()
    assert not helper.menu.keyboard_enabled
    assert helper.menu.windowFlags() & QtCore.Qt.WindowDoesNotAcceptFocus


def test_source_is_frozen_for_the_request_even_if_another_app_activates_before_dispatch(palette):
    helper, native, owner = palette.helper, palette.native, palette.owner
    helper.menu.buttons['selection'].click()
    native.current = 202
    helper._remember_foreground()
    assert helper._selection_target == 202
    dispatch_now(helper)
    owner.launch_translate_selection.assert_called_once_with(expected_target=101)


def test_pending_selection_stays_open_and_blocks_duplicates_until_real_completion(palette):
    helper, owner = palette.helper, palette.owner
    helper.menu.buttons['selection'].click()
    dispatch_now(helper)
    assert helper._selection_pending and helper._dispatching
    assert not helper.menu.buttons['selection'].isEnabled()
    assert not helper.menu.buttons['area'].isEnabled()
    assert helper.menu.buttons['hide'].isEnabled()
    helper.request_action('selection')
    helper.request_action('area')
    QTest.qWait(400)  # The old fixed completion delay must not end this request.
    owner.launch_translate_selection.assert_called_once_with(expected_target=101)
    owner.launch_translate.assert_not_called()
    assert helper._selection_pending and helper._dispatching
    assert helper.menu.isVisible()
    owner._show_status_signal.emit('Selected text was not found; select text in the source app.')
    assert helper.menu.isVisible()
    assert helper.menu.activity_label.text().startswith('Selected text was not found')
    owner._selection_finished_signal.emit(False)
    assert not helper._selection_pending and not helper._dispatching
    assert helper.menu.isVisible()
    assert helper.menu.buttons['selection'].isEnabled()
    assert helper.menu.activity_label.text().startswith('Selected text was not found')


@pytest.mark.parametrize('success', (True, False))
def test_manual_close_while_waiting_does_not_reopen_on_completion(palette, success):
    helper, owner = palette.helper, palette.owner
    helper.menu.buttons['selection'].click()
    dispatch_now(helper)
    assert helper._selection_pending
    QTest.keyClick(helper.menu, QtCore.Qt.Key_Escape)
    assert not helper.menu.isVisible()
    assert not helper._panel_open
    owner._show_status_signal.emit('The source request has finished.')
    assert not helper.menu.isVisible()
    owner._selection_finished_signal.emit(success)
    palette.app.processEvents()
    assert not helper._dispatching
    assert not helper.menu.isVisible()
    assert helper.anchor.isVisible()


@pytest.mark.parametrize('action,mode', (('area', 'capture:translate'), ('screen', 'fullscreen'), ('dynamic', 'game')))
def test_capture_temporarily_hides_then_restores_an_explicitly_open_panel(palette, action, mode):
    helper, owner = palette.helper, palette.owner
    method = getattr(owner, ACTION_METHODS[action])
    method.side_effect = lambda: mode_coordinator.request_mode(mode, lambda: None)
    helper.menu.buttons[action].click()
    assert not helper.menu.isVisible()
    assert not helper.anchor.isVisible()
    assert helper._panel_open
    dispatch_now(helper)
    method.assert_called_once_with()
    helper._finish_dispatch()
    assert mode_coordinator.active_mode() == mode
    assert not helper.menu.isVisible()
    assert not helper.anchor.isVisible()
    assert mode_coordinator.release_mode(mode)
    assert helper.anchor.isVisible()
    assert helper.menu.isVisible()
    assert helper._panel_open


def test_a_panel_closed_before_capture_stays_closed_afterward(palette):
    helper, owner = palette.helper, palette.owner
    helper.toggle_menu()
    assert not helper.menu.isVisible()
    assert not helper._panel_open
    owner.launch_translate.side_effect = lambda: mode_coordinator.request_mode('capture:translate', lambda: None)
    helper.request_action('area')
    dispatch_now(helper)
    helper._finish_dispatch()
    mode_coordinator.release_mode('capture:translate')
    assert helper.anchor.isVisible()
    assert not helper.menu.isVisible()
    assert not helper._panel_open


def test_a_refused_worker_immediately_unlocks_the_panel(palette):
    helper, owner = palette.helper, palette.owner
    owner.launch_translate_selection.return_value = False
    helper.menu.buttons['selection'].click()
    dispatch_now(helper)
    assert not helper._selection_pending
    assert not helper._dispatching
    assert helper.menu.isVisible()
    assert helper.menu.buttons['selection'].isEnabled()


def test_failed_start_does_not_leave_a_delayed_callback_that_unlocks_the_next_job(palette):
    helper, owner = palette.helper, palette.owner
    owner.launch_translate_selection.side_effect = RuntimeError('test start failure')
    helper.menu.buttons['selection'].click()
    dispatch_now(helper)
    assert not helper._selection_pending and not helper._dispatching
    owner.launch_translate_selection.side_effect = None
    helper.menu.buttons['selection'].click()
    dispatch_now(helper)
    QTest.qWait(400)
    assert helper._selection_pending and helper._dispatching
    owner._selection_finished_signal.emit(True)


def test_unrelated_status_and_completion_cannot_change_an_idle_panel(palette):
    helper, owner = palette.helper, palette.owner
    before = helper.menu.activity_label.text()
    owner._show_status_signal.emit('Status from another workflow')
    owner._selection_finished_signal.emit(False)
    assert helper.menu.activity_label.text() == before
    assert helper.menu.isVisible()
    assert not helper._dispatching


def test_a_modal_opened_before_dispatch_cancels_pending_selection(palette):
    helper, owner = palette.helper, palette.owner
    helper.menu.buttons['selection'].click()
    helper._dispatch_timer.stop()
    with mock.patch.object(QtWidgets.QApplication, 'activeModalWidget', return_value=object()):
        helper._dispatch()
    helper._finish_dispatch()
    owner.launch_translate_selection.assert_not_called()
    assert not helper._selection_pending
    assert not helper._dispatching


def test_a_new_capture_before_selection_dispatch_takes_precedence(palette):
    helper, owner = palette.helper, palette.owner
    helper.menu.buttons['selection'].click()
    helper._dispatch_timer.stop()
    mode_coordinator.request_mode('capture:ocr', lambda: None)
    helper._dispatch()
    helper._finish_dispatch()
    owner.launch_translate_selection.assert_not_called()
    assert not helper._selection_pending
    assert not helper._dispatching
    assert not helper.menu.isVisible()
    assert mode_coordinator.release_mode('capture:ocr')
    assert helper.menu.isVisible()
