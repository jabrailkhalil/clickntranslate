"""One embedded update page for check, consent, progress and errors."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QProgressBar, QPushButton, QVBoxLayout, QHBoxLayout, QWidget
from button_styles import button_qss


class InlineUpdatePage(QWidget):
    def __init__(self, owner):
        super().__init__(owner.settings_pages)
        self.owner = owner
        self.setObjectName('inlineUpdatePage')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        from settings_window import settings_text
        language = owner.parent.current_interface_language
        title = QLabel(settings_text(language, 'update'))
        title.setStyleSheet('font-size:18px; font-weight:600; background:transparent;')
        layout.addWidget(title)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.label.setStyleSheet('font-size:14px; background:transparent;')
        layout.addWidget(self.label)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        layout.addWidget(self.progress)
        layout.addStretch(1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.extra = QPushButton()
        self.extra.hide()
        self.primary = QPushButton()
        self.secondary = QPushButton()
        for button in (self.extra, self.secondary, self.primary):
            button.setMinimumHeight(30)
            actions.addWidget(button)
        self.primary.clicked.connect(lambda: self._primary_action())
        self.secondary.clicked.connect(lambda: self._secondary_action())
        layout.addLayout(actions)
        self._primary_action = lambda: None
        self._secondary_action = lambda: None
        owner.settings_pages.addWidget(self)
        self.setStyleSheet('QWidget#inlineUpdatePage { background:transparent; }')
        for button in (self.primary, self.secondary, self.extra):
            button.setStyleSheet(button_qss(dark=owner.parent.current_theme != 'Светлая'))
        from styled_dialogs import install_accent_controls
        install_accent_controls(self, dark=owner.parent.current_theme != 'Светлая')

    def actions(self, primary='', callback=None, secondary='', secondary_callback=None):
        self.extra.hide()
        self.primary.setText(primary)
        self.primary.setVisible(bool(primary))
        self.secondary.setText(secondary)
        self.secondary.setVisible(bool(secondary))
        self._primary_action = callback or (lambda: None)
        self._secondary_action = secondary_callback or (lambda: None)

    def setLabelText(self, text):
        self.label.setText(text)

    def setRange(self, minimum, maximum):
        self.progress.show()
        self.progress.setRange(minimum, maximum)

    def setValue(self, value):
        self.progress.setValue(value)

    def bring_to_front(self):
        self.owner._set_settings_page(self.owner.settings_pages.indexOf(self))


def page(owner):
    from PyQt5 import sip
    current = getattr(owner, '_update_progress', None)
    if not isinstance(current, InlineUpdatePage) or sip.isdeleted(current):
        current = InlineUpdatePage(owner)
        owner._update_progress = current
    current.bring_to_front()
    return current


def result(owner, text, primary='', callback=None, secondary='', secondary_callback=None):
    current = page(owner)
    current.setLabelText(text)
    current.progress.hide()
    current.actions(primary, callback, secondary, secondary_callback)
