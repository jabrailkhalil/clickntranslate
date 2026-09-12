"""Live Windows overlays with capture exclusion and a native window shape.

Windows 10 rejects display affinity for Qt's per-pixel-alpha backing windows.
A regular surface with a window region can stay visible during screen capture.
"""

import ctypes
from ctypes import wintypes
import logging
import sys

from PyQt5 import QtCore, QtGui


def configure_surface(widget, *, windows):
    widget.setAttribute(QtCore.Qt.WA_TranslucentBackground, not windows)


def rounded_region(rect, radius):
    path = QtGui.QPainterPath()
    path.addRoundedRect(QtCore.QRectF(rect), radius, radius)
    return QtGui.QRegion(path.toFillPolygon().toPolygon())


def set_surface_region(widget, region, *, windows):
    if not windows:
        return
    # Empty QRegion clears the mask and exposes the WHOLE window. An off-window
    # nonempty region makes an idle overlay invisible without unmapping it.
    region = region.intersected(QtGui.QRegion(widget.rect()))
    if region.isEmpty():
        region = QtGui.QRegion(-2, -2, 1, 1)
    if widget.mask() != region:
        widget.setMask(region)


def exclude_from_capture(widget):
    if sys.platform != 'win32':
        return False
    try:
        # Older Windows interprets 0x11 as WDA_MONITOR, which captures a black
        # rectangle instead of the underlying source. Never accept that mode.
        if sys.getwindowsversion().build < 19041:
            return False
        api = ctypes.WinDLL('user32', use_last_error=True)
        api.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        api.SetWindowDisplayAffinity.restype = wintypes.BOOL
        api.GetWindowDisplayAffinity.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        api.GetWindowDisplayAffinity.restype = wintypes.BOOL
        hwnd = int(widget.winId())
        if not api.SetWindowDisplayAffinity(hwnd, 0x11):
            raise ctypes.WinError(ctypes.get_last_error())
        value = wintypes.DWORD()
        return bool(api.GetWindowDisplayAffinity(hwnd, ctypes.byref(value)) and value.value == 0x11)
    except Exception:
        logging.getLogger('clickntranslate.game').exception('Cannot exclude the live overlay from Windows capture')
        return False
