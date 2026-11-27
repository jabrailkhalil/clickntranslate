"""Opaque engine-center surfaces: child moves must not leave cached pixels."""
from PyQt5 import QtCore, QtGui, QtWidgets
from classic_style import classic_palette


def engine_actions_icon(dark):
    """Three dots without a missing font glyph or a second menu indicator."""
    image = QtGui.QPixmap(36, 36)
    image.setDevicePixelRatio(2)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(classic_palette(dark)['text']))
    for x in (4, 9, 14):
        painter.drawEllipse(QtCore.QPointF(x, 9), 1.5, 1.5)
    painter.end()
    return QtGui.QIcon(image)


class EngineActivationButton(QtWidgets.QPushButton):
    """Both captions fit without changing width when an engine becomes active."""
    captions = ()

    def sizeHint(self):
        self.ensurePolished()
        option = QtWidgets.QStyleOptionButton()
        self.initStyleOption(option)
        metrics = self.fontMetrics()
        hint = QtCore.QSize()
        # Measuring a difference from QPushButton.sizeHint() mixed two font
        # rounding paths and changed width by 1px at e.g. 81%/103%. Measure
        # every complete caption through the same style instead.
        for caption in (*self.captions, self.text()):
            option.text = caption
            content = metrics.size(QtCore.Qt.TextShowMnemonic, caption)
            hint = hint.expandedTo(self.style().sizeFromContents(
                QtWidgets.QStyle.CT_PushButton, option, content, self))
        return hint.expandedTo(QtWidgets.QApplication.globalStrut())

    def minimumSizeHint(self):
        return self.sizeHint()


class EngineTaskLabel(QtWidgets.QLabel):
    """Keep progress readable in the space left by the fixed footer actions."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)

    def minimumSizeHint(self):
        return QtCore.QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        option = QtWidgets.QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(QtWidgets.QStyle.PE_Widget, option, painter, self)
        painter.setLayoutDirection(self.layoutDirection())
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QtGui.QPalette.WindowText))
        rect = self.contentsRect()
        painter.drawText(rect, QtCore.Qt.AlignLeading | QtCore.Qt.AlignVCenter,
                         self.fontMetrics().elidedText(self.text(), QtCore.Qt.ElideRight, rect.width()))


class EngineCenterSurface(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dark = True
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, False)

    def set_dark(self, dark):
        self.dark = bool(dark)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(classic_palette(self.dark)['background']))
