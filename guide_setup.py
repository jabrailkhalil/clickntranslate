"""Shared onboarding recommendations and localized setup copy.

Recommendations are applied only by the user's guide action, through the
real settings controls. Opening or skipping a step never changes a setting.
"""

from button_styles import button_qss, standard_buttons
from PyQt5.QtCore import QRect, Qt
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy,
    QVBoxLayout,
)

GUIDE_SETUP_INTRO = {
    "ru": ("Настроим перевод под вас", "Начнём с автозапуска и трея, затем настроим перевод, захват экрана и горячие клавиши. У каждого шага есть объяснение и кнопка действия. Любую рекомендацию можно отложить.", "Настроить приложение"),
    "en": ("Make translation work for you", "Start with automatic startup and the tray, then set up translation, capture and shortcuts. Each step explains the benefit and lets you apply the setting. Any recommendation can wait.", "Set up the app"),
    "es": ("Configura tu traductor", "Empezaremos con el inicio automático y la bandeja; después, traducción, captura y atajos. Cada paso explica para qué sirve y permite aplicar el ajuste. Puedes dejar recomendaciones para después.", "Configurar aplicación"),
    "de": ("Übersetzung für Ihren Alltag", "Zuerst Autostart und Infobereich, dann Übersetzung, Aufnahme und Tastenkürzel. Jeder Schritt erklärt den Nutzen und bietet die passende Aktion. Empfehlungen lassen sich überspringen.", "App einrichten"),
    "fr": ("Configurez votre traducteur", "D’abord le démarrage automatique et la zone de notification, puis la traduction, la capture et les raccourcis. Chaque étape explique son intérêt et permet d’appliquer le réglage. Vous pouvez reporter chaque conseil.", "Configurer l’application"),
    "zh": ("让翻译更适合你", "先设置自动启动和托盘，再配置翻译、屏幕截取及快捷键。每一步都会说明用途，并提供直接应用设置的按钮。任何建议都可以稍后再处理。", "设置应用"),
}

GUIDE_LINUX_BODIES = {
    "ru": {
        "hotkeys": "В Linux сочетания задаются в настройках клавиатуры рабочего стола. Привяжите выбранную комбинацию к команде clickntranslate --ocr. Изменение поля внутри приложения не создаёт системное сочетание.",
        "shortcut_selection": "Выделите текст в другой программе. В настройках клавиатуры Linux назначьте сочетание для команды clickntranslate --selection — она переведёт выделенный текст.",
        "shortcut_replace": "Автоматическая замена выделенного текста пока доступна только в Windows. В Linux используйте перевод выделения и вставьте результат вручную.",
        "ocr_engine": "В Linux доступны Tesseract, EasyOCR и RapidOCR. Установите нужный движок и языковые пакеты перед распознаванием. Windows OCR здесь недоступен.",
    },
    "en": {
        "hotkeys": "On Linux, assign shortcuts in your desktop’s keyboard settings. Bind your preferred combination to clickntranslate --ocr. Editing an in-app field does not register a system shortcut.",
        "shortcut_selection": "Select text in another app. In Linux keyboard settings, assign a shortcut to clickntranslate --selection to translate that text.",
        "shortcut_replace": "Automatic selection replacement is currently available only on Windows. On Linux, translate the selection and paste the result manually.",
        "ocr_engine": "Linux supports Tesseract, EasyOCR and RapidOCR. Install the chosen engine and its language packs before recognition. Windows OCR is unavailable here.",
    },
    "es": {
        "hotkeys": "En Linux, configura los atajos en los ajustes de teclado del escritorio. Asigna la combinación a clickntranslate --ocr. Cambiar un campo de la aplicación no crea un atajo del sistema.",
        "shortcut_selection": "Selecciona texto en otra aplicación. En los ajustes de teclado de Linux, asigna un atajo a clickntranslate --selection para traducirlo.",
        "shortcut_replace": "El reemplazo automático solo está disponible en Windows. En Linux, traduce la selección y pega el resultado manualmente.",
        "ocr_engine": "Linux admite Tesseract, EasyOCR y RapidOCR. Instala el motor y sus idiomas antes de reconocer texto. Windows OCR no está disponible aquí.",
    },
    "de": {
        "hotkeys": "Unter Linux richten Sie Kürzel in den Tastatureinstellungen des Desktops ein. Verknüpfen Sie eine Kombination mit clickntranslate --ocr. Ein Feld in der App registriert kein Systemkürzel.",
        "shortcut_selection": "Markieren Sie Text in einer anderen App. Weisen Sie in den Linux-Tastatureinstellungen clickntranslate --selection ein Kürzel zu, um den Text zu übersetzen.",
        "shortcut_replace": "Automatisches Ersetzen ist derzeit nur unter Windows verfügbar. Unter Linux übersetzen Sie die Auswahl und fügen das Ergebnis selbst ein.",
        "ocr_engine": "Linux unterstützt Tesseract, EasyOCR und RapidOCR. Installieren Sie zuerst die Engine und ihre Sprachpakete. Windows OCR ist hier nicht verfügbar.",
    },
    "fr": {
        "hotkeys": "Sous Linux, configurez les raccourcis dans les paramètres du clavier du bureau. Associez une combinaison à clickntranslate --ocr. Un champ de l’application ne crée pas de raccourci système.",
        "shortcut_selection": "Sélectionnez du texte dans une autre application. Dans les paramètres du clavier Linux, associez un raccourci à clickntranslate --selection pour le traduire.",
        "shortcut_replace": "Le remplacement automatique est disponible uniquement sous Windows. Sous Linux, traduisez la sélection puis collez le résultat manuellement.",
        "ocr_engine": "Linux prend en charge Tesseract, EasyOCR et RapidOCR. Installez le moteur et ses langues avant la reconnaissance. Windows OCR n’est pas disponible ici.",
    },
    "zh": {
        "hotkeys": "在 Linux 中，请在桌面环境的键盘设置里绑定快捷键。例如，将所选组合绑定到 clickntranslate --ocr。在应用内修改字段不会注册系统快捷键。",
        "shortcut_selection": "在其他应用中选中文字。在 Linux 键盘设置里，将快捷键绑定到 clickntranslate --selection，即可翻译所选文字。",
        "shortcut_replace": "自动替换选中文字目前仅支持 Windows。在 Linux 中，请先翻译所选文字，再手动粘贴结果。",
        "ocr_engine": "Linux 支持 Tesseract、EasyOCR 和 RapidOCR。识别前请安装相应引擎及语言包。此平台不支持 Windows OCR。",
    },
}

# config key: (settings widget, page index, recommended value)
GUIDE_SETTING_STEPS = {
    "autostart": ("autostart_checkbox", 0, True),
    "start_minimized": ("start_minimized_checkbox", 0, True),
    "copy_translated_text": ("copy_translated_checkbox", 0, True),
    "history": ("history_checkbox", 0, True),
    "copy_history": ("copy_history_checkbox", 0, True),
    "keep_visible_on_ocr": ("keep_visible_checkbox", 1, False),
    "freeze_screen_on_ocr": ("freeze_screen_checkbox", 1, True),
    "dim_screen_during_ocr": ("dim_screen_during_ocr_checkbox", 1, True),
    "restore_clipboard_after_selection": ("restore_clipboard_checkbox", 1, True),
    "notifications": ("copy_notification_checkbox", 1, True),
    "update_check_on_launch": ("update_check_on_launch_checkbox", 1, True),
    "game_pause_when_inactive": ("game_pause_inactive_checkbox", 2, True),
}

GUIDE_SETUP_CHAPTERS = (
    ("startup", ("settings", "autostart", "start_minimized", "copy_translated_text", "history", "copy_history")),
    ("translation", ("ocr_engine", "translator", "result_window", "language_packages")),
    ("capture", ("settings_page_updates", "keep_visible_on_ocr", "freeze_screen_on_ocr", "dim_screen_during_ocr", "restore_clipboard_after_selection", "notifications", "update_check_on_launch")),
    ("dynamic", ("settings_page_game", "game_controls", "game_pause_when_inactive")),
    ("finish", ("settings_page_main", "hotkeys", "back_home", "shortcut_overview", "shortcut_toggle", "shortcut_selection", "shortcut_replace", "main_translate")),
)
GUIDE_SETUP_ORDER = tuple(action for _chapter, actions in GUIDE_SETUP_CHAPTERS for action in actions)
GUIDE_CHAPTER_BY_ACTION = {action: chapter for chapter, actions in GUIDE_SETUP_CHAPTERS for action in actions}

GUIDE_SETUP_LABELS = {
    "ru": {
        "completed": "Гайд завершён",
        "startup": "Удобный запуск", "translation": "Перевод", "capture": "Экран и обновления", "dynamic": "Динамический перевод", "finish": "Последние штрихи",
        "enable": "Включить и дальше", "disable": "Выключить и дальше", "next": "Далее", "later": "Позже", "open": "Открыть", "close": "Завершить гайд",
        "ready": "Уже настроено", "recommended": "Рекомендуем включить", "recommended_off": "Рекомендуем выключить", "inspect": "Проверьте настройку и продолжайте",
        "failed": "Настройка не применилась. Попробуйте ещё раз.", "done": "Можно переводить!", "done_body": "Готово полезных настроек: {ready} из {total}. Остальные можно включить позже. Гайд доступен в справке.", "finish_button": "Начать работу",
    },
    "en": {
        "completed": "Guide complete",
        "startup": "Everyday setup", "translation": "Translation", "capture": "Capture and updates", "dynamic": "Dynamic translation", "finish": "Finishing touches",
        "enable": "Enable and next", "disable": "Disable and next", "next": "Next", "later": "Later", "open": "Open", "close": "Close guide",
        "ready": "Already configured", "recommended": "Recommended: on", "recommended_off": "Recommended: off", "inspect": "Check the setting, then continue",
        "failed": "The setting did not apply. Please try again.", "done": "Ready to translate!", "done_body": "{ready} of {total} recommended settings are ready. You can change the rest later and reopen this guide from Help.", "finish_button": "Start using the app",
    },
    "es": {
        "completed": "Guía completada",
        "startup": "Uso diario", "translation": "Traducción", "capture": "Captura y actualizaciones", "dynamic": "Traducción dinámica", "finish": "Últimos ajustes",
        "enable": "Activar y seguir", "disable": "Desactivar y seguir", "next": "Siguiente", "later": "Después", "open": "Abrir", "close": "Cerrar guía",
        "ready": "Ya configurado", "recommended": "Recomendado: activar", "recommended_off": "Recomendado: desactivar", "inspect": "Revisa el ajuste y continúa",
        "failed": "No se aplicó el ajuste. Inténtalo de nuevo.", "done": "¡Todo listo para traducir!", "done_body": "Hay {ready} de {total} ajustes recomendados listos. Puedes cambiar el resto después y abrir la guía desde Ayuda.", "finish_button": "Empezar",
    },
    "de": {
        "completed": "Anleitung abgeschlossen",
        "startup": "Für den Alltag", "translation": "Übersetzung", "capture": "Aufnahme und Updates", "dynamic": "Dynamische Übersetzung", "finish": "Letzte Schritte",
        "enable": "Aktivieren & weiter", "disable": "Deaktivieren & weiter", "next": "Weiter", "later": "Später", "open": "Öffnen", "close": "Anleitung schließen",
        "ready": "Bereits eingerichtet", "recommended": "Empfehlung: aktivieren", "recommended_off": "Empfehlung: deaktivieren", "inspect": "Einstellung prüfen und fortfahren",
        "failed": "Einstellung nicht übernommen. Bitte erneut versuchen.", "done": "Bereit zum Übersetzen!", "done_body": "{ready} von {total} empfohlenen Einstellungen sind bereit. Den Rest können Sie später ändern. Die Anleitung bleibt in der Hilfe verfügbar.", "finish_button": "Loslegen",
    },
    "fr": {
        "completed": "Guide terminé",
        "startup": "Au quotidien", "translation": "Traduction", "capture": "Capture et mises à jour", "dynamic": "Traduction dynamique", "finish": "Derniers réglages",
        "enable": "Activer et continuer", "disable": "Désactiver et continuer", "next": "Suivant", "later": "Plus tard", "open": "Ouvrir", "close": "Fermer le guide",
        "ready": "Déjà configuré", "recommended": "Activation conseillée", "recommended_off": "Désactivation conseillée", "inspect": "Vérifiez le réglage, puis continuez",
        "failed": "Le réglage n’a pas été appliqué. Réessayez.", "done": "Prêt à traduire !", "done_body": "{ready} réglages recommandés sur {total} sont prêts. Les autres peuvent attendre. Le guide reste disponible dans l’aide.", "finish_button": "Commencer",
    },
    "zh": {
        "completed": "引导已完成",
        "startup": "日常使用", "translation": "翻译设置", "capture": "屏幕与更新", "dynamic": "动态翻译", "finish": "最后几步",
        "enable": "启用并继续", "disable": "关闭并继续", "next": "下一步", "later": "稍后", "open": "打开", "close": "关闭引导",
        "ready": "已设置", "recommended": "建议启用", "recommended_off": "建议关闭", "inspect": "检查设置后继续",
        "failed": "设置未生效，请重试。", "done": "可以开始翻译了！", "done_body": "已完成 {total} 项推荐设置中的 {ready} 项。其余可稍后修改，也可从帮助中重新打开引导。", "finish_button": "开始使用",
    },
}

# Bodies use the same setting order in every language; titles are read from
# the real controls so the guide always names the option the user can see.
GUIDE_SETTING_BODIES = {
    "ru": (
        "Программа будет запускаться после входа в систему. Перевод и горячие клавиши всегда под рукой.",
        "При запуске окно останется в трее и не перекроет рабочий стол. Горячие клавиши продолжат работать; значок в трее вернёт окно.",
        "Готовый перевод сразу попадёт в буфер обмена — его можно вставить в чат или документ.",
        "Сохраняйте исходный текст и перевод локально, чтобы вернуться к ним через историю переводов.",
        "Сохраняйте распознанный и скопированный текст локально. История поможет найти его, даже если буфер обмена уже изменился.",
        "Лучше скрывать окно программы на время захвата: оно не закроет текст, который вы хотите распознать.",
        "При выделении области изображение остановится. Так удобнее захватить текст из видео или меняющегося окна.",
        "Затемнение выделит выбранную область. Силу эффекта можно отрегулировать ползунком рядом.",
        "После перевода выделения возвращайте прежнее содержимое буфера. Если результат нужен именно в буфере, он сохранится там.",
        "Короткое уведомление подтвердит, что текст скопирован. Не придётся гадать, сработало ли сочетание.",
        "Программа проверит наличие новой версии при запуске и предложит обновиться, когда появятся исправления.",
        "Когда вы переключитесь в другую программу, распознавание приостановится. При возврате динамический перевод продолжится.",
        "Показывайте оригинал над переводом, чтобы быстро сверить имена и смысл. Позже эту опцию можно выключить для компактного вида.",
    ),
    "en": (
        "Launch the app when you sign in so translation and hotkeys are always ready.",
        "Start hidden in the system tray instead of covering the desktop. Hotkeys keep working; the tray icon brings the window back.",
        "Copy each finished translation to the clipboard, ready to paste into a chat or document.",
        "Save source text and translations locally so you can find them again in translation history.",
        "Keep recognized and copied text in local history, even after your clipboard changes.",
        "Hide the app while capturing the screen so its window does not cover the text you want to recognize.",
        "Freeze the image while selecting an area. This makes text in videos or changing windows easier to capture.",
        "Dim the surroundings to make the selected area clear. Adjust the strength with the slider beside it.",
        "Restore your previous clipboard after translating a selection. Results explicitly requested in the clipboard remain there.",
        "A short notification confirms that text was copied, so you know the hotkey worked.",
        "Check for a new version at startup and offer an update when fixes become available.",
        "Pause recognition while you use another app. Dynamic translation resumes when you return.",
        "Show the original above the translation to check names and meaning. Turn it off later for a compact view.",
    ),
    "es": (
        "Inicia la aplicación al entrar en el sistema para tener siempre disponibles la traducción y los atajos.",
        "Inicia en la bandeja sin cubrir el escritorio. Los atajos siguen funcionando; el icono de la bandeja recupera la ventana.",
        "Copia cada traducción al portapapeles, lista para pegarla en un chat o documento.",
        "Guarda localmente el texto original y su traducción para consultarlos en el historial.",
        "Conserva el texto reconocido y copiado en el historial local, aunque cambie el portapapeles.",
        "Oculta la aplicación durante la captura para que su ventana no tape el texto que quieres reconocer.",
        "Congela la imagen al seleccionar un área. Facilita capturar texto de vídeos o ventanas que cambian.",
        "Oscurece el entorno para distinguir el área seleccionada. Ajusta la intensidad con el control de al lado.",
        "Restaura el portapapeles anterior tras traducir una selección. Los resultados solicitados en el portapapeles se conservan.",
        "Una notificación breve confirma que se copió el texto y que el atajo funcionó.",
        "Busca nuevas versiones al iniciar y ofrece actualizar cuando haya correcciones.",
        "Pausa el reconocimiento al cambiar de aplicación y reanuda la traducción al volver.",
        "Muestra el original sobre la traducción para comprobar nombres y significado. Puedes ocultarlo después.",
    ),
    "de": (
        "Starten Sie die App bei der Anmeldung, damit Übersetzung und Tastenkürzel immer bereit sind.",
        "Starten Sie im Infobereich, ohne den Desktop zu verdecken. Tastenkürzel bleiben aktiv; das Symbol öffnet das Fenster wieder.",
        "Kopieren Sie fertige Übersetzungen direkt in die Zwischenablage, bereit für Chats und Dokumente.",
        "Speichern Sie Originaltexte und Übersetzungen lokal, um sie im Verlauf wiederzufinden.",
        "Bewahren Sie erkannte und kopierte Texte im lokalen Verlauf auf, auch wenn sich die Zwischenablage ändert.",
        "Blenden Sie das App-Fenster bei der Aufnahme aus, damit es den zu erkennenden Text nicht verdeckt.",
        "Halten Sie das Bild beim Auswählen eines Bereichs an. So lassen sich Texte aus Videos leichter erfassen.",
        "Dunkeln Sie die Umgebung ab, um die Auswahl hervorzuheben. Die Stärke regelt der Schieber daneben.",
        "Stellen Sie die Zwischenablage nach einer Auswahlübersetzung wieder her. Ausdrücklich kopierte Ergebnisse bleiben erhalten.",
        "Eine kurze Meldung bestätigt, dass Text kopiert wurde und das Tastenkürzel funktioniert hat.",
        "Prüfen Sie beim Start auf neue Versionen und erhalten Sie ein Update-Angebot, sobald Verbesserungen verfügbar sind.",
        "Pausieren Sie die Erkennung in anderen Apps. Bei der Rückkehr wird die dynamische Übersetzung fortgesetzt.",
        "Zeigen Sie das Original über der Übersetzung, um Namen und Bedeutung zu prüfen. Später lässt es sich ausblenden.",
    ),
    "fr": (
        "Lancez l’application à la connexion pour que la traduction et les raccourcis soient toujours disponibles.",
        "Démarrez dans la zone de notification sans couvrir le bureau. Les raccourcis restent actifs ; l’icône ramène la fenêtre.",
        "Copiez chaque traduction dans le presse-papiers pour la coller dans un message ou un document.",
        "Conservez localement le texte original et sa traduction pour les retrouver dans l’historique.",
        "Gardez les textes reconnus et copiés dans l’historique local, même si le presse-papiers change.",
        "Masquez l’application pendant la capture pour que sa fenêtre ne couvre pas le texte à reconnaître.",
        "Figez l’image pendant la sélection d’une zone. Cela facilite la capture de textes dans les vidéos.",
        "Assombrissez le reste de l’écran pour distinguer la sélection. Réglez l’intensité avec le curseur voisin.",
        "Restaurez le presse-papiers après la traduction d’une sélection. Les résultats demandés dans le presse-papiers y restent.",
        "Une brève notification confirme la copie du texte et le bon fonctionnement du raccourci.",
        "Vérifiez les nouvelles versions au démarrage et recevez une proposition de mise à jour lorsqu’il y a des corrections.",
        "Mettez la reconnaissance en pause dans une autre application. La traduction reprend à votre retour.",
        "Affichez l’original au-dessus de la traduction pour vérifier les noms et le sens. Vous pourrez le masquer plus tard.",
    ),
    "zh": (
        "登录系统时自动启动应用，让翻译和快捷键随时可用。",
        "启动后留在系统托盘，不遮挡桌面。快捷键继续有效，点击托盘图标即可恢复窗口。",
        "将完成的译文自动复制到剪贴板，方便粘贴到聊天或文档中。",
        "在本地保存原文和译文，以便从翻译历史中再次查看。",
        "在本地历史中保留识别并复制的文字，即使剪贴板已改变也能找回。",
        "捕获屏幕时隐藏应用窗口，避免遮挡需要识别的文字。",
        "选择区域时冻结画面，更容易捕获视频或变化窗口中的文字。",
        "调暗周围画面以突出选区，可用旁边的滑块调整强度。",
        "翻译选中文字后恢复原来的剪贴板内容。明确要求复制的结果仍会保留在剪贴板中。",
        "用简短通知确认文字已复制，方便判断快捷键是否生效。",
        "启动时检查新版本，并在有修复更新时提示升级。",
        "切换到其他应用时暂停识别，返回后继续动态翻译。",
        "在译文上方显示原文，方便核对名称和含义。需要简洁视图时可再关闭。",
    ),
}


def setup_labels(language):
    return GUIDE_SETUP_LABELS.get(language, GUIDE_SETUP_LABELS["en"])


def setting_body(language, action):
    bodies = GUIDE_SETTING_BODIES.get(language, GUIDE_SETTING_BODIES["en"])
    return dict(zip(GUIDE_SETTING_STEPS, bodies))[action]


# A measured Qt layout keeps the card usable in the fixed 700 × 400 window,
# including longer translations and the different font metrics on Linux.
class SetupGuideCard(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("setupGuide")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.chapter = QLabel()
        self.chapter.setObjectName("guideChapter")
        self.chapter.setWordWrap(True)
        self.chapter.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.progress = QLabel()
        self.progress.setObjectName("guideProgress")
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("guideClose")
        self.close_button.setFixedSize(24, 24)
        header.addWidget(self.chapter, 1)
        header.addWidget(self.progress)
        header.addWidget(self.close_button)
        layout.addLayout(header)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
        layout.addWidget(self.progress_bar)
        self.title = QLabel()
        self.title.setObjectName("guideTitle")
        self.body = QLabel()
        self.body.setObjectName("guideBody")
        self.hint = QLabel()
        self.hint.setObjectName("guideHint")
        for label in (self.title, self.body, self.hint):
            label.setWordWrap(True)
            label.setTextFormat(Qt.PlainText)
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            layout.addWidget(label)
        footer = QHBoxLayout()
        self.footer = footer
        footer.setSpacing(8)
        self.skip_button = QPushButton()
        self.skip_button.setObjectName("guideSkip")
        self.primary_button = QPushButton()
        self.primary_button.setObjectName("guidePrimary")
        footer.addWidget(self.skip_button)
        footer.addStretch()
        footer.addWidget(self.primary_button)
        layout.addLayout(footer)
        for button in (self.close_button, self.skip_button, self.primary_button):
            button.setCursor(Qt.PointingHandCursor)
        self._dark = None
        self._compact = False

    def _set_compact(self, compact):
        if compact == self._compact:
            return
        self._compact = compact
        if compact:
            self.layout().removeWidget(self.hint)
            self.footer.insertWidget(0, self.hint, 1)
            self.footer.setStretch(2, 0)
        else:
            self.footer.removeWidget(self.hint)
            self.layout().insertWidget(4, self.hint)
            self.footer.setStretch(1, 1)
        self.layout().setSpacing(4 if compact else 8)
        self.layout().setContentsMargins(16, 6 if compact else 12, 16, 6 if compact else 12)
        self._style_actions()

    def _style_actions(self):
        # A compact guide shares the fixed-height actions used in Settings.
        for button, role in ((self.primary_button, "primary"), (self.skip_button, "quiet")):
            geometry = "QPushButton { min-height:28px; }" if self._compact else ""
            button.setStyleSheet(button_qss(self._dark, role, compact=self._compact) + geometry)
            button.setMinimumWidth(0)
            button.ensurePolished()
            button.setMinimumWidth(button.sizeHint().width())
        self.layout().invalidate()

    def set_dark(self, dark):
        if dark == self._dark:
            return
        self._dark = dark
        background, ink, muted, border, accent, track = (
            ("#20202d", "#f8f5ff", "#beb8cf", "#605374", "#d0b7fa", "#3d354c")
            if dark else
            ("#ffffff", "#272133", "#665d76", "#cdbde2", "#7145aa", "#eae1f5")
        )
        self.setStyleSheet(f"""
            QFrame#setupGuide {{ background: {background}; border: 1px solid {border}; border-radius: 14px; }}
            QLabel {{ background: transparent; border: none; padding: 0; margin: 0; color: {ink}; }}
            QLabel#guideChapter, QLabel#guideProgress {{ color: {accent}; font-size: 11px; font-weight: 600; }}
            QLabel#guideTitle {{ font-size: 16px; font-weight: 700; }}
            QLabel#guideBody {{ color: {muted}; font-size: 13px; }}
            QLabel#guideHint {{ color: {accent}; font-size: 11px; font-weight: 600; }}
            QProgressBar {{ background: {track}; border: none; border-radius: 1px; }}
            QProgressBar::chunk {{ background: {accent}; border-radius: 1px; }}

        """ + standard_buttons(dark, compact=False))
        self._style_actions()

    def _height_for_width(self, width):
        self.ensurePolished()
        self.layout().invalidate()
        return max(self.layout().totalMinimumSize().height(), self.layout().totalHeightForWidth(width))

    def place(self, target_rect=None):
        """Choose a free region, then measure wrapping before fixing geometry."""
        bounds = QRect(12, 48, self.parentWidget().width() - 24, self.parentWidget().height() - 60)
        self.ensurePolished()
        self._set_compact(False)
        # Labels change between steps even when the theme/density stays the same.
        # Include the complete action labels before choosing a free region.
        self._style_actions()
        candidates = []
        if target_rect is not None:
            gap = 10
            spaces = (
                QRect(bounds.left(), bounds.top(), target_rect.left() - gap - bounds.left(), bounds.height()),
                QRect(target_rect.right() + gap + 1, bounds.top(), bounds.right() - target_rect.right() - gap, bounds.height()),
                QRect(bounds.left(), bounds.top(), bounds.width(), target_rect.top() - gap - bounds.top()),
                QRect(bounds.left(), target_rect.bottom() + gap + 1, bounds.width(), bounds.bottom() - target_rect.bottom() - gap),
            )
            for compact in (False, True):
                self._set_compact(compact)
                minimum_width = max(520 if compact else 230, self.layout().totalMinimumSize().width())
                for region in spaces:
                    width = min(bounds.width() if compact else 420, region.width())
                    if width < minimum_width:
                        continue
                    height = self._height_for_width(width)
                    if height > region.height():
                        continue
                    x = max(region.left(), min(target_rect.center().x() - width // 2, region.right() - width + 1))
                    y = max(region.top(), min(target_rect.center().y() - height // 2, region.bottom() - height + 1))
                    rect = QRect(x, y, width, height)
                    distance = (rect.center() - target_rect.center()).manhattanLength()
                    candidates.append((height * 2 + distance, rect))
                if candidates:
                    break
        if candidates:
            rect = min(candidates, key=lambda candidate: candidate[0])[1]
        else:
            # Completion has no target. The fallback also keeps the card inside
            # the window if a third-party layout override leaves no free region.
            self._set_compact(False)
            width = min(420, bounds.width())
            height = self._height_for_width(width)
            rect = QRect(bounds.center().x() - width // 2, bounds.center().y() - height // 2, width, height)
        self.setFixedSize(rect.size())
        self.move(rect.topLeft())
        self.layout().activate()
