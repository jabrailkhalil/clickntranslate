"""Check the Cocoa panel, including state Qt's isVisible() cannot report."""
import sys
from unittest import mock

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'darwin', reason='requires native Cocoa panels')


@pytest.mark.parametrize('size', [60, 100, 180])
@pytest.mark.parametrize('topmost', [True, False])
def test_native_companion_has_no_shadow_and_survives_close_to_tray(size, topmost, monkeypatch):
    import AppKit
    import Quartz
    import objc
    from PyQt5 import QtCore, QtWidgets
    from PyQt5.QtTest import QTest
    import main
    import macos_desktop
    import mode_coordinator
    from desktop_assistant import DesktopAssistant

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if app.platformName() != 'cocoa':
        pytest.skip('requires native Cocoa window visibility')
    app.setQuitOnLastWindowClosed(False)
    native_app = AppKit.NSApplication.sharedApplication()
    original_policy = native_app.activationPolicy()
    monkeypatch.setattr(main, 'LAYOUT_EDITOR_MODE', True)
    mode_coordinator.stop_active_mode()

    class Owner(QtWidgets.QWidget):
        closeEvent = main.DarkThemeApp.closeEvent
        minimize_to_tray = main.DarkThemeApp.minimize_to_tray
        _set_macos_dock_visible = main.DarkThemeApp._set_macos_dock_visible

        def has_tray(self):
            return True

    owner = Owner()
    owner.force_quit = False
    owner.current_theme = 'Светлая'
    owner.current_interface_language = 'ru'
    owner.config = dict(main.DEFAULT_CONFIG, desktop_assistant_enabled=True,
                        desktop_assistant_size=size, desktop_assistant_topmost=topmost)
    owner.save_config = mock.Mock()
    owner.show()
    helper = DesktopAssistant(owner)
    owner._desktop_assistant = helper

    def native_anchor():
        return objc.objc_object(c_void_p=int(helper.anchor.winId())).window()

    def on_screen():
        number = int(native_anchor().windowNumber())
        windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, 0)
        return any(int(w.get('kCGWindowNumber', 0)) == number for w in windows)

    try:
        native_app.activateIgnoringOtherApps_(True)
        QTest.qWait(100)
        assert not native_anchor().hasShadow()
        assert not native_anchor().hidesOnDeactivate()
        assert on_screen()
        owner.close()  # The production close handler keeps the app in the tray.
        QTest.qWait(150)
        assert not owner.isVisible()
        assert native_app.activationPolicy() == AppKit.NSApplicationActivationPolicyAccessory
        assert not helper._closed and on_screen()
        finder = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_('com.apple.finder')[0]
        finder.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
        QTest.qWait(250)
        assert not native_app.isActive()
        assert on_screen(), 'Cocoa hid the companion when the application deactivated'
        # Recreating the panel for the topmost setting must preserve both fixes.
        owner.config['desktop_assistant_topmost'] = not topmost
        helper.refresh()
        QTest.qWait(100)
        assert not native_anchor().hasShadow()
        assert not native_anchor().hidesOnDeactivate()
        assert on_screen()
        # Explicit app hiding (e.g. the permissions guide) still hides everything.
        native_app.hide_(None)
        QTest.qWait(100)
        assert not on_screen()
        native_app.unhide_(None)
        QTest.qWait(100)
        assert on_screen()
        mode_coordinator.request_mode('capture:translate', lambda: None)
        QTest.qWait(30)
        assert not on_screen()
        mode_coordinator.release_mode('capture:translate')
        QTest.qWait(30)
        assert on_screen()
        owner.save_config.assert_not_called()
    finally:
        mode_coordinator.stop_active_mode()
        helper.dispose()
        owner.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        native_app.unhide_(None)
        native_app.setActivationPolicy_(original_policy)
