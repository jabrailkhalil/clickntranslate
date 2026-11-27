"""One cached static companion shortcut; animation belongs to its settings/desktop."""
from functools import lru_cache
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_art import art_path, mascot_id, load_custom_art
from assistant_text import assistant_text, companion_display_name
from assistant_motion import PetMotion


@lru_cache(maxsize=6)
def preview_art(mascot):
    return QtGui.QPixmap(art_path(f'{mascot_id(mascot)}/preview.png'))


@lru_cache(maxsize=6)
def preview_portrait(mascot):
    # Remove the empty space in the static resting pose, without decoding an
    # animation atlas. The actual character can fill its larger shortcut.
    pixmap = preview_art(mascot)
    if pixmap.isNull():
        return pixmap
    bounds = QtGui.QRegion(pixmap.mask()).boundingRect()
    return pixmap.copy(bounds) if not bounds.isEmpty() else pixmap


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
        self._custom_art = False
        self.button = activity_owner._create_main_hotkey_pair(
            assistant_text(language, 'companion_section'), '', compact=True)
        self.button.setMinimumWidth(0)
        self.button.setFixedHeight(22)
        self.button.value_label.setFixedSize(36, 20)
        self.button.clicked.connect(self.settings_requested)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
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
        appearance = getattr(self._owner, 'config', {}).get('desktop_assistant_appearance', 'animated')
        hint = companion_display_name(self.language, self.mascot, appearance) + ' — ' + assistant_text(self.language, 'companion_settings')
        self.button.caption_label.setText(assistant_text(self.language, 'companion_section'))
        self.button.setAccessibleName(hint)
        self.button.setToolTip(hint)
        self.art = self._load_art() if self.isVisible() else None
        self._update_thumbnail()

    def _load_art(self):
        self._custom_art = False
        config = getattr(self._owner, 'config', {})
        if config.get('desktop_assistant_appearance') == 'custom':
            try:
                picture = load_custom_art(config.get('desktop_assistant_image', ''))
            except (OSError, ValueError):
                pass
            else:
                self._custom_art = True
                return picture
        return preview_art(self.mascot)

    def _update_thumbnail(self):
        if self.art is not None:
            # QGraphicsView can magnify this row for both Windows DPI and the
            # user's UI scale. Keep extra pixels instead of enlarging a 20px
            # bitmap. DPR preserves exactly the same logical row height.
            density = 4
            portrait = self.art if self._custom_art else preview_portrait(self.mascot)
            pixmap = portrait.scaled(
                32*density, max(1, self.button.value_label.height())*density,
                QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            pixmap.setDevicePixelRatio(density)
            self.button.value_label.setPixmap(pixmap)
        else:
            self.button.value_label.clear()

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
        self.art = self._load_art()
        self._update_thumbnail()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def _advance(self, elapsed):
        self.motion.advance(elapsed/1000)
