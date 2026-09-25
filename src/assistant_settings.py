"""Desktop companion preferences; independent of its enabled runtime instance."""
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_text import assistant_text
from assistant_art import APPEARANCES, companion_art
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


class AssistantSettingsPage(QtWidgets.QWidget):
    """Grouped visibility controls and a two-step companion artwork picker."""
    def __init__(self, settings):
        super().__init__(settings)
        self.settings = settings
        self.owner = settings.parent
        self.language = self.owner.current_interface_language
        self._category = None
        self._last_appearance = None
        tr = lambda key: assistant_text(self.language, key)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 0, 6, 0)
        root.setSpacing(8)
        columns = QtWidgets.QHBoxLayout()
        columns.setSpacing(18)

        visibility = QtWidgets.QWidget()
        visibility.setFixedWidth(220)
        visibility.setObjectName('assistantVisibility')
        checks = QtWidgets.QVBoxLayout(visibility)
        checks.setContentsMargins(0, 0, 0, 0)
        checks.setSpacing(2)
        self.main_visible = QtWidgets.QCheckBox(tr('main_visible_short'))
        self.main_visible.setAccessibleName(tr('main_visible'))
        self.toggle = QtWidgets.QCheckBox(tr('enabled'))
        self.topmost = QtWidgets.QCheckBox(tr('topmost'))
        for checkbox in (self.main_visible, self.toggle, self.topmost):
            checkbox.setFixedHeight(28)
            checks.addWidget(checkbox)
        checks.addStretch(1)
        columns.addWidget(visibility)

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
            button.clicked.connect(lambda checked=False, value=key: self.show_category(value))
            self.category_group.addButton(button)
            self.category_buttons[key] = button
            categories.addWidget(button, 1)
        contents.addLayout(categories)

        self.appearance_buttons = {}
        self.galleries = {}
        self.appearance_group = QtWidgets.QButtonGroup(self)
        self.appearance_group.setExclusive(True)
        for category, appearances in (
                ('dynamic', ('walking',)),
                ('static', tuple(key for key in APPEARANCES if key != 'walking'))):
            gallery = QtWidgets.QWidget()
            grid = QtWidgets.QGridLayout(gallery)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(6)
            for column in range(3):
                grid.setColumnStretch(column, 1)
            for index, key in enumerate(appearances):
                button = QtWidgets.QToolButton()
                button.setObjectName('assistantAppearance')
                button.setText(tr(key))
                button.setAccessibleName(tr(key))
                button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
                button.setIcon(header_icon('image_add', self.owner.current_theme) if key == 'custom'
                               else QtGui.QIcon(companion_art(key)))
                button.setIconSize(QtCore.QSize(30, 30))
                button.setFixedHeight(58)
                button.setMinimumWidth(0)
                button.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
                button.setCheckable(True)
                button.clicked.connect(lambda checked=False, value=key: self.choose_appearance(value))
                self.appearance_group.addButton(button)
                self.appearance_buttons[key] = button
                grid.addWidget(button, index // 3, index % 3)
            self.galleries[category] = gallery
            contents.addWidget(gallery)

        self.custom_image_row = QtWidgets.QWidget()
        image_row = QtWidgets.QHBoxLayout(self.custom_image_row)
        image_row.setContentsMargins(0, 0, 0, 0)
        image_row.setSpacing(8)
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

    def show_category(self, category):
        # Browsing a type never silently changes the saved desktop companion.
        self._category = category
        self.category_buttons[category].setChecked(True)
        for key, gallery in self.galleries.items():
            gallery.setVisible(key == category)
        walking = assistant_preferences(self.owner.config)['desktop_assistant_appearance'] == 'walking'
        for key in ('size', 'opacity'):
            self.values[key].setEnabled((category == 'dynamic') == walking)
        self.motion_options.setVisible(category == 'dynamic' and walking)
        self.custom_image_row.setVisible(category == 'static' and bool(self.owner.config.get('desktop_assistant_image')))

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
        if helper is not None:
            helper.refresh()

    def perform(self, action):
        helper = getattr(self.owner, '_desktop_assistant', None)
        if helper is not None:
            helper.request_action(action)

    def refresh_custom_icon(self):
        self.appearance_buttons['custom'].setIcon(header_icon('image_add', self.owner.current_theme))

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
        appearance = values['desktop_assistant_appearance']
        for key, button in self.appearance_buttons.items():
            button.setChecked(key == appearance)
        self.refresh_custom_icon()
        filename = values['desktop_assistant_image']
        self.custom_image_name.setText(self.custom_image_name.fontMetrics().elidedText(
            Path(filename).name if filename else '', QtCore.Qt.ElideMiddle, 190))
        self.custom_image_name.setToolTip(filename)
        if self._category is None or appearance != self._last_appearance:
            self._category = 'dynamic' if appearance == 'walking' else 'static'
        self._last_appearance = appearance
        self.show_category(self._category)
