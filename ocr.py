import sys
import asyncio
import os
import json
import logging
import logging.handlers
from datetime import datetime
import shutil
import time

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
from languages import (
    LANGUAGES as APP_LANGUAGES,
    default_target_for_source,
    detect_language_code,
    language_display_name,
    language_icon_path,
    language_short_label,
    ocr_translate_options,
    tesseract_language_code,
    windows_ocr_tag,
)
import portable_paths

APP_LANGUAGE_CODES = {language.code for language in APP_LANGUAGES}

if sys.platform == "win32":
    import ctypes

try:
    import pyperclip
except Exception:
    class _PyperclipFallback:
        @staticmethod
        def copy(text):
            try:
                app = QApplication.instance()
                if app is not None:
                    app.clipboard().setText(str(text))
            except Exception:
                return

        @staticmethod
        def paste():
            try:
                app = QApplication.instance()
                if app is not None:
                    return app.clipboard().text()
            except Exception:
                return ""

    pyperclip = _PyperclipFallback

# Настройка логирования в файл для диагностики
def get_log_dir():
    if getattr(sys, 'frozen', False):
        base_dir = portable_paths.portable_base_dir()
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

def get_log_path():
    return os.path.join(get_log_dir(), "ocr_debug.log")

def get_debug_artifact_dir():
    artifact_dir = os.path.join(get_log_dir(), "ocr_artifacts")
    os.makedirs(artifact_dir, exist_ok=True)
    return artifact_dir

_debug_log_path = get_log_path()
_OCR_LOGGER = logging.getLogger("clickntranslate.ocr")

def _setup_ocr_diagnostics_logging():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)s] [%(threadName)s] "
        "%(name)s:%(lineno)d - %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    if not any(getattr(handler, "_clickntranslate_ocr_file", False) for handler in root.handlers):
        file_handler = logging.handlers.RotatingFileHandler(
            _debug_log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler._clickntranslate_ocr_file = True
        root.addHandler(file_handler)
    logging.captureWarnings(True)

def debug_log(msg):
    _OCR_LOGGER.debug(str(msg))

_setup_ocr_diagnostics_logging()
debug_log(f"OCR diagnostics log initialized: {_debug_log_path}")

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
    return portable_paths.portable_base_dir()

def get_data_file(filename):
    data_dir = os.path.join(get_portable_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, filename)

def _new_ocr_session_id(mode):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    return f"{timestamp}-{mode}-{os.getpid()}"

def _rect_to_text(rect):
    if rect is None:
        return "None"
    return f"x={rect.x()}, y={rect.y()}, w={rect.width()}, h={rect.height()}"

def _point_to_text(point):
    if point is None:
        return "None"
    return f"x={point.x()}, y={point.y()}"

def _screen_to_text(screen):
    if screen is None:
        return "None"
    try:
        return (
            f"name={screen.name()!r}, geometry=({_rect_to_text(screen.geometry())}), "
            f"available=({_rect_to_text(screen.availableGeometry())}), "
            f"dpr={screen.devicePixelRatio():.3f}, "
            f"logicalDpi={screen.logicalDotsPerInch():.1f}, "
            f"physicalDpi={screen.physicalDotsPerInch():.1f}"
        )
    except Exception as e:
        return f"<screen describe failed: {e}>"

def _text_preview(text, limit=180):
    text = str(text or "").replace("\r", "\\r").replace("\n", "\\n")
    if len(text) > limit:
        return text[:limit] + "..."
    return text

def _score_recognized_text(text):
    text = str(text or "").strip()
    if not text:
        return float("-inf")
    useful_punctuation = set(".,:;!?/\\-_()[]{}@#%&+=<>$€£¥'\"|")
    alnum = sum(1 for ch in text if ch.isalnum())
    alpha = sum(1 for ch in text if ch.isalpha())
    spaces = sum(1 for ch in text if ch.isspace())
    useful = sum(1 for ch in text if ch in useful_punctuation)
    noise = sum(1 for ch in text if not ch.isalnum() and not ch.isspace() and ch not in useful_punctuation)
    lines = text.count("\n")
    text_len = max(len(text), 1)
    signal_density = (alnum + useful * 0.65 + spaces * 0.25) / text_len
    repeated_noise = sum(1 for left, right in zip(text, text[1:]) if left == right and not left.isalnum())
    return (
        signal_density * 45.0
        + min(alnum, 90) * 1.15
        + alpha * 0.15
        + spaces * 0.12
        + useful * 0.45
        + lines * 0.4
        - noise * 4.0
        - repeated_noise * 1.6
    )

def _prepare_tesseract_data(tess_cmd, tess_lang):
    tess_dir = os.path.dirname(tess_cmd)
    candidate_dirs = [
        os.path.join(tess_dir, "tessdata"),
        os.path.join(os.path.dirname(tess_dir), "tessdata"),
    ]
    tessdata_dir = ""
    for td in candidate_dirs:
        if os.path.isdir(td):
            tessdata_dir = td
            os.environ["TESSDATA_PREFIX"] = td
            break
    if not tessdata_dir:
        os.environ.pop("TESSDATA_PREFIX", None)
        return

    try:
        import requests
        for lang_code in [code for code in tess_lang.split("+") if code]:
            fname = f"{lang_code}.traineddata"
            target_path = os.path.join(tessdata_dir, fname)
            if os.path.exists(target_path):
                continue
            url = f"https://github.com/tesseract-ocr/tessdata/raw/main/{fname}"
            logging.info(f"Downloading {fname} ...")
            r = requests.get(url, timeout=30, stream=True)
            r.raise_for_status()
            with open(target_path + ".tmp", "wb") as f:
                shutil.copyfileobj(r.raw, f)
            os.replace(target_path + ".tmp", target_path)
            logging.info(f"{fname} downloaded into {tessdata_dir}")
    except Exception as dl_err:
        logging.warning(f"Could not prepare Tesseract language data {tess_lang}: {dl_err}")

def _tesseract_psm_order(width, height):
    psm_order = [6]
    if height < 110:
        psm_order = [7, 8, 13, 6, 11]
    elif width < 260 or height < 180:
        psm_order = [6, 7, 8, 13, 11]
    return psm_order

def _run_tesseract_ocr_image_with_cmd(pil_image, tess_cmd, tess_lang, context, session_id, cancel_check=None):
    import pytesseract

    if pil_image is None:
        return ""
    height = getattr(pil_image, "height", 0)
    width = getattr(pil_image, "width", 0)
    if height <= 0 or width <= 0:
        logging.warning(f"[OCR:{session_id}] Tesseract skipped for empty image in {context}")
        return ""

    pytesseract.pytesseract.tesseract_cmd = tess_cmd
    best_text = ""
    best_score = float("-inf")
    for psm in _tesseract_psm_order(width, height):
        if cancel_check and cancel_check():
            logging.info(f"[OCR:{session_id}] Tesseract interrupted before psm={psm}; context={context}")
            break
        tess_config = f"--oem 3 --psm {psm}"
        try:
            started = time.perf_counter()
            text = pytesseract.image_to_string(pil_image, lang=tess_lang, config=tess_config)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            stripped = text.strip()
            score = _score_recognized_text(stripped)
            logging.info(
                f"[OCR:{session_id}] Tesseract {context}; lang={tess_lang}, psm={psm}, "
                f"elapsed_ms={elapsed_ms:.1f}, raw_len={len(text)}, stripped_len={len(stripped)}, "
                f"score={score:.1f}, preview={_text_preview(stripped)}"
            )
            if stripped and score > best_score:
                best_text = text
                best_score = score
        except Exception as e:
            logging.exception(f"[OCR:{session_id}] Tesseract {context} failed with psm={psm}: {e}")
    if best_text:
        logging.info(
            f"[OCR:{session_id}] Tesseract {context} selected best result; "
            f"score={best_score:.1f}, preview={_text_preview(best_text.strip())}"
        )
    return best_text

def _recognize_tesseract_variants_with_cmd(
    pil_variants,
    tess_cmd,
    tess_lang,
    context,
    session_id,
    cancel_check=None,
):
    if not tess_cmd:
        logging.error(f"[OCR:{session_id}] Tesseract executable not found for {context}.")
        return None

    logging.info(f"[OCR:{session_id}] Using Tesseract at: {tess_cmd}; context={context}, lang={tess_lang}")
    _prepare_tesseract_data(tess_cmd, tess_lang)

    best_text = ""
    best_score = float("-inf")
    best_label = ""
    for label, pil_image in pil_variants or []:
        if cancel_check and cancel_check():
            logging.info(f"[OCR:{session_id}] Tesseract interrupted before variant={label}; context={context}")
            break
        text = _run_tesseract_ocr_image_with_cmd(
            pil_image,
            tess_cmd,
            tess_lang,
            f"{context}-{label}",
            session_id,
            cancel_check=cancel_check,
        )
        score = _score_recognized_text(text)
        logging.info(
            f"[OCR:{session_id}] Tesseract variant={label}; context={context}, "
            f"score={score:.1f}, len={len(text or '')}, preview={_text_preview(text)}"
        )
        if text and score > best_score:
            best_text = text
            best_score = score
            best_label = label

    if best_text:
        logging.info(
            f"[OCR:{session_id}] Tesseract selected variant={best_label}; "
            f"score={best_score:.1f}, preview={_text_preview(best_text)}"
        )
    return best_text

def _ocr_debug_artifacts_enabled():
    try:
        return bool(get_cached_ocr_config().get("debug_ocr_artifacts", False))
    except Exception:
        return False

def _cleanup_old_debug_artifacts(max_files=80):
    try:
        artifact_dir = get_debug_artifact_dir()
        files = [
            os.path.join(artifact_dir, name)
            for name in os.listdir(artifact_dir)
            if name.lower().endswith((".png", ".txt"))
        ]
        if len(files) <= max_files:
            return
        files.sort(key=lambda path: os.path.getmtime(path))
        for path in files[:max(0, len(files) - max_files)]:
            try:
                os.remove(path)
            except Exception:
                pass
    except Exception:
        pass

def _safe_artifact_label(label):
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(label or "artifact"))

def _save_pixmap_debug(pixmap, session_id, label, force=False):
    try:
        if not force and not _ocr_debug_artifacts_enabled():
            return ""
        if pixmap is None or pixmap.isNull():
            return ""
        _cleanup_old_debug_artifacts()
        filename = f"{session_id}-{_safe_artifact_label(label)}.png"
        path = os.path.join(get_debug_artifact_dir(), filename)
        if pixmap.save(path, "PNG"):
            logging.info(f"[OCR:{session_id}] saved pixmap artifact {label}: {path}")
            return path
    except Exception as e:
        logging.warning(f"[OCR:{session_id}] failed to save pixmap artifact {label}: {e}")
    return ""

def _save_pil_debug(image, session_id, label, force=False):
    try:
        if not force and not _ocr_debug_artifacts_enabled():
            return ""
        if image is None:
            return ""
        _cleanup_old_debug_artifacts()
        filename = f"{session_id}-{_safe_artifact_label(label)}.png"
        path = os.path.join(get_debug_artifact_dir(), filename)
        image.save(path)
        logging.info(f"[OCR:{session_id}] saved PIL artifact {label}: {path}")
        return path
    except Exception as e:
        logging.warning(f"[OCR:{session_id}] failed to save PIL artifact {label}: {e}")
    return ""

def _normalize_app_language_code(code, fallback="en", allow_universal=False, allow_auto=False):
    code = str(code or "").lower()
    if allow_universal and code == "universal":
        return code
    if allow_auto and code == "auto":
        return code
    return code if code in APP_LANGUAGE_CODES else fallback

def _configured_ocr_translate_pair(config=None, source_code=None):
    config = config or get_cached_ocr_config()
    source = _normalize_app_language_code(
        source_code or config.get("ocr_translate_source_language") or config.get("last_ocr_language"),
        "en",
        allow_auto=True,
    )
    target = default_target_for_source(source, config.get("ocr_translate_target_language"))
    return source, target

def _combo_data_to_ocr_language(data, fallback="ru"):
    if isinstance(data, (tuple, list)) and data:
        data = data[0]
    return _normalize_app_language_code(data, fallback, allow_universal=True, allow_auto=True)

def _combo_data_to_translate_pair(data, config=None):
    config = config or get_cached_ocr_config()
    if isinstance(data, (tuple, list)) and len(data) >= 2:
        source = _normalize_app_language_code(data[0], "en", allow_auto=True)
        target = _normalize_app_language_code(data[1], default_target_for_source(source))
        if source == target:
            target = default_target_for_source(source)
        return source, target
    source, _target = _configured_ocr_translate_pair(config, data)
    return source, default_target_for_source(source, config.get("ocr_translate_target_language"))

def _ocr_translate_options_from_config(config=None):
    config = config or get_cached_ocr_config()
    return ocr_translate_options(config.get("ocr_translate_target_language"))

def _find_translate_pair_index(combo, source_code, target_code=None):
    for i in range(combo.count()):
        source, target = _combo_data_to_translate_pair(combo.itemData(i))
        if source == source_code and (target_code is None or target == target_code):
            return i
    return -1

def _write_ocr_config_updates(updates):
    global _ocr_config_cache, _ocr_config_mtime
    config_path = get_data_file("config.json")
    try:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            config = {}
        config.update(updates)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        _ocr_config_cache = config
        try:
            _ocr_config_mtime = os.path.getmtime(config_path)
        except Exception:
            _ocr_config_mtime = 0
        return True
    except Exception as e:
        logging.warning(f"Failed to save OCR config updates: {e}")
        return False

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
    _write_data_writer_bytes(data_writer, byte_data)
    bitmap = winrt_imaging.SoftwareBitmap(winrt_imaging.BitmapPixelFormat.RGBA8, pil_image.width, pil_image.height)
    bitmap.copy_from_buffer(data_writer.detach_buffer())
    return bitmap

# Cache for Windows OCR engines per language tag
_OCR_ENGINE_CACHE = {}
_OVERLAY_POOL = {"ocr": None, "copy": None, "translate": None}
_WINDOWS_OCR_MISSING_NOTICE_SHOWN = set()


def _write_data_writer_bytes(data_writer, byte_data):
    try:
        data_writer.write_bytes(byte_data)
    except TypeError:
        data_writer.write_bytes(list(byte_data))


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
            primary_subtag = str(lang_tag).split("-", 1)[0].lower()
            for available_tag in _get_available_windows_ocr_language_tags():
                if str(available_tag).split("-", 1)[0].lower() != primary_subtag:
                    continue
                try:
                    if OcrEngine.is_language_supported(Language(available_tag)):
                        logging.info(
                            f"Windows OCR language {lang_tag} is not installed; "
                            f"using installed regional variant {available_tag}"
                        )
                        lang_tag = available_tag
                        is_supported = True
                        break
                except Exception:
                    continue

        if not is_supported:
            debug_log(f"Language {lang_tag} not supported by Windows OCR")
            logging.warning(f"Windows OCR language {lang_tag} is not installed")
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

def _get_available_windows_ocr_language_tags():
    if not _WINRT_AVAILABLE:
        return []
    try:
        available_langs = getattr(winrt_ocr.OcrEngine, "available_recognizer_languages", None)
        if available_langs is None:
            getter = getattr(winrt_ocr.OcrEngine, "get_available_recognizer_languages", None)
            available_langs = getter() if callable(getter) else None
        if available_langs is None:
            return []
        count = getattr(available_langs, "size", None)
        if count is None:
            count = len(available_langs)
        return [
            available_langs.get_at(i).language_tag
            for i in range(count)
        ]
    except Exception as e:
        logging.warning(f"Failed to list available Windows OCR languages: {e}")
        return []

# Cache for universal OCR engine
_UNIVERSAL_OCR_ENGINE = None

def _get_universal_ocr_engine():
    """Получить OCR движок по языкам профиля Windows, затем fallback на en-US/первый доступный."""
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

        profile_getter = getattr(OcrEngine, "try_create_from_user_profile_languages", None)
        if callable(profile_getter):
            debug_log("Trying OCR engine from user profile languages...")
            try:
                engine = profile_getter()
                if engine:
                    _UNIVERSAL_OCR_ENGINE = engine
                    debug_log("SUCCESS: Using user profile OCR engine")
                    return engine
            except Exception as e:
                debug_log(f"User profile OCR engine failed: {e}")
        
        # Fallback: en-US хорошо работает с цифрами и латиницей.
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
        available_langs = getattr(OcrEngine, "available_recognizer_languages", None)
        if available_langs is None:
            getter = getattr(OcrEngine, "get_available_recognizer_languages", None)
            available_langs = getter() if callable(getter) else None
        available_count = getattr(available_langs, "size", 0) if available_langs is not None else 0
        if available_count > 0:
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
        _write_data_writer_bytes(data_writer, bytes(ptr))

        bitmap = winrt_imaging.SoftwareBitmap(winrt_imaging.BitmapPixelFormat.RGBA8, width, height)
        bitmap.copy_from_buffer(data_writer.detach_buffer())
        debug_log(f"SoftwareBitmap created: {bitmap}")

        return bitmap
    except Exception as e:
        debug_log(f"EXCEPTION in qimage_to_softwarebitmap: {e}")
        import traceback
        debug_log(traceback.format_exc())
        return None

def _windows_ocr_max_image_dimension():
    try:
        return int(getattr(winrt_ocr.OcrEngine, "max_image_dimension", 0) or 0)
    except Exception:
        return 0

def _limit_qimage_for_windows_ocr(qimage, session_id, label):
    max_dim = _windows_ocr_max_image_dimension()
    if not qimage or qimage.isNull() or max_dim <= 0:
        return qimage
    largest = max(qimage.width(), qimage.height())
    if largest <= max_dim:
        return qimage
    scaled = qimage.scaled(
        max_dim,
        max_dim,
        QtCore.Qt.KeepAspectRatio,
        QtCore.Qt.SmoothTransformation,
    )
    logging.warning(
        f"[OCR:{session_id}] Windows OCR attempt={label} exceeded max image dimension; "
        f"scaled {qimage.width()}x{qimage.height()} -> {scaled.width()}x{scaled.height()} "
        f"(max={max_dim})"
    )
    return scaled


def _windows_ocr_result_to_text(recognized):
    if not recognized:
        return ""
    try:
        lines = recognized.lines
    except AttributeError:
        debug_log("ERROR: recognized has no 'lines' attribute")
        return ""
    except Exception as e:
        debug_log(f"ERROR accessing recognized.lines: {e}")
        return ""

    if not lines:
        debug_log("recognized.lines is empty")
        return ""

    lines_text = []
    for line in lines:
        try:
            words = list(line.words)
            line_text = " ".join(str(word.text) for word in words if str(word.text).strip())
            if not line_text:
                line_text = str(line.text or "")
        except Exception:
            line_text = str(getattr(line, "text", "") or "")
        line_text = line_text.strip()
        if line_text:
            lines_text.append(line_text)
    return "\n".join(lines_text).strip()


def _auto_ocr_language_codes(config=None):
    config = config or get_cached_ocr_config()
    preferred = [
        config.get("ocr_translate_source_language"),
        config.get("last_ocr_language"),
        "ru",
        "en",
    ]
    preferred.extend(language.code for language in APP_LANGUAGES)

    codes = []
    seen = set()
    for raw_code in preferred:
        code = _normalize_app_language_code(raw_code, "", allow_universal=False, allow_auto=False)
        if code and code not in seen:
            codes.append(code)
            seen.add(code)
    return codes


def _language_script_group(language_code):
    code = (language_code or "").lower()
    if code in {"ru", "uk"}:
        return "cyrillic"
    if code == "zh":
        return "cjk"
    if code == "ja":
        return "japanese"
    if code == "ko":
        return "korean"
    if code == "ar":
        return "arabic"
    if code == "hi":
        return "devanagari"
    return "latin"


def _ocr_script_counts(text):
    counts = {
        "latin": 0,
        "cyrillic": 0,
        "cjk": 0,
        "kana": 0,
        "hangul": 0,
        "arabic": 0,
        "devanagari": 0,
        "other": 0,
    }
    for ch in str(text or ""):
        if "\u0400" <= ch <= "\u04ff":
            counts["cyrillic"] += 1
        elif "\u4e00" <= ch <= "\u9fff":
            counts["cjk"] += 1
        elif "\u3040" <= ch <= "\u30ff":
            counts["kana"] += 1
        elif "\uac00" <= ch <= "\ud7af":
            counts["hangul"] += 1
        elif "\u0600" <= ch <= "\u06ff":
            counts["arabic"] += 1
        elif "\u0900" <= ch <= "\u097f":
            counts["devanagari"] += 1
        elif ("a" <= ch.lower() <= "z") or ("\u00c0" <= ch <= "\u024f") or ("\u1e00" <= ch <= "\u1eff"):
            counts["latin"] += 1
        elif ch.isalpha():
            counts["other"] += 1
    return counts


def _script_match_score(text, language_code):
    counts = _ocr_script_counts(text)
    total_letters = sum(counts.values())
    if total_letters <= 0:
        return 0.0

    group = _language_script_group(language_code)
    if group == "cyrillic":
        matched = counts["cyrillic"]
    elif group == "cjk":
        matched = counts["cjk"]
    elif group == "japanese":
        matched = counts["kana"] + (counts["cjk"] * 0.7)
    elif group == "korean":
        matched = counts["hangul"]
    elif group == "arabic":
        matched = counts["arabic"]
    elif group == "devanagari":
        matched = counts["devanagari"]
    else:
        matched = counts["latin"]

    ratio = matched / max(total_letters, 1)
    score = ratio * 45.0
    if total_letters >= 4 and matched <= 0:
        score -= 35.0
    elif total_letters >= 8 and ratio < 0.35:
        score -= 18.0
    return score


def _score_ocr_text_for_language(text, language_code):
    text = str(text or "").strip()
    if not text:
        return float("-inf")

    alnum = sum(1 for ch in text if ch.isalnum())
    alpha = sum(1 for ch in text if ch.isalpha())
    digits = sum(1 for ch in text if ch.isdigit())
    spaces = sum(1 for ch in text if ch.isspace())
    common_punctuation = set(".,:;!?-\u2013\u2014()[]{}\"'`/\\%+\u2116#@&")
    noise = sum(1 for ch in text if not ch.isalnum() and not ch.isspace() and ch not in common_punctuation)
    replacement_chars = text.count("\ufffd")
    tokens = [
        token.strip(".,:;!?-\u2013\u2014()[]{}\"'`/\\%+\u2116#@&")
        for token in text.replace("\n", " ").split()
    ]
    word_tokens = [token for token in tokens if any(ch.isalpha() for ch in token)]

    score = 0.0
    score += alpha * 2.2
    score += digits * 0.5
    score += min(spaces, max(alpha, 1)) * 0.15
    score += min(len(word_tokens), 40) * 1.4
    score -= noise * 1.8
    score -= replacement_chars * 20.0
    score += _script_match_score(text, language_code)

    detected = detect_language_code(text)
    if detected == language_code:
        score += 35.0
    elif _language_script_group(detected) == _language_script_group(language_code):
        score += 8.0
    elif alpha >= 4:
        score -= 14.0

    if alnum <= 1:
        score -= 10.0
    if alpha <= 0:
        score -= 8.0
    return score


def _match_available_windows_ocr_tag(expected_tag, available_by_tag):
    expected_key = str(expected_tag or "").lower()
    if expected_key in available_by_tag:
        return available_by_tag[expected_key]

    language_prefix = expected_key.split("-", 1)[0]
    if not language_prefix:
        return ""
    for available_key, available_tag in available_by_tag.items():
        if available_key == language_prefix or available_key.startswith(language_prefix + "-"):
            return available_tag
    return ""


def _windows_auto_ocr_candidates(config=None):
    available_tags = _get_available_windows_ocr_language_tags()
    available_by_tag = {str(tag).lower(): str(tag) for tag in available_tags if str(tag).strip()}
    if not available_by_tag:
        return []

    candidates = []
    seen_tags = set()
    for code in _auto_ocr_language_codes(config):
        tag = _match_available_windows_ocr_tag(windows_ocr_tag(code), available_by_tag)
        tag_key = tag.lower()
        if tag and tag_key not in seen_tags:
            candidates.append((code, tag))
            seen_tags.add(tag_key)
    return candidates


def _recognize_with_windows_auto(bitmap):
    candidates = _windows_auto_ocr_candidates()
    if not candidates:
        logging.warning("Windows OCR AUTO has no installed candidate languages; falling back to universal engine.")
        engine = _get_universal_ocr_engine()
        if engine is None:
            return ""
        loop = _get_ocr_event_loop()
        asyncio.set_event_loop(loop)
        recognized = loop.run_until_complete(run_ocr_with_engine(bitmap, engine))
        return _windows_ocr_result_to_text(recognized)

    loop = _get_ocr_event_loop()
    asyncio.set_event_loop(loop)

    best_text = ""
    best_score = float("-inf")
    best_code = ""
    best_tag = ""
    for code, tag in candidates:
        engine = _get_windows_ocr_engine(tag)
        if engine is None:
            continue
        recognized = loop.run_until_complete(run_ocr_with_engine(bitmap, engine))
        text = _windows_ocr_result_to_text(recognized)
        score = _score_ocr_text_for_language(text, code)
        detected = detect_language_code(text) if text else ""
        logging.info(
            f"Windows OCR AUTO candidate; lang={code}, tag={tag}, score={score:.1f}, "
            f"detected={detected or '-'}, len={len(text)}, preview={_text_preview(text)}"
        )
        if text and score > best_score:
            best_text = text
            best_score = score
            best_code = code
            best_tag = tag

    if best_text:
        logging.info(
            f"Windows OCR AUTO selected; lang={best_code}, tag={best_tag}, "
            f"score={best_score:.1f}, preview={_text_preview(best_text)}"
        )
    else:
        logging.warning("Windows OCR AUTO did not recognize text with any candidate language.")
    return best_text


class OCRWorker(QtCore.QThread):
    result_ready = QtCore.pyqtSignal(str)
    def __init__(self, bitmap, language_code, parent=None, use_universal=False, attempts=None, session_id="unknown"):
        super().__init__(parent)
        self.bitmap = bitmap
        self.language_code = language_code
        self.use_universal = use_universal
        self.session_id = session_id
        self.cancel_requested = False
        self.fallback_pil_variants = []
        self.tesseract_fallback_enabled = False
        self.tesseract_cmd = None
        self.tesseract_fallback_attempted = False
        if attempts is None:
            attempts = [("primary", bitmap)]
        self.attempts = [(str(label), attempt_bitmap) for label, attempt_bitmap in attempts if attempt_bitmap is not None]

    def cancel(self):
        self.cancel_requested = True
        self.requestInterruption()

    def _is_cancelled(self):
        return self.cancel_requested or self.isInterruptionRequested()

    @staticmethod
    def _extract_result_text(recognized):
        recognized_text = ""
        if not recognized:
            return recognized_text
        try:
            # Проверяем lines через try/except (hasattr вызывает ошибку импорта collections)
            lines = recognized.lines
            if lines:
                lines_text = []
                for line in lines:
                    try:
                        words = list(line.words)
                        if words:
                            line_text = " ".join(word.text for word in words)
                        else:
                            line_text = line.text
                    except Exception:
                        line_text = line.text
                    lines_text.append(line_text)
                recognized_text = "\n".join(lines_text)
            else:
                debug_log("recognized.lines is empty")
                logging.warning("Windows OCR returned empty result")
        except AttributeError:
            debug_log("ERROR: recognized has no 'lines' attribute")
        except Exception as e:
            debug_log(f"ERROR accessing recognized.lines: {e}")
        return recognized_text

    def run(self):
        debug_log(f"OCRWorker.run() started")
        debug_log(f"self.bitmap = {self.bitmap}")
        debug_log(f"self.language_code = {self.language_code}")
        debug_log(f"self.use_universal = {self.use_universal}")
        debug_log(f"self.attempts = {[label for label, _bitmap in self.attempts]}")
        loop = None
        try:
            # Выбираем engine в зависимости от режима
            if self.use_universal:
                debug_log("Using Windows OCR AUTO language selection")
                recognized_text = _recognize_with_windows_auto(self.bitmap)
                debug_log(f"Emitting AUTO result: '{recognized_text[:50]}...' (len={len(recognized_text)})")
                self.result_ready.emit(recognized_text)
                return
            else:
                lang_tag = windows_ocr_tag(self.language_code)
                debug_log(f"lang_tag = {lang_tag}")
                engine = _get_windows_ocr_engine(lang_tag)
            
            debug_log(f"engine = {engine}")
            
            if engine is None:
                debug_log("ERROR: engine is None")
                recognized_text = ""
                if self.tesseract_fallback_enabled and self.fallback_pil_variants and self.tesseract_cmd:
                    self.tesseract_fallback_attempted = True
                    tess_lang = tesseract_language_code(self.language_code)
                    logging.info(
                        f"[OCR:{self.session_id}] Windows OCR engine unavailable; "
                        f"running Tesseract fallback in OCR worker; lang={tess_lang}"
                    )
                    recognized_text = _recognize_tesseract_variants_with_cmd(
                        self.fallback_pil_variants,
                        self.tesseract_cmd,
                        tess_lang,
                        "windows-engine-missing-fallback",
                        self.session_id,
                        cancel_check=self._is_cancelled,
                    ) or ""
                if not self._is_cancelled():
                    self.result_ready.emit(recognized_text)
                return
            if not self.attempts:
                debug_log("ERROR: no OCR bitmap attempts, emitting empty result")
                self.result_ready.emit("")
                return

            # WinRT async calls run inside this worker only; sharing one global loop
            # across QThreads can crash when two OCR sessions overlap.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            best_text = ""
            best_score = float("-inf")
            best_label = ""
            for attempt_label, attempt_bitmap in self.attempts:
                if self._is_cancelled():
                    logging.info(f"[OCR:{self.session_id}] OCR worker interrupted before attempt={attempt_label}")
                    break
                try:
                    debug_log(f"Calling run_ocr_with_engine for attempt={attempt_label}...")
                    started = time.perf_counter()
                    recognized = loop.run_until_complete(run_ocr_with_engine(attempt_bitmap, engine))
                    elapsed_ms = (time.perf_counter() - started) * 1000.0
                    if self._is_cancelled():
                        logging.info(f"[OCR:{self.session_id}] OCR worker interrupted after attempt={attempt_label}")
                        break
                    debug_log(f"recognized[{attempt_label}] = {recognized}")
                    if not recognized:
                        logging.warning(
                            f"[OCR:{self.session_id}] Windows OCR attempt={attempt_label} returned None; "
                            f"elapsed_ms={elapsed_ms:.1f}"
                        )
                        continue
                    attempt_text = self._extract_result_text(recognized)
                    attempt_score = _score_recognized_text(attempt_text)
                    logging.info(
                        f"[OCR:{self.session_id}] Windows OCR attempt={attempt_label}; "
                        f"elapsed_ms={elapsed_ms:.1f}, text_len={len(attempt_text)}, "
                        f"score={attempt_score:.1f}, preview={_text_preview(attempt_text)}"
                    )
                    if attempt_text and attempt_score > best_score:
                        best_text = attempt_text
                        best_score = attempt_score
                        best_label = attempt_label
                except Exception as e:
                    logging.exception(f"[OCR:{self.session_id}] Windows OCR attempt={attempt_label} failed: {e}")

            recognized_text = best_text
            if recognized_text:
                debug_log(f"recognized_text = '{recognized_text[:100]}...' (length={len(recognized_text)})")
                logging.info(
                    f"[OCR:{self.session_id}] Windows OCR selected attempt={best_label}; "
                    f"chars={len(recognized_text)}, score={best_score:.1f}"
                )
            else:
                logging.warning(f"[OCR:{self.session_id}] Windows OCR returned empty result for all attempts")

            if not recognized_text and not self.use_universal and not self._is_cancelled():
                try:
                    universal_engine = _get_universal_ocr_engine()
                    if universal_engine is not None:
                        logging.info(
                            f"[OCR:{self.session_id}] Primary Windows OCR was empty; "
                            "retrying with universal/user-profile OCR engine"
                        )
                        universal_best_text = ""
                        universal_best_score = float("-inf")
                        universal_best_label = ""
                        for attempt_label, attempt_bitmap in self.attempts:
                            if self._is_cancelled():
                                logging.info(
                                    f"[OCR:{self.session_id}] Universal OCR retry interrupted before attempt={attempt_label}"
                                )
                                break
                            try:
                                started = time.perf_counter()
                                recognized = loop.run_until_complete(run_ocr_with_engine(attempt_bitmap, universal_engine))
                                elapsed_ms = (time.perf_counter() - started) * 1000.0
                                if self._is_cancelled():
                                    logging.info(
                                        f"[OCR:{self.session_id}] Universal OCR retry interrupted after attempt={attempt_label}"
                                    )
                                    break
                                attempt_text = self._extract_result_text(recognized)
                                attempt_score = _score_recognized_text(attempt_text)
                                logging.info(
                                    f"[OCR:{self.session_id}] Universal Windows OCR attempt={attempt_label}; "
                                    f"elapsed_ms={elapsed_ms:.1f}, text_len={len(attempt_text)}, "
                                    f"score={attempt_score:.1f}, preview={_text_preview(attempt_text)}"
                                )
                                if attempt_text and attempt_score > universal_best_score:
                                    universal_best_text = attempt_text
                                    universal_best_score = attempt_score
                                    universal_best_label = attempt_label
                            except Exception as e:
                                logging.exception(
                                    f"[OCR:{self.session_id}] Universal Windows OCR attempt={attempt_label} failed: {e}"
                                )
                        if universal_best_text:
                            recognized_text = universal_best_text
                            logging.info(
                                f"[OCR:{self.session_id}] Universal Windows OCR selected attempt={universal_best_label}; "
                                f"chars={len(recognized_text)}, score={universal_best_score:.1f}"
                            )
                except Exception as e:
                    logging.exception(f"[OCR:{self.session_id}] Universal Windows OCR retry failed: {e}")

            if (
                not recognized_text
                and self.tesseract_fallback_enabled
                and self.fallback_pil_variants
                and self.tesseract_cmd
                and not self._is_cancelled()
            ):
                self.tesseract_fallback_attempted = True
                tess_lang = tesseract_language_code(self.language_code)
                logging.info(
                    f"[OCR:{self.session_id}] Windows OCR empty; running Tesseract fallback in OCR worker; "
                    f"lang={tess_lang}, variants={[label for label, _image in self.fallback_pil_variants]}"
                )
                recognized_text = _recognize_tesseract_variants_with_cmd(
                    self.fallback_pil_variants,
                    self.tesseract_cmd,
                    tess_lang,
                    "windows-empty-fallback",
                    self.session_id,
                    cancel_check=self._is_cancelled,
                ) or ""

        except Exception as e:
            debug_log(f"EXCEPTION in OCRWorker.run(): {e}")
            import traceback
            debug_log(traceback.format_exc())
            recognized_text = ""
        finally:
            try:
                if loop is not None:
                    loop.close()
            except Exception:
                pass
        
        if self._is_cancelled():
            logging.info(f"[OCR:{self.session_id}] OCR worker result suppressed after interruption")
            return
        debug_log(f"Emitting result: '{recognized_text[:50]}...' (len={len(recognized_text)})")
        self.result_ready.emit(recognized_text)

class TesseractOCRWorker(QtCore.QThread):
    result_ready = QtCore.pyqtSignal(str)

    def __init__(self, pil_variants, language_code, tess_cmd, context, session_id, parent=None):
        super().__init__(parent)
        self.pil_variants = list(pil_variants or [])
        self.language_code = language_code
        self.tess_cmd = tess_cmd
        self.context = context
        self.session_id = session_id
        self.cancel_requested = False

    def cancel(self):
        self.cancel_requested = True
        self.requestInterruption()

    def _is_cancelled(self):
        return self.cancel_requested or self.isInterruptionRequested()

    def run(self):
        logging.info(
            f"[OCR:{self.session_id}] TesseractOCRWorker started; context={self.context}, "
            f"language={self.language_code}, variants={[label for label, _image in self.pil_variants]}"
        )
        text = ""
        try:
            if not self.tess_cmd:
                logging.error(f"[OCR:{self.session_id}] Tesseract worker has no executable path")
            elif not self.pil_variants:
                logging.error(f"[OCR:{self.session_id}] Tesseract worker has no image variants")
            else:
                tess_lang = tesseract_language_code(self.language_code)
                text = _recognize_tesseract_variants_with_cmd(
                    self.pil_variants,
                    self.tess_cmd,
                    tess_lang,
                    self.context,
                    self.session_id,
                    cancel_check=self._is_cancelled,
                ) or ""
        except Exception as e:
            logging.exception(f"[OCR:{self.session_id}] TesseractOCRWorker failed: {e}")

        if self._is_cancelled():
            logging.info(f"[OCR:{self.session_id}] Tesseract worker result suppressed after interruption")
            return
        logging.info(
            f"[OCR:{self.session_id}] TesseractOCRWorker finished; "
            f"text_len={len(text or '')}, preview={_text_preview(text)}"
        )
        self.result_ready.emit(text)

class ScreenCaptureOverlay(QWidget):
    def __init__(self, mode="ocr", defer_show=False):
        super().__init__()
        # Устанавливаем иконку приложения
        self.setWindowIcon(QtGui.QIcon(resource_path("icons/icon.ico")))
        
        self.mode = mode
        self.start_point = None
        self.end_point = None
        self.last_rect = None
        self._active_screen = None
        self._frozen_background = None
        self._frozen_background_rect = QtCore.QRect()
        self._updating_language_controls = False
        self._ocr_in_progress = False
        self._ignore_ocr_results = False
        self._handling_ocr_result = False
        self._ocr_worker_session_id = None
        self._last_ocr_raw_capture = None
        self._last_ocr_pil_variants = []
        self._last_ocr_capture_meta = {}
        # Загрузка последнего выбранного языка из конфигурации
        config = get_cached_ocr_config()
        self._freeze_screen_on_ocr = config.get("freeze_screen_on_ocr", False)
        if self.mode == "translate":
            self.current_language, self.current_target_language = _configured_ocr_translate_pair(config)
        else:
            self.current_language = config.get("last_ocr_language", "ru")
            self.current_target_language = None
        self.setWindowFlags(
            QtCore.Qt.Tool |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setCursor(QtCore.Qt.CrossCursor)
        # Используем primaryScreen для grabWindow(0) — WId=0 означает весь виртуальный десктоп
        self.screen = QApplication.primaryScreen()
        self._grab_screen = self.screen  # сохраняем для capture
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self._session_id = _new_ocr_session_id(self.mode)
        self._selection_started_at = None
        self._move_event_count = 0
        self._last_move_log_ts = 0.0
        
        # Используем текущий язык (уже загружен из конфига в __init__)
        self.lang_combo = QtWidgets.QComboBox(self)
        self.target_lang_combo = None
        self.translate_arrow_label = None
        
        # В режиме copy добавляем опцию "Универсальный" первой (эмодзи планеты)
        if self.mode == "copy":
            self.lang_combo.addItem("🌐  AUTO", "universal")
            for language in APP_LANGUAGES:
                self.lang_combo.addItem(
                    QtGui.QIcon(resource_path(language_icon_path(language.code))),
                    language.short_label,
                    language.code,
                )
        elif self.mode == "translate":
            self.lang_combo.addItem("AUTO", "auto")
            # В режиме translate источник и цель выбираются отдельно прямо в OCR-оверлее.
            for language in APP_LANGUAGES:
                self.lang_combo.addItem(
                    QtGui.QIcon(resource_path(language_icon_path(language.code))),
                    language.short_label,
                    language.code,
                )
            self.translate_arrow_label = QtWidgets.QLabel("→", self)
            self.translate_arrow_label.setAlignment(QtCore.Qt.AlignCenter)
            self.translate_arrow_label.setStyleSheet("""
                QLabel {
                    color: #d8e3f2;
                    font-size: 20px;
                    font-weight: 700;
                    background-color: rgba(22, 25, 31, 244);
                    border: 1px solid rgba(105, 123, 150, 130);
                    border-radius: 12px;
                }
            """)
            self.target_lang_combo = QtWidgets.QComboBox(self)
        else:
            for language in APP_LANGUAGES:
                self.lang_combo.addItem(
                    QtGui.QIcon(resource_path(language_icon_path(language.code))),
                    language.short_label,
                    language.code,
                )
        
        # Устанавливаем индекс на основе self.current_language (сохраненного)
        if self.mode == "copy":
            if self.current_language == "universal":
                default_index = 0
            else:
                idx = self.lang_combo.findData(self.current_language)
                default_index = idx if idx >= 0 else 0
        else:
            idx = self.lang_combo.findData(self.current_language)
            default_index = idx if idx >= 0 else 0
        self.lang_combo.setCurrentIndex(default_index)
        
        # Матовый dark-style: ровный popup, читаемые подписи, тонкий кастомный scrollbar.
        self.lang_combo.setIconSize(QtCore.QSize(30, 30))
        combo_style = """
            QComboBox {
                background-color: rgba(25, 29, 37, 248);
                color: #f6f8fb;
                border: 1px solid rgba(110, 130, 158, 155);
                border-radius: 11px;
                padding: 7px 9px 7px 9px;
                font-size: 15px;
                font-weight: 750;
                font-family: 'Segoe UI Semibold', 'Segoe UI', Arial, sans-serif;
                letter-spacing: 0.2px;
            }
            QComboBox:hover {
                background-color: rgba(31, 37, 48, 252);
                border: 1px solid rgba(145, 171, 205, 190);
            }
            QComboBox:pressed {
                background-color: rgba(18, 21, 27, 255);
                border: 1px solid rgba(116, 160, 216, 210);
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
                subcontrol-origin: padding;
                subcontrol-position: right center;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #11151c;
                color: #f5f7fa;
                border: 1px solid rgba(92, 112, 140, 210);
                border-radius: 12px;
                padding: 7px 3px 7px 5px;
                selection-background-color: #30455f;
                selection-color: #ffffff;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 4px 7px 4px 7px;
                border-radius: 9px;
                margin: 2px 4px 2px 1px;
                color: #f2f5fa;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #243044;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #365172;
                color: #ffffff;
            }
            QComboBox QAbstractItemView QScrollBar:vertical {
                background: transparent;
                border: none;
                width: 6px;
                margin: 9px 3px 9px 1px;
            }
            QComboBox QAbstractItemView QScrollBar::handle:vertical {
                background-color: rgba(154, 171, 194, 190);
                border-radius: 3px;
                min-height: 38px;
            }
            QComboBox QAbstractItemView QScrollBar::handle:vertical:hover {
                background-color: rgba(205, 218, 235, 230);
            }
            QComboBox QAbstractItemView QScrollBar::add-line:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
                border: none;
            }
            QComboBox QAbstractItemView QScrollBar::add-page:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """
        self.lang_combo.setStyleSheet(combo_style)
        self.lang_combo.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.lang_combo.view().setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.lang_combo.view().setTextElideMode(QtCore.Qt.ElideNone)
        if self.target_lang_combo is not None:
            self.target_lang_combo.setIconSize(QtCore.QSize(30, 30))
            self.target_lang_combo.setStyleSheet(combo_style)
            self.target_lang_combo.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            self.target_lang_combo.view().setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.target_lang_combo.view().setTextElideMode(QtCore.Qt.ElideNone)
            self._populate_translate_target_combo(self.current_target_language)
        # Размер зависит от режима
        combo_width = 102
        self.lang_combo.setFixedSize(combo_width, 46)
        if self.translate_arrow_label is not None:
            self.translate_arrow_label.setFixedSize(30, 46)
        if self.target_lang_combo is not None:
            self.target_lang_combo.setFixedSize(combo_width, 46)
        self.lang_combo.move((self.width() - self.lang_combo.width()) // 2, 20)
        # Показываем комбобокс (в режиме copy есть опция AUTO)
        self.lang_combo.setVisible(True if not defer_show else False)
        if self.translate_arrow_label is not None:
            self.translate_arrow_label.setVisible(True if not defer_show else False)
        if self.target_lang_combo is not None:
            self.target_lang_combo.setVisible(True if not defer_show else False)
        
        # Сохраняем язык при изменении
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        if self.target_lang_combo is not None:
            self.target_lang_combo.currentIndexChanged.connect(self.on_language_changed)

        logging.info(f"[OCR:{self._session_id}] Screen capture overlay initialized; mode={self.mode}, defer_show={defer_show}")
        if not defer_show:
            self.show_overlay()

    def _populate_translate_target_combo(self, selected_target=None):
        if self.target_lang_combo is None:
            return
        source_code = _combo_data_to_ocr_language(self.lang_combo.currentData(), "en")
        target_code = default_target_for_source(source_code, selected_target or self.current_target_language)
        self.target_lang_combo.blockSignals(True)
        try:
            self.target_lang_combo.clear()
            for language in APP_LANGUAGES:
                if language.code == source_code:
                    continue
                self.target_lang_combo.addItem(
                    QtGui.QIcon(resource_path(language_icon_path(language.code))),
                    language.short_label,
                    language.code,
                )
            idx = self.target_lang_combo.findData(target_code)
            self.target_lang_combo.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self.target_lang_combo.blockSignals(False)
        self.current_target_language = self.target_lang_combo.currentData() or default_target_for_source(source_code)

    def _current_translate_pair(self):
        source_code = _combo_data_to_ocr_language(self.lang_combo.currentData(), "en")
        target_code = None
        if self.target_lang_combo is not None:
            target_code = self.target_lang_combo.currentData()
        return source_code, default_target_for_source(source_code, target_code)

    def _refresh_language_controls_from_config(self, config):
        self._updating_language_controls = True
        try:
            if self.mode == "translate":
                source_code, target_code = _configured_ocr_translate_pair(config)
                source_idx = self.lang_combo.findData(source_code)
                if source_idx >= 0:
                    self.lang_combo.setCurrentIndex(source_idx)
                self.current_language = self.lang_combo.currentData() or source_code
                self.current_target_language = target_code
                self._populate_translate_target_combo(target_code)
            else:
                language_code = _normalize_app_language_code(
                    config.get("last_ocr_language", self.current_language),
                    "ru",
                    allow_universal=True,
                )
                idx = self.lang_combo.findData(language_code)
                if idx >= 0:
                    self.lang_combo.setCurrentIndex(idx)
                self.current_language = self.lang_combo.currentData() or language_code
        finally:
            self._updating_language_controls = False

    @staticmethod
    def _get_active_screen():
        cursor_pos = QtGui.QCursor.pos()
        return QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()

    def _capture_frozen_background(self, screen_rect):
        session_id = getattr(self, "_session_id", "unknown")
        if not self._freeze_screen_on_ocr or screen_rect.isNull():
            self._frozen_background = None
            self._frozen_background_rect = QtCore.QRect()
            logging.debug(
                f"[OCR:{session_id}] Frozen background skipped; enabled={self._freeze_screen_on_ocr}, "
                f"screen_rect=({_rect_to_text(screen_rect)})"
            )
            return

        try:
            frozen_bg = QtGui.QPixmap(screen_rect.size())
            if frozen_bg.isNull():
                self._frozen_background = None
                self._frozen_background_rect = QtCore.QRect()
                return
            frozen_bg.fill(QtCore.Qt.transparent)
            drawn_any = False
            target_screen = self._active_screen or self._get_active_screen()
            if target_screen is not None:
                shot = target_screen.grabWindow(0)
                logging.debug(
                    f"[OCR:{session_id}] Frozen grab attempt full screen; screen={_screen_to_text(target_screen)}, "
                    f"shot_null={shot.isNull()}, shot_size={shot.width()}x{shot.height()}, dpr={shot.devicePixelRatio():.3f}"
                )
                if shot.isNull():
                    shot = target_screen.grabWindow(0, 0, 0, screen_rect.width(), screen_rect.height())
                    logging.debug(
                        f"[OCR:{session_id}] Frozen grab retry; shot_null={shot.isNull()}, "
                        f"shot_size={shot.width()}x{shot.height()}, dpr={shot.devicePixelRatio():.3f}"
                    )
                if not shot.isNull():
                    painter = QtGui.QPainter(frozen_bg)
                    try:
                        painter.drawPixmap(0, 0, shot)
                    finally:
                        painter.end()
                    drawn_any = True

            if drawn_any:
                self._frozen_background = frozen_bg
                self._frozen_background_rect = screen_rect
                logging.info(
                    f"[OCR:{session_id}] Frozen background captured; rect=({_rect_to_text(screen_rect)}), "
                    f"size={frozen_bg.width()}x{frozen_bg.height()}"
                )
            else:
                self._frozen_background = None
                self._frozen_background_rect = QtCore.QRect()
                logging.warning(f"[OCR:{session_id}] Frozen background not captured; drawn_any=False")
        except Exception as e:
            logging.exception(f"[OCR:{session_id}] Failed to capture frozen OCR background: {e}")
            self._frozen_background = None
            self._frozen_background_rect = QtCore.QRect()

    def show_overlay(self):
        try:
            self._session_id = _new_ocr_session_id(self.mode)
            self.start_point = None
            self.end_point = None
            self.last_rect = None
            self._selection_started_at = None
            self._move_event_count = 0
            self._last_move_log_ts = 0.0
            self._ocr_in_progress = False
            self._ignore_ocr_results = False
            self._handling_ocr_result = False
            self._ocr_worker_session_id = None
            self._last_ocr_raw_capture = None
            self._last_ocr_pil_variants = []
            self._last_ocr_capture_meta = {}
            logging.info(f"[OCR:{self._session_id}] Showing overlay; mode={self.mode}")
            config = get_cached_ocr_config()
            self._freeze_screen_on_ocr = config.get("freeze_screen_on_ocr", False)
            self._refresh_language_controls_from_config(config)
            self.setWindowOpacity(1.0)

            # Активный монитор — тот, где находится курсор в момент запуска OCR.
            # Оверлей и заморозка работают только на нем.
            self._active_screen = self._get_active_screen()
            if self._active_screen is not None:
                overlay_rect = self._active_screen.geometry()
            else:
                overlay_rect = QtCore.QRect(0, 0, 1, 1)

            self.setGeometry(overlay_rect)
            logging.info(
                f"[OCR:{self._session_id}] Active screen: {_screen_to_text(self._active_screen)}; "
                f"overlay_rect=({_rect_to_text(overlay_rect)}); freeze={self._freeze_screen_on_ocr}; "
                f"all_screens={[ _screen_to_text(scr) for scr in QApplication.screens() ]}"
            )
            self._capture_frozen_background(overlay_rect)
            
            self.show()
            self.raise_()
            self.activateWindow()
            self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
            self._force_topmost()
            QtCore.QTimer.singleShot(80, self._force_topmost)
            QtCore.QTimer.singleShot(220, self._force_topmost)
            
            # Ensure combo is visible and raised
            self.lang_combo.setVisible(True)
            self.lang_combo.raise_()
            if self.translate_arrow_label is not None:
                self.translate_arrow_label.setVisible(True)
                self.translate_arrow_label.raise_()
            if self.target_lang_combo is not None:
                self.target_lang_combo.setVisible(True)
                self.target_lang_combo.raise_()
            QApplication.processEvents()
            self.update_combo_position()
            
            logging.info(
                f"[OCR:{self._session_id}] Controls: source_geom=({_rect_to_text(self.lang_combo.geometry())}), "
                f"source_visible={self.lang_combo.isVisible()}, "
                f"target_geom=({_rect_to_text(self.target_lang_combo.geometry()) if self.target_lang_combo else 'None'}), "
                f"source={self.lang_combo.currentData()}, target={self.target_lang_combo.currentData() if self.target_lang_combo else None}"
            )
            
            self.update()
            logging.info(f"[OCR:{self._session_id}] Overlay show command executed.")
        except Exception as e:
            logging.exception(f"[OCR:{getattr(self, '_session_id', 'unknown')}] Error showing overlay: {e}")

    def _force_topmost(self):
        """Keep the selection overlay above regular and topmost app windows."""
        try:
            self.raise_()
            if sys.platform == "win32":
                hwnd = int(self.winId())
                HWND_TOPMOST = -1
                SWP_NOSIZE = 0x0001
                SWP_NOMOVE = 0x0002
                SWP_SHOWWINDOW = 0x0040
                ctypes.windll.user32.SetWindowPos(
                    hwnd,
                    HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
                )
        except Exception:
            pass

    def resizeEvent(self, event):
        self.update_combo_position()
        super().resizeEvent(event)

    def update_combo_position(self):
        if hasattr(self, 'lang_combo') and self.lang_combo:
            # Держим позицию комбобокса на том же мониторе,
            # где был запущен оверлей.
            target_screen = self._active_screen or self._get_active_screen()
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
            controls = [self.lang_combo]
            if self.translate_arrow_label is not None and self.target_lang_combo is not None:
                controls.extend([self.translate_arrow_label, self.target_lang_combo])
            spacing = 8 if len(controls) > 1 else 0
            combo_width = sum(widget.width() for widget in controls) + spacing * (len(controls) - 1)
            
            # X in overlay coordinates = Screen Center X - Overlay X - Half Combo Width
            x = screen_center_x - overlay_top_left.x() - (combo_width // 2)
            
            # Y is just a fixed offset from the top of that screen
            y = screen_geo.top() - overlay_top_left.y() + 50 # 50px margin from top
            
            current_x = x
            for widget in controls:
                widget.move(current_x, y)
                current_x += widget.width() + spacing
            logging.info(f"Moved combo to {x}, {y} (Screen: {screen_geo})")

    def _flush_selection_paint_before_capture(self):
        session_id = getattr(self, "_session_id", "unknown")
        try:
            started = time.perf_counter()
            self.repaint()
            QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            # On Windows the compositor can lag one frame behind the widget state.
            # A tiny wait prevents capturing our own selection rectangle on small snippets.
            if not self._freeze_screen_on_ocr:
                QtCore.QThread.msleep(16)
                QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logging.info(f"[OCR:{session_id}] Selection overlay paint flushed before capture; elapsed_ms={elapsed_ms:.1f}")
        except Exception as e:
            logging.warning(f"[OCR:{session_id}] Failed to flush overlay paint before capture: {e}")

    def closeEvent(self, event):
        # Сначала убираем себя из активных оверлеев
        try:
            for active_mode, overlay in list(_ACTIVE_OVERLAYS.items()):
                if overlay is self:
                    _ACTIVE_OVERLAYS[active_mode] = None
        except Exception:
            pass
        if not self._handling_ocr_result:
            self._ignore_ocr_results = True
            self._ocr_worker_session_id = None
            self._ocr_in_progress = False
            worker = getattr(self, "ocr_worker", None)
            if worker is not None:
                try:
                    if hasattr(worker, "cancel"):
                        worker.cancel()
                    else:
                        worker.requestInterruption()
                except Exception:
                    pass
                try:
                    worker.result_ready.disconnect()
                except Exception:
                    pass
        self._frozen_background = None
        self._frozen_background_rect = QtCore.QRect()
        super().closeEvent(event)
        # Подготавливаем новый оверлей ПОСЛЕ закрытия текущего (отложенно)
        mode = self.mode
        QtCore.QTimer.singleShot(100, lambda: _safe_prepare_overlay(mode))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Затемнение отключено постоянно: выделение читается на живом/замороженном фоне.
        no_dimming = True

        # Если включена заморозка экрана — рисуем заготовленный кадр
        if self._freeze_screen_on_ocr and (self._frozen_background is None or self._frozen_background.isNull()):
            self._capture_frozen_background(self.geometry())
        if self._freeze_screen_on_ocr and self._frozen_background is not None and not self._frozen_background.isNull():
            painter.drawPixmap(0, 0, self._frozen_background)
        
        # Если не требуется затемнение, рисуем минимальный невидимый фон для перехвата мыши
        if not no_dimming:
            painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 150))
        else:
            # Минимальное затемнение (практически невидимое) для перехвата событий мыши
            # Без этого окно полностью прозрачно и клики проваливаются сквозь него
            painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 5))
        
        if self.start_point is not None and self.end_point is not None:
            rect = QtCore.QRect(self.start_point, self.end_point).normalized()
            
            # Очищаем внутреннюю область (если было затемнение)
            if not no_dimming:
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_Clear)
                painter.fillRect(rect, QtGui.QColor(0, 0, 0, 0))
                if self._freeze_screen_on_ocr and self._frozen_background is not None and not self._frozen_background.isNull():
                    painter.drawPixmap(rect, self._frozen_background, rect)
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
            if self._ocr_in_progress:
                logging.info(f"[OCR:{self._session_id}] Mouse press ignored while OCR is already running")
                return
            self.start_point = event.pos()
            self.end_point = self.start_point
            self._selection_started_at = time.monotonic()
            self._move_event_count = 0
            self._last_move_log_ts = 0.0
            logging.info(
                f"[OCR:{self._session_id}] Selection start; "
                f"local=({_point_to_text(event.pos())}), global=({_point_to_text(event.globalPos())}), "
                f"overlay=({_rect_to_text(self.geometry())}), active_screen={_screen_to_text(self._active_screen)}"
            )
            self.update()
        elif event.button() == QtCore.Qt.RightButton:
            # Правая кнопка мыши — полный выход из программы
            logging.info(f"[OCR:{self._session_id}] Right click closes overlay/app")
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
        if self.start_point is not None:
            self.end_point = event.pos()
            self._move_event_count += 1
            now = time.monotonic()
            if self._move_event_count <= 3 or self._move_event_count % 10 == 0 or now - self._last_move_log_ts > 0.5:
                rect = QtCore.QRect(self.start_point, self.end_point).normalized()
                logging.debug(
                    f"[OCR:{self._session_id}] Selection move #{self._move_event_count}; "
                    f"local=({_point_to_text(event.pos())}), global=({_point_to_text(event.globalPos())}), "
                    f"rect=({_rect_to_text(rect)})"
                )
                self._last_move_log_ts = now
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.start_point is not None and self.end_point is not None:
            self.end_point = event.pos()
            rect = QtCore.QRect(self.start_point, self.end_point).normalized()
            elapsed_ms = int((time.monotonic() - self._selection_started_at) * 1000) if self._selection_started_at else -1
            logging.info(
                f"[OCR:{self._session_id}] Selection release; "
                f"local=({_point_to_text(event.pos())}), global=({_point_to_text(event.globalPos())}), "
                f"rect=({_rect_to_text(rect)}), moves={self._move_event_count}, elapsed_ms={elapsed_ms}"
            )
            # Отклоняем случайные релизы/микроклики: они часто дают 10-15 px и гарантированно ломают OCR.
            if self._selection_started_at is None:
                logging.warning(
                    f"[OCR:{self._session_id}] Selection ignored: release without tracked mouse press; "
                    f"rect=({_rect_to_text(rect)})"
                )
                self.start_point = None
                self.end_point = None
                self._selection_started_at = None
                self.update()
                return
            min_area = 180
            if rect.width() < 8 or rect.height() < 8 or (rect.width() * rect.height()) < min_area:
                logging.info(
                    f"[OCR:{self._session_id}] Selection too small/noisy "
                    f"({rect.width()}x{rect.height()}, area={rect.width() * rect.height()}), ignoring"
                )
                self.start_point = None
                self.end_point = None
                self._selection_started_at = None
                self.update()
                return
            self.last_rect = rect
            logging.info(f"[OCR:{self._session_id}] Selection accepted; rect=({_rect_to_text(rect)})")
            self._ocr_in_progress = True
            self.start_point = None
            self.end_point = None
            self._selection_started_at = None
            self.update()
            self._flush_selection_paint_before_capture()
            self.capture_and_copy(rect)
        elif event.button() == QtCore.Qt.LeftButton:
            logging.warning(
                f"[OCR:{self._session_id}] Selection release ignored because start/end is missing; "
                f"start={_point_to_text(self.start_point)}, end={_point_to_text(self.end_point)}, "
                f"local=({_point_to_text(event.pos())}), global=({_point_to_text(event.globalPos())})"
            )

    def on_language_changed(self, index):
        """Сохраняет выбранный язык в конфиг при изменении"""
        if getattr(self, "_updating_language_controls", False):
            return
        combo_data = self.lang_combo.currentData()
        language_code = _combo_data_to_ocr_language(combo_data, "ru")
        if language_code:
            self.current_language = language_code
            updates = {"last_ocr_language": language_code}
            if self.mode == "translate":
                source_code = _combo_data_to_ocr_language(combo_data, "en")
                if self.sender() is self.lang_combo:
                    self._updating_language_controls = True
                    try:
                        self._populate_translate_target_combo(self.current_target_language)
                    finally:
                        self._updating_language_controls = False
                source_code, target_code = self._current_translate_pair()
                self.current_language = source_code
                self.current_target_language = target_code
                updates["last_ocr_language"] = "universal" if source_code == "auto" else source_code
                updates["ocr_translate_source_language"] = source_code
                updates["ocr_translate_target_language"] = target_code
            if _write_ocr_config_updates(updates):
                logging.info(f"Saved OCR language: {updates['last_ocr_language']}")

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
        app_root = get_portable_dir()
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

    @staticmethod
    def _open_windows_language_settings():
        try:
            if sys.platform == "win32":
                os.startfile("ms-settings:regionlanguage")
                return True
        except Exception as e:
            logging.warning(f"Failed to open Windows language settings: {e}")
        return False

    @staticmethod
    def _apply_message_box_theme(msg, theme):
        if theme == "Темная":
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #111216;
                    color: #f4f6fb;
                }
                QMessageBox QLabel {
                    color: #f4f6fb;
                    font-size: 13px;
                    line-height: 1.35;
                }
                QPushButton {
                    background-color: #7A5FA1;
                    color: #ffffff;
                    border: 1px solid #9b7fca;
                    border-radius: 7px;
                    padding: 7px 16px;
                    min-width: 110px;
                }
                QPushButton:hover {
                    background-color: #8B70B2;
                }
            """)
        else:
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #ffffff;
                    color: #202124;
                }
                QMessageBox QLabel {
                    color: #202124;
                    font-size: 13px;
                    line-height: 1.35;
                }
                QPushButton {
                    background-color: #7A5FA1;
                    color: #ffffff;
                    border: none;
                    border-radius: 7px;
                    padding: 7px 16px;
                    min-width: 110px;
                }
                QPushButton:hover {
                    background-color: #8B70B2;
                }
            """)

    def _show_windows_ocr_missing_notice(self, language_code, win_lang_tag, fallback_available):
        if language_code == "universal":
            return

        notice_key = (language_code, win_lang_tag, bool(fallback_available), bool(_WINRT_AVAILABLE))
        if notice_key in _WINDOWS_OCR_MISSING_NOTICE_SHOWN:
            return
        _WINDOWS_OCR_MISSING_NOTICE_SHOWN.add(notice_key)

        config = get_cached_ocr_config()
        interface_lang = config.get("interface_language", "ru")
        is_ru = interface_lang == "ru"
        language_name = language_display_name(language_code, interface_lang)
        available_tags = _get_available_windows_ocr_language_tags()

        logging.info(
            f"[OCR:{getattr(self, '_session_id', 'unknown')}] Showing Windows OCR missing notice; "
            f"language={language_code}, win_lang_tag={win_lang_tag}, fallback_available={fallback_available}, "
            f"winrt_available={_WINRT_AVAILABLE}, available_windows_ocr_languages={available_tags}"
        )

        msg = QMessageBox(self)
        msg.setWindowIcon(QtGui.QIcon(resource_path("icons/icon.ico")))
        msg.setIcon(QMessageBox.Information if fallback_available else QMessageBox.Warning)
        msg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        try:
            msg.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        except Exception:
            pass

        if is_ru:
            msg.setWindowTitle("Пакет Windows OCR не найден")
            if not _WINRT_AVAILABLE:
                msg.setText("Windows OCR сейчас недоступен.")
                details = (
                    "Компоненты Windows OCR не загрузились. "
                    "Можно продолжить через Tesseract, если он установлен."
                )
            else:
                msg.setText(f"Windows OCR не поддерживает язык: {language_name} ({win_lang_tag}).")
                details = (
                    "Скорее всего, в Windows не установлен языковой пакет распознавания. "
                    "Можно открыть настройки языка Windows и установить нужный язык."
                )
            if fallback_available:
                details += "\n\nСейчас распознавание продолжится через Tesseract."
            else:
                details += "\n\nTesseract не найден, поэтому распознавание для этого языка остановлено."
            open_text = "Открыть настройки Windows"
            continue_text = "Продолжить через Tesseract"
            close_text = "Закрыть"
        else:
            msg.setWindowTitle("Windows OCR pack missing")
            if not _WINRT_AVAILABLE:
                msg.setText("Windows OCR is not available right now.")
                details = (
                    "Windows OCR components failed to load. "
                    "The app can continue with Tesseract if it is installed."
                )
            else:
                msg.setText(f"Windows OCR does not support: {language_name} ({win_lang_tag}).")
                details = (
                    "The Windows OCR language pack is probably not installed. "
                    "You can open Windows language settings and add the required language."
                )
            if fallback_available:
                details += "\n\nRecognition will continue with Tesseract now."
            else:
                details += "\n\nTesseract was not found, so recognition for this language is stopped."
            open_text = "Open Windows settings"
            continue_text = "Continue with Tesseract"
            close_text = "Close"

        msg.setInformativeText(details)
        open_btn = msg.addButton(open_text, QMessageBox.ActionRole)
        if fallback_available:
            msg.addButton(continue_text, QMessageBox.AcceptRole)
        else:
            msg.addButton(close_text, QMessageBox.RejectRole)
        self._apply_message_box_theme(msg, config.get("theme", "Темная"))
        msg.exec_()

        if msg.clickedButton() == open_btn:
            self._open_windows_language_settings()

    @staticmethod
    def _configure_tesseract_data(tess_cmd, tess_lang):
        _prepare_tesseract_data(tess_cmd, tess_lang)

    # Сохраняем ссылку на данные изображения, чтобы QImage не потерял буфер
    _ocr_image_data = None

    def _select_target_screen_for_rect(self, global_rect):
        center = global_rect.center()
        screen = QApplication.screenAt(center)
        if screen is not None:
            return screen, "center"
        for candidate in QApplication.screens():
            if candidate.geometry().intersects(global_rect):
                return candidate, "intersects"
        return self._active_screen or self.screen or QApplication.primaryScreen(), "fallback"

    def _grab_screenshot_region(self, target_screen, global_rect):
        session_id = getattr(self, "_session_id", "unknown")
        if target_screen is None:
            logging.error(f"[OCR:{session_id}] Cannot grab screenshot: target_screen is None")
            return QtGui.QPixmap(), "", QtCore.QRect()

        screen_geo = target_screen.geometry()
        clipped_global_rect = global_rect.intersected(screen_geo)
        if clipped_global_rect.isNull() or clipped_global_rect.width() <= 0 or clipped_global_rect.height() <= 0:
            logging.error(
                f"[OCR:{session_id}] Cannot grab screenshot: selected rect outside target screen; "
                f"global=({_rect_to_text(global_rect)}), screen=({_rect_to_text(screen_geo)})"
            )
            return QtGui.QPixmap(), "", QtCore.QRect()

        if clipped_global_rect != global_rect:
            logging.warning(
                f"[OCR:{session_id}] Selection clipped to target screen; original=({_rect_to_text(global_rect)}), "
                f"clipped=({_rect_to_text(clipped_global_rect)}), screen=({_rect_to_text(screen_geo)})"
            )

        local_rect = QtCore.QRect(clipped_global_rect)
        local_rect.translate(-screen_geo.x(), -screen_geo.y())
        attempts = [
            ("screen-local", local_rect),
            ("global-fallback", clipped_global_rect),
        ]

        for attempt_name, attempt_rect in attempts:
            if attempt_rect.width() <= 0 or attempt_rect.height() <= 0:
                continue
            started = time.perf_counter()
            pixmap = target_screen.grabWindow(
                0,
                attempt_rect.x(),
                attempt_rect.y(),
                attempt_rect.width(),
                attempt_rect.height(),
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logging.info(
                f"[OCR:{session_id}] grabWindow attempt={attempt_name}; request=({_rect_to_text(attempt_rect)}), "
                f"screen=({_screen_to_text(target_screen)}), elapsed_ms={elapsed_ms:.1f}, "
                f"null={pixmap.isNull()}, pixmap={pixmap.width()}x{pixmap.height()}, "
                f"pixmap_dpr={pixmap.devicePixelRatio():.3f}"
            )
            if not pixmap.isNull() and pixmap.width() > 0 and pixmap.height() > 0:
                return pixmap, attempt_name, clipped_global_rect

        return QtGui.QPixmap(), "", clipped_global_rect

    def _run_tesseract_ocr_image(self, pil_image, tess_lang, context):
        tess_cmd = self.get_tesseract_cmd()
        if not tess_cmd:
            logging.error(f"[OCR:{self._session_id}] Tesseract executable not found for {context}.")
            return None
        return _run_tesseract_ocr_image_with_cmd(
            pil_image,
            tess_cmd,
            tess_lang,
            context,
            getattr(self, "_session_id", "unknown"),
        )

    @staticmethod
    def _score_tesseract_text(text):
        return _score_recognized_text(text)

    def _recognize_preprocessed_with_tesseract(self, pil_image, language_code, context):
        return self._recognize_tesseract_variants([("primary", pil_image)], language_code, context)

    def _recognize_tesseract_variants(self, pil_variants, language_code, context):
        tess_cmd = self.get_tesseract_cmd()
        tess_lang = tesseract_language_code(language_code)
        return _recognize_tesseract_variants_with_cmd(
            pil_variants,
            tess_cmd,
            tess_lang,
            context,
            getattr(self, "_session_id", "unknown"),
        )

    def _start_tesseract_worker(self, pil_variants, language_code, context, session_id):
        tess_cmd = self.get_tesseract_cmd()
        if not tess_cmd:
            logging.error(f"[OCR:{session_id}] Tesseract executable not found for async context={context}.")
            self.handle_ocr_result("", session_id)
            return

        self.ocr_worker = TesseractOCRWorker(
            pil_variants,
            language_code,
            tess_cmd,
            context,
            session_id,
        )
        self._ocr_worker_session_id = session_id
        self.ocr_worker.result_ready.connect(lambda text, sid=session_id: self.handle_ocr_result(text, sid))
        self.ocr_worker.finished.connect(self.ocr_worker.deleteLater)
        self.ocr_worker.start()

    def _persist_failed_ocr_artifacts(self, reason):
        session_id = getattr(self, "_session_id", "unknown")
        saved = []
        try:
            raw_capture = getattr(self, "_last_ocr_raw_capture", None)
            raw_path = _save_pixmap_debug(raw_capture, session_id, f"failed_{reason}_raw_capture", force=True)
            if raw_path:
                saved.append(raw_path)
            for label, image in getattr(self, "_last_ocr_pil_variants", []) or []:
                path = _save_pil_debug(image, session_id, f"failed_{reason}_{label}", force=True)
                if path:
                    saved.append(path)
            logging.warning(
                f"[OCR:{session_id}] OCR failure artifacts saved; reason={reason}, "
                f"count={len(saved)}, meta={getattr(self, '_last_ocr_capture_meta', {})}, files={saved}"
            )
        except Exception as e:
            logging.warning(f"[OCR:{session_id}] Could not persist failed OCR artifacts: {e}")

    def capture_and_copy(self, rect):
        session_id = getattr(self, "_session_id", "unknown")
        # rect — в локальных координатах overlay-виджета
        global_top_left = self.mapToGlobal(rect.topLeft())
        global_bottom_right = self.mapToGlobal(rect.bottomRight())
        global_rect = QtCore.QRect(global_top_left, global_bottom_right)

        logging.info(
            f"[OCR:{session_id}] capture_and_copy start; "
            f"local_rect=({_rect_to_text(rect)}), global_rect=({_rect_to_text(global_rect)}), "
            f"overlay=({_rect_to_text(self.geometry())})"
        )

        # Находим экран, содержащий центр выделенной области
        target_screen, screen_reason = self._select_target_screen_for_rect(global_rect)
        dpr = target_screen.devicePixelRatio() if target_screen is not None else 1.0
        logging.info(
            f"[OCR:{session_id}] target screen selected by {screen_reason}; "
            f"center=({_point_to_text(global_rect.center())}), screen={_screen_to_text(target_screen)}"
        )
        screenshot = QtGui.QPixmap()
        grab_attempt = ""
        captured_global_rect = global_rect
        if (
            self._freeze_screen_on_ocr
            and self._frozen_background is not None
            and not self._frozen_background.isNull()
        ):
            frozen_rect = rect.intersected(self._frozen_background.rect())
            if not frozen_rect.isNull() and frozen_rect.width() > 0 and frozen_rect.height() > 0:
                screenshot = self._frozen_background.copy(frozen_rect)
                grab_attempt = "frozen-background"
                logging.info(
                    f"[OCR:{session_id}] Captured from frozen background; "
                    f"request=({_rect_to_text(rect)}), clipped=({_rect_to_text(frozen_rect)}), "
                    f"pixmap={screenshot.width()}x{screenshot.height()}"
                )
            else:
                logging.warning(
                    f"[OCR:{session_id}] Frozen background capture skipped; "
                    f"selection outside frozen pixmap: rect=({_rect_to_text(rect)}), "
                    f"frozen_rect=({_rect_to_text(self._frozen_background.rect())})"
                )
        if screenshot.isNull():
            screenshot, grab_attempt, captured_global_rect = self._grab_screenshot_region(target_screen, global_rect)

        if screenshot.isNull():
            logging.error(f"[OCR:{session_id}] Failed to grab screenshot (result is null)")
            self._ocr_in_progress = False
            return

        self._last_ocr_raw_capture = screenshot.copy()
        self._last_ocr_capture_meta = {
            "local_rect": _rect_to_text(rect),
            "global_rect": _rect_to_text(global_rect),
            "grab_attempt": grab_attempt,
            "target_screen": _screen_to_text(target_screen),
            "frozen": bool(self._freeze_screen_on_ocr),
        }
        _save_pixmap_debug(screenshot, session_id, "raw_capture")

        qimage = screenshot.toImage()
        raw_qimage = qimage.copy()
        orig_w, orig_h = qimage.width(), qimage.height()
        logging.info(
            f"[OCR:{session_id}] Captured qimage={orig_w}x{orig_h}; screen_dpr={dpr:.3f}; "
            f"pixmap_dpr={screenshot.devicePixelRatio():.3f}; attempt={grab_attempt}; "
            f"captured_global=({_rect_to_text(captured_global_rect)}), qimage_format={qimage.format()}"
        )

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
        raw_pil_for_ocr = pil_image.convert('L')

        # --- 1. Определяем тёмный/светлый фон ---
        gray = pil_image.convert('L')
        stat = ImageStat.Stat(gray)
        mean_brightness = stat.mean[0]
        is_dark_bg = mean_brightness < 128
        logging.info(
            f"[OCR:{session_id}] Raw image stats: size={pil_image.width}x{pil_image.height}, "
            f"mean={mean_brightness:.1f}, extrema={stat.extrema[0]}, mode={pil_image.mode}, dark_bg={is_dark_bg}"
        )

        # --- 2. Если тёмный фон — инвертируем для OCR (чёрный текст на белом) ---
        if is_dark_bg:
            pil_image = ImageOps.invert(pil_image.convert('RGB')).convert('RGBA')
            logging.info(f"[OCR:{session_id}] Dark background detected (mean={mean_brightness:.0f}), inverted")

        # --- 3. Конвертация в grayscale ---
        pil_image = pil_image.convert('L')
        pil_image = ImageOps.autocontrast(pil_image, cutoff=1)

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
            logging.info(f"[OCR:{session_id}] Scaled {scale_factor:.1f}x -> {new_w}x{new_h}")

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
        logging.info(
            f"[OCR:{session_id}] Preprocess contrast stats: stddev={stddev:.1f}, "
            f"contrast_factor={contrast_factor:.2f}, source_height={height}"
        )

        enhancer = ImageEnhance.Contrast(pil_image)
        pil_image = enhancer.enhance(contrast_factor)

        # --- 6. Лёгкое повышение резкости (не агрессивное) ---
        enhancer = ImageEnhance.Sharpness(pil_image)
        pil_image = enhancer.enhance(1.5)

        def edge_mean_luminance(image):
            probe = image.convert('L')
            w, h = probe.size
            band = max(1, min(w, h, max(2, min(w, h) // 18)))
            crops = [
                probe.crop((0, 0, w, band)),
                probe.crop((0, max(0, h - band), w, h)),
                probe.crop((0, 0, band, h)),
                probe.crop((max(0, w - band), 0, w, h)),
            ]
            values = [ImageStat.Stat(crop).mean[0] for crop in crops if crop.size[0] > 0 and crop.size[1] > 0]
            return sum(values) / len(values) if values else ImageStat.Stat(probe).mean[0]

        def add_ocr_border_and_normalize(image, label):
            # OCR стабильнее, когда фон по краям светлый, а текст темный.
            normalized = image.convert('L')
            edge_mean = edge_mean_luminance(normalized)
            overall_mean = ImageStat.Stat(normalized).mean[0]
            if edge_mean < 128:
                normalized = ImageOps.invert(normalized)
                logging.info(
                    f"[OCR:{session_id}] Polarity normalized for {label}: inverted "
                    f"(edge_mean={edge_mean:.1f}, overall_mean={overall_mean:.1f})"
                )
                edge_mean = edge_mean_luminance(normalized)
            else:
                logging.info(
                    f"[OCR:{session_id}] Polarity kept for {label}: "
                    f"edge_mean={edge_mean:.1f}, overall_mean={overall_mean:.1f}"
                )
            border_fill = 255 if edge_mean >= 128 else 0
            border_size = min(32, max(10, int(normalized.height * 0.08)))
            normalized = ImageOps.expand(normalized, border=border_size, fill=border_fill)
            logging.info(
                f"[OCR:{session_id}] Preprocessed variant {label}: {normalized.width}x{normalized.height}; "
                f"border_fill={border_fill}, border_size={border_size}, "
                f"extrema={ImageStat.Stat(normalized).extrema[0]}"
            )
            _save_pil_debug(normalized, session_id, f"preprocessed_{label}")
            return normalized

        def pil_l_to_qimage(image):
            image = image.convert('L')
            data = image.tobytes()
            qimg = QtGui.QImage(data, image.width, image.height, image.width, QtGui.QImage.Format_Grayscale8)
            return qimg.copy()

        # --- 7. Создаем несколько OCR-вариантов вместо одной рискованной обработки ---
        raw_soft_pil = add_ocr_border_and_normalize(raw_pil_for_ocr, "raw")
        enhanced_pil = add_ocr_border_and_normalize(pil_image.copy(), "enhanced")
        ocr_pil_variants = [("raw", raw_soft_pil), ("enhanced", enhanced_pil)]

        if height < 120:
            binary_pil = pil_image.copy()
            try:
                import numpy as np
                arr = np.array(binary_pil)
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
                binary_pil = binary_pil.point(lambda x: 255 if x > threshold else 0, 'L')
                logging.info(f"[OCR:{session_id}] Otsu binarization for binary variant: threshold={threshold}")
            except ImportError:
                binary_pil = binary_pil.point(lambda x: 255 if x > 128 else 0, 'L')
                logging.info(f"[OCR:{session_id}] Numpy unavailable; binary variant threshold=128")
            binary_pil = add_ocr_border_and_normalize(binary_pil, "binary")
            ocr_pil_variants.append(("binary", binary_pil))
        self._last_ocr_pil_variants = list(ocr_pil_variants)

        # Основной вариант для Tesseract fallback: бинарный для мелкого текста, мягкий для крупного.
        primary_label, pil_image = ocr_pil_variants[-1] if height < 120 else ocr_pil_variants[0]
        qimage = pil_l_to_qimage(pil_image)
        logging.info(
            f"[OCR:{session_id}] Primary preprocessed variant={primary_label}; "
            f"final={pil_image.width}x{pil_image.height}"
        )
        
        combo_data = self.lang_combo.currentData()
        language_code = _combo_data_to_ocr_language(combo_data, "ru")
        self.current_language = language_code
        
        # Сохраняем выбранный язык в конфигурации
        config = get_cached_ocr_config()
        updates = {}
        if config.get("last_ocr_language") != language_code:
            updates["last_ocr_language"] = language_code
        if self.mode == "translate":
            source_code, target_code = self._current_translate_pair()
            self.current_language = source_code
            self.current_target_language = target_code
            language_code = "universal" if source_code == "auto" else source_code
            updates["last_ocr_language"] = language_code
            updates["ocr_translate_source_language"] = source_code
            updates["ocr_translate_target_language"] = target_code
        if updates:
            _write_ocr_config_updates(updates)

        # Determine which OCR engine to use
        ocr_engine_type = self.get_ocr_engine().lower()
        logging.info(
            f"[OCR:{session_id}] Using OCR engine: {ocr_engine_type.upper()}; "
            f"mode={self.mode}, ocr_language={language_code}, "
            f"translate_pair={self._current_translate_pair() if self.mode == 'translate' else None}"
        )

        if ocr_engine_type == "tesseract":
            # Пробуем несколько подготовленных вариантов: один фильтр часто спасает один кейс и ломает другой.
            tess_variants = [(label, image.convert('L') if image.mode != 'L' else image) for label, image in ocr_pil_variants]
            self._start_tesseract_worker(tess_variants, language_code, "primary", session_id)
            return  # Не использовать Windows OCR ниже

        # По умолчанию используем Windows OCR (без PIL)
        # Используем универсальный OCR если выбрано "universal" (AUTO)
        use_universal = (language_code == "universal")
        if use_universal:
            logging.info(f"[OCR:{session_id}] Running Windows OCR in UNIVERSAL mode (auto-detect language)")
        else:
            logging.info(f"[OCR:{session_id}] Running Windows OCR for language: {language_code.upper()}")
            win_lang_tag = windows_ocr_tag(language_code)
            windows_engine = _get_windows_ocr_engine(win_lang_tag)
            if windows_engine is None:
                tess_cmd = self.get_tesseract_cmd()
                self._show_windows_ocr_missing_notice(
                    language_code,
                    win_lang_tag,
                    fallback_available=bool(tess_cmd),
                )
                if not tess_cmd:
                    logging.warning(
                        f"[OCR:{session_id}] Windows OCR does not support {win_lang_tag} and Tesseract is not available; "
                        "OCR stopped before worker start."
                    )
                    self.close()
                    return
                logging.info(
                    f"[OCR:{session_id}] Windows OCR does not support {win_lang_tag} on this machine; "
                    "using Tesseract directly."
                )
                tess_variants = [(label, image.convert('L') if image.mode != 'L' else image) for label, image in ocr_pil_variants]
                self._start_tesseract_worker(
                    tess_variants,
                    language_code,
                    "windows-unsupported-direct",
                    session_id,
                )
                return
        
        windows_qimage_attempts = [("raw", raw_qimage)]
        for variant_label, variant_pil in ocr_pil_variants:
            windows_qimage_attempts.append((variant_label, pil_l_to_qimage(variant_pil)))

        bitmap_attempts = []
        for attempt_label, attempt_qimage in windows_qimage_attempts:
            attempt_qimage = _limit_qimage_for_windows_ocr(attempt_qimage, session_id, attempt_label)
            bitmap = qimage_to_softwarebitmap(attempt_qimage)
            logging.debug(f"[OCR:{session_id}] SoftwareBitmap created for {attempt_label}: {bitmap}")
            if bitmap is not None:
                bitmap_attempts.append((attempt_label, bitmap))

        if not bitmap_attempts:
            logging.error(f"[OCR:{session_id}] Failed to create SoftwareBitmap for every OCR attempt")
            if self.get_tesseract_cmd():
                logging.info(f"[OCR:{session_id}] Falling back to Tesseract after SoftwareBitmap conversion failure")
                tess_variants = [(label, image.convert('L') if image.mode != 'L' else image) for label, image in ocr_pil_variants]
                self._start_tesseract_worker(tess_variants, language_code, "windows-bitmap-fallback", session_id)
            else:
                self.handle_ocr_result("", session_id)
            return
        
        # Create worker with Tesseract fallback capability
        self.ocr_worker = OCRWorker(
            bitmap_attempts[0][1],
            language_code,
            use_universal=use_universal,
            attempts=bitmap_attempts,
            session_id=session_id,
        )
        
        # Pass the QImage for Tesseract fallback if needed
        self.ocr_worker.fallback_pil_variants = [
            (label, image.convert('L') if image.mode != 'L' else image)
            for label, image in ocr_pil_variants
        ]
        self.ocr_worker.tesseract_cmd = self.get_tesseract_cmd()
        self.ocr_worker.tesseract_fallback_enabled = bool(self.ocr_worker.tesseract_cmd)
        
        self._ocr_worker_session_id = session_id
        self.ocr_worker.result_ready.connect(lambda text, sid=session_id: self.handle_ocr_result(text, sid))
        self.ocr_worker.finished.connect(self.ocr_worker.deleteLater)
        self.ocr_worker.start()

    def handle_ocr_result(self, text, session_id=None):
        try:
            current_session = getattr(self, "_session_id", "unknown")
            expected_session = getattr(self, "_ocr_worker_session_id", None)
            if self._ignore_ocr_results or (session_id is not None and session_id != current_session):
                logging.info(
                    f"[OCR:{current_session}] Ignoring stale OCR result; "
                    f"result_session={session_id}, expected={expected_session}, ignore={self._ignore_ocr_results}"
                )
                return
            if expected_session is not None and session_id is not None and session_id != expected_session:
                logging.info(
                    f"[OCR:{current_session}] Ignoring OCR result for inactive worker session; "
                    f"result_session={session_id}, expected={expected_session}"
                )
                return
            self._handling_ocr_result = True
            logging.info(
                f"[OCR:{getattr(self, '_session_id', 'unknown')}] handle_ocr_result; "
                f"text_len={len(text or '')}, preview={_text_preview(text)}"
            )
            self._handle_ocr_result_inner(text)
        except Exception as e:
            logging.exception(f"[OCR:{getattr(self, '_session_id', 'unknown')}] Critical error in handle_ocr_result: {e}")
            # Гарантированно закрываем оверлей при любом краше
            try:
                self.close()
            except Exception:
                pass
        finally:
            self._handling_ocr_result = False
            self._ocr_in_progress = False
            self._ocr_worker_session_id = None

    def _handle_ocr_result_inner(self, text):
        session_id = getattr(self, "_session_id", "unknown")
        if not text and hasattr(self, 'ocr_worker') and hasattr(self.ocr_worker, 'qimage'):
            # If Windows OCR failed, try Tesseract as fallback
            logging.info(f"[OCR:{session_id}] Windows OCR returned empty result, attempting Tesseract fallback...")
            try:
                from PIL import Image

                pil_variants = getattr(self.ocr_worker, "fallback_pil_variants", None)
                if not pil_variants:
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
                    pil_variants = [("qimage", pil_image)]

                lang_code = getattr(self.ocr_worker, "language_code", None) or _combo_data_to_ocr_language(
                    self.lang_combo.currentData(),
                    "ru",
                )

                tess_cmd = self.get_tesseract_cmd()
                if tess_cmd:
                    text = self._recognize_tesseract_variants(pil_variants, lang_code, "windows-empty-fallback")
                else:
                    logging.warning(f"[OCR:{session_id}] Tesseract not found for fallback.")
            except Exception as e:
                logging.exception(f"[OCR:{session_id}] Tesseract fallback failed: {e}")

        if text:
            if self.mode == "translate":
                from translater import translate_text
                source_code, target_code = self._current_translate_pair()
                if source_code == "auto":
                    detected_source = detect_language_code(text)
                    if detected_source:
                        source_code = detected_source
                    if source_code == target_code:
                        target_code = default_target_for_source(source_code)
                logging.info(
                    f"[OCR:{session_id}] Translating from {source_code.upper()} to {target_code.upper()}; "
                    f"source_len={len(text)}"
                )
                try:
                    translated_text = translate_text(text, source_code, target_code)
                    if translated_text:
                        logging.info(
                            f"[OCR:{session_id}] Translation completed successfully; "
                            f"len={len(translated_text)}, preview={_text_preview(translated_text)}"
                        )
                    else:
                        logging.warning(f"[OCR:{session_id}] Translation returned empty result")
                except Exception as e:
                    logging.exception(f"[OCR:{session_id}] Translation error: {e}")
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
                    logging.info(
                        f"[OCR:{session_id}] Recognized text copied; len={len(text)}, "
                        f"preview={_text_preview(text)}"
                    )
                    # НЕ сохраняем обычный текст в историю переводов!
                    self.close()
                except Exception as e:
                    logging.exception(f"[OCR:{session_id}] OCR result handling error: {e}")
        else:
            logging.info(f"[OCR:{session_id}] OCR did not recognize text.")
            self._persist_failed_ocr_artifacts("empty_result")
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

            lang_tag = windows_ocr_tag(self.language_code)
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
        saved_src = _normalize_app_language_code(
            config.get("ocr_translate_source_language") or config.get("fullscreen_translate_from"),
            "en",
        )
        saved_tgt = default_target_for_source(
            saved_src,
            config.get("ocr_translate_target_language") or config.get("fullscreen_translate_to"),
        )

        # Capture screenshot from the screen where cursor is
        cursor_pos = QtGui.QCursor.pos()
        target_screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        geo = target_screen.geometry()

        self.screenshot = target_screen.grabWindow(0, 0, 0, geo.width(), geo.height())
        self._ocr_scale_x = (self.screenshot.width() / geo.width()) if geo.width() and not self.screenshot.isNull() else 1.0
        self._ocr_scale_y = (self.screenshot.height() / geo.height()) if geo.height() and not self.screenshot.isNull() else 1.0
        self.setGeometry(geo)

        # --- Комбо-бокс выбора направления перевода (как в обычном overlay) ---
        self.lang_combo = QtWidgets.QComboBox(self)
        for source_code, target_code in _ocr_translate_options_from_config(config):
            self.lang_combo.addItem(
                QtGui.QIcon(resource_path(language_icon_path(source_code))),
                f"{language_short_label(source_code)} \u2192 {language_short_label(target_code)}",
                (source_code, target_code),
            )
        # Восстанавливаем последний выбор
        default_idx = _find_translate_pair_index(self.lang_combo, saved_src, saved_tgt)
        if default_idx < 0:
            default_idx = _find_translate_pair_index(self.lang_combo, saved_src)
        if default_idx < 0:
            default_idx = 0
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
        self.lang_combo.setFixedSize(190, 48)

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
        lang_data = self.lang_combo.currentData()
        self.src_lang, self.tgt_lang = _combo_data_to_translate_pair(lang_data, get_cached_ocr_config())
        self.ocr_language = self.src_lang

        # Сохраняем выбор в конфиг
        _write_ocr_config_updates({
            "fullscreen_translate_from": self.src_lang,
            "fullscreen_translate_to": self.tgt_lang,
            "ocr_translate_source_language": self.src_lang,
            "ocr_translate_target_language": self.tgt_lang,
            "last_ocr_language": self.src_lang,
        })

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
                        (
                            QtCore.QRectF(
                                x / self._ocr_scale_x,
                                y / self._ocr_scale_y,
                                w / self._ocr_scale_x,
                                h / self._ocr_scale_y,
                            ),
                            orig,
                            tr,
                        )
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
