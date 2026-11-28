"""Exercise saving and reopening documents through real Qt editors."""
import json
from datetime import datetime
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import main
import document_storage
import document_translation
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


@pytest.mark.parametrize('engine', ['google', 'argos'])
def test_changing_ui_language_preserves_valid_document_directions_and_translates_the_selected_pair(
        deferred_document, monkeypatch, engine):
    document, pending = deferred_document
    monkeypatch.setattr(main.translater, 'argos_installed_translation_pairs_fast', lambda: {('ar', 'de')})
    document._populate_provider_combo(engine)
    document._refresh_document_provider_languages()
    document.source_combo.setCurrentIndex(document.source_combo.findData('ar'))
    document.target_combo.setCurrentIndex(document.target_combo.findData('de'))
    source_codes = [document.source_combo.itemData(i) for i in range(document.source_combo.count())]
    target_codes = [document.target_combo.itemData(i) for i in range(document.target_combo.count())]
    if engine == 'argos':
        assert source_codes == ['ar'] and target_codes == ['de']
    else:
        assert 'auto' in source_codes
    document.refresh_language('ar')
    assert [document.source_combo.itemData(i) for i in range(document.source_combo.count())] == source_codes
    assert [document.target_combo.itemData(i) for i in range(document.target_combo.count())] == target_codes
    assert document.source_combo.currentText() == main.language_display_name('ar', 'ar')
    assert document.target_combo.currentText() == main.language_display_name('de', 'ar')
    assert document.current_status == main.doc_text('ar', 'loaded')
    translate = mock.Mock(return_value=('Result', []))
    monkeypatch.setattr(main, 'translate_document_text', translate)
    monkeypatch.setattr(main, 'save_translation_history', mock.Mock())
    document.translate_file_button.click()
    pending.pop()()
    assert translate.call_args.args[1:] == ('ar', 'de')
    document.refresh_language('fr')
    assert document.current_status == main.doc_text('fr', 'done')


@pytest.mark.parametrize('payload', [{}, {'theme': 'light'}, {'translated_text': 'Damaged', 'chunks': [None]}])
def test_unrelated_or_damaged_session_json_leaves_the_open_draft(document, tmp_path, payload):
    path = tmp_path / 'other.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    with mock.patch.object(main.QMessageBox, 'warning') as warning:
        open_session(document, path)
    warning.assert_called_once()
    assert document.original_view.toPlainText() == 'Existing draft'
    assert document.session_payload is None


def test_saving_a_reopened_session_preserves_partial_chunk_diagnostics(document, tmp_path):
    chunks = [
        dict(index=0, source_text='First', translated_text='Первый', error=''),
        dict(index=1, source_text='Second', translated_text='[Incomplete]', error='Fixture failed'),
    ]
    original, exported = tmp_path / 'original.json', tmp_path / 'exported.json'
    original.write_text(json.dumps(dict(original_text='First Second', translated_text='Первый [Incomplete]',
                                        chunks=chunks)), encoding='utf-8')
    open_session(document, original)
    with mock.patch.object(main.QFileDialog, 'getSaveFileName', return_value=(str(exported), '')):
        document.save_button.click()
    assert json.loads(exported.read_text(encoding='utf-8'))['chunks'] == chunks


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


def test_export_keeps_the_language_and_provider_that_produced_the_visible_translation(deferred_document, tmp_path, monkeypatch):
    document, pending = deferred_document
    document._populate_provider_combo('lingva')
    document._refresh_document_provider_languages()
    document.source_combo.setCurrentIndex(document.source_combo.findData('en'))
    document.target_combo.setCurrentIndex(document.target_combo.findData('fr'))
    translate = mock.Mock(return_value=('Bonjour', []))
    monkeypatch.setattr(main, 'translate_document_text', translate)
    monkeypatch.setattr(main, 'save_translation_history', mock.Mock())
    document.translate_file_button.click()
    pending.pop()()
    assert translate.call_args.args[1:] == ('en', 'fr')
    assert translate.call_args.kwargs['provider_engine'] == 'lingva'

    for name in ('export.json', 'reopened.json'):
        document.provider_combo.setCurrentIndex(document.provider_combo.findData('google'))
        document.source_combo.setCurrentIndex(document.source_combo.findData('de'))
        document.target_combo.setCurrentIndex(document.target_combo.findData('es'))
        path = tmp_path / name
        with mock.patch.object(main.QFileDialog, 'getSaveFileName', return_value=(str(path), '')):
            document.save_button.click()
        saved = json.loads(path.read_text(encoding='utf-8'))
        assert saved['translated_text'] == 'Bonjour'
        assert (saved['source_language'], saved['target_language'], saved['provider_engine']) == ('en', 'fr', 'lingva')
        open_session(document, path)


def test_unexpected_error_keeps_every_completed_chunk_exportable(deferred_document, tmp_path, monkeypatch):
    document, pending = deferred_document
    document.load_plain_text('First Second Third')
    parts = [document_translation.TranslationChunk(i, text) for i, text in enumerate(('First ', 'Second ', 'Third'))]
    monkeypatch.setattr(document_translation, 'split_text_chunks', lambda *_a, **_kw: parts)
    # Two small chunks complete within one UI update interval.
    monkeypatch.setattr(document_translation, 'time', mock.Mock(monotonic=lambda: 1.0))

    def interrupted_provider(*args, **kwargs):
        yield 0, 'Alpha', ''
        yield 1, 'Beta', ''
        raise RuntimeError('Fixture provider stopped before chunk three')

    monkeypatch.setattr(main.translater, 'iter_translate_texts', interrupted_provider)
    history = mock.Mock()
    monkeypatch.setattr(main, 'save_translation_history', history)
    with mock.patch.object(main.QMessageBox, 'warning') as warning:
        document.translate_file_button.click()
        pending.pop()()
    warning.assert_called_once()
    history.assert_not_called()
    assert not document.translation_running
    assert document.translated_text == document.translated_view.toPlainText() == 'Alpha Beta '
    assert document.save_button.isEnabled()
    path = tmp_path / 'recovered.txt'
    with mock.patch.object(main.QFileDialog, 'getSaveFileName', return_value=(str(path), '')):
        document.save_button.click()
    assert path.read_text(encoding='utf-8') == 'Alpha Beta '


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


def test_export_never_overwrites_a_session_created_while_the_save_dialog_was_open(document, tmp_path, monkeypatch):
    original = b'{"original_text":"Another export already finished"}'
    claimed = tmp_path / 'sessions' / 'translation.json'
    claimed.parent.mkdir()
    requested = tmp_path / 'my-result.txt'
    monkeypatch.setattr(main, 'default_output_paths', lambda *_: {
        'txt': str(claimed.with_suffix('.txt')), 'session': str(claimed)})

    def choose(*_):
        claimed.write_bytes(original)
        return str(requested), ''

    document.translated_view.setPlainText('Visible answer')
    document.translated_text = 'Visible answer'
    with mock.patch.object(main.QFileDialog, 'getSaveFileName', side_effect=choose), \
         mock.patch.object(main.QMessageBox, 'warning') as warning:
        document.save_translation()
    warning.assert_not_called()
    assert requested.read_text(encoding='utf-8') == 'Visible answer'
    assert claimed.read_bytes() == original
    sessions = list(claimed.parent.glob('*.json'))
    assert len(sessions) == 2
    assert any(document_storage.load_session(path).get('translated_text') == 'Visible answer' for path in sessions)


@pytest.mark.parametrize('extension', ['json', 'txt'])
def test_user_can_export_to_a_writable_location_when_the_default_folder_is_unavailable(
        document, tmp_path, monkeypatch, extension):
    target = tmp_path / ('recovered.' + extension)
    monkeypatch.setattr(main, 'default_output_paths', mock.Mock(side_effect=PermissionError('default folder unavailable')))
    document.translated_view.setPlainText('Completed translation')
    document.translated_text = 'Completed translation'
    with mock.patch.object(main.QFileDialog, 'getSaveFileName', return_value=(str(target), '')), \
         mock.patch.object(main.QMessageBox, 'warning') as warning:
        document.save_translation()
    if extension == 'json':
        warning.assert_not_called()
        assert document_storage.load_session(target)['translated_text'] == 'Completed translation'
    else:
        warning.assert_called_once()
        assert str(target) in document.current_status
        assert target.read_text(encoding='utf-8') == 'Completed translation'


def test_open_session_allows_an_external_file_when_the_default_folder_is_unavailable(document, tmp_path, monkeypatch):
    chosen = tmp_path / 'working-session.json'
    chosen.write_text('{"original_text":"Keeps working from another directory"}', encoding='utf-8')
    monkeypatch.setattr(main, 'translations_dir', mock.Mock(side_effect=PermissionError('default folder unavailable')))
    open_session(document, chosen)
    assert document.original_view.toPlainText() == 'Keeps working from another directory'


def test_concurrent_automatic_exports_publish_every_snapshot(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    path = tmp_path / 'same-name.json'
    ready = threading.Barrier(4)

    def export(index):
        ready.wait(3)
        return document_storage.save_session(path, {'translated_text': str(index)}, unique=True)

    with ThreadPoolExecutor(max_workers=4) as workers:
        saved = list(workers.map(export, range(4)))
    assert len(set(saved)) == 4
    assert [document_storage.load_session(output)['translated_text'] for output in saved] == ['0', '1', '2', '3']
    assert not list(tmp_path.glob('.cnt-save-*.tmp'))


def test_automatic_session_on_a_drive_without_hardlinks_preserves_an_existing_file(tmp_path, monkeypatch):
    import atomic_storage
    import errno
    import os

    class PortableVolume:
        name = 'posix'

        def __getattr__(self, name):
            return getattr(os, name)

        def link(self, *_):
            raise OSError(errno.EOPNOTSUPP, 'no hard links on this volume')

    monkeypatch.setattr(atomic_storage, 'os', PortableVolume())
    old = tmp_path / 'snapshot.json'
    old.write_bytes(b'previous export')
    new_path = document_storage.save_session(old, {'translated_text': 'Another result'}, unique=True)
    assert old.read_bytes() == b'previous export'
    assert document_storage.load_session(new_path)['translated_text'] == 'Another result'
