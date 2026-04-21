import json
import getpass
import os
import sys
import warnings  # suppress noisy third-party warnings
# гасим предупреждение pkg_resources ДО первых сторонних импортов
warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API",
    category=UserWarning,
)
warnings.filterwarnings("ignore", category=UserWarning, module=r"pkg_resources")
import winreg
import subprocess
import ctypes
import threading
import time
import pyperclip
from ctypes import wintypes
import psutil
import datetime
import urllib.parse
import webbrowser

from PyQt5 import QtCore
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QComboBox,
                             QWidget, QPushButton, QSystemTrayIcon, QMenu, QMessageBox, QLineEdit, QTextEdit, QDialog, QHBoxLayout, QCheckBox, QSpacerItem, QSizePolicy, QProgressDialog)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QIcon
from settings_window import SettingsWindow
from app_version import APP_VERSION
import translater  # Импорт модуля перевода

# --- Единственная константа с дефолтной конфигурацией ---
DEFAULT_CONFIG = {
    "theme": "Темная",
    "interface_language": "en",
    "autostart": False,
    "translation_mode": "English",
    "copy_hotkey": "Ctrl+Alt+C",
    "translate_hotkey": "Ctrl+Alt+T",
    "notifications": False,
    "history": False,
    "start_minimized": False,
    "show_update_info": True,  # Показывать Welcome окно при первом запуске
    "ocr_engine": "Windows",
    "translator_engine": "Google",
    "copy_history": False,
    "copy_translated_text": False,  # Все галочки отключены по умолчанию
    "keep_visible_on_ocr": False,
    "freeze_screen_on_ocr": False,
    "last_ocr_language": "ru",
    "no_screen_dimming": False,
    "fullscreen_translate_hotkey": "Ctrl+Alt+F",
    "translate_selection_hotkey": "Ctrl+Alt+Q"
}

# --- Глобальный кэш конфигурации ---
_config_cache = None
_config_mtime = 0

def get_cached_config():
    """Возвращает закэшированную конфигурацию, перечитывая только при изменении файла."""
    global _config_cache, _config_mtime
    config_path = get_data_file("config.json")
    try:
        mtime = os.path.getmtime(config_path)
        if _config_cache is None or mtime > _config_mtime:
            with open(config_path, "r", encoding="utf-8") as f:
                _config_cache = json.load(f)
            _config_mtime = mtime
    except Exception:
        if _config_cache is None:
            _config_cache = DEFAULT_CONFIG.copy()
    return _config_cache

def invalidate_config_cache():
    """Сбрасывает кэш конфигурации после записи."""
    global _config_cache, _config_mtime
    _config_cache = None
    _config_mtime = 0

# --- Константы для RegisterHotKey ---
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

APP_WINDOW_TITLE = "Click'n'Translate"
SINGLE_INSTANCE_MUTEX_NAME = "ClicknTranslate_SingleInstance_Mutex"
SINGLE_INSTANCE_SHOW_MESSAGE = "ClicknTranslate_ShowWindow_Message"
HWND_BROADCAST = 0xFFFF
ERROR_ALREADY_EXISTS = 183
SW_SHOW = 5
SW_RESTORE = 9

_SHOW_WINDOW_MESSAGE_ID = 0
if sys.platform == "win32":
    try:
        _SHOW_WINDOW_MESSAGE_ID = ctypes.windll.user32.RegisterWindowMessageW(SINGLE_INSTANCE_SHOW_MESSAGE)
    except Exception:
        _SHOW_WINDOW_MESSAGE_ID = 0

_main_window_ref = None
_single_instance_event_filter = None

def _show_running_instance():
    """Показать главное окно уже запущенного экземпляра."""
    app = QApplication.instance()
    if app is None:
        return

    target = _main_window_ref
    if target is None:
        for widget in app.topLevelWidgets():
            if hasattr(widget, "show_window_from_tray") and widget.windowTitle() == APP_WINDOW_TITLE:
                target = widget
                break
    if target is None:
        return

    try:
        target.show_window_from_tray(force_show=True)
    except Exception:
        pass

class _SingleInstanceMessageFilter(QtCore.QAbstractNativeEventFilter):
    """Глобальный фильтр системного сообщения активации уже запущенного экземпляра."""
    def nativeEventFilter(self, eventType, message):
        event_name = eventType.decode("utf-8", "ignore") if isinstance(eventType, bytes) else str(eventType)
        if _SHOW_WINDOW_MESSAGE_ID and event_name in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == _SHOW_WINDOW_MESSAGE_ID:
                    QTimer.singleShot(0, _show_running_instance)
                    return True, 0
            except Exception:
                pass
        return False, 0

# --- Диспетчер для безопасного вызова UI из потоков хоткеев ---
class _HotkeyDispatcher(QtCore.QObject):
    triggered = QtCore.pyqtSignal(object)

hotkey_dispatcher = _HotkeyDispatcher()

def simulate_copy():
    # Эмуляция нажатия Ctrl+C для копирования выделенного текста
    VK_CONTROL = 0x11
    VK_C = 0x43
    KEYEVENTF_KEYUP = 0x0002
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.02)  # Уменьшено с 0.05 для ускорения
    ctypes.windll.user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

def get_app_dir():
    """Directory with app resources (icons, etc). In PyInstaller — temp extraction dir."""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_portable_dir():
    """Directory next to the exe for portable data (config, history, cache).
    Settings survive program updates — user just replaces exe/program files."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def ensure_json_file(filepath, default_content):
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_content, f, ensure_ascii=False, indent=4)

def ensure_data_dir_and_files():
    data_dir = os.path.join(get_portable_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    config_path = os.path.join(data_dir, "config.json")
    ensure_json_file(config_path, DEFAULT_CONFIG)
    # copy_history.json
    copy_history_path = os.path.join(data_dir, "copy_history.json")
    ensure_json_file(copy_history_path, [])
    # translation_history.json
    translation_history_path = os.path.join(data_dir, "translation_history.json")
    ensure_json_file(translation_history_path, [])
    # settings.json
    settings_path = os.path.join(data_dir, "settings.json")
    ensure_json_file(settings_path, {})

def get_data_file(filename):
    data_dir = os.path.join(get_portable_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    file_path = os.path.join(data_dir, filename)
    # Автоматически создаём нужные json-файлы с дефолтным содержимым
    if filename == "config.json":
        ensure_json_file(file_path, DEFAULT_CONFIG)
    elif filename == "copy_history.json":
        ensure_json_file(file_path, [])
    elif filename == "translation_history.json":
        ensure_json_file(file_path, [])
    elif filename == "settings.json":
        ensure_json_file(file_path, {})
    return file_path

def _save_copy_history_sync(text):
    """Синхронная запись в историю копирований (выполняется в отдельном потоке)."""
    try:
        config = get_cached_config()
        if not config.get("copy_history", False):
            return
    except Exception:
        return

    record = {"timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "text": text}
    history_file = get_data_file("copy_history.json")
    
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
                # Deduplicate consecutive + limit
                if history and history[-1].get("text") == record["text"]:
                    pass  # skip duplicate
                else:
                    history.append(record)
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
                history.append(record)
                f.seek(0)
                f.truncate()
                json.dump(history, f, ensure_ascii=False, indent=4)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        # Fallback без блокировки
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
        if not (history and history[-1].get("text") == record["text"]):
            history.append(record)
        if len(history) > 500:
            history = history[-500:]
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

def save_copy_history(text):
    """Асинхронно сохранить текст в историю копирований (не блокирует UI)."""
    threading.Thread(target=_save_copy_history_sync, args=(text,), daemon=True).start()

# Сигнал для уведомления об ошибке регистрации хоткея
class _HotkeyErrorDispatcher(QtCore.QObject):
    registration_failed = QtCore.pyqtSignal(str)

hotkey_error_dispatcher = _HotkeyErrorDispatcher()

class HotkeyListenerThread(threading.Thread):
    def __init__(self, hotkey_str, callback, hotkey_id=1):
        super().__init__()
        self.hotkey_str = hotkey_str
        self.callback = callback
        self.hotkey_id = hotkey_id
        self.daemon = True  # поток завершается вместе с основным приложением
        self._stop_event = threading.Event()
        self._registered = False
        self.modifiers, self.vk = self.parse_hotkey(self.hotkey_str)
        if self.vk is None:
            print("Неверный формат горячей клавиши.")
    
    def stop(self):
        """Остановить поток и отменить регистрацию горячей клавиши."""
        self._stop_event.set()
        if self._registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
                self._registered = False
            except Exception:
                pass

    def parse_hotkey(self, hotkey_str):
        modifiers = 0
        vk = None
        main_keys = []
        # Маппинг спецсимволов на виртуальные коды Windows
        special_vk = {
            ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF, "`": 0xC0,
            "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
            "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
            "backspace": 0x08, "escape": 0x1B, "esc": 0x1B, "del": 0x2E, "delete": 0x2E,
            "insert": 0x2D, "ins": 0x2D, "home": 0x24, "end": 0x23,
            "pageup": 0x21, "pgup": 0x21, "pagedown": 0x22, "pgdn": 0x22,
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            "printscreen": 0x2C, "print": 0x2C, "pause": 0x13,
            "numlock": 0x90, "capslock": 0x14, "scrolllock": 0x91
        }
        # Маппинг кириллических букв на латинские эквиваленты (для раскладки)
        cyrillic_to_latin = {
            'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
            'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l',
            'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
            'х': '[', 'ъ': ']', 'ж': ';', 'э': "'", 'б': ',', 'ю': '.'
        }
        parts = hotkey_str.split("+")
        for part in parts:
            token = part.strip().lower()
            # Преобразуем кириллицу в латиницу для раскладко-независимости
            if len(token) == 1 and token in cyrillic_to_latin:
                token = cyrillic_to_latin[token]
            if token in ("ctrl", "control"):
                modifiers |= MOD_CONTROL
            elif token == "alt":
                modifiers |= MOD_ALT
            elif token == "shift":
                modifiers |= MOD_SHIFT
            elif token in ("win", "meta", "super"):
                modifiers |= MOD_WIN
            elif token in special_vk:
                main_keys.append(special_vk[token])
            elif token.startswith("f") and len(token) > 1 and token[1:].isdigit():
                try:
                    fnum = int(token[1:])
                    if 1 <= fnum <= 24:  # F1-F24
                        main_keys.append(0x70 + fnum - 1)  # VK_F1 = 0x70
                except:
                    pass
            elif len(token) == 1:
                ch = token.upper()
                # ASCII буквы/цифры — VK коды совпадают с ASCII
                if ('A' <= ch <= 'Z') or ('0' <= ch <= '9'):
                    main_keys.append(ord(ch))
                elif ch in special_vk:
                    main_keys.append(special_vk[ch])
                else:
                    # Пытаемся получить VK через WinAPI
                    try:
                        vk_scan = ctypes.windll.user32.VkKeyScanW(ord(ch))
                        if vk_scan != -1 and (vk_scan & 0xFF) != 0xFF:
                            main_keys.append(vk_scan & 0xFF)
                    except Exception:
                        pass
            # иначе игнорируем
        if len(main_keys) == 0:
            print(f"Ошибка: не выбрана основная клавиша для хоткея: {hotkey_str}")
            return modifiers, None
        if len(main_keys) > 1:
            print(f"Ошибка: Windows поддерживает только одну основную клавишу в хоткее! Выбрано: {main_keys}")
            return modifiers, None
        vk = main_keys[0]
        # Добавляем MOD_NOREPEAT для предотвращения повторных срабатываний
        MOD_NOREPEAT = 0x4000
        modifiers |= MOD_NOREPEAT
        return modifiers, vk

    def run(self):
        if self.vk is None:
            print("VK is None, aborting hotkey registration.")
            hotkey_error_dispatcher.registration_failed.emit(self.hotkey_str)
            return
        # Повышаем приоритет текущего потока хоткея для меньшей задержки
        try:
            ctypes.windll.kernel32.SetThreadPriority(ctypes.windll.kernel32.GetCurrentThread(), 2)  # THREAD_PRIORITY_HIGHEST
        except Exception:
            pass
        if not ctypes.windll.user32.RegisterHotKey(None, self.hotkey_id, self.modifiers, self.vk):
            print(f"Failed to register hotkey: {self.hotkey_str}")
            # Эмитируем сигнал об ошибке для UI
            hotkey_error_dispatcher.registration_failed.emit(self.hotkey_str)
            return
        else:
            print(f"Hotkey registered successfully: {self.hotkey_str}")
            self._registered = True

        msg = wintypes.MSG()
        # Используем MsgWaitForMultipleObjects для эффективного ожидания без busy-wait
        QS_ALLINPUT = 0x04FF
        WAIT_TIMEOUT = 258
        INFINITE = 0xFFFFFFFF

        while not self._stop_event.is_set():
            # Ждём сообщения с таймаутом 50ms для проверки stop_event
            result = ctypes.windll.user32.MsgWaitForMultipleObjects(0, None, False, 50, QS_ALLINPUT)

            # Обрабатываем все доступные сообщения
            while ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0x0001):  # PM_REMOVE
                if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                    try:
                        print(f"Hotkey pressed: {self.hotkey_str}")
                        hotkey_dispatcher.triggered.emit(self.callback)
                    except Exception as e:
                        print(f"Error handling hotkey press: {e}")
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
        
        # Отменяем регистрацию при выходе
        if self._registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
                self._registered = False
            except Exception:
                pass

LANGUAGES = {
    "en": ["English", "Russian"],
    "ru": ["Английский", "Русский"]
}

INTERFACE_TEXT = {
    "en": {
        "title": "Click'n'Translate",
        "select_language": "Select languages for translation",
        "start": "Start",
        "translation_selected": "Selected translation: {src} → {tgt}",
        "settings": "Settings",
        "back": "Back to main",
        "ocr": "OCR"
    },
    "ru": {
        "title": "Click'n'Translate",
        "select_language": "Выберите языки перевода",
        "start": "Старт",
        "translation_selected": "Выбран перевод: {src} → {tgt}",
        "settings": "Настройки",
        "back": "Назад",
        "ocr": "OCR"
    }
}

THEMES = {
    "Темная": {
        "background": "#121212",
        "text_color": "#ffffff",
        "button_background": "#1e1e1e",
        "button_border": "#550000",
        "button_hover": "#333333",
        "item_hover_background": "#333333",
        "item_hover_color": "#ffffff",
        "item_selected_background": "#444444",
        "item_selected_color": "#ffffff",
    },
    "Светлая": {
        "background": "#ffffff",
        "text_color": "#000000",
        "button_background": "#f0f0f0",
        "button_border": "#cccccc",
        "button_hover": "#e0e0e0",
        "item_hover_background": "#e0e0e0",
        "item_hover_color": "#000000",
        "item_selected_background": "#c0c0c0",
        "item_selected_color": "#000000",
    }
}

def resource_path(relative_path):
    """ Получить абсолютный путь к ресурсу, работает для dev и для PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class WelcomeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.lang = parent.current_interface_language if hasattr(parent, 'current_interface_language') else 'ru'
        self.setWindowTitle(self.tr("Новости") if self.lang == 'ru' else "News")
        self.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        self.setFixedSize(500, 370)
        self.setStyleSheet("background-color: #121212; color: #fff; font-size: 16px;")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.init_ui()

    def init_ui(self):
        # Очищаем layout, если он уже есть
        layout = getattr(self, 'main_layout', None)
        if layout:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            layout = QVBoxLayout()
            self.main_layout = layout
            self.setLayout(layout)
        self.main_layout.setSpacing(0)
        # --- Флаги ---
        flag_layout = QHBoxLayout()
        self.flag_button = QPushButton()
        self.flag_button.setIcon(QIcon(resource_path("icons/Russian_flag.png")) if self.lang == 'ru' else QIcon(resource_path("icons/American_flag.png")))
        self.flag_button.setIconSize(QSize(32, 32))
        self.flag_button.setStyleSheet("background: transparent; border: none;")
        self.flag_button.clicked.connect(self.toggle_language)
        flag_layout.addWidget(self.flag_button)
        flag_layout.addStretch()
        self.main_layout.addLayout(flag_layout)
        # --- Текст ---
        if self.lang == 'ru':
            self.setWindowTitle("Новости")
            title = "<b>Добро пожаловать в Click'n'Translate!</b><br>"
            version = f"<span style='color:#aaa; font-size:13px;'>V{APP_VERSION}</span><br><br>"
            body = ("<span style='font-size:15px;'>"
                    "Советуем <b>подписаться</b> на Telegram-канал разработчика, чтобы не пропустить обновления программы и получать свежие новости.<br><br>"
                    "<a href='https://t.me/jabrail_digital' style='color:#7A5FA1; font-size:17px;'>https://t.me/jabrail_digital</a>"
                    "</span>")
            checkbox_text = "Больше не показывать это окно"
            close_text = "Закрыть"
        else:
            self.setWindowTitle("News")
            title = "<b>Welcome to Click'n'Translate!</b><br>"
            version = f"<span style='color:#aaa; font-size:13px;'>V{APP_VERSION}</span><br><br>"
            body = ("<span style='font-size:15px;'>"
                    "We recommend <b>subscribing</b> to the developer's Telegram channel to get updates and news about the program.<br><br>"
                    "<a href='https://t.me/jabrail_digital' style='color:#7A5FA1; font-size:17px;'>https://t.me/jabrail_digital</a>"
                    "</span>")
            checkbox_text = "Don't show this window again"
            close_text = "Close"
        self.label = QLabel(title + version + body)
        self.label.setOpenExternalLinks(True)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.main_layout.addWidget(self.label)
        self.checkbox = QCheckBox(checkbox_text)
        self.checkbox.setStyleSheet("color: #aaa; font-size: 14px; margin-left:0px; margin-bottom:10px;")
        self.main_layout.addWidget(self.checkbox, alignment=Qt.AlignCenter)
        btn_layout = QHBoxLayout()
        self.close_btn = QPushButton(close_text)
        self.close_btn.setStyleSheet("background-color: #7A5FA1; color: #fff; border-radius: 8px; padding: 8px 24px; font-size: 16px;")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        self.main_layout.addLayout(btn_layout)

    def toggle_language(self):
        self.lang = 'en' if self.lang == 'ru' else 'ru'
        self.parent.current_interface_language = self.lang
        self.parent.save_config()
        self.init_ui()

class DarkThemeApp(QMainWindow):
    # Signal to show translation dialog from background thread
    _show_selection_signal = QtCore.pyqtSignal(str, bool, str, str)

    def __init__(self):
        super().__init__()
        self._show_selection_signal.connect(self._show_selection_translation)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle(APP_WINDOW_TITLE)
        self.setFixedSize(700, 400)
        self._is_dragging = False
        # Важно для single-instance в режиме "start minimized":
        # создаем native HWND заранее, чтобы окно могло получить Windows message.
        self.winId()
        self._init_status_tooltip()

        self.load_config()

        # Показать приветственное окно, если не отключено
        if self.config.get("show_update_info", True):
            dlg = WelcomeDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                if dlg.checkbox.isChecked():
                    self.config["show_update_info"] = False
                    self.save_config()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(5, 45, 5, 5)
        self.central_widget.setLayout(self.main_layout)

        self.hotkeys_mode = False
        self.force_quit = False
        self.init_ui()

        self.create_tray_icon()

        # Подписка на события хоткеев из потоков
        try:
            hotkey_dispatcher.triggered.connect(self._invoke_callback_safely)
        except Exception:
            pass

        # Подписка на ошибки регистрации хоткеев
        try:
            hotkey_error_dispatcher.registration_failed.connect(self._on_hotkey_registration_failed)
        except Exception:
            pass

        # Слушатели для горячих клавиш копирования и перевода (значения берутся из настроек)
        copy_hotkey = self.config.get("copy_hotkey", "")
        if copy_hotkey:
            self.copy_hotkey_thread = HotkeyListenerThread(copy_hotkey, self.launch_copy, hotkey_id=1)
            self.copy_hotkey_thread.start()
        translate_hotkey = self.config.get("translate_hotkey", "")
        if translate_hotkey:
            self.translate_hotkey_thread = HotkeyListenerThread(translate_hotkey, self.launch_translate, hotkey_id=2)
            self.translate_hotkey_thread.start()

        fullscreen_translate_hotkey = self.config.get("fullscreen_translate_hotkey", "")
        if fullscreen_translate_hotkey:
            self.fullscreen_translate_hotkey_thread = HotkeyListenerThread(fullscreen_translate_hotkey, self.launch_fullscreen_translate, hotkey_id=3)
            self.fullscreen_translate_hotkey_thread.start()

        translate_selection_hotkey = self.config.get("translate_selection_hotkey", "")
        if translate_selection_hotkey:
            self.translate_selection_hotkey_thread = HotkeyListenerThread(translate_selection_hotkey, self.launch_translate_selection, hotkey_id=4)
            self.translate_selection_hotkey_thread.start()

        self.HotkeyListenerThread = HotkeyListenerThread

        self.setWindowIcon(QIcon(resource_path("icons/icon.ico")))

    def load_config(self):
        config_path = get_data_file("config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = DEFAULT_CONFIG.copy()
            self.save_config()
        # Извлекаем значения с дефолтами из DEFAULT_CONFIG
        self.current_theme = self.config.get("theme", DEFAULT_CONFIG["theme"])
        self.current_interface_language = self.config.get("interface_language", DEFAULT_CONFIG["interface_language"])
        self.autostart = self.config.get("autostart", DEFAULT_CONFIG["autostart"])
        self.translation_mode = self.config.get("translation_mode", LANGUAGES[self.current_interface_language][0])
        self.start_minimized = self.config.get("start_minimized", DEFAULT_CONFIG["start_minimized"])

    def save_config(self):
        self.config["theme"] = self.current_theme
        self.config["interface_language"] = self.current_interface_language
        self.config["autostart"] = getattr(self, "autostart", False)
        self.config["translation_mode"] = getattr(self, "translation_mode",
                                                  LANGUAGES[self.current_interface_language][0])
        self.config["start_minimized"] = getattr(self, "start_minimized", False)
        config_path = get_data_file("config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)
        invalidate_config_cache()  # Сбрасываем кэш после записи

    def set_autostart(self, enable: bool):
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_WRITE)
            
            # Определяем путь к исполняемому файлу
            if getattr(sys, 'frozen', False):
                # PyInstaller: используем sys.executable (путь к exe)
                exe_path = os.path.abspath(sys.executable)
            else:
                # Обычный Python: используем pythonw для запуска без консоли
                pythonw = sys.executable.replace('python.exe', 'pythonw.exe')
                script_path = os.path.abspath(sys.argv[0])
                exe_path = f'"{pythonw}" "{script_path}"'
            
            if enable:
                # Путь в кавычках на случай пробелов
                if not exe_path.startswith('"'):
                    exe_path = f'"{exe_path}"'
                winreg.SetValueEx(reg_key, "ClicknTranslate", 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(reg_key, "ClicknTranslate")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(reg_key)
        except Exception as e:
            print("Error setting autostart:", e)

    def init_ui(self):
        self.title_bar = QLabel(self)
        self.title_bar.setText(INTERFACE_TEXT[self.current_interface_language]["title"])
        self.title_bar.setGeometry(0, 0, self.width(), 40)
        self.title_bar.setAlignment(Qt.AlignCenter)

        self.flag_button = QPushButton(self)
        self.flag_button.setIcon(
            QIcon(resource_path("icons/American_flag.png")) if self.current_interface_language == "en"
            else QIcon(resource_path("icons/Russian_flag.png"))
        )
        self.flag_button.setToolTip("Сменить язык" if self.current_interface_language == "ru" else "Change language")
        self.flag_button.setStyleSheet("background-color: transparent; border: none;")
        self.flag_button.setGeometry(10, 5, 30, 30)
        self.flag_button.clicked.connect(self.toggle_language)

        self.theme_button = QPushButton(self)
        self.update_theme_icon()
        self.theme_button.setToolTip("Change theme")
        self.theme_button.setStyleSheet("background-color: transparent; border: none;")
        self.theme_button.setGeometry(50, 5, 30, 30)
        self.theme_button.clicked.connect(self.toggle_theme)

        self.minimize_button = QPushButton(self)
        self.minimize_button.setText("‒")
        self.minimize_button.setToolTip("Minimize")
        self.minimize_button.setStyleSheet("background-color: transparent; border: none;")
        self.minimize_button.setGeometry(self.width() - 70, 5, 30, 30)
        self.minimize_button.clicked.connect(self.showMinimized)

        # Кнопка помощи (FAQ)
        self.help_button = QPushButton(self)
        self.help_button.setToolTip("Помощь" if self.current_interface_language == "ru" else "Help")
        self.help_button.setStyleSheet("background-color: transparent; border: none;")
        self.help_button.setGeometry(self.width() - 155, 5, 30, 30)
        self.help_button.clicked.connect(self.show_help_dialog)
        self.update_help_icon()

        self.settings_button = QPushButton(self)
        self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['settings'])
        self.settings_button.setStyleSheet("background-color: transparent; border: none;")
        self.settings_button.setGeometry(self.width() - 120, 5, 30, 30)
        self.settings_button.clicked.connect(self.show_settings)

        self.close_button = QPushButton(self)
        self.close_button.setText("×")
        self.close_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])
        self.close_button.setStyleSheet("background-color: transparent; border: none;")
        self.close_button.setGeometry(self.width() - 40, 5, 30, 30)
        self.close_button.clicked.connect(self.close)

        self.show_main_screen()
        self.apply_theme()

    def create_tray_icon(self):
        lang = self.current_interface_language
        if lang == "en":
            open_text = "Open"
            exit_text = "Exit"
            copy_text = "Copy Text"
            translate_text = "Translate"
            fullscreen_text = "Translate Screen"
        else:
            open_text = "Открыть"
            exit_text = "Закрыть программу"
            copy_text = "Копировать текст"
            translate_text = "Перевести"
            fullscreen_text = "Перевести экран"
        self.tray_icon = QSystemTrayIcon(QIcon(resource_path("icons/icon.ico")), self)
        self.tray_icon.setToolTip("Click'n'Translate")
        tray_menu = QMenu()
        open_action = tray_menu.addAction(open_text)
        open_action.triggered.connect(lambda: self.show_window_from_tray(force_show=True))
        copy_action = tray_menu.addAction(copy_text)
        copy_action.triggered.connect(self.launch_copy)
        translate_action = tray_menu.addAction(translate_text)
        translate_action.triggered.connect(self.launch_translate)
        fullscreen_action = tray_menu.addAction(fullscreen_text)
        fullscreen_action.triggered.connect(self.launch_fullscreen_translate)
        tray_menu.addSeparator()
        exit_action = tray_menu.addAction(exit_text)
        exit_action.triggered.connect(self.exit_app)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window_from_tray()

    def show_window_from_tray(self, force_show=False):
        if self.isVisible() and not force_show:
            self.hide()
            return
        self.setWindowState(Qt.WindowNoState)
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        if sys.platform == "win32":
            try:
                hwnd = int(self.winId())
                ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW)
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

    def nativeEvent(self, eventType, message):
        event_name = eventType.decode("utf-8", "ignore") if isinstance(eventType, bytes) else str(eventType)
        if _SHOW_WINDOW_MESSAGE_ID and event_name in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == _SHOW_WINDOW_MESSAGE_ID:
                    QTimer.singleShot(0, _show_running_instance)
                    return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def _start_external(self, script_or_exe, *args):
        """Launch helper that works both in dev (python script) and frozen (exe)."""
        if getattr(sys, 'frozen', False):
            # В собранной версии просто перезапускаем тот же exe с нужным параметром
            subprocess.Popen([sys.executable, *args])
        else:
            # В режиме разработки запускаем python-скрипт
            subprocess.Popen([sys.executable, script_or_exe, *args])

    def launch_ocr(self):
        print("launch_ocr called")
        if hasattr(self, "source_lang"):
            src_text = self.source_lang.currentText().lower()
            lang = "en" if ("english" in src_text or "английский" in src_text) else "ru"
        else:
            lang = self.config.get("ocr_language", self.current_interface_language)
        try:
            # Lazy import to avoid startup penalty
            from ocr import run_screen_capture
            self.hide()
            # run overlay in current QApplication (non-blocking)
            run_screen_capture(mode="ocr")
        except Exception as e:
            print(f"Error launching OCR: {e}")
            # fallback to previous behavior
            if getattr(sys, 'frozen', False):
                self._start_external("ocr.py", "ocr", lang)
            else:
                self._start_external("ocr.py", lang)
            self.hide()

    def launch_copy(self):
        print("launch_copy called")
        try:
            from ocr import run_screen_capture
            # Проверяем настройку - сворачивать ли окно
            if not self.config.get("keep_visible_on_ocr", False):
                self.hide()
            run_screen_capture(mode="copy")
        except Exception as e:
            print(f"Error launching copy: {e}")
            if getattr(sys, 'frozen', False):
                self._start_external("ocr.py", "copy")
            else:
                self._start_external("ocr.py", "copy")
            if not self.config.get("keep_visible_on_ocr", False):
                self.hide()

    def launch_translate(self):
        print("launch_translate called")
        try:
            from ocr import run_screen_capture
            # Проверяем настройку - сворачивать ли окно
            if not self.config.get("keep_visible_on_ocr", False):
                self.hide()
            run_screen_capture(mode="translate")
        except Exception as e:
            print(f"Error launching translate: {e}")
            if getattr(sys, 'frozen', False):
                self._start_external("ocr.py", "translate")
            else:
                self._start_external("ocr.py", "translate")
            if not self.config.get("keep_visible_on_ocr", False):
                self.hide()

    def launch_fullscreen_translate(self):
        print("launch_fullscreen_translate called")
        try:
            from ocr import run_fullscreen_translate
            if not self.config.get("keep_visible_on_ocr", False):
                self.hide()

            def _do_translate():
                try:
                    run_fullscreen_translate()
                except Exception as e:
                    print(f"Error in fullscreen translate: {e}")
                    import traceback
                    traceback.print_exc()

            # Small delay to ensure window is hidden before screenshot
            QTimer.singleShot(150, _do_translate)
        except Exception as e:
            print(f"Error launching fullscreen translate: {e}")
            import traceback
            traceback.print_exc()

    # Signal to show/hide status tooltip
    _show_status_signal = QtCore.pyqtSignal(str)
    _hide_status_signal = QtCore.pyqtSignal()

    def _init_status_tooltip(self):
        """Initialize floating status tooltip."""
        from PyQt5.QtWidgets import QLabel
        self._status_label = QLabel()
        self._status_label.setWindowFlags(Qt.ToolTip | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self._status_label.setStyleSheet(
            "QLabel { background-color: #1a1a2e; color: #e0e0e0; padding: 8px 16px; "
            "border: 1px solid #550000; border-radius: 6px; font-size: 14px; }"
        )
        self._status_label.hide()
        self._show_status_signal.connect(self._on_show_status)
        self._hide_status_signal.connect(self._on_hide_status)

    def _on_show_status(self, text):
        from PyQt5.QtGui import QCursor
        self._status_label.setText(text)
        self._status_label.adjustSize()
        pos = QCursor.pos()
        self._status_label.move(pos.x() + 15, pos.y() + 15)
        self._status_label.show()

    def _on_hide_status(self):
        self._status_label.hide()

    def launch_translate_selection(self):
        """Translate currently selected text: simulate Ctrl+C, read clipboard, translate, show dialog."""
        print("launch_translate_selection called")

        def _do_copy_and_translate():
            lang = self.config.get("interface_language", "ru")
            try:
                # Release all modifier keys first
                KEYEVENTF_KEYUP = 0x0002
                for vk in (0x11, 0x12, 0x10, 0x5B, 0x5C):
                    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.35)
                # Clear clipboard, then Ctrl+C to capture selection
                pyperclip.copy("")
                simulate_copy()
                time.sleep(0.25)
                text = pyperclip.paste()
                if not text or not text.strip():
                    time.sleep(0.3)
                    text = pyperclip.paste()
                if not text or not text.strip():
                    lang = self.config.get("interface_language", "ru")
                    no_text = "No text selected" if lang == "en" else "Текст не выделен"
                    self._show_status_signal.emit(no_text)
                    time.sleep(1.5)
                    self._hide_status_signal.emit()
                    return
                text = text.strip()
                # Show status
                lang = self.config.get("interface_language", "ru")
                status_msg = "Translating..." if lang == "en" else "Переводим..."
                self._show_status_signal.emit(status_msg)
                # Auto-detect language direction
                cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04ff')
                if cyrillic_count > len(text) * 0.3:
                    source_code, target_code = "ru", "en"
                else:
                    source_code, target_code = "en", "ru"
                print(f"[SEL] translating {source_code}->{target_code}, {len(text)} chars...")
                from translater import translate_text
                translated = translate_text(text, source_code, target_code)
                self._hide_status_signal.emit()
                print(f"[SEL] result: {len(translated) if translated else 0} chars")
                if not translated:
                    return
                theme = self.config.get("theme", "Темная")
                auto_copy = self.config.get("copy_translated_text", False)
                self._show_selection_signal.emit(translated, auto_copy, lang, theme)
            except Exception as e:
                err_msg = "Translation error" if lang == "en" else "Ошибка перевода"
                self._show_status_signal.emit(f"{err_msg}: {e}")
                print(f"Error in translate_selection: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(3)
                self._hide_status_signal.emit()

        threading.Thread(target=_do_copy_and_translate, daemon=True).start()

    def _show_selection_translation(self, translated, auto_copy, lang, theme):
        """Show translation dialog from selection (called in UI thread)."""
        try:
            show_translation_dialog(self, translated, auto_copy=auto_copy, lang=lang, theme=theme)
            if auto_copy:
                pyperclip.copy(translated)
                save_copy_history(translated)
        except Exception as e:
            print(f"Error showing translation dialog: {e}")

    def restart_hotkey_listener(self):
        self.hotkey_thread = HotkeyListenerThread(self.config.get("ocr_hotkeys", "Ctrl+O"), self.launch_ocr)
        self.hotkey_thread.start()

    def apply_theme(self):
        theme = THEMES[self.current_theme]
        # Настроим стиль скроллбара в зависимости от темы
        # Настроим стиль скроллбара в зависимости от темы (как в FAQ)
        scrollbar_bg = theme['button_background']
        scrollbar_handle = '#7A5FA1'  # Фиолетовый
        scrollbar_handle_hover = '#9A7FC1'
        style_sheet = f"""
            QMainWindow {{
                background-color: {theme['background']};
            }}
            QLabel {{
                color: {theme['text_color']};
                font-size: 16px;
            }}
            QComboBox {{
                background-color: {theme['button_background']};
                color: {theme['text_color']};
                border: none;
                padding: 5px;
                font-size: 18px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme['button_background']};
                color: {theme['text_color']};
                border: none;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {theme['item_hover_background']};
                color: {theme['item_hover_color']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {theme['item_selected_background']};
                color: {theme['item_selected_color']};
            }}
            QPushButton {{
                background-color: {theme['button_background']};
                color: {theme['text_color']};
                border: 2px solid #C5B3E9;
                padding: 10px;
                font-size: 14px;
            }}
            QLineEdit, QTextEdit {{
                background-color: {theme['button_background']};
                color: {theme['text_color']};
                border: 1px solid #550000;
                padding: 5px;
                font-size: 14px;
            }}
            QTextEdit QScrollBar:vertical {{
                background: {scrollbar_bg};
                width: 12px;
                margin: 4px 2px 4px 2px;
                border-radius: 6px;
            }}
            QTextEdit QScrollBar::handle:vertical {{
                background: {scrollbar_handle};
                min-height: 30px;
                border-radius: 5px;
            }}
            QTextEdit QScrollBar::handle:vertical:hover {{
                background: {scrollbar_handle_hover};
            }}
            QTextEdit QScrollBar::add-line:vertical, QTextEdit QScrollBar::sub-line:vertical {{
                height: 0;
                background: none;
            }}
            QTextEdit QScrollBar::add-page:vertical, QTextEdit QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """
        self.setStyleSheet(style_sheet)
        if hasattr(self, "title_bar"):
            header_bg = "#c0c0c0" if self.current_theme == "Светлая" else theme['button_background']
            self.title_bar.setStyleSheet(
                f"font-size: 18px; font-weight: bold; color: {theme['text_color']}; background-color: {header_bg};"
            )
        if hasattr(self, "minimize_button") and hasattr(self, "close_button"):
            if self.current_theme == "Светлая":
                self.minimize_button.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #000000;
                        font-size: 16px;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #00aa00;
                    }
                """)
                self.close_button.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #000000;
                        font-size: 20px;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #aa0000;
                    }
                """)
            else:
                self.minimize_button.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: white;
                        font-size: 16px;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #00ff00;
                    }
                """)
                self.close_button.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: white;
                        font-size: 20px;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #ff3333;
                    }
                """)
        # Обновить иконку кнопки помощи
        self.update_help_icon()
        self.update_theme_icon()
        if hasattr(self, "settings_button"):
            if self.settings_window is None:
                if self.current_theme == "Темная":
                    self.settings_button.setIcon(QIcon(resource_path("icons/settings_light.png")))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['settings'])
                else:
                    self.settings_button.setIcon(QIcon(resource_path("icons/settings_dark.png")))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['settings'])
            else:
                if self.current_theme == "Темная":
                    self.settings_button.setIcon(QIcon(resource_path("icons/light_home.png")))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])
                else:
                    self.settings_button.setIcon(QIcon(resource_path("icons/dark_home.png")))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])

    def update_theme_icon(self):
        icon_path = resource_path("icons/sun.png") if self.current_theme == "Темная" else resource_path("icons/moon.png")
        self.theme_button.setIcon(QIcon(icon_path))

    def update_help_icon(self):
        """Обновить иконку кнопки помощи в зависимости от темы."""
        if hasattr(self, "help_button"):
            if self.current_theme == "Темная":
                self.help_button.setIcon(QIcon(resource_path("icons/faq_black_theme.png")))
            else:
                self.help_button.setIcon(QIcon(resource_path("icons/faq_white_theme.png")))

    def toggle_theme(self):
        self.current_theme = "Светлая" if self.current_theme == "Темная" else "Темная"
        self.save_config()
        self.apply_theme()
        self.update_theme_icon()
        if self.settings_window is not None:
            self.settings_window.apply_theme()

    def toggle_language(self):
        if self.current_interface_language == "en":
            self.current_interface_language = "ru"
            self.flag_button.setIcon(QIcon(resource_path("icons/Russian_flag.png")))
        else:
            self.current_interface_language = "en"
            self.flag_button.setIcon(QIcon(resource_path("icons/American_flag.png")))
        self.save_config()
        if self.settings_window is not None:
            self.settings_window.update_language()
        else:
            self.show_main_screen()
        self.apply_theme()
        self.update_theme_icon()

    def show_help_dialog(self):
        """Показать окно помощи с описанием переводчиков и OCR."""
        lang = self.current_interface_language
        theme = self.current_theme

        dialog = QDialog(self)
        dialog.setWindowTitle("FAQ" if lang == "ru" else "FAQ")
        dialog.setFixedSize(550, 550) # Вернули фиксированный размер
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Текст помощи
        if lang == "ru":
            help_text = """
<style>
    .section { margin-bottom: 18px; }
    .section-title { color: #7A5FA1; font-size: 16px; font-weight: bold; margin-bottom: 8px; border-bottom: 2px solid #7A5FA1; padding-bottom: 4px; }
    .item { margin: 6px 0; padding-left: 8px; font-size: 14px; }
    .item-title { color: #9A7FC1; font-weight: bold; }
    .recommended { color: #4CAF50; font-size: 12px; }
    .step { background-color: rgba(122, 95, 161, 0.1); padding: 8px; border-radius: 6px; margin: 4px 0; font-size: 14px; }
</style>

<div class="section">
<div class="section-title">🚀 Быстрый старт</div>
<div class="step"><b>1.</b> Нажмите горячую клавишу для копирования или перевода</div>
<div class="step"><b>2.</b> Выделите область экрана с текстом мышкой</div>
<div class="step"><b>3.</b> Выберите язык текста (флаг в углу экрана)</div>
<div class="step"><b>4.</b> Готово! Текст скопирован или переведён</div>
</div>

<div class="section">
<div class="section-title">🌐 Переводчики</div>
<div class="item"><span class="item-title">Google</span> — быстрый и точный <span class="recommended">✓ Рекомендуется</span></div>
<div class="item"><span class="item-title">Argos</span> — офлайн, работает без интернета, полностью приватный</div>
<div class="item"><span class="item-title">MyMemory</span> — бесплатный API, лимит ~5000 символов/день</div>
<div class="item"><span class="item-title">Lingva</span> — прокси к Google через публичные серверы</div>
<div class="item"><span class="item-title">LibreTranslate</span> — открытый переводчик</div>
</div>

<div class="section">
<div class="section-title">👁 OCR движки</div>
<div class="item"><span class="item-title">Windows</span> — встроенный в ОС, быстрый <span class="recommended">✓ Рекомендуется</span></div>
<div class="item" style="padding-left: 24px; font-size: 13px; color: #888;">📋 <b>AUTO</b> — цифры и латиница | <b>RU</b> — кириллица | <b>EN</b> — английский</div>
<div class="item" style="padding-left: 24px; font-size: 13px; color: #888;">⚠️ Работает только с языками, установленными в Windows (Настройки → Язык)</div>
<div class="item"><span class="item-title">Tesseract</span> — офлайн, высокая точность, <b>требует отдельной установки</b></div>
<div class="item" style="padding-left: 24px; font-size: 13px; color: #888;">⚠️ Для работы Tesseract скачайте установщик с <a href="https://github.com/UB-Mannheim/tesseract/wiki" style="color: #7A5FA1;">GitHub</a> и установите нужные языковые пакеты</div>
</div>

<div class="section">
<div class="section-title">⚙️ Настройки</div>
<div class="item"><span class="item-title">Запускать в режиме тень</span> — программа запускается свёрнутой в трей</div>
<div class="item"><span class="item-title">Копировать переведённый текст</span> — автоматически копировать перевод в буфер</div>
<div class="item"><span class="item-title">Сохранять историю</span> — сохранять историю переводов и копирований</div>
<div class="item"><span class="item-title">Не сворачивать при OCR</span> — окно остаётся видимым при захвате экрана</div>
<div class="item"><span class="item-title">Не затемнять экран</span> — только рамка выделения без затемнения</div>
</div>

<div class="section">
<div class="section-title">⌨️ Горячие клавиши</div>
<div class="item">Настройте свои комбинации в разделе «Настроить горячие клавиши»</div>
<div class="item">Если хоткей не работает — возможно он занят другой программой</div>
</div>

<div class="section">
<div class="section-title">📦 Портативность</div>
<div class="item">Программа полностью портативна — не требует установки</div>
<div class="item"><span class="item-title">Автозапуск:</span> если отключить через Диспетчер задач — включите там же</div>
</div>
"""
        else:
            help_text = """
<style>
    .section { margin-bottom: 18px; }
    .section-title { color: #7A5FA1; font-size: 16px; font-weight: bold; margin-bottom: 8px; border-bottom: 2px solid #7A5FA1; padding-bottom: 4px; }
    .item { margin: 6px 0; padding-left: 8px; font-size: 14px; }
    .item-title { color: #9A7FC1; font-weight: bold; }
    .recommended { color: #4CAF50; font-size: 12px; }
    .step { background-color: rgba(122, 95, 161, 0.1); padding: 8px; border-radius: 6px; margin: 4px 0; font-size: 14px; }
</style>

<div class="section">
<div class="section-title">🚀 Quick Start</div>
<div class="step"><b>1.</b> Press your configured hotkey for copy or translate</div>
<div class="step"><b>2.</b> Select an area on screen with text</div>
<div class="step"><b>3.</b> Choose the text language (flag in the corner)</div>
<div class="step"><b>4.</b> Done! Text is copied or translated</div>
</div>

<div class="section">
<div class="section-title">🌐 Translators</div>
<div class="item"><span class="item-title">Google</span> — fast and accurate <span class="recommended">✓ Recommended</span></div>
<div class="item"><span class="item-title">Argos</span> — offline, no internet, private</div>
<div class="item"><span class="item-title">MyMemory</span> — free API, 5000 chars/day limit</div>
<div class="item"><span class="item-title">Lingva</span> — Google proxy, more stable</div>
<div class="item"><span class="item-title">LibreTranslate</span> — open source, free</div>
</div>

<div class="section">
<div class="section-title">👁 OCR Engines</div>
<div class="item"><span class="item-title">Windows</span> — built-in, fast <span class="recommended">✓ Recommended</span></div>
<div class="item" style="padding-left: 24px; font-size: 13px; color: #888;">📋 <b>AUTO</b> — numbers & latin | <b>RU</b> — cyrillic | <b>EN</b> — english</div>
<div class="item" style="padding-left: 24px; font-size: 13px; color: #888;">⚠️ Only works with languages installed in Windows (Settings → Language)</div>
<div class="item"><span class="item-title">Tesseract</span> — accurate, offline, <b>requires separate installation</b></div>
<div class="item" style="padding-left: 24px; font-size: 13px; color: #888;">⚠️ To use Tesseract, download the installer from <a href="https://github.com/UB-Mannheim/tesseract/wiki" style="color: #7A5FA1;">GitHub</a> and install required language packs</div>
</div>

<div class="section">
<div class="section-title">⚙️ Settings</div>
<div class="item"><span class="item-title">Start minimized</span> — app starts hidden in system tray</div>
<div class="item"><span class="item-title">Copy translated text</span> — auto-copy translation to clipboard</div>
<div class="item"><span class="item-title">Save history</span> — keep history of translations and copies</div>
<div class="item"><span class="item-title">Keep window visible</span> — don't hide app during screen capture</div>
<div class="item"><span class="item-title">No screen dimming</span> — only selection frame, no overlay</div>
</div>

<div class="section">
<div class="section-title">⌨️ Hotkeys</div>
<div class="item">Configure your shortcuts in "Configure hotkeys" section</div>
<div class="item">If a hotkey doesn't work — it may be used by another app</div>
</div>

<div class="section">
<div class="section-title">📦 Portable App</div>
<div class="item">This app is fully portable — no installation required</div>
<div class="item"><span class="item-title">Autostart:</span> if disabled via Task Manager — re-enable it there</div>
</div>
"""

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml(help_text)

        # Стилизация под тему
        if theme == "Темная":
            dialog.setStyleSheet("QDialog { background-color: #121212; }")
            text_edit.setStyleSheet("""
                QTextEdit {
                    background-color: #1a1a2e;
                    color: #e0e0e0;
                    border: none;
                    border-radius: 12px;
                    padding: 15px;
                    font-size: 13px;
                    line-height: 1.5;
                }
                QScrollBar:vertical {
                    background: #1a1a2e;
                    width: 12px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background: #7A5FA1;
                    min-height: 30px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #9A7FC1;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0;
                    background: none;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none;
                }
            """)
        else:
            dialog.setStyleSheet("QDialog { background-color: #f8f8f8; }")
            text_edit.setStyleSheet("""
                QTextEdit {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #e0e0e0;
                    border-radius: 12px;
                    padding: 15px;
                    font-size: 13px;
                    line-height: 1.5;
                }
                QScrollBar:vertical {
                    background: #f0f0f0;
                    width: 12px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background: #7A5FA1;
                    min-height: 30px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #9A7FC1;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0;
                    background: none;
                }
            """)

        layout.addWidget(text_edit)

        # Кнопка закрытия
        close_btn = QPushButton("Понятно" if lang == "ru" else "Got it")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #7A5FA1;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 32px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8B70B2;
            }
        """)
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

        dialog.exec_()

    def set_settings_button_to_home(self):
        if self.current_theme == "Темная":
            self.settings_button.setIcon(QIcon(resource_path("icons/dark_home.png")))
        else:
            self.settings_button.setIcon(QIcon(resource_path("icons/light_home.png")))
        self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])
        try:
            self.settings_button.clicked.disconnect()
        except Exception:
            pass
        self.settings_button.clicked.connect(self.show_main_screen)

    def set_settings_button_to_settings(self):
        if self.current_theme == "Темная":
            self.settings_button.setIcon(QIcon(resource_path("icons/settings_light.png")))
        else:
            self.settings_button.setIcon(QIcon(resource_path("icons/settings_dark.png")))
        self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['settings'])
        try:
            self.settings_button.clicked.disconnect()
        except Exception:
            pass
        self.settings_button.clicked.connect(self.show_settings)

    def show_main_screen(self):
        self.clear_layout()
        self.settings_window = None
        self.set_settings_button_to_settings()
        
        # Получаем конфиг один раз для всей функции
        cached_config = get_cached_config()
        translator_engine = cached_config.get("translator_engine", "Argos").lower()
        ocr_engine = cached_config.get("ocr_engine", "Windows")
        
        # Отображаем конкретный переводчик
        translator_names = {
            "argos": {"en": "Argos Translate (Offline)", "ru": "Argos Translate (Офлайн)"},
            "google": {"en": "Google Translate", "ru": "Google Translate"},
            "mymemory": {"en": "MyMemory Translate", "ru": "MyMemory Translate"},
            "lingva": {"en": "Lingva Translate", "ru": "Lingva Translate"},
            "libretranslate": {"en": "LibreTranslate", "ru": "LibreTranslate"}
        }
        
        translator_info = translator_names.get(translator_engine, {"en": "Translation", "ru": "Перевод"})
        lang_label_text = translator_info.get(self.current_interface_language, translator_info["en"])
        
        self.label = QLabel(lang_label_text)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #7A5FA1; font-size: 18px; font-weight: bold; margin-top: 12px; margin-bottom: 8px;")
        self.main_layout.addWidget(self.label)
        self.main_layout.addSpacing(2)
        self.source_lang = QComboBox()
        self.source_lang.addItems(LANGUAGES[self.current_interface_language])
        self.source_lang.setCurrentIndex(0)
        self.source_lang.currentIndexChanged.connect(self.update_languages)
        self.main_layout.addWidget(self.source_lang)
        self.target_lang = QComboBox()
        self.target_lang.addItems(
            [lang for lang in LANGUAGES[self.current_interface_language] if lang != self.source_lang.currentText()]
        )
        self.target_lang.setCurrentIndex(0)
        self.main_layout.addWidget(self.target_lang)
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Enter text to translate" if self.current_interface_language == "en" else "Введите текст для перевода")
        self.text_input.setMinimumHeight(45)
        self.text_input.setMaximumHeight(70)
        self.text_input.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text_input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.main_layout.addWidget(self.text_input)

        # Кнопка перевода сразу под полем ввода
        self.translate_button = QPushButton("Translate" if self.current_interface_language == "en" else "Перевести")
        self.translate_button.clicked.connect(self.translate_input_text)
        self.translate_button.setStyleSheet("border: 2px solid #C5B3E9; border-radius: 8px; font-size: 16px; padding: 8px 0; background: none; color: #7A5FA1;")
        self.main_layout.addWidget(self.translate_button)

        # --- Блок хоткеев (показываем всегда) ---
        hk_style = "font-size: 13px; color: #888; padding: 0; margin: 0;"
        hk_val = "color: #7A5FA1; font-weight: bold;"
        not_set = "—"
        is_en = self.current_interface_language == "en"

        copy_hk = self.config.get("copy_hotkey", "") or not_set
        translate_hk = self.config.get("translate_hotkey", "") or not_set
        fs_hk = self.config.get("fullscreen_translate_hotkey", "") or not_set
        sel_hk = self.config.get("translate_selection_hotkey", "") or not_set

        tr_names = {"argos": "Argos", "google": "Google", "mymemory": "MyMemory", "lingva": "Lingva", "libretranslate": "LibreTranslate"}
        tr_name = tr_names.get(translator_engine, translator_engine.capitalize())

        # Row 1: Copy + OCR translate | OCR engine + Translator
        row1 = QHBoxLayout()
        row1.setSpacing(0)
        r1_left = QLabel(f"{'Copy' if is_en else 'Копир.'}: <span style='{hk_val}'>{copy_hk}</span> &nbsp; {'OCR Translate' if is_en else 'OCR перевод'}: <span style='{hk_val}'>{translate_hk}</span>")
        r1_left.setStyleSheet(hk_style)
        r1_left.setTextFormat(Qt.RichText)
        row1.addWidget(r1_left, alignment=Qt.AlignLeft)
        row1.addItem(QSpacerItem(10, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        r1_right = QLabel(f"OCR: <b>{ocr_engine}</b>")
        r1_right.setStyleSheet("font-size: 13px; color: #7A5FA1; margin-right: 8px;")
        r1_right.setTextFormat(Qt.RichText)
        row1.addWidget(r1_right, alignment=Qt.AlignRight)
        self.main_layout.addLayout(row1)

        # Row 2: Fullscreen + Selection | Translator
        row2 = QHBoxLayout()
        row2.setSpacing(0)
        r2_left = QLabel(f"{'Fullscreen' if is_en else 'Экран'}: <span style='{hk_val}'>{fs_hk}</span> &nbsp; {'Selection' if is_en else 'Выделение'}: <span style='{hk_val}'>{sel_hk}</span>")
        r2_left.setStyleSheet(hk_style)
        r2_left.setTextFormat(Qt.RichText)
        row2.addWidget(r2_left, alignment=Qt.AlignLeft)
        row2.addItem(QSpacerItem(10, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        r2_right = QLabel(f"{'Translator' if is_en else 'Переводчик'}: <b>{tr_name}</b>")
        r2_right.setStyleSheet("font-size: 13px; color: #7A5FA1; margin-right: 8px;")
        r2_right.setTextFormat(Qt.RichText)
        row2.addWidget(r2_right, alignment=Qt.AlignRight)
        self.main_layout.addLayout(row2)

        # Кнопка старт (shadow mode) в самом низу
        start_text = "Shadow mode" if self.current_interface_language == "en" else "Режим тени"
        self.start_button = QPushButton(start_text)
        self.start_button.setStyleSheet("border: none; font-size: 16px; padding: 8px 0; background-color: #C5B3E9; color: #111; border-radius: 8px;")
        self.main_layout.addWidget(self.start_button)
        self.start_button.clicked.connect(self.minimize_to_tray)
        self.apply_theme()

    def show_settings(self):
        self.clear_layout()
        from settings_window import SettingsWindow
        self.settings_window = SettingsWindow(self)
        self.main_layout.addWidget(self.settings_window)
        self.set_settings_button_to_home()
        self.apply_theme()

    def update_languages(self):
        src = self.source_lang.currentText()
        tgt = self.target_lang.currentText()
        available_targets = LANGUAGES[self.current_interface_language][:]
        if src in available_targets:
            available_targets.remove(src)
        self.target_lang.clear()
        self.target_lang.addItems(available_targets)
        if tgt in available_targets:
            self.target_lang.setCurrentText(tgt)
        else:
            self.target_lang.setCurrentIndex(0)

    def clear_layout(self):
        # Удаляем все виджеты и layout'ы из main_layout
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_nested_layout(item.layout())

    def _clear_nested_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_nested_layout(item.layout())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() <= 40:
            self._is_dragging = True
            self._drag_start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self.move(event.globalPos() - self._drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            event.accept()

    def _invoke_callback_safely(self, cb):
        try:
            cb()
        except Exception:
            pass

    def _on_hotkey_registration_failed(self, hotkey_str):
        """Показать уведомление, когда хоткей занят другим приложением."""
        lang = self.current_interface_language
        if lang == "ru":
            title = "Горячая клавиша недоступна"
            msg = (f"Не удалось зарегистрировать <b>{hotkey_str}</b>.<br><br>"
                   f"Эта комбинация уже используется браузером или системой "
                   f"(например, Ctrl+Shift+T открывает закрытую вкладку).<br><br>"
                   f"Попробуйте другую комбинацию в настройках.")
        else:
            title = "Hotkey unavailable"
            msg = (f"Failed to register <b>{hotkey_str}</b>.<br><br>"
                   f"This combination is already used by browser or system "
                   f"(e.g., Ctrl+Shift+T reopens closed tab).<br><br>"
                   f"Try a different combination in settings.")

        # Используем QTimer для показа в главном потоке
        QTimer.singleShot(100, lambda: self._show_hotkey_error_dialog(title, msg))

    def _show_hotkey_error_dialog(self, title, msg):
        """Показать диалог ошибки регистрации хоткея."""
        theme = self.current_theme
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setTextFormat(Qt.RichText)
        dialog.setText(msg)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowIcon(QIcon(resource_path("icons/icon.ico")))

        if theme == "Темная":
            dialog.setStyleSheet("""
                QMessageBox { background-color: #121212; }
                QLabel { color: #ffffff; font-size: 14px; }
                QPushButton { background-color: #1e1e1e; color: #ffffff; border: 1px solid #550000; padding: 6px 16px; min-width: 80px; }
                QPushButton:hover { background-color: #333333; }
            """)
        else:
            dialog.setStyleSheet("""
                QMessageBox { background-color: #ffffff; }
                QLabel { color: #000000; font-size: 14px; }
                QPushButton { background-color: #f0f0f0; color: #000000; border: 1px solid #cccccc; padding: 6px 16px; min-width: 80px; }
                QPushButton:hover { background-color: #e0e0e0; }
            """)

        dialog.exec_()

    def closeEvent(self, event):
        if not self.force_quit:
            # Сворачиваем в трей вместо закрытия
            event.ignore()
            self.hide()
            # Опционально: показать уведомление при первом сворачивании (можно добавить позже)
            return

        # Если force_quit=True, то выполняем полноценный выход
        try:
            if hasattr(self, "hotkey_thread") and self.hotkey_thread is not None:
                self.hotkey_thread.stop()
                self.hotkey_thread.join(timeout=0.5)
        except Exception as e:
            print(f"Error stopping OCR hotkey thread: {e}")
        try:
            if hasattr(self, "copy_hotkey_thread") and self.copy_hotkey_thread is not None:
                self.copy_hotkey_thread.stop()
                self.copy_hotkey_thread.join(timeout=0.5)
        except Exception as e:
            print(f"Error stopping copy hotkey thread: {e}")
        try:
            if hasattr(self, "translate_hotkey_thread") and self.translate_hotkey_thread is not None:
                self.translate_hotkey_thread.stop()
                self.translate_hotkey_thread.join(timeout=0.5)
        except Exception as e:
            print(f"Error stopping translate hotkey thread: {e}")
        try:
            if hasattr(self, "fullscreen_translate_hotkey_thread") and self.fullscreen_translate_hotkey_thread is not None:
                self.fullscreen_translate_hotkey_thread.stop()
                self.fullscreen_translate_hotkey_thread.join(timeout=0.5)
        except Exception as e:
            print(f"Error stopping fullscreen translate hotkey thread: {e}")
        try:
            if hasattr(self, "translate_selection_hotkey_thread") and self.translate_selection_hotkey_thread is not None:
                self.translate_selection_hotkey_thread.stop()
                self.translate_selection_hotkey_thread.join(timeout=0.5)
        except Exception as e:
            print(f"Error stopping selection hotkey thread: {e}")
        self.save_config()
        self.tray_icon.hide()  # Убираем иконку из трея
        event.accept()

    def exit_app(self):
        """Полный выход из приложения (вызывается из трея)."""
        self.force_quit = True
        self.close()
        # Явно завершаем приложение Qt
        QApplication.instance().quit()
        # Принудительный выход из процесса Python
        sys.exit(0)

    def translate_input_text(self):
        text = self.text_input.toPlainText()
        if text:
            # Сопоставление отображаемого языка с кодом
            lang_map = {
                "Русский": "ru",
                "Английский": "en",
                "English": "en",
                "Russian": "ru"
            }
            source_code = lang_map.get(self.source_lang.currentText(), "ru")
            target_code = lang_map.get(self.target_lang.currentText(), "en")
            try:
                # Показать прогресс, если потребуется установка моделей Argos
                progress = None
                # Локальный колбэк для обновления статуса
                def _status(msg):
                    nonlocal progress
                    if progress is None:
                        title = "Installing language packages…" if self.current_interface_language == "en" else "Установка языковых пакетов…"
                        progress = QProgressDialog(title, None, 0, 0, self)
                        progress.setCancelButton(None)
                        progress.setWindowModality(Qt.WindowModal)
                        progress.setAutoClose(False)
                        # hide ? button
                        try:
                            progress.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
                        except Exception:
                            pass
                        progress.show()
                        QApplication.processEvents()
                    try:
                        progress.setLabelText(str(msg))
                    except Exception:
                        pass
                    QApplication.processEvents()

                # Оборачиваем вызов перевода, передавая колбэк установки моделей
                def _translate_with_progress():
                    return translater.translate_text(text, source_code, target_code, status_callback=_status)

                translated_text = _translate_with_progress()
                if progress is not None:
                    try:
                        progress.close()
                    except Exception:
                        pass
                # Проверяем флаг copy_translated_text из кэша
                config = get_cached_config()
                auto_copy = config.get("copy_translated_text", True)
                lang = config.get("interface_language", "ru")
                theme = config.get("theme", "Темная")
                if auto_copy:
                    pyperclip.copy(translated_text)
                    try:
                        if config.get("copy_history", False):
                            save_copy_history(translated_text)
                    except Exception:
                        pass
                # Показываем универсальный диалог
                show_translation_dialog(self, translated_text, auto_copy=auto_copy, lang=lang, theme=theme)
                if not auto_copy:
                    try:
                        if config.get("copy_history", False):
                            save_copy_history(translated_text)
                    except Exception:
                        pass
            except Exception as e:
                QMessageBox.warning(self, "Ошибка перевода", str(e))

    def minimize_to_tray(self):
        self.hide()

# --- Универсальный диалог перевода ---
def show_translation_dialog(parent, translated_text, auto_copy=True, lang='ru', theme='Темная'):
    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton
    is_dark = theme == "Темная"
    bg = "#121212" if is_dark else "#ffffff"
    fg = "#ffffff" if is_dark else "#000000"
    btn_bg = "#1e1e1e" if is_dark else "#f0f0f0"
    btn_border = "#550000" if is_dark else "#cccccc"
    btn_hover = "#333333" if is_dark else "#e0e0e0"

    dlg = QDialog(parent)
    dlg.setWindowTitle("Click'n'Translate")
    dlg.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
    dlg.setWindowIcon(QIcon(resource_path("icons/icon.png")))
    dlg.setMinimumSize(350, 150)
    dlg.setMaximumSize(800, 600)
    dlg.setStyleSheet(f"QDialog {{ background-color: {bg}; }}")

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(12, 12, 12, 12)

    text_edit = QTextEdit()
    text_edit.setPlainText(translated_text)
    text_edit.setReadOnly(True)
    text_edit.setStyleSheet(
        f"QTextEdit {{ background-color: {bg}; color: {fg}; border: none; font-size: 16px; }}"
        f"QScrollBar:vertical {{ background: {bg}; width: 8px; }}"
        f"QScrollBar::handle:vertical {{ background: #555; border-radius: 4px; }}"
    )
    layout.addWidget(text_edit)

    btn_style = (
        f"QPushButton {{ background-color: {btn_bg}; color: {fg}; border: 1px solid {btn_border}; "
        f"padding: 6px 16px; min-width: 80px; font-size: 13px; }}"
        f"QPushButton:hover {{ background-color: {btn_hover}; }}"
    )

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()

    copy_text = "Copy" if lang == "en" else "Копировать"
    google_text = "Google" if lang == "en" else "Гугл"
    close_text = "Close" if lang == "en" else "Закрыть"

    if not auto_copy:
        copy_btn = QPushButton(copy_text)
        copy_btn.setStyleSheet(btn_style)
        copy_btn.clicked.connect(lambda: pyperclip.copy(translated_text))
        btn_layout.addWidget(copy_btn)

    google_btn = QPushButton(google_text)
    google_btn.setStyleSheet(btn_style)
    google_btn.clicked.connect(lambda: (webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(translated_text)), dlg.accept()))
    btn_layout.addWidget(google_btn)

    close_btn = QPushButton(close_text)
    close_btn.setStyleSheet(btn_style)
    close_btn.clicked.connect(dlg.accept)
    btn_layout.addWidget(close_btn)

    layout.addLayout(btn_layout)

    # Auto-size based on text length
    lines = translated_text.count('\n') + 1
    text_len = len(translated_text)
    height = min(max(150, lines * 28 + 80, text_len // 2 + 100), 600)
    width = min(max(350, min(text_len * 8, 700)), 800)
    dlg.resize(width, height)

    if auto_copy:
        pyperclip.copy(translated_text)

    dlg.exec_()

if __name__ == "__main__":

    # --- Обработка вызова как OCR подпроцесса -----------------
    if len(sys.argv) > 1 and sys.argv[1] in ("ocr", "copy", "translate"):
        from ocr import run_screen_capture
        mode_arg = sys.argv[1]
        run_screen_capture(mode="ocr" if mode_arg == "ocr" else mode_arg)
        sys.exit(0)

    # Single instance через Windows mutex
    def is_already_running():
        """Проверить через mutex, запущен ли уже экземпляр программы."""
        try:
            # Создаем уникальный mutex
            kernel32 = ctypes.windll.kernel32
            mutex = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX_NAME)
            if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                kernel32.CloseHandle(mutex)
                return True
            # Сохраняем handle чтобы mutex жил пока программа работает
            global _single_instance_mutex
            _single_instance_mutex = mutex
            return False
        except Exception:
            return False

    def bring_existing_to_front():
        """Отправить запущенному экземпляру команду раскрыть главное окно."""
        if not _SHOW_WINDOW_MESSAGE_ID:
            return False
        try:
            return bool(ctypes.windll.user32.PostMessageW(HWND_BROADCAST, _SHOW_WINDOW_MESSAGE_ID, 0, 0))
        except Exception:
            return False

    # Проверяем single instance (не разрешаем запуск нескольких копий)
    if is_already_running():
        # Пытаемся показать существующее окно
        bring_existing_to_front()
        sys.exit(0)
    
    # Читаем конфиг
    start_minimized = False
    try:
        config_path = get_data_file("config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            start_minimized = config.get("start_minimized", False)
    except Exception:
        pass
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    if _SHOW_WINDOW_MESSAGE_ID:
        try:
            _single_instance_event_filter = _SingleInstanceMessageFilter()
            app.installNativeEventFilter(_single_instance_event_filter)
        except Exception:
            _single_instance_event_filter = None
    # Повышаем приоритет процесса для уменьшения задержек
    try:
        HIGH_PRIORITY_CLASS = 0x00000080
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), HIGH_PRIORITY_CLASS)
    except Exception:
        pass
    # Прогрев OCR, чтобы первый запуск оверлея был быстрее
    try:
        from ocr import warm_up, prepare_overlay
        import logging
        # Логируем настройки при старте
        config = get_cached_config()
        logging.info("=" * 50)
        logging.info("ClicknTranslate Started")
        logging.info(f"OCR Engine: {config.get('ocr_engine', 'Windows').upper()}")
        logging.info(f"Translator: {config.get('translator_engine', 'Google').upper()}")
        logging.info(f"OCR Language: {config.get('last_ocr_language', 'ru').upper()}")
        logging.info("=" * 50)
        warm_up()
        # Подготовим заранее все режимы оверлея
        prepare_overlay("ocr")
        prepare_overlay("copy")
        prepare_overlay("translate")
    except Exception:
        pass
    window = DarkThemeApp()
    _main_window_ref = window
    # Всегда используем window.start_minimized, который инициализирован из config.json
    # Проверку на повторный запуск is_already_running() убрали
    if window.start_minimized:
        window.minimize_to_tray()
    else:
        window.show()
    app.exec_()
