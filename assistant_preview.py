"""Tiny in-window companion. No desktop overlay, capture, model or worker.

Only a 16px sprite is animated, at most 12.5 times/s while the application is
active and its main page visible. Hidden/minimized/inactive pages have no
running timer. GIFs are decoded once, not in paintEvent or in a timer callback.
"""
from functools import lru_cache
from pathlib import Path
import sys

from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_text import assistant_text


@lru_cache(maxsize=1)
def preview_frames():
    """One bounded cache: ten 32px frames and their mirrored versions (~70KiB).

    Keep the source's stable union bounds so feet don't jump between frames.
    Store at 2x the logical size for crisp high-DPI/zoomed rendering.
    """
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    reader = QtGui.QImageReader(str(root / 'icons/desktop-assistant/kirby.gif'))
    size = reader.size()
    if size.isEmpty() or max(size.width(), size.height()) > 512:
        return (), ()
    images, bounds = [], QtCore.QRect()
    while reader.canRead() and len(images) < 64:
        image = reader.read()
        if image.isNull():
            break
        images.append(image)
        pixmap = QtGui.QPixmap.fromImage(image)
        bounds = bounds.united(QtGui.QRegion(pixmap.mask()).boundingRect())
    if bounds.isEmpty():
        return (), ()
    forward = tuple(QtGui.QPixmap.fromImage(image.copy(bounds).scaled(
        32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)) for image in images)
    reverse = tuple(frame.transformed(QtGui.QTransform().scale(-1, 1)) for frame in forward)
    return forward, reverse


class _PreviewButton(QtWidgets.QAbstractButton):
    def __init__(self, rail):
        super().__init__(rail)
        self.rail = rail
        self.setFixedSize(28, 24)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def event(self, event):
        if (event.type() == QtCore.QEvent.ParentChange and hasattr(self, 'rail')
                and hasattr(self.rail, 'timer')):
            self.rail._sync_animation()
        return super().event(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        frames = self.rail.frames[0 if self.rail.direction > 0 else 1]
        if frames:
            pixmap = frames[self.rail.frame_index % len(frames)]
            size = pixmap.size().scaled(22, 22, QtCore.Qt.KeepAspectRatio)
            target = QtCore.QRect((self.width() - size.width()) // 2,
                                  self.height() - size.height(), size.width(), size.height())
            painter.drawPixmap(target, pixmap)
        else:
            painter.setPen(self.palette().text().color())
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, '✦')
        if self.hasFocus() or self.underMouse():
            painter.setPen(QtGui.QColor('#9a7fc1'))
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 3, 3)

    def enterEvent(self, event):
        self.rail._hovered = True
        self.rail._sync_animation()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.rail._hovered = False
        self.rail._sync_animation()
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.rail._sync_animation()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.rail._sync_animation()


class AssistantPreview(QtWidgets.QWidget):
    settings_requested = QtCore.pyqtSignal()
    INTERVAL_MS = 80

    def __init__(self, activity_owner, language='en', parent=None):
        super().__init__(parent)
        self.setObjectName('assistantPreviewRail')
        self.setFixedHeight(26)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._owner = activity_owner
        self._hovered = False
        self._application_active = QtWidgets.QApplication.applicationState() == QtCore.Qt.ApplicationActive
        self.frames = ((), ())  # Lazy: minimized startup does not even decode the GIF.
        self.frame_index = 0
        self.direction = 1
        self._x = 0.
        self._frame_ms = 0
        self.button = _PreviewButton(self)
        hint = assistant_text(language, 'preview_hint')
        self.button.setAccessibleName(hint)
        self.button.setToolTip(hint)
        self.button.clicked.connect(self.settings_requested)
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.CoarseTimer)
        self.timer.setInterval(self.INTERVAL_MS)
        self.timer.timeout.connect(self._tick)
        self._clock = QtCore.QElapsedTimer()
        activity_owner.installEventFilter(self)
        QtWidgets.QApplication.instance().applicationStateChanged.connect(self._application_state_changed)

    def _application_state_changed(self, state):
        self._application_active = state == QtCore.Qt.ApplicationActive
        self._sync_animation()

    def _sync_animation(self):
        active = (self.isVisible() and self.button.parentWidget() is self
                  and not self._owner.isMinimized()
                  and self._application_active and not self._hovered and not self.button.hasFocus()
                  and self.width() > self.button.width() and bool(self.frames[0]))
        if active and not self.timer.isActive():
            self._clock.start()
            self.timer.start()
        elif not active:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.frames[0]:
            self.frames = preview_frames()
        self._sync_animation()

    def hideEvent(self, event):
        self.timer.stop()
        self._hovered = False
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched is self._owner and event.type() in (
                QtCore.QEvent.WindowStateChange, QtCore.QEvent.Show, QtCore.QEvent.Hide):
            self._sync_animation()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        self._x = min(self._x, max(0, self.width() - self.button.width()))
        self.button.move(round(self._x), 0)
        self._sync_animation()
        super().resizeEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        y = self.height() - 7
        line = QtCore.QRectF(10, y, max(0, self.width() - 20), 2)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(154, 127, 193, 90))
        painter.drawRoundedRect(line, 1, 1)

    def _tick(self):
        # A busy UI never catches up by running a burst of animation frames.
        elapsed = max(0, min(self._clock.restart(), 200))
        self._advance(elapsed)

    def _advance(self, elapsed):
        maximum = max(0, self.width() - self.button.width())
        self._x += self.direction * 20 * elapsed / 1000
        if self._x >= maximum:
            self._x, self.direction = float(maximum), -1
        elif self._x <= 0:
            self._x, self.direction = 0., 1
        self._frame_ms += elapsed
        if self.frames[0] and self._frame_ms >= 110:
            step, self._frame_ms = divmod(self._frame_ms, 110)
            self.frame_index = (self.frame_index + step) % len(self.frames[0])
        self.button.move(round(self._x), 0)
        self.button.update()  # Invalidate only the 22x18 child, not the whole page.
