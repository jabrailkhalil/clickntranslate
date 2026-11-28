"""Exercise area-selector paint and OCR input on synthetic pixels, without opening a window."""

from unittest import mock
from types import SimpleNamespace

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

import api_ocr
import api_providers
import ocr
import platform_support


@pytest.fixture
def frame(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    geometry = QtCore.QRect(-160, 40, 160, 100)
    screen = SimpleNamespace(geometry=lambda: geometry, devicePixelRatio=lambda: 1.5)
    source = QtGui.QPixmap(240, 150)
    source.fill(QtGui.QColor('navy'))
    painter = QtGui.QPainter(source)
    painter.fillRect(30, 24, 36, 21, QtGui.QColor('lime'))
    painter.end()
    source.setDevicePixelRatio(1.5)
    overlay = mock.Mock(mode='copy', _session_id='synthetic', _freeze_screen_on_ocr=False,
                        _dim_screen_during_ocr=False, _ocr_in_progress=False,
                        start_point=None, end_point=None, _preview_rect=None, _active_screen=screen)
    overlay._freeze_required.side_effect = lambda: ocr.ScreenCaptureOverlay._freeze_required(overlay)
    overlay.rect.return_value = QtCore.QRect(0, 0, 160, 100)
    overlay.geometry.return_value = geometry
    overlay.mapToGlobal.side_effect = lambda point: point + geometry.topLeft()
    overlay._select_target_screen_for_rect.return_value = (screen, 'fixture')
    overlay.lang_combo.currentData.return_value = 'en'
    overlay.get_ocr_engine.return_value = next(iter(api_providers.VISION_ENGINES))
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: {})
    monkeypatch.setattr(ocr, 'notify_current_activity', mock.Mock())
    monkeypatch.setattr(ocr, '_save_pixmap_debug', mock.Mock())
    return app, overlay, source


@pytest.mark.parametrize('platform', ['linux', 'mac'])
def test_required_frozen_screen_supplies_the_pixels_shown_and_submitted_to_ocr(frame, monkeypatch, platform):
    _app, overlay, source = frame
    monkeypatch.setattr(platform_support, 'IS_LINUX', platform == 'linux')
    monkeypatch.setattr(platform_support, 'IS_MAC', platform == 'mac')
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', False)
    grab = mock.Mock(return_value=source)
    monkeypatch.setattr(ocr, 'grab_screen_pixmap', grab)
    ocr.ScreenCaptureOverlay._capture_frozen_background(overlay, overlay.geometry())
    selected = QtCore.QRect(20, 16, 24, 14)
    changed = QtGui.QPixmap(36, 21)
    changed.fill(QtGui.QColor('red'))
    overlay._grab_screenshot_region.return_value = (changed, 'live', selected)
    worker = mock.Mock()
    monkeypatch.setattr(api_ocr, 'ApiOCRWorker', worker)
    ocr.ScreenCaptureOverlay.capture_and_copy(overlay, selected)
    image = worker.call_args.args[1]
    assert image.size == (36, 21)
    assert image.getpixel((18, 10))[:3] == (0, 255, 0)
    assert overlay._last_ocr_capture_meta['frozen'] is True
    overlay._grab_screenshot_region.assert_not_called()
    grab.assert_called_once()


def render_paint(overlay, monkeypatch):
    canvas = QtGui.QImage(160, 100, QtGui.QImage.Format_ARGB32)
    canvas.fill(QtGui.QColor('black'))
    real_painter = QtGui.QPainter
    class CanvasPainter(real_painter):
        def __init__(self, target):
            super().__init__(canvas if target is overlay else target)
    with monkeypatch.context() as painting:
        painting.setattr(QtGui, 'QPainter', CanvasPainter)
        ocr.ScreenCaptureOverlay.paintEvent(overlay, None)
    return canvas


def test_selector_renders_the_required_frame_before_dragging_with_default_preferences(frame, monkeypatch, tmp_path):
    _app, overlay, source = frame
    monkeypatch.setattr(platform_support, 'IS_LINUX', True)
    overlay._frozen_background = source
    canvas = render_paint(overlay, monkeypatch)
    assert canvas.save(str(tmp_path / 'selector-before-drag.png'))
    assert canvas.pixelColor(24, 20).green() >= 245
    assert canvas.pixelColor(80, 60).blue() >= 120


def test_dimmed_frozen_selection_reveals_the_undimmed_pixels_inside_the_rectangle(frame, monkeypatch, tmp_path):
    _app, overlay, source = frame
    overlay._freeze_screen_on_ocr = True
    overlay._frozen_background = source
    overlay._dim_screen_during_ocr = True
    overlay._ocr_dim_strength = 50
    overlay._preview_rect = QtCore.QRect(18, 14, 48, 32)
    canvas = render_paint(overlay, monkeypatch)
    assert canvas.save(str(tmp_path / 'selector-dimmed.png'))
    assert canvas.pixelColor(29, 22) == QtGui.QColor('lime')
    assert 50 <= canvas.pixelColor(90, 55).blue() <= 70


def test_repainting_after_a_failed_capture_does_not_start_another_capture(frame, monkeypatch):
    _app, overlay, _ = frame
    overlay._freeze_screen_on_ocr = True
    overlay._frozen_background = None
    render_paint(overlay, monkeypatch)
    render_paint(overlay, monkeypatch)
    overlay._capture_frozen_background.assert_not_called()


@pytest.mark.parametrize('reason', ['wayland_cancel', 'wayland_denied', 'mac_revoked'])
def test_denied_opening_frame_ends_area_selection_and_releases_the_next_hotkey(frame, monkeypatch, reason):
    import linux_capture
    import macos_desktop
    import mode_coordinator
    app, overlay, _ = frame
    wayland = reason.startswith('wayland')
    monkeypatch.setattr(platform_support, 'IS_LINUX', wayland)
    monkeypatch.setattr(platform_support, 'IS_MAC', not wayland)
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', False)
    monkeypatch.setattr(platform_support, 'is_wayland', lambda: wayland)
    why = linux_capture.CaptureCancelled if reason == 'wayland_cancel' else linux_capture.CaptureDeclined
    portal = mock.Mock(side_effect=why('Synthetic portal rejection'))
    monkeypatch.setattr(linux_capture, 'grab_screen', portal)
    preflight = mock.Mock(return_value=False)
    monkeypatch.setattr(macos_desktop, 'permission_granted', preflight)
    screen = overlay._active_screen
    overlay._get_active_screen.return_value = screen
    overlay.thread.return_value = app.thread()
    overlay.windowState.return_value = QtCore.Qt.WindowNoState
    overlay._capture_frozen_background.side_effect = lambda rect: ocr.ScreenCaptureOverlay._capture_frozen_background(overlay, rect)
    overlay.show_overlay.side_effect = lambda: ocr.ScreenCaptureOverlay.show_overlay(overlay)
    monkeypatch.setattr(ocr, 'style_capture_controls', mock.Mock())
    monkeypatch.setattr(QtWidgets.QApplication, 'screens', lambda: [screen])
    monkeypatch.setattr(QtCore.QTimer, 'singleShot', mock.Mock())
    monkeypatch.setattr(ocr, '_ACTIVE_OVERLAYS', {})
    monkeypatch.setattr(ocr, '_OVERLAY_POOL', {'copy': overlay})
    mode_coordinator._reset_for_tests()
    try:
        ocr.run_screen_capture('copy')
        overlay.show.assert_not_called()
        assert mode_coordinator.active_mode() is None
        assert not ocr._ACTIVE_OVERLAYS.get('copy')
        assert portal.call_count == int(wayland)
        assert preflight.call_count == int(not wayland)
    finally:
        mode_coordinator._reset_for_tests()


def test_denied_fullscreen_capture_stops_before_constructing_visible_controls(frame, monkeypatch):
    import linux_capture
    import mode_coordinator
    _app, overlay, _ = frame
    monkeypatch.setattr(platform_support, 'IS_LINUX', True)
    monkeypatch.setattr(platform_support, 'IS_MAC', False)
    monkeypatch.setattr(platform_support, 'is_wayland', lambda: True)
    monkeypatch.setattr(QtGui.QCursor, 'pos', lambda: QtCore.QPoint(-80, 70))
    monkeypatch.setattr(QtWidgets.QApplication, 'screenAt', lambda point: overlay._active_screen)
    grab = mock.Mock(side_effect=linux_capture.CaptureDeclined('Synthetic saved denial'))
    monkeypatch.setattr(linux_capture, 'grab_screen', grab)
    controls = mock.Mock(side_effect=AssertionError('Fullscreen controls created after denial'))
    monkeypatch.setattr(ocr, 'DropDownCombo', controls)
    monkeypatch.setattr(QtWidgets.QWidget, 'show', mock.Mock())
    monkeypatch.setattr(ocr, '_fullscreen_overlay_ref', None)
    mode_coordinator._reset_for_tests()
    try:
        ocr.run_fullscreen_translate()
        assert mode_coordinator.active_mode() is None
        assert ocr._fullscreen_overlay_ref is None
        controls.assert_not_called()
        grab.assert_called_once()
    finally:
        mode_coordinator._reset_for_tests()


def test_unsuccessful_wayland_region_capture_consults_the_portal_once(frame, monkeypatch):
    _app, overlay, _ = frame
    monkeypatch.setattr(platform_support, 'IS_LINUX', True)
    monkeypatch.setattr(platform_support, 'is_wayland', lambda: True)
    grab = mock.Mock(return_value=QtGui.QPixmap())
    monkeypatch.setattr(ocr, 'grab_screen_pixmap', grab)
    absolute = QtCore.QRect(-142, 54, 30, 24)
    pixmap, name, clipped = ocr.ScreenCaptureOverlay._grab_screenshot_region(
        overlay, overlay._active_screen, absolute)
    assert pixmap.isNull() and name == '' and clipped == absolute
    grab.assert_called_once_with(overlay._active_screen, 18, 14, 30, 24)
