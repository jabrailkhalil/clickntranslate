"""Dock visibility and menu-bar restoration without driving another app's UI."""
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

import macos_desktop


@pytest.mark.parametrize('visible, current, expected', [(False, 0, 1), (True, 1, 0), (False, 1, None)])
def test_dock_policy_switches_only_when_needed(monkeypatch, visible, current, expected):
    application = SimpleNamespace(activationPolicy=lambda: current, setActivationPolicy_=mock.Mock(return_value=True))
    framework = SimpleNamespace(NSApplication=SimpleNamespace(sharedApplication=lambda: application),
                                NSApplicationActivationPolicyRegular=0, NSApplicationActivationPolicyAccessory=1)
    monkeypatch.setitem(sys.modules, 'AppKit', framework)
    macos_desktop.set_dock_visible(visible)
    if expected is None:
        application.setActivationPolicy_.assert_not_called()
    else:
        application.setActivationPolicy_.assert_called_once_with(expected)


def test_rejected_dock_policy_is_reported(monkeypatch):
    application = SimpleNamespace(activationPolicy=lambda: 0, setActivationPolicy_=lambda policy: False)
    framework = SimpleNamespace(NSApplication=SimpleNamespace(sharedApplication=lambda: application),
                                NSApplicationActivationPolicyRegular=0, NSApplicationActivationPolicyAccessory=1)
    monkeypatch.setitem(sys.modules, 'AppKit', framework)
    with pytest.raises(RuntimeError, match='Dock visibility'):
        macos_desktop.set_dock_visible(False)


@pytest.mark.skipif(sys.platform != 'darwin', reason='requires native AppKit')
def test_native_shadow_startup_menu_hotkey_close_and_dock_minimize(monkeypatch):
    import AppKit
    import main
    from PyQt5 import QtCore, QtWidgets
    from macos_smoke import shadow_mode_check

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if app.platformName() != 'cocoa':
        pytest.skip('requires Cocoa status item and activation policy')
    app.setQuitOnLastWindowClosed(False)
    nsapp = AppKit.NSApplication.sharedApplication()
    original_policy = nsapp.activationPolicy()
    monkeypatch.setattr(main, 'LAYOUT_EDITOR_MODE', True)
    monkeypatch.setattr(main, 'get_cached_config', lambda: dict(main.DEFAULT_CONFIG))
    monkeypatch.setattr(main.DarkThemeApp, 'save_config', lambda self: None)
    monkeypatch.setattr(main.DarkThemeApp, 'sync_autostart_state', lambda self, **kwargs: False)
    monkeypatch.setattr(main.DarkThemeApp, '_maybe_start_first_run_guide', lambda self: None)
    window = main.DarkThemeApp()
    window.create_tray_icon()
    try:
        # A deliberately moved window must not jump when AppKit restores it.
        window.move(window.screen().availableGeometry().topLeft() + QtCore.QPoint(40, 50))
        result = shadow_mode_check(main, app, window)
        assert result['cases'] == 13
        assert result['shadow_hotkey_callbacks'] == 10
    finally:
        window.force_quit = True
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        nsapp.setActivationPolicy_(original_policy)
