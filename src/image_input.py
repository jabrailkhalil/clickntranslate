"""Clipboard/file images use the selected OCR backend without capturing the screen."""
import os
import copy
from pathlib import Path
import threading

from PyQt5 import QtCore, QtGui, QtWidgets


TEXT = {
    'en': {'open': 'Open image', 'hint': 'Translate a photo or screenshot. Choose a file, drop an image here, or paste it with Ctrl+V.', 'images': 'Images', 'reading': 'Reading image…', 'large': 'This image is too large. Use an image up to 16 megapixels and a file up to 32 MB.', 'invalid': 'Could not read this image. Choose a PNG, JPEG, WebP, BMP, TIFF or GIF file.', 'empty': 'No text was found. Check the OCR engine and source language, or try a clearer image.', 'error': 'Could not recognize the image', 'cancel': 'Cancel image recognition'},
    'ru': {'open': 'Открыть изображение', 'hint': 'Перевести фото или скриншот. Выберите файл, перетащите изображение сюда или вставьте его через Ctrl+V.', 'images': 'Изображения', 'reading': 'Распознавание изображения…', 'large': 'Изображение слишком большое. Используйте изображение до 16 мегапикселей и файл до 32 МБ.', 'invalid': 'Не удалось прочитать изображение. Выберите файл PNG, JPEG, WebP, BMP, TIFF или GIF.', 'empty': 'Текст не найден. Проверьте OCR-движок и исходный язык или попробуйте более чёткое изображение.', 'error': 'Не удалось распознать изображение', 'cancel': 'Отменить распознавание изображения'},
    'es': {'open': 'Abrir imagen', 'hint': 'Traduce una foto o captura. Elige un archivo, arrastra una imagen aquí o pégala con Ctrl+V.', 'images': 'Imágenes', 'reading': 'Reconociendo imagen…', 'large': 'La imagen es demasiado grande. Usa una imagen de hasta 16 megapíxeles y un archivo de hasta 32 MB.', 'invalid': 'No se pudo leer la imagen. Elige un archivo PNG, JPEG, WebP, BMP, TIFF o GIF.', 'empty': 'No se encontró texto. Revisa el motor OCR y el idioma de origen o prueba una imagen más clara.', 'error': 'No se pudo reconocer la imagen', 'cancel': 'Cancelar reconocimiento de imagen'},
    'de': {'open': 'Bild öffnen', 'hint': 'Foto oder Screenshot übersetzen. Datei wählen, Bild hierher ziehen oder mit Ctrl+V einfügen.', 'images': 'Bilder', 'reading': 'Bild wird erkannt…', 'large': 'Das Bild ist zu groß. Verwende ein Bild mit höchstens 16 Megapixeln und eine Datei bis 32 MB.', 'invalid': 'Das Bild konnte nicht gelesen werden. Wähle eine PNG-, JPEG-, WebP-, BMP-, TIFF- oder GIF-Datei.', 'empty': 'Kein Text gefunden. Prüfe OCR-Engine und Ausgangssprache oder verwende ein deutlicheres Bild.', 'error': 'Bilderkennung fehlgeschlagen', 'cancel': 'Bilderkennung abbrechen'},
    'fr': {'open': 'Ouvrir une image', 'hint': 'Traduisez une photo ou une capture. Choisissez un fichier, déposez une image ici ou collez-la avec Ctrl+V.', 'images': 'Images', 'reading': 'Reconnaissance de l’image…', 'large': 'Cette image est trop grande. Utilisez une image de 16 mégapixels maximum et un fichier de 32 Mo maximum.', 'invalid': 'Impossible de lire cette image. Choisissez un fichier PNG, JPEG, WebP, BMP, TIFF ou GIF.', 'empty': 'Aucun texte trouvé. Vérifiez le moteur OCR et la langue source ou essayez une image plus nette.', 'error': 'Impossible de reconnaître l’image', 'cancel': 'Annuler la reconnaissance de l’image'},
    'zh': {'open': '打开图片', 'hint': '翻译照片或截图。选择文件、将图片拖到这里，或按 Ctrl+V 粘贴。', 'images': '图片', 'reading': '正在识别图片…', 'large': '图片过大。请使用不超过 1600 万像素、文件不超过 32 MB 的图片。', 'invalid': '无法读取图片。请选择 PNG、JPEG、WebP、BMP、TIFF 或 GIF 文件。', 'empty': '未找到文字。请检查 OCR 引擎和源语言，或尝试更清晰的图片。', 'error': '无法识别图片', 'cancel': '取消图片识别'},
    'pt': {'open': 'Abrir imagem', 'hint': 'Traduza uma foto ou captura de tela. Escolha um arquivo, arraste uma imagem aqui ou cole com Ctrl+V.', 'images': 'Imagens', 'reading': 'Reconhecendo imagem…', 'large': 'A imagem é muito grande. Use uma imagem de até 16 megapixels e um arquivo de até 32 MB.', 'invalid': 'Não foi possível ler a imagem. Escolha um arquivo PNG, JPEG, WebP, BMP, TIFF ou GIF.', 'empty': 'Nenhum texto encontrado. Verifique o mecanismo OCR e o idioma de origem ou tente uma imagem mais nítida.', 'error': 'Não foi possível reconhecer a imagem', 'cancel': 'Cancelar reconhecimento da imagem'},
    'it': {'open': 'Apri immagine', 'hint': 'Traduci una foto o schermata. Scegli un file, trascina qui un’immagine o incollala con Ctrl+V.', 'images': 'Immagini', 'reading': 'Riconoscimento immagine…', 'large': 'L’immagine è troppo grande. Usa un’immagine fino a 16 megapixel e un file fino a 32 MB.', 'invalid': 'Impossibile leggere l’immagine. Scegli un file PNG, JPEG, WebP, BMP, TIFF o GIF.', 'empty': 'Nessun testo trovato. Controlla il motore OCR e la lingua di origine o prova un’immagine più nitida.', 'error': 'Impossibile riconoscere l’immagine', 'cancel': 'Annulla riconoscimento immagine'},
    'ar': {'open': 'فتح صورة', 'hint': 'ترجم صورة أو لقطة شاشة. اختر ملفًا، أو اسحب صورة إلى هنا، أو الصقها باستخدام Ctrl+V.', 'images': 'الصور', 'reading': 'جارٍ التعرف على نص الصورة…', 'large': 'الصورة كبيرة جدًا. استخدم صورة لا تتجاوز 16 ميجابكسل وملفًا لا يتجاوز 32 ميجابايت.', 'invalid': 'تعذر قراءة الصورة. اختر ملف PNG أو JPEG أو WebP أو BMP أو TIFF أو GIF.', 'empty': 'لم يُعثر على نص. تحقق من محرك OCR ولغة المصدر أو جرّب صورة أوضح.', 'error': 'تعذر التعرف على نص الصورة', 'cancel': 'إلغاء التعرف على نص الصورة'},

    'tr': {'open': 'Görüntü aç',
     'hint': 'Fotoğraf veya ekran görüntüsünü çevirin. Dosya seçin, buraya görüntü bırakın veya Ctrl+V '
             'ile yapıştırın.',
     'images': 'Görüntüler',
     'reading': 'Görüntü okunuyor…',
     'large': 'Görüntü çok büyük. En fazla 16 megapiksel ve 32 MB dosya kullanın.',
     'invalid': 'Görüntü okunamadı. PNG, JPEG, WebP, BMP, TIFF veya GIF seçin.',
     'empty': 'Metin bulunamadı. OCR motoru ve kaynak dilini kontrol edin veya daha net görüntü '
              'deneyin.',
     'error': 'Görüntü tanınamadı',
     'cancel': 'Görüntü tanımayı iptal et'},
    'hi': {'open': 'इमेज खोलें',
     'hint': 'फ़ोटो या स्क्रीनशॉट अनुवाद करें। फ़ाइल चुनें, इमेज यहाँ छोड़ें या Ctrl+V से चिपकाएँ।',
     'images': 'इमेज',
     'reading': 'इमेज पढ़ी जा रही है…',
     'large': 'इमेज बहुत बड़ी है। अधिकतम 16 मेगापिक्सेल और 32 MB की फ़ाइल इस्तेमाल करें।',
     'invalid': 'इमेज पढ़ नहीं सके। PNG, JPEG, WebP, BMP, TIFF या GIF चुनें।',
     'empty': 'टेक्स्ट नहीं मिला। OCR इंजन और स्रोत भाषा जाँचें या साफ़ इमेज आज़माएँ।',
     'error': 'इमेज पहचानी नहीं जा सकी',
     'cancel': 'इमेज पहचान रद्द करें'},
    'id': {'open': 'Buka gambar',
     'hint': 'Terjemahkan foto atau tangkapan layar. Pilih berkas, letakkan gambar di sini, atau '
             'tempel dengan Ctrl+V.',
     'images': 'Gambar',
     'reading': 'Membaca gambar…',
     'large': 'Gambar terlalu besar. Gunakan gambar hingga 16 megapiksel dan berkas hingga 32 MB.',
     'invalid': 'Gambar tidak dapat dibaca. Pilih PNG, JPEG, WebP, BMP, TIFF, atau GIF.',
     'empty': 'Teks tidak ditemukan. Periksa mesin OCR dan bahasa sumber, atau coba gambar lebih '
              'jelas.',
     'error': 'Gambar tidak dapat dikenali',
     'cancel': 'Batalkan pengenalan gambar'},
}
EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff', '.gif'}
MAX_PIXELS = 16_000_000
MAX_BYTES = 32 * 1024 * 1024


def image_text(locale, key):
    text = TEXT.get(locale, TEXT['en'])[key]
    if key == 'hint' and QtWidgets.QApplication.instance() is not None:
        text = text.replace('Ctrl+V', QtGui.QKeySequence(QtGui.QKeySequence.Paste).toString(QtGui.QKeySequence.NativeText))
    return text


def image_filter(locale):
    return image_text(locale, 'images') + ' (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif)'


def image_icon(dark=True):
    pixmap = QtGui.QPixmap(24, 24)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtGui.QPen(QtGui.QColor('#eeeaf2' if dark else '#332a3d'), 1.6))
    painter.drawRoundedRect(QtCore.QRectF(3, 4, 18, 16), 2, 2)
    painter.drawEllipse(QtCore.QPointF(8, 9), 1.5, 1.5)
    painter.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(4, 17), QtCore.QPointF(10, 12),
                                       QtCore.QPointF(14, 16), QtCore.QPointF(17, 13), QtCore.QPointF(20, 16)]))
    painter.end()
    return QtGui.QIcon(pixmap)


def is_image_file(path):
    return Path(path).suffix.lower() in EXTENSIONS


def has_image_mime(mime):
    # Drag-move and paste availability are queried repeatedly. Inspect formats
    # here, and copy full-resolution pixels only when the user actually inserts.
    return mime.hasImage() or any(url.isLocalFile() and is_image_file(url.toLocalFile())
                                 for url in mime.urls() if mime.hasUrls())


def image_from_mime(mime):
    """Copy clipboard pixels before leaving the GUI thread; never write to it."""
    if mime.hasImage():
        value = mime.imageData()
        image = value.toImage() if isinstance(value, QtGui.QPixmap) else value
        if isinstance(image, QtGui.QImage) and not image.isNull():
            return image.copy()
    for url in mime.urls() if mime.hasUrls() else ():
        path = url.toLocalFile()
        if path and is_image_file(path):
            return path
    return None


class ImageInputTextEdit(QtWidgets.QTextEdit):
    image_requested = QtCore.pyqtSignal(object)
    file_requested = QtCore.pyqtSignal(str)

    def _document_path(self, mime):
        if self.receivers(self.file_requested) and mime.hasUrls():
            return next((url.toLocalFile() for url in mime.urls() if url.isLocalFile()), '')
        return ''

    def canInsertFromMimeData(self, mime):
        return has_image_mime(mime) or bool(self._document_path(mime)) or super().canInsertFromMimeData(mime)

    def keyPressEvent(self, event):
        if event.matches(QtGui.QKeySequence.Paste) and self.receivers(self.image_requested) and not self.isReadOnly():
            mime = QtWidgets.QApplication.clipboard().mimeData()
            if has_image_mime(mime):
                self.insertFromMimeData(mime)
                event.accept()
                return
        super().keyPressEvent(event)

    def insertFromMimeData(self, mime):
        image = image_from_mime(mime)
        if image is not None and self.receivers(self.image_requested):
            self.image_requested.emit(image)
            return
        path = self._document_path(mime)
        if path:
            self.file_requested.emit(path)
            return
        super().insertFromMimeData(mime)

    def dragEnterEvent(self, event):
        if (self.receivers(self.image_requested) and has_image_mime(event.mimeData())) or self._document_path(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event):
        image = image_from_mime(event.mimeData())
        if image is not None and self.receivers(self.image_requested):
            self.image_requested.emit(image)
            event.acceptProposedAction()
        elif self._document_path(event.mimeData()):
            self.file_requested.emit(self._document_path(event.mimeData()))
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


def load_image(payload):
    if isinstance(payload, QtGui.QImage):
        image = payload
    else:
        if os.path.getsize(payload) > MAX_BYTES:
            raise ValueError('large')
        reader = QtGui.QImageReader(str(payload))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.width() * size.height() > MAX_PIXELS:
            raise ValueError('large')
        image = reader.read()
    if image.isNull():
        raise ValueError('invalid')
    if image.width() * image.height() > MAX_PIXELS:
        raise ValueError('large')
    return image


def recognize_image(payload, config, source, target, cancelled):
    image = load_image(payload)
    if cancelled():
        return '', None
    from api_providers import VISION_ENGINES, recognize, ProviderError, display_error
    engine = str(config.get('ocr_engine', 'Windows'))
    provider = {name.lower(): key for name, key in VISION_ENGINES.items()}.get(engine.lower())
    if provider:
        from PIL import Image
        rgba = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
        buffer = rgba.bits()
        buffer.setsize(rgba.byteCount())
        pil = Image.frombytes('RGBA', (rgba.width(), rgba.height()), bytes(buffer),
                              'raw', 'RGBA', rgba.bytesPerLine()).convert('RGB')
        try:
            result = recognize(provider, pil, source, target, config, cancelled)
        except ProviderError as error:
            raise RuntimeError(display_error(error, config.get('interface_language', 'en'))) from None
        return result.source, result.translation
    from ocr import create_position_ocr_worker
    worker = create_position_ocr_worker(image, source, engine)
    if worker is None:
        raise ValueError('invalid')
    if source == 'auto' and getattr(worker, 'engine', '') == 'windows':
        from ocr import _recognize_with_windows_auto
        return _recognize_with_windows_auto(worker.bitmap, cancel_check=cancelled,
            join_paragraphs=config.get('ocr_join_paragraphs') is True), None
    rows = []
    worker.result_ready.connect(lambda value: rows.extend(value), QtCore.Qt.DirectConnection)
    worker.run()  # This function already runs outside the GUI thread.
    if cancelled():
        return '', None
    if getattr(worker, 'error_message', ''):
        raise RuntimeError(worker.error_message)
    if config.get('ocr_join_paragraphs') is True:
        from ocr_paragraphs import paragraph_text
        text = paragraph_text(rows)
    else:
        text = '\n'.join(str(row[4]) for row in rows if str(row[4]).strip())
    return text, None


class ImageImportController(QtCore.QObject):
    ready = QtCore.pyqtSignal(str, object)
    failed = QtCore.pyqtSignal(str)
    busy_changed = QtCore.pyqtSignal(bool)
    _completed = QtCore.pyqtSignal(int, object)

    def __init__(self, parent):
        super().__init__(parent)
        self.busy = False
        self._revision = 0
        self._cancel = threading.Event()
        self._completed.connect(self._deliver)
        self.destroyed.connect(lambda: self._cancel.set())

    def start(self, payload, config, source, target):
        if self.busy:
            return False
        self._revision += 1
        revision = self._revision
        self._cancel = cancel = threading.Event()
        snapshot = copy.deepcopy(config)
        self.busy = True
        self.busy_changed.emit(True)

        def run():
            try:
                original, translated = recognize_image(payload, snapshot, source, target, cancel.is_set)
                result = (original, translated, '' if original.strip() else 'empty')
            except Exception as error:
                result = ('', None, str(error) if str(error) in ('large', 'invalid') else 'invalid' if isinstance(error, OSError) else str(error))
            if not cancel.is_set():
                try:
                    self._completed.emit(revision, result)
                except RuntimeError:
                    pass  # The owning window was closed while OCR was finishing.
        threading.Thread(target=run, name='image-recognition', daemon=True).start()
        return True

    def cancel(self):
        self._revision += 1
        self._cancel.set()
        was_busy, self.busy = self.busy, False
        if was_busy:
            self.busy_changed.emit(False)

    def _deliver(self, revision, result):
        if revision != self._revision or self._cancel.is_set():
            return
        self.busy = False
        self.busy_changed.emit(False)
        original, translated, error = result
        if error:
            self.failed.emit(error)
        else:
            self.ready.emit(original, translated)
