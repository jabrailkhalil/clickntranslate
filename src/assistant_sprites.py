"""Pets v2 artwork: whole frames with one shared cell viewport.

Paint calls select rectangles from cached PNGs. They never rebuild anatomy,
warp faces, interpolate pixels or read files.
"""
from bisect import bisect_right
from functools import lru_cache
from itertools import accumulate
import math

from PyQt5 import QtCore, QtGui
from assistant_art import art_path, mascot_id

CELL = QtCore.QSize(192, 208)
ATLAS = QtCore.QSize(1536, 2288)
ROWS = {
    'idle': (0, (280, 110, 110, 140, 140, 320)),
    'running-right': (1, (120,) * 7 + (220,)),
    'running-left': (2, (120,) * 7 + (220,)),
    'waving': (3, (140, 140, 140, 280)),
    'jumping': (4, (140, 140, 140, 140, 280)),
    'failed': (5, (140,) * 7 + (240,)),
    'waiting': (6, (150,) * 5 + (260,)),
    'running': (7, (120,) * 5 + (220,)),
    'review': (8, (150,) * 5 + (280,)),
}
STATIONARY_STATES = ('idle', 'waving', 'jumping', 'running', 'waiting', 'review', 'failed')
POSES = {
    'neutral': ('idle', 0), 'happy': ('waving', 1),
    'curious': ('waiting', 2), 'thinking': ('running', 1),
    'surprised': ('jumping', 1), 'sad': ('failed', 3),
    'sleepy': ('idle', 3), 'blink': ('idle', 3),
    'sleep': ('idle', 3), 'proud': ('review', 5),
    'success': ('jumping', 2), 'work': ('running', 0),
    'walk': ('idle', 0),
}
POSES.update({state: (state, 0) for state in STATIONARY_STATES})


def frame_index(durations, seconds):
    ends = tuple(accumulate(durations))
    elapsed = max(0., float(seconds)) * 1000 % ends[-1]
    return min(len(ends) - 1, bisect_right(ends, elapsed))


def look_index(angle):
    """Clockwise screen coordinates: zero up, 90 right, 180 down."""
    return int(math.floor((float(angle) % 360 + 11.25) / 22.5)) % 16


class SpriteAtlas:
    def __init__(self, mascot):
        self.mascot = mascot_id(mascot)
        self._pixmap = None
        self._thumbnail = None

    @property
    def thumbnail(self):
        if self._thumbnail is None:
            reader = QtGui.QImageReader(art_path(f'{self.mascot}/pets-v2.png'))
            if reader.size() != ATLAS:
                raise ValueError(f'Invalid Pets v2 atlas for {self.mascot}')
            reader.setScaledSize(ATLAS / 4)
            pixmap = QtGui.QPixmap.fromImage(reader.read())
            if pixmap.size() != ATLAS / 4 or not pixmap.hasAlphaChannel():
                raise ValueError(f'Invalid Pets thumbnail for {self.mascot}')
            self._thumbnail = pixmap
        return self._thumbnail

    @property
    def pixmap(self):
        if self._pixmap is None:
            pixmap = QtGui.QPixmap(art_path(f'{self.mascot}/pets-v2.png'))
            if pixmap.size() != ATLAS or not pixmap.hasAlphaChannel():
                raise ValueError(f'Invalid Pets v2 atlas for {self.mascot}')
            self._pixmap = pixmap
        return self._pixmap

    def source(self, state='idle', seconds=0., *, facing=1, gaze=None, index=None, compact=False):
        pixmap = self.thumbnail if compact else self.pixmap
        if gaze is not None:
            direction = look_index(gaze)
            rect = QtCore.QRect(direction % 8 * 192, (9 + direction // 8) * 208, 192, 208)
        else:
            if state not in STATIONARY_STATES:
                state = 'idle'
            row, durations = ROWS[state]
            column = frame_index(durations, seconds) if index is None else int(index) % len(durations)
            rect = QtCore.QRect(column * 192, row * 208, 192, 208)
        if compact:
            rect = QtCore.QRect(rect.x()//4, rect.y()//4, 48, 52)
        return pixmap, rect

    def pose(self, expression='neutral', special=''):
        state, index = POSES.get(special or expression, POSES['neutral'])
        row, durations = ROWS[state]
        rect = QtCore.QRect(index % len(durations) * 192, row * 208, 192, 208)
        if self._pixmap is not None:
            return self._pixmap.copy(rect)
        # Picker thumbnails retain only one cell, not six decoded full atlases.
        reader = QtGui.QImageReader(art_path(f'{self.mascot}/pets-v2.png'))
        if reader.size() != ATLAS:
            raise ValueError(f'Invalid Pets v2 atlas for {self.mascot}')
        reader.setClipRect(rect)
        result = QtGui.QPixmap.fromImage(reader.read())
        if result.size() != CELL or not result.hasAlphaChannel():
            raise ValueError(f'Invalid Pets pose for {self.mascot}')
        return result


@lru_cache(maxsize=6)
def atlas(mascot):
    return SpriteAtlas(mascot_id(mascot))


def paint_sprite(painter, rect, mascot, state='idle', seconds=0., *, facing=1, gaze=None):
    artwork = atlas(mascot)
    pixmap, source = artwork.source(state, seconds, facing=facing, gaze=gaze,
                                    compact=max(rect.width(), rect.height()) <= 32)
    size = QtCore.QSizeF(CELL).scaled(rect.size(), QtCore.Qt.KeepAspectRatio)
    target = QtCore.QRectF(rect.center().x() - size.width() / 2,
                         rect.bottom() - size.height(), size.width(), size.height())
    painter.save()
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    painter.drawPixmap(target, pixmap, QtCore.QRectF(source))
    painter.restore()
