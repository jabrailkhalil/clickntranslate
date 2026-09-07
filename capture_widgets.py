"""Compact language controls shared by OCR capture on every desktop platform."""

from PyQt5 import QtCore, QtGui, QtWidgets

from languages import language_display_name
from settings_window import DropDownCombo
from styled_dialogs import install_tooltip_style, set_widget_stylesheet


class _LanguageRow(QtWidgets.QStyledItemDelegate):
    def __init__(self, combo):
        super().__init__(combo)
        self.combo = combo

    def label(self, index):
        code = index.data(QtCore.Qt.UserRole)
        return (language_display_name(code, self.combo.interface_language)
                if code else str(index.data(QtCore.Qt.DisplayRole) or ''))

    def sizeHint(self, option, index):
        metrics = QtGui.QFontMetrics(self.combo.font())
        return QtCore.QSize(max(244, metrics.horizontalAdvance(self.label(index)) + 88), 40)

    def paint(self, painter, option, index):
        palette = self.combo.colors
        chosen = index.row() == self.combo.currentIndex()
        hover = bool(option.state & (QtWidgets.QStyle.State_MouseOver | QtWidgets.QStyle.State_Selected))
        enabled = bool(index.flags() & QtCore.Qt.ItemIsEnabled)
        rect = QtCore.QRectF(option.rect).adjusted(4, 2, -4, -2)
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        if chosen or hover:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(palette['selected'] if chosen else palette['hover']))
            painter.drawRoundedRect(rect, 7, 7)
        icon = index.data(QtCore.Qt.DecorationRole)
        if isinstance(icon, QtGui.QIcon):
            icon.paint(painter, QtCore.QRect(int(rect.left()) + 10, int(rect.center().y()) - 11, 22, 22))
        font = self.combo.font()
        font.setWeight(QtGui.QFont.DemiBold if chosen else QtGui.QFont.Normal)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(palette['text'] if enabled else palette['muted']))
        label_rect = rect.adjusted(44, 0, -30, 0)
        label = QtGui.QFontMetrics(font).elidedText(self.label(index), QtCore.Qt.ElideRight, int(label_rect.width()))
        painter.drawText(label_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, label)
        if chosen and enabled:
            pen = QtGui.QPen(QtGui.QColor(palette['accent']), 1.8, QtCore.Qt.SolidLine,
                            QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
            painter.setPen(pen)
            x, y = rect.right() - 17, rect.center().y()
            path = QtGui.QPainterPath(QtCore.QPointF(x - 4, y))
            path.lineTo(x - 1, y + 3)
            path.lineTo(x + 5, y - 4)
            painter.drawPath(path)
        painter.restore()


class CaptureLanguageCombo(DropDownCombo):
    POPUP_GAP = 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self.interface_language = 'en'
        self.colors = {}
        self.setItemDelegate(_LanguageRow(self))
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setMaxVisibleItems(8)
        self.view().setMouseTracking(True)
        self.view().setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        install_tooltip_style()
        self.set_capture_theme(True)

    def set_capture_theme(self, dark, language='en'):
        self.interface_language = language
        self.colors = (dict(surface='#211d29', text='#f5f0fc', muted='#a49bad', border='#544760',
                            hover='#2e2638', selected='#3e3050', accent='#c3a5eb') if dark else
                       dict(surface='#faf7fd', text='#302638', muted='#8b8095', border='#c8b9d7',
                            hover='#f0e9f7', selected='#e9ddf4', accent='#765099'))
        c = self.colors
        font = QtWidgets.QApplication.font()
        font.setPixelSize(14)
        self.setFont(font)
        self.setIconSize(QtCore.QSize(22, 22))
        self.setFixedSize(112, 44)
        palette = self.palette()
        for role in (QtGui.QPalette.Text, QtGui.QPalette.WindowText, QtGui.QPalette.ButtonText):
            palette.setColor(role, QtGui.QColor(c['text']))
        self.setPalette(palette)
        self.setStyleSheet(f"""
            QComboBox {{ background:{c['surface']}; color:{c['text']}; border:1px solid {c['border']};
                border-radius:10px; padding:4px 25px 4px 12px; font-size:14px; font-weight:600; }}
            QComboBox:hover, QComboBox:on {{ border-color:{c['accent']}; background:{c['hover']}; }}
            QComboBox:disabled {{ color:{c['muted']}; }}
            QComboBox::drop-down {{ width:20px; border:0; background:transparent; }}
            QComboBox::down-arrow {{ image:none; }}
        """)
        self._paint_popup_frame()

    def _paint_popup_frame(self):
        if not getattr(self, 'colors', None):
            return
        c = self.colors
        view, popup = self.view(), self.view().window()
        popup.setObjectName('captureLanguagePopup')
        popup.setProperty('clickntranslateRoundedPopup', True)
        popup.setWindowFlag(QtCore.Qt.FramelessWindowHint, True)
        popup.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        popup.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        popup.setAutoFillBackground(False)
        set_widget_stylesheet(popup, f"""
            QFrame#captureLanguagePopup {{ background:{c['surface']}; border:1px solid {c['border']};
                border-radius:10px; padding:6px; }}
        """)
        set_widget_stylesheet(view, f"""
            QAbstractItemView {{ background:transparent; color:{c['text']}; border:0; outline:none; }}
            QScrollBar:vertical {{ background:transparent; width:6px; margin:7px 0; border:0; }}
            QScrollBar::handle:vertical {{ background:{c['border']}; border-radius:3px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{c['accent']}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
        """)
        view.viewport().setAutoFillBackground(False)

    def eventFilter(self, watched, event):
        if (event.type() == QtCore.QEvent.Paint and watched is self.view().window()
                and getattr(self, 'colors', None)):
            # QComboBox's private container omits its stylesheet background
            # when translucent. Paint the card before Qt paints its children.
            painter = QtGui.QPainter(watched)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(QtGui.QPen(QtGui.QColor(self.colors['border']), 1))
            painter.setBrush(QtGui.QColor(self.colors['surface']))
            painter.drawRoundedRect(QtCore.QRectF(watched.rect()).adjusted(.5, .5, -.5, -.5), 10, 10)
            return True
        return super().eventFilter(watched, event)
