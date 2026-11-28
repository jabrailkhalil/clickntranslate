"""Feedback when replacement cannot prove that the focused control is editable."""

EDIT_TARGET_UNAVAILABLE = {
    'ru': 'Не удалось подтвердить поле ввода. Используйте обычный перевод выделения.',
    'en': 'Could not verify an editable field. Use Translate selected text instead.',
    'es': 'No se pudo verificar un campo editable. Usa Traducir texto seleccionado.',
    'de': 'Kein bearbeitbares Textfeld bestätigt. Verwende die Übersetzung der Textauswahl.',
    'fr': 'Impossible de confirmer un champ modifiable. Utilisez la traduction du texte sélectionné.',
    'zh': '无法确认可编辑的输入框。请改用翻译选中文字。',
    'pt': 'Não foi possível confirmar um campo editável. Use Traduzir texto selecionado.',
    'it': 'Impossibile verificare un campo modificabile. Usa Traduci testo selezionato.',
    'ar': 'تعذر التحقق من وجود حقل قابل للتحرير. استخدم ترجمة النص المحدد بدلًا من ذلك.',
    'tr': 'Düzenlenebilir bir alan doğrulanamadı. Bunun yerine seçili metni çevirin.',
    'hi': 'संपादन योग्य फ़ील्ड की पुष्टि नहीं हो सकी। इसके बजाय चयनित टेक्स्ट का अनुवाद करें।',
    'id': 'Kolom yang dapat diedit tidak dapat diverifikasi. Gunakan terjemahan teks yang dipilih.',
}


def edit_target_unavailable(language):
    return EDIT_TARGET_UNAVAILABLE.get(language, EDIT_TARGET_UNAVAILABLE['en'])


RELEASE_SHORTCUT_KEYS = {
    'ru': 'Отпустите клавиши сочетания и попробуйте ещё раз.',
    'en': 'Release the shortcut keys and try again.',
    'es': 'Suelta las teclas del atajo y vuelve a intentarlo.',
    'de': 'Lass die Tasten des Tastenkürzels los und versuche es erneut.',
    'fr': 'Relâchez les touches du raccourci et réessayez.',
    'zh': '请松开快捷键后重试。',
    'pt': 'Solte as teclas do atalho e tente novamente.',
    'it': 'Rilascia i tasti della scorciatoia e riprova.',
    'ar': 'حرّر مفاتيح الاختصار وحاول مرة أخرى.',
    'tr': 'Kısayol tuşlarını bırakıp tekrar deneyin.',
    'hi': 'शॉर्टकट की कुंजियाँ छोड़ें और फिर से कोशिश करें।',
    'id': 'Lepaskan tombol pintasan lalu coba lagi.',
}


PASSIVE_SELECTION_HELP = {
    'ru': 'Кнопка и автоперевод работают, когда приложение поддерживает системное чтение выделения. Если они не появляются, используйте горячую клавишу перевода выделенного текста.',
    'en': 'The button and automatic translation require system access to the selected text. If they do not appear, use the Translate selected text hotkey.',
    'es': 'El botón y la traducción automática requieren acceso del sistema al texto seleccionado. Si no aparecen, usa el atajo para traducir el texto seleccionado.',
    'de': 'Schaltfläche und automatische Übersetzung benötigen Systemzugriff auf die Textauswahl. Falls sie nicht erscheinen, verwende das Tastenkürzel für die Auswahlübersetzung.',
    'fr': 'Le bouton et la traduction automatique nécessitent un accès système au texte sélectionné. Sinon, utilisez le raccourci de traduction du texte sélectionné.',
    'zh': '翻译按钮和自动翻译需要应用支持系统读取选中文字。如果没有出现，请使用翻译选中文字的快捷键。',
    'pt': 'O botão e a tradução automática exigem acesso do sistema ao texto selecionado. Se não aparecerem, use o atalho para traduzir o texto selecionado.',
    'it': 'Il pulsante e la traduzione automatica richiedono accesso di sistema al testo selezionato. Se non compaiono, usa la scorciatoia per tradurre il testo selezionato.',
    'ar': 'يتطلب الزر والترجمة التلقائية أن يتيح التطبيق للنظام قراءة النص المحدد. إذا لم يظهرا، فاستخدم اختصار ترجمة النص المحدد.',
    'tr': 'Düğme ve otomatik çeviri için sistemin seçili metni okuyabilmesi gerekir. Görünmüyorlarsa seçili metni çevirme kısayolunu kullanın.',
    'hi': 'बटन और अपने आप अनुवाद के लिए सिस्टम को चयनित टेक्स्ट पढ़ने की सुविधा चाहिए। ये न दिखें तो चयनित टेक्स्ट के अनुवाद का शॉर्टकट इस्तेमाल करें।',
    'id': 'Tombol dan terjemahan otomatis memerlukan akses sistem ke teks yang dipilih. Jika tidak muncul, gunakan pintasan terjemahan teks yang dipilih.',
}
