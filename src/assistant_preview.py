"""One cached static companion shortcut; animation belongs to its settings/desktop."""
from functools import lru_cache
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_art import art_path, mascot_id
from assistant_text import assistant_text
from assistant_motion import PetMotion


@lru_cache(maxsize=6)
def preview_art(mascot):
    return QtGui.QPixmap(art_path(f'{mascot_id(mascot)}/preview.png'))


class _PreviewButton(QtWidgets.QAbstractButton):
    def __init__(self, rail):
        super().__init__(rail)
        self.rail = rail
        self.setMinimumWidth(28)
        self.setFixedHeight(22)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.clicked.connect(rail.settings_requested)

    def paintEvent(self, event):
        art = self.rail.art
        if art is None:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        size = QtCore.QSizeF(art.size()).scaled(22, 22, QtCore.Qt.KeepAspectRatio)
        painter.drawPixmap(QtCore.QRectF(3, (22-size.height())/2, size.width(), size.height()),
                           art, QtCore.QRectF(art.rect()))
        font = QtGui.QFont(self.font())
        font.setPixelSize(13)
        painter.setFont(font)
        painter.setPen(QtGui.QColor('#99919f' if self.rail._owner.current_theme != 'Светлая' else '#71647b'))
        painter.drawText(QtCore.QRect(33, 0, max(0, self.width()-33), 22), QtCore.Qt.AlignVCenter,
                         self.text())


class AssistantPreview(QtWidgets.QWidget):
    settings_requested = QtCore.pyqtSignal()
    dismiss_requested = QtCore.pyqtSignal()

    def __init__(self, activity_owner, language='en', parent=None):
        super().__init__(parent)
        self.setObjectName('assistantPreviewRail')
        self.setFixedHeight(22)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._owner, self.language = activity_owner, language
        self._choice_dialog = None
        self.art = None
        self.button = _PreviewButton(self)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(6, 0, 0, 0)
        row.addWidget(self.button)
        # Retain the shared activity API without a repaint timer or atlas decode.
        self.timer = QtCore.QTimer(self)
        self.set_mascot(getattr(activity_owner, 'config', {}).get('desktop_assistant_mascot'))

    @property
    def motion(self):
        return self.motions[self.mascot]

    def set_mascot(self, mascot):
        self.mascot = mascot_id(mascot)
        self.motions = {self.mascot: PetMotion(self.mascot)}
        self.buttons = {self.mascot: self.button}
        self.set_reactions(getattr(self._owner, 'config', {}).get('desktop_assistant_reactions', True) is True)
        self.set_activity(getattr(self._owner, '_companion_activity', 'idle'))
        hint = assistant_text(self.language, self.mascot) + ' — ' + assistant_text(self.language, 'companion_settings')
        self.button.setText(assistant_text(self.language, 'companion_section'))
        self.button.setAccessibleName(hint)
        self.button.setToolTip(hint)
        self.art = preview_art(self.mascot) if self.isVisible() else None
        self.button.update()

    def set_activity(self, activity):
        self.motion.set_activity(activity)

    def set_reactions(self, enabled):
        self.motion.reactions = enabled

    def react(self, state):
        self.motion.play(state)

    def _sync_animation(self):
        self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.art = preview_art(self.mascot)
        self.button.update()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def _advance(self, elapsed):
        self.motion.advance(elapsed/1000)
