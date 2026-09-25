"""Monochrome outline icons, drawn at the title bar's actual display size."""

import math

from PyQt5 import QtCore, QtGui


class _HeaderIcon(QtGui.QIconEngine):
    def __init__(self, kind, dark):
        super().__init__()
        self.kind = kind
        self.dark = dark

    def clone(self):
        return _HeaderIcon(self.kind, self.dark)

    def paint(self, painter, rect, mode, state):
        painter.save()
        try:
            side = min(rect.width(), rect.height())
            painter.translate(rect.x() + (rect.width() - side) / 2,
                              rect.y() + (rect.height() - side) / 2)
            painter.scale(side / 24, side / 24)
            # A tall rectangular page looks larger than a circular badge at
            # the same measured height, so inset it without thinning its lines.
            span = {'help': 18, 'home': 20, 'document': 19, 'settings': 22, 'image_add': 22}[self.kind]
            extent = 22 if self.kind == 'document' else 24
            glyph_scale = (extent - 1.5) / span
            painter.translate(12, 12)
            painter.scale(glyph_scale, glyph_scale)
            painter.translate(-12.25 if self.kind == 'document' else -12, -12)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            color = QtGui.QColor('#ffffff' if self.dark else '#000000')
            if mode == QtGui.QIcon.Disabled:
                color.setAlpha(95)
            # Match the stroke weight of the original settings icon.
            pen = QtGui.QPen(color, 1.5 / glyph_scale)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            pen.setJoinStyle(QtCore.Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            path = QtGui.QPainterPath()
            if self.kind == 'help':
                painter.drawEllipse(QtCore.QRectF(3, 3, 18, 18))
                painter.drawPoint(QtCore.QPointF(12, 7.5))
                path.moveTo(10.5, 11)
                path.lineTo(12, 11)
                path.lineTo(12, 16.5)
                path.moveTo(10.5, 16.5)
                path.lineTo(13.5, 16.5)
            elif self.kind == 'home':
                # The original badge: a compact house inside a circle. Keep
                # its roof, doorway and rounded base, with both shapes unfilled.
                painter.drawEllipse(QtCore.QRectF(2, 2, 20, 20))
                path.moveTo(7.3, 9.5)
                path.lineTo(12, 5.7)
                path.lineTo(17, 9.5)
                path.lineTo(17, 15.8)
                path.quadTo(17, 16.3, 16.5, 16.3)
                path.lineTo(14.2, 16.3)
                path.quadTo(13.7, 16.3, 13.7, 15.8)
                path.lineTo(13.7, 12)
                path.lineTo(10.6, 12)
                path.lineTo(10.6, 15.8)
                path.quadTo(10.6, 16.3, 10.1, 16.3)
                path.lineTo(7.8, 16.3)
                path.quadTo(7.3, 16.3, 7.3, 15.8)
                path.closeSubpath()
            elif self.kind == 'settings':
                # Draw every state and resolution locally: no image/plugin or
                # working-directory dependency on another portable installation.
                for index in range(48):
                    angle = math.tau * index / 48 - math.pi / 2
                    radius = 10.5 if index % 6 in (1, 2, 3, 4) else 8.2
                    point = QtCore.QPointF(12 + math.cos(angle) * radius,
                                          12 + math.sin(angle) * radius)
                    if index == 0:
                        path.moveTo(point)
                    else:
                        path.lineTo(point)
                path.closeSubpath()
                painter.drawEllipse(QtCore.QRectF(7.5, 7.5, 9, 9))
                painter.drawEllipse(QtCore.QRectF(10, 10, 4, 4))
            elif self.kind == 'image_add':
                path.moveTo(13, 20)
                path.lineTo(5, 20)
                path.quadTo(3, 20, 3, 18)
                path.lineTo(3, 5)
                path.quadTo(3, 3, 5, 3)
                path.lineTo(18, 3)
                path.quadTo(20, 3, 20, 5)
                path.lineTo(20, 12)
                painter.drawEllipse(QtCore.QRectF(6, 6, 3, 3))
                path.moveTo(3, 16)
                path.lineTo(8, 11)
                path.lineTo(12, 15)
                path.lineTo(15, 12)
                path.lineTo(17, 14)
                path.moveTo(16, 19)
                path.lineTo(22, 19)
                path.moveTo(19, 16)
                path.lineTo(19, 22)
            else:  # document
                path.moveTo(5.5, 2.5)
                path.lineTo(14, 2.5)
                path.lineTo(19, 7.5)
                path.lineTo(19, 21.5)
                path.lineTo(5.5, 21.5)
                path.closeSubpath()
                path.moveTo(14, 2.5)
                path.lineTo(14, 7.5)
                path.lineTo(19, 7.5)
                for y, end in ((11.5, 16), (14.5, 16), (17.5, 12.5)):
                    path.moveTo(8.5, y)
                    path.lineTo(end, y)
            painter.drawPath(path)
        finally:
            painter.restore()

    def pixmap(self, size, mode, state):
        pixmap = QtGui.QPixmap(size)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        return pixmap


def header_icon(kind, theme):
    if kind not in ('help', 'home', 'document', 'settings', 'image_add'):
        raise ValueError(f'Unknown header icon: {kind}')
    return QtGui.QIcon(_HeaderIcon(kind, theme == 'Темная'))
