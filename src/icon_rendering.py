"""Request icon pixels for the actual painter, including proxy zoom and DPR."""
import math
from functools import lru_cache
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets


@lru_cache(maxsize=64)
def _flag_renderer(path):
    from PyQt5.QtSvg import QSvgRenderer
    return QSvgRenderer(path)


class _FlagIconEngine(QtGui.QIconEngine):
    """Keep the frame's final clip in QPainter, outside QtSvg's nested clips."""
    def __init__(self, path):
        super().__init__()
        self.path = path

    def clone(self):
        return _FlagIconEngine(self.path)

    def actualSize(self, size, mode, state):
        return QtCore.QSize(90, 80).scaled(size, QtCore.Qt.KeepAspectRatio)

    def pixmap(self, size, mode, state):
        size = self.actualSize(size, mode, state)
        if size.isEmpty():
            return QtGui.QPixmap()
        key = f'cnt-flag:{self.path}:{size.width()}:{size.height()}:{mode}:{state}'
        cached = QtGui.QPixmapCache.find(key)
        if cached is not None:
            return cached
        renderer = _flag_renderer(self.path)
        if not renderer.isValid():
            return QtGui.QPixmap()
        layer = QtGui.QPixmap(size)
        layer.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(layer)
        renderer.render(painter, QtCore.QRectF(0, 0, size.width(), size.height()))
        painter.end()
        result = QtGui.QPixmap(size)
        result.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(result)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        painter.scale(size.width()/90, size.height()/80)
        outer = QtGui.QPainterPath()
        outer.addRoundedRect(QtCore.QRectF(2, 6, 86, 68), 12, 12)
        painter.fillPath(outer, QtCore.Qt.white)
        inner = QtGui.QPainterPath()
        inner.addRoundedRect(QtCore.QRectF(6, 10, 78, 60), 8, 8)
        painter.setClipPath(inner)
        painter.drawPixmap(QtCore.QRectF(0, 0, 90, 80), layer, QtCore.QRectF(layer.rect()))
        painter.end()
        if mode == QtGui.QIcon.Disabled and QtWidgets.QApplication.instance() is not None:
            result = QtWidgets.QApplication.style().generatedIconPixmap(mode, result, QtWidgets.QStyleOption())
        QtGui.QPixmapCache.insert(key, result)  # Qt's shared, size-bounded LRU; no private bitmap pool.
        return result

    def paint(self, painter, rect, mode, state):
        paint_icon(painter, QtGui.QIcon(self.clone()), rect, mode, state)


@lru_cache(maxsize=128)
def load_icon(path):
    path = str(path)
    resource = Path(path)
    if resource.suffix.lower() == '.svg' and resource.parent.name == 'flags':
        return QtGui.QIcon(_FlagIconEngine(path))
    return QtGui.QIcon(path)


def paint_icon(painter, icon, rect, mode=QtGui.QIcon.Normal, state=QtGui.QIcon.Off):
    rect = QtCore.QRectF(rect)
    if icon.isNull() or rect.isEmpty():
        return
    transform = painter.deviceTransform()
    sx = math.hypot(transform.m11(), transform.m12())
    sy = math.hypot(transform.m21(), transform.m22())
    requested = QtCore.QSize(max(1, math.ceil(rect.width()*sx-1e-9)),
                            max(1, math.ceil(rect.height()*sy-1e-9)))
    pixels = icon.pixmap(requested, mode, state)
    if pixels.isNull():
        return
    pixels.setDevicePixelRatio(1)
    fitted = QtCore.QSizeF(pixels.size()).scaled(rect.size(), QtCore.Qt.KeepAspectRatio)
    target = QtCore.QRectF(rect.center().x()-fitted.width()/2,
                         rect.center().y()-fitted.height()/2, fitted.width(), fitted.height())
    painter.save()
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
    painter.drawPixmap(target, pixels, QtCore.QRectF(pixels.rect()))
    painter.restore()


class ScalableIconLabel(QtWidgets.QLabel):
    """A vector-backed label, without a fixed-size raster preview to stretch."""
    def __init__(self, icon, parent=None):
        super().__init__(parent)
        self._icon = QtGui.QIcon(icon)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        paint_icon(painter, self._icon, self.contentsRect(),
                   QtGui.QIcon.Normal if self.isEnabled() else QtGui.QIcon.Disabled)
