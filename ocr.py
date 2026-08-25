import sys
import asyncio
import os
import json
import logging
import logging.handlers
import subprocess
import tempfile
from datetime import datetime
from dataclasses import dataclass
import shutil
import time
import re

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
from styled_dialogs import NativeDialogFrameFilter, StyledMessageBox, install_qt_exception_guard

QMessageBox = StyledMessageBox
from languages import (
    LANGUAGES as APP_LANGUAGES,
    default_target_for_source,
    detect_language_code,
    easyocr_language_codes,
    language_likelihood_score,
    language_display_name,
    language_icon_path,
    language_short_label,
    ocr_translate_options,
    tesseract_language_code,
    windows_ocr_tag,
)
import platform_support
import portable_paths

APP_LANGUAGE_CODES = {language.code for language in APP_LANGUAGES}

OCR_UI_TEXT = {
    "en": {
        "tess_download_data": "Tesseract: downloading {language} language data...", "tess_downloading": "Tesseract: downloading {language}... {percent}%",
        "tess_ready": "Tesseract: {language} language data is ready", "tess_retrying": "Tesseract: retrying {language} download ({attempt}/{total})...", "recognizing": "Recognizing text...",
        "win_missing_title": "Windows OCR pack missing", "win_unavailable": "Windows OCR is not available right now.",
        "win_components": "Windows OCR components failed to load. The app can continue with Tesseract if it is installed.",
        "win_unsupported": "Windows OCR does not support: {language} ({tag}).",
        "win_pack": "The Windows OCR language pack is probably not installed. You can open Windows language settings and add the required language.",
        "win_continue": "Recognition will continue with Tesseract now.", "win_stopped": "Tesseract was not found, so recognition for this language is stopped.",
        "open_windows": "Open Windows settings", "continue_tesseract": "Continue with Tesseract", "close": "Close",
        "recognition_failed": "Recognition failed", "engine_unavailable": "{engine} is unavailable",
        "engine_unavailable_info": "The {engine} engine is not installed or failed to load.\n\nTry:\n• Choose {engine} in settings and install the local package\n• Choose another OCR engine in settings",
        "engine_unreliable": "{engine} did not find reliable text",
        "engine_unreliable_info": "{engine} did not detect text with enough confidence.\n\nTry:\n• Check the selected recognition language\n• Select a tighter, higher-contrast area\n• Switch to another OCR engine",
        "auto_unreliable": "Text was not recognized reliably",
        "auto_unreliable_info": "Weak results were filtered out so noise is not sent to the translator.\n\nTry:\n• Select the text area more tightly, without extra borders or background\n• Choose the specific source language\n• Try another OCR engine or install the Windows OCR language pack",
        "not_recognized": "😔 Text not recognized", "not_recognized_info": "Try:\n• Select an area with larger text\n• Make sure the text has good contrast\n• Choose a different OCR engine in settings",
        "translate": "Translate", "ocr_init_failed": "OCR initialization failed", "screen_no_text": "No text recognized on screen",
        "translation_failed": "Translation failed", "translating_screen": "Translating screen...", "fullscreen_hint": "ESC — close  |  RMB — drag",
        "no_installed_languages": "No OCR languages installed",
        "no_installed_translation_pairs": "No installed translation pairs",
        "install_languages_first": "Install a language first in Settings → Language packages.",
        "swap_languages": "Swap languages",
    },
    "ru": {
        "tess_download_data": "Tesseract: скачиваю языковой пакет {language}...", "tess_downloading": "Tesseract: скачиваю {language}... {percent}%",
        "tess_ready": "Tesseract: пакет {language} готов", "tess_retrying": "Tesseract: повторная загрузка {language} ({attempt}/{total})...", "recognizing": "Распознаю текст...",
        "win_missing_title": "Пакет Windows OCR не найден", "win_unavailable": "Windows OCR сейчас недоступен.",
        "win_components": "Компоненты Windows OCR не загрузились. Можно продолжить через Tesseract, если он установлен.",
        "win_unsupported": "Windows OCR не поддерживает язык: {language} ({tag}).",
        "win_pack": "Скорее всего, в Windows не установлен языковой пакет распознавания. Можно открыть настройки языка Windows и установить нужный язык.",
        "win_continue": "Сейчас распознавание продолжится через Tesseract.", "win_stopped": "Tesseract не найден, поэтому распознавание для этого языка остановлено.",
        "open_windows": "Открыть настройки Windows", "continue_tesseract": "Продолжить через Tesseract", "close": "Закрыть",
        "recognition_failed": "Не удалось распознать", "engine_unavailable": "{engine} недоступен",
        "engine_unavailable_info": "Движок {engine} не установлен или не загрузился.\n\nПопробуйте:\n• Выбрать {engine} в настройках и установить локальный пакет\n• Выбрать другой OCR-движок в настройках",
        "engine_unreliable": "{engine} не нашёл надёжный текст",
        "engine_unreliable_info": "{engine} не обнаружил текст с достаточной уверенностью.\n\nПопробуйте:\n• Проверить выбранный язык распознавания\n• Выделить область точнее и контрастнее\n• Переключиться на другой OCR-движок",
        "auto_unreliable": "Текст не распознан надёжно",
        "auto_unreliable_info": "Слабые результаты отфильтрованы, чтобы не отправлять мусор в переводчик.\n\nПопробуйте:\n• Выделить область точнее, без лишних рамок и фона\n• Выбрать конкретный язык текста\n• Попробовать другой OCR-движок или установить языковой пакет Windows OCR",
        "not_recognized": "😔 Текст не распознан", "not_recognized_info": "Попробуйте:\n• Выделить область с более крупным текстом\n• Убедиться, что текст контрастный\n• Выбрать другой OCR-движок в настройках",
        "translate": "Перевести", "ocr_init_failed": "Не удалось запустить OCR", "screen_no_text": "Текст на экране не распознан",
        "translation_failed": "Ошибка перевода", "translating_screen": "Перевод экрана...", "fullscreen_hint": "ESC — закрыть  |  ПКМ — перетащить",
        "no_installed_languages": "Нет установленных языков OCR",
        "no_installed_translation_pairs": "Нет установленных направлений перевода",
        "install_languages_first": "Сначала установите язык: Настройки → Языковые пакеты.",
        "swap_languages": "Поменять языки местами",
    },
    "es": {
        "tess_download_data": "Tesseract: descargando datos de idioma para {language}...", "tess_downloading": "Tesseract: descargando {language}... {percent}%",
        "tess_ready": "Tesseract: los datos de {language} están listos", "tess_retrying": "Tesseract: reintentando la descarga de {language} ({attempt}/{total})...", "recognizing": "Reconociendo texto...",
        "win_missing_title": "Falta el paquete de Windows OCR", "win_unavailable": "Windows OCR no está disponible ahora.",
        "win_components": "No se pudieron cargar los componentes de Windows OCR. La aplicación puede continuar con Tesseract si está instalado.",
        "win_unsupported": "Windows OCR no admite: {language} ({tag}).", "win_pack": "Probablemente no está instalado el paquete de idioma de Windows OCR. Puedes abrir la configuración de idioma de Windows y añadir el idioma necesario.",
        "win_continue": "El reconocimiento continuará ahora con Tesseract.", "win_stopped": "No se encontró Tesseract, por lo que se detuvo el reconocimiento para este idioma.",
        "open_windows": "Abrir configuración de Windows", "continue_tesseract": "Continuar con Tesseract", "close": "Cerrar",
        "recognition_failed": "Error de reconocimiento", "engine_unavailable": "{engine} no está disponible",
        "engine_unavailable_info": "El motor {engine} no está instalado o no se pudo cargar.\n\nPrueba:\n• Elige {engine} en la configuración e instala el paquete local\n• Elige otro motor OCR",
        "engine_unreliable": "{engine} no encontró texto fiable", "engine_unreliable_info": "{engine} no detectó texto con suficiente confianza.\n\nPrueba:\n• Revisa el idioma de reconocimiento\n• Selecciona un área más ajustada y con más contraste\n• Cambia de motor OCR",
        "auto_unreliable": "El texto no se reconoció de forma fiable", "auto_unreliable_info": "Los resultados débiles se filtraron para no enviar ruido al traductor.\n\nPrueba:\n• Selecciona el área con más precisión\n• Elige el idioma de origen\n• Usa otro motor OCR o instala el paquete de Windows OCR",
        "not_recognized": "😔 No se reconoció el texto", "not_recognized_info": "Prueba:\n• Selecciona texto más grande\n• Comprueba que tenga buen contraste\n• Elige otro motor OCR",
        "translate": "Traducir", "ocr_init_failed": "No se pudo iniciar OCR", "screen_no_text": "No se reconoció texto en la pantalla",
        "translation_failed": "Error de traducción", "translating_screen": "Traduciendo la pantalla...", "fullscreen_hint": "ESC — cerrar  |  Botón derecho — arrastrar",
        "no_installed_languages": "No hay idiomas OCR instalados",
        "no_installed_translation_pairs": "No hay direcciones de traducción instaladas",
        "install_languages_first": "Instala primero un idioma en Ajustes → Paquetes de idioma.",
        "swap_languages": "Intercambiar idiomas",
    },
    "de": {
        "tess_download_data": "Tesseract: Sprachdaten für {language} werden heruntergeladen...", "tess_downloading": "Tesseract: {language} wird heruntergeladen... {percent}%",
        "tess_ready": "Tesseract: Sprachdaten für {language} sind bereit", "tess_retrying": "Tesseract: {language} wird erneut geladen ({attempt}/{total})...", "recognizing": "Text wird erkannt...",
        "win_missing_title": "Windows-OCR-Paket fehlt", "win_unavailable": "Windows OCR ist momentan nicht verfügbar.",
        "win_components": "Windows-OCR-Komponenten konnten nicht geladen werden. Die App kann mit Tesseract fortfahren, wenn es installiert ist.",
        "win_unsupported": "Windows OCR unterstützt {language} ({tag}) nicht.", "win_pack": "Das Windows-OCR-Sprachpaket ist wahrscheinlich nicht installiert. Öffne die Windows-Spracheinstellungen und füge die benötigte Sprache hinzu.",
        "win_continue": "Die Erkennung wird jetzt mit Tesseract fortgesetzt.", "win_stopped": "Tesseract wurde nicht gefunden; die Erkennung für diese Sprache wurde gestoppt.",
        "open_windows": "Windows-Einstellungen öffnen", "continue_tesseract": "Mit Tesseract fortfahren", "close": "Schließen",
        "recognition_failed": "Erkennung fehlgeschlagen", "engine_unavailable": "{engine} ist nicht verfügbar",
        "engine_unavailable_info": "Die {engine}-Engine ist nicht installiert oder konnte nicht geladen werden.\n\nVersuche:\n• {engine} in den Einstellungen wählen und das lokale Paket installieren\n• Eine andere OCR-Engine wählen",
        "engine_unreliable": "{engine} hat keinen zuverlässigen Text gefunden", "engine_unreliable_info": "{engine} hat Text nicht mit ausreichender Sicherheit erkannt.\n\nVersuche:\n• Erkennungssprache prüfen\n• Einen engeren, kontrastreicheren Bereich auswählen\n• Eine andere OCR-Engine wählen",
        "auto_unreliable": "Text wurde nicht zuverlässig erkannt", "auto_unreliable_info": "Schwache Ergebnisse wurden gefiltert, damit kein Rauschen übersetzt wird.\n\nVersuche:\n• Den Textbereich genauer auswählen\n• Die konkrete Ausgangssprache wählen\n• Eine andere OCR-Engine verwenden oder das Windows-OCR-Paket installieren",
        "not_recognized": "😔 Text nicht erkannt", "not_recognized_info": "Versuche:\n• Einen Bereich mit größerem Text auswählen\n• Auf guten Kontrast achten\n• Eine andere OCR-Engine wählen",
        "translate": "Übersetzen", "ocr_init_failed": "OCR konnte nicht gestartet werden", "screen_no_text": "Auf dem Bildschirm wurde kein Text erkannt",
        "translation_failed": "Übersetzung fehlgeschlagen", "translating_screen": "Bildschirm wird übersetzt...", "fullscreen_hint": "ESC — schließen  |  Rechtsklick — ziehen",
        "no_installed_languages": "Keine OCR-Sprachen installiert",
        "no_installed_translation_pairs": "Keine Übersetzungsrichtungen installiert",
        "install_languages_first": "Installiere zuerst eine Sprache unter Einstellungen → Sprachpakete.",
        "swap_languages": "Sprachen tauschen",
    },
    "fr": {
        "tess_download_data": "Tesseract : téléchargement des données de langue {language}...", "tess_downloading": "Tesseract : téléchargement de {language}... {percent}%",
        "tess_ready": "Tesseract : les données de {language} sont prêtes", "tess_retrying": "Tesseract : nouvelle tentative de téléchargement de {language} ({attempt}/{total})...", "recognizing": "Reconnaissance du texte...",
        "win_missing_title": "Module Windows OCR manquant", "win_unavailable": "Windows OCR n’est pas disponible actuellement.",
        "win_components": "Les composants Windows OCR n’ont pas pu être chargés. L’application peut continuer avec Tesseract s’il est installé.",
        "win_unsupported": "Windows OCR ne prend pas en charge : {language} ({tag}).", "win_pack": "Le module de langue Windows OCR n’est probablement pas installé. Ouvrez les paramètres de langue de Windows et ajoutez la langue requise.",
        "win_continue": "La reconnaissance va continuer avec Tesseract.", "win_stopped": "Tesseract est introuvable ; la reconnaissance pour cette langue est arrêtée.",
        "open_windows": "Ouvrir les paramètres Windows", "continue_tesseract": "Continuer avec Tesseract", "close": "Fermer",
        "recognition_failed": "Échec de la reconnaissance", "engine_unavailable": "{engine} n’est pas disponible",
        "engine_unavailable_info": "Le moteur {engine} n’est pas installé ou n’a pas pu être chargé.\n\nEssayez :\n• Choisir {engine} dans les paramètres et installer le paquet local\n• Choisir un autre moteur OCR",
        "engine_unreliable": "{engine} n’a pas trouvé de texte fiable", "engine_unreliable_info": "{engine} n’a pas détecté de texte avec une confiance suffisante.\n\nEssayez :\n• Vérifier la langue de reconnaissance\n• Sélectionner une zone plus précise et contrastée\n• Changer de moteur OCR",
        "auto_unreliable": "Le texte n’a pas été reconnu de façon fiable", "auto_unreliable_info": "Les résultats faibles ont été filtrés pour ne pas envoyer de bruit au traducteur.\n\nEssayez :\n• Sélectionner la zone plus précisément\n• Choisir la langue source exacte\n• Utiliser un autre moteur OCR ou installer le module Windows OCR",
        "not_recognized": "😔 Texte non reconnu", "not_recognized_info": "Essayez :\n• Sélectionner une zone avec un texte plus grand\n• Vérifier le contraste\n• Choisir un autre moteur OCR",
        "translate": "Traduire", "ocr_init_failed": "Impossible de démarrer l’OCR", "screen_no_text": "Aucun texte reconnu à l’écran",
        "translation_failed": "Échec de la traduction", "translating_screen": "Traduction de l’écran...", "fullscreen_hint": "ESC — fermer  |  Clic droit — déplacer",
        "no_installed_languages": "Aucune langue OCR installée",
        "no_installed_translation_pairs": "Aucune direction de traduction installée",
        "install_languages_first": "Installez d’abord une langue dans Réglages → Modules de langue.",
        "swap_languages": "Inverser les langues",
    },
    "zh": {
        "tess_download_data": "Tesseract：正在下载 {language} 语言数据...", "tess_downloading": "Tesseract：正在下载 {language}... {percent}%",
        "tess_ready": "Tesseract：{language} 语言数据已就绪", "tess_retrying": "Tesseract：正在重试下载 {language}（{attempt}/{total}）…", "recognizing": "正在识别文本...",
        "win_missing_title": "缺少 Windows OCR 语言包", "win_unavailable": "Windows OCR 当前不可用。",
        "win_components": "Windows OCR 组件加载失败。如果已安装 Tesseract，应用可以继续使用它。",
        "win_unsupported": "Windows OCR 不支持：{language}（{tag}）。", "win_pack": "可能尚未安装 Windows OCR 语言包。你可以打开 Windows 语言设置并添加所需语言。",
        "win_continue": "现在将使用 Tesseract 继续识别。", "win_stopped": "未找到 Tesseract，因此已停止识别此语言。",
        "open_windows": "打开 Windows 设置", "continue_tesseract": "使用 Tesseract 继续", "close": "关闭",
        "recognition_failed": "识别失败", "engine_unavailable": "{engine} 不可用",
        "engine_unavailable_info": "{engine} 引擎未安装或加载失败。\n\n请尝试：\n• 在设置中选择 {engine} 并安装本地包\n• 选择其他 OCR 引擎",
        "engine_unreliable": "{engine} 未找到可靠文本", "engine_unreliable_info": "{engine} 未以足够置信度检测到文本。\n\n请尝试：\n• 检查所选识别语言\n• 更精确地选择高对比度区域\n• 切换到其他 OCR 引擎",
        "auto_unreliable": "未能可靠识别文本", "auto_unreliable_info": "已过滤置信度较低的结果，以免向翻译器发送噪声。\n\n请尝试：\n• 更精确地选择文本区域\n• 选择具体的源语言\n• 使用其他 OCR 引擎或安装 Windows OCR 语言包",
        "not_recognized": "😔 未识别到文本", "not_recognized_info": "请尝试：\n• 选择字号更大的文本区域\n• 确保文本对比度良好\n• 在设置中选择其他 OCR 引擎",
        "translate": "翻译", "ocr_init_failed": "OCR 初始化失败", "screen_no_text": "未识别到屏幕文字",
        "translation_failed": "翻译失败", "translating_screen": "正在翻译屏幕...", "fullscreen_hint": "ESC — 关闭  |  右键 — 拖动",
        "no_installed_languages": "未安装 OCR 语言",
        "no_installed_translation_pairs": "未安装翻译方向",
        "install_languages_first": "请先在设置 → 语言包中安装语言。",
        "swap_languages": "交换语言",
    },
}


def ocr_ui_text(lang, key, **values):
    texts = OCR_UI_TEXT.get(lang, OCR_UI_TEXT["en"])
    template = texts.get(key, OCR_UI_TEXT["en"].get(key, key))
    return template.format(**values)

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


def close_ocr_diagnostics_logging():
    """Release the rotating log so Clear cache can remove it on Windows."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if not getattr(handler, "_clickntranslate_ocr_file", False):
            continue
        root.removeHandler(handler)
        try:
            handler.flush()
        finally:
            handler.close()


def reopen_ocr_diagnostics_logging():
    """Restore diagnostics after a complete cache cleanup."""
    _setup_ocr_diagnostics_logging()

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


_QT_ICON_CACHE = {}


def _cached_qt_icon(relative_path):
    """Load immutable UI icons once instead of decoding them per overlay."""
    normalized_path = str(relative_path or "").replace("\\", "/")
    icon = _QT_ICON_CACHE.get(normalized_path)
    if icon is None:
        icon = QtGui.QIcon(resource_path(normalized_path))
        _QT_ICON_CACHE[normalized_path] = icon
    return icon

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

def _tesseract_language_display_name(tess_code, interface_language=None):
    interface_language = interface_language or get_cached_ocr_config().get("interface_language", "en")
    for language in APP_LANGUAGES:
        if language.tesseract_code == tess_code:
            return language.display_name(interface_language)
    return tess_code


# Language data comes straight from the tessdata repository on GitHub and is
# tens of megabytes, so a dropped connection is common enough to retry.
_TESSDATA_DOWNLOAD_ATTEMPTS = 3
_TESSDATA_RETRY_DELAY_SECONDS = 2


def _prepare_tesseract_data(
    tess_cmd,
    tess_lang,
    status_callback=None,
    cancel_check=None,
    raise_on_error=False,
):
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
        error = RuntimeError("Tesseract tessdata directory was not found.")
        if raise_on_error:
            raise error
        logging.warning(str(error))
        return []

    prepared = []
    tmp_path = ""
    try:
        import requests
        interface_language = get_cached_ocr_config().get("interface_language", "en")
        for lang_code in [code for code in tess_lang.split("+") if code]:
            fname = f"{lang_code}.traineddata"
            target_path = os.path.join(tessdata_dir, fname)
            if os.path.isfile(target_path) and os.path.getsize(target_path) > 0:
                prepared.append(target_path)
                continue
            if cancel_check and cancel_check():
                return prepared
            url = f"https://github.com/tesseract-ocr/tessdata/raw/main/{fname}"
            display_name = _tesseract_language_display_name(lang_code, interface_language)
            status_text = ocr_ui_text(interface_language, "tess_download_data", language=display_name)
            if status_callback:
                status_callback(status_text)
            logging.info(f"Downloading {fname} into {tessdata_dir} ...")
            tmp_path = target_path + ".tmp"
            # These files are tens of megabytes straight from GitHub, so a single
            # dropped connection used to fail the whole install and the user had
            # to guess that simply retrying would work.  Retry transient network
            # failures here instead.
            canceled = False
            for attempt in range(_TESSDATA_DOWNLOAD_ATTEMPTS):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                downloaded = 0
                total = 0
                try:
                    with requests.get(url, timeout=180, stream=True) as r:
                        r.raise_for_status()
                        try:
                            total = int((r.headers.get("Content-Length") or "0").strip() or "0")
                        except Exception:
                            total = 0
                        with open(tmp_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=1024 * 1024):
                                if cancel_check and cancel_check():
                                    canceled = True
                                    break
                                if not chunk:
                                    continue
                                f.write(chunk)
                                downloaded += len(chunk)
                                if status_callback and total > 0:
                                    percent = int(downloaded * 100 / max(total, 1))
                                    status_callback(
                                        ocr_ui_text(
                                            interface_language,
                                            "tess_downloading",
                                            language=display_name,
                                            percent=percent,
                                        )
                                    )
                    if canceled:
                        break
                    # A truncated transfer is the common failure mode and is
                    # worth another attempt rather than an immediate error.
                    if total and downloaded != total:
                        raise RuntimeError(
                            f"Incomplete Tesseract package {fname}: "
                            f"received {downloaded} of {total} bytes."
                        )
                    if not os.path.isfile(tmp_path) or os.path.getsize(tmp_path) <= 0:
                        raise RuntimeError(f"Downloaded Tesseract package {fname} is empty.")
                    break
                except Exception as attempt_error:
                    if cancel_check and cancel_check():
                        canceled = True
                        break
                    if attempt + 1 >= _TESSDATA_DOWNLOAD_ATTEMPTS:
                        raise
                    delay = _TESSDATA_RETRY_DELAY_SECONDS * (attempt + 1)
                    logging.warning(
                        f"Tesseract package {fname} download attempt {attempt + 1} failed "
                        f"({attempt_error}); retrying in {delay}s"
                    )
                    if status_callback:
                        status_callback(
                            ocr_ui_text(
                                interface_language,
                                "tess_retrying",
                                language=display_name,
                                attempt=attempt + 2,
                                total=_TESSDATA_DOWNLOAD_ATTEMPTS,
                            )
                        )
                    time.sleep(delay)
            if canceled:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                return prepared
            os.replace(tmp_path, target_path)
            tmp_path = ""
            prepared.append(target_path)
            if status_callback:
                status_callback(ocr_ui_text(interface_language, "tess_ready", language=display_name))
            logging.info(f"{fname} downloaded into {tessdata_dir}")
    except Exception as dl_err:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        logging.warning(f"Could not prepare Tesseract language data {tess_lang}: {dl_err}")
        if raise_on_error:
            raise
    return prepared


def _system_tessdata_dirs():
    """Where a distribution package keeps its tessdata.

    Debian uses /usr/share/tesseract-ocr/<version>/tessdata, Fedora and Arch use
    /usr/share/tessdata, and Homebrew and /usr/local builds have their own. None
    of these sit next to the binary, which is the only place the portable
    Windows layout has to look.
    """
    if platform_support.IS_WINDOWS:
        return []
    import glob

    directories = []
    for pattern in (
        "/usr/share/tesseract-ocr/*/tessdata",
        "/usr/share/tessdata",
        "/usr/local/share/tessdata",
        "/usr/local/share/tesseract-ocr/*/tessdata",
        "/opt/homebrew/share/tessdata",
        "/var/lib/flatpak/exports/share/tessdata",
    ):
        directories.extend(sorted(glob.glob(pattern), reverse=True))
    return directories


def _configure_installed_tesseract_data(tess_cmd, tess_lang):
    required = [f"{code}.traineddata" for code in str(tess_lang or "").split("+") if code]
    tess_dir = os.path.dirname(tess_cmd or "")
    candidate_dirs = [
        os.environ.get("TESSDATA_PREFIX", ""),
        os.path.join(tess_dir, "tessdata"),
        os.path.join(os.path.dirname(tess_dir), "tessdata"),
        *_system_tessdata_dirs(),
    ]
    for data_dir in candidate_dirs:
        if data_dir and required and all(os.path.isfile(os.path.join(data_dir, name)) for name in required):
            os.environ["TESSDATA_PREFIX"] = data_dir
            return data_dir

    # A packaged Tesseract may keep its data somewhere none of those patterns
    # cover. If the binary itself reports the languages it can already find
    # them, and forcing TESSDATA_PREFIX would only break that.
    codes = {code for code in str(tess_lang or "").split("+") if code}
    if codes and codes <= _tesseract_reported_languages(tess_cmd):
        return os.environ.get("TESSDATA_PREFIX", "") or str(tess_dir or "tesseract")
    return ""

def _tesseract_psm_order(width, height):
    psm_order = [6]
    if height < 110:
        psm_order = [7, 8, 13, 6, 11]
    elif width < 260 or height < 180:
        psm_order = [6, 7, 8, 13, 11]
    return psm_order


def _configure_pytesseract_system_environment(pytesseract):
    """Make pytesseract launch the distro binary outside the AppImage runtime."""
    if not platform_support.IS_LINUX:
        return
    module = pytesseract.pytesseract
    original = getattr(module, "subprocess_args", None)
    if not callable(original) or getattr(original, "_clickntranslate_system_env", False) is True:
        return

    def subprocess_args(*args, **kwargs):
        result = original(*args, **kwargs)
        result["env"] = platform_support.system_subprocess_env()
        return result

    subprocess_args._clickntranslate_system_env = True
    module.subprocess_args = subprocess_args

def _run_tesseract_ocr_image_with_cmd(pil_image, tess_cmd, tess_lang, context, session_id, cancel_check=None):
    import pytesseract

    _configure_pytesseract_system_environment(pytesseract)

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
    status_callback=None,
    cancel_check=None,
):
    if not tess_cmd:
        logging.error(f"[OCR:{session_id}] Tesseract executable not found for {context}.")
        return None

    logging.info(f"[OCR:{session_id}] Using Tesseract at: {tess_cmd}; context={context}, lang={tess_lang}")
    if not _configure_installed_tesseract_data(tess_cmd, tess_lang):
        logging.error(
            f"[OCR:{session_id}] Tesseract language data is not installed for {tess_lang}; "
            "use Settings > Language packages."
        )
        return ""
    if cancel_check and cancel_check():
        return ""

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


_RAPID_OCR_ENGINE = None
_RAPID_OCR_IMPORT_ERROR = None
_RAPID_OCR_LOCAL_PATHS_READY = False
_RAPID_OCR_DLL_DIR_HANDLES = []


def _native_ocr_worker_enabled():
    if sys.platform != "win32":
        return False
    return bool(getattr(sys, "frozen", False) or os.environ.get("CLICKNTRANSLATE_USE_OCR_WORKER") == "1")


def _native_ocr_worker_path():
    if not getattr(sys, "frozen", False):
        return ""
    executable_dir = os.path.dirname(sys.executable)
    worker_name = platform_support.executable_name("OcrWorker")
    for path in (
        os.path.join(executable_dir, "_internal", worker_name),
        os.path.join(executable_dir, worker_name),
    ):
        if os.path.isfile(path):
            return path
    return ""


def _native_ocr_worker_command():
    if getattr(sys, "frozen", False):
        worker_path = _native_ocr_worker_path()
        return [worker_path] if os.path.isfile(worker_path) else []
    worker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_worker.py")
    return [sys.executable, worker_script] if os.path.isfile(worker_script) else []


def _call_native_ocr_worker(request, pil_variants=None, timeout=1800):
    command = _native_ocr_worker_command()
    if not command:
        raise RuntimeError("Native OCR worker is missing from this build.")

    temp_dir = tempfile.mkdtemp(prefix="clickntranslate_ocr_")
    try:
        images = []
        for index, (label, image) in enumerate(pil_variants or []):
            image_path = os.path.join(temp_dir, f"image-{index + 1}.png")
            image.save(image_path, format="PNG")
            images.append({"label": str(label), "path": image_path})
        payload = dict(request)
        payload["images"] = images
        request_path = os.path.join(temp_dir, "request.json")
        with open(request_path, "w", encoding="utf-8") as request_file:
            json.dump(payload, request_file, ensure_ascii=False)

        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        completed = subprocess.run(
            [*command, request_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        output = (completed.stdout or "").strip()
        if completed.returncode != 0:
            detail = (completed.stderr or output or f"exit code {completed.returncode}").strip()
            raise RuntimeError(f"Native OCR worker failed: {detail[:1200]}")
        try:
            response = json.loads(output)
        except Exception as exc:
            detail = (completed.stderr or output or "empty output").strip()
            raise RuntimeError(f"Native OCR worker returned invalid output: {detail[:1200]}") from exc
        if response.get("error"):
            raise RuntimeError(str(response["error"]))
        return response
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _probe_native_ocr_worker(
    engine,
    root_dir,
    language_codes=None,
    initialize=False,
    allow_download=False,
):
    request = {
        "action": "recognize" if initialize else "import",
        "engine": engine,
        "root_dir": root_dir,
        "language_codes": list(language_codes or []),
        "allow_download": bool(allow_download),
    }
    try:
        _call_native_ocr_worker(request)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _recognize_with_native_ocr_worker(
    engine,
    pil_variants,
    context,
    session_id,
    language_code="en",
    status_callback=None,
):
    if status_callback:
        engine_name = "RapidOCR" if engine == "rapidocr" else "EasyOCR" if engine == "easyocr" else engine
        status_callback(f"Starting {engine_name}…")
    root_dir = _rapidocr_local_root() if engine == "rapidocr" else _easyocr_local_root()
    language_codes = easyocr_language_codes(language_code) if engine == "easyocr" else []
    response = _call_native_ocr_worker(
        {
            "action": "recognize",
            "engine": engine,
            "root_dir": root_dir,
            "language_codes": language_codes,
            # Recognition must never trigger a model download. Optional OCR
            # packages are prepared explicitly from Settings > Language packages.
            "allow_download": False,
        },
        pil_variants=pil_variants,
    )

    auto_candidates = []
    best_reason = f"{engine}_empty"
    for result in response.get("results") or []:
        if result.get("error"):
            best_reason = f"{engine}_error"
            logging.error(
                f"[OCR:{session_id}] {engine} worker variant={result.get('label')}; "
                f"context={context} failed: {result['error']}"
            )
            continue
        text = str(result.get("text") or "").strip()
        confidence = float(result.get("confidence") or 0.0)
        confidence_floor = 0.20 if engine == "easyocr" else 0.28
        reject_reason = (
            f"low_{engine}_confidence"
            if text and confidence and confidence < confidence_floor
            else ""
        )
        candidate = _make_auto_ocr_candidate(
            text,
            engine=engine,
            language_code=language_code if engine == "easyocr" else "",
            image_label=str(result.get("label") or ""),
            confidence=confidence,
            boxes_count=int(result.get("boxes_count") or 0),
            elapsed_ms=float(result.get("elapsed_ms") or 0.0),
            reject_reason=reject_reason,
        )
        auto_candidates.append(candidate)
        if candidate.reject_reason:
            best_reason = candidate.reject_reason

    selected, selector_reason = _select_best_auto_ocr_candidate(
        auto_candidates,
        session_id=session_id,
        context=f"{engine} OCR worker",
    )
    if selected is not None:
        return selected.text, ""
    return "", selector_reason or best_reason


def _rapidocr_local_root():
    return (
        os.environ.get("CLICKNTRANSLATE_RAPIDOCR_DIR")
        or os.path.join(get_portable_dir(), "ocr", "rapidocr")
    )


def _rapidocr_local_candidate_paths(root_dir=None):
    root_dir = root_dir or _rapidocr_local_root()
    candidates = [
        root_dir,
        os.path.join(root_dir, "site-packages"),
        os.path.join(root_dir, "Lib", "site-packages"),
        os.path.join(root_dir, "lib", "site-packages"),
    ]
    try:
        for name in os.listdir(root_dir):
            lower = name.lower()
            if lower.startswith("python") or lower in {"venv", ".venv"}:
                candidates.append(os.path.join(root_dir, name, "Lib", "site-packages"))
                candidates.append(os.path.join(root_dir, name, "lib", "site-packages"))
    except Exception:
        pass

    unique = []
    seen = set()
    for path in candidates:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen or not os.path.isdir(path):
            continue
        seen.add(normalized)
        unique.append(os.path.abspath(path))
    return unique


def _rapidocr_dll_candidate_paths(package_paths):
    candidates = []
    for path in package_paths:
        candidates.append(path)
        candidates.append(os.path.join(path, "onnxruntime", "capi"))
        candidates.append(os.path.join(path, "cv2"))
    unique = []
    seen = set()
    for path in candidates:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen or not os.path.isdir(path):
            continue
        seen.add(normalized)
        unique.append(os.path.abspath(path))
    return unique


def _ensure_rapidocr_local_paths():
    global _RAPID_OCR_LOCAL_PATHS_READY
    if _RAPID_OCR_LOCAL_PATHS_READY:
        return
    package_paths = _rapidocr_local_candidate_paths()
    for path in reversed(package_paths):
        if path not in sys.path:
            sys.path.insert(0, path)
            logging.info(f"RapidOCR local path added: {path}")
    if hasattr(os, "add_dll_directory"):
        for path in _rapidocr_dll_candidate_paths(package_paths):
            try:
                _RAPID_OCR_DLL_DIR_HANDLES.append(os.add_dll_directory(path))
            except Exception as exc:
                logging.debug(f"RapidOCR DLL path skipped {path}: {exc}")
    _RAPID_OCR_LOCAL_PATHS_READY = True


def reset_rapidocr_runtime_cache(clear_modules=False):
    global _RAPID_OCR_ENGINE, _RAPID_OCR_IMPORT_ERROR, _RAPID_OCR_LOCAL_PATHS_READY
    _RAPID_OCR_ENGINE = None
    _RAPID_OCR_IMPORT_ERROR = None
    _RAPID_OCR_LOCAL_PATHS_READY = False
    while _RAPID_OCR_DLL_DIR_HANDLES:
        handle = _RAPID_OCR_DLL_DIR_HANDLES.pop()
        try:
            handle.close()
        except Exception:
            pass
    if clear_modules:
        prefixes = ("rapidocr", "rapidocr_onnxruntime", "onnxruntime", "cv2")
        for module_name in list(sys.modules):
            if module_name in prefixes or any(module_name.startswith(prefix + ".") for prefix in prefixes):
                sys.modules.pop(module_name, None)


def rapidocr_importable():
    global _RAPID_OCR_IMPORT_ERROR
    if _native_ocr_worker_enabled():
        available, error = _probe_native_ocr_worker("rapidocr", _rapidocr_local_root())
        _RAPID_OCR_IMPORT_ERROR = None if available else error
        return available, error
    _ensure_rapidocr_local_paths()
    errors = []
    try:
        from rapidocr import RapidOCR  # noqa: F401
        _RAPID_OCR_IMPORT_ERROR = None
        return True, ""
    except Exception as exc:
        errors.append(f"rapidocr: {exc}")
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: F401
            _RAPID_OCR_IMPORT_ERROR = None
            return True, ""
        except Exception as legacy_exc:
            errors.append(f"rapidocr_onnxruntime: {legacy_exc}")
    _RAPID_OCR_IMPORT_ERROR = "; ".join(errors)
    return False, _RAPID_OCR_IMPORT_ERROR


def _get_rapidocr_engine():
    global _RAPID_OCR_ENGINE, _RAPID_OCR_IMPORT_ERROR
    if _RAPID_OCR_ENGINE is not None:
        return _RAPID_OCR_ENGINE

    _ensure_rapidocr_local_paths()
    rapid_cls = None
    errors = []
    try:
        from rapidocr import RapidOCR as rapid_cls
    except Exception as exc:
        errors.append(f"rapidocr: {exc}")
        try:
            from rapidocr_onnxruntime import RapidOCR as rapid_cls
        except Exception as legacy_exc:
            errors.append(f"rapidocr_onnxruntime: {legacy_exc}")

    if rapid_cls is None:
        _RAPID_OCR_IMPORT_ERROR = "; ".join(errors)
        logging.error(f"RapidOCR is not available: {_RAPID_OCR_IMPORT_ERROR}")
        return None

    init_attempts = (
        {"text_score": 0.35, "print_verbose": False},
        {"print_verbose": False},
        {},
    )
    for kwargs in init_attempts:
        try:
            _RAPID_OCR_ENGINE = rapid_cls(**kwargs)
            _RAPID_OCR_IMPORT_ERROR = None
            logging.info(f"RapidOCR engine initialized with args={kwargs}")
            return _RAPID_OCR_ENGINE
        except TypeError:
            continue
        except Exception as exc:
            _RAPID_OCR_IMPORT_ERROR = str(exc)
            logging.exception(f"RapidOCR initialization failed with args={kwargs}: {exc}")
            return None

    _RAPID_OCR_IMPORT_ERROR = "RapidOCR constructor signature is unsupported"
    logging.error(_RAPID_OCR_IMPORT_ERROR)
    return None


def rapidocr_available():
    if _native_ocr_worker_enabled():
        available, _error = _probe_native_ocr_worker(
            "rapidocr", _rapidocr_local_root(), initialize=True
        )
        return available
    return _get_rapidocr_engine() is not None


def rapidocr_status():
    available = rapidocr_available()
    return available, "" if available else (_RAPID_OCR_IMPORT_ERROR or "RapidOCR is not available")


def _rapidocr_box_origin(box):
    try:
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        return min(ys), min(xs)
    except Exception:
        return 0.0, 0.0


def _parse_rapidocr_output(output):
    if isinstance(output, tuple):
        result = output[0] if output else None
    else:
        result = output
    if result is None:
        return []

    items = []
    if hasattr(result, "txts"):
        raw_texts = getattr(result, "txts", None)
        raw_scores = getattr(result, "scores", None)
        raw_boxes = getattr(result, "boxes", None)
        texts = list(raw_texts) if raw_texts is not None else []
        scores = list(raw_scores) if raw_scores is not None else []
        boxes = list(raw_boxes) if raw_boxes is not None else []
        for index, text in enumerate(texts):
            score = scores[index] if index < len(scores) else 0.0
            box = boxes[index] if index < len(boxes) else None
            items.append((box, str(text or ""), float(score or 0.0)))
    elif isinstance(result, (list, tuple)):
        for row in result:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            box = row[0]
            text = row[1]
            score = row[2] if len(row) >= 3 else 0.0
            try:
                score = float(score or 0.0)
            except Exception:
                score = 0.0
            items.append((box, str(text or ""), score))

    items = [
        (box, text.strip(), score)
        for box, text, score in items
        if text and text.strip()
    ]
    items.sort(key=lambda item: _rapidocr_box_origin(item[0]))
    return items


def _recognize_rapidocr_variants(pil_variants, context, session_id, cancel_check=None):
    if _native_ocr_worker_enabled():
        try:
            return _recognize_with_native_ocr_worker(
                "rapidocr", pil_variants, context, session_id
            )
        except Exception as exc:
            logging.exception(f"[OCR:{session_id}] RapidOCR worker failed: {exc}")
            return "", "rapidocr_unavailable"
    engine = _get_rapidocr_engine()
    if engine is None:
        return "", "rapidocr_unavailable"
    auto_candidates = []
    best_reason = "rapidocr_empty"

    for label, pil_image in pil_variants or []:
        if cancel_check and cancel_check():
            logging.info(f"[OCR:{session_id}] RapidOCR interrupted before variant={label}; context={context}")
            break
        try:
            image = pil_image.convert("RGB") if getattr(pil_image, "mode", "") != "RGB" else pil_image
            started = time.perf_counter()
            output = engine(image)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if cancel_check and cancel_check():
                logging.info(f"[OCR:{session_id}] RapidOCR interrupted after variant={label}; context={context}")
                break
            items = _parse_rapidocr_output(output)
            text = "\n".join(item[1] for item in items).strip()
            confidences = [item[2] for item in items if item[2] > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            reject_reason = ""
            if text and avg_confidence and avg_confidence < 0.28:
                reject_reason = "low_rapidocr_confidence"
            candidate = _make_auto_ocr_candidate(
                text,
                engine="rapidocr",
                image_label=label,
                confidence=avg_confidence,
                boxes_count=len(items),
                elapsed_ms=elapsed_ms,
                reject_reason=reject_reason,
            )
            auto_candidates.append(candidate)
            if candidate.reject_reason:
                best_reason = candidate.reject_reason
        except Exception as exc:
            best_reason = "rapidocr_error"
            logging.exception(f"[OCR:{session_id}] RapidOCR variant={label}; context={context} failed: {exc}")

    selected, selector_reason = _select_best_auto_ocr_candidate(
        auto_candidates,
        session_id=session_id,
        context=f"RapidOCR {context}",
    )
    if selected is not None:
        return selected.text, ""
    if selector_reason:
        best_reason = selector_reason
    return "", best_reason


_EASY_OCR_READERS = {}
_EASY_OCR_IMPORT_ERROR = None
_EASY_OCR_LOCAL_PATHS_READY = False
_EASY_OCR_DLL_DIR_HANDLES = []


def _easyocr_local_root():
    return (
        os.environ.get("CLICKNTRANSLATE_EASYOCR_DIR")
        or os.path.join(get_portable_dir(), "ocr", "easyocr")
    )


def _easyocr_local_candidate_paths(root_dir=None):
    root_dir = root_dir or _easyocr_local_root()
    candidates = [
        root_dir,
        os.path.join(root_dir, "site-packages"),
        os.path.join(root_dir, "Lib", "site-packages"),
        os.path.join(root_dir, "lib", "site-packages"),
    ]
    try:
        for name in os.listdir(root_dir):
            lower = name.lower()
            if lower.startswith("python") or lower in {"venv", ".venv"}:
                candidates.append(os.path.join(root_dir, name, "Lib", "site-packages"))
                candidates.append(os.path.join(root_dir, name, "lib", "site-packages"))
    except Exception:
        pass

    unique = []
    seen = set()
    for path in candidates:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen or not os.path.isdir(path):
            continue
        seen.add(normalized)
        unique.append(os.path.abspath(path))
    return unique


def _easyocr_dll_candidate_paths(package_paths):
    candidates = []
    for path in package_paths:
        candidates.append(path)
        candidates.append(os.path.join(path, "cv2"))
        candidates.append(os.path.join(path, "torch", "lib"))
        candidates.append(os.path.join(path, "torchvision"))
        candidates.append(os.path.join(path, "numpy.libs"))
    unique = []
    seen = set()
    for path in candidates:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen or not os.path.isdir(path):
            continue
        seen.add(normalized)
        unique.append(os.path.abspath(path))
    return unique


def _ensure_easyocr_local_paths():
    global _EASY_OCR_LOCAL_PATHS_READY
    if _EASY_OCR_LOCAL_PATHS_READY:
        return
    package_paths = _easyocr_local_candidate_paths()
    for path in reversed(package_paths):
        if path not in sys.path:
            sys.path.insert(0, path)
            logging.info(f"EasyOCR local path added: {path}")
    if hasattr(os, "add_dll_directory"):
        for path in _easyocr_dll_candidate_paths(package_paths):
            try:
                _EASY_OCR_DLL_DIR_HANDLES.append(os.add_dll_directory(path))
            except Exception as exc:
                logging.debug(f"EasyOCR DLL path skipped {path}: {exc}")
    _EASY_OCR_LOCAL_PATHS_READY = True


def reset_easyocr_runtime_cache(clear_modules=False):
    global _EASY_OCR_READERS, _EASY_OCR_IMPORT_ERROR, _EASY_OCR_LOCAL_PATHS_READY
    _EASY_OCR_READERS = {}
    _EASY_OCR_IMPORT_ERROR = None
    _EASY_OCR_LOCAL_PATHS_READY = False
    while _EASY_OCR_DLL_DIR_HANDLES:
        handle = _EASY_OCR_DLL_DIR_HANDLES.pop()
        try:
            handle.close()
        except Exception:
            pass
    if clear_modules:
        prefixes = (
            "easyocr",
            "torch",
            "torchvision",
            "cv2",
            "skimage",
            "scipy",
            "pyclipper",
            "shapely",
            "bidi",
            "yaml",
        )
        for module_name in list(sys.modules):
            if module_name in prefixes or any(module_name.startswith(prefix + ".") for prefix in prefixes):
                sys.modules.pop(module_name, None)


def easyocr_importable():
    global _EASY_OCR_IMPORT_ERROR
    if _native_ocr_worker_enabled():
        available, error = _probe_native_ocr_worker("easyocr", _easyocr_local_root())
        _EASY_OCR_IMPORT_ERROR = None if available else error
        return available, error
    _ensure_easyocr_local_paths()
    try:
        import easyocr  # noqa: F401
        _EASY_OCR_IMPORT_ERROR = None
        return True, ""
    except Exception as exc:
        _EASY_OCR_IMPORT_ERROR = str(exc)
        return False, _EASY_OCR_IMPORT_ERROR


def _easyocr_model_dir():
    model_dir = os.path.join(_easyocr_local_root(), "models")
    os.makedirs(model_dir, exist_ok=True)
    return model_dir


def _get_easyocr_reader(language_code, download_enabled=False):
    global _EASY_OCR_IMPORT_ERROR
    language_codes = tuple(easyocr_language_codes(language_code))
    if language_codes in _EASY_OCR_READERS:
        return _EASY_OCR_READERS[language_codes]

    _ensure_easyocr_local_paths()
    try:
        import easyocr
        model_dir = _easyocr_model_dir()
        user_network_dir = os.path.join(_easyocr_local_root(), "user_network")
        os.makedirs(user_network_dir, exist_ok=True)
        reader = easyocr.Reader(
            list(language_codes),
            gpu=False,
            model_storage_directory=model_dir,
            user_network_directory=user_network_dir,
            download_enabled=bool(download_enabled),
            verbose=False,
        )
        _EASY_OCR_READERS[language_codes] = reader
        _EASY_OCR_IMPORT_ERROR = None
        logging.info(f"EasyOCR reader initialized for languages={language_codes}; model_dir={model_dir}")
        return reader
    except Exception as exc:
        _EASY_OCR_IMPORT_ERROR = str(exc)
        logging.exception(f"EasyOCR reader initialization failed for languages={language_codes}: {exc}")
        return None


def easyocr_available(language_code="en", download_enabled=False):
    if _native_ocr_worker_enabled():
        available, _error = _probe_native_ocr_worker(
            "easyocr",
            _easyocr_local_root(),
            language_codes=easyocr_language_codes(language_code),
            initialize=True,
            allow_download=download_enabled,
        )
        return available
    return _get_easyocr_reader(language_code, download_enabled=download_enabled) is not None


def easyocr_status(language_code="en"):
    available = easyocr_available(language_code)
    return available, "" if available else (_EASY_OCR_IMPORT_ERROR or "EasyOCR is not available")


def _parse_easyocr_output(output):
    items = []
    if output is None:
        return items
    for row in output:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        box = row[0]
        text = row[1]
        score = row[2] if len(row) >= 3 else 0.0
        try:
            score = float(score or 0.0)
        except Exception:
            score = 0.0
        text = str(text or "").strip()
        if text:
            items.append((box, text, score))
    items.sort(key=lambda item: _rapidocr_box_origin(item[0]))
    return items


def _recognize_easyocr_variants(pil_variants, language_code, context, session_id, status_callback=None, cancel_check=None):
    if _native_ocr_worker_enabled():
        try:
            return _recognize_with_native_ocr_worker(
                "easyocr",
                pil_variants,
                context,
                session_id,
                language_code=language_code,
                status_callback=status_callback,
            )
        except Exception as exc:
            logging.exception(f"[OCR:{session_id}] EasyOCR worker failed: {exc}")
            return "", "easyocr_unavailable"
    if status_callback:
        language_codes = ", ".join(easyocr_language_codes(language_code))
        status_callback(f"EasyOCR: preparing {language_codes}")
    reader = _get_easyocr_reader(language_code)
    if reader is None:
        return "", "easyocr_unavailable"

    auto_candidates = []
    best_reason = "easyocr_empty"
    for label, pil_image in pil_variants or []:
        if cancel_check and cancel_check():
            logging.info(f"[OCR:{session_id}] EasyOCR interrupted before variant={label}; context={context}")
            break
        try:
            image = pil_image.convert("RGB") if getattr(pil_image, "mode", "") != "RGB" else pil_image
            import numpy as np
            started = time.perf_counter()
            output = reader.readtext(np.array(image), detail=1, paragraph=False)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if cancel_check and cancel_check():
                logging.info(f"[OCR:{session_id}] EasyOCR interrupted after variant={label}; context={context}")
                break
            items = _parse_easyocr_output(output)
            text = "\n".join(item[1] for item in items).strip()
            confidences = [item[2] for item in items if item[2] > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            reject_reason = ""
            if text and avg_confidence and avg_confidence < 0.20:
                reject_reason = "low_easyocr_confidence"
            candidate = _make_auto_ocr_candidate(
                text,
                engine="easyocr",
                language_code=language_code,
                image_label=label,
                confidence=avg_confidence,
                boxes_count=len(items),
                elapsed_ms=elapsed_ms,
                reject_reason=reject_reason,
            )
            auto_candidates.append(candidate)
            if candidate.reject_reason:
                best_reason = candidate.reject_reason
        except Exception as exc:
            best_reason = "easyocr_error"
            logging.exception(f"[OCR:{session_id}] EasyOCR variant={label}; context={context} failed: {exc}")

    selected, selector_reason = _select_best_auto_ocr_candidate(
        auto_candidates,
        session_id=session_id,
        context=f"EasyOCR {context}",
    )
    if selected is not None:
        return selected.text, ""
    if selector_reason:
        best_reason = selector_reason
    return "", best_reason


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
    )
    target = default_target_for_source(source, config.get("ocr_translate_target_language"))
    return source, target

def _combo_data_to_ocr_language(data, fallback="ru"):
    if isinstance(data, (tuple, list)) and data:
        data = data[0]
    return _normalize_app_language_code(data, fallback)

def _combo_data_to_translate_pair(data, config=None):
    config = config or get_cached_ocr_config()
    if isinstance(data, (tuple, list)) and len(data) >= 2:
        source = _normalize_app_language_code(data[0], "en")
        target = _normalize_app_language_code(data[1], default_target_for_source(source))
        if source == target:
            target = default_target_for_source(source)
        return source, target
    source, _target = _configured_ocr_translate_pair(config, data)
    return source, default_target_for_source(source, config.get("ocr_translate_target_language"))


_EASYOCR_MODEL_GROUP_BY_LANGUAGE = {
    "en": "english_g2", "ru": "cyrillic_g2", "uk": "cyrillic_g2",
    "de": "latin_g2", "fr": "latin_g2", "es": "latin_g2", "it": "latin_g2",
    "pt": "latin_g2", "pl": "latin_g2", "tr": "latin_g2", "nl": "latin_g2",
    "zh": "zh_sim_g2", "ch_sim": "zh_sim_g2", "ja": "japanese_g2",
    "ko": "korean_g2", "ar": "arabic", "hi": "devanagari",
}
_EASYOCR_MODEL_FILE_VARIANTS = {
    "english_g2": ("english_g2.pth",),
    "cyrillic_g2": ("cyrillic_g2.pth", "cyrillic.pth"),
    "latin_g2": ("latin_g2.pth", "latin.pth"),
    "zh_sim_g2": ("zh_sim_g2.pth", "chinese_sim.pth"),
    "japanese_g2": ("japanese_g2.pth", "japanese.pth"),
    "korean_g2": ("korean_g2.pth", "korean.pth"),
    "arabic": ("arabic.pth",),
    "devanagari": ("devanagari.pth",),
}


def _python_package_file_present(candidate_paths, package_names):
    for root in candidate_paths:
        for package_name in package_names:
            package_path = os.path.join(root, package_name)
            if os.path.isfile(package_path + ".py") or os.path.isfile(os.path.join(package_path, "__init__.py")):
                return True
    return False


def _tesseract_reported_languages(tess_cmd):
    """Language codes Tesseract itself reports.

    A distribution package keeps its tessdata somewhere the app cannot guess
    (`/usr/share/tesseract-ocr/<version>/tessdata` on Debian), so asking the
    binary is the only portable way to enumerate languages. The directory scan
    below still covers the portable Windows install, where tessdata sits next to
    the executable.
    """
    if not tess_cmd:
        return set()
    try:
        completed = subprocess.run(
            [tess_cmd, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=15,
            env=platform_support.system_subprocess_env(),
            **platform_support.no_window_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logging.debug(f"tesseract --list-langs failed: {exc}")
        return set()
    if completed.returncode != 0:
        return set()
    # The first line is a header such as "List of available languages (3):".
    lines = (completed.stdout or "").splitlines()
    return {line.strip() for line in lines[1:] if line.strip()}


def _tesseract_installed_language_codes():
    try:
        tess_cmd = ScreenCaptureOverlay.get_tesseract_cmd()
    except Exception:
        tess_cmd = None
    if not tess_cmd or not os.path.isfile(tess_cmd):
        return []
    reported = _tesseract_reported_languages(tess_cmd)
    data_dirs = [
        os.environ.get("TESSDATA_PREFIX", ""),
        os.path.join(os.path.dirname(tess_cmd), "tessdata"),
        os.path.join(os.path.dirname(os.path.dirname(tess_cmd)), "tessdata"),
    ]
    result = []
    for language in APP_LANGUAGES:
        code = tesseract_language_code(language.code)
        if code in reported:
            result.append(language.code)
            continue
        filename = code + ".traineddata"
        if any(path and os.path.isfile(os.path.join(path, filename)) for path in data_dirs):
            result.append(language.code)
    return result


def _easyocr_installed_language_codes():
    root = _easyocr_local_root()
    if not _python_package_file_present(_easyocr_local_candidate_paths(root), ("easyocr",)):
        return []
    model_dir = os.path.join(root, "models")
    if not os.path.isfile(os.path.join(model_dir, "craft_mlt_25k.pth")):
        return []
    result = []
    for language in APP_LANGUAGES:
        easy_codes = easyocr_language_codes(language.code)
        primary_code = easy_codes[0] if easy_codes else language.code
        group = _EASYOCR_MODEL_GROUP_BY_LANGUAGE.get(
            primary_code,
            _EASYOCR_MODEL_GROUP_BY_LANGUAGE.get(language.code),
        )
        groups = [group] if group else []
        installed = bool(groups) and all(
            any(os.path.isfile(os.path.join(model_dir, filename)) for filename in _EASYOCR_MODEL_FILE_VARIANTS[group])
            for group in groups
        )
        if installed:
            result.append(language.code)
    return result


def _rapidocr_installed_language_codes():
    if getattr(sys, "frozen", False):
        bundled_worker = _native_ocr_worker_path()
        if os.path.isfile(bundled_worker):
            # ClicknTranslate.spec embeds RapidOCR, ONNX Runtime and the shared
            # English/Chinese PP-OCR models in this isolated worker.
            return [code for code in ("en", "zh") if code in APP_LANGUAGE_CODES]
    root = _rapidocr_local_root()
    if not _python_package_file_present(
        _rapidocr_local_candidate_paths(root),
        ("rapidocr", "rapidocr_onnxruntime"),
    ):
        return []
    # The bundled RapidOCR recognizer is one shared Chinese + English model.
    return [code for code in ("en", "zh") if code in APP_LANGUAGE_CODES]


def installed_ocr_language_codes(engine=None, config=None):
    """Return only OCR languages usable by the selected local engine."""
    config = config or get_cached_ocr_config()
    engine_name = usable_ocr_engine(
        engine or config.get("ocr_engine", platform_support.default_ocr_engine())
    ).strip().lower()
    if engine_name in {"rapid", "rapidocr"}:
        return _rapidocr_installed_language_codes()
    if engine_name in {"easy", "easyocr"}:
        return _easyocr_installed_language_codes()
    if engine_name == "tesseract":
        return _tesseract_installed_language_codes()

    available_tags = [str(tag or "").lower() for tag in _get_available_windows_ocr_language_tags()]
    result = []
    for language in APP_LANGUAGES:
        expected = windows_ocr_tag(language.code).lower()
        primary = expected.split("-", 1)[0]
        if any(tag == expected or tag.split("-", 1)[0] == primary for tag in available_tags):
            result.append(language.code)
    return result


def _installed_argos_translation_pairs():
    try:
        import translater
        return {
            (source, target)
            for source, target in translater.argos_installed_translation_pairs_fast()
            if source in APP_LANGUAGE_CODES and target in APP_LANGUAGE_CODES
        }
    except Exception as exc:
        logging.warning(f"Could not inspect installed Argos packages: {exc}")
        return set()


def _translation_targets_for_source(source_code, config=None):
    config = config or get_cached_ocr_config()
    engine_name = str(config.get("translator_engine", "Google")).strip().lower()
    if engine_name == "argos":
        pairs = _installed_argos_translation_pairs()
        return [language.code for language in APP_LANGUAGES if (source_code, language.code) in pairs]
    return [language.code for language in APP_LANGUAGES if language.code != source_code]


def _ocr_translate_options_from_config(config=None):
    config = config or get_cached_ocr_config()
    installed_sources = set(installed_ocr_language_codes(config=config))
    engine_name = str(config.get("translator_engine", "Google")).strip().lower()
    if engine_name == "argos":
        pairs = _installed_argos_translation_pairs()
        return [
            (source, target)
            for source, target in sorted(pairs)
            if source in installed_sources
        ]
    return [
        pair
        for pair in ocr_translate_options(config.get("ocr_translate_target_language"))
        if pair[0] in installed_sources
    ]

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
        # Keep the live main window in sync. Otherwise a later save from the
        # settings screen can overwrite a language pair that the OCR/fullscreen
        # overlay has already persisted to disk.
        for module_name in ("main", "__main__"):
            module = sys.modules.get(module_name)
            if module is None:
                continue
            window = getattr(module, "_main_window_ref", None)
            live_config = getattr(window, "config", None)
            if isinstance(live_config, dict):
                live_config.update(updates)
            invalidate = getattr(module, "invalidate_config_cache", None)
            if callable(invalidate):
                invalidate()
        return True
    except Exception as e:
        logging.warning(f"Failed to save OCR config updates: {e}")
        return False


def _remove_auto_mode_from_config(config):
    if not isinstance(config, dict):
        return {}
    updates = {}
    if str(config.get("last_ocr_language", "")).lower() in {"auto", "universal"}:
        updates["last_ocr_language"] = "ru"
    for key in ("ocr_translate_source_language", "fullscreen_translate_from"):
        if str(config.get(key, "")).lower() in {"auto", "universal"}:
            updates[key] = "en"
    if updates:
        config.update(updates)
    return updates


# --- Кэширование конфигурации ---
_ocr_config_cache = None
_ocr_config_mtime = 0


def invalidate_ocr_config_cache():
    """Force the next OCR action to read settings freshly from disk."""
    global _ocr_config_cache, _ocr_config_mtime
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
            auto_updates = _remove_auto_mode_from_config(_ocr_config_cache)
            if auto_updates:
                try:
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(_ocr_config_cache, f, ensure_ascii=False, indent=4)
                    mtime = os.path.getmtime(config_path)
                except Exception as e:
                    logging.warning(f"Failed to remove AUTO OCR config values: {e}")
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
    debug_log("run_ocr_with_engine called")
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

def usable_ocr_engine(engine):
    """Map a configured engine onto one that exists on this platform.

    A config written on Windows names the WinRT engine, which no other system
    has. Without this the OCR flow would take the Windows path and report a
    missing engine instead of simply using the platform default.
    """
    name = str(engine or "").strip()
    if name.lower() in platform_support.available_ocr_engines():
        return name
    default = platform_support.default_ocr_engine()
    if name:
        logging.info(f"OCR engine {name!r} is not available on this platform; using {default}.")
    return default


def grab_screen_pixmap(screen, x=0, y=0, width=-1, height=-1):
    """Grab (part of) `screen`.

    Windows and X11 read the root window through Qt. Wayland refuses that, so
    linux_capture routes the grab through the desktop portal or a compositor
    helper, and the result is cropped to the requested rectangle here.
    """
    if screen is None:
        return QtGui.QPixmap()
    wants_region = width > 0 and height > 0
    if platform_support.IS_LINUX and platform_support.is_wayland():
        import linux_capture

        try:
            pixmap = linux_capture.grab_screen(screen)
        except linux_capture.CaptureError as exc:
            # Never raise into a Qt callback: an escaping exception is what left
            # the 1.5.4 full-screen overlay spinning forever. Callers already
            # handle a null pixmap and report it.
            logging.error(f"Screen capture is unavailable: {exc}")
            return QtGui.QPixmap()
        if pixmap.isNull() or not wants_region:
            return pixmap
        ratio = pixmap.width() / max(1, screen.geometry().width())
        return pixmap.copy(
            int(round(x * ratio)),
            int(round(y * ratio)),
            int(round(width * ratio)),
            int(round(height * ratio)),
        )
    if wants_region:
        return screen.grabWindow(0, x, y, width, height)
    return screen.grabWindow(0)


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
        if platform_support.supports_windows_ocr():
            logging.error("WinRT modules are not available")
        else:
            # WinRT is a Windows API; its absence elsewhere is normal, not a fault.
            logging.debug("WinRT is not available on this platform; another OCR engine is used")
        return None
    
    try:
        debug_log("Getting Language and OcrEngine classes...")
        # Используем предзагруженные модули
        Language = winrt_glob.Language
        OcrEngine = winrt_ocr.OcrEngine
        debug_log(f"Language={Language}, OcrEngine={OcrEngine}")
        
        # Prefer the exact installed WinRT tag before probing.  Windows exposes
        # Simplified Chinese as zh-Hans-CN on some builds even though the DISM
        # capability is named zh-CN.  Creating the generic tag can otherwise
        # select the wrong regional engine or return an unusable instance.
        available_tags = _get_available_windows_ocr_language_tags()
        available_by_tag = {
            str(tag).lower(): str(tag)
            for tag in available_tags
            if str(tag).strip()
        }
        matched_tag = _match_available_windows_ocr_tag(lang_tag, available_by_tag)
        if matched_tag:
            lang_tag = matched_tag

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
                debug_log("FAILED: OcrEngine.try_create_from_language returned None")
        
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
        if platform_support.supports_windows_ocr():
            logging.error("WinRT modules are not available")
        else:
            # WinRT is a Windows API; its absence elsewhere is normal, not a fault.
            logging.debug("WinRT is not available on this platform; another OCR engine is used")
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
    debug_log("qimage_to_softwarebitmap called")
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
    score += language_likelihood_score(text, language_code) * 3.0

    # Cross-alphabet OCR often produces odd mixed-case tokens (for example,
    # Russian "Привет" read by the English engine as "npneT"). Legitimate
    # title case and all-caps acronyms are left alone.
    mixed_case_tokens = 0
    for token in word_tokens:
        letters = "".join(ch for ch in token if ch.isalpha())
        if not letters or not (any(ch.islower() for ch in letters) and any(ch.isupper() for ch in letters)):
            continue
        if not (letters[0].isupper() and letters[1:].islower()):
            mixed_case_tokens += 1
    score -= mixed_case_tokens * 4.0

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


def _auto_ocr_rejection_reason(text, score):
    text = str(text or "").strip()
    if not text:
        return "empty"

    allowed_punctuation = set(".,:;!?-\u2013\u2014()[]{}\"'`/\\%+\u2116#@&_=<>$€£¥|")
    alnum = sum(1 for ch in text if ch.isalnum())
    alpha = sum(1 for ch in text if ch.isalpha())
    digits = sum(1 for ch in text if ch.isdigit())
    noise = sum(1 for ch in text if not ch.isalnum() and not ch.isspace() and ch not in allowed_punctuation)
    compact_len = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))

    if compact_len < 2:
        return "too_short"
    if alnum <= 0:
        return "no_text_signal"
    if noise > max(2, alnum // 2):
        return "too_noisy"
    if alpha <= 0:
        return "" if digits >= 2 and noise <= 1 else "numeric_signal_too_weak"
    if score >= 8.0:
        return ""
    if alnum >= 4 and noise == 0 and score >= 0.0:
        return ""
    return "low_confidence"


def _is_acceptable_auto_ocr_text(text, score):
    return _auto_ocr_rejection_reason(text, score) == ""


@dataclass
class AutoOcrCandidate:
    text: str
    engine: str = ""
    language_code: str = ""
    image_label: str = ""
    confidence: float = 0.0
    boxes_count: int = 0
    elapsed_ms: float = 0.0
    score: float = float("-inf")
    reject_reason: str = ""
    detected_language: str = ""


def _normalized_auto_candidate_text(text):
    return " ".join(str(text or "").split()).strip().lower()


def _is_numeric_auto_candidate(text):
    text = str(text or "").strip()
    alnum = sum(1 for ch in text if ch.isalnum())
    alpha = sum(1 for ch in text if ch.isalpha())
    digits = sum(1 for ch in text if ch.isdigit())
    return alnum >= 2 and digits >= 2 and alpha == 0


def _make_auto_ocr_candidate(
    text,
    engine,
    language_code="",
    image_label="",
    confidence=0.0,
    boxes_count=0,
    elapsed_ms=0.0,
    reject_reason="",
):
    text = str(text or "").strip()
    detected = detect_language_code(text) if text else ""
    generic_score = _score_recognized_text(text)
    if language_code and language_code not in {"auto", "universal"}:
        language_score = _score_ocr_text_for_language(text, language_code)
    elif detected:
        language_score = _score_ocr_text_for_language(text, detected)
    else:
        language_score = generic_score

    score = max(generic_score, language_score)
    try:
        confidence = float(confidence or 0.0)
    except Exception:
        confidence = 0.0
    if confidence > 0:
        score += min(confidence, 1.0) * 42.0
    if boxes_count:
        score += min(int(boxes_count), 16) * 1.4
    if engine == "rapidocr" and boxes_count:
        score += 6.0
    if language_code == "universal" and detected:
        score += 4.0

    reason = reject_reason or _auto_ocr_rejection_reason(text, score)
    return AutoOcrCandidate(
        text=text,
        engine=engine,
        language_code=language_code or "",
        image_label=image_label or "",
        confidence=confidence,
        boxes_count=int(boxes_count or 0),
        elapsed_ms=float(elapsed_ms or 0.0),
        score=score,
        reject_reason=reason,
        detected_language=detected or "",
    )


def _apply_auto_ocr_consensus_bonus(candidates):
    counts = {}
    for candidate in candidates:
        normalized = _normalized_auto_candidate_text(candidate.text)
        if normalized:
            counts[normalized] = counts.get(normalized, 0) + 1
    for candidate in candidates:
        normalized = _normalized_auto_candidate_text(candidate.text)
        duplicates = counts.get(normalized, 0) - 1
        if duplicates > 0:
            candidate.score += min(18.0, duplicates * 8.0)


def _select_best_auto_ocr_candidate(candidates, session_id="unknown", context="AUTO"):
    candidates = list(candidates or [])
    _apply_auto_ocr_consensus_bonus(candidates)
    for candidate in candidates:
        logging.info(
            f"[OCR:{session_id}] {context} candidate; engine={candidate.engine}, "
            f"lang={candidate.language_code or '-'}, detected={candidate.detected_language or '-'}, "
            f"variant={candidate.image_label or '-'}, boxes={candidate.boxes_count}, "
            f"conf={candidate.confidence:.3f}, score={candidate.score:.1f}, "
            f"reject={candidate.reject_reason or '-'}, preview={_text_preview(candidate.text)}"
        )

    accepted = [
        candidate for candidate in candidates
        if candidate.text and not candidate.reject_reason
    ]
    if not accepted:
        reasons = [candidate.reject_reason for candidate in candidates if candidate.reject_reason]
        return None, reasons[0] if reasons else "empty"

    accepted.sort(key=lambda candidate: candidate.score, reverse=True)
    best = accepted[0]
    best_normalized = _normalized_auto_candidate_text(best.text)
    second = next(
        (
            candidate for candidate in accepted[1:]
            if _normalized_auto_candidate_text(candidate.text) != best_normalized
        ),
        None,
    )
    if second is not None and best.score < 72.0 and (best.score - second.score) < 7.0:
        logging.info(
            f"[OCR:{session_id}] {context} rejected ambiguous candidates; "
            f"best={best.score:.1f}/{_text_preview(best.text)}, "
            f"second={second.score:.1f}/{_text_preview(second.text)}"
        )
        return None, "ambiguous_candidates"

    if not _is_numeric_auto_candidate(best.text) and best.score < 34.0:
        logging.info(
            f"[OCR:{session_id}] {context} rejected weak best candidate; "
            f"score={best.score:.1f}, preview={_text_preview(best.text)}"
        )
        return None, "low_confidence"

    logging.info(
        f"[OCR:{session_id}] {context} selected; engine={best.engine}, "
        f"lang={best.language_code or '-'}, variant={best.image_label or '-'}, "
        f"score={best.score:.1f}, preview={_text_preview(best.text)}"
    )
    return best, ""


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


def _coerce_ocr_attempts(attempts_or_bitmap):
    if attempts_or_bitmap is None:
        return []
    if (
        isinstance(attempts_or_bitmap, tuple)
        and len(attempts_or_bitmap) == 2
        and isinstance(attempts_or_bitmap[0], str)
    ):
        label, bitmap = attempts_or_bitmap
        return [(label, bitmap)] if bitmap is not None else []
    if isinstance(attempts_or_bitmap, (list, tuple)):
        attempts = []
        for index, item in enumerate(attempts_or_bitmap):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                label, bitmap = item
            else:
                label, bitmap = f"attempt-{index + 1}", item
            if bitmap is not None:
                attempts.append((str(label), bitmap))
        return attempts
    return [("primary", attempts_or_bitmap)]


def _recognize_with_windows_auto(attempts_or_bitmap, cancel_check=None, session_id="unknown"):
    attempts = _coerce_ocr_attempts(attempts_or_bitmap)
    if not attempts:
        logging.warning(f"[OCR:{session_id}] Windows OCR AUTO has no bitmap attempts.")
        return ""
    if cancel_check is None:
        def cancel_check():
            return False

    candidates = _windows_auto_ocr_candidates()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    auto_candidates = []
    try:
        if candidates:
            for code, tag in candidates:
                if cancel_check():
                    logging.info(f"[OCR:{session_id}] Windows OCR AUTO interrupted before candidate lang={code}, tag={tag}")
                    break
                engine = _get_windows_ocr_engine(tag)
                if engine is None:
                    continue
                for attempt_label, bitmap in attempts:
                    if cancel_check():
                        logging.info(
                            f"[OCR:{session_id}] Windows OCR AUTO interrupted before "
                            f"candidate lang={code}, attempt={attempt_label}"
                        )
                        break
                    try:
                        started = time.perf_counter()
                        recognized = loop.run_until_complete(run_ocr_with_engine(bitmap, engine))
                        elapsed_ms = (time.perf_counter() - started) * 1000.0
                        if cancel_check():
                            logging.info(
                                f"[OCR:{session_id}] Windows OCR AUTO interrupted after "
                                f"candidate lang={code}, attempt={attempt_label}"
                            )
                            break
                        text = _windows_ocr_result_to_text(recognized)
                        auto_candidates.append(
                            _make_auto_ocr_candidate(
                                text,
                                engine="windows",
                                language_code=code,
                                image_label=attempt_label,
                                elapsed_ms=elapsed_ms,
                            )
                        )
                    except Exception as e:
                        logging.exception(
                            f"[OCR:{session_id}] Windows OCR AUTO candidate failed; "
                            f"lang={code}, tag={tag}, attempt={attempt_label}: {e}"
                        )
        else:
            logging.warning(
                f"[OCR:{session_id}] Windows OCR AUTO has no installed candidate languages; "
                "falling back to universal engine."
            )

        if not cancel_check():
            try:
                universal_engine = _get_universal_ocr_engine()
                if universal_engine is not None:
                    logging.info(f"[OCR:{session_id}] Windows OCR AUTO running universal/user-profile pass")
                    for attempt_label, bitmap in attempts:
                        if cancel_check():
                            logging.info(
                                f"[OCR:{session_id}] Windows OCR AUTO universal interrupted before attempt={attempt_label}"
                            )
                            break
                        try:
                            started = time.perf_counter()
                            recognized = loop.run_until_complete(run_ocr_with_engine(bitmap, universal_engine))
                            elapsed_ms = (time.perf_counter() - started) * 1000.0
                            if cancel_check():
                                logging.info(
                                    f"[OCR:{session_id}] Windows OCR AUTO universal interrupted after attempt={attempt_label}"
                                )
                                break
                            text = _windows_ocr_result_to_text(recognized)
                            auto_candidates.append(
                                _make_auto_ocr_candidate(
                                    text,
                                    engine="windows-universal",
                                    language_code="universal",
                                    image_label=attempt_label,
                                    elapsed_ms=elapsed_ms,
                                )
                            )
                        except Exception as e:
                            logging.exception(
                                f"[OCR:{session_id}] Windows OCR AUTO universal failed; attempt={attempt_label}: {e}"
                            )
            except Exception as e:
                logging.exception(f"[OCR:{session_id}] Windows OCR AUTO universal setup failed: {e}")

        selected, reason = _select_best_auto_ocr_candidate(
            auto_candidates,
            session_id=session_id,
            context="Windows OCR AUTO",
        )
        if selected is not None:
            return selected.text
        if cancel_check():
            logging.info(f"[OCR:{session_id}] Windows OCR AUTO stopped after cancellation.")
        else:
            logging.warning(
                f"[OCR:{session_id}] Windows OCR AUTO did not produce a reliable candidate; reason={reason}"
            )
        return ""
    finally:
        try:
            loop.close()
        except Exception:
            pass
        asyncio.set_event_loop(None)


class OCRWorker(QtCore.QThread):
    result_ready = QtCore.pyqtSignal(str)
    status_update = QtCore.pyqtSignal(str)
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
        self.failure_reason = None
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
        debug_log("OCRWorker.run() started")
        debug_log(f"self.bitmap = {self.bitmap}")
        debug_log(f"self.language_code = {self.language_code}")
        debug_log(f"self.use_universal = {self.use_universal}")
        debug_log(f"self.attempts = {[label for label, _bitmap in self.attempts]}")
        loop = None
        try:
            # Выбираем engine в зависимости от режима
            if self.use_universal:
                debug_log("Using Windows OCR AUTO language selection")
                recognized_text = _recognize_with_windows_auto(
                    self.attempts,
                    cancel_check=self._is_cancelled,
                    session_id=self.session_id,
                )
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
                        f"[OCR:{self.session_id}] Windows OCR AUTO empty; running Tesseract fallback; "
                        f"lang={tess_lang}, variants={[label for label, _image in self.fallback_pil_variants]}"
                    )
                    recognized_text = _recognize_tesseract_variants_with_cmd(
                        self.fallback_pil_variants,
                        self.tesseract_cmd,
                        tess_lang,
                        "windows-auto-empty-fallback",
                        self.session_id,
                        status_callback=self.status_update.emit,
                        cancel_check=self._is_cancelled,
                    ) or ""
                    if recognized_text:
                        candidate = _make_auto_ocr_candidate(
                            recognized_text,
                            engine="tesseract",
                            language_code=self.language_code,
                            image_label="fallback",
                        )
                        selected, reject_reason = _select_best_auto_ocr_candidate(
                            [candidate],
                            session_id=self.session_id,
                            context="Windows OCR AUTO Tesseract fallback",
                        )
                        if reject_reason:
                            logging.info(
                                f"[OCR:{self.session_id}] Windows OCR AUTO Tesseract fallback rejected; "
                                f"reason={reject_reason}, score={candidate.score:.1f}, "
                                f"preview={_text_preview(recognized_text)}"
                            )
                            recognized_text = ""
                        elif selected is not None:
                            recognized_text = selected.text
                debug_log(f"Emitting AUTO result: '{recognized_text[:50]}...' (len={len(recognized_text)})")
                if not recognized_text and not self._is_cancelled():
                    self.failure_reason = "auto_low_confidence_or_empty"
                if not self._is_cancelled():
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
                        status_callback=self.status_update.emit,
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
                    status_callback=self.status_update.emit,
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
    status_update = QtCore.pyqtSignal(str)

    def __init__(self, pil_variants, language_code, tess_cmd, context, session_id, parent=None):
        super().__init__(parent)
        self.pil_variants = list(pil_variants or [])
        self.language_code = language_code
        self.tess_cmd = tess_cmd
        self.context = context
        self.session_id = session_id
        self.cancel_requested = False
        self.failure_reason = None

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
                    status_callback=self.status_update.emit,
                    cancel_check=self._is_cancelled,
                ) or ""
                if self.language_code in {"universal", "auto"} and text:
                    candidate = _make_auto_ocr_candidate(
                        text,
                        engine="tesseract",
                        language_code="universal",
                        image_label=self.context,
                    )
                    selected, reason = _select_best_auto_ocr_candidate(
                        [candidate],
                        session_id=self.session_id,
                        context=f"Tesseract AUTO {self.context}",
                    )
                    if selected is None:
                        self.failure_reason = "auto_low_confidence_or_empty"
                        logging.info(
                            f"[OCR:{self.session_id}] Tesseract AUTO result rejected; "
                            f"reason={reason}, preview={_text_preview(text)}"
                        )
                        text = ""
                    else:
                        text = selected.text
        except Exception as e:
            self.failure_reason = "tesseract_error"
            logging.exception(f"[OCR:{self.session_id}] TesseractOCRWorker failed: {e}")

        if self._is_cancelled():
            logging.info(f"[OCR:{self.session_id}] Tesseract worker result suppressed after interruption")
            return
        logging.info(
            f"[OCR:{self.session_id}] TesseractOCRWorker finished; "
            f"text_len={len(text or '')}, preview={_text_preview(text)}"
        )
        self.result_ready.emit(text)


class RapidOCRWorker(QtCore.QThread):
    result_ready = QtCore.pyqtSignal(str)
    status_update = QtCore.pyqtSignal(str)

    def __init__(self, pil_variants, context, session_id, parent=None):
        super().__init__(parent)
        self.pil_variants = list(pil_variants or [])
        self.context = context
        self.session_id = session_id
        self.cancel_requested = False
        self.failure_reason = None

    def cancel(self):
        self.cancel_requested = True
        self.requestInterruption()

    def _is_cancelled(self):
        return self.cancel_requested or self.isInterruptionRequested()

    def run(self):
        logging.info(
            f"[OCR:{self.session_id}] RapidOCRWorker started; context={self.context}, "
            f"variants={[label for label, _image in self.pil_variants]}"
        )
        text = ""
        try:
            if not self.pil_variants:
                self.failure_reason = "rapidocr_empty"
                logging.error(f"[OCR:{self.session_id}] RapidOCR worker has no image variants")
            else:
                text, failure_reason = _recognize_rapidocr_variants(
                    self.pil_variants,
                    self.context,
                    self.session_id,
                    cancel_check=self._is_cancelled,
                )
                self.failure_reason = failure_reason or None
        except Exception as e:
            self.failure_reason = "rapidocr_error"
            logging.exception(f"[OCR:{self.session_id}] RapidOCRWorker failed: {e}")

        if self._is_cancelled():
            logging.info(f"[OCR:{self.session_id}] RapidOCR worker result suppressed after interruption")
            return
        logging.info(
            f"[OCR:{self.session_id}] RapidOCRWorker finished; "
            f"text_len={len(text or '')}, failure={self.failure_reason or '-'}, preview={_text_preview(text)}"
        )
        self.result_ready.emit(text)


class EasyOCRWorker(QtCore.QThread):
    result_ready = QtCore.pyqtSignal(str)
    status_update = QtCore.pyqtSignal(str)

    def __init__(self, pil_variants, language_code, context, session_id, parent=None):
        super().__init__(parent)
        self.pil_variants = list(pil_variants or [])
        self.language_code = language_code
        self.context = context
        self.session_id = session_id
        self.cancel_requested = False
        self.failure_reason = None

    def cancel(self):
        self.cancel_requested = True
        self.requestInterruption()

    def _is_cancelled(self):
        return self.cancel_requested or self.isInterruptionRequested()

    def run(self):
        logging.info(
            f"[OCR:{self.session_id}] EasyOCRWorker started; context={self.context}, "
            f"language={self.language_code}, easyocr_languages={easyocr_language_codes(self.language_code)}, "
            f"variants={[label for label, _image in self.pil_variants]}"
        )
        text = ""
        try:
            if not self.pil_variants:
                self.failure_reason = "easyocr_empty"
                logging.error(f"[OCR:{self.session_id}] EasyOCR worker has no image variants")
            else:
                text, failure_reason = _recognize_easyocr_variants(
                    self.pil_variants,
                    self.language_code,
                    self.context,
                    self.session_id,
                    status_callback=self.status_update.emit,
                    cancel_check=self._is_cancelled,
                )
                self.failure_reason = failure_reason or None
        except Exception as e:
            self.failure_reason = "easyocr_error"
            logging.exception(f"[OCR:{self.session_id}] EasyOCRWorker failed: {e}")

        if self._is_cancelled():
            logging.info(f"[OCR:{self.session_id}] EasyOCR worker result suppressed after interruption")
            return
        logging.info(
            f"[OCR:{self.session_id}] EasyOCRWorker finished; "
            f"text_len={len(text or '')}, failure={self.failure_reason or '-'}, preview={_text_preview(text)}"
        )
        self.result_ready.emit(text)


class ScreenCaptureOverlay(QWidget):
    def __init__(self, mode="ocr", defer_show=False):
        super().__init__()
        # Устанавливаем иконку приложения
        self.setWindowIcon(_cached_qt_icon("icons/icon.ico"))
        
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
        self._ocr_status_text = ""
        self._last_ocr_raw_capture = None
        self._last_ocr_pil_variants = []
        self._last_ocr_capture_meta = {}
        # Загрузка последнего выбранного языка из конфигурации
        config = get_cached_ocr_config()
        self._freeze_screen_on_ocr = config.get("freeze_screen_on_ocr", False)
        if self.mode == "translate":
            self.current_language, self.current_target_language = _configured_ocr_translate_pair(config)
        else:
            self.current_language = _normalize_app_language_code(config.get("last_ocr_language"), "ru")
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
        available_source_codes = installed_ocr_language_codes(config=config)
        if self.mode == "translate" and str(config.get("translator_engine", "Google")).lower() == "argos":
            available_source_codes = [
                code for code in available_source_codes
                if _translation_targets_for_source(code, config)
            ]
        
        if self.mode == "copy":
            for language in APP_LANGUAGES:
                if language.code not in available_source_codes:
                    continue
                self.lang_combo.addItem(
                    _cached_qt_icon(language_icon_path(language.code)),
                    language.short_label,
                    language.code,
                )
        elif self.mode == "translate":
            # В режиме translate источник и цель выбираются отдельно прямо в OCR-оверлее.
            for language in APP_LANGUAGES:
                if language.code not in available_source_codes:
                    continue
                self.lang_combo.addItem(
                    _cached_qt_icon(language_icon_path(language.code)),
                    language.short_label,
                    language.code,
                )
            self.translate_arrow_label = QtWidgets.QToolButton(self)
            self.translate_arrow_label.setText("⇄")
            self.translate_arrow_label.setCursor(QtCore.Qt.ArrowCursor)
            self.translate_arrow_label.setToolTip(
                ocr_ui_text(config.get("interface_language", "en"), "swap_languages")
            )
            self.translate_arrow_label.setStyleSheet("""
                QToolButton {
                    color: #d8e3f2;
                    font-size: 17px;
                    font-weight: 700;
                    background-color: rgba(22, 25, 31, 244);
                    border: 1px solid rgba(105, 123, 150, 130);
                    border-radius: 12px;
                }
                QToolButton:hover {
                    background-color: rgba(40, 47, 60, 252);
                    border-color: rgba(160, 186, 220, 220);
                }
                QToolButton:disabled {
                    color: rgba(118, 128, 143, 180);
                    border-color: rgba(73, 82, 96, 110);
                }
            """)
            self.translate_arrow_label.clicked.connect(self._swap_translate_languages)
            self.target_lang_combo = QtWidgets.QComboBox(self)
        else:
            for language in APP_LANGUAGES:
                if language.code not in available_source_codes:
                    continue
                self.lang_combo.addItem(
                    _cached_qt_icon(language_icon_path(language.code)),
                    language.short_label,
                    language.code,
                )
        
        # Устанавливаем индекс на основе self.current_language (сохраненного)
        if self.lang_combo.count() == 0:
            interface_language = config.get("interface_language", "en")
            self.lang_combo.addItem(ocr_ui_text(interface_language, "no_installed_languages"), None)
            self.lang_combo.setEnabled(False)
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
        # Показываем комбобокс выбора конкретного языка.
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
            target_codes = _translation_targets_for_source(source_code, get_cached_ocr_config())
            for language in APP_LANGUAGES:
                if language.code not in target_codes:
                    continue
                self.target_lang_combo.addItem(
                    _cached_qt_icon(language_icon_path(language.code)),
                    language.short_label,
                    language.code,
                )
            if self.target_lang_combo.count() == 0:
                interface_language = get_cached_ocr_config().get("interface_language", "en")
                self.target_lang_combo.addItem(
                    ocr_ui_text(interface_language, "no_installed_translation_pairs"),
                    None,
                )
                self.target_lang_combo.setEnabled(False)
            else:
                self.target_lang_combo.setEnabled(True)
                idx = self.target_lang_combo.findData(target_code)
                self.target_lang_combo.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self.target_lang_combo.blockSignals(False)
        self.current_target_language = self.target_lang_combo.currentData() or default_target_for_source(source_code)
        self._update_translate_swap_enabled()

    def _refresh_available_language_choices(self, config):
        available_codes = installed_ocr_language_codes(config=config)
        if self.mode == "translate" and str(config.get("translator_engine", "Google")).lower() == "argos":
            available_codes = [
                code for code in available_codes
                if _translation_targets_for_source(code, config)
            ]
        current_codes = [self.lang_combo.itemData(index) for index in range(self.lang_combo.count())]
        if current_codes == available_codes:
            return
        self.lang_combo.blockSignals(True)
        try:
            self.lang_combo.clear()
            for language in APP_LANGUAGES:
                if language.code not in available_codes:
                    continue
                self.lang_combo.addItem(
                    _cached_qt_icon(language_icon_path(language.code)),
                    language.short_label,
                    language.code,
                )
            if self.lang_combo.count() == 0:
                interface_language = config.get("interface_language", "en")
                self.lang_combo.addItem(
                    ocr_ui_text(interface_language, "no_installed_languages"),
                    None,
                )
                self.lang_combo.setEnabled(False)
            else:
                self.lang_combo.setEnabled(True)
        finally:
            self.lang_combo.blockSignals(False)

    def _current_translate_pair(self):
        source_code = _combo_data_to_ocr_language(self.lang_combo.currentData(), "en")
        target_code = None
        if self.target_lang_combo is not None:
            target_code = self.target_lang_combo.currentData()
        return source_code, default_target_for_source(source_code, target_code)

    def _update_translate_swap_enabled(self):
        button = self.translate_arrow_label
        if button is None or self.target_lang_combo is None:
            return
        source = self.lang_combo.currentData()
        target = self.target_lang_combo.currentData()
        reverse_targets = (
            _translation_targets_for_source(str(target), get_cached_ocr_config())
            if target else []
        )
        button.setEnabled(
            bool(
                source
                and target
                and self.lang_combo.findData(target) >= 0
                and str(source) in reverse_targets
            )
        )

    def _swap_translate_languages(self):
        if self.target_lang_combo is None:
            return
        source = self.lang_combo.currentData()
        target = self.target_lang_combo.currentData()
        if not source or not target or self.lang_combo.findData(target) < 0:
            self._update_translate_swap_enabled()
            return
        if str(source) not in _translation_targets_for_source(str(target), get_cached_ocr_config()):
            self._update_translate_swap_enabled()
            return
        self._updating_language_controls = True
        try:
            self.lang_combo.setCurrentIndex(self.lang_combo.findData(target))
            self.current_language = str(target)
            self.current_target_language = str(source)
            self._populate_translate_target_combo(str(source))
            target_index = self.target_lang_combo.findData(source)
            if target_index >= 0:
                self.target_lang_combo.setCurrentIndex(target_index)
        finally:
            self._updating_language_controls = False
        source_code, target_code = self._current_translate_pair()
        self.current_language = source_code
        self.current_target_language = target_code
        _write_ocr_config_updates({
            "last_ocr_language": source_code,
            "ocr_translate_source_language": source_code,
            "ocr_translate_target_language": target_code,
        })
        self._update_translate_swap_enabled()

    def _refresh_language_controls_from_config(self, config):
        self._updating_language_controls = True
        try:
            self._refresh_available_language_choices(config)
            if self.mode == "translate":
                source_code, target_code = _configured_ocr_translate_pair(config)
                source_idx = self.lang_combo.findData(source_code)
                if source_idx < 0 and self.lang_combo.count():
                    # The saved language is not installed for this engine (a
                    # config carried over from another machine, or a language
                    # pack that was removed). Fall back to the first installed
                    # one instead of leaving the control unselected.
                    source_idx = 0
                if source_idx >= 0:
                    self.lang_combo.setCurrentIndex(source_idx)
                self.current_language = self.lang_combo.currentData() or source_code
                self.current_target_language = target_code
                self._populate_translate_target_combo(target_code)
            else:
                language_code = _normalize_app_language_code(
                    config.get("last_ocr_language", self.current_language),
                    "ru",
                )
                idx = self.lang_combo.findData(language_code)
                if idx < 0 and self.lang_combo.count():
                    idx = 0  # saved language is not installed for this engine
                if idx >= 0:
                    self.lang_combo.setCurrentIndex(idx)
                self.current_language = self.lang_combo.currentData() or language_code
        finally:
            self._updating_language_controls = False

    @staticmethod
    def _get_active_screen():
        cursor_pos = QtGui.QCursor.pos()
        return QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()

    def _freeze_required(self):
        """Whether the overlay must paint a screenshot instead of being see-through.

        A translucent window only looks translucent where a compositing manager
        is running. GNOME and KDE composite; openbox, i3 and a plain XFCE do not,
        and there the selection overlay comes out solid black — the user drags a
        box across a black screen. Flameshot and NormCap both sidestep this by
        selecting on a frozen screenshot, so Linux does the same here whatever
        the setting says. Windows composites always and keeps the setting.
        """
        if platform_support.IS_LINUX:
            return True
        return bool(self._freeze_screen_on_ocr)

    def _capture_frozen_background(self, screen_rect):
        session_id = getattr(self, "_session_id", "unknown")
        if not self._freeze_required() or screen_rect.isNull():
            self._frozen_background = None
            self._frozen_background_rect = QtCore.QRect()
            logging.debug(
                f"[OCR:{session_id}] Frozen background skipped; required={self._freeze_required()}, "
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
                shot = grab_screen_pixmap(target_screen)
                logging.debug(
                    f"[OCR:{session_id}] Frozen grab attempt full screen; screen={_screen_to_text(target_screen)}, "
                    f"shot_null={shot.isNull()}, shot_size={shot.width()}x{shot.height()}, dpr={shot.devicePixelRatio():.3f}"
                )
                if shot.isNull():
                    shot = grab_screen_pixmap(target_screen, 0, 0, screen_rect.width(), screen_rect.height())
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
            self._ocr_status_text = ""
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
            # Raising the parent while a native QComboBox popup is open steals
            # focus from that popup on Windows. The list remains visible, but
            # the clicked row is never committed. Delayed topmost retries run
            # shortly after the overlay appears, exactly when a fast user opens
            # the language list, so leave the already-topmost window alone until
            # the popup closes.
            for combo in (self.lang_combo, self.target_lang_combo):
                if combo is not None and combo.view().isVisible():
                    return
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

    def _default_ocr_status_text(self):
        lang = get_cached_ocr_config().get("interface_language", "en")
        return ocr_ui_text(lang, "recognizing")

    @QtCore.pyqtSlot(str)
    def _set_ocr_status_text(self, text):
        self._ocr_status_text = str(text or "")
        self.update()

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

        if self._ocr_in_progress and getattr(self, "_ocr_status_text", ""):
            text = self._ocr_status_text
            font = QtGui.QFont("Segoe UI", 11)
            font.setWeight(QtGui.QFont.DemiBold)
            painter.setFont(font)
            metrics = QtGui.QFontMetrics(font)
            text_width = min(metrics.horizontalAdvance(text), max(120, self.width() - 80))
            box_width = min(max(220, text_width + 36), max(220, self.width() - 40))
            box_height = 42
            status_top = 132 if self.height() >= 220 else max(78, self.height() - box_height - 20)
            box = QtCore.QRect(
                max(20, (self.width() - box_width) // 2),
                status_top,
                box_width,
                box_height,
            )
            painter.setPen(QtGui.QPen(QtGui.QColor(140, 170, 210, 170), 1))
            painter.setBrush(QtGui.QColor(18, 22, 30, 232))
            painter.drawRoundedRect(box, 10, 10)
            painter.setPen(QtGui.QColor(245, 248, 252))
            painter.drawText(box.adjusted(14, 0, -14, 0), QtCore.Qt.AlignCenter, text)
            
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
            if self.lang_combo.currentData() is None or (
                self.mode == "translate"
                and self.target_lang_combo is not None
                and self.target_lang_combo.currentData() is None
            ):
                interface_language = get_cached_ocr_config().get("interface_language", "en")
                QMessageBox.information(
                    self,
                    "Language packages",
                    ocr_ui_text(interface_language, "install_languages_first"),
                )
                self.close()
                return
            self.last_rect = rect
            logging.info(f"[OCR:{self._session_id}] Selection accepted; rect=({_rect_to_text(rect)})")
            self._ocr_in_progress = True
            self._ocr_status_text = self._default_ocr_status_text()
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
                updates["last_ocr_language"] = source_code
                updates["ocr_translate_source_language"] = source_code
                updates["ocr_translate_target_language"] = target_code
                self._update_translate_swap_enabled()
            if _write_ocr_config_updates(updates):
                logging.info(f"Saved OCR language: {updates['last_ocr_language']}")

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            logging.info("Нажата клавиша ESC, завершаем OCR.")
            self.close()

    @staticmethod
    def get_ocr_engine():
        """Return selected OCR engine from config.json."""
        return usable_ocr_engine(
            get_cached_ocr_config().get("ocr_engine", platform_support.default_ocr_engine())
        )

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

        msg.setWindowTitle(ocr_ui_text(interface_lang, "win_missing_title"))
        if not _WINRT_AVAILABLE:
            msg.setText(ocr_ui_text(interface_lang, "win_unavailable"))
            details = ocr_ui_text(interface_lang, "win_components")
        else:
            msg.setText(
                ocr_ui_text(interface_lang, "win_unsupported", language=language_name, tag=win_lang_tag)
            )
            details = ocr_ui_text(interface_lang, "win_pack")
        if fallback_available:
            details += "\n\n" + ocr_ui_text(interface_lang, "win_continue")
        else:
            details += "\n\n" + ocr_ui_text(interface_lang, "win_stopped")
        open_text = ocr_ui_text(interface_lang, "open_windows")
        continue_text = ocr_ui_text(interface_lang, "continue_tesseract")
        close_text = ocr_ui_text(interface_lang, "close")

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
        return _configure_installed_tesseract_data(tess_cmd, tess_lang)

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
            pixmap = grab_screen_pixmap(
                target_screen,
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

    def _start_rapidocr_worker(self, pil_variants, context, session_id):
        self.ocr_worker = RapidOCRWorker(
            pil_variants,
            context,
            session_id,
        )
        self._ocr_worker_session_id = session_id
        self.ocr_worker.status_update.connect(self._set_ocr_status_text)
        self.ocr_worker.result_ready.connect(lambda text, sid=session_id: self.handle_ocr_result(text, sid))
        self.ocr_worker.finished.connect(self.ocr_worker.deleteLater)
        self.ocr_worker.start()

    def _start_easyocr_worker(self, pil_variants, language_code, context, session_id):
        self.ocr_worker = EasyOCRWorker(
            pil_variants,
            language_code,
            context,
            session_id,
        )
        self._ocr_worker_session_id = session_id
        self.ocr_worker.status_update.connect(self._set_ocr_status_text)
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
        from PIL import Image, ImageEnhance, ImageOps, ImageStat

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
            language_code = source_code
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

        if ocr_engine_type in {"rapidocr", "rapid"}:
            rapid_variants = [
                (label, image.convert("RGB") if image.mode != "RGB" else image)
                for label, image in ocr_pil_variants
            ]
            self._start_rapidocr_worker(rapid_variants, "primary", session_id)
            return  # RapidOCR сам делает text detection + recognition и возвращает confidence

        if ocr_engine_type in {"easyocr", "easy"}:
            easy_variants = [
                (label, image.convert("RGB") if image.mode != "RGB" else image)
                for label, image in ocr_pil_variants
            ]
            self._start_easyocr_worker(easy_variants, language_code, "primary", session_id)
            return  # EasyOCR использует выбранный язык + английский fallback для смешанного текста

        # По умолчанию используем Windows OCR (без PIL)
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
        self.ocr_worker.status_update.connect(self._set_ocr_status_text)
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
            self._ocr_status_text = ""

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
                    auto_copy = config.get("copy_translated_text", False)
                    # Ленивый импорт для избежания циклического импорта
                    from main import (
                        result_window_hidden_for,
                        show_translation_dialog,
                        save_copy_history,
                    )

                    if result_window_hidden_for(config, "area"):
                        platform_support.copy_text(translated_text)
                        save_copy_history(translated_text)
                        save_translation_history(text, translated_text, target_code)
                        self.close()
                        return

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

                    show_translation_dialog(
                        dialog_parent,
                        translated_text,
                        auto_copy=auto_copy,
                        lang=lang,
                        theme=theme,
                        source_text=text,
                        source_lang=source_code,
                        target_lang=target_code,
                        result_mode="area",
                    )
                    # Сохраняем переводы в историю (исходный текст и перевод)
                    save_translation_history(text, translated_text, target_code)
                self.close()
            else:
                try:
                    # Ленивый импорт для избежания циклического импорта
                    from main import save_copy_history
                    platform_support.copy_text(text)
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
            worker = getattr(self, "ocr_worker", None)
            failure_reason = getattr(worker, "failure_reason", "") if worker is not None else ""
            
            msg.setWindowTitle(ocr_ui_text(lang, "recognition_failed"))
            if failure_reason in {"rapidocr_unavailable", "easyocr_unavailable"}:
                engine = "RapidOCR" if failure_reason.startswith("rapid") else "EasyOCR"
                msg.setText(ocr_ui_text(lang, "engine_unavailable", engine=engine))
                msg.setInformativeText(ocr_ui_text(lang, "engine_unavailable_info", engine=engine))
            elif failure_reason in {
                "rapidocr_empty", "rapidocr_error", "low_rapidocr_confidence",
                "easyocr_empty", "easyocr_error", "low_easyocr_confidence",
            }:
                engine = "RapidOCR" if failure_reason.startswith("rapid") or "rapidocr" in failure_reason else "EasyOCR"
                msg.setText(ocr_ui_text(lang, "engine_unreliable", engine=engine))
                msg.setInformativeText(ocr_ui_text(lang, "engine_unreliable_info", engine=engine))
            elif failure_reason == "auto_low_confidence_or_empty":
                msg.setText(ocr_ui_text(lang, "auto_unreliable"))
                msg.setInformativeText(ocr_ui_text(lang, "auto_unreliable_info"))
            else:
                msg.setText(ocr_ui_text(lang, "not_recognized"))
                msg.setInformativeText(ocr_ui_text(lang, "not_recognized_info"))
            
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

def _is_gui_thread():
    app = QApplication.instance()
    return app is not None and QtCore.QThread.currentThread() == app.thread()


def prepare_overlay(mode="ocr"):
    """Cache an overlay without ever constructing QWidget objects off-thread."""
    if not _is_gui_thread():
        logging.warning(
            "Skipped OCR overlay preparation outside QApplication's GUI thread; "
            "the overlay will be prepared by the queued GUI callback or lazily on first use"
        )
        return False
    try:
        cached = _OVERLAY_POOL.get(mode)
        if cached is not None and cached.thread() != QApplication.instance().thread():
            logging.warning(f"Discarding {mode} OCR overlay with invalid thread affinity")
            _OVERLAY_POOL[mode] = None
            cached = None
        if cached is None:
            _OVERLAY_POOL[mode] = ScreenCaptureOverlay(mode, defer_show=True)
        return True
    except Exception:
        _OVERLAY_POOL[mode] = None
        logging.exception(f"Could not prepare {mode} OCR overlay")
        return False

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
    app = QApplication.instance()
    if ov is not None and app is not None and ov.thread() != app.thread():
        logging.warning(f"Ignoring cached {mode} OCR overlay created outside the GUI thread")
        _OVERLAY_POOL[mode] = None
        ov = None
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
        install_qt_exception_guard()
        app._native_dialog_frame_filter = NativeDialogFrameFilter(app)
        app.installEventFilter(app._native_dialog_frame_filter)
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

def _group_screen_ocr_lines(lines_data):
    """Return stable visual lines, merging only fragments on the same baseline.

    Full-screen translation is a replacement layer, not a collection of
    floating translation cards.  Keeping separate OCR rows separate lets each
    translated row cover the exact source row underneath it.  Some engines do
    split one visual row into two fragments, so those fragments are merged only
    when they substantially overlap vertically and are separated by a small
    horizontal gap.
    """
    lines = []
    for item in lines_data or []:
        if not isinstance(item, (list, tuple)) or len(item) < 5:
            continue
        try:
            x, y, width, height = (float(item[0]), float(item[1]), float(item[2]), float(item[3]))
        except (TypeError, ValueError):
            continue
        text = str(item[4] or "").strip()
        if not text or width <= 0 or height <= 0:
            continue
        lines.append((x, y, width, height, text))
    lines.sort(key=lambda item: (item[1], item[0]))

    groups = []
    for line in lines:
        x, y, width, height, _text = line
        best_group = None
        best_gap = None
        for group_index, group in enumerate(groups):
            left = min(item[0] for item in group)
            right = max(item[0] + item[2] for item in group)
            top = min(item[1] for item in group)
            bottom = max(item[1] + item[3] for item in group)
            vertical_overlap = max(0.0, min(y + height, bottom) - max(y, top))
            vertical_ratio = vertical_overlap / max(1.0, min(height, bottom - top))
            horizontal_gap = max(0.0, max(left, x) - min(right, x + width))
            same_baseline = vertical_ratio >= 0.58
            close_fragment = horizontal_gap <= max(18.0, 1.25 * max(height, bottom - top))
            if not (same_baseline and close_fragment):
                continue
            if best_gap is None or horizontal_gap < best_gap:
                best_group = group_index
                best_gap = horizontal_gap
        if best_group is None:
            groups.append([line])
        else:
            groups[best_group].append(line)

    blocks = []
    for group in groups:
        min_x = min(item[0] for item in group)
        min_y = min(item[1] for item in group)
        max_x = max(item[0] + item[2] for item in group)
        max_y = max(item[1] + item[3] for item in group)
        ordered = sorted(group, key=lambda item: item[0])
        text = " ".join(item[4] for item in ordered)
        blocks.append((min_x, min_y, max_x - min_x, max_y - min_y, text))
    blocks.sort(key=lambda item: (item[1], item[0]))
    return blocks


def _split_marked_screen_translation(translated, count):
    marker_re = re.compile(r"\[\[\[\s*CXT(\d{4})\s*\]\]\]", re.IGNORECASE)
    matches = list(marker_re.finditer(str(translated or "")))
    if len(matches) != count:
        return None
    result = [""] * count
    seen = set()
    for index, match in enumerate(matches):
        block_index = int(match.group(1))
        if block_index < 0 or block_index >= count or block_index in seen:
            return None
        seen.add(block_index)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(translated)
        result[block_index] = str(translated[start:end]).strip()
    if seen != set(range(count)) or any(not value for value in result):
        return None
    return result


def _translate_screen_texts(texts, translate_func, source_code, target_code):
    """Translate blocks in one request while preserving mapping; safely fall back per block."""
    values = [str(text or "").strip() for text in texts]
    if not values:
        return []

    def translate_chunk(chunk):
        if len(chunk) == 1:
            return [str(translate_func(chunk[0], source_code, target_code) or "").strip()]
        marked = "\n".join(
            f"[[[CXT{index:04d}]]]\n{text}"
            for index, text in enumerate(chunk)
        )
        translated = translate_func(marked, source_code, target_code)
        mapped = _split_marked_screen_translation(translated, len(chunk))
        if mapped is not None:
            return mapped
        logging.warning("Fullscreen translation did not preserve block markers; retrying blocks separately")
        return [
            str(translate_func(text, source_code, target_code) or "").strip()
            for text in chunk
        ]

    # Provider limits differ. Small ordered batches avoid rejecting a text-rich
    # screen while still using far fewer network calls than one request per OCR
    # rectangle.
    translated_values = []
    chunk = []
    chunk_length = 0
    for value in values:
        marker_cost = 18
        if chunk and (len(chunk) >= 24 or chunk_length + len(value) + marker_cost > 3500):
            translated_values.extend(translate_chunk(chunk))
            chunk = []
            chunk_length = 0
        chunk.append(value)
        chunk_length += len(value) + marker_cost
    if chunk:
        translated_values.extend(translate_chunk(chunk))
    return translated_values


class FullScreenOCRWorker(QtCore.QThread):
    """OCR worker that returns text lines with bounding box positions."""

    # Must stay `object` (PyQt_PyObject).  `pyqtSignal(list)` compiles to
    # `result_ready(QVariantList)`, which refuses to connect to the
    # `@pyqtSlot(object)` receiver and would also flatten the (x, y, w, h, text)
    # tuples through QVariant.
    result_ready = QtCore.pyqtSignal(object)  # list of (x, y, w, h, text)

    def __init__(self, bitmap, language_code="ru", parent=None):
        super().__init__(parent)
        self.bitmap = bitmap
        self.language_code = language_code

    def run(self):
        lines_data = []
        try:
            if self.isInterruptionRequested():
                return
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

            if self.isInterruptionRequested():
                return

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

        if not self.isInterruptionRequested():
            self.result_ready.emit(lines_data)


class FullScreenTranslateOverlay(QWidget):
    """Overlay that translates all visible text on screen and shows translations at original positions."""

    _translation_result_ready = QtCore.pyqtSignal(int, object, str)

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
        self._ocr_workers = set()
        self._pending_translation_pair = None
        self._translation_run_id = 0
        self._is_dragging = False
        self._drag_offset = QtCore.QPoint()
        self._translation_result_ready.connect(self._apply_translation_result)
        self._rerun_timer = QtCore.QTimer(self)
        self._rerun_timer.setSingleShot(True)
        self._rerun_timer.setInterval(180)
        self._rerun_timer.timeout.connect(self._restart_translation_from_controls)

        # Read config
        config = get_cached_ocr_config()
        saved_src = _normalize_app_language_code(
            config.get("fullscreen_translate_from") or config.get("ocr_translate_source_language"),
            "en",
        )
        saved_tgt = default_target_for_source(
            saved_src,
            config.get("fullscreen_translate_to") or config.get("ocr_translate_target_language"),
        )

        # Capture screenshot from the screen where cursor is
        cursor_pos = QtGui.QCursor.pos()
        target_screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        geo = target_screen.geometry()

        self.screenshot = grab_screen_pixmap(target_screen, 0, 0, geo.width(), geo.height())
        self._ocr_scale_x = (self.screenshot.width() / geo.width()) if geo.width() and not self.screenshot.isNull() else 1.0
        self._ocr_scale_y = (self.screenshot.height() / geo.height()) if geo.height() and not self.screenshot.isNull() else 1.0
        self.setGeometry(geo)

        # Full-screen OCR needs an installed Windows OCR language, while the
        # translation target depends on the selected translator. Keep these as
        # two independent controls so any valid direction can be chosen.
        self.lang_combo = QtWidgets.QComboBox(self)
        self.target_lang_combo = QtWidgets.QComboBox(self)
        self.translate_arrow_label = QtWidgets.QToolButton(self)
        self.translate_arrow_label.setText("⇄")
        self.translate_arrow_label.setCursor(QtCore.Qt.ArrowCursor)
        self.translate_arrow_label.setToolTip(
            ocr_ui_text(config.get("interface_language", "en"), "swap_languages")
        )
        fullscreen_config = dict(config)
        # Positional full-screen OCR uses Windows OCR's native line geometry.
        fullscreen_config["ocr_engine"] = "Windows"
        available_sources = installed_ocr_language_codes(config=fullscreen_config)
        if str(config.get("translator_engine", "Google")).strip().lower() == "argos":
            available_sources = [
                code for code in available_sources
                if _translation_targets_for_source(code, config)
            ]
        for language in APP_LANGUAGES:
            if language.code not in available_sources:
                continue
            self.lang_combo.addItem(
                _cached_qt_icon(language_icon_path(language.code)),
                language.short_label,
                language.code,
            )
        no_source_languages = self.lang_combo.count() == 0
        if no_source_languages:
            self.lang_combo.addItem(
                ocr_ui_text(config.get("interface_language", "en"), "no_installed_languages"),
                None,
            )
        # Восстанавливаем последний выбор
        default_idx = self.lang_combo.findData(saved_src)
        if default_idx < 0:
            default_idx = 0
        self.lang_combo.setCurrentIndex(default_idx)

        self.translate_arrow_label.setStyleSheet("""
            QToolButton {
                color: #d8e3f2;
                font-size: 17px;
                font-weight: 700;
                background-color: rgba(22, 25, 31, 244);
                border: 1px solid rgba(105, 123, 150, 130);
                border-radius: 11px;
            }
            QToolButton:hover {
                background-color: rgba(40, 47, 60, 252);
                border-color: rgba(160, 186, 220, 220);
            }
            QToolButton:disabled {
                color: rgba(118, 128, 143, 180);
                border-color: rgba(73, 82, 96, 110);
            }
        """)
        combo_style = """
            QComboBox {
                background-color: rgba(25, 29, 37, 248);
                color: #f6f8fb;
                border: 1px solid rgba(110, 130, 158, 155);
                border-radius: 11px;
                padding: 7px 9px;
                font-size: 15px;
                font-weight: 750;
                font-family: 'Segoe UI Semibold', 'Segoe UI', Arial, sans-serif;
            }
            QComboBox:hover {
                background-color: rgba(31, 37, 48, 252);
                border: 1px solid rgba(145, 171, 205, 190);
            }
            QComboBox::drop-down { border: none; width: 0px; }
            QComboBox::down-arrow { image: none; width: 0px; height: 0px; }
            QComboBox QAbstractItemView {
                background-color: #11151c;
                color: #f5f7fa;
                border: 1px solid rgba(92, 112, 140, 210);
                border-radius: 12px;
                padding: 7px 3px 7px 5px;
                selection-background-color: #365172;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 4px 7px;
                border-radius: 9px;
                margin: 2px 4px 2px 1px;
            }
            QComboBox QAbstractItemView::item:hover { background-color: #243044; }
        """
        for combo in (self.lang_combo, self.target_lang_combo):
            combo.setIconSize(QtCore.QSize(30, 30))
            combo.setStyleSheet(combo_style)
            combo.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            combo.view().setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            combo.view().setTextElideMode(QtCore.Qt.ElideNone)
            combo.setFixedSize(112, 48)
        self.translate_arrow_label.setFixedSize(32, 48)
        self._populate_fullscreen_target_combo(saved_tgt)

        self.lang_combo.currentIndexChanged.connect(self._on_fullscreen_source_changed)
        self.target_lang_combo.currentIndexChanged.connect(self._on_fullscreen_target_changed)
        self.translate_arrow_label.clicked.connect(self._swap_fullscreen_languages)
        controls_enabled = not no_source_languages and self.target_lang_combo.currentData() is not None
        self.lang_combo.setEnabled(not no_source_languages)
        self.target_lang_combo.setEnabled(controls_enabled)

        # Позиционируем элементы по центру сверху
        total_w = (
            self.lang_combo.width() + 8 + self.translate_arrow_label.width() + 8
            + self.target_lang_combo.width()
        )
        start_x = (geo.width() - total_w) // 2
        top_y = 30
        self.lang_combo.move(start_x, top_y)
        next_x = start_x + self.lang_combo.width() + 8
        self.translate_arrow_label.move(next_x, top_y)
        next_x += self.translate_arrow_label.width() + 8
        self.target_lang_combo.move(next_x, top_y)

        logging.info(f"FullScreenOverlay: screen geo={geo}, screenshot size={self.screenshot.width()}x{self.screenshot.height()}")

        self.show()
        self.raise_()
        self.activateWindow()
        if controls_enabled:
            QtCore.QTimer.singleShot(0, self._restart_translation_from_controls)

    def _populate_fullscreen_target_combo(self, selected_target=None):
        source_code = _combo_data_to_ocr_language(self.lang_combo.currentData(), "en")
        target_code = default_target_for_source(source_code, selected_target)
        self.target_lang_combo.blockSignals(True)
        try:
            self.target_lang_combo.clear()
            available_targets = _translation_targets_for_source(source_code, get_cached_ocr_config())
            for language in APP_LANGUAGES:
                if language.code not in available_targets:
                    continue
                self.target_lang_combo.addItem(
                    _cached_qt_icon(language_icon_path(language.code)),
                    language.short_label,
                    language.code,
                )
            if self.target_lang_combo.count() == 0:
                interface_language = get_cached_ocr_config().get("interface_language", "en")
                self.target_lang_combo.addItem(
                    ocr_ui_text(interface_language, "no_installed_translation_pairs"),
                    None,
                )
                self.target_lang_combo.setEnabled(False)
            else:
                idx = self.target_lang_combo.findData(target_code)
                self.target_lang_combo.setCurrentIndex(idx if idx >= 0 else 0)
                self.target_lang_combo.setEnabled(True)
        finally:
            self.target_lang_combo.blockSignals(False)
        self._update_fullscreen_swap_enabled()

    def _on_fullscreen_source_changed(self):
        previous_target = self.target_lang_combo.currentData()
        self._populate_fullscreen_target_combo(previous_target)
        self._on_fullscreen_target_changed()

    def _on_fullscreen_target_changed(self):
        self._update_fullscreen_swap_enabled()
        if self._persist_fullscreen_pair():
            self._rerun_timer.start()

    def _update_fullscreen_swap_enabled(self):
        source = self.lang_combo.currentData()
        target = self.target_lang_combo.currentData()
        reverse_targets = (
            _translation_targets_for_source(str(target), get_cached_ocr_config())
            if target else []
        )
        self.translate_arrow_label.setEnabled(
            bool(
                source
                and target
                and self.lang_combo.findData(target) >= 0
                and str(source) in reverse_targets
            )
        )

    def _swap_fullscreen_languages(self):
        source = self.lang_combo.currentData()
        target = self.target_lang_combo.currentData()
        if not source or not target or self.lang_combo.findData(target) < 0:
            self._update_fullscreen_swap_enabled()
            return
        if str(source) not in _translation_targets_for_source(str(target), get_cached_ocr_config()):
            self._update_fullscreen_swap_enabled()
            return
        self.lang_combo.blockSignals(True)
        try:
            self.lang_combo.setCurrentIndex(self.lang_combo.findData(target))
        finally:
            self.lang_combo.blockSignals(False)
        self._populate_fullscreen_target_combo(str(source))
        target_index = self.target_lang_combo.findData(source)
        if target_index >= 0:
            self.target_lang_combo.setCurrentIndex(target_index)
        self._on_fullscreen_target_changed()

    def _persist_fullscreen_pair(self):
        source_code = self.lang_combo.currentData()
        target_code = self.target_lang_combo.currentData()
        valid = source_code in APP_LANGUAGE_CODES and target_code in APP_LANGUAGE_CODES and source_code != target_code
        if valid:
            _write_ocr_config_updates({
                "fullscreen_translate_from": source_code,
                "fullscreen_translate_to": target_code,
            })
        return bool(valid)

    def _restart_translation_from_controls(self):
        """Immediately rerun OCR and translation for the selected direction."""
        if not self._persist_fullscreen_pair():
            return
        self.src_lang = _combo_data_to_ocr_language(self.lang_combo.currentData(), "en")
        self.tgt_lang = _normalize_app_language_code(
            self.target_lang_combo.currentData(),
            default_target_for_source(self.src_lang),
        )
        if self.src_lang == self.tgt_lang:
            return
        self.ocr_language = self.src_lang
        self._translation_run_id += 1
        self.loading = True
        self.translated_blocks.clear()
        self.error_message = None
        self.update()

        # Windows OCR cannot reliably process the same full-screen bitmap from
        # several language workers at once. Keep only the newest requested pair
        # and let the currently running native call finish; its result is already
        # invalidated by translation_run_id and will be ignored.
        self._pending_translation_pair = (self.src_lang, self.tgt_lang)
        if self._ocr_workers:
            logging.info(
                f"FullScreenOverlay: queued latest OCR pair "
                f"({self.src_lang}->{self.tgt_lang}); waiting for the active worker"
            )
            for worker in list(self._ocr_workers):
                try:
                    worker.requestInterruption()
                except RuntimeError:
                    pass
            return
        self._start_pending_fullscreen_ocr()

    def _start_pending_fullscreen_ocr(self):
        if self._ocr_workers or not self._pending_translation_pair:
            return
        source_code, target_code = self._pending_translation_pair
        self._pending_translation_pair = None
        run_id = self._translation_run_id
        logging.info(f"FullScreenOverlay: starting OCR ({source_code}->{target_code})")
        try:
            self._start_ocr(run_id, source_code, target_code)
        except Exception:
            # Anything that stops the OCR worker from starting must surface as a
            # visible error.  Qt swallows slot exceptions through the app-wide
            # guard, which previously left the overlay showing "Translating
            # screen..." forever.
            logging.exception("FullScreenOverlay: could not start screen OCR")
            self._fail_translation(run_id, "ocr_init_failed")

    def _fail_translation(self, run_id, message_key):
        """Leave the overlay in a readable failed state instead of loading forever."""
        if run_id != self._translation_run_id:
            return
        self.loading = False
        lang = get_cached_ocr_config().get("interface_language", "en")
        self.error_message = ocr_ui_text(lang, message_key)
        self.update()

    def _start_ocr(self, run_id, source_code, target_code):
        qimage = self.screenshot.toImage()
        bitmap = qimage_to_softwarebitmap(qimage)
        if bitmap is None:
            self._fail_translation(run_id, "ocr_init_failed")
            return

        worker = FullScreenOCRWorker(bitmap, source_code)
        worker.translation_run_id = run_id
        worker.translation_source_code = source_code
        worker.translation_target_code = target_code
        self.ocr_worker = worker
        self._ocr_workers.add(worker)
        worker.result_ready.connect(self._on_fullscreen_ocr_result)
        worker.finished.connect(self._release_finished_ocr_worker)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    @QtCore.pyqtSlot(object)
    def _on_fullscreen_ocr_result(self, lines):
        worker = self.sender() or self.ocr_worker
        if worker is None:
            return
        self._on_ocr_complete(
            lines,
            int(getattr(worker, "translation_run_id", -1)),
            str(getattr(worker, "translation_source_code", "")),
            str(getattr(worker, "translation_target_code", "")),
        )

    @QtCore.pyqtSlot()
    def _release_finished_ocr_worker(self):
        worker = self.sender()
        if worker is None:
            return
        self._ocr_workers.discard(worker)
        if not self._ocr_workers and self._pending_translation_pair and self.isVisible():
            QtCore.QTimer.singleShot(0, self._start_pending_fullscreen_ocr)

    def _on_ocr_complete(self, lines_data, run_id, source_code, target_code):
        if run_id != self._translation_run_id:
            return
        if not lines_data:
            self._fail_translation(run_id, "screen_no_text")
            return

        try:
            self._lines_data = _group_screen_ocr_lines(lines_data)
            import threading
            threading.Thread(
                target=self._translate_all,
                args=(run_id, list(self._lines_data), source_code, target_code),
                daemon=True,
            ).start()
        except Exception:
            logging.exception("FullScreenOverlay: could not start screen translation")
            self._fail_translation(run_id, "translation_failed")

    def _translate_all(self, run_id, lines_data, source_code, target_code):
        blocks = []
        error_message = ""
        try:
            from translater import translate_text

            src, tgt = source_code, target_code
            logging.info(f"FullScreenOverlay: translating {len(lines_data)} blocks ({src}->{tgt})")

            all_texts = [item[4] for item in lines_data]
            translated_texts = _translate_screen_texts(all_texts, translate_text, src, tgt)

            if translated_texts and any(translated_texts):
                for i, (x, y, w, h, orig) in enumerate(lines_data):
                    tr = translated_texts[i].strip() if i < len(translated_texts) else orig
                    if not tr:
                        tr = orig
                    blocks.append(
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
                error_message = ocr_ui_text(lang, "translation_failed")
        except Exception as e:
            error_message = str(e)

        self._translation_result_ready.emit(run_id, blocks, error_message)

    @QtCore.pyqtSlot(int, object, str)
    def _apply_translation_result(self, run_id, blocks, error_message):
        if run_id != self._translation_run_id:
            return
        self.translated_blocks = list(blocks or [])
        self.error_message = str(error_message or "") or None
        self.loading = False
        if self.translated_blocks and not self.error_message:
            original_text = "\n".join(str(block[1] or "") for block in self.translated_blocks)
            translated_text = "\n".join(str(block[2] or "") for block in self.translated_blocks)
            save_translation_history(original_text, translated_text, self.tgt_lang)
        self.update()

    # ---- painting --------------------------------------------------

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)

        # Screenshot as background
        painter.drawPixmap(0, 0, self.screenshot)
        # Keep the original screen intact after translation.  Dimming is only
        # useful while choosing a direction or waiting for OCR; replacement
        # mode should look like the source words themselves were changed.
        if self.loading or self.error_message or not self.translated_blocks:
            painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 72))

        if self.loading:
            self._paint_loading(painter)
        elif self.error_message:
            self._paint_center_msg(painter, self.error_message, QtGui.QColor(80, 20, 20, 230))
        elif self.translated_blocks:
            source_rects = [
                QtCore.QRectF(block[0]).normalized()
                for block in self.translated_blocks
            ]
            occupied = []
            painted_blocks = []
            for block_index, (rect_f, original, translated) in enumerate(self.translated_blocks):
                layout = self._translation_block_layout(
                    rect_f,
                    original,
                    translated,
                    occupied=occupied,
                    obstacles=[
                        source_rect
                        for source_index, source_rect in enumerate(source_rects)
                        if source_index != block_index
                    ],
                )
                occupied.append(layout[0])
                painted_blocks.append((rect_f, original, translated, layout))

            # Paint every replacement background first.  Text is painted in a
            # second pass so an adjacent background can never erase glyphs that
            # were already drawn during the same frame.
            for rect_f, original, translated, layout in painted_blocks:
                self._paint_block(
                    painter,
                    rect_f,
                    original,
                    translated,
                    layout=layout,
                    draw_text=False,
                )
            for rect_f, original, translated, layout in painted_blocks:
                self._paint_block(
                    painter,
                    rect_f,
                    original,
                    translated,
                    layout=layout,
                    draw_background=False,
                )
            self._paint_hint(painter)
        # else: начальный экран — комбо-бокс и кнопка видны поверх скриншота

        painter.end()

    def _paint_loading(self, painter):
        config = get_cached_ocr_config()
        lang = config.get("interface_language", "en")
        text = ocr_ui_text(lang, "translating_screen")
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

    def _translation_block_layout(
        self,
        rect_f,
        original,
        text,
        occupied=None,
        obstacles=None,
    ):
        # Each Windows OCR result is a visual line.  Keep its translation on one
        # line as well: wrapping a long translation inside a tiny source height
        # created tall side cards and overlapping fragments.  The replacement
        # may grow horizontally, but only through space where no other OCR line
        # or translated block exists.
        pad = 2.0
        screen_margin = 8.0
        bounds = QtCore.QRectF(
            screen_margin,
            screen_margin,
            max(1.0, self.width() - screen_margin * 2),
            max(1.0, self.height() - screen_margin * 2),
        )
        source_rect = QtCore.QRectF(rect_f).normalized()
        source_rect = source_rect.adjusted(-pad, -pad, pad, pad).intersected(bounds)
        if source_rect.isEmpty():
            source_rect = QtCore.QRectF(
                bounds.left(),
                bounds.top(),
                max(1.0, min(bounds.width(), rect_f.width())),
                max(1.0, min(bounds.height(), rect_f.height())),
            )

        left_limit = bounds.left()
        right_limit = bounds.right()
        blocker_gap = 3.0
        for blocker in list(obstacles or ()) + list(occupied or ()):
            blocker = QtCore.QRectF(blocker).normalized().intersected(bounds)
            if blocker.isEmpty():
                continue
            vertical_overlap = max(
                0.0,
                min(source_rect.bottom(), blocker.bottom())
                - max(source_rect.top(), blocker.top()),
            )
            minimum_overlap = max(
                2.0,
                min(source_rect.height(), blocker.height()) * 0.35,
            )
            if vertical_overlap < minimum_overlap:
                continue
            if blocker.right() <= source_rect.left():
                left_limit = max(left_limit, blocker.right() + blocker_gap)
            elif blocker.left() >= source_rect.right():
                right_limit = min(right_limit, blocker.left() - blocker_gap)

        left_limit = min(left_limit, source_rect.left())
        right_limit = max(right_limit, source_rect.right())
        corridor_width = max(source_rect.width(), right_limit - left_limit)
        # Do not let one tiny OCR fragment turn into a card spanning half the
        # screen.  A modest local expansion plus font fitting is less invasive
        # and preserves nearby imagery that OCR did not recognize as text.
        local_width_cap = max(
            source_rect.width() * 2.2,
            source_rect.width() + 160.0,
        )
        available_width = max(
            source_rect.width(),
            min(corridor_width, local_width_cap),
        )
        source_line_height = max(8.0, rect_f.height())
        start_font_size = max(7, min(30, int(source_line_height * 0.72)))
        flags = QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter | QtCore.Qt.TextSingleLine

        chosen_font = QtGui.QFont("Segoe UI", 6)
        required_width = source_rect.width()
        for font_size in range(start_font_size, 5, -1):
            font = QtGui.QFont("Segoe UI", font_size)
            metrics = QtGui.QFontMetrics(font)
            measured_width = metrics.horizontalAdvance(str(text or "")) + pad * 2
            measured_height = metrics.height() + 1
            chosen_font = font
            required_width = measured_width
            if (
                measured_width <= available_width
                and measured_height <= source_rect.height()
            ):
                break

        required_width = min(available_width, max(source_rect.width(), required_width))
        desired_left = source_rect.center().x() - required_width / 2.0
        desired_left = max(left_limit, min(desired_left, right_limit - required_width))
        bg_rect = QtCore.QRectF(
            desired_left,
            source_rect.top(),
            required_width,
            source_rect.height(),
        ).intersected(bounds)

        # Extremely long unbroken strings can still exceed the whole free
        # corridor at 6 pt.  Condense only as a last resort, keeping the full
        # translation visible instead of clipping or replacing it with an
        # ellipsis.
        available_text_width = max(1.0, bg_rect.width() - pad * 2)
        measured_width = QtGui.QFontMetrics(chosen_font).horizontalAdvance(str(text or ""))
        if measured_width > available_text_width:
            stretch = max(50, min(100, int(100 * available_text_width / measured_width)))
            chosen_font.setStretch(stretch)

        draw_rect = bg_rect.adjusted(pad, 0.0, -pad, 0.0)
        return bg_rect, draw_rect, chosen_font, flags

    def _paint_block(
        self,
        painter,
        rect_f,
        original,
        text,
        layout=None,
        draw_background=True,
        draw_text=True,
    ):
        bg_rect, draw_rect, font, flags = layout or self._translation_block_layout(
            rect_f, original, text
        )
        background, foreground = self._replacement_palette(
            QtCore.QRectF(rect_f).normalized().adjusted(-2, -2, 2, 2)
        )
        if draw_background:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(background)
            painter.drawRect(bg_rect)
        if draw_text:
            painter.setFont(font)
            painter.setPen(foreground)
            measured_width = painter.fontMetrics().horizontalAdvance(str(text or ""))
            if measured_width > draw_rect.width() and measured_width > 0:
                # QFont stretch has platform-specific rounding.  A final
                # painter transform guarantees that the last glyph remains
                # visible instead of being clipped at the rectangle edge.
                horizontal_scale = max(0.05, draw_rect.width() / measured_width)
                painter.save()
                painter.setClipRect(bg_rect)
                painter.translate(draw_rect.left(), 0)
                painter.scale(horizontal_scale, 1.0)
                scaled_rect = QtCore.QRectF(
                    0,
                    draw_rect.top(),
                    draw_rect.width() / horizontal_scale,
                    draw_rect.height(),
                )
                painter.drawText(scaled_rect, flags, text)
                painter.restore()
            else:
                painter.drawText(draw_rect, flags, text)

    def _replacement_palette(self, rect_f):
        """Estimate the source area's background and readable foreground.

        Sampling the perimeter avoids most glyph pixels and gives a simple
        local inpainting effect for white documents, dark game UI, and colored
        menu bars without introducing detached purple cards.
        """
        image = self.screenshot.toImage()
        if image.isNull():
            return QtGui.QColor(17, 15, 31, 252), QtGui.QColor(247, 243, 255)
        ratio = float(self.screenshot.devicePixelRatioF() or 1.0)
        left = max(0.0, rect_f.left())
        right = min(float(self.width() - 1), rect_f.right())
        top = max(0.0, rect_f.top())
        bottom = min(float(self.height() - 1), rect_f.bottom())
        samples = []

        def add_sample(x, y):
            px = max(0, min(image.width() - 1, int(round(x * ratio))))
            py = max(0, min(image.height() - 1, int(round(y * ratio))))
            color = image.pixelColor(px, py)
            samples.append((color.red(), color.green(), color.blue()))

        for step in range(13):
            fraction = step / 12.0
            x = left + (right - left) * fraction
            y = top + (bottom - top) * fraction
            add_sample(x, top)
            add_sample(x, bottom)
            add_sample(left, y)
            add_sample(right, y)
        if not samples:
            return QtGui.QColor(17, 15, 31, 252), QtGui.QColor(247, 243, 255)

        def median(channel):
            values = sorted(sample[channel] for sample in samples)
            return values[len(values) // 2]

        red, green, blue = median(0), median(1), median(2)
        background = QtGui.QColor(red, green, blue, 252)
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        foreground = (
            QtGui.QColor(22, 22, 25)
            if luminance >= 145
            else QtGui.QColor(250, 248, 253)
        )
        return background, foreground

    def _paint_hint(self, painter):
        config = get_cached_ocr_config()
        lang = config.get("interface_language", "en")
        hint = ocr_ui_text(lang, "fullscreen_hint")
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
        self._translation_run_id += 1
        self._rerun_timer.stop()
        self._pending_translation_pair = None
        for worker in list(self._ocr_workers):
            try:
                worker.requestInterruption()
            except RuntimeError:
                pass
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
