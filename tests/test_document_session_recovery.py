"""Exercise saving and reopening documents through real Qt editors."""
import json
from datetime import datetime
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import main
import document_storage
import portable_paths
from qt_layout_test_support import ensure_layout_fonts


@pytest.fixture
def document(tmp_path, monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ensure_layout_fonts(app)
    monkeypatch.setattr(portable_paths, 'portable_base_dir', lambda: str(tmp_path))
    monkeypatch.setattr(main, 'get_cached_config', lambda: dict(main.DEFAULT_CONFIG, interface_language='en'))
    monkeypatch.setattr(main.translater, 'argos_installed_translation_pairs_fast', lambda: set())
    monkeypatch.setattr(main.translater, 'hymt_installed', lambda: False)
    dialog = main.DocumentTranslationDialog(None)
    dialog.load_plain_text('Existing draft')
    yield dialog
    dialog.close()
    dialog.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def open_session(document, path):
    with mock.patch.object(main.QFileDialog, 'getOpenFileName', return_value=(str(path), '')):
        document.open_session()


def test_saved_language_pair_and_provider_survive_reopening(document, tmp_path):
    payload = {'original_text': 'Guten Tag', 'translated_text': 'Bonjour',
               'source_language': 'de', 'target_language': 'fr', 'provider_engine': 'lingva'}
    path = tmp_path / 'session.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    open_session(document, path)
    assert document.original_view.toPlainText() == 'Guten Tag'
    assert document.translated_view.toPlainText() == 'Bonjour'
    assert document._source_code() == 'de'
    assert document.target_combo.currentData() == 'fr'
    assert document._provider_engine() == 'lingva'


@pytest.mark.parametrize('engine', ['argos', 'hymt'])
def test_reopening_offline_session_never_selects_an_online_provider(document, tmp_path, engine):
    path = tmp_path / 'session.json'
    path.write_text(json.dumps({'original_text': 'Private local draft', 'provider_engine': engine}), encoding='utf-8')
    open_session(document, path)
    assert document._provider_engine() == engine


@pytest.mark.parametrize('key', ['original_text', 'translated_text', 'source_file_name', 'provider_engine'])
@pytest.mark.parametrize('value', [None, 42, {}, []])
def test_bad_session_fields_leave_current_draft_untouched(document, tmp_path, key, value):
    path = tmp_path / 'session.json'
    path.write_text(json.dumps({key: value}), encoding='utf-8')
    with mock.patch.object(main.QMessageBox, 'warning') as warning:
        open_session(document, path)
    warning.assert_called_once()
    assert document.original_view.toPlainText() == 'Existing draft'
    assert not document.original_view.signalsBlocked()


@pytest.mark.parametrize('failure_at', ['paths', 'text', 'session'])
def test_save_error_is_reported_and_draft_is_kept(document, tmp_path, failure_at):
    document.translated_text = 'Edited translation'
    document.translated_view.setPlainText(document.translated_text)
    function = {'paths': 'default_output_paths', 'text': 'save_text', 'session': 'save_session'}[failure_at]
    with mock.patch.object(main.QFileDialog, 'getSaveFileName', return_value=(str(tmp_path / 'result.txt'), '')), \
         mock.patch.object(main, function, side_effect=PermissionError('simulated file is locked')), \
         mock.patch.object(main.QMessageBox, 'warning') as warning:
        document.save_translation()
    warning.assert_called_once()
    assert 'file is locked' in warning.call_args.args[-1]
    assert document.original_view.toPlainText() == 'Existing draft'
    assert document.translated_view.toPlainText() == 'Edited translation'


@pytest.fixture
def deferred_document(document, monkeypatch):
    pending = []

    class DeferredWorker:
        def __init__(self, *, target, **kwargs):
            self.target = target

        def start(self):
            pending.append(self.target)

    monkeypatch.setattr(main.threading, 'Thread', DeferredWorker)
    monkeypatch.setattr(main, '_resolve_translation_provider', lambda owner, engine, *args: engine)
    return document, pending


@pytest.mark.parametrize('dismiss', ['close', 'reject'])
@pytest.mark.parametrize('delivery', ['error', 'done', 'progress', 'delta'])
def test_dismissing_document_retires_translation_without_late_dialogs(deferred_document, dismiss, delivery):
    document, pending = deferred_document
    document._start_translation('Existing draft')
    assert len(pending) == 1
    old = document._document_translation_generation
    cancellation = document._translation_cancel_event
    document._deliver_document_translation(old, 'delta', ('Completed prefix', 1, 2))

    with mock.patch.object(main.QMessageBox, 'warning') as warning, \
         mock.patch.object(main, 'save_translation_history') as history:
        getattr(document, dismiss)()
        before = document.translated_view.toPlainText()
        status = document.current_status
        values = {'error': ('late connection failure',), 'done': ('STALE', []),
                  'progress': (1, 1, 'stale status'), 'delta': ('STALE', 1, 1)}[delivery]
        document._document_translation_signal.emit(old, delivery, values)
        assert cancellation.is_set()
        assert not document.translation_running
        assert document._translation_cancel_event is None
        assert document.translated_view.toPlainText() == before == 'Completed prefix'
        assert document.translated_text == before
        assert document.current_status == status
        warning.assert_not_called()
        history.assert_not_called()


@pytest.mark.parametrize('dismiss', ['close', 'reject'])
def test_reused_document_is_not_completed_by_its_dismissed_worker(deferred_document, dismiss):
    document, pending = deferred_document
    document._start_translation('Existing draft')
    old = document._document_translation_generation
    old_cancel = document._translation_cancel_event
    getattr(document, dismiss)()
    document.load_plain_text('Fresh source')
    assert document.original_view.toPlainText() == 'Fresh source'
    document._start_translation('Fresh source')
    assert len(pending) == 2
    fresh_generation = document._document_translation_generation
    fresh_cancel = document._translation_cancel_event
    assert fresh_generation != old and old_cancel.is_set()
    with mock.patch.object(main.QMessageBox, 'warning') as warning, \
         mock.patch.object(main, 'save_translation_history') as history:
        document._document_translation_signal.emit(old, 'error', ('stale failure',))
        document._document_translation_signal.emit(old, 'done', ('STALE', []))
        assert document.translation_running
        assert document._translation_cancel_event is fresh_cancel
        assert not fresh_cancel.is_set()
        assert document.original_view.toPlainText() == 'Fresh source'
        assert document.translated_view.toPlainText() == ''
        warning.assert_not_called()
        history.assert_not_called()


def test_cancel_button_keeps_completed_chunks_until_its_worker_stops(deferred_document):
    document, pending = deferred_document
    document._start_translation('Existing draft')
    generation = document._document_translation_generation
    cancellation = document._translation_cancel_event
    document._deliver_document_translation(generation, 'delta', ('Completed prefix', 1, 2))
    document.translate_file_button.click()
    assert cancellation.is_set() and document.translation_running
    assert not document.translate_file_button.isEnabled()
    with mock.patch.object(main, 'save_translation_history') as history:
        document._document_translation_signal.emit(generation, 'done', ('Completed prefix', []))
        assert not document.translation_running
        assert document.translated_view.toPlainText() == 'Completed prefix'
        assert document.translated_text == 'Completed prefix'
        assert document.translate_file_button.isEnabled()
        history.assert_not_called()


def test_cancelled_document_worker_error_keeps_partial_text_without_a_warning(deferred_document):
    document, pending = deferred_document
    document._start_translation('Existing draft')
    generation = document._document_translation_generation
    document._deliver_document_translation(generation, 'delta', ('Completed prefix', 1, 2))
    document.translate_file_button.click()
    with mock.patch.object(main.QMessageBox, 'warning') as warning, \
         mock.patch.object(main, 'save_translation_history') as history:
        document._document_translation_signal.emit(generation, 'error', ('connection aborted while canceling',))
        assert not document.translation_running
        assert document.translated_view.toPlainText() == 'Completed prefix'
        assert document.translated_text == 'Completed prefix'
        assert document.current_status == main.doc_text(document.lang, 'translation_canceled')
        warning.assert_not_called()
        history.assert_not_called()


@pytest.mark.parametrize('extension', ['txt', 'md'])
def test_exporting_twice_in_one_second_preserves_each_automatic_session(document, tmp_path, monkeypatch, extension):
    class FrozenClock:
        @staticmethod
        def now():
            return datetime(2026, 11, 6, 19, 15, 0)

    monkeypatch.setattr(document_storage, 'datetime', FrozenClock)
    targets = [tmp_path / ('first.' + extension), tmp_path / ('second.' + extension)]
    with mock.patch.object(main.QFileDialog, 'getSaveFileName', side_effect=[(str(path), '') for path in targets]), \
         mock.patch.object(main.QMessageBox, 'warning') as warning:
        for index, source in enumerate(('First source', 'Second source')):
            document.load_plain_text(source)
            document.translated_text = 'Translation ' + str(index)
            document.translated_view.setPlainText(document.translated_text)
            document._set_busy(False)
            document.save_button.click()
            if index == 0:
                first_sessions = list((tmp_path / 'data' / 'translations').glob('*.json'))
                assert len(first_sessions) == 1
                first_path, first_bytes = first_sessions[0], first_sessions[0].read_bytes()

    warning.assert_not_called()
    sessions = list((tmp_path / 'data' / 'translations').glob('*.json'))
    assert len(sessions) == 2
    assert first_path.read_bytes() == first_bytes
    assert {json.loads(path.read_text(encoding='utf-8'))['original_text'] for path in sessions} == {'First source', 'Second source'}
    assert [path.read_text(encoding='utf-8') for path in targets] == ['Translation 0', 'Translation 1']
