"""Semantic labels and direct per-region translations retain their identity."""
import json
import random
from unittest import mock

import pytest
from PIL import Image

import api_providers
from api_providers import VisionLayout, VisionResult
import game_mode
from live_translation import LiveTextState
from test_desktop_ux import app
from test_dynamic_session_boundaries import live_overlays, start_ocr


@pytest.mark.parametrize('language,text', [('zh', '水'), ('ja', '火'), ('ko', '물')])
@pytest.mark.parametrize('fullscreen,direct', [(False, False), (False, True), (True, False), (True, True)])
def test_a_single_cjk_word_survives_both_dynamic_ocr_routes(
        live_overlays, monkeypatch, language, text, fullscreen, direct):
    overlay = live_overlays(fullscreen, direct, source=language)
    overlay._start_block_translation = mock.Mock()
    clock = [10.0]
    monkeypatch.setattr(game_mode.time, 'monotonic', lambda: clock[0])
    for _ in range(2 if fullscreen and not direct else 1):
        worker = start_ocr(overlay, fullscreen)
        if fullscreen:
            result = VisionLayout([(10, 10, 32, 24, text)])
            if direct:
                result.translations = ['TRANSLATED WORD']
        else:
            result = VisionResult(text, 'TRANSLATED WORD') if direct else text
        worker.result_ready.emit(result)
        worker.finished.emit()
        clock[0] += .2
    if fullscreen:
        assert [item[4] for item in overlay._live.lines] == [text]
        if direct:
            assert [item[5] for item in overlay._blocks] == ['TRANSLATED WORD']
            overlay._start_block_translation.assert_not_called()
        else:
            assert [item[4] for item in overlay._start_block_translation.call_args.args[0]] == [text]
    elif direct:
        assert overlay.translation_label.text() == 'TRANSLATED WORD'
    else:
        overlay._start_translation.assert_called_once_with(text)


@pytest.mark.parametrize('text', ['a', '.', '/', '9', 'Ａ'])
@pytest.mark.parametrize('direct', [False, True])
def test_single_latin_glyphs_and_noise_keep_the_existing_fullscreen_filter(live_overlays, text, direct):
    overlay = live_overlays(fullscreen=True, direct=direct)
    overlay._start_block_translation = mock.Mock()
    worker = start_ocr(overlay, True)
    result = VisionLayout([(10, 10, 32, 24, text)])
    if direct:
        result.translations = ['NOISE TRANSLATION']
    worker.result_ready.emit(result)
    worker.finished.emit()
    assert not overlay._live.lines and not overlay._blocks
    overlay._start_block_translation.assert_not_called()


@pytest.mark.parametrize('frame_count', [1, 2, 3])
def test_direct_duplicate_sources_keep_each_regions_translation_when_reordered_or_removed(
        live_overlays, monkeypatch, frame_count):
    overlay = live_overlays(fullscreen=True, direct=True)
    overlay._start_block_translation = mock.Mock()
    image = Image.new('RGB', (overlay.width(), overlay.height()), 'white')
    frames = [
        [('a', [10, 10, 40, 60], 'noise'),
         ('Open', [100, 100, 250, 160], 'Открыть'),
         ('Open', [600, 400, 750, 460], 'Открыто')],
        [('Open', [650, 500, 800, 560], 'Открыто здесь'),
         ('a', [10, 10, 40, 60], 'noise'),
         ('Open', [100, 200, 250, 260], 'Открыть здесь')],
        [('Open', [650, 500, 800, 560], 'Только текущая область')],
    ]
    monkeypatch.setattr(api_providers, 'validate', lambda *_: {'vision': True, 'direct': True})
    monkeypatch.setattr(api_providers, 'credential', lambda *_: 'unused-fixture-key')
    latest = None
    for frame in frames[:frame_count]:
        raw = json.dumps({'regions': [dict(source=source, box=box, translation=value)
                                      for source, box, value in frame]})
        monkeypatch.setattr(api_providers, '_text_response', lambda *_args, value=raw: value)
        latest = api_providers.recognize_regions('openai', image, 'en', 'ru', overlay.config)
        worker = start_ocr(overlay, True)
        worker.result_ready.emit(latest)
        worker.finished.emit()
    expected = [(*item, value) for item, value in zip(latest, latest.translations) if item[4] != 'a']
    assert overlay._blocks == expected
    overlay._start_block_translation.assert_not_called()


def test_seeded_duplicate_labels_always_use_only_current_boxes_and_scripts():
    state = LiveTextState(stable_after=0)
    seeded = random.Random(202611065)
    words = ['Open', 'باب', '水', '火', '保存', 'Settings']
    for frame in range(80):
        slots = seeded.sample(range(30), seeded.randint(0, 12))
        lines = [(10 + (slot % 5) * 200, 20 + (slot // 5) * 50, 160, 24, seeded.choice(words))
                 for slot in slots]
        state.observe(lines, frame)
        state.remember((word, 'translation:' + word) for word in words)
        assert state.blocks() == [(*item, 'translation:' + item[4]) for item in lines]


@pytest.mark.parametrize('transition', ['ordinary', 'empty', 'reset'])
def test_direct_frame_snapshot_clears_without_polluting_the_normal_text_cache(transition):
    state = LiveTextState()
    state.remember([('Cached label', 'TEXT CACHE')])
    duplicates = [(10, 10, 100, 24, 'Open'), (300, 100, 100, 24, 'Open')]
    state.observe(duplicates, 0, translations=['DIRECT LEFT', 'DIRECT RIGHT'])
    assert [item[5] for item in state.blocks()] == ['DIRECT LEFT', 'DIRECT RIGHT']
    assert not state.pending(10) and not state.settling(10)
    if transition == 'empty':
        state.observe([], 1)
        assert not state.blocks() and not state.pending(1)
    elif transition == 'reset':
        state.reset_visible()
        assert not state.blocks() and not state.pending(1)
    current = [(500, 200, 100, 24, 'Open'), (10, 300, 150, 24, 'Cached label')]
    state.observe(current, 2)
    state.observe(current, 2.2)
    assert state.blocks() == [(*current[1], 'TEXT CACHE')]
    assert state.pending(2.2) == ['Open']


@pytest.mark.parametrize('outside_first', [False, True])
def test_clipping_a_direct_duplicate_keeps_the_visible_boxes_own_translation(live_overlays, outside_first):
    overlay = live_overlays(fullscreen=True, direct=True)
    overlay._start_block_translation = mock.Mock()
    inside = (10, 10, 100, 24, 'Open')
    outside = (overlay.width() + 100, 10, 100, 24, 'Open')
    lines = VisionLayout([outside, inside] if outside_first else [inside, outside])
    lines.translations = ['OFFSCREEN', 'VISIBLE'] if outside_first else ['VISIBLE', 'OFFSCREEN']
    worker = start_ocr(overlay, True)
    worker.result_ready.emit(lines)
    worker.finished.emit()
    assert overlay._blocks == [(*inside, 'VISIBLE')]
    overlay._start_block_translation.assert_not_called()


@pytest.mark.parametrize('source,target,provider', [('en', 'ru', 'Google'), ('ja', 'en', 'Bing'), ('en', 'ar', 'Google')])
def test_a_new_dynamic_language_provider_session_starts_without_old_semantic_cache(
        live_overlays, source, target, provider):
    previous = live_overlays(fullscreen=True)
    previous._live.observe([(10, 10, 100, 24, 'Open')], 0)
    previous._live.remember([('Open', 'PREVIOUS SESSION')])
    previous.close()
    previous.config['translator_engine'] = provider
    current = live_overlays(fullscreen=True, source=source, target=target)
    current._live.observe([(10, 10, 100, 24, 'Open')], 0)
    assert not current._live.blocks()
    assert current.source_language == source and current.target_language == target
    assert current.engine == provider
