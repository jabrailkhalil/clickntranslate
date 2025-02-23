import asyncio
import os
import winrt

from PIL import Image
from winrt.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage import StorageFile, FileAccessMode
import winrt.windows.storage.streams as streams

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QWidget


# -------------------- Функции для OCR --------------------
async def run_ocr_with_engine(bitmap, engine):
    return await engine.recognize_async(bitmap)


def load_image_from_pil(pil_image):
    pil_image = pil_image.convert("RGBA")
    data_writer = streams.DataWriter()
    byte_data = pil_image.tobytes()
    data_writer.write_bytes(list(byte_data))
    bitmap = SoftwareBitmap(BitmapPixelFormat.RGBA8, pil_image.width, pil_image.height)
    bitmap.copy_from_buffer(data_writer.detach_buffer())
    return bitmap


# -------------------- Поток для выполнения OCR --------------------
class OCRWorker(QtCore.QThread):
    result_ready = QtCore.pyqtSignal(str)

    def __init__(self, bitmap, language_code, parent=None):
        super().__init__(parent)
        self.bitmap = bitmap
        self.language_code = language_code

    def run(self):
        try:
            from winrt.windows.globalization import Language
            language = Language(self.language_code)
            engine = OcrEngine.try_create_from_language(language)
            if engine is None:
                self.result_ready.emit("")
                return
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            recognized = loop.run_until_complete(run_ocr_with_engine(self.bitmap, engine))
            recognized_text = recognized.text if recognized and recognized.text else ""
            loop.close()
        except Exception as e:
            print("Ошибка OCR:", e)
            recognized_text = ""
        self.result_ready.emit(recognized_text)


# -------------------- Оверлей для захвата области экрана и выбора языка --------------------
class ScreenCaptureOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.start_point = None
        self.end_point = None
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.screen = QApplication.primaryScreen()
        self.showFullScreen()
        # Создаем комбобокс для выбора языка с флагами
        self.lang_combo = QtWidgets.QComboBox(self)
        self.lang_combo.addItem(QtGui.QIcon("icons/Russian_flag.png"), "Русский", "ru")
        self.lang_combo.addItem(QtGui.QIcon("icons/American_flag.png"), "English", "en")
        self.lang_combo.setCurrentIndex(0)
        self.lang_combo.setIconSize(QtCore.QSize(64, 64))
        # Устанавливаем стиль без стрелки, с нужным размером бокса
        self.lang_combo.setStyleSheet("""
            background-color: rgba(255,255,255,200);
            font-size: 12px;
            min-height: 64px;
            QComboBox::down-arrow { image: none; }
            QComboBox::drop-down { border: 0px; width: 0px; }
        """)
        self.lang_combo.adjustSize()
        # Размещаем комбобокс по центру верхней части экрана
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
            self.update()

    def mouseMoveEvent(self, event):
        if self.start_point:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.start_point and self.end_point:
            rect = QtCore.QRect(self.start_point, self.end_point).normalized()
            self.capture_and_copy(rect)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
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
        self.ocr_worker = OCRWorker(bitmap, language_code)
        self.ocr_worker.result_ready.connect(self.handle_ocr_result)
        self.ocr_worker.start()

    def handle_ocr_result(self, text):
        import pyperclip
        if text:
            try:
                pyperclip.copy(text)
                print("Распознанный текст скопирован в буфер обмена:", text)
            except Exception as e:
                print("Ошибка копирования в буфер через pyperclip:", e)
        else:
            print("OCR не распознал текст.")
        self.close()


def run_screen_capture():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        overlay = ScreenCaptureOverlay()
        overlay.show()
        app.exec_()
    else:
        overlay = ScreenCaptureOverlay()
        overlay.show()


if __name__ == "__main__":
    run_screen_capture()
