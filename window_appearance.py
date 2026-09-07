"""Shared native-dialog sizing and palette, independent of OCR screen coordinates."""

import re
import math
import weakref

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5 import sip

from ui_scaling import BASE_SCALE, DEFAULT_SCALE, normalize_ui_scale, center_window, window_position_context


_PIXELS = re.compile(r'(-?\d+(?:\.\d+)?)px\b')
_COLOUR = re.compile(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b')


class _StoredAppearance:
    """Qt owns this snapshot even if a private child's Python wrapper expires."""
    def __init__(self, manager, data):
        self.manager = weakref.ref(manager)
        self.data = data


def themed_stylesheet(style, dark):
    """Bring legacy, explicitly coloured surfaces into the selected palette."""
    def block(match):
        body = match.group(1)
        background = re.search(r'(?<!-)background(?:-color)?\s*:\s*(#[\da-fA-F]{3,6})', body)
        accent = False
        if background:
            colour = QtGui.QColor(background.group(1))
            accent = colour.saturation() > 70 and 85 <= colour.lightness() <= 180

        def declaration(item):
            name, value = item.group(1), item.group(2)
            def colour(token):
                c = QtGui.QColor(token.group())
                light = c.lightness()
                if 'background' in name:
                    if not dark and light < 90:
                        return '#f2eef5' if light > 25 else '#e9e4ed'
                    if dark and light > 200:
                        return '#1d1a22' if light < 245 else '#141217'
                elif 'border' in name:
                    if not dark and light > 180:
                        return '#9684a6'
                    if dark and light < 65:
                        return '#776585'
                elif name in ('color', 'selection-color') and not accent:
                    if not dark and light > 140:
                        return '#302837'
                    if dark and light < 120:
                        return '#f1edf5'
                return token.group()
            return name + ':' + _COLOUR.sub(colour, value)
        return '{' + re.sub(r'([\w-]+)\s*:\s*([^;{}]+)', declaration, body) + '}'
    if style.strip() and '{' not in style:
        return re.sub(r'\{([^{}]*)\}', block, '{' + style + '}')[1:-1]
    return re.sub(r'\{([^{}]*)\}', block, style)


def scaled_stylesheet(style, factor):
    return _PIXELS.sub(lambda m: f'{round(float(m.group(1)) * factor)}px', style)


def themed_html(value, dark, factor):
    value = themed_stylesheet(value, dark)
    value = re.sub(r'(style=")([^"]*)(")',
                   lambda m: m[1] + themed_stylesheet('{' + m[2] + '}', dark)[1:-1] + m[3], value)
    value = scaled_stylesheet(value, factor)
    return re.sub(r'(\d+(?:\.\d+)?)pt\b', lambda m: f'{float(m[1]) * factor:g}pt', value)


class DialogAppearance(QtCore.QObject):
    def __init__(self, app, percent=DEFAULT_SCALE, theme='Темная'):
        super().__init__(app)
        self.app = app
        self.percent = normalize_ui_scale(percent)
        self.theme = theme
        self._windows = weakref.WeakKeyDictionary()
        self._busy = False
        self._pending = weakref.WeakSet()
        app.installEventFilter(self)
        app.setProperty('ui_theme', theme)
        from styled_dialogs import install_tooltip_style
        install_tooltip_style(app, theme != 'Светлая')

    def _eligible(self, window):
        return (isinstance(window, (QtWidgets.QDialog, QtWidgets.QMenu)) and window.isWindow()
                and window.graphicsProxyWidget() is None)

    def _baseline(self, obj, records):
        record = records.get(obj)
        if record is None:
            saved = obj.property('_cntAppearanceBaseline')
            if isinstance(saved, _StoredAppearance) and saved.manager() is self:
                record = saved.data
                records[obj] = record
        return record

    def _remember_baseline(self, obj, records, record):
        records[obj] = record
        # Qt creates some scroll-area containers and layouts internally. Their
        # Python wrappers are transient; a WeakKeyDictionary alone loses the
        # original font and margins between two applications of the same scale.
        obj.setProperty('_cntAppearanceBaseline', _StoredAppearance(self, record))

    def eventFilter(self, watched, event):
        event_type = event.type()
        if (self._busy or event_type not in (QtCore.QEvent.Polish, QtCore.QEvent.Show, QtCore.QEvent.StyleChange)
                or not isinstance(watched, QtWidgets.QWidget)):
            return False
        window = watched.window()
        if not self._eligible(window):
            return False
        if (event.type() == QtCore.QEvent.Polish and isinstance(watched, QtWidgets.QMenu)):
            # QMenu calculates its screen position before Show. Applying its
            # padding there would enlarge the first popup below the taskbar.
            self.apply(watched)
        elif event.type() == QtCore.QEvent.Show and watched is window:
            automatic_position = (window.windowType() != QtCore.Qt.Popup
                                  and not window.testAttribute(QtCore.Qt.WA_Moved))
            self.apply(window)
            if automatic_position:
                center_window(window, available=self.available_geometry(window))
                position = window.pos()
                reference = weakref.ref(window)
                def finish_position():
                    item = reference()
                    if (item is not None and not sip.isdeleted(item) and item.isVisible()
                            and item.pos() == position):
                        center_window(item, available=self.available_geometry(item))
                QtCore.QTimer.singleShot(0, finish_position)
        elif event.type() == QtCore.QEvent.StyleChange and window in self._windows:
            self._queue(window)
        return False

    def _queue(self, window):
        if window in self._pending:
            return
        self._pending.add(window)
        reference = weakref.ref(window)
        def update():
            item = reference()
            if item is not None:
                self._pending.discard(item)
                if not sip.isdeleted(item):
                    self.apply(item)
        QtCore.QTimer.singleShot(0, update)

    def refresh(self, percent=None, theme=None):
        if percent is not None:
            self.percent = normalize_ui_scale(percent)
        if theme is not None:
            self.theme = theme
            self.app.setProperty('ui_theme', theme)
            from styled_dialogs import install_tooltip_style
            install_tooltip_style(self.app, theme != 'Светлая')
        for window in list(self.app.topLevelWidgets()):
            if self._eligible(window) and (window.isVisible() or window in self._windows):
                self.apply(window)

    def set_window_percent(self, window, percent, anchor_widget=None):
        anchor = anchor_widget.mapToGlobal(anchor_widget.rect().center()) if anchor_widget is not None else None
        window.setProperty('ui_scale_override', normalize_ui_scale(percent))
        self.apply(window)
        if anchor is not None:
            position = window.pos() + anchor - anchor_widget.mapToGlobal(anchor_widget.rect().center())
            available = self.available_geometry(window)
            window.move(max(available.left(), min(position.x(), available.right() - window.width() + 1)),
                        max(available.top(), min(position.y(), available.bottom() - window.height() + 1)))

    def window_percent(self, window):
        return normalize_ui_scale(window.property('ui_scale_override') or self.percent)

    def available_geometry(self, window):
        if not window.testAttribute(QtCore.Qt.WA_Moved):
            return window_position_context(window)[1]
        screen = window.screen() or self.app.primaryScreen()
        return screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)

    def apply(self, window):
        if self._busy or sip.isdeleted(window):
            return
        if isinstance(window, QtWidgets.QMenu):
            self._apply_menu(window)
            return
        self._busy = True
        updates = window.updatesEnabled()
        window.setUpdatesEnabled(False)
        root_layout = window.layout()
        layout_enabled = root_layout.isEnabled() if root_layout is not None else False
        try:
            window.ensurePolished()
            state = self._windows.get(window)
            if state is None:
                if window.layout() is not None:
                    window.layout().activate()
                base_size = window.size().expandedTo(window.minimumSizeHint())
                if root_layout is not None and root_layout.hasHeightForWidth() and window.minimumHeight() != window.maximumHeight():
                    base_size.setHeight(max(base_size.height(), root_layout.totalHeightForWidth(base_size.width())))
                state = {'size': base_size,
                         'widgets': weakref.WeakKeyDictionary(),
                         'layouts': weakref.WeakKeyDictionary(), 'factor': 1.0,
                         'theme': None, 'last_size': window.size()}
                if hasattr(window, '_TITLE_HEIGHT'):
                    state['title_height'] = window._TITLE_HEIGHT
                self._windows[window] = state
            if root_layout is not None:
                root_layout.setEnabled(False)
            if state['theme'] != self.theme:
                refresh = getattr(window, 'refresh_theme', None)
                if callable(refresh):
                    refresh(self.theme)
                elif hasattr(window, '_dark') and callable(getattr(window, '_apply_style', None)):
                    window._dark = self.theme != 'Светлая'
                    window._apply_style()
                state['theme'] = self.theme
            # Preserve resizing done by the user between scale changes.
            if window.size() != state['last_size']:
                state['size'] = window.size() / state['factor']
            available = self.available_geometry(window)
            base = state['size']
            fitting_factor = min(max(1, available.width() - 24) / max(1, base.width()),
                                 max(1, available.height() - 32) / max(1, base.height()))
            maximum_percent = min(200, math.floor(fitting_factor * BASE_SCALE))
            factor = min(self.window_percent(window) / BASE_SCALE,
                         maximum_percent / BASE_SCALE if maximum_percent >= 80 else fitting_factor)
            widgets = [window] + [w for w in window.findChildren(QtWidgets.QWidget) if w.window() is window]
            # Snapshot before changing any parent font or stylesheet.
            for widget in widgets:
                record = self._baseline(widget, state['widgets'])
                if record is None:
                    record = {'font': QtGui.QFont(widget.font()), 'minimum': widget.minimumSize(),
                              'maximum': widget.maximumSize(), 'style': widget.styleSheet(),
                              'last_style': widget.styleSheet(), 'geometry': widget.geometry()}
                    if isinstance(widget, QtWidgets.QAbstractButton):
                        record['icon_size'] = widget.iconSize()
                    if isinstance(widget, QtWidgets.QSplitter):
                        record['handle_width'] = widget.handleWidth()
                    if isinstance(widget, QtWidgets.QLabel):
                        pixmap = widget.pixmap()
                        if pixmap is not None and not pixmap.isNull():
                            record['pixmap'] = QtGui.QPixmap(pixmap)
                    self._remember_baseline(widget, state['widgets'], record)
                elif widget.styleSheet() != record['last_style']:
                    record['style'] = widget.styleSheet()
                if isinstance(widget, QtWidgets.QLabel):
                    pixmap = widget.pixmap()
                    if pixmap is not None and not pixmap.isNull() and pixmap.cacheKey() != record.get('last_pixmap_key'):
                        record['pixmap'] = QtGui.QPixmap(pixmap)
                if isinstance(widget, QtWidgets.QTextBrowser):
                    html = widget.toHtml()
                    if html != record.get('last_html'):
                        record['html'] = html
                elif isinstance(widget, QtWidgets.QLabel) and '<' in widget.text():
                    if widget.text() != record.get('last_html'):
                        record['html'] = widget.text()
            dark = self.theme != 'Светлая'
            if 'title_height' in state:
                window._TITLE_HEIGHT = round(state['title_height'] * factor)
            for widget in widgets:
                record = state['widgets'][widget]
                font = QtGui.QFont(record['font'])
                if font.pixelSize() > 0:
                    font.setPixelSize(max(1, round(font.pixelSize() * factor)))
                else:
                    font.setPointSizeF(max(1, font.pointSizeF() * factor))
                widget.setFont(font)
                widget.setMinimumSize(record['minimum'] * factor)
                maximum = record['maximum']
                widget.setMaximumSize(*(16777215 if value == 16777215 else round(value * factor)
                                        for value in (maximum.width(), maximum.height())))
                if 'icon_size' in record:
                    widget.setIconSize(record['icon_size'] * factor)
                if 'handle_width' in record:
                    widget.setHandleWidth(max(1, round(record['handle_width'] * factor)))
                if 'pixmap' in record:
                    pixmap = record['pixmap']
                    widget.setPixmap(pixmap.scaled(pixmap.size() * factor,
                                                   QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                    record['last_pixmap_key'] = widget.pixmap().cacheKey()
                if 'html' in record:
                    html = themed_html(record['html'], dark, factor)
                    if isinstance(widget, QtWidgets.QTextBrowser):
                        if html != record.get('rendered_html'):
                            position = widget.verticalScrollBar().value()
                            widget.setHtml(html)
                            widget.verticalScrollBar().setValue(position)
                        record['last_html'] = widget.toHtml()
                    else:
                        widget.setText(html)
                        record['last_html'] = html
                    record['rendered_html'] = html
                style = scaled_stylesheet(themed_stylesheet(record['style'], dark), factor)
                record['last_style'] = style
                # Bypass message-box style composition: its source stays unscaled.
                QtWidgets.QWidget.setStyleSheet(widget, style)
                palette = widget.palette()
                for role, colour in ((QtGui.QPalette.Window, '#161319' if dark else '#eee9f2'),
                                     (QtGui.QPalette.Base, '#201c25' if dark else '#faf8fc'),
                                     (QtGui.QPalette.Text, '#f1edf5' if dark else '#302837'),
                                     (QtGui.QPalette.WindowText, '#f1edf5' if dark else '#302837'),
                                     (QtGui.QPalette.ButtonText, '#f1edf5' if dark else '#302837')):
                    palette.setColor(role, QtGui.QColor(colour))
                widget.setPalette(palette)
                if widget.parentWidget() is window and window.layout() is None:
                    geometry = record['geometry']
                    widget.setGeometry(QtCore.QRect(geometry.topLeft() * factor, geometry.size() * factor))
            layouts = window.findChildren(QtWidgets.QLayout)
            for layout in layouts:
                if layout.parentWidget() is None or layout.parentWidget().window() is not window:
                    continue
                record = self._baseline(layout, state['layouts'])
                if record is None:
                    m = layout.contentsMargins()
                    record = (m.left(), m.top(), m.right(), m.bottom(), layout.spacing())
                    self._remember_baseline(layout, state['layouts'], record)
                layout.setContentsMargins(*(round(v * factor) for v in record[:4]))
                if record[4] >= 0:
                    layout.setSpacing(round(record[4] * factor))
            state['factor'] = factor
            window.setProperty('ui_effective_scale', factor)
            window.setProperty('ui_maximum_scale_percent', maximum_percent)
            if root_layout is not None:
                root_layout.setEnabled(layout_enabled)
                root_layout.activate()
            target_size = base * factor
            if root_layout is not None and root_layout.hasHeightForWidth() and window.minimumHeight() != window.maximumHeight():
                target_size.setHeight(max(target_size.height(), root_layout.totalHeightForWidth(target_size.width())))
            window.resize(target_size)
            for widget in widgets:
                if widget.layout() is not None:
                    widget.layout().activate()
            window.move(max(available.left(), min(window.x(), available.right() - window.width() + 1)),
                        max(available.top(), min(window.y(), available.bottom() - window.height() + 1)))
            state['last_size'] = window.size()
            from styled_dialogs import apply_dark_native_frame
            apply_dark_native_frame(window, dark)
            updated = getattr(window, '_refresh_scale_caption', None)
            if callable(updated):
                updated()
        finally:
            if root_layout is not None:
                root_layout.setEnabled(layout_enabled)
            window.setUpdatesEnabled(updates)
            self._busy = False

    def _apply_menu(self, menu):
        """Menus keep their native size and fit above the taskbar."""
        self._busy = True
        try:
            state = self._windows.get(menu)
            if state is None:
                state = {'style': menu.styleSheet(), 'last_style': menu.styleSheet(),
                         'font': QtGui.QFont(menu.font() if menu.testAttribute(QtCore.Qt.WA_SetFont)
                                             else self.app.font('QMenu'))}
                self._windows[menu] = state
            elif menu.styleSheet() != state['last_style']:
                state['style'] = menu.styleSheet()
            dark = self.theme != 'Светлая'
            if state['style']:
                style = themed_stylesheet(state['style'], dark)
            else:
                from button_styles import button_palette
                colors = button_palette(dark)
                style = f"""
                    QMenu {{ background:{colors['surface']}; color:{colors['text']};
                        border:1px solid {colors['border']}; padding:4px; }}
                    QMenu::item {{ padding:5px 22px 5px 10px; border-radius:4px; }}
                    QMenu::item:selected {{ background:{colors['hover']}; }}
                    QMenu::item:disabled {{ color:{colors['disabled']}; }}
                    QMenu::separator {{ height:1px; background:{colors['border']}; margin:4px 6px; }}
                """
            state['last_style'] = style
            if menu.font() != state['font']:
                menu.setFont(state['font'])
            if menu.styleSheet() != style:
                menu.setStyleSheet(style)
            menu.setProperty('ui_effective_scale', 1.0)
            if menu.isVisible():
                screen = menu.screen() or self.app.primaryScreen()
                if screen is not None:
                    available = screen.availableGeometry()
                    menu.move(max(available.left(), min(menu.x(), available.right() - menu.width() + 1)),
                              max(available.top(), min(menu.y(), available.bottom() - menu.height() + 1)))
        finally:
            self._busy = False


def install_window_appearance(app, percent=DEFAULT_SCALE, theme='Темная'):
    manager = getattr(app, '_dialog_appearance', None)
    if manager is None:
        manager = DialogAppearance(app, percent, theme)
        app._dialog_appearance = manager
    else:
        manager.refresh(percent, theme)
    return manager


def refresh_window_appearance(percent=None, theme=None):
    app = QtWidgets.QApplication.instance()
    manager = getattr(app, '_dialog_appearance', None)
    if manager is not None:
        manager.refresh(percent, theme)
    elif app is not None and theme is not None:
        app.setProperty('ui_theme', theme)
        from styled_dialogs import install_tooltip_style
        install_tooltip_style(app, theme != 'Светлая')


def style_capture_controls(overlay, config, controls):
    """Keep screen controls compact, opaque and independent of the app's zoom."""
    from button_styles import button_qss
    from settings_window import DropDownCombo, modern_combo_style
    controls = [widget for widget in controls if widget is not None]
    dark = config.get('theme', 'Темная') != 'Светлая'
    for widget in controls:
        if widget.property('capture_base_size') is None:
            widget.setProperty('capture_base_size', widget.size())
            widget.setProperty('capture_base_icon', widget.iconSize())
    overlay.setProperty('ui_effective_scale', 1.0)
    for widget in controls:
        if isinstance(widget, QtWidgets.QComboBox):
            style = modern_combo_style(dark, 14) + """
                QComboBox { margin:0; padding:3px 20px 3px 7px; }
                QComboBox::drop-down { width:18px; }
            """
            if isinstance(widget, DropDownCombo):
                widget.setMaxVisibleItems(9)
                widget.set_popup_background('#20212a' if dark else '#f1edf4')
            # Reserve the icon, the language code and the chevron separately.
            # The settings-field padding hid the code in these compact fields.
            widget.setFixedSize(max(112, widget.property('capture_base_size').width()), 44)
            widget.setIconSize(QtCore.QSize(28, 28))
        else:
            style = button_qss(dark, 'secondary',
                               selector='QToolButton' if isinstance(widget, QtWidgets.QToolButton) else 'QPushButton',
                               icon=isinstance(widget, QtWidgets.QToolButton), compact=True)
            widget.setFixedSize(max(36, widget.property('capture_base_size').width()), 44)
            widget.setIconSize(widget.property('capture_base_icon'))
        widget.setStyleSheet(style)
        palette = widget.palette()
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor('#f1edf5' if dark else '#302837'))
        widget.setPalette(palette)
