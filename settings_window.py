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
        "history_view": "View translation history"
    },
    "ru": {
        "autostart": "Запускать вместе с Windows",
        "translation_mode": "Режим перевода текста: {mode}",
        "hotkeys": "Настроить горячие клавиши",
        "save_and_back": "Сохранить и вернуться",
        "copy_to_clipboard": "Копировать в буфер",
        "history": "Сохранять историю переводов",
        "test_ocr": "Проверить OCR",
        "save": "Сохранить",
        "back": "Назад",
        "remove_hotkey": "Нажмите ESC для удаления горячей клавиши",
        "history_view": "Посмотреть историю переводов"
    }
}

TRANSLATION_MODES = {
    "en": ["Area selection", "Full screen selection", "Word selection"],
    "ru": ["Выделение области", "Выделение всего экрана", "Выбор слова"]
}

class ClearableKeySequenceEdit(QKeySequenceEdit):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(event)

def add_to_startup(file_path=""):
    if file_path == "":
        file_path = os.path.realpath(__file__)
    link_path = r'C:\Users\%s\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup' % USER_NAME
    os.symlink(file_path, link_path + "\\clickntranslate.lnk")

def remove_startup():
    link_path = r'C:\Users\%s\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\clickntranslate.lnk' % USER_NAME
    os.remove(link_path)

# Класс HistoryDialog удалён, т.к. история теперь отображается внутри настроек

class SettingsWindow(QWidget):
    def switch_startup(self, state):
        self.parent.config["autostart"] = self.autostart_checkbox.isChecked()
        self.parent.save_config()
        if self.autostart_checkbox.isChecked():
            add_to_startup()
        else:
            remove_startup()

    def auto_save_setting(self, key, value):
        self.parent.config[key] = value
        self.parent.save_config()

    def on_history_checkbox_toggled(self, state):
        self.auto_save_setting("history", state)
        # Кнопка просмотра истории остаётся активной всегда
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
        self.main_layout.addSpacing(1)

        self.copy_checkbox = QCheckBox(SETTINGS_TEXT[lang]["copy_to_clipboard"])
        self.copy_checkbox.setChecked(self.parent.config.get("copy_to_clipboard", False))
        self.copy_checkbox.toggled.connect(lambda state: self.auto_save_setting("copy_to_clipboard", state))
        self.main_layout.addWidget(self.copy_checkbox)
        self.main_layout.addSpacing(1)

        self.history_checkbox = QCheckBox(SETTINGS_TEXT[lang]["history"])
        self.history_checkbox.setChecked(self.parent.config.get("history", False))
        self.history_checkbox.toggled.connect(self.on_history_checkbox_toggled)
        self.main_layout.addWidget(self.history_checkbox)

        self.main_layout.addSpacing(100)

        # --- ГРУППА КНОПОК ---
        self.translation_mode_button = QPushButton(
            SETTINGS_TEXT[lang]["translation_mode"].format(
                mode=self.parent.config.get("translation_mode", TRANSLATION_MODES[lang][0])
            )
        )
        self.translation_mode_button.clicked.connect(self.cycle_translation_mode)
        self.main_layout.addWidget(self.translation_mode_button)

        self.main_layout.addSpacing(1)

        hotkeys_button = QPushButton(SETTINGS_TEXT[lang]["hotkeys"])
        hotkeys_button.clicked.connect(self.show_hotkeys_screen)
        self.main_layout.addWidget(hotkeys_button)

        self.main_layout.addSpacing(1)

        self.history_view_button = QPushButton(SETTINGS_TEXT[lang]["history_view"])
        self.history_view_button.clicked.connect(self.show_history_view)
        # Кнопка просмотра истории всегда будет активна
        self.history_view_button.setEnabled(True)
        self.main_layout.addWidget(self.history_view_button)

        self.main_layout.addSpacing(5)

    def cycle_translation_mode(self):
        lang = self.parent.current_interface_language
        modes = TRANSLATION_MODES[lang]
        current_mode = self.parent.config.get("translation_mode", modes[0])
        try:
            index = modes.index(current_mode)
        except ValueError:
            index = 0
        new_mode = modes[(index + 1) % len(modes)]
        self.parent.config["translation_mode"] = new_mode
        self.parent.save_config()
        self.translation_mode_button.setText(
            SETTINGS_TEXT[lang]["translation_mode"].format(mode=new_mode)
        )

    def show_hotkeys_screen(self):
        self.clear_main_layout()
        self.hotkeys_mode = True
        self.main_layout.setContentsMargins(9, 9, 9, 9)
        self.main_layout.setSpacing(9)

        lang = self.parent.current_interface_language
        label = QLabel(SETTINGS_TEXT[lang]["hotkeys"])
        self.main_layout.addWidget(label)

        self.hotkey_input = ClearableKeySequenceEdit()
        saved_hotkeys = self.parent.config.get("hotkeys", "")
        self.hotkey_input.setKeySequence(QKeySequence(saved_hotkeys))
        self.main_layout.addWidget(self.hotkey_input)
        self.hotkey_input.keySequenceChanged.connect(self.save_hotkeys)

        remove_label = QLabel(SETTINGS_TEXT[lang]["remove_hotkey"])
        self.main_layout.addWidget(remove_label)

        back_button = QPushButton(SETTINGS_TEXT[lang]["back"])
        back_button.clicked.connect(self.back_from_hotkeys)
        self.main_layout.addWidget(back_button)

        self.apply_theme()

    def back_from_hotkeys(self):
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(0)
        self.init_ui()
        self.apply_theme()

    def save_hotkeys(self):
        hotkey_seq = self.hotkey_input.keySequence().toString()
        self.parent.config["hotkeys"] = hotkey_seq
        self.parent.hotkeys = hotkey_seq
        self.parent.save_config()
        self.parent.restart_hotkey_listener()

    def show_history_view(self):
        # Отображаем историю переводов прямо в окне настроек
        self.clear_main_layout()
        lang = self.parent.current_interface_language

        title_label = QLabel("История переводов")
        self.main_layout.addWidget(title_label)

        self.history_text_edit = QTextEdit()
        self.history_text_edit.setReadOnly(True)
        # Устанавливаем стиль для корректного отображения в зависимости от темы
        if self.parent.current_theme == "Темная":
            self.history_text_edit.setStyleSheet("background-color: #121212; color: #ffffff;")
        else:
            self.history_text_edit.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.main_layout.addWidget(self.history_text_edit)
        self.load_history_embedded()

        clear_button = QPushButton("Очистить историю")
        clear_button.clicked.connect(self.clear_history)
        self.main_layout.addWidget(clear_button)

        back_button = QPushButton(SETTINGS_TEXT[lang]["back"])
        back_button.clicked.connect(self.back_from_history)
        self.main_layout.addWidget(back_button)

    def load_history_embedded(self):
        history_file = "translation_history.json"
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                if history:
                    text = ""
                    for record in history:
                        # Форматируем так, чтобы было видно дату, текст и разделитель
                        text += f"{record.get('timestamp')} ({record.get('language')}):\n"
                        text += f"{record.get('text')}\n"
                        text += "-" * 40 + "\n\n"
                    self.history_text_edit.setText(text)
                else:
                    self.history_text_edit.setText("История пуста.")
            except Exception as e:
                self.history_text_edit.setText("Ошибка чтения истории.")
        else:
            self.history_text_edit.setText("История пуста.")

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

    def save_and_back(self):
        self.parent.config["autostart"] = self.autostart_checkbox.isChecked()
        self.parent.config["copy_to_clipboard"] = self.copy_checkbox.isChecked()
        self.parent.config["history"] = self.history_checkbox.isChecked()
        self.parent.save_config()
        self.parent.set_autostart(self.autostart_checkbox.isChecked())
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

        if self.hotkeys_mode and hasattr(self, 'hotkey_input'):
            if self.parent.current_theme == "Темная":
                self.hotkey_input.setStyleSheet(
                    "background-color: #2a2a2a; color: #ffffff; border: 1px solid #ffffff; padding: 4px;"
                )
            else:
                self.hotkey_input.setStyleSheet(
                    "background-color: #ffffff; color: #000000; border: 1px solid #000000; padding: 4px;"
                )
        # Если окно истории открыто, обновляем его стиль
        if hasattr(self, "history_text_edit"):
            if self.parent.current_theme == "Темная":
                self.history_text_edit.setStyleSheet("background-color: #121212; color: #ffffff;")
            else:
                self.history_text_edit.setStyleSheet("background-color: #ffffff; color: #000000;")
