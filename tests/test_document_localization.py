"""Document failures and saved partial text follow UI language, not source language."""
from string import Formatter
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui

import document_messages as messages
import document_translation as documents
import main
from assistant_text import assistant_action_text
from settings_guide_content import guide_updates
from settings_window import settings_text
from test_document_session_recovery import document


LOCALES = tuple(main.INTERFACE_LANGUAGE_BY_CODE)


@pytest.mark.parametrize('locale', LOCALES)
def test_document_messages_have_localized_meaning_and_matching_parameters(locale):
    source = messages._TEXT['en']
    translated = messages._TEXT[locale]
    assert len(translated) == len(source) == len(messages._KEYS)
    for english, value in zip(source, translated):
        assert value.strip()
        assert {field for _, field, _, _ in Formatter().parse(value) if field} == {
            field for _, field, _, _ in Formatter().parse(english) if field}
        if locale != 'en':
            assert value != english


@pytest.mark.parametrize('locale', LOCALES)
@pytest.mark.parametrize('error,key', [
    ('File not found.', 'missing'), ('No file selected.', 'no_file'),
    ('No readable text was found in this file.', 'empty'),
    ('Invalid DOCX file.', 'invalid_docx'), ('DOCX document.xml is missing.', 'docx_missing'),
    ('PDF support requires the pypdf package.', 'missing_pdf'),
    ('No selectable text was found in this PDF. Scanned PDFs require OCR.', 'scanned_pdf'),
])
def test_known_parser_errors_have_complete_translated_explanations(locale, error, key):
    value = messages.localized_document_error(error, locale)
    assert value == messages.document_message(locale, key)
    if locale != 'en':
        assert value != error


@pytest.mark.parametrize('locale', LOCALES)
def test_extensions_paths_and_unknown_diagnostics_are_preserved(locale):
    unsupported = messages.localized_document_error(
        'Unsupported file type: .xyz. Supported: .docx, .html, .txt.', locale)
    assert '.xyz' in unsupported and '.docx, .html, .txt' in unsupported
    if locale != 'en':
        assert 'Unsupported file type' not in unsupported and 'Supported:' not in unsupported
    raw = 'Failed to read <b>Документ</b>.txt: [Errno 13] C:/files/Документ.txt'
    detail = messages.localized_document_error(raw, locale)
    assert detail.startswith(messages.document_message(locale, 'read_error'))
    assert raw in detail and messages.document_message(locale, 'details') in detail


@pytest.mark.parametrize('locale', LOCALES)
def test_partial_translation_localizes_our_marker_and_keeps_raw_error_out_of_export(locale):
    progress, partial = [], []
    diagnostic = 'API key rejected (HTTP 401)'
    with mock.patch.object(documents.translater, 'iter_translate_texts',
                           return_value=iter([(0, 'أول', ''), (1, '', diagnostic)])):
        translated, results = documents.translate_document_text(
            'First\n\nSecond', 'en', 'ar', provider_engine='google', max_chars=8,
            interface_language=locale,
            progress_callback=lambda *args: progress.append(args),
            partial_callback=lambda *args: partial.append(args))
    marker = messages.document_message(locale, 'chunk_failed', number=2)
    assert marker in translated and marker in partial[-1][0]
    assert diagnostic not in translated
    assert results[1].error == diagnostic
    assert results[0].source_text + results[1].source_text == 'First\n\nSecond'
    assert progress[0][2] == messages.document_message(locale, 'translating', current=1, total=2)
    assert progress[-1][2] == messages.document_message(locale, 'translated', current=2, total=2)


@pytest.mark.parametrize('locale', LOCALES)
def test_actual_document_dialog_localizes_failure_and_escapes_technical_markup(document, locale):
    document.lang = locale
    raw = 'Failed to read <img src="bad">.txt: Permission denied'
    with mock.patch.object(main.QMessageBox, 'warning') as warning:
        document._on_document_error(raw)
    value = messages.localized_document_error(raw, locale)
    assert document.current_status == value
    assert document.status_pill.textFormat() == QtCore.Qt.PlainText
    html = warning.call_args.args[2]
    assert '<img ' not in html and '&lt;img ' in html
    rich = QtGui.QTextDocument()
    rich.setHtml(html)
    assert raw in rich.toPlainText()


@pytest.mark.parametrize('locale', LOCALES)
def test_document_gui_passes_ui_language_separately_from_translation_languages(document, locale, monkeypatch):
    jobs = []
    document.lang = locale
    document.load_plain_text('Source text')
    monkeypatch.setattr(main, '_resolve_translation_provider', lambda _owner, engine, *args: engine)
    monkeypatch.setattr(main.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=lambda: jobs.append(target)))
    with mock.patch.object(main, 'translate_document_text', return_value=('Translated', [])) as translate:
        document._start_translation('Source text')
        jobs.pop()()
    assert translate.call_args.kwargs['interface_language'] == locale


@pytest.mark.parametrize('locale,enabled_word,optional_word', [
    ('en', 'on by default', 'optional'), ('ru', 'включено по умолчанию', 'необязателен'),
    ('es', 'activado de forma predeterminada', 'opcional'), ('de', 'standardmäßig an', 'optional'),
    ('fr', 'activé par défaut', 'facultative'), ('zh', '默认开启', '可选'),
    ('pt', 'ativado por padrão', 'opcional'), ('it', 'attivo per impostazione predefinita', 'facoltativo'),
    ('ar', 'مفعّل افتراضيًا', 'اختياري'), ('tr', 'varsayılan olarak açıktır', 'isteğe bağlı'),
    ('hi', 'डिफ़ॉल्ट में चालू', 'वैकल्पिक'), ('id', 'aktif secara bawaan', 'opsional'),
])
def test_guidance_matches_defaults_and_the_optional_output_behavior(locale, enabled_word, optional_word):
    assert main.DEFAULT_CONFIG['close_result_window_on_outside_click'] is True
    assert enabled_word in guide_updates(locale)['result_behavior'][1]
    assert main.DEFAULT_CONFIG['game_manual_output'] is False
    assert optional_word in assistant_action_text(locale, 'dynamic')[1]
    # A control's current caption must appear in the explanation as well as its
    # heading, so searching the help for what is visible in Settings succeeds.
    label = settings_text(locale, 'result_window_label').rstrip(':： ')
    explanations = [text for _title, items in main.HELP_CONTENT[locale] for text in items]
    assert any(label in text for text in explanations)
    for mode in main.RESULT_WINDOW_MODES:
        row = settings_text(locale, 'result_window_row_' + mode)
        assert any(row in text for text in explanations), (locale, mode)


@pytest.mark.parametrize('locale,removed_page', [
    ('en', 'Data and updates'), ('ru', 'Данные и обновления'),
    ('es', 'Datos y actualizaciones'), ('de', 'Daten und Updates'),
    ('fr', 'Données et mises à jour'), ('zh', '数据与更新'),
    ('pt', 'Dados e atualizações'), ('it', 'Dati e aggiornamenti'),
    ('ar', 'البيانات والتحديثات'), ('tr', 'Veriler ve güncellemeler'),
    ('hi', 'डेटा और अपडेट'), ('id', 'Data dan pembaruan'),
])
def test_active_guide_and_help_do_not_send_users_to_removed_submenus(locale, removed_page):
    guide = str(main.guide_text(locale))
    help_content = str(main.HELP_CONTENT[locale])
    assert removed_page not in guide
    assert removed_page not in help_content
