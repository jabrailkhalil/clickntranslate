"""Tiny in-window companion. No desktop overlay, capture, model or worker.

Only a 20px sprite is animated, at most 60 times/s while its page is visible.
The animation continues in inactive windows. Hidden/minimized pages have no
running timer. Artwork is decoded once; both views play the same whole frames.
"""
import math
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_text import assistant_text
from assistant_art import mascot_id
from assistant_motion import PetMotion, paint_pet, skin


class _PreviewButton(QtWidgets.QAbstractButton):
    def __init__(self, rail):
        super().__init__(rail)
        self.rail = rail
        self.setFixedSize(28, 22)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def event(self, event):
        if (event.type() == QtCore.QEvent.ParentChange and hasattr(self, 'rail')
                and hasattr(self.rail, 'timer')):
            self.rail._sync_animation()
        return super().event(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        if self.rail.art:
            motion = self.rail.motion
            action = motion.action()
            fraction = self.rail._x-round(self.rail._x)
            paint_pet(painter, QtCore.QRectF((self.width()-22)/2+fraction, 0, 22, 22),
                      self.rail.mascot, phase=motion.phase, time=motion.time,
                      action=action, facing=self.rail.direction, crawl_phase=motion.crawl_phase,
                      state_time=motion.seconds(action),
                      gaze=self.rail.gaze if self.rail._hovered and action == 'idle' else None)
        else:
            painter.setPen(self.palette().text().color())
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, '✦')

    def enterEvent(self, event):
        self.rail._hovered = True
        self.rail.motion.interact()
        self.rail._sync_animation()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.rail._hovered = False
        self.rail.gaze = None
        self.rail._sync_animation()
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        offset = event.localPos() - QtCore.QPointF(self.width()/2, self.height()*.44)
        self.rail.gaze = (math.degrees(math.atan2(offset.x(), -offset.y())) % 360
                          if abs(offset.x()) + abs(offset.y()) > 3 else None)
        self.update()
        super().mouseMoveEvent(event)

    def focusInEvent(self, event):
        self.rail._sync_animation()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.rail._sync_animation()


class AssistantPreview(QtWidgets.QWidget):
    settings_requested = QtCore.pyqtSignal()
    dismiss_requested = QtCore.pyqtSignal()
    INTERVAL_MS = 16

    def __init__(self, activity_owner, language='en', parent=None):
        super().__init__(parent)
        self.setObjectName('assistantPreviewRail')
        self.setFixedHeight(22)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._owner = activity_owner
        self.language = language
        self._menu_open = False
        self._choice_dialog = None
        font = QtGui.QFont(self.font())
        font.setPixelSize(13)
        self.setFont(font)
        self._hovered = False
        self.gaze = None
        self.art = None
        self.mascot = mascot_id(getattr(activity_owner, 'config', {}).get('desktop_assistant_mascot'))
        self.motion = PetMotion(self.mascot)
        self.motion.reactions = getattr(activity_owner, 'config', {}).get('desktop_assistant_reactions', True) is True
        self.motion.set_activity(getattr(activity_owner, '_companion_activity', 'idle'))
        self.direction = 1
        self._x = 0.
        self.button = _PreviewButton(self)
        hint = assistant_text(language, 'preview_hint')
        self.button.setAccessibleName(hint)
        self.button.setToolTip(hint)
        self.button.clicked.connect(self._show_menu)
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.setInterval(self.INTERVAL_MS)
        self.timer.timeout.connect(self._tick)
        self._clock = QtCore.QElapsedTimer()
        activity_owner.installEventFilter(self)

    def _track_start(self):
        return min(max(0, self.width() - self.button.width()), self.fontMetrics().horizontalAdvance(
            assistant_text(self.language, 'page')) + 12)

    def _show_menu(self):
        if self._menu_open:
            self._choice_dialog.hide()
            return
        from desktop_assistant import AssistantMenu
        from assistant_motion import play_reaction
        from ui_scaling import desktop_control_scale
        from game_mode import _foreground_window
        helper = getattr(self._owner, '_desktop_assistant', None)
        if helper is not None:
            helper._foreground = _foreground_window()
        if self._choice_dialog is None:
            screen = self.screen()
            available = screen.availableGeometry()
            factor = min(desktop_control_scale(screen), available.width()/360, available.height()/360)
            dialog = AssistantMenu(self.language, self._owner.current_theme != 'Светлая',
                                   factor, mascot=self.mascot)
            self._choice_dialog = dialog
            dialog.reaction_requested.connect(lambda state: play_reaction(self._owner, state, preview=self))
            dialog.action_requested.connect(self._request_action)
            dialog.visibility_changed.connect(self._menu_visibility)
            self.destroyed.connect(dialog.deleteLater)
        play_reaction(self._owner, 'waving', preview=self)
        self._choice_dialog.set_activity(getattr(self._owner, '_companion_activity', 'idle'))
        origin = self.button.mapToGlobal(QtCore.QPoint())
        self._choice_dialog.open_beside(QtCore.QRect(origin, self.button.size()), self.screen().availableGeometry())

    def _menu_visibility(self, visible):
        self._menu_open = visible
        self.motion.menu_open = visible
        self._sync_animation()

    def _request_action(self, action):
        self._choice_dialog.hide()
        if action == 'settings':
            self.settings_requested.emit()
        elif action == 'hide':
            self.dismiss_requested.emit()
        else:
            helper = getattr(self._owner, '_desktop_assistant', None)
            if helper is not None:
                helper.request_action(action)
            else:
                from desktop_assistant import ACTION_METHODS
                method = 'open_text_translation' if action == 'text' else ACTION_METHODS.get(action)
                callback = getattr(self._owner, method, None) if method else None
                if callback is not None:
                    QtCore.QTimer.singleShot(180, callback)

    def _sync_animation(self):
        active = (self.isVisible() and self.button.parentWidget() is self
                  and not self._owner.isMinimized()
                  and self.width() > self.button.width() and bool(self.art))
        if active and not self.timer.isActive():
            self._clock.start()
            self.timer.start()
        elif not active:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        if self.art is None:
            self.art = skin(self.mascot)
        self._sync_animation()

    def set_mascot(self, mascot):
        mascot = mascot_id(mascot)
        if mascot == self.mascot:
            return
        self.mascot = mascot
        if self._choice_dialog is not None:
            self._choice_dialog.hide()
            self._choice_dialog.deleteLater()
            self._choice_dialog = None
        self.art = skin(mascot) if self.isVisible() else None
        self.motion.mascot = mascot
        self.motion.crawl_phase = 0
        self.motion.greet()
        self._sync_animation()
        self.button.update()

    def hideEvent(self, event):
        self.timer.stop()
        self._hovered = False
        if self._choice_dialog is not None:
            self._choice_dialog.hide()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched is self._owner and event.type() == QtCore.QEvent.WindowDeactivate:
            self._hovered = False
            self._sync_animation()
        if watched is self._owner and event.type() in (
                QtCore.QEvent.WindowStateChange, QtCore.QEvent.Show, QtCore.QEvent.Hide):
            self._sync_animation()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        self._x = float(self._track_start())
        self.button.move(round(self._x), 0)
        self._sync_animation()
        super().resizeEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        dark = getattr(self._owner, 'current_theme', 'Темная') != 'Светлая'
        color = QtGui.QColor('#99919f' if dark else '#71647b')
        painter.setPen(color)
        painter.drawText(self.rect().adjusted(6, 0, 0, 0), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                         assistant_text(self.language, 'page'))

    def _tick(self):
        # A busy UI never catches up by running a burst of animation frames.
        elapsed = max(0, min(self._clock.restart(), 200))
        self._advance(elapsed)

    def _advance(self, elapsed):
        self.motion.advance(elapsed / 1000)
        self.button.update()
