"""Optional desktop companion and shortcuts to existing workflows.

No keyboard hooks, screen polling, translation engine or network access lives
here. Capture ownership hides both windows before the first screenshot.
"""
from pathlib import Path
import logging
import math
import sys
import weakref

from PyQt5 import QtCore, QtGui, QtWidgets, sip

from assistant_text import assistant_text
from button_styles import button_qss
from assistant_settings import BEHAVIORS, assistant_preferences
from assistant_art import companion_art
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
        self.behavior = 'idle'
        self.appearance = 'orb'
        self.custom_image = ''
        self.speed = 40
        self.facing = 1
        self._walk_remainder = 0.0
        self.menu_open = False
        self._clock = QtCore.QElapsedTimer()
        self._animation = QtCore.QTimer(self)
        self._animation.setInterval(33)
        self._animation.timeout.connect(self._advance)
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
        # Transparent in every state: no hover disc, border or native focus box.
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        walking = self.appearance == 'walking'
        if walking:
            pixmap = self.movie.currentPixmap()
        else:
            pixmap = companion_art(self.appearance, self.custom_image)
        if not pixmap.isNull():
            source = self._sprite_bounds if walking and not self._sprite_bounds.isEmpty() else pixmap.rect()
            extent = round(self.width() * .86)
            size = source.size().scaled(extent, extent, QtCore.Qt.KeepAspectRatio)
            # The walking sprite never changes into unrelated 3D art. Static
            # shortcuts are centered and have no animation or breathing timer.
            baseline = self.height() * .93 if walking else (self.height() + size.height()) / 2
            painter.translate(self.width() / 2, baseline)
            if walking:
                painter.scale(self.facing, 1)
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
        active = self.appearance == 'walking' and self.isVisible() and not self._hover and self._press is None and not self.menu_open
        if self.movie.state() == QtGui.QMovie.NotRunning:
            self.movie.start()
        self.movie.setPaused(not (active and self.behavior == 'walk'))
        animate = active and self.behavior == 'walk'
        if animate and not self._animation.isActive():
            self._clock.start()
            self._animation.start()
        elif not animate:
            self._animation.stop()

    def set_behavior(self, behavior):
        self.behavior = behavior if behavior in BEHAVIORS else 'idle'
        self._sync_motion()
        self.update()

    def _advance(self, seconds=None):
        if (self.appearance != 'walking' or self.behavior != 'walk'
                or not self.isVisible() or self._hover or self._press is not None or self.menu_open):
            return
        dt = min(.1, self._clock.restart() / 1000) if seconds is None else seconds
        if self.appearance == 'walking' and self.behavior == 'walk':
            screen = QtWidgets.QApplication.screenAt(self.geometry().center()) or self.screen()
            bounds = screen.availableGeometry()
            self._walk_remainder += self.speed * desktop_control_scale(screen) * dt
            step = int(self._walk_remainder)
            self._walk_remainder -= step
            target = self.pos() + QtCore.QPoint(step * self.facing, 0)
            clamped = clamp_position(target, self.size(), bounds)
            if clamped != target:
                self.facing *= -1
            self.move(clamped)
        self.update()

    def hideEvent(self, event):
        self.movie.setPaused(True)
        self._animation.stop()
        self._press = None
        self._hover = False
        super().hideEvent(event)

    def enterEvent(self, event):
        self._hover = True
        self._sync_motion()
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self._sync_motion()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press = event.globalPos()
            self._origin = self.pos()
            self._dragging = False
            self._sync_motion()
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
            self._sync_motion()


class ActionButton(QtWidgets.QPushButton):
    def __init__(self, title, description, dark, parent=None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        # Each program action is its own card. The previous transparent
        # buttons ran together into one large block, especially on dark mode.
        self.setStyleSheet(button_qss(dark, 'secondary') + 'QPushButton { text-align:left; }')
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

    def minimumSizeHint(self):
        # Two-column cards must wrap their descriptions instead of forcing the
        # scroll area's content wider than the popup viewport.
        return self.layout().minimumSize()

    def heightForWidth(self, width):
        return self.layout().totalHeightForWidth(width)


class AssistantMenu(QtWidgets.QFrame):
    action_requested = QtCore.pyqtSignal(str)
    visibility_changed = QtCore.pyqtSignal(bool)

    def __init__(self, language, dark, factor=1.0, behavior='idle', appearance='orb'):
        super().__init__(None, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setObjectName('desktopAssistantMenu')
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setWindowTitle(assistant_text(language, 'title'))
        background, border = ('#201d28', '#746087') if dark else ('#f7f3fa', '#a18bb9')
        header, header_border = ('#292431', '#4d425a') if dark else ('#eee8f4', '#d2c5dd')
        self.setStyleSheet(f'''
            QFrame#desktopAssistantMenu {{ background:{background}; border:1px solid {border}; border-radius:12px; }}
            QFrame#assistantMenuHeader {{ background:{header}; border:1px solid {header_border}; border-radius:9px; }}
            QFrame#assistantMenuDivider {{ background:{header_border}; border:0; max-height:1px; }}
            QFrame#assistantMenuHeader QLabel {{ background:transparent; border:0; }}
        ''')
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(9, 9, 9, 9)
        outer.setSpacing(7)
        self.header_widget = QtWidgets.QFrame(self)
        self.header_widget.setObjectName('assistantMenuHeader')
        header_layout = QtWidgets.QVBoxLayout(self.header_widget)
        header_layout.setContentsMargins(7, 5, 7, 7)
        header_layout.setSpacing(5)
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
        header_layout.addLayout(title_row)
        navigation = QtWidgets.QHBoxLayout()
        navigation.setSpacing(6)
        self.section_buttons = {}
        self.section_pages = {}
        for key in ('translation_section', 'companion_section'):
            button = QtWidgets.QPushButton(assistant_text(language, key))
            button.setCheckable(True)
            button.setStyleSheet(button_qss(dark, 'secondary', compact=True))
            button.setMinimumHeight(34)
            button.clicked.connect(lambda checked=False, section=key: self.select_section(section))
            self.section_buttons[key] = button
            navigation.addWidget(button)
        header_layout.addLayout(navigation)
        outer.addWidget(self.header_widget)
        divider = QtWidgets.QFrame(self)
        divider.setObjectName('assistantMenuDivider')
        divider.setFixedHeight(1)
        outer.addWidget(divider)
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
        self.factor = factor
        for key in self.section_buttons:
            page = QtWidgets.QWidget()
            self.section_pages[key] = page
            layout.addWidget(page)
        translate_layout = QtWidgets.QGridLayout(self.section_pages['translation_section'])
        translate_layout.setContentsMargins(2, 5, 2, 5)
        translate_layout.setHorizontalSpacing(8)
        translate_layout.setVerticalSpacing(8)
        for index, action in enumerate(('text', 'area', 'screen', 'copy', 'dynamic', 'documents')):
            button = ActionButton(*assistant_text(language, action), dark)
            button.setMinimumHeight(80)
            button.clicked.connect(lambda checked=False, key=action: self.action_requested.emit(key))
            translate_layout.addWidget(button, index // 2, index % 2)
            self.buttons[action] = button
        companion_layout = QtWidgets.QVBoxLayout(self.section_pages['companion_section'])
        companion_layout.setContentsMargins(4, 8, 4, 8)
        companion_layout.setSpacing(10)
        explanation = QtWidgets.QLabel(assistant_text(language, 'walking_hint' if appearance == 'walking' else 'static_hint'))
        explanation.setWordWrap(True)
        explanation.setStyleSheet(f'color:{"#bdb2ca" if dark else "#70647e"}; font-size:13px;')
        companion_layout.addWidget(explanation)
        modes = QtWidgets.QGridLayout()
        for index, mode in enumerate(BEHAVIORS):
            button = QtWidgets.QPushButton(assistant_text(language, 'pause_walk' if mode == 'idle' else mode))
            button.setCheckable(True)
            button.setChecked(mode == behavior)
            button.setEnabled(appearance == 'walking')
            button.setVisible(appearance == 'walking')
            button.setStyleSheet(button_qss(dark, 'secondary', compact=True))
            button.setMinimumHeight(30)
            button.clicked.connect(lambda checked=False, key=mode: self.action_requested.emit(key))
            modes.addWidget(button, index // 2, index % 2)
            self.buttons[mode] = button
        companion_layout.addLayout(modes)
        heading = QtWidgets.QLabel(assistant_text(language, 'quick_actions'))
        heading.setStyleSheet(explanation.styleSheet())
        companion_layout.addWidget(heading)
        fun = QtWidgets.QHBoxLayout()
        for action in ('home',):
            button = QtWidgets.QPushButton(assistant_text(language, action))
            button.setStyleSheet(button_qss(dark, 'quiet', compact=True))
            button.setMinimumHeight(30)
            button.clicked.connect(lambda checked=False, key=action: self.action_requested.emit(key))
            fun.addWidget(button)
            self.buttons[action] = button
        companion_layout.addLayout(fun)
        companion_layout.addStretch(1)
        footer = QtWidgets.QHBoxLayout()
        for action in ('settings', 'guide'):
            button = QtWidgets.QPushButton(assistant_text(language, 'companion_settings' if action == 'settings' else action))
            button.setStyleSheet(button_qss(dark, 'primary' if action == 'settings' else 'secondary', compact=True))
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
        self.select_section('translation_section')
        from window_appearance import scale_native_controls
        scale_native_controls(self, factor)

    def _apply_rounded_shape(self):
        # On Windows and Linux the QWidget mask clips the native popup window,
        # not just the rounded background painted by the stylesheet. Cocoa
        # keeps its antialiased translucent corners and deliberately skips it.
        from styled_dialogs import _apply_rounded_popup_mask
        _apply_rounded_popup_mask(self, 12)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_rounded_shape()

    def select_section(self, section):
        for key, page in self.section_pages.items():
            page.setVisible(key == section)
            self.section_buttons[key].setChecked(key == section)
        if self.isVisible() and hasattr(self, '_placement'):
            self.open_beside(*self._placement)

    def open_beside(self, anchor, available):
        self._placement = (QtCore.QRect(anchor), QtCore.QRect(available))
        self.ensurePolished()
        width = min(round(420 * self.factor), available.width())
        content_width = max(80, width - round(34 * self.factor))
        self._content.setMinimumHeight(0)
        self._content.setMinimumHeight(self._content.layout().totalHeightForWidth(content_width))
        height = min(max(round(330 * self.factor), self._content.minimumHeight() + round(108 * self.factor)), available.height())
        self.resize(width, height)
        x = anchor.left() - width - 8
        if x < available.left():
            x = anchor.right() + 9
        point = clamp_position(QtCore.QPoint(x, anchor.bottom() - height + 1), self.size(), available)
        self.move(point)
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
        context = (self.owner.current_interface_language, self.owner.current_theme != 'Светлая', factor,
                   preferences['desktop_assistant_behavior'], preferences['desktop_assistant_appearance'])
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
        self.anchor.speed = preferences['desktop_assistant_speed']
        self.anchor.appearance = preferences['desktop_assistant_appearance']
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
        self.menu.open_beside(self.anchor.geometry(), screen.availableGeometry())

    def _menu_visibility(self, visible):
        self.anchor.menu_open = visible
        self.anchor._sync_motion()

    def request_action(self, action):
        if (self._closed or self._dispatching
                or QtWidgets.QApplication.activeModalWidget() is not None):
            return
        if action not in (*ACTION_METHODS, *BEHAVIORS, 'home', 'text', 'settings', 'hide'):
            return
        if action in BEHAVIORS and self.anchor.appearance != 'walking':
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
            return
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
        self.anchor.movie.stop()
        self.anchor._animation.stop()
        self.anchor.close()
        self.anchor.deleteLater()
        self.deleteLater()
