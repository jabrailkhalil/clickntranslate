"""Empty planned pieces must neither bill a service nor start a local model."""
from unittest import mock

import pytest

import api_providers as api
import document_translation as documents
import translater
from test_api_document_failures import api_config
from test_translation_chunks import isolated_translation


@pytest.mark.parametrize('provider', ['openai', 'openai-compatible', 'gemini', 'anthropic', 'deepl'])
def test_blank_translation_never_calls_the_paid_adapter(api_config, provider, monkeypatch):
    translate = mock.Mock(return_value='unexpected translation')
    monkeypatch.setattr(api, 'translate', translate)
    for source in ('', ' \n\t '):
        assert translater.translate_text(source, 'en', 'ar', engine=provider) == source
    translate.assert_not_called()


@pytest.mark.parametrize('provider', ['openai', 'openai-compatible', 'gemini', 'anthropic', 'deepl'])
def test_whitespace_document_pieces_keep_source_and_skip_the_paid_adapter(api_config, provider, monkeypatch):
    source = 'First paragraph.' + ' ' * 80 + 'Last paragraph.'
    calls = []

    def translate(engine, text, *args, **kwargs):
        calls.append(text)
        return text

    monkeypatch.setattr(api, 'translate', translate)
    translated, pieces = documents.translate_document_text(source, 'en', 'ar',
        provider_engine=provider, max_chars=24)
    assert translated == source and ''.join(piece.source_text for piece in pieces) == source
    assert any(not piece.source_text.strip() for piece in pieces)
    assert all(text.strip() for text in calls)
    assert len(calls) == sum(bool(piece.source_text.strip()) for piece in pieces)


def test_already_cancelled_argos_document_does_not_construct_a_worker(api_config, monkeypatch):
    monkeypatch.setattr(translater, '_argos_document_worker_supported', lambda: True)
    thread = mock.Mock(side_effect=AssertionError('A cancelled document constructed a worker'))
    monkeypatch.setattr(translater.threading, 'Thread', thread)
    with pytest.raises(translater.TranslationCancelledError):
        list(translater.iter_translate_texts(['Private paragraph.'], 'en', 'ar',
                                            engine='argos', cancel_callback=lambda: True))
    thread.assert_not_called()


def test_blank_input_still_obeys_an_already_requested_cancellation(api_config, monkeypatch):
    translate = mock.Mock()
    monkeypatch.setattr(api, 'translate', translate)
    with pytest.raises(translater.TranslationCancelledError):
        translater.translate_text(' \n\t ', 'en', 'ar', engine='openai', cancel_callback=lambda: True)
    translate.assert_not_called()
