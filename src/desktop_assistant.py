"""Optional desktop companion and shortcuts to existing workflows.

No keyboard hooks, screen polling, translation engine or network access lives
here. Capture ownership hides both windows before the first screenshot.
"""
import logging
import math
import sys
import weakref

from PyQt5 import QtCore, QtGui, QtWidgets, sip

from assistant_text import assistant_text
from button_styles import button_qss
from assistant_settings import BEHAVIORS, assistant_preferences
from assistant_art import DEFAULT_MASCOT, companion_art, mascot_id
from assistant_motion import PetMotion, paint_pet, play_reaction
from ui_scaling import desktop_control_scale
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
        if sys.platform == 'darwin':
            # Cocoa otherwise adds a shadow around the transparent panel;
            # at the compact size its cached bounds look like a square border.
            flags |= QtCore.Qt.NoDropShadowWindowHint
        super().__init__(None, flags)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        if sys.platform == 'darwin':
            # An NSPanel normally disappears when its app deactivates, including
            # after the main window switches to the menu bar / accessory mode.
            self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setFixedSize(84, 84)
        self._press = None
        self._dragging = False
        self._hover = False
        self._gaze_angle = None
        self.dark = True
        self.behavior = 'idle'
        self.appearance = 'portrait'
        self.mascot = DEFAULT_MASCOT
        self.custom_image = ''
        self.menu_open = False
        self._clock = QtCore.QElapsedTimer()
        self._animation = QtCore.QTimer(self)
        self._animation.setTimerType(QtCore.Qt.PreciseTimer)
        self._animation.setInterval(16)
        self._animation.timeout.connect(self._advance)
        self.motion = PetMotion(self.mascot)

    def set_mascot(self, mascot):
        mascot = mascot_id(mascot)
        if mascot == self.mascot:
            return
        self.mascot = mascot
        self.motion.mascot = mascot
        self.motion.crawl_phase = 0
        self.motion.greet()
        self._sync_motion()
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        # Layered Windows surfaces retain old pixels when a smaller pose is
        # blended over the previous frame. Replace its alpha before drawing.
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), QtCore.Qt.transparent)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        # Transparent in every state: no hover disc, border or native focus box.
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        if self.appearance in ('animated', 'walking') or self._explicit_reaction():
            action = self.motion.action()
            paint_pet(painter, QtCore.QRectF(self.rect()), self.mascot,
                      time=self.motion.time, action=action,
                      state_time=self.motion.seconds(action),
                      gaze=self._gaze_angle if self._hover and action == 'idle' else None)
            return
        pixmap = companion_art(self.appearance, self.custom_image, self.mascot)
        if not pixmap.isNull():
            source = pixmap.rect()
            extent = self.width()
            size = source.size().scaled(extent, extent, QtCore.Qt.KeepAspectRatio)
            # Static poses are centered and have no animation timer.
            baseline = (self.height() + size.height()) / 2
            painter.translate(self.width() / 2, baseline)
            target = QtCore.QRect(-size.width() // 2, -size.height(), size.width(), size.height())
            painter.drawPixmap(target, pixmap, source)
        else:
            painter.setPen(QtGui.QColor('#c9b1e7' if self.dark else '#755295'))
            painter.setFont(QtGui.QFont('Segoe UI', 32))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, '✦')

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_motion()

    def _sync_motion(self):
        active = ((self.appearance in ('animated', 'walking') or self._explicit_reaction()) and self.isVisible()
                  and self._press is None)
        animate = active
        if animate and not self._animation.isActive():
            self._clock.start()
            self._animation.start()
        elif not animate:
            self._animation.stop()

    def _explicit_reaction(self):
        return (self.appearance != 'custom' and bool(self.motion.gesture)
                and self.motion.gesture_age < self.motion.gesture_duration)

    def set_behavior(self, behavior):
        self.behavior = behavior if behavior in BEHAVIORS else 'idle'
        self._sync_motion()
        self.update()

    def _advance(self, seconds=None):
        if (not (self.appearance in ('animated', 'walking') or self._explicit_reaction())
                or not self.isVisible() or self._press is not None):
            return
        dt = min(.1, self._clock.restart() / 1000) if seconds is None else seconds
        self.motion.advance(dt)
        self._sync_motion()
        self.update()

    def hideEvent(self, event):
        self._animation.stop()
        self._press = None
        self._hover = False
        super().hideEvent(event)

    def enterEvent(self, event):
        self._hover = True
        self.motion.interact()
        self._sync_motion()
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self._gaze_angle = None
        self._sync_motion()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.motion.interact()
            self._press = event.globalPos()
            self._origin = self.pos()
            self._dragging = False
            self._sync_motion()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._press is None or not event.buttons() & QtCore.Qt.LeftButton:
            offset = event.localPos() - QtCore.QPointF(self.width()/2, self.height()*.44)
            self._gaze_angle = (math.degrees(math.atan2(offset.x(), -offset.y())) % 360
                                if abs(offset.x()) + abs(offset.y()) > self.width()*.08 else None)
            self.update()
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
            self._sync_motion()


class ActionButton(QtWidgets.QPushButton):
    def __init__(self, title, description, dark, parent=None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        self.setToolTip(description)
        self.setStyleSheet(button_qss(dark, 'secondary', compact=True))
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        label = QtWidgets.QLabel(title)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        label.setStyleSheet(f'color:{"#f5f0fa" if dark else "#302837"}; background:transparent; border:0; font-size:13px;')
        layout.addWidget(label)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

    def sizeHint(self):
        return self.layout().totalSizeHint()

    def minimumSizeHint(self):
        return self.layout().minimumSize()

    def heightForWidth(self, width):
        return self.layout().totalHeightForWidth(width)


class AssistantMenu(QtWidgets.QFrame):
    """Compact actions and native reactions, anchored below the companion."""
    action_requested = QtCore.pyqtSignal(str)
    visibility_changed = QtCore.pyqtSignal(bool)

    def __init__(self, language, dark, factor=1.0, behavior='idle', appearance='animated', mascot=DEFAULT_MASCOT):
        super().__init__(None, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.language = language
        self.setObjectName('desktopAssistantMenu')
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setWindowTitle(assistant_text(language, 'quick_actions'))
        self.factor = factor
        self._background = QtGui.QColor('#121212' if dark else '#f0edf3')
        self._border = QtGui.QColor('#584963' if dark else '#bcaacb')
        from rounded_windows import clip_rounded_window
        clip_rounded_window(self, self, 8)
        self.setStyleSheet('QFrame#desktopAssistantMenu { background:transparent; border:0; }')
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(assistant_text(language, mascot))
        title.setStyleSheet(f'color:{"#eee7f5" if dark else "#302639"}; background:transparent; font-size:16px; font-weight:600;')
        header.addWidget(title, 1)
        close = QtWidgets.QPushButton('×')
        close.setFixedSize(26, 26)
        close.setAccessibleName(assistant_text(language, 'close_menu'))
        close.setStyleSheet(button_qss(dark, 'close', icon=True))
        close.clicked.connect(self.hide)
        header.addWidget(close)
        outer.addLayout(header)
        self.activity_label = QtWidgets.QLabel()
        self.activity_label.setWordWrap(True)
        self.activity_label.setStyleSheet(f'color:{"#bdb2ca" if dark else "#70647e"}; background:transparent; border:0; font-size:12px;')
        outer.addWidget(self.activity_label)
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.buttons = {}
        for index, action in enumerate(('area', 'screen', 'text', 'copy', 'dynamic', 'documents')):
            button = ActionButton(*assistant_text(language, action), dark)
            button.setMinimumHeight(44)
            button.clicked.connect(lambda checked=False, key=action: self.action_requested.emit(key))
            grid.addWidget(button, index // 2, index % 2)
            self.buttons[action] = button
        outer.addLayout(grid)
        footer = QtWidgets.QHBoxLayout()
        for action, label in (('settings', 'settings'), ('hide', 'tray_hide')):
            button = QtWidgets.QPushButton(assistant_text(language, label))
            button.setStyleSheet(button_qss(dark, 'quiet', compact=True))
            button.setMinimumHeight(28)
            button.clicked.connect(lambda checked=False, key=action: self.action_requested.emit(key))
            self.buttons[action] = button
            footer.addWidget(button)
        outer.addLayout(footer)
        self.set_activity('idle')
        from window_appearance import scale_native_controls
        scale_native_controls(self, factor)

    def set_activity(self, activity):
        self.activity_label.setText(assistant_text(self.language, 'activity_' + activity))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(self._border, 1))
        painter.setBrush(self._background)
        painter.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(.5, .5, -.5, -.5),
                                8 * self.factor, 8 * self.factor)

    def open_beside(self, anchor, available):
        self.ensurePolished()
        width = min(round(360 * self.factor), available.width())
        self.setFixedWidth(width)
        self.layout().activate()
        height = max(self.layout().totalHeightForWidth(width), self.layout().minimumSize().height())
        self.resize(width, height)
        x = anchor.center().x() - width // 2
        y = anchor.bottom() + 8
        if y + self.height() > available.bottom() + 1:
            y = anchor.top() - self.height() - 8
        self.move(clamp_position(QtCore.QPoint(x, y), self.size(), available))
        self.show()

    def showEvent(self, event):
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.visibility_changed.emit(False)

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
        self.anchor.motion.set_activity(getattr(owner, '_companion_activity', 'idle'))
        self.menu = None
        self._context = None
        self._closed = False
        self._dispatching = False
        self._foreground = 0
        self._mode_changed.connect(self.refresh_visibility)
        reference = weakref.ref(self)
        def notify_mode():
            helper = reference()
            if helper is not None and not sip.isdeleted(helper) and not helper._closed:
                helper._mode_changed.emit()
        self._unsubscribe = mode_coordinator.subscribe(notify_mode)
        self.destroyed.connect(lambda _=None, unsubscribe=self._unsubscribe: unsubscribe())
        owner.destroyed.connect(self.dispose)
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
                screen.logicalDotsPerInchChanged.connect(self._metrics_changed)
                self._screens.add(screen)
        self.restore_position()

    def _metrics_changed(self, *_):
        self.refresh()
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

        # Dragging to a monitor with a different DPI must update the mascot and
        # its menu without changing the normalized home position just saved.
        self.refresh()

    def refresh(self):
        if self._closed:
            return
        preferences = assistant_preferences(self.owner.config)
        screen = QtWidgets.QApplication.screenAt(self.anchor.geometry().center()) or self.anchor.screen()
        factor = desktop_control_scale(screen)
        available = screen.availableGeometry()
        menu_factor = min(factor, available.width()/360, available.height()/360)
        context = (self.owner.current_interface_language, self.owner.current_theme != 'Светлая', menu_factor,
                   preferences['desktop_assistant_behavior'], preferences['desktop_assistant_appearance'],
                   preferences['desktop_assistant_mascot'])
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
        size = round(84 * factor * preferences['desktop_assistant_size'] / 100)
        resized = self.anchor.width() != size
        self.anchor.setFixedSize(size, size)
        if resized:
            self.restore_position()
        self.anchor.appearance = preferences['desktop_assistant_appearance']
        self.anchor.set_mascot(preferences['desktop_assistant_mascot'])
        self.anchor.motion.reactions = preferences['desktop_assistant_reactions']
        self.anchor.custom_image = preferences['desktop_assistant_image']
        self.anchor.setProperty('ui_effective_scale', factor)
        if self.anchor.behavior != preferences['desktop_assistant_behavior']:
            self.anchor.set_behavior(preferences['desktop_assistant_behavior'])
        self.anchor.setWindowOpacity(preferences['desktop_assistant_opacity'] / 100)
        topmost = bool(self.anchor.windowFlags() & QtCore.Qt.WindowStaysOnTopHint)
        if topmost != preferences['desktop_assistant_topmost']:
            self.anchor.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, preferences['desktop_assistant_topmost'])
        screen = self.anchor.screen()
        if screen is not None:
            self.anchor.move(clamp_position(self.anchor.pos(), self.anchor.size(), screen.availableGeometry()))
        self.refresh_visibility()
        self.anchor.update()

    def refresh_visibility(self):
        if self._closed:
            return
        visible = (self.owner.config.get('desktop_assistant_enabled') is True
                   and not self._dispatching and mode_coordinator.active_mode() is None)
        self.anchor.setVisible(visible)
        self.anchor._sync_motion()
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
            self.menu.visibility_changed.connect(self._menu_visibility)
        screen = QtWidgets.QApplication.screenAt(self.anchor.geometry().center()) or self.anchor.screen()
        play_reaction(self.owner, 'waving', anchor=self.anchor)
        self.menu.set_activity(getattr(self.owner, '_companion_activity', 'idle'))
        self.menu.open_beside(self.anchor.geometry(), screen.availableGeometry())

    def _menu_visibility(self, visible):
        self.anchor.menu_open = visible
        self.anchor.motion.menu_open = visible
        self.anchor._sync_motion()

    def request_action(self, action):
        if (self._closed or self._dispatching
                or QtWidgets.QApplication.activeModalWidget() is not None):
            return
        if action not in (*ACTION_METHODS, *BEHAVIORS, 'home', 'text', 'settings', 'hide'):
            return
        if action in BEHAVIORS and self.anchor.appearance not in ('animated', 'walking'):
            return
        if self.menu is not None:
            self.menu.hide()
        if action in BEHAVIORS:
            self.owner.config['desktop_assistant_behavior'] = action
            self.owner.save_config()
            self.refresh()
            page = getattr(getattr(self.owner, 'settings_window', None), 'settings_assistant_page', None)
            if page is not None:
                page.refresh()
            return
        if action == 'home':
            self.restore_position()
            play_reaction(self.owner, 'jumping', anchor=self.anchor)
            return
        if action == 'hide':
            self.owner.set_desktop_assistant_enabled(False)
            return
        if action not in CAPTURE_ACTIONS:
            play_reaction(self.owner, 'review', anchor=self.anchor)
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
            if self._action in ('settings', 'guide'):
                self.owner.show_window_from_tray(force_show=True)
            if self._action == 'text':
                self.owner.open_text_translation()
            elif self._action == 'settings':
                show = getattr(self.owner, 'show_assistant_settings', self.owner.show_settings)
                show()
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
                screen.logicalDotsPerInchChanged.disconnect(self._metrics_changed)
            except (RuntimeError, TypeError):
                pass
        if self.menu is not None:
            self.menu.close()
            self.menu.deleteLater()
        self.anchor._animation.stop()
        self.anchor.close()
        self.anchor.deleteLater()
        self.deleteLater()
