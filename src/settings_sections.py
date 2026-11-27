"""Stable settings destinations and compact captions for the fixed viewport.

Page numbers 0–3 are public legacy IDs used by the guide and mode editors.
Visual order is deliberately independent of those IDs.
"""

PAGE_APPLICATION = 0
PAGE_TRANSLATION = 1
PAGE_DYNAMIC = 2
PAGE_COMPANION = 3
PAGE_OCR = 4
PAGE_COUNT = 5
VISUAL_PAGE_ORDER = (PAGE_APPLICATION, PAGE_TRANSLATION, PAGE_OCR,
                     PAGE_DYNAMIC, PAGE_COMPANION)

PAGE_CAPTIONS = {
    'en': ('Application', 'Translation', 'Dynamic', 'Companion', 'OCR'),
    'ru': ('Приложение', 'Перевод', 'Динамика', 'Компаньон', 'OCR'),
    'es': ('Aplicación', 'Traducción', 'Dinámica', 'Compañero', 'OCR'),
    'de': ('Anwendung', 'Übersetzung', 'Dynamisch', 'Begleiter', 'OCR'),
    'fr': ('Application', 'Traduction', 'Dynamique', 'Compagnon', 'OCR'),
    'zh': ('程序', '翻译', '动态', '伙伴', 'OCR'),
    'pt': ('Aplicativo', 'Tradução', 'Dinâmica', 'Companheiro', 'OCR'),
    'it': ('Applicazione', 'Traduzione', 'Dinamica', 'Compagno', 'OCR'),
    'ar': ('التطبيق', 'الترجمة', 'مباشر', 'الرفيق', 'OCR'),
    'tr': ('Uygulama', 'Çeviri', 'Dinamik', 'Yardımcı', 'OCR'),
    'hi': ('ऐप', 'अनुवाद', 'डायनामिक', 'साथी', 'OCR'),
    'id': ('Aplikasi', 'Terjemahan', 'Dinamis', 'Pendamping', 'OCR'),
}

_KEYS = ('language', 'language_hint', 'maintenance', 'maintenance_hint',
         'offline', 'offline_hint', 'ocr_packages', 'ocr_packages_hint',
         'api', 'api_hint', 'recognition')
_TEXT = {
    'en': ('Interface language:', 'Choose the language of menus, hints and the guide.',
           'Data and updates', 'Update the application, clear the cache, reset, export or import settings, or create a bug report.',
           'Offline translation', 'Install or remove offline translation models and language pairs.',
           'OCR engines and languages', 'Install or remove text recognition engines and their language packs.',
           'API connections', 'Configure a provider, model and API key for translation, OCR or both.', 'Text recognition:'),
    'ru': ('Язык интерфейса:', 'Выберите язык меню, подсказок и руководства.',
           'Данные и обновления', 'Обновление приложения, очистка кэша, сброс, экспорт и импорт настроек, отчёт о проблеме.',
           'Офлайн-перевод', 'Установите или удалите модели и языковые пары для перевода без интернета.',
           'Движки и языки OCR', 'Установите или удалите движки распознавания текста и их языковые пакеты.',
           'API-подключения', 'Настройте сервис, модель и API-ключ для перевода, распознавания или обоих действий.', 'Распознавание текста:'),
    'es': ('Idioma de interfaz:', 'Elige el idioma de menús, ayudas y guía.',
           'Datos y actualizaciones', 'Actualiza la aplicación, borra caché, restablece, exporta o importa ajustes y crea informes de errores.',
           'Traducción sin conexión', 'Instala o elimina modelos y pares de idiomas para traducir sin Internet.',
           'Motores e idiomas OCR', 'Instala o elimina motores de reconocimiento y sus paquetes de idiomas.',
           'Conexiones API', 'Configura un servicio, modelo y clave API para traducir, reconocer texto o ambas cosas.', 'Reconocimiento de texto:'),
    'de': ('Oberflächensprache:', 'Sprache für Menüs, Hinweise und Anleitung wählen.',
           'Daten und Updates', 'App aktualisieren, Cache leeren, Einstellungen zurücksetzen, exportieren oder importieren und Fehlerberichte erstellen.',
           'Offline-Übersetzung', 'Modelle und Sprachpaare für Übersetzungen ohne Internet installieren oder entfernen.',
           'OCR-Engines und Sprachen', 'Texterkennungs-Engines und ihre Sprachpakete installieren oder entfernen.',
           'API-Verbindungen', 'Dienst, Modell und API-Schlüssel für Übersetzung, Texterkennung oder beides einrichten.', 'Texterkennung:'),
    'fr': ('Langue de l’interface :', 'Choisissez la langue des menus, des aides et du guide.',
           'Données et mises à jour', 'Mettre à jour l’application, vider le cache, réinitialiser, exporter ou importer les réglages et créer un rapport de problème.',
           'Traduction hors ligne', 'Installer ou supprimer les modèles et paires de langues pour traduire sans Internet.',
           'Moteurs et langues OCR', 'Installer ou supprimer les moteurs de reconnaissance et leurs langues.',
           'Connexions API', 'Configurer un service, un modèle et une clé API pour traduire, reconnaître du texte ou les deux.', 'Reconnaissance de texte :'),
    'zh': ('界面语言：', '选择菜单、提示和指南的语言。',
           '数据与更新', '更新程序、清除缓存、重置、导出或导入设置，以及生成问题报告。',
           '离线翻译', '安装或删除离线翻译模型和语言对。',
           'OCR 引擎与语言', '安装或删除文字识别引擎及其语言包。',
           'API 连接', '配置服务、模型和 API 密钥，用于翻译、文字识别或两者。', '文字识别：'),
    'pt': ('Idioma da interface:', 'Escolha o idioma dos menus, dicas e guia.',
           'Dados e atualizações', 'Atualize o aplicativo, limpe o cache, redefina, exporte ou importe configurações e crie um relatório de problema.',
           'Tradução offline', 'Instale ou remova modelos e pares de idiomas para traduzir sem internet.',
           'Motores e idiomas OCR', 'Instale ou remova motores de reconhecimento de texto e seus pacotes de idiomas.',
           'Conexões de API', 'Configure serviço, modelo e chave de API para tradução, reconhecimento de texto ou ambos.', 'Reconhecimento de texto:'),
    'it': ('Lingua interfaccia:', 'Scegli la lingua di menu, suggerimenti e guida.',
           'Dati e aggiornamenti', 'Aggiorna l’app, svuota la cache, ripristina, esporta o importa le impostazioni e crea un rapporto sui problemi.',
           'Traduzione offline', 'Installa o rimuovi modelli e coppie linguistiche per tradurre senza internet.',
           'Motori e lingue OCR', 'Installa o rimuovi motori di riconoscimento e relativi pacchetti lingua.',
           'Connessioni API', 'Configura servizio, modello e chiave API per traduzione, riconoscimento o entrambi.', 'Riconoscimento testo:'),
    'ar': ('لغة الواجهة:', 'اختر لغة القوائم والتلميحات والدليل.',
           'البيانات والتحديثات', 'تحديث التطبيق ومسح التخزين المؤقت وإعادة الضبط وتصدير الإعدادات أو استيرادها وإنشاء تقرير مشكلة.',
           'الترجمة دون اتصال', 'ثبّت نماذج الترجمة وأزواج اللغات للعمل دون الإنترنت أو احذفها.',
           'محركات OCR ولغاتها', 'ثبّت محركات التعرف على النص وحزم لغاتها أو احذفها.',
           'اتصالات API', 'اضبط الخدمة والنموذج ومفتاح API للترجمة أو التعرف على النص أو كليهما.', 'التعرف على النص:'),
    'tr': ('Arayüz dili:', 'Menülerin, ipuçlarının ve kılavuzun dilini seçin.',
           'Veriler ve güncellemeler', 'Uygulamayı güncelleyin, önbelleği temizleyin, ayarları sıfırlayın, dışa veya içe aktarın ve hata raporu oluşturun.',
           'Çevrimdışı çeviri', 'İnternetsiz çeviri için modelleri ve dil çiftlerini yükleyin veya kaldırın.',
           'OCR motorları ve diller', 'Metin tanıma motorlarını ve dil paketlerini yükleyin veya kaldırın.',
           'API bağlantıları', 'Çeviri, metin tanıma veya ikisi için hizmet, model ve API anahtarı ayarlayın.', 'Metin tanıma:'),
    'hi': ('इंटरफ़ेस भाषा:', 'मेनू, संकेत और गाइड की भाषा चुनें।',
           'डेटा और अपडेट', 'ऐप अपडेट करें, कैश साफ़ करें, सेटिंग्स रीसेट, निर्यात या आयात करें और समस्या रिपोर्ट बनाएँ।',
           'ऑफ़लाइन अनुवाद', 'इंटरनेट के बिना अनुवाद के लिए मॉडल और भाषा जोड़ियाँ इंस्टॉल करें या हटाएँ।',
           'OCR इंजन और भाषाएँ', 'टेक्स्ट पहचान इंजन और उनके भाषा पैक इंस्टॉल करें या हटाएँ।',
           'API कनेक्शन', 'अनुवाद, टेक्स्ट पहचान या दोनों के लिए सेवा, मॉडल और API कुंजी सेट करें।', 'टेक्स्ट पहचान:'),
    'id': ('Bahasa antarmuka:', 'Pilih bahasa menu, petunjuk dan panduan.',
           'Data dan pembaruan', 'Perbarui aplikasi, bersihkan cache, reset, ekspor atau impor pengaturan dan buat laporan masalah.',
           'Terjemahan offline', 'Pasang atau hapus model dan pasangan bahasa untuk menerjemahkan tanpa internet.',
           'Mesin dan bahasa OCR', 'Pasang atau hapus mesin pengenalan teks dan paket bahasanya.',
           'Koneksi API', 'Atur layanan, model dan kunci API untuk terjemahan, pengenalan teks atau keduanya.', 'Pengenalan teks:'),
}


_KEYS += ('dim_strength',)
for _locale, _caption in {
        'en': 'Strength:', 'ru': 'Интенсивность:', 'es': 'Intensidad:',
        'de': 'Stärke:', 'fr': 'Intensité :', 'zh': '强度：',
        'pt': 'Intensidade:', 'it': 'Intensità:', 'ar': 'الشدة:',
        'tr': 'Yoğunluk:', 'hi': 'तीव्रता:', 'id': 'Intensitas:'}.items():
    _TEXT[_locale] += (_caption,)


def page_caption(locale, page_id):
    return PAGE_CAPTIONS.get(locale, PAGE_CAPTIONS['en'])[page_id]


def section_text(locale, key):
    return _TEXT.get(locale, _TEXT['en'])[_KEYS.index(key)]
