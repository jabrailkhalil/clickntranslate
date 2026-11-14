"""Registration errors belong to a listener until GUI delivery, with fake OS APIs."""
import threading
from types import SimpleNamespace

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import main


class ErrorOwner(QtCore.QObject):
    _on_hotkey_registration_failed = main.DarkThemeApp._on_hotkey_registration_failed
    _flush_hotkey_registration_errors = main.DarkThemeApp._flush_hotkey_registration_errors
    restart_all_hotkey_listeners = main.DarkThemeApp.restart_all_hotkey_listeners

    def __init__(self):
        super().__init__()
        self.current_interface_language = 'en'
        self.force_quit = False
        self.dialogs = []
        self._show_hotkey_error_dialog = lambda *args: self.dialogs.append(args)
        self._hotkey_services_enabled = True
        self.config = {'copy_hotkey': 'Ctrl+Alt+F3'}
        self.HotkeyListenerThread = main.HotkeyListenerThread
        for name in ('launch_copy', 'launch_translate', 'launch_fullscreen_translate',
                     'launch_translate_selection', 'launch_translate_replace_selection',
                     'toggle_window_visibility', 'launch_game_translate'):
            setattr(self, name, lambda: None)

    def _on_owned_hotkey_registration_failed(self, cancelled, shortcut):
        # The fixture also runs on the before-fix source without this method.
        return main.DarkThemeApp._on_owned_hotkey_registration_failed(self, cancelled, shortcut)


class FakeUser32:
    def __init__(self):
        self.succeeds = False
        self.fail_loop = False
        self.registered = threading.Event()
        self.calls = []

    def RegisterHotKey(self, _window, identifier, _modifiers, _key):
        self.calls.append(('register', identifier, self.succeeds))
        if self.succeeds:
            self.registered.set()
        return int(self.succeeds)

    def UnregisterHotKey(self, _window, identifier):
        self.calls.append(('unregister', identifier))
        return 1

    def MsgWaitForMultipleObjects(self, *_args):
        if self.fail_loop:
            raise OSError('synthetic message-pump failure')
        threading.Event().wait(.002)
        return 258

    def PeekMessageW(self, *_args):
        return 0


@pytest.fixture
def scenario(monkeypatch):
    assert QtWidgets.QApplication.platformName().split(':')[0] == 'offscreen'
    user = FakeUser32()
    kernel = SimpleNamespace(GetCurrentThread=lambda: 1, SetThreadPriority=lambda *_args: 1)
    monkeypatch.setattr(main.ctypes, 'windll', SimpleNamespace(user32=user, kernel32=kernel), raising=False)
    monkeypatch.setattr(main.platform_support, 'IS_MAC', False)
    owner = ErrorOwner()
    dispatcher = main._HotkeyErrorDispatcher()
    monkeypatch.setattr(main, 'hotkey_error_dispatcher', dispatcher)
    dispatcher.registration_failed.connect(owner._on_hotkey_registration_failed)
    if hasattr(dispatcher, 'registration_failed_owned'):
        dispatcher.registration_failed_owned.connect(owner._on_owned_hotkey_registration_failed)
    state = SimpleNamespace(user=user, owner=owner, dispatcher=dispatcher, listeners=[])

    def listener(shortcut=None):
        value = main.HotkeyListenerThread(shortcut or owner.config['copy_hotkey'], lambda: None)
        state.listeners.append(value)
        return value

    state.listener = listener
    try:
        yield state
    finally:
        current = getattr(owner, 'copy_hotkey_thread', None)
        listeners = list(state.listeners)
        if current is not None and current not in listeners:
            listeners.append(current)
        for value in listeners:
            value.stop()
            value.join(1)
            assert not value.is_alive()
        owner.deleteLater()
        QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('delivery', ['queued-signal', 'pending-dialog-timer'])
def test_successful_same_chord_retry_retires_the_old_listener_warning(scenario, delivery):
    state, owner = scenario, scenario.owner
    old = state.listener()
    owner.copy_hotkey_thread = old
    old.start()
    old.join(1)
    assert not old.is_alive() and owner.dialogs == []
    if delivery == 'pending-dialog-timer':
        QtWidgets.QApplication.processEvents()
        assert owner._hotkey_registration_error_timer.isActive()
    state.user.succeeds = True
    owner.restart_all_hotkey_listeners()
    current = owner.copy_hotkey_thread
    assert current is not old and old._stop_event.is_set()
    assert state.user.registered.wait(1) and current.is_alive()
    QTest.qWait(160)
    assert current.is_alive() and current._registered
    assert owner.dialogs == []


def test_mixed_queued_errors_keep_the_current_failure_and_drop_the_retired_one(scenario):
    old, current = scenario.listener('Ctrl+Alt+F3'), scenario.listener('Ctrl+Alt+F4')
    old.start()
    old.join(1)
    current.start()
    current.join(1)
    assert not old.is_alive() and not current.is_alive()
    old.stop()
    QTest.qWait(160)
    assert len(scenario.owner.dialogs) == 1
    assert 'Ctrl+Alt+F4' in scenario.owner.dialogs[0][1]
    assert 'Ctrl+Alt+F3' not in scenario.owner.dialogs[0][1]


def test_listener_retired_during_another_modal_cannot_show_a_late_warning(scenario):
    owner = scenario.owner
    old = scenario.listener()

    def modal(*args):
        owner.dialogs.append(args)
        if len(owner.dialogs) == 1:
            old.start()
            old.join(1)
            # An existing modal's nested loop can receive another worker error.
            QtWidgets.QApplication.processEvents()
            old.stop()

    owner._show_hotkey_error_dialog = modal
    owner._on_hotkey_registration_failed('Ctrl+Alt+F2')
    QTest.qWait(350)
    assert len(owner.dialogs) == 1
    assert 'Ctrl+Alt+F2' in owner.dialogs[0][1]


def test_new_reload_retires_pending_synchronous_admission_failures(scenario):
    owner = scenario.owner

    def refuse(*_args, **_kwargs):
        raise OSError('synthetic exhausted listener capacity')

    owner.HotkeyListenerThread = refuse
    owner.restart_all_hotkey_listeners()
    assert owner.dialogs == [] and owner._hotkey_registration_error_timer.isActive()
    owner.HotkeyListenerThread = main.HotkeyListenerThread
    scenario.user.succeeds = True
    owner.restart_all_hotkey_listeners()
    assert scenario.user.registered.wait(1)
    QTest.qWait(160)
    assert owner.copy_hotkey_thread.is_alive()
    assert owner.dialogs == []


BACKENDS = ['invalid', 'windows-register', 'windows-pump', 'mac-registry', 'double-tap-registry']


def failed_listener(scenario, monkeypatch, backend):
    def refused(*_args, **_kwargs):
        raise RuntimeError('synthetic registry refusal')

    shortcut = 'Ctrl+Alt+F3'
    if backend == 'invalid':
        shortcut = 'Ctr+V'
    elif backend == 'windows-pump':
        scenario.user.succeeds, scenario.user.fail_loop = True, True
    elif backend == 'mac-registry':
        import macos_hotkeys
        monkeypatch.setattr(main.platform_support, 'IS_MAC', True)
        monkeypatch.setattr(macos_hotkeys, 'registry', lambda: SimpleNamespace(register=refused))
    elif backend == 'double-tap-registry':
        import double_tap_hotkeys
        shortcut = 'Ctrl, Ctrl'
        monkeypatch.setattr(double_tap_hotkeys, 'registry', lambda: SimpleNamespace(register=refused))
    listener = scenario.listener(shortcut)
    listener.start()
    listener.join(1)
    assert not listener.is_alive()
    return listener, shortcut


@pytest.mark.parametrize('backend', BACKENDS)
def test_retired_error_from_each_listener_backend_is_suppressed(scenario, monkeypatch, backend):
    listener, _shortcut = failed_listener(scenario, monkeypatch, backend)
    listener.stop()
    QTest.qWait(160)
    assert scenario.owner.dialogs == []


@pytest.mark.parametrize('backend', BACKENDS)
def test_current_error_from_each_listener_backend_still_reports(scenario, monkeypatch, backend):
    _listener, shortcut = failed_listener(scenario, monkeypatch, backend)
    QTest.qWait(160)
    assert len(scenario.owner.dialogs) == 1
    assert shortcut in scenario.owner.dialogs[0][1]
