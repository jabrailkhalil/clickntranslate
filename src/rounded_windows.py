"""Clip a frameless native window to its actual rounded content surface."""
import sys
import weakref

from PyQt5 import QtCore, QtGui, sip


def rounded_clip_region(rect, radius, *, inset=0.0, stroke_width=0.0):
    """A conservative native clip matching a rounded painted surface.

    Radius and geometry must be the same ones used by the surface painter.
    An integer native mask clips transparent corners, never its visible stroke.
    """
    rect = QtCore.QRect(rect)
    if rect.isEmpty():
        return QtGui.QRegion()
    radius = max(0., min(float(radius), max(0., min(rect.width(), rect.height())/2-inset)))
    path = QtGui.QPainterPath()
    path.addRoundedRect(QtCore.QRectF(rect).adjusted(inset,inset,-inset,-inset), radius, radius)
    if stroke_width:
        stroke = QtGui.QPainterPathStroker()
        stroke.setWidth(stroke_width)
        path = path.united(stroke.createStroke(path))
    region = QtGui.QRegion(path.toFillPolygon().toPolygon())
    # This is only a fallback for non-composited platforms. A conservative
    # pixel around the integer polygon retains the antialiased painted edge.
    expanded = QtGui.QRegion(region)
    for x,y in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)):
        expanded |= region.translated(x,y)
    return expanded.intersected(QtGui.QRegion(rect))


def uses_alpha_surface(window):
    """Layered native windows and graphics scenes already clip by paint alpha."""
    return (window.graphicsProxyWidget() is not None
            or sys.platform in ('win32','darwin')
            and window.testAttribute(QtCore.Qt.WA_TranslucentBackground)
            and bool(window.windowFlags() & QtCore.Qt.FramelessWindowHint))


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
        if uses_alpha_surface(window):
            # QRegion uses integer logical coordinates and cuts curved border
            # pixels at fractional DPI. The painted transparent surface keeps
            # all antialiasing on Windows/Cocoa and in a graphics proxy.
            if not window.mask().isEmpty():
                window.clearMask()
            return
        rect = QtCore.QRectF(surface.rect())
        if rect.isEmpty():
            return
        rect.moveTopLeft(QtCore.QPointF(surface.mapTo(window, QtCore.QPoint())))
        factor = float(window.property('ui_effective_scale') or 1.0)
        region = rounded_clip_region(rect.toAlignedRect(), self.radius * factor)
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
