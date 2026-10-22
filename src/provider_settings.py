"""A compact, scrollable connection editor inside the existing settings window."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
                            QLineEdit, QCheckBox, QPushButton, QScrollArea, QFrame)
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
    text = {
        'ru': 'Изображения: {provider} · {model}. Один запрос; отдельный переводчик используется только для обычного текста.',
        'en': 'Images: {provider} · {model}. One request; the separate translator is used only for plain text.',
        'es': 'Imágenes: {provider} · {model}. Una petición; el otro traductor solo se usa para texto.',
        'de': 'Bilder: {provider} · {model}. Eine Anfrage; der separate Übersetzer wird nur für Text verwendet.',
        'fr': 'Images : {provider} · {model}. Une requête ; le traducteur séparé sert uniquement au texte.',
        'zh': '图像：{provider} · {model}。一次请求；单独的翻译服务仅用于普通文本。',
    }
    note.setText(text.get(lang,text['en']).format(provider=BY_KEY[provider].name, model=item['model']) if direct else '')
    note.setVisible(direct)
    for attribute, provider_key in (('translator_combo', config.get('translator_engine', '').lower()),
                                    ('ocr_engine_combo', provider)):
        combo = getattr(settings,attribute,None)
        if combo is not None and provider_key in BY_KEY:
            connection=profile(provider_key,config)
            combo.setToolTip(tooltip_text(f"{BY_KEY[provider_key].name} · {connection['model']}\n{provider_text(lang,'help')}"))


def show_provider_settings(settings, provider=None):
    page = getattr(settings, 'api_connections_page', None)
    from PyQt5 import sip
    if page is None or sip.isdeleted(page) or settings.settings_pages.indexOf(page) < 0:
        page = ProviderSettingsPage(settings)
        settings.api_connections_page = page
        settings.settings_pages.addWidget(page)
    if provider in BY_KEY:
        page.service.setCurrentIndex(page.service.findData(provider))
    settings.settings_pages.setCurrentWidget(page)


class ProviderSettingsPage(QWidget):
    def __init__(self, settings):
        super().__init__(settings.settings_pages)
        from settings_window import DropDownCombo
        from styled_dialogs import install_accent_controls, tooltip_text
        from button_styles import button_qss
        self.settings, self.lang = settings, settings.parent.current_interface_language
        self.drafts = {}
        self.active = None
        tr = lambda key: provider_text(self.lang, key)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(4, 4, 8, 4)
        body.setSpacing(4)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.service = DropDownCombo(content)
        settings._apply_engine_combo_style(self.service)
        for spec in PROVIDERS:
            self.service.addItem(spec.name, spec.key)
        self.address, self.key, self.model = (QLineEdit(content) for _ in range(3))
        self.address.setMaxLength(2048)
        self.model.setMaxLength(200)
        self.key.setMaxLength(8192)
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setClearButtonEnabled(True)
        self.address.setPlaceholderText('https://…/v1')
        self.model.setPlaceholderText('Model ID')
        for name, widget in (('service', self.service), ('address', self.address), ('key', self.key), ('model', self.model)):
            widget.setFixedHeight(28)
            widget.setAccessibleName(tr(name).rstrip(':： '))
            widget.setToolTip(tooltip_text(tr('help') if name == 'service' else tr(name)))
            form.addRow(tr(name), widget)
        body.addLayout(form)
        self.vision = QCheckBox(tr('vision'), content)
        self.direct = QCheckBox(tr('direct'), content)
        self.vision.toggled.connect(lambda checked: self.direct.setEnabled(checked))
        for flag in (self.vision, self.direct):
            flag.setFixedHeight(28)
            flag.setToolTip(tooltip_text(tr('help')))
            body.addWidget(flag)
        self.note = QLabel(tr('help'), content)
        self.note.setObjectName('assistantNote')
        self.note.setWordWrap(True)
        body.addWidget(self.note)
        self.status = QLabel('', content)
        self.status.setObjectName('assistantNote')
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        body.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        footer = QHBoxLayout()
        self.delete = QPushButton(tr('delete'), self)
        self.save = QPushButton(tr('save'), self)
        self.back = QPushButton(tr('back'), self)
        dark = settings.parent.current_theme != 'Светлая'
        for button, role in ((self.delete, 'danger'), (self.save, 'primary'), (self.back, 'secondary')):
            button.setFixedHeight(29)
            button.setStyleSheet(button_qss(dark, role, compact=True))
            footer.addWidget(button)
        outer.addLayout(footer)
        self.save.clicked.connect(self.save_profile)
        self.delete.clicked.connect(self.delete_key)
        self.back.clicked.connect(lambda: settings._set_settings_page(1))
        self.service.currentIndexChanged.connect(self.load_profile)
        install_accent_controls(self, dark=dark)
        self.load_profile()

    def _capture(self):
        return dict(url=self.address.text().strip(), model=self.model.text().strip(),
                    vision=self.vision.isChecked(), direct=self.direct.isChecked(), key=self.key.text())

    def load_profile(self, *_args):
        from provider_secrets import get_key
        if self.active:
            self.drafts[self.active] = self._capture()
        self.active = self.service.currentData()
        spec = BY_KEY[self.active]
        item = self.drafts.get(self.active, profile(self.active, self.settings.parent.config))
        self.address.setText(item['url'])
        # Official-service credentials can never be sent to a custom host.
        self.address.setReadOnly(self.active not in {'openai-compatible', 'libretranslate', 'deepl'})
        self.model.setText(item['model'])
        self.model.setEnabled(spec.protocol not in {'deepl', 'libre'})
        self.key.setText(item.get('key', ''))
        self.key.setPlaceholderText(provider_text(self.lang, 'stored' if get_key(self.active, item['url']) else 'empty'))
        self.vision.setEnabled(spec.vision)
        self.vision.setChecked(item['vision'] and spec.vision)
        self.direct.setChecked(item['direct'] and spec.vision)
        self.direct.setEnabled(self.vision.isChecked())
        self.status.clear()

    def save_profile(self):
        from provider_secrets import set_key
        spec, item = BY_KEY[self.active], self._capture()
        try:
            validate_url(item['url'])
            if self.active == 'deepl' and item['url'] not in {'https://api-free.deepl.com/v2', 'https://api.deepl.com/v2'}:
                raise ProviderError('DeepL API accepts only the official Free or Pro address.')
            if spec.protocol not in {'deepl', 'libre'} and not item['model']:
                raise ProviderError(provider_text(self.lang, 'model'))
        except ProviderError as error:
            self.status.setText(str(error))
            return
        persisted = True
        if item['key']:
            persisted = set_key(self.active, item['url'], item.pop('key'))
        else:
            item.pop('key')
        profiles = dict(self.settings.parent.config.get('api_providers', {}))
        profiles[self.active] = item
        self.settings.auto_save_setting('api_providers', profiles)
        refresh_provider_routing(self.settings)
        self.key.clear()
        from provider_secrets import get_key
        self.key.setPlaceholderText(provider_text(self.lang, 'stored' if get_key(self.active, item['url']) else 'empty'))
        self.drafts[self.active] = item
        self.status.setText(provider_text(self.lang, 'saved' if persisted else 'session'))

    def delete_key(self):
        from provider_secrets import set_key
        persisted = set_key(self.active, profile(self.active, self.settings.parent.config)['url'], '')
        self.key.clear()
        self.drafts.pop(self.active, None)
        self.key.setPlaceholderText(provider_text(self.lang, 'empty'))
        self.status.setText(provider_text(self.lang, 'saved' if persisted else 'session'))
