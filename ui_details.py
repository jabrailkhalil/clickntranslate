"""Small native widgets for the welcome screen; no animation or network work."""
from PyQt5 import QtCore, QtGui, QtWidgets, QtSvg

# Monochrome brand silhouettes, matching the links on the application's site.
_SOCIAL_PATHS = {
    'telegram': 'M21.44 3.62 18.15 20.1c-.25 1.16-.9 1.45-1.82.9l-5-3.69-2.41 2.32c-.27.27-.5.5-1.02.5l.36-5.1 9.28-8.39c.4-.36-.09-.56-.62-.2L5.45 13.67.55 12.14c-1.07-.33-1.09-1.07.22-1.58L19.94 3.17c.89-.33 1.67.2 1.5.45Z',
    'github': 'M12 .3a12 12 0 0 0-3.793 23.385c.6.111.82-.261.82-.577v-2.234c-3.338.726-4.043-1.416-4.043-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.09-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.835 2.807 1.305 3.492.998.108-.776.418-1.305.762-1.605-2.665-.305-5.467-1.334-5.467-5.931 0-1.31.469-2.381 1.236-3.221-.124-.303-.536-1.524.117-3.176 0 0 1.008-.322 3.301 1.23a11.51 11.51 0 0 1 6.006 0c2.291-1.552 3.297-1.23 3.297-1.23.653 1.652.242 2.873.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.216.694.825.576A12.001 12.001 0 0 0 12 .3Z',
}


class _SocialIcon(QtGui.QIconEngine):
    def __init__(self, kind, dark=True):
        super().__init__()
        self.kind = kind
        self.dark = dark
        self.renderers = {}
        for use_dark, color in ((True, '#c4bdce'), (False, '#655276')):
            self.renderers[use_dark] = QtSvg.QSvgRenderer(
                ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
                 '<path fill="' + color + '" d="' + _SOCIAL_PATHS[kind] + '"/></svg>').encode())

    def clone(self):
        return _SocialIcon(self.kind, self.dark)

    def paint(self, painter, rect, mode, state):
        painter.save()
        if mode == QtGui.QIcon.Disabled:
            painter.setOpacity(.4)
        side = min(rect.width(), rect.height())
        inset = max(1.0, side * 0.08) if self.kind == 'github' else 0.0
        target = QtCore.QRectF(rect.center().x() - side / 2 + inset / 2,
                              rect.center().y() - side / 2 + inset / 2,
                              max(1.0, side - inset), max(1.0, side - inset))
        dark = self.dark
        if dark is None:
            app = QtWidgets.QApplication.instance()
            dark = app is None or app.property('ui_theme') != 'Светлая'
        self.renderers[bool(dark)].render(painter, target)
        painter.restore()

    def pixmap(self, size, mode, state):
        image = QtGui.QPixmap(size)
        image.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(image)
        self.paint(painter, image.rect(), mode, state)
        painter.end()
        return image


def social_icon(kind, dark=True):
    return QtGui.QIcon(_SocialIcon(kind, dark))


class WelcomeCheckBox(QtWidgets.QCheckBox):
    """Keep native checkbox behaviour, but paint an unmistakable check mark.

    Styling an indicator's background removes the native tick on some Qt
    platform styles. Use Qt's actual (scaled, RTL-aware) indicator rectangle.
    The entire row is clickable, not only the small text bounding rectangle.
    """
    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isChecked():
            return
        option = QtWidgets.QStyleOptionButton()
        self.initStyleOption(option)
        rect = self.style().subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, option, self)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        # The shared theme converter can recolour QSS indicator backgrounds.
        # Paint fill and mark together so their contrast cannot diverge.
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor('#7a5fa1'))
        painter.drawRoundedRect(QtCore.QRectF(rect).adjusted(.5, .5, -.5, -.5), 4, 4)
        painter.setPen(QtGui.QPen(QtGui.QColor('#ffffff'), max(1.8, rect.width() / 8),
                                 QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        path = QtGui.QPainterPath()
        path.moveTo(rect.x() + rect.width() * .23, rect.y() + rect.height() * .51)
        path.lineTo(rect.x() + rect.width() * .43, rect.y() + rect.height() * .71)
        path.lineTo(rect.x() + rect.width() * .78, rect.y() + rect.height() * .29)
        painter.drawPath(path)
