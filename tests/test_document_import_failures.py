"""Failed PDF extraction never publishes a silently truncated attachment."""
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

import document_parser
from document_translation import TranslationChunkResult
import main
from test_document_session_recovery import document


def pdf_reader(monkeypatch, pages):
    monkeypatch.setitem(sys.modules, 'pypdf', SimpleNamespace(
        PdfReader=lambda _path: SimpleNamespace(pages=pages)))


def page(text):
    return SimpleNamespace(extract_text=mock.Mock(return_value=text))


@pytest.fixture
def pdf_path(tmp_path):
    path = tmp_path / 'controlled.pdf'
    path.write_bytes(b'%PDF controlled reader fixture\n')
    return path


@pytest.mark.parametrize('error_type', [RuntimeError, ValueError, MemoryError])
@pytest.mark.parametrize('failure_page', [1, 2])
def test_extraction_error_aborts_the_pdf_with_the_page_number(
        pdf_path, monkeypatch, error_type, failure_page):
    broken = SimpleNamespace(extract_text=mock.Mock(side_effect=error_type('broken page fixture')))
    after = page('Must not read after failure')
    pages = ([page('Readable prefix')] if failure_page == 2 else []) + [broken, after]
    pdf_reader(monkeypatch, pages)
    with pytest.raises(document_parser.DocumentParseError, match=f'PDF page {failure_page}') as failure:
        document_parser.parse_document(pdf_path)
    assert pdf_path.name in str(failure.value)
    assert 'broken page fixture' in str(failure.value)
    after.extract_text.assert_not_called()


@pytest.mark.parametrize('empty', [None, '', ' \n\t '])
def test_an_empty_image_only_page_is_not_an_extraction_error(pdf_path, monkeypatch, empty):
    pdf_reader(monkeypatch, [page('Page one text'), page(empty), page('Page three text')])
    result = document_parser.parse_document(pdf_path)
    assert result.text == '--- Page 1 ---\nPage one text\n\n--- Page 3 ---\nPage three text'


@pytest.mark.parametrize('empty', [None, ''])
def test_an_entire_image_only_pdf_keeps_the_existing_ocr_guidance(pdf_path, monkeypatch, empty):
    pdf_reader(monkeypatch, [page(empty), page(empty)])
    with pytest.raises(document_parser.DocumentParseError, match='Scanned PDFs require OCR'):
        document_parser.parse_document(pdf_path)


def test_a_valid_pdf_still_preserves_every_page_and_unicode_text(pdf_path, monkeypatch):
    pdf_reader(monkeypatch, [page('Hello مرحبا'), page('日本語 — Привет')])
    result = document_parser.parse_document(pdf_path)
    assert result.text == '--- Page 1 ---\nHello مرحبا\n\n--- Page 2 ---\n日本語 — Привет'


def test_failed_pdf_attachment_keeps_the_current_document_draft_translation_and_results(
        document, pdf_path, tmp_path, monkeypatch):
    previous = tmp_path / 'previous.txt'
    previous.write_text('Existing imported source', encoding='utf-8')
    monkeypatch.setattr(main, 'parse_document', document_parser.parse_document)
    monkeypatch.setattr(main.threading, 'Thread', lambda target, **_kwargs: SimpleNamespace(start=target))
    document.load_file(str(previous))
    document.translated_view.setPlainText('Existing translation')
    document.translated_text = 'Existing translation'
    document.translation_results = [TranslationChunkResult(0, 'Existing imported source', 'Existing translation')]
    before = (document.current_document, document.session_payload,
              document.original_view.toPlainText(), document.translated_view.toPlainText(),
              document.translated_text, list(document.translation_results))
    broken = SimpleNamespace(extract_text=mock.Mock(side_effect=RuntimeError('broken page fixture')))
    pdf_reader(monkeypatch, [page('Partial text must not be committed'), broken])
    with mock.patch.object(main.QMessageBox, 'warning') as warning:
        document.load_file(str(pdf_path))
    assert (document.current_document, document.session_payload,
            document.original_view.toPlainText(), document.translated_view.toPlainText(),
            document.translated_text, document.translation_results) == before
    assert not document._document_loading and not document.translation_running
    assert document.attach_button.isEnabled()
    warning.assert_called_once()
