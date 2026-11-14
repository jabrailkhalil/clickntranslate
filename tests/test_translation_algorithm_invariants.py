"""Bounded seeded and fault checks for translation/OCR data ownership."""
from collections import Counter
import json
from pathlib import Path
import random
import re
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

import api_providers as api
import cache_manager
import main
import ocr_paragraphs
import translater
from test_argos_components import installation
from test_translation_chunks import isolated_translation
from translation_chunks import split_text


def managed_argos(generation, model='b'):
    return {'receipt': {'generation': generation, 'files': [
        {'sha256': 'a' * 64, 'kind': 'zip', 'destination': 'runtime'},
        {'sha256': model * 64, 'kind': 'zip', 'destination': 'models/en__ru'},
    ]}}


def test_argos_model_update_retranslates_instead_of_returning_the_old_result(isolated_translation, monkeypatch):
    current = {'runtime': managed_argos('first')}
    monkeypatch.setattr(translater, '_managed_argos_runtime', lambda: current['runtime'])
    monkeypatch.setattr(translater, 'argos_runtime_available', lambda: True)
    calls = []

    def translate(*args, **kwargs):
        calls.append(current['runtime']['receipt']['generation'])
        return 'Result from ' + calls[-1]

    monkeypatch.setattr(translater, '_try_argos_translate', translate)
    assert translater.translate_text('Same text', 'en', 'ru', engine='argos') == 'Result from first'
    current['runtime'] = managed_argos('second', model='c')
    assert translater.translate_text('Same text', 'en', 'ru', engine='argos') == 'Result from second'
    assert calls == ['first', 'second']


@pytest.mark.parametrize('segment', [False, True])
def test_argos_cache_is_bound_to_approved_bytes_and_the_original_operation(isolated_translation, monkeypatch, segment):
    current = {'runtime': managed_argos('first')}
    monkeypatch.setattr(translater, '_managed_argos_runtime', lambda: current['runtime'])
    first = translater._TranslationCache('en', 'ru')
    first.save('Same text', 'Old model result', 'argos', segment=segment)
    # Reinstall/rollback UUID alone does not change the approved runtime/model.
    current['runtime'] = managed_argos('second')
    assert translater._TranslationCache('en', 'ru').get('Same text', 'argos', segment=segment) == 'Old model result'
    current['runtime'] = managed_argos('third', model='c')
    third = translater._TranslationCache('en', 'ru')
    assert third.get('Same text', 'argos', segment=segment) is None
    third.save('Same text', 'New model result', 'argos', segment=segment)
    assert first.get('Same text', 'argos', segment=segment) == 'Old model result'
    assert translater._TranslationCache('en', 'ar').get('Same text', 'argos', segment=segment) is None


def test_argos_runtime_selected_for_cache_lookup_remains_leased_through_the_request(installation, monkeypatch, tmp_path):
    from component_store import _MAINTENANCE_DONE
    root, catalog, _downloads, install = installation
    first = install(pairs=[('en', 'ru')])
    cache_manager.invalidate_translation_cache()
    monkeypatch.setattr(main, 'get_data_file', lambda name: str(tmp_path / name))
    monkeypatch.setattr(translater, 'get_cached_translator_config', lambda: {})
    original_get = translater._TranslationCache.get
    switched = False

    def update(revision):
        catalog['bundles'].append(dict(catalog['bundles'][0], id=f'argos-r{revision}', revision=revision))
        install()

    def get_then_update(cache, text, engine, segment=False):
        nonlocal switched
        result = original_get(cache, text, engine, segment)
        if not switched:
            switched = True
            update(2)
        return result

    def worker(request, *args, **kwargs):
        runtime = args[-1]
        assert runtime['receipt']['generation'] == first['receipt']['generation']
        update(3)  # The first generation now needs its live translation lease.
        assert first['folder'].is_dir()
        return {'result': 'Translated by the originally selected runtime', 'error': ''}

    monkeypatch.setattr(translater._TranslationCache, 'get', get_then_update)
    monkeypatch.setattr(translater, '_run_argos_worker_request_inner', worker)
    try:
        assert translater.translate_text('Private fixture', 'en', 'ru', engine='argos') == 'Translated by the originally selected runtime'
        assert _MAINTENANCE_DONE.wait(3)
        assert not first['folder'].exists()
    finally:
        cache_manager.invalidate_translation_cache()


def test_argos_document_model_change_between_chunks_never_mixes_or_relabels_cached_results(isolated_translation, monkeypatch):
    root = isolated_translation / 'components'
    current = {'runtime': managed_argos('first')}
    for generation in ('first', 'second'):
        (root / 'generations' / generation).mkdir(parents=True)
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR', str(root))
    monkeypatch.setattr(translater, '_managed_argos_runtime', lambda: current['runtime'])
    monkeypatch.setattr(translater, '_argos_document_worker_supported', lambda: True)
    calls = []

    def worker(request, *args, chunk_callback, **kwargs):
        runtime = args[-1]
        generation = runtime['receipt']['generation']
        calls.append(generation)
        for piece in request['pieces']:
            chunk_callback({'index': piece['index'], 'text': generation + ':' + piece['text']})
            if generation == 'first':
                current['runtime'] = managed_argos('second', model='c')
        return {'completed': len(request['pieces']), 'error': ''}

    monkeypatch.setattr(translater, '_run_argos_worker_request_inner', worker)
    texts = ['one', 'two', 'three', 'four']
    first = list(translater.iter_translate_texts(texts, 'en', 'ru', engine='argos'))
    second = list(translater.iter_translate_texts(texts, 'en', 'ru', engine='argos'))
    assert first == [(i, 'first:' + text, '') for i, text in enumerate(texts)]
    assert second == [(i, 'second:' + text, '') for i, text in enumerate(texts)]
    assert list(translater.iter_translate_texts(texts, 'en', 'ru', engine='argos')) == second
    assert calls == ['first', 'second']


@pytest.mark.parametrize('segment', [False, True])
def test_legacy_argos_retains_its_existing_cache_namespace(isolated_translation, monkeypatch, segment):
    monkeypatch.setattr(translater, '_managed_argos_runtime', lambda: None)
    operation = translater._TranslationCache('en', 'ru')
    operation.save('Legacy fixture', 'Legacy result', 'argos', segment=segment)
    assert operation._bound_engine_key('argos', segment) == ('segment-v2:' if segment else '') + 'argos'
    assert translater._TranslationCache('en', 'ru').get('Legacy fixture', 'argos', segment=segment) == 'Legacy result'


@pytest.mark.parametrize('document', [False, True])
@pytest.mark.parametrize('legacy_worker', [False, True])
def test_bound_unmanaged_argos_does_not_switch_to_newly_installed_managed_worker(monkeypatch, tmp_path, document, legacy_worker):
    import platform_support
    root = tmp_path / 'components'
    managed = managed_argos('second', model='c')
    managed.update(command=['managed-b-python', 'managed-b-adapter'], folder=root / 'generations' / 'second')
    managed['folder'].mkdir(parents=True)
    executable = tmp_path / 'app' / 'ClicknTranslateApp.exe'
    legacy = executable.parent / '_internal' / platform_support.executable_name('ArgosWorker')
    if legacy_worker:
        legacy.parent.mkdir(parents=True)
        legacy.write_text('unlaunched fixture', encoding='utf-8')
    monkeypatch.setattr(translater.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(translater.sys, 'executable', str(executable))
    monkeypatch.delenv('CLICKNTRANSLATE_ARGOS_WORKER', raising=False)
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR', str(root))
    monkeypatch.setattr(main, 'get_data_file', lambda name: str(tmp_path / name))
    monkeypatch.setattr(translater, 'get_cached_translator_config', lambda: {})
    current = {'runtime': None}
    monkeypatch.setattr(translater, '_managed_argos_runtime', lambda: current['runtime'])
    monkeypatch.setattr(translater, 'argos_runtime_available', lambda: True)
    monkeypatch.setattr(translater, '_argos_document_worker_supported',
                        lambda: bool(current['runtime']) or legacy_worker)
    commands, local = [], []

    def local_translate(text, *args, **kwargs):
        local.append(text)
        return 'legacy:' + text

    monkeypatch.setattr(translater, '_try_argos_translate_local', local_translate)

    def spawn(command, **kwargs):
        commands.append(command)
        request = json.loads(Path(command[-1]).read_text(encoding='utf-8'))
        label = 'managed' if command[0] == 'managed-b-python' else 'legacy'
        if request['action'] == 'translate_chunks':
            events = [{'type': 'chunk', 'index': piece['index'], 'text': label + ':' + piece['text']}
                      for piece in request['pieces']]
            Path(request['event_path']).write_text(''.join(json.dumps(event) + '\n' for event in events), encoding='utf-8')
            result = {'completed': len(events), 'error': ''}
        else:
            result = {'result': label + ':' + request['text'], 'error': ''}
        kwargs['stdout'].write(json.dumps(result))
        return SimpleNamespace(poll=lambda: 0, wait=lambda **_kwargs: 0)

    monkeypatch.setattr(translater.subprocess, 'Popen', spawn)
    cache_manager.invalidate_translation_cache()
    original_get = translater._TranslationCache.get
    switched = False

    def get_then_install(cache, text, engine, segment=False):
        nonlocal switched
        result = original_get(cache, text, engine, segment)
        if not switched:
            switched = True
            current['runtime'] = managed
        return result

    texts = ['cached', 'pending'] if document else ['pending']
    try:
        if document:
            translater._TranslationCache('en', 'ru').save('cached', 'legacy:cached', 'argos')
        monkeypatch.setattr(translater._TranslationCache, 'get', get_then_install)
        if document:
            first = list(translater.iter_translate_texts(texts, 'en', 'ru', engine='argos'))
            assert first == [(i, 'legacy:' + text, '') for i, text in enumerate(texts)]
        else:
            assert translater.translate_text(texts[0], 'en', 'ru', engine='argos') == 'legacy:' + texts[0]
        if legacy_worker:
            assert commands[0][0] == str(legacy)
            assert not local
        else:
            assert not commands and local == ['pending']
        second = list(translater.iter_translate_texts(texts, 'en', 'ru', engine='argos'))
        assert second == [(i, 'managed:' + text, '') for i, text in enumerate(texts)]
        assert commands[-1][0] == 'managed-b-python'
    finally:
        cache_manager.invalidate_translation_cache()


@pytest.mark.parametrize('change', ['endpoint', 'model', 'key'])
def test_api_document_keeps_one_connection_snapshot_between_streamed_pieces(isolated_translation, monkeypatch, change):
    config = {'api_providers': {'openai-compatible': {'model': 'first-model', 'url': 'https://first.example.test/v1'}}}
    key = {'current': 'first-test-key'}
    monkeypatch.setattr(translater, 'get_cached_translator_config', lambda: config)
    monkeypatch.setattr(api, 'credential', lambda *_: key['current'])
    calls = []

    def translate(provider, text, source, target, settings, cancel, *, api_key):
        profile = settings['api_providers'][provider]
        calls.append((text, source, target, profile['url'], profile['model'], api_key))
        return text.upper()

    monkeypatch.setattr(api, 'translate', translate)
    operation = translater.iter_translate_texts(['one', 'two'], 'en', 'ar', engine='openai-compatible')
    assert next(operation) == (0, 'ONE', '')
    if change == 'endpoint':
        config['api_providers']['openai-compatible']['url'] = 'https://second.example.test/v1'
    elif change == 'model':
        config['api_providers']['openai-compatible']['model'] = 'second-model'
    else:
        key['current'] = 'second-test-key'
    assert list(operation) == [(1, 'TWO', '')]
    assert all(call[3:] == ('https://first.example.test/v1', 'first-model', 'first-test-key') for call in calls)
    # A new operation must see the edited connection and miss the first cache.
    assert list(translater.iter_translate_texts(['one'], 'en', 'ar', engine='openai-compatible')) == [(0, 'ONE', '')]
    assert len(calls) == 3


@pytest.mark.parametrize('seed', [63, 811, 20261106])
def test_seeded_unicode_chunk_plan_is_lossless_and_stays_inside_both_budgets(seed):
    randomizer = random.Random(seed)
    symbols = list('abc. !?\r\n\t\0') + ['مرحبا', '中文', '🙂', 'e\u0301', '\u200d', '\ufeff', '\u00ad']
    for _ in range(100):
        source = ''.join(randomizer.choice(symbols) for _ in range(randomizer.randrange(1, 90)))
        byte_budget = randomizer.randrange(4, 72)
        char_budget = randomizer.randrange(1, 40)
        parts = split_text(source, max_bytes=byte_budget, max_chars=char_budget)
        assert ''.join(parts) == source
        assert all(part and len(part) <= char_budget and len(part.encode('utf-8')) <= byte_budget for part in parts)


@pytest.mark.parametrize('seed', [67, 911, 20261106])
def test_seeded_ocr_geometry_retains_each_text_fragment_once(seed):
    randomizer = random.Random(seed)
    rows = []
    for i in range(48):
        text = ('مقطع' if i % 3 == 0 else 'fragment') + f'_{i:03d}'
        geometry = (randomizer.randrange(-200, 400), randomizer.randrange(0, 20) * 15,
                    randomizer.randrange(4, 80), randomizer.randrange(8, 25))
        if i % 11 == 0:
            geometry = (None, None, None, None)
        elif i % 13 == 0:
            geometry = (float('nan'), 0, 10, 10)
        rows.append((*geometry, text))
    randomizer.shuffle(rows)
    actual = ocr_paragraphs.paragraph_text(rows)
    assert Counter(re.findall(r'(?:fragment|مقطع)_\d{3}', actual)) == Counter(row[4] for row in rows)


@pytest.mark.parametrize('fault', ['wrong_index', 'duplicate_index', 'missing_text', 'early_eof'])
def test_argos_mapping_fault_keeps_completed_and_cached_pieces_without_shifting(monkeypatch, fault):
    save = mock.Mock()
    cache = SimpleNamespace(get=lambda text, _engine: 'cached' if text == 'existing' else None, save=save)

    def request(payload, *, chunk_callback, **kwargs):
        chunk_callback({'index': 0, 'text': 'FIRST'})
        if fault == 'wrong_index':
            chunk_callback({'index': 4, 'text': 'WRONG'})
        elif fault == 'duplicate_index':
            chunk_callback({'index': 0, 'text': 'WRONG'})
        elif fault == 'missing_text':
            chunk_callback({'index': 2})
        return {'completed': 1, 'error': ''}

    monkeypatch.setattr(translater, '_run_argos_worker_request', request)
    values = list(translater._iter_argos_document(['first', 'existing', 'third', 'fourth'],
                                                 'en', 'ru', cache, None, None))
    assert values[:2] == [(0, 'FIRST', ''), (1, 'cached', '')]
    assert all(not text and error for _index, text, error in values[2:])
    save.assert_called_once_with('first', 'FIRST', 'argos')


@pytest.mark.parametrize('cancel', [False, True])
def test_argos_stream_close_or_cancel_stops_a_backpressured_producer(monkeypatch, cancel):
    worker_stopped = threading.Event()
    cancelled = threading.Event()
    cache = SimpleNamespace(get=lambda *_: None, save=lambda *_: None)

    def request(payload, *, chunk_callback, cancel_callback, **kwargs):
        try:
            for piece in payload['pieces']:
                translater._check_translation_cancelled(cancel_callback)
                chunk_callback({'index': piece['index'], 'text': piece['text'].upper()})
            return {'completed': len(payload['pieces']), 'error': ''}
        finally:
            worker_stopped.set()

    monkeypatch.setattr(translater, '_run_argos_worker_request', request)
    operation = translater._iter_argos_document([str(i) for i in range(30)],
        'en', 'ru', cache, None, cancelled.is_set)
    assert next(operation) == (0, '0', '')
    if cancel:
        cancelled.set()
        with pytest.raises(translater.TranslationCancelledError):
            next(operation)
    else:
        operation.close()
    assert worker_stopped.wait(1)
