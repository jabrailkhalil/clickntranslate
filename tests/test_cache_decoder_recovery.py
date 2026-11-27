"""Corrupt disposable JSON cannot disable reuse of successful translations."""
import json
import threading
from unittest.mock import Mock

import pytest

import cache_manager as cache
import translater
from test_translation_chunks import isolated_translation


@pytest.fixture
def cache_case(isolated_translation, monkeypatch):
    root = isolated_translation
    path = root / 'cache' / cache.TRANSLATION_CACHE_FILE
    path.parent.mkdir()
    protected = {'config.json': b'{"profile":"keep"}', 'translation_history.json': b'[]'}
    for name, contents in protected.items():
        (root / name).write_bytes(contents)
    workers = []
    original = threading.Thread

    def writer(*args, **kwargs):
        thread = original(*args, **kwargs)
        workers.append(thread)
        return thread

    monkeypatch.setattr(cache.threading, 'Thread', writer)
    yield root, path, workers
    for worker in workers:
        worker.join(5)
        assert not worker.is_alive()
    for name, contents in protected.items():
        assert (root / name).read_bytes() == contents


def nested(kind):
    # 10–50KiB fixtures exceed the decoder's protected nesting bound, without
    # changing Python recursion settings or exhausting memory/stack resources.
    return '[' * 5000 + '0' + ']' * 5000 if kind == 'array' else '{"entry":' * 5000 + '0' + '}' * 5000


@pytest.mark.parametrize('kind', ['array', 'object'])
def test_decoder_recursion_is_a_recoverable_cache_miss(cache_case, kind):
    root, path, workers = cache_case
    path.write_text(nested(kind), encoding='utf-8')
    assert cache.get_cached_translation(str(root), 'Source', 'en', 'ru', 'google') is None
    assert cache._load_translation_cache(str(root)) == {}


@pytest.mark.parametrize('kind', ['array', 'object'])
def test_successful_translation_repairs_cache_and_survives_a_cold_reload(cache_case, monkeypatch, kind):
    root, path, workers = cache_case
    path.write_text(nested(kind), encoding='utf-8')
    provider = Mock(return_value='Translated')
    monkeypatch.setattr(translater, '_google_translate_chunk', provider)
    assert translater.translate_text('Source', 'en', 'ru', engine='google') == 'Translated'
    assert translater.translate_text('Source', 'en', 'ru', engine='google') == 'Translated'
    for worker in workers:
        worker.join(5)
        assert not worker.is_alive()
    assert isinstance(json.loads(path.read_text(encoding='utf-8')), dict)
    cache.invalidate_translation_cache()
    assert translater.translate_text('Source', 'en', 'ru', engine='google') == 'Translated'
    provider.assert_called_once()


def test_deep_looking_literal_text_is_not_rejected_or_shortened(cache_case):
    root, path, workers = cache_case
    translated = '[' * 5000 + 'literal' + ']' * 5000
    key = cache._translation_cache_key('Source', 'en', 'ru', 'google')
    path.write_text(json.dumps({key: {'translated': translated}}), encoding='utf-8')
    assert cache.get_cached_translation(str(root), 'Source', 'en', 'ru', 'google') == translated


def test_unwritable_cache_still_reuses_a_successful_in_memory_result(cache_case, monkeypatch):
    root, path, workers = cache_case
    monkeypatch.setattr(cache, 'get_cache_dir', Mock(side_effect=PermissionError('audit-only read-only cache')))
    provider = Mock(return_value='Translated')
    monkeypatch.setattr(translater, '_google_translate_chunk', provider)
    assert translater.translate_text('Source', 'en', 'ru', engine='google') == 'Translated'
    assert translater.translate_text('Source', 'en', 'ru', engine='google') == 'Translated'
    provider.assert_called_once()
