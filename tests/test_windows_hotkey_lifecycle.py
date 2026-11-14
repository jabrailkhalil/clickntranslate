"""Hotkey lifecycle contracts using fake WinAPI; never register OS shortcuts."""
import threading
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtWidgets
from PyQt5.QtTest import QTest

import main
from test_desktop_ux import app, window


class FakeUser32:
    def __init__(self, *, success=True, fail_loop=False):
        self.success, self.fail_loop = success, fail_loop
        self.registered = threading.Event()
        self.owner = None
        self.calls = []

    def RegisterHotKey(self, hwnd, identifier, modifiers, key):
        self.calls.append(('register', threading.get_ident(), identifier))
        if self.success:
            self.owner = threading.get_ident()
        self.registered.set()
        return int(self.success)

    def UnregisterHotKey(self, hwnd, identifier):
        self.calls.append(('unregister', threading.get_ident(), identifier))
        if self.owner != threading.get_ident():
            return 0  # Windows thread-owned hotkeys cannot be freed by the GUI.
        self.owner = None
        return 1

    def MsgWaitForMultipleObjects(self, *_args):
        if self.fail_loop:
            raise OSError('simulated message pump failure')
        threading.Event().wait(.002)
        return 258

    def PeekMessageW(self, *_args):
        return 0


@pytest.fixture
def fake_api(monkeypatch):
    user = FakeUser32()
    kernel = SimpleNamespace(GetCurrentThread=lambda: 1, SetThreadPriority=lambda *args: 1)
    monkeypatch.setattr(main.ctypes, 'windll', SimpleNamespace(user32=user, kernel32=kernel), raising=False)
    monkeypatch.setattr(main.platform_support, 'IS_MAC', False)
    return user


def test_listener_unregisters_on_its_registering_thread_before_replacement(fake_api):
    caller = threading.get_ident()
    for _ in range(3):
        fake_api.registered.clear()
        listener = main.HotkeyListenerThread('Ctrl+Alt+F23', lambda: None)
        listener.start()
        assert fake_api.registered.wait(2)
        listener.stop()
        listener.join(timeout=1)
        assert not listener.is_alive() and fake_api.owner is None
        register, unregister = fake_api.calls[-2:]
        assert register[1] == unregister[1] != caller
        assert not listener._registered


def test_message_pump_failure_still_releases_the_thread_owned_key(fake_api):
    fake_api.fail_loop = True
    listener = main.HotkeyListenerThread('Ctrl+Alt+F23', lambda: None)
    listener.start()
    listener.join(timeout=1)
    assert not listener.is_alive() and fake_api.owner is None
    assert [call[0] for call in fake_api.calls] == ['register', 'unregister']


def test_cancelled_listener_does_not_register_after_stop(fake_api):
    listener = main.HotkeyListenerThread('Ctrl+Alt+F23', lambda: None)
    listener.stop()
    listener.start()
    listener.join(timeout=1)
    assert not fake_api.calls


def test_failed_registration_never_unregisters_another_listeners_key(fake_api):
    fake_api.success = False
    listener = main.HotkeyListenerThread('Ctrl+Alt+F23', lambda: None)
    listener.start()
    listener.join(timeout=1)
    assert [call[0] for call in fake_api.calls] == ['register']
    assert not listener._registered


def test_queued_action_after_stop_is_ignored_and_recording_shortcuts_does_not_launch(app):
    callback = mock.Mock()
    listener = main.HotkeyListenerThread('Ctrl+Alt+F23', callback)
    editor = QtWidgets.QKeySequenceEdit()
    with mock.patch.object(main.QApplication, 'focusWidget', return_value=editor):
        listener._invoke()
    callback.assert_not_called()
    with mock.patch.object(main.QApplication, 'focusWidget', return_value=None):
        listener._invoke()
    callback.assert_called_once_with()
    listener.stop()
    listener._invoke()
    callback.assert_called_once_with()
    editor.deleteLater()


BINDINGS = (
    ('copy_hotkey', 'save_copy_hotkey', 'launch_copy', 1),
    ('translate_hotkey', 'save_translate_hotkey', 'launch_translate', 2),
    ('fullscreen_translate_hotkey', 'save_fullscreen_translate_hotkey', 'launch_fullscreen_translate', 3),
    ('translate_selection_hotkey', 'save_translate_selection_hotkey', 'launch_translate_selection', 4),
    ('translate_replace_selection_hotkey', 'save_translate_replace_selection_hotkey', 'launch_translate_replace_selection', 6),
    ('toggle_window_hotkey', 'save_toggle_window_hotkey', 'toggle_window_visibility', 5),
    ('game_translate_hotkey', 'save_game_translate_hotkey', 'launch_game_translate', 7),
)


@pytest.mark.parametrize('binding', BINDINGS, ids=lambda item: item[0])
def test_preview_and_layout_modes_save_preferences_without_registering_keys(window, binding):
    key, method, _callback, _identifier = binding
    assert window._hotkey_services_enabled is False  # Fixture uses layout mode.
    window.show_settings()
    settings = window.settings_window
    settings.show_hotkeys_screen()
    window.HotkeyListenerThread = mock.Mock()
    getattr(settings, key+'_input').setHotkeyText('Ctrl+Alt+F23')
    getattr(settings, method)()
    assert window.config[key] == 'Ctrl+Alt+F23'
    window.HotkeyListenerThread.assert_not_called()


@pytest.mark.parametrize('binding', BINDINGS, ids=lambda item: item[0])
def test_focus_out_without_editing_does_not_restart_a_working_shortcut(window, binding):
    key, method, _callback, _identifier = binding
    window.show_settings()
    settings = window.settings_window
    settings.show_hotkeys_screen()
    old = mock.Mock()
    old.is_alive.return_value = True
    setattr(window, key+'_thread', old)
    window.HotkeyListenerThread = mock.Mock()
    window._hotkey_services_enabled = True
    window.save_config.reset_mock()
    try:
        getattr(settings, method)()
        old.stop.assert_not_called()
        window.HotkeyListenerThread.assert_not_called()
        window.save_config.assert_not_called()
    finally:
        window._hotkey_services_enabled = False


@pytest.mark.parametrize('binding', BINDINGS, ids=lambda item: item[0])
def test_changed_shortcut_replaces_only_its_listener_and_clear_keeps_it_disabled(window, binding):
    key, method, callback, identifier = binding
    window.show_settings()
    settings = window.settings_window
    settings.show_hotkeys_screen()
    old, new = mock.Mock(), mock.Mock()
    setattr(window, key+'_thread', old)
    window.HotkeyListenerThread = mock.Mock(return_value=new)
    window._hotkey_services_enabled = True
    field = getattr(settings, key+'_input')
    try:
        field.setHotkeyText('Ctrl+Alt+F23')
        getattr(settings, method)()
        assert window.config[key] == 'Ctrl+Alt+F23'
        old.stop.assert_called_once_with()
        old.join.assert_called_once_with(timeout=.5)
        window.HotkeyListenerThread.assert_called_once_with(
            'Ctrl+Alt+F23', getattr(window, callback), hotkey_id=identifier)
        new.start.assert_called_once_with()
        window.HotkeyListenerThread.reset_mock()
        field.clear()
        getattr(settings, method)()
        assert window.config[key] == ''
        assert getattr(window, key+'_thread') is None
        new.stop.assert_called_once_with()
        window.HotkeyListenerThread.assert_not_called()
    finally:
        window._hotkey_services_enabled = False


def test_external_registration_conflict_preserves_saved_shortcut_and_editor(window, app, fake_api, monkeypatch):
    fake_api.success = False
    window.show_settings()
    settings = window.settings_window
    settings.show_hotkeys_screen()
    window._hotkey_services_enabled = True
    field = settings.copy_hotkey_input
    field.setHotkeyText('Ctrl+Alt+F23')
    messages = []
    monkeypatch.setattr(window, '_show_hotkey_error_dialog', lambda title, text: messages.append(text))
    try:
        settings.save_copy_hotkey()
        window.copy_hotkey_thread.join(timeout=1)
        # Delivery crosses from the native listener to Qt and then a short
        # GUI timer; allow both event turns without relying on a 100 ms race.
        for _ in range(20):
            if messages:
                break
            QTest.qWait(50)
        assert window.config['copy_hotkey'] == field.hotkeyText() == 'Ctrl+Alt+F23'
        assert messages and 'Ctrl+Alt+F23' in messages[0]
    finally:
        window._hotkey_services_enabled = False


def test_unchanged_shortcut_can_retry_a_failed_registration(window):
    window.show_settings()
    settings = window.settings_window
    settings.show_hotkeys_screen()
    old, new = mock.Mock(), mock.Mock()
    old.is_alive.return_value = False
    window.copy_hotkey_thread = old
    window.HotkeyListenerThread = mock.Mock(return_value=new)
    window._hotkey_services_enabled = True
    try:
        settings.save_copy_hotkey()
        old.stop.assert_called_once_with()
        new.start.assert_called_once_with()
        assert window.config['copy_hotkey'] == settings.copy_hotkey_input.hotkeyText()
    finally:
        window._hotkey_services_enabled = False


def test_import_does_not_enable_hotkeys_in_a_preview(window):
    window.HotkeyListenerThread = mock.Mock()
    window.restart_all_hotkey_listeners()
    window.HotkeyListenerThread.assert_not_called()
    assert all(getattr(window, key+'_thread') is None for key, *_ in BINDINGS)


def test_import_stops_all_old_listeners_before_starting_changed_bindings(window):
    events = []
    for key, *_ in BINDINGS:
        old = mock.Mock()
        old.stop.side_effect = lambda: events.append('stop')
        setattr(window, key+'_thread', old)
    window.HotkeyListenerThread = mock.Mock(side_effect=lambda *_args, **_kwargs: mock.Mock(
        start=lambda: events.append('start')))
    window._hotkey_services_enabled = True
    try:
        window.restart_all_hotkey_listeners()
        assert events == ['stop']*7 + ['start']*7
        assert window.HotkeyListenerThread.call_args_list == [
            mock.call(window.config[key], getattr(window, callback), hotkey_id=identifier)
            for key, _method, callback, identifier in BINDINGS]
    finally:
        window._hotkey_services_enabled = False
