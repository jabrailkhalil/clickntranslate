"""Live QA must not label an untranslated provider response as a success."""
import pytest

from tools.functional_check import _translated_sample


@pytest.mark.parametrize('value', ['', 'Hello world, how are you today?', 'HTTP 200 OK'])
def test_live_translation_probe_rejects_an_empty_or_untranslated_result(value):
    with pytest.raises(AssertionError):
        _translated_sample(value)


def test_live_translation_probe_accepts_the_translated_sentence():
    assert _translated_sample('Привет, мир! Как твои дела?') == 'Привет, мир! Как твои дела?'
