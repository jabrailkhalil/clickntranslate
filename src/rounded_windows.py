"""Clip a frameless native window to its actual rounded content surface."""
import sys
import weakref

from PyQt5 import QtCore, QtGui, sip


class _RoundedSurface(QtCore.QObject):
    def __init__(self, window, surface, radius):
        super().__init__(window)
        self.window_ref = weakref.ref(window)
        # Retain the Python wrapper of layout-owned frames. Qt may otherwise
        # discard a wrapper even while the C++ surface remains alive.
        self.surface = surface
        self.radius = radius
        window.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        window.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        window.installEventFilter(self)
        if surface is not window:
            surface.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.Show, QtCore.QEvent.Resize,
                            QtCore.QEvent.Move, QtCore.QEvent.LayoutRequest):
            self.update_shape()
        elif (event.type() == QtCore.QEvent.DynamicPropertyChange
              and event.propertyName() == b'ui_effective_scale'):
            self.update_shape()
        return False

    def update_shape(self):
        window, surface = self.window_ref(), self.surface
        if (window is None or surface is None or sip.isdeleted(window)
                or sip.isdeleted(surface) or not window.isWindow()):
            return
        if sys.platform == 'darwin':
            return  # Cocoa uses the translucent, antialiased painted surface.
        rect = QtCore.QRectF(surface.rect())
        if rect.isEmpty():
            return
        rect.moveTopLeft(QtCore.QPointF(surface.mapTo(window, QtCore.QPoint())))
        factor = float(window.property('ui_effective_scale') or 1.0)
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, self.radius * factor, self.radius * factor)
        region = QtGui.QRegion(path.toFillPolygon().toPolygon())
        if window.mask() != region:
            window.setMask(region)


def clip_rounded_window(window, surface, radius):
    # Keep the filter alive for exactly the native window's lifetime. No queued
    # callback may access a widget that a page rebuild has already deleted.
    previous = getattr(window, '_rounded_surface', None)
    if previous is not None:
        window.removeEventFilter(previous)
        old_surface = previous.surface
        if old_surface is not None and not sip.isdeleted(old_surface):
            old_surface.removeEventFilter(previous)
        previous.deleteLater()
    window._rounded_surface = _RoundedSurface(window, surface, radius)
