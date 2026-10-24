"""Shared onboarding recommendations and localized setup copy.

Recommendations are applied only by the user's guide action, through the
real settings controls. Opening or skipping a step never changes a setting.
"""

from button_styles import button_qss, standard_buttons
from settings_sections import PAGE_APPLICATION, PAGE_TRANSLATION, PAGE_OCR, PAGE_DYNAMIC
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

    'pt': ('Configure a tradução para você',
     'Comece pelo início automático e pela bandeja. Depois configure a tradução, a captura e os '
     'atalhos. Cada etapa explica a opção e permite aplicá-la. Você pode deixar qualquer recomendação '
     'para depois.',
     'Configure o aplicativo'),
    'it': ('Configura la traduzione per te',
     'Inizia dall’avvio automatico e dall’area di notifica, poi configura traduzione, acquisizione e '
     'scorciatoie. Ogni passaggio spiega un’opzione e permette di applicarla. Puoi rimandare qualsiasi '
     'consiglio.',
     "Configura l'app"),

    'ar': ('اضبط الترجمة بما يناسبك',
     'ابدأ بالتشغيل التلقائي وأيقونة شريط النظام، ثم اضبط الترجمة والالتقاط والاختصارات. توضح كل خطوة '
     'فائدتها وتتيح تطبيق الإعداد. يمكنك تأجيل أي اقتراح.',
     'إعداد التطبيق'),

    'tr': ('Çeviriyi kendinize göre ayarlayın',
     'Otomatik başlangıç ve tepsiyle başlayın; sonra çeviri, yakalama ve kısayolları ayarlayın. Her '
     'adım faydasını açıklar ve ayarı uygulamanızı sağlar. Önerileri erteleyebilirsiniz.',
     'Uygulamayı ayarla'),
    'hi': ('अनुवाद को अपने अनुकूल बनाएँ',
     'अपने आप शुरू करने और ट्रे से शुरू करें, फिर अनुवाद, कैप्चर और शॉर्टकट सेट करें। हर कदम फ़ायदा '
     'समझाकर सेटिंग लागू करने देता है। सुझाव बाद के लिए छोड़ सकते हैं।',
     'ऐप सेट करें'),
    'id': ('Sesuaikan terjemahan untuk Anda',
     'Mulai dengan mulai otomatis dan baki sistem, lalu atur terjemahan, tangkapan, dan pintasan. '
     'Setiap langkah menjelaskan manfaat dan menerapkan pengaturan. Semua rekomendasi boleh ditunda.',
     'Siapkan aplikasi'),
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

    'pt': {'hotkeys': 'No Linux, atribua atalhos nas configurações de teclado da sua área de trabalho. '
                'Vincule sua combinação preferida a clickntranslate --ocr. A edição de um campo no '
                'aplicativo não registra um atalho do sistema.',
     'shortcut_selection': 'Selecione o texto em outro aplicativo. Nas configurações do teclado Linux, '
                           'atribua um atalho a clickntranslate --selection para traduzir esse texto.',
     'shortcut_replace': 'A substituição de seleção automática está atualmente disponível apenas no '
                         'Windows. No Linux, traduza a seleção e cole o resultado manualmente.',
     'ocr_engine': 'Linux suporta Tesseract, EasyOCR e RapidOCR. Instale o motor escolhido e seus '
                   'pacotes de idiomas antes do reconhecimento. Windows OCR não está disponível aqui.'},
    'it': {'hotkeys': 'Su Linux, assegna scorciatoie nelle impostazioni della tastiera del desktop. Associa '
                'la tua combinazione preferita a clickntranslate --ocr. La modifica di un campo in-app '
                'non registra un collegamento di sistema.',
     'shortcut_selection': "Seleziona il testo in un'altra app. Nelle impostazioni della tastiera "
                           'Linux, assegna una scorciatoia a clickntranslate --selection per tradurre '
                           'quel testo.',
     'shortcut_replace': 'La sostituzione automatica della selezione è attualmente disponibile solo su '
                         'Windows. Su Linux, traduci la selezione e incolla il risultato manualmente.',
     'ocr_engine': 'Linux supporta Tesseract, EasyOCR e RapidOCR. Installare il motore scelto ed i '
                   'relativi pacchetti lingua prima del riconoscimento. Windows OCR non è disponibile '
                   'qui.'},

    'ar': {'hotkeys': 'في Linux، عيّن الاختصارات في إعدادات لوحة المفاتيح لسطح المكتب. اربط الاختصار المطلوب '
                'بالأمر clickntranslate --ocr. تعديل الحقل داخل التطبيق لا يسجّل اختصارًا في النظام.',
     'shortcut_selection': 'حدد نصًا في تطبيق آخر. في إعدادات لوحة المفاتيح في Linux، عيّن اختصارًا '
                           'للأمر clickntranslate --selection لترجمة هذا النص.',
     'shortcut_replace': 'الاستبدال التلقائي للنص المحدد متاح حاليًا في Windows فقط. في Linux، ترجم '
                         'النص المحدد والصق النتيجة يدويًا.',
     'ocr_engine': 'يدعم Linux محركات Tesseract وEasyOCR وRapidOCR. ثبّت المحرك المختار وحزم لغاته قبل '
                   'التعرف على النص. Windows OCR غير متاح هنا.'},

    'tr': {'hotkeys': "Linux'ta masaüstünün klavye ayarlarından kısayol atayın. İstediğiniz birleşimi "
                'clickntranslate --ocr komutuna bağlayın. Uygulamadaki alanı değiştirmek sistem '
                'kısayolu oluşturmaz.',
     'shortcut_selection': 'Başka uygulamada metin seçin. Linux klavye ayarlarında clickntranslate '
                           '--selection komutuna kısayol atayın.',
     'shortcut_replace': "Otomatik seçim değiştirme yalnızca Windows'ta kullanılabilir. Linux'ta "
                         'seçimi çevirip sonucu elle yapıştırın.',
     'ocr_engine': 'Linux Tesseract, EasyOCR ve RapidOCR destekler. Tanımadan önce motoru ve dil '
                   'paketlerini kurun. Windows OCR burada yoktur.'},
    'hi': {'hotkeys': 'Linux में डेस्कटॉप की कीबोर्ड सेटिंग्स से शॉर्टकट बनाएँ। अपनी कुंजी जोड़ी '
                'clickntranslate --ocr से जोड़ें। ऐप का बॉक्स बदलने से सिस्टम शॉर्टकट नहीं बनता।',
     'shortcut_selection': 'दूसरे ऐप में टेक्स्ट चुनें। Linux की कीबोर्ड सेटिंग्स में clickntranslate '
                           '--selection का शॉर्टकट बनाएँ।',
     'shortcut_replace': 'चयन अपने आप बदलना अभी सिर्फ़ Windows पर है। Linux में चयन का अनुवाद करके '
                         'परिणाम खुद चिपकाएँ।',
     'ocr_engine': 'Linux में Tesseract, EasyOCR और RapidOCR हैं। पहचान से पहले इंजन और भाषा पैकेज '
                   'इंस्टॉल करें। यहाँ Windows OCR नहीं है।'},
    'id': {'hotkeys': 'Di Linux, atur pintasan pada pengaturan papan ketik desktop. Hubungkan kombinasi '
                'pilihan ke clickntranslate --ocr. Mengedit kolom dalam aplikasi tidak mendaftarkan '
                'pintasan sistem.',
     'shortcut_selection': 'Pilih teks di aplikasi lain. Di pengaturan papan ketik Linux, tetapkan '
                           'pintasan ke clickntranslate --selection untuk menerjemahkannya.',
     'shortcut_replace': 'Penggantian pilihan otomatis saat ini hanya tersedia di Windows. Di Linux, '
                         'terjemahkan pilihan lalu tempel hasil secara manual.',
     'ocr_engine': 'Linux mendukung Tesseract, EasyOCR, dan RapidOCR. Pasang mesin dan paket bahasanya '
                   'sebelum pengenalan. Windows OCR tidak tersedia di sini.'},
}

# config key: (settings widget, page index, recommended value)
GUIDE_SETTING_STEPS = {
    "autostart": ("autostart_checkbox", PAGE_APPLICATION, True),
    "start_minimized": ("start_minimized_checkbox", PAGE_APPLICATION, True),
    "copy_translated_text": ("copy_translated_checkbox", PAGE_TRANSLATION, True),
    "history": ("history_checkbox", PAGE_APPLICATION, True),
    "copy_history": ("copy_history_checkbox", PAGE_APPLICATION, True),
    "keep_visible_on_ocr": ("keep_visible_checkbox", PAGE_OCR, False),
    "freeze_screen_on_ocr": ("freeze_screen_checkbox", PAGE_OCR, True),
    "dim_screen_during_ocr": ("dim_screen_during_ocr_checkbox", PAGE_OCR, True),
    "restore_clipboard_after_selection": ("restore_clipboard_checkbox", PAGE_TRANSLATION, True),
    "notifications": ("copy_notification_checkbox", PAGE_OCR, True),
    "update_check_on_launch": ("update_check_on_launch_checkbox", PAGE_APPLICATION, True),
    "game_pause_when_inactive": ("game_pause_inactive_checkbox", PAGE_DYNAMIC, True),
}

GUIDE_SETUP_CHAPTERS = (
    ("startup", ("settings", "autostart", "start_minimized", "history", "copy_history", "update_check_on_launch")),
    ("translation", ("settings_page_updates", "translator", "copy_translated_text", "restore_clipboard_after_selection", "result_window", "result_behavior", "language_packages", "api_connections")),
    ("capture", ("ocr_engine", "keep_visible_on_ocr", "freeze_screen_on_ocr", "dim_screen_during_ocr", "notifications")),
    ("dynamic", ("settings_page_game", "game_controls", "game_pause_when_inactive")),
    ("finish", ("settings_page_main", "result_text", "selection_behavior", "hotkeys", "back_home", "shortcut_overview", "shortcut_toggle", "shortcut_selection", "shortcut_replace", "main_translate")),
)
GUIDE_SETUP_ORDER = tuple(action for _chapter, actions in GUIDE_SETUP_CHAPTERS for action in actions)
GUIDE_CHAPTER_BY_ACTION = {action: chapter for chapter, actions in GUIDE_SETUP_CHAPTERS for action in actions}

GUIDE_SETUP_LABELS = {
    "ru": {
        "completed": "Гайд завершён",
        "startup": "Удобный запуск", "translation": "Перевод", "capture": "Захват экрана", "dynamic": "Динамический перевод", "finish": "Последние штрихи",
        "enable": "Включить и дальше", "disable": "Выключить и дальше", "next": "Далее", "later": "Позже", "open": "Открыть", "close": "Завершить гайд",
        "ready": "Уже настроено", "recommended": "Рекомендуем включить", "recommended_off": "Рекомендуем выключить", "inspect": "Проверьте настройку и продолжайте",
        "failed": "Настройка не применилась. Попробуйте ещё раз.", "done": "Можно переводить!", "done_body": "Готово полезных настроек: {ready} из {total}. Остальные можно включить позже. Гайд доступен в справке.", "finish_button": "Начать работу",
    },
    "en": {
        "completed": "Guide complete",
        "startup": "Everyday setup", "translation": "Translation", "capture": "Screen capture", "dynamic": "Dynamic translation", "finish": "Finishing touches",
        "enable": "Enable and next", "disable": "Disable and next", "next": "Next", "later": "Later", "open": "Open", "close": "Close guide",
        "ready": "Already configured", "recommended": "Recommended: on", "recommended_off": "Recommended: off", "inspect": "Check the setting, then continue",
        "failed": "The setting did not apply. Please try again.", "done": "Ready to translate!", "done_body": "{ready} of {total} recommended settings are ready. You can change the rest later and reopen this guide from Help.", "finish_button": "Start using the app",
    },
    "es": {
        "completed": "Guía completada",
        "startup": "Uso diario", "translation": "Traducción", "capture": "Captura de pantalla", "dynamic": "Traducción dinámica", "finish": "Últimos ajustes",
        "enable": "Activar y seguir", "disable": "Desactivar y seguir", "next": "Siguiente", "later": "Después", "open": "Abrir", "close": "Cerrar guía",
        "ready": "Ya configurado", "recommended": "Recomendado: activar", "recommended_off": "Recomendado: desactivar", "inspect": "Revisa el ajuste y continúa",
        "failed": "No se aplicó el ajuste. Inténtalo de nuevo.", "done": "¡Todo listo para traducir!", "done_body": "Hay {ready} de {total} ajustes recomendados listos. Puedes cambiar el resto después y abrir la guía desde Ayuda.", "finish_button": "Empezar",
    },
    "de": {
        "completed": "Anleitung abgeschlossen",
        "startup": "Für den Alltag", "translation": "Übersetzung", "capture": "Bildschirmaufnahme", "dynamic": "Dynamische Übersetzung", "finish": "Letzte Schritte",
        "enable": "Aktivieren & weiter", "disable": "Deaktivieren & weiter", "next": "Weiter", "later": "Später", "open": "Öffnen", "close": "Anleitung schließen",
        "ready": "Bereits eingerichtet", "recommended": "Empfehlung: aktivieren", "recommended_off": "Empfehlung: deaktivieren", "inspect": "Einstellung prüfen und fortfahren",
        "failed": "Einstellung nicht übernommen. Bitte erneut versuchen.", "done": "Bereit zum Übersetzen!", "done_body": "{ready} von {total} empfohlenen Einstellungen sind bereit. Den Rest können Sie später ändern. Die Anleitung bleibt in der Hilfe verfügbar.", "finish_button": "Loslegen",
    },
    "fr": {
        "completed": "Guide terminé",
        "startup": "Au quotidien", "translation": "Traduction", "capture": "Capture d’écran", "dynamic": "Traduction dynamique", "finish": "Derniers réglages",
        "enable": "Activer et continuer", "disable": "Désactiver et continuer", "next": "Suivant", "later": "Plus tard", "open": "Ouvrir", "close": "Fermer le guide",
        "ready": "Déjà configuré", "recommended": "Activation conseillée", "recommended_off": "Désactivation conseillée", "inspect": "Vérifiez le réglage, puis continuez",
        "failed": "Le réglage n’a pas été appliqué. Réessayez.", "done": "Prêt à traduire !", "done_body": "{ready} réglages recommandés sur {total} sont prêts. Les autres peuvent attendre. Le guide reste disponible dans l’aide.", "finish_button": "Commencer",
    },
    "zh": {
        "completed": "引导已完成",
        "startup": "日常使用", "translation": "翻译设置", "capture": "屏幕捕获", "dynamic": "动态翻译", "finish": "最后几步",
        "enable": "启用并继续", "disable": "关闭并继续", "next": "下一步", "later": "稍后", "open": "打开", "close": "关闭引导",
        "ready": "已设置", "recommended": "建议启用", "recommended_off": "建议关闭", "inspect": "检查设置后继续",
        "failed": "设置未生效，请重试。", "done": "可以开始翻译了！", "done_body": "已完成 {total} 项推荐设置中的 {ready} 项。其余可稍后修改，也可从帮助中重新打开引导。", "finish_button": "开始使用",
    },

    'pt': {'completed': 'Guia completo',
     'startup': 'Configuração diária',
     'translation': 'Tradução',
     'capture': 'Captura de tela',
     'dynamic': 'Tradução dinâmica',
     'finish': 'Toques finais',
     'enable': 'Ativar e avançar',
     'disable': 'Desativar e avançar',
     'next': 'Avançar',
     'later': 'Mais tarde',
     'open': 'Abrir',
     'close': 'Fechar guia',
     'ready': 'Já configurado',
     'recommended': 'Recomendado: ativado',
     'recommended_off': 'Recomendado: desativado',
     'inspect': 'Verifique a configuração e continue',
     'failed': 'A configuração não se aplica. Por favor, tente novamente.',
     'done': 'Pronto para traduzir!',
     'done_body': '{ready} de {total} configurações recomendadas estão prontas. Você pode alterar as '
                  'outras depois e reabrir este guia na Ajuda.',
     'finish_button': 'Comece a usar o aplicativo'},
    'it': {'completed': 'Guida completata',
     'startup': 'Configurazione quotidiana',
     'translation': 'Traduzione',
     'capture': 'Cattura dello schermo',
     'dynamic': 'Traduzione dinamica',
     'finish': 'Tocchi finali',
     'enable': 'Attiva e avanti',
     'disable': 'Disattiva e avanti',
     'next': 'Avanti',
     'later': 'Più tardi',
     'open': 'Apri',
     'close': 'Chiudi guida',
     'ready': 'Già configurato',
     'recommended': 'Consigliato: attivo',
     'recommended_off': 'Consigliato: disattivato',
     'inspect': "Controllare l'impostazione, quindi continuare",
     'failed': "L'impostazione non è stata applicata. Per favore riprova.",
     'done': 'Pronto per tradurre!',
     'done_body': '{ready} impostazioni consigliate su {total} sono pronte. Puoi modificare le altre '
                  'in seguito e riaprire questa guida da Aiuto.',
     'finish_button': "Inizia a utilizzare l'app"},

    'ar': {'completed': 'اكتمل الدليل',
     'startup': 'الإعداد اليومي',
     'translation': 'الترجمة',
     'capture': 'التقاط الشاشة',
     'dynamic': 'الترجمة المستمرة',
     'finish': 'اللمسات الأخيرة',
     'enable': 'تفعيل ثم التالي',
     'disable': 'تعطيل ثم التالي',
     'next': 'التالي',
     'later': 'لاحقًا',
     'open': 'فتح',
     'close': 'إغلاق الدليل',
     'ready': 'تم إعداده بالفعل',
     'recommended': 'المقترح: مفعّل',
     'recommended_off': 'المقترح: معطّل',
     'inspect': 'تحقق من الإعداد ثم تابع',
     'failed': 'لم يُطبَّق الإعداد. حاول مرة أخرى.',
     'done': 'كل شيء جاهز للترجمة!',
     'done_body': 'اكتمل {ready} من أصل {total} إعدادًا مقترحًا. يمكنك تغيير الباقي لاحقًا وإعادة فتح '
                  'هذا الدليل من المساعدة.',
     'finish_button': 'بدء استخدام التطبيق'},

    'tr': {'completed': 'Rehber tamamlandı',
     'startup': 'Günlük kullanım',
     'translation': 'Çeviri',
     'capture': 'Ekran yakalama',
     'dynamic': 'Dinamik çeviri',
     'finish': 'Son dokunuşlar',
     'enable': 'Aç ve ilerle',
     'disable': 'Kapat ve ilerle',
     'next': 'İleri',
     'later': 'Daha sonra',
     'open': 'Aç',
     'close': 'Rehberi kapat',
     'ready': 'Zaten ayarlandı',
     'recommended': 'Önerilen: açık',
     'recommended_off': 'Önerilen: kapalı',
     'inspect': 'Ayarı kontrol edip devam edin',
     'failed': 'Ayar uygulanmadı. Tekrar deneyin.',
     'done': 'Çeviriye hazırsınız!',
     'done_body': '{total} önerilen ayardan {ready} tanesi hazır. Kalanları sonra değiştirebilir, '
                  "rehberi Yardım'dan yeniden açabilirsiniz.",
     'finish_button': 'Uygulamayı kullanmaya başla'},
    'hi': {'completed': 'गाइड पूरा हुआ',
     'startup': 'रोज़मर्रा की सेटिंग्स',
     'translation': 'अनुवाद',
     'capture': 'स्क्रीन कैप्चर',
     'dynamic': 'गतिशील अनुवाद',
     'finish': 'अंतिम सेटिंग्स',
     'enable': 'चालू करें और आगे बढ़ें',
     'disable': 'बंद करें और आगे बढ़ें',
     'next': 'अगला',
     'later': 'बाद में',
     'open': 'खोलें',
     'close': 'गाइड बंद करें',
     'ready': 'पहले से सेट है',
     'recommended': 'सुझाव: चालू',
     'recommended_off': 'सुझाव: बंद',
     'inspect': 'सेटिंग जाँचकर आगे बढ़ें',
     'failed': 'सेटिंग लागू नहीं हुई। फिर कोशिश करें।',
     'done': 'अनुवाद के लिए तैयार!',
     'done_body': '{total} सुझाई सेटिंग्स में से {ready} तैयार हैं। बाकी बाद में बदल सकते हैं और '
                  'सहायता से गाइड फिर खोल सकते हैं।',
     'finish_button': 'ऐप इस्तेमाल करें'},
    'id': {'completed': 'Panduan selesai',
     'startup': 'Pengaturan sehari-hari',
     'translation': 'Terjemahan',
     'capture': 'Tangkapan layar',
     'dynamic': 'Terjemahan dinamis',
     'finish': 'Sentuhan akhir',
     'enable': 'Aktifkan dan lanjut',
     'disable': 'Nonaktifkan dan lanjut',
     'next': 'Berikutnya',
     'later': 'Nanti',
     'open': 'Buka',
     'close': 'Tutup panduan',
     'ready': 'Sudah diatur',
     'recommended': 'Disarankan: aktif',
     'recommended_off': 'Disarankan: nonaktif',
     'inspect': 'Periksa pengaturan, lalu lanjutkan',
     'failed': 'Pengaturan tidak diterapkan. Silakan coba lagi.',
     'done': 'Siap menerjemahkan!',
     'done_body': '{ready} dari {total} pengaturan yang disarankan siap. Ubah sisanya nanti dan buka '
                  'kembali panduan dari Bantuan.',
     'finish_button': 'Mulai gunakan aplikasi'},
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

    'pt': ('Inicie o aplicativo ao fazer login para que a tradução e os atalhos estejam sempre prontas.',
     'Comece escondido na bandeja do sistema em vez de cobrir a área de trabalho. As atalhos continuam '
     'funcionando; o ícone da bandeja traz a janela de volta.',
     'Copie cada tradução finalizada para a área de transferência, pronta para colar em um bate-papo '
     'ou documento.',
     'Salve o texto original e as traduções localmente para poder encontrá-los novamente no histórico '
     'de traduções.',
     'Mantenha o texto reconhecido e copiado no histórico local, mesmo após a alteração da área de '
     'transferência.',
     'Oculte o aplicativo durante a captura da tela para que sua janela não cubra o texto que você '
     'deseja reconhecer.',
     'Congele a imagem durante a seleção da área. Isso facilita capturar texto em vídeos e janelas que '
     'mudam.',
     'Escureça o ambiente para tornar a área selecionada clara. Ajuste a força com o controle '
     'deslizante ao lado.',
     'Restaure sua área de transferência anterior após traduzir uma seleção. Os resultados solicitados '
     'explicitamente na área de transferência permanecem lá.',
     'Uma breve notificação confirma que o texto foi copiado, para que você saiba que o atalho '
     'funcionou.',
     'Verifique se há uma nova versão na inicialização e ofereça uma atualização quando as correções '
     'estiverem disponíveis.',
     'Pause o reconhecimento enquanto você usa outro aplicativo. A tradução dinâmica é retomada quando '
     'você retorna.',
     'Mostre o original acima da tradução para verificar nomes e significados. Desligue-o mais tarde '
     'para uma visualização compacta.'),
    'it': ("Avvia l'app quando accedi in modo che la traduzione e le scorciatoie siano sempre pronti.",
     'Inizia nascosto nella barra delle applicazioni invece di coprire il desktop. I scorciatoie '
     "continuano a funzionare; l'icona nella barra delle applicazioni riporta la finestra.",
     'Copia ogni traduzione completata negli appunti, pronta per essere incollata in una chat o in un '
     'documento.',
     'Salva il testo sorgente e le traduzioni localmente in modo da poterli ritrovare nella cronologia '
     'delle traduzioni.',
     'Conserva il testo riconosciuto e copiato nella cronologia locale, anche dopo la modifica degli '
     'appunti.',
     "Nascondi l'app durante l'acquisizione dello schermo in modo che la sua finestra non copra il "
     'testo che desideri riconoscere.',
     'Congela l’immagine durante la selezione dell’area. Così è più facile acquisire testo da video e '
     'finestre che cambiano.',
     "Oscura l'ambiente circostante per rendere chiara l'area selezionata. Regola la forza con il "
     'cursore accanto ad esso.',
     'Ripristina gli appunti precedenti dopo aver tradotto una selezione. I risultati esplicitamente '
     'richiesti negli appunti rimangono lì.',
     'Una breve notifica conferma che il testo è stato copiato, quindi sai che la scorciatoia ha '
     'funzionato.',
     "Verifica la presenza di una nuova versione all'avvio e offri un aggiornamento quando le "
     'correzioni diventano disponibili.',
     "Metti in pausa il riconoscimento mentre usi un'altra app. La traduzione dinamica riprende al tuo "
     'ritorno.',
     "Mostra l'originale sopra la traduzione per verificare nomi e significato. Spegnilo più tardi per "
     'una visualizzazione compatta.'),

    'ar': ('شغّل التطبيق عند تسجيل الدخول لتكون الترجمة والاختصارات جاهزة دائمًا.',
     'ابدأ مخفيًا في شريط النظام بدلًا من تغطية سطح المكتب. تستمر الاختصارات في العمل، وتعيد أيقونة '
     'شريط النظام إظهار النافذة.',
     'انسخ كل ترجمة مكتملة إلى الحافظة لتكون جاهزة للصق في محادثة أو مستند.',
     'احفظ النصوص الأصلية وترجماتها محليًا للعثور عليها مجددًا في سجل الترجمات.',
     'احتفظ بالنصوص التي جرى التعرف عليها ونسخها في سجل محلي، حتى بعد تغير محتوى الحافظة.',
     'أخفِ التطبيق أثناء التقاط الشاشة حتى لا تحجب نافذته النص المطلوب التعرف عليه.',
     'جمّد الصورة أثناء تحديد المنطقة. يسهل ذلك التقاط النص في الفيديو والنوافذ المتغيرة.',
     'عتّم ما يحيط بالمنطقة المحددة لتوضيحها. اضبط شدة التعتيم باستخدام شريط التمرير بجانب الإعداد.',
     'استعد محتوى الحافظة السابق بعد ترجمة النص المحدد. تبقى النتائج التي طلبت نسخها إلى الحافظة '
     'صراحةً فيها.',
     'يؤكد إشعار قصير نسخ النص لتعرف أن الاختصار قد عمل.',
     'تحقق من وجود إصدار جديد عند بدء التشغيل واقترح التحديث عند توفر إصلاحات.',
     'أوقف التعرف على النص مؤقتًا أثناء استخدام تطبيق آخر. تُستأنف الترجمة المستمرة عند العودة.',
     'أظهر النص الأصلي فوق الترجمة للتحقق من الأسماء والمعنى. يمكنك تعطيله لاحقًا لعرض أكثر اختصارًا.'),

    'tr': ('Çeviri ve kısayolların hazır olması için oturum açıldığında uygulamayı başlatın.',
     'Masaüstünü kaplamak yerine tepside gizli başlayın. Kısayollar çalışır; tepsi simgesi pencereyi '
     'geri getirir.',
     'Her biten çeviriyi sohbet veya belgeye yapıştırmak üzere panoya kopyalayın.',
     'Daha sonra geçmişte bulmak için kaynak metin ve çevirileri yerel kaydedin.',
     'Pano değişse bile tanınan ve kopyalanan metni yerel geçmişte tutun.',
     'Penceresi tanınacak metni kapatmasın diye ekran yakalarken uygulamayı gizleyin.',
     'Alan seçerken görüntüyü dondurun. Video veya değişen pencerelerdeki metni yakalamayı '
     'kolaylaştırır.',
     'Seçili alanı belirginleştirmek için çevresini karartın. Yanındaki kaydırıcıyla gücünü ayarlayın.',
     'Seçim çevirisinden sonra önceki panoyu geri yükleyin. Özellikle panoya istenen sonuçlar orada '
     'kalır.',
     'Kısa bildirim kopyalamayı onaylar; kısayolun çalıştığını anlarsınız.',
     'Başlangıçta yeni sürümü denetleyip düzeltmeler geldiğinde güncelleme önerin.',
     'Başka uygulama kullanırken tanımayı duraklatın. Geri dönünce dinamik çeviri sürer.',
     'Adları ve anlamı kontrol etmek için özgün metni çevirinin üstünde gösterin. Küçük görünüm için '
     'sonra kapatın.'),
    'hi': ('साइन इन पर ऐप शुरू करें ताकि अनुवाद और शॉर्टकट हमेशा तैयार हों।',
     'डेस्कटॉप ढकने की जगह ट्रे में छिपाकर शुरू करें। शॉर्टकट काम करते हैं; ट्रे आइकन विंडो वापस लाता '
     'है।',
     'हर पूरा अनुवाद क्लिपबोर्ड पर कॉपी करें, चैट या दस्तावेज़ में चिपकाने के लिए।',
     'स्रोत और अनुवाद स्थानीय रूप से सहेजें ताकि इतिहास में फिर मिलें।',
     'क्लिपबोर्ड बदलने के बाद भी पहचाना और कॉपी किया टेक्स्ट स्थानीय इतिहास में रखें।',
     'कैप्चर करते समय ऐप छिपाएँ ताकि उसकी विंडो पढ़ने वाला टेक्स्ट न ढके।',
     'क्षेत्र चुनते समय दृश्य स्थिर करें। वीडियो या बदलती विंडो का टेक्स्ट कैप्चर करना आसान होगा।',
     'चुना क्षेत्र स्पष्ट करने के लिए आसपास मंद करें। पास के स्लाइडर से स्तर बदलें।',
     'चयन अनुवाद के बाद पिछला क्लिपबोर्ड लौटाएँ। जिन्हें स्पष्ट रूप से कॉपी करने को कहा हो वे परिणाम '
     'रहते हैं।',
     'छोटी सूचना कॉपी की पुष्टि करती है, ताकि शॉर्टकट चलने का पता हो।',
     'शुरू होते समय नया संस्करण जाँचें और सुधार उपलब्ध हों तो अपडेट सुझाएँ।',
     'दूसरे ऐप में होने पर पहचान रोकें। लौटने पर गतिशील अनुवाद फिर शुरू होगा।',
     'नाम और अर्थ जाँचने के लिए अनुवाद के ऊपर मूल दिखाएँ। छोटा दृश्य चाहिए तो बाद में बंद करें।'),
    'id': ('Jalankan aplikasi saat masuk agar terjemahan dan pintasan selalu siap.',
     'Mulai tersembunyi di baki sistem tanpa menutupi desktop. Pintasan tetap bekerja; ikon baki '
     'mengembalikan jendela.',
     'Salin setiap terjemahan selesai ke papan klip, siap ditempel ke obrolan atau dokumen.',
     'Simpan teks sumber dan terjemahan secara lokal agar dapat ditemukan lagi dalam riwayat.',
     'Simpan teks yang dikenali dan disalin dalam riwayat lokal meskipun papan klip berubah.',
     'Sembunyikan aplikasi saat menangkap layar agar jendelanya tidak menutupi teks yang ingin '
     'dikenali.',
     'Bekukan gambar saat memilih area agar teks dalam video atau jendela berubah lebih mudah '
     'ditangkap.',
     'Redupkan sekeliling agar area pilihan jelas. Sesuaikan kekuatan dengan penggeser di sampingnya.',
     'Pulihkan papan klip sebelumnya setelah menerjemahkan pilihan. Hasil yang diminta secara khusus '
     'untuk disalin tetap ada.',
     'Notifikasi singkat mengonfirmasi teks disalin agar Anda tahu pintasan bekerja.',
     'Periksa versi baru saat mulai dan tawarkan pembaruan saat perbaikan tersedia.',
     'Jeda pengenalan saat memakai aplikasi lain. Terjemahan dinamis dilanjutkan saat Anda kembali.',
     'Tampilkan teks asli di atas terjemahan untuk memeriksa nama dan makna. Nonaktifkan nanti untuk '
     'tampilan ringkas.'),
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
        # QVBoxLayout rounds wrapped label heights down by a pixel, which clips
        # the last line of long translations (the Chinese setup text is the
        # worst case). Grow the card by exactly the shortfall.
        deficit = 0
        for label in (self.title, self.body, self.hint):
            if label.isVisible():
                needed = label.heightForWidth(label.width())
                if label.height() < needed:
                    deficit = max(deficit, needed - label.height())
        if deficit:
            grown = self.geometry()
            grown.setHeight(grown.height() + deficit)
            if grown.bottom() > bounds.bottom():
                grown.moveTop(max(bounds.top(), grown.y() - (grown.bottom() - bounds.bottom())))
            self.setFixedSize(grown.size())
            self.move(grown.topLeft())
            self.layout().activate()
