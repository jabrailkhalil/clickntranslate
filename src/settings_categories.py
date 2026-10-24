"""Arrange program and translation preferences in the fixed settings viewport."""
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)
from settings_sections import PAGE_OCR, section_text


CAPTIONS = {
    'en': ('Translation and OCR', 'OCR options', 'Quick translation'),
    'ru': ('Перевод и OCR', 'Параметры OCR', 'Быстрый перевод'),
    'es': ('Traducción y OCR', 'Opciones de OCR', 'Traducción rápida'),
    'de': ('Übersetzung und OCR', 'OCR-Optionen', 'Schnellübersetzung'),
    'fr': ('Traduction et OCR', 'Options OCR', 'Traduction rapide'),
    'zh': ('翻译与 OCR', 'OCR 选项', '快速翻译'),

    'pt': ('Tradução e OCR', 'Opções de OCR', 'Tradução rápida'),
    'it': ('Traduzione e OCR', "Opzioni dell'OCR", 'Traduzione veloce'),

    'ar': ('الترجمة والتعرف على النص', 'خيارات التعرف على النص', 'الترجمة السريعة'),

    'tr': ('Çeviri ve OCR', 'OCR seçenekleri', 'Hızlı çeviri'),
    'hi': ('अनुवाद और OCR', 'OCR विकल्प', 'त्वरित अनुवाद'),
    'id': ('Terjemahan dan OCR', 'Opsi OCR', 'Terjemahan cepat'),
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

    'ar': ('استعادة الحافظة',
     'إغلاق النتيجة بالنقر خارجها',
     'الترجمة السريعة للنص المحدد',
     'إظهار زر',
     'الترجمة الآن'),

    'tr': ('Panoyu geri yükle',
     'Dışarı tıklanınca sonucu kapat',
     'Hızlı seçim çevirisi',
     'Düğme göster',
     'Şimdi çevir'),
    'hi': ('क्लिपबोर्ड बहाल करें',
     'बाहर क्लिक पर परिणाम बंद करें',
     'त्वरित चयन अनुवाद',
     'बटन दिखाएँ',
     'अभी अनुवाद करें'),
    'id': ('Pulihkan papan klip',
     'Tutup hasil saat klik di luar',
     'Terjemahan pilihan cepat',
     'Tampilkan tombol',
     'Terjemahkan sekarang'),
}


PARAGRAPH_TEXT = {
    'en': ('Join OCR lines into paragraphs', 'Before translating captured text, joins wrapped lines within a paragraph. Visible gaps, columns and list items remain separate. Useful for books and dialogue; turn off to keep the original line layout.'),
    'ru': ('Объединять строки в абзацы', 'Перед переводом текста с экрана убирает переносы внутри абзацев. Видимые промежутки, колонки и пункты списков сохраняются. Удобно для книг и диалогов; выключите, чтобы сохранить исходные строки.'),
    'es': ('Unir líneas OCR en párrafos', 'Antes de traducir el texto capturado, une las líneas de cada párrafo. Conserva espacios visibles entre bloques, columnas y elementos de listas. Útil para libros y diálogos; desactiva para conservar las líneas originales.'),
    'de': ('OCR-Zeilen zu Absätzen verbinden', 'Verbindet umgebrochene Zeilen vor der Übersetzung. Sichtbare Absatzabstände, Spalten und Listeneinträge bleiben getrennt. Für Bücher und Dialoge; ausschalten, um die ursprünglichen Zeilen beizubehalten.'),
    'fr': ('Réunir les lignes OCR en paragraphes', 'Réunit les lignes d’un paragraphe avant de traduire le texte capturé. Préserve les espacements visibles, colonnes et éléments de liste. Utile pour les livres et dialogues ; désactivez pour conserver les lignes d’origine.'),
    'zh': ('将 OCR 行合并为段落', '翻译屏幕文字前，合并段落内因排版产生的换行。保留可见的段落间距、分栏和列表项。适合书籍和对话；关闭后保留原始行布局。'),
    'pt': ('Unir linhas OCR em parágrafos', 'Antes de traduzir o texto capturado, une as linhas de cada parágrafo. Mantém separados os espaços visíveis entre blocos, as colunas e os itens de listas. Útil para livros e diálogos; desative para manter as linhas originais.'),
    'it': ('Unisci le righe OCR in paragrafi', 'Prima di tradurre il testo acquisito, unisce le righe di ogni paragrafo. Mantiene separati spazi visibili tra blocchi, colonne e voci degli elenchi. Utile per libri e dialoghi; disattiva per mantenere le righe originali.'),

    'ar': ('دمج أسطر OCR في فقرات',
     'يدمج الأسطر الملتفة داخل الفقرة قبل ترجمة النص الملتقط. تبقى الفواصل المرئية والأعمدة وعناصر '
     'القوائم منفصلة. مفيد للكتب والحوارات؛ عطّله للحفاظ على توزيع الأسطر الأصلي.'),

    'tr': ('OCR satırlarını paragraflarda birleştir',
     'Yakalanan metni çevirmeden önce aynı paragraftaki satırları birleştirir. Boşluklar, sütunlar ve '
     'liste öğeleri ayrı kalır. Kitap ve diyaloglar için yararlıdır; özgün satır düzeni için kapatın.'),
    'hi': ('OCR पंक्तियाँ अनुच्छेद में जोड़ें',
     'कैप्चर किए टेक्स्ट के अनुवाद से पहले अनुच्छेद की टूटी पंक्तियाँ जोड़ता है। खाली जगह, कॉलम और '
     'सूची बिंदु अलग रहते हैं। किताबों और संवादों में उपयोगी; मूल पंक्तियाँ रखने के लिए बंद करें।'),
    'id': ('Gabung baris OCR menjadi paragraf',
     'Sebelum menerjemahkan, gabungkan baris terbungkus dalam satu paragraf. Jarak, kolom, dan butir '
     'daftar tetap terpisah. Berguna untuk buku dan dialog; nonaktifkan untuk tata baris asli.'),
}


def _empty(layout):
    while layout.count():
        layout.takeAt(0)


def _scroll(page, content, name):
    """Only the body scrolls; action buttons keep one predictable position."""
    scroll = QScrollArea(page)
    scroll.setObjectName(name)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setMinimumSize(0, 0)
    scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
    content.setObjectName(name + 'Content')
    content.setMinimumWidth(0)
    if content.layout() is not None:
        content.layout().setSizeConstraint(QLayout.SetMinimumSize)
    scroll.setWidget(content)
    scroll.viewport().setAutoFillBackground(False)
    scroll.setStyleSheet('QScrollArea { background:transparent; border:none; } '
                        'QWidget#' + content.objectName() + ' { background:transparent; border:none; }')
    return scroll


def _panel(settings, parent, rows):
    """All categories use the same connected action grid and physical edges."""
    panel = QWidget(parent)
    panel.setObjectName('settingsActionPanel')
    panel.setAttribute(Qt.WA_StyledBackground, True)
    height = 29
    panel.setFixedHeight(len(rows) * height + max(0, len(rows)-1) + 2)
    grid = QGridLayout(panel)
    grid.setContentsMargins(1, 1, 1, 1)
    grid.setHorizontalSpacing(0)
    grid.setVerticalSpacing(1)
    columns = max(len(row) for row in rows)
    for column in range(columns):
        grid.setColumnStretch(column, 1)
    for row, buttons in enumerate(rows):
        for column, button in enumerate(buttons):
            button.setParent(panel)
            button.setFixedHeight(height)
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            grid.addWidget(button, row, column * (columns // len(buttons)),
                           1, columns // len(buttons))
    return panel


def _new_action(settings, key, hint, callback):
    from settings_window import OpticallyCenteredPushButton
    from styled_dialogs import tooltip_text
    lang = settings.parent.current_interface_language
    button = OpticallyCenteredPushButton(section_text(lang, key))
    button.setToolTip(tooltip_text(section_text(lang, hint)))
    button.setAccessibleName(section_text(lang, key))
    button.setAccessibleDescription(section_text(lang, hint))
    button.clicked.connect(callback)
    return button


def _flag(control):
    control.setObjectName('settingsPageCheckbox')
    control.setFixedHeight(28)
    control.setStyleSheet('margin:0; padding:0;')
    return control


def _form(content):
    grid = QGridLayout(content)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(4)
    grid.setColumnStretch(0, 1)
    return grid


def _wrap_mode_pages(settings):
    # Transfer the existing layouts and controls intact: signals and values
    # retain a single owner, including the optional custom-image row.
    page = settings.settings_game_page
    grid = page.layout()
    for control in (settings.game_languages_label, settings.game_language_controls,
                    settings.game_source_combo, settings.game_target_combo,
                    settings.game_swap_button, settings.game_scan_interval_label,
                    settings.game_interval_controls, settings.game_overlay_opacity_label,
                    settings.game_opacity_controls):
        control.setFixedHeight(28)
    for control in (settings.game_pause_inactive_checkbox, settings.game_show_original_checkbox,
                    settings.game_manual_output_checkbox, settings.game_toolbar_checkbox,
                    settings.game_remember_template_checkbox):
        _flag(control)
    grid.removeWidget(settings.game_help_button)
    grid.removeWidget(settings.game_launch_button)
    grid.setRowStretch(9, 0)
    content = QWidget()
    content.setLayout(grid)
    settings.game_settings_content = content
    settings.game_settings_scroll = _scroll(page, content, 'dynamicSettingsScroll')
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(4)
    root.addWidget(settings.game_settings_scroll, 1)
    settings.game_action_panel = _panel(settings, page,
        ((settings.game_help_button, settings.game_launch_button),))
    root.addWidget(settings.game_action_panel)

    page = settings.settings_assistant_page
    old_root = page.layout()
    old_footer = old_root.takeAt(old_root.count()-1).layout()
    _empty(old_footer)
    old_footer.deleteLater()
    content = QWidget()
    content.setLayout(old_root)
    settings.assistant_settings_content = content
    settings.assistant_settings_scroll = _scroll(page, content, 'companionSettingsScroll')
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(4)
    root.addWidget(settings.assistant_settings_scroll, 1)
    settings.assistant_action_panel = _panel(settings, page,
        ((page.action_buttons['home'], page.dismiss_button),))
    root.addWidget(settings.assistant_action_panel)


def organize(settings, general_layout, form, updates_layout, dim_row):
    from settings_window import InterfaceLanguageButton, settings_text
    from styled_dialogs import tooltip_text
    from PyQt5.QtGui import QIcon

    lang = settings.parent.current_interface_language
    compact = COMPACT.get(lang, COMPACT['en'])
    _empty(form)
    _empty(updates_layout)
    _empty(dim_row)
    _empty(general_layout)

    # Application: six program preferences and one coherent display column.
    general = settings.settings_general_page
    content = QWidget()
    content.setLayout(form)
    form.setVerticalSpacing(2)
    for row, control in enumerate((settings.autostart_checkbox,
            settings.start_minimized_checkbox, settings.copy_history_checkbox,
            settings.history_checkbox, settings.button_tooltips_checkbox,
            settings.update_check_on_launch_checkbox)):
        control.setParent(content)
        form.addWidget(_flag(control), row, 0, Qt.AlignLeft)
    settings.interface_language_label = QLabel(section_text(lang, 'language'), content)
    settings.interface_language_button = InterfaceLanguageButton('', content)
    settings.interface_language_button.setObjectName('settingsInterfaceLanguage')
    settings.interface_language_button.setFixedSize(180, 28)
    settings.interface_language_button.setIconSize(QSize(18, 18))
    settings.interface_language_button.setToolTip(tooltip_text(section_text(lang, 'language_hint')))
    settings.interface_language_label.setToolTip(settings.interface_language_button.toolTip())
    settings.interface_language_label.setBuddy(settings.interface_language_button)
    from main import INTERFACE_LANGUAGE_OPTIONS, resource_path
    option = next((item for item in INTERFACE_LANGUAGE_OPTIONS if item['code'] == lang),
                  INTERFACE_LANGUAGE_OPTIONS[0])
    settings.interface_language_button.setText(option['name'])
    settings.interface_language_button.setIcon(QIcon(resource_path(option['icon'])))
    settings.interface_language_button.setAccessibleName(section_text(lang, 'language').rstrip(':： '))
    settings.interface_language_button.clicked.connect(
        lambda _checked=False: settings.parent.show_interface_language_menu(restore_to='settings'))
    for row, label, control in (
            (0, settings.interface_language_label, settings.interface_language_button),
            (1, settings.ui_scale_label, settings.ui_scale_control),
            (2, settings.translation_font_label, settings.translation_font_control)):
        label.setParent(content)
        control.setParent(content)
        label.setStyleSheet('margin:0; padding:0; font-size:14px;')
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.addWidget(label, row, 1)
        form.addWidget(control, row, 2)
    settings.translation_font_preview.setParent(content)
    form.addWidget(settings.translation_font_preview, 3, 2, 2, 1, Qt.AlignVCenter)
    form.setRowStretch(6, 1)
    settings.application_settings_content = content
    settings.application_settings_scroll = _scroll(general, content, 'applicationSettingsScroll')
    general_layout.addWidget(settings.application_settings_scroll, 1)

    # Maintenance is a nested page; keep its controls alive for inline updates.
    old_panel = settings.settings_action_panel
    settings.maintenance_page = QWidget(settings)
    settings.maintenance_page.setObjectName('maintenancePage')
    maintenance_root = QVBoxLayout(settings.maintenance_page)
    maintenance_root.setContentsMargins(8, 4, 8, 0)
    maintenance_root.setSpacing(12)
    settings.maintenance_title = QLabel(section_text(lang, 'maintenance'))
    settings.maintenance_title.setWordWrap(True)
    maintenance_root.addWidget(settings.maintenance_title)
    settings.maintenance_action_panel = _panel(settings, settings.maintenance_page, (
        (settings.update_btn, settings.clear_cache_btn),
        (settings.export_settings_btn, settings.import_settings_btn),
        (settings.create_bug_report_btn, settings.reset_btn)))
    maintenance_root.addWidget(settings.maintenance_action_panel)
    maintenance_root.addStretch(1)
    from settings_window import OpticallyCenteredPushButton
    settings.maintenance_back_button = OpticallyCenteredPushButton(settings_text(lang, 'back'))
    settings.maintenance_back_button.setToolTip(settings_text(lang, 'back'))
    settings.maintenance_back_button.clicked.connect(settings._return_from_secondary_view)
    settings.maintenance_footer = _panel(settings, settings.maintenance_page,
                                       ((settings.maintenance_back_button,),))
    maintenance_root.addWidget(settings.maintenance_footer)
    settings.maintenance_page.hide()
    settings.maintenance_button = _new_action(settings, 'maintenance', 'maintenance_hint',
                                             settings.show_maintenance_view)
    settings.application_action_panel = _panel(settings, general,
        ((settings.hotkeys_button, settings.maintenance_button),))
    settings.settings_action_panel = settings.application_action_panel
    general_layout.addWidget(settings.application_action_panel)
    old_panel.hide()
    old_panel.deleteLater()
    settings.settings_transfer_panel.hide()

    # Translation owns result behaviour; OCR no longer competes for its rows.
    page = settings.settings_updates_page
    content = QWidget()
    grid = _form(content)
    settings.translation_settings_grid = grid
    for row, label, control in (
            (0, settings.translator_engine_label, settings.translator_combo),
            (1, settings.result_window_label, settings.result_window_control)):
        label.setParent(content)
        control.setParent(content)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        control.setFixedSize(270, 28)
        grid.addWidget(label, row, 0)
        grid.addWidget(control, row, 1)
    settings.restore_clipboard_checkbox.setText(compact[0])
    settings.close_result_on_outside_click_checkbox = QCheckBox(compact[1], content)
    close_flag = settings.close_result_on_outside_click_checkbox
    close_flag.setChecked(settings.parent.config.get('close_result_window_on_outside_click') is True)
    close_flag.setToolTip(tooltip_text(settings_text(lang, 'close_result_window_on_outside_click_tooltip')))
    close_flag.toggled.connect(lambda checked: settings.auto_save_setting(
        'close_result_window_on_outside_click', bool(checked)))
    for row, control in enumerate((settings.copy_translated_checkbox,
            settings.replace_select_all_checkbox, settings.restore_clipboard_checkbox,
            close_flag), 2):
        control.setParent(content)
        grid.addWidget(_flag(control), row, 0, 1, 2, Qt.AlignLeft)
    settings.provider_routing_note = QLabel(content)
    settings.provider_routing_note.setObjectName('assistantNote')
    settings.provider_routing_note.setFixedHeight(28)
    settings.provider_routing_note.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    def open_image_api(_link):
        from api_providers import VISION_ENGINES
        from provider_settings import show_provider_settings
        show_provider_settings(settings, VISION_ENGINES.get(settings.parent.config.get('ocr_engine')))
    settings.provider_routing_note.linkActivated.connect(open_image_api)
    grid.addWidget(settings.provider_routing_note, 6, 0, 1, 2)
    grid.setRowStretch(7, 1)
    settings.translation_settings_content = content
    settings.translation_settings_scroll = _scroll(page, content, 'translationSettingsScroll')
    updates_layout.setSpacing(4)
    updates_layout.addWidget(settings.translation_settings_scroll, 1)
    from provider_settings import show_provider_settings
    settings.translation_offline_button = _new_action(settings, 'offline', 'offline_hint',
                                                      settings.show_offline_translation_packages)
    def open_translation_api(_checked=False):
        from provider_catalog import provider_id
        show_provider_settings(settings, provider_id(settings.parent.config.get('translator_engine')))
    settings.translation_api_button = _new_action(settings, 'api', 'api_hint', open_translation_api)
    settings.translation_action_panel = _panel(settings, page, (
        (settings.translation_offline_button, settings.translation_api_button),
        (settings.copy_history_btn, settings.translation_history_btn)))
    updates_layout.addWidget(settings.translation_action_panel)

    # OCR has its own complete form and package/API routes.
    settings.settings_ocr_page = QWidget(settings)
    settings.settings_ocr_page.setObjectName('settingsOcrPage')
    root = QVBoxLayout(settings.settings_ocr_page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(4)
    content = QWidget()
    grid = _form(content)
    settings.ocr_settings_grid = grid
    settings.ocr_engine_label.setParent(content)
    settings.ocr_engine_label.setText(section_text(lang, 'recognition'))
    settings.ocr_engine_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    settings.ocr_engine_combo.setParent(content)
    settings.ocr_engine_combo.setFixedSize(270, 28)
    grid.addWidget(settings.ocr_engine_label, 0, 0)
    grid.addWidget(settings.ocr_engine_combo, 0, 1)
    caption, hint = PARAGRAPH_TEXT.get(lang, PARAGRAPH_TEXT['en'])
    settings.ocr_join_paragraphs_checkbox = QCheckBox(caption, content)
    paragraph_flag = settings.ocr_join_paragraphs_checkbox
    paragraph_flag.setChecked(settings.parent.config.get('ocr_join_paragraphs') is True)
    paragraph_flag.setToolTip(tooltip_text(hint))
    paragraph_flag.setAccessibleDescription(hint)
    paragraph_flag.toggled.connect(lambda checked: settings.auto_save_setting('ocr_join_paragraphs', bool(checked)))
    for row, control in enumerate((paragraph_flag, settings.keep_visible_checkbox,
                                   settings.freeze_screen_checkbox), 1):
        control.setParent(content)
        grid.addWidget(_flag(control), row, 0, 1, 2, Qt.AlignLeft)
    settings.dim_screen_during_ocr_checkbox.setParent(content)
    grid.addWidget(_flag(settings.dim_screen_during_ocr_checkbox), 4, 0, Qt.AlignLeft)
    dim_controls = QWidget(content)
    dim_controls.setFixedHeight(28)
    slider_row = QHBoxLayout(dim_controls)
    slider_row.setContentsMargins(0, 0, 0, 0)
    slider_row.setSpacing(8)
    slider_row.addStretch(1)
    slider_row.addWidget(settings.ocr_dim_strength_value)
    slider_row.addWidget(settings.ocr_dim_strength_slider)
    grid.addWidget(dim_controls, 4, 1)
    settings.copy_notification_checkbox.setParent(content)
    grid.addWidget(_flag(settings.copy_notification_checkbox), 5, 0, 1, 2, Qt.AlignLeft)
    grid.setRowStretch(6, 1)
    settings.ocr_settings_content = content
    settings.ocr_settings_scroll = _scroll(settings.settings_ocr_page, content, 'ocrSettingsScroll')
    root.addWidget(settings.ocr_settings_scroll, 1)
    settings.ocr_languages_btn.setText(section_text(lang, 'ocr_packages'))
    settings.ocr_languages_btn.setToolTip(tooltip_text(section_text(lang, 'ocr_packages_hint')))
    settings._apply_language_package_task_status()
    def open_ocr_api(_checked=False):
        from api_providers import VISION_ENGINES
        show_provider_settings(settings, VISION_ENGINES.get(settings.parent.config.get('ocr_engine')))
    settings.ocr_api_button = _new_action(settings, 'api', 'api_hint', open_ocr_api)
    settings.ocr_action_panel = _panel(settings, settings.settings_ocr_page,
        ((settings.ocr_languages_btn, settings.ocr_api_button),))
    root.addWidget(settings.ocr_action_panel)
    settings.settings_pages.addWidget(settings.settings_ocr_page)
    assert settings.settings_pages.indexOf(settings.settings_ocr_page) == PAGE_OCR
    settings.settings_ocr_page.hide()
    _wrap_mode_pages(settings)
    from provider_settings import refresh_provider_routing
    refresh_provider_routing(settings)


def reveal(settings, widget):
    """Guide links follow their control after category or secondary-page moves."""
    for page, name in ((0, 'application_settings_scroll'), (1, 'translation_settings_scroll'),
                       (4, 'ocr_settings_scroll'), (2, 'game_settings_scroll'),
                       (3, 'assistant_settings_scroll')):
        scroll = getattr(settings, name, None)
        if scroll is not None and scroll.widget().isAncestorOf(widget):
            settings._set_settings_page(page)
            scroll.ensureWidgetVisible(widget)
            return
