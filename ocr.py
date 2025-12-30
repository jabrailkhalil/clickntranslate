import sys
import asyncio
import os
import json
import logging
from datetime import datetime
import shutil
import numpy as np

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
import pyperclip

# Настройка логирования в файл для диагностики
def get_log_path():
    if hasattr(sys, '_MEIPASS'):
        # В сборке - логируем рядом с exe
        return os.path.join(os.path.dirname(sys.executable), "ocr_debug.log")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_debug.log")

_debug_log_path = get_log_path()

def debug_log(msg):
    """Записать сообщение в лог-файл."""
    try:
        with open(_debug_log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except:
        pass

debug_log("=" * 50)
debug_log("OCR module loading...")
debug_log(f"sys.executable: {sys.executable}")
debug_log(f"frozen: {getattr(sys, 'frozen', False)}")
debug_log(f"_MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")

# Явные импорты winrt для PyInstaller (должны быть до использования)
_WINRT_AVAILABLE = False
_WINRT_ERROR = None
winrt_collections = None  # Будет загружен лениво

try:
    debug_log("Trying to import winrt...")
    import winrt
    debug_log(f"winrt imported: {winrt}")
    debug_log(f"winrt location: {getattr(winrt, '__file__', 'N/A')}")
    
    debug_log("Trying to import winrt.windows.media.ocr...")
    import winrt.windows.media.ocr as winrt_ocr
    debug_log(f"winrt_ocr imported: {winrt_ocr}")
    
    debug_log("Trying to import winrt.windows.globalization...")
    import winrt.windows.globalization as winrt_glob
    debug_log(f"winrt_glob imported: {winrt_glob}")
    
    debug_log("Trying to import winrt.windows.graphics.imaging...")
    import winrt.windows.graphics.imaging as winrt_imaging
    debug_log(f"winrt_imaging imported: {winrt_imaging}")
    
    debug_log("Trying to import winrt.windows.storage.streams...")
    import winrt.windows.storage.streams as winrt_streams
    debug_log(f"winrt_streams imported: {winrt_streams}")
    
    debug_log("Trying to import winrt.windows.foundation...")
    import winrt.windows.foundation as winrt_foundation
    debug_log(f"winrt_foundation imported: {winrt_foundation}")
    
    # collections импортируем опционально (используется лениво)
    try:
        debug_log("Trying to import winrt.windows.foundation.collections...")
        import winrt.windows.foundation.collections as winrt_collections
        debug_log(f"winrt_collections imported: {winrt_collections}")
    except ImportError:
        debug_log("winrt.windows.foundation.collections not available at startup (will try lazy load)")
    
    _WINRT_AVAILABLE = True
    debug_log("SUCCESS: Core winrt modules imported!")
except ImportError as e:
    _WINRT_ERROR = str(e)
    debug_log(f"IMPORT ERROR: {e}")
    import traceback
    debug_log(traceback.format_exc())
except Exception as e:
    _WINRT_ERROR = str(e)
    debug_log(f"EXCEPTION: {e}")
    import traceback
    debug_log(traceback.format_exc())

debug_log(f"_WINRT_AVAILABLE = {_WINRT_AVAILABLE}")

# Lazy import for RapidOCR (optional, super-fast)
_rapidocr_engine = None

def _get_rapidocr_engine():
    """Возвращает переиспользуемый экземпляр RapidOCR."""
    global _rapidocr_engine
    if _rapidocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapidocr_engine = RapidOCR()
        except ImportError:
            logging.warning("RapidOCR not installed. Install with: pip install rapidocr-onnxruntime")
            return None
    return _rapidocr_engine
# Ленивый импорт для избежания циклического импорта
# from main import save_copy_history, show_translation_dialog

logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(message)s')  # Уменьшен уровень логирования

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_data_file(filename):
    data_dir = os.path.join(get_app_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, filename)

# --- Кэширование конфигурации ---
_ocr_config_cache = None
_ocr_config_mtime = 0

def get_cached_ocr_config():
    """Возвращает закэшированную конфигурацию OCR."""
    global _ocr_config_cache, _ocr_config_mtime
    config_path = get_data_file("config.json")
    try:
        mtime = os.path.getmtime(config_path)
        if _ocr_config_cache is None or mtime > _ocr_config_mtime:
            with open(config_path, "r", encoding="utf-8") as f:
                _ocr_config_cache = json.load(f)
            _ocr_config_mtime = mtime
    except Exception:
        if _ocr_config_cache is None:
            _ocr_config_cache = {}
    return _ocr_config_cache

def load_ocr_config():
    return get_cached_ocr_config().get("ocr_language", "ru")

def _save_translation_history_sync(text, language):
    """Синхронная запись в историю переводов (выполняется в отдельном потоке)."""
    try:
        config = get_cached_ocr_config()
    except Exception:
        return
    if not config.get("history", False):
        return
    history_file = get_data_file("translation_history.json")
    if not os.path.exists(history_file):
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=4)
    
    history = []
    try:
        if sys.platform == "win32":
            import msvcrt
            with open(history_file, "r+", encoding="utf-8") as f:
                try:
                    f.seek(0, 2)
                    file_size = f.tell()
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, max(file_size, 1))
                except Exception:
                    pass
                try:
                    content = f.read()
                    if content.strip():
                        history = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    history = []
                history.append({
                    "timestamp": datetime.now().isoformat(),
                    "language": language,
                    "text": text
                })
                f.seek(0)
                f.truncate()
                json.dump(history, f, ensure_ascii=False, indent=4)
                try:
                    f.seek(0, 2)
                    file_size = f.tell()
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, max(file_size, 1))
                except Exception:
                    pass
        else:
            import fcntl
            with open(history_file, "r+", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    content = f.read()
                    if content.strip():
                        history = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    history = []
                history.append({
                    "timestamp": datetime.now().isoformat(),
                    "language": language,
                    "text": text
                })
                f.seek(0)
                f.truncate()
                json.dump(history, f, ensure_ascii=False, indent=4)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        # Fallback без блокировки
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
        history.append({
            "timestamp": datetime.now().isoformat(),
            "language": language,
            "text": text
        })
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

def save_translation_history(text, language):
    """Асинхронно сохранить перевод в историю (не блокирует UI)."""
    import threading
    threading.Thread(target=_save_translation_history_sync, args=(text, language), daemon=True).start()

async def run_ocr_with_engine(bitmap, engine):
    debug_log(f"run_ocr_with_engine called")
    debug_log(f"bitmap = {bitmap}")
    debug_log(f"engine = {engine}")
    try:
        # Ensure the bitmap is valid
        if bitmap is None:
            debug_log("ERROR: Bitmap is None!")
            return None
        
        debug_log("Calling engine.recognize_async...")
        result = await engine.recognize_async(bitmap)
        debug_log(f"recognize_async returned: {result}")
        
        if result:
            debug_log(f"Result object: {result}")
            # Check if lines exist
            if hasattr(result, 'lines'):
                line_count = len(result.lines) if result.lines else 0
                debug_log(f"Lines count: {line_count}")
                if line_count > 0:
                    for i, line in enumerate(result.lines):
                        debug_log(f"Line {i}: {line.text}")
                return result
            else:
                debug_log("ERROR: Result has no 'lines' attribute")
                return None
        else:
            debug_log("ERROR: recognize_async returned None")
            return None
    except Exception as e:
        debug_log(f"EXCEPTION in run_ocr_with_engine: {e}")
        import traceback
        debug_log(traceback.format_exc())
        return None

def load_image_from_pil(pil_image):
    # Используем предзагруженные winrt модули
    if not _WINRT_AVAILABLE:
        return None
    pil_image = pil_image.convert("RGBA")
    data_writer = winrt_streams.DataWriter()
    byte_data = pil_image.tobytes()
    data_writer.write_bytes(list(byte_data))
    bitmap = winrt_imaging.SoftwareBitmap(winrt_imaging.BitmapPixelFormat.RGBA8, pil_image.width, pil_image.height)
    bitmap.copy_from_buffer(data_writer.detach_buffer())
    return bitmap

# Cache for Windows OCR engines per language tag
_OCR_ENGINE_CACHE = {}
_OVERLAY_POOL = {"ocr": None, "copy": None, "translate": None}

def _get_windows_ocr_engine(lang_tag: str):
    """Получить Windows OCR движок для указанного языка."""
    global _WINRT_AVAILABLE
    
    debug_log(f"_get_windows_ocr_engine called with lang_tag={lang_tag}")
    debug_log(f"_WINRT_AVAILABLE = {_WINRT_AVAILABLE}")
    
    if not _WINRT_AVAILABLE:
        debug_log(f"FAILED: WinRT not available. Error was: {_WINRT_ERROR}")
        logging.error("WinRT modules are not available")
        return None
    
    try:
        debug_log("Getting Language and OcrEngine classes...")
        # Используем предзагруженные модули
        Language = winrt_glob.Language
        OcrEngine = winrt_ocr.OcrEngine
        debug_log(f"Language={Language}, OcrEngine={OcrEngine}")
        
        # Check if language is supported
        debug_log(f"Checking if language {lang_tag} is supported...")
        is_supported = OcrEngine.is_language_supported(Language(lang_tag))
        debug_log(f"is_language_supported = {is_supported}")
        
        if not is_supported:
            debug_log(f"Language {lang_tag} not supported, looking for fallback...")
            # Try to find a fallback
            available_langs = OcrEngine.get_available_recognizer_languages()
            debug_log(f"Available languages count: {available_langs.size}")
            if available_langs.size > 0:
                fallback = available_langs.get_at(0)
                debug_log(f"Falling back to: {fallback.language_tag}")
                lang_tag = fallback.language_tag
            else:
                debug_log("ERROR: No OCR languages installed on this system!")
                return None

        if lang_tag not in _OCR_ENGINE_CACHE:
            debug_log(f"Creating new OCR engine for {lang_tag}...")
            lang = Language(lang_tag)
            engine = OcrEngine.try_create_from_language(lang)
            debug_log(f"Engine created: {engine}")
            if engine:
                _OCR_ENGINE_CACHE[lang_tag] = engine
                debug_log(f"SUCCESS: OCR engine cached for {lang_tag}")
            else:
                debug_log(f"FAILED: OcrEngine.try_create_from_language returned None")
        
        result = _OCR_ENGINE_CACHE.get(lang_tag)
        debug_log(f"Returning engine: {result}")
        return result
    except Exception as e:
        debug_log(f"EXCEPTION in _get_windows_ocr_engine: {e}")
        import traceback
        debug_log(traceback.format_exc())
        return None

def qimage_to_softwarebitmap(qimage):
    debug_log(f"qimage_to_softwarebitmap called")
    debug_log(f"qimage = {qimage}, isNull = {qimage.isNull() if qimage else 'N/A'}")
    
    # Convert QImage (RGBA8888) to SoftwareBitmap without PIL
    if not _WINRT_AVAILABLE:
        debug_log("ERROR: WINRT not available in qimage_to_softwarebitmap")
        return None

    try:
        qimg = qimage.convertToFormat(QtGui.QImage.Format_RGBA8888)
        width = qimg.width()
        height = qimg.height()
        debug_log(f"Image size: {width}x{height}")

        ptr = qimg.constBits()
        ptr.setsize(qimg.byteCount())
        debug_log(f"Byte count: {qimg.byteCount()}")

        data_writer = winrt_streams.DataWriter()
        data_writer.write_bytes(bytes(ptr))

        bitmap = winrt_imaging.SoftwareBitmap(winrt_imaging.BitmapPixelFormat.RGBA8, width, height)
        bitmap.copy_from_buffer(data_writer.detach_buffer())
        debug_log(f"SoftwareBitmap created: {bitmap}")

        return bitmap
    except Exception as e:
        debug_log(f"EXCEPTION in qimage_to_softwarebitmap: {e}")
        import traceback
        debug_log(traceback.format_exc())
        return None

# Глобальный event loop для OCR (переиспользование)
_ocr_event_loop = None

def _get_ocr_event_loop():
    global _ocr_event_loop
    if _ocr_event_loop is None or _ocr_event_loop.is_closed():
        _ocr_event_loop = asyncio.new_event_loop()
    return _ocr_event_loop

class OCRWorker(QtCore.QThread):
    result_ready = QtCore.pyqtSignal(str)
    def __init__(self, bitmap, language_code, parent=None):
        super().__init__(parent)
        self.bitmap = bitmap
        self.language_code = language_code

    def run(self):
        debug_log(f"OCRWorker.run() started")
        debug_log(f"self.bitmap = {self.bitmap}")
        debug_log(f"self.language_code = {self.language_code}")
        try:
            # Определяем language tag
            lang_tag = {"en": "en-US", "ru": "ru-RU"}.get(self.language_code, self.language_code)
            debug_log(f"lang_tag = {lang_tag}")
            
            engine = _get_windows_ocr_engine(lang_tag)
            debug_log(f"engine = {engine}")
            
            if engine is None:
                debug_log("ERROR: engine is None, emitting empty result")
                self.result_ready.emit("")
                return

            # Переиспользуем event loop
            loop = _get_ocr_event_loop()
            asyncio.set_event_loop(loop)

            debug_log("Calling run_ocr_with_engine...")
            recognized = loop.run_until_complete(run_ocr_with_engine(self.bitmap, engine))
            debug_log(f"recognized = {recognized}")

            recognized_text = ""
            if recognized and hasattr(recognized, 'lines'):
                recognized_text = "\n".join(line.text for line in recognized.lines)
                debug_log(f"recognized_text = '{recognized_text[:100]}...' (length={len(recognized_text)})")
            else:
                debug_log("No recognized text (recognized is None or no lines)")

        except Exception as e:
            debug_log(f"EXCEPTION in OCRWorker.run(): {e}")
            import traceback
            debug_log(traceback.format_exc())
            recognized_text = ""
        
        debug_log(f"Emitting result: '{recognized_text[:50]}...' (len={len(recognized_text)})")
        self.result_ready.emit(recognized_text)

class ScreenCaptureOverlay(QWidget):
    def __init__(self, mode="ocr", defer_show=False):
        super().__init__()
        # Устанавливаем иконку приложения
        self.setWindowIcon(QtGui.QIcon(resource_path("icons/icon.ico")))
        
        self.mode = mode
        self.start_point = None
        self.end_point = None
        self.last_rect = None
        self.current_language = "ru"
        # Removed Qt.Tool, added WindowStaysOnTopHint and FramelessWindowHint
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setCursor(QtCore.Qt.CrossCursor)
        self.screen = QApplication.primaryScreen()
        
        if not defer_show:
            self.show_overlay()
            
        logging.info("Screen capture overlay initialized.")
        default_lang = load_ocr_config()
        self.lang_combo = QtWidgets.QComboBox(self)
        self.lang_combo.addItem(QtGui.QIcon(resource_path("icons/Russian_flag.png")), "Русский", "ru")
        self.lang_combo.addItem(QtGui.QIcon(resource_path("icons/American_flag.png")), "English", "en")
        default_index = 0 if default_lang == "ru" else 1
        self.lang_combo.setCurrentIndex(default_index)
        self.lang_combo.setIconSize(QtCore.QSize(64, 64))
        self.lang_combo.setStyleSheet("""
            background-color: rgba(255,255,255,200);
            font-size: 12px;
            min-height: 64px;
            min-width: 200px;
            QComboBox::down-arrow { image: none; }
            QComboBox::drop-down { border: 0px; width: 0px; }
        """)
        self.lang_combo.setFixedSize(200, 64)
        self.lang_combo.move((self.width() - self.lang_combo.width()) // 2, 20)
        self.lang_combo.setVisible(True if not defer_show else False)

    def show_overlay(self):
        try:
            logging.info("Showing overlay...")
            self.setWindowOpacity(1.0)
            
            # Calculate the total geometry of all screens
            total_rect = QtCore.QRect()
            for screen in QApplication.screens():
                total_rect = total_rect.united(screen.geometry())
            
            # Set geometry to cover the entire virtual desktop
            self.setGeometry(total_rect)
            logging.info(f"Overlay geometry set to: {total_rect}")
            
            self.show()
            self.raise_()
            self.activateWindow()
            self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
            
            # Ensure combo is visible and raised
            self.lang_combo.setVisible(True)
            self.lang_combo.raise_()
            QApplication.processEvents()
            self.update_combo_position()
            
            logging.info(f"Lang combo geometry: {self.lang_combo.geometry()}")
            logging.info(f"Lang combo visible: {self.lang_combo.isVisible()}")
            
            self.update()
            logging.info("Overlay show command executed.")
        except Exception as e:
            logging.error(f"Error showing overlay: {e}")

    def resizeEvent(self, event):
        self.update_combo_position()
        super().resizeEvent(event)

    def update_combo_position(self):
        if hasattr(self, 'lang_combo') and self.lang_combo:
            # Center horizontally relative to the active screen or the entire virtual desktop
            # For better UX, let's center it on the primary screen or the screen where the mouse is
            
            # Find the screen containing the cursor
            cursor_pos = QtGui.QCursor.pos()
            target_screen = QApplication.screenAt(cursor_pos)
            if not target_screen:
                target_screen = QApplication.primaryScreen()
            
            screen_geo = target_screen.geometry()
            
            # Calculate position relative to the overlay's coordinate system
            # The overlay covers the whole virtual desktop, so its (0,0) might be negative relative to primary screen
            # We need to map screen coordinates to overlay coordinates
            
            # Overlay local coordinates are relative to self.pos() (top-left of virtual desktop)
            overlay_top_left = self.geometry().topLeft()
            
            # Center on the target screen
            screen_center_x = screen_geo.center().x()
            combo_width = self.lang_combo.width()
            
            # X in overlay coordinates = Screen Center X - Overlay X - Half Combo Width
            x = screen_center_x - overlay_top_left.x() - (combo_width // 2)
            
            # Y is just a fixed offset from the top of that screen
            y = screen_geo.top() - overlay_top_left.y() + 50 # 50px margin from top
            
            self.lang_combo.move(x, y)
            logging.info(f"Moved combo to {x}, {y} (Screen: {screen_geo})")

    def closeEvent(self, event):
        try:
            prepare_overlay(self.mode)
        except Exception:
            pass
        super().closeEvent(event)

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
        elif event.button() == QtCore.Qt.RightButton:
            # Правая кнопка мыши — полный выход из программы
            logging.info("Правая кнопка мыши — выход из программы")
            self.close()
            # Находим главное окно и вызываем полный выход
            app = QApplication.instance()
            for widget in app.topLevelWidgets():
                if hasattr(widget, 'exit_app'):
                    widget.exit_app()
                    return
            # Fallback: просто завершаем приложение
            app.quit()

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

    @staticmethod
    def get_ocr_engine():
        """Return selected OCR engine from config.json ('Windows' or 'Tesseract')."""
        return get_cached_ocr_config().get("ocr_engine", "Windows")

    # Кэш пути к Tesseract
    _tesseract_cmd_cache = None

    @classmethod
    def get_tesseract_cmd(cls):
        if cls._tesseract_cmd_cache is not None:
            return cls._tesseract_cmd_cache

        tess_cmd = shutil.which("tesseract")
        app_root = get_app_dir()
        local_root = os.path.join(app_root, "ocr", "tesseract")

        # 1) Check direct path
        direct_cmd = os.path.join(local_root, "tesseract.exe")
        if os.path.exists(direct_cmd):
            cls._tesseract_cmd_cache = direct_cmd
            return direct_cmd

        # 2) Recursive search
        for root_dir, _dirs, files in os.walk(local_root):
            if "tesseract.exe" in files:
                result = os.path.join(root_dir, "tesseract.exe")
                cls._tesseract_cmd_cache = result
                return result

        # 3) Standard paths
        if not tess_cmd:
            standard_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.join(os.path.expanduser("~"), "AppData", "Local", "Tesseract-OCR", "tesseract.exe"),
            ]
            for path in standard_paths:
                if os.path.exists(path):
                    cls._tesseract_cmd_cache = path
                    return path

        cls._tesseract_cmd_cache = tess_cmd
        return tess_cmd

    def capture_and_copy(self, rect):
        # Convert overlay-local rect to global screen coordinates
        # The overlay covers the virtual desktop, but its local (0,0) corresponds to its top-left position
        # which might be negative in global coordinates if there's a monitor to the left/top.
        
        # rect is in local coordinates of the overlay widget
        # Map top-left and bottom-right to global coordinates
        global_top_left = self.mapToGlobal(rect.topLeft())
        global_bottom_right = self.mapToGlobal(rect.bottomRight())
        
        global_rect = QtCore.QRect(global_top_left, global_bottom_right)
        
        logging.info(f"Selected local rect: {rect}")
        logging.info(f"Mapped global rect: {global_rect}")
        
        # Grab the specific area from the screen using global coordinates
        # QScreen.grabWindow(0) grabs the desktop. The x, y, w, h arguments are relative to the screen's origin?
        # Actually, for multi-monitor, it's safer to grab the specific screen or use the primary screen with global coords if it supports it.
        # But grabWindow(0) on primary screen usually captures the whole virtual desktop in Qt5 on Windows.
        
        screenshot = self.screen.grabWindow(0, global_rect.x(), global_rect.y(), global_rect.width(), global_rect.height())
        
        # Check if screenshot is valid
        if screenshot.isNull():
            logging.error("Failed to grab screenshot (result is null)")
            return

        qimage = screenshot.toImage()
        language_code = self.lang_combo.currentData() or "ru"
        self.current_language = language_code

        # Determine which OCR engine to use
        ocr_engine_type = self.get_ocr_engine().lower()

        if ocr_engine_type == "rapidocr":
            # Super-fast RapidOCR (ONNX-based)
            from PIL import Image
            qimg_rgba = qimage.convertToFormat(QtGui.QImage.Format_RGBA8888)
            ptr = qimg_rgba.constBits(); ptr.setsize(qimg_rgba.byteCount())
            pil_image = Image.frombuffer("RGBA", (qimg_rgba.width(), qimg_rgba.height()), ptr, "raw", "RGBA", 0, 1)

            rapidocr = _get_rapidocr_engine()
            if rapidocr is None:
                logging.error("RapidOCR not available, falling back to Windows OCR")
            else:
                try:
                    # Convert to RGB numpy array for RapidOCR
                    img_array = np.array(pil_image.convert("RGB"))
                    result, _ = rapidocr(img_array)
                    if result:
                        recognized_text = "\n".join([line[1] for line in result])
                    else:
                        recognized_text = ""
                    logging.info(f"RapidOCR result: {len(recognized_text)} chars")
                    self.handle_ocr_result(recognized_text)
                    return
                except Exception as e:
                    logging.error(f"RapidOCR error: {e}")
                    # Fall through to Windows OCR

        if ocr_engine_type == "tesseract":
            # Determine path to tesseract
            # Lazy import pytesseract and requests
            import pytesseract
            import requests
            # For tesseract we need PIL image
            from PIL import Image
            qimg_rgba = qimage.convertToFormat(QtGui.QImage.Format_RGBA8888)
            ptr = qimg_rgba.constBits(); ptr.setsize(qimg_rgba.byteCount())
            pil_image = Image.frombuffer("RGBA", (qimg_rgba.width(), qimg_rgba.height()), ptr, "raw", "RGBA", 0, 1)
            
            tess_cmd = self.get_tesseract_cmd()
            
            if tess_cmd:
                pytesseract.pytesseract.tesseract_cmd = tess_cmd
                logging.info(f"Using Tesseract at: {tess_cmd}")

                # Устанавливаем TESSDATA_PREFIX для корректного поиска моделей
                tess_dir = os.path.dirname(tess_cmd)
                candidate_dirs = [
                    os.path.join(tess_dir, "tessdata"),  # стандартное расположение в portable-сборке
                    os.path.join(os.path.dirname(tess_dir), "tessdata"),  # если exe лежит в bin/
                ]
                for td in candidate_dirs:
                    if os.path.isdir(td):
                        os.environ["TESSDATA_PREFIX"] = td
                        break
                else:
                    # на всякий случай убираем переменную, чтобы Tesseract искал в своих стандартных местах
                    os.environ.pop("TESSDATA_PREFIX", None)

                # --- Проверяем наличие языковой модели и при необходимости скачиваем ---
                def ensure_lang_model(lang_code, dest_dir):
                    fname = f"{lang_code}.traineddata"
                    target_path = os.path.join(dest_dir, fname)
                    if os.path.exists(target_path):
                        return
                    try:
                        url = f"https://github.com/tesseract-ocr/tessdata/raw/main/{fname}"
                        logging.info(f"Downloading {fname} …")
                        r = requests.get(url, timeout=30, stream=True)
                        r.raise_for_status()
                        with open(target_path + '.tmp', 'wb') as f:
                            shutil.copyfileobj(r.raw, f)
                        os.replace(target_path + '.tmp', target_path)
                        logging.info(f"{fname} downloaded into {dest_dir}")
                    except Exception as dl_err:
                        logging.warning(f"Could not download language model {lang_code}: {dl_err}")

                tessdata_dir = os.environ.get("TESSDATA_PREFIX")
                if tessdata_dir and os.path.isdir(tessdata_dir):
                    required = ["eng", "rus"]
                    for lc in required:
                        ensure_lang_model(lc, tessdata_dir)
            else:
                logging.error("Tesseract executable not found.")
                return "Текст не распознан"
            # Map language codes for Tesseract
            tess_lang = "eng" if language_code == "en" else "rus"
            try:
                logging.info(f"Запуск Tesseract OCR для языка '{tess_lang}'...")
                # Оптимизация скорости: --oem 3 (LSTM only), --psm 6 (single block)
                tess_config = '--oem 3 --psm 6'
                recognized_text = pytesseract.image_to_string(pil_image, lang=tess_lang, config=tess_config)
                logging.info("Tesseract OCR завершил распознавание.")
            except Exception as e:
                logging.error(f"Ошибка Tesseract OCR: {e}")
                recognized_text = ""
            # Обработать результат напрямую
            self.handle_ocr_result(recognized_text)
            return  # Не использовать Windows OCR ниже

        # По умолчанию используем Windows OCR (без PIL)
        bitmap = qimage_to_softwarebitmap(qimage)
        logging.info(f"Используемый язык для OCR: {language_code}")
        
        # Create worker with Tesseract fallback capability
        self.ocr_worker = OCRWorker(bitmap, language_code)
        
        # Pass the QImage for Tesseract fallback if needed
        self.ocr_worker.qimage = qimage
        
        self.ocr_worker.result_ready.connect(self.handle_ocr_result)
        self.ocr_worker.start()

    def handle_ocr_result(self, text):
        if not text and hasattr(self, 'ocr_worker') and hasattr(self.ocr_worker, 'qimage'):
            # If Windows OCR failed, try Tesseract as fallback
            logging.info("Windows OCR returned empty result, attempting Tesseract fallback...")
            try:
                import pytesseract
                from PIL import Image
                
                qimage = self.ocr_worker.qimage
                qimg_rgba = qimage.convertToFormat(QtGui.QImage.Format_RGBA8888)
                ptr = qimg_rgba.constBits()
                ptr.setsize(qimg_rgba.byteCount())
                pil_image = Image.frombuffer("RGBA", (qimg_rgba.width(), qimg_rgba.height()), ptr, "raw", "RGBA", 0, 1)
                
                # Determine Tesseract language
                lang_code = self.lang_combo.currentData() or "ru"
                tess_lang = "eng" if lang_code == "en" else "rus"
                
                # Configure Tesseract path
                tess_cmd = self.get_tesseract_cmd()
                if tess_cmd:
                    pytesseract.pytesseract.tesseract_cmd = tess_cmd
                    
                    # Setup TESSDATA_PREFIX
                    tess_dir = os.path.dirname(tess_cmd)
                    candidate_dirs = [
                        os.path.join(tess_dir, "tessdata"),
                        os.path.join(os.path.dirname(tess_dir), "tessdata"),
                    ]
                    for td in candidate_dirs:
                        if os.path.isdir(td):
                            os.environ["TESSDATA_PREFIX"] = td
                            break
                    
                    # Simplified fallback attempt with speed optimizations
                    tess_config = '--oem 3 --psm 6'
                    text = pytesseract.image_to_string(pil_image, lang=tess_lang, config=tess_config)
                    logging.info(f"Tesseract fallback result length: {len(text)}")
                else:
                    logging.warning("Tesseract not found for fallback.")
            except Exception as e:
                logging.error(f"Tesseract fallback failed: {e}")

        if text:
            if self.mode == "translate":
                from translater import translate_text
                lang_code = self.lang_combo.currentData() or "ru"
                if lang_code == "ru":
                    source_code = "ru"
                    target_code = "en"
                else:
                    source_code = "en"
                    target_code = "ru"
                try:
                    translated_text = translate_text(text, source_code, target_code)
                except Exception as e:
                    QMessageBox.warning(self, "Ошибка перевода", str(e))
                    translated_text = ""
                if translated_text:
                    # Определяем тему и язык из кэша
                    config = get_cached_ocr_config()
                    theme = config.get("theme", "Темная")
                    lang = config.get("interface_language", "ru")
                    auto_copy = config.get("copy_translated_text", True)
                    # Ленивый импорт для избежания циклического импорта
                    from main import show_translation_dialog, save_copy_history
                    show_translation_dialog(self, translated_text, auto_copy=auto_copy, lang=lang, theme=theme)
                    if auto_copy:
                        pyperclip.copy(translated_text)
                        save_copy_history(translated_text)
                    else:
                        # Если пользователь скопировал вручную, обработка уже в диалоге
                        pass
                    # Сохраняем только переводы в историю переводов
                    save_translation_history(translated_text, target_code)
                self.close()
            else:
                try:
                    # Ленивый импорт для избежания циклического импорта
                    from main import save_copy_history
                    pyperclip.copy(text)
                    save_copy_history(text)
                    logging.info(f"Распознанный текст скопирован в буфер обмена: {text}")
                    # НЕ сохраняем обычный текст в историю переводов!
                    self.close()
                except Exception as e:
                    logging.error(f"Ошибка обработки OCR результата: {e}")
        else:
            logging.info("OCR не распознал текст.")
            # Получаем тему из конфига
            config = get_cached_ocr_config()
            theme = config.get("theme", "Светлая")
            lang = config.get("interface_language", "en")
            
            msg = QMessageBox(self)
            msg.setWindowIcon(QtGui.QIcon(resource_path("icons/icon.ico")))
            msg.setIcon(QMessageBox.NoIcon)
            
            if lang == "ru":
                msg.setWindowTitle("Не удалось распознать")
                msg.setText("😔 Текст не распознан")
                msg.setInformativeText(
                    "Попробуйте:\n"
                    "• Выделить область с более крупным текстом\n"
                    "• Убедиться, что текст контрастный\n"
                    "• Выбрать другой OCR движок в настройках"
                )
            else:
                msg.setWindowTitle("Recognition failed")
                msg.setText("😔 Text not recognized")
                msg.setInformativeText(
                    "Try:\n"
                    "• Select an area with larger text\n"
                    "• Make sure the text has good contrast\n"
                    "• Choose a different OCR engine in settings"
                )
            
            msg.setStandardButtons(QMessageBox.Ok)
            
            if theme == "Темная":
                msg.setStyleSheet("""
                    QMessageBox { 
                        background-color: #1a1a2e; 
                    }
                    QMessageBox QLabel { 
                        color: #ffffff; 
                        font-size: 14px; 
                    }
                    QPushButton { 
                        background-color: #7A5FA1; 
                        color: #ffffff; 
                        border: none; 
                        border-radius: 6px;
                        padding: 8px 24px; 
                        min-width: 80px;
                        font-size: 14px;
                    }
                    QPushButton:hover { 
                        background-color: #8B70B2; 
                    }
                """)
            else:
                msg.setStyleSheet("""
                    QMessageBox { 
                        background-color: #ffffff; 
                    }
                    QMessageBox QLabel { 
                        color: #333333; 
                        font-size: 14px; 
                    }
                    QPushButton { 
                        background-color: #7A5FA1; 
                        color: #ffffff; 
                        border: none; 
                        border-radius: 6px;
                        padding: 8px 24px; 
                        min-width: 80px;
                        font-size: 14px;
                    }
                    QPushButton:hover { 
                        background-color: #8B70B2; 
                    }
                """)
            
            msg.exec_()
            self.close()

def prepare_overlay(mode="ocr"):
    try:
        if mode not in _OVERLAY_POOL or _OVERLAY_POOL[mode] is None:
            _OVERLAY_POOL[mode] = ScreenCaptureOverlay(mode, defer_show=True)
    except Exception:
        _OVERLAY_POOL[mode] = None

_ACTIVE_OVERLAYS = {}

def get_or_show_overlay(mode="ocr"):
    # Close existing active overlay of the same mode if any
    if _ACTIVE_OVERLAYS.get(mode):
        try:
            _ACTIVE_OVERLAYS[mode].close()
        except Exception:
            pass
            
    ov = _OVERLAY_POOL.get(mode)
    if ov is None:
        ov = ScreenCaptureOverlay(mode, defer_show=False)
    else:
        ov.show_overlay()
    
    # Keep reference to prevent garbage collection
    _ACTIVE_OVERLAYS[mode] = ov
    _OVERLAY_POOL[mode] = None

def run_screen_capture(mode="ocr"):
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        logging.info("Запуск OCR приложения...")
        get_or_show_overlay(mode)
        app.exec_()
    else:
        get_or_show_overlay(mode)

def warm_up():
    # Pre-initialize OCR engines for common languages to reduce first-use latency
    try:
        _get_windows_ocr_engine("ru-RU")
        _get_windows_ocr_engine("en-US")
    except Exception:
        pass
    # Pre-initialize RapidOCR (optional)
    try:
        _get_rapidocr_engine()
    except Exception:
        pass

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "translate":
        run_screen_capture("translate")
    else:
        run_screen_capture()
