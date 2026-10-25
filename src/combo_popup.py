"""Shared, measured list rows for selectors and capture-language popups."""
import html
from functools import lru_cache

from PyQt5 import QtCore, QtGui, QtWidgets

from classic_style import classic_palette


GROUP_HEADER_ROLE = QtCore.Qt.UserRole + 100
CHECKED_ROLE = QtCore.Qt.UserRole + 101


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
    colors = classic_palette(dark)
    return dict(surface=surface or colors['field'], text=colors['text'],
                muted=colors['muted'], border=colors['border'],
                hover=colors['hover'], selected=colors['selected'],
                accent=colors['accent_text'])


class PopupRowDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, combo, *, mark_current=True):
        super().__init__(combo)
        self.combo = combo
        self.mark_current = mark_current

    def label(self, index):
        return str(index.data(QtCore.Qt.DisplayRole) or '')

    def marked(self, index):
        """Both single choices and independent switches use the same tick."""
        checked = index.data(CHECKED_ROLE)
        if checked is not None:
            return bool(checked)
        return self.mark_current and index.row() == self.combo.currentIndex()

    def _language_gutter(self):
        search = getattr(self.combo, '_language_search', None)
        return search is not None and not search.isHidden()

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
        if code is None and self._language_gutter():
            from language_search import language_code_for_option_text
            return _language_flag(language_code_for_option_text(self.label(index)))
        return QtGui.QIcon()

    def _font(self, index):
        font = QtGui.QFont(self.combo.font())
        font.setWeight(QtGui.QFont.Normal)
        if index.data(GROUP_HEADER_ROLE):
            font.setPixelSize(max(11, round(13*popup_scale(self.combo))))
        return font

    def sizeHint(self, option, index):
        scale = popup_scale(self.combo)
        header = bool(index.data(GROUP_HEADER_ROLE))
        font = self._font(index)
        metrics = QtGui.QFontMetrics(font)
        icon = self.icon(index)
        gutter = not header and (not icon.isNull() or self._language_gutter())
        decoration = 24*scale if gutter else 0
        width = metrics.horizontalAdvance(self.label(index)) + round((18 if header else 38)*scale+decoration)
        height = max(round((26 if header else 30)*scale), metrics.height()+round(8*scale))
        specified = index.data(QtCore.Qt.SizeHintRole)
        if isinstance(specified, QtCore.QSize):
            width, height = max(width, specified.width()), max(height, specified.height())
        return QtCore.QSize(width, height)

    def paint(self, painter, option, index):
        scale, colors = popup_scale(self.combo), self.combo.popup_colors()
        header = bool(index.data(GROUP_HEADER_ROLE))
        enabled = bool(index.flags() & QtCore.Qt.ItemIsEnabled)
        chosen = enabled and not header and self.marked(index)
        hover = enabled and bool(option.state & (QtWidgets.QStyle.State_MouseOver | QtWidgets.QStyle.State_Selected))
        rect = QtCore.QRectF(option.rect)
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        if chosen or hover:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(colors['selected'] if chosen else colors['hover']))
            painter.drawRect(rect)
        font = self._font(index)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(colors['muted'] if header or not enabled else colors['text']))
        content = rect.adjusted(8*scale, 0, -8*scale, 0)
        rtl = self.combo.layoutDirection() == QtCore.Qt.RightToLeft
        icon = self.icon(index)
        if isinstance(icon, QtGui.QIcon) and not icon.isNull() and not header:
            size = round(18*scale)
            x = content.right()-size if rtl else content.left()
            pixels = icon.pixmap(QtCore.QSize(size*3, size*3),
                                 QtGui.QIcon.Normal if enabled else QtGui.QIcon.Disabled)
            if not pixels.isNull():
                fitted = QtCore.QSizeF(pixels.size()).scaled(QtCore.QSizeF(size, size), QtCore.Qt.KeepAspectRatio)
                target = QtCore.QRectF(x+(size-fitted.width())/2,
                    content.center().y()-fitted.height()/2, fitted.width(), fitted.height())
                painter.drawPixmap(target, pixels, QtCore.QRectF(pixels.rect()))
        if not header and (not icon.isNull() or self._language_gutter()):
            content.adjust(0 if rtl else 24*scale, 0, -24*scale if rtl else 0, 0)
        if not header:
            content.adjust(20*scale if rtl else 0, 0, 0 if rtl else -20*scale, 0)
        label = QtGui.QFontMetrics(font).elidedText(self.label(index), QtCore.Qt.ElideRight, max(0, round(content.width())))
        painter.drawText(content, QtCore.Qt.AlignVCenter | (QtCore.Qt.AlignRight if rtl else QtCore.Qt.AlignLeft), label)
        if chosen:
            x = rect.left()+11*scale if rtl else rect.right()-11*scale
            y = rect.center().y()
            painter.setPen(QtGui.QPen(QtGui.QColor(colors['accent']), 1.35*scale,
                                     QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            path = QtGui.QPainterPath(QtCore.QPointF(x-4*scale, y))
            path.lineTo(x-scale, y+3*scale)
            path.lineTo(x+5*scale, y-4*scale)
            painter.drawPath(path)
        painter.restore()

    def helpEvent(self, event, view, option, index):
        app = QtWidgets.QApplication.instance()
        if app is not None and app.property('buttonTooltipsEnabled') is False:
            QtWidgets.QToolTip.hideText()
            return False
        from styled_dialogs import tooltip_has_text
        if index.isValid() and not tooltip_has_text(index.data(QtCore.Qt.ToolTipRole)):
            label = self.label(index)
            if self.sizeHint(option, index).width() > option.rect.width():
                QtWidgets.QToolTip.showText(event.globalPos(), '<span>'+html.escape(label)+'</span>', view)
                return True
        return super().helpEvent(event, view, option, index)
