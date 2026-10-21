"""Desktop companion preferences; independent of its enabled runtime instance."""
from PyQt5 import QtCore, QtWidgets, sip

from assistant_text import assistant_text
from assistant_art import APPEARANCES, LEGACY_APPEARANCES, MASCOTS, DEFAULT_MASCOT, mascot_id
from header_icons import header_icon
from pathlib import Path


from number_controls import NumberStepper as AssistantNumberBox


BEHAVIORS = ('idle',)
ASSISTANT_DEFAULTS = {
    'main_assistant_visible': True,
    'desktop_assistant_behavior': 'idle',
    'desktop_assistant_size': 100,
    'desktop_assistant_speed': 40,
    'desktop_assistant_opacity': 100,
    'desktop_assistant_topmost': True,
    'desktop_assistant_appearance': 'animated',
    'desktop_assistant_mascot': DEFAULT_MASCOT,
    'desktop_assistant_reactions': True,
    'desktop_assistant_image': '',
}


def assistant_preferences(config):
    values = {key: config.get(key, default) for key, default in ASSISTANT_DEFAULTS.items()}
    # Old walking profiles become stationary animation; static choices retain
    # the closest built-in v2 pose. Never resume travel after an upgrade.
    old = values['desktop_assistant_appearance']
    old = old if isinstance(old, str) else 'portrait'
    values['desktop_assistant_appearance'] = LEGACY_APPEARANCES.get(old, old)
    values['desktop_assistant_behavior'] = 'idle'
    for key, lower, upper in (('size', 60, 180), ('speed', 20, 100), ('opacity', 40, 100)):
        name = 'desktop_assistant_' + key
        try:
            value = int(values[name]) if not isinstance(values[name], bool) else ASSISTANT_DEFAULTS[name]
        except (ValueError, TypeError, OverflowError):
            value = ASSISTANT_DEFAULTS[name]
        values[name] = max(lower, min(upper, value))
    values['desktop_assistant_topmost'] = values['desktop_assistant_topmost'] is True
    values['desktop_assistant_mascot'] = mascot_id(values['desktop_assistant_mascot'])
    values['desktop_assistant_reactions'] = values['desktop_assistant_reactions'] is True
    if values['desktop_assistant_appearance'] not in APPEARANCES:
        values['desktop_assistant_appearance'] = 'portrait'
    if not isinstance(values['desktop_assistant_image'], str):
        values['desktop_assistant_image'] = ''
    return values


class AssistantSettingsPage(QtWidgets.QWidget):
    """The same left-checkbox/right-field grid as the other settings tabs."""
    def __init__(self, settings):
        super().__init__(settings)
        self.settings = settings
        self.owner = settings.parent
        self.language = self.owner.current_interface_language
        tr = lambda key: assistant_text(self.language, key)
        from settings_window import DropDownCombo
        from assistant_stage import MascotStage
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        self.options = QtWidgets.QWidget()
        self.options.setObjectName('assistantOptions')
        form = QtWidgets.QGridLayout(self.options)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(2)
        form.setColumnStretch(0, 1)
        self.form_grid = form
        self.main_visible = QtWidgets.QCheckBox(tr('main_visible_short'))
        self.main_visible.setAccessibleName(tr('main_visible'))
        self.toggle = QtWidgets.QCheckBox(tr('enabled'))
        self.topmost = QtWidgets.QCheckBox(tr('topmost'))
        self.reactions = QtWidgets.QCheckBox(tr('reactions'))
        self.reactions.setToolTip(tr('reactions_hint'))
        self.reactions.toggled.connect(lambda checked: self.save('reactions', checked))
        for row, checkbox in enumerate((self.main_visible, self.toggle, self.topmost, self.reactions)):
            checkbox.setFixedHeight(28)
            checkbox.setStyleSheet('margin:0; padding:0;')
            form.addWidget(checkbox, row, 0)

        self.mode_combo = DropDownCombo()
        self.mode_combo.setObjectName('assistantDisplayMode')
        for value, label in (('animated', 'mode_animated'), ('portrait', 'mode_static'), ('custom', 'custom')):
            self.mode_combo.addItem(tr(label), value)
        self.mode_combo.setToolTip(tr('animated_hint'))
        self.mode_combo.currentIndexChanged.connect(lambda: self.choose_appearance(self.mode_combo.currentData()))
        self.values = {}
        for key, low, high in (('size', 60, 180), ('opacity', 40, 100)):
            field = AssistantNumberBox(dark=self.owner.current_theme != 'Светлая')
            field.setRange(low, high)
            field.setSuffix('%')
            field.setKeyboardTracking(False)
            field.setToolTip(f'{tr(key)}: {low}–{high}%')
            field.valueChanged.connect(lambda value, name=key: self.save(name, value))
            self.values[key] = field
        self.field_labels = {}
        for row, (name, field) in enumerate((('display_mode', self.mode_combo),
                                              ('size', self.values['size']), ('opacity', self.values['opacity']))):
            label = QtWidgets.QLabel(tr(name))
            label.setFixedHeight(28)
            label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            label.setStyleSheet('margin:0; padding:0;')
            label.setBuddy(field)
            field.setAccessibleName(tr(name))
            field.setFixedSize(180, 28)
            form.addWidget(label, row, 1, QtCore.Qt.AlignVCenter)
            form.addWidget(field, row, 2, QtCore.Qt.AlignVCenter)
            self.field_labels[name] = label
        root.addWidget(self.options)
        self.mascot_preview = MascotStage(self.owner, self)
        self.mascot_preview.step_requested.connect(self.cycle_mascot)
        root.addWidget(self.mascot_preview, 1)

        self.custom_image_row = QtWidgets.QWidget()
        image_row = QtWidgets.QHBoxLayout(self.custom_image_row)
        image_row.setContentsMargins(0, 0, 0, 0)
        image_row.setSpacing(8)
        custom_button = QtWidgets.QToolButton()
        custom_button.setObjectName('assistantAppearance')
        custom_button.setText(tr('custom'))
        custom_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        custom_button.setIconSize(QtCore.QSize(20, 20))
        custom_button.setFixedHeight(28)
        custom_button.clicked.connect(self._choose_custom_image)
        self.appearance_buttons = {'custom': custom_button}
        image_row.addWidget(custom_button)
        self.custom_image_name = QtWidgets.QLabel()
        self.custom_image_name.setObjectName('assistantNote')
        self.custom_image_name.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        image_row.addWidget(self.custom_image_name, 1)
        self.replace_image = QtWidgets.QPushButton(tr('change_image'))
        self.replace_image.setFixedHeight(28)
        self.replace_image.clicked.connect(self._choose_custom_image)
        image_row.addWidget(self.replace_image)
        root.addWidget(self.custom_image_row)

        footer = QtWidgets.QHBoxLayout()
        footer.setSpacing(8)
        self.action_buttons = {}
        home = QtWidgets.QPushButton(tr('home'))
        home.setFixedHeight(30)
        home.clicked.connect(lambda: self.perform('home'))
        self.action_buttons['home'] = home
        footer.addWidget(home)
        footer.addStretch(1)
        self.dismiss_button = QtWidgets.QPushButton(tr('dismiss'))
        self.dismiss_button.setObjectName('desktopAssistantDismiss')
        self.dismiss_button.setFixedHeight(30)
        self.dismiss_button.setToolTip(tr('dismiss_hint'))
        self.dismiss_button.clicked.connect(settings._dismiss_desktop_assistant_until_restart)
        footer.addWidget(self.dismiss_button)
        root.addLayout(footer)
        self.toggle.toggled.connect(settings._set_desktop_assistant_enabled)
        self.main_visible.toggled.connect(self.owner.set_main_assistant_visible)
        self.topmost.toggled.connect(lambda checked: self.save('topmost', checked))
        self.refresh()

    def choose_appearance(self, appearance):
        appearance = LEGACY_APPEARANCES.get(appearance, appearance)
        if appearance == 'custom':
            filename = self.owner.config.get('desktop_assistant_image', '')
            if not filename:
                self._choose_custom_image()
                return
            if not self._validate_custom_image(filename):
                return
        self.owner.config['desktop_assistant_behavior'] = 'idle'
        self.save('appearance', appearance)
        self.refresh()

    def cycle_mascot(self, direction):
        current = assistant_preferences(self.owner.config)['desktop_assistant_mascot']
        self.choose_mascot(MASCOTS[(MASCOTS.index(current) + direction) % len(MASCOTS)])

    def choose_mascot(self, mascot):
        # Selecting a character also leaves a custom image, while preserving
        # the selected built-in pose.
        if self.owner.config.get('desktop_assistant_appearance') == 'custom':
            self.owner.config['desktop_assistant_appearance'] = 'portrait'
        self.save('mascot', mascot_id(mascot))
        self.refresh()
        from assistant_motion import play_reaction
        play_reaction(self.owner, 'waving')

    def _validate_custom_image(self, filename):
        from assistant_art import ImageLoadError, load_custom_art
        from styled_dialogs import StyledMessageBox
        from ui_scaling import native_window_parent
        try:
            load_custom_art(filename)
        except ImageLoadError as error:
            reason = assistant_text(self.language, error.reason).format(**error.details)
            StyledMessageBox.warning(native_window_parent(self), assistant_text(self.language, 'choose_image'),
                assistant_text(self.language, 'image_failed').format(name=Path(filename).name, reason=reason))
            self.refresh()
            return False
        return True

    def _choose_custom_image(self):
        from ui_scaling import native_window_parent
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            native_window_parent(self), assistant_text(self.language, 'choose_image'),
            self.owner.config.get('desktop_assistant_image', ''),
            'Images (*.png *.jpg *.jpeg *.webp *.bmp)')
        if not filename or not self._validate_custom_image(filename):
            self.refresh()
            return
        self.owner.config['desktop_assistant_image'] = filename
        self.choose_appearance('custom')

    def save(self, key, value):
        self.owner.config['desktop_assistant_' + key] = value
        self.owner.save_config()
        self.mascot_preview.motion.reactions = assistant_preferences(self.owner.config)['desktop_assistant_reactions']
        self.mascot_preview.update()
        helper = getattr(self.owner, '_desktop_assistant', None)
        if helper is not None and not sip.isdeleted(helper):
            helper.refresh()
        preview = getattr(self.owner, 'assistant_preview', None)
        if preview is not None and not sip.isdeleted(preview):
            preview.set_mascot(assistant_preferences(self.owner.config)['desktop_assistant_mascot'])
            preview.set_reactions(assistant_preferences(self.owner.config)['desktop_assistant_reactions'])
        if key in ('size', 'opacity', 'topmost'):
            from assistant_motion import play_reaction
            play_reaction(self.owner, 'review')

    def perform(self, action):
        helper = getattr(self.owner, '_desktop_assistant', None)
        if helper is not None:
            helper.request_action(action)

    def refresh_custom_icon(self):
        from settings_window import modern_combo_style
        from styled_dialogs import set_widget_stylesheet
        self.appearance_buttons['custom'].setIcon(header_icon('image_add', self.owner.current_theme))
        for combo in (self.mode_combo,):
            set_widget_stylesheet(combo, modern_combo_style(self.owner.current_theme != 'Светлая', 14))

    def refresh(self):
        values = assistant_preferences(self.owner.config)
        enabled = (self.owner.config.get('desktop_assistant_enabled') is True
                   and not getattr(self.owner, '_desktop_assistant_suppressed_until_restart', False))
        self.dismiss_button.setEnabled(enabled)
        self.action_buttons['home'].setEnabled(enabled)
        for widget, value in ((self.toggle, enabled), (self.topmost, values['desktop_assistant_topmost']),
                              (self.main_visible, self.owner.config.get('main_assistant_visible', True) is True)):
            with QtCore.QSignalBlocker(widget):
                widget.setChecked(value)
        for key, field in self.values.items():
            with QtCore.QSignalBlocker(field):
                field.setValue(values['desktop_assistant_' + key])
        with QtCore.QSignalBlocker(self.reactions):
            self.reactions.setChecked(values['desktop_assistant_reactions'])
        appearance = values['desktop_assistant_appearance']
        mascot = values['desktop_assistant_mascot']
        mode = appearance if appearance in ('animated', 'custom') else 'portrait'
        with QtCore.QSignalBlocker(self.mode_combo):
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(mode))
        self.mascot_preview.configure(mascot, appearance, values['desktop_assistant_image'])
        self.refresh_custom_icon()
        filename = values['desktop_assistant_image']
        self.custom_image_name.setText(self.custom_image_name.fontMetrics().elidedText(
            Path(filename).name if filename else '', QtCore.Qt.ElideMiddle, 190))
        self.custom_image_name.setToolTip(filename)
        self.custom_image_row.setVisible(mode == 'custom')
        self.replace_image.setVisible(bool(filename))
