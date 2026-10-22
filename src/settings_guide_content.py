"""Settings guide copy and routes follow the visible settings categories."""
COPY = {
 'ru': (
    'Настройки перевода и результата',
    'Основные настройки: запуск, история, подсказки, проверка обновлений, показ окна, масштаб и размер текста результата с примером.',
    'Перевод и OCR: движки, копирование, замена выделения, восстановление буфера, закрытие результата кликом снаружи и параметры захвата. Все параметры OCR видны сразу.',
    'Языковые пакеты → API',
    'Во вкладке API окна «Языковые пакеты» выберите сервис, введите ключ и ID модели. «Сохранить и выбрать» подключает его к переводу; режим распознавания также выбирает этот сервис для OCR. API необязателен.',
    'Текст результата',
    'В основных настройках стрелки «Текст результата» меняют шрифт перевода. Пример ниже обновляется сразу. «Масштаб» отдельно меняет весь интерфейс.',
    'Закрытие результата',
    '«Закрывать результат кликом снаружи» находится в «Перевод и OCR». Включите, если хотите убирать окно перевода при переходе в другое приложение. По умолчанию выключено.',
    'Запуск перевода выделения',
    'Главное окно → режим «Выделение» → настройки языков, либо «Настроить горячие клавиши» → «Режим выделения». В поле «После выделения» выберите горячую клавишу, кнопку рядом с текстом или немедленный перевод. Это способы запуска одного режима, с теми же языками и переводчиком.',
    'Один запрос распознаёт и переводит изображение выбранной моделью. Для обычного текста используется тот же сервис, если нажать «Сохранить и выбрать». Ключи остаются в системном хранилище и не попадают в экспорт. Облачный сервис может брать плату за запросы.',
 ),
 'en': (
    'Translation and result settings',
    'General: startup, history, tooltips, update checks, result window, interface scale and result text size with a preview.',
    'Translation and OCR: engines, copying, replacing a selection, clipboard restoration, closing results on outside click and capture options. All OCR options are immediately visible.',
    'Language packages → API',
    'In the API tab of Language packages, choose a service and enter its key and model ID. Save and select uses it for translation; a recognition mode also selects it for OCR. API services are optional.',
    'Result text',
    'In General, Result text arrows change the translation font and the preview updates immediately. Scale changes the entire interface separately.',
    'Closing results',
    'Close result on outside click is in Translation and OCR. Enable it to dismiss the translation window when using another app. Off by default.',
    'Starting selection translation',
    'Main window → Selection → language settings, or Configure hotkeys → Selection mode. After selecting chooses a hotkey, a button beside the text, or immediate translation. These are triggers for the same mode, languages and translator.',
    'One request recognizes and translates an image using the chosen model. Save and select also uses this service for plain text. Keys stay in the system vault and are not exported. The cloud service may charge for requests.',
 ),
 'es': (
    'Ajustes de traducción y resultado',
    'General: inicio, historiales, ayudas, actualizaciones, ventana de resultado, escala y tamaño del texto con vista previa.',
    'Traducción y OCR: motores, copia, reemplazo, portapapeles, cierre al pulsar fuera y captura. Las opciones OCR siempre están visibles.',
    'Paquetes de idioma → API',
    'En la pestaña API de Paquetes de idioma, elige un servicio, su clave y el ID del modelo. Guardar y elegir lo usa para traducir; un modo de reconocimiento también lo selecciona para OCR. La API es opcional.',
    'Texto del resultado',
    'En General, las flechas del tamaño del resultado cambian la fuente y actualizan la vista previa. La escala cambia toda la interfaz por separado.',
    'Cerrar resultados',
    'Cerrar resultado al pulsar fuera está en Traducción y OCR. Oculta el resultado al usar otra app. Desactivado de forma predeterminada.',
    'Iniciar la traducción de selección',
    'Ventana principal → Selección → idiomas, o Configurar atajos → Modo Selección. Tras seleccionar permite usar el atajo, mostrar un botón junto al texto o traducir al instante. Usan el mismo modo, idiomas y traductor.',
    'Una petición reconoce y traduce una imagen con el modelo elegido. Guardar y elegir usa el mismo servicio para texto. Las claves quedan en la bóveda del sistema y no se exportan. El servicio puede cobrar por las peticiones.',
 ),
 'de': (
    'Übersetzung und Ergebnis einstellen',
    'Allgemein: Start, Verlauf, Hinweise, Updates, Ergebnisfenster, Skalierung und Textgröße mit Vorschau.',
    'Übersetzung und OCR: Dienste, Kopieren, Auswahl ersetzen, Zwischenablage, Außenklick und Aufnahme. Alle OCR-Optionen sind direkt sichtbar.',
    'Sprachpakete → API',
    'Im API-Tab der Sprachpakete Dienst, Schlüssel und Modell-ID eingeben. Speichern und wählen verwendet den Dienst zur Übersetzung; ein Erkennungsmodus wählt ihn auch für OCR. API-Dienste sind optional.',
    'Ergebnistext',
    'Unter Allgemein ändern die Pfeile beim Ergebnistext die Übersetzungsschrift mit direkter Vorschau. Skalierung ändert separat die gesamte Oberfläche.',
    'Ergebnisse schließen',
    'Ergebnis bei Außenklick schließen befindet sich unter Übersetzung und OCR. Schließt das Ergebnis beim Wechsel zu einer anderen App. Standardmäßig aus.',
    'Auswahlübersetzung starten',
    'Hauptfenster → Auswahl → Spracheinstellungen oder Tastenkürzel → Auswahlmodus. Nach der Auswahl: Tastenkürzel, Schaltfläche neben dem Text oder sofort übersetzen. Derselbe Modus, dieselben Sprachen und derselbe Übersetzer.',
    'Eine Anfrage erkennt und übersetzt ein Bild mit dem gewählten Modell. Speichern und wählen nutzt den Dienst auch für Text. Schlüssel bleiben im Systemtresor und werden nicht exportiert. Der Dienst kann Anfragen berechnen.',
 ),
 'fr': (
    'Réglages de traduction et de résultat',
    'Général : démarrage, historiques, aides, mises à jour, fenêtre de résultat, échelle et taille du texte avec aperçu.',
    'Traduction et OCR : moteurs, copie, remplacement, presse-papiers, fermeture au clic extérieur et capture. Toutes les options OCR restent visibles.',
    'Modules de langue → API',
    'Dans l’onglet API des modules de langue, choisissez un service, sa clé et son identifiant de modèle. Enregistrer et choisir l’utilise pour traduire ; un mode de reconnaissance le choisit aussi pour l’OCR. L’API est facultative.',
    'Texte du résultat',
    'Dans Général, les flèches du texte du résultat changent la police avec aperçu immédiat. L’échelle modifie toute l’interface séparément.',
    'Fermer les résultats',
    'Fermer le résultat au clic extérieur se trouve dans Traduction et OCR. Ferme le résultat lorsque vous utilisez une autre app. Désactivé par défaut.',
    'Démarrer la traduction de sélection',
    'Fenêtre principale → Sélection → langues, ou Configurer les raccourcis → Mode Sélection. Après sélection : raccourci, bouton près du texte ou traduction immédiate. Même mode, mêmes langues et même traducteur.',
    'Une requête reconnaît et traduit une image avec le modèle choisi. Enregistrer et choisir utilise aussi ce service pour le texte. Les clés restent dans le coffre système et ne sont pas exportées. Le service peut facturer les requêtes.',
 ),
 'zh': (
    '翻译与结果设置',
    '常规设置：启动、历史、提示、更新、结果窗口、界面缩放和带预览的结果文字大小。',
    '翻译与 OCR：引擎、复制、替换选中文字、恢复剪贴板、外部点击关闭结果和屏幕捕获。所有 OCR 选项均直接显示。',
    '语言包 → API',
    '在语言包窗口的 API 标签页中选择服务，输入密钥和模型 ID。“保存并选用”将其用于翻译；识别模式也将其用于 OCR。API 为可选功能。',
    '结果文字',
    '常规设置中的结果文字箭头调整译文字体，预览立即更新。缩放单独调整整个界面。',
    '关闭结果',
    '在翻译与 OCR 中启用“点击外部关闭结果”，切换到其他应用时关闭翻译窗口。默认关闭。',
    '启动选中文字翻译',
    '主窗口 → 选中文字 → 语言设置，或设置快捷键 → 选中文字模式。选择文字后可使用快捷键、显示文字旁的按钮或立即翻译。它们使用相同模式、语言和翻译服务。',
    '一次请求使用所选模型识别并翻译图像。“保存并选用”也将此服务用于普通文字。密钥保留在系统密钥库中，不会导出。云服务可能收费。',
 ),
}


def guide_updates(language):
    c = COPY.get(language, COPY['en'])
    return {key: (c[i], c[i+1]) for key, i in (
        ('api_connections', 3), ('result_text', 5), ('result_behavior', 7), ('selection_behavior', 9))}


def update_help(content):
    from selection_options import TEXT
    for lang, sections in content.items():
        c = COPY.get(lang, COPY['en'])
        for index, (title, items) in enumerate(sections):
            if any("OCR</span>" in item for item in items) and any('span' in item for item in items[2:]):
                sections[index] = (c[0], [c[1], c[2], *items])
        sections.append((c[3], [c[4], c[11]]))
        sections.append((c[5], [c[6]]))
        sections.append((c[7], [c[8]]))
        sections.append((c[9], [c[10], TEXT.get(lang, TEXT['en'])[5]]))
