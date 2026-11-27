"""Two clear navigation levels for the existing package dialog."""
from PyQt5 import QtCore, QtGui, QtWidgets
from classic_style import classic_palette


class PackageTabBar(QtWidgets.QTabBar):
    def __init__(self, parent=None, *, primary=False):
        super().__init__(parent)
        self.primary = primary
        self.dark = True
        self.setDrawBase(False)
        self.setExpanding(True)
        self.setUsesScrollButtons(False)
        self.setElideMode(QtCore.Qt.ElideRight)
        self.setMouseTracking(True)
        self._hovered = -1

    def apply_theme(self, dark):
        self.dark = dark
        font = QtGui.QFont('Segoe UI')
        font.setPixelSize(13)
        self.setFont(font)
        self.updateGeometry()
        self.update()

    def tabSizeHint(self, index):
        metrics = self.fontMetrics()
        # Equal sections on the first row, compact engine labels beneath it.
        texts = [metrics.horizontalAdvance(self.tabText(i)) for i in range(self.count())]
        width = max(texts, default=80) + 32 if self.primary else metrics.horizontalAdvance(self.tabText(index)) + 28
        return QtCore.QSize(width, max(34, metrics.height() + 16))

    def paintEvent(self, event):
        c = classic_palette(self.dark)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        if self.primary:
            painter.setPen(QtGui.QPen(QtGui.QColor(c['border']), 1))
            painter.setBrush(QtGui.QColor(c['field']))
            painter.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 6, 6)
        else:
            painter.setPen(QtGui.QPen(QtGui.QColor(c['border']), 1))
            painter.drawLine(0, self.height()-1, self.width(), self.height()-1)
        for index in range(self.count()):
            rect = QtCore.QRectF(self.tabRect(index))
            chosen = index == self.currentIndex()
            if self.primary and (chosen or index == self._hovered):
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(QtGui.QColor(c['selected'] if chosen else c['hover']))
                painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 4, 4)
            elif chosen:
                painter.setPen(QtGui.QPen(QtGui.QColor(c['accent_text']), 2))
                painter.drawLine(QtCore.QPointF(rect.left()+10, rect.bottom()-1), QtCore.QPointF(rect.right()-10, rect.bottom()-1))
            painter.setFont(self.font())
            painter.setPen(QtGui.QColor(c['text'] if chosen or index == self._hovered else c['muted']))
            label = self.fontMetrics().elidedText(self.tabText(index), QtCore.Qt.ElideRight, max(0, int(rect.width())-16))
            painter.drawText(rect, QtCore.Qt.AlignCenter, label)

    def mouseMoveEvent(self, event):
        self._hovered = self.tabAt(event.pos())
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered = -1
        self.update()
        super().leaveEvent(event)
