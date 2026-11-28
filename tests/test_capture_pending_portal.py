"""A desktop mode can change while its screenshot portal is running a nested Qt loop."""

from unittest import mock
from types import SimpleNamespace
import sys
import threading

import pytest
import PyQt5
from PyQt5 import QtCore, QtGui, QtWidgets

import linux_capture
import mode_coordinator
import ocr
import platform_support
from test_frozen_capture_session import frame


@pytest.fixture
def pending_capture(frame, monkeypatch, tmp_path):
    app, area, pixels = frame
    screen = area._active_screen
    area.thread.return_value = app.thread()
    area.windowState.return_value = QtCore.Qt.WindowNoState
    area._get_active_screen.return_value = screen
    area._capture_frozen_background.side_effect = lambda rect: ocr.ScreenCaptureOverlay._capture_frozen_background(area, rect)
    area.show_overlay.side_effect = lambda: ocr.ScreenCaptureOverlay.show_overlay(area)
    monkeypatch.setattr(platform_support, 'IS_LINUX', True)
    monkeypatch.setattr(platform_support, 'IS_MAC', False)
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', False)
    monkeypatch.setattr(platform_support, 'is_wayland', lambda: True)
    monkeypatch.setattr(QtGui.QCursor, 'pos', lambda: QtCore.QPoint(-80, 70))
    monkeypatch.setattr(QtWidgets.QApplication, 'screens', lambda: [screen])
    monkeypatch.setattr(QtWidgets.QApplication, 'screenAt', lambda p: screen)
    monkeypatch.setattr(ocr, 'style_capture_controls', mock.Mock())
    monkeypatch.setattr(ocr, '_ACTIVE_OVERLAYS', {})
    monkeypatch.setattr(ocr, '_OVERLAY_POOL', {'copy': area})
    monkeypatch.setattr(ocr, '_fullscreen_overlay_ref', None)
    monkeypatch.setattr(linux_capture, 'qt_platform_name', lambda: 'wayland')
    monkeypatch.setattr(linux_capture, 'portal_available', lambda: True)
    helpers = mock.Mock(side_effect=AssertionError('Capture helper attempted after a superseded mode'))
    monkeypatch.setattr(linux_capture, 'capture_with_helper', helpers)
    image = tmp_path / 'synthetic.png'
    assert pixels.save(str(image))

    def pending(callback, *, answer=True):
        bus = mock.Mock()
        bus.baseService.return_value = ':1.12'
        subscription = {}
        def connect(_service, path, _interface, _signal, slot):
            subscription.update(path=path, slot=slot)
            return True
        bus.connect.side_effect = connect
        def screenshot(*_args):
            def dispatch():
                callback()
                if answer and not bus.asyncCall.called:
                    subscription['slot'](0, {'uri': str(image)})
            QtCore.QTimer.singleShot(0, dispatch)
            return SimpleNamespace(isValid=lambda: True, value=lambda: subscription['path'])
        screenshot = mock.Mock(side_effect=screenshot)
        dbus = SimpleNamespace(
            QDBusConnection=SimpleNamespace(sessionBus=lambda: bus), QDBusReply=lambda value: value,
            QDBusMessage=SimpleNamespace(createMethodCall=lambda *args: args),
            QDBusInterface=lambda *_: SimpleNamespace(isValid=lambda: True, call=screenshot))
        monkeypatch.setitem(sys.modules, 'PyQt5.QtDBus', dbus)
        monkeypatch.setattr(PyQt5, 'QtDBus', dbus, raising=False)
        return screenshot, bus
    mode_coordinator._reset_for_tests()
    yield area, pending
    helpers.assert_not_called()
    mode_coordinator._reset_for_tests()


@pytest.mark.parametrize('next_mode', ['toggle', 'game', 'new_copy'])
def test_late_area_frame_cannot_reopen_a_stopped_selection(pending_capture, next_mode):
    area, pending = pending_capture
    def switch():
        if next_mode == 'toggle':
            ocr.run_screen_capture('copy')
        elif next_mode == 'new_copy':
            ocr.run_screen_capture('copy')
            mode_coordinator.request_mode('capture:copy', mock.Mock())
        else:
            mode_coordinator.request_mode('game', mock.Mock())
    grab, bus = pending(switch)
    ocr.run_screen_capture('copy')
    grab.assert_called_once()
    area.show.assert_not_called()
    assert not ocr._ACTIVE_OVERLAYS.get('copy')
    assert mode_coordinator.active_mode() == {'toggle': None, 'game': 'game', 'new_copy': 'capture:copy'}[next_mode]
    bus.asyncCall.assert_called_once_with(('org.freedesktop.portal.Desktop', bus.connect.call_args.args[1],
                                          'org.freedesktop.portal.Request', 'Close'))


@pytest.mark.parametrize('next_mode', ['toggle', 'game'])
def test_late_fullscreen_frame_cannot_cover_the_new_mode(pending_capture, monkeypatch, next_mode):
    _area, pending = pending_capture
    def switch():
        if next_mode == 'toggle':
            ocr.run_fullscreen_translate()
        else:
            mode_coordinator.request_mode('game', mock.Mock())
    grab, bus = pending(switch)
    controls = mock.Mock(side_effect=AssertionError('Stale fullscreen controls created'))
    monkeypatch.setattr(ocr, 'DropDownCombo', controls)
    monkeypatch.setattr(QtWidgets.QWidget, 'show', mock.Mock())
    ocr.run_fullscreen_translate()
    grab.assert_called_once()
    controls.assert_not_called()
    assert ocr._fullscreen_overlay_ref is None
    assert mode_coordinator.active_mode() == (None if next_mode == 'toggle' else 'game')
    bus.asyncCall.assert_called_once()


def test_an_unanswered_permission_request_closes_without_starting_another_capture(pending_capture, monkeypatch):
    area, pending = pending_capture
    monkeypatch.setattr(linux_capture, '_PORTAL_TIMEOUT_MS', 5)
    grab, bus = pending(lambda: None, answer=False)
    ocr.run_screen_capture('copy')
    grab.assert_called_once()
    bus.asyncCall.assert_called_once()
    area.show.assert_not_called()
    assert mode_coordinator.active_mode() is None


@pytest.mark.parametrize('direct_api', ['portal', 'screen'])
def test_independent_capture_survives_a_change_in_another_active_mode(pending_capture, direct_api):
    area, pending = pending_capture
    mode_coordinator.request_mode('game', mock.Mock())
    screenshot, bus = pending(lambda: mode_coordinator.request_mode('fullscreen', mock.Mock()))
    if direct_api == 'portal':
        assert linux_capture.capture_with_portal().endswith('synthetic.png')
    else:
        assert not linux_capture.grab_screen(area._active_screen).isNull()
    screenshot.assert_called_once()
    bus.asyncCall.assert_not_called()
    assert mode_coordinator.active_mode() == 'fullscreen'


@pytest.mark.parametrize('mode', ['copy', 'fullscreen'])
@pytest.mark.parametrize('failure', [ocr._CaptureRequestDeclined, RuntimeError])
def test_capture_called_on_a_worker_is_delivered_to_the_gui_thread(pending_capture, monkeypatch, mode, failure):
    _area, _pending = pending_capture
    app = QtWidgets.QApplication.instance()
    callback_threads = []
    def denied(*args):
        callback_threads.append(QtCore.QThread.currentThread())
        raise failure('synthetic')
    excepthook = mock.Mock()
    monkeypatch.setattr(sys, 'excepthook', excepthook)
    monkeypatch.setattr(ocr, 'get_or_show_overlay', denied)
    monkeypatch.setattr(ocr, 'FullScreenTranslateOverlay', denied)
    callback = (lambda: ocr.run_screen_capture('copy')) if mode == 'copy' else ocr.run_fullscreen_translate
    worker = threading.Thread(target=callback)
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert not callback_threads
    app.processEvents()
    assert callback_threads == [app.thread()]
    assert mode_coordinator.active_mode() is None
    excepthook.assert_not_called()


def test_linux_shortcut_received_on_socket_thread_handles_declined_ocr_without_external_retry(pending_capture, monkeypatch):
    import main
    app = QtWidgets.QApplication.instance()
    window = mock.Mock(config={'keep_visible_on_ocr': True})
    window.launch_copy.side_effect = lambda: main.DarkThemeApp.launch_copy(window)
    callback_threads = []
    def denied(mode):
        callback_threads.append(QtCore.QThread.currentThread())
        raise ocr._CaptureRequestDeclined('synthetic')
    monkeypatch.setattr(ocr, 'get_or_show_overlay', denied)
    dispatcher = main._HotkeyDispatcher()
    class Receiver(QtCore.QObject):
        @QtCore.pyqtSlot(object)
        def deliver(self, callback):
            main.DarkThemeApp._invoke_callback_safely(self, callback)
    receiver = Receiver()
    dispatcher.triggered.connect(receiver.deliver, QtCore.Qt.QueuedConnection)
    monkeypatch.setattr(main, 'hotkey_dispatcher', dispatcher)
    worker = threading.Thread(target=main.DarkThemeApp.handle_shortcut_command, args=(window, 'copy'))
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive() and not callback_threads
    app.processEvents()
    assert callback_threads == [app.thread()]
    window._start_external.assert_not_called()
    assert mode_coordinator.active_mode() is None
