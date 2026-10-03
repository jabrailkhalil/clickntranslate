"""Desktop companion preferences; independent of its enabled runtime instance."""
from PyQt5 import QtCore, QtGui, QtWidgets, sip

from assistant_text import assistant_text
from assistant_art import APPEARANCES, MASCOTS, DEFAULT_MASCOT, companion_art, mascot_id
from header_icons import header_icon
from pathlib import Path


from number_controls import NumberStepper as AssistantNumberBox


BEHAVIORS = ('idle', 'walk')
ASSISTANT_DEFAULTS = {
    'main_assistant_visible': True,
    'desktop_assistant_behavior': 'idle',
    'desktop_assistant_size': 100,
    'desktop_assistant_speed': 40,
    'desktop_assistant_opacity': 100,
    'desktop_assistant_topmost': True,
    'desktop_assistant_appearance': 'portrait',
    'desktop_assistant_mascot': DEFAULT_MASCOT,
    'desktop_assistant_reactions': True,
    'desktop_assistant_image': '',
}


def assistant_preferences(config):
    values = {key: config.get(key, default) for key, default in ASSISTANT_DEFAULTS.items()}
    # Preserve older choices without mixing static art with a walking sprite.
    if values['desktop_assistant_appearance'] == 'animated':
        values['desktop_assistant_appearance'] = {
            'walk': 'walking', 'sleep': 'sleep_icon', 'look': 'portrait', 'idle': 'portrait',
        }.get(str(values['desktop_assistant_behavior']), 'portrait')
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
    values['desktop_assistant_mascot'] = mascot_id(values['desktop_assistant_mascot'])
    values['desktop_assistant_reactions'] = values['desktop_assistant_reactions'] is True
    if values['desktop_assistant_appearance'] not in APPEARANCES:
        values['desktop_assistant_appearance'] = ASSISTANT_DEFAULTS['desktop_assistant_appearance']
    if not isinstance(values['desktop_assistant_image'], str):
        values['desktop_assistant_image'] = ''
    return values


class AssistantSettingsPage(QtWidgets.QWidget):
    """Grouped visibility controls and a two-step companion artwork picker."""
    def __init__(self, settings):
        super().__init__(settings)
        self.settings = settings
        self.owner = settings.parent
        self.language = self.owner.current_interface_language
        self._category = None
        self._last_appearance = None
        self._static_appearance = 'portrait'
        tr = lambda key: assistant_text(self.language, key)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 0, 6, 0)
        root.setSpacing(10)
        columns = QtWidgets.QHBoxLayout()
        columns.setSpacing(24)

        visibility = QtWidgets.QWidget()
        visibility.setObjectName('assistantVisibility')
        checks = QtWidgets.QGridLayout(visibility)
        checks.setContentsMargins(0, 0, 0, 0)
        checks.setHorizontalSpacing(24)
        checks.setVerticalSpacing(2)
        checks.setColumnStretch(0, 1)
        checks.setColumnStretch(1, 1)
        self.main_visible = QtWidgets.QCheckBox(tr('main_visible_short'))
        self.main_visible.setAccessibleName(tr('main_visible'))
        self.toggle = QtWidgets.QCheckBox(tr('enabled'))
        self.topmost = QtWidgets.QCheckBox(tr('topmost'))
        self.reactions = QtWidgets.QCheckBox(tr('reactions'))
        self.reactions.setToolTip(tr('reactions_hint'))
        self.reactions.toggled.connect(lambda checked: self.save('reactions', checked))
        for index, checkbox in enumerate((self.main_visible, self.toggle, self.topmost, self.reactions)):
            checkbox.setFixedHeight(26)
            checks.addWidget(checkbox, index // 2, index % 2)
        root.addWidget(visibility)

        character = QtWidgets.QWidget()
        character.setFixedWidth(210)
        identity = QtWidgets.QVBoxLayout(character)
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(6)
        from settings_window import DropDownCombo
        mascot_label = QtWidgets.QLabel(tr('mascot'))
        mascot_label.setObjectName('assistantFieldLabel')
        identity.addWidget(mascot_label)
        self.mascot_combo = DropDownCombo()
        self.mascot_combo.setObjectName('assistantMascot')
        self.mascot_combo.setAccessibleName(tr('mascot'))
        self.mascot_combo.setIconSize(QtCore.QSize(24, 24))
        self.mascot_combo.setFixedHeight(32)
        self.mascot_combo.setMaxVisibleItems(5)
        mascot_label.setBuddy(self.mascot_combo)
        for key in MASCOTS:
            self.mascot_combo.addItem(QtGui.QIcon(companion_art('portrait', mascot=key)), tr(key), key)
        self.mascot_combo.currentIndexChanged.connect(
            lambda: self.choose_mascot(self.mascot_combo.currentData()))
        identity.addWidget(self.mascot_combo)
        self.mascot_preview = QtWidgets.QLabel()
        self.mascot_preview.setObjectName('assistantMascotPreview')
        self.mascot_preview.setFixedHeight(116)
        self.mascot_preview.setAlignment(QtCore.Qt.AlignCenter)
        identity.addWidget(self.mascot_preview)
        identity.addStretch(1)
        columns.addWidget(character)

        self.options = QtWidgets.QWidget()
        self.options.setObjectName('assistantOptions')
        contents = QtWidgets.QVBoxLayout(self.options)
        contents.setContentsMargins(0, 0, 0, 0)
        contents.setSpacing(8)
        categories = QtWidgets.QHBoxLayout()
        categories.setSpacing(6)
        self.category_buttons = {}
        self.category_group = QtWidgets.QButtonGroup(self)
        self.category_group.setExclusive(True)
        for key in ('dynamic', 'static'):
            button = QtWidgets.QPushButton(tr('category_' + key))
            button.setObjectName('assistantCategory')
            button.setCheckable(True)
            button.setFixedHeight(28)
            button.clicked.connect(lambda checked=False, value=key: self.choose_category(value))
            self.category_group.addButton(button)
            self.category_buttons[key] = button
            categories.addWidget(button, 1)
        contents.addLayout(categories)

        self.appearance_buttons = {}
        self.galleries = {}
        self.appearance_group = QtWidgets.QButtonGroup(self)
        self.appearance_group.setExclusive(True)
        static_gallery = QtWidgets.QWidget()
        static_layout = QtWidgets.QVBoxLayout(static_gallery)
        static_layout.setContentsMargins(0, 0, 0, 0)
        self.pose_combo = DropDownCombo()
        self.pose_combo.setObjectName('assistantPose')
        self.pose_combo.setAccessibleName(tr('emotion'))
        self.pose_combo.setFixedHeight(36)
        self.pose_combo.setIconSize(QtCore.QSize(26, 26))
        self.pose_combo.setMaxVisibleItems(7)
        for key in APPEARANCES:
            if key not in ('walking', 'custom'):
                self.pose_combo.addItem(QtGui.QIcon(companion_art(key)), tr(key), key)
        self.pose_combo.currentIndexChanged.connect(lambda: self.choose_appearance(self.pose_combo.currentData()))
        # Activating the already-selected first item must also leave walking/custom.
        self.pose_combo.activated.connect(lambda: self.choose_appearance(self.pose_combo.currentData())
            if self.owner.config.get('desktop_assistant_appearance') != self.pose_combo.currentData() else None)
        static_layout.addWidget(self.pose_combo)
        contents.addWidget(static_gallery)
        self.galleries['static'] = static_gallery
        self.custom_image_row = QtWidgets.QWidget()
        image_row = QtWidgets.QHBoxLayout(self.custom_image_row)
        image_row.setContentsMargins(0, 0, 0, 0)
        image_row.setSpacing(8)
        custom_button = QtWidgets.QToolButton()
        custom_button.setObjectName('assistantAppearance')
        custom_button.setText(tr('custom'))
        custom_button.setAccessibleName(tr('custom'))
        custom_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        custom_button.setIconSize(QtCore.QSize(20, 20))
        custom_button.setFixedHeight(28)
        custom_button.setCheckable(True)
        custom_button.clicked.connect(lambda: self.choose_appearance('custom'))
        self.appearance_group.addButton(custom_button)
        self.appearance_buttons['custom'] = custom_button
        image_row.addWidget(custom_button)
        self.custom_image_name = QtWidgets.QLabel()
        self.custom_image_name.setObjectName('assistantNote')
        self.custom_image_name.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        image_row.addWidget(self.custom_image_name, 1)
        self.replace_image = QtWidgets.QPushButton(tr('change_image'))
        self.replace_image.setFixedHeight(28)
        self.replace_image.clicked.connect(self._choose_custom_image)
        image_row.addWidget(self.replace_image)
        contents.addWidget(self.custom_image_row)

        self.values = {}
        for key, low, high, suffix in (('size', 60, 180, '%'), ('opacity', 40, 100, '%'), ('speed', 20, 100, '')):
            field = AssistantNumberBox(dark=self.owner.current_theme != 'Светлая')
            field.setRange(low, high)
            field.setSuffix(suffix)
            field.setFixedHeight(28)
            field.setKeyboardTracking(False)
            field.setAccessibleName(tr(key))
            field.setToolTip(f'{tr(key)}: {low}–{high}{suffix}')
            field.valueChanged.connect(lambda value, name=key: self.save(name, value))
            self.values[key] = field
        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(2)
        for column, key in enumerate(('size', 'opacity')):
            label = QtWidgets.QLabel(tr(key))
            label.setObjectName('assistantFieldLabel')
            label.setBuddy(self.values[key])
            form.addWidget(label, 0, column)
            form.addWidget(self.values[key], 1, column)
            form.setColumnStretch(column, 1)
        contents.addLayout(form)
        self.motion_options = QtWidgets.QWidget()
        motion = QtWidgets.QGridLayout(self.motion_options)
        motion.setContentsMargins(0, 0, 0, 0)
        motion.setHorizontalSpacing(8)
        motion.setVerticalSpacing(2)
        motion.setColumnStretch(0, 1)
        motion.setColumnStretch(1, 1)
        speed_label = QtWidgets.QLabel(tr('speed_short'))
        speed_label.setObjectName('assistantFieldLabel')
        speed_label.setBuddy(self.values['speed'])
        motion.addWidget(speed_label, 0, 0)
        motion.addWidget(self.values['speed'], 1, 0)
        self.pause_walk = QtWidgets.QCheckBox(tr('pause_walk'))
        self.pause_walk.setToolTip(tr('walking_hint'))
        self.pause_walk.toggled.connect(lambda paused: self.save('behavior', 'idle' if paused else 'walk'))
        motion.addWidget(self.pause_walk, 1, 1)
        contents.addWidget(self.motion_options)
        contents.addStretch(1)
        columns.addWidget(self.options, 1)
        root.addLayout(columns, 1)

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

    def choose_category(self, category):
        appearance = assistant_preferences(self.owner.config)['desktop_assistant_appearance']
        if category == 'dynamic' and appearance != 'walking':
            self.choose_appearance('walking')
        elif category == 'static' and appearance == 'walking':
            self.choose_appearance(self._static_appearance)
        else:
            self.show_category(category)

    def show_category(self, category):
        self._category = category
        self.category_buttons[category].setChecked(True)
        for key, gallery in self.galleries.items():
            gallery.setVisible(key == category)
        walking = assistant_preferences(self.owner.config)['desktop_assistant_appearance'] == 'walking'
        self.motion_options.setVisible(category == 'dynamic' and walking)
        self.custom_image_row.setVisible(category == 'static')
        self.replace_image.setVisible(bool(self.owner.config.get('desktop_assistant_image')))

    def choose_appearance(self, appearance):
        if appearance == 'custom':
            filename = self.owner.config.get('desktop_assistant_image', '')
            if not filename:
                self._choose_custom_image()
                return
            if not self._validate_custom_image(filename):
                return
        self.owner.config['desktop_assistant_behavior'] = 'walk' if appearance == 'walking' else 'idle'
        self._category = 'dynamic' if appearance == 'walking' else 'static'
        self.save('appearance', appearance)
        self.refresh()

    def choose_mascot(self, mascot):
        # Selecting a character also leaves a custom image, while preserving
        # any pose and walking pause chosen for a built-in character.
        if self.owner.config.get('desktop_assistant_appearance') == 'custom':
            self.owner.config['desktop_assistant_appearance'] = 'portrait'
        self.save('mascot', mascot_id(mascot))
        self.refresh()

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
        helper = getattr(self.owner, '_desktop_assistant', None)
        if helper is not None and not sip.isdeleted(helper):
            helper.refresh()
        preview = getattr(self.owner, 'assistant_preview', None)
        if preview is not None and not sip.isdeleted(preview):
            preview.set_mascot(assistant_preferences(self.owner.config)['desktop_assistant_mascot'])
            preview.motion.reactions = assistant_preferences(self.owner.config)['desktop_assistant_reactions']

    def perform(self, action):
        helper = getattr(self.owner, '_desktop_assistant', None)
        if helper is not None:
            helper.request_action(action)

    def refresh_custom_icon(self):
        from settings_window import modern_combo_style
        from styled_dialogs import set_widget_stylesheet
        self.appearance_buttons['custom'].setIcon(header_icon('image_add', self.owner.current_theme))
        for combo in (self.mascot_combo, self.pose_combo):
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
        with QtCore.QSignalBlocker(self.pause_walk):
            self.pause_walk.setChecked(values['desktop_assistant_behavior'] != 'walk')
        with QtCore.QSignalBlocker(self.reactions):
            self.reactions.setChecked(values['desktop_assistant_reactions'])
        appearance = values['desktop_assistant_appearance']
        if appearance != 'walking':
            self._static_appearance = appearance
        mascot = values['desktop_assistant_mascot']
        with QtCore.QSignalBlocker(self.mascot_combo):
            self.mascot_combo.setCurrentIndex(self.mascot_combo.findData(mascot))
        if appearance not in ('walking', 'custom'):
            with QtCore.QSignalBlocker(self.pose_combo):
                self.pose_combo.setCurrentIndex(max(0, self.pose_combo.findData(appearance)))
        for index in range(self.pose_combo.count()):
            self.pose_combo.setItemIcon(index, QtGui.QIcon(companion_art(self.pose_combo.itemData(index), mascot=mascot)))
        self.mascot_preview.setPixmap(companion_art(appearance, values['desktop_assistant_image'], mascot=mascot).scaled(
            104, 104, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        for key, button in self.appearance_buttons.items():
            button.setChecked(key == appearance)
            if key != 'custom':
                button.setIcon(QtGui.QIcon(companion_art(key, mascot=mascot)))
        self.refresh_custom_icon()
        filename = values['desktop_assistant_image']
        self.custom_image_name.setText(self.custom_image_name.fontMetrics().elidedText(
            Path(filename).name if filename else '', QtCore.Qt.ElideMiddle, 190))
        self.custom_image_name.setToolTip(filename)
        if self._category is None or appearance != self._last_appearance:
            self._category = 'dynamic' if appearance == 'walking' else 'static'
        self._last_appearance = appearance
        self.show_category(self._category)
