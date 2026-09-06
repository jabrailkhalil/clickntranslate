"""Request boundaries, resume behavior and cancellation, without live services."""
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

import cache_manager
import document_translation as documents
import main
import translater
from translation_chunks import provider_chunks, split_text


@pytest.mark.parametrize('text', [
    '  Первый абзац. В нём два предложения!\r\n\r\nВторой абзац?  ' * 80,
    '你好世界。这是第二句话！真的吗？没有空格。' * 120,
    '🙂🌍 hello\tworld\n' * 200, 'word ' * 2000, 'x' * 7000,
    ' \n\t ' * 1000, 'e\u0301👩\u200d💻' * 400,
])
@pytest.mark.parametrize('limit', [4, 17, 500, 1500])
def test_chunks_are_lossless_and_obey_both_limits(text, limit):
    chunks = split_text(text, max_bytes=limit, max_chars=111)
    assert ''.join(chunks) == text
    assert all(chunk and len(chunk.encode('utf-8')) <= limit and len(chunk) <= 111 for chunk in chunks)


def test_whole_sentences_are_kept_together_when_they_fit():
    first = 'First complete sentence. '
    second = 'Second complete sentence. '
    assert split_text(first + second + 'Last.', max_bytes=39) == [first, second + 'Last.']
    assert split_text('你好世界。这是第二句话！结束。', max_bytes=30) == ['你好世界。', '这是第二句话！结束。']


def test_paragraphs_take_priority_and_no_separator_is_invented():
    first = 'First sentence. More.\n\n'
    second = 'A second paragraph with two sentences. Yes.'
    chunks = split_text(first + second, max_chars=50)
    assert chunks == [first, second]
    assert split_text('a' * 25, max_chars=10) == ['a' * 10, 'a' * 10, 'a' * 5]


def test_abbreviations_and_decimals_do_not_create_false_sentence_ends():
    text = 'Done. Dr. Smith measured 3.14 meters. End.'
    assert split_text(text, max_chars=18)[0] == 'Done. '
    text = 'Done. Version 3.14159 remains unchanged.'
    assert split_text(text, max_chars=16)[0] == 'Done. '


@pytest.mark.parametrize('kwargs', [{'max_bytes': 0}, {'max_chars': -1}, {'max_bytes': 2.5}, {'max_chars': True}, {}])
def test_invalid_limits_fail_instead_of_looping(kwargs):
    with pytest.raises(ValueError):
        split_text('hello', **kwargs)


def test_too_small_byte_limit_for_unicode_fails_cleanly():
    with pytest.raises(ValueError):
        split_text('🙂', max_bytes=3)


@pytest.fixture
def isolated_translation(monkeypatch, tmp_path):
    cache_manager.invalidate_translation_cache()
    monkeypatch.setattr(main, 'get_data_file', lambda name: str(tmp_path / name))
    monkeypatch.setattr(translater, 'get_cached_translator_config', lambda: {'translator_engine': 'google'})
    monkeypatch.setattr(translater, '_try_argos_translate', lambda *args, **kwargs: None)
    monkeypatch.delenv('CLICKNTRANSLATE_LIBRETRANSLATE_API_KEY', raising=False)
    monkeypatch.delenv('CLICKNTRANSLATE_LIBRETRANSLATE_URL', raising=False)
    yield tmp_path
    cache_manager.invalidate_translation_cache()


@pytest.mark.parametrize('engine,raw_function', [('google', '_google_translate_chunk'), ('mymemory', '_mymemory_translate_chunk')])
def test_document_requests_match_the_shared_plan_once(engine, raw_function, isolated_translation, monkeypatch):
    text = '  Вступление.\n\n' + ''.join(f'Это предложение номер {i}, содержащее несколько слов. ' for i in range(130)) + '\n\nКонец.  '
    calls, progress = [], []

    def identity(value, *args, **kwargs):
        calls.append(value)
        return value

    monkeypatch.setattr(translater, raw_function, identity)
    result, pieces = documents.translate_document_text(text, 'ru', 'en', provider_engine=engine,
        progress_callback=lambda done, total, message: progress.append((done, total)))
    expected = provider_chunks(text, engine)
    assert result == text
    assert [piece.source_text for piece in pieces] == expected
    assert calls == [chunk.strip() for chunk in expected]
    assert progress[-1] == (len(expected), len(expected))


def test_retry_plain_text_only_resends_the_failed_and_untranslated_parts(isolated_translation, monkeypatch):
    text = ''.join(f'Sentence {i} has some words and a final stop. ' for i in range(90))
    chunks = provider_chunks(text, 'mymemory')
    calls = []

    def fail_second(value, *args):
        calls.append(value)
        if len(calls) == 2:
            raise RuntimeError('Temporary outage')
        return value

    monkeypatch.setattr(translater, '_mymemory_translate_chunk', fail_second)
    with pytest.raises(RuntimeError, match='outage'):
        translater.translate_text(text, 'en', 'ru', engine='mymemory')
    assert translater.translate_text(text, 'en', 'ru', engine='mymemory') == text
    assert calls.count(chunks[0].strip()) == 1
    assert calls.count(chunks[1].strip()) == 2


def test_document_retry_reuses_successful_parts_and_keeps_paragraphs(isolated_translation, monkeypatch):
    text = '\n\n'.join(f'Paragraph {i}. ' + ('meaningful words ' * 30) for i in range(8))
    calls = []

    def fail_second(value, *args, **kwargs):
        calls.append(value)
        if len(calls) == 2:
            raise RuntimeError('Temporary outage')
        return value

    monkeypatch.setattr(translater, '_google_translate_chunk', fail_second)
    _, failed = documents.translate_document_text(text, 'en', 'ru', provider_engine='google')
    initial_calls = len(calls)
    assert sum(bool(item.error) for item in failed) == 1
    translated, results = documents.translate_document_text(text, 'en', 'ru', provider_engine='google')
    assert translated == text
    assert not any(item.error for item in results)
    assert len(calls) == initial_calls + 1


def test_cancel_stops_requests_and_does_not_start_fallback(isolated_translation, monkeypatch):
    cancel = threading.Event()
    text = 'An entire sentence. ' * 150
    calls = []

    def translate(value, *args, **kwargs):
        calls.append(value)
        cancel.set()
        return value

    monkeypatch.setattr(translater, '_google_translate_chunk', translate)
    rescue = mock.Mock()
    monkeypatch.setattr(translater, '_try_argos_translate', rescue)
    partial, results = documents.translate_document_text(text, 'en', 'ru', provider_engine='google', cancel_event=cancel)
    assert len(calls) == len(results) == 1
    assert partial == provider_chunks(text, 'google')[0]
    assert not results[0].error
    rescue.assert_not_called()


def test_cancellation_prevents_a_google_endpoint_retry(isolated_translation, monkeypatch):
    cancel = threading.Event()

    def request(*args, **kwargs):
        cancel.set()
        return SimpleNamespace(status_code=429)

    get = mock.Mock(side_effect=request)
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(get=get))
    with pytest.raises(translater.TranslationCancelledError):
        translater.translate_text('Hello', 'en', 'ru', engine='google', cancel_callback=cancel.is_set)
    assert get.call_count == 1


def test_batch_documents_use_fewer_requests_and_preserve_order(isolated_translation, monkeypatch):
    text = '\n\n'.join(f'Paragraph {i}. ' + ('some words ' * 80) for i in range(10))
    requests = []

    def post(url, json, timeout):
        requests.append(json['q'])
        q = json['q']
        return SimpleNamespace(status_code=200, json=lambda: {'translatedText': q})

    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(post=post))
    translated, results = documents.translate_document_text(text, 'en', 'ru', provider_engine='libretranslate')
    assert translated == text
    assert not any(result.error for result in results)
    assert len(requests) == 3
    assert [len(q) for q in requests] == [4, 4, 2]
    assert len(results) == 10
    documents.translate_document_text(text, 'en', 'ru', provider_engine='libretranslate')
    assert len(requests) == 3


def test_unsupported_batch_retries_singly_on_the_same_server(isolated_translation, monkeypatch):
    calls = []

    def post(url, json, timeout):
        calls.append((url, json))
        q = json['q']
        if isinstance(q, list):
            return SimpleNamespace(status_code=400, json=lambda: {'error': 'Batch limit is 1'})
        return SimpleNamespace(status_code=200, json=lambda: {'translatedText': q})

    monkeypatch.setenv('CLICKNTRANSLATE_LIBRETRANSLATE_URL', 'https://chosen.example.test')
    monkeypatch.setenv('CLICKNTRANSLATE_LIBRETRANSLATE_API_KEY', 'private-test-key')
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(post=post))
    results = list(translater.iter_translate_texts(['One.', 'Two.', 'Three.', 'Four.', 'Five.'], 'en', 'ru', engine='libretranslate'))
    assert [result[1] for result in results] == ['One.', 'Two.', 'Three.', 'Four.', 'Five.']
    assert len(calls) == 6
    assert sum(isinstance(payload['q'], list) for _, payload in calls) == 1
    assert all(url == 'https://chosen.example.test/translate' and payload['api_key'] == 'private-test-key' for url, payload in calls)


@pytest.mark.parametrize('status,answer', [(429, {'error': 'Slow down'}), (200, {'translatedText': ['missing item']}),
                                         (200, {'translatedText': ['One.', None]})])
def test_failed_batch_never_shifts_results_or_caches_partial_answers(status, answer, isolated_translation, monkeypatch):
    post = mock.Mock(return_value=SimpleNamespace(status_code=status, json=lambda: answer))
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(post=post))
    results = list(translater.iter_translate_texts(['One.', 'Two.'], 'en', 'ru', engine='libretranslate'))
    assert all(error and not result for _, result, error in results)
    assert post.call_count == 1
    cache = translater._TranslationCache('en', 'ru')
    assert cache.get('One.', 'libretranslate') is None


def test_cache_never_crosses_provider_or_custom_server_boundaries(isolated_translation, monkeypatch):
    cache_manager.save_cached_translation(str(isolated_translation), 'Hello', 'en', 'ru', 'Legacy unscoped result')
    cache = translater._TranslationCache('en', 'ru')
    assert cache.get('Hello', 'google') is None
    cache.save('Hello', 'From server A', 'libretranslate')
    monkeypatch.setenv('CLICKNTRANSLATE_LIBRETRANSLATE_URL', 'https://other.example.test')
    assert cache.get('Hello', 'libretranslate') is None


def test_rate_limit_stops_remaining_batches_but_keeps_cached_results(isolated_translation, monkeypatch):
    post = mock.Mock(return_value=SimpleNamespace(status_code=429, json=lambda: {'error': 'Slow down'}))
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(post=post))
    cache = translater._TranslationCache('en', 'ru')
    cache.save('Part 8.', 'Already translated.', 'libretranslate')
    results = list(translater.iter_translate_texts([f'Part {i}.' for i in range(10)], 'en', 'ru', engine='libretranslate'))
    assert post.call_count == 1
    assert len(results) == 10
    assert results[8] == (8, 'Already translated.', '')
    assert all(error for index, _, error in results if index != 8)


def test_cancel_after_batch_retains_every_received_piece_for_resume(isolated_translation, monkeypatch):
    cancel = threading.Event()
    calls = []

    def post(url, json, timeout):
        calls.append(json['q'])
        cancel.set()
        return SimpleNamespace(status_code=200, json=lambda: {'translatedText': json['q']})

    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(post=post))
    texts = [f'Part {i}.' for i in range(7)]
    results = []
    with pytest.raises(translater.TranslationCancelledError):
        for result in translater.iter_translate_texts(texts, 'en', 'ru', engine='libretranslate', cancel_callback=cancel.is_set):
            results.append(result)
    assert len(results) == 4
    assert len(calls) == 1
    cache = translater._TranslationCache('en', 'ru')
    assert all(cache.get(text, 'libretranslate') == text for text in texts[:4])


def test_batch_failure_preserves_cached_parts_without_switching_provider(isolated_translation, monkeypatch):
    monkeypatch.setattr(translater, '_libretranslate_batch', mock.Mock(side_effect=RuntimeError('Server down')))
    monkeypatch.setattr(translater, '_try_argos_translate', mock.Mock(side_effect=RuntimeError('Runtime missing')))
    cache = translater._TranslationCache('en', 'ru')
    cache.save('Cached.', 'Ready.', 'libretranslate')
    results = list(translater.iter_translate_texts(['Cached.', 'One.', 'Two.'], 'en', 'ru', engine='libretranslate'))
    assert results[0] == (0, 'Ready.', '')
    assert all('Server down' in error for _, _, error in results[1:])
    translater._try_argos_translate.assert_not_called()


@pytest.mark.parametrize('engine', ['google', 'lingva', 'mymemory', 'libretranslate'])
def test_selected_provider_failure_never_switches_even_with_legacy_fallback_enabled(engine, isolated_translation, monkeypatch):
    monkeypatch.setattr(translater, 'get_cached_translator_config', lambda: {
        'translator_engine': engine, 'allow_online_provider_fallback': True})
    functions = {'google': 'google_translate', 'lingva': 'lingva_translate',
                 'mymemory': 'mymemory_translate', 'libretranslate': 'libretranslate'}
    calls = {}
    for name, function in functions.items():
        calls[name] = mock.Mock(side_effect=RuntimeError(f'{name} unavailable'))
        monkeypatch.setattr(translater, function, calls[name])
    offline = mock.Mock(return_value='Unexpected offline translation')
    monkeypatch.setattr(translater, '_try_argos_translate', offline)
    with pytest.raises(RuntimeError, match=f'{engine} unavailable'):
        translater.translate_text('Selected engine only.', 'en', 'ru')
    assert calls[engine].call_count == 1
    assert all(call.call_count == 0 for name, call in calls.items() if name != engine)
    offline.assert_not_called()


def test_unknown_engine_does_not_use_google_or_argos(isolated_translation, monkeypatch):
    google, argos = mock.Mock(), mock.Mock()
    monkeypatch.setattr(translater, 'google_translate', google)
    monkeypatch.setattr(translater, '_try_argos_translate', argos)
    with pytest.raises(ValueError, match='Unknown translation engine'):
        translater.translate_text('Text', 'en', 'ru', engine='obsolete-engine')
    google.assert_not_called()
    argos.assert_not_called()


@pytest.mark.parametrize('invalid', ['', '  ', 42, ['wrong'], {'translated': 'wrong'}])
def test_invalid_cached_translation_is_a_cache_miss(invalid, isolated_translation, monkeypatch):
    monkeypatch.setattr(cache_manager, 'get_cached_translation', lambda *args, **kwargs: invalid)
    assert translater._TranslationCache('en', 'ru').get('Hello', 'google') is None
