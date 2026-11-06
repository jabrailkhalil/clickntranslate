"""Optional desktop companion and shortcuts to existing workflows.

No keyboard hooks, screen polling, translation engine or network access lives
here. Capture ownership hides both windows before the first screenshot.
"""
import logging
import math
import sys
import threading
import weakref

from PyQt5 import QtCore, QtGui, QtWidgets, sip

from assistant_text import assistant_text, assistant_action_text, companion_display_name
from button_styles import button_qss, button_palette, connected_action_panel
from assistant_settings import BEHAVIORS, assistant_preferences, normalized_assistant_actions
from assistant_art import DEFAULT_MASCOT, companion_art, mascot_id
from assistant_motion import PetMotion, paint_pet, play_reaction
from assistant_sprites import look_index
from ui_scaling import desktop_control_scale
import mode_coordinator


CAPTURE_ACTIONS = frozenset(('screen', 'area', 'dynamic', 'copy'))
FOREGROUND_ACTIONS = CAPTURE_ACTIONS | {'selection', 'replace'}
ACTION_METHODS = {
    'screen': 'launch_fullscreen_translate', 'area': 'launch_translate',
    'dynamic': 'launch_game_translate', 'copy': 'launch_copy',
    'documents': 'open_document_translation',
    'selection': 'launch_translate_selection', 'replace': 'launch_translate_replace_selection',
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
        position = dict(screen=value['screen'], x=max(0., min(x, 1.)), y=max(0., min(y, 1.)))
        if value.get('space') == 'screen':
            position['space'] = 'screen'
        return position
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
        self._menu_gaze_angle = None
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
        self._layer_guard = QtCore.QTimer(self)
        self._layer_guard.setTimerType(QtCore.Qt.CoarseTimer)
        self._layer_guard.setInterval(2000)
        self._layer_guard.timeout.connect(self._sync_window_layer)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._sync_window_layer)

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
        gaze = self._menu_gaze_angle if self.menu_open else self._gaze_angle if self._hover else None
        if (self.appearance in ('animated', 'walking') or self._explicit_reaction()
                or self.appearance != 'custom' and gaze is not None):
            action = self.motion.action()
            paint_pet(painter, QtCore.QRectF(self.rect()), self.mascot,
                      time=self.motion.time, action=action,
                      state_time=self.motion.seconds(action),
                      gaze=gaze if self.appearance != 'custom' else None)
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
        self._sync_window_layer()

    def event(self, event):
        result = super().event(event)
        if (event.type() == QtCore.QEvent.WinIdChange
                and getattr(self, '_layer_guard', None) is not None):
            QtCore.QTimer.singleShot(0, self._sync_window_layer)
        return result

    def _sync_window_layer(self, *_):
        if sip.isdeleted(self):
            return
        app = QtWidgets.QApplication.instance()
        native_windows = (sys.platform == 'win32' and app is not None
                          and app.platformName().split(':')[0] == 'windows')
        enabled = bool(self.windowFlags() & QtCore.Qt.WindowStaysOnTopHint)
        if not native_windows or not self.isVisible():
            self._layer_guard.stop()
            return
        if enabled:
            if not self._layer_guard.isActive():
                self._layer_guard.start()
        else:
            self._layer_guard.stop()
        handle = self.windowHandle()
        if handle is not None:
            from window_layer import synchronize_topmost
            screen = self.screen()
            over_taskbar = bool(screen and not screen.availableGeometry().contains(self.geometry()))
            synchronize_topmost(int(handle.winId()), enabled, above_taskbar=over_taskbar)

    def _sync_motion(self):
        active = ((self.appearance in ('animated', 'walking') or self._explicit_reaction()) and self.isVisible()
                  and self._press is None)
        animate = active
        self._animation.setInterval(33 if self.mascot == 'click' and self.motion.action() != 'idle' else 80)
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
        previous = self.motion.render_key()
        self.motion.advance(dt)
        self._sync_motion()
        if self.motion.render_key() != previous:
            self.update()

    def hideEvent(self, event):
        self._layer_guard.stop()
        self._animation.stop()
        self._press = None
        self._hover = False
        super().hideEvent(event)

    def enterEvent(self, event):
        self._hover = True
        self.motion.interact()
        self._look_at(self.mapFromGlobal(QtGui.QCursor.pos()))
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
            self._look_at(event.localPos())
            return
        offset = event.globalPos() - self._press
        if offset.manhattanLength() >= QtWidgets.QApplication.startDragDistance():
            self._dragging = True
        if self._dragging:
            screen = QtWidgets.QApplication.screenAt(event.globalPos()) or self.screen()
            self.move(clamp_position(self._origin + offset, self.size(), screen.geometry()))
            self._sync_window_layer()

    def _look_at(self, point):
        if self.menu_open or self.appearance == 'custom':
            return
        offset = QtCore.QPointF(point) - QtCore.QPointF(self.width()/2, self.height()*.44)
        angle = (math.degrees(math.atan2(offset.x(), -offset.y())) % 360
                 if abs(offset.x()) + abs(offset.y()) > self.width()*.08 else None)
        if angle is not None:
            angle = look_index(angle)*22.5
        if angle != self._gaze_angle:
            self._gaze_angle = angle
            self.update()

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
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        label = QtWidgets.QLabel(title)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        colors = button_palette(dark)
        label.setStyleSheet(f'QLabel {{ color:{colors["text"]}; background:transparent; border:0; '
                           f'font-size:13px; font-weight:600; }} QLabel:disabled {{ color:{colors["disabled"]}; }}')
        layout.addWidget(label)
        policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def sizeHint(self):
        return self.layout().totalSizeHint()

    def minimumSizeHint(self):
        return self.layout().minimumSize()

    def heightForWidth(self, width):
        return self.layout().totalHeightForWidth(width)


class AssistantMenu(QtWidgets.QFrame):
    """A persistent, non-modal tool palette anchored to the companion."""
    action_requested = QtCore.pyqtSignal(str)
    visibility_changed = QtCore.pyqtSignal(bool)
    placement_changed = QtCore.pyqtSignal()
    pointer_entered = QtCore.pyqtSignal()

    def __init__(self, language, dark, factor=1.0, behavior='idle', appearance='animated', mascot=DEFAULT_MASCOT,
                 actions=None, *, icon=None, keyboard=False):
        flags = QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
        if not keyboard:
            flags |= QtCore.Qt.WindowDoesNotAcceptFocus
        super().__init__(None, flags)
        self.keyboard_enabled = bool(keyboard)
        self.language = language
        self.setObjectName('desktopAssistantMenu')
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, not keyboard)
        if sys.platform == 'darwin':
            self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)
        self.setWindowTitle(assistant_text(language, 'quick_actions'))
        self.setLayoutDirection(QtCore.Qt.RightToLeft if language == 'ar' else QtCore.Qt.LeftToRight)
        self.factor = factor
        from classic_style import classic_palette
        colors = classic_palette(dark)
        self._background = QtGui.QColor(colors['background'])
        self._border = QtGui.QColor(colors['border'])
        from rounded_windows import clip_rounded_window
        clip_rounded_window(self, self, 8)
        self.setStyleSheet('QFrame#desktopAssistantMenu { background:transparent; border:0; }')
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        self.header = QtWidgets.QFrame(self)
        self.header.setObjectName('assistantMenuHeader')
        self.header.setFixedHeight(36)
        self.header.setStyleSheet(f'QFrame#assistantMenuHeader {{ background:{colors["header"]}; '
            f'border:0; border-bottom:1px solid {colors["header_border"]}; '
            f'border-top-left-radius:7px; border-top-right-radius:7px; }}')
        header = QtWidgets.QHBoxLayout(self.header)
        header.setContentsMargins(10, 2, 4, 2)
        icon = icon or QtWidgets.QApplication.windowIcon()
        if not icon.isNull():
            logo = QtWidgets.QLabel()
            logo.setFixedSize(18, 18)
            logo.setPixmap(icon.pixmap(18, 18))
            logo.setStyleSheet('background:transparent; border:0;')
            header.addWidget(logo)
        title = QtWidgets.QLabel(companion_display_name(language, mascot, appearance))
        title.setStyleSheet(f'color:{colors["text"]}; background:transparent; border:0; font-size:13px; font-weight:600;')
        header.addWidget(title, 1)
        close = QtWidgets.QPushButton('×')
        close.setFixedSize(26, 26)
        close.setAccessibleName(assistant_text(language, 'close_menu'))
        close.setToolTip(close.accessibleName())
        close.setStyleSheet(button_qss(dark, 'close', icon=True))
        close.clicked.connect(self.hide)
        header.addWidget(close)
        outer.addWidget(self.header)
        self.content = QtWidgets.QWidget(self)
        body = QtWidgets.QVBoxLayout(self.content)
        body.setContentsMargins(8, 8, 8, 8)
        body.setSpacing(8)
        outer.addWidget(self.content, 1)
        self.activity_label = QtWidgets.QLabel()
        self.activity_label.setWordWrap(True)
        self.activity_label.setStyleSheet(f'QLabel {{ color:{colors["muted"]}; background:transparent; '
            f'border:0; font-size:12px; }} QLabel[statusError="true"] {{ color:{colors["danger"]}; }}')
        self.activity_label.setTextFormat(QtCore.Qt.PlainText)
        self.activity_label.setAccessibleName(assistant_text(language, 'panel_status'))
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(0)
        self.scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background:transparent; border:0; }')
        from scrollbar_styles import scrollbar_stylesheet
        self.scroll.setStyleSheet(self.scroll.styleSheet() + scrollbar_stylesheet())
        self.scroll.verticalScrollBar().setProperty('_cntScrollDark', dark)
        self.action_surface = QtWidgets.QWidget()
        self.action_surface.setObjectName('assistantActionPanel')
        grid = QtWidgets.QGridLayout(self.action_surface)
        grid.setContentsMargins(1, 1, 1, 1)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.buttons = {}
        selected = normalized_assistant_actions(actions)
        index = 0
        for action in selected:
            button = ActionButton(*assistant_action_text(language, action), dark)
            button.setMinimumHeight(34)
            if action == 'replace' and sys.platform.startswith('linux'):
                from settings_window import settings_text
                button.setEnabled(False)
                button.setToolTip(settings_text(language, 'replace_selection_unavailable'))
            button.clicked.connect(lambda checked=False, key=action: self.action_requested.emit(key))
            if action == 'open':
                grid.addWidget(button, 0, 0, 1, 2)
            else:
                grid.addWidget(button, index // 2 + ('open' in selected), index % 2)
                index += 1
            self.buttons[action] = button
        self.scroll.setWidget(self.action_surface)
        body.addWidget(self.scroll)
        # Inherit RTL from the menu before choosing the physical corners.
        connected_action_panel(self.action_surface, dark)
        # Keep feedback near the actions, without another framed card.
        body.addWidget(self.activity_label)
        self.footer = QtWidgets.QWidget(self.content)
        self.footer.setObjectName('assistantMenuFooter')
        footer = QtWidgets.QGridLayout(self.footer)
        footer.setContentsMargins(1, 1, 1, 1)
        footer.setSpacing(0)
        footer.setColumnStretch(0, 1)
        footer.setColumnStretch(1, 1)
        for action, label in (('settings', 'settings'), ('hide', 'tray_hide')):
            button = QtWidgets.QPushButton(assistant_text(language, label))
            button.setFixedHeight(29)
            button.clicked.connect(lambda checked=False, key=action: self.action_requested.emit(key))
            self.buttons[action] = button
            footer.addWidget(button, 0, 0 if action == 'settings' else 1)
        connected_action_panel(self.footer, dark)
        body.addWidget(self.footer)
        self.set_activity('idle')
        from window_appearance import scale_native_controls
        scale_native_controls(self, factor)
        from keyboard_navigation import install_keyboard_navigation
        install_keyboard_navigation()

    def enterEvent(self, event):
        self.pointer_entered.emit()
        super().enterEvent(event)

    def set_keyboard_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.keyboard_enabled:
            return
        self.keyboard_enabled = enabled
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, not enabled)
        self.setWindowFlag(QtCore.Qt.WindowDoesNotAcceptFocus, not enabled)
        self._sync_input_mode()

    def _sync_input_mode(self):
        app = QtWidgets.QApplication.instance()
        if (sys.platform == 'win32' and app is not None
                and app.platformName().split(':')[0] == 'windows' and self.windowHandle() is not None):
            from window_layer import synchronize_no_activate
            synchronize_no_activate(int(self.winId()), not self.keyboard_enabled)

    def event(self, event):
        result = super().event(event)
        if event.type() == QtCore.QEvent.WinIdChange and hasattr(self, 'keyboard_enabled'):
            self._sync_input_mode()
        return result

    def nativeEvent(self, event_type, message):
        if sys.platform == 'win32' and bytes(event_type) == b'windows_generic_MSG':
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0021:  # WM_MOUSEACTIVATE, before the button press.
                self.pointer_entered.emit()
                if not self.keyboard_enabled:
                    return True, 3  # MA_NOACTIVATE (not MA_NOACTIVATEANDEAT).
        return super().nativeEvent(event_type, message)

    def set_actions_enabled(self, enabled):
        for action, button in self.buttons.items():
            if action != 'hide':
                button.setEnabled(bool(enabled) and not (action == 'replace' and sys.platform.startswith('linux')))

    def set_status(self, text, *, error=False):
        if self.activity_label.property('statusError') != error:
            self.activity_label.setProperty('statusError', error)
            self.activity_label.style().unpolish(self.activity_label)
            self.activity_label.style().polish(self.activity_label)
        self.activity_label.setText(str(text))
        self.activity_label.setVisible(bool(text))
        if self.isVisible() and hasattr(self, '_available_rect'):
            self.open_beside(self._anchor_rect, self._available_rect)

    def set_activity(self, activity):
        self.set_status(assistant_text(self.language, 'activity_' + activity) if activity != 'idle' else '')

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), QtCore.Qt.transparent)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(self._border, 1))
        painter.setBrush(self._background)
        painter.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(.5, .5, -.5, -.5),
                                8 * self.factor, 8 * self.factor)

    def open_beside(self, anchor, available):
        self._anchor_rect, self._available_rect = QtCore.QRect(anchor), QtCore.QRect(available)
        self.ensurePolished()
        width = min(round(360 * self.factor), available.width())
        self.setFixedWidth(width)
        self.layout().activate()
        margins = self.layout().contentsMargins()
        body_margins = self.content.layout().contentsMargins()
        content_width = (width - margins.left() - margins.right() - body_margins.left() - body_margins.right()
                         - self.style().pixelMetric(QtWidgets.QStyle.PM_ScrollBarExtent))
        grid = self.action_surface.layout()
        content_height = max(grid.totalHeightForWidth(content_width), grid.minimumSize().height())
        # The title and footer stay visible; only actions scroll on a small or
        # high-DPI display. Measure against the scrollbar's narrowest viewport.
        self.scroll.setFixedHeight(0)
        self.content.layout().invalidate()
        self.content.updateGeometry()
        self.layout().invalidate()
        chrome = max(self.layout().totalHeightForWidth(width), self.layout().minimumSize().height())
        self.scroll.setFixedHeight(min(content_height, max(0, available.height() - chrome - 8)))
        # The body is a QWidget, so its old minimumSizeHint remains cached
        # until its own layout is invalidated, even after the scroll changes.
        self.content.layout().invalidate()
        self.content.updateGeometry()
        self.layout().invalidate()
        height = max(self.layout().totalHeightForWidth(width), self.layout().minimumSize().height())
        self.setFixedHeight(height)
        self.layout().activate()
        x = anchor.center().x() - width // 2
        y = anchor.bottom() + 8
        if y + self.height() > available.bottom() + 1:
            y = anchor.top() - self.height() - 8
        self.move(clamp_position(QtCore.QPoint(x, y), self.size(), available))
        self.show()
        self.placement_changed.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_input_mode()
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
        self._action = None
        self._panel_open = False
        self._menu_keyboard = False
        self._suspending_menu = False
        self._selection_pending = False
        self._selection_message = ''
        self._selection_failed = False
        self._selection_target = None
        self._selection_request_target = None
        self._selection_request_token = None
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
        app.applicationStateChanged.connect(self._application_state_changed)
        self._tagged_selection_feedback = all(getattr(owner, name, None) is not None for name in (
            '_companion_selection_status_signal', '_companion_selection_finished_signal'))
        selection_signals = (
            (('_companion_selection_status_signal', self._receive_owned_selection_status),
             ('_companion_selection_finished_signal', self._owned_selection_finished))
            if self._tagged_selection_feedback else
            (('_show_status_signal', self._receive_selection_status),
             ('_selection_finished_signal', self._selection_finished)))
        for name, slot in selection_signals:
            signal = getattr(owner, name, None)
            if signal is not None:
                signal.connect(slot)
        app.screenAdded.connect(self._screens_changed)
        app.screenRemoved.connect(self._screens_changed)
        self._screens = set()
        self._screens_changed()
        self.refresh()

    def _screens_changed(self, *_):
        for screen in QtWidgets.QApplication.screens():
            if screen not in self._screens:
                screen.availableGeometryChanged.connect(self.restore_position)
                screen.geometryChanged.connect(self.restore_position)
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
        # Earlier saved positions were relative to the work area. Restore
        # those unchanged; new positions include the taskbar strip.
        bounds = (screen.geometry() if stored and stored.get('space') == 'screen'
                  else screen.availableGeometry())
        x, y = (stored['x'], stored['y']) if stored else (.98, .85)
        point = QtCore.QPoint(bounds.left() + round(max(0, bounds.width() - self.anchor.width()) * x),
                             bounds.top() + round(max(0, bounds.height() - self.anchor.height()) * y))
        self.anchor.move(clamp_position(point, self.anchor.size(), screen.geometry()))
        if self.menu is not None and self.menu.isVisible():
            self.menu.open_beside(self.anchor.geometry(), screen.availableGeometry())

    def save_position(self):
        screen = QtWidgets.QApplication.screenAt(self.anchor.geometry().center()) or self.anchor.screen()
        bounds = screen.geometry()
        self.owner.config['desktop_assistant_position'] = {
            'screen': screen.name(),
            'space': 'screen',
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
                   preferences['desktop_assistant_mascot'], tuple(preferences['desktop_assistant_actions']))
        if context != self._context:
            if self.menu is not None:
                self._suspending_menu = True
                try:
                    self.menu.close()
                finally:
                    self._suspending_menu = False
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
            self.anchor.move(clamp_position(self.anchor.pos(), self.anchor.size(), screen.geometry()))
        self.refresh_visibility()
        self.anchor.update()

    def refresh_visibility(self):
        if self._closed:
            return
        enabled = self.owner.config.get('desktop_assistant_enabled') is True
        visible = (enabled and not (self._dispatching and self._action in CAPTURE_ACTIONS)
                   and mode_coordinator.active_mode() is None)
        if not enabled:
            self._panel_open = False
        self.anchor.setVisible(visible)
        self.anchor._sync_window_layer()
        self.anchor._sync_motion()
        if not visible and self.menu is not None:
            self._suspending_menu = True
            try:
                self.menu.hide()
            finally:
                self._suspending_menu = False
        elif visible and self._panel_open and (self.menu is None or not self.menu.isVisible()):
            self._show_menu()

    def toggle_menu(self, keyboard=False):
        if (self._closed or not self.anchor.isVisible()
                or QtWidgets.QApplication.activeModalWidget() is not None):
            return
        if self.menu is not None and self.menu.isVisible():
            self.menu.hide()
            return
        self._remember_foreground()
        self._menu_keyboard = bool(keyboard)
        self._show_menu()
        if keyboard:
            self.menu.activateWindow()
            first = next((button for button in self.menu.buttons.values() if button.isEnabled()), None)
            if first is not None:
                first.setFocus(QtCore.Qt.TabFocusReason)

    def _show_menu(self):
        if self.menu is None:
            self.menu = AssistantMenu(*self._context, icon=self.owner.windowIcon(), keyboard=self._menu_keyboard)
            self.menu.action_requested.connect(self.request_action)
            self.menu.visibility_changed.connect(self._menu_visibility)
            self.menu.placement_changed.connect(self._update_menu_gaze)
            self.menu.pointer_entered.connect(self._remember_foreground)
        self._suspending_menu = True
        try:
            self.menu.set_keyboard_enabled(self._menu_keyboard)
        finally:
            self._suspending_menu = False
        screen = QtWidgets.QApplication.screenAt(self.anchor.geometry().center()) or self.anchor.screen()
        if self._selection_message:
            self.menu.set_status(self._selection_message, error=self._selection_failed)
        else:
            self.menu.set_activity(getattr(self.owner, '_companion_activity', 'idle'))
        self.menu.set_actions_enabled(not self._dispatching)
        self.menu.open_beside(self.anchor.geometry(), screen.availableGeometry())

    def _menu_visibility(self, visible):
        if visible:
            self._panel_open = True
        elif not self._suspending_menu:
            self._panel_open = False
        self.anchor.menu_open = visible
        self.anchor.motion.menu_open = visible
        self._update_menu_gaze()
        self.anchor._sync_motion()
        self.anchor.update()

    def _application_state_changed(self, state):
        if state == QtCore.Qt.ApplicationInactive and not self._closed:
            QtCore.QTimer.singleShot(0, self._remember_foreground)

    def _remember_foreground(self):
        if self._closed:
            return
        import platform_support
        from game_mode import _foreground_window, _window_belongs_to_this_process
        current = _foreground_window()
        if current and not _window_belongs_to_this_process(current):
            self._foreground = current
            if platform_support.IS_MAC:
                from macos_desktop import foreground_target
                self._selection_target = foreground_target()
            else:
                self._selection_target = current

    def _update_menu_gaze(self):
        if self.menu is not None and self.menu.isVisible() and self.anchor.menu_open:
            eye = self.anchor.geometry().topLeft() + QtCore.QPoint(self.anchor.width()//2,
                                                                 round(self.anchor.height()*.44))
            offset = self.menu.geometry().center() - eye
            self.anchor._menu_gaze_angle = math.degrees(math.atan2(offset.x(), -offset.y())) % 360
        else:
            self.anchor._menu_gaze_angle = None
        self.anchor.update()

    def request_action(self, action):
        if self._closed:
            return
        if action == 'hide':
            self._panel_open = False
            self.owner.set_desktop_assistant_enabled(False)
            return
        if (self._dispatching
                or QtWidgets.QApplication.activeModalWidget() is not None):
            return
        if action not in (*ACTION_METHODS, *BEHAVIORS, 'home', 'open', 'text', 'settings', 'hide'):
            return
        if action == 'replace' and sys.platform.startswith('linux'):
            return
        if action in BEHAVIORS and self.anchor.appearance not in ('animated', 'walking'):
            return
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
        self._remember_foreground()
        if action in ('selection', 'replace'):
            import platform_support
            if platform_support.IS_MAC and not self._selection_target:
                from macos_desktop import ensure_permission
                if not ensure_permission('accessibility', self.owner, self._context[0]):
                    return
                self._restore_foreground()
                self._remember_foreground()
            if ((platform_support.IS_WINDOWS or platform_support.IS_MAC)
                    and (not self._selection_target or not self._restore_foreground())):
                self._selection_message = assistant_text(self._context[0], 'selection_focus_lost')
                self._selection_failed = True
                if self.menu is not None:
                    self.menu.set_status(self._selection_message, error=True)
                return
            self._selection_request_token = threading.Event() if self._tagged_selection_feedback else None
            self._selection_pending = True
            self._selection_request_target = self._selection_target
            self._selection_message = assistant_text(self._context[0], 'selection_reading')
        else:
            self._selection_message = ''
        self._selection_failed = False
        if action not in CAPTURE_ACTIONS:
            play_reaction(self.owner, 'review', anchor=self.anchor)
        self._action = action
        self._dispatching = True
        if self.menu is not None:
            self.menu.set_actions_enabled(False)
            self.menu.set_status(self._selection_message)
        self.refresh_visibility()
        if action in CAPTURE_ACTIONS:
            self._restore_foreground()
        # Capture needs time to remove both surfaces. Selection already keeps
        # its external focus, so starting it needs no extra popup-close delay.
        self._dispatch_timer.start(180 if action in CAPTURE_ACTIONS else 0)

    def _restore_foreground(self):
        try:
            import platform_support
            from game_mode import _foreground_window, _window_belongs_to_this_process
            if not (platform_support.IS_WINDOWS or platform_support.IS_MAC):
                return True
            if not self._foreground:
                return False
            current = _foreground_window()
            if current == self._foreground:
                return True
            # The user may have switched again. Never pull a different app
            # back in front merely because it was selected earlier.
            if not _window_belongs_to_this_process(current):
                return False
            if platform_support.IS_WINDOWS:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(self._foreground))
                return _foreground_window() == self._foreground
            elif platform_support.IS_MAC:
                from macos_desktop import return_focus_to_window_application, same_foreground_target
                return (return_focus_to_window_application(self._foreground)
                        and same_foreground_target(self._selection_target))
        except Exception:
            logging.exception('Could not restore focus after the assistant menu')
        return False

    def _receive_owned_selection_status(self, token, text):
        if token is self._selection_request_token:
            self._receive_selection_status(text)

    def _owned_selection_finished(self, token, success):
        if token is self._selection_request_token:
            self._selection_finished(success)

    def _receive_selection_status(self, text):
        if self._closed or not self._selection_pending:
            return
        self._selection_message = str(text)
        if self.menu is not None:
            self.menu.set_status(self._selection_message)

    def _selection_finished(self, success):
        if self._closed or not self._selection_pending:
            return
        self._selection_pending = False
        if self._selection_request_token is not None:
            self._selection_request_token.set()
            self._selection_request_token = None
        self._selection_failed = not success
        if success:
            self._selection_message = assistant_text(self._context[0], 'activity_success')
        elif not self._selection_message or self._selection_message == assistant_text(self._context[0], 'selection_reading'):
            self._selection_message = assistant_text(self._context[0], 'selection_empty')
        if self.menu is not None:
            self.menu.set_status(self._selection_message, error=not success)
        self._finish_dispatch()

    def _dispatch(self):
        if self._closed:
            return
        waiting_for_selection = False
        try:
            if (QtWidgets.QApplication.activeModalWidget() is not None
                    or (self._action in FOREGROUND_ACTIONS and mode_coordinator.active_mode() is not None)):
                # A newer hotkey or a modal dialog takes precedence over a
                # menu click still waiting for the compositor to settle.
                if self._selection_pending:
                    self._receive_selection_status(assistant_text(self._context[0], 'selection_focus_lost'))
                    self._selection_finished(False)
                    waiting_for_selection = True
                return
            if self._action in ('open', 'settings'):
                self.owner.show_window_from_tray(force_show=True)
            if self._action == 'open':
                return
            elif self._action == 'text':
                self.owner.open_text_translation()
            elif self._action == 'settings':
                show = getattr(self.owner, 'show_assistant_settings', self.owner.show_settings)
                show()
            elif self._action in ('selection', 'replace'):
                method = getattr(self.owner, ACTION_METHODS[self._action])
                started = method(expected_target=self._selection_request_target or 0,
                                 **({'_request_token': self._selection_request_token}
                                    if self._tagged_selection_feedback else {}))
                finished_signal = ('_companion_selection_finished_signal' if self._tagged_selection_feedback
                                   else '_selection_finished_signal')
                waiting_for_selection = started is not False and hasattr(self.owner, finished_signal)
                if not waiting_for_selection:
                    self._selection_finished(started is not False)
                    waiting_for_selection = True  # Already completed; no old delayed callback.
            else:
                getattr(self.owner, ACTION_METHODS[self._action])()
        except Exception:
            logging.exception('Desktop assistant action failed: %s', self._action)
            if self._selection_pending:
                self._selection_finished(False)
                waiting_for_selection = True
        finally:
            # Main's fullscreen/dynamic actions queue capture after hiding the
            # main window. Keep the companion hidden until that delay expires.
            if not waiting_for_selection:
                QtCore.QTimer.singleShot(350, self._finish_dispatch)

    def _finish_dispatch(self):
        if not self._closed:
            self._dispatching = False
            if self.menu is not None:
                self.menu.set_actions_enabled(True)
            self.refresh_visibility()

    def dispose(self):
        if self._closed:
            return
        if self._selection_request_token is not None:
            self._selection_request_token.set()
            self._selection_request_token = None
        self._closed = True
        self._dispatch_timer.stop()
        self._unsubscribe()
        app = QtWidgets.QApplication.instance()
        app.applicationStateChanged.disconnect(self._application_state_changed)
        app.screenAdded.disconnect(self._screens_changed)
        app.screenRemoved.disconnect(self._screens_changed)
        for screen in self._screens:
            try:
                screen.availableGeometryChanged.disconnect(self.restore_position)
                screen.geometryChanged.disconnect(self.restore_position)
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
