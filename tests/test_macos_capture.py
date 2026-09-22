"""ScreenCaptureKit/Quartz contracts using fake framework boundaries, not Cocoa QA."""

import os
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

import macos_capture as capture


@pytest.mark.parametrize('value,error,message', [
    ('image', None, None),
    (None, None, 'empty screen capture'),
    (None, SimpleNamespace(localizedDescription=lambda: 'permission revoked'), 'permission revoked'),
])
def test_completion_handles_success_empty_result_and_native_error(value, error, message):
    start = lambda callback: callback(value, error)
    if message:
        with pytest.raises(RuntimeError, match=message):
            capture._await_completion(start, lambda: False)
    else:
        assert capture._await_completion(start, lambda: False) == value


def test_cancelled_request_never_starts_native_capture():
    start = mock.Mock()
    with pytest.raises(capture.CaptureCancelled):
        capture._await_completion(start, lambda: True)
    start.assert_not_called()


def test_timeout_does_not_block_or_reuse_a_late_result():
    callbacks = []
    with pytest.raises(TimeoutError, match='timed out'):
        capture._await_completion(callbacks.append, lambda: False, timeout=0)
    callbacks[0]('late image', None)
    assert capture._await_completion(lambda done: done('new image', None), lambda: False) == 'new image'


@pytest.fixture
def native(monkeypatch):
    geometries = {1: (0, 0, 1920, 1080), 2: (-1280, -200, 1280, 800)}
    apps = [SimpleNamespace(processID=lambda: os.getpid()), SimpleNamespace(processID=lambda: 999999)]
    displays = [SimpleNamespace(displayID=lambda number=number: number) for number in geometries]
    content = SimpleNamespace(displays=lambda: displays, applications=lambda: apps)
    def bounds(number):
        x, y, width, height = geometries[number]
        return SimpleNamespace(origin=SimpleNamespace(x=x, y=y), size=SimpleNamespace(width=width, height=height))
    quartz = SimpleNamespace(CGDisplayBounds=bounds, CGRectMake=lambda *args: args)
    filter_object = mock.Mock()
    configuration = mock.Mock()
    factory = mock.Mock(return_value=filter_object)
    shareable = mock.Mock(side_effect=lambda done: done(content, None))
    screenshot = mock.Mock(side_effect=lambda _filter, _config, done: done('image', None))
    framework = SimpleNamespace(
        SCShareableContent=SimpleNamespace(getShareableContentWithCompletionHandler_=shareable),
        SCContentFilter=SimpleNamespace(alloc=lambda: SimpleNamespace(
            initWithDisplay_excludingApplications_exceptingWindows_=factory)),
        SCStreamConfiguration=SimpleNamespace(alloc=lambda: SimpleNamespace(init=lambda: configuration)),
        SCScreenshotManager=SimpleNamespace(captureImageWithFilter_configuration_completionHandler_=screenshot))
    monkeypatch.setitem(sys.modules, 'Quartz', quartz)
    monkeypatch.setitem(sys.modules, 'ScreenCaptureKit', framework)
    return SimpleNamespace(apps=apps, displays=displays, factory=factory,
                           configuration=configuration, shareable=shareable, screenshot=screenshot)


@pytest.mark.parametrize('density', [1, 1.5, 2])
def test_retina_region_on_left_display_excludes_our_entire_application(native, density):
    session = capture.OverlayCapture()
    screen = (-1280, -200, 1280, 800)
    region = (-1200, -100, 300, 150)
    assert session._capture_sck(screen, region, density, lambda: False) == 'image'
    native.factory.assert_called_once_with(native.displays[1], [native.apps[0]], [])
    native.configuration.setSourceRect_.assert_called_once_with((80, 100, 300, 150))
    native.configuration.setWidth_.assert_called_once_with(round(300 * density))
    native.configuration.setHeight_.assert_called_once_with(round(150 * density))
    native.configuration.setShowsCursor_.assert_called_once_with(False)
    native.configuration.setCapturesAudio_.assert_called_once_with(False)
    session._capture_sck(screen, region, density, lambda: False)
    assert native.shareable.call_count == 1
    session._capture_sck((0, 0, 1920, 1080), (10, 10, 200, 100), density, lambda: False)
    assert native.shareable.call_count == 2


@pytest.mark.parametrize('missing', ['application', 'display'])
def test_missing_exclusion_or_display_never_captures(native, missing):
    if missing == 'application':
        native.apps.pop(0)
    else:
        native.displays.clear()
    with pytest.raises(RuntimeError):
        capture.OverlayCapture()._capture_sck((0, 0, 1920, 1080), (10, 10, 100, 50), 1, lambda: False)
    native.screenshot.assert_not_called()


@pytest.mark.parametrize('foreign_windows', [[], [2, 3]])
def test_macos13_fallback_excludes_own_windows(monkeypatch, foreign_windows):
    windows = [{'owner': os.getpid(), 'number': 1}]
    windows.extend({'owner': -1, 'number': number} for number in foreign_windows)
    create = mock.Mock(return_value='image')
    quartz = SimpleNamespace(CGWindowListCopyWindowInfo=lambda *_: windows,
                             kCGWindowListOptionOnScreenOnly=1, kCGNullWindowID=0,
                             kCGWindowNumber='number', kCGWindowOwnerPID='owner',
                             CGRectMake=lambda *args: args, kCGWindowImageBestResolution=8,
                             CGWindowListCreateImageFromArray=create)
    monkeypatch.setitem(sys.modules, 'Quartz', quartz)
    if foreign_windows:
        assert capture.OverlayCapture._capture_window_list((-50, 20, 400, 300)) == 'image'
        create.assert_called_once_with((-50, 20, 400, 300), foreign_windows, 8)
    else:
        with pytest.raises(RuntimeError, match='No windows'):
            capture.OverlayCapture._capture_window_list((0, 0, 100, 100))
        create.assert_not_called()
