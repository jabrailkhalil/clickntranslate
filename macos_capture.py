"""Capture underneath our visible overlays, without changing their opacity.

Called from a worker thread. ScreenCaptureKit is used on macOS 14+, and the
window-list compositor on 13.4. Neither path changes privacy settings or includes
our own windows when exclusion fails. Images stay in memory.
"""

import os
import platform
import threading
import time


class CaptureCancelled(Exception):
    pass


def _await_completion(start, cancelled, timeout=8):
    completed = threading.Event()
    result = []

    def receive(value, error):
        result.extend((value, error))
        completed.set()

    start(receive)
    deadline = time.monotonic() + timeout
    while not completed.wait(0.1):
        if cancelled():
            raise CaptureCancelled()
        if time.monotonic() >= deadline:
            raise TimeoutError('macOS screen capture timed out')
    if cancelled():
        raise CaptureCancelled()
    value, error = result
    if error is not None:
        raise RuntimeError(str(error.localizedDescription()))
    if value is None:
        raise RuntimeError('macOS returned an empty screen capture')
    return value


class OverlayCapture:
    """One session per overlay; reuse its application exclusion filter."""

    def __init__(self):
        self._screen_key = None
        self._filter = None

    def capture(self, screen_rect, region_rect, density, cancelled=lambda: False):
        import objc
        from PyQt5.QtGui import QImage
        from AppKit import NSBitmapImageRep, NSBitmapImageFileTypePNG
        from macos_desktop import permission_granted

        if cancelled():
            raise CaptureCancelled()
        if not permission_granted('screen'):
            raise PermissionError('Screen recording access is not available to this process')
        with objc.autorelease_pool():
            if int(platform.mac_ver()[0].split('.')[0]) >= 14:
                try:
                    image = self._capture_sck(screen_rect, region_rect, density, cancelled)
                except Exception:
                    self._filter = None
                    raise
            else:
                image = self._capture_window_list(region_rect)
            if cancelled():
                raise CaptureCancelled()
            if image is None:
                raise RuntimeError('macOS returned an empty screen capture')
            bitmap = NSBitmapImageRep.alloc().initWithCGImage_(image)
            data = bitmap.representationUsingType_properties_(NSBitmapImageFileTypePNG, {})
            if data is None:
                raise RuntimeError('Unable to read the captured macOS image')
            result = QImage.fromData(bytes(data), 'PNG')
            if result.isNull():
                raise RuntimeError('Unable to decode the captured macOS image')
            result.setDevicePixelRatio(density)
            return result

    def _capture_sck(self, screen_rect, region_rect, density, cancelled):
        import Quartz
        import ScreenCaptureKit as SCK

        if self._filter is None or self._screen_key != screen_rect:
            content = _await_completion(
                SCK.SCShareableContent.getShareableContentWithCompletionHandler_, cancelled)
            display = None
            for candidate in content.displays():
                bounds = Quartz.CGDisplayBounds(candidate.displayID())
                geometry = tuple(round(value) for value in (
                    bounds.origin.x, bounds.origin.y, bounds.size.width, bounds.size.height))
                if geometry == screen_rect:
                    display = candidate
                    break
            if display is None:
                raise RuntimeError('The selected display is no longer available')
            own_apps = [app for app in content.applications() if app.processID() == os.getpid()]
            if not own_apps:
                raise RuntimeError('Unable to exclude ClicknTranslate from screen capture')
            # Application filtering also excludes newly opened translation
            # areas, so multiple simultaneous overlays never capture each other.
            self._filter = SCK.SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(
                display, own_apps, [])
            self._screen_key = screen_rect

        x, y, width, height = region_rect
        configuration = SCK.SCStreamConfiguration.alloc().init()
        configuration.setSourceRect_(Quartz.CGRectMake(
            x - screen_rect[0], y - screen_rect[1], width, height))
        configuration.setWidth_(max(1, round(width * density)))
        configuration.setHeight_(max(1, round(height * density)))
        configuration.setShowsCursor_(False)
        configuration.setCapturesAudio_(False)
        configuration.setScalesToFit_(True)
        return _await_completion(
            lambda completion: SCK.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(
                self._filter, configuration, completion), cancelled)

    @staticmethod
    def _capture_window_list(region_rect):
        import Quartz

        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID) or []
        window_ids = [int(window[Quartz.kCGWindowNumber]) for window in windows
                      if int(window.get(Quartz.kCGWindowOwnerPID, 0)) != os.getpid()]
        if not window_ids:
            raise RuntimeError('No windows are available for screen capture')
        return Quartz.CGWindowListCreateImageFromArray(
            Quartz.CGRectMake(*region_rect), window_ids, Quartz.kCGWindowImageBestResolution)
