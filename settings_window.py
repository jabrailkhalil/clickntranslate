import os
import json
import webbrowser
import requests
import zipfile
import tempfile
import shutil
import threading
import hashlib
import sys
import subprocess
import platform
import re
import time
import ctypes
import logging
import base64
import importlib.util
from pathlib import Path
from urllib.parse import urlparse
try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows development hosts
    winreg = None
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox, QKeySequenceEdit,
    QMessageBox, QTextEdit, QHBoxLayout, QComboBox, QSpacerItem, QSizePolicy, QApplication, QToolButton,
    QDialog, QProgressBar, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QLineEdit, QFrame, QGridLayout, QScrollArea, QSlider
)
from PyQt5.QtCore import Qt, QMetaObject, QUrl, pyqtSlot
from PyQt5.QtGui import QDesktopServices, QKeySequence, QIcon, QColor, QBrush
from PyQt5 import QtCore, QtGui, QtWidgets
from styled_dialogs import (
    StyledMessageBox,
    TOOLTIP_QSS,
    accent_check_pixmap,
    install_accent_controls,
    tooltip_text,
)

QMessageBox = StyledMessageBox
from app_version import APP_VERSION
import platform_support
import portable_paths
from languages import (
    LANGUAGES as APP_LANGUAGES,
    easyocr_language_codes,
    language_icon_path,
    tesseract_language_code,
    windows_ocr_tag,
)

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
    ocr_module = sys.modules.get("ocr")
    invalidate_ocr = getattr(ocr_module, "invalidate_ocr_config_cache", None)
    if callable(invalidate_ocr):
        try:
            invalidate_ocr()
        except Exception:
            pass

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def _frozen_executable_dir():
    return portable_paths.frozen_executable_dir()


def _portable_base_dir():
    return portable_paths.portable_base_dir()


def _public_executable_path():
    return portable_paths.public_executable_path()


GITHUB_OWNER = "jabrailkhalil"
GITHUB_REPO = "clickntranslate"
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
UPDATE_API_ENV = "CLICKNTRANSLATE_UPDATE_API_URL"
UPDATE_TOKEN_ENV = "CLICKNTRANSLATE_UPDATE_TOKEN"
INNO_UNINSTALL_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    r"\{70f13ecd-bf6d-4c9d-bba6-3fb112272e36}_is1"
)

logger = logging.getLogger("clickntranslate.settings")
# Windows component servicing takes one caller at a time. Two DISM sessions on
# the online image answer each other with "servicing is busy", so every query
# this app makes goes through here rather than racing the others.
_WINDOWS_SERVICING_LOCK = threading.Lock()
MICROSOFT_STORE_UPDATES_URI = "ms-windows-store://downloadsandupdates"
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
RAPIDOCR_ENGINE_DISPLAY = "RapidOCR"
RAPIDOCR_PIP_PACKAGES = ("rapidocr-onnxruntime==1.4.4",)
EASYOCR_ENGINE_DISPLAY = "EasyOCR"
EASYOCR_PYTHON_VERSION = "3.12.10"
EASYOCR_PYTHON_ARCHIVE = f"python-{EASYOCR_PYTHON_VERSION}-embed-amd64.zip"
EASYOCR_PYTHON_URL = (
    f"https://www.python.org/ftp/python/{EASYOCR_PYTHON_VERSION}/"
    f"{EASYOCR_PYTHON_ARCHIVE}"
)
EASYOCR_PYTHON_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
EASYOCR_PIP_WHEEL = "pip-25.2-py3-none-any.whl"
EASYOCR_PIP_URL = (
    "https://files.pythonhosted.org/packages/b7/3f/"
    "945ef7ab14dc4f9d7f40288d2df998d1837ee0888ec3659c813487572faa/"
    f"{EASYOCR_PIP_WHEEL}"
)
EASYOCR_PIP_SHA256 = "6d67a2b4e7f14d8b31b8b52648866fa717f45a1eb70e83002f4331d07e953717"
EASYOCR_EXTRA_INDEX_URL = "https://download.pytorch.org/whl/cpu"
# Keep this dependency set reproducible.  EasyOCR's metadata leaves most
# dependencies unpinned, which previously made an installation performed
# months after release depend on whatever PyPI happened to serve that day.
EASYOCR_PIP_PACKAGES = (
    "easyocr==1.7.2",
    "torch==2.12.1+cpu",
    "torchvision==0.27.1+cpu",
    "opencv-python-headless==5.0.0.93",
    "scipy==1.18.0",
    "numpy==2.5.1",
    "Pillow==12.3.0",
    "scikit-image==0.26.0",
    "python-bidi==0.6.11",
    "PyYAML==6.0.3",
    "Shapely==2.1.2",
    "pyclipper==1.4.0",
    "ninja==1.13.0",
    "filelock==3.32.2",
    "typing-extensions==4.16.0",
    "setuptools==81.0.0",
    "sympy==1.14.0",
    "networkx==3.6.1",
    "jinja2==3.1.6",
    "fsspec==2026.7.0",
    "mpmath==1.3.0",
    "MarkupSafe==3.0.3",
    "imageio==2.37.4",
    "tifffile==2026.7.31",
    "packaging==26.2",
    "lazy-loader==0.5",
)
# The tree above is resolved for the interpreter the Windows installer downloads
# (3.13). A distribution's Python is whatever the distribution ships — 3.10 on
# Ubuntu 22.04 — and most of those pins have no wheel for it, so the install died
# with "No matching distribution found for scipy==1.18.0" before anything was
# installed. For an interpreter we do not control, pin EasyOCR itself and leave
# the rest to pip, which knows what fits that version. `--only-binary=:all:`
# still applies, so it stays wheels-only.
EASYOCR_PIP_PACKAGES_ANY_PYTHON = (
    "easyocr==1.7.2",
    "torch",
    "torchvision",
    "opencv-python-headless",
    "numpy<3",
)
# The version the exact pin set was resolved against.
EASYOCR_PINNED_PYTHON = (3, 13)

TRANSLATOR_ENGINE_OPTIONS = (
    ("google", "Google", "online"),
    ("argos", "Argos", "offline"),
    (HYMT_ENGINE_KEY, HYMT_ENGINE_DISPLAY, "offline"),
    ("mymemory", "MyMemory", "online"),
    ("lingva", "Lingva", "online"),
    ("libretranslate", "LibreTranslate", "online"),
)


def _update_feed_api_url():
    return (os.environ.get(UPDATE_API_ENV) or GITHUB_LATEST_RELEASE_API).strip()


def _update_request_headers(url="", accept_json=False):
    headers = {"User-Agent": f"ClicknTranslate/{APP_VERSION}"}
    if accept_json:
        headers["Accept"] = "application/vnd.github+json"

    token = (os.environ.get(UPDATE_TOKEN_ENV) or "").strip()
    if token:
        host = (urlparse(url or _update_feed_api_url()).hostname or "").lower()
        if host in ("api.github.com", "github.com"):
            headers["Authorization"] = f"Bearer {token}"
            if host == "api.github.com" and "/releases/assets/" in (urlparse(url).path or ""):
                headers["Accept"] = "application/octet-stream"
    return headers


def _update_asset_download_url(asset):
    token = (os.environ.get(UPDATE_TOKEN_ENV) or "").strip()
    if token and asset.get("url"):
        return asset.get("url")
    return asset.get("browser_download_url")


def _normalized_windows_path(path):
    try:
        return os.path.normcase(os.path.realpath(os.path.abspath(str(path or "")))).rstrip("\\/")
    except (OSError, TypeError, ValueError):
        return ""


def _inno_install_root():
    if winreg is None or os.name != "nt":
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INNO_UNINSTALL_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, "InstallLocation")
    except OSError:
        return ""
    return _normalized_windows_path(value)


def _is_inno_installed_copy(app_dir=None):
    if portable_paths.is_windows_packaged() or not getattr(sys, "frozen", False):
        return False
    registered_root = _inno_install_root()
    current_root = _normalized_windows_path(app_dir or _portable_base_dir())
    return bool(registered_root and current_root and registered_root == current_root)


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


TRANSLATOR_GROUP_TEXT = {
    "en": {"online": "Online", "offline": "Offline"},
    "ru": {"online": "Онлайн", "offline": "Офлайн"},
    "es": {"online": "En línea", "offline": "Sin conexión"},
    "de": {"online": "Online", "offline": "Offline"},
    "fr": {"online": "En ligne", "offline": "Hors ligne"},
    "zh": {"online": "在线", "offline": "离线"},
}


def _configure_engine_group_header(combo, index, foreground="#f4f6fb"):
    header_item = combo.model().item(index)
    if header_item is None:
        return
    header_item.setEnabled(False)
    header_font = header_item.font()
    header_font.setBold(True)
    header_item.setFont(header_font)
    header_item.setForeground(QBrush(QColor(foreground)))


def _populate_grouped_translator_combo(
    combo,
    lang,
    foreground="#f4f6fb",
    installed_engines=None,
):
    """Populate a compact combo with disabled online/offline group labels."""
    combo.clear()
    groups = TRANSLATOR_GROUP_TEXT.get(lang, TRANSLATOR_GROUP_TEXT["en"])
    installed = {str(engine).lower() for engine in (installed_engines or ())}
    engines_by_index = []
    for kind in ("online", "offline"):
        combo.addItem(f"  {groups[kind]}", None)
        header_index = combo.count() - 1
        engines_by_index.append(None)
        _configure_engine_group_header(combo, header_index, foreground)
        options = [
            option
            for option in TRANSLATOR_ENGINE_OPTIONS
            if option[2] == kind
        ]
        if not options:
            combo.removeItem(header_index)
            engines_by_index.pop()
            continue
        options = [
            option
            for _index, option in sorted(
                enumerate(options),
                key=lambda pair: (
                    0 if pair[1][0].lower() in installed else 1,
                    pair[0],
                ),
            )
        ]
        for engine, name, option_kind in options:
            combo.addItem(name, engine)
            option_index = combo.count() - 1
            engines_by_index.append(engine)
            combo.setItemData(
                option_index,
                _translator_combo_tooltip(engine, name, option_kind, lang),
                Qt.ToolTipRole,
            )
    return engines_by_index


class _DropDownProxyStyle(QtWidgets.QProxyStyle):
    """Use a real scrollable list instead of the GTK menu-style popup."""

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QtWidgets.QStyle.SH_ComboBox_Popup:
            return 0
        return super().styleHint(hint, option, widget, returnData)


class DropDownCombo(QComboBox):
    """Combo whose list opens under the field instead of on top of it.

    Qt lines the current row up with the closed control, so the list lands one
    pixel into the field and eats the coloured outline along that edge — and
    with a long list it can cover the field completely. Dropping it below,
    clear of the border, is what every other drop-down in this window does.
    """

    POPUP_GAP = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # GTK's native menu popup ignores maxVisibleItems and adds large
        # up/down scroller buttons.  A private proxy instance keeps the rest of
        # the current Qt style while requesting the standard list popup, which
        # honours the row limit and uses the styled scrollbar.
        self._drop_down_style = _DropDownProxyStyle()
        self._drop_down_style.setParent(self)
        self.setStyle(self._drop_down_style)

    def set_popup_background(self, colour):
        """Colour for the frame Qt wraps the list in.

        The list itself is styled through the combo's stylesheet, but the popup
        is a window of its own: on Linux its frame keeps the platform default and
        showed as white bands down both sides of the list. Windows never showed
        it because the frame there ends up the same colour as the list.
        """
        self._popup_background = str(colour or "")
        self._paint_popup_frame()

    def _paint_popup_frame(self):
        view = self.view()
        popup = view.window() if view is not None else None
        if popup is None or not getattr(self, "_popup_background", ""):
            return
        background = self._popup_background
        dark = QtGui.QColor(background).lightness() < 128
        text = "#f4f6fb" if dark else "#202124"
        hover = "#33313b" if dark else "#ddd6e4"
        track = "#17161c" if dark else "#e3dde7"
        handle = "#7A5FA1" if dark else "#9b87b6"
        handle_hover = "#9A7FC1" if dark else "#7A5FA1"
        popup.setStyleSheet(f"background-color: {background};")
        popup.setAutoFillBackground(True)
        # The list is a top-level popup on Linux, so a parent selector such as
        # ``QComboBox QAbstractItemView`` does not reliably reach it.  Style the
        # view and its scrollbar directly: otherwise the proxy popup falls back
        # to the desktop's blue selection and native scrollbar.
        view.setStyleSheet(f"""
            QAbstractItemView {{
                background-color: {background};
                color: {text};
                border: none;
                outline: none;
                selection-background-color: #7A5FA1;
                selection-color: #ffffff;
            }}
            QAbstractItemView::item {{
                min-height: 24px;
                padding: 3px 6px;
            }}
            QAbstractItemView::item:hover {{
                background-color: {hover};
                color: {text};
            }}
            QAbstractItemView::item:selected {{
                background-color: #7A5FA1;
                color: #ffffff;
            }}
            QScrollBar:vertical {{
                background: {track};
                width: 10px;
                margin: 3px 2px;
                border: none;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {handle};
                min-height: 32px;
                border: none;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {handle_hover}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
                border: none;
                background: transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

    def showPopup(self):
        super().showPopup()
        self._paint_popup_frame()
        popup = self.view().window()
        if popup is None:
            return
        self._cap_popup_to_visible_rows(popup)
        top_left = self.mapToGlobal(QtCore.QPoint(0, 0))
        below = top_left.y() + self.height() + self.POPUP_GAP
        screen = self._available_screen_rect()
        if below + popup.height() > screen.bottom():
            # No room underneath: sit above the field, still clear of it.
            above = top_left.y() - popup.height() - self.POPUP_GAP
            below = above if above >= screen.top() else screen.bottom() - popup.height()
        x = min(top_left.x(), screen.right() - popup.width())
        popup.move(max(screen.left(), x), below)

    def _cap_popup_to_visible_rows(self, popup):
        """Enforce maxVisibleItems even on GTK/Qt styles that ignore it.

        Qt documents that native popup styles may disregard maxVisibleItems.
        That made the language list cover almost the whole desktop on Ubuntu
        and left no scrollbar at all.  Measure the actual styled rows, cap the
        popup window itself, and let the view expose its normal scrollbar.
        """
        view = self.view()
        if not self.style().styleHint(QtWidgets.QStyle.SH_ComboBox_Popup, None, self):
            # The standard list popup already honours maxVisibleItems exactly;
            # resizing it again would shave a few pixels from its final row.
            return
        rows = self.model().rowCount()
        visible_rows = max(1, min(rows, self.maxVisibleItems()))
        if rows <= visible_rows:
            return

        fallback_height = max(24, view.fontMetrics().height() + 10)
        content_height = 2 * view.frameWidth()
        for row in range(visible_rows):
            row_height = view.sizeHintForRow(row)
            content_height += row_height if row_height > 0 else fallback_height

        popup_chrome = max(0, popup.height() - view.height())
        capped_height = content_height + popup_chrome
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        view.setMaximumHeight(content_height)
        popup.setMaximumHeight(capped_height)
        popup.resize(popup.width(), capped_height)
        if popup.layout() is not None:
            popup.layout().activate()

    def _available_screen_rect(self):
        handle = self.window().windowHandle()
        screen = handle.screen() if handle is not None else None
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        return screen.availableGeometry()


def modern_combo_style(dark, font_size=15):
    """Return the shared modern selector style used throughout the app."""
    is_dark = bool(dark)
    bg = "#17181d" if is_dark else "#e9e4ed"
    bg_lit = "#221f2c" if is_dark else "#ded7e5"
    text = "#f4f6fb" if is_dark else "#202124"
    border = "#3d3948" if is_dark else "#d7cde7"
    border_hover = "#6f598d" if is_dark else "#ad97cb"
    accent = "#9A7FC1" if is_dark else "#8063a8"
    popup_bg = "#20212a" if is_dark else "#f1edf4"
    selection = "#5f4a88" if is_dark else "#cfc1df"
    arrow_icon = resource_path(
        "icons/chevron_down_dark.png" if is_dark else "icons/chevron_down_light.png"
    ).replace("\\", "/")
    return f"""
        QComboBox {{
            /* Keep the fixed 32px row, but inset the painted field vertically.
               Three stacked selectors then have a clear 7px visual gap without
               moving any surrounding controls in the 700x400 window. */
            margin: 2px 3px;
            padding: 3px 28px 3px 10px;
            min-height: 20px;
            background-color: {bg};
            color: {text};
            border: 1px solid {border};
            border-radius: 7px;
            font-size: {int(font_size)}px;
        }}
        QComboBox:hover {{
            background-color: {bg_lit};
            border-color: {border_hover};
        }}
        QComboBox:focus, QComboBox:on {{
            background-color: {bg_lit};
            border-color: {accent};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 24px;
            border: none;
            background: transparent;
            image: url({arrow_icon});
        }}
        QComboBox QAbstractItemView {{
            background-color: {popup_bg};
            color: {text};
            selection-background-color: {selection};
            selection-color: #ffffff;
            outline: none;
            border: 1px solid {border};
            border-radius: 7px;
            padding: 3px 0px;
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 24px;
            padding: 2px 8px;
            color: {text};
        }}
        QComboBox QAbstractItemView::item:disabled {{
            color: {text};
            background-color: {popup_bg};
        }}
    """


class ResultWindowModeCombo(DropDownCombo):
    """Drop-down that turns the result window on or off per action.

    The three actions — translating selected text, a screen area, or pressing
    Translate — are independent switches, not one choice, so an ordinary
    drop-down cannot express them: picking "Area" would have to mean the other
    two are off. This keeps the drop-down shape asked for while staying honest
    about the setting: every row in the list has its own check box, the list
    stays open while several are toggled, and the closed control summarises
    what is on.
    """

    modes_changed = QtCore.pyqtSignal()

    ROW_HEIGHT = 28

    def __init__(self, modes, labels, summaries, dark=True, parent=None,
                 short_labels=None, header="", header_color="#f4f6fb"):
        super().__init__(parent)
        self._modes = tuple(modes)
        self._summaries = dict(summaries)
        self._dark = bool(dark)
        self._help = ""
        # The closed control has 180px to work with, so it names the modes with
        # the short words; the list itself has room to spell them out.
        self._short = dict(short_labels or labels)
        self._checked = {mode: True for mode in self._modes}
        self.setModel(QtGui.QStandardItemModel(0, 1, self))
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)

        def append_header(text):
            if not text:
                return
            # "Show:" alone does not say show what, or after what. A disabled
            # first row says it where it is needed, the same way the engine
            # combos label their Online/Offline groups.
            head = QtGui.QStandardItem(text)
            head.setFlags(Qt.NoItemFlags)
            head_font = head.font()
            head_font.setBold(True)
            head.setFont(head_font)
            head.setForeground(QBrush(QColor(header_color)))
            head.setSizeHint(QtCore.QSize(0, self.ROW_HEIGHT))
            self.model().appendRow(head)

        append_header(header)
        for mode in self._modes:
            item = QtGui.QStandardItem(labels[mode])
            item.setData(mode, Qt.UserRole)
            item.setFlags(Qt.ItemIsEnabled)
            # Rows are a tick plus a short word; without this they collapse to
            # the text height and the three of them look cramped together.
            item.setSizeHint(QtCore.QSize(0, self.ROW_HEIGHT))
            self.model().appendRow(item)

        self._refresh_icons()
        # Toggle on press instead of letting the view "select" a row, so the
        # list stays open and no row ever looks like the chosen one.
        self.view().pressed.connect(self._toggle_pressed)

    # --- state ---------------------------------------------------------------

    def _item(self, mode):
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            if item.data(Qt.UserRole) == mode:
                return item
        return None

    def is_mode_checked(self, mode):
        return bool(self._checked.get(mode, False))

    def checked_modes(self):
        return tuple(mode for mode in self._modes if self._checked.get(mode))

    def set_checked_modes(self, modes):
        wanted = set(modes)
        self._checked = {mode: mode in wanted for mode in self._modes}
        self._refresh_icons()
        self._refresh_text()

    def set_mode_checked(self, mode, checked):
        if mode not in self._checked:
            return
        self._checked[mode] = bool(checked)
        self._refresh_icons()
        self._refresh_text()
        self.modes_changed.emit()

    def toggle_mode(self, mode):
        self.set_mode_checked(mode, not self.is_mode_checked(mode))

    def _toggle_pressed(self, index):
        item = self.model().itemFromIndex(index)
        if item is None or not item.isEnabled():
            return
        value = item.data(Qt.UserRole)
        if value in self._modes:
            self.toggle_mode(value)

    def _refresh_icons(self):
        # The tick is an icon rather than Qt's own check indicator: a stylesheet
        # on the combo makes Qt paint the popup itself, and its indicator would
        # be the platform's white square regardless of the window's style.
        for mode in self._modes:
            item = self._item(mode)
            if item is None:
                continue
            checked = self._checked.get(mode, False)
            item.setIcon(QIcon(accent_check_pixmap(checked, self._dark)))
            state = self._summaries.get("on" if checked else "off", "")
            item.setData(f"{item.text()} — {state}" if state else item.text(),
                         Qt.AccessibleDescriptionRole)

    # --- appearance ----------------------------------------------------------

    def available_text_width(self):
        """Room for the summary once padding and the chevron are taken out."""
        return max(40, self.width() - 42)

    def summary_text(self):
        checked = self.checked_modes()
        if len(checked) == len(self._modes):
            return self._summaries["all"]
        if not checked:
            return self._summaries["none"]

        names = ", ".join(self._short.get(mode, mode) for mode in checked)
        # The window cannot grow, so fall back to a count when the names would
        # be clipped — which happens in the longer languages.
        if QtGui.QFontMetrics(self.font()).horizontalAdvance(names) <= self.available_text_width():
            return names
        return self._summaries["count"].format(count=len(checked), total=len(self._modes))

    def detail_text(self):
        """The full list of what is on — never abbreviated to a count."""
        checked = self.checked_modes()
        if not checked:
            return self._summaries["none"]
        return ", ".join(
            item.text() for item in (self._item(mode) for mode in checked)
            if item is not None
        )

    def set_help_text(self, text):
        self._help = str(text or "")
        self._refresh_text()

    def set_dark(self, dark):
        """Follow a theme switch: the row indicators are painted pixmaps."""
        dark = bool(dark)
        if dark != self._dark:
            self._dark = dark
            self._refresh_icons()

    def _refresh_text(self):
        # The closed control may only have room for "2 of 3", so the tooltip and
        # the screen reader always spell out which actions are on.
        detail = self.detail_text()
        accessible_detail = detail
        self.setAccessibleDescription(
            f"{self._help}. {accessible_detail}" if self._help else accessible_detail
        )
        if self._help:
            self.setToolTip(tooltip_text(f"{self._help}\n{accessible_detail}"))
        self.update()

    def showPopup(self):
        # Without this the popup is only as wide as the closed control, which
        # clips the longer localized labels.
        view = self.view()
        widest = max(
            (QtGui.QFontMetrics(view.font()).horizontalAdvance(self.model().item(row).text())
             for row in range(self.model().rowCount())),
            default=0,
        )
        view.setMinimumWidth(max(self.width(), widest + 56))
        super().showPopup()

    def paintEvent(self, event):
        # The combo would otherwise show whichever row is "current"; it has to
        # show the summary instead.
        painter = QtWidgets.QStylePainter(self)
        painter.setPen(self.palette().color(QtGui.QPalette.Text))
        option = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = self.summary_text()
        option.currentIcon = QtGui.QIcon()
        painter.drawComplexControl(QtWidgets.QStyle.CC_ComboBox, option)
        painter.drawControl(QtWidgets.QStyle.CE_ComboBoxLabel, option)
        painter.end()


class OpticallyCenteredPushButton(QPushButton):
    """Paint a connected button's label at a deliberate optical centre.

    IMPORTANT: changing ``padding-top`` or ``padding-bottom`` in the footer
    button QSS does not visibly move the text with Qt's Windows stylesheet
    engine.  Do not retry that ineffective fix.  The joined button frames must
    remain stationary, so only ``CE_PushButtonLabel`` is translated here.
    """

    def __init__(self, text="", parent=None, label_offset_y=-3):
        super().__init__(text, parent)
        self._label_offset_y = int(label_offset_y)

    def paintEvent(self, event):
        option = QtWidgets.QStyleOptionButton()
        self.initStyleOption(option)
        painter = QtWidgets.QStylePainter(self)
        painter.drawControl(QtWidgets.QStyle.CE_PushButtonBevel, option)
        option.rect.translate(0, self._label_offset_y)
        painter.drawControl(QtWidgets.QStyle.CE_PushButtonLabel, option)
        painter.end()


class LanguageSwapButton(QToolButton):
    """Consistent vector swap icon for every language-pair control.

    A Unicode swap glyph changes shape and vertical alignment with the active
    font.  Drawing the two arrows ourselves keeps page 3 identical to the main
    and result-window controls at every DPI and in both themes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("")
        self.setAccessibleName("Swap languages")
        self.setIconSize(QtCore.QSize(20, 16))
        self._refresh_swap_icon()

    @staticmethod
    def _swap_pixmap(color):
        ratio = max(
            1.0,
            float(QApplication.instance().devicePixelRatio())
            if QApplication.instance() is not None else 1.0,
        )
        pixmap = QtGui.QPixmap(int(22 * ratio), int(16 * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            pen = QtGui.QPen(QtGui.QColor(color), 1.8)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(QtCore.QPointF(3.0, 5.0), QtCore.QPointF(18.0, 5.0))
            painter.drawLine(QtCore.QPointF(18.0, 5.0), QtCore.QPointF(14.5, 2.0))
            painter.drawLine(QtCore.QPointF(18.0, 5.0), QtCore.QPointF(14.5, 8.0))
            painter.drawLine(QtCore.QPointF(19.0, 11.0), QtCore.QPointF(4.0, 11.0))
            painter.drawLine(QtCore.QPointF(4.0, 11.0), QtCore.QPointF(7.5, 8.0))
            painter.drawLine(QtCore.QPointF(4.0, 11.0), QtCore.QPointF(7.5, 14.0))
        finally:
            painter.end()
        return pixmap

    def _refresh_swap_icon(self):
        dark = self.palette().color(QtGui.QPalette.Window).lightness() < 128
        normal = "#c5b3e9" if dark else "#6b4f96"
        active = "#e0d4f7" if dark else "#7a5fa1"
        disabled = QtGui.QColor(normal)
        disabled.setAlpha(90)
        icon = QtGui.QIcon()
        icon.addPixmap(self._swap_pixmap(normal), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        icon.addPixmap(self._swap_pixmap(active), QtGui.QIcon.Active, QtGui.QIcon.Off)
        icon.addPixmap(self._swap_pixmap(disabled), QtGui.QIcon.Disabled, QtGui.QIcon.Off)
        self.setIcon(icon)

    def showEvent(self, event):
        self._refresh_swap_icon()
        super().showEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.PaletteChange, QtCore.QEvent.StyleChange):
            self._refresh_swap_icon()


class SettingsPageDotButton(QToolButton):
    """Small page indicator with a comfortably large click target."""

    def __init__(self, parent=None, dark=True):
        super().__init__(parent)
        self._dark = bool(dark)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setAutoRaise(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(24, 16)

    def set_dark(self, dark):
        self._dark = bool(dark)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        if self.isChecked():
            color = QColor("#B89AE8" if self._dark else "#7A5FA1")
            diameter = 10
        else:
            color = QColor("#756B80" if self._dark else "#B6A9C7")
            diameter = 9
        if self.underMouse():
            color = QColor("#D1B8F5" if self._dark else "#8B70B2")
        x = (self.width() - diameter) / 2
        y = (self.height() - diameter) / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QtCore.QRectF(x, y, diameter, diameter))
        painter.end()


def _populate_grouped_ocr_combo(
    combo,
    lang,
    foreground="#f4f6fb",
    installed_engines=None,
):
    """All bundled OCR providers process recognition locally/offline."""
    combo.clear()
    groups = TRANSLATOR_GROUP_TEXT.get(lang, TRANSLATOR_GROUP_TEXT["en"])
    combo.addItem(f"  {groups['offline']}", None)
    _configure_engine_group_header(combo, 0, foreground)
    installed = {str(engine).lower() for engine in (installed_engines or ())}
    # The WinRT engine only exists on Windows; other systems start at Tesseract,
    # which their distribution packages.
    engines = ("Windows", "Tesseract", "RapidOCR", "EasyOCR")
    if not platform_support.supports_windows_ocr():
        engines = tuple(engine for engine in engines if engine.lower() != "windows")
    engines = [
        engine
        for _index, engine in sorted(
            enumerate(engines),
            key=lambda pair: (
                0 if pair[1].lower() in installed else 1,
                pair[0],
            ),
        )
    ]
    for engine in engines:
        combo.addItem(engine, engine)
        combo.setItemData(
            combo.count() - 1,
            _ocr_combo_tooltip(engine, lang),
            Qt.ToolTipRole,
        )


OCR_DETAIL_TEXT = {
    "en": {
        "windows": "Built into Windows. Fast for regular interface text; languages are installed in Language packages.",
        "tesseract": "Local classic OCR. Broad language support and predictable offline recognition.",
        "rapidocr": "Local neural OCR optimized for text blocks and orientation; bundled model supports Chinese and English.",
        "easyocr": "Local neural OCR for difficult images and multiple scripts; selected language models must be installed first.",
    },
    "ru": {
        "windows": "Встроен в Windows. Быстрый для обычного текста интерфейса; языки ставятся в разделе «Языковые пакеты».",
        "tesseract": "Классический локальный OCR. Много языков и предсказуемое офлайн-распознавание.",
        "rapidocr": "Локальный нейросетевой OCR для блоков текста и ориентации; встроенная модель поддерживает китайский и английский.",
        "easyocr": "Локальный нейросетевой OCR для сложных изображений и разных письменностей; языковые модели ставятся заранее.",
    },
    "es": {
        "windows": "Integrado en Windows; rápido para texto normal. Los idiomas se instalan en Paquetes de idioma.",
        "tesseract": "OCR clásico local con muchos idiomas y funcionamiento sin conexión.",
        "rapidocr": "OCR neuronal local para bloques y orientación; el modelo incluido admite chino e inglés.",
        "easyocr": "OCR neuronal local para imágenes difíciles; instala antes los modelos de idioma.",
    },
    "de": {
        "windows": "In Windows integriert und schnell für normalen Text. Sprachen werden unter Sprachpakete installiert.",
        "tesseract": "Klassische lokale OCR mit vielen Sprachen und zuverlässigem Offline-Betrieb.",
        "rapidocr": "Lokale neuronale OCR für Textblöcke und Ausrichtung; das Modell unterstützt Chinesisch und Englisch.",
        "easyocr": "Lokale neuronale OCR für schwierige Bilder; Sprachmodelle müssen vorher installiert werden.",
    },
    "fr": {
        "windows": "Intégré à Windows et rapide pour le texte courant. Les langues s’installent dans Modules de langue.",
        "tesseract": "OCR local classique avec de nombreuses langues et un fonctionnement hors ligne fiable.",
        "rapidocr": "OCR neuronal local pour les blocs et l’orientation ; le modèle inclus prend en charge le chinois et l’anglais.",
        "easyocr": "OCR neuronal local pour les images difficiles ; installez d’abord les modèles de langue.",
    },
    "zh": {
        "windows": "Windows 内置，适合普通界面文字；语言可在“语言包”中安装。",
        "tesseract": "经典本地 OCR，支持多种语言，可离线稳定运行。",
        "rapidocr": "用于文本块和方向检测的本地神经 OCR；内置模型支持中文和英文。",
        "easyocr": "适合复杂图像和多种文字的本地神经 OCR；需提前安装语言模型。",
    },
}


def _ocr_combo_tooltip(engine, lang):
    details = OCR_DETAIL_TEXT.get(lang, OCR_DETAIL_TEXT["en"])
    return details.get(str(engine or "").lower(), str(engine or ""))


TRANSLATOR_DETAIL_TEXT = {
    "en": {"google": "fast, accurate, needs internet", "argos": "local translation, requires installed language packages", HYMT_ENGINE_KEY: "local LLM model, installed separately", "mymemory": "online API with daily limit", "lingva": "online Google proxy", "libretranslate": "online LibreTranslate server"},
    "ru": {"google": "быстрый, точный, нужен интернет", "argos": "локальный перевод, нужен установленный языковой пакет", HYMT_ENGINE_KEY: "локальная LLM-модель, ставится отдельным пакетом", "mymemory": "онлайн API, есть дневной лимит", "lingva": "онлайн прокси Google", "libretranslate": "онлайн сервер LibreTranslate"},
    "es": {"google": "rápido y preciso; necesita internet", "argos": "traducción local; requiere paquetes de idioma instalados", HYMT_ENGINE_KEY: "modelo LLM local; se instala por separado", "mymemory": "API en línea con límite diario", "lingva": "proxy en línea de Google", "libretranslate": "servidor en línea LibreTranslate"},
    "de": {"google": "schnell und genau; benötigt Internet", "argos": "lokale Übersetzung; installierte Sprachpakete erforderlich", HYMT_ENGINE_KEY: "lokales LLM-Modell; wird separat installiert", "mymemory": "Online-API mit Tageslimit", "lingva": "Online-Proxy für Google", "libretranslate": "Online-Server LibreTranslate"},
    "fr": {"google": "rapide et précis ; connexion Internet requise", "argos": "traduction locale ; modules de langue installés requis", HYMT_ENGINE_KEY: "modèle LLM local ; installé séparément", "mymemory": "API en ligne avec limite quotidienne", "lingva": "proxy Google en ligne", "libretranslate": "serveur LibreTranslate en ligne"},
    "zh": {"google": "快速、准确，需要联网", "argos": "本地翻译，需要已安装的语言包", HYMT_ENGINE_KEY: "本地 LLM 模型，需要单独安装", "mymemory": "在线 API，设有每日限额", "lingva": "Google 在线代理", "libretranslate": "LibreTranslate 在线服务器"},
}


def _translator_combo_tooltip(engine, name, kind, lang):
    kind_text = _provider_kind_text(kind, lang)
    details = TRANSLATOR_DETAIL_TEXT.get(lang, TRANSLATOR_DETAIL_TEXT["en"])
    return f"{name}: {kind_text}. {details.get(engine, '')}".strip()


class UpdateCancelledError(RuntimeError):
    pass


class TesseractInstallCancelledError(RuntimeError):
    pass


class RapidOCRInstallCancelledError(RuntimeError):
    pass


class EasyOCRInstallCancelledError(RuntimeError):
    pass


class HyMTInstallCancelledError(RuntimeError):
    pass


PROGRESS_DIALOG_STYLE = """
    QDialog#progressDialogRoot {
        background: transparent;
    }
    QWidget#progressDialogFrame {
        background-color: #111111;
        color: #ffffff;
        border: 1px solid #7a61b3;
        border-radius: 10px;
    }
    QLabel {
        color: #ffffff;
        font-size: 15px;
        background: transparent;
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
"""


def _configure_progress_dialog_window(dialog):
    dialog.setObjectName("progressDialogRoot")
    dialog.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    dialog.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
    dialog.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, False)
    dialog.setWindowModality(Qt.NonModal)
    dialog.setMinimumWidth(430)
    dialog.setStyleSheet(PROGRESS_DIALOG_STYLE)


def _bring_progress_dialog_to_front(dialog):
    if getattr(dialog, "_user_minimized", False):
        return
    try:
        if dialog.isMinimized():
            dialog.showNormal()
        dialog.raise_()
        dialog.activateWindow()
    except Exception:
        pass


def _center_progress_dialog(dialog, owner):
    """Center a frameless progress window after its final size is known."""
    owner_window = None
    if isinstance(owner, QWidget):
        try:
            owner_window = owner.window()
        except Exception:
            owner_window = owner
    if owner_window is None:
        owner_parent = getattr(owner, "parent", None)
        if isinstance(owner_parent, QWidget):
            try:
                owner_window = owner_parent.window()
            except Exception:
                owner_window = owner_parent

    target_geometry = None
    if owner_window is not None:
        try:
            target_geometry = owner_window.frameGeometry()
        except Exception:
            target_geometry = None
    if target_geometry is None or not target_geometry.isValid():
        screen = QApplication.primaryScreen()
        if screen is not None:
            target_geometry = screen.availableGeometry()
    if target_geometry is None or not target_geometry.isValid():
        return

    dialog.ensurePolished()
    dialog.adjustSize()
    frame = dialog.frameGeometry()
    frame.moveCenter(target_geometry.center())
    screen = QApplication.screenAt(target_geometry.center()) or QApplication.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        x = max(available.left(), min(frame.left(), available.right() - frame.width() + 1))
        y = max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1))
        frame.moveTopLeft(QtCore.QPoint(x, y))
    dialog.move(frame.topLeft())


class UpdateProgressDialog(QDialog):
    def __init__(self, owner):
        super().__init__(None)
        self._owner = owner
        self._drag_position = None
        self._user_minimized = False
        owner_parent = getattr(owner, "parent", None)
        self._lang = getattr(owner_parent, "current_interface_language", "en")
        self.setWindowTitle(settings_text(self._lang, "update"))
        _configure_progress_dialog_window(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.frame = QWidget(self)
        self.frame.setObjectName("progressDialogFrame")
        self.frame.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        outer.addWidget(self.frame)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        frame_layout.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(12, 8, 8, 5)
        title_row.setSpacing(6)
        self._title_label = QLabel(settings_text(self._lang, "update"), self)
        self._title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #c5b3e9;")
        title_row.addWidget(self._title_label)
        title_row.addStretch()
        self._minimize_button = QToolButton(self)
        self._minimize_button.setText("-")
        self._minimize_button.setToolTip(tooltip_text(settings_text(self._lang, "minimize")))
        self._minimize_button.setFixedSize(28, 24)
        self._minimize_button.clicked.connect(self._minimize_to_taskbar)
        title_row.addWidget(self._minimize_button)
        self._close_button = QToolButton(self)
        self._close_button.setText("x")
        self._close_button.setToolTip(tooltip_text(settings_text(self._lang, "cancel")))
        self._close_button.setFixedSize(28, 24)
        self._close_button.clicked.connect(self.reject)
        title_row.addWidget(self._close_button)
        frame_layout.addLayout(title_row)

        body = QVBoxLayout()
        body.setContentsMargins(16, 8, 16, 16)
        body.setSpacing(10)
        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        body.addWidget(self.message_label)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        body.addWidget(self.progress_bar)
        self.cancel_button = QPushButton(settings_text(self._lang, "cancel"))
        self.cancel_button.clicked.connect(self.reject)
        body.addWidget(self.cancel_button, alignment=Qt.AlignRight)
        frame_layout.addLayout(body)

    def _minimize_to_taskbar(self):
        self._user_minimized = True
        self.showMinimized()

    def bring_to_front(self):
        _bring_progress_dialog_to_front(self)

    def center_on_owner(self):
        _center_progress_dialog(self, self._owner)

    def showEvent(self, event):
        self.center_on_owner()
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self.center_on_owner)

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        if hasattr(self, "_title_label"):
            self._title_label.setText(title)

    def setCancelButtonText(self, text):
        self.cancel_button.setText(text)
        if hasattr(self, "_close_button"):
            self._close_button.setToolTip(tooltip_text(text))

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

    def _request_cancel(self):
        if self._owner and getattr(self._owner, "_update_in_progress", False):
            self._owner._handle_update_progress_close_attempt()


class TesseractInstallProgressDialog(QDialog):
    canceled = QtCore.pyqtSignal()
    backgrounded = QtCore.pyqtSignal(str)

    def __init__(
        self,
        owner,
        title="Tesseract",
        in_progress_attr="_tesseract_install_in_progress",
        cancel_callback=None,
        anchor_owner=None,
    ):
        transient_owner = anchor_owner if isinstance(anchor_owner, QWidget) else owner if isinstance(owner, QWidget) else None
        super().__init__(transient_owner)
        self._owner = owner
        self._anchor_owner = transient_owner or owner
        self._title = title
        self._stable_windows_layout = str(title) == "Windows OCR"
        self._in_progress_attr = in_progress_attr
        self._cancel_callback = cancel_callback
        self._drag_position = None
        self._user_minimized = False
        owner_parent = getattr(owner, "parent", None)
        if callable(owner_parent):
            owner_parent = None
        self._lang = getattr(
            owner_parent,
            "current_interface_language",
            getattr(owner, "current_interface_language", "en"),
        )
        self.setWindowTitle(title)
        _configure_progress_dialog_window(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.frame = QWidget(self)
        self.frame.setObjectName("progressDialogFrame")
        self.frame.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        outer.addWidget(self.frame)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        frame_layout.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(12, 8, 8, 5)
        title_row.setSpacing(6)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #c5b3e9;")
        title_row.addWidget(self.title_label)
        title_row.addStretch()
        self.minimize_button = QToolButton(self)
        self.minimize_button.setText("–")
        self.minimize_button.setToolTip(tooltip_text(settings_text(self._lang, "minimize")))
        self.minimize_button.setFixedSize(28, 24)
        self.minimize_button.clicked.connect(self._minimize_to_taskbar)
        title_row.addWidget(self.minimize_button)
        self.close_button = QToolButton(self)
        self.close_button.setText("×")
        self.close_button.setToolTip(tooltip_text(settings_text(self._lang, "cancel")))
        self.close_button.setFixedSize(28, 24)
        self.close_button.clicked.connect(self.reject)
        title_row.addWidget(self.close_button)
        frame_layout.addLayout(title_row)

        body = QVBoxLayout()
        body.setContentsMargins(16, 8, 16, 16)
        body.setSpacing(10)
        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        body.addWidget(self.message_label)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        body.addWidget(self.progress_bar)
        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch()
        self.background_button = QPushButton("Continue in background")
        self.background_button.clicked.connect(self._continue_in_background)
        action_row.addWidget(self.background_button)
        self.cancel_button = QPushButton(settings_text(self._lang, "cancel"))
        self.cancel_button.clicked.connect(self.reject)
        action_row.addWidget(self.cancel_button)
        body.addLayout(action_row)
        frame_layout.addLayout(body)

        # Windows OCR grows from a one-line "Preparing" message to several
        # lines of real Windows Update / DISM detail.  Reserving that space on
        # the first frame prevents the dialog from visibly jumping in size as
        # soon as servicing starts.  Other engine installers keep their compact
        # dynamically-sized dialog.
        if self._stable_windows_layout:
            self.setFixedWidth(560)
            self.message_label.setFixedHeight(172)
            self.adjustSize()
            self.setFixedSize(560, max(340, self.sizeHint().height()))

    def _minimize_to_taskbar(self):
        self._user_minimized = True
        self.backgrounded.emit(self.message_label.text())
        self.showMinimized()

    def _continue_in_background(self):
        """Keep the worker running without repeatedly raising this window."""
        self._user_minimized = True
        self.backgrounded.emit(self.message_label.text())
        self.hide()

    def restore_from_background(self):
        """Return a deliberately hidden/minimized task to the foreground."""
        self._user_minimized = False
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.center_on_owner()
        self.bring_to_front()

    def bring_to_front(self):
        _bring_progress_dialog_to_front(self)

    def center_on_owner(self):
        _center_progress_dialog(self, self._anchor_owner)

    def showEvent(self, event):
        self.center_on_owner()
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self.center_on_owner)

    def setCancelButtonText(self, text):
        self.cancel_button.setText(text)
        self.close_button.setToolTip(tooltip_text(text))

    def setBackgroundButtonText(self, text):
        self.background_button.setText(text)

    def setCancellationPending(self, text):
        self.cancel_button.setText(text)
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.close_button.setToolTip(tooltip_text(text))

    def setLabelText(self, text):
        self.message_label.setText(text)
        if self._stable_windows_layout:
            return
        # The Windows OCR message grows a line when Windows Update goes
        # quiet. A word-wrapped label does not report the height it needs
        # unless it is asked at the width it actually has, so the dialog
        # would clip the extra line instead of growing for it.
        width = max(1, self.message_label.width())
        self.message_label.setMinimumHeight(self.message_label.heightForWidth(width))
        self.adjustSize()

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
        "update_check_on_launch": "Check for updates when the app starts",
        "dim_screen_during_ocr": "Dim the screen while selecting an OCR area",
        "ocr_dim_strength_tooltip": "Choose how dark the area outside the OCR selection becomes.",
        "restore_clipboard_after_selection": "Restore clipboard after selected-text actions",
        "restore_clipboard_tooltip": "Restore what was in the clipboard after a visible selection translation or a successful replacement. Explicit copy actions still keep the result.",
        "copy_notification": "Notify me after text is copied",
        "copy_notification_tooltip": "Show a short system notification when Click'n'Translate puts a result in the clipboard.",
        "create_bug_report": "Bug report",
        "bug_report_tooltip": "Create a diagnostic ZIP without clipboard contents, histories or document text.",
        "export_settings": "Export",
        "import_settings": "Import",
        "export_settings_tooltip": "Save all application settings to a portable JSON file.",
        "import_settings_tooltip": "Load a Click'n'Translate settings JSON and apply it now.",
        "settings_exported": "Settings were exported.\n\n{path}",
        "settings_imported": "Settings were imported and applied.",
        "settings_transfer_failed": "Could not transfer settings.\n\n{error}",
        "settings_file_filter": "Click'n'Translate settings (*.json)",
        "ocr_behavior_heading": "OCR behavior",
        "updates_heading": "Updates",
        "settings_page_main": "General settings",
        "settings_page_updates": "OCR and updates",
        "settings_page_game": "Dynamic translation",
        "game_settings_heading": "Dynamic translation",
        "game_languages": "Languages:",
        "game_swap_languages": "Swap dynamic translation languages",
        "game_scan_interval": "Scan interval:",
        "game_overlay_opacity": "Translation background:",
        "game_pause_inactive": "Pause when the target app is inactive",
        "game_pause_inactive_tooltip": "Pauses OCR when the window active at mode start is minimized or no longer in the foreground. Translation resumes automatically when you return.",
        "game_show_original": "Show recognized text above the translation",
        "game_workflow_note": "Start Dynamic translation, select one or more text areas, then press Start. Translation updates in place; launch the mode again to stop.",
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
        "error_title": "Error",
        "clear_translation_history_error": "Could not clear translation history.",
        "clear_copy_history_error": "Could not clear copy history.",
        "copy_translated_text": "Copy translated text",
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
        "game_translate_label": "Dynamic:",
        "selection_translate_label": "Selection Translate:",
        "toggle_window_hotkey_label": "Show / hide app:",
        "result_window_label": "Show window:",
        "result_window_mode_selection": "Text",
        "result_window_mode_area": "Area",
        "result_window_mode_main": "Main",
        "result_window_modes_header": "Show the window after:",
        "result_window_row_selection": "Translating selected text",
        "result_window_row_area": "Translating a screen area",
        "result_window_row_main": "Pressing Translate",
        "result_window_summary_all": "All",
        "result_window_summary_none": "Never",
        "result_window_summary_on": "shown",
        "result_window_summary_off": "hidden",
        "result_window_summary_count": "{count} of {total}",
        "result_window_tooltip": "Tick the actions that should open the translation window. Unticked actions copy the translation straight to the clipboard.",
        "result_window_mode_selection_tooltip": "Show the result window after translating selected text.",
        "result_window_mode_area_tooltip": "Show the result window after translating a screen area.",
        "result_window_mode_main_tooltip": "Show the result window after pressing Translate.",
        "replace_selection_translate_label": "Translate and replace selection:",
        "replace_selection_unavailable": "Safe automatic replacement is currently available on Windows.",
        "copy_hotkey_label": "Copy Selected Hotkey:",
        "translate_hotkey_label": "Translate Hotkey:",
        "remove_local_tesseract": "Remove local Tesseract",
        "remove_local_rapidocr": "Remove local RapidOCR",
        "remove_local_easyocr": "Remove local EasyOCR",
        "remove_local_hymt": "Remove local Hy-MT",
        "ocr_language_packs": "Language packages",
        "manage_ocr_languages": "Manage OCR and Argos language packages",
        "clearing": "Clearing...",
        "cleared": "Cleared {size}",
        "yes": "Yes",
        "no": "No",
        "cancel": "Cancel",
        "minimize": "Minimize",
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
        "update_check_on_launch": "Проверять обновления при запуске",
        "dim_screen_during_ocr": "Затемнять экран при выборе области OCR",
        "ocr_dim_strength_tooltip": "Настройте силу затемнения за пределами выбранной области OCR.",
        "restore_clipboard_after_selection": "Восстанавливать буфер после работы с выделением",
        "restore_clipboard_tooltip": "Возвращает прежнее содержимое буфера после показа перевода или успешной замены. Явное копирование всё равно сохраняет результат.",
        "copy_notification": "Уведомлять после копирования текста",
        "copy_notification_tooltip": "Показывает короткое системное уведомление, когда Click'n'Translate помещает результат в буфер.",
        "create_bug_report": "Баг-репорт",
        "bug_report_tooltip": "Создаёт диагностический ZIP без содержимого буфера, историй и текста документов.",
        "export_settings": "Экспорт",
        "import_settings": "Импорт",
        "export_settings_tooltip": "Сохраняет все настройки в переносимый JSON-файл.",
        "import_settings_tooltip": "Загружает JSON настроек Click'n'Translate и сразу применяет его.",
        "settings_exported": "Настройки экспортированы.\n\n{path}",
        "settings_imported": "Настройки импортированы и применены.",
        "settings_transfer_failed": "Не удалось перенести настройки.\n\n{error}",
        "settings_file_filter": "Настройки Click'n'Translate (*.json)",
        "ocr_behavior_heading": "Поведение OCR",
        "updates_heading": "Обновления",
        "settings_page_main": "Основные настройки",
        "settings_page_updates": "OCR и обновления",
        "settings_page_game": "Динамический перевод",
        "game_settings_heading": "Динамический перевод",
        "game_languages": "Языки:",
        "game_swap_languages": "Поменять языки динамического перевода местами",
        "game_scan_interval": "Частота проверки:",
        "game_overlay_opacity": "Фон перевода:",
        "game_pause_inactive": "Пауза, когда целевое окно неактивно",
        "game_pause_inactive_tooltip": "OCR приостанавливается, если окно, активное при запуске режима, свёрнуто или больше не находится на переднем плане. При возврате перевод продолжится автоматически.",
        "game_show_original": "Показывать распознанный текст над переводом",
        "game_workflow_note": "Запустите динамический режим, выделите одну или несколько областей и нажмите «Запустить». Перевод обновляется на месте; повторный запуск остановит режим.",
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
        "error_title": "Ошибка",
        "clear_translation_history_error": "Не удалось очистить историю переводов.",
        "clear_copy_history_error": "Не удалось очистить историю копирований.",
        "copy_translated_text": "Копировать переведённый текст",
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
        "game_translate_label": "Динамический",
        "selection_translate_label": "Перевод выделенного текста",
        "toggle_window_hotkey_label": "Свернуть / развернуть программу",
        "result_window_label": "Показывать окно:",
        "result_window_mode_selection": "Текст",
        "result_window_mode_area": "Зона",
        "result_window_mode_main": "Кнопка",
        "result_window_modes_header": "Показывать окно после:",
        "result_window_row_selection": "Перевода выделенного текста",
        "result_window_row_area": "Перевода области экрана",
        "result_window_row_main": "Нажатия кнопки «Перевести»",
        "result_window_summary_all": "Все",
        "result_window_summary_none": "Никогда",
        "result_window_summary_on": "показывать",
        "result_window_summary_off": "скрывать",
        "result_window_summary_count": "{count} из {total}",
        "result_window_tooltip": "Отметьте действия, после которых открывать окно перевода. Остальные действия сразу копируют перевод в буфер.",
        "result_window_mode_selection_tooltip": "Показывать окно после перевода выделенного текста.",
        "result_window_mode_area_tooltip": "Показывать окно после перевода области экрана.",
        "result_window_mode_main_tooltip": "Показывать окно после нажатия кнопки «Перевести».",
        "replace_selection_translate_label": "Перевести и заменить выделенное:",
        "replace_selection_unavailable": "Безопасная автоматическая замена пока доступна только в Windows.",
        "copy_hotkey_label": "Горячая клавиша для копирования",
        "translate_hotkey_label": "Перевод выделенного (OCR)",
        "remove_local_tesseract": "Удалить локальный Tesseract",
        "remove_local_rapidocr": "Удалить локальный RapidOCR",
        "remove_local_easyocr": "Удалить локальный EasyOCR",
        "remove_local_hymt": "Удалить локальный Hy-MT",
        "ocr_language_packs": "Языковые пакеты",
        "manage_ocr_languages": "Управление пакетами OCR и Argos",
        "clearing": "Выполняется...",
        "cleared": "Очищено {size}",
        "yes": "Да",
        "no": "Нет",
        "cancel": "Отмена",
        "minimize": "Свернуть",
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
        "update_check_on_launch": "Buscar actualizaciones al iniciar",
        "dim_screen_during_ocr": "Oscurecer la pantalla al seleccionar un área OCR",
        "ocr_dim_strength_tooltip": "Elige cuánto se oscurece el área fuera de la selección OCR.",
        "restore_clipboard_after_selection": "Restaurar el portapapeles tras usar texto seleccionado",
        "restore_clipboard_tooltip": "Restaura el contenido anterior tras mostrar una traducción o reemplazar la selección. Las copias explícitas conservan el resultado.",
        "copy_notification": "Notificar después de copiar texto",
        "copy_notification_tooltip": "Muestra una notificación breve cuando Click'n'Translate copia un resultado.",
        "create_bug_report": "Informe de error",
        "bug_report_tooltip": "Crea un ZIP de diagnóstico sin portapapeles, historiales ni texto de documentos.",
        "export_settings": "Exportar", "import_settings": "Importar",
        "export_settings_tooltip": "Guarda todos los ajustes en un archivo JSON portable.",
        "import_settings_tooltip": "Carga y aplica un JSON de ajustes de Click'n'Translate.",
        "settings_exported": "Ajustes exportados.\n\n{path}",
        "settings_imported": "Los ajustes se importaron y aplicaron.",
        "settings_transfer_failed": "No se pudieron transferir los ajustes.\n\n{error}",
        "settings_file_filter": "Ajustes de Click'n'Translate (*.json)",
        "ocr_behavior_heading": "Comportamiento de OCR",
        "updates_heading": "Actualizaciones",
        "settings_page_main": "Ajustes generales",
        "settings_page_updates": "OCR y actualizaciones",
        "settings_page_game": "Traducción dinámica",
        "game_settings_heading": "Traducción dinámica",
        "game_languages": "Idiomas:",
        "game_swap_languages": "Intercambiar idiomas de traducción dinámica",
        "game_scan_interval": "Intervalo de lectura:",
        "game_overlay_opacity": "Fondo de traducción:",
        "game_pause_inactive": "Pausar si la aplicación vinculada está inactiva",
        "game_pause_inactive_tooltip": "Pausa el OCR si la ventana activa al iniciar el modo se minimiza o deja de estar en primer plano. La traducción se reanuda al volver.",
        "game_show_original": "Mostrar el texto reconocido sobre la traducción",
        "game_workflow_note": "Inicia el modo dinámico, selecciona una o varias zonas y pulsa Iniciar. La traducción se actualiza en el lugar; inicia el modo otra vez para detenerlo.",
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
        "error_title": "Error",
        "clear_translation_history_error": "No se pudo borrar el historial de traducciones.",
        "clear_copy_history_error": "No se pudo borrar el historial de copias.",
        "copy_translated_text": "Copiar el texto traducido",
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
        "game_translate_label": "Dinámico:",
        "selection_translate_label": "Traduccion de seleccion:",
        "toggle_window_hotkey_label": "Mostrar / ocultar aplicacion:",
        "result_window_label": "Mostrar ventana:",
        "result_window_mode_selection": "Texto",
        "result_window_mode_area": "Área",
        "result_window_mode_main": "Botón",
        "result_window_modes_header": "Mostrar la ventana tras:",
        "result_window_row_selection": "Traducir texto seleccionado",
        "result_window_row_area": "Traducir un área de la pantalla",
        "result_window_row_main": "Pulsar Traducir",
        "result_window_summary_all": "Todas",
        "result_window_summary_none": "Nunca",
        "result_window_summary_on": "mostrar",
        "result_window_summary_off": "ocultar",
        "result_window_summary_count": "{count} de {total}",
        "result_window_tooltip": "Marca las acciones que abren la ventana de traducción. Las demás copian la traducción directamente al portapapeles.",
        "result_window_mode_selection_tooltip": "Mostrar la ventana al traducir texto seleccionado.",
        "result_window_mode_area_tooltip": "Mostrar la ventana al traducir un área de la pantalla.",
        "result_window_mode_main_tooltip": "Mostrar la ventana al pulsar Traducir.",
        "replace_selection_translate_label": "Traducir y reemplazar selección:",
        "replace_selection_unavailable": "El reemplazo automático seguro está disponible actualmente en Windows.",
        "copy_hotkey_label": "Atajo para copiar seleccion:",
        "translate_hotkey_label": "Atajo de traduccion:",
        "remove_local_tesseract": "Eliminar Tesseract local",
        "remove_local_rapidocr": "Eliminar RapidOCR local",
        "remove_local_easyocr": "Eliminar EasyOCR local",
        "remove_local_hymt": "Eliminar Hy-MT local",
        "ocr_language_packs": "Paquetes de idiomas",
        "manage_ocr_languages": "Gestionar paquetes de OCR y Argos",
        "clearing": "Borrando...",
        "cleared": "Borrado {size}",
        "yes": "Si",
        "no": "No",
        "cancel": "Cancelar",
        "minimize": "Minimizar",
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
        "update_check_on_launch": "Beim Start nach Updates suchen",
        "dim_screen_during_ocr": "Bildschirm bei der OCR-Auswahl abdunkeln",
        "ocr_dim_strength_tooltip": "Legt fest, wie stark der Bereich außerhalb der OCR-Auswahl abgedunkelt wird.",
        "restore_clipboard_after_selection": "Zwischenablage nach Textauswahl wiederherstellen",
        "restore_clipboard_tooltip": "Stellt den vorherigen Inhalt nach einer sichtbaren Übersetzung oder erfolgreichen Ersetzung wieder her. Explizites Kopieren behält das Ergebnis.",
        "copy_notification": "Nach dem Kopieren benachrichtigen",
        "copy_notification_tooltip": "Zeigt eine kurze Systemmeldung, wenn Click'n'Translate ein Ergebnis kopiert.",
        "create_bug_report": "Fehlerbericht",
        "bug_report_tooltip": "Erstellt eine Diagnose-ZIP ohne Zwischenablage, Verläufe oder Dokumenttext.",
        "export_settings": "Exportieren", "import_settings": "Importieren",
        "export_settings_tooltip": "Speichert alle Einstellungen in einer portablen JSON-Datei.",
        "import_settings_tooltip": "Lädt eine Click'n'Translate-JSON und wendet sie sofort an.",
        "settings_exported": "Einstellungen wurden exportiert.\n\n{path}",
        "settings_imported": "Einstellungen wurden importiert und angewendet.",
        "settings_transfer_failed": "Einstellungen konnten nicht übertragen werden.\n\n{error}",
        "settings_file_filter": "Click'n'Translate-Einstellungen (*.json)",
        "ocr_behavior_heading": "OCR-Verhalten",
        "updates_heading": "Updates",
        "settings_page_main": "Allgemeine Einstellungen",
        "settings_page_updates": "OCR und Updates",
        "settings_page_game": "Dynamische Übersetzung",
        "game_settings_heading": "Dynamische Übersetzung",
        "game_languages": "Sprachen:",
        "game_swap_languages": "Sprachen der dynamischen Übersetzung tauschen",
        "game_scan_interval": "Scanintervall:",
        "game_overlay_opacity": "Übersetzungshintergrund:",
        "game_pause_inactive": "Pausieren, wenn die Ziel-App inaktiv ist",
        "game_pause_inactive_tooltip": "OCR pausiert, wenn das beim Modusstart aktive Fenster minimiert wird oder nicht mehr im Vordergrund ist. Beim Zurückkehren läuft die Übersetzung automatisch weiter.",
        "game_show_original": "Erkannten Text über der Übersetzung zeigen",
        "game_workflow_note": "Dynamischen Modus starten, einen oder mehrere Textbereiche wählen und Start drücken. Die Übersetzung wird dort aktualisiert; erneutes Starten beendet den Modus.",
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
        "error_title": "Fehler",
        "clear_translation_history_error": "Der Übersetzungsverlauf konnte nicht gelöscht werden.",
        "clear_copy_history_error": "Der Kopierverlauf konnte nicht gelöscht werden.",
        "copy_translated_text": "Ubersetzten Text kopieren",
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
        "game_translate_label": "Dynamisch:",
        "selection_translate_label": "Auswahlubersetzung:",
        "toggle_window_hotkey_label": "App anzeigen / ausblenden:",
        "result_window_label": "Fenster zeigen:",
        "result_window_mode_selection": "Text",
        "result_window_mode_area": "Zone",
        "result_window_mode_main": "Knopf",
        "result_window_modes_header": "Fenster anzeigen nach:",
        "result_window_row_selection": "Übersetzen von markiertem Text",
        "result_window_row_area": "Übersetzen eines Bildschirmbereichs",
        "result_window_row_main": "Klick auf Übersetzen",
        "result_window_summary_all": "Alle",
        "result_window_summary_none": "Nie",
        "result_window_summary_on": "anzeigen",
        "result_window_summary_off": "ausblenden",
        "result_window_summary_count": "{count} von {total}",
        "result_window_tooltip": "Haken Sie die Aktionen an, die das Übersetzungsfenster öffnen sollen. Andere Aktionen kopieren die Übersetzung direkt.",
        "result_window_mode_selection_tooltip": "Fenster nach der Übersetzung markierten Textes zeigen.",
        "result_window_mode_area_tooltip": "Fenster nach der Übersetzung eines Bildschirmbereichs zeigen.",
        "result_window_mode_main_tooltip": "Fenster nach einem Klick auf Übersetzen zeigen.",
        "replace_selection_translate_label": "Auswahl übersetzen und ersetzen:",
        "replace_selection_unavailable": "Sicheres automatisches Ersetzen ist derzeit unter Windows verfügbar.",
        "copy_hotkey_label": "Tastenkurzel zum Kopieren:",
        "translate_hotkey_label": "Tastenkurzel zum Ubersetzen:",
        "remove_local_tesseract": "Lokales Tesseract entfernen",
        "remove_local_rapidocr": "Lokales RapidOCR entfernen",
        "remove_local_easyocr": "Lokales EasyOCR entfernen",
        "remove_local_hymt": "Lokales Hy-MT entfernen",
        "ocr_language_packs": "Sprachpakete",
        "manage_ocr_languages": "OCR- und Argos-Sprachpakete verwalten",
        "clearing": "Wird geleert...",
        "cleared": "{size} geleert",
        "yes": "Ja",
        "no": "Nein",
        "cancel": "Abbrechen",
        "minimize": "Minimieren",
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
        "update_check_on_launch": "Rechercher les mises à jour au démarrage",
        "dim_screen_during_ocr": "Assombrir l’écran pendant la sélection OCR",
        "ocr_dim_strength_tooltip": "Choisissez l’intensité de l’assombrissement hors de la sélection OCR.",
        "restore_clipboard_after_selection": "Restaurer le presse-papiers après une sélection",
        "restore_clipboard_tooltip": "Restaure le contenu précédent après l’affichage d’une traduction ou un remplacement réussi. Une copie explicite conserve le résultat.",
        "copy_notification": "Notifier après la copie du texte",
        "copy_notification_tooltip": "Affiche une brève notification lorsque Click'n'Translate copie un résultat.",
        "create_bug_report": "Rapport de bug",
        "bug_report_tooltip": "Crée un ZIP de diagnostic sans presse-papiers, historiques ni texte de document.",
        "export_settings": "Exporter", "import_settings": "Importer",
        "export_settings_tooltip": "Enregistre tous les réglages dans un fichier JSON portable.",
        "import_settings_tooltip": "Charge et applique un JSON de réglages Click'n'Translate.",
        "settings_exported": "Réglages exportés.\n\n{path}",
        "settings_imported": "Les réglages ont été importés et appliqués.",
        "settings_transfer_failed": "Impossible de transférer les réglages.\n\n{error}",
        "settings_file_filter": "Réglages Click'n'Translate (*.json)",
        "ocr_behavior_heading": "Comportement OCR",
        "updates_heading": "Mises à jour",
        "settings_page_main": "Réglages généraux",
        "settings_page_updates": "OCR et mises à jour",
        "settings_page_game": "Traduction dynamique",
        "game_settings_heading": "Traduction dynamique",
        "game_languages": "Langues :",
        "game_swap_languages": "Inverser les langues de la traduction dynamique",
        "game_scan_interval": "Intervalle d’analyse :",
        "game_overlay_opacity": "Fond de traduction :",
        "game_pause_inactive": "Pause si l’application liée est inactive",
        "game_pause_inactive_tooltip": "L’OCR s’arrête si la fenêtre active au lancement du mode est réduite ou n’est plus au premier plan. La traduction reprend automatiquement au retour.",
        "game_show_original": "Afficher le texte reconnu au-dessus de la traduction",
        "game_workflow_note": "Lancez le mode dynamique, choisissez une ou plusieurs zones puis appuyez sur Démarrer. La traduction s’actualise sur place ; relancer le mode l’arrête.",
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
        "error_title": "Erreur",
        "clear_translation_history_error": "Impossible d’effacer l’historique des traductions.",
        "clear_copy_history_error": "Impossible d’effacer l’historique des copies.",
        "copy_translated_text": "Copier le texte traduit",
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
        "game_translate_label": "Dynamique :",
        "selection_translate_label": "Traduction de selection :",
        "toggle_window_hotkey_label": "Afficher / masquer l'application :",
        "result_window_label": "Afficher fenêtre :",
        "result_window_mode_selection": "Texte",
        "result_window_mode_area": "Zone",
        "result_window_mode_main": "Bouton",
        "result_window_modes_header": "Afficher la fenêtre après :",
        "result_window_row_selection": "Traduction du texte sélectionné",
        "result_window_row_area": "Traduction d’une zone de l’écran",
        "result_window_row_main": "Clic sur Traduire",
        "result_window_summary_all": "Toutes",
        "result_window_summary_none": "Jamais",
        "result_window_summary_on": "afficher",
        "result_window_summary_off": "masquer",
        "result_window_summary_count": "{count} sur {total}",
        "result_window_tooltip": "Cochez les actions qui ouvrent la fenêtre de traduction. Les autres copient directement la traduction dans le presse-papiers.",
        "result_window_mode_selection_tooltip": "Afficher la fenêtre après la traduction du texte sélectionné.",
        "result_window_mode_area_tooltip": "Afficher la fenêtre après la traduction d’une zone de l’écran.",
        "result_window_mode_main_tooltip": "Afficher la fenêtre après avoir cliqué sur Traduire.",
        "replace_selection_translate_label": "Traduire et remplacer la sélection :",
        "replace_selection_unavailable": "Le remplacement automatique sécurisé est actuellement disponible sous Windows.",
        "copy_hotkey_label": "Raccourci de copie :",
        "translate_hotkey_label": "Raccourci de traduction :",
        "remove_local_tesseract": "Supprimer Tesseract local",
        "remove_local_rapidocr": "Supprimer RapidOCR local",
        "remove_local_easyocr": "Supprimer EasyOCR local",
        "remove_local_hymt": "Supprimer Hy-MT local",
        "ocr_language_packs": "Modules linguistiques",
        "manage_ocr_languages": "Gérer les modules OCR et Argos",
        "clearing": "Nettoyage...",
        "cleared": "{size} nettoye",
        "yes": "Oui",
        "no": "Non",
        "cancel": "Annuler",
        "minimize": "Réduire",
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
        "update_check_on_launch": "启动时检查更新",
        "dim_screen_during_ocr": "选择 OCR 区域时调暗屏幕",
        "ocr_dim_strength_tooltip": "设置 OCR 选择区域外的变暗程度。",
        "restore_clipboard_after_selection": "处理所选文本后恢复剪贴板",
        "restore_clipboard_tooltip": "显示翻译或成功替换后恢复原剪贴板内容；明确的复制操作仍会保留结果。",
        "copy_notification": "复制文本后通知我",
        "copy_notification_tooltip": "当 Click'n'Translate 将结果复制到剪贴板时显示简短系统通知。",
        "create_bug_report": "创建安全错误报告",
        "bug_report_tooltip": "创建不包含剪贴板、历史记录或文档文本的诊断 ZIP。",
        "export_settings": "导出设置", "import_settings": "导入设置",
        "export_settings_tooltip": "将所有应用设置保存为可移植 JSON 文件。",
        "import_settings_tooltip": "加载 Click'n'Translate 设置 JSON 并立即应用。",
        "settings_exported": "设置已导出。\n\n{path}",
        "settings_imported": "设置已导入并应用。",
        "settings_transfer_failed": "无法传输设置。\n\n{error}",
        "settings_file_filter": "Click'n'Translate 设置 (*.json)",
        "ocr_behavior_heading": "OCR 行为",
        "updates_heading": "更新",
        "settings_page_main": "常规设置",
        "settings_page_updates": "OCR 与更新",
        "settings_page_game": "动态翻译",
        "game_settings_heading": "动态翻译",
        "game_languages": "语言：",
        "game_swap_languages": "交换动态翻译语言",
        "game_scan_interval": "扫描间隔：",
        "game_overlay_opacity": "翻译背景：",
        "game_pause_inactive": "绑定应用未激活时暂停",
        "game_pause_inactive_tooltip": "如果启动模式时的活动窗口被最小化或不再位于前台，OCR 会暂停；返回该窗口后会自动继续翻译。",
        "game_show_original": "在译文上方显示识别文本",
        "game_workflow_note": "启动动态模式，选择一个或多个文字区域后点击开始。译文会在原位置更新；再次启动该模式即可停止。",
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
        "error_title": "错误",
        "clear_translation_history_error": "无法清除翻译历史。",
        "clear_copy_history_error": "无法清除复制历史。",
        "copy_translated_text": "复制翻译文本",
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
        "game_translate_label": "动态模式：",
        "selection_translate_label": "选中文本翻译：",
        "toggle_window_hotkey_label": "显示 / 隐藏应用：",
        "result_window_label": "显示窗口：",
        "result_window_mode_selection": "文本",
        "result_window_mode_area": "区域",
        "result_window_mode_main": "按钮",
        "result_window_modes_header": "在以下操作后显示窗口：",
        "result_window_row_selection": "翻译选中的文本",
        "result_window_row_area": "翻译屏幕区域",
        "result_window_row_main": "点击“翻译”按钮",
        "result_window_summary_all": "全部",
        "result_window_summary_none": "从不",
        "result_window_summary_on": "显示",
        "result_window_summary_off": "隐藏",
        "result_window_summary_count": "{count}/{total}",
        "result_window_tooltip": "勾选需要打开翻译窗口的操作。未勾选的操作会直接把译文复制到剪贴板。",
        "result_window_mode_selection_tooltip": "翻译选中文本后显示窗口。",
        "result_window_mode_area_tooltip": "翻译屏幕区域后显示窗口。",
        "result_window_mode_main_tooltip": "点击“翻译”后显示窗口。",
        "replace_selection_translate_label": "翻译并替换所选文本：",
        "replace_selection_unavailable": "安全自动替换目前仅可在 Windows 上使用。",
        "copy_hotkey_label": "复制选区快捷键：",
        "translate_hotkey_label": "翻译快捷键：",
        "remove_local_tesseract": "删除本地 Tesseract",
        "remove_local_rapidocr": "删除本地 RapidOCR",
        "remove_local_easyocr": "删除本地 EasyOCR",
        "remove_local_hymt": "删除本地 Hy-MT",
        "ocr_language_packs": "语言包",
        "manage_ocr_languages": "管理 OCR 和 Argos 语言包",
        "clearing": "正在清除...",
        "cleared": "已清除 {size}",
        "yes": "是",
        "no": "否",
        "cancel": "取消",
        "minimize": "最小化",
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


SETTINGS_EXPORT_FORMAT = "clickntranslate-settings"
SETTINGS_EXPORT_SCHEMA = 1


def settings_export_payload(config):
    """Return a portable, JSON-only settings document."""
    safe = json.loads(json.dumps(dict(config or {}), ensure_ascii=False))
    return {
        "format": SETTINGS_EXPORT_FORMAT,
        "schema": SETTINGS_EXPORT_SCHEMA,
        "app_version": APP_VERSION,
        "settings": safe,
    }


def validated_import_settings(payload, defaults):
    """Validate an exported document and return known, type-safe settings."""
    if not isinstance(payload, dict):
        raise ValueError("The settings file must contain a JSON object.")
    if payload.get("format") != SETTINGS_EXPORT_FORMAT:
        raise ValueError("This is not a Click'n'Translate settings export.")
    try:
        schema = int(payload.get("schema", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("The settings schema is invalid.") from exc
    if schema < 1 or schema > SETTINGS_EXPORT_SCHEMA:
        raise ValueError(f"Unsupported settings schema: {schema}")
    raw = payload.get("settings")
    if not isinstance(raw, dict):
        raise ValueError("The export does not contain a settings object.")

    accepted = {}
    for key, value in raw.items():
        if key not in defaults:
            continue
        default = defaults[key]
        valid = False
        if isinstance(default, bool):
            valid = isinstance(value, bool)
        elif isinstance(default, int) and not isinstance(default, bool):
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif isinstance(default, float):
            valid = isinstance(value, (int, float)) and not isinstance(value, bool)
            if valid:
                value = float(value)
        elif isinstance(default, str):
            valid = isinstance(value, str)
        elif isinstance(default, (tuple, list)):
            valid = isinstance(value, (tuple, list))
            if valid:
                value = list(value)
        elif default is None:
            valid = value is None
        if valid:
            accepted[key] = value
    numeric_ranges = {
        "ocr_dim_strength": (0, 80),
        "game_capture_interval_ms": (450, 10000),
        "game_overlay_opacity": (45, 100),
        "game_text_similarity": (0.50, 1.0),
    }
    for key, (minimum, maximum) in numeric_ranges.items():
        if key in accepted:
            accepted[key] = max(minimum, min(maximum, accepted[key]))
    if not accepted:
        raise ValueError("The export contains no compatible settings.")
    return accepted


HISTORY_RECORD_TEXT = {
    "en": {"original": "Original", "translated": "Translation", "copy": "Copy", "delete": "Delete"},
    "ru": {"original": "Оригинал", "translated": "Перевод", "copy": "Копировать", "delete": "Удалить"},
    "es": {"original": "Original", "translated": "Traducción", "copy": "Copiar", "delete": "Eliminar"},
    "de": {"original": "Original", "translated": "Übersetzung", "copy": "Kopieren", "delete": "Löschen"},
    "fr": {"original": "Original", "translated": "Traduction", "copy": "Copier", "delete": "Supprimer"},
    "zh": {"original": "原文", "translated": "译文", "copy": "复制", "delete": "删除"},
}


def history_record_text(lang, key):
    texts = HISTORY_RECORD_TEXT.get(lang, HISTORY_RECORD_TEXT["en"])
    return texts.get(key, HISTORY_RECORD_TEXT["en"].get(key, key))


UPDATE_TEXT = {
    "en": {
        "store_updates": "Updates for this version are delivered by Microsoft Store. Open the Microsoft Store Library and choose Get updates.",
        "dev_build": "Auto-update is available only in the packaged app.\nOpen releases page?",
        "checking_button": "Checking...", "checking": "Checking updates...", "downloading_word": "Downloading",
        "downloading_button": "Downloading...", "apply_wait": "The update is being applied.\nPlease wait...",
        "apply_close": "The update is already being applied. Closing is disabled right now.\nPlease wait.",
        "canceling_button": "Canceling...", "canceling_clean": "Canceling the update...\nCleaning temporary files, please wait.",
        "canceling_wait": "Canceling the update...\nPlease wait.", "check_failed": "Failed to check for updates:\n{error}",
        "parse_failed": "Failed to parse update response.", "check_cancelled": "Update check was canceled.",
        "error_title": "Update error", "unknown_error": "Unknown update error.",
        "up_to_date": "You already have the latest version: V{version}",
        "no_asset": "No compatible auto-update asset found in the release. Open releases page?",
        "invalid_url": "Invalid update asset URL.", "available_title": "Update available",
        "available_prompt": "New version found: V{latest}\nCurrent version: V{current}\n\nInstall now?",
        "preparing_download": "Preparing download...", "stage_download": "Downloading update package...",
        "stage_checksum": "Downloading checksum...", "stage_verify": "Verifying checksum...", "stage_prepare": "Preparing update...",
        "cancelled": "Update canceled. Temporary files were removed.",
        "install_failed": "Failed to install update:\n{error}",
        "restart_ready": "Update V{version} is ready.\nRestarting the app...", "restarting": "Restarting...",
        "launch_title": "Update available",
        "launch_prompt": "Version V{latest} is out. You have V{current}.",
        "launch_update": "Update now",
        "launch_skip": "Skip this version",
        "launch_later": "Later",
    },
    "ru": {
        "store_updates": "Обновления этой версии устанавливает Microsoft Store. Откройте Библиотеку Microsoft Store и нажмите «Получить обновления».",
        "dev_build": "Автообновление работает только в собранной версии приложения.\nОткрыть страницу релизов?",
        "checking_button": "Проверка...", "checking": "Проверка обновлений...", "downloading_word": "Скачивание",
        "downloading_button": "Скачивание...", "apply_wait": "Обновление уже применяется.\nПожалуйста, подождите...",
        "apply_close": "Обновление уже применяется. Закрытие сейчас недоступно.\nПожалуйста, подождите.",
        "canceling_button": "Отмена...", "canceling_clean": "Отмена обновления...\nУдаляем временные файлы, пожалуйста, подождите.",
        "canceling_wait": "Отмена обновления...\nПожалуйста, подождите.", "check_failed": "Не удалось проверить обновления:\n{error}",
        "parse_failed": "Не удалось обработать ответ от сервера обновлений.", "check_cancelled": "Проверка обновлений отменена.",
        "error_title": "Ошибка обновления", "unknown_error": "Неизвестная ошибка обновления.",
        "up_to_date": "У вас уже актуальная версия: V{version}",
        "no_asset": "В релизе нет подходящего файла для автообновления. Открыть страницу релизов?",
        "invalid_url": "Некорректный URL файла обновления.", "available_title": "Доступно обновление",
        "available_prompt": "Найдена новая версия: V{latest}\nТекущая версия: V{current}\n\nУстановить сейчас?",
        "preparing_download": "Подготовка загрузки...", "stage_download": "Загрузка файла обновления...",
        "stage_checksum": "Загрузка контрольной суммы...", "stage_verify": "Проверка контрольной суммы...", "stage_prepare": "Подготовка обновления...",
        "cancelled": "Обновление отменено. Временные файлы удалены.",
        "install_failed": "Не удалось установить обновление:\n{error}",
        "restart_ready": "Обновление до V{version} готово.\nПерезапуск приложения...", "restarting": "Перезапуск...",
        "launch_title": "Доступно обновление",
        "launch_prompt": "Вышла версия V{latest}. У вас V{current}.",
        "launch_update": "Обновить",
        "launch_skip": "Пропустить эту версию",
        "launch_later": "Позже",
    },
    "es": {
        "store_updates": "Las actualizaciones de esta versión se instalan desde Microsoft Store. Abre la Biblioteca de Microsoft Store y selecciona Obtener actualizaciones.",
        "dev_build": "La actualización automática solo está disponible en la aplicación compilada.\n¿Abrir la página de versiones?",
        "checking_button": "Comprobando...", "checking": "Buscando actualizaciones...", "downloading_word": "Descargando",
        "downloading_button": "Descargando...", "apply_wait": "La actualización se está aplicando.\nEspera...",
        "apply_close": "La actualización ya se está aplicando. No se puede cerrar ahora.\nEspera.",
        "canceling_button": "Cancelando...", "canceling_clean": "Cancelando la actualización...\nEliminando archivos temporales, espera.",
        "canceling_wait": "Cancelando la actualización...\nEspera.", "check_failed": "No se pudo buscar actualizaciones:\n{error}",
        "parse_failed": "No se pudo procesar la respuesta del servidor de actualizaciones.", "check_cancelled": "Se canceló la búsqueda de actualizaciones.",
        "error_title": "Error de actualización", "unknown_error": "Error de actualización desconocido.",
        "up_to_date": "Ya tienes la versión más reciente: V{version}",
        "no_asset": "La versión no contiene un archivo compatible para la actualización automática. ¿Abrir la página de versiones?",
        "invalid_url": "La URL del archivo de actualización no es válida.", "available_title": "Actualización disponible",
        "available_prompt": "Nueva versión: V{latest}\nVersión actual: V{current}\n\n¿Instalar ahora?",
        "preparing_download": "Preparando la descarga...", "stage_download": "Descargando el paquete de actualización...",
        "stage_checksum": "Descargando la suma de comprobación...", "stage_verify": "Verificando la suma de comprobación...", "stage_prepare": "Preparando la actualización...",
        "cancelled": "Actualización cancelada. Se eliminaron los archivos temporales.",
        "install_failed": "No se pudo instalar la actualización:\n{error}",
        "restart_ready": "La actualización V{version} está lista.\nReiniciando la aplicación...", "restarting": "Reiniciando...",
        "launch_title": "Actualización disponible",
        "launch_prompt": "Ya está la versión V{latest}. Tienes la V{current}.",
        "launch_update": "Actualizar",
        "launch_skip": "Omitir esta versión",
        "launch_later": "Más tarde",
    },
    "de": {
        "store_updates": "Updates für diese Version werden über den Microsoft Store installiert. Öffne die Bibliothek im Microsoft Store und wähle Updates abrufen.",
        "dev_build": "Die automatische Aktualisierung ist nur in der kompilierten App verfügbar.\nRelease-Seite öffnen?",
        "checking_button": "Prüfen...", "checking": "Nach Updates suchen...", "downloading_word": "Herunterladen",
        "downloading_button": "Herunterladen...", "apply_wait": "Das Update wird angewendet.\nBitte warten...",
        "apply_close": "Das Update wird bereits angewendet. Schließen ist momentan nicht möglich.\nBitte warten.",
        "canceling_button": "Abbrechen...", "canceling_clean": "Update wird abgebrochen...\nTemporäre Dateien werden entfernt. Bitte warten.",
        "canceling_wait": "Update wird abgebrochen...\nBitte warten.", "check_failed": "Updates konnten nicht geprüft werden:\n{error}",
        "parse_failed": "Die Antwort des Update-Servers konnte nicht verarbeitet werden.", "check_cancelled": "Die Update-Prüfung wurde abgebrochen.",
        "error_title": "Update-Fehler", "unknown_error": "Unbekannter Update-Fehler.",
        "up_to_date": "Du verwendest bereits die neueste Version: V{version}",
        "no_asset": "Das Release enthält keine kompatible Datei für die automatische Aktualisierung. Release-Seite öffnen?",
        "invalid_url": "Die URL der Update-Datei ist ungültig.", "available_title": "Update verfügbar",
        "available_prompt": "Neue Version: V{latest}\nAktuelle Version: V{current}\n\nJetzt installieren?",
        "preparing_download": "Download wird vorbereitet...", "stage_download": "Update-Paket wird heruntergeladen...",
        "stage_checksum": "Prüfsumme wird heruntergeladen...", "stage_verify": "Prüfsumme wird geprüft...", "stage_prepare": "Update wird vorbereitet...",
        "cancelled": "Update abgebrochen. Temporäre Dateien wurden entfernt.",
        "install_failed": "Update konnte nicht installiert werden:\n{error}",
        "restart_ready": "Update V{version} ist bereit.\nDie App wird neu gestartet...", "restarting": "Neustart...",
        "launch_title": "Update verfügbar",
        "launch_prompt": "Version V{latest} ist da. Sie haben V{current}.",
        "launch_update": "Jetzt aktualisieren",
        "launch_skip": "Diese Version überspringen",
        "launch_later": "Später",
    },
    "fr": {
        "store_updates": "Les mises à jour de cette version sont installées par le Microsoft Store. Ouvrez la Bibliothèque du Microsoft Store et choisissez Obtenir les mises à jour.",
        "dev_build": "La mise à jour automatique est disponible uniquement dans l’application compilée.\nOuvrir la page des versions ?",
        "checking_button": "Vérification...", "checking": "Recherche de mises à jour...", "downloading_word": "Téléchargement",
        "downloading_button": "Téléchargement...", "apply_wait": "La mise à jour est en cours d’application.\nVeuillez patienter...",
        "apply_close": "La mise à jour est déjà en cours d’application. La fermeture est momentanément impossible.\nVeuillez patienter.",
        "canceling_button": "Annulation...", "canceling_clean": "Annulation de la mise à jour...\nSuppression des fichiers temporaires, veuillez patienter.",
        "canceling_wait": "Annulation de la mise à jour...\nVeuillez patienter.", "check_failed": "Impossible de rechercher les mises à jour :\n{error}",
        "parse_failed": "Impossible de traiter la réponse du serveur de mises à jour.", "check_cancelled": "La recherche de mises à jour a été annulée.",
        "error_title": "Erreur de mise à jour", "unknown_error": "Erreur de mise à jour inconnue.",
        "up_to_date": "Vous utilisez déjà la dernière version : V{version}",
        "no_asset": "La version ne contient aucun fichier compatible avec la mise à jour automatique. Ouvrir la page des versions ?",
        "invalid_url": "L’URL du fichier de mise à jour n’est pas valide.", "available_title": "Mise à jour disponible",
        "available_prompt": "Nouvelle version : V{latest}\nVersion actuelle : V{current}\n\nInstaller maintenant ?",
        "preparing_download": "Préparation du téléchargement...", "stage_download": "Téléchargement du paquet de mise à jour...",
        "stage_checksum": "Téléchargement de la somme de contrôle...", "stage_verify": "Vérification de la somme de contrôle...", "stage_prepare": "Préparation de la mise à jour...",
        "cancelled": "Mise à jour annulée. Les fichiers temporaires ont été supprimés.",
        "install_failed": "Impossible d’installer la mise à jour :\n{error}",
        "restart_ready": "La mise à jour V{version} est prête.\nRedémarrage de l’application...", "restarting": "Redémarrage...",
        "launch_title": "Mise à jour disponible",
        "launch_prompt": "La version V{latest} est sortie. Vous avez la V{current}.",
        "launch_update": "Mettre à jour",
        "launch_skip": "Ignorer cette version",
        "launch_later": "Plus tard",
    },
    "zh": {
        "store_updates": "此版本由 Microsoft Store 提供更新。请打开 Microsoft Store 的“库”，然后选择“获取更新”。",
        "dev_build": "自动更新仅适用于已打包的应用。\n是否打开发布页面？",
        "checking_button": "正在检查...", "checking": "正在检查更新...", "downloading_word": "正在下载",
        "downloading_button": "正在下载...", "apply_wait": "正在应用更新。\n请稍候...",
        "apply_close": "更新已在应用中，现在无法关闭。\n请稍候。",
        "canceling_button": "正在取消...", "canceling_clean": "正在取消更新...\n正在清理临时文件，请稍候。",
        "canceling_wait": "正在取消更新...\n请稍候。", "check_failed": "无法检查更新：\n{error}",
        "parse_failed": "无法处理更新服务器的响应。", "check_cancelled": "已取消更新检查。",
        "error_title": "更新错误", "unknown_error": "未知更新错误。",
        "up_to_date": "当前已是最新版本：V{version}",
        "no_asset": "此版本中没有兼容的自动更新文件。是否打开发布页面？",
        "invalid_url": "更新文件 URL 无效。", "available_title": "有可用更新",
        "available_prompt": "发现新版本：V{latest}\n当前版本：V{current}\n\n现在安装吗？",
        "preparing_download": "正在准备下载...", "stage_download": "正在下载更新包...",
        "stage_checksum": "正在下载校验和...", "stage_verify": "正在验证校验和...", "stage_prepare": "正在准备更新...",
        "cancelled": "更新已取消，临时文件已删除。", "install_failed": "无法安装更新：\n{error}",
        "restart_ready": "更新 V{version} 已准备好。\n正在重启应用...", "restarting": "正在重启...",
        "launch_title": "有可用更新",
        "launch_prompt": "V{latest} 已发布，您当前是 V{current}。",
        "launch_update": "立即更新",
        "launch_skip": "跳过此版本",
        "launch_later": "稍后",
    },
}


ENGINE_TEXT = {
    "en": {
        "not_found": "{engine} not found", "install": "Install", "cancel": "Cancel", "remove": "Remove",
        "tesseract_prompt": "Tesseract-OCR was not found. Download and install it locally?",
        "easyocr_prompt": "EasyOCR is not installed locally. Install the neural OCR engine into the app folder?\n\nThis needs internet and about 1 GB of free disk space. The app downloads its own private installer runtime; you do not need to install Python. Language models are downloaded on first recognition. Packages will be saved to ocr\\easyocr.",
        "rapidocr_prompt": "RapidOCR is not installed locally. Install the neural OCR engine into the app folder?\n\nThis needs internet. The app downloads its own private installer runtime; you do not need to install Python. Packages will be saved to ocr\\rapidocr, and models will be cached there on first recognition.",
        "hymt_prompt": "The local Hy-MT model is not installed. Download and install the offline translation package?\n\nAbout 1.2 GB will be downloaded: the Hy-MT model and local llama.cpp runtime.",
        "preparing": "Preparing {engine} install...", "downloading_packages": "Downloading and installing {engine} packages...",
        "downloading_engine": "Downloading {engine}...", "extracting_engine": "Extracting {engine}...",
        "downloading_language": "Downloading language data {name}...", "applying": "Applying install...", "done": "Done",
        "canceling": "Canceling install...", "ready": "{engine} is installed and ready.",
        "hymt_ready": "Hy-MT is installed and ready for offline translation.", "error_title": "{engine} error",
        "install_failed": "Failed to install {engine}:\n{error}", "cancelled_title": "Cancelled",
        "install_cancelled": "{engine} installation canceled. Temporary files were removed.",
        "remove_title": "Remove {engine}", "remove_ocr_prompt": "Remove the local {engine} engine from the app folder?",
        "remove_hymt_prompt": "Remove the local Hy-MT model and runtime from the app folder?", "removed": "Local {engine} was removed.",
        "remove_failed": "Failed to remove {engine}:\n{error}", "hymt_runtime": "Downloading Hy-MT runtime...",
        "hymt_extract": "Extracting Hy-MT runtime...", "hymt_model": "Downloading Hy-MT model...", "hymt_license": "Saving Hy-MT license...",
    },
    "ru": {
        "not_found": "{engine} не найден", "install": "Установить", "cancel": "Отмена", "remove": "Удалить",
        "tesseract_prompt": "Tesseract-OCR не найден. Скачать и установить локально?",
        "easyocr_prompt": "EasyOCR не установлен локально. Установить нейросетевой OCR в папку программы?\n\nПонадобится интернет и около 1 ГБ свободного места. Программа сама загрузит изолированную среду установки — отдельно ставить Python не нужно. Языковые модели загрузятся при первом распознавании. Пакеты будут сохранены в ocr\\easyocr.",
        "rapidocr_prompt": "RapidOCR не установлен локально. Установить нейросетевой OCR в папку программы?\n\nПонадобится интернет. Программа сама загрузит изолированную среду установки — отдельно ставить Python не нужно. Пакеты будут сохранены в ocr\\rapidocr, модели будут кешироваться там же при первом распознавании.",
        "hymt_prompt": "Локальная модель Hy-MT не установлена. Скачать и установить офлайн-пакет перевода?\n\nБудет скачано около 1,2 ГБ: модель Hy-MT и локальный runtime llama.cpp.",
        "preparing": "Подготовка установки {engine}...", "downloading_packages": "Загрузка и установка пакетов {engine}...",
        "downloading_engine": "Загрузка {engine}...", "extracting_engine": "Распаковка {engine}...",
        "downloading_language": "Загрузка языковой модели {name}...", "applying": "Применение установки...", "done": "Готово",
        "canceling": "Отмена установки...", "ready": "{engine} установлен и готов к работе.",
        "hymt_ready": "Hy-MT установлен и готов к офлайн-переводу.", "error_title": "Ошибка {engine}",
        "install_failed": "Не удалось установить {engine}:\n{error}", "cancelled_title": "Отмена",
        "install_cancelled": "Установка {engine} отменена. Временные файлы удалены.",
        "remove_title": "Удалить {engine}", "remove_ocr_prompt": "Удалить локальный движок {engine} из папки программы?",
        "remove_hymt_prompt": "Удалить локальную модель Hy-MT и runtime из папки программы?", "removed": "Локальный {engine} удалён.",
        "remove_failed": "Не удалось удалить {engine}:\n{error}", "hymt_runtime": "Загрузка runtime Hy-MT...",
        "hymt_extract": "Распаковка runtime Hy-MT...", "hymt_model": "Загрузка модели Hy-MT...", "hymt_license": "Сохранение лицензии Hy-MT...",
    },
    "es": {
        "not_found": "No se encontró {engine}", "install": "Instalar", "cancel": "Cancelar", "remove": "Eliminar",
        "tesseract_prompt": "No se encontró Tesseract-OCR. ¿Descargarlo e instalarlo localmente?",
        "easyocr_prompt": "EasyOCR no está instalado localmente. ¿Instalar el motor OCR neuronal en la carpeta de la aplicación?\n\nSe necesita internet y aproximadamente 1 GB de espacio libre. La aplicación descarga su propio entorno de instalación; no necesitas instalar Python. Los modelos de idioma se descargan durante el primer reconocimiento. Los paquetes se guardarán en ocr\\easyocr.",
        "rapidocr_prompt": "RapidOCR no está instalado localmente. ¿Instalar el motor OCR neuronal en la carpeta de la aplicación?\n\nSe necesita internet. La aplicación descarga su propio entorno de instalación; no necesitas instalar Python. Los paquetes se guardarán en ocr\\rapidocr y los modelos se almacenarán allí durante el primer reconocimiento.",
        "hymt_prompt": "El modelo local Hy-MT no está instalado. ¿Descargar e instalar el paquete de traducción sin conexión?\n\nSe descargarán aproximadamente 1,2 GB: el modelo Hy-MT y el runtime local de llama.cpp.",
        "preparing": "Preparando la instalación de {engine}...", "downloading_packages": "Descargando e instalando paquetes de {engine}...",
        "downloading_engine": "Descargando {engine}...", "extracting_engine": "Extrayendo {engine}...",
        "downloading_language": "Descargando datos del idioma {name}...", "applying": "Aplicando la instalación...", "done": "Listo",
        "canceling": "Cancelando la instalación...", "ready": "{engine} está instalado y listo.",
        "hymt_ready": "Hy-MT está instalado y listo para traducir sin conexión.", "error_title": "Error de {engine}",
        "install_failed": "No se pudo instalar {engine}:\n{error}", "cancelled_title": "Cancelado",
        "install_cancelled": "Se canceló la instalación de {engine}. Se eliminaron los archivos temporales.",
        "remove_title": "Eliminar {engine}", "remove_ocr_prompt": "¿Eliminar el motor local {engine} de la carpeta de la aplicación?",
        "remove_hymt_prompt": "¿Eliminar el modelo local Hy-MT y el runtime de la carpeta de la aplicación?", "removed": "Se eliminó {engine} local.",
        "remove_failed": "No se pudo eliminar {engine}:\n{error}", "hymt_runtime": "Descargando el runtime de Hy-MT...",
        "hymt_extract": "Extrayendo el runtime de Hy-MT...", "hymt_model": "Descargando el modelo Hy-MT...", "hymt_license": "Guardando la licencia de Hy-MT...",
    },
    "de": {
        "not_found": "{engine} nicht gefunden", "install": "Installieren", "cancel": "Abbrechen", "remove": "Entfernen",
        "tesseract_prompt": "Tesseract-OCR wurde nicht gefunden. Lokal herunterladen und installieren?",
        "easyocr_prompt": "EasyOCR ist nicht lokal installiert. Die neuronale OCR-Engine im App-Ordner installieren?\n\nDafür werden Internet und etwa 1 GB freier Speicherplatz benötigt. Die App lädt eine eigene isolierte Installationsumgebung; Python muss nicht separat installiert werden. Sprachmodelle werden bei der ersten Erkennung geladen. Die Pakete werden unter ocr\\easyocr gespeichert.",
        "rapidocr_prompt": "RapidOCR ist nicht lokal installiert. Die neuronale OCR-Engine im App-Ordner installieren?\n\nDafür wird Internet benötigt. Die App lädt eine eigene isolierte Installationsumgebung; Python muss nicht separat installiert werden. Die Pakete werden unter ocr\\rapidocr gespeichert; Modelle werden bei der ersten Erkennung dort zwischengespeichert.",
        "hymt_prompt": "Das lokale Hy-MT-Modell ist nicht installiert. Das Offline-Übersetzungspaket herunterladen und installieren?\n\nEtwa 1,2 GB werden geladen: das Hy-MT-Modell und die lokale llama.cpp-Laufzeit.",
        "preparing": "Installation von {engine} wird vorbereitet...", "downloading_packages": "Pakete für {engine} werden heruntergeladen und installiert...",
        "downloading_engine": "{engine} wird heruntergeladen...", "extracting_engine": "{engine} wird entpackt...",
        "downloading_language": "Sprachdaten {name} werden heruntergeladen...", "applying": "Installation wird angewendet...", "done": "Fertig",
        "canceling": "Installation wird abgebrochen...", "ready": "{engine} ist installiert und bereit.",
        "hymt_ready": "Hy-MT ist installiert und für Offline-Übersetzungen bereit.", "error_title": "{engine}-Fehler",
        "install_failed": "{engine} konnte nicht installiert werden:\n{error}", "cancelled_title": "Abgebrochen",
        "install_cancelled": "Die Installation von {engine} wurde abgebrochen. Temporäre Dateien wurden entfernt.",
        "remove_title": "{engine} entfernen", "remove_ocr_prompt": "Die lokale {engine}-Engine aus dem App-Ordner entfernen?",
        "remove_hymt_prompt": "Das lokale Hy-MT-Modell und die Laufzeit aus dem App-Ordner entfernen?", "removed": "Das lokale {engine} wurde entfernt.",
        "remove_failed": "{engine} konnte nicht entfernt werden:\n{error}", "hymt_runtime": "Hy-MT-Laufzeit wird heruntergeladen...",
        "hymt_extract": "Hy-MT-Laufzeit wird entpackt...", "hymt_model": "Hy-MT-Modell wird heruntergeladen...", "hymt_license": "Hy-MT-Lizenz wird gespeichert...",
    },
    "fr": {
        "not_found": "{engine} introuvable", "install": "Installer", "cancel": "Annuler", "remove": "Supprimer",
        "tesseract_prompt": "Tesseract-OCR est introuvable. Le télécharger et l’installer localement ?",
        "easyocr_prompt": "EasyOCR n’est pas installé localement. Installer le moteur OCR neuronal dans le dossier de l’application ?\n\nUne connexion Internet et environ 1 Go d’espace libre sont nécessaires. L’application télécharge son propre environnement d’installation isolé ; vous n’avez pas besoin d’installer Python. Les modèles de langue sont téléchargés lors de la première reconnaissance. Les paquets seront enregistrés dans ocr\\easyocr.",
        "rapidocr_prompt": "RapidOCR n’est pas installé localement. Installer le moteur OCR neuronal dans le dossier de l’application ?\n\nUne connexion Internet est nécessaire. L’application télécharge son propre environnement d’installation isolé ; vous n’avez pas besoin d’installer Python. Les paquets seront enregistrés dans ocr\\rapidocr et les modèles y seront mis en cache lors de la première reconnaissance.",
        "hymt_prompt": "Le modèle Hy-MT local n’est pas installé. Télécharger et installer le paquet de traduction hors ligne ?\n\nEnviron 1,2 Go seront téléchargés : le modèle Hy-MT et le runtime local llama.cpp.",
        "preparing": "Préparation de l’installation de {engine}...", "downloading_packages": "Téléchargement et installation des paquets de {engine}...",
        "downloading_engine": "Téléchargement de {engine}...", "extracting_engine": "Extraction de {engine}...",
        "downloading_language": "Téléchargement des données de langue {name}...", "applying": "Application de l’installation...", "done": "Terminé",
        "canceling": "Annulation de l’installation...", "ready": "{engine} est installé et prêt.",
        "hymt_ready": "Hy-MT est installé et prêt pour la traduction hors ligne.", "error_title": "Erreur {engine}",
        "install_failed": "Impossible d’installer {engine} :\n{error}", "cancelled_title": "Annulé",
        "install_cancelled": "L’installation de {engine} a été annulée. Les fichiers temporaires ont été supprimés.",
        "remove_title": "Supprimer {engine}", "remove_ocr_prompt": "Supprimer le moteur local {engine} du dossier de l’application ?",
        "remove_hymt_prompt": "Supprimer le modèle Hy-MT local et le runtime du dossier de l’application ?", "removed": "Le {engine} local a été supprimé.",
        "remove_failed": "Impossible de supprimer {engine} :\n{error}", "hymt_runtime": "Téléchargement du runtime Hy-MT...",
        "hymt_extract": "Extraction du runtime Hy-MT...", "hymt_model": "Téléchargement du modèle Hy-MT...", "hymt_license": "Enregistrement de la licence Hy-MT...",
    },
    "zh": {
        "not_found": "未找到 {engine}", "install": "安装", "cancel": "取消", "remove": "删除",
        "tesseract_prompt": "未找到 Tesseract-OCR。是否下载并在本地安装？",
        "easyocr_prompt": "EasyOCR 未在本地安装。是否将神经网络 OCR 引擎安装到应用文件夹？\n\n需要联网并预留约 1 GB 可用空间。应用会自行下载独立的安装环境，无需另外安装 Python。语言模型会在首次识别时下载。软件包将保存到 ocr\\easyocr。",
        "rapidocr_prompt": "RapidOCR 未在本地安装。是否将神经网络 OCR 引擎安装到应用文件夹？\n\n需要联网。应用会自行下载独立的安装环境，无需另外安装 Python。软件包将保存到 ocr\\rapidocr，模型会在首次识别时缓存在同一位置。",
        "hymt_prompt": "本地 Hy-MT 模型尚未安装。是否下载并安装离线翻译包？\n\n将下载约 1.2 GB：Hy-MT 模型和本地 llama.cpp 运行时。",
        "preparing": "正在准备安装 {engine}...", "downloading_packages": "正在下载并安装 {engine} 软件包...",
        "downloading_engine": "正在下载 {engine}...", "extracting_engine": "正在解压 {engine}...",
        "downloading_language": "正在下载语言数据 {name}...", "applying": "正在应用安装...", "done": "完成",
        "canceling": "正在取消安装...", "ready": "{engine} 已安装并可用。",
        "hymt_ready": "Hy-MT 已安装并可用于离线翻译。", "error_title": "{engine} 错误",
        "install_failed": "无法安装 {engine}：\n{error}", "cancelled_title": "已取消",
        "install_cancelled": "已取消安装 {engine}，临时文件已删除。",
        "remove_title": "删除 {engine}", "remove_ocr_prompt": "是否从应用文件夹中删除本地 {engine} 引擎？",
        "remove_hymt_prompt": "是否从应用文件夹中删除本地 Hy-MT 模型和运行时？", "removed": "本地 {engine} 已删除。",
        "remove_failed": "无法删除 {engine}：\n{error}", "hymt_runtime": "正在下载 Hy-MT 运行时...",
        "hymt_extract": "正在解压 Hy-MT 运行时...", "hymt_model": "正在下载 Hy-MT 模型...", "hymt_license": "正在保存 Hy-MT 许可证...",
    },
}


def update_text(lang, key, **values):
    texts = UPDATE_TEXT.get(lang, UPDATE_TEXT["en"])
    template = texts.get(key, UPDATE_TEXT["en"].get(key, key))
    return template.format(**values)


def engine_text(lang, key, **values):
    texts = ENGINE_TEXT.get(lang, ENGINE_TEXT["en"])
    template = texts.get(key, ENGINE_TEXT["en"].get(key, key))
    return template.format(**values)

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
    import os
    def get_portable_dir():
        return _portable_base_dir()
    data_dir = os.path.join(get_portable_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, filename)

def ensure_json_file(filepath, default_content):
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_content, f, ensure_ascii=False, indent=4)


EASYOCR_MODEL_GROUP_BY_LANGUAGE = {
    "en": "english_g2",
    "ru": "cyrillic_g2",
    "uk": "cyrillic_g2",
    "de": "latin_g2",
    "fr": "latin_g2",
    "es": "latin_g2",
    "it": "latin_g2",
    "pt": "latin_g2",
    "pl": "latin_g2",
    "tr": "latin_g2",
    "nl": "latin_g2",
    "zh": "zh_sim_g2",
    "ch_sim": "zh_sim_g2",
    "ja": "japanese_g2",
    "ko": "korean_g2",
    "ar": "arabic",
    "hi": "devanagari",
}

EASYOCR_MODEL_FILE_VARIANTS = {
    "english_g2": ("english_g2.pth",),
    "cyrillic_g2": ("cyrillic_g2.pth", "cyrillic.pth"),
    "latin_g2": ("latin_g2.pth", "latin.pth"),
    "zh_sim_g2": ("zh_sim_g2.pth", "chinese_sim.pth"),
    "japanese_g2": ("japanese_g2.pth", "japanese.pth"),
    "korean_g2": ("korean_g2.pth", "korean.pth"),
    "arabic": ("arabic.pth",),
    "devanagari": ("devanagari.pth",),
}


LANGUAGE_MANAGER_TEXT = {
    "en": {
        "intro": "Install OCR languages or Argos offline translation directions here. Packages are downloaded in advance, not during recognition or translation.",
        "refresh": "Refresh", "windows_note": "Shows OCR languages available in Windows. Install only OCR without adding a keyboard.",
        "install_selected": "Install selected", "windows_settings": "Windows settings", "tesseract_note": "Tick languages to download into the local tessdata folder.",
        "install_engine": "Install engine", "easyocr_note": "Tick languages to predownload EasyOCR models. English is added as a fallback.",
        "remove_engine": "Remove engine",
        "remove_engine_tooltip": "Delete the installed {engine} engine from this computer.",
        "hymt_note": "Hy-MT is one local translation model, not per-language packages. Install it here and it appears in the translator list.",
        "translation_engine": "Translation engine", "local_model": "Local model",
        "rapidocr_note": "RapidOCR has no separate language packages. Its local neural engine includes one Chinese + English model. For Russian use Windows OCR, Tesseract, or EasyOCR.",
        "component": "Component", "package": "Package", "status": "Status", "argos_note": "All available Argos packages are shown. Non-English pairs use two packages through English.",
        "remove_highlighted": "Remove highlighted", "direction": "Direction", "search": "Search: Russian, ru, en→ru…", "language": "Language",
        "installed": "Installed", "missing": "Missing", "can_download": "Can download", "engine_missing": "{engine} missing", "checking": "Checking…",
        "unavailable": "Not available on this Windows build", "first_use": "Prepared on first OCR", "engine_first": "Install the engine first",
        "ocr_engine": "OCR engine", "runtime": "Neural runtime", "detector": "Text detection + orientation", "recognition": "Recognition",
        "loading": "Loading package list…", "load_error": "Could not load package list: ", "no_match": "No packages match your search", "no_packages": "No packages found",
        "no_selection": "Tick at least one language to install.", "already": "{engine} is already installed.", "still": "{engine} is still being checked. Please wait a moment.",
        "win_confirm": "Install selected Windows OCR components?\n\nAdministrator permission will be requested. Only OCR is installed; no keyboard or input layout is added.",
        "easy_prompt": "EasyOCR must be installed first. Start engine installation?", "argos_installed": "Selected Argos directions are installed.",
        "highlight": "Highlight one or more installed rows.", "remove_confirm": "Remove Argos packages: {packages}?\n\nThese directions will no longer work offline.", "removed": "Selected Argos packages were removed.",
        "preparing": "Preparing…", "canceling": "Canceling…", "install_failed": "Failed to install language packages:\n", "ready": "Selected language packages are ready.", "canceled": "Canceled",
        "tess_down": "Tesseract: downloading languages…", "win_wait": "Windows OCR: waiting for administrator permission…", "win_done": "Windows OCR: done",
        "win_installing": "Windows OCR: installing {language} ({current}/{total})…",
        "win_checking": "Windows OCR: checking {language}…",
        "win_verifying": "Windows OCR: verifying {language}…",
        "easy_down": "EasyOCR: downloading {language} models…", "easy_done": "EasyOCR: done",
        "ocr_section": "OCR", "translation_section": "Translation",
        "engine_not_installed_title": "{engine} is not installed",
        "engine_not_installed_body": "Install the engine first. Language packages will appear here after installation.",
        "repair_needed": "Needs repair",
        "remove_packages_confirm": "Remove selected {engine} packages: {packages}?",
        "packages_removed": "Selected {engine} language packages were removed.",
        "remove_failed": "Failed to remove language packages:\n",
        "win_removing": "Windows OCR: removing {language} ({current}/{total})…",
        "win_rolling_back": "Windows OCR: canceling and removing incomplete packages…",
    },
    "ru": {
        "intro": "Установите языки OCR или офлайн-направления Argos. Пакеты загружаются заранее, а не во время распознавания или перевода.",
        "refresh": "Обновить", "windows_note": "Показаны OCR-языки Windows. Можно установить только OCR без добавления клавиатуры.",
        "install_selected": "Установить выбранные", "windows_settings": "Настройки Windows", "tesseract_note": "Отметьте языки для загрузки в локальную папку tessdata.",
        "install_engine": "Установить движок", "easyocr_note": "Отметьте языки для загрузки моделей EasyOCR. Английский добавляется как резервный.",
        "remove_engine": "Удалить движок",
        "remove_engine_tooltip": "Удалить установленный движок {engine} с этого компьютера.",
        "hymt_note": "Hy-MT — одна локальная модель перевода, а не пакеты по языкам. Установите её здесь, и она появится в списке переводчиков.",
        "translation_engine": "Движок перевода", "local_model": "Локальная модель",
        "rapidocr_note": "Для RapidOCR не нужны отдельные языковые пакеты. Локальный нейросетевой движок включает одну модель Chinese + English. Для русского используйте Windows OCR, Tesseract или EasyOCR.",
        "component": "Компонент", "package": "Пакет", "status": "Статус", "argos_note": "Показаны все пакеты Argos. Неанглийские пары используют два пакета через английский.",
        "remove_highlighted": "Удалить выделенные", "direction": "Направление", "search": "Поиск: русский, ru, en→ru…", "language": "Язык",
        "installed": "Установлен", "missing": "Не установлен", "can_download": "Можно скачать", "engine_missing": "{engine} не установлен", "checking": "Проверка…",
        "unavailable": "Недоступен в этой версии Windows", "first_use": "Подготовится при первом OCR", "engine_first": "Сначала установите движок",
        "ocr_engine": "OCR-движок", "runtime": "Нейросетевой runtime", "detector": "Поиск и ориентация текста", "recognition": "Распознавание",
        "loading": "Загрузка списка пакетов…", "load_error": "Не удалось загрузить список: ", "no_match": "По запросу ничего не найдено", "no_packages": "Пакеты не найдены",
        "no_selection": "Отметьте хотя бы один язык.", "already": "{engine} уже установлен.", "still": "Проверка {engine} ещё выполняется. Подождите немного.",
        "win_confirm": "Установить выбранные OCR-компоненты Windows?\n\nБудет запрошено разрешение администратора. Устанавливается только OCR без клавиатуры и раскладки.",
        "easy_prompt": "Сначала нужно установить EasyOCR. Запустить установку движка?", "argos_installed": "Выбранные направления Argos установлены.",
        "highlight": "Выделите установленные строки.", "remove_confirm": "Удалить пакеты Argos: {packages}?\n\nЭти направления перестанут работать офлайн.", "removed": "Выбранные пакеты Argos удалены.",
        "preparing": "Подготовка…", "canceling": "Отмена…", "install_failed": "Не удалось установить языковые пакеты:\n", "ready": "Выбранные пакеты готовы.", "canceled": "Отменено",
        "tess_down": "Tesseract: загрузка языков…", "win_wait": "Windows OCR: ожидание разрешения администратора…", "win_done": "Windows OCR: готово",
        "win_installing": "Windows OCR: установка {language} ({current}/{total})…",
        "win_checking": "Windows OCR: проверка {language}…",
        "win_verifying": "Windows OCR: подтверждение установки {language}…",
        "easy_down": "EasyOCR: загрузка моделей {language}…", "easy_done": "EasyOCR: готово",
        "ocr_section": "OCR", "translation_section": "Переводчики",
        "engine_not_installed_title": "{engine} не установлен",
        "engine_not_installed_body": "Сначала установите движок. После установки здесь появятся языковые пакеты.",
        "repair_needed": "Требуется восстановление",
        "remove_packages_confirm": "Удалить выбранные пакеты {engine}: {packages}?",
        "packages_removed": "Выбранные языковые пакеты {engine} удалены.",
        "remove_failed": "Не удалось удалить языковые пакеты:\n",
        "win_removing": "Windows OCR: удаление {language} ({current}/{total})…",
        "win_rolling_back": "Windows OCR: отмена и удаление незавершённых пакетов…",
    },
    "es": {
        "intro": "Instala aquí idiomas OCR o direcciones sin conexión de Argos. Los paquetes se descargan por adelantado.",
        "refresh": "Actualizar", "windows_note": "Muestra los idiomas OCR de Windows. Instala solo OCR sin añadir un teclado.",
        "install_selected": "Instalar seleccionados", "windows_settings": "Configuración de Windows", "tesseract_note": "Marca idiomas para descargarlos en la carpeta tessdata local.",
        "install_engine": "Instalar motor", "easyocr_note": "Marca idiomas para descargar modelos EasyOCR. Se añade inglés como reserva.",
        "remove_engine": "Eliminar motor",
        "remove_engine_tooltip": "Eliminar el motor {engine} instalado en este equipo.",
        "hymt_note": "Hy-MT es un único modelo local de traducción, no paquetes por idioma. Instálalo aquí y aparecerá en la lista de traductores.",
        "translation_engine": "Motor de traducción", "local_model": "Modelo local",
        "rapidocr_note": "RapidOCR no usa paquetes de idioma separados. Su motor neuronal local incluye un modelo Chinese + English. Para ruso usa Windows OCR, Tesseract o EasyOCR.",
        "component": "Componente", "package": "Paquete", "status": "Estado", "argos_note": "Se muestran todos los paquetes Argos. Los pares sin inglés usan dos paquetes a través del inglés.",
        "remove_highlighted": "Eliminar resaltados", "direction": "Dirección", "search": "Buscar: ruso, ru, en→ru…", "language": "Idioma",
        "installed": "Instalado", "missing": "No instalado", "can_download": "Disponible", "engine_missing": "Falta {engine}", "checking": "Comprobando…",
        "unavailable": "No disponible en esta versión de Windows", "first_use": "Se preparará en el primer OCR", "engine_first": "Instala primero el motor",
        "ocr_engine": "Motor OCR", "runtime": "Entorno neuronal", "detector": "Detección y orientación", "recognition": "Reconocimiento",
        "loading": "Cargando lista de paquetes…", "load_error": "No se pudo cargar la lista: ", "no_match": "No hay paquetes coincidentes", "no_packages": "No se encontraron paquetes",
        "no_selection": "Marca al menos un idioma.", "already": "{engine} ya está instalado.", "still": "Todavía se está comprobando {engine}. Espera un momento.",
        "win_confirm": "¿Instalar los componentes OCR de Windows seleccionados?\n\nSe solicitará permiso de administrador. Solo se instala OCR, sin teclado ni distribución.",
        "easy_prompt": "Primero debes instalar EasyOCR. ¿Iniciar la instalación?", "argos_installed": "Las direcciones de Argos seleccionadas están instaladas.",
        "highlight": "Resalta filas instaladas.", "remove_confirm": "¿Eliminar paquetes Argos: {packages}?\n\nEstas direcciones dejarán de funcionar sin conexión.", "removed": "Se eliminaron los paquetes Argos seleccionados.",
        "preparing": "Preparando…", "canceling": "Cancelando…", "install_failed": "No se pudieron instalar los paquetes:\n", "ready": "Los paquetes seleccionados están listos.", "canceled": "Cancelado",
        "tess_down": "Tesseract: descargando idiomas…", "win_wait": "Windows OCR: esperando permiso de administrador…", "win_done": "Windows OCR: listo",
        "win_installing": "Windows OCR: instalando {language} ({current}/{total})…",
        "win_checking": "Windows OCR: comprobando {language}…",
        "win_verifying": "Windows OCR: verificando {language}…",
        "easy_down": "EasyOCR: descargando modelos de {language}…", "easy_done": "EasyOCR: listo",
        "ocr_section": "OCR", "translation_section": "Traducción",
        "engine_not_installed_title": "{engine} no está instalado",
        "engine_not_installed_body": "Instala primero el motor. Los paquetes de idioma aparecerán aquí después.",
        "repair_needed": "Requiere reparación",
        "remove_packages_confirm": "¿Eliminar los paquetes seleccionados de {engine}: {packages}?",
        "packages_removed": "Se eliminaron los paquetes de idioma seleccionados de {engine}.",
        "remove_failed": "No se pudieron eliminar los paquetes:\n",
        "win_removing": "Windows OCR: eliminando {language} ({current}/{total})…",
        "win_rolling_back": "Windows OCR: cancelando y eliminando paquetes incompletos…",
    },
    "de": {
        "intro": "Installiere hier OCR-Sprachen oder Argos-Offline-Richtungen. Pakete werden vorab heruntergeladen.",
        "refresh": "Aktualisieren", "windows_note": "Zeigt Windows-OCR-Sprachen. Installiert nur OCR ohne zusätzliche Tastatur.",
        "install_selected": "Ausgewählte installieren", "windows_settings": "Windows-Einstellungen", "tesseract_note": "Markiere Sprachen für den lokalen tessdata-Ordner.",
        "install_engine": "Engine installieren", "easyocr_note": "Markiere Sprachen für EasyOCR-Modelle. Englisch wird als Reserve ergänzt.",
        "remove_engine": "Engine entfernen",
        "remove_engine_tooltip": "Die installierte {engine}-Engine von diesem Rechner löschen.",
        "hymt_note": "Hy-MT ist ein einzelnes lokales Übersetzungsmodell, keine Sprachpakete. Hier installieren, dann erscheint es in der Übersetzerliste.",
        "translation_engine": "Übersetzungs-Engine", "local_model": "Lokales Modell",
        "rapidocr_note": "RapidOCR benötigt keine separaten Sprachpakete. Die lokale neuronale Engine enthält ein Chinese + English-Modell. Für Russisch nutze Windows OCR, Tesseract oder EasyOCR.",
        "component": "Komponente", "package": "Paket", "status": "Status", "argos_note": "Alle Argos-Pakete werden angezeigt. Nicht englische Paare verwenden zwei Pakete über Englisch.",
        "remove_highlighted": "Markierte entfernen", "direction": "Richtung", "search": "Suchen: Russisch, ru, en→ru…", "language": "Sprache",
        "installed": "Installiert", "missing": "Nicht installiert", "can_download": "Verfügbar", "engine_missing": "{engine} fehlt", "checking": "Prüfung…",
        "unavailable": "In dieser Windows-Version nicht verfügbar", "first_use": "Beim ersten OCR vorbereitet", "engine_first": "Zuerst die Engine installieren",
        "ocr_engine": "OCR-Engine", "runtime": "Neuronale Laufzeit", "detector": "Texterkennung und Ausrichtung", "recognition": "Erkennung",
        "loading": "Paketliste wird geladen…", "load_error": "Paketliste konnte nicht geladen werden: ", "no_match": "Keine passenden Pakete", "no_packages": "Keine Pakete gefunden",
        "no_selection": "Markiere mindestens eine Sprache.", "already": "{engine} ist bereits installiert.", "still": "{engine} wird noch geprüft. Bitte kurz warten.",
        "win_confirm": "Ausgewählte Windows-OCR-Komponenten installieren?\n\nAdministratorrechte werden angefordert. Nur OCR wird installiert, ohne Tastatur oder Layout.",
        "easy_prompt": "EasyOCR muss zuerst installiert werden. Installation starten?", "argos_installed": "Die ausgewählten Argos-Richtungen sind installiert.",
        "highlight": "Markiere installierte Zeilen.", "remove_confirm": "Argos-Pakete entfernen: {packages}?\n\nDiese Richtungen funktionieren danach nicht mehr offline.", "removed": "Die ausgewählten Argos-Pakete wurden entfernt.",
        "preparing": "Vorbereitung…", "canceling": "Abbruch…", "install_failed": "Sprachpakete konnten nicht installiert werden:\n", "ready": "Die ausgewählten Pakete sind bereit.", "canceled": "Abgebrochen",
        "tess_down": "Tesseract: Sprachen werden geladen…", "win_wait": "Windows OCR: Administratorfreigabe wird erwartet…", "win_done": "Windows OCR: fertig",
        "win_installing": "Windows OCR: {language} wird installiert ({current}/{total})…",
        "win_checking": "Windows OCR: {language} wird geprüft…",
        "win_verifying": "Windows OCR: {language} wird verifiziert…",
        "easy_down": "EasyOCR: Modelle für {language} werden geladen…", "easy_done": "EasyOCR: fertig",
        "ocr_section": "OCR", "translation_section": "Übersetzung",
        "engine_not_installed_title": "{engine} ist nicht installiert",
        "engine_not_installed_body": "Installiere zuerst die Engine. Danach werden die Sprachpakete hier angezeigt.",
        "repair_needed": "Reparatur erforderlich",
        "remove_packages_confirm": "Ausgewählte {engine}-Pakete entfernen: {packages}?",
        "packages_removed": "Die ausgewählten {engine}-Sprachpakete wurden entfernt.",
        "remove_failed": "Sprachpakete konnten nicht entfernt werden:\n",
        "win_removing": "Windows OCR: {language} wird entfernt ({current}/{total})…",
        "win_rolling_back": "Windows OCR: Abbruch und Entfernung unvollständiger Pakete…",
    },
    "fr": {
        "intro": "Installez ici les langues OCR ou les directions Argos hors ligne. Les modules sont téléchargés à l’avance.",
        "refresh": "Actualiser", "windows_note": "Affiche les langues OCR Windows. Installe uniquement OCR sans ajouter de clavier.",
        "install_selected": "Installer la sélection", "windows_settings": "Paramètres Windows", "tesseract_note": "Cochez les langues à placer dans le dossier tessdata local.",
        "install_engine": "Installer le moteur", "easyocr_note": "Cochez les langues pour les modèles EasyOCR. L’anglais est ajouté en secours.",
        "remove_engine": "Supprimer le moteur",
        "remove_engine_tooltip": "Supprimer le moteur {engine} installé sur cet ordinateur.",
        "hymt_note": "Hy-MT est un seul modèle de traduction local, pas des modules par langue. Installez-le ici et il apparaît dans la liste des traducteurs.",
        "translation_engine": "Moteur de traduction", "local_model": "Modèle local",
        "rapidocr_note": "RapidOCR n’utilise pas de modules de langue séparés. Son moteur neuronal local inclut un modèle Chinese + English. Pour le russe, utilisez Windows OCR, Tesseract ou EasyOCR.",
        "component": "Composant", "package": "Module", "status": "État", "argos_note": "Tous les modules Argos sont affichés. Les paires sans anglais utilisent deux modules via l’anglais.",
        "remove_highlighted": "Supprimer la sélection", "direction": "Direction", "search": "Rechercher : russe, ru, en→ru…", "language": "Langue",
        "installed": "Installé", "missing": "Non installé", "can_download": "Disponible", "engine_missing": "{engine} manquant", "checking": "Vérification…",
        "unavailable": "Indisponible dans cette version de Windows", "first_use": "Préparé au premier OCR", "engine_first": "Installez d’abord le moteur",
        "ocr_engine": "Moteur OCR", "runtime": "Runtime neuronal", "detector": "Détection et orientation", "recognition": "Reconnaissance",
        "loading": "Chargement de la liste…", "load_error": "Impossible de charger la liste : ", "no_match": "Aucun module correspondant", "no_packages": "Aucun module trouvé",
        "no_selection": "Cochez au moins une langue.", "already": "{engine} est déjà installé.", "still": "{engine} est encore vérifié. Patientez un instant.",
        "win_confirm": "Installer les composants OCR Windows sélectionnés ?\n\nUne autorisation administrateur sera demandée. Seul OCR sera installé, sans clavier ni disposition.",
        "easy_prompt": "EasyOCR doit d’abord être installé. Lancer l’installation ?", "argos_installed": "Les directions Argos sélectionnées sont installées.",
        "highlight": "Sélectionnez des lignes installées.", "remove_confirm": "Supprimer les modules Argos : {packages} ?\n\nCes directions ne fonctionneront plus hors ligne.", "removed": "Les modules Argos sélectionnés ont été supprimés.",
        "preparing": "Préparation…", "canceling": "Annulation…", "install_failed": "Impossible d’installer les modules :\n", "ready": "Les modules sélectionnés sont prêts.", "canceled": "Annulé",
        "tess_down": "Tesseract : téléchargement des langues…", "win_wait": "Windows OCR : attente de l’autorisation administrateur…", "win_done": "Windows OCR : terminé",
        "win_installing": "Windows OCR : installation de {language} ({current}/{total})…",
        "win_checking": "Windows OCR : vérification de {language}…",
        "win_verifying": "Windows OCR : validation de {language}…",
        "easy_down": "EasyOCR : téléchargement des modèles {language}…", "easy_done": "EasyOCR : terminé",
        "ocr_section": "OCR", "translation_section": "Traduction",
        "engine_not_installed_title": "{engine} n’est pas installé",
        "engine_not_installed_body": "Installez d’abord le moteur. Les modules de langue apparaîtront ensuite ici.",
        "repair_needed": "Réparation requise",
        "remove_packages_confirm": "Supprimer les modules {engine} sélectionnés : {packages} ?",
        "packages_removed": "Les modules linguistiques {engine} sélectionnés ont été supprimés.",
        "remove_failed": "Impossible de supprimer les modules :\n",
        "win_removing": "Windows OCR : suppression de {language} ({current}/{total})…",
        "win_rolling_back": "Windows OCR : annulation et suppression des modules incomplets…",
    },
    "zh": {
        "intro": "在此安装 OCR 语言或 Argos 离线翻译方向。语言包会提前下载，不会在识别或翻译时临时下载。",
        "refresh": "刷新", "windows_note": "显示 Windows 可用的 OCR 语言。只安装 OCR 组件，不添加键盘。",
        "install_selected": "安装所选项", "windows_settings": "Windows 设置", "tesseract_note": "勾选要下载到本地 tessdata 文件夹的语言。",
        "install_engine": "安装引擎", "easyocr_note": "勾选要预下载的 EasyOCR 模型。英语模型会作为备用模型。",
        "remove_engine": "卸载引擎",
        "remove_engine_tooltip": "从这台电脑上删除已安装的 {engine} 引擎。",
        "hymt_note": "Hy-MT 是一个本地翻译模型，而不是按语言划分的语言包。在这里安装后，它会出现在翻译器列表中。",
        "translation_engine": "翻译引擎", "local_model": "本地模型",
        "rapidocr_note": "RapidOCR 不需要单独的语言包。本地神经引擎内置 Chinese + English 模型；俄语请使用 Windows OCR、Tesseract 或 EasyOCR。",
        "component": "组件", "package": "语言包", "status": "状态", "argos_note": "显示所有 Argos 语言包。两个非英语语言之间需要通过英语使用两个语言包。",
        "remove_highlighted": "删除高亮项", "direction": "方向", "search": "搜索：俄语、ru、en→ru…", "language": "语言",
        "installed": "已安装", "missing": "未安装", "can_download": "可下载", "engine_missing": "未安装 {engine}", "checking": "正在检查…",
        "unavailable": "此 Windows 版本不可用", "first_use": "首次 OCR 时准备", "engine_first": "请先安装引擎",
        "ocr_engine": "OCR 引擎", "runtime": "神经网络运行时", "detector": "文本检测与方向", "recognition": "识别",
        "loading": "正在加载语言包列表…", "load_error": "无法加载语言包列表：", "no_match": "没有匹配的语言包", "no_packages": "未找到语言包",
        "no_selection": "请至少勾选一种语言。", "already": "{engine} 已安装。", "still": "仍在检查 {engine}，请稍候。",
        "win_confirm": "安装所选 Windows OCR 组件？\n\n系统将请求管理员权限。只安装 OCR 组件，不添加键盘或输入法布局。",
        "easy_prompt": "需要先安装 EasyOCR。是否开始安装？", "argos_installed": "所选 Argos 翻译方向已安装。",
        "highlight": "请高亮已安装项。", "remove_confirm": "删除 Argos 语言包：{packages}？\n\n这些方向将无法继续离线使用。", "removed": "所选 Argos 语言包已删除。",
        "preparing": "正在准备…", "canceling": "正在取消…", "install_failed": "无法安装语言包：\n", "ready": "所选语言包已准备就绪。", "canceled": "已取消",
        "tess_down": "Tesseract：正在下载语言…", "win_wait": "Windows OCR：正在等待管理员授权…", "win_done": "Windows OCR：完成",
        "win_installing": "Windows OCR：正在安装 {language}（{current}/{total}）…",
        "win_checking": "Windows OCR：正在检查 {language}…",
        "win_verifying": "Windows OCR：正在验证 {language}…",
        "easy_down": "EasyOCR：正在下载 {language} 模型…", "easy_done": "EasyOCR：完成",
        "ocr_section": "OCR", "translation_section": "翻译",
        "engine_not_installed_title": "未安装 {engine}",
        "engine_not_installed_body": "请先安装引擎。安装完成后，语言包会显示在这里。",
        "repair_needed": "需要修复",
        "remove_packages_confirm": "删除所选 {engine} 语言包：{packages}？",
        "packages_removed": "已删除所选 {engine} 语言包。",
        "remove_failed": "无法删除语言包：\n",
        "win_removing": "Windows OCR：正在删除 {language}（{current}/{total}）…",
        "win_rolling_back": "Windows OCR：正在取消并删除未完成的语言包…",
    },
}


WINDOWS_OCR_RUNTIME_TEXT = {
    "en": {
        "continue_background": "Continue in background",
        "show_progress": "Show",
        "task_installing_short": "Installing",
        "task_packages_short": "Packages",
        "task_busy_help": "Another package operation is running. Your selections are preserved; open its progress or wait for it to finish.",
        "win_component_short": "DISM {percent}%",
        "win_stage": "Step {stage}/4 · Language {current}/{total}",
        "win_time_unknown": "Windows Update controls the remaining time; an exact finish time is not available.",
        "win_activity_recent": "Windows is responding",
        "win_background_info": "Windows downloads the language from Windows Update. Expect 5-20 minutes per language, and expect the percentage to sit still for minutes at a time — that is normal, not a freeze. The work runs as a Windows service, so it continues if you send it to the background, and this window reports the result.",
        "win_download_stage": "Windows Update: {percent}% downloaded",
        "win_quiet": "No progress for {minutes} min. Windows is still responding, but its download may be stalled. You can keep waiting in the background or cancel safely.",
        "win_installing_basic": "Windows is preparing {language} ({current}/{total}). This required language component may take several minutes.",
        "win_installing": "Windows Update is downloading and installing OCR for {language} ({current}/{total}). This may take several minutes.",
        "win_cancel_pending": "Cancel requested. Windows is safely finishing the current component; this can take several minutes.",
        "win_still_working": "Windows Update is still working. Do not turn off the PC.",
        "win_registering": "Windows is registering the new OCR language. This can take a moment…",
        "win_installed_pending_restart": "Windows finished installing the OCR package. {languages} is not available to the app yet — restart Click'n'Translate, or Windows if it still does not appear.",
        "win_error_policy": "Windows Update policy blocked this OCR package. Open Windows settings or contact the system administrator (0x800f0954).",
        "win_error_source": "Windows could not download the OCR package. Check Windows Update, the internet connection, and free disk space, then try again.",
        "win_error_restart": "Windows needs a restart before it can install components. Restart the PC and try again.",
        "win_error_busy": "Windows component servicing is busy — usually Windows Update or another install is running. Wait a minute and try again; no restart is needed.",
        "win_error_generic": "Windows could not finish the OCR package operation. Install pending Windows updates, restart the PC, and try again.",
    },
    "ru": {
        "continue_background": "Продолжить в фоне",
        "show_progress": "Открыть",
        "task_installing_short": "Установка",
        "task_packages_short": "Пакеты",
        "task_busy_help": "Уже выполняется другая операция с пакетами. Выбранные галочки сохранены — откройте её прогресс или дождитесь завершения.",
        "win_component_short": "DISM {percent}%",
        "win_stage": "Этап {stage}/4 · Язык {current}/{total}",
        "win_time_unknown": "Оставшееся время определяет Центр обновления Windows; точное время завершения неизвестно.",
        "win_activity_recent": "Windows отвечает",
        "win_background_info": "Язык скачивает Центр обновления Windows. На один язык обычно уходит 5-20 минут, и проценты подолгу стоят на месте — это нормально, а не зависание. Установку выполняет служба Windows, поэтому она продолжится в фоне, а окно покажет результат.",
        "win_download_stage": "Центр обновления Windows: скачано {percent}%",
        "win_quiet": "Нет прогресса {minutes} мин. Windows отвечает, но загрузка могла остановиться. Можно продолжить ожидание в фоне или безопасно отменить.",
        "win_installing_basic": "Windows подготавливает язык {language} ({current}/{total}). Установка обязательного компонента может занять несколько минут.",
        "win_installing": "Центр обновления Windows загружает и устанавливает OCR для языка {language} ({current}/{total}). Это может занять несколько минут.",
        "win_cancel_pending": "Отмена запрошена. Windows безопасно завершает текущий компонент — это может занять несколько минут.",
        "win_still_working": "Центр обновления Windows продолжает работу. Не выключайте компьютер.",
        "win_registering": "Windows регистрирует новый язык OCR. Это может занять некоторое время…",
        "win_installed_pending_restart": "Windows установила OCR-пакет. Язык {languages} пока недоступен приложению — перезапустите Click'n'Translate, а если язык не появится, перезагрузите Windows.",
        "win_error_policy": "Политика Центра обновления Windows заблокировала OCR-пакет. Откройте настройки Windows или обратитесь к администратору (0x800f0954).",
        "win_error_source": "Windows не смогла скачать OCR-пакет. Проверьте Центр обновления, интернет и свободное место, затем повторите попытку.",
        "win_error_restart": "Windows требуется перезагрузка, прежде чем устанавливать компоненты. Перезагрузите компьютер и повторите попытку.",
        "win_error_busy": "Система обслуживания компонентов Windows занята — обычно это работающий Центр обновления или другая установка. Подождите минуту и повторите попытку, перезагрузка не нужна.",
        "win_error_generic": "Windows не смогла завершить операцию с OCR-пакетом. Установите ожидающие обновления Windows, перезагрузите компьютер и повторите попытку.",
    },
    "es": {
        "continue_background": "Continuar en segundo plano",
        "show_progress": "Ver",
        "task_installing_short": "Instalando",
        "task_packages_short": "Paquetes",
        "task_busy_help": "Ya hay otra operación de paquetes en curso. La selección se conserva; abre su progreso o espera a que termine.",
        "win_component_short": "DISM {percent}%",
        "win_stage": "Paso {stage}/4 · Idioma {current}/{total}",
        "win_time_unknown": "Windows Update controla el tiempo restante; no se puede calcular una hora exacta de finalización.",
        "win_activity_recent": "Windows está respondiendo",
        "win_background_info": "Windows Update descarga el idioma. Cuenta con 5-20 minutos por idioma, y el porcentaje puede quedarse quieto durante minutos: es normal, no está bloqueado. Lo ejecuta un servicio de Windows, así que continúa en segundo plano y esta ventana te dará el resultado.",
        "win_download_stage": "Windows Update: {percent}% descargado",
        "win_quiet": "Sin progreso desde hace {minutes} min. Windows sigue respondiendo, pero la descarga puede haberse detenido. Puedes esperar en segundo plano o cancelar de forma segura.",
        "win_installing_basic": "Windows está preparando {language} ({current}/{total}). Este componente obligatorio puede tardar varios minutos.",
        "win_installing": "Windows Update está descargando e instalando OCR para {language} ({current}/{total}). Puede tardar varios minutos.",
        "win_cancel_pending": "Cancelación solicitada. Windows está terminando de forma segura el componente actual; puede tardar varios minutos.",
        "win_still_working": "Windows Update sigue trabajando. No apagues el equipo.",
        "win_registering": "Windows está registrando el nuevo idioma de OCR. Puede tardar un momento…",
        "win_installed_pending_restart": "Windows terminó de instalar el paquete OCR. {languages} aún no está disponible en la aplicación: reinicia Click'n'Translate y, si sigue sin aparecer, reinicia Windows.",
        "win_error_policy": "La directiva de Windows Update bloqueó este paquete OCR. Abre Configuración de Windows o contacta con el administrador (0x800f0954).",
        "win_error_source": "Windows no pudo descargar el paquete OCR. Comprueba Windows Update, Internet y el espacio libre y vuelve a intentarlo.",
        "win_error_restart": "Windows necesita reiniciarse antes de instalar componentes. Reinicia el equipo y vuelve a intentarlo.",
        "win_error_busy": "El servicio de componentes de Windows está ocupado, normalmente por Windows Update u otra instalación. Espera un minuto y reinténtalo; no hace falta reiniciar.",
        "win_error_generic": "Windows no pudo finalizar la operación del paquete OCR. Instala las actualizaciones pendientes, reinicia el equipo y vuelve a intentarlo.",
    },
    "de": {
        "continue_background": "Im Hintergrund fortsetzen",
        "show_progress": "Öffnen",
        "task_installing_short": "Installation",
        "task_packages_short": "Pakete",
        "task_busy_help": "Ein anderer Paketvorgang läuft bereits. Die Auswahl bleibt erhalten; öffnen Sie den Fortschritt oder warten Sie auf den Abschluss.",
        "win_component_short": "DISM {percent}%",
        "win_stage": "Schritt {stage}/4 · Sprache {current}/{total}",
        "win_time_unknown": "Die Restzeit wird von Windows Update bestimmt; eine genaue Endzeit ist nicht verfügbar.",
        "win_activity_recent": "Windows antwortet",
        "win_background_info": "Windows Update lädt die Sprache herunter. Rechnen Sie mit 5-20 Minuten pro Sprache, und damit, dass die Prozentzahl minutenlang stehen bleibt — das ist normal und kein Hänger. Die Arbeit erledigt ein Windows-Dienst, sie läuft also im Hintergrund weiter, und dieses Fenster meldet das Ergebnis.",
        "win_download_stage": "Windows Update: {percent}% geladen",
        "win_quiet": "Seit {minutes} Min. kein Fortschritt. Windows antwortet noch, der Download könnte jedoch feststecken. Sie können im Hintergrund weiter warten oder sicher abbrechen.",
        "win_installing_basic": "Windows bereitet {language} vor ({current}/{total}). Diese erforderliche Komponente kann mehrere Minuten dauern.",
        "win_installing": "Windows Update lädt OCR für {language} herunter und installiert es ({current}/{total}). Dies kann mehrere Minuten dauern.",
        "win_cancel_pending": "Abbruch angefordert. Windows schließt die aktuelle Komponente sicher ab; dies kann einige Minuten dauern.",
        "win_still_working": "Windows Update arbeitet weiter. Schalten Sie den PC nicht aus.",
        "win_registering": "Windows registriert die neue OCR-Sprache. Das kann einen Moment dauern…",
        "win_installed_pending_restart": "Windows hat das OCR-Paket installiert. {languages} steht der App noch nicht zur Verfügung – starten Sie Click'n'Translate neu, und falls es weiterhin fehlt, Windows.",
        "win_error_policy": "Eine Windows-Update-Richtlinie hat dieses OCR-Paket blockiert. Öffnen Sie die Windows-Einstellungen oder wenden Sie sich an den Administrator (0x800f0954).",
        "win_error_source": "Windows konnte das OCR-Paket nicht laden. Prüfen Sie Windows Update, Internet und freien Speicherplatz und versuchen Sie es erneut.",
        "win_error_restart": "Windows benötigt einen Neustart, bevor Komponenten installiert werden können. Starten Sie den PC neu und versuchen Sie es erneut.",
        "win_error_busy": "Die Windows-Komponentenwartung ist beschäftigt — meist läuft Windows Update oder eine andere Installation. Warten Sie eine Minute und versuchen Sie es erneut; ein Neustart ist nicht nötig.",
        "win_error_generic": "Windows konnte den OCR-Paketvorgang nicht abschließen. Installieren Sie ausstehende Updates, starten Sie den PC neu und versuchen Sie es erneut.",
    },
    "fr": {
        "continue_background": "Continuer en arrière-plan",
        "show_progress": "Afficher",
        "task_installing_short": "Installation",
        "task_packages_short": "Modules",
        "task_busy_help": "Une autre opération de paquet est déjà en cours. Votre sélection est conservée ; affichez sa progression ou attendez la fin.",
        "win_component_short": "DISM {percent}%",
        "win_stage": "Étape {stage}/4 · Langue {current}/{total}",
        "win_time_unknown": "Windows Update détermine le temps restant ; aucune heure de fin exacte n’est disponible.",
        "win_activity_recent": "Windows répond",
        "win_background_info": "Windows Update télécharge la langue. Comptez 5 à 20 minutes par langue, et un pourcentage qui reste figé plusieurs minutes : c'est normal, ce n'est pas bloqué. Le travail est fait par un service Windows : il continue en arrière-plan et cette fenêtre annoncera le résultat.",
        "win_download_stage": "Windows Update : {percent}% téléchargés",
        "win_quiet": "Aucune progression depuis {minutes} min. Windows répond encore, mais le téléchargement peut être bloqué. Vous pouvez attendre en arrière-plan ou annuler sans risque.",
        "win_installing_basic": "Windows prépare {language} ({current}/{total}). Ce composant requis peut prendre plusieurs minutes.",
        "win_installing": "Windows Update télécharge et installe OCR pour {language} ({current}/{total}). Cela peut prendre plusieurs minutes.",
        "win_cancel_pending": "Annulation demandée. Windows termine le composant actuel en toute sécurité ; cela peut prendre plusieurs minutes.",
        "win_still_working": "Windows Update continue de travailler. N’éteignez pas le PC.",
        "win_registering": "Windows enregistre la nouvelle langue OCR. Cela peut prendre un moment…",
        "win_installed_pending_restart": "Windows a terminé l’installation du module OCR. {languages} n’est pas encore disponible dans l’application : redémarrez Click'n'Translate, puis Windows si la langue reste absente.",
        "win_error_policy": "La stratégie Windows Update a bloqué ce module OCR. Ouvrez les paramètres Windows ou contactez l’administrateur (0x800f0954).",
        "win_error_source": "Windows n’a pas pu télécharger le module OCR. Vérifiez Windows Update, Internet et l’espace libre, puis réessayez.",
        "win_error_restart": "Windows doit redémarrer avant de pouvoir installer des composants. Redémarrez le PC puis réessayez.",
        "win_error_busy": "La maintenance des composants Windows est occupée — généralement Windows Update ou une autre installation. Attendez une minute et réessayez ; aucun redémarrage n'est nécessaire.",
        "win_error_generic": "Windows n’a pas pu terminer l’opération du module OCR. Installez les mises à jour en attente, redémarrez le PC puis réessayez.",
    },
    "zh": {
        "continue_background": "在后台继续",
        "show_progress": "查看",
        "task_installing_short": "安装中",
        "task_packages_short": "语言包",
        "task_busy_help": "已有另一个软件包操作正在进行。所选项目会保留；请查看其进度或等待完成。",
        "win_component_short": "DISM {percent}%",
        "win_stage": "步骤 {stage}/4 · 语言 {current}/{total}",
        "win_time_unknown": "剩余时间由 Windows 更新决定，无法提供准确的完成时间。",
        "win_activity_recent": "Windows 正在响应",
        "win_background_info": "语言包由 Windows 更新下载。每种语言通常需要 5-20 分钟，进度百分比可能几分钟停在同一个数字上，这是正常现象，并非卡死。安装由 Windows 服务执行，转入后台也会继续，完成后本窗口会给出结果。",
        "win_download_stage": "Windows 更新：已下载 {percent}%",
        "win_quiet": "已有 {minutes} 分钟没有进展。Windows 仍有响应，但下载可能已停滞。您可以在后台继续等待，也可以安全取消。",
        "win_installing_basic": "Windows 正在准备 {language}（{current}/{total}）。安装必需的语言组件可能需要几分钟。",
        "win_installing": "Windows 更新正在下载并安装 {language} 的 OCR（{current}/{total}）。这可能需要几分钟。",
        "win_cancel_pending": "已请求取消。Windows 正在安全完成当前组件，这可能需要几分钟。",
        "win_still_working": "Windows 更新仍在工作，请勿关闭电脑。",
        "win_registering": "Windows 正在注册新的 OCR 语言，请稍候…",
        "win_installed_pending_restart": "Windows 已完成 OCR 包的安装。应用暂时还看不到 {languages}，请重启 Click'n'Translate；若仍未出现，请重启 Windows。",
        "win_error_policy": "Windows 更新策略阻止了此 OCR 包。请打开 Windows 设置或联系系统管理员 (0x800f0954)。",
        "win_error_source": "Windows 无法下载 OCR 包。请检查 Windows 更新、网络连接和可用磁盘空间，然后重试。",
        "win_error_restart": "Windows 需要先重启才能安装组件。请重启电脑后重试。",
        "win_error_busy": "Windows 组件服务正忙，通常是 Windows 更新或其他安装正在进行。请等待一分钟后重试，不需要重启。",
        "win_error_generic": "Windows 无法完成 OCR 包操作。请安装待处理的 Windows 更新，重启电脑后重试。",
    },
}
for _runtime_lang, _runtime_values in WINDOWS_OCR_RUNTIME_TEXT.items():
    LANGUAGE_MANAGER_TEXT.setdefault(_runtime_lang, {}).update(_runtime_values)


def language_manager_text(lang, key, **values):
    texts = LANGUAGE_MANAGER_TEXT.get(lang, LANGUAGE_MANAGER_TEXT["en"])
    value = texts.get(key, LANGUAGE_MANAGER_TEXT["en"].get(key, key))
    return value.format(**values) if values else value


class OcrLanguageManagerDialog(QDialog):
    _runtime_probe_ready = QtCore.pyqtSignal(object)

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        owner_parent = getattr(owner, "parent", None)
        if callable(owner_parent):
            try:
                owner_parent = owner_parent()
            except Exception:
                owner_parent = None
        self.lang = getattr(
            owner_parent,
            "current_interface_language",
            getattr(owner, "current_interface_language", "en"),
        )
        self._install_in_progress = False
        self._active_language_task_title = ""
        self._cancel_requested = threading.Event()
        self._windows_ocr_cancel_marker = ""
        self.progress_dialog = None
        self._task_success_message = ""
        self._task_failure_key = "install_failed"
        self._last_task_error_details = ""
        self._argos_catalog = []
        self._argos_catalog_error = ""
        self._argos_catalog_loading = True
        self._argos_catalog_request_active = False
        self._windows_tags_cache = None
        self._windows_capabilities_cache = None
        self._windows_ready_codes_cache = None
        self._easyocr_status_cache = None
        self._rapidocr_status_cache = None
        self._runtime_probe_active = False
        self._title_drag_offset = None
        self._centered_once = False

        self.setWindowTitle(settings_text(self.lang, "ocr_language_packs"))
        self.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        self.setObjectName("languageManagerDialog")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.NonModal)
        self.setFixedSize(640, 558)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = QFrame(self)
        self.title_bar.setObjectName("languageManagerTitleBar")
        self.title_bar.setFixedHeight(38)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 5, 0)
        title_layout.setSpacing(8)

        self.title_icon = QLabel()
        self.title_icon.setObjectName("languageManagerTitleIcon")
        self.title_icon.setFixedSize(18, 18)
        self.title_icon.setPixmap(QIcon(resource_path("icons/icon.ico")).pixmap(18, 18))
        title_layout.addWidget(self.title_icon, 0, Qt.AlignVCenter)

        self.title_label = QLabel(settings_text(self.lang, "ocr_language_packs"))
        self.title_label.setObjectName("languageManagerTitleLabel")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_layout.addWidget(self.title_label, 1)

        self.title_close_btn = QToolButton()
        self.title_close_btn.setObjectName("languageManagerTitleClose")
        self.title_close_btn.setText("×")
        self.title_close_btn.setCursor(Qt.PointingHandCursor)
        self.title_close_btn.setFixedSize(30, 28)
        self.title_close_btn.clicked.connect(self.reject)
        title_layout.addWidget(self.title_close_btn, 0, Qt.AlignVCenter)
        root_layout.addWidget(self.title_bar)

        self.content_widget = QWidget(self)
        self.content_widget.setObjectName("languageManagerContent")
        root_layout.addWidget(self.content_widget, 1)

        layout = QVBoxLayout(self.content_widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self._title_drag_widgets = (self.title_bar, self.title_icon, self.title_label)
        for drag_widget in self._title_drag_widgets:
            drag_widget.installEventFilter(self)

        intro = QLabel(language_manager_text(self.lang, "intro"))
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 13px;")
        layout.addWidget(intro)

        # Keep OCR engines and translation packages in two explicit visual
        # sections.  Nested tabs preserve the fixed window size while avoiding
        # one undifferentiated row of unrelated engines.
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("languagePackageSections")
        self.ocr_section_page = QWidget(self.tabs)
        self.translation_section_page = QWidget(self.tabs)
        ocr_section_layout = QVBoxLayout(self.ocr_section_page)
        translation_section_layout = QVBoxLayout(self.translation_section_page)
        for section_layout in (ocr_section_layout, translation_section_layout):
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(0)
        self.ocr_tabs = QTabWidget(self.ocr_section_page)
        self.translation_tabs = QTabWidget(self.translation_section_page)
        self.ocr_tabs.setObjectName("ocrPackageTabs")
        self.translation_tabs.setObjectName("translationPackageTabs")
        ocr_section_layout.addWidget(self.ocr_tabs)
        translation_section_layout.addWidget(self.translation_tabs)
        self.tabs.addTab(self.ocr_section_page, language_manager_text(self.lang, "ocr_section"))
        self.tabs.addTab(
            self.translation_section_page,
            language_manager_text(self.lang, "translation_section"),
        )
        layout.addWidget(self.tabs)

        self.windows_table = None
        self.tesseract_table = None
        self.easyocr_table = None
        self.rapidocr_table = None
        self.hymt_table = None
        self.argos_table = None
        self._build_tabs()

        bottom = QHBoxLayout()
        # Where a backgrounded install reports itself. Sending the progress
        # window away should not mean losing sight of the work, and it should
        # not cost another window either.
        self.task_status_label = QLabel("")
        self.task_status_label.setObjectName("languagePackageTaskStatus")
        self.task_status_label.setWordWrap(False)
        self.task_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.task_status_label.hide()
        bottom.addWidget(self.task_status_label, 1)
        self.task_show_button = QPushButton(
            language_manager_text(self.lang, "show_progress")
        )
        self.task_show_button.setObjectName("languagePackageTaskShow")
        self.task_show_button.clicked.connect(self._restore_task_progress)
        self.task_show_button.hide()
        bottom.addWidget(self.task_show_button)
        bottom.addStretch()
        self.refresh_btn = QPushButton(language_manager_text(self.lang, "refresh"))
        self.refresh_btn.clicked.connect(self.refresh_catalog)
        bottom.addWidget(self.refresh_btn)
        self.close_btn = QPushButton(settings_text(self.lang, "back"))
        self.close_btn.clicked.connect(self.accept)
        bottom.addWidget(self.close_btn)
        layout.addLayout(bottom)

        self._apply_style()
        for package_table in (
            self.windows_table,
            self.tesseract_table,
            self.easyocr_table,
            self.rapidocr_table,
            self.argos_table,
        ):
            self._apply_missing_engine_card_style(package_table)
        self._apply_package_tab_styles()
        for package_table in (
            self.windows_table,
            self.tesseract_table,
            self.easyocr_table,
            self.rapidocr_table,
            self.argos_table,
        ):
            self._apply_package_scrollbar_style(package_table)
        # Four OCR tabs must fit without tiny scroll arrows in the fixed-size
        # window, including at 125–150% Windows scaling.
        self.ocr_tabs.tabBar().setUsesScrollButtons(False)
        self.ocr_tabs.tabBar().setElideMode(Qt.ElideRight)
        self.translation_tabs.tabBar().setUsesScrollButtons(False)
        self._runtime_probe_ready.connect(self._on_runtime_probe_ready)
        QtCore.QTimer.singleShot(0, self._start_runtime_probe)
        QtCore.QTimer.singleShot(0, lambda: self._start_argos_catalog_refresh(True))

    def _owner_app(self):
        owner_parent = getattr(self.owner, "parent", None)
        if callable(owner_parent) and not hasattr(owner_parent, "current_theme"):
            try:
                owner_parent = self.owner.parent()
            except Exception:
                owner_parent = None
        return owner_parent

    def _is_dark_theme(self):
        theme = str(getattr(self._owner_app(), "current_theme", "") or "").strip().lower()
        return bool(theme) and theme not in {"светлая", "light", "white"}

    def _apply_style(self):
        dark = self._is_dark_theme()
        title_background = "#090a0d" if dark else "#f2edf7"
        title_border = "#302a3a" if dark else "#d7cde7"
        title_text = "#f7f3ff" if dark else "#2b2333"
        close_text = "#f4eefc" if dark else "#4b4057"
        chrome_style = f"""
            QFrame#languageManagerTitleBar {{
                background-color: {title_background};
                border: none;
                border-bottom: 1px solid {title_border};
            }}
            QLabel#languageManagerTitleIcon {{
                background: transparent;
                border: none;
            }}
            QLabel#languageManagerTitleLabel {{
                background: transparent;
                color: {title_text};
                border: none;
                font-size: 13px;
                font-weight: 700;
            }}
            QToolButton#languageManagerTitleClose {{
                background: transparent;
                color: {close_text};
                border: none;
                border-radius: 6px;
                font-size: 18px;
                font-weight: 500;
                padding: 0px;
            }}
            QToolButton#languageManagerTitleClose:hover {{
                background-color: #d44b55;
                color: #ffffff;
            }}
        """ + TOOLTIP_QSS
        if dark:
            self.setStyleSheet(chrome_style + """
                QDialog#languageManagerDialog { background-color: #111216; color: #f4f6fb; border: 1px solid #302a3a; font-family: 'Segoe UI'; font-size: 13px; }
                QWidget#languageManagerContent { background-color: #111216; }
                QLabel { color: #f4f6fb; font-family: 'Segoe UI'; font-size: 13px; }
                QTabWidget::pane { border: 1px solid #34313f; }
                QTabBar::tab { background: #1d1d23; color: #f4f6fb; padding: 7px 12px; }
                QTabBar::tab:selected { background: #7A5FA1; }
                QTableWidget { background: #17181d; alternate-background-color: #20212a; color: #f4f6fb; gridline-color: #34313f; selection-background-color: #5f4a88; selection-color: #ffffff; font-family: 'Segoe UI'; font-size: 14px; border: 1px solid #34313f; border-radius: 7px; }
                QTableWidget::item { color: #f4f6fb; background-color: #17181d; }
                QTableWidget::item:alternate { background-color: #20212a; }
                QTableWidget::item:disabled { color: #9ca0ad; }
                QTableCornerButton::section { background: #24212e; border: 0; }
                QHeaderView::section { background: #24212e; color: #f4f6fb; border: 0; padding: 5px; font-family: 'Segoe UI'; font-size: 13px; font-weight: 700; }
                QPushButton { background-color: #7A5FA1; color: #fff; border: none; border-radius: 7px; padding: 7px 12px; font-family: 'Segoe UI'; font-size: 13px; font-weight: 600; }
                QPushButton:hover { background-color: #8B70B2; }
                QPushButton:disabled { background-color: #3a3645; color: #8f889c; }
                QPushButton#languagePackageAction { background-color: #7A5FA1; color: #ffffff; border: none; border-radius: 7px; padding: 7px 12px; min-height: 18px; }
                QPushButton#languagePackageAction:hover { background-color: #8B70B2; }
                QPushButton#languagePackageAction:pressed { background-color: #684d91; }
                QPushButton#languagePackageAction:disabled { background-color: #3a3645; color: #8f889c; }
                QPushButton#languagePackageEngineRemove { background-color: transparent; color: #e0879a; border: 1px solid #6b3f4c; border-radius: 7px; padding: 5px 12px; font-size: 12px; font-weight: 700; }
                QPushButton#languagePackageEngineRemove:hover { background-color: #462b33; color: #ffd7de; }
                QPushButton#languagePackageEngineRemove:pressed { background-color: #5a343e; }
                QPushButton#languagePackageEngineRemove:disabled { color: #8f889c; border-color: #3a3645; }
                QFrame#languagePackageEmptyState { background: #17181d; border: 1px solid #34313f; border-radius: 10px; }
                QLabel#languagePackageEmptyTitle { color: #f4f6fb; font-size: 18px; font-weight: 700; }
                QLabel#languagePackageEmptyBody { color: #aeb2bf; font-size: 13px; }
                QLineEdit { background: #17181d; color: #f4f6fb; border: 1px solid #34313f; border-radius: 6px; padding: 6px 9px; }
                QLineEdit:focus { border-color: #7A5FA1; }
                QScrollBar:vertical { background: #14151a; width: 12px; margin: 0; border: none; }
                QScrollBar::handle:vertical { background: #67577b; min-height: 36px; border-radius: 5px; margin: 2px; }
                QScrollBar::handle:vertical:hover { background: #80699a; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; border: none; background: transparent; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
                QScrollBar:horizontal { background: #14151a; height: 12px; margin: 0; border: none; }
                QScrollBar::handle:horizontal { background: #67577b; min-width: 36px; border-radius: 5px; margin: 2px; }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; border: none; background: transparent; }
                QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
            """)
        else:
            self.setStyleSheet(chrome_style + """
                QDialog#languageManagerDialog { background-color: #f0edf3; color: #241f2a; border: 1px solid #bcb2c7; font-family: 'Segoe UI'; font-size: 13px; }
                QWidget#languageManagerContent { background-color: #f0edf3; }
                QLabel { color: #202124; font-family: 'Segoe UI'; font-size: 13px; }
                QTableWidget { background: #f3eff5; alternate-background-color: #e9e3ed; color: #241f2a; gridline-color: #c8bfce; selection-background-color: #cdbbdd; selection-color: #241f2a; font-family: 'Segoe UI'; font-size: 14px; border: 1px solid #bcb2c7; border-radius: 7px; }
                QHeaderView::section { background: #ddd7e2; color: #241f2a; border: 0; padding: 5px; font-family: 'Segoe UI'; font-size: 13px; font-weight: 700; }
                QPushButton { background-color: #7A5FA1; color: #fff; border: none; border-radius: 7px; padding: 7px 12px; font-family: 'Segoe UI'; font-size: 13px; font-weight: 600; }
                QPushButton:hover { background-color: #8B70B2; }
                QPushButton:disabled { background-color: #d8d4e2; color: #777; }
                QPushButton#languagePackageAction { background-color: #7A5FA1; color: #ffffff; border: none; border-radius: 7px; padding: 7px 12px; min-height: 18px; }
                QPushButton#languagePackageAction:hover { background-color: #8B70B2; }
                QPushButton#languagePackageAction:pressed { background-color: #684d91; }
                QPushButton#languagePackageAction:disabled { background-color: #d8d4e2; color: #777777; }
                QPushButton#languagePackageEngineRemove { background-color: transparent; color: #b03a52; border: 1px solid #e2b7c0; border-radius: 7px; padding: 5px 12px; font-size: 12px; font-weight: 700; }
                QPushButton#languagePackageEngineRemove:hover { background-color: #fbe9ed; color: #8f2a40; }
                QPushButton#languagePackageEngineRemove:pressed { background-color: #f3d7de; }
                QPushButton#languagePackageEngineRemove:disabled { color: #a39aad; border-color: #e6e1ec; }
                QFrame#languagePackageEmptyState { background: #e9e3ed; border: 1px solid #bcb2c7; border-radius: 10px; }
                QLabel#languagePackageEmptyTitle { color: #202124; font-size: 18px; font-weight: 700; }
                QLabel#languagePackageEmptyBody { color: #6f6877; font-size: 13px; }
                QLineEdit { background: #f3eff5; color: #241f2a; border: 1px solid #bcb2c7; border-radius: 6px; padding: 6px 9px; }
                QLineEdit:focus { border-color: #7A5FA1; }
                QScrollBar:vertical { background: #f1eff5; width: 12px; margin: 0; border: none; }
                QScrollBar::handle:vertical { background: #9b87b6; min-height: 36px; border-radius: 5px; margin: 2px; }
                QScrollBar::handle:vertical:hover { background: #7A5FA1; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; border: none; background: transparent; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
                QScrollBar:horizontal { background: #f1eff5; height: 12px; margin: 0; border: none; }
                QScrollBar::handle:horizontal { background: #9b87b6; min-width: 36px; border-radius: 5px; margin: 2px; }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; border: none; background: transparent; }
                QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
            """)

    def _apply_package_tab_styles(self):
        dark = self._is_dark_theme()
        text = "#f4f6fb" if dark else "#202124"
        muted = "#bcb5c8" if dark else "#625a6d"
        base = "#1b1c22" if dark else "#f0edf5"
        selected = "#7A5FA1"
        # A tab bar measures its tabs with its own font but paints them with the
        # stylesheet font. Declaring the font only in the stylesheet left every
        # tab sized for a 6pt default and painted at 14px, so the labels ran
        # over each other. Set the font on the bar and the two agree.
        self._apply_tab_bar_font(self.tabs.tabBar(), 14, bold=True)
        for inner in (self.ocr_tabs, self.translation_tabs):
            self._apply_tab_bar_font(inner.tabBar(), 13, bold=True)

        self.tabs.tabBar().setStyleSheet(f"""
            QTabBar::tab {{
                background: {base};
                color: {text};
                border: none;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                padding: 7px 17px;
                margin-right: 3px;
            }}
            QTabBar::tab:selected {{ background: {selected}; color: #ffffff; }}
            QTabBar::tab:hover:!selected {{ background: {'#292a32' if dark else '#e4ddec'}; }}
        """)
        # Weight stays put between states: a bolder selected tab would be wider
        # than the space the bar measured for it, which is the same clipping in
        # a smaller form.
        inner_style = f"""
            QTabBar::tab {{
                background: transparent;
                color: {muted};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 7px 12px 6px 12px;
                margin: 0px;
            }}
            QTabBar::tab:selected {{
                color: {text};
                background: transparent;
                border-bottom: 2px solid {selected};
            }}
            QTabBar::tab:hover:!selected {{ color: {text}; }}
        """
        self.ocr_tabs.tabBar().setStyleSheet(inner_style)
        self.translation_tabs.tabBar().setStyleSheet(inner_style)

    @staticmethod
    def _apply_tab_bar_font(tab_bar, pixel_size, bold=False):
        font = QtGui.QFont("Segoe UI")
        font.setPixelSize(pixel_size)
        font.setBold(bold)
        tab_bar.setFont(font)

    def _apply_missing_engine_card_style(self, table):
        if table is None:
            return
        frame = getattr(table, "_package_missing_frame", None)
        if frame is None:
            return
        dark = self._is_dark_theme()
        card = "#17181d" if dark else "#f7f6fb"
        border = "#34313f" if dark else "#d8d2e2"
        text = "#f4f6fb" if dark else "#202124"
        muted = "#b7b0c2" if dark else "#675f72"
        frame.setStyleSheet(f"""
            QFrame#languagePackageEmptyState {{
                background-color: {card};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            QLabel#languagePackageEmptyTitle {{
                background: transparent;
                color: {text};
                border: none;
                font-family: 'Segoe UI';
                font-size: 18px;
                font-weight: 700;
            }}
            QLabel#languagePackageEmptyBody {{
                background: transparent;
                color: {muted};
                border: none;
                font-family: 'Segoe UI';
                font-size: 13px;
            }}
            QPushButton#languagePackageAction {{
                background-color: #7A5FA1;
                color: #ffffff;
                border: none;
                border-radius: 7px;
                padding: 7px 14px;
                font-family: 'Segoe UI';
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton#languagePackageAction:hover {{ background-color: #8B70B2; }}
            QPushButton#languagePackageAction:pressed {{ background-color: #684d91; }}
        """)

    def _apply_package_scrollbar_style(self, table):
        if table is None:
            return
        dark = self._is_dark_theme()
        track = "#15161b" if dark else "#f1eff5"
        handle = "#705b8d" if dark else "#9b87b6"
        hover = "#8b70b2" if dark else "#7A5FA1"
        vertical_style = f"""
            QScrollBar:vertical {{ background: {track}; width: 10px; margin: 2px 1px; border: none; border-radius: 5px; }}
            QScrollBar::handle:vertical {{ background: {handle}; min-height: 36px; border-radius: 4px; }}
            QScrollBar::handle:vertical:hover {{ background: {hover}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; width: 0px; border: none; background: transparent; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """
        horizontal_style = f"""
            QScrollBar:horizontal {{ background: {track}; height: 10px; margin: 1px 2px; border: none; border-radius: 5px; }}
            QScrollBar::handle:horizontal {{ background: {handle}; min-width: 36px; border-radius: 4px; }}
            QScrollBar::handle:horizontal:hover {{ background: {hover}; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ height: 0px; width: 0px; border: none; background: transparent; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
        """
        table.verticalScrollBar().setStyleSheet(vertical_style)
        table.verticalScrollBar().setFixedWidth(10)
        table.horizontalScrollBar().setStyleSheet(horizontal_style)
        table.horizontalScrollBar().setFixedHeight(10)

    def eventFilter(self, obj, event):
        if obj in getattr(self, "_title_drag_widgets", ()):
            if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._title_drag_offset = event.globalPos() - self.frameGeometry().topLeft()
                return True
            if event.type() == QtCore.QEvent.MouseMove and event.buttons() & Qt.LeftButton:
                if self._title_drag_offset is not None:
                    self.move(event.globalPos() - self._title_drag_offset)
                return True
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                self._title_drag_offset = None
                return True
        return super().eventFilter(obj, event)

    _MAX_WIDGET_HEIGHT = 16777215

    @classmethod
    def _snap_table_to_whole_rows(cls, table):
        """Let the table show whole rows only.

        The window is a fixed size, so whatever height is left over lands the
        last row half-drawn against the bottom border, which reads as a drawing
        glitch rather than as "scroll for more".

        Only ever measured while the table is uncapped: measuring a capped table
        and capping it again shaves a row off on every pass. QTableView owns its
        viewport margins for its headers, so those are not free for this.
        """
        if table.rowCount() <= 0 or table.maximumHeight() < cls._MAX_WIDGET_HEIGHT:
            return
        row_height = table.rowHeight(0) or table.verticalHeader().defaultSectionSize()
        chrome = table.horizontalHeader().height() + 2 * table.frameWidth()
        if table.horizontalScrollBar().isVisible():
            chrome += table.horizontalScrollBar().height()
        available = table.height() - chrome
        if row_height <= 0 or available < row_height:
            return
        table.setMaximumHeight((available // row_height) * row_height + chrome)

    def _center_on_owner(self):
        owner_window = None
        try:
            owner_window = self.owner.window() if self.owner is not None else None
        except Exception:
            owner_window = None
        if owner_window is not None and owner_window.isVisible():
            target = owner_window.frameGeometry().center() - self.rect().center()
        else:
            screen = QApplication.screenAt(QtGui.QCursor.pos()) if hasattr(QApplication, "screenAt") else None
            screen = screen or QApplication.primaryScreen()
            if screen is None:
                return
            target = screen.availableGeometry().center() - self.rect().center()

        screen = QApplication.screenAt(target) if hasattr(QApplication, "screenAt") else None
        screen = screen or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            target.setX(max(available.left(), min(target.x(), available.right() - self.width() + 1)))
            target.setY(max(available.top(), min(target.y(), available.bottom() - self.height() + 1)))
        self.move(target)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._centered_once:
            self._centered_once = True
            self._center_on_owner()
            QtCore.QTimer.singleShot(0, self._center_on_owner)
        # After the first idle turn the layout is final, which is the only point
        # at which a table's height means anything.
        QtCore.QTimer.singleShot(0, self._snap_visible_table)
        for tab_widget in (self.tabs, self.ocr_tabs, self.translation_tabs):
            try:
                tab_widget.currentChanged.disconnect(self._on_tab_changed)
            except TypeError:
                pass
            tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, _index):
        # A page is laid out when it is first shown, so its table can only be
        # measured after switching to it.
        QtCore.QTimer.singleShot(0, self._snap_visible_table)

    def _snap_visible_table(self):
        for table in (self.windows_table, self.tesseract_table, self.easyocr_table,
                      self.rapidocr_table, self.argos_table):
            if table is not None and table.isVisible():
                self._snap_table_to_whole_rows(table)

    def _build_tabs(self):
        # The Windows OCR tab drives Windows Features on Demand through elevated
        # PowerShell; there is no such engine or mechanism on other systems.
        if platform_support.supports_windows_ocr():
            self.windows_table = self._add_engine_tab(
                self.ocr_tabs,
                "Windows",
                language_manager_text(self.lang, "windows_note"),
                self._populate_windows_table,
                [
                    (language_manager_text(self.lang, "install_selected"), self._install_selected_windows),
                    (language_manager_text(self.lang, "remove_highlighted"), self._remove_selected_windows),
                    (language_manager_text(self.lang, "windows_settings"), self._open_windows_settings),
                ],
            )
        self.tesseract_table = self._add_engine_tab(
            self.ocr_tabs,
            "Tesseract",
            language_manager_text(self.lang, "tesseract_note"),
            self._populate_tesseract_table,
            [
                (language_manager_text(self.lang, "install_selected"), self._install_selected_tesseract),
                (language_manager_text(self.lang, "remove_highlighted"), self._remove_selected_tesseract),
            ],
            missing_engine="Tesseract",
            install_engine_callback=self._install_tesseract_engine,
            remove_engine_callback=self._remove_tesseract_engine,
        )
        self.easyocr_table = self._add_engine_tab(
            self.ocr_tabs,
            "EasyOCR",
            language_manager_text(self.lang, "easyocr_note"),
            self._populate_easyocr_table,
            [
                (language_manager_text(self.lang, "install_selected"), self._install_selected_easyocr),
                (language_manager_text(self.lang, "remove_highlighted"), self._remove_selected_easyocr),
            ],
            missing_engine=EASYOCR_ENGINE_DISPLAY,
            install_engine_callback=self._install_easyocr_engine,
            remove_engine_callback=self._remove_easyocr_engine,
        )
        self.rapidocr_table = self._add_engine_tab(
            self.ocr_tabs,
            "RapidOCR",
            language_manager_text(self.lang, "rapidocr_note"),
            self._populate_rapidocr_table,
            [],
            header_labels=[
                "",
                language_manager_text(self.lang, "component"),
                language_manager_text(self.lang, "package"),
                language_manager_text(self.lang, "status"),
            ],
            missing_engine=RAPIDOCR_ENGINE_DISPLAY,
            install_engine_callback=self._install_rapidocr_engine,
            remove_engine_callback=self._remove_rapidocr_engine,
        )
        self.rapidocr_table.setColumnHidden(0, True)

        self.hymt_table = self._add_engine_tab(
            self.translation_tabs,
            HYMT_ENGINE_DISPLAY,
            language_manager_text(self.lang, "hymt_note"),
            self._populate_hymt_table,
            [],
            header_labels=[
                "",
                language_manager_text(self.lang, "component"),
                language_manager_text(self.lang, "package"),
                language_manager_text(self.lang, "status"),
            ],
            missing_engine=HYMT_ENGINE_DISPLAY,
            install_engine_callback=self._install_hymt_engine,
            remove_engine_callback=self._remove_hymt_engine,
        )
        self.hymt_table.setColumnHidden(0, True)

        self.argos_table = self._add_engine_tab(
            self.translation_tabs,
            "Argos",
            language_manager_text(self.lang, "argos_note"),
            self._populate_argos_table,
            [
                (language_manager_text(self.lang, "install_selected"), self._install_selected_argos),
                (language_manager_text(self.lang, "remove_highlighted"), self._remove_selected_argos),
            ],
            header_labels=[
                "",
                language_manager_text(self.lang, "direction"),
                language_manager_text(self.lang, "package"),
                language_manager_text(self.lang, "status"),
            ],
            search_placeholder=language_manager_text(self.lang, "search"),
        )

    def _engine_remove_button_style(self):
        """Its own sheet: a rule in the dialog's stylesheet is outranked by the
        settings window this dialog is a child of, and the button came out
        looking like an ordinary action."""
        dark = self._is_dark_theme()
        text = "#e0879a" if dark else "#b03a52"
        border = "#6b3f4c" if dark else "#e2b7c0"
        hover_bg = "#462b33" if dark else "#fbe9ed"
        hover_text = "#ffd7de" if dark else "#8f2a40"
        pressed = "#5a343e" if dark else "#f3d7de"
        muted = "#8f889c" if dark else "#a39aad"
        muted_border = "#3a3645" if dark else "#e6e1ec"
        return f"""
            QPushButton#languagePackageEngineRemove {{
                background-color: transparent;
                color: {text};
                border: 1px solid {border};
                border-radius: 7px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton#languagePackageEngineRemove:hover {{
                background-color: {hover_bg};
                color: {hover_text};
            }}
            QPushButton#languagePackageEngineRemove:pressed {{ background-color: {pressed}; }}
            QPushButton#languagePackageEngineRemove:disabled {{
                color: {muted};
                border-color: {muted_border};
            }}
        """

    def _add_engine_tab(
        self,
        target_tabs,
        title,
        note,
        populate_func,
        actions,
        header_labels=None,
        search_placeholder="",
        missing_engine="",
        install_engine_callback=None,
        remove_engine_callback=None,
    ):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        note_label = QLabel(note)
        note_label.setWordWrap(True)

        # Removing an engine used to be a small × inside the picker in Settings,
        # which is not where anyone looks for it. It belongs on the engine's own
        # tab, opposite the note, next to everything else about that engine.
        remove_engine_button = None
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)
        header_row.addWidget(note_label, 1)
        if remove_engine_callback is not None:
            remove_engine_button = QPushButton(language_manager_text(self.lang, "remove_engine"))
            remove_engine_button.setObjectName("languagePackageEngineRemove")
            remove_engine_button.setCursor(Qt.PointingHandCursor)
            remove_engine_button.setMinimumHeight(30)
            remove_engine_button.setToolTip(
                tooltip_text(language_manager_text(self.lang, "remove_engine_tooltip", engine=title))
            )
            remove_engine_button.setStyleSheet(self._engine_remove_button_style())
            remove_engine_button.clicked.connect(remove_engine_callback)
            header_row.addWidget(remove_engine_button, 0, Qt.AlignTop | Qt.AlignRight)
        layout.addLayout(header_row)

        missing_frame = QFrame(page)
        missing_frame.setObjectName("languagePackageEmptyState")
        missing_layout = QVBoxLayout(missing_frame)
        missing_layout.setContentsMargins(32, 24, 32, 24)
        missing_layout.setSpacing(10)
        missing_layout.addStretch()
        missing_title = QLabel()
        missing_title.setObjectName("languagePackageEmptyTitle")
        missing_title.setAlignment(Qt.AlignCenter)
        missing_layout.addWidget(missing_title)
        missing_body = QLabel(language_manager_text(self.lang, "engine_not_installed_body"))
        missing_body.setObjectName("languagePackageEmptyBody")
        missing_body.setAlignment(Qt.AlignCenter)
        missing_body.setWordWrap(True)
        missing_layout.addWidget(missing_body)
        missing_install_button = QPushButton(language_manager_text(self.lang, "install_engine"))
        missing_install_button.setObjectName("languagePackageAction")
        missing_install_button.setMinimumHeight(34)
        missing_install_button.setMaximumWidth(190)
        if install_engine_callback is not None:
            missing_install_button.clicked.connect(install_engine_callback)
        else:
            missing_install_button.hide()
        missing_layout.addWidget(missing_install_button, 0, Qt.AlignHCenter)
        missing_layout.addStretch()
        missing_frame.hide()
        layout.addWidget(missing_frame, 1)

        filter_edit = None
        if search_placeholder:
            filter_edit = QLineEdit(page)
            filter_edit.setPlaceholderText(search_placeholder)
            filter_edit.setClearButtonEnabled(True)
            layout.addWidget(filter_edit)

        table = QTableWidget(page)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(header_labels or [
            "",
            language_manager_text(self.lang, "language"),
            language_manager_text(self.lang, "package"),
            language_manager_text(self.lang, "status"),
        ])
        table.verticalHeader().setVisible(False)
        # Missing packages are selected with checkboxes; installed packages
        # are selected as rows for removal.  NoSelection made the removal
        # action impossible to use.
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.setIconSize(QtCore.QSize(22, 22))
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.verticalScrollBar().setSingleStep(24)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        if self._is_dark_theme():
            header.setStyleSheet("QHeaderView::section { background-color: #24212e; color: #f4f6fb; border: 0; padding: 5px; }")
        else:
            header.setStyleSheet("QHeaderView::section { background-color: #f0eef7; color: #202124; border: 0; padding: 5px; }")
        table.setColumnWidth(0, 34)
        table._package_filter_edit = filter_edit
        table._pending_package_codes = set()
        table.itemChanged.connect(
            lambda item, target=table: self._on_package_item_changed(target, item)
        )
        table.cellClicked.connect(
            lambda row, column, target=table: self._on_package_row_clicked(target, row, column)
        )
        if filter_edit is not None:
            filter_edit.textChanged.connect(lambda _text, target=table: populate_func(target))
        layout.addWidget(table)

        action_widget = QWidget(page)
        action_row = QHBoxLayout(action_widget)
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch()
        table._package_action_buttons = []
        for text, callback in actions:
            button = QPushButton(text)
            button.setObjectName("languagePackageAction")
            button.setMinimumHeight(32)
            button.setStyleSheet("""
                QPushButton#languagePackageAction {
                    background-color: #7A5FA1;
                    color: #ffffff;
                    border: none;
                    border-radius: 7px;
                    padding: 7px 12px;
                }
                QPushButton#languagePackageAction:hover { background-color: #8B70B2; }
                QPushButton#languagePackageAction:pressed { background-color: #684d91; }
                QPushButton#languagePackageAction:disabled { background-color: #3a3645; color: #8f889c; }
            """)
            button.clicked.connect(callback)
            table._package_action_buttons.append(button)
            action_row.addWidget(button)
        layout.addWidget(action_widget)

        table._package_note_label = note_label
        table._package_remove_engine_button = remove_engine_button
        table._package_action_widget = action_widget
        table._package_missing_frame = missing_frame
        table._package_missing_title = missing_title
        table._package_missing_body = missing_body
        table._package_missing_install_button = missing_install_button
        table._package_missing_engine = str(missing_engine or "")
        target_tabs.addTab(page, title)
        populate_func(table)
        return table

    def _set_engine_missing_state(self, table, missing, engine_name=""):
        missing = bool(missing)
        engine_name = str(engine_name or getattr(table, "_package_missing_engine", ""))
        frame = getattr(table, "_package_missing_frame", None)
        if frame is None:
            return
        frame.setVisible(missing)
        table.setVisible(not missing)
        note = getattr(table, "_package_note_label", None)
        if note is not None:
            note.setVisible(not missing)
        filter_edit = getattr(table, "_package_filter_edit", None)
        if filter_edit is not None:
            filter_edit.setVisible(not missing)
        actions = getattr(table, "_package_action_widget", None)
        if actions is not None:
            actions.setVisible(not missing)
        # Nothing to remove while the engine is missing: that state offers
        # Install engine in the middle of the page instead.
        remove_engine = getattr(table, "_package_remove_engine_button", None)
        if remove_engine is not None:
            remove_engine.setVisible(not missing)
        title = getattr(table, "_package_missing_title", None)
        if title is not None:
            title.setText(
                language_manager_text(
                    self.lang,
                    "engine_not_installed_title",
                    engine=engine_name,
                )
            )

    def refresh_all(self):
        if self.windows_table is not None:
            self._populate_windows_table(self.windows_table)
        self._populate_tesseract_table(self.tesseract_table)
        self._populate_easyocr_table(self.easyocr_table)
        self._populate_rapidocr_table(self.rapidocr_table)
        self._populate_hymt_table(self.hymt_table)
        self._populate_argos_table(self.argos_table)

    def refresh_catalog(self):
        self._windows_tags_cache = None
        self._windows_capabilities_cache = None
        self._windows_ready_codes_cache = None
        self._easyocr_status_cache = None
        self._rapidocr_status_cache = None
        self.refresh_all()
        self._start_runtime_probe()
        self._start_argos_catalog_refresh(True)

    def _start_runtime_probe(self):
        """Refresh slow OCR capabilities without delaying the dialog itself."""
        if self._runtime_probe_active:
            return
        self._runtime_probe_active = True
        threading.Thread(target=self._runtime_probe_worker, daemon=True).start()

    def _runtime_probe_worker(self):
        windows_payload = {
            "windows_tags": [],
            "windows_capabilities": None,
            "windows_ready_codes": [],
        }
        try:
            windows_payload["windows_tags"] = self._available_windows_tags()
        except Exception as exc:
            windows_payload["windows_error"] = str(exc)
        try:
            windows_payload["windows_capabilities"] = self._windows_ocr_capability_catalog()
        except Exception as exc:
            windows_payload["windows_capabilities_error"] = str(exc)
        try:
            import ocr
            available_by_tag = {
                str(tag).lower(): str(tag)
                for tag in windows_payload["windows_tags"]
                if str(tag).strip()
            }
            for language in APP_LANGUAGES:
                matched = ocr._match_available_windows_ocr_tag(
                    windows_ocr_tag(language.code),
                    available_by_tag,
                )
                if matched and ocr._get_windows_ocr_engine(matched) is not None:
                    windows_payload["windows_ready_codes"].append(language.code)
        except Exception as exc:
            windows_payload["windows_ready_error"] = str(exc)
        self._emit_runtime_probe_payload(windows_payload)

        easyocr_status = (False, "EasyOCR check failed")
        try:
            easyocr_status = self.owner._easyocr_importable_status()
        except Exception as exc:
            easyocr_status = (False, str(exc))
        self._emit_runtime_probe_payload({"easyocr": easyocr_status})

        rapidocr_status = (False, "RapidOCR check failed")
        try:
            rapidocr_status = self.owner._rapidocr_importable_status()
        except Exception as exc:
            rapidocr_status = (False, str(exc))
        self._emit_runtime_probe_payload({"rapidocr": rapidocr_status, "complete": True})

    def _emit_runtime_probe_payload(self, payload):
        try:
            self._runtime_probe_ready.emit(payload)
        except RuntimeError:
            # The user may close the package window while a native worker is
            # still finishing its import probe.
            pass

    @QtCore.pyqtSlot(object)
    def _on_runtime_probe_ready(self, payload):
        if not isinstance(payload, dict):
            return
        if payload.get("complete"):
            self._runtime_probe_active = False
        if "windows_tags" in payload:
            self._windows_tags_cache = list(payload.get("windows_tags") or [])
            capabilities = payload.get("windows_capabilities")
            self._windows_capabilities_cache = (
                dict(capabilities)
                if isinstance(capabilities, dict) and capabilities
                else None
            )
            if "windows_ready_codes" in payload:
                self._windows_ready_codes_cache = set(
                    payload.get("windows_ready_codes") or []
                )
        if "easyocr" in payload:
            self._easyocr_status_cache = tuple(payload.get("easyocr") or (False, ""))
        if "rapidocr" in payload:
            self._rapidocr_status_cache = tuple(payload.get("rapidocr") or (False, ""))
        if "windows_tags" in payload and self.windows_table is not None:
            self._populate_windows_table(self.windows_table)
        if "easyocr" in payload and self.easyocr_table is not None:
            self._populate_easyocr_table(self.easyocr_table)
        if "rapidocr" in payload and self.rapidocr_table is not None:
            self._populate_rapidocr_table(self.rapidocr_table)

    def _on_package_item_changed(self, table, item):
        if item is None or item.column() != 0:
            return
        code = item.data(Qt.UserRole)
        if not code or not (item.flags() & Qt.ItemIsEnabled):
            return
        pending = table._pending_package_codes
        if item.checkState() == Qt.Checked:
            pending.add(code)
        else:
            pending.discard(code)

    def _on_package_row_clicked(self, table, row, column):
        # Qt already toggles the actual checkbox. Let the rest of the row act
        # as a larger hit target without toggling column 0 twice.
        if column == 0:
            return
        item = table.item(row, 0)
        if item is None:
            return
        required = Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
        if (item.flags() & required) != required:
            return
        item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)

    def _set_language_rows(self, table, rows):
        pending = set(getattr(table, "_pending_package_codes", set()))
        # Healthy installed packages stay at the top.  Keep source order inside
        # each group so language lists remain predictable and stable.
        rows = [
            data
            for _source_index, data in sorted(
                enumerate(rows),
                key=lambda pair: (0 if pair[1].get("checked") else 1, pair[0]),
            )
        ]
        signal_blocker = QtCore.QSignalBlocker(table)
        table.setRowCount(len(rows))
        dark = self._is_dark_theme()
        header_bg = QColor("#24212e" if dark else "#f0eef7")
        header_fg = QColor("#f4f6fb" if dark else "#202124")
        for column in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setBackground(QBrush(header_bg))
                header_item.setForeground(QBrush(header_fg))
        even_bg = QColor("#17181d" if dark else "#ffffff")
        odd_bg = QColor("#20212a" if dark else "#f7f6fb")
        fg = QColor("#f4f6fb" if dark else "#202124")
        muted_fg = QColor("#aeb2bf" if dark else "#777777")
        for row, data in enumerate(rows):
            bg = odd_bg if row % 2 else even_bg
            check_item = QTableWidgetItem()
            code = data["code"]
            check_item.setData(Qt.UserRole, code)
            show_checkbox = data.get("show_checkbox", True)
            selectable = bool(data.get("selectable", False))
            if data.get("checked") or data.get("selection_invalid", False):
                pending.discard(code)
            if show_checkbox:
                check_item.setCheckState(
                    Qt.Checked
                    if data["checked"] or (selectable and code in pending)
                    else Qt.Unchecked
                )
            flags = Qt.ItemIsUserCheckable if show_checkbox else Qt.NoItemFlags
            if show_checkbox and selectable:
                flags |= Qt.ItemIsEnabled | Qt.ItemIsSelectable
            check_item.setFlags(flags)
            check_item.setBackground(QBrush(bg))
            check_item.setForeground(QBrush(fg if selectable else muted_fg))
            table.setItem(row, 0, check_item)

            icon_path = data.get("icon", "")
            icon = QIcon(resource_path(icon_path)) if icon_path else QIcon()
            lang_item = QTableWidgetItem(icon, data["name"])
            lang_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            lang_item.setBackground(QBrush(bg))
            lang_item.setForeground(QBrush(fg))
            table.setItem(row, 1, lang_item)

            package_item = QTableWidgetItem(data["package"])
            package_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            package_item.setBackground(QBrush(bg))
            package_item.setForeground(QBrush(fg))
            table.setItem(row, 2, package_item)

            status_item = QTableWidgetItem(data["status"])
            status_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            status_item.setBackground(QBrush(bg))
            status_item.setForeground(QBrush(fg if data.get("checked") or data.get("selectable") else muted_fg))
            table.setItem(row, 3, status_item)
        table.resizeRowsToContents()
        table._pending_package_codes = pending
        del signal_blocker

    def _language_name(self, language):
        return language.display_name(self.lang)

    def _language_display_name(self, code):
        for language in APP_LANGUAGES:
            if language.code == code:
                return language.display_name(self.lang)
        return str(code).upper()

    def _status_installed(self):
        return language_manager_text(self.lang, "installed")

    def _status_missing(self):
        return language_manager_text(self.lang, "missing")

    def _status_can_download(self):
        return language_manager_text(self.lang, "can_download")

    def _status_engine_missing(self, engine_name):
        return language_manager_text(self.lang, "engine_missing", engine=engine_name)

    def _status_checking(self):
        return language_manager_text(self.lang, "checking")

    def _available_windows_tags(self):
        try:
            import ocr
            return list(ocr._get_available_windows_ocr_language_tags())
        except Exception:
            return []

    def _windows_ocr_capability_catalog(self):
        """Return OCR capability tags and states available on this Windows build."""
        if sys.platform != "win32":
            return {}
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        command = (
            "$ErrorActionPreference='Stop'; "
            "Get-WindowsCapability -Online | "
            "Where-Object { $_.Name -like 'Language.OCR~~~*' } | "
            "ForEach-Object { '{0}|{1}' -f $_.Name,$_.State }"
        )
        # One at a time. Every one of these opens a DISM session against the
        # online image, and the tab, the runtime probe and the post-install
        # verification all ask at once — dism.log showed three sessions inside
        # the same second. Overlapping sessions are what makes Windows answer
        # "servicing is busy", and each one costs a PowerShell start-up anyway.
        with _WINDOWS_SERVICING_LOCK:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=create_no_window,
                timeout=30,
            )
        if completed.returncode != 0:
            raise RuntimeError((completed.stdout or "").strip() or "Could not query Windows OCR capabilities")
        catalog = {}
        pattern = re.compile(r"^Language\.OCR~~~(.+?)~0\.0\.1\.0\|(.+)$", re.IGNORECASE)
        for line in (completed.stdout or "").splitlines():
            match = pattern.match(line.strip())
            if match:
                catalog[match.group(1).lower()] = match.group(2).strip()
        return catalog

    def _populate_windows_table(self, table):
        self._set_engine_missing_state(table, False)
        available_tags = self._windows_tags_cache
        checking = available_tags is None
        available_tags = available_tags or []
        capability_catalog = self._windows_capabilities_cache
        catalog_known = isinstance(capability_catalog, dict)
        capability_catalog = capability_catalog or {}
        available_by_tag = {str(tag).lower(): str(tag) for tag in available_tags if str(tag).strip()}
        rows = []
        for language in APP_LANGUAGES:
            expected = windows_ocr_tag(language.code)
            matched = ""
            try:
                import ocr
                matched = ocr._match_available_windows_ocr_tag(expected, available_by_tag)
            except Exception:
                matched = available_by_tag.get(expected.lower(), "")
            api_installed = bool(matched)
            engine_ready = (
                language.code in self._windows_ready_codes_cache
                if self._windows_ready_codes_cache is not None
                else api_installed
            )
            capability_state = capability_catalog.get(expected.lower(), "")
            capability_installed = capability_state.lower() == "installed"
            supported = not catalog_known or expected.lower() in capability_catalog
            unavailable = bool(catalog_known and not supported)
            # Do not trust a single Windows signal.  Interrupted DISM work can
            # report the capability as Installed before WinRT can create/use
            # the OCR language.  Such rows are offered for repair instead of
            # being presented as healthy packages.
            installed = (
                api_installed and engine_ready and capability_installed
                if catalog_known
                else api_installed and engine_ready
            )
            repair_needed = bool(
                catalog_known
                and supported
                and (
                    api_installed != capability_installed
                    or (capability_installed and not engine_ready)
                )
            )
            if checking:
                status = self._status_checking()
            elif installed:
                status = f"{self._status_installed()} ({matched or expected})"
            elif repair_needed:
                status = language_manager_text(self.lang, "repair_needed")
            elif unavailable:
                status = language_manager_text(self.lang, "unavailable")
            else:
                status = self._status_missing()
            rows.append({
                "code": language.code,
                "icon": language_icon_path(language.code),
                "name": self._language_name(language),
                "package": expected,
                "status": status,
                "checked": installed,
                "selectable": bool(not checking and supported and not installed),
                "selection_invalid": unavailable,
                "repair": repair_needed,
            })
        self._set_language_rows(table, rows)

    def _tesseract_data_dirs(self):
        tess_cmd = self.owner._find_available_tesseract_exe()
        if not tess_cmd:
            return "", []
        tess_dir = os.path.dirname(tess_cmd)
        candidate_dirs = [
            os.path.join(tess_dir, "tessdata"),
            os.path.join(os.path.dirname(tess_dir), "tessdata"),
        ]
        return tess_cmd, [path for path in candidate_dirs if os.path.isdir(path)]

    def _tesseract_language_installed(self, tess_code, data_dirs):
        return any(os.path.isfile(os.path.join(path, f"{tess_code}.traineddata")) for path in data_dirs)

    def _populate_tesseract_table(self, table):
        tess_cmd, data_dirs = self._tesseract_data_dirs()
        self._set_engine_missing_state(table, not bool(tess_cmd), "Tesseract")
        if not tess_cmd:
            table.setRowCount(0)
            table._pending_package_codes.clear()
            return
        rows = []
        for language in APP_LANGUAGES:
            tess_code = tesseract_language_code(language.code)
            installed = bool(tess_cmd and self._tesseract_language_installed(tess_code, data_dirs))
            rows.append({
                "code": language.code,
                "icon": language_icon_path(language.code),
                "name": self._language_name(language),
                "package": f"{tess_code}.traineddata",
                "status": (
                    self._status_engine_missing("Tesseract")
                    if not tess_cmd else
                    self._status_installed()
                    if installed else
                    self._status_can_download()
                ),
                "checked": installed,
                "selectable": bool(tess_cmd and not installed),
            })
        self._set_language_rows(table, rows)

    def _easyocr_model_dir(self):
        return os.path.join(self.owner._local_easyocr_dir(), "models")

    def _easyocr_model_groups_for_language(self, language_code):
        # EasyOCR adds English as a compatible language, but loads one
        # recognition network chosen by the primary script (for example,
        # cyrillic_g2 for ["ru", "en"] or zh_sim_g2 for ["ch_sim", "en"]).
        # Requiring english_g2 as a second file made successful installs look
        # incomplete and hid them from language selectors.
        easy_codes = easyocr_language_codes(language_code)
        primary_code = easy_codes[0] if easy_codes else language_code
        group = EASYOCR_MODEL_GROUP_BY_LANGUAGE.get(
            primary_code,
            EASYOCR_MODEL_GROUP_BY_LANGUAGE.get(language_code),
        )
        return [group] if group else []

    def _easyocr_group_installed(self, group):
        model_dir = self._easyocr_model_dir()
        variants = EASYOCR_MODEL_FILE_VARIANTS.get(group, (f"{group}.pth",))
        return any(os.path.isfile(os.path.join(model_dir, filename)) for filename in variants)

    def _easyocr_language_installed(self, language_code):
        model_dir = self._easyocr_model_dir()
        if not os.path.isfile(os.path.join(model_dir, "craft_mlt_25k.pth")):
            return False
        return all(self._easyocr_group_installed(group) for group in self._easyocr_model_groups_for_language(language_code))

    def _populate_easyocr_table(self, table):
        checking = self._easyocr_status_cache is None
        engine_ready, _error = self._easyocr_status_cache or (False, "")
        self._set_engine_missing_state(
            table,
            bool(not checking and not engine_ready),
            EASYOCR_ENGINE_DISPLAY,
        )
        if not checking and not engine_ready:
            table.setRowCount(0)
            table._pending_package_codes.clear()
            return
        rows = []
        for language in APP_LANGUAGES:
            groups = self._easyocr_model_groups_for_language(language.code)
            installed = bool(engine_ready and self._easyocr_language_installed(language.code))
            package = "craft + " + ", ".join(groups) if groups else "craft"
            rows.append({
                "code": language.code,
                "icon": language_icon_path(language.code),
                "name": self._language_name(language),
                "package": package,
                "status": (
                    self._status_checking()
                    if checking else
                    self._status_engine_missing(EASYOCR_ENGINE_DISPLAY)
                    if not engine_ready else
                    self._status_installed()
                    if installed else
                    self._status_can_download()
                ),
                "checked": installed,
                "selectable": bool(engine_ready and not installed),
            })
        self._set_language_rows(table, rows)

    def _populate_rapidocr_table(self, table):
        checking = self._rapidocr_status_cache is None
        engine_ready, _error = self._rapidocr_status_cache or (False, "")
        self._set_engine_missing_state(
            table,
            bool(not checking and not engine_ready),
            RAPIDOCR_ENGINE_DISPLAY,
        )
        if not checking and not engine_ready:
            table.setRowCount(0)
            table._pending_package_codes.clear()
            return
        installed = self._status_installed()
        missing = self._status_missing()
        needs_engine = language_manager_text(self.lang, "engine_first")
        rows = [
            {
                "code": "rapidocr-engine",
                "icon": "",
                "name": language_manager_text(self.lang, "ocr_engine"),
                "package": "rapidocr",
                "status": self._status_checking() if checking else installed if engine_ready else missing,
                "checked": bool(engine_ready),
                "selectable": False,
                "show_checkbox": False,
            },
            {
                "code": "rapidocr-runtime",
                "icon": "",
                "name": language_manager_text(self.lang, "runtime"),
                "package": "onnxruntime",
                "status": self._status_checking() if checking else installed if engine_ready else missing,
                "checked": bool(engine_ready),
                "selectable": False,
                "show_checkbox": False,
            },
            {
                "code": "rapidocr-detector",
                "icon": "",
                "name": language_manager_text(self.lang, "detector"),
                "package": "PP-OCR detector",
                "status": self._status_checking() if checking else installed if engine_ready else needs_engine,
                "checked": bool(engine_ready),
                "selectable": False,
                "show_checkbox": False,
            },
            {
                "code": "rapidocr-recognition",
                "icon": "",
                "name": language_manager_text(self.lang, "recognition"),
                "package": "Chinese + English",
                "status": self._status_checking() if checking else installed if engine_ready else needs_engine,
                "checked": bool(engine_ready),
                "selectable": False,
                "show_checkbox": False,
            },
        ]
        self._set_language_rows(table, rows)

    def _hymt_package_name(self):
        locate = getattr(self.owner, "_local_hymt_dir", None)
        folder = locate() if callable(locate) else ""
        return os.path.basename(str(folder).rstrip("\\/")) or "hymt"

    def _populate_hymt_table(self, table):
        """Hy-MT ships as one local model, so the table lists what it is made of
        rather than languages to tick."""
        if table is None:
            return
        # An owner without the probe (a stub, a partially built window) means
        # "not installed" rather than a crash while the dialog is opening.
        probe = getattr(self.owner, "_hymt_installed", None)
        installed = bool(probe()) if callable(probe) else False
        self._set_engine_missing_state(table, not installed, HYMT_ENGINE_DISPLAY)
        if not installed:
            table.setRowCount(0)
            table._pending_package_codes.clear()
            return
        status = self._status_installed()
        rows = [
            {
                "code": "hymt-engine",
                "icon": "",
                "name": language_manager_text(self.lang, "translation_engine"),
                "package": "Hy-MT",
                "status": status,
                "checked": True,
                "selectable": False,
                "show_checkbox": False,
            },
            {
                "code": "hymt-model",
                "icon": "",
                "name": language_manager_text(self.lang, "local_model"),
                "package": self._hymt_package_name(),
                "status": status,
                "checked": True,
                "selectable": False,
                "show_checkbox": False,
            },
        ]
        self._set_language_rows(table, rows)

    def _argos_direction_name(self, source_code, target_code):
        by_code = {language.code: language for language in APP_LANGUAGES}
        source = by_code.get(source_code)
        target = by_code.get(target_code)
        source_name = source.display_name(self.lang) if source else source_code.upper()
        target_name = target.display_name(self.lang) if target else target_code.upper()
        return f"{source_name} → {target_name}"

    def _populate_argos_table(self, table):
        self._set_engine_missing_state(table, False)
        languages_by_code = {language.code: language for language in APP_LANGUAGES}
        supported = set(languages_by_code)
        rows = []
        filter_edit = getattr(table, "_package_filter_edit", None)
        query = str(filter_edit.text() if filter_edit is not None else "").strip().casefold()
        normalized_query = query.replace("→", "->").replace(" ", "")

        def package_sort_key(package):
            source_code = str(package.get("source_code") or "").lower()
            target_code = str(package.get("target_code") or "").lower()
            pair = (source_code, target_code)
            preferred_rank = {("en", "ru"): 0, ("ru", "en"): 1}.get(pair, 2)
            return (
                0 if package.get("installed") else 1,
                preferred_rank,
                source_code,
                target_code,
            )

        packages = sorted(
            self._argos_catalog,
            key=package_sort_key,
        )
        for package in packages:
            source_code = str(package.get("source_code") or "").lower()
            target_code = str(package.get("target_code") or "").lower()
            if source_code not in supported or target_code not in supported:
                continue
            source = languages_by_code[source_code]
            target = languages_by_code[target_code]
            pair_code = f"{source_code}->{target_code}"
            searchable = " ".join(
                (
                    pair_code,
                    pair_code.replace("->", "→"),
                    source.english_name,
                    source.russian_name,
                    source.display_name(self.lang),
                    target.english_name,
                    target.russian_name,
                    target.display_name(self.lang),
                    str(package.get("package_name") or ""),
                )
            ).casefold()
            normalized_searchable = searchable.replace("→", "->").replace(" ", "")
            if query and query not in searchable and normalized_query not in normalized_searchable:
                continue
            installed = bool(package.get("installed"))
            available = bool(package.get("available"))
            version = str(package.get("version") or "").strip()
            status = self._status_installed() if installed else self._status_can_download() if available else self._status_missing()
            if version:
                status = f"{status} · v{version}"
            rows.append({
                "code": pair_code,
                "icon": language_icon_path(source_code),
                "name": self._argos_direction_name(source_code, target_code),
                "package": str(package.get("package_name") or f"translate-{source_code}_{target_code}"),
                "status": status,
                "checked": installed,
                "selectable": bool(available and not installed),
            })
        if not rows:
            if self._argos_catalog_loading:
                message = language_manager_text(self.lang, "loading")
            elif self._argos_catalog_error:
                message = language_manager_text(self.lang, "load_error") + self._argos_catalog_error
            elif query:
                message = language_manager_text(self.lang, "no_match")
            else:
                message = language_manager_text(self.lang, "no_packages")
            rows = [{
                "code": "",
                "icon": "",
                "name": message,
                "package": "",
                "status": "",
                "checked": False,
                "selectable": False,
            }]
        self._set_language_rows(table, rows)

    def _start_argos_catalog_refresh(self, refresh):
        if self._argos_catalog_request_active:
            return
        self._argos_catalog_request_active = True
        self._argos_catalog_loading = True
        self._argos_catalog_error = ""
        if self.argos_table is not None:
            self._populate_argos_table(self.argos_table)
        threading.Thread(
            target=self._load_argos_catalog_worker,
            args=(bool(refresh),),
            daemon=True,
        ).start()

    def _load_argos_catalog_worker(self, refresh):
        error = ""
        packages = []
        try:
            import translater
            packages = translater.argos_package_catalog(refresh=refresh)
        except Exception as exc:
            error = str(exc)
            if refresh:
                try:
                    packages = translater.argos_package_catalog(refresh=False)
                except Exception:
                    pass
        self._argos_catalog = list(packages or [])
        try:
            QMetaObject.invokeMethod(
                self,
                "_on_argos_catalog_ready",
                Qt.QueuedConnection,
                QtCore.Q_ARG(str, str(error)),
            )
        except RuntimeError:
            pass

    @QtCore.pyqtSlot(str)
    def _on_argos_catalog_ready(self, error):
        self._argos_catalog_request_active = False
        self._argos_catalog_loading = False
        self._argos_catalog_error = str(error or "")
        if self.argos_table is not None:
            self._populate_argos_table(self.argos_table)

    def _selected_codes(self, table):
        codes = []
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is None:
                continue
            if not (item.flags() & Qt.ItemIsEnabled):
                continue
            if item.checkState() == Qt.Checked:
                codes.append(item.data(Qt.UserRole))
        for code in sorted(getattr(table, "_pending_package_codes", set())):
            if code and code not in codes:
                codes.append(code)
        return codes

    def _highlighted_codes(self, table):
        rows = sorted({index.row() for index in table.selectionModel().selectedRows()})
        codes = []
        for row in rows:
            item = table.item(row, 0)
            code = item.data(Qt.UserRole) if item is not None else ""
            if code:
                codes.append(code)
        return codes

    def _show_no_selection(self):
        QMessageBox.information(
            self,
            settings_text(self.lang, "ocr_language_packs"),
            language_manager_text(self.lang, "no_selection"),
        )

    def _open_windows_settings(self):
        try:
            if sys.platform == "win32":
                os.startfile("ms-settings:regionlanguage")
        except Exception as exc:
            QMessageBox.warning(self, "Windows OCR", str(exc))

    def _refresh_after_owner_install(self, in_progress_attr):
        if bool(getattr(self.owner, in_progress_attr, False)):
            QtCore.QTimer.singleShot(750, lambda: self._refresh_after_owner_install(in_progress_attr))
            return
        self._windows_tags_cache = None
        self._windows_capabilities_cache = None
        self._windows_ready_codes_cache = None
        self._easyocr_status_cache = None
        self._rapidocr_status_cache = None
        self.refresh_all()
        self._start_runtime_probe()

    def _remove_engine(self, remove_method, in_progress_attr):
        """Run the owner's removal, then show the result on this page.

        The confirmation, the deletion and the engine-selector fallback all live
        in SettingsWindow already; this only routes to them and refreshes.
        """
        remover = getattr(self.owner, remove_method, None)
        if remover is None:
            return
        remover()
        QtCore.QTimer.singleShot(400, lambda: self._refresh_after_owner_install(in_progress_attr))

    def _remove_tesseract_engine(self):
        self._remove_engine("remove_tesseract_engine", "_tesseract_install_in_progress")

    def _remove_easyocr_engine(self):
        self._remove_engine("remove_easyocr_engine", "_easyocr_install_in_progress")

    def _remove_rapidocr_engine(self):
        self._remove_engine("remove_rapidocr_engine", "_rapidocr_install_in_progress")

    def _remove_hymt_engine(self):
        self._remove_engine("remove_hymt_engine", "_hymt_install_in_progress")

    def _install_hymt_engine(self):
        if self.owner._hymt_installed():
            QMessageBox.information(
                self,
                HYMT_ENGINE_DISPLAY,
                language_manager_text(self.lang, "already", engine=HYMT_ENGINE_DISPLAY),
            )
            return
        self.owner.start_hymt_install()
        QtCore.QTimer.singleShot(750, lambda: self._refresh_after_owner_install("_hymt_install_in_progress"))

    def _install_tesseract_engine(self):
        if self.owner._find_available_tesseract_exe():
            QMessageBox.information(
                self,
                "Tesseract",
                language_manager_text(self.lang, "already", engine="Tesseract"),
            )
            return
        self.owner.start_tesseract_install(progress_owner=self)
        QtCore.QTimer.singleShot(750, lambda: self._refresh_after_owner_install("_tesseract_install_in_progress"))

    def _install_easyocr_engine(self):
        if self._easyocr_status_cache is None:
            QMessageBox.information(
                self,
                EASYOCR_ENGINE_DISPLAY,
                language_manager_text(self.lang, "still", engine=EASYOCR_ENGINE_DISPLAY),
            )
            return
        ready, _error = self._easyocr_status_cache or (False, "")
        if ready:
            QMessageBox.information(
                self,
                EASYOCR_ENGINE_DISPLAY,
                language_manager_text(self.lang, "already", engine=EASYOCR_ENGINE_DISPLAY),
            )
            return
        self.owner.start_easyocr_install(progress_owner=self)
        QtCore.QTimer.singleShot(750, lambda: self._refresh_after_owner_install("_easyocr_install_in_progress"))

    def _install_rapidocr_engine(self):
        if self._rapidocr_status_cache is None:
            QMessageBox.information(
                self,
                RAPIDOCR_ENGINE_DISPLAY,
                language_manager_text(self.lang, "still", engine=RAPIDOCR_ENGINE_DISPLAY),
            )
            return
        ready, _error = self._rapidocr_status_cache or (False, "")
        if ready:
            QMessageBox.information(
                self,
                RAPIDOCR_ENGINE_DISPLAY,
                language_manager_text(self.lang, "already", engine=RAPIDOCR_ENGINE_DISPLAY),
            )
            return
        self.owner.start_rapidocr_install(progress_owner=self)
        QtCore.QTimer.singleShot(750, lambda: self._refresh_after_owner_install("_rapidocr_install_in_progress"))

    def _windows_ocr_capability_name(self, language_code):
        return f"Language.OCR~~~{windows_ocr_tag(language_code)}~0.0.1.0"

    @staticmethod
    def _windows_ocr_tag_from_capability(capability):
        return str(capability).split("~~~", 1)[1].rsplit("~", 1)[0].lower()

    def _wait_for_windows_ocr_capabilities(self, capabilities, attempts=12, delay=0.75, timeout=None):
        """Wait for DISM state propagation after the elevated installer exits.

        Measured behaviour: `Get-WindowsCapability` reports `Installed` on the
        very first poll once servicing returns, so this normally exits after one
        round.  The retry budget only covers a servicing stack that is still
        busy, and it reports progress so a slow machine never looks frozen.
        """
        missing = list(capabilities)
        last_error = None
        deadline = None
        if timeout is not None:
            deadline = time.monotonic() + max(0.0, float(timeout))
        attempt = 0
        while True:
            if self._cancel_requested.is_set():
                return missing
            try:
                catalog = self._windows_ocr_capability_catalog()
                last_error = None
                missing = [
                    capability
                    for capability in capabilities
                    if catalog.get(self._windows_ocr_tag_from_capability(capability), "").lower() != "installed"
                ]
                if not missing:
                    return []
            except Exception as exc:
                last_error = exc
            attempt += 1
            if deadline is not None:
                if time.monotonic() >= deadline:
                    break
            elif attempt >= max(1, int(attempts)):
                break
            self._emit_language_progress(
                language_manager_text(self.lang, "win_registering"),
                100,
                False,
            )
            time.sleep(max(0.0, float(delay)))
        if last_error is not None:
            raise RuntimeError(str(last_error))
        return missing

    def _wait_for_windows_ocr_engines(self, codes, timeout=90.0, delay=2.0):
        """Wait until WinRT can actually build a recognizer for the new languages.

        `OcrEngine.AvailableRecognizerLanguages` does refresh inside a running
        process, but not necessarily in the same instant the capability flips to
        `Installed`.  Probing once turned successful installs into errors, so
        poll instead and return whatever is still unusable when time runs out.
        """
        pending = [str(code) for code in codes]
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            try:
                import ocr

                # The engine objects are cached per language tag; drop them so a
                # freshly installed language is not masked by an earlier miss.
                ocr._UNIVERSAL_OCR_ENGINE = None
                ocr._OCR_ENGINE_CACHE.clear()
                available_by_tag = {
                    str(tag).lower(): str(tag)
                    for tag in ocr._get_available_windows_ocr_language_tags()
                    if str(tag).strip()
                }
                still_pending = []
                for code in pending:
                    actual_tag = ocr._match_available_windows_ocr_tag(
                        windows_ocr_tag(code),
                        available_by_tag,
                    )
                    if not actual_tag or ocr._get_windows_ocr_engine(actual_tag) is None:
                        still_pending.append(code)
                pending = still_pending
            except Exception:
                logger.exception("Could not probe Windows OCR recognizer availability")
            if not pending or self._cancel_requested.is_set():
                return pending
            if time.monotonic() >= deadline:
                return pending
            self._emit_language_progress(
                language_manager_text(self.lang, "win_registering"),
                100,
                False,
            )
            time.sleep(max(0.0, float(delay)))

    def _wait_for_windows_ocr_removal(self, capabilities, attempts=12, delay=0.75):
        remaining = list(capabilities)
        last_error = None
        for attempt in range(max(1, int(attempts))):
            if self._cancel_requested.is_set():
                return remaining
            try:
                catalog = self._windows_ocr_capability_catalog()
                remaining = [
                    capability
                    for capability in capabilities
                    if catalog.get(
                        self._windows_ocr_tag_from_capability(capability),
                        "",
                    ).lower() == "installed"
                ]
                if not remaining:
                    return []
            except Exception as exc:
                last_error = exc
            if attempt + 1 < attempts:
                time.sleep(max(0.0, float(delay)))
        if last_error is not None:
            raise RuntimeError(str(last_error))
        return remaining

    def _install_selected_windows(self):
        codes = self._selected_codes(self.windows_table)
        if not codes:
            self._show_no_selection()
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Windows OCR")
        msg.setText(
            language_manager_text(self.lang, "win_confirm")
            + "\n\n"
            + language_manager_text(self.lang, "win_background_info")
        )
        msg.setIcon(QMessageBox.Question)
        yes_btn = msg.addButton(settings_text(self.lang, "install"), QMessageBox.YesRole)
        msg.addButton(settings_text(self.lang, "cancel"), QMessageBox.NoRole)
        msg.exec_()
        if msg.clickedButton() != yes_btn:
            return
        self._run_language_task("Windows OCR", codes, self._install_windows_ocr_worker)

    def _install_selected_tesseract(self):
        tess_cmd = self.owner._find_available_tesseract_exe()
        if not tess_cmd:
            self._install_tesseract_engine()
            return
        codes = self._selected_codes(self.tesseract_table)
        if not codes:
            self._show_no_selection()
            return
        self._run_language_task("Tesseract", codes, self._install_tesseract_worker)

    def _install_selected_easyocr(self):
        if self._easyocr_status_cache is None:
            QMessageBox.information(
                self,
                EASYOCR_ENGINE_DISPLAY,
                language_manager_text(self.lang, "still", engine=EASYOCR_ENGINE_DISPLAY),
            )
            return
        ready, error = self._easyocr_status_cache
        if not ready:
            msg = QMessageBox(self)
            msg.setWindowTitle("EasyOCR")
            msg.setText(language_manager_text(self.lang, "easy_prompt"))
            if error:
                msg.setDetailedText(str(error))
            msg.setIcon(QMessageBox.Question)
            yes_btn = msg.addButton(settings_text(self.lang, "install"), QMessageBox.YesRole)
            msg.addButton(settings_text(self.lang, "cancel"), QMessageBox.NoRole)
            msg.exec_()
            if msg.clickedButton() == yes_btn:
                self._install_easyocr_engine()
            return
        codes = self._selected_codes(self.easyocr_table)
        if not codes:
            self._show_no_selection()
            return
        self._run_language_task("EasyOCR", codes, self._install_easyocr_worker)

    def _install_selected_argos(self):
        codes = self._selected_codes(self.argos_table)
        if not codes:
            self._show_no_selection()
            return
        self._run_language_task(
            "Argos",
            codes,
            self._install_argos_worker,
            success_message=language_manager_text(self.lang, "argos_installed"),
        )

    def _highlighted_installed_codes(self, table):
        rows = sorted({index.row() for index in table.selectionModel().selectedRows()})
        codes = []
        for row in rows:
            item = table.item(row, 0)
            if item is None or item.checkState() != Qt.Checked:
                continue
            code = item.data(Qt.UserRole)
            if code:
                codes.append(str(code))
        return codes

    def _confirm_package_removal(self, engine, codes):
        if not codes:
            QMessageBox.information(
                self,
                engine,
                language_manager_text(self.lang, "highlight"),
            )
            return False
        labels = ", ".join(code.upper() for code in codes)
        msg = QMessageBox(self)
        msg.setWindowTitle(engine)
        msg.setText(
            language_manager_text(
                self.lang,
                "remove_packages_confirm",
                engine=engine,
                packages=labels,
            )
        )
        msg.setIcon(QMessageBox.Warning)
        remove_btn = msg.addButton(settings_text(self.lang, "remove"), QMessageBox.DestructiveRole)
        msg.addButton(settings_text(self.lang, "cancel"), QMessageBox.RejectRole)
        msg.exec_()
        return msg.clickedButton() == remove_btn

    def _remove_selected_windows(self):
        codes = self._highlighted_installed_codes(self.windows_table)
        if not self._confirm_package_removal("Windows OCR", codes):
            return
        self._run_language_task(
            "Windows OCR",
            codes,
            self._remove_windows_ocr_worker,
            success_message=language_manager_text(
                self.lang, "packages_removed", engine="Windows OCR"
            ),
            failure_key="remove_failed",
        )

    def _remove_selected_tesseract(self):
        codes = self._highlighted_installed_codes(self.tesseract_table)
        if not self._confirm_package_removal("Tesseract", codes):
            return
        self._run_language_task(
            "Tesseract",
            codes,
            self._remove_tesseract_worker,
            success_message=language_manager_text(
                self.lang, "packages_removed", engine="Tesseract"
            ),
            failure_key="remove_failed",
        )

    def _remove_selected_easyocr(self):
        codes = self._highlighted_installed_codes(self.easyocr_table)
        if not self._confirm_package_removal(EASYOCR_ENGINE_DISPLAY, codes):
            return
        self._run_language_task(
            EASYOCR_ENGINE_DISPLAY,
            codes,
            self._remove_easyocr_worker,
            success_message=language_manager_text(
                self.lang, "packages_removed", engine=EASYOCR_ENGINE_DISPLAY
            ),
            failure_key="remove_failed",
        )

    def _remove_selected_argos(self):
        highlighted = self._highlighted_codes(self.argos_table)
        installed = {
            f"{package.get('source_code')}->{package.get('target_code')}"
            for package in self._argos_catalog
            if package.get("installed")
        }
        codes = [code for code in highlighted if code in installed]
        if not codes:
            QMessageBox.information(
                self,
                "Argos",
                language_manager_text(self.lang, "highlight"),
            )
            return
        labels = ", ".join(code.replace("->", "→").upper() for code in codes)
        msg = QMessageBox(self)
        msg.setWindowTitle("Argos")
        msg.setText(language_manager_text(self.lang, "remove_confirm", packages=labels))
        msg.setIcon(QMessageBox.Question)
        remove_btn = msg.addButton(settings_text(self.lang, "remove"), QMessageBox.DestructiveRole)
        msg.addButton(settings_text(self.lang, "cancel"), QMessageBox.RejectRole)
        msg.exec_()
        if msg.clickedButton() != remove_btn:
            return
        self._run_language_task(
            "Argos",
            codes,
            self._remove_argos_worker,
            success_message=language_manager_text(self.lang, "removed"),
            failure_key="remove_failed",
        )

    def _is_process_elevated(self):
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _run_powershell_script(self, script_path, elevated=False):
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if elevated and not self._is_process_elevated():
            escaped = script_path.replace("'", "''")
            command = (
                "$p = Start-Process -FilePath powershell.exe "
                "-Verb RunAs -Wait -PassThru "
                f"-ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','{escaped}'); "
                "if ($null -eq $p) { exit 1223 } else { exit $p.ExitCode }"
            )
            return subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=create_no_window,
                timeout=None,
            )
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=create_no_window,
            timeout=None,
        )

    def _run_language_task(
        self,
        title,
        codes,
        worker_func,
        success_message="",
        failure_key="install_failed",
    ):
        if self._install_in_progress:
            # A second servicing/download operation must never be queued behind
            # the user's back. Bring the existing work back instead; checkbox
            # selections in every table remain untouched for a later click.
            self._restore_task_progress()
            return
        self._install_in_progress = True
        self._active_language_task_title = str(title or "")
        self._set_package_actions_busy(True)
        self._task_success_message = str(success_message or "")
        self._task_failure_key = str(failure_key or "install_failed")
        self._cancel_requested.clear()
        self.progress_dialog = TesseractInstallProgressDialog(
            self,
            title=title,
            in_progress_attr="_install_in_progress",
            cancel_callback=self._request_install_cancel,
        )
        self.progress_dialog.setCancelButtonText(settings_text(self.lang, "cancel"))
        self.progress_dialog.setBackgroundButtonText(
            language_manager_text(self.lang, "continue_background")
        )
        self.progress_dialog.setLabelText(language_manager_text(self.lang, "preparing"))
        self.progress_dialog.setRange(0, 0)
        self.progress_dialog.backgrounded.connect(
            lambda text, name=title: self._on_task_backgrounded(name, text)
        )
        self._clear_task_status()
        self._publish_owner_task_status(
            f"{title}: {language_manager_text(self.lang, 'preparing')}",
            kind="running",
        )
        self.progress_dialog.show()
        self.progress_dialog.center_on_owner()
        self.progress_dialog.bring_to_front()
        threading.Thread(target=worker_func, args=(codes,), daemon=True).start()

    def _set_package_actions_busy(self, busy):
        """Allow one package mutation at a time without discarding selections."""
        busy = bool(busy)
        help_text = language_manager_text(self.lang, "task_busy_help")
        buttons = [
            button
            for button in self.findChildren(QPushButton)
            if button.objectName() in {
                "languagePackageAction",
                "languagePackageEngineRemove",
            }
        ]
        refresh = getattr(self, "refresh_btn", None)
        if refresh is not None:
            buttons.append(refresh)
        for button in buttons:
            if busy:
                if button.property("packageBusyWasEnabled") is None:
                    button.setProperty("packageBusyWasEnabled", bool(button.isEnabled()))
                    button.setProperty("packageBusyOldToolTip", button.toolTip())
                button.setEnabled(False)
                button.setToolTip(tooltip_text(help_text))
            else:
                was_enabled = button.property("packageBusyWasEnabled")
                if was_enabled is not None:
                    button.setEnabled(bool(was_enabled))
                    button.setToolTip(str(button.property("packageBusyOldToolTip") or ""))
                    button.setProperty("packageBusyWasEnabled", None)
                    button.setProperty("packageBusyOldToolTip", None)

    def reject(self):
        # Closing the package manager must not terminate an active Windows
        # servicing task. Keep the dialog object alive and let the user work
        # in the main window while the background worker finishes.
        if self._install_in_progress:
            if self.progress_dialog is not None:
                self.progress_dialog._continue_in_background()
            self.hide()
            return
        super().reject()

    def accept(self):
        # The visible Back button calls accept(), while the title-bar close
        # button calls reject(). Both routes must mean the same thing during a
        # long Windows servicing operation: keep it running in the background.
        if self._install_in_progress:
            if self.progress_dialog is not None:
                self.progress_dialog._continue_in_background()
            self.hide()
            return
        super().accept()

    def _request_install_cancel(self):
        if self._cancel_requested.is_set():
            return
        self._cancel_requested.set()
        marker = str(self._windows_ocr_cancel_marker or "")
        if marker:
            try:
                Path(marker).touch(exist_ok=True)
            except Exception:
                pass
        if self.progress_dialog is not None:
            self.progress_dialog.setLabelText(
                language_manager_text(self.lang, "win_cancel_pending")
            )
            self.progress_dialog.setRange(0, 0)
            self.progress_dialog.setCancellationPending(
                language_manager_text(self.lang, "canceling")
            )

    def _emit_language_progress(self, text, percent=0, determinate=True):
        QMetaObject.invokeMethod(
            self,
            "_on_language_progress",
            Qt.QueuedConnection,
            QtCore.Q_ARG(str, str(text)),
            QtCore.Q_ARG(int, int(max(0, min(100, percent)))),
            QtCore.Q_ARG(bool, bool(determinate)),
        )

    @QtCore.pyqtSlot(str, int, bool)
    def _on_language_progress(self, text, percent, determinate):
        if self.progress_dialog is None:
            return
        self.progress_dialog.setLabelText(text)
        if determinate:
            self.progress_dialog.setRange(0, 100)
            self.progress_dialog.setValue(percent)
        else:
            self.progress_dialog.setRange(0, 0)
        if getattr(self.progress_dialog, "_user_minimized", False):
            # Sent to the background: the window stays away, and this line in
            # the package manager carries the same information instead.
            self._show_task_status(text, percent if determinate else None)
        else:
            self._publish_owner_task_status(
                text,
                percent if determinate else None,
                kind="running",
            )
            self.progress_dialog.bring_to_front()

    def _on_task_backgrounded(self, engine, text):
        self._show_task_status(f"{engine}: {text}", kind="running")
        if getattr(self, "task_show_button", None) is not None:
            self.task_show_button.show()

    def _restore_task_progress(self):
        dialog = self.progress_dialog
        if dialog is None or not self._install_in_progress:
            return
        if getattr(self, "task_show_button", None) is not None:
            self.task_show_button.hide()
        dialog.restore_from_background()

    def _publish_owner_task_status(self, text, percent=None, kind="running"):
        publish = getattr(self.owner, "set_language_package_task_status", None)
        if callable(publish):
            publish(text, percent=percent, kind=kind)

    def _show_task_status(self, text, percent=None, kind="running"):
        """One line at the bottom of the package manager, no window involved."""
        label = getattr(self, "task_status_label", None)
        if label is None:
            return
        # The dialog's message is written over several lines. Windows exposes
        # several unrelated percentages, so its compact line names the current
        # component instead of making that number look like whole-job progress.
        parts = [piece.strip() for piece in str(text or "").splitlines() if piece.strip()]
        if self._active_language_task_title == "Windows OCR" and kind == "running":
            summary = parts[0] if parts else language_manager_text(self.lang, "task_installing_short")
            if percent is not None:
                component = language_manager_text(
                    self.lang, "win_component_short", percent=int(percent)
                )
                summary = f"{summary} · {component}"
        else:
            summary = " · ".join(parts[:2])
            if percent is not None:
                summary = f"{summary} · {int(percent)}%" if summary else f"{int(percent)}%"
        colors = {
            "running": "#c5b3e9" if self._is_dark_theme() else "#5f4a88",
            "done": "#8fd39b" if self._is_dark_theme() else "#2f7d43",
            "failed": "#e0879a" if self._is_dark_theme() else "#b03a52",
        }
        label.setStyleSheet(
            f"color: {colors.get(kind, colors['running'])}; font-size: 12px; font-weight: 600;"
        )
        metrics = QtGui.QFontMetrics(label.font())
        # Before the first show Qt reports the label's tiny sizeHint width. Use
        # the real minimum space it receives in the fixed manager layout, or a
        # useful status can be shortened to "Component …" before it appears.
        label.setText(metrics.elidedText(summary, Qt.ElideRight, max(320, label.width())))
        full_detail = str(text or summary).strip()
        if kind == "running":
            full_detail = f"{full_detail}\n\n{language_manager_text(self.lang, 'task_busy_help')}"
        label.setToolTip(tooltip_text(full_detail))
        label.setVisible(bool(summary))
        self._publish_owner_task_status(summary, percent=percent, kind=kind)

    def _clear_task_status(self):
        label = getattr(self, "task_status_label", None)
        if label is not None:
            label.clear()
            label.hide()
        button = getattr(self, "task_show_button", None)
        if button is not None:
            button.hide()

    def _finish_language_task(self, engine, error="", canceled=False):
        if not error:
            self._last_task_error_details = ""
        QMetaObject.invokeMethod(
            self,
            "_on_language_task_finished",
            Qt.QueuedConnection,
            QtCore.Q_ARG(str, str(engine)),
            QtCore.Q_ARG(str, str(error)),
            QtCore.Q_ARG(bool, bool(canceled)),
        )

    @QtCore.pyqtSlot(str, str, bool)
    def _on_language_task_finished(self, engine, error, canceled=False):
        self._install_in_progress = False
        self._set_package_actions_busy(False)
        self._active_language_task_title = ""
        # Whoever sent the work to the background asked not to be interrupted by
        # it, and that has to hold for the result too — it is reported on the
        # status line instead of in a window.
        backgrounded = bool(getattr(self.progress_dialog, "_user_minimized", False))
        if self.progress_dialog is not None:
            self.progress_dialog.hide()
            self.progress_dialog = None
        if getattr(self, "task_show_button", None) is not None:
            self.task_show_button.hide()
        self._windows_tags_cache = None
        self._windows_capabilities_cache = None
        self._windows_ready_codes_cache = None
        self._easyocr_status_cache = None
        self._rapidocr_status_cache = None
        self.refresh_all()
        self._start_runtime_probe()
        if engine == "Argos":
            self._start_argos_catalog_refresh(False)
        if not self.isVisible() and not backgrounded:
            self.show()
            self.raise_()
            self.activateWindow()
        if canceled:
            self._task_success_message = ""
            self._task_failure_key = "install_failed"
            message = language_manager_text(self.lang, "canceled")
            if backgrounded:
                self._show_task_status(f"{engine}: {message}", kind="running")
                self._publish_owner_task_status(f"{engine}: {message}", kind="idle")
                return
            self._publish_owner_task_status(f"{engine}: {message}", kind="idle")
            QMessageBox.information(self, engine, message)
            return
        if error:
            self._task_success_message = ""
            if backgrounded:
                details = str(self._last_task_error_details or "").strip()
                self._show_task_status(f"{engine}: {error}", kind="failed")
                if details:
                    self.task_status_label.setToolTip(tooltip_text(details))
                self._task_failure_key = "install_failed"
                self._last_task_error_details = ""
                return
            self._publish_owner_task_status(f"{engine}: {error}", kind="failed")
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(engine)
            box.setText(language_manager_text(self.lang, self._task_failure_key) + error)
            # What Windows actually said, behind Details. Without it a failure
            # is a dead end for the user and for anyone reading a bug report.
            details = str(self._last_task_error_details or "").strip()
            if details:
                box.setDetailedText(details)
            box.exec_()
            self._task_failure_key = "install_failed"
            self._last_task_error_details = ""
            return
        message = self._task_success_message or language_manager_text(self.lang, "ready")
        if backgrounded:
            self._show_task_status(f"{engine}: {message}", kind="done")
        else:
            self._publish_owner_task_status(f"{engine}: {message}", 100, kind="done")
            QMessageBox.information(self, engine, message)
        self._task_success_message = ""
        self._task_failure_key = "install_failed"

    def _install_tesseract_worker(self, codes):
        try:
            import ocr
            tess_cmd = self.owner._find_available_tesseract_exe()
            tess_codes = []
            for code in codes:
                tess_code = tesseract_language_code(code)
                if tess_code not in tess_codes:
                    tess_codes.append(tess_code)
            self._emit_language_progress(language_manager_text(self.lang, "tess_down"), 0, False)
            ocr._prepare_tesseract_data(
                tess_cmd,
                "+".join(tess_codes),
                status_callback=lambda text: self._emit_language_progress(text, 0, False),
                cancel_check=lambda: self._cancel_requested.is_set(),
                raise_on_error=True,
            )
            if self._cancel_requested.is_set():
                self._finish_language_task("Tesseract", canceled=True)
                return
            _tess_cmd, data_dirs = self._tesseract_data_dirs()
            missing = [
                f"{code}.traineddata"
                for code in tess_codes
                if not self._tesseract_language_installed(code, data_dirs)
            ]
            if missing:
                raise RuntimeError("Downloaded packages were not found: " + ", ".join(missing))
            self._finish_language_task("Tesseract")
        except Exception as exc:
            if self._cancel_requested.is_set():
                self._finish_language_task("Tesseract", canceled=True)
            else:
                self._finish_language_task("Tesseract", str(exc))

    @staticmethod
    def _powershell_literal(value):
        return "'" + str(value).replace("'", "''") + "'"

    def _windows_ocr_installer_script(
        self,
        codes,
        capabilities,
        repair_codes,
        status_path,
        cancel_path,
        result_path,
        output_dir,
    ):
        """Build an elevated Windows capability installer with observable phases."""
        ps = self._powershell_literal
        entries = ",\n".join(
            "    [pscustomobject]@{ Code = %s; BasicCapability = %s; Capability = %s; ForceRepair = %s }"
            % (
                ps(code),
                ps(f"Language.Basic~~~{windows_ocr_tag(code)}~0.0.1.0"),
                ps(capability),
                "$true" if code in set(repair_codes or []) else "$false",
            )
            for code, capability in zip(codes, capabilities)
        )
        return rf"""$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$StatusPath = {ps(status_path)}
$CancelPath = {ps(cancel_path)}
$ResultPath = {ps(result_path)}
$OutputDir = {ps(output_dir)}
$Packages = @(
{entries}
)
$process = $null
$InitiallyInstalled = @{{}}
$StartedAt = [DateTime]::UtcNow
$Script:DownloadPercent = -1
$Script:QuietSeconds = 0
$Script:RestartRequired = $false
$CbsLogPath = Join-Path $env:windir 'Logs\CBS\CBS.log'

function Read-CbsDownloadProgress {{
    # CBS writes "DownloadProgress: [ 49 / 100 ]" every couple of seconds while
    # Windows Update pulls the payload. That is the one signal that says the
    # install is alive when dism.exe has been showing the same number for
    # minutes. Reading it needs administrator rights, which this script has.
    param([long]$LastLength)
    $result = [pscustomobject]@{{ Length = $LastLength; Percent = $Script:DownloadPercent }}
    try {{
        $info = Get-Item -LiteralPath $CbsLogPath -Force -ErrorAction Stop
    }} catch {{
        return $result
    }}
    $result.Length = $info.Length
    if ($info.Length -le $LastLength) {{ return $result }}
    try {{
        $stream = [System.IO.File]::Open(
            $CbsLogPath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
    }} catch {{
        return $result
    }}
    try {{
        $window = [Math]::Min(65536, $info.Length)
        $null = $stream.Seek(-$window, [System.IO.SeekOrigin]::End)
        $buffer = New-Object byte[] $window
        $read = $stream.Read($buffer, 0, $window)
        $tail = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $read)
    }} finally {{
        $stream.Dispose()
    }}
    $matches = [regex]::Matches($tail, 'DownloadProgress:\s*\[\s*(\d+)\s*/\s*100\s*\]')
    if ($matches.Count -gt 0) {{
        $result.Percent = [int]$matches[$matches.Count - 1].Groups[1].Value
    }}
    return $result
}}

function Write-OcrStatus([string]$Phase, [int]$Percent, [int]$Current, [int]$Total, [string]$Code, [string]$Message) {{
    $payload = @{{
        phase = $Phase
        percent = [Math]::Max(0, [Math]::Min(100, $Percent))
        current = $Current
        total = $Total
        code = $Code
        message = $Message
        elapsed = [int]([DateTime]::UtcNow - $StartedAt).TotalSeconds
        # What Windows is doing underneath dism.exe. Its console percentage can
        # sit on one number for many minutes while the payload downloads, so
        # these say whether anything is still moving.
        download = $Script:DownloadPercent
        quiet = $Script:QuietSeconds
        restart = $Script:RestartRequired
    }} | ConvertTo-Json -Compress
    $statusTemp = "$StatusPath.$PID.$([Guid]::NewGuid().ToString('N')).tmp"
    try {{
        [System.IO.File]::WriteAllText(
            $statusTemp,
            [string]$payload,
            [System.Text.UTF8Encoding]::new($false)
        )
        $moved = $false
        for ($attempt = 0; $attempt -lt 10; $attempt++) {{
            try {{
                Move-Item -LiteralPath $statusTemp -Destination $StatusPath -Force -ErrorAction Stop
                $moved = $true
                break
            }} catch {{
                Start-Sleep -Milliseconds 30
            }}
        }}
        if (-not $moved) {{ throw 'Could not publish Windows OCR status.' }}
    }} finally {{
        if (Test-Path -LiteralPath $statusTemp) {{
            Remove-Item -LiteralPath $statusTemp -Force -ErrorAction SilentlyContinue
        }}
    }}
}}

function Test-OcrCancel {{
    return (Test-Path -LiteralPath $CancelPath)
}}

function Install-OcrCapability {{
    param(
        [string]$Name,
        [string]$Phase,
        [int]$Index,
        [int]$Current,
        [int]$Total,
        [string]$Code,
        [int]$Slot,
        [int]$SlotCount,
        [int]$StepIndex
    )
    # Add-WindowsCapability is a blocking call that reports no progress at all.
    # A Feature on Demand that still has to be downloaded from Windows Update
    # can take eight minutes or more, so driving dism.exe directly and reading
    # its percentage is the only way to show the user real progress and to keep
    # Cancel responsive while the work runs.
    $stdoutPath = Join-Path $OutputDir ("add_" + $StepIndex + ".out")
    $stderrPath = Join-Path $OutputDir ("add_" + $StepIndex + ".err")
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    $arguments = @('/Online', '/Add-Capability', ("/CapabilityName:" + $Name), '/NoRestart', '/English')
    $proc = Start-Process -FilePath dism.exe -ArgumentList $arguments -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $lastComponentPercent = -1
    # DownloadProgress values belong to the component currently being added.
    # Do not carry 100% (or another stale value) over from the previous FOD.
    $Script:DownloadPercent = -1
    $cbsLength = 0
    try {{ $cbsLength = (Get-Item -LiteralPath $CbsLogPath -Force).Length }} catch {{}}
    $tick = 0
    $lastMovement = [DateTime]::UtcNow
    while (-not $proc.HasExited) {{
        $rawPercent = 0
        if (Test-Path -LiteralPath $stdoutPath) {{
            $content = Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue
            if ($null -ne $content) {{
                $found = [regex]::Matches([string]$content, '(\d+)(?:[\.,]\d+)?%')
                if ($found.Count -gt 0) {{ $rawPercent = [int]$found[$found.Count - 1].Groups[1].Value }}
            }}
        }}
        # Windows can sit on one percentage for many minutes while the payload
        # comes down. Whether CBS.log is still growing is the difference between
        # "slow" and "wedged", and it is what the dialog reports to the user.
        # Read it every ~2 s, not every tick: the loop spins four times a second
        # to keep Cancel responsive, and that log runs to tens of megabytes.
        $tick = $tick + 1
        if (($tick % 8) -eq 1) {{
            $previousDownload = $Script:DownloadPercent
            $cbs = Read-CbsDownloadProgress -LastLength $cbsLength
            # CBS repeats the exact same DownloadProgress line every two
            # seconds even when Windows Update is stuck. Log growth proves the
            # service is alive, not that the download moved; only changed
            # percentages reset the no-progress timer.
            $moved = ($rawPercent -ne $lastComponentPercent) -or ($cbs.Percent -ne $previousDownload)
            $cbsLength = $cbs.Length
            $Script:DownloadPercent = $cbs.Percent
            if ($moved) {{ $lastMovement = [DateTime]::UtcNow }}
            $Script:QuietSeconds = [int]([DateTime]::UtcNow - $lastMovement).TotalSeconds
        }} elseif ($rawPercent -ne $lastComponentPercent) {{
            $lastMovement = [DateTime]::UtcNow
            $Script:QuietSeconds = 0
        }}

        if (Test-OcrCancel) {{
            Write-OcrStatus 'cancel_pending' $rawPercent $Current $Total $Code ''
        }} else {{
            # Re-published every tick even when nothing changed, so the elapsed
            # clock keeps ticking and the install still looks alive.
            Write-OcrStatus $Phase $rawPercent $Current $Total $Code ''
            $lastComponentPercent = $rawPercent
        }}
        Start-Sleep -Milliseconds 250
        $proc.Refresh()
    }}
    $proc.WaitForExit()
    $proc.Refresh()
    $exitCode = [int]$proc.ExitCode
    # 0 = done, 3010 = done but Windows wants a restart.  Anything else is only
    # a real failure when the capability did not actually reach Installed.
    if ($exitCode -eq 3010) {{ $Script:RestartRequired = $true }}
    if ($exitCode -ne 0 -and $exitCode -ne 3010) {{
        $state = (Get-WindowsCapability -Online -Name $Name).State
        if ($state -eq 'Installed') {{ return }}
        $details = ''
        if (Test-Path -LiteralPath $stderrPath) {{ $details = Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue }}
        if (-not $details -and (Test-Path -LiteralPath $stdoutPath)) {{ $details = Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue }}
        throw ("DISM exited with code " + $exitCode + " for " + $Name + ". " + $details)
    }}
}}

try {{
    $total = [Math]::Max(1, $Packages.Count)
    Write-OcrStatus 'starting' 0 0 $total '' ''
    for ($index = 0; $index -lt $Packages.Count; $index++) {{
        $entry = $Packages[$index]
        $current = $index + 1
        if (Test-OcrCancel) {{ throw [System.OperationCanceledException]::new('Canceled') }}

        Write-OcrStatus 'checking' 0 $current $total $entry.Code ''
        $capability = Get-WindowsCapability -Online -Name $entry.Capability
        $InitiallyInstalled[$entry.Capability] = ($capability.State -eq 'Installed')
        if ($entry.ForceRepair -and $capability.State -eq 'Installed') {{
            Write-OcrStatus 'removing' 0 $current $total $entry.Code ''
            $repairOut = Join-Path $OutputDir ("repair_remove_" + $index + ".out")
            $repairErr = Join-Path $OutputDir ("repair_remove_" + $index + ".err")
            $repairArgs = @('/Online', '/Remove-Capability', ("/CapabilityName:" + $entry.Capability), '/NoRestart', '/English')
            $process = Start-Process -FilePath dism.exe -ArgumentList $repairArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $repairOut -RedirectStandardError $repairErr
            while (-not $process.HasExited) {{
                if (Test-OcrCancel) {{
                    Write-OcrStatus 'cancel_pending' 0 $current $total $entry.Code ''
                }}
                Start-Sleep -Milliseconds 250
                $process.Refresh()
            }}
            $process.WaitForExit()
            $process.Refresh()
            $exitCode = [int]$process.ExitCode
            if ($exitCode -ne 0) {{
                $details = ''
                if (Test-Path -LiteralPath $repairErr) {{ $details = Get-Content -LiteralPath $repairErr -Raw -ErrorAction SilentlyContinue }}
                if (-not $details -and (Test-Path -LiteralPath $repairOut)) {{ $details = Get-Content -LiteralPath $repairOut -Raw -ErrorAction SilentlyContinue }}
                throw ("DISM repair removal exited with code " + $exitCode + ". " + $details)
            }}
            if (Test-OcrCancel) {{ throw [System.OperationCanceledException]::new('Canceled') }}
            $capability = Get-WindowsCapability -Online -Name $entry.Capability
        }}
        $basic = Get-WindowsCapability -Online -Name $entry.BasicCapability -ErrorAction SilentlyContinue
        if ($null -eq $basic) {{
            throw ("Windows does not offer the required capability " + $entry.BasicCapability)
        }}
        $InitiallyInstalled[$entry.BasicCapability] = ($basic.State -eq 'Installed')
        if ($basic.State -ne 'Installed') {{
            Write-OcrStatus 'installing_basic' 0 $current $total $entry.Code ''
            Install-OcrCapability -Name $entry.BasicCapability -Phase 'installing_basic' -Index $index -Current $current -Total $total -Code $entry.Code -Slot 0 -SlotCount 2 -StepIndex ($index * 2)
            if (Test-OcrCancel) {{ throw [System.OperationCanceledException]::new('Canceled') }}
            $basic = Get-WindowsCapability -Online -Name $entry.BasicCapability
            if ($basic.State -ne 'Installed') {{
                throw ("Windows did not install " + $entry.BasicCapability + ". State: " + $basic.State)
            }}
        }}

        if ($capability.State -ne 'Installed') {{
            Write-OcrStatus 'installing' 0 $current $total $entry.Code ''
            Install-OcrCapability -Name $entry.Capability -Phase 'installing' -Index $index -Current $current -Total $total -Code $entry.Code -Slot 1 -SlotCount 2 -StepIndex (($index * 2) + 1)
            if (Test-OcrCancel) {{ throw [System.OperationCanceledException]::new('Canceled') }}
        }}

        Write-OcrStatus 'verifying' 100 $current $total $entry.Code ''
        $capability = Get-WindowsCapability -Online -Name $entry.Capability
        if ($capability.State -ne 'Installed') {{
            throw ("Windows did not install " + $entry.Capability + ". State: " + $capability.State)
        }}
    }}
    # A restart-pending install is finished as far as Windows is concerned,
    # but the OCR engine will not see the language until the machine reboots,
    # so the app has to say so rather than claim it is ready.
    $resultText = if ($Script:RestartRequired) {{ 'OK_RESTART' }} else {{ 'OK' }}
    Set-Content -LiteralPath $ResultPath -Value $resultText -Encoding UTF8 -Force
    Write-OcrStatus 'done' 100 $total $total '' ''
    exit 0
}} catch [System.OperationCanceledException] {{
    Write-OcrStatus 'rolling_back' 0 0 $Packages.Count '' ''
    foreach ($entry in $Packages) {{
        foreach ($capabilityName in @($entry.Capability, $entry.BasicCapability)) {{
            if (-not $InitiallyInstalled.ContainsKey($capabilityName)) {{ continue }}
            $wasInstalled = [bool]$InitiallyInstalled[$capabilityName]
            $currentCapability = Get-WindowsCapability -Online -Name $capabilityName -ErrorAction SilentlyContinue
            if ($null -eq $currentCapability) {{ continue }}
            if ($wasInstalled -and $currentCapability.State -ne 'Installed') {{
                $null = Add-WindowsCapability -Online -Name $capabilityName -ErrorAction SilentlyContinue
            }} elseif (-not $wasInstalled -and $currentCapability.State -eq 'Installed') {{
                $null = Remove-WindowsCapability -Online -Name $capabilityName -ErrorAction SilentlyContinue
            }}
        }}
    }}
    Set-Content -LiteralPath $ResultPath -Value 'CANCELED' -Encoding UTF8 -Force
    Write-OcrStatus 'canceled' 0 0 $Packages.Count '' 'Canceled'
    exit 2
}} catch {{
    $details = ($_ | Out-String).Trim()
    Set-Content -LiteralPath $ResultPath -Value ("ERROR`n" + $details) -Encoding UTF8 -Force
    Write-OcrStatus 'error' 0 0 $Packages.Count '' $details
    exit 1
}}
"""

    def _windows_ocr_remover_script(
        self,
        codes,
        capabilities,
        status_path,
        cancel_path,
        result_path,
        output_dir,
    ):
        """Build an elevated, observable Windows OCR capability remover."""
        ps = self._powershell_literal
        entries = ",\n".join(
            "    [pscustomobject]@{ Code = %s; Capability = %s }"
            % (ps(code), ps(capability))
            for code, capability in zip(codes, capabilities)
        )
        return rf"""$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$StatusPath = {ps(status_path)}
$CancelPath = {ps(cancel_path)}
$ResultPath = {ps(result_path)}
$OutputDir = {ps(output_dir)}
$Packages = @(
{entries}
)
$process = $null
$StartedAt = [DateTime]::UtcNow

function Write-OcrStatus([string]$Phase, [int]$Percent, [int]$Current, [int]$Total, [string]$Code, [string]$Message) {{
    $payload = @{{
        phase = $Phase
        percent = [Math]::Max(0, [Math]::Min(100, $Percent))
        current = $Current
        total = $Total
        code = $Code
        message = $Message
        elapsed = [int]([DateTime]::UtcNow - $StartedAt).TotalSeconds
    }} | ConvertTo-Json -Compress
    $statusTemp = "$StatusPath.$PID.$([Guid]::NewGuid().ToString('N')).tmp"
    try {{
        [System.IO.File]::WriteAllText(
            $statusTemp,
            [string]$payload,
            [System.Text.UTF8Encoding]::new($false)
        )
        $moved = $false
        for ($attempt = 0; $attempt -lt 10; $attempt++) {{
            try {{
                Move-Item -LiteralPath $statusTemp -Destination $StatusPath -Force -ErrorAction Stop
                $moved = $true
                break
            }} catch {{
                Start-Sleep -Milliseconds 30
            }}
        }}
        if (-not $moved) {{ throw 'Could not publish Windows OCR status.' }}
    }} finally {{
        if (Test-Path -LiteralPath $statusTemp) {{
            Remove-Item -LiteralPath $statusTemp -Force -ErrorAction SilentlyContinue
        }}
    }}
}}

function Test-OcrCancel {{ return (Test-Path -LiteralPath $CancelPath) }}

try {{
    $total = [Math]::Max(1, $Packages.Count)
    for ($index = 0; $index -lt $Packages.Count; $index++) {{
        $entry = $Packages[$index]
        $current = $index + 1
        if (Test-OcrCancel) {{ throw [System.OperationCanceledException]::new('Canceled') }}
        Write-OcrStatus 'checking' ([int](100 * $index / $total)) $current $total $entry.Code ''
        $capability = Get-WindowsCapability -Online -Name $entry.Capability
        if ($capability.State -eq 'Installed') {{
            $stdoutPath = Join-Path $OutputDir ("remove_" + $index + ".out")
            $stderrPath = Join-Path $OutputDir ("remove_" + $index + ".err")
            $arguments = @('/Online', '/Remove-Capability', ("/CapabilityName:" + $entry.Capability), '/NoRestart', '/English')
            $process = Start-Process -FilePath dism.exe -ArgumentList $arguments -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
            while (-not $process.HasExited) {{
                $rawPercent = 0
                if (Test-Path -LiteralPath $stdoutPath) {{
                    $content = Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue
                    if ($null -ne $content) {{
                        $matches = [regex]::Matches([string]$content, '(\d+)(?:[\.,]\d+)?%')
                        if ($matches.Count -gt 0) {{ $rawPercent = [int]$matches[$matches.Count - 1].Groups[1].Value }}
                    }}
                }}
                if (Test-OcrCancel) {{
                    Write-OcrStatus 'cancel_pending' $rawPercent $current $total $entry.Code ''
                }} else {{
                    Write-OcrStatus 'removing' $rawPercent $current $total $entry.Code ''
                }}
                Start-Sleep -Milliseconds 250
                $process.Refresh()
            }}
            $process.WaitForExit()
            $process.Refresh()
            $exitCode = [int]$process.ExitCode
            if ($exitCode -ne 0) {{
                # Some Windows builds return a stale/non-zero transport code
                # even though DISM has already removed the capability.  The
                # capability state is authoritative; only fail if it remains.
                $afterRemoval = Get-WindowsCapability -Online -Name $entry.Capability
                if ($afterRemoval.State -ne 'Installed') {{
                    continue
                }}
                $details = ''
                if (Test-Path -LiteralPath $stderrPath) {{ $details = Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue }}
                if (-not $details -and (Test-Path -LiteralPath $stdoutPath)) {{ $details = Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue }}
                throw ("DISM exited with code " + $exitCode + ". " + $details)
            }}
            if (Test-OcrCancel) {{ throw [System.OperationCanceledException]::new('Canceled') }}
        }}
        Write-OcrStatus 'verifying' ([int](100 * $current / $total)) $current $total $entry.Code ''
        $capability = Get-WindowsCapability -Online -Name $entry.Capability
        if ($capability.State -eq 'Installed') {{
            throw ("Windows did not remove " + $entry.Capability)
        }}
    }}
    Set-Content -LiteralPath $ResultPath -Value 'OK' -Encoding UTF8 -Force
    Write-OcrStatus 'done' 100 $total $total '' ''
    exit 0
}} catch [System.OperationCanceledException] {{
    Set-Content -LiteralPath $ResultPath -Value 'CANCELED' -Encoding UTF8 -Force
    Write-OcrStatus 'canceled' 0 0 $Packages.Count '' 'Canceled'
    exit 2
}} catch {{
    $details = ($_ | Out-String).Trim()
    Set-Content -LiteralPath $ResultPath -Value ("ERROR`n" + $details) -Encoding UTF8 -Force
    Write-OcrStatus 'error' 0 0 $Packages.Count '' $details
    exit 1
}}
"""

    @staticmethod
    def _read_windows_ocr_status(status_path):
        try:
            payload = Path(status_path).read_text(encoding="utf-8-sig").strip()
            value = json.loads(payload)
            if not isinstance(value, dict):
                return None
            value["percent"] = max(0, min(100, int(value.get("percent", 0))))
            return value
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    # Windows Update routinely holds one percentage for minutes at a time, so a
    # pause only becomes worth mentioning well past that.
    WINDOWS_OCR_QUIET_WARNING_SECONDS = 300

    def _windows_ocr_detail_lines(self, status, elapsed_text):
        """The second and third lines of the installer message.

        dism.exe's own number stops moving long before anything is wrong. The
        status heartbeat says whether the elevated installer and Windows
        servicing are still responding. Only the current component's DISM
        percentage is shown in the bar; there is no invented whole-job ETA.
        """
        quiet = max(0, int(status.get("quiet", 0) or 0))
        pieces = [elapsed_text]
        download_value = status.get("download", -1)
        download = -1 if download_value is None else int(download_value)
        if 0 <= download <= 100:
            pieces.append(
                language_manager_text(self.lang, "win_download_stage", percent=download)
            )
        if quiet < self.WINDOWS_OCR_QUIET_WARNING_SECONDS:
            pieces.append(language_manager_text(self.lang, "win_activity_recent"))
        lines = [" · ".join(pieces)]
        if quiet >= self.WINDOWS_OCR_QUIET_WARNING_SECONDS:
            lines.append(
                language_manager_text(self.lang, "win_quiet", minutes=quiet // 60)
            )
        return lines

    def _windows_ocr_stage_line(self, phase, current, total):
        stages = {
            "checking": 1,
            "installing_basic": 2,
            "installing": 3,
            "verifying": 4,
        }
        stage = stages.get(str(phase))
        if stage is None:
            return ""
        return language_manager_text(
            self.lang,
            "win_stage",
            stage=stage,
            current=max(1, int(current or 1)),
            total=max(1, int(total or 1)),
        )

    def _emit_windows_ocr_status(self, status):
        phase = str(status.get("phase", ""))
        percent = int(status.get("percent", 0))
        code = str(status.get("code", ""))
        current = int(status.get("current", 0) or 0)
        total = int(status.get("total", 0) or 0)
        elapsed = max(0, int(status.get("elapsed", 0) or 0))
        elapsed_text = f"{elapsed // 60:02d}:{elapsed % 60:02d}"
        language = self._language_display_name(code) if code else code.upper()
        stage_line = self._windows_ocr_stage_line(phase, current, total)
        if phase in {"installing", "installing_basic"}:
            text = language_manager_text(
                self.lang,
                "win_installing_basic" if phase == "installing_basic" else "win_installing",
                language=language,
                current=current,
                total=total,
            )
            # The percentage now comes straight from dism.exe, so it is safe to
            # drive a real progress bar instead of an endless marquee.
            self._emit_language_progress(
                "\n".join(
                    [stage_line, text]
                    + self._windows_ocr_detail_lines(status, elapsed_text)
                    + [language_manager_text(self.lang, "win_time_unknown")]
                ),
                percent,
                True,
            )
        elif phase == "checking":
            text = language_manager_text(self.lang, "win_checking", language=language)
            self._emit_language_progress(
                f"{stage_line}\n{text}\n{elapsed_text}", percent, False
            )
        elif phase == "cancel_pending":
            self._emit_language_progress(
                f"{language_manager_text(self.lang, 'win_cancel_pending')}\n{elapsed_text}",
                percent,
                False,
            )
        elif phase == "verifying":
            text = language_manager_text(self.lang, "win_verifying", language=language)
            self._emit_language_progress(
                f"{stage_line}\n{text}\n{elapsed_text}", percent, False
            )
        elif phase == "removing":
            text = language_manager_text(
                self.lang,
                "win_removing",
                language=language,
                current=current,
                total=total,
            )
            # Also a real dism.exe percentage.
            self._emit_language_progress(f"{text}\n{elapsed_text}", percent, True)
        elif phase == "rolling_back":
            self._emit_language_progress(
                f"{language_manager_text(self.lang, 'win_rolling_back')}\n{elapsed_text}",
                percent,
                False,
            )
        elif phase == "canceled":
            self._emit_language_progress(language_manager_text(self.lang, "canceled"), 0, False)
        elif phase == "done":
            self._emit_language_progress(language_manager_text(self.lang, "win_done"), 100, True)

    @staticmethod
    def _windows_reboot_pending():
        """Whether Windows itself says a restart is owed.

        Telling someone to reboot when Windows is not asking for one sends them
        away for five minutes to fix nothing. These are the keys the servicing
        stack sets, read directly rather than through another DISM session.
        """
        if sys.platform != "win32":
            return False
        try:
            import winreg
        except ImportError:
            return False
        keys = (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\PackagesPending",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
        )
        for path in keys:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path):
                    return True
            except OSError:
                continue
        return False

    def _friendly_windows_ocr_error(self, error):
        raw = str(error or "").strip()
        logger.error("Windows OCR servicing failed: %s", raw)
        self._last_task_error_details = raw
        lowered = raw.lower()
        if "0x800f0954" in lowered:
            return language_manager_text(self.lang, "win_error_policy")
        if any(code in lowered for code in ("0x800f081f", "0x800f0906", "0x802440", "incompleteread")):
            return language_manager_text(self.lang, "win_error_source")
        # A broken script is a bug here, not a Windows state. It used to be
        # reported as a busy servicing stack, because the parser error quoted the
        # line containing "OK_RESTART" and a bare "restart" match was enough.
        if any(marker in lowered for marker in (
            "parsererror", "missingstatementblock", "is not recognized as the name",
            "unexpected token", "commandnotfoundexception",
        )):
            return language_manager_text(self.lang, "win_error_generic")
        # Ask Windows whether a reboot is owed instead of reading tea leaves in
        # the message — and match whole words, so "OK_RESTART" is not a verdict.
        servicing_codes = ("0x800f0922", "0x800f0831", "0x800f0988", "0x800f0902", "already running")
        asks_for_reboot = re.search(r"\b(restart|reboot)\b", lowered) is not None
        if any(code in lowered for code in servicing_codes) or asks_for_reboot:
            if self._windows_reboot_pending():
                return language_manager_text(self.lang, "win_error_restart")
            return language_manager_text(self.lang, "win_error_busy")
        return language_manager_text(self.lang, "win_error_generic")

    def _install_windows_ocr_worker(self, codes):
        work_dir = ""
        try:
            capabilities = []
            unique_codes = []
            repair_codes = []
            available_tags = self._available_windows_tags()
            available_by_tag = {
                str(tag).lower(): str(tag)
                for tag in available_tags
                if str(tag).strip()
            }
            capability_catalog = self._windows_ocr_capability_catalog()
            for code in codes:
                capability = self._windows_ocr_capability_name(code)
                if capability not in capabilities:
                    capabilities.append(capability)
                    unique_codes.append(code)
                    expected = windows_ocr_tag(code)
                    try:
                        import ocr
                        actual_tag = ocr._match_available_windows_ocr_tag(
                            expected,
                            available_by_tag,
                        )
                        api_installed = bool(actual_tag)
                        engine_ready = bool(
                            actual_tag
                            and ocr._get_windows_ocr_engine(actual_tag) is not None
                        )
                    except Exception:
                        api_installed = expected.lower() in available_by_tag
                        engine_ready = api_installed
                    capability_installed = (
                        capability_catalog.get(expected.lower(), "").lower() == "installed"
                    )
                    if (
                        api_installed != capability_installed
                        or (capability_installed and not engine_ready)
                    ):
                        repair_codes.append(code)
            self._emit_language_progress(
                language_manager_text(self.lang, "win_wait"),
                0,
                False,
            )
            work_dir = tempfile.mkdtemp(prefix="clickntranslate_windows_ocr_")
            script_path = os.path.join(work_dir, "install.ps1")
            status_path = os.path.join(work_dir, "status.json")
            cancel_path = os.path.join(work_dir, "cancel.request")
            result_path = os.path.join(work_dir, "result.txt")
            Path(script_path).write_text(
                self._windows_ocr_installer_script(
                    unique_codes,
                    capabilities,
                    repair_codes,
                    status_path,
                    cancel_path,
                    result_path,
                    work_dir,
                ),
                encoding="utf-8-sig",
            )
            self._windows_ocr_cancel_marker = cancel_path

            completed_box = {}
            process_finished = threading.Event()

            def run_installer():
                try:
                    # Keep every query made by this process away from the
                    # online image until the elevated servicing session exits.
                    # Locking only the catalog queries was not enough: opening
                    # the package window again could start a second DISM
                    # session while Add-Capability was still running.
                    with _WINDOWS_SERVICING_LOCK:
                        completed_box["completed"] = self._run_powershell_script(
                            script_path,
                            elevated=True,
                        )
                except Exception as exc:
                    completed_box["error"] = exc
                finally:
                    process_finished.set()

            threading.Thread(target=run_installer, daemon=True).start()
            last_status = None
            started_at = time.monotonic()
            last_elapsed = -1
            while not process_finished.wait(0.15):
                if self._cancel_requested.is_set():
                    try:
                        Path(cancel_path).touch(exist_ok=True)
                    except OSError:
                        pass
                status = self._read_windows_ocr_status(status_path)
                if status is not None:
                    elapsed = int(time.monotonic() - started_at)
                    status["elapsed"] = max(elapsed, int(status.get("elapsed", 0) or 0))
                    if status != last_status or elapsed != last_elapsed:
                        last_status = dict(status)
                        last_elapsed = elapsed
                        self._emit_windows_ocr_status(status)

            status = self._read_windows_ocr_status(status_path)
            if status is not None and status != last_status:
                self._emit_windows_ocr_status(status)
            if "error" in completed_box:
                raise completed_box["error"]
            completed = completed_box.get("completed")
            if completed is None:
                raise RuntimeError("Windows OCR installer did not return a result")

            result = ""
            try:
                result = Path(result_path).read_text(encoding="utf-8-sig").strip()
            except OSError:
                pass
            if self._cancel_requested.is_set() or result == "CANCELED" or completed.returncode == 2:
                self._finish_language_task("Windows OCR", canceled=True)
                return
            if completed.returncode != 0:
                output = (completed.stdout or "").strip()
                details = result[6:].strip() if result.startswith("ERROR") else result
                raise RuntimeError(details or output or f"PowerShell exited with code {completed.returncode}")
            self._emit_language_progress(
                language_manager_text(self.lang, "win_registering"),
                100,
                False,
            )
            # Each probe spawns PowerShell and costs 1-3 s, so poll gently; the
            # state is normally already correct on the very first round.
            missing = self._wait_for_windows_ocr_capabilities(
                capabilities, delay=2.0, timeout=120.0
            )
            if self._cancel_requested.is_set():
                self._finish_language_task("Windows OCR", canceled=True)
                return
            if missing:
                raise RuntimeError(
                    "Windows reported that these OCR capabilities are still not installed: "
                    + ", ".join(missing)
                )
            # Windows says the capability is installed.  The recognizer usually
            # becomes usable within seconds, but never treat a lagging WinRT
            # refresh as a failed install - the package is on disk either way.
            pending = self._wait_for_windows_ocr_engines(unique_codes)
            if self._cancel_requested.is_set():
                self._finish_language_task("Windows OCR", canceled=True)
                return
            if result == "OK_RESTART" and not pending:
                # DISM answered 3010: the package is in place, but Windows wants
                # a reboot before it counts as serviced. Saying "ready" here
                # would be a promise the OCR engine may not keep until then.
                pending = list(unique_codes)
            if pending:
                logger.warning(
                    "Windows OCR capabilities installed but not yet exposed by WinRT: %s",
                    ", ".join(pending),
                )
                self._emit_language_progress(language_manager_text(self.lang, "win_done"), 100, True)
                self._task_success_message = language_manager_text(
                    self.lang,
                    "win_installed_pending_restart",
                    languages=", ".join(
                        self._language_display_name(code) for code in pending
                    ),
                )
                self._finish_language_task("Windows OCR")
                return
            self._emit_language_progress(language_manager_text(self.lang, "win_done"), 100, True)
            self._finish_language_task("Windows OCR")
        except Exception as exc:
            if self._cancel_requested.is_set():
                self._finish_language_task("Windows OCR", canceled=True)
            else:
                self._finish_language_task(
                    "Windows OCR",
                    self._friendly_windows_ocr_error(exc),
                )
        finally:
            self._windows_ocr_cancel_marker = ""
            if work_dir:
                shutil.rmtree(work_dir, ignore_errors=True)

    def _remove_windows_ocr_worker(self, codes):
        work_dir = ""
        try:
            unique_codes = []
            capabilities = []
            for code in codes:
                capability = self._windows_ocr_capability_name(code)
                if capability not in capabilities:
                    unique_codes.append(code)
                    capabilities.append(capability)
            work_dir = tempfile.mkdtemp(prefix="clickntranslate_windows_ocr_remove_")
            script_path = os.path.join(work_dir, "remove.ps1")
            status_path = os.path.join(work_dir, "status.json")
            cancel_path = os.path.join(work_dir, "cancel.request")
            result_path = os.path.join(work_dir, "result.txt")
            Path(script_path).write_text(
                self._windows_ocr_remover_script(
                    unique_codes,
                    capabilities,
                    status_path,
                    cancel_path,
                    result_path,
                    work_dir,
                ),
                encoding="utf-8-sig",
            )
            self._windows_ocr_cancel_marker = cancel_path
            completed_box = {}
            process_finished = threading.Event()

            def run_remover():
                try:
                    with _WINDOWS_SERVICING_LOCK:
                        completed_box["completed"] = self._run_powershell_script(
                            script_path,
                            elevated=True,
                        )
                except Exception as exc:
                    completed_box["error"] = exc
                finally:
                    process_finished.set()

            threading.Thread(target=run_remover, daemon=True).start()
            last_status = None
            while not process_finished.wait(0.15):
                if self._cancel_requested.is_set():
                    try:
                        Path(cancel_path).touch(exist_ok=True)
                    except OSError:
                        pass
                status = self._read_windows_ocr_status(status_path)
                if status is not None and status != last_status:
                    last_status = status
                    self._emit_windows_ocr_status(status)
            status = self._read_windows_ocr_status(status_path)
            if status is not None and status != last_status:
                self._emit_windows_ocr_status(status)
            if "error" in completed_box:
                raise completed_box["error"]
            completed = completed_box.get("completed")
            if completed is None:
                raise RuntimeError("Windows OCR remover did not return a result")
            try:
                result = Path(result_path).read_text(encoding="utf-8-sig").strip()
            except OSError:
                result = ""
            if self._cancel_requested.is_set() or result == "CANCELED" or completed.returncode == 2:
                self._finish_language_task("Windows OCR", canceled=True)
                return
            transport_error = ""
            if completed.returncode != 0:
                details = result[6:].strip() if result.startswith("ERROR") else result
                transport_error = (
                    details
                    or (completed.stdout or "").strip()
                    or f"PowerShell exited with code {completed.returncode}"
                )
            # The actual Windows capability state is authoritative.  This also
            # handles older DISM builds that report a non-zero/stale exit code
            # after printing "The operation completed successfully".
            remaining = self._wait_for_windows_ocr_removal(capabilities)
            if remaining:
                if transport_error:
                    raise RuntimeError(transport_error)
                raise RuntimeError(
                    "Windows reported that these OCR capabilities are still installed: "
                    + ", ".join(remaining)
                )
            try:
                import ocr
                ocr._UNIVERSAL_OCR_ENGINE = None
                ocr._OCR_ENGINE_CACHE.clear()
            except Exception:
                pass
            self._finish_language_task("Windows OCR")
        except Exception as exc:
            if self._cancel_requested.is_set():
                self._finish_language_task("Windows OCR", canceled=True)
            else:
                self._finish_language_task(
                    "Windows OCR",
                    self._friendly_windows_ocr_error(exc),
                )
        finally:
            self._windows_ocr_cancel_marker = ""
            if work_dir:
                shutil.rmtree(work_dir, ignore_errors=True)

    def _remove_tesseract_worker(self, codes):
        try:
            _tess_cmd, data_dirs = self._tesseract_data_dirs()
            if not data_dirs:
                raise RuntimeError("Tesseract tessdata folder was not found")
            total = max(1, len(codes))
            for index, code in enumerate(codes, 1):
                if self._cancel_requested.is_set():
                    self._finish_language_task("Tesseract", canceled=True)
                    return
                tess_code = tesseract_language_code(code)
                filename = f"{tess_code}.traineddata"
                self._emit_language_progress(f"Tesseract: {filename}", int(index * 100 / total), True)
                for data_dir in data_dirs:
                    data_root = Path(data_dir).resolve()
                    target = (data_root / filename).resolve()
                    if target.parent != data_root:
                        raise RuntimeError(f"Unsafe Tesseract package path: {target}")
                    if target.is_file():
                        target.unlink()
                if self._tesseract_language_installed(tess_code, data_dirs):
                    raise RuntimeError(f"Could not remove {filename}")
            self._finish_language_task("Tesseract")
        except Exception as exc:
            self._finish_language_task("Tesseract", str(exc))

    def _remove_easyocr_worker(self, codes):
        try:
            groups = []
            for code in codes:
                for group in self._easyocr_model_groups_for_language(code):
                    if group and group not in groups:
                        groups.append(group)
            model_root = Path(self._easyocr_model_dir()).resolve()
            total = max(1, len(groups))
            for index, group in enumerate(groups, 1):
                if self._cancel_requested.is_set():
                    self._finish_language_task(EASYOCR_ENGINE_DISPLAY, canceled=True)
                    return
                self._emit_language_progress(
                    f"{EASYOCR_ENGINE_DISPLAY}: {group}",
                    int(index * 100 / total),
                    True,
                )
                for filename in EASYOCR_MODEL_FILE_VARIANTS.get(group, (f"{group}.pth",)):
                    target = (model_root / filename).resolve()
                    if target.parent != model_root:
                        raise RuntimeError(f"Unsafe EasyOCR model path: {target}")
                    if target.is_file():
                        target.unlink()
            reset = getattr(self.owner, "_reset_easyocr_runtime_cache", None)
            if callable(reset):
                reset(clear_modules=True)
            self._finish_language_task(EASYOCR_ENGINE_DISPLAY)
        except Exception as exc:
            self._finish_language_task(EASYOCR_ENGINE_DISPLAY, str(exc))

    def _install_easyocr_worker(self, codes):
        try:
            import ocr
            total = max(1, len(codes))
            for index, code in enumerate(codes, 1):
                if self._cancel_requested.is_set():
                    self._finish_language_task("EasyOCR", canceled=True)
                    return
                language = next((item for item in APP_LANGUAGES if item.code == code), None)
                language_name = language.display_name(self.lang) if language else code.upper()
                self._emit_language_progress(
                    language_manager_text(self.lang, "easy_down", language=language_name),
                    int((index - 1) * 100 / total),
                    True,
                )
                if not ocr.easyocr_available(code, download_enabled=True):
                    raise RuntimeError(f"EasyOCR could not prepare models for {language_name}")
            self._emit_language_progress(language_manager_text(self.lang, "easy_done"), 100, True)
            self._finish_language_task("EasyOCR")
        except Exception as exc:
            if self._cancel_requested.is_set():
                self._finish_language_task("EasyOCR", canceled=True)
            else:
                self._finish_language_task("EasyOCR", str(exc))

    def _parse_argos_codes(self, codes):
        pairs = []
        for code in codes:
            source_code, separator, target_code = str(code or "").partition("->")
            if separator and source_code and target_code:
                pairs.append((source_code, target_code))
        return pairs

    def _install_argos_worker(self, codes):
        try:
            import translater

            pairs = self._parse_argos_codes(codes)

            def status_callback(message):
                self._emit_language_progress(str(message), 0, False)

            def progress_callback(message, downloaded_bytes, total_bytes):
                total_bytes = int(total_bytes or 0)
                downloaded_bytes = int(downloaded_bytes or 0)
                if total_bytes > 0:
                    percent = int(downloaded_bytes * 100 / max(total_bytes, 1))
                    self._emit_language_progress(
                        f"Argos {message}: {downloaded_bytes // (1024 * 1024)} / {max(1, total_bytes // (1024 * 1024))} MB",
                        percent,
                        True,
                    )
                else:
                    self._emit_language_progress(f"Argos {message}", 0, False)

            translater.install_argos_packages(
                pairs,
                status_callback=status_callback,
                progress_callback=progress_callback,
                cancel_callback=lambda: self._cancel_requested.is_set(),
            )
            if self._cancel_requested.is_set():
                self._finish_language_task("Argos", canceled=True)
                return
            self._finish_language_task("Argos")
        except Exception as exc:
            if self._cancel_requested.is_set():
                self._finish_language_task("Argos", canceled=True)
            else:
                self._finish_language_task("Argos", str(exc))

    def _remove_argos_worker(self, codes):
        try:
            import translater
            translater.uninstall_argos_packages(
                self._parse_argos_codes(codes),
                status_callback=lambda message: self._emit_language_progress(str(message), 0, False),
            )
            self._finish_language_task("Argos")
        except Exception as exc:
            self._finish_language_task("Argos", str(exc))


class SettingsWindow(QWidget):
    def switch_startup(self, state):
        enabled = self.parent.set_autostart(self.autostart_checkbox.isChecked())
        self.autostart_checkbox.setChecked(enabled)
        self.parent.autostart = enabled
        self.parent.config["autostart"] = enabled
        self.parent.save_config()
        _invalidate_main_config_cache()  # Сбрасываем кэш после сохранения
        if enabled:
            complete = getattr(self.parent, "_complete_guide_step", None)
            if callable(complete):
                complete("autostart")

    def auto_save_setting(self, key, value):
        self.parent.config[key] = value
        if key == "start_minimized":
            self.parent.start_minimized = value
        if key == "autostart":
            self.parent.autostart = value
        self.parent.save_config()
        _invalidate_main_config_cache()  # Сбрасываем кэш после сохранения

    def _on_start_minimized_toggled(self, state):
        enabled = bool(state)
        self.auto_save_setting("start_minimized", enabled)
        if enabled:
            complete = getattr(self.parent, "_complete_guide_step", None)
            if callable(complete):
                complete("start_minimized")

    def _save_ocr_dim_strength(self, value):
        strength = max(0, min(80, int(value)))
        label = getattr(self, "ocr_dim_strength_value", None)
        if label is not None:
            label.setText(f"{strength}%")
        self.auto_save_setting("ocr_dim_strength", strength)

    def _save_game_scan_interval(self, value):
        interval = max(450, min(10000, int(value)))
        label = getattr(self, "game_scan_interval_value", None)
        if label is not None:
            label.setText(f"{interval / 1000:.1f} s")
        self.auto_save_setting("game_capture_interval_ms", interval)

    def _save_game_overlay_opacity(self, value):
        opacity = max(45, min(100, int(value)))
        label = getattr(self, "game_overlay_opacity_value", None)
        if label is not None:
            label.setText(f"{opacity}%")
        self.auto_save_setting("game_overlay_opacity", opacity)

    def _game_source_changed(self, _index=None):
        source_combo = getattr(self, "game_source_combo", None)
        target_combo = getattr(self, "game_target_combo", None)
        if source_combo is None or target_combo is None:
            return
        selected_target = target_combo.currentData()
        self._populate_game_targets(selected_target)
        self._save_game_language_pair()

    def _populate_game_targets(self, selected_target=None, fast=False):
        source_combo = getattr(self, "game_source_combo", None)
        target_combo = getattr(self, "game_target_combo", None)
        if source_combo is None or target_combo is None:
            return
        source = str(source_combo.currentData() or "en")
        preferred = str(
            selected_target
            or self.parent.config.get("game_translate_target_language")
            or "ru"
        )
        if fast:
            available = {preferred} if preferred != source else {
                "ru" if source != "ru" else "en"
            }
        else:
            try:
                from ocr import _translation_targets_for_source
                available = set(_translation_targets_for_source(source, self.parent.config))
            except Exception:
                available = {language.code for language in APP_LANGUAGES if language.code != source}
        target_combo.blockSignals(True)
        try:
            target_combo.clear()
            for language in APP_LANGUAGES:
                if language.code not in available or language.code == source:
                    continue
                target_combo.addItem(language.short_label, language.code)
            index = target_combo.findData(preferred)
            target_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            target_combo.blockSignals(False)
        self._update_game_swap_enabled()

    def _populate_game_language_controls(self, fast=False):
        source_combo = getattr(self, "game_source_combo", None)
        target_combo = getattr(self, "game_target_combo", None)
        if source_combo is None or target_combo is None:
            return
        current_source = str(
            source_combo.currentData()
            or self.parent.config.get("game_translate_source_language")
            or "en"
        )
        config = dict(self.parent.config)
        if fast:
            available = {current_source}
        else:
            try:
                from ocr import installed_ocr_language_codes
                available = set(installed_ocr_language_codes(config=config))
            except Exception:
                available = {language.code for language in APP_LANGUAGES}
        source_combo.blockSignals(True)
        try:
            source_combo.clear()
            for language in APP_LANGUAGES:
                if language.code not in available:
                    continue
                source_combo.addItem(language.short_label, language.code)
            index = source_combo.findData(current_source)
            source_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            source_combo.blockSignals(False)
        self._populate_game_targets(
            self.parent.config.get("game_translate_target_language", "ru"),
            fast=fast,
        )

    def _verify_game_language_controls(self):
        """Do the slower installed-language probe after the feature page paints."""
        if getattr(self, "_game_language_controls_verified", False):
            return
        page = getattr(self, "settings_game_page", None)
        if page is None or not page.isVisible():
            return
        self._populate_game_language_controls()
        self._game_language_controls_verified = True

    def _save_game_language_pair(self, _index=None):
        source_combo = getattr(self, "game_source_combo", None)
        target_combo = getattr(self, "game_target_combo", None)
        if source_combo is None or target_combo is None:
            return
        source, target = source_combo.currentData(), target_combo.currentData()
        if not source or not target or source == target:
            self._update_game_swap_enabled()
            return
        unchanged = (
            str(self.parent.config.get("game_translate_source_language", "")) == str(source)
            and str(self.parent.config.get("game_translate_target_language", "")) == str(target)
        )
        if unchanged:
            self._update_game_swap_enabled()
            return
        self.parent.config["game_translate_source_language"] = str(source)
        self.parent.config["game_translate_target_language"] = str(target)
        self.parent.save_config()
        _invalidate_main_config_cache()
        self._update_game_swap_enabled()

    def _update_game_swap_enabled(self):
        button = getattr(self, "game_swap_button", None)
        source_combo = getattr(self, "game_source_combo", None)
        target_combo = getattr(self, "game_target_combo", None)
        if button is None or source_combo is None or target_combo is None:
            return
        source, target = source_combo.currentData(), target_combo.currentData()
        reverse_available = False
        if source and target and source_combo.findData(target) >= 0:
            try:
                from ocr import _translation_targets_for_source
                reverse_available = str(source) in _translation_targets_for_source(
                    str(target), self.parent.config
                )
            except Exception:
                reverse_available = True
        button.setEnabled(bool(reverse_available))

    def _swap_game_languages(self):
        source_combo = getattr(self, "game_source_combo", None)
        target_combo = getattr(self, "game_target_combo", None)
        if source_combo is None or target_combo is None:
            return
        source, target = source_combo.currentData(), target_combo.currentData()
        target_index = source_combo.findData(target)
        if target_index < 0:
            self._update_game_swap_enabled()
            return
        source_combo.blockSignals(True)
        try:
            source_combo.setCurrentIndex(target_index)
        finally:
            source_combo.blockSignals(False)
        self._populate_game_targets(source)
        reverse_index = target_combo.findData(source)
        if reverse_index >= 0:
            target_combo.setCurrentIndex(reverse_index)
        self._save_game_language_pair()

    def _set_ocr_dimming_enabled(self, enabled):
        enabled = bool(enabled)
        slider = getattr(self, "ocr_dim_strength_slider", None)
        value_label = getattr(self, "ocr_dim_strength_value", None)
        if slider is not None:
            slider.setEnabled(enabled)
        if value_label is not None:
            value_label.setEnabled(enabled)
        self.auto_save_setting("dim_screen_during_ocr", enabled)

    def _create_bug_report_from_settings(self):
        creator = getattr(self.parent, "_create_bug_report", None)
        if callable(creator):
            return creator(self)
        return None

    def _settings_default_export_path(self):
        desktop = QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.DesktopLocation
        )
        folder = desktop or str(Path.home())
        return str(Path(folder) / f"ClicknTranslate-settings-v{APP_VERSION}.json")

    def export_settings(self):
        lang = self.parent.current_interface_language
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            settings_text(lang, "export_settings"),
            self._settings_default_export_path(),
            settings_text(lang, "settings_file_filter"),
        )
        if not path:
            return None
        target = Path(path)
        if target.suffix.lower() != ".json":
            target = target.with_suffix(".json")
        temporary = target.with_name(target.name + ".tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(
                    settings_export_payload(self.parent.config),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ) + "\n",
                encoding="utf-8",
            )
            os.replace(str(temporary), str(target))
        except Exception as error:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            QMessageBox.warning(
                self,
                settings_text(lang, "export_settings"),
                settings_text(lang, "settings_transfer_failed").format(error=error),
            )
            return None
        QMessageBox.information(
            self,
            settings_text(lang, "export_settings"),
            settings_text(lang, "settings_exported").format(path=target),
        )
        return target

    def import_settings(self):
        lang = self.parent.current_interface_language
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            settings_text(lang, "import_settings"),
            str(Path(self._settings_default_export_path()).parent),
            settings_text(lang, "settings_file_filter"),
        )
        if not path:
            return None
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            from main import (
                DEFAULT_CONFIG,
                merge_config_defaults,
                normalize_interface_language,
            )

            imported = validated_import_settings(payload, DEFAULT_CONFIG)
            merged, _missing = merge_config_defaults(imported)
            merged["interface_language"] = normalize_interface_language(
                merged.get("interface_language")
            )
            merged["theme"] = (
                "Светлая" if merged.get("theme") == "Светлая" else "Темная"
            )
            # Dynamic translation has one supported workflow in this release.
            merged["game_capture_mode"] = "region"

            self.parent.config = merged
            self.parent.current_theme = merged["theme"]
            self.parent.current_interface_language = merged["interface_language"]
            self.parent.start_minimized = bool(merged.get("start_minimized", False))
            self.parent.translation_mode = merged.get("translation_mode", "English")
            self.parent.autostart = bool(merged.get("autostart", False))
            actual_autostart = self.parent.set_autostart(self.parent.autostart)
            self.parent.autostart = bool(actual_autostart)
            self.parent.config["autostart"] = self.parent.autostart
            self.parent.save_config()

            restart_hotkeys = getattr(self.parent, "restart_all_hotkey_listeners", None)
            if callable(restart_hotkeys):
                restart_hotkeys()
            self.parent.apply_theme()
            self.parent.refresh_interface_language_ui()
            self.init_ui()
            self.apply_theme()
            self._set_settings_page(0)
        except Exception as error:
            logging.exception("Could not import Click'n'Translate settings")
            QMessageBox.warning(
                self,
                settings_text(lang, "import_settings"),
                settings_text(lang, "settings_transfer_failed").format(error=error),
            )
            return None

        applied_lang = self.parent.current_interface_language
        QMessageBox.information(
            self,
            settings_text(applied_lang, "import_settings"),
            settings_text(applied_lang, "settings_imported"),
        )
        return Path(path)

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
        self._tesseract_progress_owner = None
        self._rapidocr_install_in_progress = False
        self._rapidocr_install_phase = "idle"
        self._rapidocr_temp_dir = ""
        self._rapidocr_install_process = None
        self._rapidocr_cancel_requested = threading.Event()
        self._rapidocr_progress_owner = None
        self._easyocr_install_in_progress = False
        self._easyocr_install_phase = "idle"
        self._easyocr_temp_dir = ""
        self._easyocr_install_process = None
        self._easyocr_cancel_requested = threading.Event()
        self._easyocr_progress_owner = None
        self._hymt_install_in_progress = False
        self._hymt_install_phase = "idle"
        self._hymt_temp_dir = ""
        self._hymt_cancel_requested = threading.Event()
        self._language_manager_dialog = None
        self._language_package_task_state = {
            "text": "",
            "percent": None,
            "kind": "idle",
        }
        self.rapidocr_progress = None
        self.easyocr_progress = None
        self.hymt_progress = None
        self._parent_was_topmost_before_tesseract = None
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.init_ui()
        self.apply_theme()

    def clear_main_layout(self):
        # Absolute fixed-window regions are not owned by main_layout. Hide
        # their children explicitly as well: secondary screens and a language
        # rebuild must never leave a cached footer button painted on top.
        for attribute in (
            "settings_updates_page",
            "settings_game_page",
            "settings_action_panel",
            "settings_page_footer",
        ):
            region = getattr(self, attribute, None)
            if region is None:
                continue
            try:
                for child in region.findChildren(QWidget):
                    child.hide()
                region.hide()
            except RuntimeError:
                pass
        # Очищаем все элементы из текущего макета
        if self.main_layout is not None:
            while self.main_layout.count():
                item = self.main_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    # A deferred delete is not an immediate visual removal.
                    # Hide the old settings page first so a theme/language
                    # change cannot expose its cached pixels over the new one.
                    # A stacked page keeps its children's own hidden flag
                    # unchanged when only the stack is hidden, so hide every
                    # descendant explicitly as well.
                    for child in widget.findChildren(QWidget):
                        child.hide()
                    widget.hide()
                    widget.deleteLater()
                elif item.layout():
                    self.clear_nested_layout(item.layout())

    def clear_nested_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.hide()
                    widget.deleteLater()
                elif item.layout():
                    self.clear_nested_layout(item.layout())

    def setup_new_layout(self):
        # These fixed-window regions are absolute children rather than layout
        # items, so remove them explicitly when rebuilding or relanguaging.
        for attribute in (
            "settings_updates_page",
            "settings_game_page",
            "settings_action_panel",
            "settings_page_footer",
        ):
            widget = getattr(self, attribute, None)
            if widget is None:
                continue
            try:
                for child in widget.findChildren(QWidget):
                    child.hide()
                widget.hide()
                widget.deleteLater()
            except RuntimeError:
                pass
            setattr(self, attribute, None)
        # Больше не пересоздаём layout, только очищаем
        self.clear_main_layout()

    def init_ui(self):
        # Every visit starts from the compact general page.  Remembering page
        # 2/3 made Settings appear empty or unfamiliar on the next opening.
        page_to_restore = 0
        self.setup_new_layout()
        self.hotkeys_mode = False
        self._secondary_view_kind = None
        self.secondary_view_shell = None
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        # Five general rows must finish clearly above the fixed action panel.
        # An 8px gap plus 38px rows produced a 46px rhythm and let the final
        # checkbox run into the buttons in the real embedded viewport.
        self.main_layout.setSpacing(4)
        # This page is rendered inside a fixed 690x390 viewport. Keep the
        # controls top-anchored so adding a selector on the right cannot move
        # the checkbox column on the left.
        self.main_layout.setAlignment(Qt.AlignTop)
        lang = self.parent.current_interface_language
        self._ui_language = lang
        self._game_language_controls_verified = False

        # --- ГРУППА ЧЕКБОКСОВ ---
        # The layout margin already supplies the intended 5px top inset.

        margin_top_val = "-12px" if self.parent.current_theme == "Темная" else "-6px"
        fixed_height = 34
        engine_combo_width = 180
        engine_control_height = 32
        # Three joined action rows must fit above the pager in the real
        # 672x334 settings viewport. At 36px Qt overlaps the rows and paints
        # over their lower borders; 31px keeps every frame intact.
        action_button_height = 29
        
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
        
        # Правые блоки обеих строк имеют одинаковую высоту и разметку.
        # Кнопка удаления живёт в расширенной правой секции самого списка.
        self.ocr_engine_label = QLabel("OCR:")
        self.ocr_engine_label.setStyleSheet("margin:0; padding:0;")
        self.ocr_engine_label.setFixedWidth(90)
        self.ocr_engine_label.setFixedHeight(engine_control_height)
        self.ocr_engine_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Same drop-down behaviour as the other two pickers: the list opens
        # below the field instead of covering it.
        self.ocr_engine_combo = DropDownCombo()
        engine_group_color = (
            "#f4f6fb" if self.parent.current_theme != "Светлая" else "#202124"
        )
        installed_ocr_engines = {"Windows"} if platform_support.supports_windows_ocr() else set()
        if self._find_available_tesseract_exe():
            installed_ocr_engines.add("Tesseract")
        if self._rapidocr_runtime_installed():
            installed_ocr_engines.add(RAPIDOCR_ENGINE_DISPLAY)
        if self._easyocr_runtime_installed():
            installed_ocr_engines.add(EASYOCR_ENGINE_DISPLAY)
        _populate_grouped_ocr_combo(
            self.ocr_engine_combo,
            lang,
            engine_group_color,
            installed_engines=installed_ocr_engines,
        )
        default_engine = platform_support.default_ocr_engine()
        current_engine = self.parent.config.get("ocr_engine", default_engine)
        idx = self.ocr_engine_combo.findText(current_engine, Qt.MatchFixedString)
        if idx >= 0:
            self.ocr_engine_combo.setCurrentIndex(idx)
        else:
            fallback_index = self.ocr_engine_combo.findData(default_engine)
            self.ocr_engine_combo.setCurrentIndex(max(0, fallback_index))

        self.ocr_engine_combo.currentTextChanged.connect(self.handle_ocr_engine_change)
        self._apply_engine_combo_style(self.ocr_engine_combo)
        self.ocr_engine_combo.setFixedWidth(engine_combo_width)
        self.ocr_engine_combo.setFixedHeight(engine_control_height)
        # Все три правых элемента имеют высоту 32 px и один вертикальный центр.
        # Pin the controls to the row's top edge. Centering a 32px control in
        # a stylesheet-sized checkbox row rounds differently after a language
        # rebuild and produced a visible one-pixel jump on Windows.
        row1.addWidget(self.ocr_engine_label, alignment=Qt.AlignTop)
        row1.addWidget(self.ocr_engine_combo, alignment=Qt.AlignTop)
        
        # Each popup item has its own concise explanation.  Avoid one giant
        # native tooltip covering most of the fixed settings window.
        ocr_picker_help = {
            "en": "Choose an OCR engine. Missing engines can be installed when selected.",
            "ru": "Выберите OCR. Отсутствующий движок можно установить после выбора.",
            "es": "Elige un OCR. Los motores que faltan se pueden instalar al elegirlos.",
            "de": "OCR-Engine wählen. Fehlende Engines können danach installiert werden.",
            "fr": "Choisissez un OCR. Un moteur manquant peut ensuite être installé.",
            "zh": "选择 OCR；缺少的引擎可在选择后安装。",
        }
        self.ocr_engine_combo.setToolTip(tooltip_text(ocr_picker_help.get(lang, ocr_picker_help["en"])))
        self.ocr_engine_label.setToolTip(tooltip_text(ocr_picker_help.get(lang, ocr_picker_help["en"])))
        self.main_layout.addLayout(row1)
        
        # --- СТРОКА 2: Запускать в режиме тень + Переводчик ---
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(8)
        self.start_minimized_checkbox = QCheckBox(settings_text(lang, "start_minimized"))
        self.start_minimized_checkbox.setChecked(self.parent.config.get("start_minimized", False))
        self.start_minimized_checkbox.toggled.connect(self._on_start_minimized_toggled)
        self.start_minimized_checkbox.setStyleSheet(f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val}; min-width:300px;")
        self.start_minimized_checkbox.setFixedHeight(fixed_height)
        row2.addWidget(self.start_minimized_checkbox, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        row2.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # Блок переводчика повторяет ту же сетку, чтобы колонки не сдвигались.
        self.translator_engine_label = QLabel(settings_text(lang, "translator_label"))
        self.translator_engine_label.setStyleSheet("margin:0; padding:0;")
        self.translator_engine_label.setFixedWidth(90)
        self.translator_engine_label.setFixedHeight(engine_control_height)
        self.translator_engine_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.translator_combo = DropDownCombo()
        installed_translator_engines = {
            engine
            for engine, _name, kind in TRANSLATOR_ENGINE_OPTIONS
            if kind == "online"
        }
        try:
            import translater
            if translater.argos_installed_translation_pairs_fast():
                installed_translator_engines.add("argos")
        except Exception:
            pass
        if self._hymt_installed():
            installed_translator_engines.add(HYMT_ENGINE_KEY)
        self._translator_engines = _populate_grouped_translator_combo(
            self.translator_combo,
            lang,
            engine_group_color,
            installed_engines=installed_translator_engines,
        )
        
        current_tr = self.parent.config.get("translator_engine", "Google").lower()
        try:
            idx = self._translator_engines.index(current_tr)
        except ValueError:
            idx = self._translator_engines.index("google")
        self.translator_combo.setCurrentIndex(idx)
        self.translator_combo.currentIndexChanged.connect(self._on_translator_changed)
        self._apply_engine_combo_style(self.translator_combo)
        self.translator_combo.setFixedWidth(engine_combo_width)
        self.translator_combo.setFixedHeight(engine_control_height)
        row2.addWidget(self.translator_engine_label, alignment=Qt.AlignTop)
        row2.addWidget(self.translator_combo, alignment=Qt.AlignTop)
        
        translator_picker_help = {
            "en": "Online providers need internet. Installed offline providers are listed separately.",
            "ru": "Онлайн-переводчикам нужен интернет. Установленные офлайн-пакеты показаны отдельно.",
            "es": "Los proveedores online necesitan internet; los offline instalados aparecen aparte.",
            "de": "Online-Anbieter benötigen Internet; installierte Offline-Anbieter stehen separat.",
            "fr": "Les services en ligne nécessitent Internet ; les moteurs hors ligne installés sont séparés.",
            "zh": "在线服务需要网络；已安装的离线翻译器会单独显示。",
        }
        picker_help = translator_picker_help.get(lang, translator_picker_help["en"])
        self.translator_combo.setToolTip(tooltip_text(picker_help))
        self.translator_engine_label.setToolTip(tooltip_text(picker_help))
        self.main_layout.addLayout(row2)

        # --- Подготовим кнопку обновления (перенесена в группу кнопок ниже) ---
        # Убрали из этой строки

        # --- Остальные чекбоксы (start_minimized уже добавлен выше) ---

        # --- СТРОКА 3: автокопирование + поведение окна результата ---
        # Не оставляем пустую строку в левой колонке: третий основной чекбокс
        # продолжает последовательность, а управление результатом остаётся
        # выровнено с OCR и переводчиком справа.
        row3 = QHBoxLayout()
        row3.setContentsMargins(0, 0, 0, 0)
        row3.setSpacing(8)
        self.copy_translated_checkbox = QCheckBox(settings_text(lang, "copy_translated_text"))
        self.copy_translated_checkbox.setChecked(self.parent.config.get("copy_translated_text", False))
        self.copy_translated_checkbox.toggled.connect(
            lambda state: self.auto_save_setting("copy_translated_text", state)
        )
        # No min-width here: this row shares its line with the Show-window
        # picker, and a fixed 260px clipped the longer languages against it.
        # The width is set from the box's own size hint once the theme's font is
        # in place — see _fit_copy_translated_checkbox.
        self.copy_translated_checkbox.setStyleSheet(
            f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val};"
        )
        self.copy_translated_checkbox.setFixedHeight(fixed_height)
        row3.addWidget(self.copy_translated_checkbox, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        row3.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.result_window_label = QLabel(settings_text(lang, "result_window_label"))
        self.result_window_label.setStyleSheet("margin:0; padding:0;")
        result_label_font = self.result_window_label.font()
        result_label_font.setPixelSize(16)
        self.result_window_label.setFont(result_label_font)
        # This label names what the drop-down controls, so it is longer than
        # "OCR:" and sizes itself; the row is right-aligned, so the extra width
        # grows into the empty middle of the window and the columns still line
        # up with the two engine rows.
        self.result_window_label.setFixedWidth(
            max(80, QtGui.QFontMetrics(result_label_font).horizontalAdvance(
                self.result_window_label.text()) + 4)
        )
        self.result_window_label.setFixedHeight(engine_control_height)
        self.result_window_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Ленивый импорт для избежания циклического импорта
        from main import RESULT_WINDOW_MODES, result_window_hidden_modes

        hidden_modes = set(result_window_hidden_modes(self.parent.config))
        # A drop-down keeps this row consistent with the two engine pickers
        # above it. The three actions are independent switches, so each row in
        # the list carries its own check box rather than being a single choice.
        self.result_window_control = ResultWindowModeCombo(
            RESULT_WINDOW_MODES,
            {mode: settings_text(lang, f"result_window_row_{mode}")
             for mode in RESULT_WINDOW_MODES},
            {
                "all": settings_text(lang, "result_window_summary_all"),
                "none": settings_text(lang, "result_window_summary_none"),
                "on": settings_text(lang, "result_window_summary_on"),
                "off": settings_text(lang, "result_window_summary_off"),
                "count": settings_text(lang, "result_window_summary_count"),
            },
            dark=self.parent.current_theme != "Светлая",
            short_labels={mode: settings_text(lang, f"result_window_mode_{mode}")
                          for mode in RESULT_WINDOW_MODES},
            header=settings_text(lang, "result_window_modes_header"),
            header_color="#f4f6fb" if self.parent.current_theme != "Светлая" else "#202124",
        )
        self.result_window_control.setObjectName("resultWindowModes")
        self.result_window_control.setFixedSize(engine_combo_width, engine_control_height)
        self.result_window_control.setCursor(Qt.PointingHandCursor)
        for mode in RESULT_WINDOW_MODES:
            item = self.result_window_control._item(mode)
            if item is not None:
                item.setToolTip(settings_text(lang, f"result_window_mode_{mode}_tooltip"))
        # Checked means exactly what it looks like: this action SHOWS the
        # window. The persisted setting stores the inverse for backwards
        # compatibility with existing configurations.
        self.result_window_control.set_checked_modes(
            [mode for mode in RESULT_WINDOW_MODES if mode not in hidden_modes]
        )
        self.result_window_control.modes_changed.connect(self._save_result_window_modes)
        self.result_window_control.installEventFilter(self)

        self._apply_engine_combo_style(self.result_window_control)
        # The popup is a top-level widget of its own, so it misses the sweep
        # install_accent_controls() does over this window — and apply_theme()
        # runs before this control exists. Style it here, at its source.
        install_accent_controls(
            self.result_window_control.view(),
            dark=self.parent.current_theme != "Светлая",
        )
        self.result_window_control.setAccessibleName(settings_text(lang, "result_window_label"))
        # Sets both the tooltip and the accessible description, and keeps the
        # list of enabled actions in them as the rows are toggled.
        self.result_window_control.set_help_text(settings_text(lang, "result_window_tooltip"))
        self.result_window_label.setToolTip(tooltip_text(settings_text(lang, "result_window_tooltip")))

        row3.addWidget(self.result_window_label, alignment=Qt.AlignTop)
        row3.addWidget(self.result_window_control, alignment=Qt.AlignTop)
        self.main_layout.addLayout(row3)

        # Остальные чекбоксы
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

        # All three action rows share one grid. Separate horizontal layouts
        # round a width that is not divisible by three independently, which
        # made their vertical dividers disagree by one pixel. A single grid
        # owns every column boundary and removes the gaps between the rows.
        self.settings_action_panel = QWidget(self)
        self.settings_action_panel.setObjectName("settingsActionPanel")
        self.settings_action_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.settings_action_panel.setFixedHeight(action_button_height * 3 + 4)
        action_grid = QGridLayout(self.settings_action_panel)
        # The panel owns the complete outer frame. One-pixel layout gaps are
        # the internal dividers, so no child can paint over a neighbour's or
        # the panel's lower border after a language/theme rebuild.
        action_grid.setContentsMargins(1, 1, 1, 1)
        # With two 1px outer margins the fixed panel's inner width divides
        # exactly into three columns. A layout gap consumed an extra two pixels
        # and made the right column one pixel wider after every rebuild.
        action_grid.setHorizontalSpacing(0)
        action_grid.setVerticalSpacing(1)
        for column in range(3):
            action_grid.setColumnStretch(column, 1)
        
        # Левая кнопка - закругление слева (фиолетовая)
        self.clear_cache_btn = OpticallyCenteredPushButton(settings_text(lang, "clear_cache"))
        self.clear_cache_btn.setObjectName("settingsClearCacheButton")
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
                padding-bottom: 0px;
                padding-left: 12px;
                padding-right: 12px;
                font-family: 'Segoe UI';
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #8B70B2; }
        """)
        self.clear_cache_btn.setFixedHeight(action_button_height)
        self.clear_cache_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.clear_cache_btn.clicked.connect(self.clear_all_cache)
        action_grid.addWidget(self.clear_cache_btn, 0, 0)
        
        # Средняя кнопка - без закругления (красная - сброс)
        self.reset_btn = OpticallyCenteredPushButton(settings_text(lang, "reset"))
        self.reset_btn.setObjectName("settingsResetButton")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #D44444; 
                color: #fff; 
                border: none;
                border-radius: 0px;
                border-left: 1px solid rgba(255,255,255,0.15);
                border-right: 1px solid rgba(255,255,255,0.15);
                padding-top: 0px;
                padding-bottom: 0px;
                padding-left: 12px;
                padding-right: 12px;
                font-family: 'Segoe UI';
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #E55555; }
        """)
        self.reset_btn.setFixedHeight(action_button_height)
        self.reset_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.reset_btn.clicked.connect(self.reset_settings)
        action_grid.addWidget(self.reset_btn, 0, 1)
        
        # Правая кнопка - закругление справа (фиолетовая - обновление)
        self.update_btn = OpticallyCenteredPushButton(settings_text(lang, "update"))
        self.update_btn.setObjectName("settingsUpdateButton")
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
                padding-bottom: 0px;
                padding-left: 12px;
                padding-right: 12px;
                font-family: 'Segoe UI';
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #8B70B2; }
        """)
        self.update_btn.setFixedHeight(action_button_height)
        self.update_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.update_btn.clicked.connect(self.check_for_updates)
        action_grid.addWidget(self.update_btn, 0, 2)

        # --- ГРУППА КНОПОК: OCR languages | Hotkeys ---

        self.ocr_languages_btn = OpticallyCenteredPushButton(settings_text(lang, "ocr_language_packs"))
        self.ocr_languages_btn.setObjectName("settingsLanguagePackagesButton")
        self.ocr_languages_btn.clicked.connect(self.show_ocr_language_manager)
        self.ocr_languages_btn.setToolTip(tooltip_text(settings_text(lang, "manage_ocr_languages")))
        self.ocr_languages_btn.setStyleSheet("""
            QPushButton {
                padding: 0px 6px;
                font-family: 'Segoe UI';
                font-size: 16px;
                font-weight: bold;
                border-radius: 0px;
                border-right: 1px solid rgba(255,255,255,0.1);
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            QPushButton[packageTaskDone="true"] {
                color: #59c879;
            }
        """)
        self.ocr_languages_btn.setFixedHeight(action_button_height)
        self.ocr_languages_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._apply_language_package_task_status()
        action_grid.addWidget(self.ocr_languages_btn, 1, 0)

        # --- ГРУППА КНОПОК (расширенные для полного текста) ---
        self.hotkeys_button = OpticallyCenteredPushButton(settings_text(lang, "hotkeys"))
        self.hotkeys_button.setObjectName("settingsHotkeysButton")
        self.hotkeys_button.clicked.connect(self.show_hotkeys_screen)
        # Hotkeys: текст еще выше
        self.hotkeys_button.setStyleSheet("""
            padding-top: 0px;
            padding-bottom: 0px;
            padding-left: 16px;
            padding-right: 16px;
            font-family: 'Segoe UI';
            font-size: 16px;
            font-weight: bold;
            border-radius: 0px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        """)
        self.hotkeys_button.setFixedHeight(action_button_height)
        self.hotkeys_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.translation_history_btn = OpticallyCenteredPushButton(
            settings_text(lang, "translation_history_button")
        )
        self.translation_history_btn.setObjectName("settingsTranslationHistoryButton")
        self.translation_history_btn.clicked.connect(self.show_history_view)
        self.translation_history_btn.setStyleSheet("""
            QPushButton {
                padding: 0px 6px;
                font-family: 'Segoe UI';
                font-size: 16px;
                font-weight: bold;
                border-radius: 0px;
                border-left: 1px solid rgba(255,255,255,0.1);
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
        """)
        self.translation_history_btn.setFixedHeight(action_button_height)
        self.translation_history_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        action_grid.addWidget(self.translation_history_btn, 1, 2)

        # --- Нижняя строка без вертикального разреза ---

        self.copy_history_btn = OpticallyCenteredPushButton(settings_text(lang, "copy_history_button"))
        self.copy_history_btn.setObjectName("settingsCopyHistoryButton")
        self.copy_history_btn.clicked.connect(self.show_copy_history_view)
        # Copy history lives beside translation history in the upper tools row.
        self.copy_history_btn.setStyleSheet("""
            QPushButton {
                padding: 0px 6px;
                font-family: 'Segoe UI';
                font-size: 16px;
                font-weight: bold;
                border-radius: 0px;
                border-left: 1px solid rgba(255,255,255,0.1);
                border-right: 1px solid rgba(255,255,255,0.1);
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
        """)
        self.copy_history_btn.setFixedHeight(action_button_height)
        self.copy_history_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        action_grid.addWidget(self.copy_history_btn, 1, 1)
        self.hotkeys_button.setStyleSheet("""
            QPushButton {
                padding: 0px 16px;
                font-family: 'Segoe UI';
                font-size: 16px;
                font-weight: bold;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        self.hotkeys_button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        action_grid.addWidget(self.hotkeys_button, 2, 0, 1, 3)
        self._apply_action_panel_style()
        
        # --- Page 2: OCR behaviour and updates ---
        # Keep this as one clean page.  The fixed 700x400 window does not have
        # enough horizontal room for a second settings form beside it without
        # truncating both columns.
        self.settings_updates_page = QWidget(self)
        self.settings_updates_page.setObjectName("settingsUpdatesPage")
        self.settings_updates_page.setAttribute(Qt.WA_StyledBackground, True)
        updates_layout = QVBoxLayout(self.settings_updates_page)
        updates_layout.setContentsMargins(0, 0, 0, 0)
        updates_layout.setSpacing(4)
        updates_layout.setAlignment(Qt.AlignTop)
        page_checkbox_height = fixed_height

        # These controls belong together: they all change what happens while
        # the user is selecting an OCR region. Move the existing widgets from
        # page one instead of creating duplicate settings with divergent state.
        for checkbox in (self.keep_visible_checkbox, self.freeze_screen_checkbox):
            self.main_layout.removeWidget(checkbox)
            checkbox.setParent(self.settings_updates_page)
            checkbox.setFixedHeight(page_checkbox_height)
            updates_layout.addWidget(checkbox, alignment=Qt.AlignLeft)

        self.dim_screen_during_ocr_checkbox = QCheckBox(
            settings_text(lang, "dim_screen_during_ocr"), self.settings_updates_page
        )
        self.dim_screen_during_ocr_checkbox.setChecked(
            bool(self.parent.config.get("dim_screen_during_ocr", False))
        )
        self.dim_screen_during_ocr_checkbox.setStyleSheet(
            f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val};"
        )
        self.dim_screen_during_ocr_checkbox.setFixedHeight(page_checkbox_height)
        dim_tooltip = settings_text(lang, "ocr_dim_strength_tooltip")
        self.dim_screen_during_ocr_checkbox.setToolTip(tooltip_text(dim_tooltip))

        dim_row = QHBoxLayout()
        dim_row.setContentsMargins(0, 0, 0, 0)
        dim_row.setSpacing(8)
        dim_row.addWidget(
            self.dim_screen_during_ocr_checkbox,
            alignment=Qt.AlignLeft | Qt.AlignVCenter,
        )
        dim_row.addStretch(1)
        try:
            dim_strength = int(self.parent.config.get("ocr_dim_strength", 60))
        except (TypeError, ValueError):
            dim_strength = 60
        dim_strength = max(0, min(80, dim_strength))
        self.ocr_dim_strength_value = QLabel(f"{dim_strength}%")
        self.ocr_dim_strength_value.setObjectName("ocrDimStrengthValue")
        self.ocr_dim_strength_value.setFixedWidth(42)
        self.ocr_dim_strength_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ocr_dim_strength_value.setToolTip(tooltip_text(dim_tooltip))
        dim_row.addWidget(self.ocr_dim_strength_value)
        self.ocr_dim_strength_slider = QSlider(Qt.Horizontal)
        self.ocr_dim_strength_slider.setObjectName("ocrDimStrengthSlider")
        self.ocr_dim_strength_slider.setRange(0, 80)
        self.ocr_dim_strength_slider.setSingleStep(5)
        self.ocr_dim_strength_slider.setPageStep(10)
        self.ocr_dim_strength_slider.setValue(dim_strength)
        self.ocr_dim_strength_slider.setFixedWidth(140)
        self.ocr_dim_strength_slider.setToolTip(tooltip_text(dim_tooltip))
        self.ocr_dim_strength_slider.setAccessibleName(dim_tooltip)
        self.ocr_dim_strength_slider.valueChanged.connect(self._save_ocr_dim_strength)
        dim_row.addWidget(self.ocr_dim_strength_slider, alignment=Qt.AlignVCenter)
        updates_layout.addLayout(dim_row)
        self.dim_screen_during_ocr_checkbox.toggled.connect(
            self._set_ocr_dimming_enabled
        )
        self.ocr_dim_strength_slider.setEnabled(
            self.dim_screen_during_ocr_checkbox.isChecked()
        )
        self.ocr_dim_strength_value.setEnabled(
            self.dim_screen_during_ocr_checkbox.isChecked()
        )

        self.restore_clipboard_checkbox = QCheckBox(
            settings_text(lang, "restore_clipboard_after_selection"),
            self.settings_updates_page,
        )
        self.restore_clipboard_checkbox.setChecked(
            bool(self.parent.config.get("restore_clipboard_after_selection", True))
        )
        self.restore_clipboard_checkbox.setToolTip(
            tooltip_text(settings_text(lang, "restore_clipboard_tooltip"))
        )
        self.restore_clipboard_checkbox.setStyleSheet(
            f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val};"
        )
        self.restore_clipboard_checkbox.setFixedHeight(page_checkbox_height)
        self.restore_clipboard_checkbox.toggled.connect(
            lambda state: self.auto_save_setting(
                "restore_clipboard_after_selection", bool(state)
            )
        )
        updates_layout.addWidget(self.restore_clipboard_checkbox, alignment=Qt.AlignLeft)

        self.copy_notification_checkbox = QCheckBox(
            settings_text(lang, "copy_notification"), self.settings_updates_page
        )
        self.copy_notification_checkbox.setChecked(
            bool(self.parent.config.get("notifications", False))
        )
        self.copy_notification_checkbox.setToolTip(
            tooltip_text(settings_text(lang, "copy_notification_tooltip"))
        )
        self.copy_notification_checkbox.setStyleSheet(
            f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val};"
        )
        self.copy_notification_checkbox.setFixedHeight(page_checkbox_height)
        self.copy_notification_checkbox.toggled.connect(
            lambda state: self.auto_save_setting("notifications", bool(state))
        )
        updates_layout.addWidget(
            self.copy_notification_checkbox, alignment=Qt.AlignLeft
        )

        self.update_check_on_launch_checkbox = QCheckBox(
            settings_text(lang, "update_check_on_launch")
        )
        self.update_check_on_launch_checkbox.setChecked(
            bool(self.parent.config.get("update_check_on_launch", True))
        )
        self.update_check_on_launch_checkbox.toggled.connect(
            lambda state: self.auto_save_setting("update_check_on_launch", bool(state))
        )
        self.update_check_on_launch_checkbox.setStyleSheet(
            f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val};"
        )
        self.update_check_on_launch_checkbox.setFixedHeight(page_checkbox_height)
        updates_layout.addWidget(
            self.update_check_on_launch_checkbox,
            alignment=Qt.AlignLeft | Qt.AlignVCenter,
        )

        transfer_row = QHBoxLayout()
        transfer_row.setContentsMargins(0, 2, 0, 0)
        transfer_row.setSpacing(6)

        self.export_settings_btn = QPushButton(
            settings_text(lang, "export_settings"), self.settings_updates_page
        )
        self.export_settings_btn.setObjectName("settingsTransferButton")
        self.export_settings_btn.setToolTip(
            tooltip_text(settings_text(lang, "export_settings_tooltip"))
        )
        self.export_settings_btn.clicked.connect(self.export_settings)

        self.import_settings_btn = QPushButton(
            settings_text(lang, "import_settings"), self.settings_updates_page
        )
        self.import_settings_btn.setObjectName("settingsTransferButton")
        self.import_settings_btn.setToolTip(
            tooltip_text(settings_text(lang, "import_settings_tooltip"))
        )
        self.import_settings_btn.clicked.connect(self.import_settings)

        self.create_bug_report_btn = QPushButton(
            settings_text(lang, "create_bug_report"), self.settings_updates_page
        )
        self.create_bug_report_btn.setObjectName("settingsBugReportButton")
        self.create_bug_report_btn.setToolTip(
            tooltip_text(settings_text(lang, "bug_report_tooltip"))
        )
        self.create_bug_report_btn.clicked.connect(
            self._create_bug_report_from_settings
        )
        for button in (
            self.export_settings_btn,
            self.import_settings_btn,
            self.create_bug_report_btn,
        ):
            button.setFixedHeight(page_checkbox_height)
            button.setMinimumWidth(0)
            # Ignore translated size hints: all three buttons own exactly one
            # third of the fixed-width row in every interface language.
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            transfer_row.addWidget(button, 1)
        updates_layout.addLayout(transfer_row)
        updates_layout.addStretch()
        self.settings_updates_page.hide()

        # --- Page 3: dynamic translation ---
        # Dynamic translation has one predictable workflow: replace text in
        # one or more areas selected by the user.
        self.settings_game_page = QWidget(self)
        self.settings_game_page.setObjectName("settingsGamePage")
        self.settings_game_page.setAttribute(Qt.WA_StyledBackground, True)
        game_layout = QGridLayout(self.settings_game_page)
        game_layout.setContentsMargins(8, 0, 8, 0)
        game_layout.setHorizontalSpacing(12)
        game_layout.setVerticalSpacing(3)
        game_layout.setColumnStretch(0, 1)
        game_layout.setColumnMinimumWidth(1, 310)
        game_layout.setAlignment(Qt.AlignTop)

        self.game_settings_heading = QLabel(settings_text(lang, "game_settings_heading"))
        self.game_settings_heading.setObjectName("gameSettingsHeading")
        self.game_settings_heading.setFixedHeight(28)
        game_layout.addWidget(self.game_settings_heading, 0, 0, 1, 2)

        def game_row(label_text):
            label = QLabel(label_text, self.settings_game_page)
            label.setObjectName("gameSettingsLabel")
            label.setFixedHeight(32)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            return label

        self.game_languages_label = game_row(
            settings_text(lang, "game_languages")
        )
        self.game_language_controls = QWidget(self.settings_game_page)
        self.game_language_controls.setObjectName("gameLanguageControls")
        self.game_language_controls.setFixedSize(310, 32)
        language_row = QHBoxLayout(self.game_language_controls)
        language_row.setContentsMargins(0, 0, 0, 0)
        language_row.setSpacing(6)
        self.game_source_combo = DropDownCombo(self.settings_game_page)
        self.game_target_combo = DropDownCombo(self.settings_game_page)
        for combo in (self.game_source_combo, self.game_target_combo):
            combo.setFixedSize(132, 32)
            self._apply_engine_combo_style(combo)
        self.game_swap_button = LanguageSwapButton(self.settings_game_page)
        self.game_swap_button.setObjectName("gameLanguageSwap")
        self.game_swap_button.setFixedSize(34, 32)
        self.game_swap_button.setToolTip(tooltip_text(settings_text(lang, "game_swap_languages")))
        language_row.addWidget(self.game_source_combo)
        language_row.addWidget(self.game_swap_button)
        language_row.addWidget(self.game_target_combo)
        game_layout.addWidget(self.game_languages_label, 1, 0)
        game_layout.addWidget(self.game_language_controls, 1, 1)

        self.game_scan_interval_label = game_row(
            settings_text(lang, "game_scan_interval")
        )
        try:
            game_interval = int(self.parent.config.get("game_capture_interval_ms", 850))
        except (TypeError, ValueError):
            game_interval = 850
        game_interval = max(450, min(10000, game_interval))
        self.game_interval_controls = QWidget(self.settings_game_page)
        self.game_interval_controls.setObjectName("gameIntervalControls")
        self.game_interval_controls.setFixedSize(310, 32)
        interval_row = QHBoxLayout(self.game_interval_controls)
        interval_row.setContentsMargins(0, 0, 0, 0)
        interval_row.setSpacing(8)
        self.game_scan_interval_slider = QSlider(Qt.Horizontal, self.settings_game_page)
        self.game_scan_interval_slider.setObjectName("gameScanIntervalSlider")
        self.game_scan_interval_slider.setRange(450, 10000)
        self.game_scan_interval_slider.setSingleStep(50)
        self.game_scan_interval_slider.setPageStep(500)
        self.game_scan_interval_slider.setValue(game_interval)
        self.game_scan_interval_slider.setFixedWidth(240)
        self.game_scan_interval_value = QLabel(f"{game_interval / 1000:.1f} s")
        self.game_scan_interval_value.setObjectName("gameSettingValue")
        self.game_scan_interval_value.setFixedWidth(62)
        self.game_scan_interval_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        interval_row.addWidget(self.game_scan_interval_slider)
        interval_row.addWidget(self.game_scan_interval_value)
        game_layout.addWidget(self.game_scan_interval_label, 2, 0)
        game_layout.addWidget(self.game_interval_controls, 2, 1)

        self.game_overlay_opacity_label = game_row(
            settings_text(lang, "game_overlay_opacity")
        )
        try:
            game_opacity = int(self.parent.config.get("game_overlay_opacity", 88))
        except (TypeError, ValueError):
            game_opacity = 88
        game_opacity = max(45, min(100, game_opacity))
        self.game_opacity_controls = QWidget(self.settings_game_page)
        self.game_opacity_controls.setObjectName("gameOpacityControls")
        self.game_opacity_controls.setFixedSize(310, 32)
        opacity_row = QHBoxLayout(self.game_opacity_controls)
        opacity_row.setContentsMargins(0, 0, 0, 0)
        opacity_row.setSpacing(8)
        self.game_overlay_opacity_slider = QSlider(Qt.Horizontal, self.settings_game_page)
        self.game_overlay_opacity_slider.setObjectName("gameOverlayOpacitySlider")
        self.game_overlay_opacity_slider.setRange(45, 100)
        self.game_overlay_opacity_slider.setSingleStep(1)
        self.game_overlay_opacity_slider.setPageStep(5)
        self.game_overlay_opacity_slider.setValue(game_opacity)
        self.game_overlay_opacity_slider.setFixedWidth(240)
        self.game_overlay_opacity_value = QLabel(f"{game_opacity}%")
        self.game_overlay_opacity_value.setObjectName("gameSettingValue")
        self.game_overlay_opacity_value.setFixedWidth(62)
        self.game_overlay_opacity_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        opacity_row.addWidget(self.game_overlay_opacity_slider)
        opacity_row.addWidget(self.game_overlay_opacity_value)
        game_layout.addWidget(self.game_overlay_opacity_label, 3, 0)
        game_layout.addWidget(self.game_opacity_controls, 3, 1)

        self.game_pause_inactive_checkbox = QCheckBox(
            settings_text(lang, "game_pause_inactive"), self.settings_game_page
        )
        self.game_pause_inactive_checkbox.setChecked(
            bool(self.parent.config.get("game_pause_when_inactive", True))
        )
        self.game_pause_inactive_checkbox.setToolTip(
            tooltip_text(settings_text(lang, "game_pause_inactive_tooltip"))
        )
        self.game_pause_inactive_checkbox.setFixedHeight(page_checkbox_height)
        self.game_pause_inactive_checkbox.setStyleSheet(
            f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val};"
        )
        game_layout.addWidget(
            self.game_pause_inactive_checkbox, 4, 0, 1, 2, Qt.AlignLeft | Qt.AlignVCenter
        )

        self.game_show_original_checkbox = QCheckBox(
            settings_text(lang, "game_show_original"), self.settings_game_page
        )
        self.game_show_original_checkbox.setChecked(
            bool(self.parent.config.get("game_show_original_text", False))
        )
        self.game_show_original_checkbox.setFixedHeight(page_checkbox_height)
        self.game_show_original_checkbox.setStyleSheet(
            f"margin-left:0px; margin-bottom:0px; margin-top:{margin_top_val};"
        )
        game_layout.addWidget(
            self.game_show_original_checkbox, 5, 0, 1, 2, Qt.AlignLeft | Qt.AlignVCenter
        )

        self.game_workflow_note = QLabel(
            settings_text(lang, "game_workflow_note"), self.settings_game_page
        )
        self.game_workflow_note.setObjectName("gameWorkflowNote")
        self.game_workflow_note.setWordWrap(True)
        self.game_workflow_note.setFixedHeight(42)
        game_layout.addWidget(self.game_workflow_note, 6, 0, 1, 2)
        game_layout.setRowStretch(7, 1)

        # Build the hidden page from the known application language catalog.
        # Probing EasyOCR/Tesseract packages before Settings has even painted
        # was the visible pause reported by users; exact availability is
        # reconciled lazily when the Dynamic page is opened.
        self._populate_game_language_controls(fast=True)
        self.game_source_combo.currentIndexChanged.connect(self._game_source_changed)
        self.game_target_combo.currentIndexChanged.connect(self._save_game_language_pair)
        self.game_swap_button.clicked.connect(self._swap_game_languages)
        self.game_scan_interval_slider.valueChanged.connect(
            self._save_game_scan_interval
        )
        self.game_overlay_opacity_slider.valueChanged.connect(
            self._save_game_overlay_opacity
        )
        self.game_pause_inactive_checkbox.toggled.connect(
            lambda state: self.auto_save_setting("game_pause_when_inactive", bool(state))
        )
        self.game_show_original_checkbox.toggled.connect(
            lambda state: self.auto_save_setting("game_show_original_text", bool(state))
        )
        self.settings_game_page.hide()

        # --- Переключатель страниц ---
        # The version moved to the persistent FAQ header.  Only the dots use
        # this space now, so the connected buttons retain their lower border.
        self.settings_page_footer = QWidget(self)
        dots_layout = QHBoxLayout(self.settings_page_footer)
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(0)
        dots_layout.setAlignment(Qt.AlignCenter)
        self.settings_page_dots = []
        dark = self.parent.current_theme != "Светлая"
        for index, text_key in enumerate((
            "settings_page_main",
            "settings_page_updates",
            "settings_page_game",
        )):
            dot = SettingsPageDotButton(self.settings_page_footer, dark=dark)
            dot.setAccessibleName(settings_text(lang, text_key))
            dot.setToolTip(tooltip_text(settings_text(lang, text_key)))
            dot.clicked.connect(
                lambda _checked=False, page_index=index: self._set_settings_page(page_index)
            )
            dots_layout.addWidget(dot)
            self.settings_page_dots.append(dot)
        self.settings_page_footer.setFixedHeight(16)
        self.main_layout.addStretch()
        self._position_settings_updates_page()
        self._set_settings_page(page_to_restore)
        QtCore.QTimer.singleShot(0, self._position_settings_updates_page)

    def _set_settings_page(self, index):
        updates_page = getattr(self, "settings_updates_page", None)
        game_page = getattr(self, "settings_game_page", None)
        if updates_page is None or game_page is None:
            return
        index = max(0, min(int(index), 2))
        self._settings_page_index = index
        action_panel = getattr(self, "settings_action_panel", None)
        if index:
            if action_panel is not None:
                action_panel.hide()
            self._position_settings_updates_page()
        else:
            if action_panel is not None:
                action_panel.show()
                action_panel.raise_()
        updates_page.setVisible(index == 1)
        game_page.setVisible(index == 2)
        if index == 1:
            updates_page.raise_()
        elif index == 2:
            game_page.raise_()
            # Paint the page before reconciling optional OCR packages.  The
            # user sees an immediate page change even on machines where
            # loading flag icons or probing EasyOCR is slow.
            QtCore.QTimer.singleShot(80, self._verify_game_language_controls)
        footer = getattr(self, "settings_page_footer", None)
        if footer is not None:
            footer.show()
            footer.raise_()
        for dot_index, dot in enumerate(getattr(self, "settings_page_dots", ())):
            dot.setChecked(dot_index == index)
        complete = getattr(self.parent, "_complete_guide_step", None)
        if callable(complete):
            complete({0: "settings_page_main", 1: "settings_page_updates", 2: "settings_page_game"}[index])

    def _position_settings_updates_page(self):
        overlay = getattr(self, "settings_updates_page", None)
        game_page = getattr(self, "settings_game_page", None)
        footer = getattr(self, "settings_page_footer", None)
        if overlay is None or game_page is None or footer is None:
            return
        margins = self.main_layout.contentsMargins()
        top = margins.top()
        left = margins.left()
        right = self.width() - margins.right()
        footer_top = self.height() - margins.bottom() - footer.height()
        footer.setGeometry(
            left,
            footer_top,
            max(0, right - left),
            footer.height(),
        )
        footer_layout = footer.layout()
        if footer_layout is not None:
            footer_layout.invalidate()
            footer_layout.activate()
        fixed_gap = 6
        action_panel = getattr(self, "settings_action_panel", None)
        if action_panel is not None:
            action_top = footer_top - fixed_gap - action_panel.height()
            action_panel.setGeometry(
                left,
                action_top,
                max(0, right - left),
                action_panel.height(),
            )
        bottom = max(top, footer_top - fixed_gap)
        overlay.setGeometry(left, top, max(0, right - left), max(0, bottom - top))
        game_page.setGeometry(left, top, max(0, right - left), max(0, bottom - top))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_settings_updates_page()

    def set_language_package_task_status(self, text="", percent=None, kind="running"):
        """Keep a background package job visible after its dialog is hidden.

        A system notification would reintroduce the Windows notification sound
        that this app deliberately avoids. The settings button is always the
        route back to the package manager, so it carries the quiet persistent
        state instead.
        """
        self._language_package_task_state = {
            "text": str(text or ""),
            "percent": None if percent is None else max(0, min(100, int(percent))),
            "kind": str(kind or "idle"),
        }
        self._apply_language_package_task_status()

    def _apply_language_package_task_status(self):
        button = getattr(self, "ocr_languages_btn", None)
        if button is None:
            return
        lang = getattr(self.parent, "current_interface_language", "en")
        base = settings_text(lang, "ocr_language_packs")
        state = dict(getattr(self, "_language_package_task_state", {}) or {})
        kind = state.get("kind", "idle")
        if kind in {"running", "done", "failed"}:
            # The normal label fills almost the whole one-third-width button.
            # Status text used to push its first/last letters outside the fixed
            # window, so active badges use a deliberately short localized base.
            base = language_manager_text(lang, "task_packages_short")
        if kind == "running":
            # A package task can expose a download percentage and a separate
            # DISM component percentage. Neither is whole-job progress, so the
            # Settings button advertises the state, not a misleading number.
            suffix = " · " + language_manager_text(lang, "task_installing_short")
        elif kind == "done":
            suffix = " · " + engine_text(lang, "done")
        elif kind == "failed":
            suffix = " · !"
        else:
            suffix = ""
        button.setText(base + suffix)
        button.setProperty("packageTaskDone", kind == "done")
        # Dynamic Qt properties do not automatically trigger a stylesheet
        # recalculation.
        button.style().unpolish(button)
        button.style().polish(button)
        help_text = settings_text(lang, "manage_ocr_languages")
        detail = str(state.get("text") or "").strip()
        button.setToolTip(tooltip_text(f"{help_text}\n{detail}" if detail else help_text))
        button.setAccessibleDescription(detail or help_text)

    def show_ocr_language_manager(self):
        # Completion is an unread badge until the user follows it. Opening the
        # package manager acknowledges it; ongoing and failed work remains
        # visible until it is actually resolved.
        state = dict(getattr(self, "_language_package_task_state", {}) or {})
        if state.get("kind") == "done":
            self.set_language_package_task_status(kind="idle")
        complete_guide_step = getattr(self.parent, "_complete_guide_step", None)
        if callable(complete_guide_step):
            complete_guide_step("language_packages")
        dialog = self._language_manager_dialog
        # Its text is built once, from the language it was created with, so a
        # dialog from before a language switch has to be replaced rather than
        # reused.
        if dialog is not None:
            try:
                stale = dialog.lang != getattr(self.parent, "current_interface_language", "en")
            except RuntimeError:
                stale = True
            if stale and not getattr(dialog, "_install_in_progress", False):
                try:
                    dialog.close()
                    dialog.deleteLater()
                except RuntimeError:
                    pass
                dialog = None
                self._language_manager_dialog = None
        if dialog is None:
            dialog = OcrLanguageManagerDialog(self)
            self._language_manager_dialog = dialog
        elif not getattr(dialog, "_install_in_progress", False):
            dialog.refresh_all()
            dialog._start_runtime_probe()
            if dialog.argos_table.isVisible():
                dialog._start_argos_catalog_refresh(False)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _fit_copy_translated_checkbox(self):
        """Give the box room for its own label.

        It shares a row with the Show-window picker, so anything past its width
        is drawn over by that control — which is how "Копировать сразу
        переведённый текст" ended up cut off. 260px is kept as a floor so the
        English window looks exactly as it did.
        """
        box = getattr(self, "copy_translated_checkbox", None)
        if box is None:
            return
        try:
            box.setMinimumWidth(max(260, box.sizeHint().width()))
        except RuntimeError:
            pass

    def _apply_engine_combo_style(self, combo):
        if combo is None:
            return
        combo.setStyleSheet(self._engine_combo_style())
        if isinstance(combo, DropDownCombo):
            dark = getattr(getattr(self, "parent", None), "current_theme", "") != "Светлая"
            combo.set_popup_background("#20212a" if dark else "#f1edf4")

    def _apply_game_language_combo_style(self, combo):
        """Keep the two-letter language code visible in the compact pair."""
        if combo is None:
            return
        dark = getattr(getattr(self, "parent", None), "current_theme", "") != "Светлая"
        combo.setStyleSheet(
            modern_combo_style(dark, font_size=13)
            + """
                QComboBox {
                    margin: 2px 0px;
                    padding: 3px 19px 3px 5px;
                }
                QComboBox::drop-down { width: 18px; }
            """
        )
        if isinstance(combo, DropDownCombo):
            combo.set_popup_background("#20212a" if dark else "#f1edf4")

    def _engine_combo_style(self):
        is_dark = getattr(getattr(self, "parent", None), "current_theme", "") != "Светлая"
        return modern_combo_style(is_dark)

    def _secondary_palette(self):
        if self.parent.current_theme == "Темная":
            return {
                "surface": "#111218",
                "card": "#181820",
                "field": "#0c0d13",
                "field_alt": "#211a2b",
                "text": "#f7f3ff",
                "muted": "#aaa0b8",
                "border": "#393243",
                "soft_border": "#2b2733",
                "accent": "#a98bd7",
                "accent_hover": "#b99be8",
                "danger": "#d85b64",
                "danger_hover": "#e66b74",
                "scroll": "#6f5a8c",
            }
        return {
            "surface": "#ece7f0",
            "card": "#f3eff5",
            "field": "#e5dfe9",
            "field_alt": "#ddd3e5",
            "text": "#241d2d",
            "muted": "#756b80",
            "border": "#d5cae2",
            "soft_border": "#e8e0ef",
            "accent": "#76599d",
            "accent_hover": "#8566ad",
            "danger": "#c94e58",
            "danger_hover": "#dc5d67",
            "scroll": "#9b84b8",
        }

    def _secondary_view_stylesheet(self):
        colors = self._secondary_palette()
        return f"""
            QFrame#secondaryViewShell {{
                background-color: {colors['surface']};
                border: 1px solid {colors['soft_border']};
                border-radius: 12px;
            }}
            QFrame#secondaryViewShell QLabel {{
                background: transparent;
                border: none;
                color: {colors['text']};
            }}
            QLabel#secondaryTitle {{
                color: {colors['text']};
                font-size: 21px;
                font-weight: 800;
            }}
            QLabel#secondaryHint {{
                color: {colors['muted']};
                font-size: 12px;
            }}
            QLabel#secondaryCount {{
                color: {colors['accent']};
                background-color: {colors['card']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
                padding: 3px 9px;
                font-size: 12px;
                font-weight: 700;
            }}
            QFrame#secondaryCard {{
                background-color: {colors['card']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
            }}
            QLabel#secondaryFieldLabel {{
                color: {colors['text']};
                font-size: 14px;
                font-weight: 600;
                padding-left: 2px;
            }}
            QKeySequenceEdit#secondaryHotkeyInput {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
            QKeySequenceEdit#secondaryHotkeyInput QLineEdit {{
                background-color: {colors['field']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 14px;
                font-weight: 700;
                selection-background-color: {colors['accent']};
                selection-color: #ffffff;
            }}
            QKeySequenceEdit#secondaryHotkeyInput QLineEdit:focus {{
                border: 1px solid {colors['accent']};
            }}
            QScrollArea#historyScroll {{
                background: transparent;
                border: none;
            }}
            QWidget#historyScrollContent {{
                background: transparent;
            }}
            QFrame#historyRecordCard {{
                background-color: {colors['card']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
            }}
            QLabel#historyMeta {{
                color: {colors['muted']};
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#historyLanguageBadge {{
                color: {colors['accent']};
                background-color: {colors['field']};
                border: 1px solid {colors['soft_border']};
                border-radius: 7px;
                padding: 2px 7px;
                font-size: 11px;
                font-weight: 800;
            }}
            QLabel#historySectionCaption {{
                color: {colors['muted']};
                font-size: 10px;
                font-weight: 800;
                padding-left: 2px;
            }}
            QFrame#historyTextBlock {{
                background-color: {colors['field']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
            QFrame#historyTextBlock[translated="true"] {{
                background-color: {colors['field_alt']};
                border: 1px solid {colors['accent']};
            }}
            QLabel#historyRecordOriginal,
            QLabel#historyRecordTranslated,
            QLabel#historyRecordText {{
                background: transparent;
                color: {colors['text']};
                border: none;
                padding: 1px;
                font-family: 'Segoe UI';
                font-size: 15px;
            }}
            QLabel#historyRecordTranslated {{
                font-weight: 700;
            }}
            QLabel#historyEmptyState {{
                color: {colors['muted']};
                font-size: 14px;
                padding: 44px 12px;
            }}
            QPushButton#historyCopyButton,
            QPushButton#historyDeleteButton {{
                background: transparent;
                border: 1px solid {colors['border']};
                border-radius: 7px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton#historyCopyButton {{ color: {colors['accent']}; }}
            QPushButton#historyCopyButton:hover {{
                color: #ffffff;
                background-color: {colors['accent']};
            }}
            QPushButton#historyDeleteButton {{ color: {colors['danger']}; }}
            QPushButton#historyDeleteButton:hover {{
                color: #ffffff;
                background-color: {colors['danger']};
            }}
            QPushButton#secondaryBackButton {{
                background-color: {colors['accent']};
                color: #ffffff;
                border: none;
                border-radius: 9px;
                padding: 7px 22px;
                font-size: 14px;
                font-weight: 800;
            }}
            QPushButton#secondaryBackButton:hover {{
                background-color: {colors['accent_hover']};
            }}
            QPushButton#secondaryClearButton {{
                background-color: transparent;
                color: {colors['danger']};
                border: 1px solid {colors['danger']};
                border-radius: 9px;
                padding: 7px 16px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton#secondaryClearButton:hover {{
                background-color: {colors['danger_hover']};
                color: #ffffff;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 4px 1px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors['scroll']};
                min-height: 30px;
                border-radius: 4px;
                margin: 1px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {colors['accent']};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
                background: transparent;
                border: none;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """

    def _create_secondary_shell(self, title, count_label=None):
        shell = QFrame()
        shell.setObjectName("secondaryViewShell")
        shell.setStyleSheet(self._secondary_view_stylesheet())
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(14, 10, 14, 10)
        shell_layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 2, 0)
        title_label = QLabel(title)
        title_label.setObjectName("secondaryTitle")
        header.addWidget(title_label, 1)
        if count_label is not None:
            count_label.setObjectName("secondaryCount")
            count_label.setAlignment(Qt.AlignCenter)
            header.addWidget(count_label, 0, Qt.AlignVCenter)
        shell_layout.addLayout(header)

        self.secondary_view_shell = shell
        self.secondary_title_label = title_label
        self.main_layout.addWidget(shell)
        return shell_layout

    @staticmethod
    def _configure_secondary_button(button, object_name):
        button.setObjectName(object_name)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedHeight(38)

    def _refresh_secondary_view_theme(self):
        shell = getattr(self, "secondary_view_shell", None)
        if shell is None:
            return
        try:
            shell.setStyleSheet(self._secondary_view_stylesheet())
        except RuntimeError:
            self.secondary_view_shell = None

    def show_hotkeys_screen(self):
        self.setup_new_layout()
        self.hotkeys_mode = True
        self._secondary_view_kind = "hotkeys"
        self.main_layout.setContentsMargins(10, 7, 10, 7)
        self.main_layout.setSpacing(0)

        lang = self.parent.current_interface_language
        shell_layout = self._create_secondary_shell(settings_text(lang, "hotkeys"))

        hotkey_card = QFrame()
        hotkey_card.setObjectName("secondaryCard")
        hotkey_grid = QGridLayout(hotkey_card)
        hotkey_grid.setContentsMargins(12, 9, 12, 9)
        hotkey_grid.setHorizontalSpacing(14)
        # The shell has 320 logical pixels in the fixed main window. Six 36 px
        # fields plus five 7 px gaps and the card margins need 269 px, while Qt
        # can give the card only 219 px. It consequently placed rows 34–35 px
        # apart and their 36 px rounded frames overlapped. Keep a deliberate,
        # visible 4 px gutter and size the card to the exact non-overlapping
        # requirement. Seven 27 px rows plus six 3 px gaps and the card
        # margins need 225 px; this still fits without adding a scrollbar.
        hotkey_grid.setVerticalSpacing(3)
        hotkey_grid.setColumnStretch(0, 1)
        hotkey_grid.setColumnMinimumWidth(1, 230)
        hotkey_card.setFixedHeight(227)
        self.hotkey_card = hotkey_card

        self.copy_hotkey_input = ClearableKeySequenceEdit()
        saved_copy_hotkey = self.parent.config.get("copy_hotkey", "")
        self.copy_hotkey_input.setKeySequence(QKeySequence(saved_copy_hotkey))
        self.translate_hotkey_input = ClearableKeySequenceEdit()
        saved_translate_hotkey = self.parent.config.get("translate_hotkey", "")
        self.translate_hotkey_input.setKeySequence(QKeySequence(saved_translate_hotkey))
        self.fullscreen_translate_hotkey_input = ClearableKeySequenceEdit()
        saved_fs_hotkey = self.parent.config.get("fullscreen_translate_hotkey", "")
        self.fullscreen_translate_hotkey_input.setKeySequence(QKeySequence(saved_fs_hotkey))
        self.translate_selection_hotkey_input = ClearableKeySequenceEdit()
        saved_sel_hotkey = self.parent.config.get("translate_selection_hotkey", "")
        self.translate_selection_hotkey_input.setKeySequence(QKeySequence(saved_sel_hotkey))
        self.translate_replace_selection_hotkey_input = ClearableKeySequenceEdit()
        saved_replace_hotkey = self.parent.config.get(
            "translate_replace_selection_hotkey", ""
        )
        self.translate_replace_selection_hotkey_input.setKeySequence(
            QKeySequence(saved_replace_hotkey)
        )
        if platform_support.IS_LINUX:
            self.translate_replace_selection_hotkey_input.setEnabled(False)
            self.translate_replace_selection_hotkey_input.setToolTip(
                settings_text(lang, "replace_selection_unavailable")
            )
        self.toggle_window_hotkey_input = ClearableKeySequenceEdit()
        saved_toggle_hotkey = self.parent.config.get("toggle_window_hotkey", "")
        self.toggle_window_hotkey_input.setKeySequence(QKeySequence(saved_toggle_hotkey))
        self.game_translate_hotkey_input = ClearableKeySequenceEdit()
        saved_game_hotkey = self.parent.config.get("game_translate_hotkey", "")
        self.game_translate_hotkey_input.setKeySequence(QKeySequence(saved_game_hotkey))

        hotkey_rows = (
            (settings_text(lang, "copy_hotkey_label"), self.copy_hotkey_input),
            (settings_text(lang, "translate_hotkey_label"), self.translate_hotkey_input),
            (settings_text(lang, "fullscreen_translate_label"), self.fullscreen_translate_hotkey_input),
            (settings_text(lang, "selection_translate_label"), self.translate_selection_hotkey_input),
            (settings_text(lang, "replace_selection_translate_label"), self.translate_replace_selection_hotkey_input),
            (settings_text(lang, "game_translate_label"), self.game_translate_hotkey_input),
            (settings_text(lang, "toggle_window_hotkey_label"), self.toggle_window_hotkey_input),
        )
        self.hotkey_labels = []
        for row, (label_text, key_input) in enumerate(hotkey_rows):
            label = QLabel(label_text.rstrip(":"))
            label.setObjectName("secondaryFieldLabel")
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label.setFixedHeight(27)
            key_input.setObjectName("secondaryHotkeyInput")
            key_input.setFixedHeight(27)
            key_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            hotkey_grid.addWidget(label, row, 0)
            hotkey_grid.addWidget(key_input, row, 1)
            if key_input is self.translate_replace_selection_hotkey_input and platform_support.IS_LINUX:
                label.setToolTip(settings_text(lang, "replace_selection_unavailable"))
            self.hotkey_labels.append(label)
        shell_layout.addWidget(hotkey_card)

        self.copy_hotkey_input.keySequenceChanged.connect(self.save_copy_hotkey)
        self.translate_hotkey_input.keySequenceChanged.connect(self.save_translate_hotkey)
        self.fullscreen_translate_hotkey_input.keySequenceChanged.connect(self.save_fullscreen_translate_hotkey)
        self.translate_selection_hotkey_input.keySequenceChanged.connect(self.save_translate_selection_hotkey)
        self.translate_replace_selection_hotkey_input.keySequenceChanged.connect(
            self.save_translate_replace_selection_hotkey
        )
        self.toggle_window_hotkey_input.keySequenceChanged.connect(self.save_toggle_window_hotkey)
        self.game_translate_hotkey_input.keySequenceChanged.connect(self.save_game_translate_hotkey)

        remove_label = QLabel(settings_text(lang, "remove_hotkey"))
        remove_label.setObjectName("secondaryHint")
        remove_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.hotkey_hint_label = remove_label

        back_button = QPushButton(settings_text(lang, "back"))
        self._configure_secondary_button(back_button, "secondaryBackButton")
        back_button.clicked.connect(self.back_from_hotkeys)
        self.hotkey_back_button = back_button

        footer = QHBoxLayout()
        footer.setContentsMargins(2, 0, 2, 0)
        footer.addWidget(remove_label, 1)
        footer.addWidget(back_button, 0)
        shell_layout.addLayout(footer)

        self._refresh_secondary_view_theme()
        if hasattr(self.parent, "_complete_guide_step"):
            self.parent._complete_guide_step("hotkeys")

    def focus_hotkey_setting(self, config_key):
        """Open the hotkey page and focus the field named by its config key."""
        if not getattr(self, "hotkeys_mode", False):
            self.show_hotkeys_screen()
        field_names = {
            "copy_hotkey": "copy_hotkey_input",
            "translate_hotkey": "translate_hotkey_input",
            "fullscreen_translate_hotkey": "fullscreen_translate_hotkey_input",
            "translate_selection_hotkey": "translate_selection_hotkey_input",
            "translate_replace_selection_hotkey": "translate_replace_selection_hotkey_input",
            "game_translate_hotkey": "game_translate_hotkey_input",
            "toggle_window_hotkey": "toggle_window_hotkey_input",
        }
        field = getattr(self, field_names.get(str(config_key), ""), None)
        if field is None:
            return False

        def activate_field():
            try:
                field.setFocus(Qt.OtherFocusReason)
                editor = field.findChild(QLineEdit)
                if editor is not None:
                    editor.selectAll()
            except RuntimeError:
                pass

        QtCore.QTimer.singleShot(0, activate_field)
        return True

    def save_copy_hotkey(self):
        hotkey_str = self.copy_hotkey_input.keySequence().toString()
        self.parent.config["copy_hotkey"] = hotkey_str
        self.parent.save_config()
        if platform_support.IS_LINUX:
            return
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
        if platform_support.IS_LINUX:
            return
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
        if platform_support.IS_LINUX:
            return
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
        if platform_support.IS_LINUX:
            return
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

    def save_translate_replace_selection_hotkey(self):
        hotkey_str = self.translate_replace_selection_hotkey_input.keySequence().toString()
        self.parent.config["translate_replace_selection_hotkey"] = hotkey_str
        self.parent.save_config()
        if platform_support.IS_LINUX:
            return
        thread = getattr(self.parent, "translate_replace_selection_hotkey_thread", None)
        if thread is not None:
            try:
                thread.stop()
                thread.join(timeout=0.5)
            except Exception as exc:
                print(f"Error stopping replace-selection hotkey thread: {exc}")
            self.parent.translate_replace_selection_hotkey_thread = None
        if hotkey_str:
            self.parent.translate_replace_selection_hotkey_thread = self.parent.HotkeyListenerThread(
                hotkey_str,
                self.parent.launch_translate_replace_selection,
                hotkey_id=6,
            )
            self.parent.translate_replace_selection_hotkey_thread.start()

    def save_toggle_window_hotkey(self):
        hotkey_str = self.toggle_window_hotkey_input.keySequence().toString()
        self.parent.config["toggle_window_hotkey"] = hotkey_str
        self.parent.save_config()
        if platform_support.IS_LINUX:
            return
        thread = getattr(self.parent, "toggle_window_hotkey_thread", None)
        if thread is not None:
            try:
                thread.stop()
                thread.join(timeout=0.5)
            except Exception as exc:
                print(f"Error stopping window toggle hotkey thread: {exc}")
            self.parent.toggle_window_hotkey_thread = None
        if hotkey_str:
            self.parent.toggle_window_hotkey_thread = self.parent.HotkeyListenerThread(
                hotkey_str,
                self.parent.toggle_window_visibility,
                hotkey_id=5,
            )
            self.parent.toggle_window_hotkey_thread.start()

    def save_game_translate_hotkey(self):
        hotkey_str = self.game_translate_hotkey_input.keySequence().toString()
        self.parent.config["game_translate_hotkey"] = hotkey_str
        self.parent.save_config()
        if hasattr(self.parent, "refresh_interface_language_ui"):
            self.parent.refresh_interface_language_ui()
        if platform_support.IS_LINUX:
            return
        thread = getattr(self.parent, "game_translate_hotkey_thread", None)
        if thread is not None:
            try:
                thread.stop()
                thread.join(timeout=0.5)
            except Exception as exc:
                print(f"Error stopping dynamic translation hotkey thread: {exc}")
            self.parent.game_translate_hotkey_thread = None
        if hotkey_str:
            self.parent.game_translate_hotkey_thread = self.parent.HotkeyListenerThread(
                hotkey_str,
                self.parent.launch_game_translate,
                hotkey_id=7,
            )
            self.parent.game_translate_hotkey_thread.start()

    def back_from_hotkeys(self):
        self.init_ui()
        self.apply_theme()

    def show_history_view(self):
        self.clear_main_layout()
        self.hotkeys_mode = False
        self._secondary_view_kind = "history"
        self.main_layout.setContentsMargins(10, 7, 10, 7)
        self.main_layout.setSpacing(0)
        lang = self.parent.current_interface_language

        self.history_count_label = QLabel("0")
        shell_layout = self._create_secondary_shell(
            settings_text(lang, "history_title"),
            self.history_count_label,
        )

        self.history_scroll_area, self.history_cards_layout = self._create_history_scroll()
        shell_layout.addWidget(self.history_scroll_area, 1)
        self.load_history_embedded()

        clear_button = QPushButton(settings_text(lang, "clear_translation_history"))
        self._configure_secondary_button(clear_button, "secondaryClearButton")
        clear_button.clicked.connect(self.clear_history)
        back_button = QPushButton(settings_text(lang, "back"))
        self._configure_secondary_button(back_button, "secondaryBackButton")
        back_button.clicked.connect(self.back_from_history)
        self.history_clear_button = clear_button
        self.history_back_button = back_button

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addWidget(clear_button, 0)
        footer.addStretch(1)
        footer.addWidget(back_button, 0)
        shell_layout.addLayout(footer)
        self._refresh_secondary_view_theme()

    def _create_history_scroll(self):
        scroll = QScrollArea()
        scroll.setObjectName("historyScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMinimumHeight(190)

        content = QWidget()
        content.setObjectName("historyScrollContent")
        cards_layout = QVBoxLayout(content)
        cards_layout.setContentsMargins(0, 0, 4, 0)
        cards_layout.setSpacing(8)
        scroll.setWidget(content)
        return scroll, cards_layout

    def _clear_history_cards(self, cards_layout):
        while cards_layout.count():
            item = cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self.clear_nested_layout(item.layout())

    @staticmethod
    def _format_history_timestamp(value):
        try:
            from datetime import datetime
            return datetime.fromisoformat(str(value or "")).strftime("%d.%m.%Y  ·  %H:%M")
        except Exception:
            return str(value or "")

    @staticmethod
    def _history_label(text, object_name):
        label = QLabel(str(text or ""))
        label.setObjectName(object_name)
        label.setTextFormat(Qt.PlainText)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        return label

    def _add_history_field(
        self,
        card_layout,
        caption,
        text,
        object_name,
        record_index,
        copy_mode,
        field_name,
        translated=False,
    ):
        lang = self.parent.current_interface_language
        if caption:
            caption_label = QLabel(caption)
            caption_label.setObjectName("historySectionCaption")
            card_layout.addWidget(caption_label)

        text_block = QFrame()
        text_block.setObjectName("historyTextBlock")
        text_block.setProperty("translated", bool(translated))
        text_layout = QVBoxLayout(text_block)
        text_layout.setContentsMargins(10, 8, 10, 8)
        text_layout.setSpacing(0)
        text_layout.addWidget(self._history_label(text, object_name))
        card_layout.addWidget(text_block)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 2)
        action_row.setSpacing(6)
        action_row.addStretch(1)
        copy_button = QPushButton(history_record_text(lang, "copy"))
        copy_button.setObjectName("historyCopyButton")
        copy_button.setProperty("historyField", field_name)
        copy_button.setCursor(Qt.PointingHandCursor)
        copy_button.setMinimumHeight(28)
        copy_button.clicked.connect(
            lambda _checked=False, value=str(text or ""): QApplication.clipboard().setText(value)
        )
        delete_button = QPushButton(history_record_text(lang, "delete"))
        delete_button.setObjectName("historyDeleteButton")
        delete_button.setProperty("recordIndex", record_index)
        delete_button.setProperty("historyField", field_name)
        delete_button.setCursor(Qt.PointingHandCursor)
        delete_button.setMinimumHeight(28)
        delete_button.clicked.connect(
            lambda _checked=False, index=record_index, mode=copy_mode: self._delete_history_record(mode, index)
        )
        action_row.addWidget(copy_button)
        action_row.addWidget(delete_button)
        card_layout.addLayout(action_row)

    def _add_history_record_card(self, cards_layout, record, record_index, copy_mode=False):
        if not isinstance(record, dict):
            record = {"text": str(record or "")}
        lang = self.parent.current_interface_language

        card = QFrame()
        card.setObjectName("historyRecordCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(11, 9, 11, 9)
        card_layout.setSpacing(5)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(7)
        language = str(record.get("language", "") or "").upper()
        if language and not copy_mode:
            language_badge = QLabel(language)
            language_badge.setObjectName("historyLanguageBadge")
            meta_row.addWidget(language_badge, 0, Qt.AlignLeft | Qt.AlignVCenter)
        meta_row.addStretch(1)
        date_label = QLabel(self._format_history_timestamp(record.get("timestamp", "")))
        date_label.setObjectName("historyMeta")
        date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        meta_row.addWidget(date_label, 0, Qt.AlignRight | Qt.AlignVCenter)
        card_layout.addLayout(meta_row)

        if copy_mode:
            self._add_history_field(
                card_layout,
                "",
                record.get("text", ""),
                "historyRecordText",
                record_index,
                True,
                "text",
            )
        elif "original" in record or "translated" in record:
            self._add_history_field(
                card_layout,
                history_record_text(lang, "original"),
                record.get("original", ""),
                "historyRecordOriginal",
                record_index,
                False,
                "original",
            )
            self._add_history_field(
                card_layout,
                history_record_text(lang, "translated"),
                record.get("translated", ""),
                "historyRecordTranslated",
                record_index,
                False,
                "translated",
                translated=True,
            )
        else:
            self._add_history_field(
                card_layout,
                "",
                record.get("text", ""),
                "historyRecordText",
                record_index,
                False,
                "text",
            )
        cards_layout.addWidget(card)
        return card

    def _populate_history_cards(self, records, copy_mode=False):
        records = records if isinstance(records, list) else []
        cards_layout = self.copy_history_cards_layout if copy_mode else self.history_cards_layout
        count_label = self.copy_history_count_label if copy_mode else self.history_count_label
        self._clear_history_cards(cards_layout)
        count_label.setText(str(len(records)))
        cards = []
        if not records:
            empty_label = QLabel(settings_text(self.parent.current_interface_language, "history_empty"))
            empty_label.setObjectName("historyEmptyState")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setWordWrap(True)
            cards_layout.addWidget(empty_label)
        else:
            for record_index, record in reversed(list(enumerate(records))):
                cards.append(
                    self._add_history_record_card(
                        cards_layout,
                        record,
                        record_index,
                        copy_mode,
                    )
                )
        cards_layout.addStretch(1)
        if copy_mode:
            self.copy_history_record_cards = cards
        else:
            self.history_record_cards = cards

    @staticmethod
    def _write_history_records(history_file, records):
        target = Path(history_file)
        temporary = target.with_name(target.name + ".tmp")
        try:
            temporary.write_text(
                json.dumps(records, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
            os.replace(str(temporary), str(target))
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _delete_history_record(self, copy_mode, record_index):
        history_file = get_data_file("copy_history.json" if copy_mode else "translation_history.json")
        ensure_json_file(history_file, [])
        try:
            with open(history_file, "r", encoding="utf-8") as stream:
                records = json.load(stream)
            records = records if isinstance(records, list) else []
            if 0 <= int(record_index) < len(records):
                records.pop(int(record_index))
                self._write_history_records(history_file, records)
            if copy_mode:
                self.load_copy_history_embedded()
            else:
                self.load_history_embedded()
        except Exception:
            lang = self.parent.current_interface_language
            QMessageBox.warning(
                self,
                settings_text(lang, "error_title"),
                settings_text(
                    lang,
                    "clear_copy_history_error" if copy_mode else "clear_translation_history_error",
                ),
            )

    def load_history_embedded(self):
        history_file = get_data_file("translation_history.json")
        ensure_json_file(history_file, [])
        lang = self.parent.current_interface_language
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
            history = history if isinstance(history, list) else []
            self._populate_history_cards(history)
        except Exception:
            self.history_count_label.setText("!")
            self._clear_history_cards(self.history_cards_layout)
            error_label = QLabel(settings_text(lang, "history_error"))
            error_label.setObjectName("historyEmptyState")
            error_label.setAlignment(Qt.AlignCenter)
            self.history_cards_layout.addWidget(error_label)
            self.history_cards_layout.addStretch(1)

    def clear_history(self):
        history_file = get_data_file("translation_history.json")
        ensure_json_file(history_file, [])
        try:
            self._write_history_records(history_file, [])
            self.load_history_embedded()
        except Exception:
            lang = self.parent.current_interface_language
            QMessageBox.warning(
                self,
                settings_text(lang, "error_title"),
                settings_text(lang, "clear_translation_history_error"),
            )

    def back_from_history(self):
        self.init_ui()
        self.apply_theme()

    def show_copy_history_view(self):
        self.clear_main_layout()
        self.hotkeys_mode = False
        self._secondary_view_kind = "copy_history"
        self.main_layout.setContentsMargins(10, 7, 10, 7)
        self.main_layout.setSpacing(0)
        lang = self.parent.current_interface_language

        self.copy_history_count_label = QLabel("0")
        shell_layout = self._create_secondary_shell(
            settings_text(lang, "copy_history_title"),
            self.copy_history_count_label,
        )

        self.copy_history_scroll_area, self.copy_history_cards_layout = self._create_history_scroll()
        shell_layout.addWidget(self.copy_history_scroll_area, 1)
        self.load_copy_history_embedded()

        clear_button = QPushButton(settings_text(lang, "clear_copy_history"))
        self._configure_secondary_button(clear_button, "secondaryClearButton")
        clear_button.clicked.connect(self.clear_copy_history)
        back_button = QPushButton(settings_text(lang, "back"))
        self._configure_secondary_button(back_button, "secondaryBackButton")
        back_button.clicked.connect(self.back_from_copy_history)
        self.copy_history_clear_button = clear_button
        self.copy_history_back_button = back_button

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addWidget(clear_button, 0)
        footer.addStretch(1)
        footer.addWidget(back_button, 0)
        shell_layout.addLayout(footer)
        self._refresh_secondary_view_theme()

    def load_copy_history_embedded(self):
        history_file = get_data_file("copy_history.json")
        ensure_json_file(history_file, [])
        lang = self.parent.current_interface_language
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
            history = history if isinstance(history, list) else []
            self._populate_history_cards(history, copy_mode=True)
        except Exception:
            self.copy_history_count_label.setText("!")
            self._clear_history_cards(self.copy_history_cards_layout)
            error_label = QLabel(settings_text(lang, "history_error"))
            error_label.setObjectName("historyEmptyState")
            error_label.setAlignment(Qt.AlignCenter)
            self.copy_history_cards_layout.addWidget(error_label)
            self.copy_history_cards_layout.addStretch(1)

    def clear_copy_history(self):
        history_file = get_data_file("copy_history.json")
        ensure_json_file(history_file, [])
        try:
            self._write_history_records(history_file, [])
            self.load_copy_history_embedded()
        except Exception:
            lang = self.parent.current_interface_language
            QMessageBox.warning(
                self,
                settings_text(lang, "error_title"),
                settings_text(lang, "clear_copy_history_error"),
            )

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

        if portable_paths.is_windows_packaged():
            if not QDesktopServices.openUrl(QUrl(MICROSOFT_STORE_UPDATES_URI)):
                QMessageBox.information(
                    self,
                    settings_text(lang, "update"),
                    update_text(lang, "store_updates"),
                )
            return

        if not getattr(sys, "frozen", False):
            msg = QMessageBox(self)
            msg.setWindowTitle(settings_text(lang, "update"))
            msg.setText(update_text(lang, "dev_build"))
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
        lang = self.parent.current_interface_language
        self._set_parent_update_flow_active(True)
        self._update_cancel_requested.clear()
        self._update_phase = "checking"
        self._update_temp_dir = ""
        self._set_update_controls_enabled(False, update_text(lang, "checking_button"))
        self._show_update_progress(update_text(lang, "checking"))
        self._update_in_progress = True

        worker = threading.Thread(target=self._check_latest_release_worker, daemon=True)
        worker.start()

    def _set_parent_update_flow_active(self, active):
        parent = getattr(self, "parent", None)
        if parent is not None:
            parent._update_flow_active = bool(active)

    def _set_update_controls_enabled(self, enabled, text=None):
        if not hasattr(self, "update_btn"):
            return
        if text is None:
            text = settings_text(self.parent.current_interface_language, "update")
        self.update_btn.setEnabled(enabled)
        self.update_btn.setText(text)

    def _show_update_progress(self, text, determinate=False, value=0):
        title = settings_text(self.parent.current_interface_language, "update")
        if not hasattr(self, "_update_progress") or self._update_progress is None:
            self._update_progress = UpdateProgressDialog(self)
            self._update_progress.setWindowTitle(title)
            self._update_progress.setCancelButtonText(settings_text(self.parent.current_interface_language, "cancel"))
            self._update_progress.setWindowModality(Qt.NonModal)
            self._update_progress.setAutoClose(False)
            self._update_progress.setAutoReset(False)
            self._update_progress.setMinimumDuration(0)
            self._update_progress.setMinimumWidth(430)
            self._update_progress.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            try:
                owner_window = self.window()
                owner_center = owner_window.frameGeometry().center()
                progress_frame = self._update_progress.frameGeometry()
                progress_frame.moveCenter(owner_center)
                self._update_progress.move(progress_frame.topLeft())
            except Exception:
                pass
        else:
            try:
                self._update_progress.setWindowTitle(title)
            except Exception:
                pass
        try:
            self._update_progress.setWindowModality(Qt.NonModal)
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
        if not self._update_progress.isVisible() and not getattr(self._update_progress, "_user_minimized", False):
            self._update_progress.show()
        self._update_progress.bring_to_front()

    @QtCore.pyqtSlot(str)
    def _on_update_progress_text(self, text):
        self._show_update_progress(text, determinate=False)

    @QtCore.pyqtSlot(str, int, int)
    def _on_update_download_progress(self, stage_text, downloaded_bytes, total_bytes):
        lang = self.parent.current_interface_language
        downloaded_bytes = max(0, int(downloaded_bytes))
        total_bytes = max(0, int(total_bytes))
        downloaded_mb = downloaded_bytes / (1024 * 1024)

        if total_bytes > 0:
            percent = int((downloaded_bytes * 100) / total_bytes)
            total_mb = total_bytes / (1024 * 1024)
            label = f"{stage_text}\n{downloaded_mb:.1f}/{total_mb:.1f} MB ({percent}%)"
            self._show_update_progress(label, determinate=True, value=percent)
            prefix = update_text(lang, "downloading_word")
            self._set_update_controls_enabled(False, f"{prefix} {percent}%")
            return

        label = f"{stage_text}\n{downloaded_mb:.1f} MB"
        self._show_update_progress(label, determinate=False)
        self._set_update_controls_enabled(False, update_text(lang, "downloading_button"))

    def _hide_update_progress(self):
        if hasattr(self, "_update_progress") and self._update_progress is not None:
            progress = self._update_progress
            try:
                progress.blockSignals(True)
                progress.hide()
                progress.deleteLater()
            except Exception:
                pass
            finally:
                try:
                    progress.blockSignals(False)
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
        return getattr(self, "_update_phase", "") in ("applying", "restarting")

    def _is_update_cancelable(self):
        return self._update_in_progress and not self._is_update_apply_stage()

    def _handle_update_progress_close_attempt(self):
        if not self._update_in_progress:
            return

        lang = self.parent.current_interface_language
        if self._is_update_apply_stage():
            self._show_update_progress(
                update_text(lang, "apply_wait"),
                determinate=False
            )
            QMessageBox.information(
                self,
                settings_text(lang, "update"),
                update_text(lang, "apply_close"),
            )
            return

        if not self._update_cancel_requested.is_set():
            self._update_cancel_requested.set()
            self._update_phase = "canceling"
            self._set_update_controls_enabled(False, update_text(lang, "canceling_button"))
            self._show_update_progress(
                update_text(lang, "canceling_clean"),
                determinate=False
            )
            return

        self._show_update_progress(
            update_text(lang, "canceling_wait"),
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
        lang = self.parent.current_interface_language
        try:
            update_api_url = _update_feed_api_url()
            headers = _update_request_headers(update_api_url, accept_json=True)
            response = requests.get(update_api_url, headers=headers, timeout=20)
            response.raise_for_status()
            release = response.json()
        except Exception as e:
            if self._update_cancel_requested.is_set():
                self._post_update_check_result({"status": "cancelled"})
                return
            self._post_update_check_result({
                "status": "error",
                "error": update_text(lang, "check_failed", error=str(e)),
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
        asset_url = _update_asset_download_url(selected_asset)
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
        lang = self.parent.current_interface_language
        self._update_in_progress = False
        self._update_phase = "idle"
        self._set_update_controls_enabled(True)
        self._hide_update_progress()

        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {"status": "error", "error": update_text(lang, "parse_failed")}

        status = payload.get("status")
        latest_version = payload.get("latest_version") or APP_VERSION

        if status == "cancelled" or self._update_cancel_requested.is_set():
            self._set_parent_update_flow_active(False)
            self._update_cancel_requested.clear()
            self._cleanup_update_temp_dir()
            QMessageBox.information(
                self,
                settings_text(lang, "update"),
                update_text(lang, "check_cancelled"),
            )
            return

        if status == "error":
            self._set_parent_update_flow_active(False)
            QMessageBox.warning(
                self,
                update_text(lang, "error_title"),
                payload.get("error", update_text(lang, "unknown_error")),
            )
            return

        if status == "up_to_date":
            self._set_parent_update_flow_active(False)
            QMessageBox.information(
                self,
                settings_text(lang, "update"),
                update_text(lang, "up_to_date", version=APP_VERSION),
            )
            return

        if status in ("no_asset", "invalid_asset"):
            self._set_parent_update_flow_active(False)
            msg = QMessageBox(self)
            msg.setWindowTitle(settings_text(lang, "update"))
            msg.setText(update_text(lang, "no_asset"))
            msg.setIcon(QMessageBox.Information)
            msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            yes_btn = msg.addButton(settings_text(lang, "open"), QMessageBox.YesRole)
            msg.addButton(settings_text(lang, "cancel"), QMessageBox.NoRole)
            msg.exec_()
            if msg.clickedButton() == yes_btn:
                webbrowser.open(GITHUB_RELEASES_PAGE)
            return

        if status == "ready" and not platform_support.supports_in_app_update():
            self._set_parent_update_flow_active(False)
            # Only the Windows build ships the helpers that replace the running
            # app. Elsewhere the new version is announced and the user updates
            # through whatever installed it (a new AppImage, their package
            # manager), which is what Linux desktop apps do.
            msg = QMessageBox(self)
            msg.setWindowTitle(update_text(lang, "available_title"))
            msg.setText(update_text(lang, "available_prompt", latest=latest_version, current=APP_VERSION))
            msg.setIcon(QMessageBox.Information)
            msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            open_btn = msg.addButton(settings_text(lang, "open"), QMessageBox.YesRole)
            msg.addButton(settings_text(lang, "later"), QMessageBox.NoRole)
            msg.exec_()
            if msg.clickedButton() == open_btn:
                webbrowser.open(GITHUB_RELEASES_PAGE)
            return

        if status == "ready":
            asset_name = payload.get("asset_name") or f"ClicknTranslate-v{latest_version}.zip"
            asset_url = payload.get("asset_url")
            checksum_url = payload.get("checksum_url")
            if not asset_url:
                self._set_parent_update_flow_active(False)
                QMessageBox.warning(
                    self,
                    update_text(lang, "error_title"),
                    update_text(lang, "invalid_url"),
                )
                return

            confirm = QMessageBox(self)
            confirm.setWindowTitle(update_text(lang, "available_title"))
            confirm.setIcon(QMessageBox.Question)
            confirm.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            confirm.setText(update_text(lang, "available_prompt", latest=latest_version, current=APP_VERSION))
            yes_btn = confirm.addButton(settings_text(lang, "install"), QMessageBox.YesRole)
            confirm.addButton(settings_text(lang, "later"), QMessageBox.NoRole)
            confirm.exec_()
            if confirm.clickedButton() != yes_btn:
                self._set_parent_update_flow_active(False)
                return

            self._start_update_download(asset_url, asset_name, latest_version, checksum_url)
            return

        self._set_parent_update_flow_active(False)

    def _start_update_download(self, asset_url, asset_name, latest_version, checksum_url=""):
        lang = self.parent.current_interface_language
        self._update_in_progress = True
        self._update_phase = "preparing_download"
        self._update_temp_dir = ""
        self._update_cancel_requested.clear()
        self._set_update_controls_enabled(False, update_text(lang, "downloading_button"))
        self._show_update_progress(update_text(lang, "preparing_download"), determinate=False)
        worker = threading.Thread(
            target=self._download_and_prepare_update,
            args=(asset_url, asset_name, latest_version, checksum_url),
            daemon=True
        )
        worker.start()

    def _pick_update_asset(self, assets):
        installed_copy = _is_inno_installed_copy()
        if installed_copy:
            setup_assets = []
            for asset in assets:
                name = (asset.get("name") or "").lower()
                compact_name = name.replace("-", "").replace("_", "")
                if (
                    name.endswith(".exe")
                    and "clickntranslate" in compact_name
                    and ("setup" in name or "installer" in name)
                    and (asset.get("browser_download_url") or asset.get("url"))
                ):
                    setup_assets.append(asset)
            if setup_assets:
                return sorted(
                    setup_assets,
                    key=lambda asset: (
                        "installer" in (asset.get("name") or "").lower(),
                        "win64" in (asset.get("name") or "").lower(),
                        "x64" in (asset.get("name") or "").lower(),
                    ),
                    reverse=True,
                )[0]

        zip_assets = []
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if (
                name.endswith(".zip")
                and "bootstrap" not in name
                and "update-bridge" not in name
                and (asset.get("browser_download_url") or asset.get("url"))
            ):
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
        base_name = re.sub(r"\.(zip|exe)$", "", asset_name.lower())
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
                return _update_asset_download_url(asset) or ""
            if ("." + base_name + ".") in name:
                return _update_asset_download_url(asset) or ""
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name in candidates:
                return _update_asset_download_url(asset) or ""
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

    def _download_file(
        self,
        url,
        destination_path,
        timeout=120,
        progress_callback=None,
        cancel_callback=None,
        max_attempts=5,
    ):
        """Download atomically with retry and HTTP Range resume support."""
        partial_path = destination_path + ".part"
        last_error = None
        for attempt in range(1, max(1, int(max_attempts)) + 1):
            if cancel_callback and cancel_callback():
                raise UpdateCancelledError("Update canceled by the user.")

            try:
                downloaded_bytes = os.path.getsize(partial_path)
            except OSError:
                downloaded_bytes = 0

            headers = _update_request_headers(url)
            if downloaded_bytes > 0:
                headers["Range"] = f"bytes={downloaded_bytes}-"

            try:
                with requests.get(
                    url,
                    stream=True,
                    timeout=(20, timeout),
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    resumed = downloaded_bytes > 0 and getattr(response, "status_code", 200) == 206
                    if downloaded_bytes > 0 and not resumed:
                        downloaded_bytes = 0
                        try:
                            os.remove(partial_path)
                        except OSError:
                            pass

                    content_range = response.headers.get("Content-Range") or ""
                    range_match = re.search(r"/(\d+)$", content_range)
                    if range_match:
                        total_bytes = int(range_match.group(1))
                    else:
                        try:
                            remaining = int(
                                (response.headers.get("Content-Length") or "0").strip()
                                or "0"
                            )
                        except (TypeError, ValueError):
                            remaining = 0
                        total_bytes = downloaded_bytes + remaining if remaining else 0

                    if progress_callback:
                        try:
                            progress_callback(downloaded_bytes, total_bytes)
                        except Exception:
                            pass

                    with open(partial_path, "ab" if resumed else "wb") as output:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if cancel_callback and cancel_callback():
                                raise UpdateCancelledError("Update canceled by the user.")
                            if not chunk:
                                continue
                            output.write(chunk)
                            downloaded_bytes += len(chunk)
                            if progress_callback:
                                try:
                                    progress_callback(downloaded_bytes, total_bytes)
                                except Exception:
                                    pass
                        output.flush()
                        os.fsync(output.fileno())

                    if total_bytes and downloaded_bytes != total_bytes:
                        raise IOError(
                            f"Incomplete download: received {downloaded_bytes} of {total_bytes} bytes"
                        )
                    if downloaded_bytes <= 0:
                        raise IOError("The server returned an empty update file")

                os.replace(partial_path, destination_path)
                return
            except UpdateCancelledError:
                try:
                    os.remove(partial_path)
                except OSError:
                    pass
                raise
            except Exception as error:
                last_error = error
                logger.warning(
                    "Update download attempt %s/%s failed for %s: %s",
                    attempt,
                    max_attempts,
                    url,
                    error,
                )
                if attempt >= max_attempts:
                    break
                for _step in range(attempt * 4):
                    if cancel_callback and cancel_callback():
                        try:
                            os.remove(partial_path)
                        except OSError:
                            pass
                        raise UpdateCancelledError("Update canceled by the user.")
                    time.sleep(0.25)

        raise RuntimeError("The update download was interrupted repeatedly.") from last_error

    def _download_and_prepare_update(self, asset_url, asset_name, latest_version, checksum_url=""):
        temp_dir = None
        try:
            lang = getattr(getattr(self, "parent", None), "current_interface_language", "en")
            stage_download = update_text(lang, "stage_download")
            stage_checksum = update_text(lang, "stage_checksum")
            stage_verify = update_text(lang, "stage_verify")
            stage_prepare = update_text(lang, "stage_prepare")

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
            safe_name = os.path.basename(asset_name or f"ClicknTranslate-v{latest_version}.zip")
            package_path = os.path.join(temp_dir, safe_name)
            package_kind = os.path.splitext(safe_name)[1].lower()
            if package_kind not in (".zip", ".exe"):
                raise RuntimeError("Unsupported update package type.")
            if package_kind == ".exe" and not _is_inno_installed_copy():
                raise RuntimeError("Installer updates are available only for an installed copy.")

            self._check_update_cancel_requested()
            self._update_phase = "downloading"
            _emit_stage_text(stage_download)
            self._download_file(
                asset_url,
                package_path,
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
                    actual = self._compute_sha256(package_path)
                    if not actual:
                        raise RuntimeError("Не удалось вычислить SHA256 для загруженного архива.")
                    if actual != expected:
                        raise RuntimeError("Контрольная сумма обновления не совпала (checksum mismatch).")
            if package_kind == ".zip" and not zipfile.is_zipfile(package_path):
                raise RuntimeError("Скачанный файл не является zip архивом.")

            if package_kind == ".exe":
                try:
                    with open(package_path, "rb") as executable:
                        if executable.read(2) != b"MZ":
                            raise RuntimeError("The downloaded installer is not a valid Windows executable.")
                except OSError as error:
                    raise RuntimeError(f"Could not validate the downloaded installer: {error}") from error

            self._check_update_cancel_requested()
            self._update_phase = "preparing"
            _emit_stage_text(stage_prepare)
            self._update_phase = "applying"
            ok, err = self._launch_apply_updater(
                package_path,
                package_kind,
                latest_version,
            )
            if not ok:
                raise RuntimeError(err or "Updater launch failed")

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

    def _launch_apply_updater(self, package_path, package_kind, latest_version):
        if portable_paths.is_windows_packaged():
            return False, "Microsoft Store manages updates for this package"
        if not getattr(sys, "frozen", False):
            return False, "Auto-update is available only in a packaged app"

        helper_candidates = [
            resource_path("ClicknTranslateUpdater.exe"),
            os.path.join(_frozen_executable_dir(), "_internal", "ClicknTranslateUpdater.exe"),
            os.path.join(_frozen_executable_dir(), "ClicknTranslateUpdater.exe"),
        ]
        helper_source = next(
            (candidate for candidate in helper_candidates if os.path.isfile(candidate)),
            "",
        )
        if not helper_source:
            return False, "The verified update helper is missing"

        app_dir = _portable_base_dir()
        exe_name = os.path.basename(_public_executable_path())
        helper_dir = tempfile.mkdtemp(prefix="clickntranslate_update_runner_")
        helper_path = os.path.join(helper_dir, "ClicknTranslateUpdater.exe")
        try:
            shutil.copy2(helper_source, helper_path)
        except Exception as error:
            shutil.rmtree(helper_dir, ignore_errors=True)
            return False, f"Could not prepare the update helper: {error}"

        def _encoded(value):
            return base64.b64encode(str(value).encode("utf-8")).decode("ascii")

        arguments = [
            "--mode", "setup" if package_kind == ".exe" else "zip",
            "--app-dir", _encoded(app_dir),
            "--package", _encoded(package_path),
            "--exe", _encoded(exe_name),
            "--version", str(latest_version),
            "--pid", str(os.getpid()),
        ]
        try:
            requires_elevation = self._install_dir_requires_elevation(app_dir)
            if requires_elevation:
                ok, error = self._launch_elevated_process(
                    helper_path,
                    arguments,
                    tempfile.gettempdir(),
                )
                if not ok:
                    shutil.rmtree(helper_dir, ignore_errors=True)
                    return False, f"Windows did not start the update helper: {error}"
            else:
                subprocess.Popen(
                    [helper_path, *arguments],
                    cwd=tempfile.gettempdir(),
                    close_fds=True,
                )
            return True, None
        except Exception as error:
            shutil.rmtree(helper_dir, ignore_errors=True)
            return False, f"Could not start the update helper: {error}"

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

    def _install_dir_requires_elevation(self, app_dir):
        if os.name != "nt" or not os.path.isdir(app_dir):
            return False
        probe_path = os.path.join(app_dir, f".clickntranslate-write-probe-{os.getpid()}-{threading.get_ident()}")
        try:
            descriptor = os.open(probe_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            os.remove(probe_path)
            return False
        except OSError as error:
            try:
                if os.path.exists(probe_path):
                    os.remove(probe_path)
            except OSError:
                pass
            return isinstance(error, PermissionError) or getattr(error, "winerror", None) == 5

    def _launch_elevated_process(self, executable, arguments, cwd):
        if os.name != "nt":
            return False, RuntimeError("Elevation is available only on Windows")
        try:
            parameters = subprocess.list2cmdline(list(arguments))
            shell_execute = ctypes.windll.shell32.ShellExecuteW
            shell_execute.argtypes = [
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_int,
            ]
            # ShellExecuteW returns an HINSTANCE/INT_PTR.  Leaving ctypes at
            # its default c_int return type truncates valid 64-bit handles and
            # can make a successful UAC launch look like a failure.
            shell_execute.restype = ctypes.c_void_p
            result = shell_execute(
                None,
                "runas",
                executable,
                parameters,
                cwd,
                0,
            )
            result_value = int(result or 0)
            if result_value <= 32:
                return False, OSError(result_value, "Windows refused to start the elevated updater")
            return True, None
        except Exception as error:
            return False, error

    def _launch_hidden_powershell_script(self, script_path, extra_args, elevated=False):
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # The public launcher historically started the inner PyInstaller app
        # with ``app`` as its current directory. A child updater inherited
        # that directory and then Windows refused to move it, so the update
        # silently rolled back to the old version. Always start PowerShell
        # from a directory outside the installation tree.
        updater_cwd = tempfile.gettempdir()
        last_err = None
        for candidate in SettingsWindow._powershell_launch_candidates(self):
            try:
                arguments = [
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-WindowStyle", "Hidden",
                    "-File", script_path,
                    *extra_args,
                ]
                if elevated:
                    ok, error = SettingsWindow._launch_elevated_process(
                        self,
                        candidate,
                        arguments,
                        updater_cwd,
                    )
                    if ok:
                        return True, None
                    last_err = error
                    continue
                subprocess.Popen(
                    [candidate, *arguments],
                    creationflags=create_no_window,
                    cwd=updater_cwd,
                )
                return True, None
            except Exception as e:
                last_err = e
                continue
        return False, last_err

    def _launch_setup_updater(self, setup_path, latest_version):
        if portable_paths.is_windows_packaged():
            return False, "Microsoft Store manages updates for this package"
        if not getattr(sys, "frozen", False) or not _is_inno_installed_copy():
            return False, "Installer update is available only for an installed copy"

        app_dir = _portable_base_dir()
        exe_name = os.path.basename(_public_executable_path())
        current_pid = os.getpid()
        fd, script_path = tempfile.mkstemp(prefix="clickntranslate_setup_updater_", suffix=".ps1")
        os.close(fd)

        script = r'''param(
    [string]$AppDir,
    [string]$SetupPath,
    [int]$TargetPid,
    [string]$ExeName,
    [string]$ExpectedVersion
)
$logPath = Join-Path ([System.IO.Path]::GetTempPath()) "clickntranslate_update.log"
$setupLog = Join-Path ([System.IO.Path]::GetTempPath()) "clickntranslate_setup_update.log"
$ErrorActionPreference = 'Stop'

function Write-UpdateLog {
    param([string]$Message)
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'
    Add-Content -Path $logPath -Value "[$ts] $Message" -ErrorAction SilentlyContinue
}

function Clear-PyInstallerEnv {
    Get-ChildItem Env: -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -like "_PYI_*" -or $_.Name -ieq "_MEIPASS2"
    } | ForEach-Object {
        Remove-Item -LiteralPath ("Env:" + $_.Name) -ErrorAction SilentlyContinue
    }
}

function Show-UpdateError {
    param([string]$Message)
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            $Message,
            "Click'n'Translate update",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    } catch {}
}

Set-Location -LiteralPath ([System.IO.Path]::GetTempPath())
Write-UpdateLog "Installer updater start: AppDir=$AppDir; SetupPath=$SetupPath; TargetPid=$TargetPid; Expected=$ExpectedVersion"

try {
    $deadline = (Get-Date).AddSeconds(30)
    while (Get-Process -Id $TargetPid -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) {
            Write-UpdateLog "Application did not exit; terminating process tree $TargetPid"
            & taskkill.exe /PID $TargetPid /T /F 2>&1 | ForEach-Object { Write-UpdateLog $_ }
            break
        }
        Start-Sleep -Milliseconds 250
    }

    $quotedDir = '"' + $AppDir.Replace('"', '') + '"'
    $quotedLog = '"' + $setupLog.Replace('"', '') + '"'
    $setupArguments = @(
        "/SILENT",
        "/SUPPRESSMSGBOXES",
        "/NOCANCEL",
        "/NORESTART",
        "/CLOSEAPPLICATIONS",
        "/FORCECLOSEAPPLICATIONS",
        "/NORESTARTAPPLICATIONS",
        "/LOGCLOSEAPPLICATIONS",
        "/DIR=$quotedDir",
        "/LOG=$quotedLog"
    )
    Write-UpdateLog "Starting Inno Setup with Windows Restart Manager"
    $setup = Start-Process -FilePath $SetupPath -ArgumentList $setupArguments -WorkingDirectory ([System.IO.Path]::GetTempPath()) -Wait -PassThru
    Write-UpdateLog "Setup exit code: $($setup.ExitCode)"
    if ($setup.ExitCode -ne 0) {
        throw "Installer exited with code $($setup.ExitCode). See $setupLog"
    }

    $targetExe = Join-Path $AppDir $ExeName
    if (-not (Test-Path -LiteralPath $targetExe)) {
        throw "Updated launcher was not installed: $targetExe"
    }
    $fileVersion = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($targetExe).FileVersion
    Write-UpdateLog "Installed launcher version: $fileVersion"
    if (-not $fileVersion -or -not $fileVersion.StartsWith($ExpectedVersion + ".")) {
        throw "Installed version $fileVersion does not match expected version $ExpectedVersion"
    }

    Clear-PyInstallerEnv
    Start-Process -FilePath $targetExe -WorkingDirectory $AppDir -ArgumentList '--show-after-update'
    Write-UpdateLog "Updated installed copy started successfully"
}
catch {
    $message = "The update could not be installed.`n`n$($_.Exception.Message)"
    Write-UpdateLog ("Installer updater failed: " + $_.Exception.Message)
    try {
        $fallbackExe = Join-Path $AppDir $ExeName
        if (Test-Path -LiteralPath $fallbackExe) {
            Clear-PyInstallerEnv
            Start-Process -FilePath $fallbackExe -WorkingDirectory $AppDir -ArgumentList '--show-after-update'
        }
    } catch {}
    Show-UpdateError $message
}
finally {
    Remove-Item -LiteralPath $SetupPath -Force -ErrorAction SilentlyContinue
    $packageDirectory = Split-Path -Parent $SetupPath
    if ($packageDirectory -and (Test-Path -LiteralPath $packageDirectory)) {
        Remove-Item -LiteralPath $packageDirectory -Recurse -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
'''
        try:
            with open(script_path, "w", encoding="utf-8") as script_file:
                script_file.write(script)
        except Exception as error:
            return False, f"Failed to create installer updater script: {error}"

        try:
            requires_elevation = SettingsWindow._install_dir_requires_elevation(self, app_dir)
            ok, error = SettingsWindow._launch_hidden_powershell_script(
                self,
                script_path,
                [
                    "-AppDir", app_dir,
                    "-SetupPath", setup_path,
                    "-TargetPid", str(current_pid),
                    "-ExeName", exe_name,
                    "-ExpectedVersion", str(latest_version),
                ],
                elevated=requires_elevation,
            )
            if ok:
                return True, None
            return False, f"Failed to launch installer updater: {error}"
        except Exception as error:
            return False, f"Failed to launch installer updater: {error}"

    def _launch_zip_updater(self, zip_path):
        if portable_paths.is_windows_packaged():
            return False, "Microsoft Store manages updates for this package"
        if not getattr(sys, "frozen", False):
            return False, "Auto-update is available only in packaged app"

        app_dir = _portable_base_dir()
        exe_name = os.path.basename(_public_executable_path())
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

function Clear-PyInstallerEnv {
    Get-ChildItem Env: -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -like "_PYI_*" -or $_.Name -ieq "_MEIPASS2"
    } | ForEach-Object {
        Remove-Item -LiteralPath ("Env:" + $_.Name) -ErrorAction SilentlyContinue
    }
}

function Test-PreservedInstallItem {
    param([System.IO.FileSystemInfo]$Item)
    if ($Item.Name -ieq "data" -or $Item.Name -ieq "ocr" -or $Item.Name -ieq "translators") {
        return $true
    }
    if (-not $Item.PSIsContainer -and $Item.Name -match '^unins\d*\.(exe|dat|msg)$') {
        return $true
    }
    return $false
}

function Get-DescendantProcessIds {
    param([int]$RootPid)
    try {
        $snapshot = @(Get-CimInstance Win32_Process -ErrorAction Stop)
        $pending = New-Object System.Collections.Generic.Queue[int]
        $result = New-Object System.Collections.Generic.List[int]
        $pending.Enqueue($RootPid)
        while ($pending.Count -gt 0) {
            $parentPid = $pending.Dequeue()
            foreach ($process in $snapshot) {
                if ([int]$process.ParentProcessId -eq $parentPid -and -not $result.Contains([int]$process.ProcessId)) {
                    $childPid = [int]$process.ProcessId
                    $result.Add($childPid)
                    $pending.Enqueue($childPid)
                }
            }
        }
        return @($result)
    } catch {
        Write-UpdateLog ("Could not snapshot child processes: " + $_.Exception.Message)
        return @()
    }
}

$pathCanonicalizerAvailable = $true
try {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace ClickNTranslate {
    public static class NativePath {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetLongPathNameW(
            string shortPath,
            StringBuilder longPath,
            uint bufferLength
        );

        public static string GetLongPath(string path) {
            var buffer = new StringBuilder(32768);
            var length = GetLongPathNameW(path, buffer, (uint)buffer.Capacity);
            return length > 0 && length < buffer.Capacity ? buffer.ToString() : path;
        }
    }
}
"@ -ErrorAction Stop
} catch {
    $pathCanonicalizerAvailable = $false
    Write-UpdateLog ("Could not load Windows path canonicalizer: " + $_.Exception.Message)
}

function Resolve-ComparablePath {
    param([string]$LiteralPath)
    $resolved = [System.IO.Path]::GetFullPath($LiteralPath)
    try {
        $resolved = (Get-Item -LiteralPath $resolved -Force -ErrorAction Stop).FullName
    } catch {}
    if ($pathCanonicalizerAvailable) {
        try {
            $resolved = [ClickNTranslate.NativePath]::GetLongPath($resolved)
        } catch {}
    }
    return $resolved.TrimEnd('\', '/')
}

function Stop-InstallProcesses {
    param([string]$InstallRoot, [int[]]$KnownChildPids)
    foreach ($childPid in @($KnownChildPids)) {
        if (Get-Process -Id $childPid -ErrorAction SilentlyContinue) {
            Write-UpdateLog "Stopping surviving application child process $childPid"
            Stop-Process -Id $childPid -Force -ErrorAction SilentlyContinue
        }
    }

    $rootPrefix = (Resolve-ComparablePath $InstallRoot) + [System.IO.Path]::DirectorySeparatorChar
    try {
        foreach ($process in @(Get-CimInstance Win32_Process -ErrorAction Stop)) {
            $executable = [string]$process.ExecutablePath
            $comparableExecutable = if ($executable) { Resolve-ComparablePath $executable } else { "" }
            if ($comparableExecutable.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                Write-UpdateLog "Stopping process from install directory: PID=$($process.ProcessId); Path=$executable"
                Stop-Process -Id ([int]$process.ProcessId) -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        Write-UpdateLog ("Could not enumerate install-directory processes: " + $_.Exception.Message)
    }

    for ($attempt = 1; $attempt -le 40; $attempt++) {
        $remaining = @()
        try {
            $remaining = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
                $path = [string]$_.ExecutablePath
                $comparablePath = if ($path) { Resolve-ComparablePath $path } else { "" }
                $comparablePath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
            })
        } catch {}
        if ($remaining.Count -eq 0) { return }
        if ($attempt -eq 40) {
            throw "Application processes are still using files in $InstallRoot"
        }
        Start-Sleep -Milliseconds 250
    }
}

function Move-UpdateItemWithRetry {
    param(
        [string]$LiteralPath,
        [string]$Destination,
        [int]$Attempts = 120
    )
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Move-Item -LiteralPath $LiteralPath -Destination $Destination -Force
            return
        }
        catch {
            if ($attempt -ge $Attempts) { throw }
            Write-UpdateLog "Move attempt $attempt failed for ${LiteralPath}: $($_.Exception.Message)"
            Start-Sleep -Milliseconds 250
        }
    }
}

# Normalize the script location as an additional safeguard. The process is
# also created with a temp-directory cwd above; that creation-time setting is
# the part that reliably avoids the Windows directory lock.
Set-Location -LiteralPath ([System.IO.Path]::GetTempPath())

Write-UpdateLog "Updater start: AppDir=$AppDir; ZipPath=$ZipPath; Exe=$ExeName; TargetPid=$TargetPid"
Write-UpdateLog "Updater working directory: $(Get-Location)"
$knownChildPids = @(Get-DescendantProcessIds -RootPid $TargetPid)
Write-UpdateLog "Captured child process IDs: $($knownChildPids -join ',')"

$extractDir = $null
$backupDir = $null
$backupComplete = $false
$updateApplied = $false
try {
    $deadline = (Get-Date).AddSeconds(30)
    while (Get-Process -Id $TargetPid -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) {
            Write-UpdateLog "Application did not exit in time, force terminating process tree $TargetPid"
            try { & taskkill.exe /PID $TargetPid /T /F 2>&1 | ForEach-Object { Write-UpdateLog $_ } } catch {}
            break
        }
        Start-Sleep -Milliseconds 300
    }

    Write-UpdateLog "Target app process is not running; start applying update"
    Stop-InstallProcesses -InstallRoot $AppDir -KnownChildPids $knownChildPids
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
    $payloadHasLauncherApp = Test-Path -LiteralPath (Join-Path $payloadRoot "app\ClicknTranslateApp.exe")
    $payloadHasLauncherInternal = Test-Path -LiteralPath (Join-Path $payloadRoot "app\_internal")
    if (-not $payloadHasInternal -and -not ($payloadHasLauncherApp -and $payloadHasLauncherInternal)) {
        throw "Update payload has neither a flat _internal directory nor app\ClicknTranslateApp.exe"
    }

    $appParent = Split-Path -Parent $AppDir
    $backupDir = Join-Path $appParent (".clickntranslate_backup_" + [Guid]::NewGuid().ToString("N"))
    New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
    Write-UpdateLog "Program backup directory: $backupDir"

    Get-ChildItem -LiteralPath $AppDir -Force | ForEach-Object {
        if (Test-PreservedInstallItem $_) { return }
        Write-UpdateLog "Moving existing program item to backup: $($_.FullName)"
        Move-UpdateItemWithRetry -LiteralPath $_.FullName -Destination $backupDir
    }
    $backupComplete = $true

    Get-ChildItem -LiteralPath $payloadRoot -Force | ForEach-Object {
        if ($_.Name -ieq "data" -or $_.Name -ieq "ocr" -or $_.Name -ieq "translators") { return }
        Write-UpdateLog "Copying update item: $($_.FullName)"
        Copy-Item -LiteralPath $_.FullName -Destination $AppDir -Recurse -Force
    }

    if ($payloadHasInternal -and -not (Test-Path -LiteralPath (Join-Path $AppDir "_internal"))) {
        throw "Update payload copy failed: _internal directory is missing"
    }
    if ($payloadHasLauncherApp -and (
        -not (Test-Path -LiteralPath (Join-Path $AppDir "app\ClicknTranslateApp.exe")) -or
        -not (Test-Path -LiteralPath (Join-Path $AppDir "app\_internal"))
    )) {
        throw "Update payload copy failed: launcher app directory is incomplete"
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
    Clear-PyInstallerEnv
    Start-Process -FilePath $targetExe -WorkingDirectory $AppDir -ArgumentList '--show-after-update'
    Write-UpdateLog "Updated executable started"
    $updateApplied = $true
}


catch {
    Write-UpdateLog ("Updater failed: " + $_.Exception.Message)
    if ($backupDir -and (Test-Path -LiteralPath $backupDir)) {
        try {
            if ($backupComplete) {
                Get-ChildItem -LiteralPath $AppDir -Force | ForEach-Object {
                    if (Test-PreservedInstallItem $_) { return }
                    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
            Get-ChildItem -LiteralPath $backupDir -Force | ForEach-Object {
                Write-UpdateLog "Restoring program item from backup: $($_.FullName)"
                Move-Item -LiteralPath $_.FullName -Destination $AppDir -Force
            }
            Write-UpdateLog "Previous version restored after updater failure"
        }
        catch {
            Write-UpdateLog ("Rollback failed: " + $_.Exception.Message)
        }
    }
    try {
        $fallbackExe = Join-Path $AppDir $ExeName
        if (Test-Path -LiteralPath $fallbackExe) {
            Write-UpdateLog "Launching fallback executable after updater failure: $fallbackExe"
            Clear-PyInstallerEnv
            Start-Process -FilePath $fallbackExe -WorkingDirectory $AppDir -ArgumentList '--show-after-update'
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
    if ($backupDir -and (Test-Path -LiteralPath $backupDir)) {
        if ($updateApplied) {
            Write-UpdateLog "Removing successful-update backup: $backupDir"
            Remove-Item -LiteralPath $backupDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        elseif (-not (Get-ChildItem -LiteralPath $backupDir -Force -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $backupDir -Force -ErrorAction SilentlyContinue
        }
        else {
            Write-UpdateLog "Preserving non-empty rollback backup for recovery: $backupDir"
        }
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
            requires_elevation = SettingsWindow._install_dir_requires_elevation(self, app_dir)
            ok, err = SettingsWindow._launch_hidden_powershell_script(
                self,
                script_path,
                [
                    "-AppDir", app_dir,
                    "-ZipPath", zip_path,
                    "-TargetPid", str(current_pid),
                    "-ExeName", exe_name,
                ],
                elevated=requires_elevation,
            )
            if ok:
                return True, None
            return False, f"Failed to launch updater: {err}"
        except Exception as e:
            return False, f"Failed to launch updater: {e}"

    @QtCore.pyqtSlot()
    def _restore_update_button_after_download(self):
        self._update_in_progress = False
        self._set_parent_update_flow_active(False)
        self._update_phase = "idle"
        self._update_cancel_requested.clear()
        self._cleanup_update_temp_dir()
        self._set_update_controls_enabled(True)
        self._hide_update_progress()

    @QtCore.pyqtSlot()
    def _on_update_cancelled(self):
        self._update_in_progress = False
        self._set_parent_update_flow_active(False)
        self._update_phase = "idle"
        self._cleanup_update_temp_dir()
        self._update_cancel_requested.clear()
        self._set_update_controls_enabled(True)
        self._hide_update_progress()

        lang = self.parent.current_interface_language
        QMessageBox.information(
            self,
            settings_text(lang, "update"),
            update_text(lang, "cancelled"),
        )

    @pyqtSlot(str)
    def _on_update_failed(self, error_text):
        self._update_in_progress = False
        self._set_parent_update_flow_active(False)
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

        lang = self.parent.current_interface_language
        friendly_error = self._friendly_update_error(error_text, lang)
        QMessageBox.warning(
            self,
            update_text(lang, "error_title"),
            friendly_error,
        )

    def _friendly_update_error(self, error_text, lang=None):
        raw = str(error_text or "").strip()
        logger.error("Update failed: %s", raw)
        language = lang or getattr(
            getattr(self, "parent", None),
            "current_interface_language",
            "en",
        )
        messages = {
            "en": {
                "network": "The download was interrupted. Check the connection and click Update again — the app will resume safely.",
                "checksum": "The downloaded update was incomplete or damaged. It was not installed; click Update to download it again.",
                "permission": "Windows blocked access to the application folder. Close other copies of Click'n'Translate and approve the administrator prompt, then try again.",
                "generic": "The update could not be installed. Your current version was kept. Close other copies of the app and try Update again.",
            },
            "ru": {
                "network": "Загрузка прервалась. Проверьте интернет и снова нажмите «Обновление» — программа безопасно продолжит загрузку.",
                "checksum": "Обновление скачалось не полностью или было повреждено. Оно не установлено; нажмите «Обновление», чтобы скачать заново.",
                "permission": "Windows запретила доступ к папке программы. Закройте другие копии Click'n'Translate, подтвердите запрос администратора и повторите попытку.",
                "generic": "Не удалось установить обновление. Текущая версия сохранена. Закройте другие копии программы и снова нажмите «Обновление».",
            },
            "es": {
                "network": "La descarga se interrumpió. Comprueba Internet y pulsa Actualizar de nuevo; la aplicación continuará de forma segura.",
                "checksum": "La actualización descargada está incompleta o dañada. No se instaló; pulsa Actualizar para descargarla otra vez.",
                "permission": "Windows bloqueó el acceso a la carpeta. Cierra otras copias de Click'n'Translate, acepta el permiso de administrador e inténtalo de nuevo.",
                "generic": "No se pudo instalar la actualización. Se conservó la versión actual. Cierra otras copias e inténtalo de nuevo.",
            },
            "de": {
                "network": "Der Download wurde unterbrochen. Prüfen Sie das Internet und klicken Sie erneut auf Update; die App setzt sicher fort.",
                "checksum": "Das Update wurde unvollständig oder beschädigt geladen und nicht installiert. Klicken Sie erneut auf Update.",
                "permission": "Windows hat den Zugriff auf den Programmordner blockiert. Schließen Sie weitere App-Kopien, bestätigen Sie die Administratorabfrage und versuchen Sie es erneut.",
                "generic": "Das Update konnte nicht installiert werden. Die aktuelle Version blieb erhalten. Schließen Sie weitere App-Kopien und versuchen Sie es erneut.",
            },
            "fr": {
                "network": "Le téléchargement a été interrompu. Vérifiez Internet puis cliquez de nouveau sur Mettre à jour ; l’application reprendra en sécurité.",
                "checksum": "La mise à jour téléchargée est incomplète ou endommagée. Elle n’a pas été installée ; relancez la mise à jour.",
                "permission": "Windows a bloqué l’accès au dossier. Fermez les autres copies, acceptez la demande administrateur puis réessayez.",
                "generic": "La mise à jour n’a pas pu être installée. La version actuelle a été conservée. Fermez les autres copies puis réessayez.",
            },
            "zh": {
                "network": "下载已中断。请检查网络并再次点击“更新”，程序会安全地继续下载。",
                "checksum": "下载的更新不完整或已损坏，因此未安装。请再次点击“更新”重新下载。",
                "permission": "Windows 阻止访问程序文件夹。请关闭其他 Click'n'Translate 实例，确认管理员提示后重试。",
                "generic": "无法安装更新，当前版本已保留。请关闭其他程序实例后再次点击“更新”。",
            },
        }
        lowered = raw.lower()
        if any(token in lowered for token in ("incompleteread", "connection", "timeout", "interrupted repeatedly", "download")):
            key = "network"
        elif any(token in lowered for token in ("checksum", "sha256", "not a valid", "not a zip", "damaged")):
            key = "checksum"
        elif any(token in lowered for token in ("access is denied", "permission", "winerror 5", "administrator")):
            key = "permission"
        else:
            key = "generic"
        return messages.get(language, messages["en"])[key]

    @pyqtSlot(str)
    def _on_update_ready_to_restart(self, latest_version):
        self._update_in_progress = True
        self._update_phase = "restarting"
        self._update_temp_dir = ""
        self._update_cancel_requested.clear()

        lang = self.parent.current_interface_language
        restart_text = update_text(lang, "restart_ready", version=latest_version)
        self._set_update_controls_enabled(False, update_text(lang, "restarting"))
        self._show_update_progress(restart_text, determinate=False)
        QtCore.QTimer.singleShot(800, self._exit_application_for_update_restart)

    @QtCore.pyqtSlot()
    def _exit_application_for_update_restart(self):
        kill_timer = threading.Timer(2.0, lambda: os._exit(0))
        kill_timer.daemon = True
        kill_timer.start()

        parent = getattr(self, "parent", None)
        try:
            if parent is not None:
                if hasattr(parent, "force_quit"):
                    parent.force_quit = True
                tray_icon = getattr(parent, "tray_icon", None)
                if tray_icon is not None:
                    try:
                        tray_icon.hide()
                    except Exception:
                        pass
                exit_app = getattr(parent, "exit_app", None)
                if callable(exit_app):
                    exit_app()
                    return
        except BaseException:
            pass

        app = QApplication.instance()
        if app is not None:
            app.quit()
        os._exit(0)

    def _apply_action_panel_style(self):
        """Paint the connected action grid as one complete framed control."""
        panel = getattr(self, "settings_action_panel", None)
        if panel is None:
            return
        dark = self.parent.current_theme != "Светлая"
        separator = "#6b587d" if dark else "#a99ab7"
        surface = "#15151a" if dark else "#e4dee8"
        hover = "#242129" if dark else "#d8d0df"
        text = "#ffffff" if dark else "#2b2531"
        panel.setStyleSheet(
            "QWidget#settingsActionPanel {"
            f" background:{separator}; border:1px solid {separator};"
            " border-radius:9px; }"
        )

        top_specs = (
            (getattr(self, "clear_cache_btn", None), "#7A5FA1", "#8B70B2", "8px", "0px"),
            (getattr(self, "reset_btn", None), "#D44444", "#E55555", "0px", "0px"),
            (getattr(self, "update_btn", None), "#7A5FA1", "#8B70B2", "0px", "8px"),
        )
        for column, (button, background, active, left_radius, right_radius) in enumerate(top_specs):
            if button is None:
                continue
            divider = f"border-left:1px solid {separator};" if column else ""
            button.setStyleSheet(f"""
                QPushButton {{
                    background:{background}; color:#ffffff; border:none;
                    {divider}
                    border-top-left-radius:{left_radius};
                    border-top-right-radius:{right_radius};
                    border-bottom-left-radius:0px; border-bottom-right-radius:0px;
                    padding:0 8px; font-family:'Segoe UI';
                    font-size: 16px; font-weight: 700;
                }}
                QPushButton:hover {{ background:{active}; }}
            """)

        middle_buttons = (
            getattr(self, "ocr_languages_btn", None),
            getattr(self, "copy_history_btn", None),
            getattr(self, "translation_history_btn", None),
        )
        for column, button in enumerate(middle_buttons):
            if button is not None:
                divider = f"border-left:1px solid {separator};" if column else ""
                button.setStyleSheet(f"""
                    QPushButton {{ background:{surface}; color:{text}; border:none;
                        {divider} border-radius:0; padding:0 6px;
                        font-family:'Segoe UI'; font-size: 16px; font-weight: 700; }}
                    QPushButton:hover {{ background:{hover}; }}
                    QPushButton[packageTaskDone="true"] {{ color:#398f53; }}
                """)
        hotkeys = getattr(self, "hotkeys_button", None)
        if hotkeys is not None:
            hotkeys.setStyleSheet(f"""
                QPushButton {{ background:{surface}; color:{text}; border:none;
                    border-top-left-radius:0; border-top-right-radius:0;
                    border-bottom-left-radius:8px; border-bottom-right-radius:8px;
                    padding:0 12px; font-family:'Segoe UI';
                    font-size: 16px; font-weight: 700; }}
                QPushButton:hover {{ background:{hover}; }}
            """)

    def apply_theme(self):
        THEMES_LOCAL = {
            "Темная": {
                "background": "#121212",
                "text_color": "#ffffff",
            },
            "Светлая": {
                "background": "#f0edf3",
                "text_color": "#241f2a",
            }
        }
        theme = THEMES_LOCAL.get(self.parent.current_theme) or next(iter(THEMES_LOCAL.values()))
        self._ui_theme = self.parent.current_theme
        dark = self.parent.current_theme != "Светлая"
        slider_track = "#3a3344" if dark else "#d4cadc"
        slider_disabled = "#29262d" if dark else "#e3dde7"
        disabled_text = "#756B80" if dark else "#7c7087"
        report_hover = "#211b29" if dark else "#ded6e5"
        style = f"""
            QWidget {{
                background-color: {theme['background']};
            }}
            {TOOLTIP_QSS}
            QLabel {{
                color: {theme['text_color']};
                font-size: 16px;
            }}
            QCheckBox {{
                color: {theme['text_color']};
                font-size: 16px;
                spacing: 10px;
            }}
            QCheckBox::indicator {{
                /* Only the size is set here. Colouring the indicator through
                   the stylesheet would replace the platform rendering and take
                   the check mark with it, so AccentControlStyle paints it. */
                width: 20px;
                height: 20px;
            }}
            QCheckBox:disabled {{
                color: {disabled_text};
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
            QSlider#ocrDimStrengthSlider::groove:horizontal {{
                height: 5px;
                background: {slider_track};
                border-radius: 2px;
            }}
            QSlider#ocrDimStrengthSlider::sub-page:horizontal {{
                background: #9B78C8;
                border-radius: 2px;
            }}
            QSlider#ocrDimStrengthSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                margin: -6px 0;
                background: #C5B3E9;
                border: 1px solid #7A5FA1;
                border-radius: 8px;
            }}
            QSlider#ocrDimStrengthSlider::groove:horizontal:disabled,
            QSlider#ocrDimStrengthSlider::sub-page:horizontal:disabled {{
                background: {slider_disabled};
            }}
            QSlider#ocrDimStrengthSlider::handle:horizontal:disabled {{
                background: #756B80;
                border-color: #5f5668;
            }}
            QLabel#ocrDimStrengthValue {{
                color: {theme['text_color']};
                font-size: 14px;
                font-weight: 700;
            }}
            QLabel#ocrDimStrengthValue:disabled {{
                color: {disabled_text};
            }}
            QLabel#gameSettingsHeading {{
                color: #A97BDD;
                font-size: 16px;
                font-weight: 800;
            }}
            QLabel#gameSettingsLabel {{
                color: {theme['text_color']};
                font-size: 14px;
                font-weight: 600;
            }}
            QLabel#gameSettingValue {{
                color: {theme['text_color']};
                font-size: 14px;
                font-weight: 700;
            }}
            QLabel#gameWorkflowNote {{
                color: {disabled_text};
                font-size: 13px;
                font-weight: 600;
            }}
            QToolButton#gameLanguageSwap {{
                color: #B78BE5;
                background: transparent;
                border: 1px solid #6C587E;
                border-radius: 9px;
                font-size: 17px;
                font-weight: 800;
            }}
            QToolButton#gameLanguageSwap:hover {{
                background: {report_hover};
                border-color: #A97BDD;
            }}
            QToolButton#gameLanguageSwap:disabled {{
                color: {disabled_text};
                border-color: {slider_disabled};
            }}
            QSlider#gameScanIntervalSlider::groove:horizontal,
            QSlider#gameOverlayOpacitySlider::groove:horizontal {{
                height: 5px;
                background: {slider_track};
                border-radius: 2px;
            }}
            QSlider#gameScanIntervalSlider::sub-page:horizontal,
            QSlider#gameOverlayOpacitySlider::sub-page:horizontal {{
                background: #9B78C8;
                border-radius: 2px;
            }}
            QSlider#gameScanIntervalSlider::handle:horizontal,
            QSlider#gameOverlayOpacitySlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                margin: -6px 0;
                background: #C5B3E9;
                border: 1px solid #7A5FA1;
                border-radius: 8px;
            }}
            QPushButton#settingsBugReportButton,
            QPushButton#settingsTransferButton {{
                background: transparent;
                color: {theme['text_color']};
                border: 1px solid #C5B3E9;
                border-radius: 8px;
                padding: 0px 7px;
                text-align: center;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton#settingsBugReportButton:hover,
            QPushButton#settingsTransferButton:hover {{
                background: {report_hover};
                border-color: #9B78C8;
            }}
        """
        self.setStyleSheet(style)
        self._apply_action_panel_style()
        install_accent_controls(self, dark=self.parent.current_theme != "Светлая")
        for dot in getattr(self, "settings_page_dots", ()):
            try:
                dot.set_dark(self.parent.current_theme != "Светлая")
            except RuntimeError:
                pass
        # The theme sets the font this box is measured with, so its width can
        # only be worked out here.
        self._fit_copy_translated_checkbox()
        for combo_name in (
            "ocr_engine_combo",
            "translator_combo",
            "game_source_combo",
            "game_target_combo",
        ):
            combo = getattr(self, combo_name, None)
            if combo is not None:
                try:
                    self._apply_engine_combo_style(combo)
                except RuntimeError:
                    pass
        result_control = getattr(self, "result_window_control", None)
        if result_control is not None:
            try:
                # Same styling as the engine pickers: the three rows now live in
                # a drop-down, so they must not drift apart visually.
                self._apply_engine_combo_style(result_control)
                # The row ticks are painted pixmaps, so they have to be redrawn
                # for the new palette rather than restyled.
                result_control.set_dark(self.parent.current_theme != "Светлая")
                # The popup is its own top-level widget and misses the sweep
                # install_accent_controls does over this window.
                install_accent_controls(
                    result_control.view(), dark=self.parent.current_theme != "Светлая"
                )
            except RuntimeError:
                pass

        self._refresh_secondary_view_theme()
        secondary_kind = getattr(self, "_secondary_view_kind", None)
        if secondary_kind == "history":
            try:
                self.load_history_embedded()
            except RuntimeError:
                self.history_scroll_area = None
        elif secondary_kind == "copy_history":
            try:
                self.load_copy_history_embedded()
            except RuntimeError:
                self.copy_history_scroll_area = None

    def update_language(self):
        self.init_ui()
        # init_ui() creates a completely new widget tree. Reapply both the
        # palette and AccentControlStyle to those new controls immediately;
        # otherwise reparented OCR check boxes fall back to Windows' native
        # white squares and font-dependent size hints move the footer rows.
        self.apply_theme()
        # The package manager builds all of its text once, from the language it
        # was created with, and it is kept alive between openings — so without
        # this it stays in the old language until the app restarts.
        self._relanguage_language_manager()

    def _relanguage_language_manager(self):
        dialog = getattr(self, "_language_manager_dialog", None)
        if dialog is None:
            return
        current = getattr(self.parent, "current_interface_language", "en")
        try:
            if dialog.lang == current:
                return
            # Never pull the window out from under a running install: it owns
            # the progress dialog and the worker's cancel flag. It will be
            # rebuilt the next time it is opened instead.
            if getattr(dialog, "_install_in_progress", False):
                return
            was_visible = dialog.isVisible()
            sections = (
                dialog.tabs.currentIndex(),
                dialog.ocr_tabs.currentIndex(),
                dialog.translation_tabs.currentIndex(),
            )
            geometry = dialog.geometry()
            dialog.close()
            dialog.deleteLater()
        except RuntimeError:
            self._language_manager_dialog = None
            return
        self._language_manager_dialog = None
        if not was_visible:
            return

        fresh = OcrLanguageManagerDialog(self)
        self._language_manager_dialog = fresh
        # Put the user back on the tab they were reading, where they left it.
        fresh.tabs.setCurrentIndex(sections[0])
        fresh.ocr_tabs.setCurrentIndex(sections[1])
        fresh.translation_tabs.setCurrentIndex(sections[2])
        fresh.show()
        fresh.setGeometry(geometry)
        fresh.raise_()
        fresh.activateWindow()

    def eventFilter(self, obj, event):
        # It used to keep the pickers' × buttons positioned. Those are gone —
        # engines are removed from their own tab in Language packages now — but
        # the filter stays installed so a future watcher has somewhere to live.
        return super().eventFilter(obj, event)

    def _save_result_window_modes(self, *_args):
        control = getattr(self, "result_window_control", None)
        if control is None:
            return
        # Storage remains "hidden modes" for compatibility, while the screen
        # presents the friendlier inverse: a ticked row means SHOW the window.
        from main import RESULT_WINDOW_MODES

        checked = set(control.checked_modes())
        hidden_modes = [mode for mode in RESULT_WINDOW_MODES if mode not in checked]
        self.auto_save_setting("result_window_hidden_modes", hidden_modes)
        complete_guide_step = getattr(self.parent, "_complete_guide_step", None)
        if callable(complete_guide_step):
            complete_guide_step("result_window")

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
        return _portable_base_dir()

    def _local_tesseract_dir(self):
        return os.path.join(self._portable_app_dir(), "ocr", "tesseract")

    def _local_rapidocr_dir(self):
        return os.path.join(self._portable_app_dir(), "ocr", "rapidocr")

    def _local_easyocr_dir(self):
        return os.path.join(self._portable_app_dir(), "ocr", "easyocr")

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

    def _rapidocr_candidate_paths_under(self, root_dir):
        candidates = [
            root_dir,
            os.path.join(root_dir, "site-packages"),
            os.path.join(root_dir, "Lib", "site-packages"),
            os.path.join(root_dir, "lib", "site-packages"),
        ]
        try:
            for name in os.listdir(root_dir):
                lower = name.lower()
                if lower.startswith("python") or lower in {"venv", ".venv"}:
                    candidates.append(os.path.join(root_dir, name, "Lib", "site-packages"))
                    candidates.append(os.path.join(root_dir, name, "lib", "site-packages"))
        except Exception:
            pass
        unique = []
        seen = set()
        for path in candidates:
            normalized = os.path.normcase(os.path.abspath(path))
            if normalized in seen or not os.path.isdir(path):
                continue
            seen.add(normalized)
            unique.append(os.path.abspath(path))
        return unique

    def _rapidocr_package_present_under(self, root_dir):
        if not root_dir or not os.path.isdir(root_dir):
            return False
        has_core = False
        has_backend = False
        for path in self._rapidocr_candidate_paths_under(root_dir):
            names = set()
            try:
                names = {name.lower() for name in os.listdir(path)}
            except Exception:
                continue
            if "rapidocr" in names or "rapidocr_onnxruntime" in names:
                has_core = True
            if "onnxruntime" in names or "rapidocr_onnxruntime" in names:
                has_backend = True
        return has_core and has_backend

    def _local_rapidocr_installed(self):
        return self._rapidocr_package_present_under(self._local_rapidocr_dir())

    @staticmethod
    def _module_available_without_import(*module_names):
        """Check an optional runtime without executing its package import.

        Importing EasyOCR pulls Torch and importing RapidOCR pulls ONNX Runtime.
        Doing either from a combo-box signal blocks Qt's UI thread for a
        noticeable amount of time.  Runtime validation still happens in the
        background installer/worker; selection only needs a cheap presence
        check.
        """
        for module_name in module_names:
            try:
                if importlib.util.find_spec(module_name) is not None:
                    return True
            except (ImportError, AttributeError, ValueError):
                continue
        return False

    def _rapidocr_runtime_installed(self):
        if self._local_rapidocr_installed():
            return True
        return self._module_available_without_import(
            "rapidocr", "rapidocr_onnxruntime"
        )

    def _easyocr_package_present_under(self, root_dir):
        if not root_dir or not os.path.isdir(root_dir):
            return False
        for path in self._rapidocr_candidate_paths_under(root_dir):
            try:
                names = {name.lower() for name in os.listdir(path)}
            except Exception:
                continue
            if "easyocr" in names:
                return True
        return False

    def _local_easyocr_installed(self):
        return self._easyocr_package_present_under(self._local_easyocr_dir())

    def _easyocr_runtime_installed(self):
        if self._local_easyocr_installed():
            return True
        return self._module_available_without_import("easyocr")

    def _reset_tesseract_runtime_cache(self):
        try:
            import ocr
            if hasattr(ocr, "ScreenCaptureOverlay"):
                ocr.ScreenCaptureOverlay._tesseract_cmd_cache = None
            ocr._ocr_config_cache = None
            ocr._ocr_config_mtime = 0
        except Exception:
            pass

    def _reset_rapidocr_runtime_cache(self, clear_modules=False):
        try:
            import ocr
            if hasattr(ocr, "reset_rapidocr_runtime_cache"):
                ocr.reset_rapidocr_runtime_cache(clear_modules=clear_modules)
            ocr._ocr_config_cache = None
            ocr._ocr_config_mtime = 0
        except Exception:
            pass

    def _reset_easyocr_runtime_cache(self, clear_modules=False):
        try:
            import ocr
            if hasattr(ocr, "reset_easyocr_runtime_cache"):
                ocr.reset_easyocr_runtime_cache(clear_modules=clear_modules)
            ocr._ocr_config_cache = None
            ocr._ocr_config_mtime = 0
        except Exception:
            pass

    def _rapidocr_importable_status(self):
        try:
            import ocr
            if hasattr(ocr, "rapidocr_importable"):
                return ocr.rapidocr_importable()
        except Exception as exc:
            return False, str(exc)
        return False, "RapidOCR import check is unavailable"

    def _easyocr_importable_status(self):
        try:
            import ocr
            if hasattr(ocr, "easyocr_importable"):
                return ocr.easyocr_importable()
        except Exception as exc:
            return False, str(exc)
        return False, "EasyOCR import check is unavailable"

    def _rapidocr_runtime_status(self):
        try:
            import ocr
            if hasattr(ocr, "rapidocr_status"):
                return ocr.rapidocr_status()
        except Exception as exc:
            return False, str(exc)
        return False, "RapidOCR runtime check is unavailable"

    def _set_ocr_combo_silently(self, engine_name):
        if not hasattr(self, "ocr_engine_combo"):
            return
        self.ocr_engine_combo.blockSignals(True)
        self.ocr_engine_combo.setCurrentText(engine_name)
        self.ocr_engine_combo.blockSignals(False)

    def handle_ocr_engine_change(self, text):
        if text == RAPIDOCR_ENGINE_DISPLAY:
            self._handle_rapidocr_engine_change()
            return
        if text == EASYOCR_ENGINE_DISPLAY:
            self._handle_easyocr_engine_change()
            return
        if text != "Tesseract":
            self.save_ocr_engine(text)
            return

        default_engine = platform_support.default_ocr_engine()
        self.previous_ocr_engine = self.parent.config.get("ocr_engine", default_engine)
        if self._find_available_tesseract_exe():
            self.save_ocr_engine("Tesseract")
            return

        lang = self.parent.current_interface_language
        if platform_support.IS_LINUX:
            # Linux distributions package Tesseract, so the app points at the
            # package manager instead of downloading an installer.
            self._show_linux_tesseract_hint(lang)
            self._set_ocr_combo_silently(self.previous_ocr_engine or default_engine)
            self.save_ocr_engine(self.previous_ocr_engine or default_engine)
            return

        msg = QMessageBox(self)
        msg.setWindowTitle(engine_text(lang, "not_found", engine="Tesseract"))
        msg.setText(engine_text(lang, "tesseract_prompt"))
        msg.setIcon(QMessageBox.Question)
        msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        msg.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        yes_btn = msg.addButton(engine_text(lang, "install"), QMessageBox.YesRole)
        msg.addButton(engine_text(lang, "cancel"), QMessageBox.NoRole)
        msg.exec_()
        if msg.clickedButton() == yes_btn:
            self.start_tesseract_install()
            return

        self._set_ocr_combo_silently(self.previous_ocr_engine or default_engine)
        self.save_ocr_engine(self.previous_ocr_engine or default_engine)

    def _show_linux_tesseract_hint(self, lang):
        """Tell a Linux user which package provides Tesseract."""
        command = platform_support.tesseract_install_hint()
        is_ru = lang == "ru"
        message = (
            f"Tesseract не найден. Установите его через пакетный менеджер:\n\n{command}"
            if is_ru
            else f"Tesseract is not installed. Install it with your package manager:\n\n{command}"
        )
        msg = QMessageBox(self)
        msg.setWindowTitle(engine_text(lang, "not_found", engine="Tesseract"))
        msg.setText(message)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        msg.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        msg.exec_()

    def _handle_easyocr_engine_change(self):
        self.previous_ocr_engine = self.parent.config.get("ocr_engine", platform_support.default_ocr_engine())
        if self._easyocr_runtime_installed():
            self.save_ocr_engine(EASYOCR_ENGINE_DISPLAY)
            return

        lang = self.parent.current_interface_language
        msg = QMessageBox(self)
        msg.setWindowTitle(engine_text(lang, "not_found", engine="EasyOCR"))
        msg.setText(engine_text(lang, "easyocr_prompt"))
        msg.setIcon(QMessageBox.Question)
        msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        msg.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        yes_btn = msg.addButton(engine_text(lang, "install"), QMessageBox.YesRole)
        msg.addButton(engine_text(lang, "cancel"), QMessageBox.NoRole)
        msg.exec_()
        if msg.clickedButton() == yes_btn:
            self.start_easyocr_install()
            return

        self._set_ocr_combo_silently(self.previous_ocr_engine or "Windows")
        self.save_ocr_engine(self.previous_ocr_engine or "Windows")

    def _handle_rapidocr_engine_change(self):
        self.previous_ocr_engine = self.parent.config.get("ocr_engine", platform_support.default_ocr_engine())
        if self._rapidocr_runtime_installed():
            self.save_ocr_engine(RAPIDOCR_ENGINE_DISPLAY)
            return

        lang = self.parent.current_interface_language
        msg = QMessageBox(self)
        msg.setWindowTitle(engine_text(lang, "not_found", engine="RapidOCR"))
        msg.setText(engine_text(lang, "rapidocr_prompt"))
        msg.setIcon(QMessageBox.Question)
        msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        msg.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        yes_btn = msg.addButton(engine_text(lang, "install"), QMessageBox.YesRole)
        msg.addButton(engine_text(lang, "cancel"), QMessageBox.NoRole)
        msg.exec_()
        if msg.clickedButton() == yes_btn:
            self.start_rapidocr_install()
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

    def _delete_local_rapidocr_dir(self):
        rapidocr_dir = self._local_rapidocr_dir()
        if not os.path.isdir(rapidocr_dir):
            return True, ""
        try:
            shutil.rmtree(rapidocr_dir, ignore_errors=False)
            self._reset_rapidocr_runtime_cache(clear_modules=True)
            return True, ""
        except Exception as e:
            return False, str(e)

    def _delete_local_easyocr_dir(self):
        easyocr_dir = self._local_easyocr_dir()
        if not os.path.isdir(easyocr_dir):
            return True, ""
        try:
            shutil.rmtree(easyocr_dir, ignore_errors=False)
            self._reset_easyocr_runtime_cache(clear_modules=True)
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
        # Keep a provider switch independent of importing the translation
        # runtime.  These are the same platform-aware names translater.py uses.
        candidates = tuple(
            platform_support.executable_name(stem).lower()
            for stem in ("hymt", "llama-cli", "llama-run", "main")
        )
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
                try:
                    idx = self._translator_engines.index("google")
                except ValueError:
                    idx = 0
        self.translator_combo.blockSignals(True)
        self.translator_combo.setCurrentIndex(idx)
        self.translator_combo.blockSignals(False)

    def _current_translator_engine_from_combo(self):
        combo = getattr(self, "translator_combo", None)
        if combo is None:
            return "google"
        idx = combo.currentIndex()
        if hasattr(self, "_translator_engines") and 0 <= idx < len(self._translator_engines):
            return self._translator_engines[idx] or "google"
        return "google"

    def _show_manual_hymt_hint(self, lang):
        """Explain how to supply a llama.cpp runner where we cannot ship one."""
        import translater

        target_dir = os.path.join(_portable_base_dir(), "translators", "hymt")
        runner_names = ", ".join(translater.hymt_runner_names())
        is_ru = lang == "ru"
        message = (
            "Автоматическая установка Hy-MT доступна только в Windows.\n\n"
            f"Положите модель {HYMT_MODEL_FILE} и исполняемый файл llama.cpp "
            f"({runner_names}) в папку:\n{target_dir}"
            if is_ru
            else
            "The automatic Hy-MT download is available on Windows only.\n\n"
            f"Put the {HYMT_MODEL_FILE} model and a llama.cpp runner "
            f"({runner_names}) in:\n{target_dir}"
        )
        msg = QMessageBox(self)
        msg.setWindowTitle(engine_text(lang, "not_found", engine="Hy-MT"))
        msg.setText(message)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        msg.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        msg.exec_()

    def _on_translator_changed(self, idx):
        # Сохраняем имя движка из списка
        if hasattr(self, '_translator_engines') and 0 <= idx < len(self._translator_engines):
            value = self._translator_engines[idx]
        else:
            value = "google"
        if not value:
            return
        if value != HYMT_ENGINE_KEY:
            self.auto_save_setting("translator_engine", value)
            return

        self.previous_translator_engine = self.parent.config.get("translator_engine", "Google").lower()
        if self._hymt_installed():
            self.auto_save_setting("translator_engine", HYMT_ENGINE_KEY)
            return

        lang = self.parent.current_interface_language
        if not platform_support.IS_WINDOWS:
            # The pinned llama.cpp archive is the Windows build, so instead of
            # downloading something that cannot run, explain how to supply a
            # local runner. Hy-MT still works once one is in place.
            self._show_manual_hymt_hint(lang)
            fallback = self.previous_translator_engine or "google"
            self._set_translator_combo_silently(fallback)
            self.auto_save_setting("translator_engine", fallback)
            return

        msg = QMessageBox(self)
        msg.setWindowTitle(engine_text(lang, "not_found", engine="Hy-MT"))
        msg.setText(engine_text(lang, "hymt_prompt"))
        msg.setIcon(QMessageBox.Question)
        msg.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        msg.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        yes_btn = msg.addButton(engine_text(lang, "install"), QMessageBox.YesRole)
        msg.addButton(engine_text(lang, "cancel"), QMessageBox.NoRole)
        msg.exec_()
        if msg.clickedButton() == yes_btn:
            self.start_hymt_install()
            return

        fallback = self.previous_translator_engine or "google"
        self._set_translator_combo_silently(fallback)
        self.auto_save_setting("translator_engine", fallback)

    def start_download_thread(self):
        self.start_tesseract_install()

    def start_tesseract_install(self, progress_owner=None):
        if (
            self._tesseract_install_in_progress
            or self._rapidocr_install_in_progress
            or self._easyocr_install_in_progress
            or self._hymt_install_in_progress
        ):
            return
        lang = self.parent.current_interface_language
        self._tesseract_install_in_progress = True
        self._tesseract_install_phase = "starting"
        self._tesseract_cancel_requested.clear()
        self._tesseract_temp_dir = ""
        self._tesseract_progress_owner = progress_owner
        self.ocr_engine_combo.setEnabled(False)
        self._set_parent_topmost_for_tesseract_install(False)
        self._show_tesseract_progress(engine_text(lang, "preparing", engine="Tesseract"), 0)
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
            lang = getattr(getattr(self, "parent", None), "current_interface_language", "en")
            machine = platform.machine().lower()
            is_x64 = machine in ("amd64", "x86_64")
            bundle_url = self._get_tesseract_bundle_url(is_x64)
            temp_dir = tempfile.mkdtemp(prefix="clickntranslate_tesseract_")
            self._tesseract_temp_dir = temp_dir
            bundle_path = os.path.join(temp_dir, TESSERACT_BUNDLE_NAME_WIN64)
            extract_dir = os.path.join(temp_dir, "extract")
            os.makedirs(extract_dir, exist_ok=True)

            download_text = engine_text(lang, "downloading_engine", engine="Tesseract")
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

            extract_text = engine_text(lang, "extracting_engine", engine="Tesseract")
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
                model_text = engine_text(lang, "downloading_language", name=name)
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
            self._emit_tesseract_progress(engine_text(lang, "applying"), 96)
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

            self._emit_tesseract_progress(engine_text(lang, "done"), 100)
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
        lang = self.parent.current_interface_language
        if not hasattr(self, "progress") or self.progress is None:
            self.progress = TesseractInstallProgressDialog(
                self,
                anchor_owner=self._tesseract_progress_owner,
            )
            self.progress.setWindowTitle("Tesseract")
            self.progress.setCancelButtonText(engine_text(lang, "cancel"))
            self.progress.setWindowModality(
                Qt.WindowModal if self._tesseract_progress_owner is not None else Qt.NonModal
            )
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
        self.progress.bring_to_front()

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
        lang = self.parent.current_interface_language
        self._tesseract_cancel_requested.set()
        self._show_tesseract_progress(engine_text(lang, "canceling"), 0, False)

    def _finish_tesseract_install_state(self):
        self._tesseract_install_in_progress = False
        self._tesseract_install_phase = "idle"
        self._tesseract_cancel_requested.clear()
        self._tesseract_progress_owner = None
        self.ocr_engine_combo.setEnabled(True)
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
        lang = self.parent.current_interface_language
        QMessageBox.information(
            self,
            "Tesseract",
            engine_text(lang, "ready", engine="Tesseract"),
        )

    @QtCore.pyqtSlot(str)
    def _on_tesseract_install_failed(self, error):
        self._finish_tesseract_install_state()
        self._hide_tesseract_progress()
        self._restore_settings_view()
        prev_engine = self.previous_ocr_engine or "Windows"
        self._set_ocr_combo_silently(prev_engine)
        self.save_ocr_engine(prev_engine)
        lang = self.parent.current_interface_language
        QMessageBox.warning(
            self,
            engine_text(lang, "error_title", engine="Tesseract"),
            engine_text(lang, "install_failed", engine="Tesseract", error=str(error)),
        )

    @QtCore.pyqtSlot()
    def _on_tesseract_install_cancelled(self):
        self._finish_tesseract_install_state()
        self._hide_tesseract_progress()
        self._restore_settings_view()
        prev_engine = self.previous_ocr_engine or "Windows"
        self._set_ocr_combo_silently(prev_engine)
        self.save_ocr_engine(prev_engine)
        lang = self.parent.current_interface_language
        QMessageBox.information(
            self,
            engine_text(lang, "cancelled_title"),
            engine_text(lang, "install_cancelled", engine="Tesseract"),
        )

    def _emit_rapidocr_progress(self, text, percent=0, determinate=True):
        QMetaObject.invokeMethod(
            self,
            "_on_rapidocr_progress",
            Qt.QueuedConnection,
            QtCore.Q_ARG(str, str(text)),
            QtCore.Q_ARG(int, int(max(0, min(100, percent)))),
            QtCore.Q_ARG(bool, bool(determinate))
        )

    def _check_rapidocr_cancel_requested(self):
        if self._rapidocr_cancel_requested.is_set():
            raise RapidOCRInstallCancelledError("RapidOCR installation canceled by user.")

    def _python_command_output(self, command, args, timeout=30):
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            [*command, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=create_no_window,
        )
        return completed.returncode, (completed.stdout or "").strip()

    def _python_command_version(self, command):
        code = "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        return_code, output = self._python_command_output(command, ["-c", code], timeout=20)
        if return_code != 0:
            return ""
        return output.splitlines()[-1].strip() if output else ""

    def _python_command_has_pip(self, command):
        return_code, _output = self._python_command_output(command, ["-m", "pip", "--version"], timeout=30)
        return return_code == 0

    def _find_rapidocr_install_python_command(self, engine_name=RAPIDOCR_ENGINE_DISPLAY, package_dir=None):
        required = f"{sys.version_info.major}.{sys.version_info.minor}"
        candidates = []
        if not getattr(sys, "frozen", False):
            candidates.append([sys.executable])
        py_launcher = shutil.which("py")
        if py_launcher:
            candidates.append([py_launcher, f"-{required}"])
        # Distributions install versioned interpreters (python3.12), so probe the
        # exact one first: the plain python3 is often a different minor version,
        # and these wheels are imported by the frozen worker, so the ABI has to
        # match exactly.
        for name in (f"python{required}", "python", "python3"):
            found = shutil.which(name)
            if found:
                candidates.append([found])

        checked = []
        for candidate in candidates:
            label = " ".join(candidate)
            if label in checked:
                continue
            checked.append(label)
            try:
                version = self._python_command_version(candidate)
                if version != required:
                    continue
                if not self._python_command_has_pip(candidate):
                    continue
                return candidate
            except Exception:
                continue
        if platform_support.IS_LINUX:
            # Windows falls back to a downloadable embedded interpreter; on Linux
            # the distribution provides one, so name the package to install.
            raise RuntimeError(
                f"Python {required} with pip was not found. {engine_name} needs an interpreter "
                f"matching this build. Install it with your package manager "
                f"({platform_support.python_install_hint(required)}), or place the "
                f"{engine_name} packages in {package_dir or self._local_rapidocr_dir()}."
            )
        raise RuntimeError(
            f"Python {required} with pip was not found. Install Python {required} or manually place "
            f"{engine_name} packages into {package_dir or self._local_rapidocr_dir()}."
        )

    def _portable_pip_bootstrap_plan(self, is_x64=True):
        if platform_support.IS_LINUX:
            # The bootstrap downloads the Windows embedded distribution; there is
            # no equivalent to ship for Linux.
            raise RuntimeError(
                "The bundled Python bootstrap is Windows-only. Install a matching "
                "python3 from your package manager instead."
            )
        if not is_x64:
            raise RuntimeError("Automatic OCR engine installation supports Windows x64 only.")
        return {
            "python": {
                "name": EASYOCR_PYTHON_ARCHIVE,
                "url": EASYOCR_PYTHON_URL,
                "sha256": EASYOCR_PYTHON_SHA256,
            },
            "pip": {
                "name": EASYOCR_PIP_WHEEL,
                "url": EASYOCR_PIP_URL,
                "sha256": EASYOCR_PIP_SHA256,
            },
        }

    def _prepare_portable_pip_command(
        self,
        temp_dir,
        engine_name,
        cancel_callback=None,
        progress_callback=None,
    ):
        """Download a private Python/pip bootstrap without modifying Windows."""
        is_x64 = platform.machine().lower() in {"amd64", "x86_64"} and sys.maxsize > 2**32
        plan = self._portable_pip_bootstrap_plan(is_x64=is_x64)
        bootstrap_dir = os.path.join(temp_dir, "python-bootstrap")
        runtime_dir = os.path.join(bootstrap_dir, "runtime")
        os.makedirs(runtime_dir, exist_ok=True)

        def download(item, base_percent, span):
            destination = os.path.join(bootstrap_dir, item["name"])

            def report(downloaded, total):
                if progress_callback is None:
                    return
                if total > 0:
                    percent = base_percent + int((downloaded * span) / total)
                    progress_callback(percent, True)
                else:
                    progress_callback(base_percent, False)

            self._download_file(
                item["url"],
                destination,
                timeout=180,
                progress_callback=report,
                cancel_callback=cancel_callback,
            )
            self._verify_file_sha256(destination, item["sha256"], item["name"])
            return destination

        python_archive = download(plan["python"], 1, 8)
        if cancel_callback and cancel_callback():
            raise UpdateCancelledError(f"{engine_name} installation canceled by user.")
        if not zipfile.is_zipfile(python_archive):
            raise RuntimeError("Downloaded portable Python package is not a zip archive.")
        with zipfile.ZipFile(python_archive, "r") as archive:
            archive.extractall(runtime_dir)
        if cancel_callback and cancel_callback():
            raise UpdateCancelledError(f"{engine_name} installation canceled by user.")

        python_exe = os.path.join(runtime_dir, "python.exe")
        if not os.path.isfile(python_exe):
            raise RuntimeError("Portable Python package does not contain python.exe.")
        required = f"{sys.version_info.major}.{sys.version_info.minor}"
        installed = self._python_command_version([python_exe])
        if installed != required:
            raise RuntimeError(
                f"Portable Python {installed or 'unknown'} is incompatible with the app runtime {required}."
            )

        pip_wheel = download(plan["pip"], 9, 2)
        if cancel_callback and cancel_callback():
            raise UpdateCancelledError(f"{engine_name} installation canceled by user.")
        pip_entry = os.path.join(pip_wheel, "pip")
        return [python_exe, pip_entry]

    @staticmethod
    def _pip_target_python_version(pip_command):
        """The Python version the packages will be installed for.

        The command is either our downloaded interpreter or whichever python3
        the system provides, and those need different requirement sets.
        """
        if not pip_command:
            return (0, 0)
        try:
            completed = subprocess.run(
                [pip_command[0], "-c", "import sys; print('%d %d' % sys.version_info[:2])"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=30,
                **platform_support.no_window_kwargs(),
            )
            major, _, minor = (completed.stdout or "").strip().partition(" ")
            return (int(major), int(minor))
        except (OSError, ValueError, subprocess.SubprocessError):
            return (0, 0)

    def _easyocr_requirements(self, pip_command):
        version = self._pip_target_python_version(pip_command)
        if version >= EASYOCR_PINNED_PYTHON:
            return EASYOCR_PIP_PACKAGES
        logger.info(
            "EasyOCR: target Python %s is older than %s, installing with resolved "
            "dependencies instead of the pinned tree",
            ".".join(str(part) for part in version),
            ".".join(str(part) for part in EASYOCR_PINNED_PYTHON),
        )
        return EASYOCR_PIP_PACKAGES_ANY_PYTHON

    def _prepare_engine_pip_command(
        self,
        temp_dir,
        engine_name,
        package_dir,
        cancel_callback=None,
        progress_callback=None,
    ):
        try:
            python_command = self._find_rapidocr_install_python_command(engine_name, package_dir)
            return [*python_command, "-m", "pip"]
        except RuntimeError:
            return self._prepare_portable_pip_command(
                temp_dir,
                engine_name,
                cancel_callback=cancel_callback,
                progress_callback=progress_callback,
            )

    def _restore_rapidocr_backup(self, final_dir, backup_dir):
        if not backup_dir or not os.path.isdir(backup_dir):
            return
        try:
            if os.path.isdir(final_dir):
                shutil.rmtree(final_dir, ignore_errors=True)
            shutil.move(backup_dir, final_dir)
        except Exception:
            pass

    def start_rapidocr_install(self, progress_owner=None):
        if (
            self._rapidocr_install_in_progress
            or self._tesseract_install_in_progress
            or self._easyocr_install_in_progress
            or self._hymt_install_in_progress
        ):
            return
        lang = self.parent.current_interface_language
        self._rapidocr_install_in_progress = True
        self._rapidocr_install_phase = "starting"
        self._rapidocr_cancel_requested.clear()
        self._rapidocr_temp_dir = ""
        self._rapidocr_install_process = None
        self._rapidocr_progress_owner = progress_owner
        self.ocr_engine_combo.setEnabled(False)
        self._set_parent_topmost_for_tesseract_install(False)
        self._show_rapidocr_progress(
            engine_text(lang, "preparing", engine="RapidOCR"),
            0,
            False
        )
        threading.Thread(target=self._install_rapidocr_worker, daemon=True).start()

    def _install_rapidocr_worker(self):
        temp_dir = ""
        backup_dir = ""
        final_dir = self._local_rapidocr_dir()
        try:
            lang = getattr(getattr(self, "parent", None), "current_interface_language", "en")
            temp_dir = tempfile.mkdtemp(prefix="clickntranslate_rapidocr_")
            self._rapidocr_temp_dir = temp_dir
            package_root = os.path.join(temp_dir, "site-packages")
            os.makedirs(package_root, exist_ok=True)

            self._rapidocr_install_phase = "installing"
            install_text = engine_text(lang, "downloading_packages", engine="RapidOCR")
            self._emit_rapidocr_progress(install_text, 0, False)
            pip_command = self._prepare_engine_pip_command(
                temp_dir,
                RAPIDOCR_ENGINE_DISPLAY,
                final_dir,
                cancel_callback=lambda: self._rapidocr_cancel_requested.is_set(),
                progress_callback=lambda percent, determinate: self._emit_rapidocr_progress(
                    engine_text(lang, "preparing", engine="RapidOCR"),
                    percent,
                    determinate,
                ),
            )
            cmd = [
                *pip_command,
                "install",
                "--upgrade",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--only-binary=:all:",
                "--no-warn-script-location",
                "--target",
                package_root,
                *RAPIDOCR_PIP_PACKAGES,
            ]
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=create_no_window,
            )
            self._rapidocr_install_process = process
            output_tail = []
            if process.stdout is not None:
                for line in process.stdout:
                    if line:
                        clean_line = line.strip()
                        if clean_line:
                            output_tail.append(clean_line)
                            output_tail = output_tail[-40:]
                            self._emit_rapidocr_progress(install_text, 0, False)
                    if self._rapidocr_cancel_requested.is_set():
                        try:
                            process.terminate()
                        except Exception:
                            pass
                        raise RapidOCRInstallCancelledError("RapidOCR installation canceled by user.")
            return_code = process.wait()
            self._rapidocr_install_process = None
            self._check_rapidocr_cancel_requested()
            if return_code != 0:
                tail = "\n".join(output_tail[-12:])
                raise RuntimeError(f"pip install failed with code {return_code}.\n{tail}".strip())
            if not self._rapidocr_package_present_under(package_root):
                raise RuntimeError("RapidOCR packages were not found after pip install.")

            self._rapidocr_install_phase = "applying"
            self._emit_rapidocr_progress(engine_text(lang, "applying"), 92)
            os.makedirs(os.path.dirname(final_dir), exist_ok=True)
            if os.path.isdir(final_dir):
                backup_dir = f"{final_dir}.backup-{int(time.time())}"
                shutil.move(final_dir, backup_dir)
            shutil.move(package_root, final_dir)
            self._reset_rapidocr_runtime_cache(clear_modules=True)
            importable, import_error = self._rapidocr_importable_status()
            if not importable:
                raise RuntimeError(f"RapidOCR was installed but could not be imported:\n{import_error}")
            if backup_dir and os.path.isdir(backup_dir):
                shutil.rmtree(backup_dir, ignore_errors=True)
                backup_dir = ""

            self._emit_rapidocr_progress(engine_text(lang, "done"), 100)
            QMetaObject.invokeMethod(self, "_on_rapidocr_install_ready", Qt.QueuedConnection)
        except (RapidOCRInstallCancelledError, UpdateCancelledError):
            self._restore_rapidocr_backup(final_dir, backup_dir)
            self._reset_rapidocr_runtime_cache(clear_modules=True)
            QMetaObject.invokeMethod(self, "_on_rapidocr_install_cancelled", Qt.QueuedConnection)
        except Exception as e:
            self._restore_rapidocr_backup(final_dir, backup_dir)
            self._reset_rapidocr_runtime_cache(clear_modules=True)
            QMetaObject.invokeMethod(
                self,
                "_on_rapidocr_install_failed",
                Qt.QueuedConnection,
                QtCore.Q_ARG(str, str(e))
            )
        finally:
            if self._rapidocr_install_process is not None:
                try:
                    self._rapidocr_install_process.terminate()
                except Exception:
                    pass
                self._rapidocr_install_process = None
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            self._rapidocr_temp_dir = ""

    def _show_rapidocr_progress(self, text, percent=0, determinate=True):
        lang = self.parent.current_interface_language
        if self.rapidocr_progress is None:
            self.rapidocr_progress = TesseractInstallProgressDialog(
                self,
                title=RAPIDOCR_ENGINE_DISPLAY,
                in_progress_attr="_rapidocr_install_in_progress",
                cancel_callback=self._request_rapidocr_install_cancel,
                anchor_owner=self._rapidocr_progress_owner,
            )
            self.rapidocr_progress.setCancelButtonText(engine_text(lang, "cancel"))
            self.rapidocr_progress.setWindowModality(
                Qt.WindowModal if self._rapidocr_progress_owner is not None else Qt.NonModal
            )
            self.rapidocr_progress.setAutoClose(False)
            self.rapidocr_progress.setAutoReset(False)
            self.rapidocr_progress.setMinimumDuration(0)
            self.rapidocr_progress.setMinimumWidth(430)
            self.rapidocr_progress.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            try:
                owner_window = self.window()
                owner_center = owner_window.frameGeometry().center()
                progress_frame = self.rapidocr_progress.frameGeometry()
                progress_frame.moveCenter(owner_center)
                self.rapidocr_progress.move(progress_frame.topLeft())
            except Exception:
                pass
        self.rapidocr_progress.setLabelText(text)
        if determinate:
            self.rapidocr_progress.setRange(0, 100)
            self.rapidocr_progress.setValue(max(0, min(100, int(percent))))
        else:
            self.rapidocr_progress.setRange(0, 0)
        if not self.rapidocr_progress.isVisible() and not getattr(self.rapidocr_progress, "_user_minimized", False):
            self.rapidocr_progress.show()
        self.rapidocr_progress.bring_to_front()

    @QtCore.pyqtSlot(str, int, bool)
    def _on_rapidocr_progress(self, text, percent, determinate):
        self._show_rapidocr_progress(text, percent, determinate)

    def _hide_rapidocr_progress(self):
        if self.rapidocr_progress is not None:
            try:
                self.rapidocr_progress.blockSignals(True)
                try:
                    self.rapidocr_progress.hide()
                finally:
                    self.rapidocr_progress.blockSignals(False)
            except Exception:
                pass

    def _request_rapidocr_install_cancel(self):
        if not self._rapidocr_install_in_progress:
            return
        lang = self.parent.current_interface_language
        self._rapidocr_cancel_requested.set()
        process = self._rapidocr_install_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass
        self._show_rapidocr_progress(engine_text(lang, "canceling"), 0, False)

    def _finish_rapidocr_install_state(self):
        self._rapidocr_install_in_progress = False
        self._rapidocr_install_phase = "idle"
        self._rapidocr_cancel_requested.clear()
        self._rapidocr_install_process = None
        self._rapidocr_progress_owner = None
        if hasattr(self, "ocr_engine_combo"):
            self.ocr_engine_combo.setEnabled(True)
        self._restore_parent_topmost_after_tesseract_install()

    @QtCore.pyqtSlot()
    def _on_rapidocr_install_ready(self):
        self._finish_rapidocr_install_state()
        self._hide_rapidocr_progress()
        self._restore_settings_view()
        self._reset_rapidocr_runtime_cache(clear_modules=True)
        self._set_ocr_combo_silently(RAPIDOCR_ENGINE_DISPLAY)
        self.save_ocr_engine(RAPIDOCR_ENGINE_DISPLAY)
        lang = self.parent.current_interface_language
        QMessageBox.information(
            self,
            RAPIDOCR_ENGINE_DISPLAY,
            engine_text(lang, "ready", engine="RapidOCR"),
        )

    @QtCore.pyqtSlot(str)
    def _on_rapidocr_install_failed(self, error):
        self._finish_rapidocr_install_state()
        self._hide_rapidocr_progress()
        self._restore_settings_view()
        prev_engine = self.previous_ocr_engine or "Windows"
        self._set_ocr_combo_silently(prev_engine)
        self.save_ocr_engine(prev_engine)
        lang = self.parent.current_interface_language
        QMessageBox.warning(
            self,
            engine_text(lang, "error_title", engine="RapidOCR"),
            engine_text(lang, "install_failed", engine="RapidOCR", error=str(error)),
        )

    @QtCore.pyqtSlot()
    def _on_rapidocr_install_cancelled(self):
        self._finish_rapidocr_install_state()
        self._hide_rapidocr_progress()
        self._restore_settings_view()
        prev_engine = self.previous_ocr_engine or "Windows"
        self._set_ocr_combo_silently(prev_engine)
        self.save_ocr_engine(prev_engine)
        lang = self.parent.current_interface_language
        QMessageBox.information(
            self,
            engine_text(lang, "cancelled_title"),
            engine_text(lang, "install_cancelled", engine="RapidOCR"),
        )

    def _emit_easyocr_progress(self, text, percent=0, determinate=True):
        QMetaObject.invokeMethod(
            self,
            "_on_easyocr_progress",
            Qt.QueuedConnection,
            QtCore.Q_ARG(str, str(text)),
            QtCore.Q_ARG(int, int(max(0, min(100, percent)))),
            QtCore.Q_ARG(bool, bool(determinate))
        )

    def _check_easyocr_cancel_requested(self):
        if self._easyocr_cancel_requested.is_set():
            raise EasyOCRInstallCancelledError("EasyOCR installation canceled by user.")

    def start_easyocr_install(self, progress_owner=None):
        if (
            self._easyocr_install_in_progress
            or self._rapidocr_install_in_progress
            or self._tesseract_install_in_progress
            or self._hymt_install_in_progress
        ):
            return
        lang = self.parent.current_interface_language
        self._easyocr_install_in_progress = True
        self._easyocr_install_phase = "starting"
        self._easyocr_cancel_requested.clear()
        self._easyocr_temp_dir = ""
        self._easyocr_install_process = None
        self._easyocr_progress_owner = progress_owner
        self.ocr_engine_combo.setEnabled(False)
        self._set_parent_topmost_for_tesseract_install(False)
        self._show_easyocr_progress(
            engine_text(lang, "preparing", engine="EasyOCR"),
            0,
            False
        )
        threading.Thread(target=self._install_easyocr_worker, daemon=True).start()

    def _install_easyocr_worker(self):
        temp_dir = ""
        backup_dir = ""
        final_dir = self._local_easyocr_dir()
        try:
            lang = getattr(getattr(self, "parent", None), "current_interface_language", "en")
            temp_dir = tempfile.mkdtemp(prefix="clickntranslate_easyocr_")
            self._easyocr_temp_dir = temp_dir
            package_root = os.path.join(temp_dir, "site-packages")
            os.makedirs(package_root, exist_ok=True)

            self._easyocr_install_phase = "installing"
            install_text = engine_text(lang, "downloading_packages", engine="EasyOCR")
            self._emit_easyocr_progress(install_text, 0, False)
            pip_command = self._prepare_engine_pip_command(
                temp_dir,
                EASYOCR_ENGINE_DISPLAY,
                final_dir,
                cancel_callback=lambda: self._easyocr_cancel_requested.is_set(),
                progress_callback=lambda percent, determinate: self._emit_easyocr_progress(
                    engine_text(lang, "preparing", engine="EasyOCR"),
                    percent,
                    determinate,
                ),
            )
            cmd = [
                *pip_command,
                "install",
                "--upgrade",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--only-binary=:all:",
                "--no-warn-script-location",
                "--target",
                package_root,
                "--extra-index-url",
                EASYOCR_EXTRA_INDEX_URL,
                *self._easyocr_requirements(pip_command),
            ]
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=create_no_window,
            )
            self._easyocr_install_process = process
            output_tail = []
            if process.stdout is not None:
                for line in process.stdout:
                    if line:
                        clean_line = line.strip()
                        if clean_line:
                            output_tail.append(clean_line)
                            output_tail = output_tail[-40:]
                            self._emit_easyocr_progress(install_text, 0, False)
                    if self._easyocr_cancel_requested.is_set():
                        try:
                            process.terminate()
                        except Exception:
                            pass
                        raise EasyOCRInstallCancelledError("EasyOCR installation canceled by user.")
            return_code = process.wait()
            self._easyocr_install_process = None
            self._check_easyocr_cancel_requested()
            if return_code != 0:
                tail = "\n".join(output_tail[-12:])
                raise RuntimeError(f"pip install failed with code {return_code}.\n{tail}".strip())
            if not self._easyocr_package_present_under(package_root):
                raise RuntimeError("EasyOCR packages were not found after pip install.")

            self._easyocr_install_phase = "applying"
            self._emit_easyocr_progress(engine_text(lang, "applying"), 92)
            os.makedirs(os.path.dirname(final_dir), exist_ok=True)
            if os.path.isdir(final_dir):
                backup_dir = f"{final_dir}.backup-{int(time.time())}"
                shutil.move(final_dir, backup_dir)
            shutil.move(package_root, final_dir)
            self._reset_easyocr_runtime_cache(clear_modules=True)
            importable, import_error = self._easyocr_importable_status()
            if not importable:
                raise RuntimeError(f"EasyOCR was installed but could not be imported:\n{import_error}")
            if backup_dir and os.path.isdir(backup_dir):
                shutil.rmtree(backup_dir, ignore_errors=True)
                backup_dir = ""

            self._emit_easyocr_progress(engine_text(lang, "done"), 100)
            QMetaObject.invokeMethod(self, "_on_easyocr_install_ready", Qt.QueuedConnection)
        except (EasyOCRInstallCancelledError, UpdateCancelledError):
            self._restore_rapidocr_backup(final_dir, backup_dir)
            self._reset_easyocr_runtime_cache(clear_modules=True)
            QMetaObject.invokeMethod(self, "_on_easyocr_install_cancelled", Qt.QueuedConnection)
        except Exception as e:
            self._restore_rapidocr_backup(final_dir, backup_dir)
            self._reset_easyocr_runtime_cache(clear_modules=True)
            QMetaObject.invokeMethod(
                self,
                "_on_easyocr_install_failed",
                Qt.QueuedConnection,
                QtCore.Q_ARG(str, str(e))
            )
        finally:
            if self._easyocr_install_process is not None:
                try:
                    self._easyocr_install_process.terminate()
                except Exception:
                    pass
                self._easyocr_install_process = None
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            self._easyocr_temp_dir = ""

    def _show_easyocr_progress(self, text, percent=0, determinate=True):
        lang = self.parent.current_interface_language
        if self.easyocr_progress is None:
            self.easyocr_progress = TesseractInstallProgressDialog(
                self,
                title=EASYOCR_ENGINE_DISPLAY,
                in_progress_attr="_easyocr_install_in_progress",
                cancel_callback=self._request_easyocr_install_cancel,
                anchor_owner=self._easyocr_progress_owner,
            )
            self.easyocr_progress.setCancelButtonText(engine_text(lang, "cancel"))
            self.easyocr_progress.setWindowModality(
                Qt.WindowModal if self._easyocr_progress_owner is not None else Qt.NonModal
            )
            self.easyocr_progress.setAutoClose(False)
            self.easyocr_progress.setAutoReset(False)
            self.easyocr_progress.setMinimumDuration(0)
            self.easyocr_progress.setMinimumWidth(430)
            self.easyocr_progress.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
            try:
                owner_window = self.window()
                owner_center = owner_window.frameGeometry().center()
                progress_frame = self.easyocr_progress.frameGeometry()
                progress_frame.moveCenter(owner_center)
                self.easyocr_progress.move(progress_frame.topLeft())
            except Exception:
                pass
        self.easyocr_progress.setLabelText(text)
        if determinate:
            self.easyocr_progress.setRange(0, 100)
            self.easyocr_progress.setValue(max(0, min(100, int(percent))))
        else:
            self.easyocr_progress.setRange(0, 0)
        if not self.easyocr_progress.isVisible() and not getattr(self.easyocr_progress, "_user_minimized", False):
            self.easyocr_progress.show()
        self.easyocr_progress.bring_to_front()

    @QtCore.pyqtSlot(str, int, bool)
    def _on_easyocr_progress(self, text, percent, determinate):
        self._show_easyocr_progress(text, percent, determinate)

    def _hide_easyocr_progress(self):
        if self.easyocr_progress is not None:
            try:
                self.easyocr_progress.blockSignals(True)
                try:
                    self.easyocr_progress.hide()
                finally:
                    self.easyocr_progress.blockSignals(False)
            except Exception:
                pass

    def _request_easyocr_install_cancel(self):
        if not self._easyocr_install_in_progress:
            return
        lang = self.parent.current_interface_language
        self._easyocr_cancel_requested.set()
        process = self._easyocr_install_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass
        self._show_easyocr_progress(engine_text(lang, "canceling"), 0, False)

    def _finish_easyocr_install_state(self):
        self._easyocr_install_in_progress = False
        self._easyocr_install_phase = "idle"
        self._easyocr_cancel_requested.clear()
        self._easyocr_install_process = None
        self._easyocr_progress_owner = None
        if hasattr(self, "ocr_engine_combo"):
            self.ocr_engine_combo.setEnabled(True)
        self._restore_parent_topmost_after_tesseract_install()

    @QtCore.pyqtSlot()
    def _on_easyocr_install_ready(self):
        self._finish_easyocr_install_state()
        self._hide_easyocr_progress()
        self._restore_settings_view()
        self._reset_easyocr_runtime_cache(clear_modules=True)
        self._set_ocr_combo_silently(EASYOCR_ENGINE_DISPLAY)
        self.save_ocr_engine(EASYOCR_ENGINE_DISPLAY)
        lang = self.parent.current_interface_language
        QMessageBox.information(
            self,
            EASYOCR_ENGINE_DISPLAY,
            engine_text(lang, "ready", engine="EasyOCR"),
        )

    @QtCore.pyqtSlot(str)
    def _on_easyocr_install_failed(self, error):
        self._finish_easyocr_install_state()
        self._hide_easyocr_progress()
        self._restore_settings_view()
        prev_engine = self.previous_ocr_engine or "Windows"
        self._set_ocr_combo_silently(prev_engine)
        self.save_ocr_engine(prev_engine)
        lang = self.parent.current_interface_language
        QMessageBox.warning(
            self,
            engine_text(lang, "error_title", engine="EasyOCR"),
            engine_text(lang, "install_failed", engine="EasyOCR", error=str(error)),
        )

    @QtCore.pyqtSlot()
    def _on_easyocr_install_cancelled(self):
        self._finish_easyocr_install_state()
        self._hide_easyocr_progress()
        self._restore_settings_view()
        prev_engine = self.previous_ocr_engine or "Windows"
        self._set_ocr_combo_silently(prev_engine)
        self.save_ocr_engine(prev_engine)
        lang = self.parent.current_interface_language
        QMessageBox.information(
            self,
            engine_text(lang, "cancelled_title"),
            engine_text(lang, "install_cancelled", engine="EasyOCR"),
        )

    def start_hymt_install(self):
        if (
            self._hymt_install_in_progress
            or self._tesseract_install_in_progress
            or self._rapidocr_install_in_progress
            or self._easyocr_install_in_progress
        ):
            return
        lang = self.parent.current_interface_language
        self._hymt_install_in_progress = True
        self._hymt_install_phase = "starting"
        self._hymt_cancel_requested.clear()
        self._hymt_temp_dir = ""
        self.translator_combo.setEnabled(False)
        self._set_parent_topmost_for_tesseract_install(False)
        self._show_hymt_progress(
            engine_text(lang, "preparing", engine="Hy-MT"),
            0
        )
        threading.Thread(target=self._install_hymt_worker, daemon=True).start()

    def _get_hymt_download_plan(self, is_x64=True):
        if not platform_support.IS_WINDOWS:
            # The pinned llama.cpp archive and its checksum are the Windows x64
            # build. Rather than ship an unverified binary for another system,
            # Linux users point the app at their own llama.cpp (see
            # _show_linux_hymt_hint).
            raise RuntimeError(
                "The automatic Hy-MT download is available on Windows only. "
                "Place a llama.cpp runner and the GGUF model in translators/hymt."
            )
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
            lang = getattr(getattr(self, "parent", None), "current_interface_language", "en")
            machine = platform.machine().lower()
            is_x64 = machine in ("amd64", "x86_64")
            plan = self._get_hymt_download_plan(is_x64)
            temp_dir = tempfile.mkdtemp(prefix="clickntranslate_hymt_")
            self._hymt_temp_dir = temp_dir
            package_root = os.path.join(temp_dir, "package")
            runtime_dir = os.path.join(package_root, "runtime")
            os.makedirs(runtime_dir, exist_ok=True)

            runtime_text = engine_text(lang, "hymt_runtime")
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

            extract_text = engine_text(lang, "hymt_extract")
            self._hymt_install_phase = "extracting"
            self._emit_hymt_progress(extract_text, 13)
            with zipfile.ZipFile(runtime_zip_path, "r") as zip_ref:
                zip_ref.extractall(runtime_dir)
            self._check_hymt_cancel_requested()

            runner_path = self._find_hymt_runner_under(package_root)
            if not runner_path:
                raise RuntimeError("Hy-MT runtime must contain llama-cli.exe, llama-run.exe, or hymt.exe.")

            model_text = engine_text(lang, "hymt_model")
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

            docs_text = engine_text(lang, "hymt_license")
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
            self._emit_hymt_progress(engine_text(lang, "applying"), 96)
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

            self._emit_hymt_progress(engine_text(lang, "done"), 100)
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
        lang = self.parent.current_interface_language
        if self.hymt_progress is None:
            self.hymt_progress = TesseractInstallProgressDialog(
                self,
                title=HYMT_ENGINE_DISPLAY,
                in_progress_attr="_hymt_install_in_progress",
                cancel_callback=self._request_hymt_install_cancel
            )
            self.hymt_progress.setCancelButtonText(engine_text(lang, "cancel"))
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
        self.hymt_progress.bring_to_front()

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
        lang = self.parent.current_interface_language
        self._hymt_cancel_requested.set()
        self._show_hymt_progress(engine_text(lang, "canceling"), 0, False)

    def _finish_hymt_install_state(self):
        self._hymt_install_in_progress = False
        self._hymt_install_phase = "idle"
        self._hymt_cancel_requested.clear()
        if hasattr(self, "translator_combo"):
            self.translator_combo.setEnabled(True)
        self._restore_parent_topmost_after_tesseract_install()

    @QtCore.pyqtSlot()
    def _on_hymt_install_ready(self):
        self._finish_hymt_install_state()
        self._hide_hymt_progress()
        self._restore_settings_view()
        self._reset_hymt_runtime_cache()
        self._set_translator_combo_silently(HYMT_ENGINE_KEY)
        self.auto_save_setting("translator_engine", HYMT_ENGINE_KEY)
        lang = self.parent.current_interface_language
        QMessageBox.information(
            self,
            HYMT_ENGINE_DISPLAY,
            engine_text(lang, "hymt_ready"),
        )

    @QtCore.pyqtSlot(str)
    def _on_hymt_install_failed(self, error):
        self._finish_hymt_install_state()
        self._hide_hymt_progress()
        self._restore_settings_view()
        prev_engine = self.previous_translator_engine or "google"
        self._set_translator_combo_silently(prev_engine)
        self.auto_save_setting("translator_engine", prev_engine)
        lang = self.parent.current_interface_language
        QMessageBox.warning(
            self,
            engine_text(lang, "error_title", engine="Hy-MT"),
            engine_text(lang, "install_failed", engine="Hy-MT", error=str(error)),
        )

    @QtCore.pyqtSlot()
    def _on_hymt_install_cancelled(self):
        self._finish_hymt_install_state()
        self._hide_hymt_progress()
        self._restore_settings_view()
        prev_engine = self.previous_translator_engine or "google"
        self._set_translator_combo_silently(prev_engine)
        self.auto_save_setting("translator_engine", prev_engine)
        lang = self.parent.current_interface_language
        QMessageBox.information(
            self,
            engine_text(lang, "cancelled_title"),
            engine_text(lang, "install_cancelled", engine="Hy-MT"),
        )

    def remove_hymt_engine(self):
        lang = self.parent.current_interface_language
        if self._hymt_install_in_progress:
            self._request_hymt_install_cancel()
            return
        hymt_dir = self._local_hymt_dir()
        if not os.path.isdir(hymt_dir):
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle(engine_text(lang, "remove_title", engine="Hy-MT"))
        confirm.setText(engine_text(lang, "remove_hymt_prompt"))
        confirm.setIcon(QMessageBox.Question)
        confirm.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        confirm.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        yes_btn = confirm.addButton(engine_text(lang, "remove"), QMessageBox.YesRole)
        confirm.addButton(engine_text(lang, "cancel"), QMessageBox.NoRole)
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
            QMessageBox.information(
                self,
                HYMT_ENGINE_DISPLAY,
                engine_text(lang, "removed", engine="Hy-MT"),
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                engine_text(lang, "error_title", engine="Hy-MT"),
                engine_text(lang, "remove_failed", engine="Hy-MT", error=str(e)),
            )

    def remove_ocr_engine(self):
        current = getattr(getattr(self, "ocr_engine_combo", None), "currentText", lambda: "")()
        if current == RAPIDOCR_ENGINE_DISPLAY:
            self.remove_rapidocr_engine()
            return
        if current == EASYOCR_ENGINE_DISPLAY:
            self.remove_easyocr_engine()
            return
        self.remove_tesseract_engine()

    def remove_rapidocr_engine(self):
        lang = self.parent.current_interface_language
        if self._rapidocr_install_in_progress:
            self._request_rapidocr_install_cancel()
            return
        rapidocr_dir = self._local_rapidocr_dir()
        if not os.path.isdir(rapidocr_dir):
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle(engine_text(lang, "remove_title", engine="RapidOCR"))
        confirm.setText(engine_text(lang, "remove_ocr_prompt", engine="RapidOCR"))
        confirm.setIcon(QMessageBox.Question)
        confirm.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        yes_btn = confirm.addButton(engine_text(lang, "remove"), QMessageBox.YesRole)
        confirm.addButton(engine_text(lang, "cancel"), QMessageBox.NoRole)
        confirm.exec_()
        if confirm.clickedButton() != yes_btn:
            return
        removed, error = self._delete_local_rapidocr_dir()
        try:
            if not removed:
                raise RuntimeError(error)
            if self.parent.config.get("ocr_engine") == RAPIDOCR_ENGINE_DISPLAY:
                self._set_ocr_combo_silently("Windows")
                self.save_ocr_engine("Windows")
            QMessageBox.information(
                self,
                RAPIDOCR_ENGINE_DISPLAY,
                engine_text(lang, "removed", engine="RapidOCR"),
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                engine_text(lang, "error_title", engine="RapidOCR"),
                engine_text(lang, "remove_failed", engine="RapidOCR", error=str(e)),
            )

    def remove_easyocr_engine(self):
        lang = self.parent.current_interface_language
        if self._easyocr_install_in_progress:
            self._request_easyocr_install_cancel()
            return
        easyocr_dir = self._local_easyocr_dir()
        if not os.path.isdir(easyocr_dir):
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle(engine_text(lang, "remove_title", engine="EasyOCR"))
        confirm.setText(engine_text(lang, "remove_ocr_prompt", engine="EasyOCR"))
        confirm.setIcon(QMessageBox.Question)
        confirm.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        yes_btn = confirm.addButton(engine_text(lang, "remove"), QMessageBox.YesRole)
        confirm.addButton(engine_text(lang, "cancel"), QMessageBox.NoRole)
        confirm.exec_()
        if confirm.clickedButton() != yes_btn:
            return
        removed, error = self._delete_local_easyocr_dir()
        try:
            if not removed:
                raise RuntimeError(error)
            if self.parent.config.get("ocr_engine") == EASYOCR_ENGINE_DISPLAY:
                self._set_ocr_combo_silently("Windows")
                self.save_ocr_engine("Windows")
            QMessageBox.information(
                self,
                EASYOCR_ENGINE_DISPLAY,
                engine_text(lang, "removed", engine="EasyOCR"),
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                engine_text(lang, "error_title", engine="EasyOCR"),
                engine_text(lang, "remove_failed", engine="EasyOCR", error=str(e)),
            )

    def remove_tesseract_engine(self):
        lang = self.parent.current_interface_language
        if self._tesseract_install_in_progress:
            self._request_tesseract_install_cancel()
            return
        tesseract_dir = self._local_tesseract_dir()
        if not os.path.isdir(tesseract_dir):
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle(engine_text(lang, "remove_title", engine="Tesseract"))
        confirm.setText(engine_text(lang, "remove_ocr_prompt", engine="Tesseract"))
        confirm.setIcon(QMessageBox.Question)
        confirm.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        yes_btn = confirm.addButton(engine_text(lang, "remove"), QMessageBox.YesRole)
        confirm.addButton(engine_text(lang, "cancel"), QMessageBox.NoRole)
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
            QMessageBox.information(
                self,
                "Tesseract",
                engine_text(lang, "removed", engine="Tesseract"),
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                engine_text(lang, "error_title", engine="Tesseract"),
                engine_text(lang, "remove_failed", engine="Tesseract", error=str(e)),
            )

    def clear_all_cache(self):
        """Очистить временные кэши, не затрагивая настройки, истории и модели."""
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
            total_before = stats_before["cache_bytes"]
        except Exception:
            data_dir = None
            total_before = 0

        total_cleared = 0
        ocr_logging_paused = False

        # Windows cannot delete an open rotating log. Release it briefly so
        # the cleanup really removes all diagnostics and OCR artifacts.
        try:
            import ocr
            ocr.close_ocr_diagnostics_logging()
            ocr_logging_paused = True
        except Exception:
            pass

        # 1. Clear all disposable on-disk state. User settings, histories and
        # installed engines/models are outside these explicitly scoped paths.
        if data_dir:
            try:
                total_cleared += cm_clear(data_dir, _portable_base_dir())
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

        if ocr_logging_paused:
            try:
                import ocr
                ocr.reopen_ocr_diagnostics_logging()
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
                    self._apply_action_panel_style()
                    self.clear_cache_btn.setEnabled(True)
                except Exception:
                    pass
            
            QTimer.singleShot(2000, restore_button)


    def reset_settings(self):
        """Reset behaviour settings while preserving the interface language."""
        lang = self.parent.current_interface_language
        title = settings_text(lang, "reset")
        question = settings_text(lang, "reset_question")
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(question)
        box.setIcon(QMessageBox.Question)
        box.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        yes_btn = box.addButton(settings_text(lang, "yes"), QMessageBox.YesRole)
        box.addButton(settings_text(lang, "no"), QMessageBox.NoRole)
        box.exec_()
        reply = QMessageBox.Yes if box.clickedButton() == yes_btn else QMessageBox.No
        if reply != QMessageBox.Yes:
            return
        # Default configuration
        default_config = {
            "theme": "Темная",
            # Language is identity/navigation state, not a behaviour setting.
            # Resetting it while the title-bar flag kept the previous icon made
            # the application visibly contradict itself until the next launch.
            "interface_language": lang,
            "ocr_language": "ru",
            "autostart": False,
            "autostart_backend": (
                "store_startup_task"
                if portable_paths.is_windows_packaged()
                else "startup_shortcut"
            ),
            "translation_mode": "English",
            "main_translation_source_language": "en",
            "main_translation_target_language": "ru",
            "selection_translate_source_language": "en",
            "selection_translate_target_language": "ru",
            "replace_selection_source_language": "en",
            "replace_selection_target_language": "ru",
            "hotkey_language_editor_mode": "selection",
            "ocr_hotkeys": "Ctrl+O",
            "copy_hotkey": "Ctrl+Alt+C",
            "translate_hotkey": "Ctrl+Alt+T",
            "notifications": False,
            "history": False,
            "start_minimized": False,
            "update_check_on_launch": True,
            # Do not replay already acknowledged release notes after resetting
            # unrelated behaviour settings.
            "last_seen_startup_news_version": self.parent.config.get(
                "last_seen_startup_news_version", ""
            ),
            "last_seen_startup_news_id": self.parent.config.get(
                "last_seen_startup_news_id", ""
            ),
            "show_update_info": False,
            "first_run_guide_completed": False,
            "first_run_guide_pending": False,
            "ocr_engine": platform_support.default_ocr_engine(),
            "copy_translated_text": False,
            "restore_clipboard_after_selection": True,
            "freeze_screen_on_ocr": False,
            "dim_screen_during_ocr": False,
            "ocr_dim_strength": 60,
            "debug_ocr_artifacts": False,
            "copy_history": False,
            "translator_engine": "Google",
            "allow_online_provider_fallback": False,
            "keep_visible_on_ocr": False,
            "last_ocr_language": "ru",
            "ocr_translate_source_language": "en",
            "ocr_translate_target_language": "ru",
            "fullscreen_translate_from": "en",
            "fullscreen_translate_to": "ru",
            "game_translate_source_language": "en",
            "game_translate_target_language": "ru",
            "game_capture_mode": "region",
            "game_capture_interval_ms": 850,
            "game_text_similarity": 0.90,
            "game_pause_when_inactive": True,
            "game_show_original_text": False,
            "game_overlay_opacity": 88,
            "no_screen_dimming": False,
            "fullscreen_translate_hotkey": "Ctrl+Alt+F",
            "translate_selection_hotkey": "Ctrl+Alt+Q",
            "translate_replace_selection_hotkey": "Ctrl+Shift+Q",
            "game_translate_hotkey": "Ctrl+Alt+G",
            "toggle_window_hotkey": "Ctrl+Shift+Space",
            "hotkey_defaults_revision": 5,
            "result_window_hidden_modes": [],
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
        msg_clear.addButton(no_text, QMessageBox.NoRole)
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
