"""Qt flags alone do not prove that the native window is still topmost."""
import sys
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest
from desktop_assistant import AssistantAnchor
import window_layer


def test_native_sync_does_not_reorder_an_already_correct_window():
    api = mock.Mock()
    with mock.patch.object(window_layer, '_windows_api', return_value=(api, mock.Mock())), \
         mock.patch.object(window_layer, 'native_topmost', return_value=True):
        assert window_layer.synchronize_topmost(123, True)
    api.SetWindowPos.assert_not_called()


def test_native_sync_preserves_geometry_owner_and_focus():
    api = mock.Mock()
    with mock.patch.object(window_layer, '_windows_api', return_value=(api, mock.Mock())), \
         mock.patch.object(window_layer, 'native_topmost', side_effect=[False, True]):
        assert window_layer.synchronize_topmost(123, True)
    api.SetWindowPos.assert_called_once_with(123, -1, 0, 0, 0, 0, 0x0213)


def test_hidden_companion_stops_layer_maintenance():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    anchor = AssistantAnchor()
    try:
        anchor._layer_guard.start()
        anchor._sync_window_layer()
        assert not anchor._layer_guard.isActive()
        assert not anchor.isVisible()
    finally:
        anchor.close()
        anchor.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_windows_native_companion_recovers_lost_topmost_without_focus():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if sys.platform != 'win32' or app.platformName().split(':')[0] != 'windows':
        pytest.skip('requires native Windows Qt windows')
    import ctypes
    api, _ = window_layer._windows_api()
    api.GetForegroundWindow.restype = ctypes.c_void_p
    foreground = api.GetForegroundWindow()
    anchor = AssistantAnchor()
    anchor.move(-32000, -32000)  # native test surface stays outside the user's monitors
    try:
        anchor.show()
        app.processEvents()
        hwnd = int(anchor.winId())
        assert window_layer.native_topmost(hwnd) is True
        anchor._layer_guard.setInterval(50)
        # Reproduce reported drift: native state is lost while Qt keeps its flag.
        assert api.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0213)
        assert window_layer.native_topmost(hwnd) is False
        assert anchor.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
        QTest.qWait(150)
        assert window_layer.native_topmost(hwnd) is True
        assert api.GetForegroundWindow() == foreground
        anchor.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, False)
        anchor.show()
        app.processEvents()
        anchor._sync_window_layer()
        assert window_layer.native_topmost(int(anchor.winId())) is False
        assert not anchor._layer_guard.isActive()
        anchor.hide()
        QTest.qWait(100)
        assert not anchor.isVisible()
        assert not anchor._layer_guard.isActive()
    finally:
        anchor.close()
        anchor.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
