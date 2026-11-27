"""Shared engine-center copy and a metadata-only update comparison."""
MAINTENANCE_KEYS = ('more', 'refresh_list', 'connection', 'install_hint', 'remove_hint')
MAINTENANCE = {
 'en': ('Engine actions', 'Refresh package list', 'Connection', 'Check missing languages to install them. Installed languages are already ticked.', 'Select installed rows to remove their language packages.'),
 'ru': ('Действия с движком', 'Обновить список пакетов', 'Подключение', 'Отметьте отсутствующие языки для установки. Уже установленные отмечены заранее.', 'Выделите строки установленных пакетов, чтобы удалить их.'),
 'es': ('Acciones del motor', 'Actualizar lista de paquetes', 'Conexión', 'Marca los idiomas que faltan para instalarlos. Los instalados ya están marcados.', 'Selecciona las filas instaladas para eliminar sus paquetes de idiomas.'),
 'de': ('Engine-Aktionen', 'Paketliste aktualisieren', 'Verbindung', 'Fehlende Sprachen zur Installation markieren. Installierte Sprachen sind bereits angehakt.', 'Installierte Zeilen auswählen, um ihre Sprachpakete zu entfernen.'),
 'fr': ('Actions du moteur', 'Actualiser la liste des modules', 'Connexion', 'Cochez les langues manquantes pour les installer. Les langues installées sont déjà cochées.', 'Sélectionnez les lignes installées pour supprimer leurs modules de langue.'),
 'zh': ('引擎操作', '刷新软件包列表', '连接', '勾选缺少的语言进行安装。已安装的语言已勾选。', '选择已安装的行以删除其语言包。'),
 'pt': ('Ações do motor', 'Atualizar lista de pacotes', 'Conexão', 'Marque os idiomas ausentes para instalá-los. Os instalados já estão marcados.', 'Selecione as linhas instaladas para remover seus pacotes de idiomas.'),
 'it': ('Azioni del motore', 'Aggiorna elenco pacchetti', 'Connessione', 'Seleziona le lingue mancanti da installare. Quelle installate sono già spuntate.', 'Seleziona le righe installate per rimuovere i pacchetti di lingua.'),
 'ar': ('إجراءات المحرك', 'تحديث قائمة الحزم', 'الاتصال', 'حدّد اللغات الناقصة لتثبيتها. اللغات المثبتة محددة مسبقًا.', 'اختر صفوف الحزم المثبتة لإزالة حزم اللغات الخاصة بها.'),
 'tr': ('Motor işlemleri', 'Paket listesini yenile', 'Bağlantı', 'Kurmak için eksik dilleri işaretleyin. Kurulu diller zaten işaretlidir.', 'Dil paketlerini kaldırmak için kurulu satırları seçin.'),
 'hi': ('इंजन की कार्रवाइयाँ', 'पैकेज सूची रीफ़्रेश करें', 'कनेक्शन', 'इंस्टॉल करने के लिए अनुपलब्ध भाषाएँ चुनें। इंस्टॉल भाषाएँ पहले से चिह्नित हैं।', 'भाषा पैकेज हटाने के लिए इंस्टॉल की गई पंक्तियाँ चुनें।'),
 'id': ('Tindakan mesin', 'Muat ulang daftar paket', 'Koneksi', 'Centang bahasa yang belum ada untuk memasangnya. Bahasa terpasang sudah dicentang.', 'Pilih baris terpasang untuk menghapus paket bahasanya.'),
}
TEXT = {
 'en': ('Engines and API', 'Install engines and language models, or configure an API service here.', 'Check updates', 'Checking…', 'Up to date', 'Update', 'Current', 'Available', 'Already available on this computer. No separate center package was installed.', 'Installed separately through ClicknTranslate.', 'This package contains the engine and its base models. Other languages are selected separately where supported.', 'Check download access', 'Back to engines', 'Download connection', 'Checks the component catalog, GitHub API and a package file. Packages are not downloaded.', 'Check again', 'Available', 'Connection failed', 'Access restricted', 'Catalog', 'GitHub API', 'Package files', 'Not checked', 'ms', 'No verified package is available for this system.', 'Choose what this connection will do. Saving alone does not change the active engines.'),
 'ru': ('Движки и API', 'Здесь устанавливаются движки и языковые модели, настраиваются API-сервисы.', 'Проверить обновления', 'Проверка…', 'Актуальная версия', 'Обновить', 'Сейчас', 'Доступно', 'Уже доступен на этом компьютере. Отдельный пакет центра не устанавливался.', 'Установлен отдельно через ClicknTranslate.', 'Пакет содержит движок и базовые модели. Дополнительные языки выбираются отдельно, если движок это поддерживает.', 'Проверить доступ к загрузкам', 'К движкам', 'Подключение к загрузкам', 'Проверяются каталог компонентов, GitHub API и файл пакета. Сами пакеты не скачиваются.', 'Проверить снова', 'Доступен', 'Нет соединения', 'Доступ ограничен', 'Каталог', 'GitHub API', 'Файлы пакетов', 'Не проверен', 'мс', 'Для этой системы пока нет проверенного пакета.', 'Выберите, для чего использовать подключение. Простое сохранение не меняет активные движки.'),
 'es': ('Motores y API', 'Instala motores y modelos de idiomas o configura un servicio API aquí.', 'Buscar actualizaciones', 'Comprobando…', 'Versión actual', 'Actualizar', 'Actual', 'Disponible', 'Ya disponible en este equipo. No se instaló un paquete separado del centro.', 'Instalado por separado mediante ClicknTranslate.', 'El paquete contiene el motor y sus modelos básicos. Otros idiomas se eligen aparte cuando se admite.', 'Comprobar acceso a descargas', 'Volver a motores', 'Conexión de descarga', 'Comprueba catálogo, GitHub API y un archivo de paquete. No descarga los paquetes.', 'Comprobar otra vez', 'Disponible', 'Sin conexión', 'Acceso restringido', 'Catálogo', 'GitHub API', 'Archivos de paquetes', 'Sin comprobar', 'ms', 'Aún no hay un paquete verificado para este sistema.', 'Elige para qué usar la conexión. Guardar no cambia los motores activos.'),
 'de': ('Engines und API', 'Engines und Sprachmodelle installieren oder einen API-Dienst einrichten.', 'Updates prüfen', 'Wird geprüft…', 'Aktuell', 'Aktualisieren', 'Aktuell installiert', 'Verfügbar', 'Auf diesem Computer bereits verfügbar. Kein separates Center-Paket installiert.', 'Separat über ClicknTranslate installiert.', 'Das Paket enthält Engine und Basismodelle. Weitere Sprachen werden, sofern unterstützt, separat gewählt.', 'Downloadzugriff prüfen', 'Zu den Engines', 'Downloadverbindung', 'Prüft Katalog, GitHub API und eine Paketdatei. Pakete werden nicht heruntergeladen.', 'Erneut prüfen', 'Erreichbar', 'Keine Verbindung', 'Zugriff eingeschränkt', 'Katalog', 'GitHub API', 'Paketdateien', 'Nicht geprüft', 'ms', 'Für dieses System gibt es noch kein geprüftes Paket.', 'Wählen Sie den Zweck der Verbindung. Speichern allein ändert keine aktive Engine.'),
 'fr': ('Moteurs et API', 'Installez des moteurs et modèles de langues ou configurez un service API ici.', 'Vérifier les mises à jour', 'Vérification…', 'À jour', 'Mettre à jour', 'Actuel', 'Disponible', 'Déjà disponible sur cet ordinateur. Aucun paquet distinct du centre installé.', 'Installé séparément via ClicknTranslate.', 'Ce paquet contient le moteur et ses modèles de base. Les autres langues se choisissent séparément si le moteur le permet.', 'Vérifier l’accès aux téléchargements', 'Retour aux moteurs', 'Connexion de téléchargement', 'Vérifie le catalogue, GitHub API et un fichier de paquet, sans télécharger les paquets.', 'Vérifier à nouveau', 'Accessible', 'Connexion impossible', 'Accès restreint', 'Catalogue', 'GitHub API', 'Fichiers de paquets', 'Non vérifié', 'ms', 'Aucun paquet vérifié disponible pour ce système.', 'Choisissez l’usage de la connexion. Enregistrer seul ne change pas les moteurs actifs.'),
 'zh': ('引擎与 API', '在此安装引擎和语言模型，或配置 API 服务。', '检查更新', '正在检查…', '已是最新版', '更新', '当前', '可用', '此计算机上已可用，未通过本中心安装独立软件包。', '通过 ClicknTranslate 单独安装。', '此软件包包含引擎和基础模型。若引擎支持，可单独选择其他语言。', '检查下载连接', '返回引擎', '下载连接', '检查组件目录、GitHub API 和软件包文件，不下载软件包。', '重新检查', '可访问', '连接失败', '访问受限', '目录', 'GitHub API', '软件包文件', '未检查', '毫秒', '此系统尚无经过验证的软件包。', '选择此连接的用途。仅保存不会更改当前引擎。'),
 'pt': ('Motores e API', 'Instale motores e modelos de idiomas ou configure um serviço API aqui.', 'Verificar atualizações', 'Verificando…', 'Atualizado', 'Atualizar', 'Atual', 'Disponível', 'Já disponível neste computador. Nenhum pacote separado foi instalado pelo centro.', 'Instalado separadamente pelo ClicknTranslate.', 'O pacote contém o motor e os modelos básicos. Outros idiomas são escolhidos separadamente quando houver suporte.', 'Verificar acesso aos downloads', 'Voltar aos motores', 'Conexão de download', 'Verifica catálogo, GitHub API e um arquivo de pacote. Os pacotes não são baixados.', 'Verificar novamente', 'Disponível', 'Falha de conexão', 'Acesso restrito', 'Catálogo', 'GitHub API', 'Arquivos dos pacotes', 'Não verificado', 'ms', 'Ainda não há pacote verificado para este sistema.', 'Escolha o uso da conexão. Apenas salvar não muda os motores ativos.'),
 'it': ('Motori e API', 'Installa motori e modelli linguistici o configura un servizio API qui.', 'Controlla aggiornamenti', 'Controllo…', 'Aggiornato', 'Aggiorna', 'Attuale', 'Disponibile', 'Già disponibile sul computer. Nessun pacchetto separato installato dal centro.', 'Installato separatamente tramite ClicknTranslate.', 'Il pacchetto contiene motore e modelli di base. Altre lingue si scelgono a parte, se supportate.', 'Verifica accesso ai download', 'Torna ai motori', 'Connessione download', 'Controlla catalogo, GitHub API e un file di pacchetto senza scaricare i pacchetti.', 'Controlla di nuovo', 'Disponibile', 'Connessione fallita', 'Accesso limitato', 'Catalogo', 'GitHub API', 'File dei pacchetti', 'Non verificato', 'ms', 'Non ci sono ancora pacchetti verificati per questo sistema.', 'Scegli l’uso della connessione. Il solo salvataggio non cambia i motori attivi.'),
 'ar': ('المحركات وAPI', 'ثبّت المحركات ونماذج اللغات أو اضبط خدمة API هنا.', 'التحقق من التحديثات', 'جارٍ التحقق…', 'الإصدار الأحدث', 'تحديث', 'الحالي', 'المتاح', 'متاح بالفعل على هذا الكمبيوتر. لم تُثبّت حزمة مستقلة من المركز.', 'مثبّت بشكل مستقل عبر ClicknTranslate.', 'تحتوي الحزمة على المحرك والنماذج الأساسية. تُختار اللغات الأخرى بشكل مستقل عند دعمها.', 'فحص الوصول إلى التنزيلات', 'العودة للمحركات', 'اتصال التنزيل', 'يفحص الكتالوج وGitHub API وملف حزمة دون تنزيل الحزم.', 'الفحص مجددًا', 'متاح', 'فشل الاتصال', 'الوصول مقيّد', 'الكتالوج', 'GitHub API', 'ملفات الحزم', 'لم يُفحص', 'مللي ثانية', 'لا توجد حزمة موثقة لهذا النظام بعد.', 'اختر استخدام الاتصال. الحفظ وحده لا يغيّر المحركات النشطة.'),
 'tr': ('Motorlar ve API', 'Burada motor ve dil modelleri yükleyin veya API servisi ayarlayın.', 'Güncellemeleri denetle', 'Denetleniyor…', 'Güncel', 'Güncelle', 'Şu an', 'Kullanılabilir', 'Bu bilgisayarda zaten var. Merkezden ayrı bir paket yüklenmedi.', 'ClicknTranslate üzerinden ayrı yüklendi.', 'Paket motor ve temel modelleri içerir. Destekleniyorsa diğer diller ayrıca seçilir.', 'İndirme erişimini denetle', 'Motorlara dön', 'İndirme bağlantısı', 'Katalog, GitHub API ve paket dosyası denetlenir. Paketler indirilmez.', 'Tekrar denetle', 'Erişilebilir', 'Bağlantı yok', 'Erişim kısıtlı', 'Katalog', 'GitHub API', 'Paket dosyaları', 'Denetlenmedi', 'ms', 'Bu sistem için henüz doğrulanmış paket yok.', 'Bağlantının kullanımını seçin. Yalnız kaydetmek etkin motorları değiştirmez.'),
 'hi': ('इंजन और API', 'यहाँ इंजन और भाषा मॉडल इंस्टॉल करें या API सेवा सेट करें।', 'अपडेट जाँचें', 'जाँच जारी…', 'नवीनतम संस्करण', 'अपडेट करें', 'मौजूदा', 'उपलब्ध', 'इस कंप्यूटर पर पहले से उपलब्ध है। केंद्र का अलग पैकेज इंस्टॉल नहीं हुआ।', 'ClicknTranslate से अलग इंस्टॉल किया गया।', 'पैकेज में इंजन और मूल मॉडल हैं। समर्थित होने पर अन्य भाषाएँ अलग चुनी जाती हैं।', 'डाउनलोड पहुँच जाँचें', 'इंजन पर लौटें', 'डाउनलोड कनेक्शन', 'कैटलॉग, GitHub API और पैकेज फ़ाइल जाँचता है। पैकेज डाउनलोड नहीं होते।', 'फिर जाँचें', 'उपलब्ध', 'कनेक्शन विफल', 'पहुँच सीमित', 'कैटलॉग', 'GitHub API', 'पैकेज फ़ाइलें', 'जाँच नहीं हुई', 'मिलीसेकंड', 'इस सिस्टम के लिए अभी सत्यापित पैकेज नहीं है।', 'कनेक्शन का उपयोग चुनें। सिर्फ़ सहेजने से सक्रिय इंजन नहीं बदलते।'),
 'id': ('Mesin dan API', 'Pasang mesin dan model bahasa atau atur layanan API di sini.', 'Periksa pembaruan', 'Memeriksa…', 'Versi terbaru', 'Perbarui', 'Saat ini', 'Tersedia', 'Sudah tersedia di komputer ini. Paket terpisah belum dipasang lewat pusat.', 'Dipasang terpisah melalui ClicknTranslate.', 'Paket berisi mesin dan model dasar. Bahasa lain dipilih terpisah jika didukung.', 'Periksa akses unduhan', 'Kembali ke mesin', 'Koneksi unduhan', 'Memeriksa katalog, GitHub API dan berkas paket. Paket tidak diunduh.', 'Periksa lagi', 'Tersedia', 'Koneksi gagal', 'Akses dibatasi', 'Katalog', 'GitHub API', 'Berkas paket', 'Belum diperiksa', 'md', 'Belum ada paket terverifikasi untuk sistem ini.', 'Pilih kegunaan koneksi. Menyimpan saja tidak mengubah mesin aktif.'),
}
KEYS = ('title', 'intro', 'check_updates', 'checking', 'current', 'update', 'installed', 'available',
        'local', 'managed', 'base', 'check_access', 'back', 'network_title', 'network_intro',
        'again', 'ok', 'failed', 'restricted', 'catalog', 'api', 'files', 'unchecked', 'ms',
        'no_package', 'api_intro')


def text(lang, key):
    if key in MAINTENANCE_KEYS:
        return MAINTENANCE.get(lang, MAINTENANCE['en'])[MAINTENANCE_KEYS.index(key)]
    if key == 'no_download':
        return NO_DOWNLOAD.get(lang, NO_DOWNLOAD['en'])
    if key in ACTION_KEYS:
        return ACTIONS.get(lang, ACTIONS['en'])[ACTION_KEYS.index(key)]
    if key == 'check_help':
        return CHECK_HELP.get(lang, CHECK_HELP['en'])
    return TEXT.get(lang, TEXT['en'])[KEYS.index(key)]


ACTION_KEYS = ('activate', 'active', 'setup_first', 'ready_help', 'select')
ACTIONS = {
 'en': ('Use this engine', 'Active', 'Install the engine and its languages first.', 'Only installed engines and configured API services are listed. Add more in Engines and API.', 'Choose an engine'),
 'ru': ('Сделать активным', 'Активен', 'Сначала установите движок и языки.', 'В списке только установленные движки и настроенные API. Добавить другие можно в «Движки и API».', 'Выберите движок'),
 'es': ('Usar este motor', 'Activo', 'Instala primero el motor y sus idiomas.', 'Solo motores instalados y API configuradas. Añade otros en Motores y API.', 'Elige un motor'),
 'de': ('Engine verwenden', 'Aktiv', 'Zuerst Engine und Sprachen installieren.', 'Nur installierte Engines und eingerichtete APIs. Weitere unter Engines und API hinzufügen.', 'Engine wählen'),
 'fr': ('Utiliser ce moteur', 'Actif', 'Installez d’abord le moteur et ses langues.', 'Seuls les moteurs installés et les API configurées sont affichés. Ajoutez-en dans Moteurs et API.', 'Choisir un moteur'),
 'zh': ('使用此引擎', '正在使用', '请先安装引擎和语言。', '仅显示已安装的引擎和已配置的 API。请在引擎与 API 中添加。', '选择引擎'),
 'pt': ('Usar este motor', 'Ativo', 'Instale primeiro o motor e os idiomas.', 'Só motores instalados e APIs configuradas. Adicione outros em Motores e API.', 'Escolha um motor'),
 'it': ('Usa questo motore', 'Attivo', 'Installa prima il motore e le lingue.', 'Solo motori installati e API configurate. Aggiungine in Motori e API.', 'Scegli un motore'),
 'ar': ('استخدام هذا المحرك', 'نشط', 'ثبّت المحرك واللغات أولًا.', 'تظهر المحركات المثبتة وخدمات API المضبوطة فقط. أضف المزيد في المحركات وAPI.', 'اختر محركًا'),
 'tr': ('Bu motoru kullan', 'Etkin', 'Önce motoru ve dilleri yükleyin.', 'Yalnız kurulu motorlar ve ayarlı API hizmetleri gösterilir. Motorlar ve API bölümünden ekleyin.', 'Motor seçin'),
 'hi': ('यह इंजन इस्तेमाल करें', 'सक्रिय', 'पहले इंजन और भाषाएँ इंस्टॉल करें।', 'केवल इंस्टॉल इंजन और तैयार API दिखते हैं। इंजन और API में और जोड़ें।', 'इंजन चुनें'),
 'id': ('Gunakan mesin ini', 'Aktif', 'Pasang mesin dan bahasanya dahulu.', 'Hanya mesin terpasang dan API terkonfigurasi ditampilkan. Tambahkan di Mesin dan API.', 'Pilih mesin'),
}

NO_DOWNLOAD = {
 'en': 'Online service. No engine or model download is needed.',
 'ru': 'Онлайн-сервис. Скачивать движок и модели не требуется.',
 'es': 'Servicio en línea. No necesita descargar motores ni modelos.',
 'de': 'Onlinedienst. Kein Download von Engine oder Modellen nötig.',
 'fr': 'Service en ligne. Aucun moteur ou modèle à télécharger.',
 'zh': '在线服务，无需下载引擎或模型。',
 'pt': 'Serviço online. Não é preciso baixar motor ou modelos.',
 'it': 'Servizio online. Non occorre scaricare motori o modelli.',
 'ar': 'خدمة عبر الإنترنت. لا يلزم تنزيل محرك أو نماذج.',
 'tr': 'Çevrimiçi hizmet. Motor veya model indirmeniz gerekmez.',
 'hi': 'ऑनलाइन सेवा। इंजन या मॉडल डाउनलोड की ज़रूरत नहीं है।',
 'id': 'Layanan daring. Tidak perlu mengunduh mesin atau model.',
}


CHECK_HELP = {
 'en': 'Checks the version without downloading packages. Installing an update requires a separate click.',
 'ru': 'Проверяет версию без скачивания пакетов. Для установки обновления нужно отдельное нажатие.',
 'es': 'Comprueba la versión sin descargar paquetes. La instalación requiere otro clic.',
 'de': 'Prüft die Version ohne Paketdownload. Die Installation erfordert einen weiteren Klick.',
 'fr': 'Vérifie la version sans télécharger de paquet. Un autre clic lance l’installation.',
 'zh': '只检查版本，不下载软件包。安装更新需要再次点击。',
 'pt': 'Verifica a versão sem baixar pacotes. A instalação exige outro clique.',
 'it': 'Controlla la versione senza scaricare pacchetti. L’installazione richiede un altro clic.',
 'ar': 'يفحص الإصدار دون تنزيل الحزم. يتطلب تثبيت التحديث نقرة أخرى.',
 'tr': 'Paket indirmeden sürümü denetler. Yükleme için ayrıca tıklamanız gerekir.',
 'hi': 'पैकेज डाउनलोड किए बिना संस्करण जाँचता है। अपडेट इंस्टॉल करने के लिए अलग क्लिक चाहिए।',
 'id': 'Memeriksa versi tanpa mengunduh paket. Pemasangan memerlukan klik terpisah.',
}


COMPONENTS = {'rapidocr': 'ocr.rapidocr', 'easyocr': 'ocr.easyocr', 'tesseract': 'ocr.tesseract',
              'argos': 'translation.argos', 'hymt': 'translation.hymt'}


def installed_states():
    from component_catalog import component_store_path
    from component_store import ComponentStore
    store = ComponentStore(component_store_path())
    states = {}
    for engine, component in COMPONENTS.items():
        try:
            states[engine] = bool(store.describe(component))
        except Exception:
            states[engine] = None
    return states


def compare_update(catalog, engine, *, store, target=None, channel='stable'):
    """Inspect receipts and signed metadata, never import/validate/download engines."""
    from app_version import APP_VERSION
    from component_catalog import choose_bundle, materialize_bundle
    component = COMPONENTS[engine]
    old = store.describe(component)
    receipt = old['receipt'] if old else {}
    defaults = {'tesseract': ('eng', 'rus'), 'easyocr': ('english_g2',)}
    installed_languages = receipt.get('languages', ())
    candidate = choose_bundle(catalog, component, APP_VERSION, target=target, channel=channel,
                              languages=installed_languages if receipt else defaults.get(engine, ()))
    languages = (installed_languages if receipt else defaults.get(engine, ())) if candidate.get('language_files') else candidate.get('languages', ())
    candidate = materialize_bundle(candidate, languages)
    current = bool(receipt and receipt.get('bundle') == candidate['id']
                   and receipt.get('files') == candidate['files']
                   and receipt.get('languages') == candidate['languages'])
    artifacts = catalog['artifacts']
    size = sum(artifacts[digest]['size'] for digest in {f['sha256'] for f in candidate['files']})
    def version(data):
        value = str(data.get('version') or data.get('id') or data.get('bundle') or '')
        return value + (' · r' + str(data['revision']) if value and data.get('revision') is not None else '')
    return {'current': current, 'installed': version(receipt), 'available': version(candidate),
            'size': size, 'bundle': candidate['id'], 'managed': bool(receipt)}
