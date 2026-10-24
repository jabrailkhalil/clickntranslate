"""Paged language selection in the home panel, using the shared UI chrome."""
from PyQt5 import QtCore, QtGui, QtWidgets

from button_styles import button_palette, button_qss
from styled_dialogs import tooltip_text
from ui_scaling import ScaleArrowButton


PICKER_TEXT = {
    'en': ('Interface language', 'Previous language page', 'Next language page', 'Close language selection'),
    'ru': ('Язык интерфейса', 'Предыдущая страница языков', 'Следующая страница языков', 'Закрыть выбор языка'),
    'es': ('Idioma de la interfaz', 'Página anterior de idiomas', 'Página siguiente de idiomas', 'Cerrar la selección de idioma'),
    'de': ('Oberflächensprache', 'Vorherige Sprachseite', 'Nächste Sprachseite', 'Sprachauswahl schließen'),
    'fr': ('Langue de l’interface', 'Page de langues précédente', 'Page de langues suivante', 'Fermer le choix de langue'),
    'zh': ('界面语言', '上一页语言', '下一页语言', '关闭语言选择'),
    'pt': ('Idioma da interface', 'Página anterior de idiomas', 'Próxima página de idiomas', 'Fechar a seleção de idioma'),
    'it': ('Lingua dell’interfaccia', 'Pagina precedente delle lingue', 'Pagina successiva delle lingue', 'Chiudi la selezione della lingua'),
    'ar': ('لغة الواجهة', 'صفحة اللغات السابقة', 'صفحة اللغات التالية', 'إغلاق اختيار اللغة'),

    'tr': ('Arayüz dili', 'Önceki dil sayfası', 'Sonraki dil sayfası', 'Dil seçimini kapat'),
    'hi': ('इंटरफ़ेस की भाषा', 'भाषाओं का पिछला पेज', 'भाषाओं का अगला पेज', 'भाषा चयन बंद करें'),
    'id': ('Bahasa antarmuka',
     'Halaman bahasa sebelumnya',
     'Halaman bahasa berikutnya',
     'Tutup pemilihan bahasa'),
}


class _RoundedChoices(QtWidgets.QFrame):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Rectangular cell backgrounds must not cover the frame's lower corners.
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


class LanguagePickerConnection(QtWidgets.QWidget):
    """One outline joins the pressed flag to its panel without blocking input."""
    def __init__(self, parent, *, dark=True):
        super().__init__(parent)
        self.setObjectName('interfaceLanguageConnection')
        self.setProperty('_cntTransientChrome', True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self._outline = QtGui.QPainterPath()
        self._tab = QtGui.QPainterPath()
        self.set_theme(dark)

    def set_theme(self, dark):
        self._surface = QtGui.QColor('#1d1922' if dark else '#ffffff')
        self._edge = QtGui.QColor('#62566e' if dark else '#927cab')
        self.update()

    def set_areas(self, flag, panel):
        bounds = flag.united(panel).adjusted(-1, -1, 1, 1)
        self.setGeometry(bounds)
        flag = QtCore.QRectF(flag.translated(-bounds.topLeft())).adjusted(.5, .5, -.5, -.5)
        panel = QtCore.QRectF(panel.translated(-bounds.topLeft())).adjusted(.5, .5, -.5, -.5)
        body = QtGui.QPainterPath()
        body.addRoundedRect(panel, 10, 10)
        tab = QtGui.QPainterPath()
        tab.addRoundedRect(flag, 6, 6)
        # Join along the panel's left edge; the adjacent theme button is clear.
        left = max(panel.left(), flag.left())
        right = min(panel.right(), flag.right())
        if right > left and panel.top() >= flag.center().y():
            stem = QtGui.QPainterPath()
            stem.addRect(QtCore.QRectF(left, flag.center().y(), right-left,
                                      panel.top()+10-flag.center().y()))
            tab = tab.united(stem)
        self._tab = tab
        self._outline = body.united(tab)
        self.update()

    def contains_global(self, point):
        from ui_scaling import widget_global_rect
        rect = widget_global_rect(self)
        if rect.isEmpty():
            return False
        local = QtCore.QPointF((point.x()-rect.left())*self.width()/rect.width(),
                              (point.y()-rect.top())*self.height()/rect.height())
        return self._outline.contains(local)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        # The body already paints its surface and children. Fill only the tab
        # and seam, then draw the shared boundary above all cell backgrounds.
        painter.fillPath(self._tab, self._surface)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(self._edge, 1, QtCore.Qt.SolidLine,
                                  QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPath(self._outline)


class InterfaceLanguagePicker(QtWidgets.QFrame):
    languageSelected = QtCore.pyqtSignal(str)
    dismissed = QtCore.pyqtSignal()
    PAGE_SIZE = 10
    COLUMNS = 5
    PANEL_HEIGHT = 146

    def __init__(self, options, current, resource_path, parent=None, *, dark=True):
        super().__init__(parent)
        self.setObjectName('interfaceLanguagePicker')
        self.setProperty('keyboardOwnNavigation', True)
        self.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.buttons, self.name_labels, self.ticks = {}, {}, {}
        self._codes = tuple(option['code'] for option in options)
        self._current = current
        self.keyboard_mode = False
        self._button_indexes = {}
        self.setMinimumHeight(90)
        self.resize(670, self.PANEL_HEIGHT)
        texts = PICKER_TEXT.get(current, PICKER_TEXT['en'])
        body = QtWidgets.QVBoxLayout(self)
        body.setContentsMargins(2, 2, 2, 2)
        body.setSpacing(0)
        header = QtWidgets.QWidget(self)
        header.setFixedHeight(26)
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(4)
        spacer = QtWidgets.QWidget(header)
        spacer.setFixedWidth(22)
        row.addWidget(spacer)
        self.title = QtWidgets.QLabel(texts[0], header)
        self.title.setObjectName('interfaceLanguageTitle')
        self.title.setAlignment(QtCore.Qt.AlignCenter)
        self.title.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        row.addWidget(self.title, 1)
        self.close_button = QtWidgets.QToolButton(header)
        self.close_button.setText('×')
        self.close_button.setFixedSize(22, 22)
        self.close_button.setFocusPolicy(QtCore.Qt.TabFocus)
        self.close_button.setToolTip(tooltip_text(texts[3]))
        self.close_button.setAccessibleName(texts[3])
        self.close_button.clicked.connect(self.dismissed)
        self.close_button.installEventFilter(self)
        row.addWidget(self.close_button)
        body.addWidget(header)
        self.choices = _RoundedChoices(self)
        self.choices.setObjectName('interfaceLanguageChoices')
        choices_layout = QtWidgets.QHBoxLayout(self.choices)
        choices_layout.setContentsMargins(2, 0, 2, 0)
        choices_layout.setSpacing(0)
        self.previous_button = ScaleArrowButton(self.choices)
        self.next_button = ScaleArrowButton(self.choices)
        for button, glyph, label in ((self.previous_button, '‹', texts[1]),
                                     (self.next_button, '›', texts[2])):
            button.setText(glyph)
            button.setFixedSize(24, 32)
            button.setFocusPolicy(QtCore.Qt.TabFocus)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setToolTip(tooltip_text(label))
            button.setAccessibleName(label)
            button.installEventFilter(self)
        choices_layout.addWidget(self.previous_button, 0, QtCore.Qt.AlignVCenter)
        pages_host = QtWidgets.QWidget(self.choices)
        choices_layout.addWidget(pages_host, 1)
        choices_layout.addWidget(self.next_button, 0, QtCore.Qt.AlignVCenter)
        self.pages = QtWidgets.QStackedLayout(pages_host)
        self.pages.setContentsMargins(0, 0, 0, 0)
        selected_page = 0
        for offset in range(0, len(options), self.PAGE_SIZE):
            page = QtWidgets.QWidget(pages_host)
            grid = QtWidgets.QGridLayout(page)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(0)
            for col in range(5):
                grid.setColumnStretch(col, 1)
            for line in range(2):
                grid.setRowStretch(line, 1)
            for index in range(self.PAGE_SIZE):
                if offset+index >= len(options):
                    cell = QtWidgets.QFrame(page)
                else:
                    option = options[offset+index]
                    code, name = option['code'], option['name']
                    cell = QtWidgets.QPushButton(page)
                    cell.setFocusPolicy(QtCore.Qt.StrongFocus)
                    cell.setCursor(QtCore.Qt.PointingHandCursor)
                    cell.setAccessibleName(name)
                    cell.setToolTip(tooltip_text(name))
                    cell.clicked.connect(lambda _checked=False, code=code: self.languageSelected.emit(code))
                    cell.installEventFilter(self)
                    self._button_indexes[cell] = offset+index
                    content = QtWidgets.QHBoxLayout(cell)
                    content.setContentsMargins(7, 0, 5, 0)
                    content.setSpacing(5)
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
                    label.setLayoutDirection(QtCore.Qt.RightToLeft if code == 'ar' else QtCore.Qt.LeftToRight)
                    label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter | QtCore.Qt.AlignAbsolute)
                    label.setMinimumWidth(0)
                    label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
                    content.addWidget(label, 1)
                    tick = QtWidgets.QLabel(cell)
                    tick.setFixedWidth(12 if code == current else 0)
                    content.addWidget(tick)
                    cell.setProperty('current', code == current)
                    if code == current:
                        selected_page = offset // self.PAGE_SIZE
                    self.ticks[code] = tick
                    for child in (flag, label, tick):
                        child.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
                    self.buttons[code], self.name_labels[code] = cell, label
                cell.setObjectName('interfaceLanguageCell')
                cell.setProperty('divider', index % 5 != 4)
                cell.setProperty('topRow', index < 5)
                cell.setMinimumSize(0, 30)
                cell.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
                grid.addWidget(cell, index // 5, index % 5)
            self.pages.addWidget(page)
        self.previous_button.clicked.connect(lambda: self.set_page(
            self.pages.currentIndex()-1, focus=True, keyboard=self.keyboard_mode))
        self.next_button.clicked.connect(lambda: self.set_page(
            self.pages.currentIndex()+1, focus=True, keyboard=self.keyboard_mode))
        self.set_page(selected_page)
        body.addWidget(self.choices, 1)
        self.set_theme(dark)
        escape = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape), self)
        escape.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        escape.activated.connect(self.dismissed)

    def _set_keyboard_mode(self, keyboard):
        self.keyboard_mode = bool(keyboard)
        navigation = getattr(QtWidgets.QApplication.instance(), '_keyboard_navigation', None)
        if navigation is not None:
            navigation.keyboard = self.keyboard_mode
            if not self.keyboard_mode:
                navigation._hide_ring()
        if not self.keyboard_mode:
            for control in (*self.buttons.values(), self.previous_button, self.next_button, self.close_button):
                if control.property('keyboardFocus'):
                    control.setProperty('keyboardFocus', False)
                    control.style().unpolish(control)
                    control.style().polish(control)
                    control.update()

    def set_page(self, page, *, focus=False, keyboard=None):
        if keyboard is not None:
            self._set_keyboard_mode(keyboard)
        self.pages.setCurrentIndex(max(0, min(self.pages.count()-1, page)))
        self.previous_button.setEnabled(self.pages.currentIndex() > 0)
        self.next_button.setEnabled(self.pages.currentIndex() < self.pages.count()-1)
        for button in (self.previous_button, self.next_button):
            button.setVisible(self.pages.count() > 1)
        if focus:
            self._focus_index(self.pages.currentIndex()*self.PAGE_SIZE)

    def _focus_index(self, index, reason=None):
        index = max(0, min(len(self._codes)-1, index))
        self.set_page(index//self.PAGE_SIZE)
        if reason is None:
            reason = QtCore.Qt.TabFocusReason if self.keyboard_mode else QtCore.Qt.OtherFocusReason
        self.buttons[self._codes[index]].setFocus(reason)

    def focus_current_language(self, keyboard=None):
        if keyboard is not None:
            self._set_keyboard_mode(keyboard)
        self._focus_index(self._codes.index(self._current))

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonDblClick):
            self._set_keyboard_mode(False)
        if event.type() != QtCore.QEvent.KeyPress:
            return super().eventFilter(watched, event)
        self._set_keyboard_mode(True)
        key = event.key()
        if key in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab):
            first = self.pages.currentIndex()*self.PAGE_SIZE
            controls = [self.buttons[code] for code in self._codes[first:first+self.PAGE_SIZE]]
            controls += [button for button in (self.previous_button, self.next_button, self.close_button)
                         if button.isVisible() and button.isEnabled()]
            backwards = key == QtCore.Qt.Key_Backtab or bool(event.modifiers() & QtCore.Qt.ShiftModifier)
            index = controls.index(watched) if watched in controls else 0
            controls[(index+(-1 if backwards else 1)) % len(controls)].setFocus(
                QtCore.Qt.BacktabFocusReason if backwards else QtCore.Qt.TabFocusReason)
        elif key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Space):
            watched.click()
        elif key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down,
                     QtCore.Qt.Key_PageUp, QtCore.Qt.Key_PageDown, QtCore.Qt.Key_Home, QtCore.Qt.Key_End):
            index = self._button_indexes.get(watched, self.pages.currentIndex()*self.PAGE_SIZE)
            page, slot = divmod(index, self.PAGE_SIZE)
            row, column = divmod(slot, self.COLUMNS)
            target = index
            if key in (QtCore.Qt.Key_PageUp, QtCore.Qt.Key_PageDown):
                page += -1 if key == QtCore.Qt.Key_PageUp else 1
                page = max(0, min(self.pages.count()-1, page))
                target = min(page*self.PAGE_SIZE+slot, len(self._codes)-1)
            elif key == QtCore.Qt.Key_Home:
                target = 0
            elif key == QtCore.Qt.Key_End:
                target = len(self._codes)-1
            elif key in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                candidate = index+(-self.COLUMNS if key == QtCore.Qt.Key_Up else self.COLUMNS)
                if 0 <= candidate < len(self._codes) and candidate//self.PAGE_SIZE == page:
                    target = candidate
            elif key == QtCore.Qt.Key_Right:
                if column < self.COLUMNS-1 and index+1 < min((page+1)*self.PAGE_SIZE, len(self._codes)):
                    target = index+1
                elif page < self.pages.count()-1:
                    target = min((page+1)*self.PAGE_SIZE+row*self.COLUMNS, len(self._codes)-1)
            elif column > 0:
                target = index-1
            elif page > 0:
                target = (page-1)*self.PAGE_SIZE+row*self.COLUMNS+self.COLUMNS-1
            self._focus_index(target)
        else:
            return super().eventFilter(watched, event)
        event.accept()
        return True

    def mousePressEvent(self, event):
        self._set_keyboard_mode(False)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.dismissed.emit()
            event.accept()
            return
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
            QLabel#interfaceLanguageName {{color:{ink}; border:0; font-size:14px; font-weight:400;}}
        ''')
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
        for button in (self.previous_button, self.next_button):
            button.setStyleSheet(button_qss(dark, 'quiet', selector='QToolButton', icon=True, radius=4)
                                + 'QToolButton:disabled {background:transparent; border-color:transparent;}')
        check = QtGui.QPixmap(24, 28)
        check.setDevicePixelRatio(2)
        check.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(check)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(colors['focus']), 1.6, QtCore.Qt.SolidLine,
                                  QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(1, 7), QtCore.QPointF(4.5, 10.5), QtCore.QPointF(11, 3.5)]))
        painter.end()
        for tick in self.ticks.values():
            tick.setPixmap(check)

    def set_language(self, current):
        """Apply a choice immediately and keep the current language page open."""
        texts = PICKER_TEXT.get(current, PICKER_TEXT['en'])
        self._current = current
        self.title.setText(texts[0])
        for button, label in ((self.previous_button, texts[1]), (self.next_button, texts[2]),
                              (self.close_button, texts[3])):
            button.setToolTip(tooltip_text(label))
            button.setAccessibleName(label)
        for code, button in self.buttons.items():
            selected = code == current
            if bool(button.property('current')) != selected:
                button.setProperty('current', selected)
                self.ticks[code].setFixedWidth(12 if selected else 0)
                button.style().unpolish(button)
                button.style().polish(button)
                button.update()
