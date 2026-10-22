"""Short explanations for controls without a separate help panel."""

LANGUAGES = ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it')
HINTS = {
    'hover_tips': (
        'Show explanations when you hold the pointer over a control.',
        'Показывать пояснения, когда указатель задерживается на элементе интерфейса.',
        'Muestra explicaciones al mantener el puntero sobre un control.',
        'Erklärungen anzeigen, wenn der Mauszeiger über einem Bedienelement bleibt.',
        'Afficher une explication lorsque le pointeur reste sur une commande.',
        '将鼠标停留在控件上时显示说明。', 'Mostre explicações quando você mantém o ponteiro sobre um controle.', 'Mostra le spiegazioni quando tieni il puntatore su un controllo.'),
    'clear_cache': (
        'Clear cached recognition and translation results. New requests will be processed again.',
        'Удалить сохранённые в кэше результаты распознавания и перевода. При новом запросе они будут обработаны заново.',
        'Borra los resultados en caché de OCR y traducción. Las nuevas solicitudes se procesarán de nuevo.',
        'Zwischengespeicherte OCR- und Übersetzungsergebnisse löschen. Neue Anfragen werden erneut verarbeitet.',
        'Effacer les résultats OCR et les traductions en cache. Les prochaines demandes seront traitées à nouveau.',
        '清除缓存的识别和翻译结果。下次请求时将重新处理。', 'Limpe os resultados de reconhecimento e tradução em cache. Novas solicitações serão processadas novamente.', 'Cancella il riconoscimento memorizzato nella cache e i risultati della traduzione. Le nuove richieste verranno nuovamente elaborate.'),
    'reset': (
        'Restore the default application settings. A confirmation appears first.',
        'Вернуть настройки приложения по умолчанию. Сначала появится подтверждение.',
        'Restaura los ajustes predeterminados de la aplicación tras confirmarlo.',
        'Standardeinstellungen der App wiederherstellen. Zuerst erscheint eine Bestätigung.',
        'Rétablir les réglages par défaut de l’application après confirmation.',
        '恢复应用的默认设置，操作前会要求确认。', 'Restaure as configurações padrão do aplicativo. Uma confirmação aparece primeiro.', "Ripristina le impostazioni predefinite dell'applicazione. Prima viene visualizzata una conferma."),
    'update': (
        'Check whether a newer version of Click’n’Translate is available.',
        'Проверить, доступна ли новая версия Click’n’Translate.',
        'Comprueba si hay una nueva versión de Click’n’Translate.',
        'Prüfen, ob eine neuere Version von Click’n’Translate verfügbar ist.',
        'Vérifier si une nouvelle version de Click’n’Translate est disponible.',
        '检查 Click’n’Translate 是否有新版本。', 'Verifique se uma versão mais recente do Click’n’Translate está disponível.', 'Controlla se è disponibile una versione più recente di Click’n’Translate.'),
    'copy_history': (
        'Open previously recognized and copied text saved in local history.',
        'Открыть ранее распознанный и скопированный текст из локальной истории.',
        'Abre el texto reconocido y copiado guardado en el historial local.',
        'Lokal gespeicherte, zuvor erkannte und kopierte Texte öffnen.',
        'Ouvrir les textes reconnus et copiés enregistrés dans l’historique local.',
        '打开本地历史记录中保存的识别和复制文本。', 'Abra texto previamente reconhecido e copiado salvo no histórico local.', 'Apri il testo precedentemente riconosciuto e copiato salvato nella cronologia locale.'),
    'translation_history': (
        'Open source texts and translations saved in local history.',
        'Открыть исходные тексты и переводы, сохранённые в локальной истории.',
        'Abre los textos originales y las traducciones del historial local.',
        'Lokal gespeicherte Ausgangstexte und Übersetzungen öffnen.',
        'Ouvrir les textes source et traductions enregistrés localement.',
        '打开本地保存的原文和译文。', 'Abrir os textos originais e as traduções salvos no histórico local.', 'Apri i testi originali e le traduzioni salvati nella cronologia locale.'),
    'hotkeys': (
        'Configure shortcuts for screen capture, translation and showing the main window.',
        'Настроить сочетания клавиш для захвата экрана, перевода и вызова главного окна.',
        'Configura atajos para capturar la pantalla, traducir y mostrar la ventana principal.',
        'Tastenkürzel für Bildschirmaufnahme, Übersetzung und das Hauptfenster einstellen.',
        'Configurer les raccourcis de capture, de traduction et d’affichage de la fenêtre principale.',
        '设置屏幕捕获、翻译和显示主窗口的快捷键。', 'Configure atalhos para captura de tela, tradução e exibição da janela principal.', "Configura scorciatoie per l'acquisizione dello schermo, la traduzione e la visualizzazione della finestra principale."),
    'keep_visible': (
        'Keep the main window on screen while you select an OCR area.',
        'Оставлять главное окно на экране во время выбора области распознавания.',
        'Mantiene visible la ventana principal al seleccionar un área OCR.',
        'Das Hauptfenster bei der Auswahl eines OCR-Bereichs sichtbar lassen.',
        'Garder la fenêtre principale visible pendant la sélection de la zone OCR.',
        '选择 OCR 区域时保持主窗口可见。', 'Mantenha a janela principal na tela enquanto seleciona uma área de OCR.', "Mantieni la finestra principale sullo schermo mentre selezioni un'area OCR."),
    'scan_interval': (
        'Time between checks of the selected screen area. A longer interval reduces CPU use.',
        'Интервал проверки выбранной области экрана. Чем он больше, тем ниже нагрузка на процессор.',
        'Tiempo entre comprobaciones del área seleccionada. Un intervalo mayor reduce el uso de CPU.',
        'Zeit zwischen Prüfungen des gewählten Bereichs. Ein längeres Intervall senkt die CPU-Last.',
        'Délai entre les vérifications de la zone choisie. Un délai plus long réduit la charge du processeur.',
        '所选屏幕区域的检查间隔。间隔越长，CPU 占用越低。', 'Tempo entre verificações da área selecionada da tela. Um intervalo mais longo reduz o uso da CPU.', "Tempo tra i controlli dell'area dello schermo selezionata. Un intervallo più lungo riduce l'utilizzo della CPU."),
    'overlay_background': (
        'Opacity of the background behind the live translation, from transparent to solid.',
        'Непрозрачность фона под динамическим переводом: от прозрачного до сплошного.',
        'Opacidad del fondo de la traducción dinámica, de transparente a sólido.',
        'Deckkraft des Hintergrunds der dynamischen Übersetzung: transparent bis undurchsichtig.',
        'Opacité du fond de la traduction dynamique, de transparent à opaque.',
        '动态翻译背景的不透明度，从透明到完全不透明。', 'Opacidade do fundo por trás da tradução ao vivo, de transparente a sólido.', 'Opacità dello sfondo dietro la traduzione dal vivo, da trasparente a solido.'),
    'no_overlay_on_text': (
        'Place the translation away from the recognized text so the original remains visible.',
        'Размещать перевод в стороне от распознанного текста, чтобы оригинал оставался виден.',
        'Coloca la traducción fuera del texto reconocido para mantener visible el original.',
        'Die Übersetzung neben dem erkannten Text platzieren, damit das Original sichtbar bleibt.',
        'Placer la traduction à côté du texte reconnu pour garder l’original visible.',
        '将译文放在识别文本旁边，使原文保持可见。', 'Coloque a tradução longe do texto reconhecido para que o original permaneça visível.', "Posiziona la traduzione lontano dal testo riconosciuto in modo che l'originale rimanga visibile."),
    'source_language': (
        'Language of the original text.', 'Язык исходного текста.',
        'Idioma del texto original.', 'Sprache des Ausgangstextes.',
        'Langue du texte source.', '原文的语言。', 'Idioma do texto original.', 'Lingua del testo originale.'),
    'target_language': (
        'Language to translate into.', 'Язык, на который нужно переводить.',
        'Idioma al que se traduce.', 'Sprache, in die übersetzt wird.',
        'Langue vers laquelle traduire.', '要翻译成的语言。', 'Idioma para o qual traduzir.', 'Lingua in cui tradurre.'),
    'desktop_enabled': (
        'Show the selected companion on the desktop with quick translation actions.',
        'Показывать выбранного маскота на рабочем столе с быстрыми действиями перевода.',
        'Muestra la mascota elegida en el escritorio con acciones rápidas de traducción.',
        'Den gewählten Begleiter mit schnellen Übersetzungsaktionen auf dem Desktop anzeigen.',
        'Afficher le compagnon choisi sur le bureau avec les actions rapides de traduction.',
        '在桌面显示所选吉祥物，并提供快捷翻译操作。', 'Mostrar o mascote escolhido na área de trabalho com ações rápidas de tradução.', 'Mostra sul desktop la mascotte scelta con le azioni rapide di traduzione.'),
    'desktop_main': (
        'Show a companion shortcut in the main window. Click it to open companion settings.',
        'Показывать маскота в главном окне. Нажатие откроет настройки маскота.',
        'Muestra una mascota en la ventana principal. Haz clic para abrir sus ajustes.',
        'Einen Begleiter im Hauptfenster anzeigen. Anklicken öffnet seine Einstellungen.',
        'Afficher le compagnon dans la fenêtre principale. Un clic ouvre ses réglages.',
        '在主窗口中显示吉祥物入口，点击可打开吉祥物设置。', 'Mostrar o mascote na janela principal. Clique nele para abrir suas configurações.', 'Mostra la mascotte nella finestra principale. Un clic apre le sue impostazioni.'),
    'desktop_topmost': (
        'Keep the desktop companion visible above other application windows.',
        'Держать маскота на рабочем столе поверх окон других приложений.',
        'Mantiene la mascota por encima de las ventanas de otras aplicaciones.',
        'Den Desktop-Begleiter über anderen Anwendungsfenstern anzeigen.',
        'Garder le compagnon au-dessus des fenêtres des autres applications.',
        '让桌面吉祥物显示在其他应用窗口上方。', 'Manter o mascote da área de trabalho acima das outras janelas.', 'Mantieni la mascotte sul desktop sopra le altre finestre.'),
    'desktop_home': (
        'Move the desktop companion back to its saved position.',
        'Вернуть маскота на рабочем столе в сохранённое положение.',
        'Devuelve la mascota a su posición guardada en el escritorio.',
        'Den Desktop-Begleiter an seine gespeicherte Position zurücksetzen.',
        'Ramener le compagnon à sa position enregistrée sur le bureau.',
        '将桌面吉祥物移回已保存的位置。', 'Retornar o mascote à posição salva na área de trabalho.', 'Riporta la mascotte alla posizione salvata sul desktop.'),
    'shadow_mode': (
        'Hide the main window and keep translation hotkeys available through the system tray.',
        'Скрыть главное окно и продолжить перевод горячими клавишами. Вернуть окно можно из трея.',
        'Oculta la ventana principal y mantiene los atajos de traducción disponibles en la bandeja.',
        'Das Hauptfenster ausblenden; Übersetzungskürzel bleiben über den Infobereich verfügbar.',
        'Masquer la fenêtre principale et garder les raccourcis de traduction actifs via la zone de notification.',
        '隐藏主窗口，通过系统托盘保留翻译快捷键。', 'Oculte a janela principal e mantenha os atalhos de tradução disponíveis na bandeja do sistema.', 'Nascondi la finestra principale e mantieni le scorciatoie per la traduzione disponibili nella barra delle applicazioni.'),
}


def control_hint(language, key):
    return HINTS[key][LANGUAGES.index(language) if language in LANGUAGES else 0]
