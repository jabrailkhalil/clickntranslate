"""Provider labels, in-band status and operation snapshots keep dispatch coherent."""
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

import api_providers as api
import document_translation as documents
import translater
from test_api_document_failures import api_config
from test_translation_chunks import isolated_translation


@pytest.mark.parametrize('name,provider', [('Claude', 'anthropic'), ('Custom API', 'openai-compatible'), ('DeepL API', 'deepl')])
@pytest.mark.parametrize('status', [401, 403, 429])
@pytest.mark.parametrize('use_label', [False, True])
def test_document_labels_preserve_completed_prefix_and_cached_tail_after_rejection(
        api_config, monkeypatch, name, provider, status, use_label):
    selected = name if use_label else provider
    source = 'First.\n\nDenied.\n\nCached.\n\nUnsent.'
    chunks = documents.split_text_chunks(source, max_chars=10, engine=provider)
    translate = mock.Mock(return_value='READY')
    monkeypatch.setattr(api, 'translate', translate)
    # Populate the cache through the same public label accepted by scalar
    # translation, then use it in a later document operation.
    assert translater.translate_text(chunks[2].text, 'en', 'ru', engine=selected) == 'READY'
    translate.reset_mock()
    translate.side_effect = ['COMPLETED', api.ProviderError('Controlled rejection', status_code=status)]
    output, results = documents.translate_document_text(source, 'en', 'ru', provider_engine=selected, max_chars=10)
    assert [result.index for result in results] == [0, 1, 2, 3]
    assert results[0].translated_text.strip() == 'COMPLETED' and not results[0].error
    assert results[2].translated_text.strip() == 'READY' and not results[2].error
    assert results[1].error and results[3].error == results[1].error
    assert output.startswith('COMPLETED') and 'READY' in output
    assert translate.call_count == 2


def response(status, text='UNEXPECTED', detail='Controlled rejection'):
    return SimpleNamespace(status_code=200, raise_for_status=lambda: None,
        json=lambda: {'responseStatus': status, 'responseDetails': detail,
                      'responseData': {'translatedText': text}})


def assert_mymemory_rejection_keeps_received_parts(monkeypatch, status):
    calls = []

    def get(_url, *, params, timeout):
        text = params['q']
        calls.append(text)
        return response(200, 'READY' if text == 'Cached.' else 'COMPLETED') if text in {'Cached.', 'First.'} else response(status)

    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(get=get))
    assert translater.translate_text('Cached.', 'en', 'ru', engine='mymemory') == 'READY'
    calls.clear()
    results = list(translater.iter_translate_texts(['First.', 'Denied.', 'Cached.', 'Unsent.'],
                                                  'en', 'ru', engine='mymemory'))
    assert calls == ['First.', 'Denied.']
    assert results[0] == (0, 'COMPLETED', '')
    assert results[2] == (2, 'READY', '')
    assert results[1][2] and results[3][2] == results[1][2]
    assert not results[1][1] and not results[3][1]


@pytest.mark.parametrize('status', [401, 403, 429])
@pytest.mark.parametrize('as_string', [False, True])
def test_mymemory_in_band_rejection_stops_dispatch_but_keeps_completed_and_cached_parts(
        api_config, monkeypatch, status, as_string):
    assert_mymemory_rejection_keeps_received_parts(monkeypatch, str(status) if as_string else status)


@pytest.mark.parametrize('status', [401.0, 403.0, 429.0])
def test_mymemory_integral_float_rejection_uses_the_existing_block_policy(api_config, monkeypatch, status):
    assert_mymemory_rejection_keeps_received_parts(monkeypatch, status)


@pytest.mark.parametrize('status', [200, '200', 200.0])
def test_mymemory_success_accepts_numeric_or_string_status_and_can_be_cached(api_config, monkeypatch, status):
    get = mock.Mock(return_value=response(status, 'READY'))
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(get=get))
    assert translater.translate_text('Source.', 'en', 'ru', engine='mymemory') == 'READY'
    assert translater.translate_text('Source.', 'en', 'ru', engine='mymemory') == 'READY'
    get.assert_called_once()


@pytest.mark.parametrize('invalid', [None, [], {}, True, False, 200.5, float('nan'), float('inf'), -float('inf'), '200.0', 'broken', ''])
def test_mymemory_malformed_status_does_not_accept_or_cache_a_translation(api_config, monkeypatch, invalid):
    get = mock.Mock(return_value=response(invalid))
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(get=get))
    with pytest.raises(Exception, match='MyMemory error: Controlled rejection') as failure:
        translater.translate_text('Source.', 'en', 'ru', engine='mymemory')
    assert translater._provider_status_code(failure.value) is None
    assert not hasattr(failure.value, 'response')
    assert translater._TranslationCache('en', 'ru').get('Source.', 'mymemory') is None
    get.assert_called_once()


@pytest.mark.parametrize('invalid', ['2_00', '4_29', '+200', '-200', '٢٠٠', '２００'],
                         ids=['success-underscore', 'quota-underscore', 'plus-sign', 'minus-sign', 'arabic-digits', 'fullwidth-digits'])
def test_mymemory_status_string_rejects_nondecimal_code_grammar(api_config, monkeypatch, invalid):
    get = mock.Mock(return_value=response(invalid))
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(get=get))
    with pytest.raises(RuntimeError, match='MyMemory error: Controlled rejection') as failure:
        translater.translate_text('Source.', 'en', 'ru', engine='mymemory')
    assert failure.value.status_code is None
    assert translater._TranslationCache('en', 'ru').get('Source.', 'mymemory') is None
    get.assert_called_once()


def test_mymemory_status_string_accepts_trimmed_ascii_code(api_config, monkeypatch):
    get = mock.Mock(return_value=response(' \t200\r\n ', 'READY'))
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(get=get))
    assert translater.translate_text('Source.', 'en', 'ru', engine='mymemory') == 'READY'
    get.assert_called_once()


@pytest.mark.parametrize('status', [401, '403', 429.0])
def test_mymemory_rejection_retains_only_safe_integer_status_metadata(api_config, monkeypatch, status):
    get = mock.Mock(return_value=response(status))
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(get=get))
    with pytest.raises(RuntimeError, match='MyMemory error: Controlled rejection') as failure:
        translater.translate_text('Source.', 'en', 'ru', engine='mymemory')
    assert type(failure.value.status_code) is int
    assert failure.value.status_code == int(status)
    assert vars(failure.value) == {'status_code': int(status)}
    get.assert_called_once()


@pytest.mark.parametrize('payload', [None, [], 200, 'private synthetic server body'])
def test_mymemory_nonobject_json_fails_without_reflecting_the_payload(api_config, monkeypatch, payload):
    get = mock.Mock(return_value=SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                                                 json=lambda: payload))
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(get=get))
    with pytest.raises(RuntimeError, match='MyMemory returned an invalid response') as failure:
        translater.translate_text('Source.', 'en', 'ru', engine='mymemory')
    assert 'private' not in str(failure.value)
    assert translater._provider_status_code(failure.value) is None
    assert translater._TranslationCache('en', 'ru').get('Source.', 'mymemory') is None
    get.assert_called_once()


@pytest.mark.parametrize('status', [503, '503'])
def test_mymemory_transient_status_does_not_block_the_following_piece(api_config, monkeypatch, status):
    get = mock.Mock(side_effect=[response(status), response(200, 'NEXT')])
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(get=get))
    results = list(translater.iter_translate_texts(['First.', 'Second.'], 'en', 'ru', engine='mymemory'))
    assert get.call_count == 2
    assert results[0][2] and results[1] == (1, 'NEXT', '')


@pytest.mark.parametrize('status', [401, 403, 429, '401', '403', '429'])
def test_mymemory_cancellation_still_precedes_rejection_dispatch(api_config, monkeypatch, status):
    cancelled = threading.Event()

    def reject(*_args, **_kwargs):
        cancelled.set()
        return response(status)

    get = mock.Mock(side_effect=reject)
    monkeypatch.setattr(translater, '_get_http_session', lambda: SimpleNamespace(get=get))
    with pytest.raises(translater.TranslationCancelledError):
        list(translater.iter_translate_texts(['First.', 'Unsent.'], 'en', 'ru', engine='mymemory',
                                            cancel_callback=cancelled.is_set))
    get.assert_called_once()


def test_api_document_keeps_url_model_and_key_snapshot_then_new_operation_uses_new_values(api_config, monkeypatch):
    current_key = {'value': 'old-synthetic-key'}
    api_config['api_providers']['openai-compatible'] = {'url': 'https://old.test/v1', 'model': 'old-model'}
    monkeypatch.setattr(api, 'credential', lambda *_: current_key['value'])
    seen = []

    def translate(provider, text, source, target, config, cancel, *, api_key):
        item = api.profile(provider, config)
        seen.append((item['url'], item['model'], api_key))
        if len(seen) == 1:
            api_config['api_providers']['openai-compatible'].update(url='https://new.test/v1', model='new-model')
            current_key['value'] = 'new-synthetic-key'
        return 'T:' + text

    monkeypatch.setattr(api, 'translate', translate)
    list(translater.iter_translate_texts(['First.', 'Second.'], 'en', 'ru', engine='openai-compatible'))
    assert translater.translate_text('Fresh.', 'en', 'ru', engine='openai-compatible') == 'T:Fresh.'
    assert seen == [('https://old.test/v1', 'old-model', 'old-synthetic-key')] * 2 + [
        ('https://new.test/v1', 'new-model', 'new-synthetic-key')]
