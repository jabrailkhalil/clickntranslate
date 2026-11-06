"""Dynamic retries launch failures using generated pixels, never a desktop grab."""
import pytest
from PyQt5 import QtGui

from api_providers import VisionLayout, VisionResult
import api_ocr
import game_mode
import ocr
from test_dynamic_session_boundaries import ApiWorker, CaptureWorker, TextWorker, live_overlays
from test_desktop_ux import app


def actual_tick(overlay, monkeypatch, fullscreen, mac=False):
    owner = game_mode.GameFullscreenOverlay if fullscreen else game_mode.GameTranslationOverlay
    monkeypatch.setattr(overlay, '_scan_once', owner._scan_once.__get__(overlay))
    monkeypatch.setattr(overlay, '_target_is_active', lambda: True)
    if not fullscreen:
        monkeypatch.setattr(overlay, '_update_bound_region', lambda: None)
    monkeypatch.setattr(game_mode.platform_support, 'IS_MAC', mac)
    image = QtGui.QImage(80, 40, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor('white'))
    monkeypatch.setattr(overlay, '_grab_screen' if fullscreen else '_grab_region',
                        lambda: QtGui.QPixmap.fromImage(image))


@pytest.mark.parametrize('fullscreen,direct', [(False, False), (False, True), (True, False)])
@pytest.mark.parametrize('stage', ['construct', 'start'])
@pytest.mark.parametrize('error_type', [RuntimeError, OSError])
def test_failed_ocr_launch_leaves_no_busy_worker_and_the_same_frame_can_retry(
        live_overlays, monkeypatch, fullscreen, direct, stage, error_type):
    overlay = live_overlays(fullscreen, direct)
    actual_tick(overlay, monkeypatch, fullscreen)
    workers, attempts = [], []
    base = ApiWorker if direct or fullscreen else TextWorker

    def create(*args, **kwargs):
        first = not attempts
        attempts.append(True)
        if first and stage == 'construct':
            raise error_type('fixture OCR constructor unavailable')
        worker = base(*args, **kwargs)
        workers.append(worker)
        if first:
            worker.start.side_effect = error_type('fixture OCR thread unavailable')
        return worker

    if fullscreen:
        monkeypatch.setattr(ocr, 'create_position_ocr_worker', create)
    elif direct:
        monkeypatch.setattr(api_ocr, 'ApiOCRWorker', create)
    else:
        monkeypatch.setattr(ocr, 'RapidOCRWorker', create)
    overlay._scan_once()
    assert not overlay._ocr_busy
    assert not overlay._workers
    assert overlay._active_ocr_worker is None
    # Identical frames already have a bounded retry cadence. Advance logical
    # ticks without sleeping or changing that production policy.
    for _ in range(30):
        overlay._scan_once()
        if overlay._ocr_busy:
            break
    assert len(attempts) == 2
    current = workers[-1]
    current.start.assert_called_once()
    assert overlay._workers == {current}
    if fullscreen:
        result = VisionLayout([(10, 10, 100, 24, 'new scene')])
        result.translations = ['NEW TRANSLATION']
    else:
        result = VisionResult('new scene', 'NEW TRANSLATION') if direct else 'new scene'
    current.result_ready.emit(result)
    current.finished.emit()
    assert not overlay._ocr_busy
    assert not overlay._workers
    if fullscreen:
        assert [item[5] for item in overlay._blocks] == ['NEW TRANSLATION']
    elif direct:
        assert overlay.translation_label.text() == 'NEW TRANSLATION'
    else:
        overlay._start_translation.assert_called_once_with('new scene')


@pytest.mark.parametrize('fullscreen', [False, True])
@pytest.mark.parametrize('stage', ['construct', 'start'])
def test_failed_macos_capture_launch_can_retry_without_a_stale_busy_token(
        live_overlays, monkeypatch, fullscreen, stage):
    overlay = live_overlays(fullscreen)
    actual_tick(overlay, monkeypatch, fullscreen, mac=True)
    overlay._native_capture = object()
    attempts, workers = [], []

    def create(*args, **kwargs):
        first = not attempts
        attempts.append(True)
        if first and stage == 'construct':
            raise RuntimeError('fixture capture constructor unavailable')
        worker = CaptureWorker(*args, **kwargs)
        workers.append(worker)
        if first:
            worker.start.side_effect = RuntimeError('fixture capture thread unavailable')
        return worker

    monkeypatch.setattr(game_mode, '_MacOverlayCaptureWorker', create)
    overlay._scan_once()
    assert not overlay._capture_busy
    assert not overlay._workers
    assert overlay._active_capture_worker is None
    overlay._scan_once()
    assert len(attempts) == 2
    assert overlay._capture_busy
    assert overlay._workers == {workers[-1]}
    workers[-1].finished.emit()  # Cooperative cancellation may produce no image.
    assert not overlay._capture_busy
    assert not overlay._workers
