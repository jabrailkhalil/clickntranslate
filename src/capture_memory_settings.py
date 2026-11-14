"""Localized mode selection for the optional capture-memory toolbar controls."""

_KEYS = ('label', 'translate', 'copy', 'short_translate', 'short_copy', 'all',
         'none', 'count', 'on', 'off', 'hint', 'error')
_TEXT = {
    'en': ('Remember area:', 'Translate a screen area', 'Recognize and copy text',
           'Area translation', 'OCR copying', 'Both modes', 'Off', '{count} of {total}',
           'Memory control shown', 'Memory control hidden',
           'Choose the modes that allow area memory and show its checkbox in the capture panel. You can turn memory off and on there. Clearing a mode here hides the checkbox and clears its saved area. Dynamic templates are configured separately.',
           'Could not save the area memory preferences.'),
    'ru': ('Запоминать область:', 'Перевод области экрана', 'Распознавание и копирование текста',
           'Перевод области', 'Копирование OCR', 'Оба режима', 'Выключено', '{count} из {total}',
           'Галочка памяти доступна', 'Галочка памяти скрыта',
           'Выберите режимы, в которых разрешено запоминать область и нужна галочка в панели захвата. Там память можно выключить и снова включить. Снятие пункта здесь скрывает галочку и очищает сохранённую область. Шаблоны динамики настраиваются отдельно.',
           'Не удалось сохранить настройки памяти областей.'),
    'es': ('Recordar zona:', 'Traducir una zona de pantalla', 'Reconocer y copiar texto',
           'Traducir zona', 'Copiar OCR', 'Ambos modos', 'Desactivado', '{count} de {total}',
           'Control de memoria visible', 'Control de memoria oculto',
           'Elige los modos que permiten recordar zonas y muestran la casilla en el panel de captura. Allí puedes desactivar y reactivar la memoria. Desmarcar un modo aquí oculta la casilla y borra su zona guardada. Las plantillas dinámicas se configuran por separado.',
           'No se pudieron guardar los ajustes de memoria de zonas.'),
    'de': ('Bereich merken:', 'Bildschirmbereich übersetzen', 'Text erkennen und kopieren',
           'Bereich übersetzen', 'OCR kopieren', 'Beide Modi', 'Aus', '{count} von {total}',
           'Speicheroption sichtbar', 'Speicheroption ausgeblendet',
           'Modi auswählen, in denen Bereiche gespeichert werden dürfen und die Option im Aufnahmebereich erscheint. Dort lässt sich das Speichern aus- und einschalten. Das Abwählen hier blendet die Option aus und löscht den gespeicherten Bereich. Dynamische Vorlagen werden separat eingestellt.',
           'Die Einstellungen zum Speichern von Bereichen konnten nicht gespeichert werden.'),
    'fr': ('Mémoriser la zone :', 'Traduire une zone de l’écran', 'Reconnaître et copier le texte',
           'Traduction de zone', 'Copie OCR', 'Les deux modes', 'Désactivé', '{count} sur {total}',
           'Option de mémoire visible', 'Option de mémoire masquée',
           'Choisissez les modes qui permettent de mémoriser une zone et affichent la case dans le panneau de capture. Vous pouvez y désactiver puis réactiver la mémoire. Décocher un mode ici masque la case et efface sa zone mémorisée. Les modèles dynamiques se règlent séparément.',
           'Impossible d’enregistrer les préférences de mémorisation des zones.'),
    'zh': ('记住区域：', '翻译屏幕区域', '识别并复制文字',
           '区域翻译', 'OCR 复制', '两种模式', '关闭', '{count}/{total}',
           '显示记忆选项', '隐藏记忆选项',
           '选择允许记住区域并在捕获面板显示复选框的模式。可在面板内关闭或重新启用记忆。在这里取消某模式会隐藏复选框并清除已保存区域。动态模板需单独设置。',
           '无法保存区域记忆设置。'),
    'pt': ('Lembrar área:', 'Traduzir uma área da tela', 'Reconhecer e copiar texto',
           'Tradução de área', 'Cópia OCR', 'Ambos os modos', 'Desativado', '{count} de {total}',
           'Opção de memória visível', 'Opção de memória oculta',
           'Escolha os modos que permitem lembrar áreas e mostram a caixa no painel de captura. Ali você pode desativar e reativar a memória. Desmarcar um modo aqui oculta a caixa e apaga a área salva. Os modelos dinâmicos são configurados separadamente.',
           'Não foi possível salvar as preferências de memória de áreas.'),
    'it': ('Ricorda area:', 'Traduci un’area dello schermo', 'Riconosci e copia il testo',
           'Traduzione area', 'Copia OCR', 'Entrambe', 'Disattivato', '{count} di {total}',
           'Opzione memoria visibile', 'Opzione memoria nascosta',
           'Scegli le modalità che consentono di ricordare l’area e mostrano la casella nel pannello di acquisizione. Da lì puoi disattivare e riattivare la memoria. Deselezionare una modalità qui nasconde la casella e cancella l’area salvata. I modelli dinamici si configurano separatamente.',
           'Impossibile salvare le preferenze della memoria delle aree.'),
    'ar': ('تذكر المنطقة:', 'ترجمة منطقة من الشاشة', 'التعرف على النص ونسخه',
           'ترجمة المنطقة', 'نسخ النص', 'كلا الوضعين', 'معطل', '{count} من {total}',
           'خيار التذكر ظاهر', 'خيار التذكر مخفي',
           'اختر الأوضاع التي تسمح بتذكر المنطقة وتعرض مربع الاختيار في لوحة الالتقاط. يمكنك تعطيل التذكر وإعادة تفعيله من اللوحة. إلغاء وضع هنا يخفي المربع ويمسح منطقته المحفوظة. تُضبط قوالب الترجمة الديناميكية بشكل منفصل.',
           'تعذر حفظ تفضيلات تذكر المناطق.'),
    'tr': ('Alanı hatırla:', 'Ekran alanını çevir', 'Metni tanı ve kopyala',
           'Alan çevirisi', 'OCR kopyalama', 'İki mod da', 'Kapalı', '{count}/{total}',
           'Hafıza seçeneği görünür', 'Hafıza seçeneği gizli',
           'Alan hafızasına izin veren ve yakalama panelinde onay kutusunu gösteren modları seçin. Panelden hafızayı kapatıp açabilirsiniz. Burada bir modun işaretini kaldırmak kutuyu gizler ve kayıtlı alanı siler. Dinamik şablonlar ayrı ayarlanır.',
           'Alan hafızası tercihleri kaydedilemedi.'),
    'hi': ('क्षेत्र याद रखें:', 'स्क्रीन क्षेत्र का अनुवाद', 'टेक्स्ट पहचानें और कॉपी करें',
           'क्षेत्र अनुवाद', 'OCR कॉपी', 'दोनों मोड', 'बंद', '{total} में से {count}',
           'मेमोरी विकल्प दिखाएँ', 'मेमोरी विकल्प छिपाएँ',
           'वे मोड चुनें जिनमें क्षेत्र याद रखना और कैप्चर पैनल में टिक दिखाना है। पैनल में मेमोरी बंद और फिर चालू कर सकते हैं। यहाँ मोड की टिक हटाने पर विकल्प छिपता है और सहेजा क्षेत्र मिटता है। डायनामिक टेम्पलेट अलग से सेट होते हैं।',
           'क्षेत्र मेमोरी की सेटिंग सहेजी नहीं जा सकीं।'),
    'id': ('Ingat area:', 'Terjemahkan area layar', 'Kenali dan salin teks',
           'Terjemahan area', 'Salin OCR', 'Kedua mode', 'Nonaktif', '{count} dari {total}',
           'Opsi memori ditampilkan', 'Opsi memori disembunyikan',
           'Pilih mode yang mengizinkan memori area dan menampilkan kotak centang di panel tangkapan. Memori dapat dimatikan dan diaktifkan kembali dari panel. Membatalkan mode di sini menyembunyikan kotak dan menghapus area tersimpan. Templat dinamis diatur terpisah.',
           'Tidak dapat menyimpan preferensi memori area.'),
}


def text(locale, key):
    from text_direction import ui_directional_text
    return ui_directional_text(_TEXT.get(locale, _TEXT['en'])[_KEYS.index(key)], locale)


def make_control(settings, parent):
    from settings_window import ResultWindowModeCombo
    from capture_regions import MEMORY_MODES, memory_control_modes
    locale = settings.parent.current_interface_language
    control = ResultWindowModeCombo(MEMORY_MODES,
        {mode: text(locale, mode) for mode in MEMORY_MODES},
        {key: text(locale, key) for key in ('all', 'none', 'count', 'on', 'off')},
        dark=settings.parent.current_theme != 'Светлая', parent=parent,
        short_labels={mode: text(locale, 'short_'+mode) for mode in MEMORY_MODES})
    control.set_help_text(text(locale, 'hint'))
    control.setAccessibleName(text(locale, 'label'))
    for mode in MEMORY_MODES:
        control._item(mode).setToolTip(text(locale, 'hint'))
    control.set_checked_modes(memory_control_modes(settings.parent.config))
    control.modes_changed.connect(settings._save_capture_memory_modes)
    settings._apply_engine_combo_style(control)
    return control
