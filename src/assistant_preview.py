"""Tiny in-window companion. No desktop overlay, capture, model or worker.

Only a 20px sprite is animated, at most 60 times/s while its page is visible.
The animation continues in inactive windows. Hidden/minimized pages have no
running timer. Artwork is decoded once; motion shares the desktop rig.
"""
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
                      action=action, facing=self.rail.direction, crawl_phase=motion.crawl_phase)
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
        font = QtGui.QFont(self.font())
        font.setPixelSize(13)
        self.setFont(font)
        self._hovered = False
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
            return
        self._menu_open = True
        self._sync_animation()
        # An embedded QMenu inherits the graphics proxy's clipping and native
        # menu palette. A real owned dialog has its own complete native surface.
        from styled_dialogs import CenteredFramelessDialog
        from ui_scaling import native_window_parent
        from button_styles import button_qss
        from rounded_windows import clip_rounded_window
        dark = self._owner.current_theme != 'Светлая'
        dialog = CenteredFramelessDialog(native_window_parent(self), drag_height=42)
        self._choice_dialog = dialog
        dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        dialog.setObjectName('companionChoice')
        dialog.setWindowTitle(assistant_text(self.language, 'page'))
        dialog.setFixedWidth(350)
        outer = QtWidgets.QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QtWidgets.QFrame(dialog)
        frame.setObjectName('companionChoiceFrame')
        outer.addWidget(frame)
        dialog.setStyleSheet(f'''
            QDialog#companionChoice {{ background:transparent; }}
            QFrame#companionChoiceFrame {{ background:{'#121212' if dark else '#f0edf3'};
                border:1px solid {'#584963' if dark else '#bcaacb'}; border-radius:8px; }}
            QLabel {{ color:{'#eee7f5' if dark else '#302639'}; background:transparent; border:0; }}
        ''')
        clip_rounded_window(dialog, frame, 8)
        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(assistant_text(self.language, 'page'))
        title.setStyleSheet('font-size:16px; font-weight:600;')
        header.addWidget(title, 1)
        close = QtWidgets.QPushButton('×')
        close.setFixedSize(28, 28)
        close.setAccessibleName(assistant_text(self.language, 'close_menu'))
        close.setStyleSheet(button_qss(dark, 'close', icon=True))
        close.clicked.connect(dialog.reject)
        header.addWidget(close)
        layout.addLayout(header)
        note = QtWidgets.QLabel(assistant_text(self.language, 'preview_choices'))
        note.setWordWrap(True)
        note.setStyleSheet('font-size:13px;')
        layout.addWidget(note)
        actions = QtWidgets.QHBoxLayout()
        for key, result in (('companion_settings', 1), ('dismiss', 2)):
            button = QtWidgets.QPushButton(assistant_text(self.language, key))
            button.setStyleSheet(button_qss(dark, 'primary' if result == 1 else 'secondary', compact=True))
            button.setMinimumHeight(32)
            button.clicked.connect(lambda checked=False, value=result: dialog.done(value))
            actions.addWidget(button)
        layout.addLayout(actions)
        def finished(result):
            self._menu_open = False
            self.button.clearFocus()
            self._sync_animation()
            self._choice_dialog = None
            if result == 1:
                self.settings_requested.emit()
            elif result == 2:
                self.dismiss_requested.emit()
        dialog.finished.connect(finished)
        dialog.open()

    def _sync_animation(self):
        active = (self.isVisible() and self.button.parentWidget() is self
                  and not self._owner.isMinimized()
                  and not self._hovered and not self._menu_open
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
        self.art = skin(mascot) if self.isVisible() else None
        self.motion.mascot = mascot
        self.motion.crawl_phase = 0
        self._sync_animation()
        self.button.update()

    def hideEvent(self, event):
        self.timer.stop()
        self._hovered = False
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
        self._x = min(self._x, max(0, self.width() - self.button.width()))
        self._x = max(self._track_start(), self._x)
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
        maximum = max(0, self.width() - self.button.width())
        before = self._x
        self._x += self.direction * self.motion.advance(elapsed / 1000, 10, 22)
        if self._x >= maximum:
            self._x, self.direction = float(maximum), -1
        elif self._x <= self._track_start():
            self._x, self.direction = float(self._track_start()), 1
        self.motion.moved(self._x-before, 22)
        self.button.move(round(self._x), 0)
        self.button.update()  # Invalidate only the 22x18 child, not the whole page.
