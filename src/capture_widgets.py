"""Compact language controls shared by OCR capture on every desktop platform."""

from PyQt5 import QtCore, QtGui, QtWidgets

from button_styles import paint_down_arrow
from languages import language_display_name, language_short_label
from settings_window import DropDownCombo
from styled_dialogs import install_tooltip_style
from combo_popup import PopupRowDelegate, popup_palette


class _LanguageRow(PopupRowDelegate):
    def label(self, index):
        code = index.data(QtCore.Qt.UserRole)
        return (language_display_name(code, self.combo.interface_language)
                if code else str(index.data(QtCore.Qt.DisplayRole) or ''))

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        hint.setWidth(max(round(224*self.combo.ui_factor), hint.width()))
        return hint


class CaptureLanguageCombo(DropDownCombo):
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
        self.colors = popup_palette(dark)
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
                border-radius:7px; padding:3px 20px 3px 8px; font-size:14px; font-weight:400; }}
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
        font.setWeight(QtGui.QFont.Normal)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(c['text']))
        label = language_short_label(self.currentData()) if self.currentData() else self.currentText()
        label_rect = QtCore.QRectF(38*s, 0, self.width()-62*s, self.height())
        painter.drawText(label_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, label)
        paint_down_arrow(painter, QtCore.QRectF(self.width()-24*s, 0, 18*s, self.height()),
                         self.font(), QtGui.QColor(c['text']), s)

    def _paint_popup_frame(self):
        if getattr(self, 'colors', None):
            super()._paint_popup_frame()

    def popup_colors(self):
        return self.colors if getattr(self, 'colors', None) else super().popup_colors()
