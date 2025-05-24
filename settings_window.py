import getpass
import os
import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox, QKeySequenceEdit,
    QMessageBox, QTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

USER_NAME = getpass.getuser()
SETTINGS_TEXT = {
    "en": {
        "autostart": "Start with Windows",
        "translation_mode": "Text translation mode: {mode}",
        "hotkeys": "Configure hotkeys",
        "save_and_back": "Save and return",
        "copy_to_clipboard": "Copy to clipboard",
        "history": "Save translation history",
        "test_ocr": "Test OCR Translation",
        "save": "Save",
        "back": "Back",
        "remove_hotkey": "Press ESC to remove hotkey",
        "history_view": "View translation history",
        "start_minimized": "Start in shadow mode",
        "copy_history_view": "Show copy history",
        "copy_history": "Save copy history",
        "clear_copy_history": "Clear copy history",
        "clear_translation_history": "Clear translation history",
        "history_title": "Translation history",
        "copy_history_title": "Copy history",
        "history_empty": "History is empty.",
        "history_error": "Error reading history."
    },
    "ru": {
        "autostart": "Запускать вместе с Windows",
        "translation_mode": "Режим перевода текста: {mode}",
        # Обновлённый текст: теперь явно указывается мгновенный перевод выделенного текста
        "hotkeys": "Настроить горячие клавиши",
        "save_and_back": "Сохранить и вернуться",
        "copy_to_clipboard": "Копировать в буфер",
        "history": "Сохранять историю переводов",
        "test_ocr": "Проверить OCR",
        "save": "Сохранить",
        "back": "Назад",
        "remove_hotkey": "Нажмите ESC для удаления горячей клавиши",
        "history_view": "Посмотреть историю переводов",
        "start_minimized": "Запускать в режиме тень",
        "copy_history_view": "Показать историю копирований",
        "copy_history": "Сохранять историю копирований",
        "clear_copy_history": "Очистить историю копирований",
        "clear_translation_history": "Очистить историю переводов",
        "history_title": "История переводов",
        "copy_history_title": "История копирований",
        "history_empty": "История пуста.",
        "history_error": "Ошибка чтения истории."
    }
}

class ClearableKeySequenceEdit(QKeySequenceEdit):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(event)

# Класс HistoryDialog удалён, т.к. история теперь отображается внутри настроек

class SettingsWindow(QWidget):
    def switch_startup(self, state):
        self.parent.config["autostart"] = self.autostart_checkbox.isChecked()
        self.parent.save_config()
        self.parent.set_autostart(self.autostart_checkbox.isChecked())
        self.parent.autostart = self.autostart_checkbox.isChecked()

    def auto_save_setting(self, key, value):
        self.parent.config[key] = value
        if key == "start_minimized":
            self.parent.start_minimized = value
        if key == "autostart":
            self.parent.autostart = value
        self.parent.save_config()

    def on_history_checkbox_toggled(self, state):
        self.auto_save_setting("history", state)
        if hasattr(self, "history_view_button"):
            self.history_view_button.setEnabled(True)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.hotkeys_mode = False
        self.create_layout()
        self.init_ui()
        self.apply_theme()

    def create_layout(self):
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(0)
        self.setLayout(self.main_layout)

    def clear_main_layout(self):
        while self.main_layout.count():
            widget = self.main_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()

    def init_ui(self):
        self.clear_main_layout()
        self.hotkeys_mode = False
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(0)
        lang = self.parent.current_interface_language

        # --- ГРУППА ЧЕКБОКСОВ ---
        self.main_layout.addSpacing(5)

        self.autostart_checkbox = QCheckBox(SETTINGS_TEXT[lang]["autostart"])
        self.autostart_checkbox.setChecked(self.parent.config.get("autostart", False))
        self.autostart_checkbox.clicked.connect(self.switch_startup)
        self.main_layout.addWidget(self.autostart_checkbox)
        self.main_layout.addSpacing(8)

        self.start_minimized_checkbox = QCheckBox(SETTINGS_TEXT[lang]["start_minimized"])
        self.start_minimized_checkbox.setChecked(self.parent.config.get("start_minimized", False))
        self.start_minimized_checkbox.toggled.connect(lambda state: self.auto_save_setting("start_minimized", state))
        self.main_layout.addWidget(self.start_minimized_checkbox)
        self.main_layout.addSpacing(8)

        self.copy_checkbox = QCheckBox(SETTINGS_TEXT[lang]["copy_to_clipboard"])
        self.copy_checkbox.setChecked(self.parent.config.get("copy_to_clipboard", False))
        self.copy_checkbox.toggled.connect(lambda state: self.auto_save_setting("copy_to_clipboard", state))
        self.main_layout.addWidget(self.copy_checkbox)
        self.main_layout.addSpacing(8)

        self.copy_history_checkbox = QCheckBox(SETTINGS_TEXT[lang]["copy_history"])
        self.copy_history_checkbox.setChecked(self.parent.config.get("copy_history", False))
        self.copy_history_checkbox.toggled.connect(lambda state: self.auto_save_setting("copy_history", state))
        self.main_layout.addWidget(self.copy_history_checkbox)
        self.main_layout.addSpacing(8)

        self.history_checkbox = QCheckBox(SETTINGS_TEXT[lang]["history"])
        self.history_checkbox.setChecked(self.parent.config.get("history", False))
        self.history_checkbox.toggled.connect(self.on_history_checkbox_toggled)
        self.main_layout.addWidget(self.history_checkbox)

        self.main_layout.addSpacing(100)

        # --- ГРУППА КНОПОК ---
        hotkeys_button = QPushButton(SETTINGS_TEXT[lang]["hotkeys"])
        hotkeys_button.clicked.connect(self.show_hotkeys_screen)
        self.main_layout.addWidget(hotkeys_button)

        self.main_layout.addSpacing(20)

        # Кнопка истории переводов
        self.history_view_button = QPushButton(SETTINGS_TEXT[lang]["history_view"])
        self.history_view_button.clicked.connect(self.show_history_view)
        self.history_view_button.setEnabled(True)
        self.main_layout.addWidget(self.history_view_button)

        self.main_layout.addSpacing(12)

        # Кнопка истории копирований
        self.copy_history_view_button = QPushButton(SETTINGS_TEXT[lang]["copy_history_view"])
        self.copy_history_view_button.clicked.connect(self.show_copy_history_view)
        self.copy_history_view_button.setEnabled(True)
        self.main_layout.addWidget(self.copy_history_view_button)

        self.main_layout.addSpacing(5)

    def show_hotkeys_screen(self):
        self.clear_main_layout()
        self.hotkeys_mode = True
        self.main_layout.setContentsMargins(9, 9, 9, 9)
        self.main_layout.setSpacing(9)

        lang = self.parent.current_interface_language

        # Блок для настройки горячей клавиши "Copy Selected"
        label_copy = QLabel("Copy Selected Hotkey:" if lang == "en" else "Горячая клавиша для копирования")
        self.main_layout.addWidget(label_copy)

        self.copy_hotkey_input = ClearableKeySequenceEdit()
        saved_copy_hotkey = self.parent.config.get("copy_hotkey", "")
        self.copy_hotkey_input.setKeySequence(QKeySequence(saved_copy_hotkey))
        self.main_layout.addWidget(self.copy_hotkey_input)
        self.copy_hotkey_input.keySequenceChanged.connect(self.save_copy_hotkey)

        self.main_layout.addSpacing(10)

        # Блок для настройки горячей клавиши "Translate Selected"
        label_translate = QLabel("Translate Selected Hotkey:" if lang == "en" else "Горячая клавиша для мгновенного перевода выделенного текста")
        self.main_layout.addWidget(label_translate)

        self.translate_hotkey_input = ClearableKeySequenceEdit()
        saved_translate_hotkey = self.parent.config.get("translate_hotkey", "")
        self.translate_hotkey_input.setKeySequence(QKeySequence(saved_translate_hotkey))
        self.main_layout.addWidget(self.translate_hotkey_input)
        self.translate_hotkey_input.keySequenceChanged.connect(self.save_translate_hotkey)

        # Инструктивная надпись для удаления комбинации
        remove_label = QLabel(SETTINGS_TEXT[lang]["remove_hotkey"])
        self.main_layout.addWidget(remove_label)

        # Кнопка возврата
        back_button = QPushButton(SETTINGS_TEXT[lang]["back"])
        back_button.clicked.connect(self.back_from_hotkeys)
        self.main_layout.addWidget(back_button)

        self.apply_theme()

    def save_copy_hotkey(self):
        hotkey_str = self.copy_hotkey_input.keySequence().toString()
        self.parent.config["copy_hotkey"] = hotkey_str
        self.parent.save_config()
        # Перезапуск слушателя горячих клавиш для копирования
        if hasattr(self.parent, "copy_hotkey_thread") and self.parent.copy_hotkey_thread is not None:
            # Остановить старый поток невозможно, но мы просто не будем его использовать
            self.parent.copy_hotkey_thread = None
        if hotkey_str:
            self.parent.copy_hotkey_thread = self.parent.HotkeyListenerThread(hotkey_str, self.parent.launch_copy)
            self.parent.copy_hotkey_thread.start()

    def save_translate_hotkey(self):
        hotkey_str = self.translate_hotkey_input.keySequence().toString()
        self.parent.config["translate_hotkey"] = hotkey_str
        self.parent.save_config()
        # Перезапуск слушателя горячих клавиш для перевода
        if hasattr(self.parent, "translate_hotkey_thread") and self.parent.translate_hotkey_thread is not None:
            self.parent.translate_hotkey_thread = None
        if hotkey_str:
            self.parent.translate_hotkey_thread = self.parent.HotkeyListenerThread(hotkey_str, self.parent.launch_translate)
            self.parent.translate_hotkey_thread.start()

    def back_from_hotkeys(self):
        self.init_ui()
        self.apply_theme()

    def show_history_view(self):
        self.clear_main_layout()
        lang = self.parent.current_interface_language

        title_label = QLabel(SETTINGS_TEXT[lang]["history_title"])
        self.main_layout.addWidget(title_label)

        self.history_text_edit = QTextEdit()
        self.history_text_edit.setReadOnly(True)
        if self.parent.current_theme == "Темная":
            self.history_text_edit.setStyleSheet("background-color: #121212; color: #ffffff;")
        else:
            self.history_text_edit.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.main_layout.addWidget(self.history_text_edit)
        self.load_history_embedded()

        self.main_layout.addSpacing(10)

        clear_button = QPushButton(SETTINGS_TEXT[lang]["clear_translation_history"])
        clear_button.clicked.connect(self.clear_history)
        self.main_layout.addWidget(clear_button)

        self.main_layout.addSpacing(10)

        back_button = QPushButton(SETTINGS_TEXT[lang]["back"])
        back_button.clicked.connect(self.back_from_history)
        self.main_layout.addWidget(back_button)

    def load_history_embedded(self):
        history_file = "translation_history.json"
        lang = self.parent.current_interface_language
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                if history:
                    text = ""
                    for record in history:
                        text += f"{record.get('timestamp')} ({record.get('language')}):\n"
                        text += f"{record.get('text')}\n"
                        text += "-" * 40 + "\n\n"
                    self.history_text_edit.setText(text)
                else:
                    self.history_text_edit.setText(SETTINGS_TEXT[lang]["history_empty"])
            except Exception as e:
                self.history_text_edit.setText(SETTINGS_TEXT[lang]["history_error"])
        else:
            self.history_text_edit.setText(SETTINGS_TEXT[lang]["history_empty"])

    def clear_history(self):
        history_file = "translation_history.json"
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=4)
            self.load_history_embedded()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", "Не удалось очистить историю переводов.")

    def back_from_history(self):
        self.init_ui()
        self.apply_theme()

    def show_copy_history_view(self):
        self.clear_main_layout()
        lang = self.parent.current_interface_language

        title_label = QLabel(SETTINGS_TEXT[lang]["copy_history_title"])
        self.main_layout.addWidget(title_label)

        self.copy_history_text_edit = QTextEdit()
        self.copy_history_text_edit.setReadOnly(True)
        if self.parent.current_theme == "Темная":
            self.copy_history_text_edit.setStyleSheet("background-color: #121212; color: #ffffff;")
        else:
            self.copy_history_text_edit.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.main_layout.addWidget(self.copy_history_text_edit)
        self.load_copy_history_embedded()

        self.main_layout.addSpacing(10)

        clear_button = QPushButton(SETTINGS_TEXT[lang]["clear_copy_history"])
        clear_button.clicked.connect(self.clear_copy_history)
        self.main_layout.addWidget(clear_button)

        self.main_layout.addSpacing(10)

        back_button = QPushButton(SETTINGS_TEXT[lang]["back"])
        back_button.clicked.connect(self.back_from_copy_history)
        self.main_layout.addWidget(back_button)

    def load_copy_history_embedded(self):
        history_file = "copy_history.json"
        lang = self.parent.current_interface_language
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                if history:
                    text = ""
                    for record in history:
                        text += f"{record.get('timestamp')}\n"
                        text += f"{record.get('text')}\n"
                        text += "-" * 40 + "\n\n"
                    self.copy_history_text_edit.setText(text)
                else:
                    self.copy_history_text_edit.setText(SETTINGS_TEXT[lang]["history_empty"])
            except Exception as e:
                self.copy_history_text_edit.setText(SETTINGS_TEXT[lang]["history_error"])
        else:
            self.copy_history_text_edit.setText(SETTINGS_TEXT[lang]["history_empty"])

    def clear_copy_history(self):
        history_file = "copy_history.json"
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=4)
            self.load_copy_history_embedded()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", "Не удалось очистить историю копирований.")

    def back_from_copy_history(self):
        self.init_ui()
        self.apply_theme()

    def save_and_back(self):
        self.parent.config["autostart"] = self.autostart_checkbox.isChecked()
        self.parent.config["copy_to_clipboard"] = self.copy_checkbox.isChecked()
        self.parent.config["copy_history"] = self.copy_history_checkbox.isChecked()
        self.parent.config["history"] = self.history_checkbox.isChecked()
        self.parent.config["start_minimized"] = self.start_minimized_checkbox.isChecked()
        self.parent.autostart = self.autostart_checkbox.isChecked()
        self.parent.start_minimized = self.start_minimized_checkbox.isChecked()
        self.parent.save_config()
        self.parent.set_autostart(self.autostart_checkbox.isChecked())
        self.init_ui()
        self.parent.show_main_screen()

    def apply_theme(self):
        THEMES_LOCAL = {
            "Темная": {
                "background": "#121212",
                "text_color": "#ffffff",
            },
            "Светлая": {
                "background": "#ffffff",
                "text_color": "#000000",
            }
        }
        theme = THEMES_LOCAL[self.parent.current_theme]
        style = f"""
            QWidget {{
                background-color: {theme['background']};
            }}
            QLabel {{
                color: {theme['text_color']};
                font-size: 16px;
            }}
            QCheckBox {{
                color: {theme['text_color']};
                font-size: 16px;
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
            }}
            QPushButton {{
                background-color: {theme['background']};
                color: {theme['text_color']};
                border: 2px solid #C5B3E9;
                padding: 4px;
                font-size: 16px;
            }}
            QPushButton#saveReturnButton {{
                border: 2px solid #C5B3E9;
            }}
        """
        self.setStyleSheet(style)

        if self.hotkeys_mode:
            if self.parent.current_theme == "Темная":
                self.copy_hotkey_input.setStyleSheet(
                    "background-color: #2a2a2a; color: #ffffff; border: 1px solid #ffffff; padding: 4px;"
                )
                self.translate_hotkey_input.setStyleSheet(
                    "background-color: #2a2a2a; color: #ffffff; border: 1px solid #ffffff; padding: 4px;"
                )
            else:
                self.copy_hotkey_input.setStyleSheet(
                    "background-color: #ffffff; color: #000000; border: 1px solid #000000; padding: 4px;"
                )
                self.translate_hotkey_input.setStyleSheet(
                    "background-color: #ffffff; color: #000000; border: 1px solid #000000; padding: 4px;"
                )
        if hasattr(self, "history_text_edit") and self.history_text_edit is not None:
            try:
                if self.parent.current_theme == "Темная":
                    self.history_text_edit.setStyleSheet("background-color: #121212; color: #ffffff;")
                else:
                    self.history_text_edit.setStyleSheet("background-color: #ffffff; color: #000000;")
            except RuntimeError:
                self.history_text_edit = None
        if hasattr(self, "copy_history_text_edit") and self.copy_history_text_edit is not None:
            try:
                if self.parent.current_theme == "Темная":
                    self.copy_history_text_edit.setStyleSheet("background-color: #121212; color: #ffffff;")
                else:
                    self.copy_history_text_edit.setStyleSheet("background-color: #ffffff; color: #000000;")
            except RuntimeError:
                self.copy_history_text_edit = None

    def update_language(self):
        self.init_ui()
