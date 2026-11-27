"""Taskbar placement preserves old coordinates and never activates a window."""
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

from test_desktop_assistant import app, companion
import window_layer


@pytest.mark.parametrize('left,top', [(0, 0), (-1920, -200), (1920, 300)])
def test_saved_companion_can_use_taskbar_strip_and_restore_it(companion, left, top):
    full = QtCore.QRect(left, top, 1920, 1080)
    work = full.adjusted(0, 0, 0, -48)
    screen = SimpleNamespace(name=lambda: 'test-monitor', geometry=lambda: full,
                             availableGeometry=lambda: work)
    companion.owner.config['desktop_assistant_position'] = {
        'screen': 'test-monitor', 'space': 'screen', 'x': .7, 'y': 1.}
    with mock.patch.object(QtWidgets.QApplication, 'screens', return_value=[screen]), \
         mock.patch.object(QtWidgets.QApplication, 'screenAt', return_value=screen), \
         mock.patch.object(companion, 'refresh'):
        companion.restore_position()
        assert companion.anchor.geometry().bottom() == full.bottom()
        assert not work.contains(companion.anchor.geometry())
        assert full.contains(companion.anchor.geometry())
        expected = companion.anchor.pos()
        companion.save_position()
        assert companion.owner.config['desktop_assistant_position']['space'] == 'screen'
        companion.anchor.move(0, 0)
        companion.restore_position()
        assert companion.anchor.pos() == expected
        # Existing users keep their old work-area coordinates until they drag.
        del companion.owner.config['desktop_assistant_position']['space']
        companion.restore_position()
        assert companion.anchor.geometry().bottom() == work.bottom()


def test_dragging_companion_reaches_full_monitor_bottom(companion):
    full = QtCore.QRect(0, 0, 1920, 1080)
    screen = SimpleNamespace(geometry=lambda: full)
    anchor = companion.anchor
    anchor.move(300, 500)
    anchor._press = QtCore.QPoint(320, 520)
    anchor._origin = anchor.pos()
    event = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(20, 20),
        QtCore.QPointF(320, 1079), QtCore.Qt.NoButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
    with mock.patch.object(QtWidgets.QApplication, 'screenAt', return_value=screen), \
         mock.patch.object(anchor, '_sync_window_layer') as sync:
        anchor.mouseMoveEvent(event)
    assert anchor.geometry().bottom() == full.bottom()
    sync.assert_called_once()


def test_export_import_keeps_full_monitor_position_marker():
    import main
    from settings_window import settings_export_payload, validated_import_settings
    position = dict(screen='second-monitor', space='screen', x=.9, y=1.)
    result = validated_import_settings(settings_export_payload(
        {'desktop_assistant_position': position}), main.DEFAULT_CONFIG)
    assert result['desktop_assistant_position'] == position


def test_layer_reasserts_only_when_overlapping_taskbar_is_above():
    api = mock.Mock()
    with mock.patch.object(window_layer, '_windows_api', return_value=(api, mock.Mock())), \
         mock.patch.object(window_layer, 'native_topmost', return_value=True), \
         mock.patch.object(window_layer, '_taskbar_above', return_value=True) as taskbar:
        assert window_layer.synchronize_topmost(123, True, above_taskbar=True)
        taskbar.assert_called_once_with(123)
    api.SetWindowPos.assert_called_once_with(123, -1, 0, 0, 0, 0, 0x0213)


@pytest.mark.parametrize('enabled,overlap', [(True, False), (False, True)])
def test_layer_does_not_reorder_when_not_needed(enabled, overlap):
    api = mock.Mock()
    with mock.patch.object(window_layer, '_windows_api', return_value=(api, mock.Mock())), \
         mock.patch.object(window_layer, 'native_topmost', return_value=enabled), \
         mock.patch.object(window_layer, '_taskbar_above', return_value=False) as taskbar:
        assert window_layer.synchronize_topmost(123, enabled, above_taskbar=overlap)
        taskbar.assert_not_called()
    api.SetWindowPos.assert_not_called()


@pytest.mark.parametrize('name,bounds,expected', [
    ('Shell_TrayWnd', (0, 1032, 1920, 1080), True),
    ('Shell_SecondaryTrayWnd', (0, 1032, 1920, 1080), True),
    ('Shell_TrayWnd', (1920, 1032, 3840, 1080), False),
    ('UnrelatedTopmostApp', (0, 1032, 1920, 1080), False),
])
def test_taskbar_detection_uses_native_overlap_and_shell_class(name, bounds, expected):
    api = mock.Mock()
    api.GetWindow.side_effect = [222, 0]
    api.IsWindowVisible.return_value = True
    def rect(handle, pointer):
        values = (50, 1000, 150, 1080) if handle == 123 else bounds
        pointer._obj.left, pointer._obj.top, pointer._obj.right, pointer._obj.bottom = values
        return True
    api.GetWindowRect.side_effect = rect
    def class_name(handle, buffer, length):
        buffer.value = name
        return len(name)
    api.GetClassNameW.side_effect = class_name
    with mock.patch.object(window_layer, '_windows_api', return_value=(api, mock.Mock())):
        assert window_layer._taskbar_above(123) is expected
