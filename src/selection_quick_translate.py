"""Floating quick-translate affordance for text selected in other applications."""

from __future__ import annotations

import logging
import sys
import threading

from PyQt5 import QtCore, QtGui, QtWidgets

import mode_coordinator
import platform_support
from selection_platform import foreground_token, is_foreign_foreground, read_selected_text

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
        # OS/CLI selection reads can block. The controller coalesces these
        # ticks into one worker instead of doing that work on the GUI thread.
        self.activity.emit()


class _ProbeSignals(QtCore.QObject):
    completed = QtCore.pyqtSignal(object)


class _SelectionProbe(QtCore.QRunnable):
    def __init__(self, request, primary_text):
        super().__init__()
        self.request = request
        self.primary_text = primary_text
        self.cancelled = threading.Event()
        self.signals = _ProbeSignals()

    def run(self):
        result = dict(self.request, text="")
        target = self.request['target']
        validate = lambda: not self.cancelled.is_set() and (target is None or foreground_token() == target)
        try:
            if validate():
                result['text'] = read_selected_text(
                    allow_copy_fallback=not platform_support.IS_LINUX,
                    primary_text=self.primary_text, validate_target=validate).strip()
        except Exception:
            logger.debug('Selection probe failed', exc_info=True)
        self.signals.completed.emit(result)


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
        self._disposed = False
        self._revision = 0
        self._inflight = None
        self._probe_again = False
        self._queued_click = ""
        self._last_button_selection = None
        self._mode = "button"
        self._button = SelectionQuickButton()
        self._button.clicked.connect(self._on_button_clicked)
        self._pending_text = ""
        self._pending_target = None
        self._last_auto_text = ""
        self._anchor = QtCore.QPoint()
        self._debounce = QtCore.QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._complete_probe)
        self._hide_timer = QtCore.QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(HIDE_TIMEOUT_MS)
        self._hide_timer.timeout.connect(self._dismiss_selection)
        self._activity_monitors = []
        self._mode_unsubscribe = mode_coordinator.subscribe(self._on_mode_changed)
        owner.destroyed.connect(self.dispose)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        self._cancel_probe()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._mode_unsubscribe()
        self.set_active(False)
        self._button.hide()
        self._button.deleteLater()

    def configure(self, enabled, mode):
        self._cancel_probe()
        self._revision += 1
        self._dismiss_selection()
        self._last_button_selection = None
        self._mode = mode if mode in ("button", "automatic") else "button"
        self.clear_auto_dedupe()
        self.set_active(bool(enabled))

    def clear_auto_dedupe(self):
        """Allow the same selection to fire automatic translate again."""
        self._last_auto_text = ""

    def set_active(self, enabled):
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        self._revision += 1
        self._debounce.stop()
        self._probe_again = False
        self._queued_click = ""
        self._dismiss_selection()
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
                "es": "Activa Accesibilidad para traducir el texto seleccionado",
                "de": "Bedienungshilfen für die Auswahlübersetzung aktivieren",
                "fr": "Activez l’accessibilité pour traduire le texte sélectionné",
                "zh": "请启用辅助功能以翻译选中的文字",

                'pt': 'Ative a acessibilidade para tradução de seleção rápida',
                'it': "Abilita l'accessibilità per la traduzione rapida della selezione",
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
            monitor.activity.connect(self._schedule_probe if platform_support.IS_WINDOWS else self._complete_probe)
            monitor.start()

    def _stop_monitor(self):
        monitors = list(getattr(self, "_activity_monitors", []) or [])
        self._activity_monitors = []
        for monitor in monitors:
            monitor.stop()
            monitor.deleteLater()

    def _on_mode_changed(self):
        self._cancel_probe()
        self._revision += 1
        self._debounce.stop()
        self._probe_again = False
        self._queued_click = ""
        self._dismiss_selection()

    def eventFilter(self, watched, event):
        if not self._enabled:
            return False
        if event.type() == QtCore.QEvent.MouseButtonPress and self._button.isVisible():
            global_pos = event.globalPos()
            if not self._button.geometry().contains(global_pos):
                self._dismiss_selection()
        if event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
            self._dismiss_selection()
        return False

    def _schedule_probe(self):
        self._cancel_probe()
        self._revision += 1
        self._dismiss_selection()
        self._last_button_selection = None
        if not self._should_accept_activity():
            return
        self._anchor = QtGui.QCursor.pos()
        self._debounce.start()

    def _should_accept_activity(self):
        if not self._enabled or self._disposed:
            return False
        if mode_coordinator.active_mode() is not None:
            return False
        if QtWidgets.QApplication.activeModalWidget() is not None:
            return False
        if not is_foreign_foreground():
            return False
        return True

    def _dismiss_selection(self):
        self._button.hide()
        self._hide_timer.stop()
        self._pending_text = ""
        self._pending_target = None

    def _cancel_probe(self):
        if self._inflight is not None:
            self._inflight.cancelled.set()

    def _complete_probe(self, clicked_text=""):
        if not self._should_accept_activity():
            self._dismiss_selection()
            return
        if self._inflight is not None:
            self._probe_again = True
            self._queued_click = clicked_text or self._queued_click
            return
        target = foreground_token()
        if self._pending_text and self._pending_target != target:
            self._dismiss_selection()
        # Qt clipboard access stays on its owning thread. CLI fallbacks and
        # Accessibility/UIA/Ctrl+C reads run in the bounded worker below.
        primary_text = None
        if platform_support.IS_LINUX:
            clipboard = QtWidgets.QApplication.clipboard()
            primary_text = clipboard.text(clipboard.Selection) if clipboard.supportsSelection() else ""
        request = dict(revision=self._revision, target=target, clicked=clicked_text)
        task = _SelectionProbe(request, primary_text)
        task.signals.completed.connect(self._probe_finished)
        self._inflight = task
        QtCore.QThreadPool.globalInstance().start(task)

    @QtCore.pyqtSlot(object)
    def _probe_finished(self, result):
        self._inflight = None
        if self._disposed:
            return
        valid = (result['revision'] == self._revision and self._should_accept_activity()
                 and result['target'] == foreground_token())
        if valid:
            self._accept_probe(result)
        else:
            self._dismiss_selection()
        if self._probe_again:
            clicked = self._queued_click
            self._probe_again, self._queued_click = False, ""
            if clicked or not self._debounce.isActive():
                self._complete_probe(clicked)

    def _accept_probe(self, result):
        text, target = result['text'], result['target']
        if len(text) < MIN_SELECTION_CHARS:
            self._dismiss_selection()
            self._last_button_selection = None
            self.clear_auto_dedupe()
            return
        if result['clicked']:
            self._dismiss_selection()
            if text == result['clicked']:
                self.translate_requested.emit(text)
            return
        if self._mode == "automatic":
            if (target, text) == self._last_auto_text:
                return
            self._last_auto_text = (target, text)
            self.translate_requested.emit(text)
            return
        if self._last_button_selection == (target, text):
            return
        self._last_button_selection = (target, text)
        self._pending_text = text
        self._pending_target = target
        self._anchor = QtGui.QCursor.pos()
        self._button.show_near(self._anchor)
        self._hide_timer.start()

    def _on_button_clicked(self):
        text = self._pending_text.strip()
        valid = self._should_accept_activity() and self._pending_target == foreground_token()
        self._revision += 1
        self._cancel_probe()
        self._dismiss_selection()
        if valid and len(text) >= MIN_SELECTION_CHARS:
            self._complete_probe(clicked_text=text)
