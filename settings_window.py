import getpass
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox, QKeySequenceEdit
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
        "notifications": "Show notifications",
        "history": "Save translation history",
        "test_ocr": "Test OCR Translation",
        "save": "Save",
        "back": "Back",
        "remove_hotkey": "Press ESC to remove hotkey"
    },
    "ru": {
        "autostart": "Запускать вместе с Windows",
        "translation_mode": "Режим перевода текста: {mode}",
        "hotkeys": "Настроить горячие клавиши",
        "save_and_back": "Сохранить и вернуться",
        "notifications": "Показывать уведомления",
        "history": "Сохранять историю переводов",
        "test_ocr": "Проверить OCR",
        "save": "Сохранить",
        "back": "Назад",
        "remove_hotkey": "Нажмите ESC для удаления горячей клавиши"
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




class SettingsWindow(QWidget):
    def switch_startup(self, int):
        if self.autostart_checkbox.isChecked():
            add_to_startup()
        else:
            remove_startup()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.hotkeys_mode = False
        self.create_layout()
        self.init_ui()
        self.apply_theme()

    def create_layout(self):
        self.main_layout = QVBoxLayout()
        # Отступы по бокам — по 5 пикселей
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        # Убираем автоматический spacing, чтобы контролировать отступы вручную
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
        lang = self.parent.current_interface_language

        #
        # -- ГРУППА ЧЕКБОКСОВ (ФЛАГИ) --
        #

        # Слегка опускаем группу чекбоксов (5 пикселей сверху)
        self.main_layout.addSpacing(5)

        # Первый чекбокс
        self.autostart_checkbox = QCheckBox(SETTINGS_TEXT[lang]["autostart"])
        self.autostart_checkbox.setChecked(self.parent.config.get("autostart", False))
        self.autostart_checkbox.clicked.connect(self.switch_startup)
        self.main_layout.addWidget(self.autostart_checkbox)
        # Отступ в 1 px
        self.main_layout.addSpacing(1)

        # Второй чекбокс
        self.notifications_checkbox = QCheckBox(SETTINGS_TEXT[lang]["notifications"])
        self.notifications_checkbox.setChecked(self.parent.config.get("notifications", False))
        self.main_layout.addWidget(self.notifications_checkbox)
        # Отступ в 1 px
        self.main_layout.addSpacing(1)

        # Третий чекбокс
        self.history_checkbox = QCheckBox(SETTINGS_TEXT[lang]["history"])
        self.history_checkbox.setChecked(self.parent.config.get("history", False))
        self.main_layout.addWidget(self.history_checkbox)

        # -- Большой отступ между чекбоксами и кнопками (20 px) --
        self.main_layout.addSpacing(80)

        #
        # -- ГРУППА КНОПОК --
        #

        # Кнопка «Режим перевода»
        self.translation_mode_button = QPushButton(
            SETTINGS_TEXT[lang]["translation_mode"].format(
                mode=self.parent.config.get("translation_mode", TRANSLATION_MODES[lang][0])
            )
        )
        self.translation_mode_button.clicked.connect(self.cycle_translation_mode)
        self.main_layout.addWidget(self.translation_mode_button)

        # Уменьшаем отступ между «Text translation mode» и «Configure hotkeys»
        self.main_layout.addSpacing(1)

        # Кнопка «Настроить горячие клавиши»
        hotkeys_button = QPushButton(SETTINGS_TEXT[lang]["hotkeys"])
        hotkeys_button.clicked.connect(self.show_hotkeys_screen)
        self.main_layout.addWidget(hotkeys_button)

        # Небольшой отступ перед кнопкой «Сохранить и вернуться»
        self.main_layout.addSpacing(10)

        # Кнопка «Сохранить и вернуться»
        save_return_button = QPushButton(SETTINGS_TEXT[lang]["save_and_back"])
        save_return_button.setObjectName("saveReturnButton")
        save_return_button.clicked.connect(self.save_and_back)
        self.main_layout.addWidget(save_return_button)

        # Небольшой отступ внизу (5 px), чтобы кнопки не прилипали к нижнему краю
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
        self.translation_mode_button.setText(
            SETTINGS_TEXT[lang]["translation_mode"].format(mode=new_mode)
        )

    def show_hotkeys_screen(self):
        self.clear_main_layout()
        self.hotkeys_mode = True
        # На экране горячих клавиш вернём отступы и spacing побольше
        self.main_layout.setContentsMargins(9, 9, 9, 9)
        self.main_layout.setSpacing(9)

        lang = self.parent.current_interface_language
        label = QLabel(SETTINGS_TEXT[lang]["hotkeys"])
        self.main_layout.addWidget(label)

        self.hotkey_input = ClearableKeySequenceEdit()
        saved_hotkeys = self.parent.config.get("hotkeys", "")
        self.hotkey_input.setKeySequence(QKeySequence(saved_hotkeys))
        self.main_layout.addWidget(self.hotkey_input)

        self.remove_label = QLabel(SETTINGS_TEXT[lang]["remove_hotkey"])
        self.main_layout.addWidget(self.remove_label)

        save_button = QPushButton(SETTINGS_TEXT[lang]["save"])
        save_button.clicked.connect(self.save_hotkeys)
        self.main_layout.addWidget(save_button)

        back_button = QPushButton(SETTINGS_TEXT[lang]["back"])
        back_button.clicked.connect(self.back_from_hotkeys)
        self.main_layout.addWidget(back_button)

        self.apply_theme()

    def back_from_hotkeys(self):
        # Возвращаемся к «жёсткой» верстке
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(0)
        self.init_ui()
        self.apply_theme()

    def save_hotkeys(self):
        hotkey_seq = self.hotkey_input.keySequence().toString()
        self.parent.config["hotkeys"] = hotkey_seq
        self.parent.hotkeys = hotkey_seq
        self.parent.save_config()

    def save_and_back(self):
        self.parent.config["autostart"] = self.autostart_checkbox.isChecked()
        self.parent.config["notifications"] = self.notifications_checkbox.isChecked()
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
                border: 1px solid {theme['text_color']};
                padding: 4px;
                font-size: 16px;
            }}
            /* Для кнопки Save and return делаем бледно-фиолетовую обводку */
            QPushButton#saveReturnButton {{
                border: 2px solid #C5B3E9;
            }}
        """
        self.setStyleSheet(style)

        # Если открыта страница настроек горячих клавиш, стилизуем поле ввода
        if self.hotkeys_mode and hasattr(self, 'hotkey_input'):
            if self.parent.current_theme == "Темная":
                self.hotkey_input.setStyleSheet(
                    "background-color: #2a2a2a; color: #ffffff; border: 1px solid #ffffff; padding: 4px;"
                )
            else:
                self.hotkey_input.setStyleSheet(
                    "background-color: #ffffff; color: #000000; border: 1px solid #000000; padding: 4px;"
                )

    def update_language(self):
        lang = self.parent.current_interface_language
        if self.hotkeys_mode:
            self.show_hotkeys_screen()
        else:
            autostart = self.autostart_checkbox.isChecked()
            notifications = self.notifications_checkbox.isChecked()
            history = self.history_checkbox.isChecked()
            self.init_ui()
            self.autostart_checkbox.setChecked(autostart)
            self.notifications_checkbox.setChecked(notifications)
            self.history_checkbox.setChecked(history)
        self.apply_theme()
