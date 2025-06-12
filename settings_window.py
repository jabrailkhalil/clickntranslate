import getpass
import os
import json
import webbrowser
import requests, zipfile, tempfile, shutil, threading
import sys
import subprocess
import platform
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox, QKeySequenceEdit,
    QMessageBox, QTextEdit, QHBoxLayout, QComboBox, QProgressDialog, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QMetaObject, pyqtSlot
from PyQt5.QtGui import QKeySequence
from PyQt5 import QtCore

USER_NAME = getpass.getuser()
SETTINGS_TEXT = {
    "en": {
        "autostart": "Start with OS",
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
        "history_error": "Error reading history.",
        "copy_translated_text": "Copy translated text automatically"
    },
    "ru": {
        "autostart": "Запускать вместе с ОС",
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
        "history_error": "Ошибка чтения истории.",
        "copy_translated_text": "Копировать сразу переведённый текст"
    }
}

class ClearableKeySequenceEdit(QKeySequenceEdit):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(event)

# Класс HistoryDialog удалён, т.к. история теперь отображается внутри настроек

def get_data_file(filename):
    import sys, os
    def get_app_dir():
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    data_dir = os.path.join(get_app_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, filename)

def ensure_json_file(filepath, default_content):
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_content, f, ensure_ascii=False, indent=4)

def load_settings():
    settings_path = get_data_file("settings.json")
    ensure_json_file(settings_path, {})
    with open(settings_path, "r", encoding="utf-8") as f:
        return json.load(f)

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
        self.previous_ocr_engine = None  # Для отката OCR движка при отмене загрузки
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.init_ui()
        self.apply_theme()

    def clear_main_layout(self):
        # Очищаем все элементы из текущего макета
        if self.main_layout is not None:
            while self.main_layout.count():
                item = self.main_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                elif item.layout():
                    self.clear_nested_layout(item.layout())

    def clear_nested_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                elif item.layout():
                    self.clear_nested_layout(item.layout())

    def setup_new_layout(self):
        # Больше не пересоздаём layout, только очищаем
        self.clear_main_layout()

    def init_ui(self):
        self.setup_new_layout()
        self.hotkeys_mode = False
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(0)
        lang = self.parent.current_interface_language

        # --- ГРУППА ЧЕКБОКСОВ ---
        self.main_layout.addSpacing(5)
        self.main_layout.setSpacing(0)

        # Чекбокс "Запускать вместе с ОС" слева, справа — Движок OCR и ComboBox (жесткое позиционирование)
        top_row = QHBoxLayout()
        self.autostart_checkbox = QCheckBox(SETTINGS_TEXT[lang]["autostart"])
        self.autostart_checkbox.setChecked(self.parent.config.get("autostart", False))
        self.autostart_checkbox.clicked.connect(self.switch_startup)
        margin_top_chk = "-12px" if self.parent.current_theme == "Темная" else "-6px"
        fixed_height = 38
        self.autostart_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:10px; margin-top:{margin_top_chk}; min-width:210px;")
        self.autostart_checkbox.setFixedHeight(fixed_height)
        top_row.addWidget(self.autostart_checkbox, alignment=Qt.AlignLeft)
        # Spacer для выравнивания справа
        top_row.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        # --- OCR controls on the right ---
        ocr_label = QLabel("OCR Engine:" if lang == "en" else "Движок OCR:")
        ocr_label.setStyleSheet("margin-left:0px; margin-right:4px; min-width:90px; text-align:right;")
        self.ocr_engine_combo = QComboBox()
        self.ocr_engine_combo.addItems(["Windows", "Tesseract"])
        current_engine = self.parent.config.get("ocr_engine", "Windows")
        idx = self.ocr_engine_combo.findText(current_engine, Qt.MatchFixedString)
        if idx >= 0:
            self.ocr_engine_combo.setCurrentIndex(idx)
        self.ocr_engine_combo.currentTextChanged.connect(self.handle_ocr_engine_change)
        self.ocr_engine_combo.setStyleSheet("min-width:110px; margin-right:0px;")
        top_row.addWidget(ocr_label, alignment=Qt.AlignRight)
        top_row.addWidget(self.ocr_engine_combo, alignment=Qt.AlignRight)
        self.main_layout.addLayout(top_row)
        # Вертикальный отступ после первой строки (чтобы совпадало с остальными чекбоксами)
        self.main_layout.addSpacing(10)

        # --- Подготовим кнопку сброса (будет на одной строке с чекбоксом "Copy translated") ---
        self.reset_button = QPushButton("Обновление" if lang == 'ru' else "Update")
        self.reset_button.setStyleSheet("background-color: #7A5FA1; color: #fff; border-radius: 6px; padding: 6px 16px; font-size: 14px;")
        self.reset_button.setFixedHeight(self.ocr_engine_combo.sizeHint().height() + 2)
        self.reset_button.clicked.connect(lambda: webbrowser.open('https://t.me/jabrail_digital'))
        self.main_layout.addSpacing(6)

        # --- Checkbox group starts (start_minimized, copy etc.) ---
        # Определяем сдвиг по вертикали для чекбоксов (чтобы не обрезать верхнюю грань в светлой теме)
        margin_top_val = "-12px" if self.parent.current_theme == "Темная" else "-6px"
        # Чекбокс "Запускать в режиме тень" сразу под автозапуском
        checkbox_style = "margin-left:0px; margin-bottom:10px;"
        fixed_height = 38
        self.start_minimized_checkbox = QCheckBox(SETTINGS_TEXT[lang]["start_minimized"])
        self.start_minimized_checkbox.setChecked(self.parent.config.get("start_minimized", False))
        self.start_minimized_checkbox.toggled.connect(lambda state: self.auto_save_setting("start_minimized", state))
        self.start_minimized_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:10px; margin-top:{margin_top_val}; min-width:400px;")
        self.start_minimized_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.start_minimized_checkbox, alignment=Qt.AlignLeft)

        # Остальные чекбоксы
        self.copy_translated_checkbox = QCheckBox(SETTINGS_TEXT[lang]["copy_translated_text"])
        self.copy_translated_checkbox.setChecked(self.parent.config.get("copy_translated_text", False))
        self.copy_translated_checkbox.toggled.connect(lambda state: self.auto_save_setting("copy_translated_text", state))
        self.copy_translated_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:10px; margin-top:{margin_top_val}; min-width:400px;")
        self.copy_translated_checkbox.setFixedHeight(fixed_height)
        # --- Строка: чекбокс «copy translated» слева + кнопка сброса справа ---
        row_copy = QHBoxLayout()
        row_copy.addWidget(self.copy_translated_checkbox, alignment=Qt.AlignLeft)
        row_copy.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        row_copy.addWidget(self.reset_button, alignment=Qt.AlignRight)
        self.main_layout.addLayout(row_copy)

        self.copy_history_checkbox = QCheckBox(SETTINGS_TEXT[lang]["copy_history"])
        self.copy_history_checkbox.setChecked(self.parent.config.get("copy_history", False))
        self.copy_history_checkbox.toggled.connect(lambda state: self.auto_save_setting("copy_history", state))
        self.copy_history_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:10px; margin-top:{margin_top_val}; min-width:400px;")
        self.copy_history_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.copy_history_checkbox, alignment=Qt.AlignLeft)

        self.history_checkbox = QCheckBox(SETTINGS_TEXT[lang]["history"])
        self.history_checkbox.setChecked(self.parent.config.get("history", False))
        self.history_checkbox.toggled.connect(self.on_history_checkbox_toggled)
        self.history_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:10px; margin-top:{margin_top_val}; min-width:400px;")
        self.history_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.history_checkbox, alignment=Qt.AlignLeft)

        # --- конец блока чекбоксов ---
        self.main_layout.addSpacing(14)

        # --- ГРУППА КНОПОК ---
        hotkeys_button = QPushButton(SETTINGS_TEXT[lang]["hotkeys"])
        hotkeys_button.clicked.connect(self.show_hotkeys_screen)
        self.main_layout.addWidget(hotkeys_button)
        self.main_layout.addSpacing(20)
        # --- Две кнопки в одну строку ---
        btn_row = QHBoxLayout()
        history_btn = QPushButton("Показать историю переводов" if lang == 'ru' else "Show translation history")
        history_btn.clicked.connect(self.show_history_view)
        copy_history_btn = QPushButton("Показать историю копирований" if lang == 'ru' else "Show copy history")
        copy_history_btn.clicked.connect(self.show_copy_history_view)
        btn_row.addWidget(history_btn)
        btn_row.addWidget(copy_history_btn)
        self.main_layout.addLayout(btn_row)
        self.main_layout.addSpacing(20)
        # --- Кнопка обновления отдельно внизу ---
        version_label = QLabel("V1.00.0")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #7A5FA1; font-size: 16px; font-weight: bold; margin-bottom: 2px; margin-top: 2px;")
        self.main_layout.addWidget(version_label)
        update_btn = QPushButton("Сброс настроек" if lang == 'ru' else "Reset settings")
        update_btn.setStyleSheet("background-color: #FF6666; color: #fff; border-radius: 8px; padding: 6px 16px; font-size: 14px; min-width: 200px;")
        update_btn.clicked.connect(self.reset_settings)
        self.main_layout.addStretch()
        self.main_layout.addWidget(update_btn, alignment=Qt.AlignBottom)

    def show_hotkeys_screen(self):
        self.setup_new_layout()
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
        history_file = get_data_file("translation_history.json")
        ensure_json_file(history_file, [])
        lang = self.parent.current_interface_language
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

    def clear_history(self):
        history_file = get_data_file("translation_history.json")
        ensure_json_file(history_file, [])
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
        history_file = get_data_file("copy_history.json")
        ensure_json_file(history_file, [])
        lang = self.parent.current_interface_language
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

    def clear_copy_history(self):
        history_file = get_data_file("copy_history.json")
        ensure_json_file(history_file, [])
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
        self.parent.config["copy_translated_text"] = self.copy_translated_checkbox.isChecked()
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

    def handle_ocr_engine_change(self, text):
        import shutil
        if text == "Tesseract":
            # Сохраняем прошлый движок для отката
            self.previous_ocr_engine = self.parent.config.get("ocr_engine", "Windows")
            # Проверяем наличие tesseract (в PATH или в локальной папке)
            tesseract_path = shutil.which("tesseract")
            if not tesseract_path:
                local_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "ocr", "tesseract", "tesseract.exe")
                if not os.path.exists(local_path):
                    # Предлагаем скачать автоматически
                    msg = QMessageBox(self)
                    if self.parent.current_interface_language == "ru":
                        msg.setWindowTitle("Tesseract не найден")
                        msg.setText("Tesseract-OCR не найден. Скачать и установить?")
                    else:
                        msg.setWindowTitle("Tesseract not found")
                        msg.setText("Tesseract-OCR not found. Download and install?")
                    msg.setIcon(QMessageBox.NoIcon)
                    # remove ? context help button from title bar
                    msg.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
                    if self.parent.current_interface_language == "ru":
                        yes_btn = msg.addButton("Да", QMessageBox.YesRole)
                        no_btn = msg.addButton("Нет", QMessageBox.NoRole)
                    else:
                        yes_btn = msg.addButton("Yes", QMessageBox.YesRole)
                        no_btn = msg.addButton("No", QMessageBox.NoRole)

                    # uniform theme styling
                    if self.parent.current_theme == "Темная":
                        msg.setStyleSheet(
                            "QMessageBox { background-color: #121212; color: #ffffff; } "
                            "QLabel { color: #ffffff; font-size: 16px; } "
                            "QPushButton { background-color: #1e1e1e; color: #ffffff; border: 1px solid #550000; padding: 5px; min-width: 80px; } "
                            "QPushButton:hover { background-color: #333333; }")
                    else:
                        msg.setStyleSheet(
                            "QMessageBox { background-color: #ffffff; color: #000000; } "
                            "QLabel { color: #000000; font-size: 16px; } "
                            "QPushButton { background-color: #f0f0f0; color: #000000; border: 1px solid #550000; padding: 5px; min-width: 80px; } "
                            "QPushButton:hover { background-color: #e0e0e0; }")

                    msg.exec_()
                    if msg.clickedButton() == yes_btn:
                        self.start_download_thread()
                        return  # не сохраняем пока не скачаем
                    else:
                        # Ставим первый доступный (Windows)
                        self.ocr_engine_combo.blockSignals(True)
                        self.ocr_engine_combo.setCurrentText("Windows")
                        self.ocr_engine_combo.blockSignals(False)
                        self.save_ocr_engine("Windows")
                        return
        self.save_ocr_engine(text)

    def save_ocr_engine(self, text):
        self.auto_save_setting("ocr_engine", text)

    def start_download_thread(self):
        """Скачать portable-версию Tesseract и две языковые модели (eng, rus)."""
        import tempfile
        # Определяем архитектуру
        machine = platform.machine().lower()
        is_x64 = machine in ("amd64", "x86_64")
        # Основной и резервный portable-zip
        if is_x64:
            portable_urls = [
                "https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.3.20231005/tesseract-ocr-w64-5.3.3.20231005-portable.zip",
                "https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.1.20230401/tesseract-ocr-w64-5.3.1.20230401-portable.zip"
            ]
        else:
            portable_urls = [
                "https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.3.20231005/tesseract-ocr-w32-5.3.3.20231005-portable.zip",
                "https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.1.20230401/tesseract-ocr-w32-5.3.1.20230401-portable.zip"
            ]
        model_urls = {
            "eng": "https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata",
            "rus": "https://github.com/tesseract-ocr/tessdata/raw/main/rus.traineddata",
        }
        total_files = 1 + len(model_urls)  # zip + models
        progress_text = "Downloading Tesseract …" if self.parent.current_interface_language == "en" else "Загрузка Tesseract …"
        self.progress = QProgressDialog(progress_text, "Cancel", 0, 100, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setAutoClose(False)
        # remove ? button
        self.progress.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.progress.show()

        # стилизуем прогресс-бар в соответствии с темой
        if self.parent.current_theme == "Темная":
            self.progress.setStyleSheet(
                "QProgressDialog { background-color: #121212; color: #ffffff; } "
                "QLabel { color: #ffffff; font-size: 16px; } "
                "QPushButton { background-color: #1e1e1e; color: #ffffff; border: 1px solid #550000; padding: 4px 12px; } "
                "QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; color: #ffffff; } "
                "QProgressBar::chunk { background-color: #7A5FA1; width: 20px; }")
        else:
            self.progress.setStyleSheet(
                "QProgressDialog { background-color: #ffffff; color: #000000; } "
                "QLabel { color: #000000; font-size: 16px; } "
                "QPushButton { background-color: #f0f0f0; color: #000000; border: 1px solid #550000; padding: 4px 12px; } "
                "QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; color: #ffffff; } "
                "QProgressBar::chunk { background-color: #7A5FA1; width: 20px; }")

        def worker():
            try:
                app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                temp_dir = os.path.join(app_dir, "temp")
                ocr_dir = os.path.join(app_dir, "ocr")
                tesseract_dir = os.path.join(ocr_dir, "tesseract")
                # очистка прошлых остатков
                for p in (temp_dir, tesseract_dir):
                    if os.path.exists(p):
                        shutil.rmtree(p, ignore_errors=True)
                os.makedirs(temp_dir, exist_ok=True)
                os.makedirs(tesseract_dir, exist_ok=True)
                current_index = 0
                # --- Скачиваем portable zip (с fallback) ---
                zip_temp_path = os.path.join(temp_dir, "tess_portable.zip")
                zip_ok = False
                for url in portable_urls:
                    if self.progress.wasCanceled():
                        raise Exception("cancelled")
                    r = requests.get(url, stream=True, timeout=30)
                    total_len = int(r.headers.get("content-length", 0))
                    downloaded = 0
                    with open(zip_temp_path, "wb") as f:
                        for chunk in r.iter_content(8192):
                            if self.progress.wasCanceled():
                                raise Exception("cancelled")
                            f.write(chunk)
                            downloaded += len(chunk)
                            base_progress = int(downloaded * 100 / total_len) if total_len else 0
                            QtCore.QMetaObject.invokeMethod(self.progress, "setValue", Qt.QueuedConnection, QtCore.Q_ARG(int, int(base_progress / total_files)))
                    # Проверяем, действительно ли это zip
                    if zipfile.is_zipfile(zip_temp_path):
                        zip_ok = True
                        break
                    else:
                        os.unlink(zip_temp_path)
                if not zip_ok:
                    # --- Fallback: EXE-установщик, распаковка через 7z ---
                    if is_x64:
                        exe_url = "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
                    else:
                        exe_url = "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w32-setup-5.3.0.20221222.exe"
                    exe_temp_path = os.path.join(temp_dir, "tess_setup.exe")
                    r = requests.get(exe_url, stream=True, timeout=30)
                    with open(exe_temp_path, "wb") as f:
                        for chunk in r.iter_content(8192):
                            if self.progress.wasCanceled():
                                raise Exception("cancelled")
                            f.write(chunk)
                    try:
                        # Пытаемся запустить интерактивный установщик поверх всех окон
                        self.progress.close()
                        self.parent.hide()
                        try:
                            lang_param = '/LANG=Russian' if self.parent.current_interface_language == 'ru' else '/LANG=English'
                            dir_param = f'/DIR="{tesseract_dir}"'

                            # Показываем диалог с инструкцией и автокопированием пути
                            import pyperclip
                            pyperclip.copy(tesseract_dir)
                            info_box = QMessageBox(self)
                            info_box.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
                            if self.parent.current_theme == "Темная":
                                info_box.setStyleSheet(
                                    "QMessageBox { background-color: #121212; color: #ffffff; } "
                                    "QLabel { color: #ffffff; font-size: 16px; } "
                                    "QPushButton { background-color: #1e1e1e; color: #ffffff; border: 1px solid #550000; padding: 5px 16px; } "
                                    "QPushButton:hover { background-color: #333333; }")
                            else:
                                info_box.setStyleSheet(
                                    "QMessageBox { background-color: #ffffff; color: #000000; } "
                                    "QLabel { color: #000000; font-size: 16px; } "
                                    "QPushButton { background-color: #f0f0f0; color: #000000; border: 1px solid #550000; padding: 5px 16px; } "
                                    "QPushButton:hover { background-color: #e0e0e0; }")

                            if self.parent.current_interface_language == 'ru':
                                info_box.setWindowTitle("Установка Tesseract")
                                info_box.setText(
                                    f"Мастер установки откроется сейчас.\n\nВыберите путь установки:\n<b>{tesseract_dir}</b>\n(путь уже скопирован в буфер обмена)\n\nДобавьте русский язык (rus) в списке языковых моделей и завершите установку.")
                                ok_text = "Продолжить"
                            else:
                                info_box.setWindowTitle("Tesseract setup")
                                info_box.setText(
                                    f"Installer will open now.\n\nChoose install path:\n<b>{tesseract_dir}</b>\n(Path is already copied to clipboard)\n\nMake sure to include Russian (rus) language files then finish setup.")
                                ok_text = "Continue"
                            info_box.addButton(ok_text, QMessageBox.AcceptRole)
                            info_box.setIcon(QMessageBox.NoIcon)
                            info_box.exec_()

                            if sys.platform.startswith('win'):
                                # ждём завершения мастера установки
                                subprocess.run([exe_temp_path, lang_param, dir_param], shell=True)
                            else:
                                subprocess.run([exe_temp_path, dir_param])
                        except Exception:
                            pass

                        # После выхода мастера проверяем, появился ли tesseract.exe
                        tess_exe = None
                        for root, _dirs, files in os.walk(tesseract_dir):
                            for f in files:
                                if f.lower() == "tesseract.exe":
                                    tess_exe = os.path.join(root, f)
                                    break
                            if tess_exe:
                                break

                        if not tess_exe:
                            # ищем системную установку
                            tess_exe = shutil.which("tesseract")
                            if not tess_exe:
                                for p in [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                                          r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                                          os.path.join(os.path.expanduser("~"), "AppData", "Local", "Tesseract-OCR", "tesseract.exe")]:
                                    if os.path.exists(p):
                                        tess_exe = p
                                        break

                        if tess_exe and os.path.exists(tess_exe):
                            QtCore.QMetaObject.invokeMethod(self, "_portable_ready", Qt.QueuedConnection, QtCore.Q_ARG(str, tess_exe))
                        else:
                            QtCore.QMetaObject.invokeMethod(self, "_download_failed", Qt.QueuedConnection, QtCore.Q_ARG(str, "tesseract.exe not found after installer finished"))
                        return
                    except Exception as install_err:
                        QtCore.QMetaObject.invokeMethod(self, "_download_failed", Qt.QueuedConnection, QtCore.Q_ARG(str, f"Installer launch failed: {install_err}"))
                        return
                else:
                    # Распаковываем portable zip
                    with zipfile.ZipFile(zip_temp_path, 'r') as zip_ref:
                        zip_ref.extractall(tesseract_dir)
                    os.unlink(zip_temp_path)
                current_index += 1
                # --- tessdata dir ---
                possible_tessdata = [os.path.join(tesseract_dir, "tessdata"),
                                     os.path.join(tesseract_dir, "share", "tessdata")]
                tessdata_dir = None
                for td in possible_tessdata:
                    if os.path.isdir(td):
                        tessdata_dir = td
                        break
                if tessdata_dir is None:
                    tessdata_dir = os.path.join(tesseract_dir, "tessdata")
                    os.makedirs(tessdata_dir, exist_ok=True)
                # --- Скачиваем языковые модели ---
                for name, url in model_urls.items():
                    if self.progress.wasCanceled():
                        raise Exception("cancelled")
                    model_path = os.path.join(tessdata_dir, f"{name}.traineddata")
                    r = requests.get(url, stream=True, timeout=30)
                    with open(model_path, "wb") as f:
                        for chunk in r.iter_content(8192):
                            if self.progress.wasCanceled():
                                raise Exception("cancelled")
                            f.write(chunk)
                    current_index += 1
                    QtCore.QMetaObject.invokeMethod(
                        self.progress,
                        "setValue",
                        Qt.QueuedConnection,
                        QtCore.Q_ARG(int, int(current_index * 100 / total_files))
                    )
                # Ищем tesseract.exe
                tess_exe = None
                for root, dirs, files in os.walk(tesseract_dir):
                    if "tesseract.exe" in files:
                        tess_exe = os.path.join(root, "tesseract.exe")
                        break
                if not tess_exe:
                    raise Exception("tesseract.exe not found after extraction")
                # успех
                QtCore.QMetaObject.invokeMethod(self, "_portable_ready", Qt.QueuedConnection, QtCore.Q_ARG(str, tess_exe))
            except Exception as e:
                if str(e) == "cancelled":
                    QtCore.QMetaObject.invokeMethod(self, "_handle_download_cancel", Qt.QueuedConnection)
                else:
                    QtCore.QMetaObject.invokeMethod(self, "_download_failed", Qt.QueuedConnection, QtCore.Q_ARG(str, str(e)))
        threading.Thread(target=worker, daemon=True).start()
        
    @QtCore.pyqtSlot(str)
    def _portable_ready(self, tesseract_path):
        self.progress.close()
        from PyQt5.QtWidgets import QMessageBox
        # Проверяем, что файл существует
        if os.path.exists(tesseract_path):
            # Устанавливаем TESSDATA_PREFIX для текущего процесса
            tessdata_dir = os.path.join(os.path.dirname(tesseract_path), "tessdata")
            if os.path.isdir(tessdata_dir):
                os.environ["TESSDATA_PREFIX"] = tessdata_dir
            msg_text = "Tesseract portable installed successfully! You can now use Tesseract OCR." if self.parent.current_interface_language == "en" else "Tesseract portable успешно установлен! Теперь можно использовать Tesseract OCR."
            QMessageBox.information(self, "Success" if self.parent.current_interface_language == "en" else "Успех", msg_text)
            # Сохраняем выбор Tesseract
            self.save_ocr_engine("Tesseract")

            # Разворачиваем/показываем главное окно
            try:
                self.parent.show()  # на случай, если было скрыто
                self.parent.raise_()
                self.parent.activateWindow()
            except Exception:
                pass

            # Обновляем главную метку OCR, если пользователь не в настройках
            try:
                if not (hasattr(self.parent, "settings_window") and self.parent.settings_window is not None):
                    self.parent.show_main_screen()
            except Exception:
                pass
        else:
            QMessageBox.warning(self, "Error", "Failed to setup Tesseract")
            # Возвращаем на Windows OCR
            self.ocr_engine_combo.blockSignals(True)
            self.ocr_engine_combo.setCurrentText("Windows")
            self.ocr_engine_combo.blockSignals(False)
            self.save_ocr_engine("Windows")

    @pyqtSlot(str)
    def _download_failed(self, error):
        self.progress.close()
        # Если ошибка связана с правами доступа, показываем подробную инструкцию
        if 'Permission denied' in error or 'permission denied' in error.lower():
            msg_text = (
                "Не удалось установить Tesseract из-за ошибки доступа к файлам.\n\n"
                "Возможные причины и решения:\n"
                "- Запустите программу от имени администратора.\n"
                "- Убедитесь, что папки 'ocr/tesseract' и 'temp' не заняты другими процессами.\n"
                "- Удалите вручную папки 'ocr/tesseract' и 'temp', если они остались после неудачной попытки.\n"
                "- Проверьте, не блокирует ли антивирус создание файлов.\n"
            ) if self.parent.current_interface_language == 'ru' else (
                "Failed to install Tesseract due to file access error.\n\n"
                "Possible reasons and solutions:\n"
                "- Run the program as administrator.\n"
                "- Make sure the 'ocr/tesseract' and 'temp' folders are not used by other processes.\n"
                "- Delete the 'ocr/tesseract' and 'temp' folders manually if they remain after a failed attempt.\n"
                "- Check if your antivirus is blocking file creation.\n"
            )
            QMessageBox.warning(self, "Ошибка доступа" if self.parent.current_interface_language == 'ru' else "Permission Error", msg_text)
        else:
            QMessageBox.warning(self, "Error", f"Failed to install Tesseract: {error}")
        # revert selection
        self.ocr_engine_combo.blockSignals(True)
        self.ocr_engine_combo.setCurrentText("Windows")
        self.ocr_engine_combo.blockSignals(False)
        self.save_ocr_engine("Windows")

    @QtCore.pyqtSlot()
    def _show_manual_install_info(self):
        self.progress.close()
        from PyQt5.QtWidgets import QMessageBox
        
        msg_title = "Manual Installation Required" if self.parent.current_interface_language == "en" else "Требуется ручная установка"
        msg_text = """Automatic Tesseract installation failed due to Windows compatibility issues.
        
Please install Tesseract manually:
1. Download: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location
3. Restart the program and select Tesseract again

The program will continue using Windows OCR for now.""" if self.parent.current_interface_language == "en" else """Автоматическая установка Tesseract не удалась из-за проблем совместимости с Windows.

Пожалуйста, установите Tesseract вручную:
1. Скачайте: https://github.com/UB-Mannheim/tesseract/wiki
2. Установите в стандартную папку
3. Перезапустите программу и выберите Tesseract снова

Пока программа будет использовать Windows OCR."""
        
        msg = QMessageBox(self)
        msg.setWindowTitle(msg_title)
        msg.setText(msg_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec_()
        
        # Возвращаем на Windows OCR
        self.ocr_engine_combo.blockSignals(True)
        self.ocr_engine_combo.setCurrentText("Windows")
        self.ocr_engine_combo.blockSignals(False)
        self.save_ocr_engine("Windows")

    @QtCore.pyqtSlot()
    def _handle_download_cancel(self):
        self.progress.close()
        # Удаляем временные папки
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        temp_dir = os.path.join(app_dir, "temp")
        tesseract_dir = os.path.join(app_dir, "ocr", "tesseract")
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception:
            pass
        try:
            if os.path.exists(tesseract_dir):
                shutil.rmtree(tesseract_dir)
        except Exception:
            pass
        # Возвращаем прошлый движок
        prev_engine = self.previous_ocr_engine or "Windows"
        self.ocr_engine_combo.blockSignals(True)
        self.ocr_engine_combo.setCurrentText(prev_engine)
        self.ocr_engine_combo.blockSignals(False)
        self.save_ocr_engine(prev_engine)
        from PyQt5.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Отмена" if self.parent.current_interface_language == "ru" else "Cancelled")
        msg.setText("Загрузка Tesseract отменена. Возвращён прошлый движок OCR." if self.parent.current_interface_language == "ru" else "Tesseract download cancelled. Previous OCR engine restored.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

    def reset_settings(self):
        """Reset all program settings to default values (white theme, English, etc.)."""
        lang = self.parent.current_interface_language
        title = "Сброс" if lang == 'ru' else "Reset"
        question = "Вы уверены, что хотите сбросить все настройки?" if lang == 'ru' else "Are you sure you want to reset all settings?"
        reply = QMessageBox.question(self, title, question, QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        # Default configuration
        default_config = {
            "theme": "Светлая",
            "interface_language": "en",
            "ocr_language": "en",
            "autostart": False,
            "translation_mode": "English",
            "ocr_hotkeys": "Ctrl+O",
            "copy_hotkey": "Ctrl+K",
            "translate_hotkey": "Ctrl+F",
            "notifications": False,
            "history": False,
            "start_minimized": False,
            "show_update_info": True,
            "ocr_engine": "Windows",
            "copy_translated_text": False,
            "copy_history": False
        }
        # Save to disk
        config_path = get_data_file("config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            QMessageBox.warning(self, title, str(e))
            return
        # Update parent state
        self.parent.config = default_config
        self.parent.current_theme = default_config["theme"]
        self.parent.current_interface_language = default_config["interface_language"]
        self.parent.autostart = default_config["autostart"]
        self.parent.translation_mode = default_config["translation_mode"]
        self.parent.start_minimized = default_config["start_minimized"]
        # Сохраняем конфиг
        self.parent.save_config()

        # Перестроить интерфейс под новую тему и сброшенные настройки до показа диалогов
        self.init_ui()
        self.parent.apply_theme()
        self.apply_theme()

        # Предложить очистить истории
        msg_clear = QMessageBox(self)
        if lang == 'ru':
            msg_clear.setWindowTitle('Очистить истории?')
            msg_clear.setText('Очистить историю переводов и историю копирований?')
            yes_text, no_text = 'Да', 'Нет'
        else:
            msg_clear.setWindowTitle('Clear histories?')
            msg_clear.setText('Clear translation history and copy history?')
            yes_text, no_text = 'Yes', 'No'
        yes_btn = msg_clear.addButton(yes_text, QMessageBox.YesRole)
        no_btn = msg_clear.addButton(no_text, QMessageBox.NoRole)
        msg_clear.setIcon(QMessageBox.Question)
        msg_clear.exec_()
        if msg_clear.clickedButton() == yes_btn:
            for fname in ("translation_history.json", "copy_history.json"):
                try:
                    path = get_data_file(fname)
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump([], f)
                except Exception:
                    pass

        done_text = "Настройки сброшены" if lang == 'ru' else "Settings were reset"
        QMessageBox.information(self, title, done_text)
