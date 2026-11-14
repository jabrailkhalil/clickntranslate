"""Live pipeline boundaries using generated pixels and controlled Qt workers."""
import threading
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

import api_ocr
from api_providers import VisionLayout, VisionResult
import background_tasks
import game_mode
import ocr
import ocr_readiness
import windows_overlay
import translater
from test_desktop_ux import app


class TextWorker(QtCore.QObject):
    result_ready = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.start = mock.Mock()
        self.cancel = mock.Mock()
        self.requestInterruption = mock.Mock()


class ApiWorker(TextWorker):
    result_ready = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)


class CaptureWorker(TextWorker):
    result_ready = QtCore.pyqtSignal(object, str)


@pytest.fixture
def live_overlays(app, monkeypatch):
    assert app.platformName() == 'offscreen'
    config = dict(theme='Темная', interface_language='en', ocr_engine='RapidOCR',
                  translator_engine='Google', history=False, game_pause_when_inactive=False,
                  ocr_join_paragraphs=True,
                  api_providers={'openai': dict(vision=True, direct=True)})
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: config)
    monkeypatch.setattr(game_mode, '_exclude_from_windows_capture', lambda *_: True)
    monkeypatch.setattr(game_mode, '_keep_overlay_visible_without_focus', lambda *_: None)
    monkeypatch.setattr(game_mode, '_window_rect', lambda *_: QtCore.QRect())
    monkeypatch.setattr(game_mode, '_window_belongs_to_this_process', lambda *_: False)
    monkeypatch.setattr(windows_overlay, 'configure_surface', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ocr_readiness, 'begin_activity', mock.Mock())
    monkeypatch.setattr(ocr_readiness, 'end_activity', mock.Mock())
    monkeypatch.setattr(QtCore.QTimer, 'singleShot', lambda *_: None)
    monkeypatch.setattr(game_mode, '_prepare_game_ocr_variants', lambda image: [('generated', object())])
    monkeypatch.setattr(ocr, 'RapidOCRWorker', TextWorker)
    monkeypatch.setattr(api_ocr, 'ApiOCRWorker', ApiWorker)
    monkeypatch.setattr(ocr, 'create_position_ocr_worker', lambda *_args, **_kwargs: ApiWorker())
    owned = []

    def create(fullscreen=False, direct=False, source='en', target='ru'):
        config['ocr_engine'] = 'OpenAI API' if direct else 'RapidOCR'
        overlay = (game_mode.GameFullscreenOverlay(source, target) if fullscreen else
                   game_mode.GameTranslationOverlay(QtCore.QRect(10, 10, 360, 100), source, target))
        overlay._timer.stop()
        overlay._scan_once = mock.Mock()
        overlay._start_translation = mock.Mock()
        owned.append(overlay)
        return overlay

    yield create
    for overlay in owned:
        for worker in list(overlay._workers):
            worker.finished.emit()
        overlay.close()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


def start_ocr(overlay, fullscreen):
    image = QtGui.QImage(80, 40, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor('white'))
    previous = set(overlay._workers)
    (overlay._start_position_ocr if fullscreen else overlay._start_ocr)(image)
    return (set(overlay._workers) - previous).pop()


def deliver_queued(worker, value):
    def emit():
        worker.result_ready.emit(value)
        worker.finished.emit()
    thread = threading.Thread(target=emit, name='Dynamic-queued-fixture')
    thread.start()
    thread.join(1)
    assert not thread.is_alive()


@pytest.mark.parametrize('fullscreen,direct', [(False, False), (False, True), (True, True)])
def test_ocr_queued_before_pause_cannot_become_current_after_resume(app, live_overlays, fullscreen, direct):
    overlay = live_overlays(fullscreen, direct)
    initial_text = None if fullscreen else overlay.translation_label.text()
    worker = start_ocr(overlay, fullscreen)
    if fullscreen:
        value = VisionLayout([(10, 10, 100, 24, 'old scene')])
        value.translations = ['OLD TRANSLATION']
    else:
        value = VisionResult('old scene', 'OLD TRANSLATION') if direct else 'old scene'
    deliver_queued(worker, value)
    overlay._toggle_pause()
    overlay._toggle_pause()
    app.processEvents()
    if fullscreen:
        assert not overlay._live.lines and not overlay._blocks
    else:
        overlay._start_translation.assert_not_called()
        assert overlay.translation_label.text() == initial_text
    assert not overlay._ocr_busy


@pytest.mark.parametrize('fullscreen', [False, True])
def test_old_ocr_finished_does_not_release_a_replacement_workers_busy_state(live_overlays, fullscreen):
    overlay = live_overlays(fullscreen)
    old = start_ocr(overlay, fullscreen)
    overlay._toggle_pause()
    overlay._toggle_pause()
    current = start_ocr(overlay, fullscreen)
    old.finished.emit()
    assert overlay._ocr_busy
    assert current in overlay._workers
    current.finished.emit()
    assert not overlay._ocr_busy


@pytest.mark.parametrize('before,after', [
    ('Collect 20 berries to complete the quest.', 'Collect 21 berries to complete the quest.'),
    ('Соберите 20 ягод, чтобы завершить задание.', 'Соберите 21 ягод, чтобы завершить задание.'),
    ('اجمع ٢٠ ثمرة لإكمال المهمة', 'اجمع ٢١ ثمرة لإكمال المهمة'),
    ('The temperature is -10 degrees.', 'The temperature is 10 degrees.'),
    ('The temperature is - 10 degrees.', 'The temperature is + 10 degrees.'),
    ('درجة الحرارة هي − ١٠ درجات.', 'درجة الحرارة هي + ١٠ درجات.'),
])
def test_small_numeric_change_is_not_suppressed_as_ocr_jitter(live_overlays, before, after):
    overlay = live_overlays()
    overlay._last_source_text = before
    overlay._ocr_frame_changed = False  # A small patch can share a frame fingerprint.
    overlay._consume_ocr_result(after)
    overlay._start_translation.assert_called_once_with(after)


@pytest.mark.parametrize('before,after', [
    ('The temperature is -10 degrees.', 'The temperature is - 10 degrees.'),
    ('درجة الحرارة هي −١٠ درجات.', 'درجة الحرارة هي − ١٠ درجات.'),
])
def test_unchanged_numeric_value_with_sign_spacing_still_counts_as_ocr_jitter(before, after):
    assert game_mode.game_texts_are_similar(before, after)


def test_region_resume_rechecks_the_same_fingerprint_instead_of_reusing_a_stale_scene(live_overlays):
    overlay = live_overlays()
    overlay._last_frame = b'old-frame'
    overlay._last_source_text = 'old scene'
    overlay._pending_source_text = 'old queued scene'
    cancelled = overlay._translation_cancel = threading.Event()
    overlay._toggle_pause()
    overlay._toggle_pause()
    assert cancelled.is_set()
    assert not overlay._last_frame and not overlay._last_source_text and not overlay._pending_source_text


@pytest.mark.parametrize('fullscreen,direct', [(False, False), (False, True), (True, True)])
def test_current_queued_ocr_after_resume_is_delivered_on_the_gui_thread(app, live_overlays, fullscreen, direct):
    overlay = live_overlays(fullscreen, direct)
    overlay._toggle_pause()
    overlay._toggle_pause()
    worker = start_ocr(overlay, fullscreen)
    if fullscreen:
        value = VisionLayout([(10, 10, 100, 24, 'new scene')])
        value.translations = ['NEW TRANSLATION']
    else:
        value = VisionResult('new scene', 'NEW TRANSLATION') if direct else 'new scene'
    if not fullscreen and not direct:
        overlay._start_translation.side_effect = lambda *_: (
            QtCore.QThread.currentThread() is app.thread() or pytest.fail('OCR delivered outside the GUI thread'))
    deliver_queued(worker, value)
    app.processEvents()
    if fullscreen:
        assert [item[5] for item in overlay._blocks] == ['NEW TRANSLATION']
    elif direct:
        assert overlay.translation_label.text() == 'NEW TRANSLATION'
    else:
        overlay._start_translation.assert_called_once_with('new scene')
    assert not overlay._ocr_busy


@pytest.mark.parametrize('fullscreen', [False, True])
@pytest.mark.parametrize('deliver_image', [False, True])
def test_cancelled_macos_capture_never_processes_an_old_frame_and_releases_busy(
        app, live_overlays, monkeypatch, fullscreen, deliver_image):
    overlay = live_overlays(fullscreen)
    overlay._native_capture = object()
    overlay._process_frame = mock.Mock()
    monkeypatch.setattr(game_mode, '_MacOverlayCaptureWorker', CaptureWorker)
    screen = app.primaryScreen()
    region = screen.geometry() if fullscreen else overlay.region
    game_mode._start_macos_capture(overlay, screen, region)
    worker = next(iter(overlay._workers))
    image = QtGui.QImage(80, 40, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor('white'))

    def emit():
        if deliver_image:
            worker.result_ready.emit(image, '')
        worker.finished.emit()

    thread = threading.Thread(target=emit, name='Dynamic-capture-fixture')
    thread.start()
    thread.join(1)
    assert not thread.is_alive()
    overlay._toggle_pause()
    overlay._toggle_pause()
    assert overlay._capture_busy  # Interruption has not yet delivered finished.
    worker.cancel.assert_called_once()
    app.processEvents()
    overlay._process_frame.assert_not_called()
    assert not overlay._capture_busy


@pytest.mark.parametrize('fullscreen', [False, True])
def test_cancelled_translation_cannot_complete_a_new_request_after_resume(
        app, live_overlays, monkeypatch, fullscreen):
    overlay = live_overlays(fullscreen)
    jobs = []
    monkeypatch.setattr(background_tasks.TRANSLATION_EXECUTOR, 'submit', lambda work: (jobs.append(work) or True))
    monkeypatch.setattr(translater, 'translate_text', lambda text, *_args, **_kwargs: text.upper())
    if fullscreen:
        def start(text):
            lines = [(10, 10, 100, 24, text)]
            overlay._live.observe(lines, 1.0)
            overlay._start_block_translation(lines)
    else:
        start_method = game_mode.GameTranslationOverlay._start_translation.__get__(overlay)
        def start(text):
            overlay._last_source_text = text
            start_method(text)
    start('old scene')
    cancelled = overlay._translation_cancel
    overlay._toggle_pause()
    overlay._toggle_pause()
    assert cancelled.is_set()
    start('new scene')
    current_revision = overlay._revision
    jobs.pop(0)()  # A provider may finish even after its cancellation flag is set.
    assert overlay._translation_busy
    assert overlay._revision == current_revision
    jobs.pop(0)()
    assert not overlay._translation_busy
    if fullscreen:
        assert [item[4:] for item in overlay._blocks] == [('new scene', 'NEW SCENE')]
    else:
        assert overlay.translation_label.text() == 'NEW SCENE'


def test_old_api_error_queued_before_pause_does_not_overwrite_resumed_status(app, live_overlays):
    overlay = live_overlays(direct=True)
    worker = start_ocr(overlay, False)
    thread = threading.Thread(target=lambda: (worker.failed.emit('old quota error'), worker.finished.emit()))
    thread.start()
    thread.join(1)
    assert not thread.is_alive()
    overlay._toggle_pause()
    overlay._toggle_pause()
    status, tooltip = overlay.status_label.text(), overlay.status_label.toolTip()
    app.processEvents()
    assert (overlay.status_label.text(), overlay.status_label.toolTip()) == (status, tooltip)
