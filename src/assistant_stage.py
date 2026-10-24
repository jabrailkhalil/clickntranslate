"""A small themed desk scene for the selected companion, drawn natively by Qt."""
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_art import MASCOTS, DEFAULT_MASCOT, companion_art
from assistant_text import assistant_text
from button_styles import button_qss
from ui_scaling import ScaleArrowButton
from assistant_motion import PetMotion, paint_pet


class MascotStage(QtWidgets.QWidget):
    step_requested = QtCore.pyqtSignal(int)
    TRANSITION_MS = 260

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
        self._previous_layer = None
        self._progress = 1.
        self._direction = 1
        self._requested_direction = 0
        self._button_theme = None
        self.transition = QtCore.QVariantAnimation(self)
        self.transition.setDuration(self.TRANSITION_MS)
        self.transition.setStartValue(0.)
        self.transition.setEndValue(1.)
        self.transition.setEasingCurve(QtCore.QEasingCurve.InOutCubic)
        self.transition.valueChanged.connect(self._transition_frame)
        self.transition.finished.connect(self._finish_transition)
        self.previous_button = ScaleArrowButton(self)
        self.next_button = ScaleArrowButton(self)
        self.previous_button.setText('‹')
        self.next_button.setText('›')
        language = owner.current_interface_language
        for button, key, direction in ((self.previous_button, 'previous_mascot', -1),
                                       (self.next_button, 'next_mascot', 1)):
            button.setFixedSize(36, 36)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setFocusPolicy(QtCore.Qt.StrongFocus)
            button.setProperty('keyboardArrowControl', True)
            button.setAccessibleName(assistant_text(language, key))
            button.setToolTip(assistant_text(language, key))
            button.installEventFilter(self)
            button.clicked.connect(lambda checked=False, step=direction: self._browse(step))
        self.motion = PetMotion(self.mascot)
        self.motion.set_activity(getattr(owner, '_companion_activity', 'idle'))
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.clock = QtCore.QElapsedTimer()
        owner.installEventFilter(self)

    def _browse(self, direction):
        self._requested_direction = direction
        self.step_requested.emit(direction)

    def configure(self, mascot, appearance, custom_image):
        changed = self.mascot != mascot
        if changed:
            # Snapshot only the moving layer. Rapid clicks continue from the
            # currently visible blend instead of restarting an old animation.
            previous = self._render_carousel() if self.isVisible() else None
            self.transition.stop()
            delta = (MASCOTS.index(mascot) - MASCOTS.index(self.mascot)) % len(MASCOTS)
            self._direction = self._requested_direction or (1 if delta <= len(MASCOTS)//2 else -1)
            self._requested_direction = 0
            self._previous_layer = previous
            self._progress = 0. if previous is not None else 1.
        self.mascot, self.appearance, self.custom_image = mascot, appearance, custom_image
        self.motion.mascot = mascot
        self.motion.reactions = self.owner.config.get('desktop_assistant_reactions', True) is True
        self.setAccessibleName(assistant_text(self.owner.current_interface_language, mascot))
        self._style_buttons()
        if changed:
            self.motion.greet()
            if self._previous_layer is not None and not self.owner.isMinimized():
                self.transition.start()
            else:
                self._finish_transition()
        self._sync_animation()
        self.update()

    def _style_buttons(self):
        dark = self.owner.current_theme != 'Светлая'
        if self._button_theme != dark:
            self._button_theme = dark
            style = button_qss(dark, 'quiet', 'QToolButton', icon=True) + 'QToolButton { font-size:30px; }'
            for button in (self.previous_button, self.next_button):
                button.setStyleSheet(style)

    def _transition_frame(self, value):
        self._progress = float(value)
        self.update()

    def _finish_transition(self):
        self.transition.stop()
        self._previous_layer = None
        self._progress = 1.
        self.update()

    def resizeEvent(self, event):
        self._finish_transition()
        offset = min(160, self.width()*.34)
        y = round(self.height()*.55-18)
        self.previous_button.move(round(self.width()/2-offset-18), y)
        self.next_button.move(round(self.width()/2+offset-18), y)
        super().resizeEvent(event)

    def _carousel_rect(self):
        left, right = self.previous_button.geometry().right()+8, self.next_button.x()-8
        return QtCore.QRectF(left, 0, max(1, right-left), self.height())

    def _render_carousel(self):
        density = self.devicePixelRatioF()
        result = QtGui.QPixmap(self.size()*density)
        result.setDevicePixelRatio(density)
        result.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(result)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self._paint_carousel(painter)
        painter.end()
        return result

    def _paint_carousel(self, painter):
        painter.save()
        viewport = self._carousel_rect()
        painter.setClipRect(viewport, QtCore.Qt.IntersectClip)
        distance = viewport.width()
        if self._previous_layer is not None:
            painter.drawPixmap(QtCore.QPointF(-self._direction*distance*self._progress, 0), self._previous_layer)
            painter.translate(self._direction*distance*(1-self._progress), 0)
        self._paint_occupant(painter)
        painter.restore()

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
        self._finish_transition()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched in (self.previous_button, self.next_button) and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right):
                self._browse(-1 if event.key() == QtCore.Qt.Key_Left else 1)
                return True
        if watched is self.owner and event.type() == QtCore.QEvent.WindowStateChange:
            if self.owner.isMinimized():
                self._finish_transition()
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
        self._paint_carousel(painter)
        painter.setClipping(False)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor('#493b54' if dark else '#d4c5df'), 1))
        painter.drawRoundedRect(rect, 8, 8)

    def _paint_occupant(self, painter):
        dark = self.owner.current_theme != 'Светлая'
        cx, ground = self.width()/2, self.height()-17
        font = QtGui.QFont(self.font())
        font.setPixelSize(14)
        font.setWeight(QtGui.QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QtGui.QColor('#eee7f5' if dark else '#554264'))
        painter.drawText(QtCore.QRectF(cx-96, 3, 192, 22), QtCore.Qt.AlignCenter,
                         assistant_text(self.owner.current_interface_language, self.mascot))
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 25 if dark else 13))
        painter.drawEllipse(QtCore.QRectF(cx-85, ground+3, 170, 15))
        painter.setBrush(QtGui.QColor('#655074' if dark else '#c4afd5'))
        painter.drawRoundedRect(QtCore.QRectF(cx-70, ground-1, 140, 12), 5, 5)
        painter.setBrush(QtGui.QColor('#88709a' if dark else '#ddd0e8'))
        painter.drawEllipse(QtCore.QRectF(cx-70, ground-6, 140, 12))
        extent = min(112, self.height()-40)
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
