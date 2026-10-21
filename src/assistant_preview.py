"""Six compact companions in one stationary row; every click opens settings."""
import math
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_art import MASCOTS, mascot_id
from assistant_text import assistant_text
from assistant_motion import PetMotion, paint_pet, skin


class _PreviewButton(QtWidgets.QAbstractButton):
    def __init__(self, rail, mascot):
        super().__init__(rail)
        self.rail, self.mascot = rail, mascot
        self.gaze = None
        self.setFixedSize(28, 22)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        hint = assistant_text(rail.language, 'companion_settings')
        self.setAccessibleName(assistant_text(rail.language, mascot) + ' — ' + hint)
        self.setToolTip(self.accessibleName())
        self.clicked.connect(self._configure)

    def _configure(self):
        self.rail.motions[self.mascot].greet()
        self.rail.settings_requested.emit()

    def event(self, event):
        if event.type() == QtCore.QEvent.ParentChange and hasattr(self, 'rail') and hasattr(self.rail, 'timer'):
            self.rail._sync_animation()
        return super().event(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        motion = self.rail.motions[self.mascot]
        action = motion.action()
        paint_pet(painter, QtCore.QRectF((self.width()-22)/2, 0, 22, 22), self.mascot,
                  action=action, time=motion.time, state_time=motion.seconds(action),
                  gaze=self.gaze if self.underMouse() and action == 'idle' else None)

    def enterEvent(self, event):
        self.rail._hovered = True
        self.rail.motions[self.mascot].interact()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.rail._hovered = False
        self.gaze = None
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        offset = event.localPos() - QtCore.QPointF(self.width()/2, self.height()*.44)
        self.gaze = math.degrees(math.atan2(offset.x(), -offset.y())) % 360 if abs(offset.x())+abs(offset.y()) > 3 else None
        self.update()
        super().mouseMoveEvent(event)


class AssistantPreview(QtWidgets.QWidget):
    settings_requested = QtCore.pyqtSignal()
    dismiss_requested = QtCore.pyqtSignal()
    INTERVAL_MS = 33

    def __init__(self, activity_owner, language='en', parent=None):
        super().__init__(parent)
        self.setObjectName('assistantPreviewRail')
        self.setFixedHeight(22)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._owner, self.language = activity_owner, language
        self._hovered = False
        self._choice_dialog = None  # The main row never creates a desktop popup.
        self.mascot = mascot_id(getattr(activity_owner, 'config', {}).get('desktop_assistant_mascot'))
        self.art = None
        self.motions = {mascot: PetMotion(mascot) for mascot in MASCOTS}
        for index, motion in enumerate(self.motions.values()):
            motion.time = index*.13
        self.set_reactions(getattr(activity_owner, 'config', {}).get('desktop_assistant_reactions', True) is True)
        self.set_activity(getattr(activity_owner, '_companion_activity', 'idle'))
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(6, 0, 0, 0)
        row.setSpacing(0)
        self.label = QtWidgets.QLabel(assistant_text(language, 'mascots'))
        self.label.setStyleSheet('font-size:13px; color:' + ('#99919f' if activity_owner.current_theme != 'Светлая' else '#71647b') + ';')
        row.addWidget(self.label)
        row.addSpacing(8)
        self.buttons = {}
        for mascot in MASCOTS:
            button = _PreviewButton(self, mascot)
            self.buttons[mascot] = button
            row.addWidget(button)
        row.addStretch(1)
        self.button = self.buttons[self.mascot]
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.setInterval(self.INTERVAL_MS)
        self.timer.timeout.connect(self._tick)
        self._clock = QtCore.QElapsedTimer()
        activity_owner.installEventFilter(self)

    @property
    def motion(self):
        return self.motions[self.mascot]

    def set_activity(self, activity):
        for motion in self.motions.values():
            motion.set_activity(activity)
        self.update()

    def set_reactions(self, enabled):
        for motion in self.motions.values():
            motion.reactions = enabled

    def react(self, state):
        self.motion.play(state)
        self.button.update()
        self._sync_animation()

    def _sync_animation(self):
        active = (self.isVisible() and not self._owner.isMinimized()
                  and all(button.parentWidget() is self for button in self.buttons.values()))
        if active and not self.timer.isActive():
            self._clock.start()
            self.timer.start()
        elif not active:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.art = skin(self.mascot)
        self._sync_animation()

    def set_mascot(self, mascot):
        self.mascot = mascot_id(mascot)
        self.button = self.buttons[self.mascot]
        self.art = skin(self.mascot) if self.isVisible() else None
        self._sync_animation()

    def hideEvent(self, event):
        self.timer.stop()
        self._hovered = False
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched is self._owner and event.type() == QtCore.QEvent.WindowStateChange:
            self._sync_animation()
        return super().eventFilter(watched, event)

    def _tick(self):
        self._advance(max(0, min(self._clock.restart(), 200)))

    def _advance(self, elapsed):
        for mascot, motion in self.motions.items():
            motion.advance(elapsed/1000)
            self.buttons[mascot].update()
