"""Searchable interface languages in the existing app panel."""
import unicodedata
from PyQt5 import QtCore, QtGui, QtWidgets

from button_styles import button_palette, button_qss
from styled_dialogs import tooltip_text
from languages import LANGUAGES, LOCALIZED_LANGUAGE_NAMES
from language_search import SEARCH_TEXT


_PICKER_LABELS = {
    'en': ('Interface language', 'Close language selection'),
    'ru': ('Язык интерфейса', 'Закрыть выбор языка'),
    'es': ('Idioma de la interfaz', 'Cerrar la selección de idioma'),
    'de': ('Oberflächensprache', 'Sprachauswahl schließen'),
    'fr': ('Langue de l’interface', 'Fermer le choix de langue'),
    'zh': ('界面语言', '关闭语言选择'),
    'pt': ('Idioma da interface', 'Fechar a seleção de idioma'),
    'it': ('Lingua dell’interfaccia', 'Chiudi la selezione della lingua'),
    'ar': ('لغة الواجهة', 'إغلاق اختيار اللغة'),
    'tr': ('Arayüz dili', 'Dil seçimini kapat'),
    'hi': ('इंटरफ़ेस की भाषा', 'भाषा चयन बंद करें'),
    'id': ('Bahasa antarmuka', 'Tutup pemilihan bahasa'),
}
# Keep title and close at indexes 0/3 for the title-bar flag's accessible label.
PICKER_TEXT = {code: (title, *SEARCH_TEXT[code], close)
               for code, (title, close) in _PICKER_LABELS.items()}



def _search_key(value):
    return ''.join(char for char in unicodedata.normalize('NFKD', str(value).casefold())
                   if not unicodedata.combining(char))


class _RoundedChoices(QtWidgets.QFrame):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h, r = float(self.width()), float(self.height()), 9.
        path = QtGui.QPainterPath()
        path.moveTo(0, 0)
        path.lineTo(w, 0)
        path.lineTo(w, h-r)
        path.quadTo(w, h, w-r, h)
        path.lineTo(r, h)
        path.quadTo(0, h, 0, h-r)
        path.closeSubpath()
        self.setMask(QtGui.QRegion(path.toFillPolygon().toPolygon()))


class InterfaceLanguagePicker(QtWidgets.QFrame):
    languageSelected = QtCore.pyqtSignal(str)
    dismissed = QtCore.pyqtSignal()
    COLUMNS, ROW_HEIGHT, PANEL_HEIGHT = 4, 38, 146

    def __init__(self, options, current, resource_path, parent=None, *, dark=True):
        super().__init__(parent)
        self.setObjectName('interfaceLanguagePicker')
        self.setProperty('keyboardOwnNavigation', True)
        self.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMinimumHeight(70)
        self.resize(672, self.PANEL_HEIGHT)
        self.buttons, self.name_labels, self.ticks = {}, {}, {}
        self._codes = tuple(option['code'] for option in options)
        self._current = current
        self._active_code = current if current in self._codes else next(iter(self._codes), None)
        self._visible_codes = self._codes
        self.keyboard_mode = False
        languages = {language.code: language for language in LANGUAGES}
        self._search_terms = {}
        for option in options:
            code = option['code']
            language = languages.get(code)
            aliases = [code, option['name'], *option.get('aliases', ())]
            if language is not None:
                aliases += [language.english_name, language.russian_name]
            # Changing UI language must not invalidate an existing search.
            aliases += [names.get(code, '') for names in LOCALIZED_LANGUAGE_NAMES.values()]
            self._search_terms[code] = _search_key('\n'.join(aliases))

        body = QtWidgets.QVBoxLayout(self)
        # The styled frame already reserves its one-pixel outer boundary.
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.header = QtWidgets.QWidget(self)
        self.header.setFixedHeight(28)
        row = QtWidgets.QHBoxLayout(self.header)
        row.setContentsMargins(8, 1, 4, 1)
        row.setSpacing(8)
        self.title = QtWidgets.QLabel(self.header)
        self.title.setObjectName('interfaceLanguageTitle')
        self.title.setMinimumWidth(0)
        self.title.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        row.addWidget(self.title, 1)
        self.search = QtWidgets.QLineEdit(self.header)
        self.search.setObjectName('interfaceLanguageSearch')
        self.search.setFixedSize(206, 24)
        self.search.setClearButtonEnabled(True)
        self.search.installEventFilter(self)
        for control in self.search.findChildren(QtWidgets.QAbstractButton):
            control.installEventFilter(self)
        row.addWidget(self.search)
        self.close_button = QtWidgets.QToolButton(self.header)
        self.close_button.setText('×')
        self.close_button.setFixedSize(24, 24)
        self.close_button.setFocusPolicy(QtCore.Qt.TabFocus)
        self.close_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_button.clicked.connect(self.dismissed)
        self.close_button.installEventFilter(self)
        row.addWidget(self.close_button)
        body.addWidget(self.header)
        self.choices = _RoundedChoices(self)
        self.choices.setObjectName('interfaceLanguageChoices')
        choices_layout = QtWidgets.QVBoxLayout(self.choices)
        choices_layout.setContentsMargins(1, 1, 1, 0)
        choices_layout.setSpacing(0)
        self.scroll = QtWidgets.QScrollArea(self.choices)
        self.scroll.setObjectName('interfaceLanguageScroll')
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setFocusPolicy(QtCore.Qt.NoFocus)
        self.scroll.viewport().setObjectName('interfaceLanguageViewport')
        self.scroll.viewport().installEventFilter(self)
        self.scroll.verticalScrollBar().installEventFilter(self)
        self.catalog = QtWidgets.QWidget(self.scroll)
        self.catalog.setObjectName('interfaceLanguageCatalog')
        self.catalog.installEventFilter(self)
        self.grid = QtWidgets.QGridLayout(self.catalog)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(0)
        self.grid.setAlignment(QtCore.Qt.AlignTop)
        for column in range(self.COLUMNS):
            self.grid.setColumnStretch(column, 1)
        for option in options:
            code, name = option['code'], option['name']
            cell = QtWidgets.QPushButton(self.catalog)
            cell.setObjectName('interfaceLanguageCell')
            cell.setCheckable(True)
            cell.setFixedHeight(self.ROW_HEIGHT)
            cell.setMinimumWidth(0)
            cell.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
            cell.setCursor(QtCore.Qt.PointingHandCursor)
            cell.setAccessibleName(name)
            cell.setToolTip(tooltip_text(name))
            cell.clicked.connect(lambda _checked=False, code=code: self._activate(code))
            cell.installEventFilter(self)
            content = QtWidgets.QHBoxLayout(cell)
            content.setContentsMargins(8, 0, 6, 0)
            content.setSpacing(6)
            flag = QtWidgets.QLabel(cell)
            flag.setObjectName('interfaceLanguageFlag')
            flag.setFixedSize(18, 18)
            flag.setAlignment(QtCore.Qt.AlignCenter)
            pixels = QtGui.QPixmap(resource_path(option['icon'])).scaled(
                flag.size()*4, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            pixels.setDevicePixelRatio(4)
            flag.setPixmap(pixels)
            content.addWidget(flag)
            label = QtWidgets.QLabel(name, cell)
            label.setObjectName('interfaceLanguageName')
            label.setLayoutDirection(QtCore.Qt.RightToLeft if code.split('-')[0] in ('ar', 'he', 'fa', 'ur')
                                     else QtCore.Qt.LeftToRight)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter | QtCore.Qt.AlignAbsolute)
            label.setMinimumWidth(0)
            label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            content.addWidget(label, 1)
            tick = QtWidgets.QLabel(cell)
            tick.setFixedSize(12, 14)
            content.addWidget(tick)
            for child in (flag, label, tick):
                child.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            self.buttons[code], self.name_labels[code], self.ticks[code] = cell, label, tick
        self.scroll.setWidget(self.catalog)
        choices_layout.addWidget(self.scroll)
        self.empty = QtWidgets.QLabel(self.scroll.viewport())
        self.empty.setObjectName('interfaceLanguageEmpty')
        self.empty.setAlignment(QtCore.Qt.AlignCenter)
        self.empty.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.empty.hide()
        body.addWidget(self.choices, 1)
        self.search.textChanged.connect(self._apply_filter)
        self._apply_filter()
        self.set_theme(dark)
        self.set_language(current)
        for sequence, callback in ((QtCore.Qt.Key_Escape, self._dismiss_keyboard),
                                   ('Ctrl+F', self._focus_search)):
            shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(sequence), self)
            shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)

    @property
    def visible_codes(self):
        return self._visible_codes

    def _set_keyboard_mode(self, keyboard):
        self.keyboard_mode = bool(keyboard)
        navigation = getattr(QtWidgets.QApplication.instance(), '_keyboard_navigation', None)
        if navigation is not None:
            navigation.keyboard = self.keyboard_mode
            if not self.keyboard_mode:
                navigation._hide_ring()
        if not self.keyboard_mode:
            for control in (*self.buttons.values(), self.search, self.close_button):
                if control.property('keyboardFocus'):
                    control.setProperty('keyboardFocus', False)
                    control.style().unpolish(control)
                    control.style().polish(control)
                    control.update()

    def _apply_filter(self, *_args):
        terms = _search_key(self.search.text()).split()
        visible = tuple(code for code in self._codes
                        if all(term in self._search_terms[code] for term in terms))
        old_focus = self.focusWidget()
        while self.grid.count():
            self.grid.takeAt(0)
        self._visible_codes = visible
        if self._active_code not in visible:
            self._active_code = self._current if self._current in visible else next(iter(visible), None)
        for code, button in self.buttons.items():
            button.setVisible(code in visible)
            button.setFocusPolicy(QtCore.Qt.StrongFocus if code == self._active_code else QtCore.Qt.ClickFocus)
        rows = (len(visible)+self.COLUMNS-1)//self.COLUMNS
        for index, code in enumerate(visible):
            button = self.buttons[code]
            button.setProperty('divider', index % self.COLUMNS != self.COLUMNS-1 and index < len(visible)-1)
            button.setProperty('topRow', index//self.COLUMNS < rows-1)
            self.grid.addWidget(button, index//self.COLUMNS, index % self.COLUMNS)
            button.style().unpolish(button)
            button.style().polish(button)
        self.catalog.setMinimumHeight(rows*self.ROW_HEIGHT)
        self.grid.activate()
        self.scroll.verticalScrollBar().setValue(0)
        self.empty.setVisible(not visible)
        self.empty.setGeometry(self.scroll.viewport().rect())
        if not visible and old_focus in self.buttons.values():
            self.search.setFocus(QtCore.Qt.TabFocusReason if self.keyboard_mode else QtCore.Qt.OtherFocusReason)
        elif old_focus in self.buttons.values() and not old_focus.isVisible() and visible:
            self._focus_code(self._active_code)

    def _focus_code(self, code, reason=None):
        if code not in self._visible_codes:
            self.search.setFocus(reason if reason is not None else QtCore.Qt.OtherFocusReason)
            return
        self._active_code = code
        for other, button in self.buttons.items():
            button.setFocusPolicy(QtCore.Qt.StrongFocus if other == code else QtCore.Qt.ClickFocus)
        if reason is None:
            reason = QtCore.Qt.TabFocusReason if self.keyboard_mode else QtCore.Qt.OtherFocusReason
        self.buttons[code].setFocus(reason)
        self.scroll.ensureWidgetVisible(self.buttons[code], 0, 0)

    def focus_current_language(self, keyboard=None):
        if keyboard is not None:
            self._set_keyboard_mode(keyboard)
        self._focus_code(self._current if self._current in self._visible_codes else self._active_code)

    def _focus_search(self):
        self._set_keyboard_mode(True)
        self.search.setFocus(QtCore.Qt.ShortcutFocusReason)
        self.search.selectAll()

    def _dismiss_keyboard(self):
        self._set_keyboard_mode(True)
        self.dismissed.emit()

    def _activate(self, code):
        self.set_language(code)
        self.languageSelected.emit(code)

    def _tab(self, watched, backwards):
        controls = [self.search]
        if self._active_code in self._visible_codes:
            controls.append(self.buttons[self._active_code])
        controls.append(self.close_button)
        if watched in self.buttons.values() and self._active_code in self._visible_codes:
            watched = self.buttons[self._active_code]
        index = controls.index(watched) if watched in controls else 0
        target = controls[(index+(-1 if backwards else 1)) % len(controls)]
        reason = QtCore.Qt.BacktabFocusReason if backwards else QtCore.Qt.TabFocusReason
        if target in self.buttons.values():
            self._focus_code(self._active_code, reason)
        else:
            target.setFocus(reason)

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonDblClick, QtCore.QEvent.Wheel):
            self._set_keyboard_mode(False)
        if kind == QtCore.QEvent.Resize and watched is self.scroll.viewport() and hasattr(self, 'empty'):
            self.empty.setGeometry(self.scroll.viewport().rect())
        if kind == QtCore.QEvent.FocusIn and watched in self.buttons.values():
            self._active_code = next(code for code, button in self.buttons.items() if button is watched)
            for code, button in self.buttons.items():
                button.setFocusPolicy(QtCore.Qt.StrongFocus if code == self._active_code else QtCore.Qt.ClickFocus)
        if kind != QtCore.QEvent.KeyPress:
            return super().eventFilter(watched, event)
        self._set_keyboard_mode(True)
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            self._dismiss_keyboard()
        elif key == QtCore.Qt.Key_F and event.modifiers() == QtCore.Qt.ControlModifier:
            self._focus_search()
        elif key in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab):
            self._tab(watched, key == QtCore.Qt.Key_Backtab or bool(event.modifiers() & QtCore.Qt.ShiftModifier))
        elif watched is self.search:
            if self._visible_codes and key in (QtCore.Qt.Key_Down, QtCore.Qt.Key_Up, QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                code = self._active_code if key != QtCore.Qt.Key_Up else self._visible_codes[-1]
                self._focus_code(code)
                if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    self._activate(code)
            else:
                return super().eventFilter(watched, event)
        elif watched in self.buttons.values():
            index = self._visible_codes.index(self._active_code)
            target = index
            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Space):
                self._activate(self._active_code)
            elif key == QtCore.Qt.Key_Home:
                target = 0
            elif key == QtCore.Qt.Key_End:
                target = len(self._visible_codes)-1
            elif key == QtCore.Qt.Key_Left:
                target -= index % self.COLUMNS > 0
            elif key == QtCore.Qt.Key_Right:
                target += index % self.COLUMNS < self.COLUMNS-1 and index+1 < len(self._visible_codes)
            elif key == QtCore.Qt.Key_Up:
                target = max(index-self.COLUMNS, index % self.COLUMNS)
            elif key == QtCore.Qt.Key_Down:
                if index//self.COLUMNS < (len(self._visible_codes)-1)//self.COLUMNS:
                    target = min(index+self.COLUMNS, len(self._visible_codes)-1)
            elif key in (QtCore.Qt.Key_PageUp, QtCore.Qt.Key_PageDown):
                step = max(1, self.scroll.viewport().height()//self.ROW_HEIGHT)*self.COLUMNS
                target = max(0, min(len(self._visible_codes)-1,
                                   index+(-step if key == QtCore.Qt.Key_PageUp else step)))
            elif event.text().isprintable() and not event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier):
                self._focus_search()
                self.search.setText(event.text())
                return True
            else:
                return super().eventFilter(watched, event)
            if target != index or key in (QtCore.Qt.Key_Home, QtCore.Qt.Key_End):
                self._focus_code(self._visible_codes[target])
        elif watched is self.close_button and key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Space):
            self.close_button.click()
        else:
            return super().eventFilter(watched, event)
        event.accept()
        return True

    def mousePressEvent(self, event):
        self._set_keyboard_mode(False)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self._dismiss_keyboard()
            event.accept()
        else:
            super().keyPressEvent(event)


    def set_theme(self, dark):
        colors = button_palette(dark)
        ink, surface, edge, frame = (('#f2eff6', '#121116', '#433a4c', '#62566e') if dark
                                    else ('#27222d', '#f8f5fb', '#d7cde3', '#927cab'))
        self.setStyleSheet(f'''
            QFrame#interfaceLanguagePicker {{background:{'#1d1922' if dark else '#ffffff'};
                border:1px solid {frame}; border-radius:10px;}}
            QWidget {{background:transparent;}}
            QLabel#interfaceLanguageTitle {{color:{ink}; border:0; font-size:12px; font-weight:600;}}
            QFrame#interfaceLanguageChoices {{background:{surface}; border:0; border-top:1px solid {edge};}}
            QScrollArea#interfaceLanguageScroll {{background:transparent; border:0;}}
            QWidget#interfaceLanguageViewport, QWidget#interfaceLanguageCatalog {{background:{surface}; border:0;}}
            QLineEdit#interfaceLanguageSearch {{background:{surface}; color:{ink}; border:1px solid {edge};
                border-radius:5px; padding:0 7px; font-size:12px; font-weight:400;}}
            QLineEdit#interfaceLanguageSearch[keyboardFocus="true"]:focus {{border-color:{colors['focus']};}}
            QLabel#interfaceLanguageEmpty {{color:{ink}; border:0; font-size:12px;}}
            QScrollBar:vertical {{background:transparent; width:7px; margin:2px 0;}}
            QScrollBar::handle:vertical {{background:{frame}; min-height:18px; border-radius:3px;}}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{background:transparent;}}
            QLabel#interfaceLanguageName {{color:{ink}; border:0; font-size:14px; font-weight:400;}}
        ''')
        # QScrollArea owns an opaque viewport; transparent cell backgrounds
        # must never expose the platform's default light Base brush.
        for widget in (self.scroll.viewport(), self.catalog):
            palette = widget.palette()
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor(surface))
            palette.setColor(QtGui.QPalette.Base, QtGui.QColor(surface))
            widget.setPalette(palette)
            widget.setAutoFillBackground(True)
            widget.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        # Local chrome wins over the scaled canvas's general button rules.
        cell_style = f'''
            QPushButton#interfaceLanguageCell, QFrame#interfaceLanguageCell {{background:transparent; border:0; border-radius:0; padding:0;}}
            #interfaceLanguageCell[divider="true"] {{border-right:1px solid {edge};}}
            #interfaceLanguageCell[topRow="true"] {{border-bottom:1px solid {edge};}}
            QPushButton#interfaceLanguageCell:hover,
            QPushButton#interfaceLanguageCell[pointerHover="true"] {{background:{colors['hover']};}}
            QPushButton#interfaceLanguageCell[pointerHover="false"]:hover {{background:transparent;}}
            QPushButton#interfaceLanguageCell[current="true"] {{background:{colors['hover']};}}
            QPushButton#interfaceLanguageCell[current="true"] QLabel#interfaceLanguageName {{font-weight:600;}}
            QPushButton#interfaceLanguageCell[keyboardFocus="true"]:focus {{border:1px solid {colors['focus']};}}
        '''
        for cell in self.choices.findChildren(QtWidgets.QWidget, 'interfaceLanguageCell'):
            cell.setStyleSheet(cell_style)
        self.close_button.setStyleSheet(button_qss(dark, 'quiet', selector='QToolButton', icon=True, radius=4))
        check = QtGui.QPixmap(24, 28)
        check.setDevicePixelRatio(2)
        check.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(check)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(colors['focus']), 1.6, QtCore.Qt.SolidLine,
                                  QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(1, 7), QtCore.QPointF(4.5, 10.5), QtCore.QPointF(11, 3.5)]))
        painter.end()
        self._check = check
        for code, tick in self.ticks.items():
            tick.setPixmap(check if code == self._current else QtGui.QPixmap())

    def set_language(self, current):
        """Apply a choice immediately and keep the current filter and focus."""
        texts = PICKER_TEXT.get(current, PICKER_TEXT['en'])
        self._current = current
        self.title.setText(texts[0])
        self.setAccessibleName(texts[0])
        search, empty = SEARCH_TEXT.get(current, SEARCH_TEXT['en'])
        self.search.setPlaceholderText(search)
        self.search.setAccessibleName(search)
        self.empty.setText(empty)
        self.close_button.setToolTip(tooltip_text(texts[3]))
        self.close_button.setAccessibleName(texts[3])
        for code, button in self.buttons.items():
            selected = code == current
            button.setChecked(selected)
            if bool(button.property('current')) != selected:
                button.setProperty('current', selected)
                self.ticks[code].setPixmap(self._check if selected else QtGui.QPixmap())
                button.style().unpolish(button)
                button.style().polish(button)
                button.update()
