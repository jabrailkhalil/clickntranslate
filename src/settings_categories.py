"""Arrange program and translation preferences in the fixed settings viewport."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QLabel,
    QScrollArea, QVBoxLayout, QWidget,
)


CAPTIONS = {
    'en': ('Translation and OCR', 'OCR options', 'Quick translation'),
    'ru': ('Перевод и OCR', 'Параметры OCR', 'Быстрый перевод'),
    'es': ('Traducción y OCR', 'Opciones de OCR', 'Traducción rápida'),
    'de': ('Übersetzung und OCR', 'OCR-Optionen', 'Schnellübersetzung'),
    'fr': ('Traduction et OCR', 'Options OCR', 'Traduction rapide'),
    'zh': ('翻译与 OCR', 'OCR 选项', '快速翻译'),

    'pt': ('Tradução e OCR', 'Opções de OCR', 'Tradução rápida'),
    'it': ('Traduzione e OCR', "Opzioni dell'OCR", 'Traduzione veloce'),
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

    'pt': ('Restaurar área de transferência',
     'Fechar resultado ao clicar fora',
     'Tradução de seleção rápida',
     'Mostrar um botão',
     'Traduzir agora'),
    'it': ('Ripristina appunti',
     'Chiudi risultato con clic esterno',
     'Traduzione di selezione rapida',
     'Mostra un pulsante',
     'Traduci adesso'),
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
        settings.copy_history_checkbox, settings.history_checkbox,
        settings.button_tooltips_checkbox, settings.update_check_on_launch_checkbox,
    )
    for row, flag in enumerate(program_flags):
        flag.setParent(general)
        flag.setObjectName('settingsPageCheckbox')
        form.addWidget(flag, row, 0, Qt.AlignLeft)
    for row, label, control in (
        (0, settings.result_window_label, settings.result_window_control),
        (1, settings.ui_scale_label, settings.ui_scale_control),
        (2, settings.translation_font_label, settings.translation_font_control),
    ):
        for widget in (label, control):
            widget.setParent(general)
        form.addWidget(label, row, 1)
        form.addWidget(control, row, 2)
    settings.translation_font_preview.setParent(general)
    form.addWidget(settings.translation_font_preview, 3, 2, 2, 1, Qt.AlignVCenter)
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
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(0)
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(1)
    grid.setColumnStretch(0, 1)
    body.addLayout(grid)
    settings.translation_settings_grid = grid
    flags = (
        settings.copy_translated_checkbox, settings.replace_select_all_checkbox,
        settings.restore_clipboard_checkbox,
    )
    settings.restore_clipboard_checkbox.setText(compact[0])
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
    close_flag.setObjectName('settingsPageCheckbox')
    close_flag.setFixedHeight(28)
    grid.addWidget(close_flag, 3, 0, 1, 3, Qt.AlignLeft)
    for row, label, control in (
        (0, settings.ocr_engine_label, settings.ocr_engine_combo),
        (1, settings.translator_engine_label, settings.translator_combo),
    ):
        for widget in (label, control):
            widget.setParent(content)
        grid.addWidget(label, row, 1)
        grid.addWidget(control, row, 2)
    settings.provider_routing_note = QLabel(content)
    settings.provider_routing_note.setObjectName('assistantNote')
    settings.provider_routing_note.setWordWrap(False)
    settings.provider_routing_note.setFixedHeight(28)
    settings.provider_routing_note.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    def open_image_api(_link):
        from api_providers import VISION_ENGINES
        from provider_settings import show_provider_settings
        show_provider_settings(settings, VISION_ENGINES.get(settings.parent.config.get('ocr_engine')))
    settings.provider_routing_note.linkActivated.connect(open_image_api)
    grid.addWidget(settings.provider_routing_note, 2, 1, 1, 2, Qt.AlignTop)
    from provider_settings import refresh_provider_routing
    refresh_provider_routing(settings)

    for row, flag in ((4, settings.keep_visible_checkbox), (5, settings.freeze_screen_checkbox)):
        flag.setParent(content)
        flag.setObjectName('settingsPageCheckbox')
        flag.setFixedHeight(28)
        grid.addWidget(flag, row, 0, 1, 3, Qt.AlignLeft)
    # Dimming belongs to the same visible form, not an expanding subpage.
    while dim_row.count():
        dim_row.takeAt(0)
    settings.dim_screen_during_ocr_checkbox.setParent(content)
    grid.addWidget(settings.dim_screen_during_ocr_checkbox, 6, 0, Qt.AlignLeft)
    from PyQt5.QtWidgets import QHBoxLayout
    dim_controls = QWidget(content)
    slider_row = QHBoxLayout(dim_controls)
    slider_row.setContentsMargins(0, 0, 0, 0)
    slider_row.addStretch(1)
    slider_row.addWidget(settings.ocr_dim_strength_value)
    slider_row.addWidget(settings.ocr_dim_strength_slider)
    grid.addWidget(dim_controls, 6, 1, 1, 2)
    settings.copy_notification_checkbox.setParent(content)
    settings.copy_notification_checkbox.setFixedHeight(28)
    grid.addWidget(settings.copy_notification_checkbox, 7, 0, 1, 3, Qt.AlignLeft)
    body.addStretch(1)
    settings.translation_action_panel = QWidget(settings.settings_updates_page)
    settings.translation_action_panel.setObjectName('settingsActionPanel')
    settings.translation_action_panel.setFixedHeight(61)
    tools = QGridLayout(settings.translation_action_panel)
    tools.setContentsMargins(1, 1, 1, 1)
    tools.setHorizontalSpacing(0)
    tools.setVerticalSpacing(1)
    tools.setColumnStretch(0, 1)
    tools.setColumnStretch(1, 1)
    settings.ocr_languages_btn.setParent(settings.translation_action_panel)
    tools.addWidget(settings.ocr_languages_btn, 0, 0, 1, 2)
    for column, button in enumerate((settings.copy_history_btn, settings.translation_history_btn)):
        button.setParent(settings.translation_action_panel)
        tools.addWidget(button, 1, column)
    scroll.setWidget(content)
    scroll.viewport().setAutoFillBackground(False)
    updates_layout.addWidget(scroll)
    updates_layout.addWidget(settings.translation_action_panel)
    settings.translation_settings_scroll = scroll
    # Plain container backgrounds follow the same palette as the other pages.
    scroll.setStyleSheet('QScrollArea, QWidget#translationSettingsContent { background: transparent; border: none; }')
    install_accent_controls(content, dark=settings.parent.current_theme != 'Светлая')
    settings.settings_page_tabs[1].setText(captions[0])
    settings.settings_page_tabs[1].setAccessibleName(captions[0])
    settings.settings_page_tabs[1].setToolTip(tooltip_text(captions[0]))


def reveal(settings, widget):
    """Keep guide links valid after moving controls to their actual category."""
    scroll = getattr(settings, 'translation_settings_scroll', None)
    if scroll is not None and scroll.widget().isAncestorOf(widget):
        settings._set_settings_page(1)
        scroll.ensureWidgetVisible(widget)
