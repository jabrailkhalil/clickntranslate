"""Localized document diagnostics; file contents and technical details stay intact."""
_KEYS = ('translating', 'translated', 'chunk_failed', 'no_file', 'missing', 'empty',
         'decode', 'invalid_docx', 'docx_missing', 'missing_pdf', 'scanned_pdf',
         'unsupported', 'supported', 'read_error', 'failed', 'details')
_TEXT = {
    'en': ('Translating chunk {current}/{total}', 'Translated chunk {current}/{total}',
           '[Translation failed for chunk {number}.]', 'No file selected.', 'File not found.',
           'No readable text was found in this file.', 'Could not decode this text file.',
           'Invalid DOCX file.', 'The DOCX file is missing document.xml.',
           'PDF support requires the pypdf package.',
           'This PDF has no selectable text. Scanned pages require OCR.',
           'Unsupported file type: {extension}.', 'Supported types: {extensions}.',
           'Could not read this document.', 'The document operation failed.', 'Technical details'),
    'ru': ('Перевод фрагмента {current}/{total}', 'Переведён фрагмент {current}/{total}',
           '[Не удалось перевести фрагмент {number}.]', 'Файл не выбран.', 'Файл не найден.',
           'В этом файле не найден читаемый текст.', 'Не удалось определить кодировку текстового файла.',
           'Некорректный файл DOCX.', 'В файле DOCX отсутствует document.xml.',
           'Для работы с PDF нужен пакет pypdf.',
           'В этом PDF нет выделяемого текста. Отсканированные страницы требуют OCR.',
           'Неподдерживаемый тип файла: {extension}.', 'Поддерживаемые типы: {extensions}.',
           'Не удалось прочитать документ.', 'Операция с документом не выполнена.', 'Технические сведения'),
    'es': ('Traduciendo fragmento {current}/{total}', 'Fragmento traducido {current}/{total}',
           '[No se pudo traducir el fragmento {number}.]', 'No se ha seleccionado ningún archivo.', 'Archivo no encontrado.',
           'No se encontró texto legible en este archivo.', 'No se pudo determinar la codificación del archivo de texto.',
           'Archivo DOCX no válido.', 'El archivo DOCX no contiene document.xml.',
           'La compatibilidad con PDF requiere el paquete pypdf.',
           'Este PDF no contiene texto seleccionable. Las páginas escaneadas requieren OCR.',
           'Tipo de archivo no compatible: {extension}.', 'Tipos compatibles: {extensions}.',
           'No se pudo leer el documento.', 'La operación con el documento falló.', 'Detalles técnicos'),
    'de': ('Abschnitt {current}/{total} wird übersetzt', 'Abschnitt {current}/{total} übersetzt',
           '[Abschnitt {number} konnte nicht übersetzt werden.]', 'Keine Datei ausgewählt.', 'Datei nicht gefunden.',
           'In dieser Datei wurde kein lesbarer Text gefunden.', 'Die Zeichenkodierung der Textdatei konnte nicht erkannt werden.',
           'Ungültige DOCX-Datei.', 'In der DOCX-Datei fehlt document.xml.',
           'Für PDF-Unterstützung wird das Paket pypdf benötigt.',
           'Diese PDF enthält keinen auswählbaren Text. Gescannte Seiten benötigen OCR.',
           'Nicht unterstützter Dateityp: {extension}.', 'Unterstützte Typen: {extensions}.',
           'Das Dokument konnte nicht gelesen werden.', 'Der Dokumentvorgang ist fehlgeschlagen.', 'Technische Details'),
    'fr': ('Traduction du fragment {current}/{total}', 'Fragment {current}/{total} traduit',
           '[Impossible de traduire le fragment {number}.]', 'Aucun fichier sélectionné.', 'Fichier introuvable.',
           'Aucun texte lisible trouvé dans ce fichier.', 'Impossible de déterminer l’encodage du fichier texte.',
           'Fichier DOCX non valide.', 'Le fichier DOCX ne contient pas document.xml.',
           'La prise en charge du PDF nécessite le paquet pypdf.',
           'Ce PDF ne contient aucun texte sélectionnable. Les pages numérisées nécessitent un OCR.',
           'Type de fichier non pris en charge : {extension}.', 'Types pris en charge : {extensions}.',
           'Impossible de lire le document.', 'L’opération sur le document a échoué.', 'Détails techniques'),
    'zh': ('正在翻译第 {current}/{total} 段', '已翻译第 {current}/{total} 段',
           '[第 {number} 段翻译失败。]', '未选择文件。', '找不到文件。',
           '此文件中未找到可读文字。', '无法确定文本文件的编码。',
           'DOCX 文件无效。', 'DOCX 文件缺少 document.xml。',
           'PDF 支持需要 pypdf 包。', '此 PDF 没有可选择的文字。扫描页面需要 OCR。',
           '不支持的文件类型：{extension}。', '支持的类型：{extensions}。',
           '无法读取此文档。', '文档操作失败。', '技术详情'),
    'pt': ('Traduzindo trecho {current}/{total}', 'Trecho {current}/{total} traduzido',
           '[Não foi possível traduzir o trecho {number}.]', 'Nenhum arquivo selecionado.', 'Arquivo não encontrado.',
           'Não foi encontrado texto legível neste arquivo.', 'Não foi possível identificar a codificação do arquivo de texto.',
           'Arquivo DOCX inválido.', 'O arquivo DOCX não contém document.xml.',
           'O suporte a PDF requer o pacote pypdf.',
           'Este PDF não tem texto selecionável. Páginas digitalizadas exigem OCR.',
           'Tipo de arquivo não compatível: {extension}.', 'Tipos compatíveis: {extensions}.',
           'Não foi possível ler o documento.', 'A operação com o documento falhou.', 'Detalhes técnicos'),
    'it': ('Traduzione del frammento {current}/{total}', 'Frammento {current}/{total} tradotto',
           '[Impossibile tradurre il frammento {number}.]', 'Nessun file selezionato.', 'File non trovato.',
           'Nessun testo leggibile trovato nel file.', 'Impossibile determinare la codifica del file di testo.',
           'File DOCX non valido.', 'Nel file DOCX manca document.xml.',
           'Il supporto PDF richiede il pacchetto pypdf.',
           'Questo PDF non contiene testo selezionabile. Le pagine scansionate richiedono OCR.',
           'Tipo di file non supportato: {extension}.', 'Tipi supportati: {extensions}.',
           'Impossibile leggere il documento.', 'L’operazione sul documento non è riuscita.', 'Dettagli tecnici'),
    'ar': ('جارٍ ترجمة المقطع {current}/{total}', 'تُرجم المقطع {current}/{total}',
           '[تعذّرت ترجمة المقطع {number}.]', 'لم يتم اختيار ملف.', 'الملف غير موجود.',
           'لم يُعثر على نص مقروء في هذا الملف.', 'تعذّر تحديد ترميز الملف النصي.',
           'ملف DOCX غير صالح.', 'يفتقد ملف DOCX إلى document.xml.',
           'يتطلب دعم PDF حزمة pypdf.', 'لا يحتوي ملف PDF هذا على نص قابل للتحديد. تتطلب الصفحات الممسوحة OCR.',
           'نوع الملف غير مدعوم: {extension}.', 'الأنواع المدعومة: {extensions}.',
           'تعذّرت قراءة المستند.', 'تعذّر تنفيذ العملية على المستند.', 'تفاصيل تقنية'),
    'tr': ('{current}/{total}. parça çevriliyor', '{current}/{total}. parça çevrildi',
           '[{number}. parça çevrilemedi.]', 'Dosya seçilmedi.', 'Dosya bulunamadı.',
           'Bu dosyada okunabilir metin bulunamadı.', 'Metin dosyasının karakter kodlaması belirlenemedi.',
           'Geçersiz DOCX dosyası.', 'DOCX dosyasında document.xml eksik.',
           'PDF desteği için pypdf paketi gerekir.',
           'Bu PDF seçilebilir metin içermiyor. Taranmış sayfalar OCR gerektirir.',
           'Desteklenmeyen dosya türü: {extension}.', 'Desteklenen türler: {extensions}.',
           'Belge okunamadı.', 'Belge işlemi başarısız oldu.', 'Teknik ayrıntılar'),
    'hi': ('खंड {current}/{total} का अनुवाद हो रहा है', 'खंड {current}/{total} का अनुवाद हुआ',
           '[खंड {number} का अनुवाद नहीं हो सका।]', 'कोई फ़ाइल नहीं चुनी गई।', 'फ़ाइल नहीं मिली।',
           'इस फ़ाइल में पढ़ने योग्य टेक्स्ट नहीं मिला।', 'टेक्स्ट फ़ाइल की एन्कोडिंग पहचानी नहीं जा सकी।',
           'अमान्य DOCX फ़ाइल।', 'DOCX फ़ाइल में document.xml नहीं है।',
           'PDF समर्थन के लिए pypdf पैकेज चाहिए।', 'इस PDF में चुना जा सकने वाला टेक्स्ट नहीं है। स्कैन किए पृष्ठों के लिए OCR चाहिए।',
           'असमर्थित फ़ाइल प्रकार: {extension}।', 'समर्थित प्रकार: {extensions}।',
           'दस्तावेज़ पढ़ा नहीं जा सका।', 'दस्तावेज़ की प्रक्रिया विफल हुई।', 'तकनीकी विवरण'),
    'id': ('Menerjemahkan bagian {current}/{total}', 'Bagian {current}/{total} diterjemahkan',
           '[Bagian {number} tidak dapat diterjemahkan.]', 'Tidak ada berkas yang dipilih.', 'Berkas tidak ditemukan.',
           'Tidak ditemukan teks yang dapat dibaca dalam berkas ini.', 'Pengodean berkas teks tidak dapat ditentukan.',
           'Berkas DOCX tidak valid.', 'Berkas DOCX tidak memiliki document.xml.',
           'Dukungan PDF memerlukan paket pypdf.', 'PDF ini tidak memiliki teks yang dapat dipilih. Halaman pindaian memerlukan OCR.',
           'Jenis berkas tidak didukung: {extension}.', 'Jenis yang didukung: {extensions}.',
           'Dokumen tidak dapat dibaca.', 'Operasi dokumen gagal.', 'Detail teknis'),
}


def document_message(language, key, **values):
    return _TEXT.get(language, _TEXT['en'])[_KEYS.index(key)].format(**values)


def localized_document_error(error, language):
    """Translate our parser failures; retain unknown library/OS details verbatim."""
    raw = str(error)
    exact = {
        'No file selected.': 'no_file', 'File not found.': 'missing',
        'No readable text was found in this file.': 'empty', 'Invalid DOCX file.': 'invalid_docx',
        'DOCX document.xml is missing.': 'docx_missing',
        'PDF support requires the pypdf package.': 'missing_pdf',
        'No selectable text was found in this PDF. Scanned PDFs require OCR.': 'scanned_pdf',
    }
    if raw in exact:
        return document_message(language, exact[raw])
    if raw.startswith('Unsupported file type: '):
        extension, separator, supported = raw.removeprefix('Unsupported file type: ').partition('. Supported: ')
        extension = extension.removesuffix('.')
        value = document_message(language, 'unsupported', extension='?' if extension == 'unknown' else extension)
        if separator:
            value += '\n' + document_message(language, 'supported', extensions=supported.removesuffix('.'))
        return value
    # Known file/type identifiers are kept as written, rather than translated
    # or reflected as markup by the UI. Unknown errors remain diagnostic data.
    key = ('decode' if raw.startswith('Could not decode text file:') else
           'read_error' if raw.startswith('Failed to read ') else 'failed')
    return (document_message(language, key) + '\n\n' +
            document_message(language, 'details') + ':\n' + raw)
