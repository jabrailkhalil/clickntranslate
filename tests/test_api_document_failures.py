"""API document failures retain completed work without useless billed requests."""
import json
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

import api_providers as api
import document_translation as documents
import translater
from test_translation_chunks import isolated_translation


@pytest.fixture
def api_config(isolated_translation, monkeypatch):
    config = {'interface_language': 'ru', 'api_providers': {
        item.key: {'model': 'test-model', 'url': item.url or 'https://custom.test/v1'}
        for item in api.PROVIDERS}}
    monkeypatch.setattr(translater, 'get_cached_translator_config', lambda: config)
    monkeypatch.setattr(api, 'credential', lambda *args: 'test-secret')
    return config


def response(status, translated='translated'):
    result = mock.MagicMock(status_code=status)
    result.__enter__.return_value = result
    # OpenAI Responses success, never a real server or response body.
    payload = {'status': 'completed', 'output': [{'type': 'message', 'content': [
        {'type': 'output_text', 'text': translated}]}]}
    result.iter_content.return_value = [json.dumps(payload).encode()]
    result.text = 'private echoed content and test-secret'
    return result


@pytest.mark.parametrize('provider', ['openai', 'openai-compatible', 'gemini', 'anthropic', 'deepl'])
@pytest.mark.parametrize('status', [401, 403, 429])
def test_blocked_connection_stops_remaining_api_document_requests(api_config, provider, status):
    post = mock.Mock(return_value=response(status))
    with mock.patch.object(api, '_session', return_value=mock.Mock(post=post)):
        results = list(translater.iter_translate_texts(
            ['First paragraph.', 'Second paragraph.', 'Third paragraph.'], 'en', 'ar', engine=provider))
    assert post.call_count == 1
    assert [item[0] for item in results] == [0, 1, 2]
    assert all(not item[1] and item[2] for item in results)
    assert len({item[2] for item in results}) == 1
    assert all('test-secret' not in item[2] and 'private' not in item[2] for item in results)


@pytest.mark.parametrize('language', ['en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id'])
@pytest.mark.parametrize('status', [401, 403, 429, 503])
def test_localized_api_failure_preserves_http_status(api_config, status, language):
    api_config['interface_language'] = language
    with mock.patch.object(api, '_session', return_value=mock.Mock(post=mock.Mock(return_value=response(status)))):
        with pytest.raises(api.ProviderError) as error:
            translater.translate_text('A paragraph.', 'en', 'ar', engine='openai')
    assert error.value.status_code == status
    assert str(error.value) and 'test-secret' not in str(error.value)
    if language == 'ru':
        assert {401: 'ключ', 403: 'Ошибка API', 429: 'лимит', 503: 'Ошибка API'}[status] in str(error.value)


def test_quota_failure_keeps_completed_and_cached_pieces_without_sending_the_tail(api_config):
    texts = ['First paragraph.', 'Quota exhausted.', 'Cached paragraph.', 'Unsent paragraph.']
    cache = translater._TranslationCache('en', 'ar')
    cache.save(texts[2], 'cached result', 'openai')
    post = mock.Mock(side_effect=[response(200, 'completed result'), response(429)])
    with mock.patch.object(api, '_session', return_value=mock.Mock(post=post)):
        results = list(translater.iter_translate_texts(texts, 'en', 'ar', engine='openai'))
    assert post.call_count == 2
    assert results[0] == (0, 'completed result', '')
    assert results[2] == (2, 'cached result', '')
    assert results[1][1] == results[3][1] == ''
    assert results[1][2] == results[3][2] and results[1][2]
    assert cache.get(texts[0], 'openai') == 'completed result'
    assert cache.get(texts[1], 'openai') is None
    assert cache.get(texts[3], 'openai') is None


def test_transient_api_failure_does_not_prevent_later_document_pieces(api_config):
    post = mock.Mock(side_effect=[response(503), response(200, 'next paragraph')])
    with mock.patch.object(api, '_session', return_value=mock.Mock(post=post)):
        results = list(translater.iter_translate_texts(['First.', 'Second.'], 'en', 'ar', engine='openai'))
    assert post.call_count == 2
    assert results[0][2]
    assert results[1] == (1, 'next paragraph', '')


def test_document_failure_retains_all_source_chunks_and_reports_partial_success(api_config):
    source = 'First paragraph.\n\nSecond paragraph.\n\nThird paragraph.'
    post = mock.Mock(side_effect=[response(200, 'completed'), response(429)])
    with mock.patch.object(api, '_session', return_value=mock.Mock(post=post)):
        translated, results = documents.translate_document_text(source, 'en', 'ar',
            provider_engine='openai', max_chars=20)
    assert ''.join(item.source_text for item in results) == source
    assert results[0].translated_text.strip() == 'completed' and not results[0].error
    assert all(item.error for item in results[1:])
    assert translated.startswith('completed')
    assert post.call_count == 2


def test_api_cancellation_stops_before_sending_the_next_piece(api_config):
    cancelled = threading.Event()
    post = mock.Mock(return_value=response(200, 'completed'))
    with mock.patch.object(api, '_session', return_value=mock.Mock(post=post)):
        iterator = translater.iter_translate_texts(['First.', 'Second.'], 'en', 'ar', engine='openai',
                                                  cancel_callback=cancelled.is_set)
        assert next(iterator) == (0, 'completed', '')
        cancelled.set()
        with pytest.raises(translater.TranslationCancelledError):
            next(iterator)
    assert post.call_count == 1


def test_whitespace_after_quota_failure_is_retained_without_an_error(api_config):
    post = mock.Mock(return_value=response(429))
    with mock.patch.object(api, '_session', return_value=mock.Mock(post=post)):
        results = list(translater.iter_translate_texts(['First.', '', '\n\t', 'Unsent.'],
                       'en', 'ar', engine='openai'))
    assert results[1] == (1, '', '')
    assert results[2] == (2, '\n\t', '')
    assert results[0][2] and results[3][2]
    assert post.call_count == 1


def test_cancellation_during_quota_failure_is_not_reported_as_a_provider_error(api_config):
    cancelled = threading.Event()

    def reject(*args, **kwargs):
        cancelled.set()
        return response(429)

    post = mock.Mock(side_effect=reject)
    with mock.patch.object(api, '_session', return_value=mock.Mock(post=post)):
        with pytest.raises(translater.TranslationCancelledError):
            list(translater.iter_translate_texts(['First.', 'Unsent.'], 'en', 'ar', engine='openai',
                                                cancel_callback=cancelled.is_set))
    assert post.call_count == 1


@pytest.mark.parametrize('status', [401, 403, 429])
def test_libre_connection_rejection_stops_remaining_document_batches(api_config, status):
    post=mock.Mock(return_value=SimpleNamespace(status_code=status,text='',
                                               json=lambda:{'error':'Connection unavailable'}))
    with mock.patch.object(translater,'_get_http_session',return_value=SimpleNamespace(post=post)):
        results=list(translater.iter_translate_texts([f'Paragraph {i}' for i in range(12)],
                                                    'en','ar',engine='libretranslate'))
    assert post.call_count==1
    assert len(results)==12 and all(item[2] for item in results)


@pytest.mark.parametrize('change', ['model', 'key'])
def test_response_in_flight_cannot_poison_the_new_connection_cache(api_config, monkeypatch, change):
    keys={'current':'old-secret'}
    monkeypatch.setattr(api,'credential',lambda *args:keys['current'])
    def old_request(*args,**kwargs):
        assert kwargs['json']['model']=='test-model'
        assert kwargs['headers']['Authorization']=='Bearer old-secret'
        if change=='model':
            api_config['api_providers']['openai']['model']='new-model'
        else:
            keys['current']='new-secret'
        return response(200,'old connection result')
    post=mock.Mock(side_effect=old_request)
    with mock.patch.object(api,'_session',return_value=mock.Mock(post=post)):
        assert translater.translate_text('Same paragraph.','en','ar',engine='openai')=='old connection result'
        post.side_effect=None
        post.return_value=response(200,'new connection result')
        assert translater.translate_text('Same paragraph.','en','ar',engine='openai')=='new connection result'
    assert post.call_count==2
