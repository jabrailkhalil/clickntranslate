"""Arrange program and translation preferences in the fixed settings viewport."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QHBoxLayout, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)


CAPTIONS = {
    'en': ('Translation and OCR', 'OCR options', 'Quick translation'),
    'ru': ('Перевод и OCR', 'Параметры OCR', 'Быстрый перевод'),
    'es': ('Traducción y OCR', 'Opciones de OCR', 'Traducción rápida'),
    'de': ('Übersetzung und OCR', 'OCR-Optionen', 'Schnellübersetzung'),
    'fr': ('Traduction et OCR', 'Options OCR', 'Traduction rapide'),
    'zh': ('翻译与 OCR', 'OCR 选项', '快速翻译'),
}

COMPACT = {
    'en': ('Restore clipboard', 'Close result on outside click', 'Quick selection translation',
           'Show a button', 'Translate now'),
    'ru': ('Сохранять буфер обмена', 'Закрывать результат кликом снаружи', 'Быстрый перевод выделения',
           'Кнопка у текста', 'Сразу'),
    'es': ('Restaurar portapapeles', 'Cerrar resultado al pulsar fuera', 'Traducción rápida de selección',
           'Mostrar botón', 'Traducir ahora'),
    'de': ('Zwischenablage erhalten', 'Ergebnis bei Außenklick schließen', 'Auswahl schnell übersetzen',
           'Mit Schaltfläche', 'Sofort übersetzen'),
    'fr': ('Restaurer le presse-papiers', 'Fermer le résultat au clic extérieur', 'Traduction rapide de sélection',
           'Bouton de texte', 'Traduire aussitôt'),
    'zh': ('恢复剪贴板', '点击外部关闭结果', '快速翻译选中文本', '显示按钮', '立即翻译'),
}


def organize(settings, general_layout, form, updates_layout, dim_row):
    from settings_window import DropDownCombo, settings_text
    from styled_dialogs import tooltip_text, install_accent_controls

    lang = settings.parent.current_interface_language
    captions = CAPTIONS.get(lang, CAPTIONS['en'])
    compact = COMPACT.get(lang, COMPACT['en'])
    # Detach layout items, retaining the existing controls and their signals.
    while form.count():
        form.takeAt(0)
    while updates_layout.count():
        updates_layout.takeAt(0)
    general = settings.settings_general_page
    program_flags = (
        settings.autostart_checkbox, settings.start_minimized_checkbox,
        settings.button_tooltips_checkbox, settings.update_check_on_launch_checkbox,
    )
    for row, flag in enumerate(program_flags):
        flag.setParent(general)
        flag.setObjectName('settingsPageCheckbox')
        form.addWidget(flag, row, 0, Qt.AlignLeft)
    for control in (settings.ui_scale_label, settings.ui_scale_control):
        control.setParent(general)
    form.addWidget(settings.ui_scale_label, 0, 1)
    form.addWidget(settings.ui_scale_control, 0, 2)
    # Program maintenance and shortcuts stay on the program page.
    action_grid = settings.settings_action_panel.layout()
    for button in (settings.ocr_languages_btn, settings.copy_history_btn,
                   settings.translation_history_btn):
        action_grid.removeWidget(button)
    for column, button in enumerate((settings.export_settings_btn,
                                    settings.import_settings_btn,
                                    settings.create_bug_report_btn)):
        button.setParent(settings.settings_action_panel)
        action_grid.addWidget(button, 1, column)
    settings.settings_transfer_panel.hide()

    # A real scroll viewport is the fallback for long translations, fonts and
    # expanded OCR options. No control is laid out behind the action panel.
    scroll = QScrollArea(settings.settings_updates_page)
    scroll.setObjectName('translationSettingsScroll')
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    content = QWidget()
    content.setObjectName('translationSettingsContent')
    body = QVBoxLayout(content)
    body.setContentsMargins(0, 0, 8, 0)
    body.setSpacing(4)
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(2)
    grid.setColumnStretch(0, 1)
    body.addLayout(grid)
    settings.translation_settings_grid = grid
    flags = (
        settings.copy_translated_checkbox, settings.copy_history_checkbox,
        settings.history_checkbox, settings.replace_select_all_checkbox,
        settings.restore_clipboard_checkbox,
    )
    for row, flag in enumerate(flags):
        flag.setParent(content)
        flag.setObjectName('settingsPageCheckbox')
        grid.addWidget(flag, row, 0, Qt.AlignLeft)
    settings.close_result_on_outside_click_checkbox = QCheckBox(
        settings_text(lang, 'close_result_window_on_outside_click'), content)
    close_flag = settings.close_result_on_outside_click_checkbox
    close_flag.setText(compact[1])
    close_flag.setChecked(settings.parent.config.get('close_result_window_on_outside_click') is True)
    close_flag.setToolTip(tooltip_text(settings_text(lang, 'close_result_window_on_outside_click_tooltip')))
    close_flag.toggled.connect(lambda checked: settings.auto_save_setting(
        'close_result_window_on_outside_click', bool(checked)))
    settings.selection_quick_translate_checkbox = QCheckBox(
        settings_text(lang, 'selection_quick_translate_enabled'), content)
    quick_flag = settings.selection_quick_translate_checkbox
    quick_flag.setText(compact[2])
    settings.restore_clipboard_checkbox.setText(compact[0])
    quick_flag.setChecked(settings.parent.config.get('selection_quick_translate_enabled') is True)
    quick_flag.setToolTip(tooltip_text(settings_text(lang, 'selection_quick_translate_tooltip')))
    for row, flag in ((5, close_flag), (6, quick_flag)):
        flag.setObjectName('settingsPageCheckbox')
        flag.setFixedHeight(28)
        grid.addWidget(flag, row, 0, Qt.AlignLeft)
    settings.selection_quick_translate_mode_combo = DropDownCombo(content)
    mode = settings.selection_quick_translate_mode_combo
    mode.addItem(compact[3], 'button')
    mode.addItem(compact[4], 'automatic')
    for index, key in enumerate(('selection_quick_translate_mode_button', 'selection_quick_translate_mode_automatic')):
        mode.setItemData(index, tooltip_text(settings_text(lang, key)), Qt.ToolTipRole)
    mode.setCurrentIndex(max(0, mode.findData(settings.parent.config.get('selection_quick_translate_mode', 'button'))))
    mode.setFixedSize(180, 28)
    mode.setAccessibleName(captions[2])
    mode.setToolTip(quick_flag.toolTip())
    settings._apply_engine_combo_style(mode)
    mode.setEnabled(quick_flag.isChecked())
    mode.currentIndexChanged.connect(lambda _index: settings._set_selection_quick_translate_mode(mode.currentData()))
    quick_flag.toggled.connect(settings._set_selection_quick_translate_enabled)
    grid.addWidget(mode, 6, 2)
    for row, label, control in (
        (0, settings.ocr_engine_label, settings.ocr_engine_combo),
        (1, settings.translator_engine_label, settings.translator_combo),
        (2, settings.result_window_label, settings.result_window_control),
        (3, settings.translation_font_label, settings.translation_font_control),
    ):
        for widget in (label, control):
            widget.setParent(content)
        grid.addWidget(label, row, 1)
        grid.addWidget(control, row, 2)
    settings.translation_font_preview.setParent(content)
    grid.addWidget(settings.translation_font_preview, 4, 2, 2, 1, Qt.AlignVCenter)

    settings.translation_action_panel = QWidget(content)
    settings.translation_action_panel.setObjectName('settingsActionPanel')
    settings.translation_action_panel.setFixedHeight(31)
    tools = QHBoxLayout(settings.translation_action_panel)
    tools.setContentsMargins(1, 1, 1, 1)
    tools.setSpacing(0)
    for button in (settings.ocr_languages_btn, settings.copy_history_btn,
                   settings.translation_history_btn):
        button.setParent(settings.translation_action_panel)
        tools.addWidget(button, 1)
    body.addWidget(settings.translation_action_panel)
    settings.ocr_options_button = QPushButton(captions[1], content)
    settings.ocr_options_button.setCheckable(True)
    settings.ocr_options_button.setFixedHeight(28)
    body.addWidget(settings.ocr_options_button)
    settings.ocr_options_panel = QWidget(content)
    options = QVBoxLayout(settings.ocr_options_panel)
    options.setContentsMargins(0, 0, 0, 0)
    options.setSpacing(2)
    for flag in (settings.keep_visible_checkbox, settings.freeze_screen_checkbox):
        flag.setParent(settings.ocr_options_panel)
        options.addWidget(flag)
    options.addLayout(dim_row)
    settings.copy_notification_checkbox.setParent(settings.ocr_options_panel)
    options.addWidget(settings.copy_notification_checkbox)
    body.addWidget(settings.ocr_options_panel)
    settings.ocr_options_panel.hide()
    settings.ocr_options_button.toggled.connect(settings.ocr_options_panel.setVisible)
    body.addStretch(1)
    scroll.setWidget(content)
    scroll.viewport().setAutoFillBackground(False)
    updates_layout.addWidget(scroll)
    settings.translation_settings_scroll = scroll
    # Plain container backgrounds follow the same palette as the other pages.
    scroll.setStyleSheet('QScrollArea, QWidget#translationSettingsContent { background: transparent; border: none; }')
    install_accent_controls(content, dark=settings.parent.current_theme != 'Светлая')
    settings.settings_page_tabs[1].setText(captions[0])
    settings.settings_page_tabs[1].setAccessibleName(captions[0])
    settings.settings_page_tabs[1].setToolTip(tooltip_text(captions[0]))


def reveal(settings, widget):
    """Keep guide links valid after moving controls to their actual category."""
    panel = getattr(settings, 'ocr_options_panel', None)
    if panel is not None and panel.isAncestorOf(widget):
        settings.ocr_options_button.setChecked(True)
    scroll = getattr(settings, 'translation_settings_scroll', None)
    if scroll is not None and scroll.widget().isAncestorOf(widget):
        settings._set_settings_page(1)
        scroll.ensureWidgetVisible(widget)
