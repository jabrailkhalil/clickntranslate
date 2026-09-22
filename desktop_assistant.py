"""Optional, stationary desktop companion and shortcuts to existing workflows.

No keyboard hooks, screen polling, translation engine or network access lives
here. Capture ownership hides both windows before the first screenshot.
"""
from pathlib import Path
import logging
import math
import sys

from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_text import assistant_text
from button_styles import button_qss
import mode_coordinator


CAPTURE_ACTIONS = frozenset(('screen', 'area', 'dynamic', 'copy'))
ACTION_METHODS = {
    'screen': 'launch_fullscreen_translate', 'area': 'launch_translate',
    'dynamic': 'launch_game_translate', 'copy': 'launch_copy',
    'documents': 'open_document_translation', 'guide': 'start_first_run_guide',
}


def clamp_position(point, size, bounds):
    return QtCore.QPoint(
        max(bounds.left(), min(point.x(), bounds.right() - size.width() + 1)),
        max(bounds.top(), min(point.y(), bounds.bottom() - size.height() + 1)),
    )


def normalized_position(value):
    if not isinstance(value, dict) or not isinstance(value.get('screen'), str):
        return None
    try:
        x, y = float(value['x']), float(value['y'])
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        return dict(screen=value['screen'], x=max(0., min(x, 1.)), y=max(0., min(y, 1.)))
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


class AssistantAnchor(QtWidgets.QWidget):
    clicked = QtCore.pyqtSignal()
    relocated = QtCore.pyqtSignal()

    def __init__(self):
        flags = QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
        flags |= QtCore.Qt.WindowDoesNotAcceptFocus
        super().__init__(None, flags)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedSize(84, 84)
        self._press = None
        self._dragging = False
        self._hover = False
        self.dark = True
        resource_root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        self.movie = QtGui.QMovie(str(resource_root / 'icons/desktop-assistant/kirby.gif'), parent=self)
        self.movie.setCacheMode(QtGui.QMovie.CacheAll)
        # The upstream GIF has a large transparent margin. Use one stable
        # union for every frame so the character has a useful size and does
        # not wobble when its feet move; the source asset stays unchanged.
        self._sprite_bounds = QtCore.QRect()
        for index in range(self.movie.frameCount()):
            self.movie.jumpToFrame(index)
            bounds = QtGui.QRegion(self.movie.currentPixmap().mask()).boundingRect()
            self._sprite_bounds = self._sprite_bounds.united(bounds)
        self.movie.jumpToFrame(0)
        self.movie.frameChanged.connect(lambda _: self.update())

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        if self._hover:
            painter.setBrush(QtGui.QColor('#3c314e' if self.dark else '#eee4f7'))
            painter.setPen(QtGui.QColor('#9279ac' if self.dark else '#a18ab7'))
            painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))
        pixmap = self.movie.currentPixmap()
        if not pixmap.isNull():
            source = self._sprite_bounds if not self._sprite_bounds.isEmpty() else pixmap.rect()
            size = source.size().scaled(64, 64, QtCore.Qt.KeepAspectRatio)
            target = QtCore.QRect((self.width() - size.width()) // 2,
                                 (self.height() - size.height()) // 2, size.width(), size.height())
            painter.drawPixmap(target, pixmap, source)
        else:
            painter.setPen(QtGui.QColor('#c9b1e7' if self.dark else '#755295'))
            painter.setFont(QtGui.QFont('Segoe UI', 32))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, '✦')

    def showEvent(self, event):
        super().showEvent(event)
        if self.movie.state() == QtGui.QMovie.NotRunning:
            self.movie.start()
        self.movie.setPaused(False)

    def hideEvent(self, event):
        self.movie.setPaused(True)
        self._press = None
        self._hover = False
        super().hideEvent(event)

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press = event.globalPos()
            self._origin = self.pos()
            self._dragging = False
            event.accept()

    def mouseMoveEvent(self, event):
        if self._press is None or not event.buttons() & QtCore.Qt.LeftButton:
            return
        offset = event.globalPos() - self._press
        if offset.manhattanLength() >= QtWidgets.QApplication.startDragDistance():
            self._dragging = True
        if self._dragging:
            screen = QtWidgets.QApplication.screenAt(event.globalPos()) or self.screen()
            self.move(clamp_position(self._origin + offset, self.size(), screen.availableGeometry()))

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.clicked.emit()
        elif event.button() == QtCore.Qt.LeftButton and self._press is not None:
            moved = self._dragging
            self._press = None
            if moved:
                self.relocated.emit()
            else:
                self.clicked.emit()


class ActionButton(QtWidgets.QPushButton):
    def __init__(self, title, description, dark, parent=None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        self.setStyleSheet(button_qss(dark, 'quiet') + 'QPushButton { text-align:left; padding:0; }')
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)
        for text, bold in ((title, True), (description, False)):
            label = QtWidgets.QLabel(text)
            label.setWordWrap(True)
            label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            color = ('#f5f0fa' if dark else '#302837') if bold else ('#bdb2ca' if dark else '#70647e')
            label.setStyleSheet(f'color:{color}; background:transparent; border:none; font-size:{13 if bold else 12}px; font-weight:{600 if bold else 400};')
            layout.addWidget(label)
        policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def sizeHint(self):
        return self.layout().totalSizeHint()

    def heightForWidth(self, width):
        return self.layout().totalHeightForWidth(width)


class AssistantMenu(QtWidgets.QFrame):
    action_requested = QtCore.pyqtSignal(str)

    def __init__(self, language, dark):
        super().__init__(None, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setObjectName('desktopAssistantMenu')
        self.setWindowTitle(assistant_text(language, 'title'))
        background, border = ('#201d28', '#746087') if dark else ('#f7f3fa', '#a18bb9')
        self.setStyleSheet(f'QFrame#desktopAssistantMenu {{ background:{background}; border:1px solid {border}; border-radius:10px; }}')
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 10, 8, 8)
        outer.setSpacing(5)
        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(assistant_text(language, 'title'))
        title.setStyleSheet(f'color:{"#f5f0fa" if dark else "#302837"}; font-size:16px; font-weight:600; padding-left:8px;')
        title_row.addWidget(title, 1)
        close = QtWidgets.QPushButton('×')
        close.setAccessibleName(assistant_text(language, 'hide'))
        close.setFixedSize(28, 28)
        close.setStyleSheet(button_qss(dark, 'close', icon=True))
        close.clicked.connect(self.hide)
        title_row.addWidget(close)
        outer.addLayout(title_row)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background:transparent; border:none; }')
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.buttons = {}
        for action in ('screen', 'area', 'dynamic', 'copy', 'text', 'documents'):
            button = ActionButton(*assistant_text(language, action), dark)
            button.clicked.connect(lambda checked=False, key=action: self.action_requested.emit(key))
            layout.addWidget(button)
            self.buttons[action] = button
        footer = QtWidgets.QHBoxLayout()
        for action in ('settings', 'guide'):
            button = QtWidgets.QPushButton(assistant_text(language, action))
            button.setStyleSheet(button_qss(dark, compact=True))
            button.setMinimumHeight(32)
            button.clicked.connect(lambda checked=False, key=action: self.action_requested.emit(key))
            footer.addWidget(button)
            self.buttons[action] = button
        layout.addLayout(footer)
        hide = QtWidgets.QPushButton(assistant_text(language, 'hide'))
        hide.setStyleSheet(button_qss(dark, 'quiet', compact=True))
        hide.setMinimumHeight(30)
        hide.setToolTip(assistant_text(language, 'hide_hint'))
        hide.clicked.connect(lambda: self.action_requested.emit('hide'))
        layout.addWidget(hide)
        self.buttons['hide'] = hide
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self._content = content

    def open_beside(self, anchor, available):
        self.ensurePolished()
        width = min(360, available.width())
        content_width = max(80, width - 34)
        self._content.setMinimumHeight(self._content.layout().totalHeightForWidth(content_width))
        height = min(max(450, self._content.minimumHeight() + 64), available.height())
        self.resize(width, height)
        x = anchor.left() - width - 8
        if x < available.left():
            x = anchor.right() + 9
        point = clamp_position(QtCore.QPoint(x, anchor.bottom() - height + 1), self.size(), available)
        self.move(point)
        self.show()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class DesktopAssistant(QtCore.QObject):
    _mode_changed = QtCore.pyqtSignal()

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.anchor = AssistantAnchor()
        self.menu = None
        self._context = None
        self._closed = False
        self._dispatching = False
        self._foreground = 0
        self._mode_changed.connect(self.refresh_visibility)
        self._unsubscribe = mode_coordinator.subscribe(self._mode_changed.emit)
        self.anchor.clicked.connect(self.toggle_menu)
        self.anchor.relocated.connect(self.save_position)
        self._dispatch_timer = QtCore.QTimer(self)
        self._dispatch_timer.setSingleShot(True)
        self._dispatch_timer.timeout.connect(self._dispatch)
        app = QtWidgets.QApplication.instance()
        app.screenAdded.connect(self._screens_changed)
        app.screenRemoved.connect(self._screens_changed)
        self._screens = set()
        self._screens_changed()
        self.refresh()

    def _screens_changed(self, *_):
        for screen in QtWidgets.QApplication.screens():
            if screen not in self._screens:
                screen.availableGeometryChanged.connect(self.restore_position)
                self._screens.add(screen)
        self.restore_position()

    def restore_position(self, *_):
        if self._closed:
            return
        stored = normalized_position(self.owner.config.get('desktop_assistant_position'))
        screens = QtWidgets.QApplication.screens()
        screen = next((s for s in screens if stored and s.name() == stored['screen']), None)
        screen = screen or self.owner.screen() or QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return
        bounds = screen.availableGeometry()
        x, y = (stored['x'], stored['y']) if stored else (.98, .85)
        point = QtCore.QPoint(bounds.left() + round(max(0, bounds.width() - self.anchor.width()) * x),
                             bounds.top() + round(max(0, bounds.height() - self.anchor.height()) * y))
        self.anchor.move(clamp_position(point, self.anchor.size(), bounds))
        if self.menu is not None:
            self.menu.hide()

    def save_position(self):
        screen = QtWidgets.QApplication.screenAt(self.anchor.geometry().center()) or self.anchor.screen()
        bounds = screen.availableGeometry()
        self.owner.config['desktop_assistant_position'] = {
            'screen': screen.name(),
            'x': (self.anchor.x() - bounds.x()) / max(1, bounds.width() - self.anchor.width()),
            'y': (self.anchor.y() - bounds.y()) / max(1, bounds.height() - self.anchor.height()),
        }
        self.owner.save_config()

    def refresh(self):
        if self._closed:
            return
        context = (self.owner.current_interface_language, self.owner.current_theme != 'Светлая')
        if context != self._context:
            if self.menu is not None:
                self.menu.close()
                self.menu.deleteLater()
                self.menu = None
            self._context = context
            self.anchor.dark = context[1]
            self.anchor.setToolTip(assistant_text(context[0], 'hint'))
            self.anchor.setAccessibleName(assistant_text(context[0], 'setting').rstrip(':：'))
            self.anchor.update()
        self.refresh_visibility()

    def refresh_visibility(self):
        if self._closed:
            return
        visible = (self.owner.config.get('desktop_assistant_enabled') is True
                   and not self._dispatching and mode_coordinator.active_mode() is None)
        self.anchor.setVisible(visible)
        if not visible and self.menu is not None:
            self.menu.hide()

    def toggle_menu(self):
        if (self._closed or not self.anchor.isVisible()
                or QtWidgets.QApplication.activeModalWidget() is not None):
            return
        if self.menu is not None and self.menu.isVisible():
            self.menu.hide()
            return
        # Read the external target before Qt's popup can take focus.
        from game_mode import _foreground_window
        self._foreground = _foreground_window()
        if self.menu is None:
            self.menu = AssistantMenu(*self._context)
            self.menu.action_requested.connect(self.request_action)
        screen = QtWidgets.QApplication.screenAt(self.anchor.geometry().center()) or self.anchor.screen()
        self.menu.open_beside(self.anchor.geometry(), screen.availableGeometry())

    def request_action(self, action):
        if (self._closed or self._dispatching
                or QtWidgets.QApplication.activeModalWidget() is not None):
            return
        if action not in (*ACTION_METHODS, 'text', 'settings', 'hide'):
            return
        if self.menu is not None:
            self.menu.hide()
        if action == 'hide':
            self.owner.set_desktop_assistant_enabled(False)
            return
        self._action = action
        self._dispatching = True
        self.refresh_visibility()
        if action in CAPTURE_ACTIONS:
            self._restore_foreground()
        # Let the compositor remove the popup and companion before capture.
        self._dispatch_timer.start(180 if action in CAPTURE_ACTIONS else 0)

    def _restore_foreground(self):
        if not self._foreground:
            return
        try:
            import platform_support
            from game_mode import _foreground_window, _window_belongs_to_this_process
            if not _window_belongs_to_this_process(_foreground_window()):
                return
            if platform_support.IS_WINDOWS:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(self._foreground))
            elif platform_support.IS_MAC:
                from macos_desktop import return_focus_to_window_application
                return_focus_to_window_application(self._foreground)
        except Exception:
            logging.exception('Could not restore focus after the assistant menu')

    def _dispatch(self):
        if self._closed:
            return
        try:
            if (QtWidgets.QApplication.activeModalWidget() is not None
                    or (self._action in CAPTURE_ACTIONS and mode_coordinator.active_mode() is not None)):
                # A newer hotkey or a modal dialog takes precedence over a
                # menu click still waiting for the compositor to settle.
                return
            if self._action in ('text', 'settings', 'guide'):
                self.owner.show_window_from_tray(force_show=True)
            if self._action == 'text':
                self.owner.show_main_screen()
            elif self._action == 'settings':
                self.owner.show_settings()
            else:
                getattr(self.owner, ACTION_METHODS[self._action])()
        except Exception:
            logging.exception('Desktop assistant action failed: %s', self._action)
        finally:
            # Main's fullscreen/dynamic actions queue capture after hiding the
            # main window. Keep the companion hidden until that delay expires.
            QtCore.QTimer.singleShot(350, self._finish_dispatch)

    def _finish_dispatch(self):
        if not self._closed:
            self._dispatching = False
            self.refresh_visibility()

    def dispose(self):
        if self._closed:
            return
        self._closed = True
        self._dispatch_timer.stop()
        self._unsubscribe()
        app = QtWidgets.QApplication.instance()
        app.screenAdded.disconnect(self._screens_changed)
        app.screenRemoved.disconnect(self._screens_changed)
        for screen in self._screens:
            try:
                screen.availableGeometryChanged.disconnect(self.restore_position)
            except (RuntimeError, TypeError):
                pass
        if self.menu is not None:
            self.menu.close()
            self.menu.deleteLater()
        self.anchor.movie.stop()
        self.anchor.close()
        self.anchor.deleteLater()
        self.deleteLater()
