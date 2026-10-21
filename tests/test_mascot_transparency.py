"""Transparent animation frames replace old alpha instead of leaving trails."""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_art import MASCOTS
from assistant_sprites import ROWS, STATIONARY_STATES
from desktop_assistant import AssistantAnchor
from test_desktop_ux import app


def render(anchor, image):
    painter = QtGui.QPainter(image)
    anchor.render(painter, flags=QtWidgets.QWidget.DrawChildren)
    painter.end()


@pytest.mark.parametrize('mascot', MASCOTS)
def test_each_animation_frame_clears_previous_pose_alpha(app, mascot):
    anchor = AssistantAnchor()
    anchor.setFixedSize(144, 144)
    anchor.set_mascot(mascot)
    anchor.appearance = 'animated'
    anchor.show()
    anchor._animation.stop()
    surface = QtGui.QImage(144, 144, QtGui.QImage.Format_ARGB32_Premultiplied)
    surface.fill(QtGui.QColor('#c02a53'))
    try:
        for state in STATIONARY_STATES:
            elapsed = 0
            for duration in ROWS[state][1]:
                seconds = (elapsed+duration/2)/1000
                elapsed += duration
                anchor.motion.play(state)
                anchor.motion.gesture_age = seconds
                render(anchor, surface)
                fresh = QtGui.QImage(surface.size(), surface.format())
                fresh.fill(QtCore.Qt.transparent)
                render(anchor, fresh)
                assert surface == fresh, (mascot, state, seconds)
                assert surface.pixelColor(0, 0).alpha() == 0
        anchor.motion.gesture = None
        anchor.motion.set_activity('idle')
        anchor._hover = True
        for direction in range(16):
            anchor._gaze_angle = direction*22.5
            render(anchor, surface)
            fresh.fill(QtCore.Qt.transparent)
            render(anchor, fresh)
            assert surface == fresh, (mascot, 'gaze', direction)
    finally:
        anchor.close()
        anchor.deleteLater()
