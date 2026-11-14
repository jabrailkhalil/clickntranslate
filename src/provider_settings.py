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


_SAVE_ERROR = {
    'en': 'Could not save the connection. Check free space and access to the settings file, then try again.',
    'ru': 'Не удалось сохранить подключение. Проверьте свободное место и доступ к файлу настроек, затем повторите попытку.',
    'es': 'No se pudo guardar la conexión. Comprueba el espacio libre y el acceso al archivo de ajustes e inténtalo de nuevo.',
    'de': 'Die Verbindung konnte nicht gespeichert werden. Speicherplatz und Zugriff auf die Einstellungsdatei prüfen und erneut versuchen.',
    'fr': 'Impossible d’enregistrer la connexion. Vérifiez l’espace libre et l’accès au fichier de réglages, puis réessayez.',
    'zh': '无法保存连接。请检查可用空间和设置文件的访问权限，然后重试。',
    'pt': 'Não foi possível salvar a conexão. Verifique o espaço livre e o acesso ao arquivo de configurações e tente novamente.',
    'it': 'Impossibile salvare la connessione. Controlla lo spazio libero e l’accesso al file delle impostazioni, poi riprova.',
    'ar': 'تعذّر حفظ الاتصال. تحقّق من المساحة المتاحة وصلاحية الوصول إلى ملف الإعدادات، ثم حاول مجددًا.',
    'tr': 'Bağlantı kaydedilemedi. Boş alanı ve ayar dosyasına erişimi kontrol edip yeniden deneyin.',
    'hi': 'कनेक्शन सहेजा नहीं जा सका। खाली स्थान और सेटिंग फ़ाइल की अनुमति जाँचें, फिर कोशिश करें।',
    'id': 'Koneksi tidak dapat disimpan. Periksa ruang kosong dan akses ke berkas pengaturan, lalu coba lagi.',
}


_DELETE_STATUS = {
    'en': ('Key deleted.',
           'Key disabled for this session. Deletion from the system key vault could not be confirmed; the key may be available again after restart.',
           'Save or restore the API address before deleting its saved key.'),
    'ru': ('Ключ удалён.',
           'Ключ отключён на этот сеанс. Не удалось подтвердить удаление из системного хранилища; после перезапуска ключ может снова стать доступен.',
           'Сохраните или восстановите адрес API, прежде чем удалять сохранённый для него ключ.'),
    'es': ('Clave eliminada.',
           'Clave desactivada para esta sesión. No se pudo confirmar su eliminación de la bóveda del sistema; podría volver a estar disponible tras reiniciar.',
           'Guarda o restaura la dirección API antes de eliminar su clave guardada.'),
    'de': ('Schlüssel gelöscht.',
           'Schlüssel für diese Sitzung deaktiviert. Die Löschung aus dem Systemtresor konnte nicht bestätigt werden; nach einem Neustart ist er möglicherweise wieder verfügbar.',
           'API-Adresse speichern oder wiederherstellen, bevor der dafür gespeicherte Schlüssel gelöscht wird.'),
    'fr': ('Clé supprimée.',
           'Clé désactivée pour cette session. La suppression du coffre système n’a pas pu être confirmée ; elle pourrait être disponible à nouveau après le redémarrage.',
           'Enregistrez ou rétablissez l’adresse API avant de supprimer la clé correspondante.'),
    'zh': ('密钥已删除。',
           '密钥已在本次会话中禁用。无法确认是否已从系统密钥库中删除；重启后密钥可能再次可用。',
           '删除已保存的密钥前，请先保存或恢复 API 地址。'),
    'pt': ('Chave excluída.',
           'Chave desativada nesta sessão. Não foi possível confirmar a exclusão do cofre do sistema; a chave poderá ficar disponível novamente após reiniciar.',
           'Salve ou restaure o endereço da API antes de excluir a chave salva para ele.'),
    'it': ('Chiave eliminata.',
           'Chiave disattivata per questa sessione. Non è stato possibile confermare la rimozione dal portachiavi di sistema; potrebbe essere nuovamente disponibile dopo il riavvio.',
           'Salva o ripristina l’indirizzo API prima di eliminare la chiave salvata per esso.'),
    'ar': ('تم حذف المفتاح.',
           'تم تعطيل المفتاح لهذه الجلسة. تعذّر تأكيد حذفه من مخزن مفاتيح النظام؛ قد يصبح متاحًا مرة أخرى بعد إعادة التشغيل.',
           'احفظ عنوان API أو استعده قبل حذف المفتاح المحفوظ له.'),
    'tr': ('Anahtar silindi.',
           'Anahtar bu oturum için devre dışı bırakıldı. Sistem kasasından silindiği doğrulanamadı; yeniden başlatınca tekrar kullanılabilir hale gelebilir.',
           'Kayıtlı anahtarını silmeden önce API adresini kaydedin veya geri yükleyin.'),
    'hi': ('कुंजी हटा दी गई।',
           'इस सत्र के लिए कुंजी बंद कर दी गई है। सिस्टम वॉल्ट से हटने की पुष्टि नहीं हुई; पुनः शुरू करने पर कुंजी फिर उपलब्ध हो सकती है।',
           'सहेजी कुंजी हटाने से पहले API पता सहेजें या पुराना पता वापस रखें।'),
    'id': ('Kunci dihapus.',
           'Kunci dinonaktifkan untuk sesi ini. Penghapusan dari brankas sistem tidak dapat dipastikan; kunci mungkin tersedia lagi setelah memulai ulang.',
           'Simpan atau pulihkan alamat API sebelum menghapus kunci yang tersimpan untuk alamat tersebut.'),
}


_ROUTING = {
 'en': ('After “Save and select”:', 'Text translation: {service}. OCR stays {ocr}.', 'OCR: {service}; then translation: {translator}. Text translator stays unchanged.', 'Images: {service} recognizes and translates in one request. Plain text also uses this service.', 'Selected for OCR only.', 'Save this connection without changing the active translator or OCR engine.', 'This service is currently used for OCR. Choose another OCR engine before disabling image input.'),
 'ru': ('После «Сохранить и выбрать»:', 'Перевод текста: {service}. OCR остаётся {ocr}.', 'Распознавание: {service}; затем перевод: {translator}. Переводчик текста не меняется.', 'Изображения: {service} распознаёт и переводит одним запросом. Обычный текст тоже переводит этот сервис.', 'Выбран только для OCR.', 'Сохранить подключение, не меняя выбранные движки перевода и OCR.', 'Этот сервис сейчас используется для OCR. Сначала выберите другой OCR-движок, затем отключайте распознавание изображений.'),
 'es': ('Después de Guardar y elegir:', 'Traducción de texto: {service}. OCR sigue en {ocr}.', 'OCR: {service}; después, traducción: {translator}. El traductor de texto no cambia.', 'Imágenes: {service} reconoce y traduce en una petición. El texto también usa este servicio.', 'Elegido solo para OCR.', 'Guarda la conexión sin cambiar el traductor ni el motor OCR activos.', 'Este servicio se usa para OCR. Elige otro motor OCR antes de desactivar la entrada de imágenes.'),
 'de': ('Nach Speichern und wählen:', 'Textübersetzung: {service}. OCR bleibt {ocr}.', 'OCR: {service}; danach Übersetzung: {translator}. Der Textübersetzer bleibt unverändert.', 'Bilder: {service} erkennt und übersetzt in einer Anfrage. Auch Text nutzt diesen Dienst.', 'Nur für OCR ausgewählt.', 'Verbindung speichern, ohne den aktiven Übersetzer oder die OCR-Engine zu ändern.', 'Dieser Dienst wird für OCR verwendet. Wählen Sie eine andere OCR-Engine, bevor Sie Bildeingaben deaktivieren.'),
 'fr': ('Après Enregistrer et choisir :', 'Traduction du texte : {service}. L’OCR reste {ocr}.', 'OCR : {service} ; puis traduction : {translator}. Le traducteur de texte ne change pas.', 'Images : {service} reconnaît et traduit en une requête. Le texte utilise aussi ce service.', 'Choisi uniquement pour l’OCR.', 'Enregistrer la connexion sans changer le traducteur ni le moteur OCR actifs.', 'Ce service est utilisé pour l’OCR. Choisissez un autre moteur OCR avant de désactiver les images.'),
 'zh': ('点击“保存并选用”后：', '文字翻译：{service}。OCR 仍为 {ocr}。', 'OCR：{service}；然后由 {translator} 翻译。文字翻译服务保持不变。', '图像：{service} 在一次请求中识别并翻译。普通文字也使用此服务。', '已选择仅用于 OCR。', '保存连接，不更改当前翻译服务或 OCR 引擎。', '此服务正在用于 OCR。请先选择其他 OCR 引擎，再关闭图像输入。'),
 'pt': ('Após Salvar e selecionar:', 'Tradução de texto: {service}. OCR continua em {ocr}.', 'OCR: {service}; depois, tradução: {translator}. O tradutor de texto não muda.', 'Imagens: {service} reconhece e traduz em uma solicitação. O texto também usa esse serviço.', 'Selecionado apenas para OCR.', 'Salve a conexão sem alterar o tradutor ou o motor OCR ativos.', 'Este serviço está em uso para OCR. Escolha outro motor OCR antes de desativar a entrada de imagens.'),
 'it': ('Dopo Salva e seleziona:', 'Traduzione del testo: {service}. OCR rimane {ocr}.', 'OCR: {service}; poi traduzione: {translator}. Il traduttore del testo non cambia.', 'Immagini: {service} riconosce e traduce in una richiesta. Anche il testo usa questo servizio.', 'Selezionato solo per OCR.', 'Salva la connessione senza cambiare il traduttore o il motore OCR attivi.', 'Questo servizio è usato per OCR. Scegli un altro motore OCR prima di disattivare le immagini.'),
 'ar': ('بعد الحفظ والاختيار:', 'ترجمة النص: {service}. يبقى OCR على {ocr}.', 'التعرف: {service}؛ ثم الترجمة: {translator}. لا يتغير مترجم النص.', 'الصور: يتعرف {service} ويترجم في طلب واحد. يستخدم النص العادي الخدمة نفسها.', 'تم اختياره للتعرف على النص فقط.', 'احفظ الاتصال دون تغيير المترجم أو محرك OCR النشط.', 'تُستخدم هذه الخدمة حاليًا للتعرف على النص. اختر محرك OCR آخر قبل تعطيل إدخال الصور.'),
 'tr': ('Kaydet ve seç sonrasında:', 'Metin çevirisi: {service}. OCR, {ocr} olarak kalır.', 'OCR: {service}; ardından çeviri: {translator}. Metin çevirmeni değişmez.', 'Görüntüler: {service} tek istekte tanır ve çevirir. Düz metin de bu hizmeti kullanır.', 'Yalnız OCR için seçildi.', 'Etkin çevirmeni veya OCR motorunu değiştirmeden bağlantıyı kaydedin.', 'Bu hizmet OCR için kullanılıyor. Görüntü girişini kapatmadan önce başka bir OCR motoru seçin.'),
 'hi': ('सहेजें और चुनें के बाद:', 'टेक्स्ट अनुवाद: {service}। OCR {ocr} ही रहेगा।', 'OCR: {service}; फिर अनुवाद: {translator}। टेक्स्ट अनुवादक नहीं बदलता।', 'इमेज: {service} एक अनुरोध में पहचान और अनुवाद करता है। साधारण टेक्स्ट भी यही सेवा इस्तेमाल करता है।', 'सिर्फ़ OCR के लिए चुना गया।', 'सक्रिय अनुवादक या OCR इंजन बदले बिना कनेक्शन सहेजें।', 'यह सेवा अभी OCR के लिए इस्तेमाल हो रही है। इमेज इनपुट बंद करने से पहले दूसरा OCR इंजन चुनें।'),
 'id': ('Setelah Simpan dan pilih:', 'Terjemahan teks: {service}. OCR tetap {ocr}.', 'OCR: {service}; lalu terjemahan: {translator}. Penerjemah teks tidak berubah.', 'Gambar: {service} mengenali dan menerjemahkan dalam satu permintaan. Teks biasa juga memakai layanan ini.', 'Dipilih hanya untuk OCR.', 'Simpan koneksi tanpa mengubah penerjemah atau mesin OCR aktif.', 'Layanan ini sedang dipakai untuk OCR. Pilih mesin OCR lain sebelum menonaktifkan masukan gambar.'),
}


def routing_text(lang, index, **values):
    return _ROUTING.get(lang, _ROUTING['en'])[index].format(**values)


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
        outer.setContentsMargins(0, 8, 0, 0)
        outer.setSpacing(6)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName('apiConnectionsContent')
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)
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
            widget.setFixedHeight(28)
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
        self.usage.setFixedHeight(28)
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
        # Keep the explanation available without repeating a paragraph below
        # the five self-labelled fields on every visit.
        explanation = self.note.text() + '\n\n' + tr('help')
        self.note.hide()
        self.usage.setToolTip(tooltip_text(explanation))
        self.usage.setAccessibleDescription(explanation)
        self.routing_label = QLabel('', content)
        self.routing_label.setObjectName('apiConnectionRouting')
        self.routing_label.setWordWrap(True)
        self.routing_label.setTextFormat(Qt.PlainText)
        body.addWidget(self.routing_label)
        self.status = QLabel('', content)
        self.status.setObjectName('apiConnectionStatus')
        self.status.setWordWrap(True)
        self.status.hide()
        body.addWidget(self.status)
        body.addStretch(1)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll, 1)
        footer = QHBoxLayout()
        footer.setSpacing(6)
        self.delete = QPushButton(tr('delete'), self)
        self.save = QPushButton(tr('save'), self)
        self.use = QPushButton(connection_text(self.lang, 4), self)
        for button, role in ((self.delete, 'danger'), (self.save, 'secondary'), (self.use, 'primary')):
            button.setProperty('buttonRole', role)
            button.setFixedHeight(29)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            footer.addWidget(button, 1)
        outer.addLayout(footer)
        self.save.clicked.connect(self.save_profile)
        self.use.clicked.connect(self.select_profile)
        self.delete.clicked.connect(self.delete_key)
        self.service.currentIndexChanged.connect(self.load_profile)
        self.usage.currentIndexChanged.connect(self._refresh_routing_preview)
        self.model.textChanged.connect(self._refresh_routing_preview)
        self.save.setToolTip(tooltip_text(routing_text(self.lang, 5)))
        self.save.setAccessibleDescription(routing_text(self.lang, 5))
        self.address.textChanged.connect(lambda text: self.address.setToolTip(tooltip_text(text)))
        self.apply_theme()
        self.load_profile()

    def apply_theme(self):
        from PyQt5.QtGui import QColor, QPalette
        from settings_window import compact_combo_style
        from styled_dialogs import install_accent_controls, set_widget_stylesheet
        from button_styles import standard_buttons
        from classic_style import classic_palette
        dark = self.app.current_theme != 'Светлая'
        colors = classic_palette(dark)
        field, text, border, muted = (colors[key] for key in ('field', 'text', 'border', 'muted'))
        set_widget_stylesheet(self, f"""
            QWidget#apiConnectionsPage {{ background:{colors['background']}; border:none; }}
            QWidget#apiConnectionsContent, QScrollArea {{ background:transparent; border:none; }}
            QLabel {{ color:{text}; font-size:14px; background:transparent; }}
            QLabel#apiConnectionHint, QLabel#apiConnectionStatus, QLabel#apiConnectionRouting {{ color:{muted}; font-size:12px; }}
            QLineEdit {{ color:{text}; background:{field}; border:1px solid {border}; border-radius:6px; margin:0; padding:1px 8px; font-size:14px; }}
            QLineEdit:focus {{ border-color:{colors['accent_text']}; }}
        """ + standard_buttons(dark, compact=True))
        for combo in (self.service, self.usage):
            set_widget_stylesheet(combo, compact_combo_style(dark))
            combo.set_popup_background(field)
            # QSS min-height resets QComboBox's native minimum; keep the form
            # row identical to its line edits after the style has been polished.
            combo.ensurePolished()
            combo.setFixedHeight(28)
        for field_widget in (self.address, self.key, self.model):
            palette = field_widget.palette()
            palette.setColor(QPalette.PlaceholderText, QColor(muted))
            field_widget.setPalette(palette)
        install_accent_controls(self, dark=dark)
        # Stylesheet fonts must also inform the form's label measurements.
        self.ensurePolished()
        for label in self.labels:
            label.ensurePolished()
            ink_width = label.fontMetrics().boundingRect(label.text()).width()
            label.setMinimumWidth(max(label.sizeHint().width(), ink_width + 4))

    def _capture(self):
        usage = self.usage.currentData()
        return dict(url=self.address.text().strip(), model=self.model.text().strip(),
                    vision=usage in ('ocr', 'direct'), direct=usage == 'direct', key=self.key.text())

    def _set_status(self, text):
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _refresh_routing_preview(self, *_args):
        if not self.active or getattr(self, '_loading_profile', False):
            return
        from provider_catalog import TRANSLATION_PROVIDERS, provider_id
        from styled_dialogs import tooltip_text
        names = {key: name for key, name, _kind in TRANSLATION_PROVIDERS}
        config = self.app.config
        translator = names.get(provider_id(config.get('translator_engine')), str(config.get('translator_engine', '')))
        ocr = str(config.get('ocr_engine', ''))
        model = self.model.text().strip()
        service = BY_KEY[self.active].name + (' · ' + model if model else '')
        usage = self.usage.currentData() or 'text'
        text = routing_text(self.lang, {'text': 1, 'ocr': 2, 'direct': 3}[usage],
                            service=service, translator=translator, ocr=ocr)
        from api_providers import VISION_ENGINES
        if usage == 'text' and VISION_ENGINES.get(config.get('ocr_engine')) == self.active:
            text = routing_text(self.lang, 6)
        self.routing_label.setText(routing_text(self.lang, 0) + '\n' + text)
        self.routing_label.setToolTip(tooltip_text(text))
        self.usage.setAccessibleDescription(self.note.text() + '\n\n' + provider_text(self.lang, 'help') + '\n\n' + text)

    def load_profile(self, *_args):
        from provider_secrets import get_key
        self._loading_profile = True
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
        self._set_status('')
        self._loading_profile = False
        self._refresh_routing_preview()

    def _save_preferences(self, values):
        missing = object()
        previous = {key: self.app.config.get(key, missing) for key in values}
        self.app.config.update(values)
        try:
            if self.app.save_config() is False:
                raise OSError('Settings publication was refused')
        except Exception:
            for key, value in previous.items():
                if value is missing:
                    self.app.config.pop(key, None)
                else:
                    self.app.config[key] = value
            self._set_status(_SAVE_ERROR.get(self.lang, _SAVE_ERROR['en']))
            return False
        from settings_window import _invalidate_main_config_cache
        _invalidate_main_config_cache()
        complete = getattr(self.app, '_complete_guide_setting', None)
        if callable(complete):
            for key in values:
                complete(key)
        return True

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
            self._set_status(str(error) if str(error) == connection_text(self.lang, 8)
                             else display_error(error, self.lang))
            return False
        from api_providers import VISION_ENGINES
        if VISION_ENGINES.get(self.app.config.get('ocr_engine')) == self.active and not item['vision']:
            self._set_status(routing_text(self.lang, 6))
            return False
        key = item.pop('key')
        profiles = dict(self.app.config.get('api_providers', {}))
        profiles[self.active] = item
        if not self._save_preferences({'api_providers': profiles}):
            return False
        persisted = set_key(self.active, item['url'], key) if key else True
        self.settings._refresh_ready_engine_choices()
        refresh_provider_routing(self.settings)
        self.key.clear()
        self.key.setPlaceholderText(provider_text(self.lang, 'stored' if get_key(self.active, item['url']) else 'empty'))
        self.drafts[self.active] = item
        self._set_status(provider_text(self.lang, 'saved' if persisted else 'session'))
        return True

    def select_profile(self):
        if not self.save_profile():
            return
        from api_providers import VISION_ENGINES, validate
        try:
            validate(self.active, self.app.config)
        except ProviderError as error:
            from api_providers import display_error
            self._set_status(display_error(error, self.lang))
            return
        status = self.status.text()
        usage = self.usage.currentData()
        values = {}
        if usage in ('text', 'direct'):
            values['translator_engine'] = self.active
        if usage in ('ocr', 'direct'):
            engine = next(name for name, key in VISION_ENGINES.items() if key == self.active)
            values['ocr_engine'] = engine
        if not self._save_preferences(values):
            return
        if 'translator_engine' in values:
            self.settings._set_translator_combo_silently(self.active)
        if 'ocr_engine' in values:
            self.settings._set_ocr_combo_silently(engine)
        refresh_provider_routing(self.settings)
        self._refresh_routing_preview()
        selected = routing_text(self.lang, 4) if usage == 'ocr' else connection_text(self.lang, 7 if usage == 'direct' else 6)
        self._set_status(selected + ' ' + status)

    def delete_key(self):
        from provider_secrets import set_key
        saved_url = profile(self.active, self.app.config)['url']
        if self.address.text().strip().rstrip('/') != saved_url:
            self._set_status(_DELETE_STATUS.get(self.lang, _DELETE_STATUS['en'])[2])
            return
        persisted = set_key(self.active, saved_url, '')
        self.key.clear()
        self.drafts.pop(self.active, None)
        self.key.setPlaceholderText(provider_text(self.lang, 'empty'))
        self.settings._refresh_ready_engine_choices()
        self._set_status(_DELETE_STATUS.get(self.lang, _DELETE_STATUS['en'])[0 if persisted else 1])
