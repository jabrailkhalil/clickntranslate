"""Shared, consistently styled dialogs used by every application process."""

from __future__ import annotations

import ctypes
import logging
import os
import re
import sys
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets


def install_qt_exception_guard() -> None:
    """Log uncaught Qt callback errors instead of letting PyQt abort the GUI."""
    if getattr(sys.excepthook, "_clickntranslate_qt_guard", False):
        return

    previous_hook = sys.excepthook

    def _guard(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            previous_hook(exc_type, exc_value, exc_traceback)
            return
        try:
            logging.getLogger("clickntranslate.qt").critical(
                "Unhandled exception in Qt callback",
                exc_info=(exc_type, exc_value, exc_traceback),
            )
        except Exception:
            try:
                previous_hook(exc_type, exc_value, exc_traceback)
            except Exception:
                pass

    _guard._clickntranslate_qt_guard = True
    sys.excepthook = _guard


def _resource_path(relative_path: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / relative_path)


def _theme_value(widget) -> str:
    """Find the nearest explicit application theme without importing app modules."""
    seen = set()
    current = widget
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        try:
            for attr in ("current_theme", "theme"):
                value = getattr(current, attr, None)
                if isinstance(value, str) and value:
                    return value.lower()

            owner = getattr(current, "owner", None)
            if owner is not None:
                current = owner
                continue

            # SettingsWindow intentionally stores its QWidget parent in a
            # ``parent`` instance attribute, shadowing QObject.parent().  Both
            # forms are valid in this project, so never assume it is callable.
            parent_ref = getattr(current, "parent", None)
            current = parent_ref() if callable(parent_ref) else parent_ref
        except (RuntimeError, TypeError):
            # Theme detection must never escape into a Qt signal handler: an
            # unhandled Python exception there aborts a windowed PyQt process.
            return ""
    return ""


def _uses_dark_theme(widget=None) -> bool:
    value = _theme_value(widget)
    if not value:
        app = QtWidgets.QApplication.instance()
        value = _theme_value(app.activeWindow()) if app is not None else ""
    if any(marker in value for marker in ("свет", "light")):
        return False
    if any(marker in value for marker in ("тем", "dark")):
        return True
    # The application's default and release screenshots use the dark theme.
    return True


def apply_dark_native_frame(widget, enabled: bool = True) -> None:
    """Ask Windows to render a native Qt dialog frame with a dark title bar."""
    if os.name != "nt" or widget is None:
        return
    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(1 if enabled else 0)
        dwmapi = ctypes.windll.dwmapi
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE variants
            try:
                if dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
                ) == 0:
                    break
            except Exception:
                continue
        if enabled:
            # Caption, caption text and border colors on current Windows builds.
            for attribute, color in ((35, 0x00151515), (36, 0x00FFFFFF), (34, 0x002C2C2C)):
                try:
                    color_value = ctypes.c_uint(color)
                    dwmapi.DwmSetWindowAttribute(
                        hwnd,
                        attribute,
                        ctypes.byref(color_value),
                        ctypes.sizeof(color_value),
                    )
                except Exception:
                    continue
    except Exception:
        pass


class NativeDialogFrameFilter(QtCore.QObject):
    """Keeps the title bars of remaining native Qt dialogs consistently dark."""

    def eventFilter(self, watched, event):
        if (
            event.type() == QtCore.QEvent.Show
            and isinstance(watched, QtWidgets.QDialog)
            and not (watched.windowFlags() & QtCore.Qt.FramelessWindowHint)
        ):
            QtCore.QTimer.singleShot(0, lambda dialog=watched: apply_dark_native_frame(dialog, True))
        return super().eventFilter(watched, event)


class _TitleBar(QtWidgets.QFrame):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self._drag_offset = None
        self.setObjectName("styledMessageTitleBar")
        self.setFixedHeight(42)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 6, 0)
        layout.setSpacing(9)

        self.icon_label = QtWidgets.QLabel(self)
        self.icon_label.setObjectName("styledMessageAppIcon")
        self.icon_label.setFixedSize(20, 20)
        icon = QtGui.QIcon(_resource_path("icons/icon.ico"))
        if not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(18, 18))
        layout.addWidget(self.icon_label)

        self.title_label = QtWidgets.QLabel(self)
        self.title_label.setObjectName("styledMessageTitle")
        layout.addWidget(self.title_label, 1)

        self.close_button = QtWidgets.QToolButton(self)
        self.close_button.setObjectName("styledMessageClose")
        self.close_button.setText("×")
        self.close_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_button.setFixedSize(34, 32)
        self.close_button.setToolTip("Close")
        self.close_button.clicked.connect(dialog.reject)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.dialog.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.dialog.move(event.globalPos() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class StyledMessageBox(QtWidgets.QMessageBox):
    """Drop-in QMessageBox with the same chrome as Click'n'Translate windows."""

    _TITLE_HEIGHT = 42

    def __init__(self, parent=None):
        self._styled_ready = False
        self._external_stylesheet = ""
        super().__init__(parent)
        self._styled_ready = True
        self._dark = _uses_dark_theme(parent)
        self._message_icon = self.NoIcon
        self._positioned = False

        self.setWindowFlags(
            (self.windowFlags() | QtCore.Qt.Dialog)
            & ~QtCore.Qt.WindowContextHelpButtonHint
            | QtCore.Qt.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        self.setObjectName("styledMessageBox")
        self.setMinimumWidth(500)
        self.setMaximumWidth(650)

        layout = self.layout()
        if layout is not None:
            margins = layout.contentsMargins()
            layout.setContentsMargins(
                max(20, margins.left()),
                self._TITLE_HEIGHT + 18,
                max(20, margins.right()),
                max(16, margins.bottom()),
            )

        self.title_bar = _TitleBar(self)
        self.title_bar.raise_()
        self._apply_style()

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        bar = getattr(self, "title_bar", None)
        if bar is not None:
            bar.title_label.setText(str(title))

    def setWindowIcon(self, icon):
        super().setWindowIcon(icon)
        bar = getattr(self, "title_bar", None)
        if bar is not None and isinstance(icon, QtGui.QIcon) and not icon.isNull():
            bar.icon_label.setPixmap(icon.pixmap(18, 18))

    def setIcon(self, icon):
        self._message_icon = icon
        super().setIcon(icon)
        if getattr(self, "_styled_ready", False):
            QtCore.QTimer.singleShot(0, self._refresh_status_icon)

    def setIconPixmap(self, pixmap):
        self._message_icon = None
        super().setIconPixmap(pixmap)

    def setStyleSheet(self, style):
        if not getattr(self, "_styled_ready", False):
            super().setStyleSheet(style)
            return
        self._external_stylesheet = str(style or "")
        white_box = re.search(
            r"QMessageBox\s*\{[^}]*background(?:-color)?\s*:\s*(?:#fff(?:fff)?|white)",
            self._external_stylesheet,
            re.IGNORECASE | re.DOTALL,
        )
        dark_box = re.search(
            r"QMessageBox\s*\{[^}]*background(?:-color)?\s*:\s*(?:#(?:0[0-9a-f]{5}|1[0-9a-f]{5}|2[0-9a-f]{5})|black)",
            self._external_stylesheet,
            re.IGNORECASE | re.DOTALL,
        )
        if white_box:
            self._dark = False
        elif dark_box:
            self._dark = True
        self._apply_style()

    def _apply_style(self):
        dark = getattr(self, "_dark", True)
        background = "#101114" if dark else "#f8f8fb"
        panel = "#17181d" if dark else "#ffffff"
        text = "#f5f5f7" if dark else "#17171a"
        muted = "#b8b8c2" if dark else "#55545e"
        border = "#33313c" if dark else "#d7d3df"
        button = "#211f28" if dark else "#ffffff"
        button_hover = "#322d3d" if dark else "#eee9f5"
        qss = f"""
            QWidget#styledMessageBox {{
                background: {background};
                color: {text};
                border: 1px solid {border};
            }}
            QFrame#styledMessageTitleBar {{
                background: #151515;
                border: none;
                border-bottom: 1px solid #29292d;
            }}
            QLabel#styledMessageTitle {{
                color: #f7f7f7;
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#styledMessageAppIcon {{
                background: transparent;
                border: none;
            }}
            QToolButton#styledMessageClose {{
                color: #eeeeee;
                background: transparent;
                border: none;
                border-radius: 4px;
                font-size: 22px;
                font-weight: 300;
            }}
            QToolButton#styledMessageClose:hover {{
                color: #ffffff;
                background: #c42b1c;
            }}
            QWidget#styledMessageBox QLabel {{
                color: {text};
                background: transparent;
                border: none;
                font-size: 13px;
            }}
            QWidget#styledMessageBox QLabel#qt_msgbox_informativelabel {{
                color: {muted};
                font-size: 12px;
            }}
            QWidget#styledMessageBox QPushButton {{
                min-width: 92px;
                min-height: 34px;
                padding: 0 14px;
                color: {text};
                background: {button};
                border: 1px solid #8060a8;
                border-radius: 5px;
                font-size: 13px;
                font-weight: 500;
            }}
            QWidget#styledMessageBox QPushButton:hover {{
                background: {button_hover};
                border-color: #a985d2;
            }}
            QWidget#styledMessageBox QPushButton:pressed {{
                background: #735397;
                color: #ffffff;
            }}
            QWidget#styledMessageBox QPushButton:default {{
                background: #7959a0;
                color: #ffffff;
                border-color: #a985d2;
            }}
        """
        super().setStyleSheet((self._external_stylesheet + "\n" + qss).strip())

    def _status_color_and_glyph(self):
        icon = self._message_icon
        if icon == self.Question:
            return "#2788d7", "?"
        if icon == self.Warning:
            return "#e7a619", "!"
        if icon == self.Critical:
            return "#d94a4a", "×"
        if icon == self.Information:
            return "#7959a0", "i"
        return None, ""

    def _status_pixmap(self, size=42):
        color, glyph = self._status_color_and_glyph()
        if color is None:
            return QtGui.QPixmap()
        ratio = max(1.0, float(self.devicePixelRatioF()))
        px = int(size * ratio)
        pixmap = QtGui.QPixmap(px, px)
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(color))
        painter.drawEllipse(QtCore.QRectF(2, 2, size - 4, size - 4))
        font = QtGui.QFont("Segoe UI", 21)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#ffffff"))
        painter.drawText(QtCore.QRectF(0, 0, size, size), QtCore.Qt.AlignCenter, glyph)
        painter.end()
        return pixmap

    def _refresh_status_icon(self):
        label = self.findChild(QtWidgets.QLabel, "qt_msgboxex_icon_label")
        if label is None:
            return
        pixmap = self._status_pixmap()
        if pixmap.isNull():
            label.hide()
            return
        label.setFixedSize(48, 48)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setPixmap(pixmap)
        label.show()

    def _prepare_contents(self):
        layout = self.layout()
        if layout is not None:
            layout.setContentsMargins(20, self._TITLE_HEIGHT + 18, 20, 16)
        for label in self.findChildren(QtWidgets.QLabel):
            if label.objectName() in {
                "styledMessageTitle",
                "styledMessageAppIcon",
                "qt_msgboxex_icon_label",
            }:
                continue
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setMaximumWidth(505)
        self._refresh_status_icon()
        if layout is not None:
            layout.invalidate()
            layout.activate()
        self.adjustSize()
        if self.width() < self.minimumWidth():
            self.resize(self.minimumWidth(), self.height())
        bar = getattr(self, "title_bar", None)
        if bar is not None:
            bar.title_label.setText(self.windowTitle())
            bar.setGeometry(0, 0, self.width(), self._TITLE_HEIGHT)
            bar.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        bar = getattr(self, "title_bar", None)
        if bar is not None:
            bar.setGeometry(0, 0, self.width(), self._TITLE_HEIGHT)
            bar.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._finish_show)

    def _finish_show(self):
        self._prepare_contents()
        if not self._positioned:
            self._positioned = True
            self._center_on_owner()

    def _center_on_owner(self):
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            available = QtWidgets.QApplication.desktop().availableGeometry(parent)
            # SettingsWindow is embedded inside the frameless main window, so
            # its frameGeometry is parent-relative. Convert its visible center
            # to desktop coordinates before positioning this top-level dialog.
            center = parent.mapToGlobal(parent.rect().center())
        else:
            app = QtWidgets.QApplication.instance()
            active = app.activeWindow() if app is not None else None
            if active is not None and active is not self and active.isVisible():
                available = QtWidgets.QApplication.desktop().availableGeometry(active)
                center = active.mapToGlobal(active.rect().center())
            else:
                available = QtWidgets.QApplication.desktop().availableGeometry(self)
                center = available.center()
        frame = self.frameGeometry()
        frame.moveCenter(center)
        x = max(available.left(), min(frame.left(), available.right() - frame.width() + 1))
        y = max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1))
        self.move(x, y)

    @classmethod
    def _run_standard(cls, parent, title, text, icon, buttons, default_button):
        box = cls(parent)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(icon)
        box.setStandardButtons(buttons)
        if default_button not in (cls.NoButton, None):
            try:
                box.setDefaultButton(default_button)
            except TypeError:
                pass
        return box.exec_()

    @classmethod
    def information(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(
            parent,
            title,
            text,
            cls.Information,
            cls.Ok if buttons is None else buttons,
            cls.NoButton if defaultButton is None else defaultButton,
        )

    @classmethod
    def warning(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(
            parent,
            title,
            text,
            cls.Warning,
            cls.Ok if buttons is None else buttons,
            cls.NoButton if defaultButton is None else defaultButton,
        )

    @classmethod
    def critical(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(
            parent,
            title,
            text,
            cls.Critical,
            cls.Ok if buttons is None else buttons,
            cls.NoButton if defaultButton is None else defaultButton,
        )

    @classmethod
    def question(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(
            parent,
            title,
            text,
            cls.Question,
            (cls.Yes | cls.No) if buttons is None else buttons,
            cls.NoButton if defaultButton is None else defaultButton,
        )
