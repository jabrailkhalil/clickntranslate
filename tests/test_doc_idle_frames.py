"""Doc never displays the malformed left ankle from the rejected idle cells."""
from itertools import accumulate

import pytest
from PyQt5 import QtCore, QtGui

from assistant_art import MASCOTS, art_path
from assistant_sprites import CELL, ROWS, STATIONARY_STATES, SpriteAtlas, paint_sprite
from test_desktop_ux import app


def render(seconds, size):
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    paint_sprite(painter, QtCore.QRectF(0, 0, size, size), 'orbit', 'idle', seconds)
    painter.end()
    return image


@pytest.mark.parametrize('size', [28, 96, 144])
def test_doc_idle_uses_only_visually_accepted_whole_frames_at_every_scale(app, size):
    # Cell 1 is the clean raised breathing pose; cell 0 is the clean rest pose.
    # Cells 2–5 have a white extension from the body to the left foot.
    resting, raised = render(.14, size), render(.335, size)
    assert resting != raised  # Keep genuine motion rather than a still image.
    starts = (0, *accumulate(ROWS['idle'][1]))
    for slot in range(6):
        seconds = (starts[slot] + ROWS['idle'][1][slot] / 2) / 1000
        assert render(seconds, size) == (raised if slot == 1 else resting)
        assert render(seconds + 1.1, size) == render(seconds, size)


@pytest.mark.parametrize('expression', ['blink', 'sleepy', 'sleep'])
def test_doc_legacy_idle_poses_also_use_the_clean_frame(app, expression):
    atlas = SpriteAtlas('orbit')
    expected = QtGui.QPixmap(art_path('orbit/pets-v2.png')).copy(QtCore.QRect(QtCore.QPoint(), CELL))
    assert atlas.pose(expression).toImage() == expected.toImage()


@pytest.mark.parametrize('mascot', MASCOTS)
def test_other_characters_and_other_doc_reactions_retain_their_native_frames(app, mascot):
    atlas = SpriteAtlas(mascot)
    for state in STATIONARY_STATES:
        if mascot == 'orbit' and state == 'idle':
            continue
        row, durations = ROWS[state]
        for column in range(len(durations)):
            _, rect = atlas.source(state, index=column)
            assert rect == QtCore.QRect(column*192, row*208, 192, 208)
    for direction in range(16):
        _, rect = atlas.source(gaze=direction*22.5)
        assert rect == QtCore.QRect(direction % 8*192, (9+direction//8)*208, 192, 208)
