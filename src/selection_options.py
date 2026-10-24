"""One trigger choice inside the existing Selection mode editor."""
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel

TEXT = {
    'ru': ('После выделения:', 'По горячей клавише', 'Показать кнопку перевода', 'Перевести сразу', 'Режим выделения', 'В другом приложении выделите текст. Выберите, запускать перевод горячей клавишей, кнопкой рядом с выделением или автоматически. Используется выбранный переводчик и языки режима «Выделение».'),
    'en': ('After selecting:', 'Use the hotkey', 'Show a translate button', 'Translate immediately', 'Selection mode', 'Select text in another app. Start translation with the hotkey, a button beside the selection, or automatically. Uses the selected translator and Selection languages.'),
    'es': ('Tras seleccionar:', 'Usar el atajo', 'Mostrar botón de traducción', 'Traducir al instante', 'Modo Selección', 'Selecciona texto en otra app. Traduce con el atajo, un botón junto al texto o automáticamente. Usa el traductor elegido y los idiomas de Selección.'),
    'de': ('Nach der Auswahl:', 'Mit Tastenkürzel', 'Übersetzen-Schaltfläche zeigen', 'Sofort übersetzen', 'Auswahlmodus', 'Text in einer anderen App auswählen. Mit Tastenkürzel, Schaltfläche neben dem Text oder automatisch übersetzen. Verwendet den gewählten Übersetzer und das Auswahl-Sprachpaar.'),
    'fr': ('Après sélection :', 'Utiliser le raccourci', 'Afficher un bouton de traduction', 'Traduire aussitôt', 'Mode Sélection', 'Sélectionnez du texte dans une autre app. Traduisez par raccourci, bouton près du texte ou automatiquement. Utilise le traducteur choisi et les langues du mode Sélection.'),
    'zh': ('选择文字后：', '使用快捷键', '显示翻译按钮', '立即翻译', '选中文字模式', '在其他应用中选择文字，通过快捷键、文字旁的按钮或自动翻译。使用所选翻译服务和选中文字模式的语言。'),

    'pt': ('Após selecionar:',
     'Usar o atalho',
     'Mostrar um botão de tradução',
     'Traduzir imediatamente',
     'Modo de seleção',
     'Selecione o texto em outro aplicativo. Inicie a tradução com o atalho, um botão ao lado da '
     'seleção ou automaticamente. Usa o tradutor selecionado e os idiomas de seleção.'),
    'it': ('Dopo la selezione:',
     'Usa la scorciatoia',
     'Mostra un pulsante di traduzione',
     'Traduci immediatamente',
     'Modalità di selezione',
     "Seleziona il testo in un'altra app. Avvia la traduzione con la scorciatoia, un pulsante accanto "
     'alla selezione o automaticamente. Utilizza il traduttore selezionato e le lingue di selezione.'),

    'ar': ('بعد التحديد:',
     'استخدام الاختصار',
     'إظهار زر ترجمة',
     'الترجمة فورًا',
     'وضع التحديد',
     'حدد نصًا في تطبيق آخر. ابدأ الترجمة بالاختصار، أو بزر بجوار التحديد، أو تلقائيًا. يُستخدم '
     'المترجم المختار ولغتا وضع التحديد.'),
}


class SelectionTriggerControl(QWidget):
    def __init__(self, owner, parent=None):
        super().__init__(parent)
        from settings_window import DropDownCombo
        from styled_dialogs import tooltip_text
        self.owner = owner
        labels = TEXT.get(owner.current_interface_language, TEXT['en'])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.label = QLabel(labels[0], self)
        self.combo = DropDownCombo(self)
        self.combo.setMinimumHeight(32)
        self.combo.setAccessibleName(labels[0])
        for text, code in zip(labels[1:4], ('hotkey', 'button', 'automatic')):
            self.combo.addItem(text, code)
        self.label.setBuddy(self.combo)
        self.setToolTip(tooltip_text(labels[5]))
        layout.addWidget(self.label)
        layout.addWidget(self.combo, 1)
        self.refresh()
        self.combo.currentIndexChanged.connect(self._changed)

    def refresh(self):
        config = self.owner.config
        mode = str(config.get('selection_quick_translate_mode') or 'button') if config.get('selection_quick_translate_enabled') is True else 'hotkey'
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(max(0, self.combo.findData(mode)))
        self.combo.blockSignals(False)

    def _changed(self, *_args):
        mode = self.combo.currentData()
        if mode != 'hotkey' and not self.owner.ensure_mac_accessibility_for_selection():
            self.refresh()
            return
        self.owner.config['selection_quick_translate_enabled'] = mode != 'hotkey'
        self.owner.config['selection_quick_translate_mode'] = 'automatic' if mode == 'automatic' else 'button'
        self.owner.save_config()
        self.owner._sync_selection_quick_translate()
        from settings_window import _invalidate_main_config_cache
        _invalidate_main_config_cache()
