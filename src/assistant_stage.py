"""A small themed desk scene for the selected companion, drawn natively by Qt."""
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_art import DEFAULT_MASCOT, companion_art
from assistant_motion import PetMotion, paint_pet


class MascotStage(QtWidgets.QWidget):
    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self.owner = owner
        self.setObjectName('assistantMascotPreview')
        self.setMinimumHeight(110)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.mascot = DEFAULT_MASCOT
        self.appearance = 'animated'
        self.custom_image = ''
        self.motion = PetMotion(self.mascot)
        self.motion.set_activity(getattr(owner, '_companion_activity', 'idle'))
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.clock = QtCore.QElapsedTimer()
        owner.installEventFilter(self)

    def configure(self, mascot, appearance, custom_image):
        changed = self.mascot != mascot
        self.mascot, self.appearance, self.custom_image = mascot, appearance, custom_image
        self.motion.mascot = mascot
        self.motion.reactions = self.owner.config.get('desktop_assistant_reactions', True) is True
        if changed:
            self.motion.greet()
        self._sync_animation()
        self.update()

    def set_activity(self, activity):
        self.motion.set_activity(activity)
        self._sync_animation()
        self.update()

    def react(self, state):
        self.motion.play(state)
        self._sync_animation()
        self.update()

    def _animated(self):
        return self.appearance == 'animated' or (self.appearance != 'custom' and
            bool(self.motion.gesture) and self.motion.gesture_age < self.motion.gesture_duration)

    def _sync_animation(self):
        active = self.isVisible() and not self.owner.isMinimized() and self._animated()
        if active and not self.timer.isActive():
            self.clock.start()
            self.timer.start()
        elif not active:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_animation()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.owner and event.type() == QtCore.QEvent.WindowStateChange:
            self._sync_animation()
        return super().eventFilter(watched, event)

    def _tick(self):
        self.motion.advance(min(.2, self.clock.restart()/1000))
        self._sync_animation()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.react('jumping')
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        dark = self.owner.current_theme != 'Светлая'
        rect = QtCore.QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.setClipPath(path)
        wall = QtGui.QLinearGradient(0, 0, 0, self.height())
        wall.setColorAt(0, QtGui.QColor('#24202e' if dark else '#f8f5fc'))
        wall.setColorAt(1, QtGui.QColor('#31273c' if dark else '#eae0f3'))
        painter.fillRect(rect, wall)
        cx, ground = self.width()/2, self.height()-17
        glow = QtGui.QRadialGradient(QtCore.QPointF(cx, ground-45), 150)
        glow.setColorAt(0, QtGui.QColor(183, 146, 225, 36 if dark else 28))
        glow.setColorAt(1, QtCore.Qt.transparent)
        painter.fillRect(rect, glow)
        horizon = self.height()*.64
        painter.fillRect(QtCore.QRectF(0, horizon, self.width(), self.height()-horizon),
                         QtGui.QColor('#2c2435' if dark else '#e6dced'))
        painter.setPen(QtGui.QPen(QtGui.QColor('#44374e' if dark else '#d8cbe3'), 1))
        painter.drawLine(QtCore.QPointF(0, horizon), QtCore.QPointF(self.width(), horizon))
        # Low books and upright translation cards make a small desk, rather
        # than a detached portrait. All decoration follows the app's palette.
        painter.setPen(QtCore.Qt.NoPen)
        for dx, dy, width, color in ((115, 0, 66, '#72578c' if dark else '#c3acd6'),
                                     (121, -9, 58, '#a48abd' if dark else '#ded0e9')):
            painter.setBrush(QtGui.QColor(color))
            painter.drawRoundedRect(QtCore.QRectF(cx+dx, ground+dy, width, 8), 2, 2)
        for dx, dy, angle, text in ((-164, -39, -9, 'A'), (139, -49, 8, '文')):
            painter.save()
            painter.translate(cx+dx, ground+dy)
            painter.rotate(angle)
            painter.setPen(QtGui.QPen(QtGui.QColor('#655172' if dark else '#cdbbdb'), 1))
            painter.setBrush(QtGui.QColor('#3e314a' if dark else '#f9f5fc'))
            painter.drawRoundedRect(QtCore.QRectF(0, 0, 31, 38), 4, 4)
            painter.setPen(QtGui.QColor('#bba3d3' if dark else '#9670b4'))
            font = QtGui.QFont(self.font())
            font.setPixelSize(18)
            painter.setFont(font)
            painter.drawText(QtCore.QRectF(0, 0, 31, 38), QtCore.Qt.AlignCenter, text)
            painter.restore()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 25 if dark else 13))
        painter.drawEllipse(QtCore.QRectF(cx-85, ground+3, 170, 15))
        painter.setBrush(QtGui.QColor('#655074' if dark else '#c4afd5'))
        painter.drawRoundedRect(QtCore.QRectF(cx-70, ground-1, 140, 12), 5, 5)
        painter.setBrush(QtGui.QColor('#88709a' if dark else '#ddd0e8'))
        painter.drawEllipse(QtCore.QRectF(cx-70, ground-6, 140, 12))
        extent = min(112, self.height()-22)
        target = QtCore.QRectF(cx-extent/2, ground-extent*.923, extent, extent)
        if self._animated():
            action = self.motion.action()
            paint_pet(painter, target, self.mascot, action=action,
                      time=self.motion.time, state_time=self.motion.seconds(action))
        else:
            pixmap = companion_art(self.appearance, self.custom_image, self.mascot)
            size = QtCore.QSizeF(pixmap.size()).scaled(target.size(), QtCore.Qt.KeepAspectRatio)
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
            painter.drawPixmap(QtCore.QRectF(cx-size.width()/2, target.bottom()-size.height(),
                                            size.width(), size.height()), pixmap, QtCore.QRectF(pixmap.rect()))
        painter.setClipping(False)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor('#493b54' if dark else '#d4c5df'), 1))
        painter.drawRoundedRect(rect, 8, 8)
