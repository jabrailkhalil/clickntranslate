"""Real worker threads, corrupt cache inputs and fault-injected persistence."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import cache_manager as cache


@pytest.fixture
def cache_file(tmp_path):
    path = tmp_path / 'cache' / cache.TRANSLATION_CACHE_FILE
    path.parent.mkdir()
    yield str(tmp_path), path
    cache.invalidate_translation_cache()


@pytest.mark.parametrize('payload', [[], ['not an object'], None, 17, 'broken'])
def test_invalid_cache_root_is_a_recoverable_miss(cache_file, payload):
    directory, path = cache_file
    path.write_text(json.dumps(payload), encoding='utf-8')
    assert cache.get_cached_translation(directory, 'Hello', 'en', 'ru', 'Google') is None
    loaded = cache._load_translation_cache(directory)
    assert loaded == {}


@pytest.mark.parametrize('bad_entry', [42, ['bad'], 'bad', {'created': 1}, {'translated': 42}])
def test_bad_entry_does_not_hide_a_valid_translation(cache_file, bad_entry):
    directory, path = cache_file
    bad_key = cache._translation_cache_key('bad', 'en', 'ru', 'Google')
    good_key = cache._translation_cache_key('good', 'en', 'ru', 'Google')
    path.write_text(json.dumps({bad_key: bad_entry, good_key: {'translated': 'correct', 'accessed': 1}}), encoding='utf-8')
    assert cache.get_cached_translation(directory, 'bad', 'en', 'ru', 'Google') is None
    assert cache.get_cached_translation(directory, 'good', 'en', 'ru', 'Google') == 'correct'


def test_failed_cache_write_preserves_last_complete_json(cache_file, monkeypatch):
    directory, path = cache_file
    previous = b'{"previous":{"translated":"saved"}}'
    path.write_bytes(previous)
    loaded = cache._load_translation_cache(directory)
    def interrupted(self, value, *args, **kwargs):
        yield '{"partial":'
        raise OSError('simulated disk full')
    monkeypatch.setattr(json.JSONEncoder, 'iterencode', interrupted)
    cache._save_translation_cache(directory, loaded)
    assert path.read_bytes() == previous


def test_burst_of_translations_uses_one_pending_writer(cache_file, monkeypatch):
    directory, path = cache_file
    started = []
    thread_class = threading.Thread
    def worker(*args, **kwargs):
        thread = thread_class(*args, **kwargs)
        started.append(thread)
        return thread
    monkeypatch.setattr(cache.threading, 'Thread', worker)
    # The disk writer cannot proceed until all forty completions are queued.
    with cache._cache_lock:
        for index in range(40):
            cache.save_cached_translation(directory, str(index), 'en', 'ru', f'value {index}', 'Google')
    for thread in started:
        thread.join(5)
        assert not thread.is_alive()
    assert len(started) == 1
    data = json.loads(path.read_text(encoding='utf-8'))
    assert len(data) == 40
    for index in range(40):
        assert cache.get_cached_translation(directory, str(index), 'en', 'ru', 'Google') == f'value {index}'


def test_concurrent_reads_saves_and_lru_eviction_remain_consistent(cache_file, monkeypatch):
    directory, path = cache_file
    monkeypatch.setattr(cache, 'MAX_TRANSLATION_CACHE', 50)
    barrier = threading.Barrier(8)
    def translate(worker):
        barrier.wait(timeout=5)
        for index in range(30):
            source = f'{worker}:{index}'
            cache.save_cached_translation(directory, source, 'en', 'ru', source, 'Google')
            result = cache.get_cached_translation(directory, source, 'en', 'ru', 'Google')
            assert result in (None, source)  # Another worker may already evict it.
            assert cache.get_cached_translation(directory, source, 'en', 'ru', 'Lingva', strict_engine=True) is None
    with ThreadPoolExecutor(max_workers=8) as workers:
        futures = [workers.submit(translate, worker) for worker in range(8)]
        for result in futures:
            result.result(timeout=20)
    loaded = cache._load_translation_cache(directory)
    cache._save_translation_cache(directory, loaded)
    persisted = json.loads(path.read_text(encoding='utf-8'))
    assert len(persisted) == 50
    assert persisted == loaded


def test_clear_waits_for_active_write_and_old_generation_cannot_return(cache_file, monkeypatch):
    directory, path = cache_file
    loaded = cache._load_translation_cache(directory)
    loaded['old'] = {'translated': 'old'}
    entered, release, clearing = threading.Event(), threading.Event(), threading.Event()
    original = cache.write_json
    def paused_write(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        original(*args, **kwargs)
    monkeypatch.setattr(cache, 'write_json', paused_write)
    def clear():
        clearing.set()
        cache.clear_all_cache(directory)
    with ThreadPoolExecutor(max_workers=2) as workers:
        saving = workers.submit(cache._save_translation_cache, directory, loaded)
        try:
            assert entered.wait(5)
            removing = workers.submit(clear)
            assert clearing.wait(5)
        finally:
            release.set()
        saving.result(timeout=5)
        removing.result(timeout=5)
    assert not path.exists()
    cache._save_translation_cache(directory, loaded)
    assert not path.exists()
    cache.save_cached_translation(directory, 'new', 'en', 'ru', 'new translation', 'Google')
    replacement = cache._load_translation_cache(directory)
    cache._save_translation_cache(directory, replacement)
    cache._save_translation_cache(directory, loaded)
    assert json.loads(path.read_text(encoding='utf-8')) == replacement


@pytest.mark.parametrize('stamp', [None, {}, 'bad', float('inf'), float('nan'), 10 ** 400])
def test_corrupt_access_times_do_not_break_lru(cache_file, monkeypatch, stamp):
    directory, path = cache_file
    monkeypatch.setattr(cache, 'MAX_TRANSLATION_CACHE', 1)
    path.write_text(json.dumps({'old': {'translated': 'old', 'accessed': stamp}}), encoding='utf-8')
    cache.save_cached_translation(directory, 'new', 'en', 'ru', 'new', 'Google')
    assert cache.get_cached_translation(directory, 'new', 'en', 'ru', 'Google') == 'new'
    loaded = cache._load_translation_cache(directory)
    cache._save_translation_cache(directory, loaded)
    assert len(loaded) == 1 and 'old' not in loaded
