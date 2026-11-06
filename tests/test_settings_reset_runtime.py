"""Reset applies default preferences to running services without native hooks."""
from unittest import mock

from PyQt5 import QtCore

import main
import settings_window
from test_desktop_ux import app, window


class ResetMessages:
    Question, Warning, Information, YesRole, NoRole, Yes, No = range(7)
    count = 0

    def __init__(self, _parent=None):
        type(self).count += 1
        self.index = type(self).count
        self.yes = object()

    def __getattr__(self, name):
        if name.startswith('set'):
            return lambda *_args: None
        raise AttributeError(name)

    def addButton(self, _label, role):
        return self.yes if role == self.YesRole else object()

    def exec_(self):
        pass

    def clickedButton(self):
        # Confirm Reset, preserve histories, dismiss the completion notice.
        return self.yes if self.index == 1 else None


class FakeListener:
    created = []

    def __init__(self, shortcut, callback=None, hotkey_id=None):
        self.shortcut = shortcut
        self.callback = callback
        self.hotkey_id = hotkey_id
        self.running = False
        self.stopped = False
        type(self).created.append(self)

    def start(self):
        self.running = True

    def stop(self):
        self.running = False
        self.stopped = True

    def join(self, timeout=None):
        pass


def test_reset_replaces_custom_shortcuts_and_stops_enabled_selection_action(window, app, monkeypatch):
    window.set_interface_language('de')
    window.show_settings()
    settings = window.settings_window
    window.config.update(copy_hotkey='Ctrl+Shift+Y', selection_quick_translate_enabled=True,
                         selection_quick_translate_mode='automatic', capture_area_memory_modes=['translate', 'copy'],
                         remember_translate_area=True, remember_copy_area=True,
                         last_translate_area={'screen': 'old screen'}, last_copy_area={'screen': 'old screen'})
    old = FakeListener('Ctrl+Shift+Y')
    old.start()
    controller = mock.Mock(enabled=True, mode='automatic')

    def configure(enabled, mode):
        controller.enabled, controller.mode = enabled, mode

    controller.configure.side_effect = configure
    monkeypatch.setattr(window, 'copy_hotkey_thread', old, raising=False)
    monkeypatch.setattr(window, '_selection_quick_translate', controller, raising=False)
    monkeypatch.setattr(window, 'HotkeyListenerThread', FakeListener, raising=False)
    monkeypatch.setattr(window, '_hotkey_services_enabled', True)
    monkeypatch.setattr(window, 'set_autostart', lambda enabled: enabled)
    monkeypatch.setattr(settings_window, 'QMessageBox', ResetMessages)
    ResetMessages.count = 0
    FakeListener.created.clear()

    settings.reset_settings()
    for _ in range(3):
        app.processEvents()

    defaults = main.fresh_config('de')
    assert old.stopped and not old.running
    bindings = ((1, 'copy_hotkey'), (2, 'translate_hotkey'), (3, 'fullscreen_translate_hotkey'),
                (4, 'translate_selection_hotkey'), (6, 'translate_replace_selection_hotkey'),
                (5, 'toggle_window_hotkey'), (7, 'game_translate_hotkey'))
    assert [(item.hotkey_id, item.shortcut) for item in FakeListener.created] == [
        (hotkey_id, defaults[key]) for hotkey_id, key in bindings]
    assert all(item.running for item in FakeListener.created)
    assert controller.enabled is False and controller.mode == 'button'
    assert window.config['interface_language'] == 'de'
    for key in ('remember_translate_area', 'remember_copy_area'):
        assert window.config[key] is False
    assert window.config['last_translate_area'] is None
    assert window.config['last_copy_area'] is None
    assert settings.capture_memory_modes.checked_modes() == ()
    assert settings.settings_pages.currentIndex() == 0
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
