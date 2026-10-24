"""API connection editor embedded in the language package manager."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
                            QLineEdit, QPushButton, QScrollArea, QFrame)
from api_providers import PROVIDERS, BY_KEY, profile, validate_url, ProviderError

_KEYS = ('connections', 'service', 'address', 'key', 'model', 'vision', 'direct',
         'save', 'back', 'delete', 'saved', 'session', 'help', 'stored', 'empty')
_TEXT = {
 'en': ('API connections', 'Service:', 'API address:', 'API key:', 'Model:', 'Model accepts images',
        'Recognize and translate in one request', 'Save', 'Back', 'Delete key', 'Saved',
        'Saved for this session. The system key vault is unavailable; enter the key again after restarting.',
        'Translation uses the selected service. For OCR, choose this service in the OCR list. One-request mode translates the selected image with this model and skips the separate translator. Keys stay in the system vault and are excluded from exports. API usage may be billed by the service.',
        'Key saved; leave blank to keep it', 'Enter the service API key'),
 'ru': ('API-подключения', 'Сервис:', 'Адрес API:', 'API-ключ:', 'Модель:', 'Модель принимает изображения',
        'Распознавать и переводить одним запросом', 'Сохранить', 'Назад', 'Удалить ключ', 'Сохранено',
        'Ключ сохранён на этот сеанс. Системное хранилище недоступно; после перезапуска введите ключ снова.',
        'Для перевода выберите сервис в списке переводчиков, для распознавания — в списке OCR. Режим одного запроса переводит выделенное изображение этой моделью без отдельного переводчика. Ключи хранятся в системном хранилище и не попадают в экспорт. Сервис может брать плату за запросы.',
        'Ключ сохранён; пустое поле не меняет его', 'Введите API-ключ сервиса'),
 'es': ('Conexiones API', 'Servicio:', 'Dirección API:', 'Clave API:', 'Modelo:', 'El modelo acepta imágenes',
        'Reconocer y traducir en una petición', 'Guardar', 'Atrás', 'Borrar clave', 'Guardado',
        'Clave guardada para esta sesión. La bóveda del sistema no está disponible; vuelve a introducirla tras reiniciar.',
        'Elige el servicio en Traductor o en OCR. El modo de una petición traduce la imagen seleccionada con este modelo sin un traductor adicional. Las claves se guardan en la bóveda del sistema y no se exportan. El servicio puede cobrar por las peticiones.',
        'Clave guardada; deja vacío para conservarla', 'Introduce la clave API del servicio'),
 'de': ('API-Verbindungen', 'Dienst:', 'API-Adresse:', 'API-Schlüssel:', 'Modell:', 'Modell akzeptiert Bilder',
        'Erkennen und übersetzen in einer Anfrage', 'Speichern', 'Zurück', 'Schlüssel löschen', 'Gespeichert',
        'Schlüssel für diese Sitzung gespeichert. Der Systemtresor ist nicht verfügbar; nach dem Neustart erneut eingeben.',
        'Dienst unter Übersetzer oder OCR wählen. Der Ein-Anfrage-Modus übersetzt das ausgewählte Bild mit diesem Modell ohne separaten Übersetzer. Schlüssel bleiben im Systemtresor und werden nicht exportiert. Der Dienst kann Anfragen berechnen.',
        'Schlüssel gespeichert; leer lassen zum Behalten', 'API-Schlüssel eingeben'),
 'fr': ('Connexions API', 'Service :', 'Adresse API :', 'Clé API :', 'Modèle :', 'Le modèle accepte les images',
        'Reconnaître et traduire en une requête', 'Enregistrer', 'Retour', 'Supprimer la clé', 'Enregistré',
        'Clé enregistrée pour cette session. Le coffre système est indisponible ; saisissez-la après le redémarrage.',
        'Choisissez le service dans Traducteur ou OCR. Le mode une requête traduit l’image sélectionnée avec ce modèle sans autre traducteur. Les clés restent dans le coffre système et ne sont pas exportées. Le service peut facturer les requêtes.',
        'Clé enregistrée ; laisser vide pour la conserver', 'Saisissez la clé API du service'),
 'zh': ('API 连接', '服务：', 'API 地址：', 'API 密钥：', '模型：', '模型支持图像输入',
        '在一次请求中识别并翻译', '保存', '返回', '删除密钥', '已保存',
        '密钥仅保存于本次会话。系统密钥库不可用，重启后需要重新输入。',
        '在翻译或 OCR 列表中选择服务。一次请求模式使用此模型翻译所选图像，不再调用其他翻译服务。密钥保存在系统密钥库中，不会导出。服务可能按请求收费。',
        '已保存密钥；留空保留', '输入服务的 API 密钥'),

    'pt': ('Conexões de API',
     'Serviço:',
     'Endereço da API:',
     'Chave de API:',
     'Modelo:',
     'Modelo aceita imagens',
     'Reconheça e traduza em uma solicitação',
     'Salvar',
     'Voltar',
     'Excluir chave',
     'Salvo',
     'Salvo para esta sessão. O cofre de chaves do sistema não está disponível; digite a chave '
     'novamente após reiniciar.',
     'A tradução utiliza o serviço selecionado. Para OCR, escolha este serviço na lista de OCR. O modo '
     'de solicitação única traduz a imagem selecionada com este modelo e ignora o tradutor separado. '
     'As chaves permanecem no cofre do sistema e são excluídas das exportações. O uso da API pode ser '
     'cobrado pelo serviço.',
     'Chave salva; deixe em branco para mantê-la',
     'Insira a chave da API do serviço'),
    'it': ('Connessioni API',
     'Servizio:',
     "Indirizzo dell'API:",
     'Chiave API:',
     'Modello:',
     'Il modello accetta immagini',
     'Riconoscere e tradurre in una sola richiesta',
     'Salva',
     'Indietro',
     'Cancella chiave',
     'Salvato',
     "Salvato per questa sessione. L'insieme di credenziali delle chiavi di sistema non è disponibile; "
     'immettere nuovamente la chiave dopo il riavvio.',
     "La traduzione utilizza il servizio selezionato. Per OCR, scegli questo servizio nell'elenco OCR. "
     "La modalità a richiesta singola traduce l'immagine selezionata con questo modello e salta il "
     'traduttore separato. Le chiavi rimangono nel caveau del sistema e sono escluse dalle '
     "esportazioni. L'utilizzo dell'API può essere fatturato dal servizio.",
     'Chiave salvata; lascia vuoto per conservarla',
     'Inserisci la chiave API del servizio'),

 'ar': ('اتصالات API',
  'الخدمة:',
  'عنوان API:',
  'مفتاح API:',
  'النموذج:',
  'النموذج يدعم الصور',
  'التعرف والترجمة في طلب واحد',
  'حفظ',
  'رجوع',
  'حذف المفتاح',
  'تم الحفظ',
  'حُفظ لهذه الجلسة فقط. مخزن مفاتيح النظام غير متاح؛ أدخل المفتاح مجددًا بعد إعادة التشغيل.',
  'تستخدم الترجمة الخدمة المختارة. للتعرف على النص، اختر الخدمة نفسها من قائمة OCR. يترجم وضع الطلب '
  'الواحد الصورة المحددة بهذا النموذج ويتجاوز المترجم المنفصل. تبقى المفاتيح في مخزن النظام '
  'وتُستبعد من التصدير. قد تفرض الخدمة رسومًا على استخدام API.',
  'المفتاح محفوظ؛ اترك الحقل فارغًا للإبقاء عليه',
  'أدخل مفتاح API للخدمة'),

 'tr': ('API bağlantıları',
  'Hizmet:',
  'API adresi:',
  'API anahtarı:',
  'Model:',
  'Model görüntü kabul eder',
  'Tek istekte tanı ve çevir',
  'Kaydet',
  'Geri',
  'Anahtarı sil',
  'Kaydedildi',
  'Bu oturum için kaydedildi. Sistem anahtar kasası kullanılamıyor; yeniden başlattıktan sonra '
  'anahtarı tekrar girin.',
  'Çeviri seçilen hizmeti kullanır. OCR için aynı hizmeti OCR listesinden seçin. Tek istek modu '
  'görüntüyü bu modelle çevirir ve ayrı çevirmeni atlar. Anahtarlar sistem kasasında tutulur, dışa '
  'aktarılmaz. API kullanımını hizmet ücretlendirebilir.',
  'Anahtar kayıtlı; korumak için boş bırakın',
  'Hizmetin API anahtarını girin'),
 'hi': ('API कनेक्शन',
  'सेवा:',
  'API पता:',
  'API कुंजी:',
  'मॉडल:',
  'मॉडल इमेज स्वीकारता है',
  'एक अनुरोध में पहचान और अनुवाद',
  'सहेजें',
  'वापस',
  'कुंजी हटाएँ',
  'सहेजा गया',
  'इस सत्र के लिए सहेजा। सिस्टम कुंजी भंडार उपलब्ध नहीं है; दोबारा शुरू करने पर कुंजी फिर डालें।',
  'अनुवाद चुनी सेवा से होता है। OCR के लिए इसी सेवा को OCR सूची में चुनें। एक-अनुरोध मोड इसी मॉडल '
  'से इमेज का अनुवाद करता है और अलग अनुवादक छोड़ता है। कुंजियाँ सिस्टम भंडार में रहती हैं, निर्यात '
  'में नहीं जातीं। सेवा API उपयोग का शुल्क ले सकती है।',
  'कुंजी सहेजी है; रखने के लिए खाली छोड़ें',
  'सेवा की API कुंजी डालें'),
 'id': ('Koneksi API',
  'Layanan:',
  'Alamat API:',
  'Kunci API:',
  'Model:',
  'Model menerima gambar',
  'Kenali dan terjemahkan dalam satu permintaan',
  'Simpan',
  'Kembali',
  'Hapus kunci',
  'Disimpan',
  'Disimpan untuk sesi ini. Brankas kunci sistem tidak tersedia; masukkan kunci lagi setelah '
  'memulai ulang.',
  'Terjemahan memakai layanan pilihan. Untuk OCR, pilih layanan ini di daftar OCR. Mode satu '
  'permintaan menerjemahkan gambar dengan model ini tanpa penerjemah terpisah. Kunci disimpan di '
  'brankas sistem dan tidak diekspor. Layanan dapat mengenakan biaya API.',
  'Kunci tersimpan; kosongkan untuk mempertahankan',
  'Masukkan kunci API layanan'),
}


def provider_text(lang, key):
    return _TEXT.get(lang, _TEXT['en'])[_KEYS.index(key)]


def refresh_provider_routing(settings):
    from api_providers import VISION_ENGINES
    from styled_dialogs import tooltip_text
    from PyQt5 import sip
    config = settings.parent.config
    lang = settings.parent.current_interface_language
    note = getattr(settings, 'provider_routing_note', None)
    if note is None or sip.isdeleted(note):
        return
    provider = VISION_ENGINES.get(config.get('ocr_engine'))
    item = profile(provider, config) if provider else {}
    direct = bool(item.get('direct') and item.get('vision'))
    from provider_catalog import provider_id
    shared = direct and provider_id(config.get('translator_engine')) == provider
    settings.translator_combo.setEnabled(not shared)
    settings.translator_engine_label.setEnabled(not shared)
    text = {
        'ru': 'Изображения: {provider} · {model}. Один запрос; отдельный переводчик используется только для обычного текста.',
        'en': 'Images: {provider} · {model}. One request; the separate translator is used only for plain text.',
        'es': 'Imágenes: {provider} · {model}. Una petición; el otro traductor solo se usa para texto.',
        'de': 'Bilder: {provider} · {model}. Eine Anfrage; der separate Übersetzer wird nur für Text verwendet.',
        'fr': 'Images : {provider} · {model}. Une requête ; le traducteur séparé sert uniquement au texte.',
        'zh': '图像：{provider} · {model}。一次请求；单独的翻译服务仅用于普通文本。',

        'pt': 'Imagens: {provider} · {model}. Um pedido; o tradutor separado é usado apenas para texto simples.',
        'it': ('Immagini: {provider} · {model}. Una richiesta; il traduttore separato viene utilizzato solo per '
         'il testo semplice.'),

        'ar': 'الصور: {provider} · {model}. طلب واحد؛ يُستخدم المترجم المنفصل للنص العادي فقط.',

        'tr': 'Görüntüler: {provider} · {model}. Tek istek; ayrı çevirmen yalnızca düz metin için kullanılır.',
        'hi': 'इमेज: {provider} · {model}। एक अनुरोध; अलग अनुवादक सिर्फ़ साधारण टेक्स्ट के लिए है।',
        'id': 'Gambar: {provider} · {model}. Satu permintaan; penerjemah terpisah hanya untuk teks biasa.',
    }
    description = text.get(lang,text['en']).format(provider=BY_KEY[provider].name, model=item['model']) if direct else ''
    captions = {
        'ru': ('Один API: ', 'API изображений: '), 'en': ('One API: ', 'Image API: '),
        'es': ('Una API: ', 'API de imagen: '), 'de': ('Eine API: ', 'Bild-API: '),
        'fr': ('Une API : ', 'API d’image : '), 'zh': ('统一 API：', '图像 API：'),

        'pt': ('Uma API: ', 'API de imagem: '),
        'it': ("Un'API: ", 'API immagine: '),

        'ar': ('API واحد: ', 'API للصور: '),

        'tr': ('Tek API: ', "Görüntü API'si: "),
        'hi': ('एक API: ', 'इमेज API: '),
        'id': ('Satu API: ', 'API gambar: '),
    }
    import html
    note.setText(captions.get(lang,captions['en'])[0 if shared else 1] +
                 '<a href="api">' + html.escape(BY_KEY[provider].name) + '</a>' if direct else '')
    note.setToolTip(tooltip_text(description + '\n' + provider_text(lang,'help')) if direct else '')
    note.setVisible(direct)
    for attribute, provider_key in (('translator_combo', config.get('translator_engine', '').lower()),
                                    ('ocr_engine_combo', provider)):
        combo = getattr(settings,attribute,None)
        if combo is not None and provider_key in BY_KEY:
            connection=profile(provider_key,config)
            combo.setToolTip(tooltip_text(f"{BY_KEY[provider_key].name} · {connection['model']}\n{provider_text(lang,'help')}"))


EXTRA = {
 'ru': ('Режим:', 'Только перевод текста', 'Распознавание текста (OCR)', 'Распознавание и перевод', 'Сохранить и выбрать', 'Настройте сервис, затем выберите его для перевода и OCR.', 'Выбран для перевода.', 'Выбран для перевода и OCR.', 'Укажите ID модели в поле «Модель».', 'API'),
 'en': ('Use for:', 'Text translation only', 'Text recognition (OCR)', 'Recognition and translation', 'Save and select', 'Configure a service, then select it for translation and OCR.', 'Selected for translation.', 'Selected for translation and OCR.', 'Enter a model ID in the Model field.', 'API'),
 'es': ('Modo:', 'Solo traducción de texto', 'Reconocimiento de texto (OCR)', 'Reconocimiento y traducción', 'Guardar y elegir', 'Configura un servicio y selecciónalo para traducción y OCR.', 'Elegido para traducir.', 'Elegido para traducción y OCR.', 'Introduce el ID del modelo.', 'API'),
 'de': ('Modus:', 'Nur Textübersetzung', 'Texterkennung (OCR)', 'Erkennen und übersetzen', 'Speichern und wählen', 'Dienst einrichten und für Übersetzung und OCR auswählen.', 'Für Übersetzung ausgewählt.', 'Für Übersetzung und OCR ausgewählt.', 'Geben Sie eine Modell-ID ein.', 'API'),
 'fr': ('Mode :', 'Traduction de texte seule', 'Reconnaissance de texte (OCR)', 'Reconnaissance et traduction', 'Enregistrer et choisir', 'Configurez un service, puis sélectionnez-le pour la traduction et l’OCR.', 'Choisi pour la traduction.', 'Choisi pour la traduction et l’OCR.', 'Saisissez un identifiant de modèle.', 'API'),
 'zh': ('模式：', '仅翻译文字', '文字识别 (OCR)', '识别并翻译', '保存并选用', '配置服务，然后将其用于翻译和 OCR。', '已选择用于翻译。', '已选择用于翻译和 OCR。', '请输入模型 ID。', 'API'),

    'pt': ('Modo:',
     'Apenas tradução de texto',
     'Reconhecimento de texto (OCR)',
     'Reconhecimento e tradução',
     'Salvar e selecionar',
     'Configure um serviço e selecione-o para tradução e OCR.',
     'Selecionado para tradução.',
     'Selecionado para tradução e OCR.',
     'Insira um ID de modelo no campo Modelo.',
     'API'),
    'it': ('Modalità:',
     'Solo traduzione del testo',
     'Riconoscimento del testo (OCR)',
     'Riconoscimento e traduzione',
     'Salva e seleziona',
     "Configura un servizio, quindi selezionalo per la traduzione e l'OCR.",
     'Selezionato per la traduzione.',
     'Selezionato per traduzione e OCR.',
     'Immettere un ID modello nel campo Modello.',
     'API'),

 'ar': ('الاستخدام:',
  'ترجمة النص فقط',
  'التعرف على النص (OCR)',
  'التعرف والترجمة',
  'حفظ واختيار',
  'اضبط خدمة ثم اخترها للترجمة والتعرف على النص.',
  'تم اختيارها للترجمة.',
  'تم اختيارها للترجمة والتعرف على النص.',
  'أدخل معرّف النموذج في حقل النموذج.',
  'API'),

 'tr': ('Kullanım:',
  'Yalnızca metin çevirisi',
  'Metin tanıma (OCR)',
  'Tanıma ve çeviri',
  'Kaydet ve seç',
  'Hizmeti ayarlayıp çeviri ve OCR için seçin.',
  'Çeviri için seçildi.',
  'Çeviri ve OCR için seçildi.',
  'Model alanına model kimliğini girin.',
  'API'),
 'hi': ('उपयोग:',
  'सिर्फ़ टेक्स्ट अनुवाद',
  'टेक्स्ट पहचान (OCR)',
  'पहचान और अनुवाद',
  'सहेजें और चुनें',
  'सेवा सेट करके अनुवाद और OCR के लिए चुनें।',
  'अनुवाद के लिए चुना गया।',
  'अनुवाद और OCR के लिए चुना गया।',
  'मॉडल बॉक्स में मॉडल ID डालें।',
  'API'),
 'id': ('Gunakan untuk:',
  'Terjemahan teks saja',
  'Pengenalan teks (OCR)',
  'Pengenalan dan terjemahan',
  'Simpan dan pilih',
  'Atur layanan, lalu pilih untuk terjemahan dan OCR.',
  'Dipilih untuk terjemahan.',
  'Dipilih untuk terjemahan dan OCR.',
  'Masukkan ID model di kolom Model.',
  'API'),
}


def connection_text(lang, index):
    return EXTRA.get(lang, EXTRA['en'])[index]


def show_provider_settings(settings, provider=None):
    """API connections live beside installed OCR and translation packages."""
    settings.show_ocr_language_manager()
    dialog = settings._language_manager_dialog
    page = dialog.show_api(provider)
    settings.api_connections_page = page
    return page


class ProviderSettingsPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        from settings_window import DropDownCombo
        from styled_dialogs import tooltip_text
        from PyQt5.QtWidgets import QSizePolicy
        self.settings = settings
        self.app = settings.parent if not callable(settings.parent) else settings.parent()
        self.lang = self.app.current_interface_language
        self.drafts, self.active = {}, None
        self.setObjectName('apiConnectionsPage')
        tr = lambda key: provider_text(self.lang, key)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 10, 0, 0)
        outer.setSpacing(8)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName('apiConnectionsContent')
        body = QVBoxLayout(content)
        body.setContentsMargins(2, 0, 8, 0)
        body.setSpacing(8)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.service = DropDownCombo(content)
        for spec in PROVIDERS:
            self.service.addItem(spec.name, spec.key)
        self.address, self.key, self.model = (QLineEdit(content) for _ in range(3))
        for technical_field in (self.address, self.key, self.model):
            technical_field.setLayoutDirection(Qt.LeftToRight)
            technical_field.setAlignment(Qt.AlignLeft)
        self.address.setMaxLength(2048)
        self.model.setMaxLength(200)
        self.key.setMaxLength(8192)
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setClearButtonEnabled(True)
        self.address.setPlaceholderText('https://…/v1')
        model_placeholder = {
            'en': 'Model ID', 'ru': 'ID модели', 'es': 'ID del modelo', 'de': 'Modell-ID',
            'fr': 'ID du modèle', 'zh': '模型 ID', 'pt': 'ID do modelo', 'it': 'ID del modello',

            'ar': 'معرّف النموذج',

            'tr': 'Model kimliği',
            'hi': 'मॉडल ID',
            'id': 'ID model',
        }
        self.model.setPlaceholderText(model_placeholder.get(self.lang,model_placeholder['en']))
        self.labels = []
        for name, widget in (('service', self.service), ('address', self.address), ('key', self.key), ('model', self.model)):
            widget.setMinimumHeight(32)
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            widget.setAccessibleName(tr(name).rstrip(':： '))
            widget.setToolTip(tooltip_text(tr('help') if name == 'service' else tr(name)))
            label = QLabel(tr(name), content)
            label.setBuddy(widget)
            label.setMinimumWidth(label.sizeHint().width())
            self.labels.append(label)
            form.addRow(label, widget)
        self.usage = DropDownCombo(content)
        self.usage.setMinimumHeight(32)
        self.usage.setAccessibleName(connection_text(self.lang, 0))
        self.usage.setToolTip(tooltip_text(tr('help')))
        label = QLabel(connection_text(self.lang, 0), content)
        label.setBuddy(self.usage)
        self.labels.append(label)
        form.addRow(label, self.usage)
        body.addLayout(form)
        self.note = QLabel(connection_text(self.lang, 5), content)
        self.note.setObjectName('apiConnectionHint')
        self.note.setWordWrap(True)
        self.note.setToolTip(tooltip_text(tr('help')))
        body.addWidget(self.note)
        self.status = QLabel('', content)
        self.status.setObjectName('apiConnectionStatus')
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        body.addStretch(1)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll, 1)
        footer = QHBoxLayout()
        footer.setSpacing(6)
        self.delete = QPushButton(tr('delete'), self)
        self.save = QPushButton(tr('save'), self)
        self.use = QPushButton(connection_text(self.lang, 4), self)
        for button in (self.delete, self.save, self.use):
            button.setMinimumHeight(32)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            footer.addWidget(button, 1)
        outer.addLayout(footer)
        self.save.clicked.connect(self.save_profile)
        self.use.clicked.connect(self.select_profile)
        self.delete.clicked.connect(self.delete_key)
        self.service.currentIndexChanged.connect(self.load_profile)
        self.address.textChanged.connect(lambda text: self.address.setToolTip(tooltip_text(text)))
        self.apply_theme()
        self.load_profile()

    def apply_theme(self):
        from settings_window import modern_combo_style
        from styled_dialogs import install_accent_controls, set_widget_stylesheet
        from button_styles import button_qss
        dark = self.app.current_theme != 'Светлая'
        field, text, border = ('#17181d', '#f4f6fb', '#34313f') if dark else ('#f3eff5', '#241f2a', '#bcb2c7')
        muted = '#aaa0b8' if dark else '#71667d'
        set_widget_stylesheet(self, f"""
            QWidget#apiConnectionsPage, QWidget#apiConnectionsContent, QScrollArea {{ background:transparent; border:none; }}
            QLabel {{ color:{text}; font-size:13px; background:transparent; }}
            QLabel#apiConnectionHint, QLabel#apiConnectionStatus {{ color:{muted}; font-size:12px; }}
            QLineEdit {{ color:{text}; background:{field}; border:1px solid {border}; border-radius:6px; padding:3px 8px; font-size:14px; }}
            QLineEdit:focus {{ border-color:#9B78C8; }}
        """)
        for combo in (self.service, self.usage):
            set_widget_stylesheet(combo, modern_combo_style(dark, font_size=14))
            combo.set_popup_background(field)
        for button, role in ((self.delete, 'danger'), (self.save, 'secondary'), (self.use, 'primary')):
            set_widget_stylesheet(button, button_qss(dark, role, compact=True))
        install_accent_controls(self, dark=dark)
        # Stylesheet fonts must also inform the form's label measurements.
        self.ensurePolished()
        for label in self.labels:
            label.ensurePolished()
            label.setMinimumWidth(label.sizeHint().width())

    def _capture(self):
        usage = self.usage.currentData()
        return dict(url=self.address.text().strip(), model=self.model.text().strip(),
                    vision=usage in ('ocr', 'direct'), direct=usage == 'direct', key=self.key.text())

    def load_profile(self, *_args):
        from provider_secrets import get_key
        if self.active:
            self.drafts[self.active] = self._capture()
        self.active = self.service.currentData()
        spec = BY_KEY[self.active]
        item = self.drafts.get(self.active, profile(self.active, self.app.config))
        self.address.setText(item['url'])
        self.address.setReadOnly(self.active not in {'openai-compatible', 'libretranslate', 'deepl'})
        self.model.setText(item['model'])
        self.model.setEnabled(spec.protocol not in {'deepl', 'libre'})
        self.key.setText(item.get('key', ''))
        self.key.setPlaceholderText(provider_text(self.lang, 'stored' if get_key(self.active, item['url']) else 'empty'))
        self.usage.clear()
        for index, code in ((1, 'text'), (2, 'ocr'), (3, 'direct')):
            if index == 1 or spec.vision:
                self.usage.addItem(connection_text(self.lang, index), code)
        usage = ('direct' if item['direct'] else 'ocr') if item['vision'] and spec.vision else 'text'
        self.usage.setCurrentIndex(max(0, self.usage.findData(usage)))
        self.usage.setEnabled(spec.vision)
        self.status.clear()

    def save_profile(self):
        from provider_secrets import set_key, get_key
        spec, item = BY_KEY[self.active], self._capture()
        try:
            validate_url(item['url'])
            if self.active == 'deepl' and item['url'] not in {'https://api-free.deepl.com/v2', 'https://api.deepl.com/v2'}:
                raise ProviderError('DeepL API accepts only the official Free or Pro address.')
            if spec.protocol not in {'deepl', 'libre'} and not item['model']:
                raise ProviderError(connection_text(self.lang, 8))
        except ProviderError as error:
            from api_providers import display_error
            self.status.setText(str(error) if str(error) == connection_text(self.lang, 8)
                                else display_error(error, self.lang))
            return False
        persisted = True
        if item['key']:
            persisted = set_key(self.active, item['url'], item.pop('key'))
        else:
            item.pop('key')
        profiles = dict(self.app.config.get('api_providers', {}))
        profiles[self.active] = item
        self.settings.auto_save_setting('api_providers', profiles)
        refresh_provider_routing(self.settings)
        self.key.clear()
        self.key.setPlaceholderText(provider_text(self.lang, 'stored' if get_key(self.active, item['url']) else 'empty'))
        self.drafts[self.active] = item
        self.status.setText(provider_text(self.lang, 'saved' if persisted else 'session'))
        return True

    def select_profile(self):
        if not self.save_profile():
            return
        from api_providers import VISION_ENGINES, validate
        try:
            validate(self.active, self.app.config)
        except ProviderError as error:
            from api_providers import display_error
            self.status.setText(display_error(error, self.lang))
            return
        status = self.status.text()
        self.settings._set_translator_combo_silently(self.active)
        self.settings.auto_save_setting('translator_engine', self.active)
        item = profile(self.active, self.app.config)
        if item['vision']:
            engine = next(name for name, key in VISION_ENGINES.items() if key == self.active)
            self.settings.ocr_engine_combo.setCurrentIndex(self.settings.ocr_engine_combo.findData(engine))
        refresh_provider_routing(self.settings)
        self.status.setText(connection_text(self.lang, 7 if item['vision'] else 6) + ' ' + status)

    def delete_key(self):
        from provider_secrets import set_key
        persisted = set_key(self.active, profile(self.active, self.app.config)['url'], '')
        self.key.clear()
        self.drafts.pop(self.active, None)
        self.key.setPlaceholderText(provider_text(self.lang, 'empty'))
        self.status.setText(provider_text(self.lang, 'saved' if persisted else 'session'))
