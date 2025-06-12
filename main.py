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

from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QComboBox,
                             QWidget, QPushButton, QSystemTrayIcon, QMenu, QMessageBox, QLineEdit, QTextEdit, QDialog, QHBoxLayout, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QIcon
from settings_window import SettingsWindow
import translater  # Импорт модуля перевода

# --- Константы для RegisterHotKey ---
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

def simulate_copy():
    # Эмуляция нажатия Ctrl+C для копирования выделенного текста
    VK_CONTROL = 0x11
    VK_C = 0x43
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def ensure_json_file(filepath, default_content):
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_content, f, ensure_ascii=False, indent=4)

def ensure_data_dir_and_files():
    data_dir = os.path.join(get_app_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    # config.json
    config_path = os.path.join(data_dir, "config.json")
    ensure_json_file(config_path, {
        "theme": "Темная",
        "interface_language": "en",
        "autostart": False,
        "translation_mode": "English",
        "ocr_hotkeys": "Ctrl+O",
        "copy_hotkey": "Ctrl+K",
        "translate_hotkey": "Ctrl+F",
        "notifications": False,
        "history": False,
        "start_minimized": False,
        "show_update_info": True,
        "ocr_engine": "Windows"
    })
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
    data_dir = os.path.join(get_app_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    file_path = os.path.join(data_dir, filename)
    # Автоматически создаём нужные json-файлы с дефолтным содержимым
    if filename == "config.json":
        ensure_json_file(file_path, {
            "theme": "Темная",
            "interface_language": "en",
            "autostart": False,
            "translation_mode": "English",
            "ocr_hotkeys": "Ctrl+O",
            "copy_hotkey": "Ctrl+K",
            "translate_hotkey": "Ctrl+F",
            "notifications": False,
            "history": False,
            "start_minimized": False,
            "show_update_info": True,
            "ocr_engine": "Windows"
        })
    elif filename == "copy_history.json":
        ensure_json_file(file_path, [])
    elif filename == "translation_history.json":
        ensure_json_file(file_path, [])
    elif filename == "settings.json":
        ensure_json_file(file_path, {})
    return file_path

def save_copy_history(text):
    try:
        config_path = get_data_file("config.json")
        ensure_json_file(config_path, {
            "theme": "Темная",
            "interface_language": "en",
            "autostart": False,
            "translation_mode": "English",
            "ocr_hotkeys": "Ctrl+O",
            "copy_hotkey": "Ctrl+K",
            "translate_hotkey": "Ctrl+F",
            "notifications": False,
            "history": False,
            "start_minimized": False,
            "show_update_info": True,
            "ocr_engine": "Windows"
        })
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        if not config.get("copy_history", False):
            return
    except Exception:
        return
    record = {"timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "text": text}
    history_file = get_data_file("copy_history.json")
    ensure_json_file(history_file, [])
    history = []
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []
    history.append(record)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

class HotkeyListenerThread(threading.Thread):
    def __init__(self, hotkey_str, callback, hotkey_id=1):
        super().__init__()
        self.hotkey_str = hotkey_str
        self.callback = callback
        self.hotkey_id = hotkey_id
        self.daemon = True  # поток завершается вместе с основным приложением
        self.modifiers, self.vk = self.parse_hotkey(self.hotkey_str)
        if self.vk is None:
            print("Неверный формат горячей клавиши.")

    def parse_hotkey(self, hotkey_str):
        modifiers = 0
        vk = None
        main_keys = []
        # Маппинг спецсимволов на виртуальные коды Windows
        special_vk = {
            ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF, "`": 0xC0,
            "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE
        }
        parts = hotkey_str.split("+")
        for part in parts:
            token = part.strip().lower()
            if token in ("ctrl", "control"):
                modifiers |= MOD_CONTROL
            elif token == "alt":
                modifiers |= MOD_ALT
            elif token == "shift":
                modifiers |= MOD_SHIFT
            elif token == "win":
                modifiers |= MOD_WIN
            elif token == "del":
                main_keys.append(0x2E)
            elif token.startswith("f") and len(token) > 1 and token[1:].isdigit():
                try:
                    fnum = int(token[1:])
                    main_keys.append(0x70 + fnum - 1)  # VK_F1 = 0x70
                except:
                    pass
            elif token in special_vk:
                main_keys.append(special_vk[token])
            elif len(token) == 1:
                main_keys.append(ord(token.upper()))
            # иначе игнорируем
        if len(main_keys) == 0:
            print("Ошибка: не выбрана основная клавиша для хоткея.")
            return modifiers, None
        if len(main_keys) > 1:
            print("Ошибка: Windows поддерживает только одну основную клавишу в хоткее! Выбрано: " + str(main_keys))
            return modifiers, None
        vk = main_keys[0]
        return modifiers, vk

    def run(self):
        if self.vk is None:
            return
        if not ctypes.windll.user32.RegisterHotKey(None, self.hotkey_id, self.modifiers, self.vk):
            print("Не удалось установить перехват горячей клавиши.")
            return
        msg = wintypes.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                QTimer.singleShot(0, self.callback)
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
        ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)

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
            version = "<span style='color:#aaa; font-size:13px;'>V1.00.0</span><br><br>"
            body = ("<span style='font-size:15px;'>"
                    "Советуем <b>подписаться</b> на Telegram-канал разработчика, чтобы не пропустить обновления программы и получать свежие новости.<br><br>"
                    "<a href='https://t.me/jabrail_digital' style='color:#7A5FA1; font-size:17px;'>https://t.me/jabrail_digital</a>"
                    "</span>")
            checkbox_text = "Больше не показывать это окно"
            close_text = "Закрыть"
        else:
            self.setWindowTitle("News")
            title = "<b>Welcome to Click'n'Translate!</b><br>"
            version = "<span style='color:#aaa; font-size:13px;'>V1.00.0</span><br><br>"
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
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Click'n'Translate")
        self.setFixedSize(700, 400)
        self._is_dragging = False

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

        self.settings_window = None
        self.init_ui()

        self.create_tray_icon()

        # Используем параметр "ocr_hotkeys" для привязки горячей клавиши OCR (дефолт "Ctrl+O")
        ocr_hotkey = self.config.get("ocr_hotkeys", "Ctrl+O")
        self.hotkey_thread = HotkeyListenerThread(ocr_hotkey, self.launch_ocr)
        self.hotkey_thread.start()
        # Слушатели для горячих клавиш копирования и перевода (значения берутся из настроек)
        copy_hotkey = self.config.get("copy_hotkey", "")
        if copy_hotkey:
            self.copy_hotkey_thread = HotkeyListenerThread(copy_hotkey, self.launch_copy)
            self.copy_hotkey_thread.start()
        translate_hotkey = self.config.get("translate_hotkey", "")
        if translate_hotkey:
            self.translate_hotkey_thread = HotkeyListenerThread(translate_hotkey, self.launch_translate)
            self.translate_hotkey_thread.start()

        self.HotkeyListenerThread = HotkeyListenerThread

        self.setWindowIcon(QIcon(resource_path("icons/icon.ico")))

    def load_config(self):
        config_path = get_data_file("config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            self.current_theme = self.config.get("theme", "Темная")
            self.current_interface_language = self.config.get("interface_language", "en")
            self.autostart = self.config.get("autostart", False)
            self.translation_mode = self.config.get("translation_mode", LANGUAGES[self.current_interface_language][0])
            self.start_minimized = self.config.get("start_minimized", False)
        else:
            self.config = {
                "theme": "Темная",
                "interface_language": "en",
                "autostart": False,
                "translation_mode": LANGUAGES["en"][0],
                "ocr_hotkeys": "Ctrl+O",
                "copy_hotkey": "Ctrl+K",
                "translate_hotkey": "Ctrl+F",
                "notifications": False,
                "history": False,
                "start_minimized": False,
                "show_update_info": True,
                "ocr_engine": "Windows"
            }
            self.current_theme = self.config["theme"]
            self.current_interface_language = self.config["interface_language"]
            self.autostart = self.config["autostart"]
            self.translation_mode = self.config["translation_mode"]
            self.start_minimized = self.config["start_minimized"]
            self.save_config()

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

    def set_autostart(self, enable: bool):
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_WRITE)
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.realpath(sys.argv[0])
            if enable:
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
        self.flag_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['title'])
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
        self.close_button.clicked.connect(QApplication.instance().quit)

        self.show_main_screen()
        self.apply_theme()

    def create_tray_icon(self):
        lang = self.current_interface_language
        if lang == "en":
            open_text = "Open"
            exit_text = "Exit"
            ocr_text = "OCR"
            copy_text = "Copy Text"
            translate_text = "Translate"
        else:
            open_text = "Открыть"
            exit_text = "Закрыть программу"
            ocr_text = "OCR"
            copy_text = "Копировать текст"
            translate_text = "Перевести"
        self.tray_icon = QSystemTrayIcon(QIcon(resource_path("icons/icon.ico")), self)
        tray_menu = QMenu()
        open_action = tray_menu.addAction(open_text)
        open_action.triggered.connect(self.show_window_from_tray)
        ocr_action = tray_menu.addAction(ocr_text)
        ocr_action.triggered.connect(self.launch_ocr)
        copy_action = tray_menu.addAction(copy_text)
        copy_action.triggered.connect(self.launch_copy)
        translate_action = tray_menu.addAction(translate_text)
        translate_action.triggered.connect(self.launch_translate)
        exit_action = tray_menu.addAction(exit_text)
        exit_action.triggered.connect(QApplication.instance().quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        from PyQt5.QtWidgets import QSystemTrayIcon
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window_from_tray()

    def show_window_from_tray(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)

    def _start_external(self, script_or_exe, *args):
        """Launch helper that works both in dev (python script) and frozen (exe)."""
        if getattr(sys, 'frozen', False):
            # В собранной версии просто перезапускаем тот же exe с нужным параметром
            subprocess.Popen([sys.executable, *args])
        else:
            # В режиме разработки запускаем python-скрипт
            subprocess.Popen([sys.executable, script_or_exe, *args])

    def launch_ocr(self):
        if hasattr(self, "source_lang"):
            src_text = self.source_lang.currentText().lower()
            lang = "en" if ("english" in src_text or "английский" in src_text) else "ru"
        else:
            lang = self.config.get("ocr_language", self.current_interface_language)
        if getattr(sys, 'frozen', False):
            self._start_external("ocr.py", "ocr", lang)
        else:
            self._start_external("ocr.py", lang)
        self.hide()

    def launch_copy(self):
        copy_hotkey = self.config.get("copy_hotkey", "")
        if copy_hotkey:
            if getattr(sys, 'frozen', False):
                self._start_external("ocr.py", "copy")  # same flag
            else:
                self._start_external("ocr.py", "copy")
        self.hide()

    def launch_translate(self):
        translate_hotkey = self.config.get("translate_hotkey", "")
        if translate_hotkey:
            if getattr(sys, 'frozen', False):
                self._start_external("ocr.py", "translate")
            else:
                self._start_external("ocr.py", "translate")
        self.hide()

    def restart_hotkey_listener(self):
        self.hotkey_thread = HotkeyListenerThread(self.config.get("ocr_hotkeys", "Ctrl+O"), self.launch_ocr)
        self.hotkey_thread.start()

    def apply_theme(self):
        theme = THEMES[self.current_theme]
        # Настроим стиль скроллбара в зависимости от темы
        scrollbar_bg = theme['button_background'] if self.current_theme != 'Темная' else '#232323'
        scrollbar_handle = '#888' if self.current_theme != 'Темная' else '#444'
        scrollbar_handle_hover = '#aaa' if self.current_theme != 'Темная' else '#666'
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
                width: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
                border: none;
            }}
            QTextEdit QScrollBar::handle:vertical {{
                background: {scrollbar_handle};
                min-height: 20px;
                border-radius: 5px;
                border: none;
            }}
            QTextEdit QScrollBar::add-line:vertical, QTextEdit QScrollBar::sub-line:vertical {{
                background: none;
                height: 0px;
            }}
            QTextEdit QScrollBar::handle:vertical:hover {{
                background: {scrollbar_handle_hover};
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
        # Стильная надпись 'Офлайн перевод'/'Offline translation'
        lang_label_text = "Offline translation" if self.current_interface_language == "en" else "Офлайн перевод"
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

        # --- Блок хоткеев ---
        hotkey_label_style = "font-size: 13px; color: #888; margin-bottom: 0px;"
        hotkey_value_style = "font-size: 15px; color: #7A5FA1; font-weight: bold; margin-bottom: 2px;"
        copy_hotkey = self.config.get("copy_hotkey", "")
        translate_hotkey = self.config.get("translate_hotkey", "")
        if copy_hotkey:
            # Получаем текущий OCR engine
            config_path = get_data_file("config.json")
            ocr_engine = "Windows"
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    ocr_engine = config.get("ocr_engine", "Windows")
            except Exception:
                pass
            hotkey_row = QHBoxLayout()
            label = QLabel(("Copy hotkey:" if self.current_interface_language == "en" else "Горячая клавиша копирования:") + f" <span style='{hotkey_value_style}'>{copy_hotkey}</span>")
            label.setStyleSheet(hotkey_label_style)
            label.setTextFormat(Qt.RichText)
            hotkey_row.addWidget(label, alignment=Qt.AlignLeft)
            ocr_label = QLabel(f"OCR: {ocr_engine}")
            ocr_label.setAlignment(Qt.AlignRight)
            ocr_label.setStyleSheet("color: #7A5FA1; font-size: 14px; font-weight: bold; margin-top: 2px; margin-bottom: 2px; margin-right: 8px;")
            hotkey_row.addWidget(ocr_label, alignment=Qt.AlignRight)
            self.main_layout.addLayout(hotkey_row)
        if translate_hotkey:
            label = QLabel(("Translate hotkey:" if self.current_interface_language == "en" else "Горячая клавиша перевода:") + f" <span style='{hotkey_value_style}'>{translate_hotkey}</span>")
            label.setStyleSheet(hotkey_label_style)
            label.setTextFormat(Qt.RichText)
            self.main_layout.addWidget(label)

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

    def closeEvent(self, event):
        self.save_config()
        event.accept()

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
                translated_text = translater.translate_text(text, source_code, target_code)
                # Проверяем флаг copy_translated_text
                config_path = get_data_file("config.json")
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                auto_copy = config.get("copy_translated_text", True)
                lang = config.get("interface_language", "ru")
                theme = config.get("theme", "Темная")
                if auto_copy:
                    pyperclip.copy(translated_text)
                    try:
                        if config.get("copy_history", False):
                            self.save_copy_history(translated_text)
                    except Exception:
                        pass
                # Показываем универсальный диалог
                show_translation_dialog(self, translated_text, auto_copy=auto_copy, lang=lang, theme=theme)
                if not auto_copy:
                    try:
                        if config.get("copy_history", False):
                            self.save_copy_history(translated_text)
                    except Exception:
                        pass
            except Exception as e:
                QMessageBox.warning(self, "Ошибка перевода", str(e))

    def minimize_to_tray(self):
        self.hide()

# --- Универсальный диалог перевода ---
def show_translation_dialog(parent, translated_text, auto_copy=True, lang='ru', theme='Темная'):
    import pyperclip
    if theme == "Темная":
        style = (
            "QMessageBox { background-color: #121212; color: #ffffff; } "
            "QLabel { color: #ffffff; font-size: 18px; } "
            "QPushButton { background-color: #1e1e1e; color: #ffffff; border: 1px solid #550000; padding: 5px; min-width: 80px; } "
            "QPushButton:hover { background-color: #333333; }"
        )
    else:
        style = (
            "QMessageBox { background-color: #ffffff; color: #000000; } "
            "QLabel { color: #000000; font-size: 18px; } "
            "QPushButton { background-color: #f0f0f0; color: #000000; border: 1px solid #cccccc; padding: 5px; min-width: 80px; } "
            "QPushButton:hover { background-color: #e0e0e0; }"
        )
    copy_text = "Copy" if lang == "en" else "Копировать"
    close_text = "Close" if lang == "en" else "Закрыть"
    google_text = "Google" if lang == "en" else "Гугл"
    msg = QMessageBox(parent)
    msg.setWindowTitle(" ")
    msg.setText(translated_text)
    if not auto_copy:
        copy_button = msg.addButton(copy_text, QMessageBox.ActionRole)
    google_button = msg.addButton(google_text, QMessageBox.ActionRole)
    close_button = msg.addButton(close_text, QMessageBox.RejectRole)
    msg.setStyleSheet(style)
    msg.setWindowFlags(msg.windowFlags() | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
    msg.setWindowIcon(QIcon("icons/icon.png"))
    msg.setIcon(QMessageBox.NoIcon)
    if auto_copy:
        pyperclip.copy(translated_text)
        # save_copy_history вызывается в вызывающем коде
    while True:
        clicked = msg.exec_()
        if not auto_copy and msg.clickedButton() == copy_button:
            pyperclip.copy(translated_text)
            # save_copy_history вызывается в вызывающем коде
        elif msg.clickedButton() == google_button:
            url = "https://www.google.com/search?q=" + urllib.parse.quote(translated_text)
            webbrowser.open(url)
            break
        else:
            break

if __name__ == "__main__":
    # --- Обработка вызова как OCR подпроцесса -----------------
    if len(sys.argv) > 1 and sys.argv[1] in ("ocr", "copy", "translate"):
        from ocr import run_screen_capture
        mode_arg = sys.argv[1]
        run_screen_capture(mode="ocr" if mode_arg == "ocr" else mode_arg)
        sys.exit(0)

    # Проверяем, есть ли уже процесс
    def is_already_running():
        this_pid = os.getpid()
        exe = sys.executable.lower()
        for p in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
            if p.info['pid'] == this_pid:
                continue
            try:
                if p.info['exe'] and p.info['exe'].lower() == exe:
                    return True
            except Exception:
                pass
        return False
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
    window = DarkThemeApp()
    # Всегда используем window.start_minimized, который инициализирован из config.json
    if window.start_minimized and not is_already_running():
        window.minimize_to_tray()
    else:
        window.show()
    app.exec_()
