"""Desktop companion copy, shared by Settings and the optional Qt widget."""

ASSISTANT_TEXT = {
    'en': {
        'tray': 'Desktop assistant', 'preview_hint': 'Configure the desktop assistant',
        'setting': 'Assistant:', 'enabled': 'On desktop', 'title': 'How can I help?',
        'hint': 'Click for translation actions. Drag to move the assistant.',
        'screen': ('Translate entire screen', 'Replace visible text with its translation.'),
        'area': ('Translate an area', 'Select the part of the screen to translate.'),
        'dynamic': ('Dynamic translation', 'Choose a source area and a separate output.'),
        'copy': ('Recognize and copy text', 'Select text on screen to copy it.'),
        'text': ('Open translator', 'Type, edit and translate text.'),
        'documents': ('Translate a document', 'Open a file or continue a saved session.'),
        'settings': 'Settings', 'guide': 'Quick guide', 'hide': 'Hide assistant',
        'hide_hint': 'Enable it again in General settings.', 'dismiss': 'Shoo', 'dismiss_hint': 'Hide the assistant until Click’n’Translate is restarted.',
    },
    'ru': {
        'tray': 'Помощник на рабочем столе', 'preview_hint': 'Настроить помощника на рабочем столе',
        'setting': 'Помощник:', 'enabled': 'На рабочем столе', 'title': 'Чем помочь?',
        'hint': 'Нажмите для выбора перевода. Перетащите помощника в удобное место.',
        'screen': ('Перевести весь экран', 'Заменить видимый текст его переводом.'),
        'area': ('Перевести область', 'Выберите часть экрана для перевода.'),
        'dynamic': ('Динамический перевод', 'Выберите источник и отдельное место вывода.'),
        'copy': ('Распознать и скопировать', 'Выберите текст на экране для копирования.'),
        'text': ('Открыть переводчик', 'Введите, дополните и переведите текст.'),
        'documents': ('Перевести документ', 'Откройте файл или сохранённую сессию.'),
        'settings': 'Настройки', 'guide': 'Обучение', 'hide': 'Скрыть помощника',
        'hide_hint': 'Включить снова можно в основных настройках.', 'dismiss': 'Прогнать', 'dismiss_hint': 'Скрыть помощника до следующего запуска Click’n’Translate.',
    },
    'de': {
        'tray': 'Desktop-Assistent', 'preview_hint': 'Desktop-Assistenten konfigurieren',
        'setting': 'Assistent:', 'enabled': 'Auf dem Desktop', 'title': 'Wie kann ich helfen?',
        'hint': 'Für Übersetzungsaktionen klicken. Zum Verschieben ziehen.',
        'screen': ('Gesamten Bildschirm übersetzen', 'Sichtbaren Text durch die Übersetzung ersetzen.'),
        'area': ('Bereich übersetzen', 'Den gewünschten Bildschirmbereich auswählen.'),
        'dynamic': ('Dynamische Übersetzung', 'Quelle und separaten Ausgabebereich wählen.'),
        'copy': ('Text erkennen und kopieren', 'Text auf dem Bildschirm zum Kopieren wählen.'),
        'text': ('Übersetzer öffnen', 'Text eingeben, bearbeiten und übersetzen.'),
        'documents': ('Dokument übersetzen', 'Datei oder gespeicherte Sitzung öffnen.'),
        'settings': 'Einstellungen', 'guide': 'Anleitung', 'hide': 'Assistent ausblenden',
        'hide_hint': 'In den allgemeinen Einstellungen wieder aktivieren.', 'dismiss': 'Wegschicken', 'dismiss_hint': 'Assistenten bis zum Neustart von Click’n’Translate ausblenden.',
    },
    'es': {
        'tray': 'Asistente de escritorio', 'preview_hint': 'Configurar el asistente de escritorio',
        'setting': 'Asistente:', 'enabled': 'En el escritorio', 'title': '¿Cómo puedo ayudar?',
        'hint': 'Haz clic para traducir. Arrastra el asistente para moverlo.',
        'screen': ('Traducir toda la pantalla', 'Sustituye el texto visible por su traducción.'),
        'area': ('Traducir un área', 'Selecciona la parte de la pantalla a traducir.'),
        'dynamic': ('Traducción dinámica', 'Elige el origen y un área de salida separada.'),
        'copy': ('Reconocer y copiar texto', 'Selecciona texto en pantalla para copiarlo.'),
        'text': ('Abrir traductor', 'Escribe, edita y traduce texto.'),
        'documents': ('Traducir un documento', 'Abre un archivo o una sesión guardada.'),
        'settings': 'Ajustes', 'guide': 'Guía', 'hide': 'Ocultar asistente',
        'hide_hint': 'Puedes activarlo de nuevo en los ajustes generales.', 'dismiss': 'Ahuyentar', 'dismiss_hint': 'Ocultar el asistente hasta reiniciar Click’n’Translate.',
    },
    'fr': {
        'tray': 'Assistant de bureau', 'preview_hint': 'Configurer l’assistant de bureau',
        'setting': 'Assistant :', 'enabled': 'Sur le bureau', 'title': 'Comment vous aider ?',
        'hint': 'Cliquez pour traduire. Faites glisser l’assistant pour le déplacer.',
        'screen': ('Traduire tout l’écran', 'Remplacer le texte visible par sa traduction.'),
        'area': ('Traduire une zone', 'Sélectionnez la partie de l’écran à traduire.'),
        'dynamic': ('Traduction dynamique', 'Choisissez la source et une zone de sortie.'),
        'copy': ('Reconnaître et copier le texte', 'Sélectionnez le texte à copier sur l’écran.'),
        'text': ('Ouvrir le traducteur', 'Saisissez, modifiez et traduisez du texte.'),
        'documents': ('Traduire un document', 'Ouvrez un fichier ou une session enregistrée.'),
        'settings': 'Réglages', 'guide': 'Guide', 'hide': 'Masquer l’assistant',
        'hide_hint': 'Réactivez-le dans les réglages généraux.', 'dismiss': 'Chasser', 'dismiss_hint': 'Masquer l’assistant jusqu’au redémarrage de Click’n’Translate.',
    },
    'zh': {
        'tray': '桌面助手', 'preview_hint': '设置桌面助手',
        'setting': '助手：', 'enabled': '在桌面显示', 'title': '需要什么帮助？',
        'hint': '点击选择翻译功能。拖动助手可调整位置。',
        'screen': ('翻译整个屏幕', '将可见文字替换为译文。'),
        'area': ('翻译区域', '选择需要翻译的屏幕区域。'),
        'dynamic': ('动态翻译', '分别选择识别区域和译文显示区域。'),
        'copy': ('识别并复制文字', '选择屏幕文字并复制。'),
        'text': ('打开翻译器', '输入、编辑并翻译文字。'),
        'documents': ('翻译文档', '打开文件或已保存的会话。'),
        'settings': '设置', 'guide': '使用指南', 'hide': '隐藏助手',
        'hide_hint': '可在常规设置中重新启用。', 'dismiss': '赶走', 'dismiss_hint': '隐藏助手，直到重新启动 Click’n’Translate。',
    },
}


_PREFERENCES = {
    'en': ('Companion', 'Enable desktop companion', 'Click to open the menu; drag to move. Movement pauses under the pointer and during screen capture.', 'Behavior', 'Stand still', 'Walk around', 'Look around', 'Sleep', 'Size', 'Walking speed', 'Opacity', 'Keep above other windows', 'Hop!', 'Return to saved spot', 'Companion settings', 'Enable it again on the Companion settings page.'),
    'ru': ('Маскот', 'Включить маскота на рабочем столе', 'Нажмите для меню, перетащите для перемещения. При наведении он останавливается, во время захвата экрана — скрывается.', 'Поведение', 'Стоять спокойно', 'Гулять по столу', 'Оглядываться', 'Спать', 'Размер', 'Скорость прогулки', 'Непрозрачность', 'Поверх других окон', 'Подпрыгнуть!', 'На своё место', 'Настройки маскота', 'Включить снова можно на странице «Маскот» в настройках.'),
    'de': ('Maskottchen', 'Desktop-Maskottchen aktivieren', 'Klicken öffnet das Menü; ziehen verschiebt es. Bei Mauszeiger und Bildschirmaufnahme pausiert es.', 'Verhalten', 'Still stehen', 'Herumlaufen', 'Umschauen', 'Schlafen', 'Größe', 'Laufgeschwindigkeit', 'Deckkraft', 'Über anderen Fenstern', 'Hüpfen!', 'Zum gespeicherten Platz', 'Maskottchen-Einstellungen', 'Auf der Seite Maskottchen wieder aktivieren.'),
    'es': ('Mascota', 'Activar mascota de escritorio', 'Haz clic para el menú y arrastra para mover. Se detiene al apuntarla y se oculta durante la captura.', 'Comportamiento', 'Quedarse quieta', 'Pasear', 'Mirar alrededor', 'Dormir', 'Tamaño', 'Velocidad', 'Opacidad', 'Encima de otras ventanas', '¡Saltar!', 'Volver a su sitio', 'Ajustes de mascota', 'Actívala de nuevo en la página Mascota.'),
    'fr': ('Mascotte', 'Activer la mascotte du bureau', 'Cliquez pour le menu, glissez pour déplacer. Elle s’arrête sous le pointeur et se cache pendant la capture.', 'Comportement', 'Rester immobile', 'Se promener', 'Regarder autour', 'Dormir', 'Taille', 'Vitesse', 'Opacité', 'Au-dessus des fenêtres', 'Sauter !', 'Revenir à sa place', 'Réglages de la mascotte', 'Réactivez-la sur la page Mascotte.'),
    'zh': ('桌面伙伴', '启用桌面伙伴', '点击打开菜单，拖动可移动。悬停时停止，屏幕捕获时隐藏。', '行为', '安静站立', '桌面散步', '四处看看', '睡觉', '大小', '散步速度', '不透明度', '置于其他窗口上方', '跳一下！', '回到原位', '伙伴设置', '可在“桌面伙伴”设置页重新启用。'),
}
for _language, _values in _PREFERENCES.items():
    ASSISTANT_TEXT[_language].update(zip(('page', 'enable_switch', 'page_hint', 'behavior', 'idle', 'walk', 'look', 'sleep', 'size', 'speed', 'opacity', 'topmost', 'hop', 'home', 'companion_settings', 'hide_hint'), _values))


_SECTIONS = {
    'walking_section': ('Kirby walk', 'Прогулка Кирби', 'Paseo de Kirby', 'Kirbys Spaziergang', 'Promenade de Kirby', '卡比散步'),
    'walking_only': ('Choose Walking to enable movement. Other icons stay still.', 'Выберите «Гуляет», чтобы включить движение. Остальные значки неподвижны.', 'Elige Paseo para activar el movimiento. Los otros iconos son estáticos.', 'Laufend aktiviert die Bewegung. Die übrigen Symbole stehen still.', 'Choisissez Marche pour le mouvement. Les autres icônes restent fixes.', '选择散步卡比可启用移动。其他图标保持静止。'),
    'orb': ('Purple', 'Мордочка', 'Violeta', 'Violett', 'Violet', '紫色伙伴'),
    'walking': ('Walking', 'Гуляет', 'Paseo', 'Laufend', 'Marche', '散步卡比'),
    'pause_walk': ('Pause walk', 'Приостановить', 'Pausar paseo', 'Pause', 'Pause', '暂停散步'),
    'walking_hint': ('Only Walking Kirby moves. Pause here or in its menu; dragging and hovering also pause the walk.', 'Гуляет только этот Кирби. Пауза — здесь или в меню; при наведении и переносе он тоже останавливается.', 'Solo este Kirby pasea. Pausa aquí o en su menú; también se detiene al apuntarlo o arrastrarlo.', 'Nur dieser Kirby läuft. Hier oder im Menü pausieren; Zeiger und Ziehen halten ihn ebenfalls an.', 'Seul ce Kirby marche. Pause ici ou dans son menu ; arrêt aussi au survol et au déplacement.', '只有这个卡比会散步。可在此处或菜单暂停，悬停和拖动时也会暂停。'),
    'speed_short': ('Speed', 'Скорость', 'Velocidad', 'Tempo', 'Vitesse', '速度'),
    'appearance': ('Appearance', 'Внешний вид', 'Apariencia', 'Aussehen', 'Apparence', '外观'),
    'animated': ('Animated', 'Живой', 'Animado', 'Animiert', 'Animé', '动态'),
    'portrait': ('Kirby', 'Кирби', 'Kirby', 'Kirby', 'Kirby', '卡比'),
    'star': ('On a star', 'На звезде', 'En estrella', 'Auf Stern', 'Sur une étoile', '星星上'),
    'sleep_icon': ('Sleepy', 'Сонный', 'Dormido', 'Schläfrig', 'Endormi', '睡觉'),
    'custom': ('My image…', 'Своя…', 'Mi imagen…', 'Eigenes…', 'Mon image…', '自选图片…'),
    'choose_image': ('Choose an image', 'Выбрать картинку', 'Elegir imagen', 'Bild auswählen', 'Choisir une image', '选择图片'),
    'image_error': ('Use a PNG, JPEG or WebP up to 10 MB and 8192 px.', 'Нужен PNG, JPEG или WebP до 10 МБ и 8192 px.', 'Usa PNG, JPEG o WebP de hasta 10 MB y 8192 px.', 'PNG, JPEG oder WebP bis 10 MB und 8192 px verwenden.', 'PNG, JPEG ou WebP jusqu’à 10 Mo et 8192 px.', '请使用不超过 10 MB 和 8192 px 的 PNG、JPEG 或 WebP。'),
    'placement': ('Size and visibility', 'Размер и видимость', 'Tamaño y visibilidad', 'Größe und Sichtbarkeit', 'Taille et visibilité', '大小和可见性'),
    'translation_section': ('Translation', 'Перевод', 'Traducción', 'Übersetzen', 'Traduction', '翻译'),
    'companion_section': ('Companion', 'Маскот', 'Mascota', 'Maskottchen', 'Mascotte', '伙伴'),
    'quick_actions': ('Quick actions', 'Быстрые действия', 'Acciones rápidas', 'Schnellaktionen', 'Actions rapides', '快捷操作'),
    'static_hint': ('Static shortcut: no movement or animation. Click for translation; drag to move.', 'Статичный значок без движения и анимации. Нажмите для перевода, перетащите для перемещения.', 'Icono estático sin animación. Haz clic para traducir; arrastra para mover.', 'Statisches Symbol ohne Animation. Klicken zum Übersetzen, ziehen zum Verschieben.', 'Icône fixe sans animation. Cliquez pour traduire, glissez pour déplacer.', '静态图标，无移动或动画。点击翻译，拖动移动。'),
    'animated_hint': ('Behavior applies only to Animated. Change it here or in the companion menu.', 'Поведение работает только в режиме «Живой». Меняйте его здесь или в меню маскота.', 'El comportamiento solo se aplica a Animado. Cámbialo aquí o en su menú.', 'Verhalten gilt nur für Animiert. Hier oder im Maskottchen-Menü ändern.', 'Le comportement concerne le mode Animé. Modifiez-le ici ou dans le menu.', '行为设置仅适用于动态模式，可在此处或伙伴菜单中修改。'),
}
for _key, _values in _SECTIONS.items():
    for _language, _value in zip(('en', 'ru', 'es', 'de', 'fr', 'zh'), _values):
        ASSISTANT_TEXT[_language][_key] = _value


def assistant_text(language, key):
    return ASSISTANT_TEXT.get(language, ASSISTANT_TEXT['en']).get(key, ASSISTANT_TEXT['en'].get(key, key))
