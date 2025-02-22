import json
import getpass
import os
import sys
import winreg
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QComboBox, QWidget, QPushButton
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from settings_window import SettingsWindow



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
        "back": "Back to main"
    },
    "ru": {
        "title": "Click'n'Translate",
        "select_language": "Выберите языки перевода",
        "start": "Начать",
        "translation_selected": "Выбран перевод: {src} → {tgt}",
        "settings": "Настройки",
        "back": "Назад"
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

    def load_config(self):
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
            self.current_theme = self.config.get("theme", "Темная")
            self.current_interface_language = self.config.get("interface_language", "en")
            self.autostart = self.config.get("autostart", False)
            self.translation_mode = self.config.get("translation_mode", LANGUAGES[self.current_interface_language][0])
            self.hotkeys = self.config.get("hotkeys", "")
        else:
            self.config = {
                "theme": "Темная",
                "interface_language": "en",
                "autostart": False,
                "translation_mode": LANGUAGES["en"][0],
                "hotkeys": "",
                "notifications": False,
                "history": False
            }
            self.current_theme = self.config["theme"]
            self.current_interface_language = self.config["interface_language"]
            self.autostart = self.config["autostart"]
            self.translation_mode = self.config["translation_mode"]
            self.hotkeys = self.config["hotkeys"]

    def save_config(self):
        self.config["theme"] = self.current_theme
        self.config["interface_language"] = self.current_interface_language
        self.config["autostart"] = getattr(self, "autostart", False)
        self.config["translation_mode"] = getattr(
            self, "translation_mode", LANGUAGES[self.current_interface_language][0]
        )
        self.config["hotkeys"] = getattr(self, "hotkeys", "")
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
        # Заменили пути на icons/American_flag.png и icons/Russian_flag.png
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

    def apply_theme(self):
        theme = THEMES[self.current_theme]
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
                font-size: 18px; /* увеличили размер шрифта */
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
                border: none;
                padding: 10px;
                font-size: 14px;
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

        # В зависимости от того, открыто ли окно настроек или нет, иконка "шестерёнки" меняется:
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
        # Заменили пути на icons/sun.png и icons/moon.png
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

        self.label = QLabel(INTERFACE_TEXT[self.current_interface_language]["select_language"])
        self.label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.label)

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

        self.start_button = QPushButton(INTERFACE_TEXT[self.current_interface_language]["start"])
        self.main_layout.addWidget(self.start_button)
        self.apply_theme()

    def show_settings(self):
        self.clear_layout()
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


if __name__ == "__main__":
    app = QApplication([])
    window = DarkThemeApp()
    window.show()
    app.exec_()
