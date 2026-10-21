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
SLEEP_DURATIONS = (360, 280, 280, 360)
EXPRESSIONS = ('neutral', 'happy', 'curious', 'thinking', 'surprised', 'sad', 'sleepy', 'proud')
POSES = {
    'neutral': ('idle', 0), 'happy': ('waving', 1),
    'curious': ('waiting', 2), 'thinking': ('review', 1),
    'surprised': ('jumping', 1), 'sad': ('failed', 3),
    'sleepy': ('sleep', 1), 'blink': ('idle', 2),
    'sleep': ('sleep', 0), 'proud': ('review', 5),
    'success': ('jumping', 2), 'work': ('running', 0),
    'walk': ('running-right', 0),
}


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
        self._sleep = None
        self.expressions = QtGui.QPixmap(art_path(f'{self.mascot}/expressions.png'))
        if self.expressions.size() != QtCore.QSize(1536, 208) or not self.expressions.hasAlphaChannel():
            raise ValueError(f'Invalid expression strip for {self.mascot}')

    @property
    def pixmap(self):
        # Character-menu portraits need only the small expression strip.
        if self._pixmap is None:
            pixmap = QtGui.QPixmap(art_path(f'{self.mascot}/pets-v2.png'))
            if pixmap.size() != ATLAS or not pixmap.hasAlphaChannel():
                raise ValueError(f'Invalid Pets v2 atlas for {self.mascot}')
            self._pixmap = pixmap
        return self._pixmap

    @property
    def sleep(self):
        if self._sleep is None:
            pixmap = QtGui.QPixmap(art_path(f'{self.mascot}/sleep.png'))
            if pixmap.size() != QtCore.QSize(768, 208) or not pixmap.hasAlphaChannel():
                raise ValueError(f'Invalid sleep strip for {self.mascot}')
            self._sleep = pixmap
        return self._sleep

    def source(self, state='idle', seconds=0., *, facing=1, gaze=None, index=None):
        if gaze is not None:
            direction = look_index(gaze)
            return self.pixmap, QtCore.QRect(direction % 8 * 192,
                                             (9 + direction // 8) * 208, 192, 208)
        if state == 'walk':
            state = 'running-right' if facing >= 0 else 'running-left'
        if state == 'sleep':
            count, row, durations, pixmap = 4, 0, SLEEP_DURATIONS, self.sleep
        else:
            row, durations = ROWS.get(state, ROWS['idle'])
            count, pixmap = len(durations), self.pixmap
        column = frame_index(durations, seconds) if index is None else int(index) % count
        return pixmap, QtCore.QRect(column * 192, row * 208, 192, 208)

    def pose(self, expression='neutral', special=''):
        if special in EXPRESSIONS:
            return self.expressions.copy(EXPRESSIONS.index(special) * 192, 0, 192, 208)
        if not special and expression in EXPRESSIONS:
            return self.expressions.copy(EXPRESSIONS.index(expression) * 192, 0, 192, 208)
        state, index = POSES.get(special or expression, POSES['neutral'])
        pixmap, rect = self.source(state, index=index)
        return pixmap.copy(rect)


@lru_cache(maxsize=6)
def atlas(mascot):
    return SpriteAtlas(mascot_id(mascot))


def paint_sprite(painter, rect, mascot, state='idle', seconds=0., *, facing=1, gaze=None):
    artwork = atlas(mascot)
    pixmap, source = artwork.source(state, seconds, facing=facing, gaze=gaze)
    size = QtCore.QSizeF(CELL).scaled(rect.size(), QtCore.Qt.KeepAspectRatio)
    target = QtCore.QRectF(rect.center().x() - size.width() / 2,
                         rect.bottom() - size.height(), size.width(), size.height())
    painter.save()
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    painter.drawPixmap(target, pixmap, QtCore.QRectF(source))
    painter.restore()
