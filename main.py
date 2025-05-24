import json
import getpass
import os
import sys
import winreg
import subprocess
import ctypes
import threading
import time
import pyperclip
from ctypes import wintypes
import psutil
import datetime

from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QComboBox,
                             QWidget, QPushButton, QSystemTrayIcon, QMenu, QMessageBox, QLineEdit, QTextEdit)
from PyQt5.QtCore import Qt, QTimer
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

def save_copy_history(text):
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        if not config.get("copy_history", False):
            return
    except Exception:
        return
    record = {"timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "text": text}
    history_file = "copy_history.json"
    history = []
    if os.path.exists(history_file):
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

class DarkThemeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Click'n'Translate")
        self.setFixedSize(600, 400)
        self._is_dragging = False

        self.load_config()

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

        self.setWindowIcon(QIcon("icons/icon.png"))

    def load_config(self):
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
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
                "start_minimized": False
            }
            self.current_theme = self.config["theme"]
            self.current_interface_language = self.config["interface_language"]
            self.autostart = self.config["autostart"]
            self.translation_mode = self.config["translation_mode"]
            self.start_minimized = self.config["start_minimized"]

    def save_config(self):
        self.config["theme"] = self.current_theme
        self.config["interface_language"] = self.current_interface_language
        self.config["autostart"] = getattr(self, "autostart", False)
        self.config["translation_mode"] = getattr(self, "translation_mode",
                                                  LANGUAGES[self.current_interface_language][0])
        self.config["start_minimized"] = getattr(self, "start_minimized", False)
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def set_autostart(self, enable: bool):
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_WRITE)
            exe_path = os.path.realpath(sys.argv[0])
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
            QIcon("icons/American_flag.png") if self.current_interface_language == "en"
            else QIcon("icons/Russian_flag.png")
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
        self.tray_icon = QSystemTrayIcon(QIcon("icons/icon.png"), self)
        tray_menu = QMenu()
        launch_action = tray_menu.addAction("Запустить OCR")
        launch_action.triggered.connect(self.launch_ocr)
        open_action = tray_menu.addAction("Открыть приложение")
        open_action.triggered.connect(self.show_window_from_tray)
        exit_action = tray_menu.addAction("Выход")
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

    def launch_ocr(self):
        if hasattr(self, "source_lang"):
            src_text = self.source_lang.currentText().lower()
            if "english" in src_text or "английский" in src_text:
                lang = "en"
            else:
                lang = "ru"
        else:
            lang = self.config.get("ocr_language", self.current_interface_language)
        subprocess.Popen([sys.executable, "ocr.py", lang])
        self.hide()

    def launch_copy(self):
        copy_hotkey = self.config.get("copy_hotkey", "")
        if copy_hotkey:
            subprocess.Popen([sys.executable, "ocr.py", "copy"])
        self.hide()

    def launch_translate(self):
        translate_hotkey = self.config.get("translate_hotkey", "")
        if translate_hotkey:
            subprocess.Popen([sys.executable, "ocr.py", "translate"])
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
                    self.settings_button.setIcon(QIcon("icons/settings_light.png"))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['settings'])
                else:
                    self.settings_button.setIcon(QIcon("icons/settings_dark.png"))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['settings'])
            else:
                if self.current_theme == "Темная":
                    self.settings_button.setIcon(QIcon("icons/light_home.png"))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])
                else:
                    self.settings_button.setIcon(QIcon("icons/dark_home.png"))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])

    def update_theme_icon(self):
        icon_path = "icons/sun.png" if self.current_theme == "Темная" else "icons/moon.png"
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
            self.flag_button.setIcon(QIcon("icons/Russian_flag.png"))
        else:
            self.current_interface_language = "en"
            self.flag_button.setIcon(QIcon("icons/American_flag.png"))
        self.save_config()
        if self.settings_window is not None:
            self.settings_window.update_language()
        else:
            self.show_main_screen()
        self.apply_theme()
        self.update_theme_icon()

    def set_settings_button_to_home(self):
        if self.current_theme == "Темная":
            self.settings_button.setIcon(QIcon("icons/dark_home.png"))
        else:
            self.settings_button.setIcon(QIcon("icons/light_home.png"))
        self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])
        try:
            self.settings_button.clicked.disconnect()
        except Exception:
            pass
        self.settings_button.clicked.connect(self.show_main_screen)

    def set_settings_button_to_settings(self):
        if self.current_theme == "Темная":
            self.settings_button.setIcon(QIcon("icons/settings_light.png"))
        else:
            self.settings_button.setIcon(QIcon("icons/settings_dark.png"))
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
            label = QLabel(("Copy hotkey:" if self.current_interface_language == "en" else "Горячая клавиша копирования:") + f" <span style='{hotkey_value_style}'>{copy_hotkey}</span>")
            label.setStyleSheet(hotkey_label_style)
            label.setTextFormat(Qt.RichText)
            self.main_layout.addWidget(label)
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
        while self.main_layout.count():
            widget = self.main_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()

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
                msg = QMessageBox(self)
                msg.setText(translated_text)
                copy_button = msg.addButton("Копировать", QMessageBox.ActionRole)
                msg.addButton(QMessageBox.Ok)
                msg.setStyleSheet(
                    "QMessageBox { background-color: #121212; color: #ffffff; } "
                    "QLabel { color: #ffffff; font-size: 18px; } "
                    "QPushButton { background-color: #1e1e1e; color: #ffffff; border: 1px solid #550000; padding: 5px; min-width: 80px; } "
                    "QPushButton:hover { background-color: #333333; }"
                )
                msg.exec_()
                if msg.clickedButton() == copy_button:
                    pyperclip.copy(translated_text)
                    self.save_copy_history(translated_text)
            except Exception as e:
                QMessageBox.warning(self, "Ошибка перевода", str(e))

    def minimize_to_tray(self):
        self.hide()

if __name__ == "__main__":
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
        with open("config.json", "r", encoding="utf-8") as f:
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
