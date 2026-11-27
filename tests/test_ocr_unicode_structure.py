"""Unicode paragraph/list structure survives actual pretranslation callers."""
import json
from types import SimpleNamespace

import pytest
from PIL import Image

import api_providers
import ocr
import ocr_paragraphs


@pytest.mark.parametrize('separator,joined_separator', [
    ('\u2029', '\n\n'), ('\u2028\u2028', '\n\n'),
    ('\n\n', '\n\n'), ('\r\n\r\n', '\n\n'), ('\r\r', '\n\n'),
    ('\u2028', ' '), ('\r\n', ' '), ('\n', ' '),
])
@pytest.mark.parametrize('joined', [False, True])
def test_api_ocr_keeps_explicit_paragraphs_and_existing_soft_wraps(
        monkeypatch, separator, joined_separator, joined):
    first, second = 'الفقرة الأولى', 'الفقرة الثانية'
    source = first + separator + second
    monkeypatch.setattr(api_providers, 'validate', lambda *_: {'vision': True, 'direct': False})
    monkeypatch.setattr(api_providers, 'credential', lambda *_: 'unused-fixture-key')
    monkeypatch.setattr(api_providers, '_text_response', lambda *_: json.dumps({'source': source, 'translation': None}))
    result = api_providers.recognize('openai', Image.new('RGB', (8, 8), 'white'), 'ar', 'en',
                                     {'ocr_join_paragraphs': joined})
    assert result.source == (first + joined_separator + second if joined else source)


@pytest.mark.parametrize('separator', ['\u2029', '\u2028\u2028'])
def test_copy_only_api_ocr_keeps_the_original_unicode_separators(monkeypatch, separator):
    source = 'First' + separator + 'Second'
    monkeypatch.setattr(api_providers, 'validate', lambda *_: {'vision': True, 'direct': False})
    monkeypatch.setattr(api_providers, 'credential', lambda *_: 'unused-fixture-key')
    monkeypatch.setattr(api_providers, '_text_response', lambda *_: json.dumps({'source': source, 'translation': None}))
    result = api_providers.recognize('openai', Image.new('RGB', (8, 8), 'white'), 'en', None,
                                     {'ocr_join_paragraphs': True})
    assert result.source == source


@pytest.mark.parametrize('prefix,suffix', [
    ('', ''), ('\u200f', ''), ('\u061c', ''), ('\u200e', ''),
    ('\u202b', '\u202c'), ('\u2067', '\u2069'),
])
@pytest.mark.parametrize('positioned', [False, True])
def test_bidi_list_markers_keep_structure_and_their_direction_controls(prefix, suffix, positioned):
    lines = ['عنوان', prefix + '١. العنصر الأول' + suffix, prefix + '٢. العنصر الثاني' + suffix]
    if positioned:
        recognized = SimpleNamespace(lines=[])
        for index, text in enumerate(lines):
            word = SimpleNamespace(text=text, bounding_rect=SimpleNamespace(x=10, y=10 + 38 * index, width=400, height=26))
            recognized.lines.append(SimpleNamespace(text=text, words=[word]))
        result = ocr._windows_ocr_result_to_text(recognized, join_paragraphs=True)
    else:
        result = ocr_paragraphs.merge_text_lines('\n'.join(lines))
    assert result == '\n\n'.join(lines)


def test_mixed_explicit_paragraphs_and_bidi_lists_reflow_only_their_wraps():
    source = 'Introduction\r\ncontinues\u2029\u200f1. First item\u2028wraps\u2028\u200f2. Second item'
    assert ocr_paragraphs.merge_text_lines(source) == (
        'Introduction continues\n\n\u200f1. First item wraps\n\n\u200f2. Second item')
