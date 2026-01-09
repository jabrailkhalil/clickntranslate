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
from PyQt5.QtGui import QKeySequence, QIcon
from PyQt5 import QtCore

# Импортируем функцию инвалидации кэша (ленивый импорт для избежания циклического импорта)
def _invalidate_main_config_cache():
    try:
        from main import invalidate_config_cache
        invalidate_config_cache()
    except ImportError:
        pass

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

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


class SettingsWindow(QWidget):
    def switch_startup(self, state):
        self.parent.config["autostart"] = self.autostart_checkbox.isChecked()
        self.parent.save_config()
        _invalidate_main_config_cache()  # Сбрасываем кэш после сохранения
        self.parent.set_autostart(self.autostart_checkbox.isChecked())
        self.parent.autostart = self.autostart_checkbox.isChecked()

    def auto_save_setting(self, key, value):
        self.parent.config[key] = value
        if key == "start_minimized":
            self.parent.start_minimized = value
        if key == "autostart":
            self.parent.autostart = value
        self.parent.save_config()
        _invalidate_main_config_cache()  # Сбрасываем кэш после сохранения

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
        self.main_layout.setSpacing(8)
        lang = self.parent.current_interface_language

        # --- ГРУППА ЧЕКБОКСОВ ---
        self.main_layout.addSpacing(5)

        margin_top_val = "-12px" if self.parent.current_theme == "Темная" else "-6px"
        fixed_height = 38
        
        # --- СТРОКА 1: Запускать вместе с ОС + Движок OCR ---
        # --- СТРОКА 1: Запускать вместе с ОС + Движок OCR ---
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(8)
        self.autostart_checkbox = QCheckBox(SETTINGS_TEXT[lang]["autostart"])
        self.autostart_checkbox.setChecked(self.parent.config.get("autostart", False))
        self.autostart_checkbox.clicked.connect(self.switch_startup)
        self.autostart_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:300px;")
        self.autostart_checkbox.setFixedHeight(fixed_height)
        row1.addWidget(self.autostart_checkbox, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        row1.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # [ИНСТРУКЦИЯ ПО ВЫРАВНИВАНИЮ]
        # Для того чтобы текст "OCR:" и "Перевод:" стоял ровно с текстом в выпадающих списках (флагах):
        # 1. Используем setFixedHeight(38) - высота всей строки.
        # 2. Используем Qt.AlignTop - прижимаем к верху, чтобы убрать непредсказуемое авто-центрирование.
        # 3. Ставим padding-top: 2px - эмпирически подобранный отступ, который выравнивает базовые линии шрифтов.
        # Любое изменение (AlignVCenter, padding > 4px) приведет к тому, что текст "уплывет" или обрежутся выносные элементы букв (р, д, ц).
        
        # OCR блок
        ocr_label = QLabel("OCR:")
        ocr_label.setStyleSheet("margin:0; padding:0; padding-top: 2px;") 
        ocr_label.setFixedWidth(90)
        ocr_label.setFixedHeight(38)
        ocr_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        
        self.ocr_engine_combo = QComboBox()
        # Два OCR движка: Windows и Tesseract
        self.ocr_engine_combo.addItems(["Windows", "Tesseract"])
        current_engine = self.parent.config.get("ocr_engine", "Windows")
        idx = self.ocr_engine_combo.findText(current_engine, Qt.MatchFixedString)
        if idx >= 0:
            self.ocr_engine_combo.setCurrentIndex(idx)
        else:
             self.ocr_engine_combo.setCurrentIndex(0)

        self.ocr_engine_combo.currentTextChanged.connect(self.handle_ocr_engine_change)
        self.ocr_engine_combo.setStyleSheet("margin-left:6px;")
        self.ocr_engine_combo.setFixedWidth(130)
        self.ocr_engine_combo.setFixedHeight(32)
        
        # Выравниваем: лейбл занимает всю высоту (38), комбобокс (32) выравнивается по центру высоты строки
        row1.addWidget(ocr_label) # Alignment внутри виджета
        row1.addWidget(self.ocr_engine_combo, alignment=Qt.AlignVCenter)
        
        # Подсказки для OCR движков
        ocr_tooltips = {
            "ru": "Windows — быстрый, встроенный, без интернета\nTesseract — точный, офлайн, поддержка многих языков",
            "en": "Windows — fast, built-in, no internet\nTesseract — accurate, offline, many languages"
        }
        self.ocr_engine_combo.setToolTip(ocr_tooltips.get(lang, ocr_tooltips["en"]))
        ocr_label.setToolTip(ocr_tooltips.get(lang, ocr_tooltips["en"]))
        self.main_layout.addLayout(row1)
        
        # --- СТРОКА 2: Запускать в режиме тень + Переводчик ---
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(8)
        self.start_minimized_checkbox = QCheckBox(SETTINGS_TEXT[lang]["start_minimized"])
        self.start_minimized_checkbox.setChecked(self.parent.config.get("start_minimized", False))
        self.start_minimized_checkbox.toggled.connect(lambda state: self.auto_save_setting("start_minimized", state))
        self.start_minimized_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:300px;")
        self.start_minimized_checkbox.setFixedHeight(fixed_height)
        row2.addWidget(self.start_minimized_checkbox, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        row2.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # Переводчик блок
        # [ИНСТРУКЦИЯ] См. выше про выравнивание (AlignTop + padding 2px)
        tr_label = QLabel("Перевод:" if lang == "ru" else "Translate:")
        tr_label.setStyleSheet("margin:0; padding:0; padding-top: 2px;")
        tr_label.setFixedWidth(90)
        tr_label.setFixedHeight(38)
        tr_label.setAlignment(Qt.AlignRight | Qt.AlignTop)

        self.translator_combo = QComboBox()
        # Порядок: Google первый
        self.translator_combo.addItems(["Google", "Argos", "MyMemory", "Lingva", "LibreTranslate"])
        # Маппинг индексов на имена движков (соответствует порядку в addItems)
        self._translator_engines = ["google", "argos", "mymemory", "lingva", "libretranslate"]
        
        current_tr = self.parent.config.get("translator_engine", "Google").lower()
        try:
            idx = self._translator_engines.index(current_tr)
        except ValueError:
            idx = 0 # Google по умолчанию
        self.translator_combo.setCurrentIndex(idx)
        self.translator_combo.currentIndexChanged.connect(self._on_translator_changed)
        self.translator_combo.setStyleSheet("margin-left:6px;")
        self.translator_combo.setFixedWidth(130)
        self.translator_combo.setFixedHeight(32)
        
        # Выравниваем
        row2.addWidget(tr_label) # Alignment внутри виджета
        row2.addWidget(self.translator_combo, alignment=Qt.AlignVCenter)
        
        # Подсказки для переводчиков
        tr_tooltips = {
            "ru": "Google — быстрый, точный, нужен интернет\nArgos — офлайн, без интернета, приватный\nMyMemory — бесплатный API, лимит 5000 симв/день\nLingva — прокси Google, более стабильный\nLibreTranslate — открытый, бесплатный",
            "en": "Google — fast, accurate, needs internet\nArgos — offline, no internet, private\nMyMemory — free API, 5000 chars/day limit\nLingva — Google proxy, more stable\nLibreTranslate — open source, free"
        }
        self.translator_combo.setToolTip(tr_tooltips.get(lang, tr_tooltips["en"]))
        tr_label.setToolTip(tr_tooltips.get(lang, tr_tooltips["en"]))
        self.main_layout.addLayout(row2)

        # --- Подготовим кнопку обновления (перенесена в группу кнопок ниже) ---
        # Убрали из этой строки

        # --- Остальные чекбоксы (start_minimized уже добавлен выше) ---

        # Остальные чекбоксы
        self.copy_translated_checkbox = QCheckBox(SETTINGS_TEXT[lang]["copy_translated_text"])
        self.copy_translated_checkbox.setChecked(self.parent.config.get("copy_translated_text", False))
        self.copy_translated_checkbox.toggled.connect(lambda state: self.auto_save_setting("copy_translated_text", state))
        self.copy_translated_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:400px;")
        self.copy_translated_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.copy_translated_checkbox, alignment=Qt.AlignLeft)

        self.copy_history_checkbox = QCheckBox(SETTINGS_TEXT[lang]["copy_history"])
        self.copy_history_checkbox.setChecked(self.parent.config.get("copy_history", False))
        self.copy_history_checkbox.toggled.connect(lambda state: self.auto_save_setting("copy_history", state))
        self.copy_history_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:400px;")
        self.copy_history_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.copy_history_checkbox, alignment=Qt.AlignLeft)

        self.history_checkbox = QCheckBox(SETTINGS_TEXT[lang]["history"])
        self.history_checkbox.setChecked(self.parent.config.get("history", False))
        self.history_checkbox.toggled.connect(self.on_history_checkbox_toggled)
        self.history_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:400px;")
        self.history_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.history_checkbox, alignment=Qt.AlignLeft)

        # Чекбокс "Не сворачивать при OCR"
        self.keep_visible_checkbox = QCheckBox("Не сворачивать при OCR" if lang == 'ru' else "Keep window visible during OCR")
        self.keep_visible_checkbox.setChecked(self.parent.config.get("keep_visible_on_ocr", False))
        self.keep_visible_checkbox.toggled.connect(lambda state: self.auto_save_setting("keep_visible_on_ocr", state))
        self.keep_visible_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:400px;")
        self.keep_visible_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.keep_visible_checkbox, alignment=Qt.AlignLeft)

        # Чекбокс "Не затемнять экран при OCR"
        self.no_dimming_checkbox = QCheckBox("Не затемнять экран при OCR" if lang == 'ru' else "No screen dimming during OCR")
        self.no_dimming_checkbox.setChecked(self.parent.config.get("no_screen_dimming", False))
        self.no_dimming_checkbox.toggled.connect(lambda state: self.auto_save_setting("no_screen_dimming", state))
        self.no_dimming_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:400px;")
        self.no_dimming_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.no_dimming_checkbox, alignment=Qt.AlignLeft)

        # --- конец блока чекбоксов ---
        self.main_layout.addSpacing(12)

        # --- Группа кнопок: Clear cache | Reset | Update (горизонтальная, связанные стили) ---
        btn_group_layout = QHBoxLayout()
        btn_group_layout.setContentsMargins(0, 0, 0, 0)
        btn_group_layout.setSpacing(0)  # Без зазора между кнопками
        
        # Левая кнопка - закругление слева (фиолетовая)
        self.clear_cache_btn = QPushButton("Очистить кэш" if lang == 'ru' else "Clear cache")
        self.clear_cache_btn.setStyleSheet("""
            QPushButton {
                background-color: #7A5FA1; 
                color: #fff; 
                border: none;
                border-top-left-radius: 8px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                padding-top: 0px;
                padding-bottom: 6px;
                padding-left: 12px;
                padding-right: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #8B70B2; }
        """)
        self.clear_cache_btn.setFixedHeight(38)
        self.clear_cache_btn.clicked.connect(self.clear_all_cache)
        btn_group_layout.addWidget(self.clear_cache_btn)
        
        # Средняя кнопка - без закругления (красная - сброс)
        reset_btn = QPushButton("Сброс" if lang == 'ru' else "Reset")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #D44444; 
                color: #fff; 
                border: none;
                border-radius: 0px;
                border-left: 1px solid rgba(255,255,255,0.15);
                border-right: 1px solid rgba(255,255,255,0.15);
                padding-top: 0px;
                padding-bottom: 6px;
                padding-left: 12px;
                padding-right: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #E55555; }
        """)
        reset_btn.setFixedHeight(38)
        reset_btn.clicked.connect(self.reset_settings)
        btn_group_layout.addWidget(reset_btn)
        
        # Правая кнопка - закругление справа (фиолетовая - обновление)
        update_btn = QPushButton("Обновление" if lang == 'ru' else "Update")
        update_btn.setStyleSheet("""
            QPushButton {
                background-color: #7A5FA1; 
                color: #fff; 
                border: none;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 0px;
                padding-top: 0px;
                padding-bottom: 6px;
                padding-left: 12px;
                padding-right: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #8B70B2; }
        """)
        update_btn.setFixedHeight(38)
        update_btn.clicked.connect(lambda: webbrowser.open('https://github.com/jabrailkhalil/clickntranslate/releases/'))
        btn_group_layout.addWidget(update_btn)
        
        self.main_layout.addLayout(btn_group_layout)
        # Убрали spacing 10, чтобы кнопки слиплись
        self.main_layout.addSpacing(0)

        # --- ГРУППА КНОПОК (расширенные для полного текста) ---
        hotkeys_button = QPushButton(SETTINGS_TEXT[lang]["hotkeys"])
        hotkeys_button.clicked.connect(self.show_hotkeys_screen)
        # Hotkeys: текст еще выше
        hotkeys_button.setStyleSheet("""
            padding-top: 2px;
            padding-bottom: 12px;
            padding-left: 16px;
            padding-right: 16px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 0px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        """)
        hotkeys_button.setMinimumWidth(320)
        hotkeys_button.setMinimumHeight(40)
        hotkeys_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.main_layout.addWidget(hotkeys_button)
        self.main_layout.addSpacing(0)
        
        # --- Две кнопки истории объединены (без зазора) ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(0)  # Без зазора
        btn_row.setContentsMargins(0, 0, 0, 0)
        
        history_btn = QPushButton("История переводов" if lang == 'ru' else "Translation history")
        history_btn.clicked.connect(self.show_history_view)
        # History (левая): Верх прямой, низ-лево круглый
        history_btn.setStyleSheet("""
            QPushButton {
                padding: 2px 12px; 
                font-size: 16px;
                font-weight: bold;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 8px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        history_btn.setMinimumHeight(38)
        history_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        copy_history_btn = QPushButton("История копирований" if lang == 'ru' else "Copy history")
        copy_history_btn.clicked.connect(self.show_copy_history_view)
        # Copy History (правая): Верх прямой, низ-право круглый
        copy_history_btn.setStyleSheet("""
            QPushButton {
                padding: 2px 12px; 
                font-size: 16px;
                font-weight: bold;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 8px;
                border-left: 1px solid rgba(255,255,255,0.1);
            }
        """)
        copy_history_btn.setMinimumHeight(38)
        copy_history_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        btn_row.addWidget(history_btn)
        btn_row.addWidget(copy_history_btn)
        self.main_layout.addLayout(btn_row)
        self.main_layout.addSpacing(10)
        
        # --- Версия программы ---
        version_label = QLabel("V1.2.2")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #7A5FA1; font-size: 16px; font-weight: bold; margin-bottom: 2px; margin-top: 2px;")
        self.main_layout.addWidget(version_label)
        self.main_layout.addStretch()

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
            # Правильно останавливаем старый поток
            try:
                self.parent.copy_hotkey_thread.stop()
                # Даём потоку время на завершение
                self.parent.copy_hotkey_thread.join(timeout=0.5)
            except Exception as e:
                print(f"Error stopping copy hotkey thread: {e}")
            self.parent.copy_hotkey_thread = None
        if hotkey_str:
            self.parent.copy_hotkey_thread = self.parent.HotkeyListenerThread(hotkey_str, self.parent.launch_copy, hotkey_id=2)
            self.parent.copy_hotkey_thread.start()

    def save_translate_hotkey(self):
        hotkey_str = self.translate_hotkey_input.keySequence().toString()
        self.parent.config["translate_hotkey"] = hotkey_str
        self.parent.save_config()
        # Перезапуск слушателя горячих клавиш для перевода
        if hasattr(self.parent, "translate_hotkey_thread") and self.parent.translate_hotkey_thread is not None:
            # Правильно останавливаем старый поток
            try:
                self.parent.translate_hotkey_thread.stop()
                # Даём потоку время на завершение
                self.parent.translate_hotkey_thread.join(timeout=0.5)
            except Exception as e:
                print(f"Error stopping translate hotkey thread: {e}")
            self.parent.translate_hotkey_thread = None
        if hotkey_str:
            self.parent.translate_hotkey_thread = self.parent.HotkeyListenerThread(hotkey_str, self.parent.launch_translate, hotkey_id=3)
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
                for record in reversed(history):  # Новые сверху
                    # Форматируем дату красиво
                    try:
                        from datetime import datetime
                        ts = record.get('timestamp', '')
                        dt = datetime.fromisoformat(ts)
                        date_str = dt.strftime("%d.%m.%Y %H:%M")
                    except:
                        date_str = record.get('timestamp', '')
                    
                    lang_code = record.get('language', '').upper()
                    text += f"📅 {date_str}  •  {lang_code}\n"
                    
                    # Поддержка и старого формата (text), и нового (original + translated)
                    if 'original' in record and 'translated' in record:
                        text += f"📝 {record.get('original')}\n"
                        text += f"🌐 {record.get('translated')}\n"
                    else:
                        # Старый формат
                        text += f"📝 {record.get('text')}\n"
                    text += "━" * 35 + "\n\n"
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
                for record in reversed(history):  # Новые сверху
                    # Форматируем дату красиво
                    try:
                        from datetime import datetime
                        ts = record.get('timestamp', '')
                        dt = datetime.fromisoformat(ts)
                        date_str = dt.strftime("%d.%m.%Y %H:%M")
                    except:
                        date_str = record.get('timestamp', '')
                    
                    text += f"📅 {date_str}\n"
                    text += f"📋 {record.get('text')}\n"
                    text += "━" * 35 + "\n\n"
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
                padding: 6px 4px;
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
                    msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
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

    def _on_translator_changed(self, idx):
        # Сохраняем имя движка из списка
        if hasattr(self, '_translator_engines') and 0 <= idx < len(self._translator_engines):
            value = self._translator_engines[idx]
        else:
            value = "argos"
        self.auto_save_setting("translator_engine", value)

    def start_download_thread(self):
        """Скачать portable-версию Tesseract и две языковые модели (eng, rus)."""
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
            im = QMessageBox(self)
            im.setWindowTitle("Success" if self.parent.current_interface_language == "en" else "Успех")
            im.setText(msg_text)
            im.setIcon(QMessageBox.Information)
            im.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            im.exec_()
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
            warn = QMessageBox(self)
            warn.setWindowTitle("Error")
            warn.setText("Failed to setup Tesseract")
            warn.setIcon(QMessageBox.Warning)
            warn.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            warn.exec_()
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
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Ошибка доступа" if self.parent.current_interface_language == 'ru' else "Permission Error")
            msg_box.setText(msg_text)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            msg_box.exec_()
        else:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"Failed to install Tesseract: {error}")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            msg_box.exec_()
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
        msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
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
        msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        msg.exec_()

    def clear_all_cache(self):
        """Очистить все кэши приложения для освобождения памяти и ускорения."""
        from PyQt5.QtCore import QTimer
        from PyQt5.QtWidgets import QApplication
        
        lang = self.parent.current_interface_language
        original_text = "Очистить кэш" if lang == 'ru' else "Clear cache"
        clearing_text = "Выполняется..." if lang == 'ru' else "Clearing..."
        
        # Показываем "Выполняется..."
        if hasattr(self, 'clear_cache_btn'):
            self.clear_cache_btn.setText(clearing_text)
            self.clear_cache_btn.setEnabled(False)
            QApplication.processEvents()
        
        total_cleared = 0  # Объём очищенного кэша в байтах
        
        # 1. Очистка кэша конфигурации main.py
        try:
            from main import invalidate_config_cache
            invalidate_config_cache()
            total_cleared += 1024  # Примерный размер кэша конфига
        except Exception:
            pass
        
        # 2. Очистка кэша OCR движков
        try:
            from ocr import _OCR_ENGINE_CACHE, _OVERLAY_POOL
            total_cleared += len(_OCR_ENGINE_CACHE) * 50000  # ~50KB на движок
            _OCR_ENGINE_CACHE.clear()
            for k in _OVERLAY_POOL:
                if _OVERLAY_POOL[k] is not None:
                    total_cleared += 10000
                _OVERLAY_POOL[k] = None
        except Exception:
            pass
        
        # 3. Очистка кэша OCR конфигурации
        try:
            import ocr
            if ocr._ocr_config_cache is not None:
                total_cleared += 2048
            ocr._ocr_config_cache = None
            ocr._ocr_config_mtime = 0
        except Exception:
            pass
        
        # 4. Очистка кэша переводчика
        try:
            import translater
            if translater._translator_config_cache is not None:
                total_cleared += 2048
            translater._translator_config_cache = None
            translater._translator_config_mtime = 0
            translater._argos_languages_cache = None
            cache_size = len(translater._argos_translations_cache)
            total_cleared += cache_size * 5000  # ~5KB на перевод
            translater._argos_translations_cache.clear()
            # Очистка HTTP сессии
            if translater._http_session is not None:
                try:
                    translater._http_session.close()
                except Exception:
                    pass
                translater._http_session = None
                total_cleared += 10000
        except Exception:
            pass
        
        # 5. Очистка временных файлов
        try:
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "temp")
            if os.path.exists(temp_dir):
                # Подсчитываем размер перед удалением
                for root, dirs, files in os.walk(temp_dir):
                    for f in files:
                        try:
                            total_cleared += os.path.getsize(os.path.join(root, f))
                        except:
                            pass
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        
        # Форматируем размер
        def format_size(size_bytes):
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
        
        size_str = format_size(total_cleared)
        done_text = f"Очищено {size_str}" if lang == 'ru' else f"Cleared {size_str}"
        
        # Показываем результат и возвращаем текст через 2 сек
        if hasattr(self, 'clear_cache_btn'):
            self.clear_cache_btn.setText(done_text)
            # Зеленый фон, но форма сохраняется (закругление только слева)
            self.clear_cache_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50; 
                    color: #fff; 
                    border: none;
                    border-top-left-radius: 8px;
                    border-bottom-left-radius: 0px;
                    border-top-right-radius: 0px;
                    border-bottom-right-radius: 0px;
                    padding-top: 0px;
                    padding-bottom: 6px;
                    padding-left: 12px;
                    padding-right: 12px;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
            
            def restore_button():
                try:
                    self.clear_cache_btn.setText(original_text)
                    # Восстанавливаем оригинальный фиолетовый стиль
                    self.clear_cache_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #7A5FA1; 
                            color: #fff; 
                            border: none;
                            border-top-left-radius: 8px;
                            border-bottom-left-radius: 0px;
                            border-top-right-radius: 0px;
                            border-bottom-right-radius: 0px;
                            padding-top: 0px;
                            padding-bottom: 6px;
                            padding-left: 12px;
                            padding-right: 12px;
                            font-size: 16px;
                            font-weight: bold;
                        }
                        QPushButton:hover { background-color: #8B70B2; }
                    """)
                    self.clear_cache_btn.setEnabled(True)
                except Exception:
                    pass
            
            QTimer.singleShot(2000, restore_button)


    def reset_settings(self):
        """Reset all program settings to default values (white theme, English, etc.)."""
        lang = self.parent.current_interface_language
        title = "Сброс" if lang == 'ru' else "Reset"
        question = "Вы уверены, что хотите сбросить все настройки?" if lang == 'ru' else "Are you sure you want to reset all settings?"
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(question)
        box.setIcon(QMessageBox.Question)
        box.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        yes_btn = box.addButton("Да" if lang == 'ru' else "Yes", QMessageBox.YesRole)
        no_btn = box.addButton("Нет" if lang == 'ru' else "No", QMessageBox.NoRole)
        box.exec_()
        reply = QMessageBox.Yes if box.clickedButton() == yes_btn else QMessageBox.No
        if reply != QMessageBox.Yes:
            return
        # Default configuration
        default_config = {
            "theme": "Темная",
            "interface_language": "en",
            "ocr_language": "ru",
            "autostart": False,
            "translation_mode": "English",
            "ocr_hotkeys": "Ctrl+O",
            "copy_hotkey": "Ctrl+Alt+C",
            "translate_hotkey": "Ctrl+Alt+T",
            "notifications": False,
            "history": False,
            "start_minimized": False,
            "show_update_info": False,
            "ocr_engine": "Windows",
            "copy_translated_text": False,
            "copy_history": False,
            "translator_engine": "Google",
            "keep_visible_on_ocr": False,
            "last_ocr_language": "ru",
            "no_screen_dimming": False
        }
        # Save to disk
        config_path = get_data_file("config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            w = QMessageBox(self)
            w.setWindowTitle(title)
            w.setText(str(e))
            w.setIcon(QMessageBox.Warning)
            w.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            w.exec_()
            return
        # Update parent state
        self.parent.config = default_config
        self.parent.current_theme = default_config["theme"]
        self.parent.current_interface_language = default_config["interface_language"]
        self.parent.autostart = default_config["autostart"]
        self.parent.translation_mode = default_config["translation_mode"]
        self.parent.start_minimized = default_config["start_minimized"]
        # Удаляем ярлык автозапуска (autostart = False)
        self.parent.set_autostart(False)
        # Сохраняем конфиг
        self.parent.save_config()
        _invalidate_main_config_cache()  # Сбрасываем кэш после сохранения

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
        msg_clear.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
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
        info = QMessageBox(self)
        info.setWindowTitle(title)
        info.setText(done_text)
        info.setIcon(QMessageBox.Information)
        info.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        info.exec_()
