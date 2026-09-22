"""Monitor origins, portal lifecycle and failed external capture processes."""
import subprocess
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

import linux_capture as capture
import platform_support


@pytest.fixture(scope='module')
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.mark.parametrize('origins', [(-320, 0), (0, -200), (-320, -200), (320, 0)])
@pytest.mark.parametrize('density', [1, 2])
def test_portal_crop_uses_virtual_desktop_origin(app, monkeypatch, origins, density):
    geometries = [QtCore.QRect(0, 0, 320, 200), QtCore.QRect(*origins, 320, 200)]
    screens = [SimpleNamespace(geometry=lambda rect=rect: rect) for rect in geometries]
    monkeypatch.setattr(QtWidgets.QApplication, 'screens', lambda: screens)
    bounds = geometries[0].united(geometries[1])
    image = QtGui.QPixmap(bounds.width()*density, bounds.height()*density)
    image.fill(QtGui.QColor('black'))
    painter = QtGui.QPainter(image)
    for rect, color in zip(geometries, ('red', 'blue')):
        relative = rect.translated(-bounds.topLeft())
        painter.fillRect(QtCore.QRect(relative.x()*density, relative.y()*density,
                                     relative.width()*density, relative.height()*density), QtGui.QColor(color))
    painter.end()
    for screen, color in zip(screens, ('red', 'blue')):
        result = capture.crop_to_screen(image, screen)
        assert result.size() == QtCore.QSize(320*density, 200*density)
        assert result.devicePixelRatioF() == density
        assert result.toImage().pixelColor(10, 10) == QtGui.QColor(color)
        assert result.toImage().pixelColor(result.width()-10, result.height()-10) == QtGui.QColor(color)


def test_single_hidpi_portal_screen_keeps_selected_region_coordinates(app, monkeypatch):
    from ocr import crop_frozen_pixmap
    screen = SimpleNamespace(geometry=lambda: QtCore.QRect(0, 0, 320, 200))
    monkeypatch.setattr(QtWidgets.QApplication, 'screens', lambda: [screen])
    image = QtGui.QPixmap(640, 400)
    image.fill(QtGui.QColor('red'))
    painter = QtGui.QPainter(image)
    painter.fillRect(QtCore.QRect(200, 100, 80, 40), QtGui.QColor('green'))
    painter.end()
    screenshot = capture.crop_to_screen(image, screen)
    selected = crop_frozen_pixmap(screenshot, QtCore.QRect(100, 50, 40, 20))
    assert selected.size() == QtCore.QSize(80, 40)
    assert selected.toImage().pixelColor(10, 10) == QtGui.QColor('green')


def test_partial_screenshot_is_removed_when_helper_times_out(tmp_path, monkeypatch):
    path = tmp_path / 'screenshot.png'
    monkeypatch.setattr(capture, '_temp_png_path', lambda: str(path))
    monkeypatch.setattr(capture.shutil, 'which', lambda name: '/bin/grim' if name == 'grim' else None)
    def timeout(*args, **kwargs):
        path.write_bytes(b'partial private screenshot')
        raise subprocess.TimeoutExpired('grim', 15)
    monkeypatch.setattr(capture.subprocess, 'run', timeout)
    with pytest.raises(capture.CaptureError):
        capture.capture_with_helper()
    assert not path.exists()


@pytest.mark.parametrize('response', [0, 1, 2, None])
def test_portal_handles_immediate_response_and_closes_timed_out_request(app, tmp_path, monkeypatch, response):
    from PyQt5 import QtDBus
    path = tmp_path / 'shot.png'
    path.write_bytes(b'fixture')
    receiver = {}
    bus = mock.Mock()
    bus.isConnected.return_value = True
    bus.baseService.return_value = ':1.42'
    def connect(service, object_path, interface, signal, slot):
        receiver.update(slot=slot, path=object_path)
        return True
    bus.connect.side_effect = connect
    interface = mock.Mock()
    interface.isValid.return_value = True
    def screenshot(*args):
        if response is not None:
            receiver['slot'](response, {'uri': str(path)})
        return SimpleNamespace(isValid=lambda: True, value=lambda: QtDBus.QDBusObjectPath(receiver['path']))
    interface.call.side_effect = screenshot
    monkeypatch.setattr(QtDBus.QDBusConnection, 'sessionBus', lambda: bus)
    monkeypatch.setattr(QtDBus, 'QDBusInterface', lambda *args: interface)
    monkeypatch.setattr(QtDBus, 'QDBusReply', lambda value: value)
    loop = mock.Mock()
    monkeypatch.setattr(QtCore, 'QEventLoop', lambda: loop)
    if response == 0:
        assert capture.capture_with_portal() == str(path)
    else:
        with pytest.raises(capture.CaptureError):
            capture.capture_with_portal()
    if response is not None:
        loop.exec_.assert_not_called()
    else:
        assert bus.asyncCall.called  # Close the compositor's lingering request.
    bus.disconnect.assert_called()


def test_portal_cancellation_never_runs_a_capture_helper(app, monkeypatch):
    monkeypatch.setattr(platform_support, 'IS_LINUX', True)
    monkeypatch.setattr(capture, 'qt_platform_name', lambda: 'wayland')
    monkeypatch.setattr(capture, 'portal_available', lambda: True)
    monkeypatch.setattr(capture, 'capture_with_portal', mock.Mock(side_effect=capture.CaptureCancelled('cancelled')))
    helper = mock.Mock()
    monkeypatch.setattr(capture, 'capture_with_helper', helper)
    with pytest.raises(capture.CaptureCancelled):
        capture.grab_screen(mock.Mock())
    helper.assert_not_called()


def test_cancelled_wayland_background_capture_does_not_open_portal_twice(app, monkeypatch):
    import ocr
    monkeypatch.setattr(platform_support, 'IS_LINUX', True)
    monkeypatch.setattr(platform_support, 'is_wayland', lambda: True)
    grab = mock.Mock(return_value=QtGui.QPixmap())
    monkeypatch.setattr(ocr, 'grab_screen_pixmap', grab)
    overlay = mock.Mock(_active_screen=app.primaryScreen())
    overlay._freeze_required.return_value = True
    ocr.ScreenCaptureOverlay._capture_frozen_background(overlay, QtCore.QRect(0, 0, 320, 200))
    grab.assert_called_once()
    assert overlay._frozen_background is None


@pytest.mark.parametrize('version,expected', [(None, False), (0, False), (1, True), (2, True)])
def test_existing_dbus_object_without_screenshot_interface_is_not_available(monkeypatch, version, expected):
    from PyQt5 import QtDBus
    monkeypatch.setattr(platform_support, 'IS_LINUX', True)
    bus = mock.Mock()
    bus.isConnected.return_value = True
    interface = mock.Mock()
    interface.isValid.return_value = True
    interface.call.return_value = SimpleNamespace(isValid=lambda: version is not None, value=lambda: version)
    monkeypatch.setattr(QtDBus.QDBusConnection, 'sessionBus', lambda: bus)
    monkeypatch.setattr(QtDBus, 'QDBusInterface', lambda *args: interface)
    monkeypatch.setattr(QtDBus, 'QDBusReply', lambda value: value)
    assert capture.portal_available() is expected


def test_working_x11_capture_does_not_start_or_probe_portals(app, monkeypatch):
    monkeypatch.setattr(platform_support, 'IS_LINUX', True)
    monkeypatch.setattr(capture, 'qt_platform_name', lambda: 'xcb')
    portal = mock.Mock(side_effect=AssertionError('Unnecessary portal probe'))
    monkeypatch.setattr(capture, 'portal_available', portal)
    image = QtGui.QPixmap(20, 20)
    image.fill(QtGui.QColor('green'))
    screen = SimpleNamespace(grabWindow=lambda value: image)
    assert capture.grab_screen(screen) is image
    portal.assert_not_called()
