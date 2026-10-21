"""Floating quick-translate affordance for text selected in other applications."""

from __future__ import annotations

import logging
import sys
import threading
import weakref

from PyQt5 import QtCore, QtGui, QtWidgets, sip

import mode_coordinator
import platform_support
from selection_platform import is_foreign_foreground, read_selected_text

logger = logging.getLogger("clickntranslate.selection")

DEBOUNCE_MS = 280
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


class _LinuxSelectionPoller(QtCore.QObject):
    activity = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(LINUX_POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._last = ""

    def start(self):
        self._last = read_selected_text()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._last = ""

    def _poll(self):
        current = read_selected_text()
        if current != self._last:
            self._last = current
            if current:
                self.activity.emit()


class _MacMouseMonitor(QtCore.QObject):
    activity = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._monitor = None

    def start(self):
        if self._monitor is not None:
            return
        import AppKit

        mask = AppKit.NSEventMaskLeftMouseUp
        reference = weakref.ref(self)

        def handler(event):
            helper = reference()
            if helper is not None and not sip.isdeleted(helper):
                helper.activity.emit()
            return event

        self._monitor = AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, handler)

    def stop(self):
        if self._monitor is None:
            return
        import AppKit

        AppKit.NSEvent.removeMonitor_(self._monitor)
        self._monitor = None


class _WindowsMouseMonitor(QtCore.QObject):
    activity = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None

    def start(self):
        if self._thread is not None:
            return
        reference = weakref.ref(self)
        self._thread = _WindowsMouseHookThread(reference)
        self._thread.activity.connect(self.activity.emit)
        self._thread.start()

    def stop(self):
        if self._thread is None:
            return
        self._thread.stop()
        self._thread.join(timeout=1.0)
        self._thread = None


class _WindowsMouseHookThread(QtCore.QThread):
    activity = QtCore.pyqtSignal()

    def __init__(self, owner_ref):
        super().__init__()
        self._owner_ref = owner_ref
        self._cancelled = threading.Event()
        self._thread_id = None

    def stop(self):
        self._cancelled.set()
        if self._thread_id:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)

    def run(self):
        import ctypes
        from ctypes import wintypes

        if sys.platform != "win32":
            return
        user = ctypes.WinDLL("user32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)

        class MouseHookStruct(ctypes.Structure):
            _fields_ = [
                ("pt", wintypes.POINT),
                ("hwnd", wintypes.HWND),
                ("wHitTestCode", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        WM_LBUTTONUP = 0x0202

        @callback_type
        def callback(code, message, address):
            if code == 0 and message == WM_LBUTTONUP and not self._cancelled.is_set():
                owner = self._owner_ref()
                if owner is not None and not sip.isdeleted(owner):
                    self.activity.emit()
            return user.CallNextHookEx(None, code, message, address)

        self._thread_id = kernel.GetCurrentThreadId()
        hook = user.SetWindowsHookExW(14, callback, kernel.GetModuleHandleW(None), 0)
        if not hook:
            logger.warning("Could not install selection mouse hook")
            return
        msg = wintypes.MSG()
        try:
            while not self._cancelled.is_set():
                result = user.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result <= 0:
                    break
                user.TranslateMessage(ctypes.byref(msg))
                user.DispatchMessageW(ctypes.byref(msg))
        finally:
            user.UnhookWindowsHookEx(hook)


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
        self._activity_monitor = None
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
                    return
        self._start_monitor()

    def _start_monitor(self):
        if platform_support.IS_LINUX:
            self._activity_monitor = _LinuxSelectionPoller(self)
        elif platform_support.IS_MAC:
            self._activity_monitor = _MacMouseMonitor(self)
        elif platform_support.IS_WINDOWS:
            self._activity_monitor = _WindowsMouseMonitor(self)
        else:
            return
        self._activity_monitor.activity.connect(self._schedule_probe)
        self._activity_monitor.start()

    def _stop_monitor(self):
        monitor = self._activity_monitor
        self._activity_monitor = None
        if monitor is not None:
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

    def _complete_probe(self):
        if not self._should_accept_activity():
            return
        allow_copy = platform_support.IS_WINDOWS and self._mode == "automatic"
        text = read_selected_text(allow_copy_fallback=allow_copy)
        if len(text.strip()) < MIN_SELECTION_CHARS:
            self._button.hide()
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
            allow_copy = platform_support.IS_WINDOWS
            text = read_selected_text(allow_copy_fallback=allow_copy).strip()
        self._button.hide()
        if len(text) >= MIN_SELECTION_CHARS:
            self.translate_requested.emit(text)
