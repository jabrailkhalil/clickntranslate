"""Gaze is consistent across characters without replaying a resized body."""
import pytest
from unittest import mock
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_art import MASCOTS
from assistant_sprites import CELL, look_index
from assistant_motion import paint_pet
from button_styles import button_palette
from classic_style import classic_palette
from desktop_assistant import AssistantMenu
from test_desktop_assistant import app, companion


def render(mascot, gaze=None):
    image = QtGui.QImage(CELL, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    paint_pet(painter, QtCore.QRectF(image.rect()), mascot, gaze=gaze, time=2.)
    painter.end()
    return image


def bounds(image):
    return QtGui.QRegion(QtGui.QPixmap.fromImage(image).mask()).boundingRect()


@pytest.mark.parametrize('mascot', MASCOTS)
def test_all_directions_keep_resting_height_and_feet(mascot, tmp_path):
    resting = bounds(render(mascot))
    frames = []
    for direction in range(16):
        angle = direction*22.5
        image = render(mascot, angle)
        box = bounds(image)
        assert abs(box.height() - resting.height()) <= 2, (mascot, angle, box, resting)
        assert abs(box.bottom() - resting.bottom()) <= 1, (mascot, angle, box, resting)
        assert abs(box.center().x() - resting.center().x()) <= 1
        assert image.pixelColor(0, 0).alpha() == 0
        frames.append(image)
    assert render(mascot, 90) != render(mascot, 270)
    sheet = QtGui.QImage(CELL.width()*len(frames), CELL.height(), QtGui.QImage.Format_ARGB32)
    sheet.fill(QtGui.QColor('#111111'))
    painter = QtGui.QPainter(sheet)
    for index, frame in enumerate(frames):
        painter.drawImage(index*CELL.width(), 0, frame)
    painter.end()
    assert sheet.save(str(tmp_path / f'{mascot}-directions.png'))


@pytest.mark.parametrize('mascot', MASCOTS)
@pytest.mark.parametrize('appearance', ('animated', 'portrait'))
def test_hover_follows_cursor_for_every_builtin_appearance(companion, mascot, appearance):
    companion.owner.config.update(desktop_assistant_mascot=mascot, desktop_assistant_appearance=appearance)
    companion.refresh()
    anchor = companion.anchor
    anchor._hover = True
    right = QtCore.QPointF(anchor.width()-2, anchor.height()*.44)
    left = QtCore.QPointF(2, anchor.height()*.44)
    event = lambda point: QtGui.QMouseEvent(QtCore.QEvent.MouseMove, point, QtCore.Qt.NoButton,
                                          QtCore.Qt.NoButton, QtCore.Qt.NoModifier)
    QtWidgets.QApplication.sendEvent(anchor, event(right))
    assert look_index(anchor._gaze_angle) == 4
    first = anchor.grab().toImage()
    QtWidgets.QApplication.sendEvent(anchor, event(left))
    assert look_index(anchor._gaze_angle) == 12
    assert anchor.grab().toImage() != first


def test_pointer_enter_updates_gaze_without_polling_or_repainting_the_same_direction(companion):
    anchor = companion.anchor
    point = QtCore.QPoint(anchor.width()-2, round(anchor.height()*.44))
    with mock.patch.object(QtGui.QCursor, 'pos', return_value=anchor.mapToGlobal(point)):
        QtWidgets.QApplication.sendEvent(anchor, QtCore.QEvent(QtCore.QEvent.Enter))
    assert anchor._hover and look_index(anchor._gaze_angle) == 4
    with mock.patch.object(anchor, 'update') as update:
        anchor._look_at(point+QtCore.QPoint(0, 1))
    update.assert_not_called()


@pytest.mark.parametrize('mascot', MASCOTS)
def test_opening_menu_points_at_its_position_even_after_pointer_leaves(companion, mascot):
    companion.owner.config.update(desktop_assistant_mascot=mascot, desktop_assistant_appearance='animated')
    companion.refresh()
    companion.anchor._hover = True
    companion.anchor._gaze_angle = 90.
    companion.toggle_menu()
    assert companion.menu.isVisible()
    assert companion.anchor.motion.action() == 'idle'
    menu_angle = companion.anchor._menu_gaze_angle
    assert menu_angle is not None
    first = companion.anchor.grab().toImage()
    QtWidgets.QApplication.sendEvent(companion.anchor, QtCore.QEvent(QtCore.QEvent.Leave))
    assert companion.anchor._menu_gaze_angle == menu_angle
    assert companion.anchor.grab().toImage() == first
    # This signal also follows a menu repositioned above/alongside an edge.
    companion.menu.move(companion.anchor.x()-companion.menu.width()-8, companion.anchor.y())
    companion.menu.placement_changed.emit()
    assert 220 < companion.anchor._menu_gaze_angle < 320
    companion.menu.hide()
    assert companion.anchor._menu_gaze_angle is None


@pytest.mark.parametrize('locale', ('ru', 'en', 'de', 'fr', 'ar', 'zh', 'es', 'pt', 'it', 'tr', 'hi', 'id'))
@pytest.mark.parametrize('dark', (True, False))
@pytest.mark.parametrize('factor', (1., 1.37, 2.))
def test_menu_uses_the_application_header_and_joined_action_grid(app, locale, dark, factor, tmp_path):
    menu = AssistantMenu(locale, dark, factor)
    try:
        available = QtCore.QRect(0, 0, 1280, 1000)
        anchor = QtCore.QRect(480, 820, 84, 84)
        menu.open_beside(anchor, available)
        # Re-measure an existing menu, including the optional activity row.
        menu.set_activity('busy')
        app.processEvents()
        assert available.contains(menu.geometry())
        assert classic_palette(dark)['header'] in menu.header.styleSheet()
        assert button_palette(dark)['surface'] in menu.buttons['open'].styleSheet()
        assert menu.action_surface.layout().verticalSpacing() == 1
        assert menu.action_surface.layout().horizontalSpacing() == 0
        assert menu.rect().contains(menu.header.geometry())
        assert menu.content.rect().contains(menu.scroll.geometry())
        assert not menu.scroll.geometry().intersects(menu.footer.geometry())
        assert menu.scroll.verticalScrollBar().maximum() == 0
        for key, button in menu.buttons.items():
            if key not in ('settings', 'hide'):
                rect = QtCore.QRect(button.mapTo(menu.scroll.viewport(), QtCore.QPoint()), button.size())
                assert menu.scroll.viewport().rect().contains(rect), (locale, dark, key, rect)
        for key in ('settings', 'hide'):
            button = menu.buttons[key]
            assert menu.rect().contains(QtCore.QRect(button.mapTo(menu, QtCore.QPoint()), button.size()))
        assert menu.grab().save(str(tmp_path / f'menu-{locale}-{dark}.png'))
    finally:
        menu.close()
        menu.deleteLater()
