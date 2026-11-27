"""Already scheduled OCR refreshes must eventually replace a similar old scene."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui

from api_providers import VisionResult
import background_tasks
import game_mode
import translater
from test_desktop_ux import app
from test_dynamic_session_boundaries import live_overlays

OLD = 'I have not reached the gate, so the guards are still waiting.'
NEW = 'I have now reached the gate, so the guards are still waiting.'


def frame(text, *, dark=False):
    image = QtGui.QImage(1600, 400, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor('black' if dark else 'white'))
    painter = QtGui.QPainter(image)
    font = QtGui.QFont('Segoe UI')
    font.setPixelSize(18)
    painter.setFont(font)
    painter.setPen(QtGui.QColor('white' if dark else 'black'))
    painter.drawText(QtCore.QPoint(20, 60), text)
    painter.end()
    return image


@pytest.fixture
def frames(app):
    return frame(OLD), frame(NEW)


@pytest.fixture
def periodic(live_overlays, monkeypatch):
    jobs = []
    monkeypatch.setattr(background_tasks.TRANSLATION_EXECUTOR, 'submit', lambda work: (jobs.append(work) or True))
    translate = mock.Mock(side_effect=lambda text, *_args, **_kwargs: 'T:' + text)
    monkeypatch.setattr(translater, 'translate_text', translate)

    def create(direct):
        overlay = live_overlays(direct=direct)
        overlay._start_translation = mock.Mock(wraps=game_mode.GameTranslationOverlay._start_translation.__get__(overlay))
        counters = {'ocr': 0}

        def tick(image, source=OLD, api_error=None):
            previous = set(overlay._workers)
            overlay._process_frame(image)
            added = set(overlay._workers) - previous
            if not added:
                return False
            assert len(added) == 1
            counters['ocr'] += 1
            worker = added.pop()
            text = source(counters['ocr']) if callable(source) else source
            if direct and api_error:
                worker.failed.emit(api_error)
            else:
                worker.result_ready.emit(VisionResult(text, 'T:' + text) if direct else text)
            # A controlled provider can finish before OCR's queued finished
            # notification. Exercise the ordinary deferred publication path.
            while jobs:
                jobs.pop(0)()
            worker.finished.emit()
            return True

        def next_result(image, source=OLD):
            for _ in range(30):
                if tick(image, source):
                    return
            pytest.fail('The existing periodic OCR retry never became eligible')

        return overlay, tick, next_result, translate, counters

    return create


def test_generated_word_edit_changes_pixels_but_remains_below_region_sampler_threshold(frames):
    before, after = frames
    assert before != after
    previous = game_mode.game_frame_fingerprint(before)
    current = game_mode.game_frame_fingerprint(after)
    assert previous != current
    assert len(previous) == len(current) == 96 * 48
    assert not game_mode.game_frames_are_different(previous, current)


@pytest.mark.parametrize('direct', [False, True])
def test_repeated_periodic_ocr_replaces_a_stable_small_word_edit_without_extra_scans(periodic, frames, direct):
    overlay, tick, _, translate, counters = periodic(direct)
    before, after = frames
    assert tick(before)
    assert overlay.translation_label.text() == 'T:' + OLD
    for _ in range(36):  # Three existing ~10-second refreshes, no actual sleep.
        tick(after, NEW)
        if counters['ocr'] == 2:
            assert overlay.translation_label.text() == 'T:' + OLD
        elif counters['ocr'] >= 3:
            assert overlay.translation_label.text() == 'T:' + NEW
    assert counters['ocr'] == 4
    assert overlay._last_source_text == NEW
    assert overlay.translation_label.text() == 'T:' + NEW
    assert translate.call_count == (0 if direct else 2)


@pytest.mark.parametrize('direct', [False, True])
def test_a_normally_changed_frame_is_applied_on_its_first_ocr_result(periodic, frames, direct):
    overlay, tick, _, translate, counters = periodic(direct)
    before, _ = frames
    tick(before)
    changed = frame(NEW, dark=True)
    assert tick(changed, NEW)
    assert counters['ocr'] == 2
    assert overlay.translation_label.text() == 'T:' + NEW
    assert translate.call_count == (0 if direct else 2)


@pytest.mark.parametrize('direct', [False, True])
def test_an_unchanged_source_never_creates_duplicate_translation_requests(periodic, frames, direct):
    overlay, tick, _, translate, counters = periodic(direct)
    before, _ = frames
    tick(before)
    for _ in range(60):
        tick(before)
    assert counters['ocr'] == 6
    assert overlay.translation_label.text() == 'T:' + OLD
    assert translate.call_count == (0 if direct else 1)


@pytest.mark.parametrize('direct', [False, True])
def test_one_off_ocr_glyph_jitter_is_not_published_at_periodic_refreshes(periodic, frames, direct):
    overlay, tick, _, translate, counters = periodic(direct)
    before, _ = frames
    typo = OLD.replace('still', 'stiIl')
    tick(before)
    for _ in range(48):
        tick(before, lambda count: typo if count in {2, 4} else OLD)
    assert counters['ocr'] == 5
    assert overlay.translation_label.text() == 'T:' + OLD
    assert translate.call_count == (0 if direct else 1)


@pytest.mark.parametrize('direct', [False, True])
@pytest.mark.parametrize('empty_count', [1, 2])
def test_empty_ocr_then_new_text_recovers_on_the_same_frame_fingerprint(periodic, frames, direct, empty_count):
    overlay, tick, next_result, translate, counters = periodic(direct)
    before, after = frames
    tick(before)
    for _ in range(empty_count):
        next_result(before, '')
    next_result(after, NEW)
    assert counters['ocr'] == 2 + empty_count
    assert overlay.translation_label.text() == 'T:' + NEW
    assert translate.call_count == (0 if direct else 2)


@pytest.mark.parametrize('direct', [False, True])
def test_provider_failure_retries_the_same_pixels_and_source_without_duplicates(periodic, frames, direct):
    overlay, tick, next_result, translate, counters = periodic(direct)
    before, _ = frames
    if not direct:
        translate.side_effect = [RuntimeError('rate limited fixture'), 'T:' + OLD]
    tick(before, api_error='rate limited fixture' if direct else None)
    next_result(before)
    for _ in range(24):
        tick(before)
    assert counters['ocr'] == 4
    assert overlay.translation_label.text() == 'T:' + OLD
    assert translate.call_count == (0 if direct else 2)
