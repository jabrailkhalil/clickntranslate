"""Desktop companion preferences; independent of its enabled runtime instance."""
from PyQt5 import QtCore, QtWidgets, sip

from assistant_text import assistant_text
from assistant_art import APPEARANCES, LEGACY_APPEARANCES, MASCOTS, DEFAULT_MASCOT, mascot_id
from header_icons import header_icon
from control_hints import control_hint
from styled_dialogs import CenteredFramelessDialog
from settings_metrics import SETTINGS_ROW_GAP, SETTINGS_ROW_HEIGHT
from pathlib import Path


from number_controls import NumberStepper as AssistantNumberBox


BEHAVIORS = ('idle',)
ASSISTANT_ACTIONS = ('open', 'area', 'screen', 'text', 'copy', 'dynamic', 'documents', 'guide')
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
    'desktop_assistant_actions': list(ASSISTANT_ACTIONS),
}


def normalized_assistant_actions(value):
    """Keep known IDs in one stable order; an empty selection is intentional."""
    if not isinstance(value, (tuple, list)):
        return list(ASSISTANT_ACTIONS)
    selected = {item for item in value if isinstance(item, str) and item in ASSISTANT_ACTIONS}
    return [action for action in ASSISTANT_ACTIONS if action in selected]


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
    values['desktop_assistant_actions'] = normalized_assistant_actions(values['desktop_assistant_actions'])
    return values


class AssistantActionsDialog(CenteredFramelessDialog):
    """Small, immediate preferences using the same shell as other dialogs."""
    actions_changed = QtCore.pyqtSignal(list)

    def __init__(self, owner):
        super().__init__(owner, drag_height=52)
        from assistant_text import assistant_action_text
        from button_styles import button_qss, standard_buttons
        from dialog_text import dialog_action_text
        from rounded_windows import clip_rounded_window
        from scrollbar_styles import scrollbar_stylesheet
        from styled_dialogs import install_accent_controls, tooltip_text
        from ui_scaling import interface_scale_factor
        from window_appearance import scale_native_controls
        from keyboard_navigation import install_keyboard_navigation
        from classic_style import classic_palette
        self.language = owner.current_interface_language
        tr = lambda key: assistant_text(self.language, key)
        dark = owner.current_theme != 'Светлая'
        self.setWindowTitle(tr('menu_buttons').rstrip('…'))
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setLayoutDirection(QtCore.Qt.RightToLeft if self.language == 'ar' else QtCore.Qt.LeftToRight)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QtWidgets.QFrame(self)
        surface.setObjectName('assistantActionsSurface')
        outer.addWidget(surface)
        panel = QtWidgets.QVBoxLayout(surface)
        panel.setContentsMargins(16, 14, 16, 14)
        panel.setSpacing(10)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(self.windowTitle())
        title.setObjectName('assistantActionsTitle')
        title.setWordWrap(True)
        header.addWidget(title, 1)
        self.close_button = QtWidgets.QToolButton()
        self.close_button.setText('×')
        self.close_button.setAccessibleName(dialog_action_text(self, 'Close'))
        self.close_button.setToolTip(self.close_button.accessibleName())
        self.close_button.setFixedSize(26, 26)
        self.close_button.setStyleSheet(button_qss(dark, 'close', 'QToolButton', icon=True))
        self.close_button.clicked.connect(self.reject)
        header.addWidget(self.close_button)
        panel.addLayout(header)
        description = QtWidgets.QLabel(tr('menu_buttons_hint'))
        description.setWordWrap(True)
        panel.addWidget(description)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(0)
        body = QtWidgets.QWidget()
        choices = QtWidgets.QVBoxLayout(body)
        choices.setContentsMargins(0, 0, 6, 0)
        choices.setSpacing(4)
        self.checkboxes = {}
        selected = assistant_preferences(owner.config)['desktop_assistant_actions']
        for action in ASSISTANT_ACTIONS:
            label, hint = assistant_action_text(self.language, action)
            checkbox = QtWidgets.QCheckBox(label)
            checkbox.setAccessibleName(label)
            checkbox.setAccessibleDescription(hint)
            checkbox.setToolTip(tooltip_text(hint))
            checkbox.setMinimumHeight(26)
            checkbox.setChecked(action in selected)
            checkbox.toggled.connect(self._emit_actions)
            choices.addWidget(checkbox)
            self.checkboxes[action] = checkbox
        choices.addStretch(1)
        self.scroll.setWidget(body)
        panel.addWidget(self.scroll, 1)
        self.note = QtWidgets.QLabel(tr('menu_buttons_note'))
        self.note.setWordWrap(True)
        self.note.setObjectName('assistantActionsNote')
        panel.addWidget(self.note)
        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        self.done_button = QtWidgets.QPushButton(dialog_action_text(self, 'Close'))
        self.done_button.setProperty('buttonRole', 'primary')
        self.done_button.setMinimumHeight(30)
        self.done_button.clicked.connect(self.accept)
        footer.addWidget(self.done_button)
        panel.addLayout(footer)
        palette = classic_palette(dark)
        background, ink, border, muted = (palette[key] for key in ('background', 'text', 'border', 'muted'))
        self.setStyleSheet(f'''
            QFrame#assistantActionsSurface {{ background:{background}; border:1px solid {border}; border-radius:8px; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background:transparent; border:0; }}
            QLabel, QCheckBox {{ color:{ink}; background:transparent; border:0; font-size:14px; }}
            QLabel#assistantActionsTitle {{ font-size:16px; font-weight:600; }}
            QLabel#assistantActionsNote {{ color:{muted}; font-size:12px; }}
            QCheckBox {{ spacing:8px; }}
            QCheckBox::indicator {{ width:18px; height:18px; }}
        ''' + standard_buttons(dark, compact=True) + scrollbar_stylesheet())
        self.scroll.verticalScrollBar().setProperty('_cntScrollDark', dark)
        install_accent_controls(self, dark)
        clip_rounded_window(self, surface, 8)
        bounds = owner.screen().availableGeometry()
        factor = min(interface_scale_factor(widget=owner), max(.5, (bounds.width()-32)/420))
        scale_native_controls(self, factor)
        self.setMinimumWidth(round(360*factor))
        self.resize(min(round(420*factor), bounds.width()-32), min(round(420*factor), bounds.height()-32))
        install_keyboard_navigation()

    def _emit_actions(self):
        self.actions_changed.emit([action for action, checkbox in self.checkboxes.items() if checkbox.isChecked()])

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._focus_first_action)

    def _focus_first_action(self):
        if sip.isdeleted(self) or not self.isVisible():
            return
        navigation = getattr(QtWidgets.QApplication.instance(), '_keyboard_navigation', None)
        if navigation is not None and navigation.keyboard:
            from keyboard_navigation import focus_control
            focus_control(self.checkboxes['open'])
        else:
            self.checkboxes['open'].setFocus(QtCore.Qt.OtherFocusReason)


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
        form.setVerticalSpacing(SETTINGS_ROW_GAP)
        form.setColumnStretch(0, 1)
        self.form_grid = form
        self.main_visible = QtWidgets.QCheckBox(tr('main_visible_short'))
        self.main_visible.setAccessibleName(tr('main_visible'))
        self.toggle = QtWidgets.QCheckBox(tr('enabled'))
        self.topmost = QtWidgets.QCheckBox(tr('topmost'))
        for control, key in ((self.main_visible, 'desktop_main'), (self.toggle, 'desktop_enabled'),
                             (self.topmost, 'desktop_topmost')):
            control.setToolTip(control_hint(self.language, key))
        self.reactions = QtWidgets.QCheckBox(tr('reactions'))
        self.reactions.setToolTip(tr('reactions_hint'))
        self.reactions.toggled.connect(lambda checked: self.save('reactions', checked))
        for row, checkbox in enumerate((self.main_visible, self.toggle, self.topmost, self.reactions)):
            checkbox.setFixedHeight(SETTINGS_ROW_HEIGHT)
            checkbox.setStyleSheet('margin:0; padding:0;')
            form.addWidget(checkbox, row, 0)

        self.mode_combo = DropDownCombo()
        self.mode_combo.setObjectName('assistantDisplayMode')
        for value, label in (('animated', 'mode_animated'), ('portrait', 'mode_static'), ('custom', 'custom')):
            self.mode_combo.addItem(tr(label), value)
        self.mode_combo.setToolTip(tr('display_mode_hint'))
        self.mode_combo.currentIndexChanged.connect(lambda: self.choose_appearance(self.mode_combo.currentData()))
        self.values = {}
        for key, low, high in (('size', 60, 180), ('opacity', 40, 100)):
            field = AssistantNumberBox(dark=self.owner.current_theme != 'Светлая', font_size=14)
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
            label.setFixedHeight(SETTINGS_ROW_HEIGHT)
            label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            label.setStyleSheet('margin:0; padding:0; font-size:14px;')
            label.setBuddy(field)
            label.setToolTip(field.toolTip())
            field.setAccessibleName(tr(name))
            if name in ('size', 'opacity'):
                for button, direction in ((field.decrease, 'decrease'), (field.increase, 'increase')):
                    hint = tr(name + '_' + direction)
                    button.setToolTip(hint)
                    button.setAccessibleName(hint)
            field.setFixedSize(180, SETTINGS_ROW_HEIGHT)
            form.addWidget(label, row, 1, QtCore.Qt.AlignVCenter)
            form.addWidget(field, row, 2, QtCore.Qt.AlignVCenter)
            self.field_labels[name] = label
        self.menu_buttons = QtWidgets.QPushButton(tr('menu_buttons'))
        self.menu_buttons.setObjectName('assistantMenuButton')
        self.menu_buttons.setProperty('buttonRole', 'secondary')
        self.menu_buttons.setFixedHeight(32)
        self.menu_buttons.setMinimumWidth(0)
        self.menu_buttons.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.menu_buttons.setToolTip(tr('menu_buttons_hint'))
        self.menu_buttons.setAccessibleName(tr('menu_buttons'))
        self.menu_buttons.setAccessibleDescription(tr('menu_buttons_hint'))
        self.menu_buttons.clicked.connect(self.configure_menu)
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
        custom_button.setToolTip(tr('choose_image'))
        custom_button.setAccessibleName(tr('choose_image'))
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
        self.replace_image.setToolTip(tr('choose_image'))
        self.replace_image.setFixedHeight(28)
        self.replace_image.clicked.connect(self._choose_custom_image)
        image_row.addWidget(self.replace_image)
        root.addWidget(self.custom_image_row)

        root.addWidget(self.menu_buttons)
        self.toggle.toggled.connect(settings._set_desktop_assistant_enabled)
        self.main_visible.toggled.connect(self.owner.set_main_assistant_visible)
        self.topmost.toggled.connect(lambda checked: self.save('topmost', checked))
        self.refresh()

    def configure_menu(self):
        dialog = getattr(self, '_actions_dialog', None)
        if dialog is not None and not sip.isdeleted(dialog):
            dialog.raise_()
            dialog.activateWindow()
            return
        dialog = self._actions_dialog = AssistantActionsDialog(self.owner)
        dialog.actions_changed.connect(lambda actions: self.save('actions', actions))
        dialog.finished.connect(lambda _result: self._close_actions_dialog(dialog))
        dialog.open()

    def _close_actions_dialog(self, dialog):
        self._actions_dialog = None
        dialog.deleteLater()

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
            f"{assistant_text(self.language, 'image_files')} (*.png *.jpg *.jpeg *.webp *.bmp)")
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
        from settings_window import compact_combo_style
        from styled_dialogs import set_widget_stylesheet
        from button_styles import button_qss
        dark = self.owner.current_theme != 'Светлая'
        self.appearance_buttons['custom'].setIcon(header_icon('image_add', self.owner.current_theme))
        for combo in (self.mode_combo,):
            set_widget_stylesheet(combo, compact_combo_style(dark))
        surface = '#302938' if dark else '#e2d8ec'
        border = '#8c739f' if dark else '#927aa8'
        set_widget_stylesheet(self.menu_buttons,
            button_qss(dark, selector='QPushButton#assistantMenuButton', compact=True)
            + f'''QPushButton#assistantMenuButton {{ background:{surface}; border-color:{border};
                min-height:28px; min-width:142px; }}
                QPushButton#assistantMenuButton[pointerHover="false"]:hover {{ background:{surface}; }}''')

    def refresh(self):
        values = assistant_preferences(self.owner.config)
        enabled = (self.owner.config.get('desktop_assistant_enabled') is True
                   and not getattr(self.owner, '_desktop_assistant_suppressed_until_restart', False))
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
