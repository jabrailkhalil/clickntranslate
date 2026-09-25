"""Compact language controls shared by OCR capture on every desktop platform."""

from PyQt5 import QtCore, QtGui, QtWidgets

from languages import language_display_name, language_short_label
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
        s = self.combo.ui_factor
        return QtCore.QSize(max(round(196*s), metrics.horizontalAdvance(self.label(index)) + round(70*s)), round(34*s))

    def paint(self, painter, option, index):
        s = self.combo.ui_factor
        palette = self.combo.colors
        chosen = index.row() == self.combo.currentIndex()
        hover = bool(option.state & (QtWidgets.QStyle.State_MouseOver | QtWidgets.QStyle.State_Selected))
        enabled = bool(index.flags() & QtCore.Qt.ItemIsEnabled)
        rect = QtCore.QRectF(option.rect).adjusted(3, 2, -3, -2)
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        if chosen or hover:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(palette['selected'] if chosen else palette['hover']))
            painter.drawRoundedRect(rect, 6, 6)
        icon = index.data(QtCore.Qt.DecorationRole)
        if isinstance(icon, QtGui.QIcon):
            icon.paint(painter, QtCore.QRect(round(rect.left() + 9*s), round(rect.center().y() - 10*s), round(20*s), round(20*s)))
        font = self.combo.font()
        font.setWeight(QtGui.QFont.DemiBold if chosen else QtGui.QFont.Normal)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(palette['text'] if enabled else palette['muted']))
        label_rect = rect.adjusted(38*s, 0, -26*s, 0)
        label = QtGui.QFontMetrics(font).elidedText(self.label(index), QtCore.Qt.ElideRight, int(label_rect.width()))
        painter.drawText(label_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, label)
        if chosen and enabled:
            pen = QtGui.QPen(QtGui.QColor(palette['accent']), 1.8, QtCore.Qt.SolidLine,
                            QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
            painter.setPen(pen)
            x, y = rect.right() - 14, rect.center().y()
            path = QtGui.QPainterPath(QtCore.QPointF(x - 4, y))
            path.lineTo(x - 1, y + 3)
            path.lineTo(x + 5, y - 4)
            painter.drawPath(path)
        painter.restore()


class CaptureLanguageCombo(DropDownCombo):
    POPUP_GAP = 5

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

    def initStyleOption(self, option):
        super().initStyleOption(option)
        # The collapsed field always paints the compact code, independently of
        # the full-name popup delegate, even during selection/close events.
        code = self.currentData()
        if code:
            option.currentText = language_short_label(code)

    def showPopup(self):
        # Native Qt combo animation first snapshots a list aligned over the
        # selected field. Our full-name delegate then appears over "RU" before
        # the popup is moved below it. Disable that snapshot only for this
        # synchronous opening and restore the application's setting afterwards.
        effect = QtCore.Qt.UI_AnimateCombo
        animated = QtWidgets.QApplication.isEffectEnabled(effect)
        try:
            QtWidgets.QApplication.setEffectEnabled(effect, False)
            super().showPopup()
        finally:
            QtWidgets.QApplication.setEffectEnabled(effect, animated)

    def set_capture_theme(self, dark, language='en', factor=1.0):
        self.ui_factor = factor
        self.interface_language = language
        self.colors = (dict(surface='#211d29', text='#f5f0fc', muted='#a49bad', border='#544760',
                            hover='#2e2638', selected='#3e3050', accent='#c3a5eb') if dark else
                       dict(surface='#faf7fd', text='#302638', muted='#8b8095', border='#c8b9d7',
                            hover='#f0e9f7', selected='#e9ddf4', accent='#765099'))
        c = self.colors
        font = QtWidgets.QApplication.font()
        font.setPixelSize(max(12, round(14 * factor)))
        self.setFont(font)
        self.setIconSize(QtCore.QSize(20, 20) * factor)
        self.setFixedSize(QtCore.QSize(108, 36) * factor)
        palette = self.palette()
        for role in (QtGui.QPalette.Text, QtGui.QPalette.WindowText, QtGui.QPalette.ButtonText):
            palette.setColor(role, QtGui.QColor(c['text']))
        self.setPalette(palette)
        from window_appearance import scaled_stylesheet
        self.setStyleSheet(scaled_stylesheet(f"""
            QComboBox {{ background:{c['surface']}; color:{c['text']}; border:1px solid {c['border']};
                border-radius:8px; padding:3px 20px 3px 8px; font-size:14px; font-weight:600; }}
            QComboBox:hover, QComboBox:on {{ border-color:{c['accent']}; background:{c['hover']}; }}
            QComboBox:disabled {{ color:{c['muted']}; }}
            QComboBox::drop-down {{ width:18px; border:0; background:transparent; }}
            QComboBox::down-arrow {{ image:none; }}
        """, factor))
        self._paint_popup_frame()

    def paintEvent(self, event):
        # Keep flag, label and chevron aligned across native styles and DPI.
        s, c = self.ui_factor, self.colors
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        active = self.underMouse() or self.view().isVisible()
        painter.setPen(QtGui.QPen(QtGui.QColor(c['accent'] if active else c['border']), 1))
        painter.setBrush(QtGui.QColor(c['hover'] if active else c['surface']))
        painter.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 6*s, 6*s)
        if not self.isEnabled():
            painter.setOpacity(.5)
        self.itemIcon(self.currentIndex()).paint(painter, QtCore.QRect(
            round(10*s), round((self.height()-20*s)/2), round(20*s), round(20*s)))
        font = self.font()
        font.setWeight(QtGui.QFont.Medium)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(c['text']))
        label = language_short_label(self.currentData()) if self.currentData() else self.currentText()
        label_rect = QtCore.QRectF(38*s, 0, self.width()-62*s, self.height())
        painter.drawText(label_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, label)
        painter.setPen(QtGui.QPen(QtGui.QColor(c['muted']), 1.5*s,
                                QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        x, y = self.width()-15*s, self.height()/2
        path = QtGui.QPainterPath(QtCore.QPointF(x-3*s, y-1.5*s))
        path.lineTo(x, y+1.5*s)
        path.lineTo(x+3*s, y-1.5*s)
        painter.drawPath(path)

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
                border-radius:8px; padding:4px; }}
        """)
        set_widget_stylesheet(view, f"""
            QAbstractItemView {{ background:transparent; color:{c['text']}; border:0; outline:none; }}
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
            painter.drawRoundedRect(QtCore.QRectF(watched.rect()).adjusted(.5, .5, -.5, -.5), 8, 8)
            return True
        return super().eventFilter(watched, event)
