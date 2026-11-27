"""Portal replies must not alias a remote file URI to a local image."""
import os
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
import PyQt5
from PyQt5 import QtCore, QtGui, QtWidgets

import linux_capture as capture
import platform_support
from test_desktop_ux import app


@pytest.mark.parametrize('uri', ['file://remote.example/tmp/shot.png',
                                  'file://user@localhost/tmp/shot.png',
                                  'file://localhost:123/tmp/shot.png',
                                  'file://[invalid/tmp/shot.png', 'file:relative.png'])
def test_nonlocal_or_malformed_file_uri_cannot_become_a_local_capture_path(uri):
    assert capture.uri_to_path(uri) == ''


@pytest.mark.parametrize('uri', ['file:/tmp/a%20b.png', 'FILE:///tmp/a%20b.png'])
def test_local_file_uri_syntax_preserves_the_decoded_path(uri):
    assert capture.uri_to_path(uri) == '/tmp/a b.png'


@pytest.mark.parametrize('authority', ['remote.example', 'user@localhost', 'localhost:123'])
def test_nonlocal_portal_reply_does_not_read_or_delete_the_local_namesake(app, tmp_path, monkeypatch, authority):
    physical = tmp_path / 'owned.png'
    image = QtGui.QImage(16, 16, QtGui.QImage.Format_ARGB32)
    image.fill(QtGui.QColor('blue'))
    assert image.save(str(physical))
    # Root-relative paths let this POSIX-URI contract be tested with a real
    # private PNG on Windows too; no user screenshot is read or captured.
    logical = physical.as_posix()[len(physical.drive):] if physical.drive else str(physical)
    if physical.drive:
        monkeypatch.chdir(physical.anchor)
    assert os.path.isfile(logical)
    assert not QtGui.QPixmap(logical).isNull()
    subscribed = {}
    bus = Mock()
    bus.isConnected.return_value = True
    bus.baseService.return_value = ':1.42'

    def connect(_service, path, _interface, _signal, slot):
        subscribed.update(path=path, slot=slot)
        return True

    bus.connect.side_effect = connect
    interface = Mock()
    interface.isValid.return_value = True

    def reply(*_args):
        subscribed['slot'](0, {'uri': 'file://' + authority + logical})
        return SimpleNamespace(isValid=lambda: True,
            value=lambda: SimpleNamespace(path=lambda: subscribed['path']))

    interface.call.side_effect = reply
    dbus = ModuleType('PyQt5.QtDBus')
    dbus.QDBusConnection = SimpleNamespace(sessionBus=lambda: bus)
    dbus.QDBusInterface = lambda *_args: interface
    dbus.QDBusReply = lambda value: value
    monkeypatch.setitem(sys.modules, 'PyQt5.QtDBus', dbus)
    monkeypatch.setattr(PyQt5, 'QtDBus', dbus, raising=False)
    monkeypatch.setattr(platform_support, 'IS_LINUX', True)
    monkeypatch.setattr(platform_support, 'desktop_environment', lambda: 'test')
    monkeypatch.setattr(capture, 'qt_platform_name', lambda: 'wayland')
    monkeypatch.setattr(capture, 'portal_available', lambda: True)
    monkeypatch.setattr(capture, 'capture_with_helper', Mock(side_effect=capture.CaptureError('no synthetic helper')))
    screen = SimpleNamespace(geometry=lambda: QtCore.QRect(0, 0, 16, 16))
    monkeypatch.setattr(QtWidgets.QApplication, 'screens', lambda: [screen])
    try:
        capture.grab_screen(screen)
        captured = True
    except capture.CaptureError:
        captured = False
    assert {'captured': captured, 'local_file_preserved': physical.exists()} == {
        'captured': False, 'local_file_preserved': True}


@pytest.mark.parametrize('uri,expected', [
    ('file:///tmp/plain.png', '/tmp/plain.png'),
    ('file://localhost/tmp/a%20b.png', '/tmp/a b.png'),
    ('file://LOCALHOST/tmp/name%23part.png', '/tmp/name#part.png'),
    ('file:///tmp/%E2%82%AC.png', '/tmp/€.png'),
    ('/tmp/plain.png', '/tmp/plain.png'),
    (r'C:\cache\image.png', r'C:\cache\image.png'),
    ('', ''),
])
def test_existing_local_and_plain_path_forms_keep_their_content(uri, expected):
    assert capture.uri_to_path(uri) == expected
