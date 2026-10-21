"""Proxy children anchor native menus to the physical window's current monitor."""
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import main
from test_desktop_ux import app, window
from ui_scaling import widget_global_point, widget_global_rect, widget_popup_geometry


@pytest.mark.parametrize('scale', [80, 100, 150])
@pytest.mark.parametrize('origin', [QtCore.QPoint(1920, 120), QtCore.QPoint(-1600, -100)])
def test_header_anchor_uses_viewport_coordinates_after_moving_between_monitors(window, app, scale, origin):
    window._ui_scale_controller.available_geometry.return_value = QtCore.QRect(origin-QtCore.QPoint(80, 80), QtCore.QSize(2560, 1400))
    window.set_ui_scale_percent(scale)
    window.move(origin)
    app.processEvents()
    controller = window._ui_scale_controller
    flag = window.flag_button
    local = flag.rect().bottomLeft()
    expected = controller.view.viewport().mapToGlobal(controller.map_widget_to_view(flag, local))
    # Reproduce Qt's stale mapToGlobal on an embedded child. The helper must
    # obtain desktop coordinates from the real viewport, never this origin.
    with mock.patch.object(flag, 'mapToGlobal', return_value=QtCore.QPoint(10, 10)):
        assert widget_global_point(flag, local) == expected
        rect = widget_global_rect(flag)
    assert rect.center().x() > origin.x()
    assert rect.width() >= flag.width() * scale / 80 - 2


@pytest.mark.parametrize('bounds', [QtCore.QRect(1920, 0, 1920, 1080), QtCore.QRect(-1600, -200, 1600, 900)])
def test_flag_menu_stays_with_its_anchor_on_the_selected_monitor(window, app, bounds):
    window._ui_scale_controller.available_geometry.return_value = bounds
    window.move(bounds.topLeft() + QtCore.QPoint(80, 80))
    app.processEvents()
    screen = SimpleNamespace(availableGeometry=lambda: bounds)
    with (mock.patch.object(QtWidgets.QApplication, 'screenAt', return_value=screen),
          mock.patch.object(main.QMenu, 'exec_', return_value=None) as popup):
        window.show_interface_language_menu()
    point = popup.call_args.args[0]
    assert bounds.contains(point)
    flag = widget_global_rect(window.flag_button)
    assert abs(point.x()-flag.left()) <= 4
    assert point.y() >= flag.bottom()


def test_menu_opens_above_a_low_anchor_and_clamps_to_negative_screen_origin(window):
    bounds = QtCore.QRect(-1200, 0, 1200, 800)
    anchor = QtCore.QRect(-35, 740, 30, 30)
    screen = SimpleNamespace(availableGeometry=lambda: bounds)
    with (mock.patch('ui_scaling.widget_global_rect', return_value=anchor),
          mock.patch.object(QtWidgets.QApplication, 'screenAt', return_value=screen)):
        geometry = widget_popup_geometry(window.flag_button, QtCore.QSize(220, 260))
    assert bounds.contains(geometry)
    assert geometry.bottom() < anchor.top()


def test_native_widgets_keep_their_ordinary_global_mapping(app):
    owner = QtWidgets.QWidget()
    child = QtWidgets.QPushButton(owner)
    owner.move(110, 130)
    child.move(20, 30)
    try:
        assert widget_global_point(child, QtCore.QPoint(3, 5)) == child.mapToGlobal(QtCore.QPoint(3, 5))
    finally:
        owner.deleteLater()


def test_native_language_menu_follows_window_on_each_connected_screen(window, app):
    from PyQt5.QtTest import QTest
    if app.platformName() == 'offscreen':
        pytest.skip('Physical monitor placement uses the native Qt backend')
    screens = app.screens()
    visited = []
    class Menu(QtWidgets.QMenu):
        def exec_(self, point):
            self.popup(point)
            QTest.qWait(40)
            screen = QtWidgets.QApplication.screenAt(point)
            assert screen is not None
            assert screen.availableGeometry().contains(self.frameGeometry())
            visited.append(screen.name())
            self.close()
    for screen in screens:
        bounds = screen.availableGeometry()
        window._ui_scale_controller.available_geometry.return_value = bounds
        window.set_ui_scale_percent(100)
        window.move(bounds.topLeft()+QtCore.QPoint(150, 100))
        QTest.qWait(60)
        with mock.patch.object(main, 'QMenu', Menu):
            window.show_interface_language_menu()
        assert visited[-1] == screen.name()
    assert len(visited) == len(screens)
