"""Download sizes from the authenticated catalog, without native imports or HTTP."""
from component_catalog import choose_bundle, ComponentError

TEXT = {
    'en': ('Languages and engines', 'Choose an engine, then install the languages you need.', 'Download', 'Engine', 'Models', 'To download', 'Size unavailable', 'Included', 'Managed by Windows', 'No package for this system', 'Shared files are counted once. Sizes refer to downloads, not disk usage.', 'Included in the engine package'),
    'ru': ('Языки и движки', 'Выберите движок и установите нужные языки.', 'Загрузка', 'Движок', 'Модели', 'К загрузке', 'Размер неизвестен', 'Включено', 'Определяет Windows', 'Нет пакета для этой системы', 'Общие файлы учтены один раз. Указан размер скачивания, а не место на диске.', 'Включено в пакет движка'),
    'es': ('Idiomas y motores', 'Elige un motor e instala los idiomas que necesites.', 'Descarga', 'Motor', 'Modelos', 'Por descargar', 'Tamaño desconocido', 'Incluido', 'Gestionado por Windows', 'Sin paquete para este sistema', 'Los archivos compartidos se cuentan una vez. Tamaños de descarga, no de disco.', 'Incluido en el paquete del motor'),
    'de': ('Sprachen und Engines', 'Engine wählen und benötigte Sprachen installieren.', 'Download', 'Engine', 'Modelle', 'Herunterzuladen', 'Größe unbekannt', 'Enthalten', 'Von Windows verwaltet', 'Kein Paket für dieses System', 'Gemeinsame Dateien zählen einmal. Downloadgröße, kein Speicherplatzbedarf.', 'Im Engine-Paket enthalten'),
    'fr': ('Langues et moteurs', 'Choisissez un moteur et installez les langues souhaitées.', 'Téléchargement', 'Moteur', 'Modèles', 'À télécharger', 'Taille inconnue', 'Inclus', 'Géré par Windows', 'Aucun paquet pour ce système', 'Les fichiers partagés sont comptés une fois. Tailles téléchargées, pas espace disque.', 'Inclus dans le paquet du moteur'),
    'zh': ('语言和引擎', '选择引擎，然后安装需要的语言。', '下载大小', '引擎', '模型', '待下载', '大小未知', '已包含', '由 Windows 管理', '此系统暂无软件包', '共享文件只计算一次。显示下载大小，而非磁盘占用。', '包含在引擎软件包中'),
    'pt': ('Idiomas e motores', 'Escolha um motor e instale os idiomas necessários.', 'Download', 'Motor', 'Modelos', 'A baixar', 'Tamanho desconhecido', 'Incluído', 'Gerenciado pelo Windows', 'Sem pacote para este sistema', 'Arquivos compartilhados são contados uma vez. Tamanho do download, não uso em disco.', 'Incluído no pacote do motor'),
    'it': ('Lingue e motori', 'Scegli un motore e installa le lingue necessarie.', 'Download', 'Motore', 'Modelli', 'Da scaricare', 'Dimensione sconosciuta', 'Incluso', 'Gestito da Windows', 'Nessun pacchetto per questo sistema', 'I file condivisi sono contati una volta. Dimensioni del download, non spazio su disco.', 'Incluso nel pacchetto del motore'),
    'ar': ('اللغات والمحركات', 'اختر محركًا وثبّت اللغات التي تحتاجها.', 'حجم التنزيل', 'المحرك', 'النماذج', 'للتنزيل', 'الحجم غير معروف', 'مضمّن', 'تديره Windows', 'لا توجد حزمة لهذا النظام', 'تُحسب الملفات المشتركة مرة واحدة. الأحجام للتنزيل وليست مساحة القرص.', 'مضمّن في حزمة المحرك'),
    'tr': ('Diller ve motorlar', 'Bir motor seçin ve gereken dilleri yükleyin.', 'İndirme', 'Motor', 'Modeller', 'İndirilecek', 'Boyut bilinmiyor', 'Dahil', 'Windows yönetir', 'Bu sistem için paket yok', 'Ortak dosyalar bir kez sayılır. İndirme boyutudur, disk kullanımı değildir.', 'Motor paketine dahil'),
    'hi': ('भाषाएँ और इंजन', 'इंजन चुनें और ज़रूरी भाषाएँ इंस्टॉल करें।', 'डाउनलोड', 'इंजन', 'मॉडल', 'डाउनलोड करना है', 'आकार अज्ञात', 'शामिल', 'Windows द्वारा प्रबंधित', 'इस सिस्टम के लिए पैकेज नहीं है', 'साझा फ़ाइलें एक बार गिनी जाती हैं। यह डाउनलोड आकार है, डिस्क उपयोग नहीं।', 'इंजन पैकेज में शामिल'),
    'id': ('Bahasa dan mesin', 'Pilih mesin, lalu pasang bahasa yang diperlukan.', 'Unduhan', 'Mesin', 'Model', 'Akan diunduh', 'Ukuran tak diketahui', 'Termasuk', 'Dikelola Windows', 'Tidak ada paket untuk sistem ini', 'Berkas bersama dihitung sekali. Ukuran unduhan, bukan penggunaan disk.', 'Termasuk dalam paket mesin'),
}
KEYS = ('title', 'intro', 'size', 'engine', 'models', 'total', 'unknown', 'included', 'windows', 'unavailable', 'size_help', 'bundled')


EXTRA_TEXT = {
    'unsupported': dict(zip(TEXT, ('Not available for this engine', 'Нет пакета для этого движка', 'No disponible para este motor',
        'Für diese Engine nicht verfügbar', 'Indisponible pour ce moteur', '此引擎暂无语言包',
        'Indisponível para este motor', 'Non disponibile per questo motore', 'غير متاح لهذا المحرك',
        'Bu motor için mevcut değil', 'इस इंजन के लिए उपलब्ध नहीं', 'Tidak tersedia untuk mesin ini'))),
    'total': dict(zip(TEXT, ('Package total', 'Весь пакет', 'Paquete completo', 'Gesamtpaket', 'Paquet complet',
        '软件包总计', 'Pacote completo', 'Pacchetto completo', 'إجمالي الحزمة', 'Toplam paket', 'कुल पैकेज', 'Total paket'))),
}


def text(lang, key):
    if key in EXTRA_TEXT:
        return EXTRA_TEXT[key].get(lang, EXTRA_TEXT[key]['en'])
    return TEXT.get(lang, TEXT['en'])[KEYS.index(key)]


def format_size(size):
    if size is None:
        return '—'
    unit = 'B'
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1000 or unit == 'GB':
            break
        value /= 1000
    if unit == 'GB':
        return f'{value:.2f} {unit}'
    return f'{value:.1f} {unit}' if unit != 'B' else f'{int(value)} B'


class PackageSizes:
    def __init__(self, catalog, *, target=None, channel='stable'):
        self.catalog = catalog
        self.bundles = {}
        from app_version import APP_VERSION
        for engine, component in (('rapidocr', 'ocr.rapidocr'), ('easyocr', 'ocr.easyocr'),
                                  ('tesseract', 'ocr.tesseract'), ('argos', 'translation.argos'), ('hymt', 'translation.hymt')):
            try:
                self.bundles[engine] = choose_bundle(catalog, component, APP_VERSION, channel=channel, target=target)
            except ComponentError:
                pass

    def files(self, engine, codes=(), *, base=True):
        bundle = self.bundles.get(engine)
        if bundle is None:
            return None
        files = list(bundle['files']) if base else []
        for code in codes:
            files.extend(bundle.get('language_files', {}).get(code, ()))
        return {item['sha256']: self.catalog['artifacts'][item['sha256']]['size'] for item in files}

    def size(self, engine, codes=(), *, base=True):
        files = self.files(engine, codes, base=base)
        return sum(files.values()) if files is not None else None

    def split_base(self, engine):
        return self.breakdown(engine)

    def breakdown(self, engine, codes=()):
        bundle = self.bundles.get(engine)
        if bundle is None:
            return None, None
        runtime = {item['sha256'] for item in bundle['files'] if not item['destination'].startswith('models/')}
        files = self.files(engine, codes)
        return sum(size for digest, size in files.items() if digest in runtime), sum(size for digest, size in files.items() if digest not in runtime)
