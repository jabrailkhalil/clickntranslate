"""Desktop companion preferences; independent of its enabled runtime instance."""
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_text import assistant_text
from assistant_art import APPEARANCES, companion_art


BEHAVIORS = ('idle', 'walk')
ASSISTANT_DEFAULTS = {
    'desktop_assistant_behavior': 'idle',
    'desktop_assistant_size': 100,
    'desktop_assistant_speed': 40,
    'desktop_assistant_opacity': 100,
    'desktop_assistant_topmost': True,
    'desktop_assistant_appearance': 'orb',
    'desktop_assistant_image': '',
}


def assistant_preferences(config):
    values = {key: config.get(key, default) for key, default in ASSISTANT_DEFAULTS.items()}
    # Preserve older choices without mixing static art with a walking sprite.
    if values['desktop_assistant_appearance'] == 'animated':
        values['desktop_assistant_appearance'] = {
            'walk': 'walking', 'sleep': 'sleep_icon', 'look': 'orb', 'idle': 'orb',
        }.get(str(values['desktop_assistant_behavior']), 'orb')
    if values['desktop_assistant_behavior'] not in BEHAVIORS:
        values['desktop_assistant_behavior'] = 'idle'
    for key, lower, upper in (('size', 60, 180), ('speed', 20, 100), ('opacity', 40, 100)):
        name = 'desktop_assistant_' + key
        try:
            value = int(values[name]) if not isinstance(values[name], bool) else ASSISTANT_DEFAULTS[name]
        except (ValueError, TypeError, OverflowError):
            value = ASSISTANT_DEFAULTS[name]
        values[name] = max(lower, min(upper, value))
    values['desktop_assistant_topmost'] = values['desktop_assistant_topmost'] is True
    if values['desktop_assistant_appearance'] not in APPEARANCES:
        values['desktop_assistant_appearance'] = 'orb'
    if not isinstance(values['desktop_assistant_image'], str):
        values['desktop_assistant_image'] = ''
    return values


class AssistantToggle(QtWidgets.QCheckBox):
    """A keyboard-accessible checkbox with an explicit on/off switch track."""
    def focusInEvent(self, event):
        self._keyboard_focus = event.reason() in (QtCore.Qt.TabFocusReason, QtCore.Qt.BacktabFocusReason, QtCore.Qt.ShortcutFocusReason)
        super().focusInEvent(event)

    def mousePressEvent(self, event):
        self._keyboard_focus = False
        super().mousePressEvent(event)
        self.update()

    def sizeHint(self):
        return QtCore.QSize(self.fontMetrics().horizontalAdvance(self.text()) + 64, 32)

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        track = QtCore.QRectF(1, (self.height() - 22) / 2, 42, 22)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor('#7a5fa1' if self.isChecked() else '#77717e'))
        painter.drawRoundedRect(track, 11, 11)
        painter.setBrush(QtGui.QColor('#ffffff'))
        painter.drawEllipse(QtCore.QRectF(track.x() + (23 if self.isChecked() else 3), track.y() + 3, 16, 16))
        painter.setPen(self.palette().color(QtGui.QPalette.WindowText))
        painter.setFont(self.font())
        painter.drawText(self.rect().adjusted(54, 0, 0, 0), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, self.text())
        if self.hasFocus() and getattr(self, '_keyboard_focus', False):
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor('#b596dd'), 1, QtCore.Qt.DotLine))
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 4, 4)


class AssistantSettingsPage(QtWidgets.QWidget):
    def __init__(self, settings):
        super().__init__(settings)
        from settings_window import DropDownCombo
        self.settings = settings
        self.owner = settings.parent
        self.language = self.owner.current_interface_language
        tr = lambda key: assistant_text(self.language, key)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 0, 6, 0)
        root.setSpacing(6)
        self.toggle = AssistantToggle(tr('enable_switch'))
        self.toggle.setMinimumHeight(32)
        self.toggle.setToolTip(tr('page_hint'))
        toggle_row = QtWidgets.QHBoxLayout()
        toggle_row.addWidget(self.toggle, 1)
        self.dismiss_button = QtWidgets.QPushButton(tr('dismiss'))
        self.dismiss_button.setObjectName('desktopAssistantDismiss')
        self.dismiss_button.setMinimumHeight(30)
        self.dismiss_button.setToolTip(tr('dismiss_hint'))
        self.dismiss_button.clicked.connect(settings._dismiss_desktop_assistant_until_restart)
        toggle_row.addWidget(self.dismiss_button)
        root.addLayout(toggle_row)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        root.addWidget(scroll, 1)
        self.options = QtWidgets.QWidget()
        self.options.setObjectName('assistantOptions')
        contents = QtWidgets.QVBoxLayout(self.options)
        contents.setContentsMargins(0, 2, 12, 0)
        contents.setSpacing(6)
        def section(title, destination=None):
            heading = QtWidgets.QLabel(tr(title))
            heading.setObjectName('assistantSection')
            (destination if destination is not None else contents).addWidget(heading)
        section('appearance')
        gallery = QtWidgets.QHBoxLayout()
        self.appearance_buttons = {}
        self.appearance_group = QtWidgets.QButtonGroup(self)
        self.appearance_group.setExclusive(True)
        for key in APPEARANCES:
            button = QtWidgets.QToolButton()
            button.setObjectName('assistantAppearance')
            button.setText(tr(key))
            button.setToolTip(tr('walking_hint' if key == 'walking' else 'static_hint'))
            button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            button.setIcon(QtGui.QIcon(companion_art(key)))
            button.setIconSize(QtCore.QSize(40, 40))
            button.setMinimumSize(72, 66)
            button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=key: self.choose_appearance(value))
            self.appearance_group.addButton(button)
            self.appearance_buttons[key] = button
            gallery.addWidget(button)
        contents.addLayout(gallery)
        lower = QtWidgets.QHBoxLayout()
        lower.setSpacing(18)
        contents.addLayout(lower)
        placement_layout = QtWidgets.QVBoxLayout()
        motion_layout = QtWidgets.QVBoxLayout()
        lower.addLayout(placement_layout, 1)
        lower.addLayout(motion_layout, 1)
        section('placement', placement_layout)
        common = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(common)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        placement_layout.addWidget(common)
        self.motion_options = QtWidgets.QWidget()
        self.motion_options.setToolTip(tr('walking_hint'))
        motion_form = QtWidgets.QFormLayout(self.motion_options)
        motion_form.setContentsMargins(0, 0, 0, 0)
        motion_form.setSpacing(6)
        self.behavior = DropDownCombo()
        for mode in BEHAVIORS:
            self.behavior.addItem(tr('pause_walk' if mode == 'idle' else mode), mode)
        self.behavior.setMinimumHeight(30)
        motion_form.addRow(self.behavior)
        self.sliders = {}
        for key, limits, suffix in (('size', (60, 180), '%'), ('speed', (20, 100), ''), ('opacity', (40, 100), '%')):
            row = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setObjectName('assistantSlider')
            slider.setMinimumHeight(24)
            slider.setRange(*limits)
            slider.setAccessibleName(tr(key))
            value = QtWidgets.QLabel()
            value.setObjectName('gameSettingValue')
            value.setMinimumWidth(48)
            layout.addWidget(slider, 1)
            layout.addWidget(value)
            slider.valueChanged.connect(lambda number, label=value, tail=suffix: label.setText(f'{number}{tail}'))
            slider.valueChanged.connect(lambda number, name=key: self.save(name, number))
            (motion_form if key == 'speed' else form).addRow(tr('speed_short' if key == 'speed' else key), row)
            self.sliders[key] = (slider, value, suffix)
        self.topmost = QtWidgets.QCheckBox(tr('topmost'))
        form.addRow(self.topmost)
        section('walking_section', motion_layout)
        self.motion_hint = QtWidgets.QLabel(tr('walking_only'))
        self.motion_hint.setWordWrap(True)
        self.motion_hint.setObjectName('assistantNote')
        motion_layout.addWidget(self.motion_hint)
        motion_layout.addWidget(self.motion_options)
        actions = QtWidgets.QHBoxLayout()
        self.action_buttons = {}
        for action in ('home',):
            button = QtWidgets.QPushButton(tr(action))
            button.setMinimumHeight(30)
            button.clicked.connect(lambda checked=False, key=action: self.perform(key))
            actions.addWidget(button)
            self.action_buttons[action] = button
        form.addRow(actions)
        placement_layout.addStretch(1)
        motion_layout.addStretch(1)
        contents.addStretch(1)
        scroll.setWidget(self.options)
        self.toggle.toggled.connect(settings._set_desktop_assistant_enabled)
        self.toggle.toggled.connect(self.options.setEnabled)
        self.behavior.currentIndexChanged.connect(lambda: self.save('behavior', self.behavior.currentData()))
        self.topmost.toggled.connect(lambda checked: self.save('topmost', checked))
        self.refresh()

    def choose_appearance(self, appearance):
        if appearance == 'walking':
            self.owner.config['desktop_assistant_behavior'] = 'walk'
        if appearance == 'custom':
            from ui_scaling import native_window_parent
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(
                native_window_parent(self), assistant_text(self.language, 'choose_image'), '',
                'Images (*.png *.jpg *.jpeg *.webp *.bmp)')
            if not filename:
                self.refresh()
                return
            from assistant_art import _read_pixmap
            from pathlib import Path
            try:
                valid = Path(filename).stat().st_size <= 10_000_000 and not _read_pixmap(filename, Path(filename).stat().st_mtime_ns).isNull()
            except OSError:
                valid = False
            if not valid:
                QtWidgets.QMessageBox.warning(native_window_parent(self), assistant_text(self.language, 'choose_image'),
                                              assistant_text(self.language, 'image_error'))
                self.refresh()
                return
            self.owner.config['desktop_assistant_image'] = filename
        self.save('appearance', appearance)
        self.refresh()

    def save(self, key, value):
        self.owner.config['desktop_assistant_' + key] = value
        self.owner.save_config()
        helper = getattr(self.owner, '_desktop_assistant', None)
        if helper is not None:
            helper.refresh()
        if key == 'behavior':
            self.sliders['speed'][0].setEnabled(value == 'walk')

    def perform(self, action):
        helper = getattr(self.owner, '_desktop_assistant', None)
        if helper is not None:
            helper.request_action(action)

    def refresh(self):
        values = assistant_preferences(self.owner.config)
        enabled = self.owner.config.get('desktop_assistant_enabled') is True
        self.dismiss_button.setEnabled(
            not getattr(self.owner, '_desktop_assistant_suppressed_until_restart', False))
        for widget, value in ((self.toggle, enabled), (self.topmost, values['desktop_assistant_topmost'])):
            blocker = QtCore.QSignalBlocker(widget)
            widget.setChecked(value)
            del blocker
        blocker = QtCore.QSignalBlocker(self.behavior)
        self.behavior.setCurrentIndex(self.behavior.findData(values['desktop_assistant_behavior']))
        del blocker
        for key, (slider, label, suffix) in self.sliders.items():
            blocker = QtCore.QSignalBlocker(slider)
            value = values['desktop_assistant_' + key]
            slider.setValue(value)
            label.setText(f'{value}{suffix}')
            del blocker
        self.options.setEnabled(enabled)
        appearance = values['desktop_assistant_appearance']
        for key, button in self.appearance_buttons.items():
            button.setChecked(key == appearance)
        self.appearance_buttons['custom'].setIcon(QtGui.QIcon(companion_art('custom', values['desktop_assistant_image'])))
        self.motion_options.setEnabled(appearance == 'walking')
        self.motion_options.setVisible(appearance == 'walking')
        self.motion_hint.setVisible(appearance != 'walking')
        self.sliders['speed'][0].setEnabled(values['desktop_assistant_behavior'] == 'walk')
