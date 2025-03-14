import sys
import asyncio
import os
import json
import winrt
import logging
from datetime import datetime

from PIL import Image
from winrt.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage import StorageFile, FileAccessMode
import winrt.windows.storage.streams as streams

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
import pyperclip

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def load_ocr_config():
    config_path = "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки конфигурации OCR: {e}")
        config = {}
    return config.get("ocr_language", "ru")

def save_translation_history(text, language):
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        return
    if not config.get("history", False):
        return

    history_file = "translation_history.json"
    if not os.path.exists(history_file):
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=4)
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
    except:
        history = []
    history.append({
        "timestamp": datetime.now().isoformat(),
        "language": language,
        "text": text
    })
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения истории переводов: {e}")

async def run_ocr_with_engine(bitmap, engine):
    logging.info("Запуск распознавания изображения с выбранным OCR движком...")
    return await engine.recognize_async(bitmap)

def load_image_from_pil(pil_image):
    pil_image = pil_image.convert("RGBA")
    data_writer = streams.DataWriter()
    byte_data = pil_image.tobytes()
    data_writer.write_bytes(list(byte_data))
    bitmap = SoftwareBitmap(BitmapPixelFormat.RGBA8, pil_image.width, pil_image.height)
    bitmap.copy_from_buffer(data_writer.detach_buffer())
    return bitmap

class OCRWorker(QtCore.QThread):
    result_ready = QtCore.pyqtSignal(str)
    def __init__(self, bitmap, language_code, parent=None):
        super().__init__(parent)
        self.bitmap = bitmap
        self.language_code = language_code
    def run(self):
        try:
            from winrt.windows.globalization import Language
            if self.language_code == "en":
                lang_tag = "en-US"
            else:
                lang_tag = self.language_code
            logging.info(f"Выбран язык для OCR: {lang_tag}")
            language = Language(lang_tag)
            engine = OcrEngine.try_create_from_language(language)
            if engine is None:
                logging.warning(f"OCR движок для '{lang_tag}' не найден, переключаюсь на 'ru'")
                language = Language("ru")
                engine = OcrEngine.try_create_from_language(language)
            if engine is None:
                logging.error("Не удалось создать OCR движок ни для выбранного языка, ни для 'ru'.")
                self.result_ready.emit("")
                return
            logging.info("OCR движок успешно создан. Начинаю распознавание...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            recognized = loop.run_until_complete(run_ocr_with_engine(self.bitmap, engine))
            recognized_text = recognized.text if recognized and recognized.text else ""
            logging.info("Распознавание завершено.")
            loop.close()
        except Exception as e:
            logging.error(f"Ошибка OCR: {e}")
            recognized_text = ""
        self.result_ready.emit(recognized_text)

class ScreenCaptureOverlay(QWidget):
    def __init__(self, mode="ocr"):
        super().__init__()
        self.mode = mode  # Режим работы: "ocr" или "translate"
        self.start_point = None
        self.end_point = None
        self.last_rect = None
        self.current_language = "ru"  # Значение по умолчанию
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.screen = QApplication.primaryScreen()
        self.showFullScreen()
        logging.info("Запущен оверлей захвата экрана.")
        default_lang = load_ocr_config()
        self.lang_combo = QtWidgets.QComboBox(self)
        self.lang_combo.addItem(QtGui.QIcon("icons/Russian_flag.png"), "Русский", "ru")
        self.lang_combo.addItem(QtGui.QIcon("icons/American_flag.png"), "English", "en")
        default_index = 0 if default_lang == "ru" else 1
        self.lang_combo.setCurrentIndex(default_index)
        self.lang_combo.setIconSize(QtCore.QSize(64, 64))
        self.lang_combo.setStyleSheet("""
            background-color: rgba(255,255,255,200);
            font-size: 12px;
            min-height: 64px;
            QComboBox::down-arrow { image: none; }
            QComboBox::drop-down { border: 0px; width: 0px; }
        """)
        self.lang_combo.adjustSize()
        self.lang_combo.move((self.width() - self.lang_combo.width()) // 2, 20)
        self.lang_combo.show()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 150))
        if self.start_point and self.end_point:
            rect = QtCore.QRect(self.start_point, self.end_point).normalized()
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_Clear)
            painter.fillRect(rect, QtGui.QColor(0, 0, 0, 0))
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            pen = QtGui.QPen(QtGui.QColor(255, 255, 255), 2)
            painter.setPen(pen)
            painter.drawRect(rect)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = self.start_point
            logging.info(f"Начало выделения: {self.start_point}")
            self.update()

    def mouseMoveEvent(self, event):
        if self.start_point:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.start_point and self.end_point:
            rect = QtCore.QRect(self.start_point, self.end_point).normalized()
            self.last_rect = rect
            logging.info(f"Завершено выделение области: {rect}")
            self.capture_and_copy(rect)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            logging.info("Нажата клавиша ESC, завершаем OCR.")
            self.close()

    def capture_and_copy(self, rect):
        screenshot = self.screen.grabWindow(0)
        selected_pixmap = screenshot.copy(rect)
        qimage = selected_pixmap.toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
        width = qimage.width()
        height = qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        pil_image = Image.frombuffer("RGBA", (width, height), ptr, "raw", "RGBA", 0, 1)
        bitmap = load_image_from_pil(pil_image)
        language_code = self.lang_combo.currentData() or "ru"
        self.current_language = language_code
        logging.info(f"Используемый язык для OCR: {language_code}")
        self.ocr_worker = OCRWorker(bitmap, language_code)
        self.ocr_worker.result_ready.connect(self.handle_ocr_result)
        self.ocr_worker.start()

    def handle_ocr_result(self, text):
        if text:
            if self.mode == "translate":
                from translater import translate_text
                lang_code = self.lang_combo.currentData() or "ru"
                if lang_code == "ru":
                    source_code = "en"
                    target_code = "ru"
                else:
                    source_code = "ru"
                    target_code = "en"
                try:
                    translated_text = translate_text(text, source_code, target_code)
                except Exception as e:
                    QMessageBox.warning(self, "Ошибка перевода", str(e))
                    translated_text = ""
                if translated_text:
                    msg = QMessageBox(self)
                    msg.setWindowTitle("Перевод" if lang_code == "ru" else "Translation")
                    msg.setText(translated_text)
                    msg.exec_()
                self.close()
            else:
                try:
                    copy_enabled = False
                    try:
                        with open("config.json", "r", encoding="utf-8") as f:
                            config = json.load(f)
                        copy_enabled = config.get("copy_to_clipboard", False)
                    except Exception as e:
                        logging.error(f"Ошибка загрузки конфигурации: {e}")
                    if copy_enabled:
                        pyperclip.copy(text)
                        logging.info(f"Распознанный текст скопирован в буфер обмена: {text}")
                    else:
                        logging.info("Копирование в буфер обмена отключено настройками.")
                    save_translation_history(text, self.current_language)
                    self.close()
                except Exception as e:
                    logging.error(f"Ошибка обработки OCR результата: {e}")
        else:
            logging.info("OCR не распознал текст.")
            msg = QMessageBox(self)
            msg.setWindowIcon(QtGui.QIcon("icons/warning.png"))
            msg.setIcon(QMessageBox.NoIcon)
            msg.setWindowTitle("Ошибка распознавания")
            msg.setText("Распознавание не удалось. Возможно, текст слишком мелкий.\nПопробуйте увеличить область или улучшить качество.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.setStyleSheet(
                "QMessageBox { background-color: #121212; color: #ffffff; } "
                "QLabel { color: #ffffff; font-size: 18px; } "
                "QPushButton { background-color: #1e1e1e; color: #ffffff; border: 1px solid #550000; padding: 5px; min-width: 80px; } "
                "QPushButton:hover { background-color: #333333; }"
            )
            msg.exec_()

def run_screen_capture(mode="ocr"):
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        logging.info("Запуск OCR приложения...")
        overlay = ScreenCaptureOverlay(mode)
        overlay.show()
        app.exec_()
    else:
        overlay = ScreenCaptureOverlay(mode)
        overlay.show()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "translate":
        run_screen_capture("translate")
    else:
        run_screen_capture()
