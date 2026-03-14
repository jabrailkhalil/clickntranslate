import sys
import asyncio
import os
import json
import logging
from datetime import datetime
import shutil

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
import pyperclip

# Настройка логирования в файл для диагностики
def get_log_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(sys.executable), "ocr_debug.log")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_debug.log")

_debug_log_path = get_log_path()

def debug_log(msg):
    """Debug logging disabled for production."""
    pass  # Логирование отключено для production

# Инициализация (логирование отключено)

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

# Ленивый импорт для избежания циклического импорта
# from main import save_copy_history, show_translation_dialog


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_portable_dir():
    """Directory next to the exe for portable data."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_data_file(filename):
    data_dir = os.path.join(get_portable_dir(), "data")
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

def _save_translation_history_sync(original_text, translated_text, language):
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
                    "original": original_text,
                    "translated": translated_text
                })
                if len(history) > 500:
                    history = history[-500:]
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
                    "original": original_text,
                    "translated": translated_text
                })
                if len(history) > 500:
                    history = history[-500:]
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
            "original": original_text,
            "translated": translated_text
        })
        if len(history) > 500:
            history = history[-500:]
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

def save_translation_history(original_text, translated_text, language):
    """Асинхронно сохранить перевод в историю (не блокирует UI)."""
    import threading
    threading.Thread(target=_save_translation_history_sync, args=(original_text, translated_text, language), daemon=True).start()

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
            # Проверяем lines через try/except (hasattr вызывает ошибку импорта collections)
            try:
                lines = result.lines
                line_count = len(lines) if lines else 0
                debug_log(f"Lines count: {line_count}")
                if line_count > 0:
                    for i, line in enumerate(lines):
                        debug_log(f"Line {i}: {line.text}")
                return result
            except AttributeError:
                debug_log("ERROR: Result has no 'lines' attribute")
                return None
            except Exception as e:
                debug_log(f"ERROR accessing lines: {e}")
                return result  # Возвращаем result даже если не можем получить lines
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

# Cache for universal OCR engine
_UNIVERSAL_OCR_ENGINE = None

def _get_universal_ocr_engine():
    """Получить универсальный Windows OCR движок. Используем en-US как базовый (лучше всего с цифрами)."""
    global _UNIVERSAL_OCR_ENGINE, _WINRT_AVAILABLE
    
    debug_log("_get_universal_ocr_engine called")
    
    if _UNIVERSAL_OCR_ENGINE is not None:
        debug_log("Returning cached universal OCR engine")
        return _UNIVERSAL_OCR_ENGINE
    
    if not _WINRT_AVAILABLE:
        debug_log(f"FAILED: WinRT not available. Error was: {_WINRT_ERROR}")
        logging.error("WinRT modules are not available")
        return None
    
    try:
        OcrEngine = winrt_ocr.OcrEngine
        Language = winrt_glob.Language
        
        # Для универсального режима используем en-US (лучше всего с цифрами и латиницей)
        debug_log("Using en-US for universal mode (best for numbers)...")
        try:
            if OcrEngine.is_language_supported(Language("en-US")):
                engine = OcrEngine.try_create_from_language(Language("en-US"))
                if engine:
                    _UNIVERSAL_OCR_ENGINE = engine
                    debug_log("SUCCESS: Using en-US as universal engine")
                    return engine
        except Exception as e:
            debug_log(f"en-US failed: {e}")
        
        # Fallback: любой доступный язык
        debug_log("Falling back to first available language...")
        available_langs = OcrEngine.get_available_recognizer_languages()
        if available_langs.size > 0:
            first_lang = available_langs.get_at(0)
            debug_log(f"Using fallback language: {first_lang.language_tag}")
            engine = OcrEngine.try_create_from_language(first_lang)
            if engine:
                _UNIVERSAL_OCR_ENGINE = engine
                return engine
        
        debug_log("ERROR: No OCR languages available")
        return None
    except Exception as e:
        debug_log(f"EXCEPTION in _get_universal_ocr_engine: {e}")
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
    def __init__(self, bitmap, language_code, parent=None, use_universal=False):
        super().__init__(parent)
        self.bitmap = bitmap
        self.language_code = language_code
        self.use_universal = use_universal

    def run(self):
        debug_log(f"OCRWorker.run() started")
        debug_log(f"self.bitmap = {self.bitmap}")
        debug_log(f"self.language_code = {self.language_code}")
        debug_log(f"self.use_universal = {self.use_universal}")
        try:
            # Выбираем engine в зависимости от режима
            if self.use_universal:
                debug_log("Using universal OCR engine (from user profile languages)")
                engine = _get_universal_ocr_engine()
            else:
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
            if recognized:
                try:
                    # Проверяем lines через try/except (hasattr вызывает ошибку импорта collections)
                    lines = recognized.lines
                    if lines:
                        # Собираем текст из слов с правильными пробелами
                        lines_text = []
                        for line in lines:
                            try:
                                # Используем words для правильных пробелов между словами
                                words = list(line.words)
                                if words:
                                    line_text = " ".join(word.text for word in words)
                                else:
                                    line_text = line.text
                            except:
                                line_text = line.text
                            lines_text.append(line_text)
                        recognized_text = "\n".join(lines_text)
                        debug_log(f"recognized_text = '{recognized_text[:100]}...' (length={len(recognized_text)})")
                        logging.info(f"Windows OCR recognized {len(recognized_text)} chars successfully")
                    else:
                        debug_log("recognized.lines is empty")
                        logging.warning("Windows OCR returned empty result")
                except AttributeError:
                    debug_log("ERROR: recognized has no 'lines' attribute")
                except Exception as e:
                    debug_log(f"ERROR accessing recognized.lines: {e}")
            else:
                debug_log("No recognized text (recognized is None)")
                logging.warning("Windows OCR returned None")

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
        # Загрузка последнего выбранного языка из конфигурации
        config = get_cached_ocr_config()
        self.current_language = config.get("last_ocr_language", "ru")
        # Removed Qt.Tool, added WindowStaysOnTopHint and FramelessWindowHint
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setCursor(QtCore.Qt.CrossCursor)
        # Используем primaryScreen для grabWindow(0) — WId=0 означает весь виртуальный десктоп
        self.screen = QApplication.primaryScreen()
        self._grab_screen = self.screen  # сохраняем для capture
        
        if not defer_show:
            self.show_overlay()
            
        logging.info("Screen capture overlay initialized.")
        
        # Используем текущий язык (уже загружен из конфига в __init__)
        self.lang_combo = QtWidgets.QComboBox(self)
        
        # В режиме copy добавляем опцию "Универсальный" первой (эмодзи планеты)
        if self.mode == "copy":
            self.lang_combo.addItem("🌐  AUTO", "universal")
            self.lang_combo.addItem(QtGui.QIcon(resource_path("icons/Russian_flag.png")), "RU", "ru")
            self.lang_combo.addItem(QtGui.QIcon(resource_path("icons/American_flag.png")), "EN", "en")
        else:
            # В режиме translate показываем направление перевода
            self.lang_combo.addItem(QtGui.QIcon(resource_path("icons/Russian_flag.png")), "RU → EN", "ru")
            self.lang_combo.addItem(QtGui.QIcon(resource_path("icons/American_flag.png")), "EN → RU", "en")
        
        # Устанавливаем индекс на основе self.current_language (сохраненного)
        if self.mode == "copy":
            # В режиме copy есть AUTO, RU, EN (индексы 0, 1, 2)
            if self.current_language == "universal":
                default_index = 0  # AUTO
            elif self.current_language == "ru":
                default_index = 1  # RU
            elif self.current_language == "en":
                default_index = 2  # EN
            else:
                default_index = 0  # По умолчанию AUTO
        else:
            # В режиме translate только RU, EN (индексы 0, 1)
            default_index = 0 if self.current_language == "ru" else 1
        self.lang_combo.setCurrentIndex(default_index)
        
        # Photoshop-style дизайн: темный, профессиональный, с эффектами
        self.lang_combo.setIconSize(QtCore.QSize(40, 40))
        self.lang_combo.setStyleSheet("""
            QComboBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(60, 60, 60, 240),
                    stop:0.5 rgba(45, 45, 45, 245),
                    stop:1 rgba(35, 35, 35, 250));
                color: #e8e8e8;
                border: 1px solid rgba(80, 80, 80, 200);
                border-top: 1px solid rgba(100, 100, 100, 150);
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 16px;
                font-weight: 600;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-width: 110px;
            }
            QComboBox:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(75, 75, 75, 245),
                    stop:0.5 rgba(55, 55, 55, 250),
                    stop:1 rgba(45, 45, 45, 255));
                border: 1px solid rgba(100, 100, 100, 220);
                border-top: 1px solid rgba(130, 130, 130, 180);
            }
            QComboBox:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(40, 40, 40, 250),
                    stop:1 rgba(55, 55, 55, 255));
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
                subcontrol-origin: padding;
                subcontrol-position: right center;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(40, 40, 40, 252);
                color: #e8e8e8;
                border: 1px solid rgba(80, 80, 80, 200);
                border-radius: 6px;
                padding: 6px;
                selection-background-color: rgba(80, 130, 200, 180);
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 10px 14px;
                border-radius: 4px;
                margin: 2px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: rgba(70, 70, 70, 200);
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: rgba(80, 130, 200, 180);
            }
        """)
        # Размер зависит от режима (translate имеет более длинный текст)
        combo_width = 180 if self.mode == "translate" else 160
        self.lang_combo.setFixedSize(combo_width, 56)
        self.lang_combo.move((self.width() - self.lang_combo.width()) // 2, 20)
        # Показываем комбобокс (в режиме copy есть опция AUTO)
        self.lang_combo.setVisible(True if not defer_show else False)
        
        # Сохраняем язык при изменении
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)

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
        # Сначала убираем себя из активных оверлеев
        try:
            for active_mode, overlay in list(_ACTIVE_OVERLAYS.items()):
                if overlay is self:
                    _ACTIVE_OVERLAYS[active_mode] = None
        except Exception:
            pass
        super().closeEvent(event)
        # Подготавливаем новый оверлей ПОСЛЕ закрытия текущего (отложенно)
        mode = self.mode
        QtCore.QTimer.singleShot(100, lambda: _safe_prepare_overlay(mode))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Проверка настройки "не затемнять экран"
        config = get_cached_ocr_config()
        no_dimming = config.get("no_screen_dimming", False)
        
        # Если не требуется затемнение, рисуем минимальный невидимый фон для перехвата мыши
        if not no_dimming:
            painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 150))
        else:
            # Минимальное затемнение (практически невидимое) для перехвата событий мыши
            # Без этого окно полностью прозрачно и клики проваливаются сквозь него
            painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 5))
        
        if self.start_point and self.end_point:
            rect = QtCore.QRect(self.start_point, self.end_point).normalized()
            
            # Очищаем внутреннюю область (если было затемнение)
            if not no_dimming:
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_Clear)
                painter.fillRect(rect, QtGui.QColor(0, 0, 0, 0))
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            else:
                # В режиме без затемнения добавляем легкий полупрозрачный белый фон
                # чтобы область выделения была видна
                painter.fillRect(rect, QtGui.QColor(255, 255, 255, 30))
            
            # Photoshop-style рамка: голубая с эффектом свечения
            # Внешнее свечение (glow effect)
            glow_pen = QtGui.QPen(QtGui.QColor(80, 160, 255, 60), 5)
            glow_pen.setStyle(QtCore.Qt.SolidLine)
            painter.setPen(glow_pen)
            painter.drawRect(rect.adjusted(-2, -2, 2, 2))
            
            # Основная рамка (яркая голубая, как в Photoshop)
            main_pen = QtGui.QPen(QtGui.QColor(80, 160, 255, 255), 1)
            main_pen.setStyle(QtCore.Qt.SolidLine)
            painter.setPen(main_pen)
            painter.drawRect(rect)
            
            # Внутренняя светлая рамка для контраста
            inner_pen = QtGui.QPen(QtGui.QColor(200, 230, 255, 100), 1)
            inner_pen.setStyle(QtCore.Qt.SolidLine)
            painter.setPen(inner_pen)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            
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
            # Отклоняем слишком маленькие выделения (случайные клики)
            if rect.width() < 5 or rect.height() < 5:
                logging.info(f"Selection too small ({rect.width()}x{rect.height()}), ignoring")
                self.start_point = None
                self.end_point = None
                self.update()
                return
            self.last_rect = rect
            logging.info(f"Завершено выделение области: {rect}")
            self.capture_and_copy(rect)

    def on_language_changed(self, index):
        """Сохраняет выбранный язык в конфиг при изменении"""
        language_code = self.lang_combo.currentData()
        if language_code:
            self.current_language = language_code
            config_path = get_data_file("config.json")
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                config["last_ocr_language"] = language_code
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=4)
                logging.info(f"Saved OCR language: {language_code}")
            except Exception as e:
                logging.warning(f"Failed to save OCR language: {e}")

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

    # Сохраняем ссылку на данные изображения, чтобы QImage не потерял буфер
    _ocr_image_data = None

    def capture_and_copy(self, rect):
        # rect — в локальных координатах overlay-виджета
        global_top_left = self.mapToGlobal(rect.topLeft())
        global_bottom_right = self.mapToGlobal(rect.bottomRight())
        global_rect = QtCore.QRect(global_top_left, global_bottom_right)

        logging.info(f"Selected local rect: {rect}")
        logging.info(f"Mapped global rect: {global_rect}")

        # Находим экран, содержащий центр выделенной области
        target_screen = self.screen
        center = global_rect.center()
        dpr = 1.0
        for scr in QApplication.screens():
            if scr.geometry().contains(center):
                target_screen = scr
                dpr = scr.devicePixelRatio()
                break

        # DPI-aware захват: grabWindow использует физические пиксели
        screenshot = target_screen.grabWindow(
            0, global_rect.x(), global_rect.y(),
            global_rect.width(), global_rect.height()
        )

        if screenshot.isNull():
            logging.error("Failed to grab screenshot (result is null)")
            return

        qimage = screenshot.toImage()
        orig_w, orig_h = qimage.width(), qimage.height()
        logging.info(f"Captured {orig_w}x{orig_h} (DPR={dpr})")

        # ===== PIL-обработка для улучшения качества OCR =====
        from PIL import Image, ImageEnhance, ImageOps, ImageFilter, ImageStat

        # QImage → PIL (через копирование данных для безопасности)
        qimg_rgba = qimage.convertToFormat(QtGui.QImage.Format_RGBA8888)
        ptr = qimg_rgba.constBits()
        ptr.setsize(qimg_rgba.byteCount())
        pil_image = Image.frombuffer(
            "RGBA", (qimg_rgba.width(), qimg_rgba.height()),
            bytes(ptr), "raw", "RGBA", 0, 1
        )

        # --- 1. Определяем тёмный/светлый фон ---
        gray = pil_image.convert('L')
        stat = ImageStat.Stat(gray)
        mean_brightness = stat.mean[0]
        is_dark_bg = mean_brightness < 128

        # --- 2. Если тёмный фон — инвертируем для OCR (чёрный текст на белом) ---
        if is_dark_bg:
            pil_image = ImageOps.invert(pil_image.convert('RGB')).convert('RGBA')
            logging.info(f"Dark background detected (mean={mean_brightness:.0f}), inverted")

        # --- 3. Конвертация в grayscale ---
        pil_image = pil_image.convert('L')

        # --- 4. Умное масштабирование на основе высоты изображения ---
        # Windows OCR лучше всего работает при высоте текста ~35-50px
        # Используем высоту выделения как основной ориентир
        height = pil_image.height
        TARGET_TEXT_HEIGHT = 48.0

        if height < 20:
            scale_factor = 6.0
        elif height < 40:
            scale_factor = 4.0
        elif height < 80:
            scale_factor = 3.0
        elif height < 150:
            scale_factor = 2.0
        elif height < 300:
            scale_factor = 1.5
        else:
            scale_factor = 1.0

        if scale_factor > 1.0:
            new_w = int(pil_image.width * scale_factor)
            new_h = int(pil_image.height * scale_factor)
            pil_image = pil_image.resize((new_w, new_h), Image.LANCZOS)
            logging.info(f"Scaled {scale_factor:.1f}x → {new_w}x{new_h}")

        # --- 5. Умное улучшение контраста (адаптивное) ---
        stat = ImageStat.Stat(pil_image)
        stddev = stat.stddev[0]  # стандартное отклонение яркости

        if stddev < 30:
            # Низкоконтрастное изображение — нужно больше усиления
            contrast_factor = 2.5
        elif stddev < 60:
            contrast_factor = 1.8
        else:
            contrast_factor = 1.3  # Уже контрастное — не портим

        enhancer = ImageEnhance.Contrast(pil_image)
        pil_image = enhancer.enhance(contrast_factor)

        # --- 6. Лёгкое повышение резкости (не агрессивное) ---
        enhancer = ImageEnhance.Sharpness(pil_image)
        pil_image = enhancer.enhance(1.5)

        # --- 7. Бинаризация Otsu для маленьких выделений ---
        if height < 80:
            try:
                import numpy as np
                arr = np.array(pil_image)
                # Otsu's threshold
                hist, _ = np.histogram(arr.ravel(), bins=256, range=(0, 256))
                total = arr.size
                sum_total = np.dot(np.arange(256), hist)
                sum_bg, weight_bg, max_var, threshold = 0.0, 0, 0.0, 128
                for t in range(256):
                    weight_bg += hist[t]
                    if weight_bg == 0:
                        continue
                    weight_fg = total - weight_bg
                    if weight_fg == 0:
                        break
                    sum_bg += t * hist[t]
                    mean_bg = sum_bg / weight_bg
                    mean_fg = (sum_total - sum_bg) / weight_fg
                    var_between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
                    if var_between > max_var:
                        max_var = var_between
                        threshold = t
                pil_image = pil_image.point(lambda x: 255 if x > threshold else 0, 'L')
                logging.info(f"Otsu binarization: threshold={threshold}")
            except ImportError:
                # numpy не доступен — простая бинаризация
                pil_image = pil_image.point(lambda x: 255 if x > 128 else 0, 'L')

        # --- 8. Добавляем поля вокруг текста (помогает OCR определить границы) ---
        # Цвет полей совпадает с доминирующим фоном (после всех преобразований)
        stat = ImageStat.Stat(pil_image)
        border_fill = 255 if stat.mean[0] > 128 else 0
        border_size = max(16, int(pil_image.height * 0.15))
        pil_image = ImageOps.expand(pil_image, border=border_size, fill=border_fill)

        # --- 9. Конвертируем обратно в QImage (БЕЗОПАСНО — копируем данные) ---
        self._ocr_image_data = pil_image.tobytes()
        qimage = QtGui.QImage(
            self._ocr_image_data, pil_image.width, pil_image.height,
            pil_image.width, QtGui.QImage.Format_Grayscale8
        )

        logging.info(f"Final preprocessed: {pil_image.width}x{pil_image.height} (border_fill={border_fill})")
        
        language_code = self.lang_combo.currentData() or "ru"
        self.current_language = language_code
        
        # Сохраняем выбранный язык в конфигурации
        config = get_cached_ocr_config()
        if config.get("last_ocr_language") != language_code:
            config_path = get_data_file("config.json")
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    full_config = json.load(f)
                full_config["last_ocr_language"] = language_code
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(full_config, f, ensure_ascii=False, indent=4)
            except Exception:
                pass

        # Determine which OCR engine to use
        ocr_engine_type = self.get_ocr_engine().lower()
        logging.info(f"Using OCR engine: {ocr_engine_type.upper()}")

        if ocr_engine_type == "tesseract":
            import pytesseract
            import requests
            # pil_image уже подготовлен выше (grayscale, масштабированный, с бордерами)
            # Конвертируем в формат, понятный Tesseract
            tess_pil = pil_image.convert('L') if pil_image.mode != 'L' else pil_image

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
                logging.info(f"🔄 Running Tesseract OCR for language '{tess_lang}'...")
                # Оптимизация скорости: --oem 3 (LSTM only), --psm 6 (single block)
                tess_config = '--oem 3 --psm 6'
                recognized_text = pytesseract.image_to_string(tess_pil, lang=tess_lang, config=tess_config)
                if recognized_text.strip():
                    logging.info(f"✅ Tesseract recognized {len(recognized_text)} chars successfully")
                else:
                    logging.warning("Tesseract returned empty result")
            except Exception as e:
                logging.error(f"❌ Tesseract error: {e}")
                recognized_text = ""
            # Обработать результат напрямую
            self.handle_ocr_result(recognized_text)
            return  # Не использовать Windows OCR ниже

        # По умолчанию используем Windows OCR (без PIL)
        # Используем универсальный OCR если выбрано "universal" (AUTO)
        use_universal = (language_code == "universal")
        if use_universal:
            logging.info("🔄 Running Windows OCR in UNIVERSAL mode (auto-detect language)")
        else:
            logging.info(f"🔄 Running Windows OCR for language: {language_code.upper()}")
        
        bitmap = qimage_to_softwarebitmap(qimage)
        
        # Create worker with Tesseract fallback capability
        self.ocr_worker = OCRWorker(bitmap, language_code, use_universal=use_universal)
        
        # Pass the QImage for Tesseract fallback if needed
        self.ocr_worker.qimage = qimage
        
        self.ocr_worker.result_ready.connect(self.handle_ocr_result)
        self.ocr_worker.start()

    def handle_ocr_result(self, text):
        try:
            self._handle_ocr_result_inner(text)
        except Exception as e:
            logging.error(f"Critical error in handle_ocr_result: {e}")
            # Гарантированно закрываем оверлей при любом краше
            try:
                self.close()
            except Exception:
                pass

    def _handle_ocr_result_inner(self, text):
        if not text and hasattr(self, 'ocr_worker') and hasattr(self.ocr_worker, 'qimage'):
            # If Windows OCR failed, try Tesseract as fallback
            logging.info("Windows OCR returned empty result, attempting Tesseract fallback...")
            try:
                import pytesseract
                from PIL import Image

                # qimage уже предобработан (grayscale, масштаб, бордеры)
                qimage = self.ocr_worker.qimage
                w, h = qimage.width(), qimage.height()
                bpl = qimage.bytesPerLine()

                # Безопасная конвертация QImage → PIL
                if qimage.format() == QtGui.QImage.Format_Grayscale8:
                    ptr = qimage.constBits()
                    ptr.setsize(bpl * h)
                    pil_image = Image.frombytes('L', (w, h), bytes(ptr), 'raw', 'L', bpl)
                else:
                    qimg_rgba = qimage.convertToFormat(QtGui.QImage.Format_RGBA8888)
                    ptr = qimg_rgba.constBits()
                    ptr.setsize(qimg_rgba.byteCount())
                    pil_image = Image.frombuffer("RGBA", (w, h), bytes(ptr), "raw", "RGBA", 0, 1)
                    pil_image = pil_image.convert('L')

                lang_code = self.lang_combo.currentData() or "ru"
                tess_lang = "eng" if lang_code == "en" else "rus"

                tess_cmd = self.get_tesseract_cmd()
                if tess_cmd:
                    pytesseract.pytesseract.tesseract_cmd = tess_cmd
                    tess_dir = os.path.dirname(tess_cmd)
                    for td in [os.path.join(tess_dir, "tessdata"),
                               os.path.join(os.path.dirname(tess_dir), "tessdata")]:
                        if os.path.isdir(td):
                            os.environ["TESSDATA_PREFIX"] = td
                            break

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
                logging.info(f"🔄 Translating from {source_code.upper()} to {target_code.upper()}...")
                try:
                    translated_text = translate_text(text, source_code, target_code)
                    if translated_text:
                        logging.info(f"✅ Translation completed successfully ({len(translated_text)} chars)")
                    else:
                        logging.warning("Translation returned empty result")
                except Exception as e:
                    logging.error(f"❌ Translation error: {e}")
                    self.hide()
                    QMessageBox.warning(None, "Ошибка перевода", str(e))
                    translated_text = ""
                if translated_text:
                    # Определяем тему и язык из кэша
                    config = get_cached_ocr_config()
                    theme = config.get("theme", "Темная")
                    lang = config.get("interface_language", "ru")
                    auto_copy = config.get("copy_translated_text", True)
                    # Ленивый импорт для избежания циклического импорта
                    from main import show_translation_dialog, save_copy_history

                    # Скрываем оверлей ПЕРЕД показом диалога, чтобы:
                    # 1) Пользователь видел исходный контент за диалогом
                    # 2) Не было z-order проблем (диалог поверх translucent overlay)
                    self.hide()

                    # Используем главное окно приложения как parent вместо overlay
                    dialog_parent = None
                    app = QApplication.instance()
                    if app:
                        for widget in app.topLevelWidgets():
                            if hasattr(widget, 'show_window_from_tray') and widget.windowTitle() == "Click'n'Translate":
                                dialog_parent = widget
                                break

                    show_translation_dialog(dialog_parent, translated_text, auto_copy=auto_copy, lang=lang, theme=theme)
                    if auto_copy:
                        pyperclip.copy(translated_text)
                        save_copy_history(translated_text)
                    # Сохраняем переводы в историю (исходный текст и перевод)
                    save_translation_history(text, translated_text, target_code)
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
            # Скрываем оверлей перед показом диалога ошибки
            self.hide()
            # Получаем тему из конфига
            config = get_cached_ocr_config()
            theme = config.get("theme", "Светлая")
            lang = config.get("interface_language", "en")

            msg = QMessageBox()
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

def _safe_prepare_overlay(mode="ocr"):
    """Безопасная подготовка оверлея — вызывается отложенно после closeEvent."""
    try:
        prepare_overlay(mode)
    except Exception:
        pass

_ACTIVE_OVERLAYS = {}

def _close_active_overlays(except_mode=None):
    """Закрывает все активные оверлеи, кроме указанного режима."""
    for active_mode, overlay in list(_ACTIVE_OVERLAYS.items()):
        if active_mode == except_mode or not overlay:
            continue
        try:
            if overlay.isVisible():
                overlay.close()
            else:
                overlay.deleteLater()
        except Exception:
            pass
        finally:
            _ACTIVE_OVERLAYS[active_mode] = None

def get_or_show_overlay(mode="ocr"):
    # Не допускаем одновременное существование панелей разных режимов
    _close_active_overlays(except_mode=mode)

    # Если оверлей уже активен для этого режима - закрываем его (toggle behavior)
    if _ACTIVE_OVERLAYS.get(mode):
        try:
            existing = _ACTIVE_OVERLAYS[mode]
            if existing and existing.isVisible():
                existing.close()
                _ACTIVE_OVERLAYS[mode] = None
                return  # Закрыли, больше ничего не делаем
            _ACTIVE_OVERLAYS[mode] = None
        except Exception:
            pass
    
    # Создаем или показываем оверлей
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


# ============================================================
# Fullscreen Translate — OCR all text on screen and overlay translations
# ============================================================

class FullScreenOCRWorker(QtCore.QThread):
    """OCR worker that returns text lines with bounding box positions."""
    result_ready = QtCore.pyqtSignal(list)  # list of (x, y, w, h, text)

    def __init__(self, bitmap, language_code="ru", parent=None):
        super().__init__(parent)
        self.bitmap = bitmap
        self.language_code = language_code

    def run(self):
        lines_data = []
        try:
            if not _WINRT_AVAILABLE:
                logging.error("FullScreenOCR: WinRT not available")
                self.result_ready.emit([])
                return

            lang_tag = {"en": "en-US", "ru": "ru-RU"}.get(self.language_code, "en-US")
            logging.info(f"FullScreenOCR: using lang_tag={lang_tag}")
            engine = _get_windows_ocr_engine(lang_tag)
            if engine is None:
                logging.error("FullScreenOCR: engine is None")
                self.result_ready.emit([])
                return

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                recognized = loop.run_until_complete(run_ocr_with_engine(self.bitmap, engine))
            finally:
                loop.close()

            logging.info(f"FullScreenOCR: recognized={recognized}")
            if recognized:
                for line in recognized.lines:
                    words = list(line.words)
                    if not words:
                        continue
                    min_x = min(w.bounding_rect.x for w in words)
                    min_y = min(w.bounding_rect.y for w in words)
                    max_x = max(w.bounding_rect.x + w.bounding_rect.width for w in words)
                    max_y = max(w.bounding_rect.y + w.bounding_rect.height for w in words)
                    text = " ".join(w.text for w in words)
                    if text.strip():
                        lines_data.append((min_x, min_y, max_x - min_x, max_y - min_y, text))
            logging.info(f"FullScreenOCR: found {len(lines_data)} text blocks")
        except Exception as e:
            logging.error(f"FullScreenOCRWorker error: {e}")
            import traceback
            traceback.print_exc()

        self.result_ready.emit(lines_data)


class FullScreenTranslateOverlay(QWidget):
    """Overlay that translates all visible text on screen and shows translations at original positions."""

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon(resource_path("icons/icon.ico")))
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setCursor(QtCore.Qt.ArrowCursor)

        self.translated_blocks = []  # list of (QRectF, original, translated)
        self.loading = False
        self.error_message = None
        self._lines_data = []
        self.ocr_worker = None
        self._is_dragging = False
        self._drag_offset = QtCore.QPoint()

        # Read config
        config = get_cached_ocr_config()
        saved_src = config.get("fullscreen_translate_from", "en")

        # Capture screenshot from the screen where cursor is
        cursor_pos = QtGui.QCursor.pos()
        target_screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        geo = target_screen.geometry()

        self.screenshot = target_screen.grabWindow(0, geo.x(), geo.y(), geo.width(), geo.height())
        self.setGeometry(geo)

        # --- Комбо-бокс выбора направления перевода (как в обычном overlay) ---
        self.lang_combo = QtWidgets.QComboBox(self)
        self.lang_combo.addItem(QtGui.QIcon(resource_path("icons/American_flag.png")), "EN \u2192 RU", "en")
        self.lang_combo.addItem(QtGui.QIcon(resource_path("icons/Russian_flag.png")), "RU \u2192 EN", "ru")
        # Восстанавливаем последний выбор
        default_idx = 0 if saved_src == "en" else 1
        self.lang_combo.setCurrentIndex(default_idx)

        self.lang_combo.setIconSize(QtCore.QSize(32, 32))
        self.lang_combo.setStyleSheet("""
            QComboBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(60, 60, 60, 240),
                    stop:0.5 rgba(45, 45, 45, 245),
                    stop:1 rgba(35, 35, 35, 250));
                color: #e8e8e8;
                border: 1px solid rgba(80, 80, 80, 200);
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 15px;
                font-weight: 600;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QComboBox:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(75, 75, 75, 245),
                    stop:1 rgba(45, 45, 45, 255));
                border: 1px solid rgba(100, 100, 100, 220);
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow { image: none; width: 0; }
            QComboBox QAbstractItemView {
                background-color: rgba(40, 40, 40, 252);
                color: #e8e8e8;
                border: 1px solid rgba(80, 80, 80, 200);
                border-radius: 6px;
                padding: 4px;
                selection-background-color: rgba(80, 130, 200, 180);
                outline: none;
            }
            QComboBox QAbstractItemView::item { padding: 8px 12px; border-radius: 4px; margin: 2px; }
            QComboBox QAbstractItemView::item:hover { background-color: rgba(70, 70, 70, 200); }
        """)
        self.lang_combo.setFixedSize(170, 48)

        # --- Кнопка запуска перевода ---
        config_lang = config.get("interface_language", "en")
        go_text = "Перевести" if config_lang == "ru" else "Translate"
        self.go_button = QtWidgets.QPushButton(go_text, self)
        self.go_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(90, 70, 160, 240),
                    stop:1 rgba(60, 45, 120, 250));
                color: #ffffff;
                border: 1px solid rgba(120, 100, 180, 200);
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 15px;
                font-weight: 700;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(110, 90, 180, 250),
                    stop:1 rgba(80, 60, 140, 255));
            }
            QPushButton:pressed {
                background: rgba(50, 35, 100, 250);
            }
        """)
        self.go_button.setFixedSize(140, 48)
        self.go_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.go_button.clicked.connect(self._on_go_clicked)

        # Позиционируем элементы по центру сверху
        total_w = self.lang_combo.width() + 12 + self.go_button.width()
        start_x = (geo.width() - total_w) // 2
        top_y = 30
        self.lang_combo.move(start_x, top_y)
        self.go_button.move(start_x + self.lang_combo.width() + 12, top_y)

        logging.info(f"FullScreenOverlay: screen geo={geo}, screenshot size={self.screenshot.width()}x{self.screenshot.height()}")

        self.show()
        self.raise_()
        self.activateWindow()

    def _on_go_clicked(self):
        """Запуск OCR + перевода по нажатию кнопки."""
        lang_data = self.lang_combo.currentData()  # "en" или "ru"
        self.src_lang = lang_data
        self.tgt_lang = "ru" if lang_data == "en" else "en"
        self.ocr_language = self.src_lang

        # Сохраняем выбор в конфиг
        config_path = get_data_file("config.json")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            cfg["fullscreen_translate_from"] = self.src_lang
            cfg["fullscreen_translate_to"] = self.tgt_lang
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

        # Скрываем UI, показываем загрузку
        self.lang_combo.hide()
        self.go_button.hide()
        self.loading = True
        self.translated_blocks.clear()
        self.error_message = None
        self.update()

        logging.info(f"FullScreenOverlay: starting OCR ({self.src_lang}->{self.tgt_lang})")
        self._start_ocr()

    def _start_ocr(self):
        qimage = self.screenshot.toImage()
        bitmap = qimage_to_softwarebitmap(qimage)
        if bitmap is None:
            self.loading = False
            self.error_message = "OCR initialization failed"
            self.update()
            return

        self.ocr_worker = FullScreenOCRWorker(bitmap, self.ocr_language)
        self.ocr_worker.result_ready.connect(self._on_ocr_complete)
        self.ocr_worker.start()

    def _on_ocr_complete(self, lines_data):
        if not lines_data:
            self.loading = False
            config = get_cached_ocr_config()
            lang = config.get("interface_language", "en")
            self.error_message = "Текст на экране не распознан" if lang == "ru" else "No text recognized on screen"
            self.update()
            # Auto-close after 2 seconds
            QtCore.QTimer.singleShot(2000, self.close)
            return

        self._lines_data = lines_data
        import threading
        threading.Thread(target=self._translate_all, daemon=True).start()

    def _translate_all(self):
        try:
            from translater import translate_text

            src, tgt = self.src_lang, self.tgt_lang
            logging.info(f"FullScreenOverlay: translating {len(self._lines_data)} blocks ({src}->{tgt})")

            # Batch translate: join all lines, translate once, split back
            all_texts = [item[4] for item in self._lines_data]
            joined = "\n".join(all_texts)
            translated = translate_text(joined, src, tgt)

            if translated:
                parts = translated.split("\n")
                for i, (x, y, w, h, orig) in enumerate(self._lines_data):
                    tr = parts[i].strip() if i < len(parts) else orig
                    self.translated_blocks.append(
                        (QtCore.QRectF(x, y, w, h), orig, tr)
                    )
            else:
                config = get_cached_ocr_config()
                lang = config.get("interface_language", "en")
                self.error_message = "Ошибка перевода" if lang == "ru" else "Translation failed"
        except Exception as e:
            self.error_message = str(e)

        self.loading = False
        QtCore.QMetaObject.invokeMethod(self, "_refresh", QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot()
    def _refresh(self):
        self.update()

    # ---- painting --------------------------------------------------

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)

        # Screenshot as background
        painter.drawPixmap(0, 0, self.screenshot)
        # Slight dimming
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 100))

        if self.loading:
            self._paint_loading(painter)
        elif self.error_message:
            self._paint_center_msg(painter, self.error_message, QtGui.QColor(80, 20, 20, 230))
        elif self.translated_blocks:
            for rect_f, _orig, translated in self.translated_blocks:
                self._paint_block(painter, rect_f, translated)
            self._paint_hint(painter)
        # else: начальный экран — комбо-бокс и кнопка видны поверх скриншота

        painter.end()

    def _paint_loading(self, painter):
        config = get_cached_ocr_config()
        lang = config.get("interface_language", "en")
        text = "Перевод экрана..." if lang == "ru" else "Translating screen..."
        self._paint_center_msg(painter, text, QtGui.QColor(30, 20, 60, 230))

    def _paint_center_msg(self, painter, text, bg_color):
        cx, cy = self.width() // 2, self.height() // 2
        font = QtGui.QFont("Segoe UI", 15, QtGui.QFont.Bold)
        painter.setFont(font)
        fm = QtGui.QFontMetrics(font)
        tw = fm.horizontalAdvance(text) + 40
        box = QtCore.QRectF(cx - tw / 2, cy - 25, tw, 50)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(box, 12, 12)
        painter.setPen(QtGui.QColor(220, 200, 255))
        painter.drawText(box, QtCore.Qt.AlignCenter, text)

    def _paint_block(self, painter, rect_f, text):
        pad = 3
        # Calculate font size proportional to line height
        line_h = rect_f.height()
        font_size = max(8, min(int(line_h * 0.72), 40))
        font = QtGui.QFont("Segoe UI", font_size)
        fm = QtGui.QFontMetrics(font)
        text_width = fm.horizontalAdvance(text) + 8

        # Background rect — stretches to fit translated text
        bg_w = max(rect_f.width(), text_width) + pad * 2
        bg_rect = QtCore.QRectF(rect_f.x() - pad, rect_f.y() - pad, bg_w, rect_f.height() + pad * 2)

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(20, 15, 45, 215))
        painter.drawRoundedRect(bg_rect, 4, 4)

        # Text
        draw_rect = QtCore.QRectF(rect_f.x() + 2, rect_f.y(), bg_w - pad * 2, rect_f.height())
        painter.setFont(font)
        painter.setPen(QtGui.QColor(240, 230, 255))
        painter.drawText(draw_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.TextSingleLine, text)

    def _paint_hint(self, painter):
        config = get_cached_ocr_config()
        lang = config.get("interface_language", "en")
        if lang == "ru":
            hint = "ESC \u2014 \u0437\u0430\u043a\u0440\u044b\u0442\u044c  |  \u041f\u041a\u041c \u2014 \u043f\u0435\u0440\u0435\u0442\u0430\u0449\u0438\u0442\u044c"
        else:
            hint = "ESC \u2014 close  |  RMB \u2014 drag"
        font = QtGui.QFont("Segoe UI", 11)
        painter.setFont(font)
        fm = QtGui.QFontMetrics(font)
        tw = fm.horizontalAdvance(hint) + 24
        box = QtCore.QRectF(self.width() - tw - 15, 15, tw, 28)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 160))
        painter.drawRoundedRect(box, 6, 6)
        painter.setPen(QtGui.QColor(200, 200, 200, 200))
        painter.drawText(box, QtCore.Qt.AlignCenter, hint)

    # ---- input -----------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            # ПКМ — перетаскивание оверлея
            self._is_dragging = True
            self._drag_offset = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self.move(self.pos() + event.pos() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self._is_dragging = False
            self.setCursor(QtCore.Qt.ArrowCursor)

    def closeEvent(self, event):
        global _fullscreen_overlay_ref
        _fullscreen_overlay_ref = None
        super().closeEvent(event)
        self.deleteLater()


_fullscreen_overlay_ref = None
_fullscreen_translate_busy = False


def run_fullscreen_translate():
    """Launch (or toggle) the fullscreen translate overlay."""
    global _fullscreen_overlay_ref, _fullscreen_translate_busy
    if _fullscreen_translate_busy:
        return
    if _fullscreen_overlay_ref is not None:
        _fullscreen_overlay_ref.close()
        _fullscreen_overlay_ref = None
        return
    app = QApplication.instance()
    if app is None:
        return
    _fullscreen_translate_busy = True
    try:
        _fullscreen_overlay_ref = FullScreenTranslateOverlay()
    finally:
        _fullscreen_translate_busy = False


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "translate":
        run_screen_capture("translate")
    else:
        run_screen_capture()
