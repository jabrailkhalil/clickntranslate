"""Paged language selection in the home panel, using the shared UI chrome."""
import math

from PyQt5 import QtCore, QtGui, QtWidgets

from button_styles import button_palette, button_qss
from number_controls import ChoiceStepper
from styled_dialogs import tooltip_text


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


class InterfaceLanguagePicker(QtWidgets.QFrame):
    languageSelected = QtCore.pyqtSignal(str)
    dismissed = QtCore.pyqtSignal()
    PAGE_SIZE = 10

    def __init__(self, options, current, resource_path, parent=None, *, dark=True):
        super().__init__(parent)
        self.setObjectName('interfaceLanguagePicker')
        self.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.buttons, self.name_labels, self.ticks = {}, {}, []
        texts = PICKER_TEXT.get(current, PICKER_TEXT['en'])
        body = QtWidgets.QVBoxLayout(self)
        body.setContentsMargins(1, 1, 1, 1)
        body.setSpacing(0)
        header = QtWidgets.QWidget(self)
        header.setFixedHeight(26)
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(4)
        count = max(1, math.ceil(len(options) / self.PAGE_SIZE))
        spacer = QtWidgets.QWidget(header)
        spacer.setFixedWidth(120 if count > 1 else 22)
        row.addWidget(spacer)
        self.title = QtWidgets.QLabel(texts[0], header)
        self.title.setObjectName('interfaceLanguageTitle')
        self.title.setAlignment(QtCore.Qt.AlignCenter)
        self.title.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        row.addWidget(self.title, 1)
        self.pager = ChoiceStepper([(str(i), f'{i+1} / {count}') for i in range(count)],
                                   header, dark=dark, font_size=12)
        page_width = self.pager.editor.fontMetrics().horizontalAdvance(f'{count} / {count}')
        self.pager.setFixedSize(max(94, page_width+64), 22)
        spacer.setFixedWidth(self.pager.width()+26 if count > 1 else 22)
        self.pager.setVisible(count > 1)
        self.pager.setAccessibleName(texts[0])
        self.pager.editor.setAccessibleName(texts[0])
        self.pager.editor.setToolTip(tooltip_text(texts[0]))
        for button, label in ((self.pager.decrease, texts[1]), (self.pager.increase, texts[2])):
            button.setToolTip(tooltip_text(label))
            button.setAccessibleName(label)
        row.addWidget(self.pager)
        self.close_button = QtWidgets.QToolButton(header)
        self.close_button.setText('×')
        self.close_button.setFixedSize(22, 22)
        self.close_button.setFocusPolicy(QtCore.Qt.TabFocus)
        self.close_button.setToolTip(tooltip_text(texts[3]))
        self.close_button.setAccessibleName(texts[3])
        self.close_button.clicked.connect(self.dismissed)
        row.addWidget(self.close_button)
        body.addWidget(header)
        self.choices = _RoundedChoices(self)
        self.choices.setObjectName('interfaceLanguageChoices')
        self.pages = QtWidgets.QStackedLayout(self.choices)
        self.pages.setContentsMargins(0, 0, 0, 0)
        selected_page = 0
        for offset in range(0, len(options), self.PAGE_SIZE):
            page = QtWidgets.QWidget(self.choices)
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
                    cell.setFocusPolicy(QtCore.Qt.TabFocus)
                    cell.setCursor(QtCore.Qt.PointingHandCursor)
                    cell.setAccessibleName(name)
                    cell.setToolTip(tooltip_text(name))
                    cell.clicked.connect(lambda _checked=False, code=code: self.languageSelected.emit(code))
                    content = QtWidgets.QHBoxLayout(cell)
                    content.setContentsMargins(9, 0, 7, 0)
                    content.setSpacing(6)
                    flag = QtWidgets.QLabel(cell)
                    flag.setFixedSize(18, 18)
                    flag.setAlignment(QtCore.Qt.AlignCenter)
                    flag.setPixmap(QtGui.QPixmap(resource_path(option['icon'])).scaled(
                        flag.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
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
                        self.ticks.append(tick)
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
        self.pager.valueChanged.connect(lambda value: self.pages.setCurrentIndex(int(value)))
        self.pager.setValue(str(selected_page))
        body.addWidget(self.choices, 1)
        self.set_theme(dark)
        escape = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape), self)
        escape.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        escape.activated.connect(self.dismissed)

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
        self.pager.set_theme(dark)
        check = QtGui.QPixmap(24, 28)
        check.setDevicePixelRatio(2)
        check.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(check)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(colors['focus']), 1.6, QtCore.Qt.SolidLine,
                                  QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(1, 7), QtCore.QPointF(4.5, 10.5), QtCore.QPointF(11, 3.5)]))
        painter.end()
        for tick in self.ticks:
            tick.setPixmap(check)
