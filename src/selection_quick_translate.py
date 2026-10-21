"""Floating quick-translate affordance for text selected in other applications."""

from __future__ import annotations

import logging
import sys

from PyQt5 import QtCore, QtGui, QtWidgets

import mode_coordinator
import platform_support
from selection_platform import is_foreign_foreground, read_selected_text

logger = logging.getLogger("clickntranslate.selection")

DEBOUNCE_MS = 420
HIDE_TIMEOUT_MS = 9000
MIN_SELECTION_CHARS = 2
LINUX_POLL_MS = 350


def _resource_path(relative_path):
    from pathlib import Path

    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(root / relative_path)


class SelectionQuickButton(QtWidgets.QToolButton):
    def __init__(self):
        flags = QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
        flags |= QtCore.Qt.WindowDoesNotAcceptFocus
        if sys.platform == "darwin":
            flags |= QtCore.Qt.NoDropShadowWindowHint
        super().__init__(None)
        self.setWindowFlags(flags)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        if sys.platform == "darwin":
            self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self.setIconSize(QtCore.QSize(22, 22))
        self.setFixedSize(34, 34)
        icon = QtGui.QIcon(_resource_path("icons/icon.png"))
        if icon.isNull():
            icon = QtGui.QIcon(_resource_path("icons/icon.ico"))
        self.setIcon(icon)
        self.setStyleSheet(
            "QToolButton { background: rgba(18, 18, 18, 210); border: 1px solid #584963; border-radius: 17px; }"
            "QToolButton:hover { background: rgba(40, 32, 48, 230); }"
        )
        self._anchor = QtCore.QPoint()

    def show_near(self, anchor):
        self._anchor = QtCore.QPoint(anchor)
        self.adjustSize()
        from styled_dialogs import position_popup_near_cursor

        position_popup_near_cursor(self, self._anchor)
        self.show()
        self.raise_()


class _SelectionChangePoller(QtCore.QObject):
    """Detect new non-empty selection text while another app is in the foreground."""

    activity = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(LINUX_POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._last = ""

    def start(self):
        self._last = ""
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._last = ""

    def _poll(self):
        if not is_foreign_foreground():
            self._last = ""
            return
        current = read_selected_text()
        if current != self._last:
            self._last = current
            if current:
                self.activity.emit()


class _WindowsMouseReleasePoller(QtCore.QObject):
    activity = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._poll)
        self._left_down = False

    def start(self):
        self._left_down = False
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._left_down = False

    def _poll(self):
        import ctypes

        down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        if self._left_down and not down and is_foreign_foreground():
            self.activity.emit()
        self._left_down = down


class SelectionQuickTranslateController(QtCore.QObject):
    translate_requested = QtCore.pyqtSignal(str)

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._enabled = False
        self._mode = "button"
        self._button = SelectionQuickButton()
        self._button.clicked.connect(self._on_button_clicked)
        self._pending_text = ""
        self._last_auto_text = ""
        self._anchor = QtCore.QPoint()
        self._debounce = QtCore.QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._complete_probe)
        self._hide_timer = QtCore.QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(HIDE_TIMEOUT_MS)
        self._hide_timer.timeout.connect(self._button.hide)
        self._activity_monitors = []
        self._mode_unsubscribe = mode_coordinator.subscribe(self._on_mode_changed)
        owner.destroyed.connect(self.dispose)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def dispose(self):
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._mode_unsubscribe()
        self.set_active(False)
        self._button.hide()
        self._button.deleteLater()

    def configure(self, enabled, mode):
        self._mode = mode if mode in ("button", "automatic") else "button"
        self.set_active(bool(enabled))

    def set_active(self, enabled):
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        self._button.hide()
        self._stop_monitor()
        if not enabled:
            return
        if platform_support.IS_MAC:
            from macos_desktop import permission_granted

            if not permission_granted("accessibility"):
                checker = getattr(self.owner, "ensure_mac_accessibility_for_selection", None)
                if callable(checker) and not checker():
                    self._enabled = False
                    self._notify_owner("selection_quick_translate_accessibility")
                    return
        self._start_monitor()

    def _notify_owner(self, message_key):
        show = getattr(self.owner, "_show_status_signal", None)
        if show is None:
            return
        lang = getattr(self.owner, "current_interface_language", "en")
        messages = {
            "selection_quick_translate_accessibility": {
                "en": "Enable Accessibility for quick selection translate",
                "ru": "Включите универсальный доступ для быстрого перевода выделения",
            }
        }
        localized = messages.get(message_key, {})
        body = localized.get(lang) or localized.get("en", "")
        if body:
            show.emit(body)

    def _start_monitor(self):
        monitors = []
        if platform_support.IS_LINUX:
            monitors.append(_SelectionChangePoller(self))
        elif platform_support.IS_MAC:
            monitors.append(_SelectionChangePoller(self))
        elif platform_support.IS_WINDOWS:
            monitors.append(_WindowsMouseReleasePoller(self))
        else:
            return
        self._activity_monitors = monitors
        for monitor in monitors:
            monitor.activity.connect(self._schedule_probe)
            monitor.start()

    def _stop_monitor(self):
        monitors = list(getattr(self, "_activity_monitors", []) or [])
        self._activity_monitors = []
        for monitor in monitors:
            monitor.stop()
            monitor.deleteLater()

    def _on_mode_changed(self):
        if mode_coordinator.active_mode() is not None:
            self._button.hide()

    def eventFilter(self, watched, event):
        if not self._enabled:
            return False
        if event.type() == QtCore.QEvent.MouseButtonPress and self._button.isVisible():
            global_pos = event.globalPos()
            if not self._button.geometry().contains(global_pos):
                self._button.hide()
        if event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
            self._button.hide()
        return False

    def _schedule_probe(self):
        if not self._should_accept_activity():
            return
        self._anchor = QtGui.QCursor.pos()
        self._debounce.start()

    def _should_accept_activity(self):
        if not self._enabled:
            return False
        if mode_coordinator.active_mode() is not None:
            return False
        if QtWidgets.QApplication.activeModalWidget() is not None:
            return False
        if not is_foreign_foreground():
            return False
        return True

    def _read_probe_text(self):
        return read_selected_text(
            allow_copy_fallback=not platform_support.IS_LINUX
        ).strip()

    def _complete_probe(self):
        if not self._should_accept_activity():
            return
        text = self._read_probe_text()
        if len(text) < MIN_SELECTION_CHARS:
            return
        if self._mode == "automatic":
            if text == self._last_auto_text:
                return
            self._last_auto_text = text
            self.translate_requested.emit(text)
            return
        self._pending_text = text
        self._button.show_near(self._anchor)
        self._hide_timer.start()

    def _on_button_clicked(self):
        text = self._pending_text.strip()
        if len(text) < MIN_SELECTION_CHARS:
            text = read_selected_text(
                allow_copy_fallback=not platform_support.IS_LINUX
            ).strip()
        self._button.hide()
        if len(text) >= MIN_SELECTION_CHARS:
            self.translate_requested.emit(text)
