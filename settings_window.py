import os
import json
import webbrowser
import requests, zipfile, tempfile, shutil, threading, hashlib
import sys
import subprocess
import platform
import re
import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox, QKeySequenceEdit,
    QMessageBox, QTextEdit, QHBoxLayout, QComboBox, QProgressDialog, QSpacerItem, QSizePolicy, QApplication, QToolButton,
    QDialog, QProgressBar
)
from PyQt5.QtCore import Qt, QMetaObject, pyqtSlot
from PyQt5.QtGui import QKeySequence, QIcon
from PyQt5 import QtCore
from app_version import APP_VERSION

# Импортируем функцию инвалидации кэша (ленивый импорт для избежания циклического импорта)
def _invalidate_main_config_cache():
    for module_name in ("main", "__main__"):
        module = sys.modules.get(module_name)
        invalidate_config_cache = getattr(module, "invalidate_config_cache", None)
        if callable(invalidate_config_cache):
            try:
                invalidate_config_cache()
            except Exception:
                pass
            return

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


GITHUB_OWNER = "jabrailkhalil"
GITHUB_REPO = "clickntranslate"
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
TESSERACT_BUNDLE_RELEASE_TAG = "v1.3.2"
TESSERACT_BUNDLE_NAME_WIN64 = "ClicknTranslate-tesseract-win64.zip"
TESSERACT_BUNDLE_URL_WIN64 = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/"
    f"{TESSERACT_BUNDLE_RELEASE_TAG}/{TESSERACT_BUNDLE_NAME_WIN64}"
)
HYMT_MODEL_FILE = "HY-MT1.5-1.8B-Q4_K_M.gguf"
HYMT_MODEL_URL = (
    "https://huggingface.co/tencent/HY-MT1.5-1.8B-GGUF/resolve/main/"
    f"{HYMT_MODEL_FILE}?download=true"
)
HYMT_MODEL_SHA256 = "4383ac0c3c8e476de98ff979c2a3f069f8c4fb385e7860cf2d28da896cc477c7"
HYMT_RUNTIME_ARCHIVE_NAME_WIN64 = "llama-b9048-bin-win-cpu-x64.zip"
HYMT_RUNTIME_URL_WIN64 = (
    "https://github.com/ggml-org/llama.cpp/releases/download/b9048/"
    f"{HYMT_RUNTIME_ARCHIVE_NAME_WIN64}"
)
HYMT_RUNTIME_SHA256 = "7412d3b73de94b9d29d3a7f9f971c68f35bac3cc47c1a45fc60b01b962663938"
HYMT_LICENSE_URL = "https://huggingface.co/tencent/HY-MT1.5-1.8B-GGUF/resolve/main/License.txt?download=true"
HYMT_README_URL = "https://huggingface.co/tencent/HY-MT1.5-1.8B-GGUF/resolve/main/README.md?download=true"
HYMT_NOTICE_TEXT = (
    "Tencent HY is licensed under the Tencent HY Community License Agreement, "
    "Copyright (c) 2025 Tencent. All Rights Reserved. The trademark rights of "
    "\"Tencent HY\" are owned by Tencent or its affiliate."
)
HYMT_ENGINE_KEY = "hymt"
HYMT_ENGINE_DISPLAY = "Hy-MT"

TRANSLATOR_ENGINE_OPTIONS = (
    ("google", "Google", "online"),
    ("argos", "Argos", "offline"),
    (HYMT_ENGINE_KEY, HYMT_ENGINE_DISPLAY, "offline"),
    ("mymemory", "MyMemory", "online"),
    ("lingva", "Lingva", "online"),
    ("libretranslate", "LibreTranslate", "online"),
)


def _provider_kind_text(kind, lang):
    if kind == "offline":
        return {
            "ru": "офлайн",
            "es": "offline",
            "de": "offline",
            "fr": "offline",
            "zh": "离线",
        }.get(lang, "offline")
    return {
        "ru": "онлайн",
        "es": "online",
        "de": "online",
        "fr": "online",
        "zh": "在线",
    }.get(lang, "online")


def _translator_combo_labels(lang):
    return [
        name
        for _key, name, kind in TRANSLATOR_ENGINE_OPTIONS
    ]


def _translator_combo_tooltip(engine, name, kind, lang):
    kind_text = _provider_kind_text(kind, lang)
    if lang == "ru":
        details = {
            "google": "быстрый, точный, нужен интернет",
            "argos": "локальный перевод, нужен установленный языковой пакет",
            HYMT_ENGINE_KEY: "локальная LLM-модель, ставится отдельным пакетом",
            "mymemory": "онлайн API, есть дневной лимит",
            "lingva": "онлайн прокси Google",
            "libretranslate": "онлайн сервер LibreTranslate",
        }
    else:
        details = {
            "google": "fast, accurate, needs internet",
            "argos": "local translation, requires installed language packages",
            HYMT_ENGINE_KEY: "local LLM model, installed separately",
            "mymemory": "online API with daily limit",
            "lingva": "online Google proxy",
            "libretranslate": "online LibreTranslate server",
        }
    return f"{name}: {kind_text}. {details.get(engine, '')}".strip()


class UpdateCancelledError(RuntimeError):
    pass


class TesseractInstallCancelledError(RuntimeError):
    pass


class HyMTInstallCancelledError(RuntimeError):
    pass


class UpdateProgressDialog(QProgressDialog):
    def __init__(self, owner):
        super().__init__("", None, 0, 100, owner)
        self._owner = owner

    def closeEvent(self, event):
        if self._owner and getattr(self._owner, "_update_in_progress", False):
            self._owner._handle_update_progress_close_attempt()
            event.ignore()
            return
        super().closeEvent(event)

    def reject(self):
        if self._owner and getattr(self._owner, "_update_in_progress", False):
            self._owner._handle_update_progress_close_attempt()
            return
        super().reject()


class TesseractInstallProgressDialog(QDialog):
    canceled = QtCore.pyqtSignal()

    def __init__(self, owner, title="Tesseract", in_progress_attr="_tesseract_install_in_progress", cancel_callback=None):
        super().__init__(None)
        self._owner = owner
        self._title = title
        self._in_progress_attr = in_progress_attr
        self._cancel_callback = cancel_callback
        self._drag_position = None
        self._user_minimized = False
        owner_parent = getattr(owner, "parent", None)
        self._lang = getattr(owner_parent, "current_interface_language", "en")
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.NonModal)
        self.setMinimumWidth(430)
        self.setStyleSheet("""
            QDialog {
                background-color: #111111;
                color: #ffffff;
                border: 1px solid #7a61b3;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
                font-size: 15px;
            }
            QPushButton {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #6f5aa8;
                padding: 5px 12px;
            }
            QPushButton:hover {
                background-color: #333333;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 6px;
                text-align: center;
                background: #1d1d1d;
                color: #ffffff;
                min-height: 20px;
            }
            QProgressBar::chunk {
                background-color: #7a61b3;
                border-radius: 5px;
            }
            QToolButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 15px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #2b2440;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(12, 8, 8, 5)
        title_row.setSpacing(6)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #c5b3e9;")
        title_row.addWidget(self.title_label)
        title_row.addStretch()
        self.minimize_button = QToolButton(self)
        self.minimize_button.setText("–")
        self.minimize_button.setToolTip("Свернуть" if self._lang == "ru" else "Minimize")
        self.minimize_button.setFixedSize(28, 24)
        self.minimize_button.clicked.connect(self._minimize_to_taskbar)
        title_row.addWidget(self.minimize_button)
        self.close_button = QToolButton(self)
        self.close_button.setText("×")
        self.close_button.setToolTip(settings_text(self._lang, "cancel"))
        self.close_button.setFixedSize(28, 24)
        self.close_button.clicked.connect(self.reject)
        title_row.addWidget(self.close_button)
        outer.addLayout(title_row)

        body = QVBoxLayout()
        body.setContentsMargins(16, 8, 16, 16)
        body.setSpacing(10)
        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        body.addWidget(self.message_label)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        body.addWidget(self.progress_bar)
        self.cancel_button = QPushButton(settings_text(self._lang, "cancel"))
        self.cancel_button.clicked.connect(self.reject)
        body.addWidget(self.cancel_button, alignment=Qt.AlignRight)
        outer.addLayout(body)

    def _minimize_to_taskbar(self):
        self._user_minimized = True
        self.showMinimized()

    def setCancelButtonText(self, text):
        self.cancel_button.setText(text)
        self.close_button.setToolTip(text)

    def setLabelText(self, text):
        self.message_label.setText(text)

    def setRange(self, minimum, maximum):
        self.progress_bar.setRange(minimum, maximum)

    def setValue(self, value):
        self.progress_bar.setValue(value)

    def setAutoClose(self, _value):
        pass

    def setAutoReset(self, _value):
        pass

    def setMinimumDuration(self, _value):
        pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 38:
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_position is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_position)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.WindowStateChange:
            self._user_minimized = self.isMinimized()
        super().changeEvent(event)

    def closeEvent(self, event):
        if self._owner and getattr(self._owner, self._in_progress_attr, False):
            self._request_cancel()
            event.ignore()
            return
        super().closeEvent(event)

    def reject(self):
        if self._owner and getattr(self._owner, self._in_progress_attr, False):
            self._request_cancel()
            return
        super().reject()

    def _request_cancel(self):
        if callable(self._cancel_callback):
            self._cancel_callback()
            return
        if self._owner and hasattr(self._owner, "_request_tesseract_install_cancel"):
            self._owner._request_tesseract_install_cancel()


def _normalize_version(version_text):
    if not version_text:
        return "0"
    version = version_text.strip()
    if version.lower().startswith("v"):
        version = version[1:]
    return version


def _version_to_tuple(version_text):
    normalized = _normalize_version(version_text)
    parts = re.findall(r"\d+", normalized)
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def _is_newer_version(latest, current):
    latest_tuple = _version_to_tuple(latest)
    current_tuple = _version_to_tuple(current)
    max_len = max(len(latest_tuple), len(current_tuple))
    latest_tuple = latest_tuple + (0,) * (max_len - len(latest_tuple))
    current_tuple = current_tuple + (0,) * (max_len - len(current_tuple))
    return latest_tuple > current_tuple

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
        "copy_translated_text": "Copy translated text automatically",
        "freeze_screen_on_ocr": "Freeze screen during OCR",
        "fullscreen_translate_hotkey": "Fullscreen Translate Hotkey:",
        "fullscreen_from": "From:",
        "fullscreen_to": "To:",
        "translate_selection_hotkey": "Translate Selection Hotkey:",
        "translator_label": "Translate:",
        "keep_visible_on_ocr": "Keep window visible during OCR",
        "clear_cache": "Clear cache",
        "reset": "Reset",
        "update": "Update",
        "translation_history_button": "Translation history",
        "copy_history_button": "Copy history",
        "fullscreen_translate_label": "Fullscreen Translate:",
        "selection_translate_label": "Selection Translate:",
        "copy_hotkey_label": "Copy Selected Hotkey:",
        "translate_hotkey_label": "Translate Hotkey:",
        "remove_local_tesseract": "Remove local Tesseract",
        "remove_local_hymt": "Remove local Hy-MT",
        "clearing": "Clearing...",
        "cleared": "Cleared {size}",
        "yes": "Yes",
        "no": "No",
        "cancel": "Cancel",
        "open": "Open",
        "install": "Install",
        "later": "Later",
        "remove": "Remove",
        "reset_question": "Are you sure you want to reset all settings?",
        "clear_histories_title": "Clear histories?",
        "clear_histories_question": "Clear translation history and copy history?",
        "settings_reset_done": "Settings were reset"
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
        "copy_translated_text": "Копировать сразу переведённый текст",
        "freeze_screen_on_ocr": "Заморозить экран при OCR",
        "fullscreen_translate_hotkey": "Горячая клавиша для перевода всего экрана",
        "fullscreen_from": "С:",
        "fullscreen_to": "На:",
        "translate_selection_hotkey": "Перевод выделенного текста",
        "translator_label": "Перевод:",
        "keep_visible_on_ocr": "Не сворачивать при OCR",
        "clear_cache": "Очистить кэш",
        "reset": "Сброс",
        "update": "Обновление",
        "translation_history_button": "История переводов",
        "copy_history_button": "История копирований",
        "fullscreen_translate_label": "Перевод всего экрана",
        "selection_translate_label": "Перевод выделенного текста",
        "copy_hotkey_label": "Горячая клавиша для копирования",
        "translate_hotkey_label": "Перевод выделенного (OCR)",
        "remove_local_tesseract": "Удалить локальный Tesseract",
        "remove_local_hymt": "Удалить локальный Hy-MT",
        "clearing": "Выполняется...",
        "cleared": "Очищено {size}",
        "yes": "Да",
        "no": "Нет",
        "cancel": "Отмена",
        "open": "Открыть",
        "install": "Установить",
        "later": "Позже",
        "remove": "Удалить",
        "reset_question": "Вы уверены, что хотите сбросить все настройки?",
        "clear_histories_title": "Очистить истории?",
        "clear_histories_question": "Очистить историю переводов и историю копирований?",
        "settings_reset_done": "Настройки сброшены"
    },
    "es": {
        "autostart": "Iniciar con el sistema",
        "translation_mode": "Modo de traduccion: {mode}",
        "hotkeys": "Configurar atajos",
        "save_and_back": "Guardar y volver",
        "copy_to_clipboard": "Copiar al portapapeles",
        "history": "Guardar historial de traducciones",
        "test_ocr": "Probar OCR",
        "save": "Guardar",
        "back": "Volver",
        "remove_hotkey": "Pulsa ESC para quitar el atajo",
        "history_view": "Ver historial de traducciones",
        "start_minimized": "Iniciar en modo sombra",
        "copy_history_view": "Mostrar historial de copias",
        "copy_history": "Guardar historial de copias",
        "clear_copy_history": "Borrar historial de copias",
        "clear_translation_history": "Borrar historial de traducciones",
        "history_title": "Historial de traducciones",
        "copy_history_title": "Historial de copias",
        "history_empty": "El historial esta vacio.",
        "history_error": "Error al leer el historial.",
        "copy_translated_text": "Copiar automaticamente el texto traducido",
        "freeze_screen_on_ocr": "Congelar pantalla durante OCR",
        "fullscreen_translate_hotkey": "Atajo de traduccion de pantalla:",
        "fullscreen_from": "De:",
        "fullscreen_to": "A:",
        "translate_selection_hotkey": "Atajo para traducir seleccion:",
        "translator_label": "Traducir:",
        "keep_visible_on_ocr": "Mantener ventana visible durante OCR",
        "clear_cache": "Borrar cache",
        "reset": "Restablecer",
        "update": "Actualizar",
        "translation_history_button": "Historial de traducciones",
        "copy_history_button": "Historial de copias",
        "fullscreen_translate_label": "Traduccion de pantalla:",
        "selection_translate_label": "Traduccion de seleccion:",
        "copy_hotkey_label": "Atajo para copiar seleccion:",
        "translate_hotkey_label": "Atajo de traduccion:",
        "remove_local_tesseract": "Eliminar Tesseract local",
        "remove_local_hymt": "Eliminar Hy-MT local",
        "clearing": "Borrando...",
        "cleared": "Borrado {size}",
        "yes": "Si",
        "no": "No",
        "cancel": "Cancelar",
        "open": "Abrir",
        "install": "Instalar",
        "later": "Mas tarde",
        "remove": "Eliminar",
        "reset_question": "Seguro que quieres restablecer todos los ajustes?",
        "clear_histories_title": "Borrar historiales?",
        "clear_histories_question": "Borrar el historial de traducciones y de copias?",
        "settings_reset_done": "Ajustes restablecidos"
    },
    "de": {
        "autostart": "Mit dem System starten",
        "translation_mode": "Ubersetzungsmodus: {mode}",
        "hotkeys": "Tastenkurzel konfigurieren",
        "save_and_back": "Speichern und zuruck",
        "copy_to_clipboard": "In Zwischenablage kopieren",
        "history": "Ubersetzungsverlauf speichern",
        "test_ocr": "OCR testen",
        "save": "Speichern",
        "back": "Zuruck",
        "remove_hotkey": "ESC drucken, um das Tastenkurzel zu entfernen",
        "history_view": "Ubersetzungsverlauf anzeigen",
        "start_minimized": "Im Schattenmodus starten",
        "copy_history_view": "Kopierverlauf anzeigen",
        "copy_history": "Kopierverlauf speichern",
        "clear_copy_history": "Kopierverlauf leeren",
        "clear_translation_history": "Ubersetzungsverlauf leeren",
        "history_title": "Ubersetzungsverlauf",
        "copy_history_title": "Kopierverlauf",
        "history_empty": "Der Verlauf ist leer.",
        "history_error": "Fehler beim Lesen des Verlaufs.",
        "copy_translated_text": "Ubersetzten Text automatisch kopieren",
        "freeze_screen_on_ocr": "Bildschirm wahrend OCR einfrieren",
        "fullscreen_translate_hotkey": "Tastenkurzel fur Bildschirmubersetzung:",
        "fullscreen_from": "Von:",
        "fullscreen_to": "Nach:",
        "translate_selection_hotkey": "Tastenkurzel fur Auswahlubersetzung:",
        "translator_label": "Ubersetzen:",
        "keep_visible_on_ocr": "Fenster wahrend OCR sichtbar halten",
        "clear_cache": "Cache leeren",
        "reset": "Zurucksetzen",
        "update": "Aktualisieren",
        "translation_history_button": "Ubersetzungsverlauf",
        "copy_history_button": "Kopierverlauf",
        "fullscreen_translate_label": "Bildschirmubersetzung:",
        "selection_translate_label": "Auswahlubersetzung:",
        "copy_hotkey_label": "Tastenkurzel zum Kopieren:",
        "translate_hotkey_label": "Tastenkurzel zum Ubersetzen:",
        "remove_local_tesseract": "Lokales Tesseract entfernen",
        "remove_local_hymt": "Lokales Hy-MT entfernen",
        "clearing": "Wird geleert...",
        "cleared": "{size} geleert",
        "yes": "Ja",
        "no": "Nein",
        "cancel": "Abbrechen",
        "open": "Offnen",
        "install": "Installieren",
        "later": "Spater",
        "remove": "Entfernen",
        "reset_question": "Mochtest du wirklich alle Einstellungen zurucksetzen?",
        "clear_histories_title": "Verlaufe leeren?",
        "clear_histories_question": "Ubersetzungs- und Kopierverlauf leeren?",
        "settings_reset_done": "Einstellungen wurden zuruckgesetzt"
    },
    "fr": {
        "autostart": "Demarrer avec le systeme",
        "translation_mode": "Mode de traduction : {mode}",
        "hotkeys": "Configurer les raccourcis",
        "save_and_back": "Enregistrer et revenir",
        "copy_to_clipboard": "Copier dans le presse-papiers",
        "history": "Enregistrer l'historique des traductions",
        "test_ocr": "Tester l'OCR",
        "save": "Enregistrer",
        "back": "Retour",
        "remove_hotkey": "Appuyez sur ESC pour supprimer le raccourci",
        "history_view": "Voir l'historique des traductions",
        "start_minimized": "Demarrer en mode ombre",
        "copy_history_view": "Afficher l'historique des copies",
        "copy_history": "Enregistrer l'historique des copies",
        "clear_copy_history": "Effacer l'historique des copies",
        "clear_translation_history": "Effacer l'historique des traductions",
        "history_title": "Historique des traductions",
        "copy_history_title": "Historique des copies",
        "history_empty": "L'historique est vide.",
        "history_error": "Erreur de lecture de l'historique.",
        "copy_translated_text": "Copier automatiquement le texte traduit",
        "freeze_screen_on_ocr": "Figer l'ecran pendant l'OCR",
        "fullscreen_translate_hotkey": "Raccourci traduction plein ecran :",
        "fullscreen_from": "De :",
        "fullscreen_to": "Vers :",
        "translate_selection_hotkey": "Raccourci traduction de selection :",
        "translator_label": "Traduire :",
        "keep_visible_on_ocr": "Garder la fenetre visible pendant l'OCR",
        "clear_cache": "Vider le cache",
        "reset": "Reinitialiser",
        "update": "Mettre a jour",
        "translation_history_button": "Historique des traductions",
        "copy_history_button": "Historique des copies",
        "fullscreen_translate_label": "Traduction plein ecran :",
        "selection_translate_label": "Traduction de selection :",
        "copy_hotkey_label": "Raccourci de copie :",
        "translate_hotkey_label": "Raccourci de traduction :",
        "remove_local_tesseract": "Supprimer Tesseract local",
        "remove_local_hymt": "Supprimer Hy-MT local",
        "clearing": "Nettoyage...",
        "cleared": "{size} nettoye",
        "yes": "Oui",
        "no": "Non",
        "cancel": "Annuler",
        "open": "Ouvrir",
        "install": "Installer",
        "later": "Plus tard",
        "remove": "Supprimer",
        "reset_question": "Voulez-vous vraiment reinitialiser tous les reglages ?",
        "clear_histories_title": "Effacer les historiques ?",
        "clear_histories_question": "Effacer l'historique des traductions et des copies ?",
        "settings_reset_done": "Reglages reinitialises"
    },
    "zh": {
        "autostart": "随系统启动",
        "translation_mode": "文本翻译模式：{mode}",
        "hotkeys": "配置快捷键",
        "save_and_back": "保存并返回",
        "copy_to_clipboard": "复制到剪贴板",
        "history": "保存翻译历史",
        "test_ocr": "测试 OCR",
        "save": "保存",
        "back": "返回",
        "remove_hotkey": "按 ESC 删除快捷键",
        "history_view": "查看翻译历史",
        "start_minimized": "以阴影模式启动",
        "copy_history_view": "显示复制历史",
        "copy_history": "保存复制历史",
        "clear_copy_history": "清除复制历史",
        "clear_translation_history": "清除翻译历史",
        "history_title": "翻译历史",
        "copy_history_title": "复制历史",
        "history_empty": "历史为空。",
        "history_error": "读取历史时出错。",
        "copy_translated_text": "自动复制翻译文本",
        "freeze_screen_on_ocr": "OCR 时冻结屏幕",
        "fullscreen_translate_hotkey": "全屏翻译快捷键：",
        "fullscreen_from": "从：",
        "fullscreen_to": "到：",
        "translate_selection_hotkey": "翻译选中文本快捷键：",
        "translator_label": "翻译：",
        "keep_visible_on_ocr": "OCR 时保持窗口可见",
        "clear_cache": "清除缓存",
        "reset": "重置",
        "update": "更新",
        "translation_history_button": "翻译历史",
        "copy_history_button": "复制历史",
        "fullscreen_translate_label": "全屏翻译：",
        "selection_translate_label": "选中文本翻译：",
        "copy_hotkey_label": "复制选区快捷键：",
        "translate_hotkey_label": "翻译快捷键：",
        "remove_local_tesseract": "删除本地 Tesseract",
        "remove_local_hymt": "删除本地 Hy-MT",
        "clearing": "正在清除...",
        "cleared": "已清除 {size}",
        "yes": "是",
        "no": "否",
        "cancel": "取消",
        "open": "打开",
        "install": "安装",
        "later": "稍后",
        "remove": "删除",
        "reset_question": "确定要重置所有设置吗？",
        "clear_histories_title": "清除历史？",
        "clear_histories_question": "清除翻译历史和复制历史吗？",
        "settings_reset_done": "设置已重置"
    }
}

def settings_text(lang, key):
    texts = SETTINGS_TEXT.get(lang, SETTINGS_TEXT["en"])
    return texts.get(key, SETTINGS_TEXT["en"].get(key, key))

class ClearableKeySequenceEdit(QKeySequenceEdit):
    """QKeySequenceEdit that always stores English key names regardless of keyboard layout."""

    _CYR_TO_LAT = {
        'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P',
        'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L',
        'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M',
        'Х': '[', 'Ъ': ']', 'Ж': ';', 'Э': "'", 'Б': ',', 'Ю': '.',
    }

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(event)
            seq_str = self.keySequence().toString()
            normalized = self._normalize_hotkey(seq_str)
            if normalized != seq_str:
                self.setKeySequence(QKeySequence(normalized))

    @classmethod
    def _normalize_hotkey(cls, hotkey_str):
        result = []
        for ch in hotkey_str:
            upper = ch.upper()
            if upper in cls._CYR_TO_LAT:
                result.append(cls._CYR_TO_LAT[upper])
            else:
                result.append(ch)
        return ''.join(result)

# Класс HistoryDialog удалён, т.к. история теперь отображается внутри настроек

def get_data_file(filename):
    import sys, os
    def get_portable_dir():
        if hasattr(sys, '_MEIPASS'):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    data_dir = os.path.join(get_portable_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, filename)

def ensure_json_file(filepath, default_content):
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_content, f, ensure_ascii=False, indent=4)


class SettingsWindow(QWidget):
    def switch_startup(self, state):
        enabled = self.parent.set_autostart(self.autostart_checkbox.isChecked())
        self.autostart_checkbox.setChecked(enabled)
        self.parent.autostart = enabled
        self.parent.config["autostart"] = enabled
        self.parent.save_config()
        _invalidate_main_config_cache()  # Сбрасываем кэш после сохранения

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
        self.previous_translator_engine = None
        self._update_in_progress = False
        self._update_phase = "idle"
        self._update_temp_dir = ""
        self._update_cancel_requested = threading.Event()
        self._tesseract_install_in_progress = False
        self._tesseract_install_phase = "idle"
        self._tesseract_temp_dir = ""
        self._tesseract_cancel_requested = threading.Event()
        self._hymt_install_in_progress = False
        self._hymt_install_phase = "idle"
        self._hymt_temp_dir = ""
        self._hymt_cancel_requested = threading.Event()
        self.hymt_progress = None
        self._parent_was_topmost_before_tesseract = None
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
        self.autostart_checkbox = QCheckBox(settings_text(lang, "autostart"))
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
        self.ocr_engine_combo.currentTextChanged.connect(lambda _text: self._sync_ocr_engine_delete_button())
        self.ocr_engine_combo.setStyleSheet("margin-left:6px; padding-right:18px;")
        self.ocr_engine_combo.setFixedWidth(130)
        self.ocr_engine_combo.setFixedHeight(32)
        self.ocr_engine_combo.installEventFilter(self)
        self.ocr_engine_delete_btn = QToolButton(self.ocr_engine_combo)
        self.ocr_engine_delete_btn.setObjectName("ocrEngineDeleteButton")
        self.ocr_engine_delete_btn.setText("x")
        self.ocr_engine_delete_btn.setCursor(Qt.PointingHandCursor)
        self.ocr_engine_delete_btn.setToolTip(settings_text(lang, "remove_local_tesseract"))
        self.ocr_engine_delete_btn.clicked.connect(self.remove_tesseract_engine)
        self.ocr_engine_delete_btn.setStyleSheet("""
            QToolButton#ocrEngineDeleteButton {
                background-color: rgba(212, 68, 68, 0.85);
                color: #ffffff;
                border: none;
                border-radius: 7px;
                font-size: 10px;
                font-weight: bold;
                padding: 0px;
                margin: 0px;
            }
            QToolButton#ocrEngineDeleteButton:hover {
                background-color: #d44444;
            }
        """)
        self._sync_ocr_engine_delete_button()
        QtCore.QTimer.singleShot(0, self._sync_ocr_engine_delete_button)

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
        self.start_minimized_checkbox = QCheckBox(settings_text(lang, "start_minimized"))
        self.start_minimized_checkbox.setChecked(self.parent.config.get("start_minimized", False))
        self.start_minimized_checkbox.toggled.connect(lambda state: self.auto_save_setting("start_minimized", state))
        self.start_minimized_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:300px;")
        self.start_minimized_checkbox.setFixedHeight(fixed_height)
        row2.addWidget(self.start_minimized_checkbox, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        row2.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # Переводчик блок
        # [ИНСТРУКЦИЯ] См. выше про выравнивание (AlignTop + padding 2px)
        tr_label = QLabel(settings_text(lang, "translator_label"))
        tr_label.setStyleSheet("margin:0; padding:0; padding-top: 2px;")
        tr_label.setFixedWidth(90)
        tr_label.setFixedHeight(38)
        tr_label.setAlignment(Qt.AlignRight | Qt.AlignTop)

        self.translator_combo = QComboBox()
        # Порядок: Google первый, офлайн-движки рядом.
        self.translator_combo.addItems(_translator_combo_labels(lang))
        for option_index, (engine, name, kind) in enumerate(TRANSLATOR_ENGINE_OPTIONS):
            self.translator_combo.setItemData(
                option_index,
                _translator_combo_tooltip(engine, name, kind, lang),
                Qt.ToolTipRole,
            )
        # Маппинг индексов на имена движков (соответствует порядку в addItems)
        self._translator_engines = [engine for engine, _name, _kind in TRANSLATOR_ENGINE_OPTIONS]
        
        current_tr = self.parent.config.get("translator_engine", "Google").lower()
        try:
            idx = self._translator_engines.index(current_tr)
        except ValueError:
            idx = 0 # Google по умолчанию
        self.translator_combo.setCurrentIndex(idx)
        self.translator_combo.currentIndexChanged.connect(self._on_translator_changed)
        self.translator_combo.currentIndexChanged.connect(lambda _idx: self._sync_translator_engine_delete_button())
        self.translator_combo.setStyleSheet("margin-left:6px; padding-right:18px;")
        self.translator_combo.setFixedWidth(130)
        self.translator_combo.setFixedHeight(32)
        self.translator_combo.installEventFilter(self)
        self.translator_engine_delete_btn = QToolButton(self.translator_combo)
        self.translator_engine_delete_btn.setObjectName("translatorEngineDeleteButton")
        self.translator_engine_delete_btn.setText("x")
        self.translator_engine_delete_btn.setCursor(Qt.PointingHandCursor)
        self.translator_engine_delete_btn.setToolTip(settings_text(lang, "remove_local_hymt"))
        self.translator_engine_delete_btn.clicked.connect(self.remove_hymt_engine)
        self.translator_engine_delete_btn.setStyleSheet("""
            QToolButton#translatorEngineDeleteButton {
                background-color: rgba(212, 68, 68, 0.85);
                color: #ffffff;
                border: none;
                border-radius: 7px;
                font-size: 10px;
                font-weight: bold;
                padding: 0px;
                margin: 0px;
            }
            QToolButton#translatorEngineDeleteButton:hover {
                background-color: #d44444;
            }
        """)
        self._sync_translator_engine_delete_button()
        QtCore.QTimer.singleShot(0, self._sync_translator_engine_delete_button)
        
        # Выравниваем
        row2.addWidget(tr_label) # Alignment внутри виджета
        row2.addWidget(self.translator_combo, alignment=Qt.AlignVCenter)
        
        # Подсказки для переводчиков
        tr_tooltips = {
            "ru": "Google — быстрый, точный, нужен интернет\nArgos — офлайн, без интернета, приватный\nHy-MT — локальная LLM-модель, ставится отдельным пакетом\nMyMemory — бесплатный API, лимит 5000 симв/день\nLingva — прокси Google, более стабильный\nLibreTranslate — открытый, бесплатный",
            "en": "Google — fast, accurate, needs internet\nArgos — offline, no internet, private\nHy-MT — local LLM model, installed as a separate package\nMyMemory — free API, 5000 chars/day limit\nLingva — Google proxy, more stable\nLibreTranslate — open source, free"
        }
        self.translator_combo.setToolTip(tr_tooltips.get(lang, tr_tooltips["en"]))
        tr_label.setToolTip(tr_tooltips.get(lang, tr_tooltips["en"]))
        self.main_layout.addLayout(row2)

        # --- Подготовим кнопку обновления (перенесена в группу кнопок ниже) ---
        # Убрали из этой строки

        # --- Остальные чекбоксы (start_minimized уже добавлен выше) ---

        # Остальные чекбоксы
        self.copy_translated_checkbox = QCheckBox(settings_text(lang, "copy_translated_text"))
        self.copy_translated_checkbox.setChecked(self.parent.config.get("copy_translated_text", False))
        self.copy_translated_checkbox.toggled.connect(lambda state: self.auto_save_setting("copy_translated_text", state))
        self.copy_translated_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:400px;")
        self.copy_translated_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.copy_translated_checkbox, alignment=Qt.AlignLeft)

        self.copy_history_checkbox = QCheckBox(settings_text(lang, "copy_history"))
        self.copy_history_checkbox.setChecked(self.parent.config.get("copy_history", False))
        self.copy_history_checkbox.toggled.connect(lambda state: self.auto_save_setting("copy_history", state))
        self.copy_history_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:400px;")
        self.copy_history_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.copy_history_checkbox, alignment=Qt.AlignLeft)

        self.history_checkbox = QCheckBox(settings_text(lang, "history"))
        self.history_checkbox.setChecked(self.parent.config.get("history", False))
        self.history_checkbox.toggled.connect(self.on_history_checkbox_toggled)
        self.history_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:400px;")
        self.history_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.history_checkbox, alignment=Qt.AlignLeft)

        # Чекбокс "Не сворачивать при OCR"
        self.keep_visible_checkbox = QCheckBox(settings_text(lang, "keep_visible_on_ocr"))
        self.keep_visible_checkbox.setChecked(self.parent.config.get("keep_visible_on_ocr", False))
        self.keep_visible_checkbox.toggled.connect(lambda state: self.auto_save_setting("keep_visible_on_ocr", state))
        self.keep_visible_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:400px;")
        self.keep_visible_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.keep_visible_checkbox, alignment=Qt.AlignLeft)

        # Последний чекбокс в фиксированном окне: заморозка экрана при OCR
        self.freeze_screen_checkbox = QCheckBox(settings_text(lang, "freeze_screen_on_ocr"))
        self.freeze_screen_checkbox.setChecked(self.parent.config.get("freeze_screen_on_ocr", False))
        self.freeze_screen_checkbox.toggled.connect(lambda state: self.auto_save_setting("freeze_screen_on_ocr", state))
        self.freeze_screen_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:400px;")
        self.freeze_screen_checkbox.setFixedHeight(fixed_height)
        self.main_layout.addWidget(self.freeze_screen_checkbox, alignment=Qt.AlignLeft)

        # --- конец блока чекбоксов ---
        self.main_layout.addSpacing(4)

        # --- Группа кнопок: Clear cache | Reset | Update (горизонтальная, связанные стили) ---
        btn_group_layout = QHBoxLayout()
        btn_group_layout.setContentsMargins(0, 0, 0, 0)
        btn_group_layout.setSpacing(0)  # Без зазора между кнопками
        
        # Левая кнопка - закругление слева (фиолетовая)
        self.clear_cache_btn = QPushButton(settings_text(lang, "clear_cache"))
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
        reset_btn = QPushButton(settings_text(lang, "reset"))
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
        self.update_btn = QPushButton(settings_text(lang, "update"))
        self.update_btn.setStyleSheet("""
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
        self.update_btn.setFixedHeight(38)
        self.update_btn.clicked.connect(self.check_for_updates)
        btn_group_layout.addWidget(self.update_btn)
        
        self.main_layout.addLayout(btn_group_layout)
        # Убрали spacing 10, чтобы кнопки слиплись
        self.main_layout.addSpacing(0)

        # --- ГРУППА КНОПОК (расширенные для полного текста) ---
        self.hotkeys_button = QPushButton(settings_text(lang, "hotkeys"))
        self.hotkeys_button.clicked.connect(self.show_hotkeys_screen)
        # Hotkeys: текст еще выше
        self.hotkeys_button.setStyleSheet("""
            padding-top: 2px;
            padding-bottom: 12px;
            padding-left: 16px;
            padding-right: 16px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 0px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        """)
        self.hotkeys_button.setMinimumWidth(320)
        self.hotkeys_button.setMinimumHeight(40)
        self.hotkeys_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.main_layout.addWidget(self.hotkeys_button)
        self.main_layout.addSpacing(0)
        
        # --- Две кнопки истории объединены (без зазора) ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(0)  # Без зазора
        btn_row.setContentsMargins(0, 0, 0, 0)
        
        history_btn = QPushButton(settings_text(lang, "translation_history_button"))
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
        
        copy_history_btn = QPushButton(settings_text(lang, "copy_history_button"))
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
        version_label = QLabel(f"V{APP_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #7A5FA1; font-size: 16px; font-weight: bold; margin-bottom: 2px; margin-top: 2px;")
        self.main_layout.addWidget(version_label)
        self.main_layout.addStretch()

    def show_hotkeys_screen(self):
        self.setup_new_layout()
        self.hotkeys_mode = True
        self.main_layout.setContentsMargins(9, 5, 9, 5)
        self.main_layout.setSpacing(3)

        lang = self.parent.current_interface_language

        # Блок для настройки горячей клавиши "Copy Selected"
        label_copy = QLabel(settings_text(lang, "copy_hotkey_label"))
        self.main_layout.addWidget(label_copy)

        self.copy_hotkey_input = ClearableKeySequenceEdit()
        saved_copy_hotkey = self.parent.config.get("copy_hotkey", "")
        self.copy_hotkey_input.setKeySequence(QKeySequence(saved_copy_hotkey))
        self.main_layout.addWidget(self.copy_hotkey_input)
        self.copy_hotkey_input.keySequenceChanged.connect(self.save_copy_hotkey)

        self.main_layout.addSpacing(2)

        # Блок для настройки горячей клавиши "Translate Selected"
        label_translate = QLabel(settings_text(lang, "translate_hotkey_label"))
        self.main_layout.addWidget(label_translate)

        self.translate_hotkey_input = ClearableKeySequenceEdit()
        saved_translate_hotkey = self.parent.config.get("translate_hotkey", "")
        self.translate_hotkey_input.setKeySequence(QKeySequence(saved_translate_hotkey))
        self.main_layout.addWidget(self.translate_hotkey_input)
        self.translate_hotkey_input.keySequenceChanged.connect(self.save_translate_hotkey)

        self.main_layout.addSpacing(4)

        # Блок для настройки горячей клавиши "Fullscreen Translate"
        label_fullscreen = QLabel(settings_text(lang, "fullscreen_translate_label"))
        self.main_layout.addWidget(label_fullscreen)

        self.fullscreen_translate_hotkey_input = ClearableKeySequenceEdit()
        saved_fs_hotkey = self.parent.config.get("fullscreen_translate_hotkey", "")
        self.fullscreen_translate_hotkey_input.setKeySequence(QKeySequence(saved_fs_hotkey))
        self.main_layout.addWidget(self.fullscreen_translate_hotkey_input)
        self.fullscreen_translate_hotkey_input.keySequenceChanged.connect(self.save_fullscreen_translate_hotkey)

        self.main_layout.addSpacing(4)

        # Блок для настройки горячей клавиши "Translate Selection" (перевод выделенного текста)
        label_selection = QLabel(settings_text(lang, "selection_translate_label"))
        self.main_layout.addWidget(label_selection)

        self.translate_selection_hotkey_input = ClearableKeySequenceEdit()
        saved_sel_hotkey = self.parent.config.get("translate_selection_hotkey", "")
        self.translate_selection_hotkey_input.setKeySequence(QKeySequence(saved_sel_hotkey))
        self.main_layout.addWidget(self.translate_selection_hotkey_input)
        self.translate_selection_hotkey_input.keySequenceChanged.connect(self.save_translate_selection_hotkey)

        # Инструктивная надпись для удаления комбинации
        remove_label = QLabel(settings_text(lang, "remove_hotkey"))
        self.main_layout.addWidget(remove_label)

        self.main_layout.addStretch()

        # Кнопка возврата
        back_button = QPushButton(settings_text(lang, "back"))
        back_button.clicked.connect(self.back_from_hotkeys)
        self.main_layout.addWidget(back_button)

        self.apply_theme()
        if hasattr(self.parent, "_complete_guide_step"):
            self.parent._complete_guide_step("hotkeys")

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
            self.parent.copy_hotkey_thread = self.parent.HotkeyListenerThread(hotkey_str, self.parent.launch_copy, hotkey_id=1)
            self.parent.copy_hotkey_thread.start()

    def save_translate_hotkey(self):
        hotkey_str = self.translate_hotkey_input.keySequence().toString()
        self.parent.config["translate_hotkey"] = hotkey_str
        self.parent.save_config()
        if hasattr(self.parent, "translate_hotkey_thread") and self.parent.translate_hotkey_thread is not None:
            try:
                self.parent.translate_hotkey_thread.stop()
                self.parent.translate_hotkey_thread.join(timeout=0.5)
            except Exception as e:
                print(f"Error stopping translate hotkey thread: {e}")
            self.parent.translate_hotkey_thread = None
        if hotkey_str:
            self.parent.translate_hotkey_thread = self.parent.HotkeyListenerThread(hotkey_str, self.parent.launch_translate, hotkey_id=2)
            self.parent.translate_hotkey_thread.start()

    def save_fullscreen_translate_hotkey(self):
        hotkey_str = self.fullscreen_translate_hotkey_input.keySequence().toString()
        self.parent.config["fullscreen_translate_hotkey"] = hotkey_str
        self.parent.save_config()
        if hasattr(self.parent, "fullscreen_translate_hotkey_thread") and self.parent.fullscreen_translate_hotkey_thread is not None:
            try:
                self.parent.fullscreen_translate_hotkey_thread.stop()
                self.parent.fullscreen_translate_hotkey_thread.join(timeout=0.5)
            except Exception as e:
                print(f"Error stopping fullscreen translate hotkey thread: {e}")
            self.parent.fullscreen_translate_hotkey_thread = None
        if hotkey_str:
            self.parent.fullscreen_translate_hotkey_thread = self.parent.HotkeyListenerThread(hotkey_str, self.parent.launch_fullscreen_translate, hotkey_id=3)
            self.parent.fullscreen_translate_hotkey_thread.start()

    def save_translate_selection_hotkey(self):
        hotkey_str = self.translate_selection_hotkey_input.keySequence().toString()
        self.parent.config["translate_selection_hotkey"] = hotkey_str
        self.parent.save_config()
        if hasattr(self.parent, "translate_selection_hotkey_thread") and self.parent.translate_selection_hotkey_thread is not None:
            try:
                self.parent.translate_selection_hotkey_thread.stop()
                self.parent.translate_selection_hotkey_thread.join(timeout=0.5)
            except Exception as e:
                print(f"Error stopping translate selection hotkey thread: {e}")
            self.parent.translate_selection_hotkey_thread = None
        if hotkey_str:
            self.parent.translate_selection_hotkey_thread = self.parent.HotkeyListenerThread(hotkey_str, self.parent.launch_translate_selection, hotkey_id=4)
            self.parent.translate_selection_hotkey_thread.start()

    def back_from_hotkeys(self):
        self.init_ui()
        self.apply_theme()

    def show_history_view(self):
        self.clear_main_layout()
        lang = self.parent.current_interface_language

        title_label = QLabel(settings_text(lang, "history_title"))
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

        clear_button = QPushButton(settings_text(lang, "clear_translation_history"))
        clear_button.clicked.connect(self.clear_history)
        self.main_layout.addWidget(clear_button)

        self.main_layout.addSpacing(10)

        back_button = QPushButton(settings_text(lang, "back"))
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
                self.history_text_edit.setText(settings_text(lang, "history_empty"))
        except Exception as e:
            self.history_text_edit.setText(settings_text(lang, "history_error"))

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

        title_label = QLabel(settings_text(lang, "copy_history_title"))
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

        clear_button = QPushButton(settings_text(lang, "clear_copy_history"))
        clear_button.clicked.connect(self.clear_copy_history)
        self.main_layout.addWidget(clear_button)

        self.main_layout.addSpacing(10)

        back_button = QPushButton(settings_text(lang, "back"))
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
                self.copy_history_text_edit.setText(settings_text(lang, "history_empty"))
        except Exception as e:
            self.copy_history_text_edit.setText(settings_text(lang, "history_error"))

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
        autostart_enabled = self.parent.set_autostart(self.autostart_checkbox.isChecked())
        self.autostart_checkbox.setChecked(autostart_enabled)
        self.parent.config["autostart"] = autostart_enabled
        self.parent.config["copy_translated_text"] = self.copy_translated_checkbox.isChecked()
        self.parent.config["copy_history"] = self.copy_history_checkbox.isChecked()
        self.parent.config["history"] = self.history_checkbox.isChecked()
        self.parent.config["start_minimized"] = self.start_minimized_checkbox.isChecked()
        self.parent.autostart = autostart_enabled
        self.parent.start_minimized = self.start_minimized_checkbox.isChecked()
        self.parent.save_config()
        self.init_ui()
        self.parent.show_main_screen()

    def check_for_updates(self):
        lang = self.parent.current_interface_language
        is_ru = lang == "ru"

        if not getattr(sys, "frozen", False):
            msg = QMessageBox(self)
            msg.setWindowTitle(settings_text(lang, "update"))
            msg.setText(
                "Автообновление работает только в собранной версии приложения.\nОткрыть страницу релизов?"
                if is_ru else
                "Auto-update is available only in the packaged app.\nOpen releases page?"
            )
            msg.setIcon(QMessageBox.Information)
            msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            yes_btn = msg.addButton(settings_text(lang, "open"), QMessageBox.YesRole)
            msg.addButton(settings_text(lang, "cancel"), QMessageBox.NoRole)
            msg.exec_()
            if msg.clickedButton() == yes_btn:
                webbrowser.open(GITHUB_RELEASES_PAGE)
            return

        if self._update_in_progress:
            return

        self._start_update_check()

    def _start_update_check(self):
        is_ru = self.parent.current_interface_language == "ru"
        self._update_cancel_requested.clear()
        self._update_phase = "checking"
        self._update_temp_dir = ""
        self._set_update_controls_enabled(False, "Проверка..." if is_ru else "Checking...")
        self._show_update_progress("Проверка обновлений..." if is_ru else "Checking updates...")
        self._update_in_progress = True

        worker = threading.Thread(target=self._check_latest_release_worker, daemon=True)
        worker.start()

    def _set_update_controls_enabled(self, enabled, text=None):
        if not hasattr(self, "update_btn"):
            return
        if text is None:
            text = settings_text(self.parent.current_interface_language, "update")
        self.update_btn.setEnabled(enabled)
        self.update_btn.setText(text)

    def _show_update_progress(self, text, determinate=False, value=0):
        is_ru = self.parent.current_interface_language == "ru"
        title = settings_text(self.parent.current_interface_language, "update")
        if not hasattr(self, "_update_progress") or self._update_progress is None:
            self._update_progress = UpdateProgressDialog(self)
            self._update_progress.setWindowTitle(title)
            self._update_progress.setCancelButton(None)
            self._update_progress.setWindowModality(Qt.WindowModal)
            self._update_progress.setAutoClose(False)
            self._update_progress.setAutoReset(False)
            self._update_progress.setMinimumDuration(0)
            self._update_progress.setMinimumWidth(430)
            self._update_progress.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            try:
                flags = self._update_progress.windowFlags()
                flags |= Qt.CustomizeWindowHint | Qt.WindowTitleHint
                flags &= ~Qt.WindowContextHelpButtonHint
                flags |= Qt.WindowCloseButtonHint
                self._update_progress.setWindowFlags(flags)
            except Exception:
                pass
            self._update_progress.setStyleSheet("""
                QProgressDialog {
                    background-color: #111111;
                    color: #ffffff;
                    border: 1px solid #6f5aa8;
                    border-radius: 8px;
                }
                QProgressBar {
                    border: 1px solid #555555;
                    border-radius: 6px;
                    text-align: center;
                    background: #1d1d1d;
                    color: #ffffff;
                    min-height: 20px;
                }
                QProgressBar::chunk {
                    background-color: #7a61b3;
                    border-radius: 5px;
                }
            """)
        else:
            try:
                self._update_progress.setWindowTitle(title)
            except Exception:
                pass
        try:
            self._update_progress.setWindowModality(Qt.WindowModal)
        except Exception:
            pass
        try:
            self._update_progress.setLabelText(text)
        except Exception:
            pass
        if determinate:
            self._update_progress.setRange(0, 100)
            self._update_progress.setValue(max(0, min(100, int(value))))
        else:
            self._update_progress.setRange(0, 0)
        self._update_progress.show()

    @QtCore.pyqtSlot(str)
    def _on_update_progress_text(self, text):
        self._show_update_progress(text, determinate=False)

    @QtCore.pyqtSlot(str, int, int)
    def _on_update_download_progress(self, stage_text, downloaded_bytes, total_bytes):
        is_ru = self.parent.current_interface_language == "ru"
        downloaded_bytes = max(0, int(downloaded_bytes))
        total_bytes = max(0, int(total_bytes))
        downloaded_mb = downloaded_bytes / (1024 * 1024)

        if total_bytes > 0:
            percent = int((downloaded_bytes * 100) / total_bytes)
            total_mb = total_bytes / (1024 * 1024)
            label = f"{stage_text}\n{downloaded_mb:.1f}/{total_mb:.1f} MB ({percent}%)"
            self._show_update_progress(label, determinate=True, value=percent)
            prefix = "Скачивание" if is_ru else "Downloading"
            self._set_update_controls_enabled(False, f"{prefix} {percent}%")
            return

        label = f"{stage_text}\n{downloaded_mb:.1f} MB"
        self._show_update_progress(label, determinate=False)
        self._set_update_controls_enabled(False, "Скачивание..." if is_ru else "Downloading...")

    def _hide_update_progress(self):
        if hasattr(self, "_update_progress") and self._update_progress is not None:
            try:
                self._update_progress.blockSignals(True)
                self._update_progress.close()
            except Exception:
                pass
            self._update_progress = None

    def _cleanup_update_temp_dir(self):
        temp_dir = getattr(self, "_update_temp_dir", "") or ""
        self._update_temp_dir = ""
        if not temp_dir:
            return
        try:
            if os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _is_update_apply_stage(self):
        return getattr(self, "_update_phase", "") == "applying"

    def _is_update_cancelable(self):
        return self._update_in_progress and not self._is_update_apply_stage()

    def _handle_update_progress_close_attempt(self):
        if not self._update_in_progress:
            return

        is_ru = self.parent.current_interface_language == "ru"
        if self._is_update_apply_stage():
            self._show_update_progress(
                "Обновление уже применяется.\nПожалуйста, подождите..." if is_ru else
                "The update is being applied.\nPlease wait...",
                determinate=False
            )
            QMessageBox.information(
                self,
                settings_text(self.parent.current_interface_language, "update"),
                "Обновление уже применяется. Закрытие сейчас недоступно.\nПожалуйста, подождите."
                if is_ru else
                "The update is already being applied. Closing is disabled right now.\nPlease wait."
            )
            return

        if not self._update_cancel_requested.is_set():
            self._update_cancel_requested.set()
            self._update_phase = "canceling"
            self._set_update_controls_enabled(False, "Отмена..." if is_ru else "Canceling...")
            self._show_update_progress(
                "Отмена обновления...\nУдаляем временные файлы, пожалуйста, подождите."
                if is_ru else
                "Canceling the update...\nCleaning temporary files, please wait.",
                determinate=False
            )
            return

        self._show_update_progress(
            "Отмена обновления...\nПожалуйста, подождите."
            if is_ru else
            "Canceling the update...\nPlease wait.",
            determinate=False
        )

    def _check_update_cancel_requested(self):
        if self._update_cancel_requested.is_set():
            raise UpdateCancelledError("Обновление отменено пользователем.")

    def _post_update_check_result(self, payload):
        try:
            payload_text = json.dumps(payload, ensure_ascii=False)
        except Exception as e:
            payload_text = json.dumps({
                "status": "error",
                "error": f"Invalid update payload: {e}"
            })
        QMetaObject.invokeMethod(
            self,
            "_on_update_check_result",
            Qt.QueuedConnection,
            QtCore.Q_ARG(str, payload_text)
        )

    def _check_latest_release_worker(self):
        is_ru = self.parent.current_interface_language == "ru"
        try:
            headers = {
                "Accept": "application/vnd.github+json",
                "User-Agent": f"ClicknTranslate/{APP_VERSION}",
            }
            response = requests.get(GITHUB_LATEST_RELEASE_API, headers=headers, timeout=20)
            response.raise_for_status()
            release = response.json()
        except Exception as e:
            if self._update_cancel_requested.is_set():
                self._post_update_check_result({"status": "cancelled"})
                return
            self._post_update_check_result({
                "status": "error",
                "error": ("Не удалось проверить обновления:\n" if is_ru else "Failed to check for updates:\n") + str(e),
            })
            return

        if self._update_cancel_requested.is_set():
            self._post_update_check_result({"status": "cancelled"})
            return

        latest_tag = release.get("tag_name") or release.get("name") or ""
        latest_version = _normalize_version(latest_tag) or APP_VERSION

        if not _is_newer_version(latest_version, APP_VERSION):
            self._post_update_check_result({
                "status": "up_to_date",
                "latest_version": latest_version,
            })
            return

        assets = release.get("assets") or []
        selected_asset = self._pick_update_asset(assets)
        if not selected_asset:
            self._post_update_check_result({
                "status": "no_asset",
                "latest_version": latest_version,
            })
            return

        asset_name = selected_asset.get("name") or f"ClicknTranslate-v{latest_version}.zip"
        asset_url = selected_asset.get("browser_download_url")
        if not asset_url:
            self._post_update_check_result({
                "status": "invalid_asset",
                "latest_version": latest_version,
            })
            return

        checksum_url = self._pick_checksum_url(assets, asset_name)
        self._post_update_check_result({
            "status": "ready",
            "latest_version": latest_version,
            "asset_name": asset_name,
            "asset_url": asset_url,
            "checksum_url": checksum_url,
        })

    @QtCore.pyqtSlot(str)
    def _on_update_check_result(self, payload_text):
        is_ru = self.parent.current_interface_language == "ru"
        self._update_in_progress = False
        self._update_phase = "idle"
        self._set_update_controls_enabled(True)
        self._hide_update_progress()

        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {"status": "error", "error": "Не удалось обработать ответ от сервера обновлений." if is_ru else "Failed to parse update response."}

        status = payload.get("status")
        latest_version = payload.get("latest_version") or APP_VERSION

        if status == "cancelled" or self._update_cancel_requested.is_set():
            self._update_cancel_requested.clear()
            self._cleanup_update_temp_dir()
            QMessageBox.information(
                self,
                settings_text(self.parent.current_interface_language, "update"),
                "Проверка обновлений отменена." if is_ru else "Update check was canceled."
            )
            return

        if status == "error":
            QMessageBox.warning(
                self,
                "Ошибка обновления" if is_ru else "Update error",
                payload.get("error", "Unknown update error.")
            )
            return

        if status == "up_to_date":
            QMessageBox.information(
                self,
                "Обновление" if is_ru else "Update",
                f"У вас уже актуальная версия: V{APP_VERSION}" if is_ru else f"You already have the latest version: V{APP_VERSION}"
            )
            return

        if status in ("no_asset", "invalid_asset"):
            msg = QMessageBox(self)
            msg.setWindowTitle(settings_text(self.parent.current_interface_language, "update"))
            msg.setText(
                "В релизе нет подходящего файла для автообновления. Открыть страницу релизов?"
                if is_ru else
                "No compatible auto-update asset found in the release. Open releases page?"
            )
            msg.setIcon(QMessageBox.Information)
            msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            yes_btn = msg.addButton(settings_text(self.parent.current_interface_language, "open"), QMessageBox.YesRole)
            msg.addButton(settings_text(self.parent.current_interface_language, "cancel"), QMessageBox.NoRole)
            msg.exec_()
            if msg.clickedButton() == yes_btn:
                webbrowser.open(GITHUB_RELEASES_PAGE)
            return

        if status == "ready":
            asset_name = payload.get("asset_name") or f"ClicknTranslate-v{latest_version}.zip"
            asset_url = payload.get("asset_url")
            checksum_url = payload.get("checksum_url")
            if not asset_url:
                QMessageBox.warning(
                    self,
                    "Ошибка обновления" if is_ru else "Update error",
                    "Некорректный URL файла обновления." if is_ru else "Invalid update asset URL."
                )
                return

            confirm = QMessageBox(self)
            confirm.setWindowTitle("Доступно обновление" if is_ru else "Update available")
            confirm.setIcon(QMessageBox.Question)
            confirm.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            confirm.setText(
                f"Найдена новая версия: V{latest_version}\nТекущая версия: V{APP_VERSION}\n\nУстановить сейчас?"
                if is_ru else
                f"New version found: V{latest_version}\nCurrent version: V{APP_VERSION}\n\nInstall now?"
            )
            yes_btn = confirm.addButton(settings_text(self.parent.current_interface_language, "install"), QMessageBox.YesRole)
            confirm.addButton(settings_text(self.parent.current_interface_language, "later"), QMessageBox.NoRole)
            confirm.exec_()
            if confirm.clickedButton() != yes_btn:
                return

            self._start_update_download(asset_url, asset_name, latest_version, checksum_url)

    def _start_update_download(self, asset_url, asset_name, latest_version, checksum_url=""):
        is_ru = self.parent.current_interface_language == "ru"
        self._update_in_progress = True
        self._update_phase = "preparing_download"
        self._update_temp_dir = ""
        self._update_cancel_requested.clear()
        self._set_update_controls_enabled(False, "Скачивание..." if is_ru else "Downloading...")
        self._show_update_progress("Подготовка загрузки..." if is_ru else "Preparing download...", determinate=False)
        worker = threading.Thread(
            target=self._download_and_prepare_update,
            args=(asset_url, asset_name, latest_version, checksum_url),
            daemon=True
        )
        worker.start()

    def _pick_update_asset(self, assets):
        zip_assets = []
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(".zip") and asset.get("browser_download_url"):
                zip_assets.append(asset)
        if not zip_assets:
            return None

        def _score(a):
            name = (a.get("name") or "").lower()
            if any(token in name for token in ("tesseract", "hymt", "hy-mt", "model", "runtime")):
                return -1
            score = 0
            if "clickntranslate" in name:
                score += 50
            if re.search(r"clickntranslate-v?\d", name):
                score += 30
            if "win" in name or "windows" in name:
                score += 20
            if "x64" in name or "win64" in name:
                score += 10
            if "portable" in name:
                score += 10
            return score

        candidates = [asset for asset in zip_assets if _score(asset) >= 0]
        if not candidates:
            return None
        return sorted(candidates, key=_score, reverse=True)[0]

    def _pick_checksum_url(self, assets, asset_name):
        if not asset_name:
            return ""
        base_name = re.sub(r"\.zip$", "", asset_name.lower())
        direct_name = f"{asset_name.lower()}"
        direct_txt_name = f"{direct_name}.txt"
        candidates = set()
        candidates.update({
            f"{base_name}.sha256",
            f"{base_name}.sha256.txt",
            f"{asset_name.lower()}.sha256",
            f"{asset_name.lower()}.sha256.txt",
            f"{base_name}.sha256sum",
            f"{base_name}.sha256sum.txt",
            direct_txt_name,
        })

        for asset in assets:
            name = (asset.get("name") or "").lower()
            if "sha256" not in name:
                continue
            if name == direct_name + ".sha256" or name == direct_name + ".sha256.txt" or name == direct_txt_name:
                return asset.get("browser_download_url", "")
            if ("." + base_name + ".") in name:
                return asset.get("browser_download_url", "")
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name in candidates:
                return asset.get("browser_download_url", "")
        return ""

    def _read_checksum(self, checksum_path, archive_name):
        try:
            with open(checksum_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return ""
        archive_name = archive_name.lower()
        for line in content.splitlines():
            parts = re.findall(r"[0-9a-fA-F]{64}", line)
            if not parts:
                continue
            low_line = line.lower()
            if archive_name in low_line:
                return parts[0].lower()
        for line in content.splitlines():
            tokens = line.strip().split()
            if len(tokens) >= 2 and re.fullmatch(r"[0-9a-fA-F]{64}", tokens[0]):
                if tokens[1].strip("*") == archive_name:
                    return tokens[0].lower()
        for line in content.splitlines():
            token = re.search(r"[0-9a-fA-F]{64}", line)
            if token:
                return token.group(0).lower()
        return ""

    def _compute_sha256(self, filepath):
        digest = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
        except Exception:
            return ""
        return digest.hexdigest().lower()

    def _download_file(self, url, destination_path, timeout=120, progress_callback=None, cancel_callback=None):
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            try:
                total_bytes = int((r.headers.get("Content-Length") or "0").strip() or "0")
            except Exception:
                total_bytes = 0
            downloaded_bytes = 0
            if cancel_callback and cancel_callback():
                raise UpdateCancelledError("Обновление отменено пользователем.")
            if progress_callback:
                try:
                    progress_callback(downloaded_bytes, total_bytes)
                except Exception:
                    pass
            with open(destination_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if cancel_callback and cancel_callback():
                        raise UpdateCancelledError("Обновление отменено пользователем.")
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        if progress_callback:
                            try:
                                progress_callback(downloaded_bytes, total_bytes)
                            except Exception:
                                pass

    def _download_and_prepare_update(self, asset_url, asset_name, latest_version, checksum_url=""):
        temp_dir = None
        try:
            is_ru = getattr(getattr(self, "parent", None), "current_interface_language", "en") == "ru"
            stage_download = "Загрузка файла обновления..." if is_ru else "Downloading update package..."
            stage_checksum = "Загрузка контрольной суммы..." if is_ru else "Downloading checksum..."
            stage_verify = "Проверка контрольной суммы..." if is_ru else "Verifying checksum..."
            stage_prepare = "Подготовка обновления..." if is_ru else "Preparing update..."

            def _emit_stage_text(stage_text):
                QMetaObject.invokeMethod(
                    self,
                    "_on_update_progress_text",
                    Qt.QueuedConnection,
                    QtCore.Q_ARG(str, stage_text)
                )

            def _emit_download_progress(stage_text, downloaded, total):
                QMetaObject.invokeMethod(
                    self,
                    "_on_update_download_progress",
                    Qt.QueuedConnection,
                    QtCore.Q_ARG(str, stage_text),
                    QtCore.Q_ARG(int, int(downloaded)),
                    QtCore.Q_ARG(int, int(total))
                )

            temp_dir = tempfile.mkdtemp(prefix="clickntranslate_update_")
            self._update_temp_dir = temp_dir
            safe_name = asset_name or f"ClicknTranslate-v{latest_version}.zip"
            zip_path = os.path.join(temp_dir, safe_name)
            if not zip_path.lower().endswith(".zip"):
                zip_path = zip_path + ".zip"

            self._check_update_cancel_requested()
            self._update_phase = "downloading"
            _emit_stage_text(stage_download)
            self._download_file(
                asset_url,
                zip_path,
                timeout=120,
                progress_callback=lambda done, total: _emit_download_progress(stage_download, done, total),
                cancel_callback=lambda: self._update_cancel_requested.is_set()
            )
            self._check_update_cancel_requested()
            if checksum_url:
                checksum_path = os.path.join(temp_dir, f"{safe_name}.sha256")
                self._update_phase = "checksum"
                _emit_stage_text(stage_checksum)
                self._download_file(
                    checksum_url,
                    checksum_path,
                    timeout=120,
                    progress_callback=lambda done, total: _emit_download_progress(stage_checksum, done, total),
                    cancel_callback=lambda: self._update_cancel_requested.is_set()
                )
                self._check_update_cancel_requested()
                self._update_phase = "verifying"
                _emit_stage_text(stage_verify)
                expected = self._read_checksum(checksum_path, safe_name)
                if expected:
                    actual = self._compute_sha256(zip_path)
                    if not actual:
                        raise RuntimeError("Не удалось вычислить SHA256 для загруженного архива.")
                    if actual != expected:
                        raise RuntimeError("Контрольная сумма обновления не совпала (checksum mismatch).")
            if not zipfile.is_zipfile(zip_path):
                raise RuntimeError("Скачанный файл не является zip архивом.")

            self._check_update_cancel_requested()
            self._update_phase = "preparing"
            _emit_stage_text(stage_prepare)
            self._update_phase = "applying"
            ok, err = self._launch_zip_updater(zip_path)
            if not ok:
                raise RuntimeError(err or "Updater launch failed")

            # Дополнительная страховка: если скрипт автозамены не перезапустил приложение
            # (например, из-за ошибки запуска внешнего процесса), через паузу запускаем запасной запуск.
            self._schedule_update_restart_fallback()

            QMetaObject.invokeMethod(
                self,
                "_on_update_ready_to_restart",
                Qt.QueuedConnection,
                QtCore.Q_ARG(str, latest_version)
            )
        except UpdateCancelledError:
            self._cleanup_update_temp_dir()
            QMetaObject.invokeMethod(
                self,
                "_on_update_cancelled",
                Qt.QueuedConnection
            )
        except Exception as e:
            try:
                self._cleanup_update_temp_dir()
            except Exception:
                pass
            try:
                if hasattr(self, "update_btn"):
                    QMetaObject.invokeMethod(
                        self,
                        "_restore_update_button_after_download",
                        Qt.QueuedConnection
                    )
            except Exception:
                pass
            QMetaObject.invokeMethod(
                self,
                "_on_update_failed",
                Qt.QueuedConnection,
                QtCore.Q_ARG(str, str(e))
            )

    def _powershell_launch_candidates(self):
        system_root = os.environ.get("SystemRoot") or r"C:\Windows"
        candidates = [
            os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
            os.path.join(system_root, "Sysnative", "WindowsPowerShell", "v1.0", "powershell.exe"),
            "powershell.exe",
            "powershell",
        ]
        unique = []
        for candidate in candidates:
            if candidate and candidate not in unique:
                unique.append(candidate)
        return unique

    def _launch_hidden_powershell_script(self, script_path, extra_args):
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        last_err = None
        for candidate in SettingsWindow._powershell_launch_candidates(self):
            try:
                subprocess.Popen(
                    [
                        candidate,
                        "-NoProfile",
                        "-ExecutionPolicy", "Bypass",
                        "-WindowStyle", "Hidden",
                        "-File", script_path,
                        *extra_args,
                    ],
                    creationflags=create_no_window
                )
                return True, None
            except Exception as e:
                last_err = e
                continue
        return False, last_err

    def _schedule_update_restart_fallback(self, delay_seconds=14, attempts=45, interval_seconds=2):
        try:
            exe_path = os.path.abspath(sys.executable)
            if not exe_path or not os.path.isfile(exe_path):
                return

            current_pid = os.getpid()
            delay_seconds = max(1, int(delay_seconds))
            attempts = max(1, int(attempts))
            interval_seconds = max(1, int(interval_seconds))
            exe_dir = os.path.dirname(exe_path)
            process_name = os.path.splitext(os.path.basename(exe_path))[0]

            fd, script_path = tempfile.mkstemp(prefix="clickntranslate_restart_", suffix=".ps1")
            os.close(fd)
            script = r"""param(
    [string]$ExePath,
    [string]$ExeDir,
    [string]$ProcessName,
    [int]$TargetPid,
    [int]$InitialDelay,
    [int]$Attempts,
    [int]$WaitSeconds
)
$logPath = Join-Path ([System.IO.Path]::GetTempPath()) "clickntranslate_update.log"
$ErrorActionPreference = 'Stop'

function Write-UpdateLog {
    param([string]$Message)
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'
    Add-Content -Path $logPath -Value "[$ts] $Message" -ErrorAction SilentlyContinue
}

Write-UpdateLog "Fallback watcher start: ExePath=$ExePath; TargetPid=$TargetPid; Attempts=$Attempts"

try {
    Start-Sleep -Seconds $InitialDelay
    for ($i = 0; $i -lt $Attempts; $i++) {
        if (Get-Process -Id $TargetPid -ErrorAction SilentlyContinue) {
            Start-Sleep -Seconds $WaitSeconds
            continue
        }
        if (Get-Process -Name $ProcessName -ErrorAction SilentlyContinue) {
            Write-UpdateLog "Fallback skip: process $ProcessName is already running"
            break
        }
        if (-not (Test-Path -LiteralPath $ExePath)) {
            Write-UpdateLog "Fallback wait: executable is missing: $ExePath"
            Start-Sleep -Seconds $WaitSeconds
            continue
        }
        Write-UpdateLog "Fallback launching executable: $ExePath"
        Start-Process -FilePath $ExePath -WorkingDirectory $ExeDir
        Write-UpdateLog "Fallback launch requested"
        break
    }
}
catch {
    Write-UpdateLog ("Fallback watcher failed: " + $_.Exception.Message)
}
finally {
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
"""
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script)

            ok, err = SettingsWindow._launch_hidden_powershell_script(
                self,
                script_path,
                [
                    "-ExePath", exe_path,
                    "-ExeDir", exe_dir,
                    "-ProcessName", process_name,
                    "-TargetPid", str(current_pid),
                    "-InitialDelay", str(delay_seconds),
                    "-Attempts", str(attempts),
                    "-WaitSeconds", str(interval_seconds),
                ]
            )
            if not ok:
                print(f"Could not launch update restart fallback: {err}")
        except Exception as e:
            print(f"Could not schedule update restart fallback: {e}")

    def _launch_zip_updater(self, zip_path):
        if not getattr(sys, "frozen", False):
            return False, "Auto-update is available only in packaged app"

        app_dir = os.path.dirname(os.path.abspath(sys.executable))
        exe_name = os.path.basename(sys.executable)
        current_pid = os.getpid()

        fd, script_path = tempfile.mkstemp(prefix="clickntranslate_updater_", suffix=".ps1")
        os.close(fd)

        script = r"""param(
    [string]$AppDir,
    [string]$ZipPath,
    [int]$TargetPid,
    [string]$ExeName
)
$logPath = Join-Path ([System.IO.Path]::GetTempPath()) "clickntranslate_update.log"
$ErrorActionPreference = 'Stop'

function Write-UpdateLog {
    param([string]$Message)
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'
    Add-Content -Path $logPath -Value "[$ts] $Message" -ErrorAction SilentlyContinue
}

Write-UpdateLog "Updater start: AppDir=$AppDir; ZipPath=$ZipPath; Exe=$ExeName; TargetPid=$TargetPid"

$extractDir = $null
try {
    $deadline = (Get-Date).AddSeconds(120)
    while (Get-Process -Id $TargetPid -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) {
            Write-UpdateLog "Application did not exit in time, force terminating process $TargetPid"
            try { Stop-Process -Id $TargetPid -Force -ErrorAction SilentlyContinue } catch {}
            break
        }
        Start-Sleep -Milliseconds 300
    }

    Write-UpdateLog "Target app process is not running; start applying update"
    $extractDir = Join-Path ([System.IO.Path]::GetTempPath()) ("clickntranslate_extract_" + [Guid]::NewGuid().ToString("N"))
    New-Item -Path $extractDir -ItemType Directory -Force | Out-Null
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $extractDir -Force
    Write-UpdateLog "Archive unpacked to $extractDir"

    $exeMatch = Get-ChildItem -LiteralPath $extractDir -Filter $ExeName -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($exeMatch) {
        $payloadRoot = $exeMatch.DirectoryName
    } else {
        throw "Update archive does not contain $ExeName"
    }
    Write-UpdateLog "Payload root: $payloadRoot"

    $payloadHasInternal = Test-Path -LiteralPath (Join-Path $payloadRoot "_internal")
    Get-ChildItem -LiteralPath $AppDir -Force | ForEach-Object {
        if ($_.Name -ieq "data") { continue }
        Write-UpdateLog "Removing existing program item: $($_.FullName)"
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }

    Get-ChildItem -LiteralPath $payloadRoot -Force | ForEach-Object {
        if ($_.Name -ieq "data") { continue }
        Write-UpdateLog "Copying update item: $($_.FullName)"
        Copy-Item -LiteralPath $_.FullName -Destination $AppDir -Recurse -Force
    }

    if ($payloadHasInternal -and -not (Test-Path -LiteralPath (Join-Path $AppDir "_internal"))) {
        throw "Update payload copy failed: _internal directory is missing"
    }

    $targetExe = Join-Path $AppDir $ExeName
    if (-not (Test-Path -LiteralPath $targetExe)) {
        Write-UpdateLog "Target executable not found by direct path, searching recursively"
        $fallback = Get-ChildItem -LiteralPath $AppDir -Filter $ExeName -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($fallback) {
            $targetExe = $fallback.FullName
        }
    }
    if (-not (Test-Path -LiteralPath $targetExe)) {
        throw "Target executable not found: $ExeName"
    }

    Write-UpdateLog "Starting updated executable: $targetExe"
    Start-Process -FilePath $targetExe -WorkingDirectory $AppDir
    Write-UpdateLog "Updated executable started"
}
catch {
    Write-UpdateLog ("Updater failed: " + $_.Exception.Message)
    try {
        $fallbackExe = Join-Path $AppDir $ExeName
        if (Test-Path -LiteralPath $fallbackExe) {
            Write-UpdateLog "Launching fallback executable after updater failure: $fallbackExe"
            Start-Process -FilePath $fallbackExe -WorkingDirectory $AppDir
        }
    } catch {}
}
finally {
    if ($extractDir -and (Test-Path -LiteralPath $extractDir)) {
        Remove-Item -LiteralPath $extractDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
"""
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script)
        except Exception as e:
            return False, f"Failed to create updater script: {e}"

        try:
            ok, err = SettingsWindow._launch_hidden_powershell_script(
                self,
                script_path,
                [
                    "-AppDir", app_dir,
                    "-ZipPath", zip_path,
                    "-TargetPid", str(current_pid),
                    "-ExeName", exe_name,
                ]
            )
            if ok:
                return True, None
            return False, f"Failed to launch updater: {err}"
        except Exception as e:
            return False, f"Failed to launch updater: {e}"

    @QtCore.pyqtSlot()
    def _restore_update_button_after_download(self):
        self._update_in_progress = False
        self._update_phase = "idle"
        self._update_cancel_requested.clear()
        self._cleanup_update_temp_dir()
        self._set_update_controls_enabled(True)
        self._hide_update_progress()

    @QtCore.pyqtSlot()
    def _on_update_cancelled(self):
        self._update_in_progress = False
        self._update_phase = "idle"
        self._cleanup_update_temp_dir()
        self._update_cancel_requested.clear()
        self._set_update_controls_enabled(True)
        self._hide_update_progress()

        is_ru = self.parent.current_interface_language == "ru"
        QMessageBox.information(
            self,
            "Обновление" if is_ru else "Update",
            "Обновление отменено. Временные файлы удалены."
            if is_ru else
            "Update canceled. Temporary files were removed."
        )

    @pyqtSlot(str)
    def _on_update_failed(self, error_text):
        self._update_in_progress = False
        self._update_phase = "idle"
        self._cleanup_update_temp_dir()
        self._update_cancel_requested.clear()
        self._set_update_controls_enabled(True)
        if hasattr(self, "_update_progress") and self._update_progress is not None:
            try:
                self._update_progress.close()
            except Exception:
                pass
            self._update_progress = None

        is_ru = self.parent.current_interface_language == "ru"
        QMessageBox.warning(
            self,
            "Ошибка обновления" if is_ru else "Update error",
            ("Не удалось установить обновление:\n" if is_ru else "Failed to install update:\n") + str(error_text)
        )

    @pyqtSlot(str)
    def _on_update_ready_to_restart(self, latest_version):
        self._update_in_progress = False
        self._update_phase = "idle"
        self._update_temp_dir = ""
        self._update_cancel_requested.clear()
        if hasattr(self, "_update_progress") and self._update_progress is not None:
            try:
                self._update_progress.close()
            except Exception:
                pass
            self._update_progress = None

        is_ru = self.parent.current_interface_language == "ru"
        QMessageBox.information(
            self,
            "Обновление" if is_ru else "Update",
            (
                f"Обновление до V{latest_version} загружено.\nПриложение перезапустится автоматически."
                if is_ru else
                f"Update V{latest_version} is downloaded.\nThe app will restart automatically."
            )
        )
        try:
            self.parent.exit_app()
        except Exception:
            QApplication.instance().quit()

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
        theme = THEMES_LOCAL.get(self.parent.current_theme) or next(iter(THEMES_LOCAL.values()))
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
                hotkey_style = "background-color: #2a2a2a; color: #ffffff; border: 1px solid #ffffff; padding: 4px;"
            else:
                hotkey_style = "background-color: #ffffff; color: #000000; border: 1px solid #000000; padding: 4px;"
            self.copy_hotkey_input.setStyleSheet(hotkey_style)
            self.translate_hotkey_input.setStyleSheet(hotkey_style)
            self.fullscreen_translate_hotkey_input.setStyleSheet(hotkey_style)
            self.translate_selection_hotkey_input.setStyleSheet(hotkey_style)
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

    def eventFilter(self, obj, event):
        if obj is getattr(self, "ocr_engine_combo", None) and event.type() in (
            QtCore.QEvent.Resize,
            QtCore.QEvent.Show,
            QtCore.QEvent.EnabledChange,
        ):
            self._sync_ocr_engine_delete_button()
        if obj is getattr(self, "translator_combo", None) and event.type() in (
            QtCore.QEvent.Resize,
            QtCore.QEvent.Show,
            QtCore.QEvent.EnabledChange,
        ):
            self._sync_translator_engine_delete_button()
        return super().eventFilter(obj, event)

    def _position_ocr_engine_delete_button(self):
        combo = getattr(self, "ocr_engine_combo", None)
        button = getattr(self, "ocr_engine_delete_btn", None)
        if combo is None or button is None:
            return
        button_size = 14
        button.setFixedSize(button_size, button_size)
        x_pos = max(0, combo.width() - 38)
        y_pos = max(0, (combo.height() - button_size) // 2)
        button.move(x_pos, y_pos)
        button.raise_()

    def _sync_ocr_engine_delete_button(self):
        button = getattr(self, "ocr_engine_delete_btn", None)
        combo = getattr(self, "ocr_engine_combo", None)
        if button is None or combo is None:
            return
        self._position_ocr_engine_delete_button()
        show_button = (
            combo.currentText() == "Tesseract"
            and bool(self._find_local_tesseract_exe())
            and not self._tesseract_install_in_progress
        )
        button.setVisible(show_button)
        button.setEnabled(show_button)

    def _position_translator_engine_delete_button(self):
        combo = getattr(self, "translator_combo", None)
        button = getattr(self, "translator_engine_delete_btn", None)
        if combo is None or button is None:
            return
        button_size = 14
        button.setFixedSize(button_size, button_size)
        x_pos = max(0, combo.width() - 38)
        y_pos = max(0, (combo.height() - button_size) // 2)
        button.move(x_pos, y_pos)
        button.raise_()

    def _sync_translator_engine_delete_button(self):
        button = getattr(self, "translator_engine_delete_btn", None)
        combo = getattr(self, "translator_combo", None)
        if button is None or combo is None:
            return
        self._position_translator_engine_delete_button()
        show_button = (
            self._current_translator_engine_from_combo() == HYMT_ENGINE_KEY
            and self._hymt_installed()
            and not self._hymt_install_in_progress
        )
        button.setVisible(show_button)
        button.setEnabled(show_button)

    def _restore_settings_view(self):
        try:
            app = QApplication.instance()
            if app is not None:
                app.setQuitOnLastWindowClosed(False)
            if self.parent is not None:
                if not self.parent.isVisible():
                    self.parent.show()
            if not self.isVisible():
                self.show()
        except Exception:
            pass

    def _set_parent_topmost_for_tesseract_install(self, enabled):
        parent = getattr(self, "parent", None)
        if parent is None:
            return
        try:
            is_topmost = bool(parent.windowFlags() & Qt.WindowStaysOnTopHint)
            if not enabled and self._parent_was_topmost_before_tesseract is None:
                self._parent_was_topmost_before_tesseract = is_topmost
            should_be_topmost = enabled and bool(self._parent_was_topmost_before_tesseract)
            if is_topmost == should_be_topmost:
                return
            was_visible = parent.isVisible()
            parent.setWindowFlag(Qt.WindowStaysOnTopHint, should_be_topmost)
            if was_visible:
                parent.show()
        except Exception:
            pass

    def _restore_parent_topmost_after_tesseract_install(self):
        self._set_parent_topmost_for_tesseract_install(True)
        self._parent_was_topmost_before_tesseract = None

    def _portable_app_dir(self):
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(sys.argv[0]))

    def _local_tesseract_dir(self):
        return os.path.join(self._portable_app_dir(), "ocr", "tesseract")

    def _find_tesseract_exe_under(self, root_dir):
        if not root_dir or not os.path.isdir(root_dir):
            return ""
        direct_path = os.path.join(root_dir, "tesseract.exe")
        if os.path.isfile(direct_path):
            return direct_path
        for current_root, _dirs, files in os.walk(root_dir):
            for name in files:
                if name.lower() == "tesseract.exe":
                    return os.path.join(current_root, name)
        return ""

    def _find_local_tesseract_exe(self):
        return self._find_tesseract_exe_under(self._local_tesseract_dir())

    def _find_available_tesseract_exe(self):
        local_exe = self._find_local_tesseract_exe()
        if local_exe:
            return local_exe
        path_exe = shutil.which("tesseract")
        if path_exe:
            return path_exe
        for path in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "Tesseract-OCR", "tesseract.exe"),
        ]:
            if os.path.isfile(path):
                return path
        return ""

    def _reset_tesseract_runtime_cache(self):
        try:
            import ocr
            if hasattr(ocr, "ScreenCaptureOverlay"):
                ocr.ScreenCaptureOverlay._tesseract_cmd_cache = None
            ocr._ocr_config_cache = None
            ocr._ocr_config_mtime = 0
        except Exception:
            pass

    def _set_ocr_combo_silently(self, engine_name):
        if not hasattr(self, "ocr_engine_combo"):
            return
        self.ocr_engine_combo.blockSignals(True)
        self.ocr_engine_combo.setCurrentText(engine_name)
        self.ocr_engine_combo.blockSignals(False)
        self._sync_ocr_engine_delete_button()

    def handle_ocr_engine_change(self, text):
        if text != "Tesseract":
            self.save_ocr_engine(text)
            return

        self.previous_ocr_engine = self.parent.config.get("ocr_engine", "Windows")
        if self._find_available_tesseract_exe():
            self.save_ocr_engine("Tesseract")
            return

        is_ru = self.parent.current_interface_language == "ru"
        msg = QMessageBox(self)
        msg.setWindowTitle("Tesseract не найден" if is_ru else "Tesseract not found")
        msg.setText(
            "Tesseract-OCR не найден. Скачать и установить локально?"
            if is_ru else
            "Tesseract-OCR was not found. Download and install it locally?"
        )
        msg.setIcon(QMessageBox.Question)
        msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        msg.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        yes_btn = msg.addButton("Установить" if is_ru else "Install", QMessageBox.YesRole)
        msg.addButton("Отмена" if is_ru else "Cancel", QMessageBox.NoRole)
        msg.exec_()
        if msg.clickedButton() == yes_btn:
            self.start_tesseract_install()
            return

        self._set_ocr_combo_silently(self.previous_ocr_engine or "Windows")
        self.save_ocr_engine(self.previous_ocr_engine or "Windows")

    def _delete_local_tesseract_dir(self):
        tesseract_dir = self._local_tesseract_dir()
        if not os.path.isdir(tesseract_dir):
            return True, ""
        try:
            shutil.rmtree(tesseract_dir, ignore_errors=False)
            self._reset_tesseract_runtime_cache()
            return True, ""
        except Exception as e:
            return False, str(e)

    def save_ocr_engine(self, text):
        self.auto_save_setting("ocr_engine", text)

    def _local_hymt_dir(self):
        return os.path.join(self._portable_app_dir(), "translators", "hymt")

    def _delete_local_hymt_dir(self):
        hymt_dir = self._local_hymt_dir()
        if not os.path.isdir(hymt_dir):
            return True, ""
        try:
            shutil.rmtree(hymt_dir, ignore_errors=False)
            self._reset_hymt_runtime_cache()
            return True, ""
        except Exception as e:
            return False, str(e)

    def _find_hymt_model_under(self, root_dir):
        if not root_dir or not os.path.isdir(root_dir):
            return ""
        direct_path = os.path.join(root_dir, HYMT_MODEL_FILE)
        if os.path.isfile(direct_path):
            return direct_path
        for current_root, _dirs, files in os.walk(root_dir):
            for name in files:
                lower = name.lower()
                if lower == HYMT_MODEL_FILE.lower() or (lower.endswith(".gguf") and "hy-mt" in lower):
                    return os.path.join(current_root, name)
        return ""

    def _find_hymt_runner_under(self, root_dir):
        if not root_dir or not os.path.isdir(root_dir):
            return ""
        candidates = ("hymt.exe", "llama-cli.exe", "llama-run.exe", "main.exe")
        for name in candidates:
            direct_path = os.path.join(root_dir, name)
            if os.path.isfile(direct_path):
                return direct_path
        for current_root, _dirs, files in os.walk(root_dir):
            lower_files = {name.lower(): name for name in files}
            for candidate in candidates:
                if candidate in lower_files:
                    return os.path.join(current_root, lower_files[candidate])
        return ""

    def _hymt_installed(self):
        root_dir = self._local_hymt_dir()
        return bool(self._find_hymt_model_under(root_dir) and self._find_hymt_runner_under(root_dir))

    def _reset_hymt_runtime_cache(self):
        try:
            import translater
            if hasattr(translater, "_hymt_runtime_cache"):
                translater._hymt_runtime_cache = None
            translater._translator_config_cache = None
            translater._translator_config_mtime = 0
        except Exception:
            pass

    def _set_translator_combo_silently(self, engine_name):
        if not hasattr(self, "translator_combo"):
            return
        idx = 0
        if hasattr(self, "_translator_engines"):
            try:
                idx = self._translator_engines.index(str(engine_name).lower())
            except ValueError:
                idx = 0
        self.translator_combo.blockSignals(True)
        self.translator_combo.setCurrentIndex(idx)
        self.translator_combo.blockSignals(False)
        self._sync_translator_engine_delete_button()

    def _current_translator_engine_from_combo(self):
        combo = getattr(self, "translator_combo", None)
        if combo is None:
            return "google"
        idx = combo.currentIndex()
        if hasattr(self, "_translator_engines") and 0 <= idx < len(self._translator_engines):
            return self._translator_engines[idx]
        return "google"

    def _on_translator_changed(self, idx):
        # Сохраняем имя движка из списка
        if hasattr(self, '_translator_engines') and 0 <= idx < len(self._translator_engines):
            value = self._translator_engines[idx]
        else:
            value = "google"
        if value != HYMT_ENGINE_KEY:
            self.auto_save_setting("translator_engine", value)
            return

        self.previous_translator_engine = self.parent.config.get("translator_engine", "Google").lower()
        if self._hymt_installed():
            self.auto_save_setting("translator_engine", HYMT_ENGINE_KEY)
            return

        is_ru = self.parent.current_interface_language == "ru"
        msg = QMessageBox(self)
        msg.setWindowTitle("Hy-MT не найден" if is_ru else "Hy-MT not found")
        msg.setText(
            "Локальная модель Hy-MT не установлена. Скачать и установить офлайн-пакет перевода?\n\n"
            "Будет скачано около 1.2 ГБ: модель Hy-MT и локальный llama.cpp runtime."
            if is_ru else
            "The local Hy-MT model is not installed. Download and install the offline translation package?\n\n"
            "About 1.2 GB will be downloaded: the Hy-MT model and local llama.cpp runtime."
        )
        msg.setIcon(QMessageBox.Question)
        msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        msg.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        yes_btn = msg.addButton("Установить" if is_ru else "Install", QMessageBox.YesRole)
        msg.addButton("Отмена" if is_ru else "Cancel", QMessageBox.NoRole)
        msg.exec_()
        if msg.clickedButton() == yes_btn:
            self.start_hymt_install()
            return

        fallback = self.previous_translator_engine or "google"
        self._set_translator_combo_silently(fallback)
        self.auto_save_setting("translator_engine", fallback)

    def start_download_thread(self):
        self.start_tesseract_install()

    def start_tesseract_install(self):
        if self._tesseract_install_in_progress:
            return
        is_ru = self.parent.current_interface_language == "ru"
        self._tesseract_install_in_progress = True
        self._tesseract_install_phase = "starting"
        self._tesseract_cancel_requested.clear()
        self._tesseract_temp_dir = ""
        self.ocr_engine_combo.setEnabled(False)
        self._sync_ocr_engine_delete_button()
        self._set_parent_topmost_for_tesseract_install(False)
        self._show_tesseract_progress("Подготовка установки Tesseract..." if is_ru else "Preparing Tesseract install...", 0)
        threading.Thread(target=self._install_tesseract_worker, daemon=True).start()

    def _get_tesseract_bundle_url(self, is_x64=True):
        if not is_x64:
            raise RuntimeError("Автоматическая установка Tesseract поддерживает только Windows x64.")
        return TESSERACT_BUNDLE_URL_WIN64

    def _emit_tesseract_progress(self, text, percent=0, determinate=True):
        QMetaObject.invokeMethod(
            self,
            "_on_tesseract_progress",
            Qt.QueuedConnection,
            QtCore.Q_ARG(str, str(text)),
            QtCore.Q_ARG(int, int(max(0, min(100, percent)))),
            QtCore.Q_ARG(bool, bool(determinate))
        )

    def _check_tesseract_cancel_requested(self):
        if self._tesseract_cancel_requested.is_set():
            raise TesseractInstallCancelledError("Tesseract installation canceled by user.")

    def _install_tesseract_worker(self):
        temp_dir = ""
        backup_dir = ""
        final_dir = self._local_tesseract_dir()
        try:
            is_ru = getattr(getattr(self, "parent", None), "current_interface_language", "en") == "ru"
            machine = platform.machine().lower()
            is_x64 = machine in ("amd64", "x86_64")
            bundle_url = self._get_tesseract_bundle_url(is_x64)
            temp_dir = tempfile.mkdtemp(prefix="clickntranslate_tesseract_")
            self._tesseract_temp_dir = temp_dir
            bundle_path = os.path.join(temp_dir, TESSERACT_BUNDLE_NAME_WIN64)
            extract_dir = os.path.join(temp_dir, "extract")
            os.makedirs(extract_dir, exist_ok=True)

            download_text = "Загрузка Tesseract..." if is_ru else "Downloading Tesseract..."
            self._tesseract_install_phase = "downloading"
            self._emit_tesseract_progress(download_text, 1)

            def download_progress(done, total):
                if total > 0:
                    percent = 1 + int((done * 72) / total)
                else:
                    percent = 6
                self._emit_tesseract_progress(download_text, percent)

            self._download_file(
                bundle_url,
                bundle_path,
                timeout=180,
                progress_callback=download_progress,
                cancel_callback=lambda: self._tesseract_cancel_requested.is_set(),
            )
            self._check_tesseract_cancel_requested()
            if not zipfile.is_zipfile(bundle_path):
                raise RuntimeError("Downloaded Tesseract bundle is not a zip archive.")

            extract_text = "Распаковка Tesseract..." if is_ru else "Extracting Tesseract..."
            self._tesseract_install_phase = "extracting"
            self._emit_tesseract_progress(extract_text, 74)
            with zipfile.ZipFile(bundle_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            self._check_tesseract_cancel_requested()

            tess_exe = self._find_tesseract_exe_under(extract_dir)
            if not tess_exe:
                raise RuntimeError("tesseract.exe not found in Tesseract bundle")

            install_dir = os.path.dirname(tess_exe)

            tessdata_dir = os.path.join(os.path.dirname(tess_exe), "tessdata")
            os.makedirs(tessdata_dir, exist_ok=True)

            models = [
                ("eng", "https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata"),
                ("rus", "https://github.com/tesseract-ocr/tessdata/raw/main/rus.traineddata"),
            ]
            for index, (name, url) in enumerate(models):
                model_path = os.path.join(tessdata_dir, f"{name}.traineddata")
                if os.path.isfile(model_path) and os.path.getsize(model_path) > 1024:
                    continue
                self._check_tesseract_cancel_requested()
                model_text = f"Загрузка языковой модели {name}..." if is_ru else f"Downloading language data {name}..."
                start = 82 + index * 6

                def model_progress(done, total, base=start, label=model_text):
                    if total > 0:
                        percent = base + int((done * 5) / total)
                    else:
                        percent = base
                    self._emit_tesseract_progress(label, percent)

                self._download_file(
                    url,
                    model_path,
                    timeout=180,
                    progress_callback=model_progress,
                    cancel_callback=lambda: self._tesseract_cancel_requested.is_set(),
                )

            self._check_tesseract_cancel_requested()
            self._tesseract_install_phase = "applying"
            self._emit_tesseract_progress("Применение установки..." if is_ru else "Applying install...", 96)
            os.makedirs(os.path.dirname(final_dir), exist_ok=True)
            if os.path.isdir(final_dir):
                backup_dir = f"{final_dir}.backup-{int(time.time())}"
                shutil.move(final_dir, backup_dir)
            shutil.move(install_dir, final_dir)
            if backup_dir and os.path.isdir(backup_dir):
                shutil.rmtree(backup_dir, ignore_errors=True)
                backup_dir = ""

            final_exe = self._find_tesseract_exe_under(final_dir)
            if not final_exe:
                raise RuntimeError("tesseract.exe not found after applying install")

            self._emit_tesseract_progress("Готово" if is_ru else "Done", 100)
            QMetaObject.invokeMethod(
                self,
                "_on_tesseract_install_ready",
                Qt.QueuedConnection,
                QtCore.Q_ARG(str, final_exe)
            )
        except (TesseractInstallCancelledError, UpdateCancelledError):
            if backup_dir and os.path.isdir(backup_dir) and not os.path.isdir(final_dir):
                try:
                    shutil.move(backup_dir, final_dir)
                except Exception:
                    pass
            QMetaObject.invokeMethod(self, "_on_tesseract_install_cancelled", Qt.QueuedConnection)
        except Exception as e:
            if backup_dir and os.path.isdir(backup_dir) and not os.path.isdir(final_dir):
                try:
                    shutil.move(backup_dir, final_dir)
                except Exception:
                    pass
            QMetaObject.invokeMethod(
                self,
                "_on_tesseract_install_failed",
                Qt.QueuedConnection,
                QtCore.Q_ARG(str, str(e))
            )
        finally:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            self._tesseract_temp_dir = ""

    def _show_tesseract_progress(self, text, percent=0, determinate=True):
        is_ru = self.parent.current_interface_language == "ru"
        if not hasattr(self, "progress") or self.progress is None:
            self.progress = TesseractInstallProgressDialog(self)
            self.progress.setWindowTitle("Tesseract")
            self.progress.setCancelButtonText("Отменить" if is_ru else "Cancel")
            self.progress.setWindowModality(Qt.NonModal)
            self.progress.setAutoClose(False)
            self.progress.setAutoReset(False)
            self.progress.setMinimumDuration(0)
            self.progress.setMinimumWidth(430)
            self.progress.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            self.progress.canceled.connect(self._request_tesseract_install_cancel)
            try:
                owner_window = self.window()
                owner_center = owner_window.frameGeometry().center()
                progress_frame = self.progress.frameGeometry()
                progress_frame.moveCenter(owner_center)
                self.progress.move(progress_frame.topLeft())
            except Exception:
                pass
        self.progress.setLabelText(text)
        if determinate:
            self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(100, int(percent))))
        else:
            self.progress.setRange(0, 0)
        if not self.progress.isVisible() and not getattr(self.progress, "_user_minimized", False):
            self.progress.show()

    @QtCore.pyqtSlot(str, int, bool)
    def _on_tesseract_progress(self, text, percent, determinate):
        self._show_tesseract_progress(text, percent, determinate)

    def _hide_tesseract_progress(self):
        if hasattr(self, "progress") and self.progress is not None:
            try:
                self.progress.blockSignals(True)
                try:
                    self.progress.hide()
                finally:
                    self.progress.blockSignals(False)
            except Exception:
                pass

    def _request_tesseract_install_cancel(self):
        if not self._tesseract_install_in_progress:
            return
        is_ru = self.parent.current_interface_language == "ru"
        self._tesseract_cancel_requested.set()
        self._show_tesseract_progress("Отмена установки..." if is_ru else "Canceling install...", 0, False)

    def _finish_tesseract_install_state(self):
        self._tesseract_install_in_progress = False
        self._tesseract_install_phase = "idle"
        self._tesseract_cancel_requested.clear()
        self.ocr_engine_combo.setEnabled(True)
        self._sync_ocr_engine_delete_button()
        self._restore_parent_topmost_after_tesseract_install()

    @QtCore.pyqtSlot(str)
    def _on_tesseract_install_ready(self, tesseract_path):
        self._finish_tesseract_install_state()
        self._hide_tesseract_progress()
        self._restore_settings_view()
        tessdata_dir = os.path.join(os.path.dirname(tesseract_path), "tessdata")
        if os.path.isdir(tessdata_dir):
            os.environ["TESSDATA_PREFIX"] = tessdata_dir
        self._reset_tesseract_runtime_cache()
        self._set_ocr_combo_silently("Tesseract")
        self.save_ocr_engine("Tesseract")
        self._sync_ocr_engine_delete_button()
        is_ru = self.parent.current_interface_language == "ru"
        QMessageBox.information(
            self,
            "Tesseract",
            "Tesseract установлен и готов к работе." if is_ru else "Tesseract is installed and ready."
        )

    @QtCore.pyqtSlot(str)
    def _on_tesseract_install_failed(self, error):
        self._finish_tesseract_install_state()
        self._hide_tesseract_progress()
        self._restore_settings_view()
        prev_engine = self.previous_ocr_engine or "Windows"
        self._set_ocr_combo_silently(prev_engine)
        self.save_ocr_engine(prev_engine)
        is_ru = self.parent.current_interface_language == "ru"
        QMessageBox.warning(
            self,
            "Ошибка Tesseract" if is_ru else "Tesseract error",
            ("Не удалось установить Tesseract:\n" if is_ru else "Failed to install Tesseract:\n") + str(error)
        )

    @QtCore.pyqtSlot()
    def _on_tesseract_install_cancelled(self):
        self._finish_tesseract_install_state()
        self._hide_tesseract_progress()
        self._restore_settings_view()
        prev_engine = self.previous_ocr_engine or "Windows"
        self._set_ocr_combo_silently(prev_engine)
        self.save_ocr_engine(prev_engine)
        is_ru = self.parent.current_interface_language == "ru"
        QMessageBox.information(
            self,
            "Отмена" if is_ru else "Cancelled",
            "Установка Tesseract отменена. Временные файлы удалены."
            if is_ru else
            "Tesseract installation canceled. Temporary files were removed."
        )

    def start_hymt_install(self):
        if self._hymt_install_in_progress or self._tesseract_install_in_progress:
            return
        is_ru = self.parent.current_interface_language == "ru"
        self._hymt_install_in_progress = True
        self._hymt_install_phase = "starting"
        self._hymt_cancel_requested.clear()
        self._hymt_temp_dir = ""
        self.translator_combo.setEnabled(False)
        self._sync_translator_engine_delete_button()
        self._set_parent_topmost_for_tesseract_install(False)
        self._show_hymt_progress(
            "Подготовка установки Hy-MT..." if is_ru else "Preparing Hy-MT install...",
            0
        )
        threading.Thread(target=self._install_hymt_worker, daemon=True).start()

    def _get_hymt_download_plan(self, is_x64=True):
        if not is_x64:
            raise RuntimeError("Автоматическая установка Hy-MT поддерживает только Windows x64.")
        return {
            "runtime": {
                "name": HYMT_RUNTIME_ARCHIVE_NAME_WIN64,
                "url": HYMT_RUNTIME_URL_WIN64,
                "sha256": HYMT_RUNTIME_SHA256,
            },
            "model": {
                "name": HYMT_MODEL_FILE,
                "url": HYMT_MODEL_URL,
                "sha256": HYMT_MODEL_SHA256,
            },
            "docs": [
                {
                    "name": "License.txt",
                    "url": HYMT_LICENSE_URL,
                },
                {
                    "name": "README.md",
                    "url": HYMT_README_URL,
                },
            ],
        }

    def _verify_file_sha256(self, filepath, expected_sha256, label):
        expected = (expected_sha256 or "").strip().lower()
        if not expected:
            return
        actual = self._compute_sha256(filepath)
        if actual != expected:
            raise RuntimeError(
                f"{label} checksum mismatch. Expected {expected}, got {actual or 'unreadable file'}."
            )

    def _emit_hymt_progress(self, text, percent=0, determinate=True):
        QMetaObject.invokeMethod(
            self,
            "_on_hymt_progress",
            Qt.QueuedConnection,
            QtCore.Q_ARG(str, str(text)),
            QtCore.Q_ARG(int, int(max(0, min(100, percent)))),
            QtCore.Q_ARG(bool, bool(determinate))
        )

    def _check_hymt_cancel_requested(self):
        if self._hymt_cancel_requested.is_set():
            raise HyMTInstallCancelledError("Hy-MT installation canceled by user.")

    def _restore_hymt_backup(self, final_dir, backup_dir):
        if not backup_dir or not os.path.isdir(backup_dir):
            return
        try:
            if os.path.isdir(final_dir):
                shutil.rmtree(final_dir, ignore_errors=True)
            shutil.move(backup_dir, final_dir)
        except Exception:
            pass

    def _install_hymt_worker(self):
        temp_dir = ""
        backup_dir = ""
        final_dir = self._local_hymt_dir()
        try:
            is_ru = getattr(getattr(self, "parent", None), "current_interface_language", "en") == "ru"
            machine = platform.machine().lower()
            is_x64 = machine in ("amd64", "x86_64")
            plan = self._get_hymt_download_plan(is_x64)
            temp_dir = tempfile.mkdtemp(prefix="clickntranslate_hymt_")
            self._hymt_temp_dir = temp_dir
            package_root = os.path.join(temp_dir, "package")
            runtime_dir = os.path.join(package_root, "runtime")
            os.makedirs(runtime_dir, exist_ok=True)

            runtime_text = "Загрузка runtime Hy-MT..." if is_ru else "Downloading Hy-MT runtime..."
            self._hymt_install_phase = "downloading"
            self._emit_hymt_progress(runtime_text, 1)

            runtime_zip_path = os.path.join(temp_dir, plan["runtime"]["name"])

            def runtime_progress(done, total):
                if total > 0:
                    percent = 1 + int((done * 10) / total)
                else:
                    percent = 4
                self._emit_hymt_progress(runtime_text, percent)

            self._download_file(
                plan["runtime"]["url"],
                runtime_zip_path,
                timeout=600,
                progress_callback=runtime_progress,
                cancel_callback=lambda: self._hymt_cancel_requested.is_set(),
            )
            self._check_hymt_cancel_requested()
            self._verify_file_sha256(runtime_zip_path, plan["runtime"]["sha256"], plan["runtime"]["name"])
            if not zipfile.is_zipfile(runtime_zip_path):
                raise RuntimeError("Downloaded Hy-MT runtime is not a zip archive.")

            extract_text = "Распаковка runtime Hy-MT..." if is_ru else "Extracting Hy-MT runtime..."
            self._hymt_install_phase = "extracting"
            self._emit_hymt_progress(extract_text, 13)
            with zipfile.ZipFile(runtime_zip_path, "r") as zip_ref:
                zip_ref.extractall(runtime_dir)
            self._check_hymt_cancel_requested()

            runner_path = self._find_hymt_runner_under(package_root)
            if not runner_path:
                raise RuntimeError("Hy-MT runtime must contain llama-cli.exe, llama-run.exe, or hymt.exe.")

            model_text = "Загрузка модели Hy-MT..." if is_ru else "Downloading Hy-MT model..."
            model_path = os.path.join(package_root, plan["model"]["name"])
            self._emit_hymt_progress(model_text, 15)

            def model_progress(done, total):
                if total > 0:
                    percent = 15 + int((done * 75) / total)
                else:
                    percent = 20
                self._emit_hymt_progress(model_text, percent)

            self._download_file(
                plan["model"]["url"],
                model_path,
                timeout=1800,
                progress_callback=model_progress,
                cancel_callback=lambda: self._hymt_cancel_requested.is_set(),
            )
            self._check_hymt_cancel_requested()
            self._verify_file_sha256(model_path, plan["model"]["sha256"], plan["model"]["name"])

            docs_text = "Сохранение лицензии Hy-MT..." if is_ru else "Saving Hy-MT license..."
            self._emit_hymt_progress(docs_text, 92)
            for index, doc in enumerate(plan["docs"]):
                self._check_hymt_cancel_requested()
                doc_path = os.path.join(package_root, doc["name"])
                try:
                    self._download_file(
                        doc["url"],
                        doc_path,
                        timeout=120,
                        progress_callback=None,
                        cancel_callback=lambda: self._hymt_cancel_requested.is_set(),
                    )
                except (HyMTInstallCancelledError, UpdateCancelledError):
                    raise
                except Exception:
                    with open(doc_path, "w", encoding="utf-8") as f:
                        f.write(f"{doc['name']} could not be downloaded automatically.\nSource: {doc['url']}\n")
                self._emit_hymt_progress(docs_text, 92 + index)

            notice_path = os.path.join(package_root, "NOTICE.txt")
            with open(notice_path, "w", encoding="utf-8") as f:
                f.write(
                    HYMT_NOTICE_TEXT
                    + "\n\nModel source: "
                    + HYMT_MODEL_URL
                    + "\nRuntime source: "
                    + HYMT_RUNTIME_URL_WIN64
                    + "\n"
                )

            manifest_path = os.path.join(package_root, "install_manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "engine": HYMT_ENGINE_KEY,
                        "model": plan["model"]["name"],
                        "model_sha256": plan["model"]["sha256"],
                        "runtime": plan["runtime"]["name"],
                        "runtime_sha256": plan["runtime"]["sha256"],
                        "model_url": plan["model"]["url"],
                        "runtime_url": plan["runtime"]["url"],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            model_path = self._find_hymt_model_under(package_root)
            runner_path = self._find_hymt_runner_under(package_root)
            if not model_path:
                raise RuntimeError(f"{HYMT_MODEL_FILE} not found after download.")
            if not runner_path:
                raise RuntimeError("Hy-MT runtime not found after download.")

            self._hymt_install_phase = "applying"
            self._emit_hymt_progress("Применение установки..." if is_ru else "Applying install...", 96)
            os.makedirs(os.path.dirname(final_dir), exist_ok=True)
            if os.path.isdir(final_dir):
                backup_dir = f"{final_dir}.backup-{int(time.time())}"
                shutil.move(final_dir, backup_dir)
            shutil.move(package_root, final_dir)

            final_model = self._find_hymt_model_under(final_dir)
            final_runner = self._find_hymt_runner_under(final_dir)
            if not final_model or not final_runner:
                raise RuntimeError("Hy-MT model or runner not found after applying install.")
            if backup_dir and os.path.isdir(backup_dir):
                shutil.rmtree(backup_dir, ignore_errors=True)
                backup_dir = ""

            self._emit_hymt_progress("Готово" if is_ru else "Done", 100)
            QMetaObject.invokeMethod(
                self,
                "_on_hymt_install_ready",
                Qt.QueuedConnection
            )
        except (HyMTInstallCancelledError, UpdateCancelledError):
            self._restore_hymt_backup(final_dir, backup_dir)
            QMetaObject.invokeMethod(self, "_on_hymt_install_cancelled", Qt.QueuedConnection)
        except Exception as e:
            self._restore_hymt_backup(final_dir, backup_dir)
            QMetaObject.invokeMethod(
                self,
                "_on_hymt_install_failed",
                Qt.QueuedConnection,
                QtCore.Q_ARG(str, str(e))
            )
        finally:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            self._hymt_temp_dir = ""

    def _show_hymt_progress(self, text, percent=0, determinate=True):
        is_ru = self.parent.current_interface_language == "ru"
        if self.hymt_progress is None:
            self.hymt_progress = TesseractInstallProgressDialog(
                self,
                title=HYMT_ENGINE_DISPLAY,
                in_progress_attr="_hymt_install_in_progress",
                cancel_callback=self._request_hymt_install_cancel
            )
            self.hymt_progress.setCancelButtonText("Отменить" if is_ru else "Cancel")
            self.hymt_progress.setWindowModality(Qt.NonModal)
            self.hymt_progress.setAutoClose(False)
            self.hymt_progress.setAutoReset(False)
            self.hymt_progress.setMinimumDuration(0)
            self.hymt_progress.setMinimumWidth(430)
            self.hymt_progress.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            try:
                owner_window = self.window()
                owner_center = owner_window.frameGeometry().center()
                progress_frame = self.hymt_progress.frameGeometry()
                progress_frame.moveCenter(owner_center)
                self.hymt_progress.move(progress_frame.topLeft())
            except Exception:
                pass
        self.hymt_progress.setLabelText(text)
        if determinate:
            self.hymt_progress.setRange(0, 100)
            self.hymt_progress.setValue(max(0, min(100, int(percent))))
        else:
            self.hymt_progress.setRange(0, 0)
        if not self.hymt_progress.isVisible() and not getattr(self.hymt_progress, "_user_minimized", False):
            self.hymt_progress.show()

    @QtCore.pyqtSlot(str, int, bool)
    def _on_hymt_progress(self, text, percent, determinate):
        self._show_hymt_progress(text, percent, determinate)

    def _hide_hymt_progress(self):
        if self.hymt_progress is not None:
            try:
                self.hymt_progress.blockSignals(True)
                try:
                    self.hymt_progress.hide()
                finally:
                    self.hymt_progress.blockSignals(False)
            except Exception:
                pass

    def _request_hymt_install_cancel(self):
        if not self._hymt_install_in_progress:
            return
        is_ru = self.parent.current_interface_language == "ru"
        self._hymt_cancel_requested.set()
        self._show_hymt_progress("Отмена установки..." if is_ru else "Canceling install...", 0, False)

    def _finish_hymt_install_state(self):
        self._hymt_install_in_progress = False
        self._hymt_install_phase = "idle"
        self._hymt_cancel_requested.clear()
        if hasattr(self, "translator_combo"):
            self.translator_combo.setEnabled(True)
        self._sync_translator_engine_delete_button()
        self._restore_parent_topmost_after_tesseract_install()

    @QtCore.pyqtSlot()
    def _on_hymt_install_ready(self):
        self._finish_hymt_install_state()
        self._hide_hymt_progress()
        self._restore_settings_view()
        self._reset_hymt_runtime_cache()
        self._set_translator_combo_silently(HYMT_ENGINE_KEY)
        self.auto_save_setting("translator_engine", HYMT_ENGINE_KEY)
        self._sync_translator_engine_delete_button()
        is_ru = self.parent.current_interface_language == "ru"
        QMessageBox.information(
            self,
            HYMT_ENGINE_DISPLAY,
            "Hy-MT установлен и готов к офлайн-переводу." if is_ru else "Hy-MT is installed and ready for offline translation."
        )

    @QtCore.pyqtSlot(str)
    def _on_hymt_install_failed(self, error):
        self._finish_hymt_install_state()
        self._hide_hymt_progress()
        self._restore_settings_view()
        prev_engine = self.previous_translator_engine or "google"
        self._set_translator_combo_silently(prev_engine)
        self.auto_save_setting("translator_engine", prev_engine)
        is_ru = self.parent.current_interface_language == "ru"
        QMessageBox.warning(
            self,
            "Ошибка Hy-MT" if is_ru else "Hy-MT error",
            ("Не удалось установить Hy-MT:\n" if is_ru else "Failed to install Hy-MT:\n") + str(error)
        )

    @QtCore.pyqtSlot()
    def _on_hymt_install_cancelled(self):
        self._finish_hymt_install_state()
        self._hide_hymt_progress()
        self._restore_settings_view()
        prev_engine = self.previous_translator_engine or "google"
        self._set_translator_combo_silently(prev_engine)
        self.auto_save_setting("translator_engine", prev_engine)
        is_ru = self.parent.current_interface_language == "ru"
        QMessageBox.information(
            self,
            "Отмена" if is_ru else "Cancelled",
            "Установка Hy-MT отменена. Временные файлы удалены."
            if is_ru else
            "Hy-MT installation canceled. Temporary files were removed."
        )

    def remove_hymt_engine(self):
        is_ru = self.parent.current_interface_language == "ru"
        if self._hymt_install_in_progress:
            self._request_hymt_install_cancel()
            return
        hymt_dir = self._local_hymt_dir()
        if not os.path.isdir(hymt_dir):
            self._sync_translator_engine_delete_button()
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Удалить Hy-MT" if is_ru else "Remove Hy-MT")
        confirm.setText(
            "Удалить локальную модель Hy-MT и runtime из папки программы?"
            if is_ru else
            "Remove the local Hy-MT model and runtime from the app folder?"
        )
        confirm.setIcon(QMessageBox.Question)
        confirm.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        confirm.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        yes_btn = confirm.addButton("Удалить" if is_ru else "Remove", QMessageBox.YesRole)
        confirm.addButton("Отмена" if is_ru else "Cancel", QMessageBox.NoRole)
        confirm.exec_()
        if confirm.clickedButton() != yes_btn:
            return
        removed, error = self._delete_local_hymt_dir()
        try:
            if not removed:
                raise RuntimeError(error)
            if self.parent.config.get("translator_engine", "").lower() == HYMT_ENGINE_KEY:
                self._set_translator_combo_silently("google")
                self.auto_save_setting("translator_engine", "google")
            self._sync_translator_engine_delete_button()
            QMessageBox.information(
                self,
                HYMT_ENGINE_DISPLAY,
                "Локальный Hy-MT удалён." if is_ru else "Local Hy-MT was removed."
            )
        except Exception as e:
            self._sync_translator_engine_delete_button()
            QMessageBox.warning(
                self,
                "Ошибка Hy-MT" if is_ru else "Hy-MT error",
                ("Не удалось удалить Hy-MT:\n" if is_ru else "Failed to remove Hy-MT:\n") + str(e)
            )

    def remove_tesseract_engine(self):
        is_ru = self.parent.current_interface_language == "ru"
        if self._tesseract_install_in_progress:
            self._request_tesseract_install_cancel()
            return
        tesseract_dir = self._local_tesseract_dir()
        if not os.path.isdir(tesseract_dir):
            self._sync_ocr_engine_delete_button()
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Удалить Tesseract" if is_ru else "Remove Tesseract")
        confirm.setText(
            "Удалить локальный движок Tesseract из папки программы?"
            if is_ru else
            "Remove the local Tesseract engine from the app folder?"
        )
        confirm.setIcon(QMessageBox.Question)
        confirm.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        yes_btn = confirm.addButton("Удалить" if is_ru else "Remove", QMessageBox.YesRole)
        confirm.addButton("Отмена" if is_ru else "Cancel", QMessageBox.NoRole)
        confirm.exec_()
        if confirm.clickedButton() != yes_btn:
            return
        removed, error = self._delete_local_tesseract_dir()
        try:
            if not removed:
                raise RuntimeError(error)
            if self.parent.config.get("ocr_engine") == "Tesseract":
                self._set_ocr_combo_silently("Windows")
                self.save_ocr_engine("Windows")
            self._sync_ocr_engine_delete_button()
            QMessageBox.information(
                self,
                "Tesseract",
                "Локальный Tesseract удалён." if is_ru else "Local Tesseract was removed."
            )
        except Exception as e:
            self._sync_ocr_engine_delete_button()
            QMessageBox.warning(
                self,
                "Ошибка Tesseract" if is_ru else "Tesseract error",
                ("Не удалось удалить Tesseract:\n" if is_ru else "Failed to remove Tesseract:\n") + str(e)
            )

    def clear_all_cache(self):
        """Очистить все кэши приложения: память, диск, история."""
        from PyQt5.QtCore import QTimer
        from PyQt5.QtWidgets import QApplication
        from cache_manager import clear_all_cache as cm_clear, get_cache_stats, format_size

        lang = self.parent.current_interface_language
        original_text = settings_text(lang, "clear_cache")
        clearing_text = settings_text(lang, "clearing")

        if hasattr(self, 'clear_cache_btn'):
            self.clear_cache_btn.setText(clearing_text)
            self.clear_cache_btn.setEnabled(False)
            QApplication.processEvents()

        # Get real stats before clearing
        try:
            from main import get_data_file
            data_dir = os.path.dirname(get_data_file("config.json"))
            stats_before = get_cache_stats(data_dir)
            total_before = stats_before["total_bytes"]
        except Exception:
            data_dir = None
            total_before = 0

        total_cleared = 0

        # 1. Clear disk cache (history, translation cache, pycache)
        if data_dir:
            try:
                total_cleared += cm_clear(data_dir)
            except Exception:
                pass

        # 2. Clear in-memory caches
        try:
            from main import invalidate_config_cache
            invalidate_config_cache()
        except Exception:
            pass

        try:
            from ocr import _OCR_ENGINE_CACHE, _OVERLAY_POOL
            _OCR_ENGINE_CACHE.clear()
            for k in _OVERLAY_POOL:
                _OVERLAY_POOL[k] = None
        except Exception:
            pass

        try:
            import ocr
            ocr._ocr_config_cache = None
            ocr._ocr_config_mtime = 0
        except Exception:
            pass

        try:
            import translater
            translater._translator_config_cache = None
            translater._translator_config_mtime = 0
            translater._argos_languages_cache = None
            translater._argos_translations_cache.clear()
            if hasattr(translater, "_hymt_runtime_cache"):
                translater._hymt_runtime_cache = None
            if translater._http_session is not None:
                try:
                    translater._http_session.close()
                except Exception:
                    pass
                translater._http_session = None
        except Exception:
            pass

        try:
            from cache_manager import invalidate_translation_cache
            invalidate_translation_cache()
        except Exception:
            pass

        # 3. Clear temp files
        try:
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "temp")
            if os.path.exists(temp_dir):
                for root, dirs, files in os.walk(temp_dir):
                    for f in files:
                        try:
                            total_cleared += os.path.getsize(os.path.join(root, f))
                        except Exception:
                            pass
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

        # Use real total if cache_manager gave us 0
        if total_cleared == 0:
            total_cleared = total_before

        size_str = format_size(total_cleared)
        done_text = settings_text(lang, "cleared").format(size=size_str)
        
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
        title = settings_text(lang, "reset")
        question = settings_text(lang, "reset_question")
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(question)
        box.setIcon(QMessageBox.Question)
        box.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        yes_btn = box.addButton(settings_text(lang, "yes"), QMessageBox.YesRole)
        no_btn = box.addButton(settings_text(lang, "no"), QMessageBox.NoRole)
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
            "autostart_backend": "startup_shortcut",
            "translation_mode": "English",
            "ocr_hotkeys": "Ctrl+O",
            "copy_hotkey": "Ctrl+Alt+C",
            "translate_hotkey": "Ctrl+Alt+T",
            "notifications": False,
            "history": False,
            "start_minimized": False,
            "show_update_info": False,
            "first_run_guide_completed": False,
            "first_run_guide_pending": False,
            "ocr_engine": "Windows",
            "copy_translated_text": False,
            "freeze_screen_on_ocr": False,
            "debug_ocr_artifacts": False,
            "copy_history": False,
            "translator_engine": "Google",
            "allow_online_provider_fallback": False,
            "keep_visible_on_ocr": False,
            "last_ocr_language": "ru",
            "ocr_translate_source_language": "en",
            "ocr_translate_target_language": "ru",
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
        msg_clear.setWindowTitle(settings_text(lang, "clear_histories_title"))
        msg_clear.setText(settings_text(lang, "clear_histories_question"))
        yes_text, no_text = settings_text(lang, "yes"), settings_text(lang, "no")
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

        done_text = settings_text(lang, "settings_reset_done")
        info = QMessageBox(self)
        info.setWindowTitle(title)
        info.setText(done_text)
        info.setIcon(QMessageBox.Information)
        info.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        info.exec_()
