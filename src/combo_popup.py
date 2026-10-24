"""Shared, measured list rows for selectors and capture-language popups."""
import html
from functools import lru_cache

from PyQt5 import QtCore, QtGui, QtWidgets


GROUP_HEADER_ROLE = QtCore.Qt.UserRole + 100


@lru_cache(maxsize=128)
def _language_flag(code):
    from languages import language_icon_path
    from project_paths import resource_root
    path = language_icon_path(code)
    return QtGui.QIcon(str(resource_root()/path)) if path else QtGui.QIcon()


def popup_scale(combo):
    explicit = getattr(combo, 'ui_factor', None)
    if isinstance(explicit, (int, float)):
        return max(.5, min(3., explicit))
    pixels = combo.font().pixelSize()
    return max(.75, min(3., pixels/14 if pixels > 0 else combo.fontMetrics().height()/18))


def popup_palette(dark, surface=None):
    return dict(surface=surface or ('#211d29' if dark else '#faf7fd'),
                text='#f5f0fc' if dark else '#302638',
                muted='#b1a7bc' if dark else '#776c82',
                border='#584963' if dark else '#c8b9d7',
                hover='#302739' if dark else '#f0e9f7',
                selected='#3e3050' if dark else '#e9ddf4',
                accent='#c3a5eb' if dark else '#765099')


class PopupRowDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, combo, *, mark_current=True):
        super().__init__(combo)
        self.combo = combo
        self.mark_current = mark_current

    def label(self, index):
        return str(index.data(QtCore.Qt.DisplayRole) or '')

    def icon(self, index):
        decoration = index.data(QtCore.Qt.DecorationRole)
        if isinstance(decoration, QtGui.QIcon) and not decoration.isNull():
            return decoration
        from languages import get_language
        code = index.data(QtCore.Qt.UserRole)
        if isinstance(code, str) and get_language(code) is not None:
            return _language_flag(code)
        # Older language fields contain names rather than ISO item data.
        # Search already verifies those catalogs; template/provider names do
        # not get interpreted as languages here.
        if code is None and getattr(self.combo, '_language_search', None) is not None:
            from language_search import language_code_for_option_text
            return _language_flag(language_code_for_option_text(self.label(index)))
        return QtGui.QIcon()

    def _font(self, index):
        font = QtGui.QFont(self.combo.font())
        font.setWeight(QtGui.QFont.Normal)
        if index.data(GROUP_HEADER_ROLE):
            font.setWeight(QtGui.QFont.DemiBold)
            font.setPixelSize(max(11, round(13*popup_scale(self.combo))))
        return font

    def sizeHint(self, option, index):
        scale = popup_scale(self.combo)
        header = bool(index.data(GROUP_HEADER_ROLE))
        font = self._font(index)
        # The selected label is slightly heavier; reserve its full width too.
        font.setWeight(QtGui.QFont.DemiBold)
        metrics = QtGui.QFontMetrics(font)
        icon = self.icon(index)
        gutter = not header and (not icon.isNull() or getattr(self.combo, '_language_search', None) is not None)
        decoration = 28*scale if gutter else 0
        width = metrics.horizontalAdvance(self.label(index)) + round((24 if header else 48)*scale+decoration)
        height = max(round((28 if header else 34)*scale), metrics.height()+round(10*scale))
        specified = index.data(QtCore.Qt.SizeHintRole)
        if isinstance(specified, QtCore.QSize):
            width, height = max(width, specified.width()), max(height, specified.height())
        return QtCore.QSize(width, height)

    def paint(self, painter, option, index):
        scale, colors = popup_scale(self.combo), self.combo.popup_colors()
        header = bool(index.data(GROUP_HEADER_ROLE))
        enabled = bool(index.flags() & QtCore.Qt.ItemIsEnabled)
        chosen = self.mark_current and enabled and index.row() == self.combo.currentIndex()
        hover = enabled and bool(option.state & (QtWidgets.QStyle.State_MouseOver | QtWidgets.QStyle.State_Selected))
        rect = QtCore.QRectF(option.rect).adjusted(scale, scale, -scale, -scale)
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        if chosen or hover:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(colors['selected'] if chosen else colors['hover']))
            painter.drawRoundedRect(rect, 5*scale, 5*scale)
        font = self._font(index)
        if chosen:
            font.setWeight(QtGui.QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(colors['muted'] if header or not enabled else colors['text']))
        content = rect.adjusted(10*scale, 0, -10*scale, 0)
        rtl = self.combo.layoutDirection() == QtCore.Qt.RightToLeft
        icon = self.icon(index)
        if isinstance(icon, QtGui.QIcon) and not icon.isNull() and not header:
            size = round(20*scale)
            x = content.right()-size if rtl else content.left()
            pixels = icon.pixmap(QtCore.QSize(size*3, size*3),
                                 QtGui.QIcon.Normal if enabled else QtGui.QIcon.Disabled)
            if not pixels.isNull():
                fitted = QtCore.QSizeF(pixels.size()).scaled(QtCore.QSizeF(size, size), QtCore.Qt.KeepAspectRatio)
                target = QtCore.QRectF(x+(size-fitted.width())/2,
                    content.center().y()-fitted.height()/2, fitted.width(), fitted.height())
                painter.drawPixmap(target, pixels, QtCore.QRectF(pixels.rect()))
        if not header and (not icon.isNull() or getattr(self.combo, '_language_search', None) is not None):
            content.adjust(0 if rtl else 28*scale, 0, -28*scale if rtl else 0, 0)
        if not header:
            content.adjust(24*scale if rtl else 0, 0, 0 if rtl else -24*scale, 0)
        label = QtGui.QFontMetrics(font).elidedText(self.label(index), QtCore.Qt.ElideRight, max(0, round(content.width())))
        painter.drawText(content, QtCore.Qt.AlignVCenter | (QtCore.Qt.AlignRight if rtl else QtCore.Qt.AlignLeft), label)
        if chosen:
            x = rect.left()+14*scale if rtl else rect.right()-14*scale
            y = rect.center().y()
            painter.setPen(QtGui.QPen(QtGui.QColor(colors['accent']), 1.6*scale,
                                     QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            path = QtGui.QPainterPath(QtCore.QPointF(x-4*scale, y))
            path.lineTo(x-scale, y+3*scale)
            path.lineTo(x+5*scale, y-4*scale)
            painter.drawPath(path)
        painter.restore()

    def helpEvent(self, event, view, option, index):
        if index.isValid() and not index.data(QtCore.Qt.ToolTipRole):
            label = self.label(index)
            if self.sizeHint(option, index).width() > option.rect.width():
                QtWidgets.QToolTip.showText(event.globalPos(), '<span>'+html.escape(label)+'</span>', view)
                return True
        return super().helpEvent(event, view, option, index)
