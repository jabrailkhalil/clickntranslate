"""Late document parsers cannot replace a newer file, draft or translation."""
import threading
from threading import Thread as RealThread
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets, sip
from PyQt5.QtTest import QTest

import main
from test_document_session_recovery import document


def parsed(path):
    return SimpleNamespace(path=path,file_name=path,size_bytes=1,
                           detected_language='en',text='Text of '+path)


@pytest.fixture
def loads(document,monkeypatch):
    jobs=[]
    monkeypatch.setattr(main.threading,'Thread',lambda target,**kwargs:SimpleNamespace(start=lambda:jobs.append(target)))
    monkeypatch.setattr(main,'parse_document',parsed)
    monkeypatch.setattr(main,'save_translation_history',mock.Mock())
    return document,jobs


def test_newer_file_survives_an_older_completion(loads):
    dialog,jobs=loads
    dialog.load_file('A.txt')
    dialog.load_file('B.txt')
    jobs[1]()
    jobs[0]()
    assert dialog.original_view.toPlainText()=='Text of B.txt'
    assert dialog.current_document.file_name=='B.txt'
    assert not dialog._document_loading


def test_worker_thread_queued_completion_does_not_replace_the_newer_file(loads,monkeypatch):
    dialog,jobs=loads
    started,release=threading.Event(),threading.Event()
    def parse(path):
        if path=='A.txt':
            started.set()
            assert release.wait(3)
        return parsed(path)
    monkeypatch.setattr(main,'parse_document',parse)
    dialog.load_file('A.txt')
    worker=RealThread(target=jobs[0])
    worker.start()
    try:
        assert started.wait(2)
        dialog.load_file('B.txt')
        jobs[1]()
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive()
    QtWidgets.QApplication.processEvents()
    assert dialog.original_view.toPlainText()=='Text of B.txt'


def test_typing_cancels_the_pending_load_without_overwriting_the_draft(loads):
    dialog,jobs=loads
    dialog.load_file('A.txt')
    assert not dialog.attach_button.isEnabled()
    dialog.original_view.setPlainText('My new draft')
    jobs[0]()
    assert dialog.original_view.toPlainText()=='My new draft'
    assert dialog.current_document is None and not dialog._document_loading
    assert dialog.attach_button.isEnabled()
    assert dialog.current_status==main.doc_text(dialog.lang,'loaded')


@pytest.mark.parametrize('replacement',['remove','plain','session','close','reject'])
def test_replacing_or_dismissing_the_view_invalidates_a_pending_file(loads,tmp_path,monkeypatch,replacement):
    dialog,jobs=loads
    dialog.load_file('A.txt')
    if replacement=='remove':
        dialog.remove_file()
    elif replacement=='plain':
        dialog.load_plain_text('A new message')
    elif replacement=='session':
        path=tmp_path/'session.json'
        path.write_text('{"original_text":"Saved draft"}',encoding='utf-8')
        with mock.patch.object(main.QFileDialog,'getOpenFileName',return_value=(str(path),'')):
            dialog.open_session()
    else:
        getattr(dialog,replacement)()
    expected=dialog.original_view.toPlainText()
    jobs[0]()
    assert dialog.original_view.toPlainText()==expected
    assert not dialog._document_loading and dialog.attach_button.isEnabled()


def test_late_load_error_does_not_cancel_the_new_document_translation(loads,monkeypatch):
    dialog,jobs=loads
    def parse(path):
        if path=='A.txt':
            raise main.DocumentParseError('No readable text was found in this file.')
        return parsed(path)
    monkeypatch.setattr(main,'parse_document',parse)
    monkeypatch.setattr(main,'_resolve_translation_provider',lambda _owner,engine,*args:engine)
    monkeypatch.setattr(main,'translate_document_text',lambda *args,**kwargs:('Translation of B',[]))
    dialog.load_file('A.txt')
    dialog.load_file('B.txt')
    jobs[1]()
    dialog._start_translation(dialog.original_view.toPlainText())
    active_event=dialog._translation_cancel_event
    assert dialog.translation_running
    with mock.patch.object(main.QMessageBox,'warning') as warning:
        jobs[0]()
    warning.assert_not_called()
    assert dialog.translation_running and dialog._translation_cancel_event is active_event
    jobs[2]()
    assert not dialog.translation_running and dialog.translated_text=='Translation of B'
    assert dialog.original_view.toPlainText()=='Text of B.txt'


def test_a_current_load_error_is_reported_and_the_next_load_can_succeed(loads,monkeypatch):
    dialog,jobs=loads
    monkeypatch.setattr(main,'parse_document',mock.Mock(side_effect=[main.DocumentParseError('File not found.'),parsed('B.txt')]))
    dialog.load_file('A.txt')
    with mock.patch.object(main.QMessageBox,'warning') as warning:
        jobs[0]()
    warning.assert_called_once()
    assert not dialog._document_loading and dialog.attach_button.isEnabled()
    dialog.load_file('B.txt')
    jobs[1]()
    assert dialog.current_document.file_name=='B.txt'


def test_translation_error_signal_still_ends_the_active_translation(loads):
    dialog,_jobs=loads
    dialog.translation_running=True
    dialog._translation_cancel_event=threading.Event()
    with mock.patch.object(main.QMessageBox,'warning') as warning:
        dialog._document_error_signal.emit('Translation provider failed')
    warning.assert_called_once()
    assert not dialog.translation_running and dialog._translation_cancel_event is None


def test_thread_start_failure_restores_loading_controls(loads,monkeypatch):
    dialog,_jobs=loads
    monkeypatch.setattr(main.threading,'Thread',lambda **kwargs:SimpleNamespace(start=mock.Mock(side_effect=RuntimeError('Worker unavailable'))))
    with mock.patch.object(main.QMessageBox,'warning') as warning:
        dialog.load_file('A.txt')
    warning.assert_called_once()
    assert not dialog._document_loading and dialog.attach_button.isEnabled()


@pytest.mark.parametrize('locale',main.INTERFACE_LANGUAGE_BY_CODE)
def test_refreshing_languages_keeps_loading_controls_and_status(loads,locale):
    dialog,jobs=loads
    dialog.load_file('A.txt')
    dialog.refresh_language(locale)
    dialog.refresh_theme('Темная')
    dialog._refresh_document_provider_languages()
    assert dialog._document_loading
    assert dialog.current_status==main.doc_text(locale,'loading')
    for control in (dialog.attach_button,dialog.open_button,dialog.translate_file_button,
                    dialog.translate_selected_button,dialog.language_arrow):
        assert not control.isEnabled()
    jobs[0]()
    assert not dialog._document_loading and dialog.attach_button.isEnabled()


def test_deleted_dialog_does_not_raise_from_a_late_worker(monkeypatch):
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    jobs=[]
    monkeypatch.setattr(main.threading,'Thread',lambda target,**kwargs:SimpleNamespace(start=lambda:jobs.append(target)))
    monkeypatch.setattr(main,'parse_document',parsed)
    dialog=main.DocumentTranslationDialog(None)
    dialog.load_file('A.txt')
    dialog.deleteLater()
    app.sendPostedEvents(None,QtCore.QEvent.DeferredDelete)
    assert sip.isdeleted(dialog)
    jobs[0]()


@pytest.mark.parametrize('action',['close','reject','delete','draft'])
def test_initial_path_does_not_start_after_its_owner_is_dismissed_or_replaced(document,monkeypatch,action):
    app=QtWidgets.QApplication.instance()
    jobs=[]
    monkeypatch.setattr(main.threading,'Thread',lambda target,**kwargs:SimpleNamespace(start=lambda:jobs.append(target)))
    monkeypatch.setattr(main,'parse_document',parsed)
    dialog=main.DocumentTranslationDialog(None,initial_path='Initial.txt')
    try:
        if action=='delete':
            dialog.deleteLater()
            app.sendPostedEvents(None,QtCore.QEvent.DeferredDelete)
            assert sip.isdeleted(dialog)
        elif action=='draft':
            dialog.original_view.setPlainText('My immediate draft')
        else:
            getattr(dialog,action)()
        app.processEvents()
        assert jobs==[]
        if action=='draft':
            assert dialog.original_view.toPlainText()=='My immediate draft'
    finally:
        if not sip.isdeleted(dialog):
            dialog.close()
            dialog.deleteLater()


def test_initial_path_starts_once_when_the_dialog_stays_open(document,monkeypatch):
    app=QtWidgets.QApplication.instance()
    jobs=[]
    monkeypatch.setattr(main.threading,'Thread',lambda target,**kwargs:SimpleNamespace(start=lambda:jobs.append(target)))
    monkeypatch.setattr(main,'parse_document',parsed)
    dialog=main.DocumentTranslationDialog(None,initial_path='Initial.txt')
    try:
        app.processEvents()
        assert len(jobs)==1 and dialog._document_loading
        jobs[0]()
        app.processEvents()
        assert len(jobs)==1 and not dialog._document_loading
        assert dialog.current_document.file_name=='Initial.txt'
    finally:
        dialog.close()
        dialog.deleteLater()


def _previous_document_state(dialog, kind):
    dialog.load_plain_text('Unsaved source draft')
    if kind == 'file':
        dialog.current_document = parsed('Previous.txt')
    elif kind == 'session':
        dialog.session_payload = {'original_text': 'Unsaved source draft',
                                  'source_file_name': 'Previous.txt'}
    dialog._populate_provider_combo('lingva')
    dialog._refresh_document_provider_languages()
    dialog.source_combo.setCurrentIndex(dialog.source_combo.findData('de'))
    dialog.target_combo.setCurrentIndex(dialog.target_combo.findData('fr'))
    dialog.translated_text = 'Unsaved translation'
    dialog.translated_view.setPlainText(dialog.translated_text)
    dialog.translation_results = [SimpleNamespace(text='Unsaved translation', error='')]
    dialog._set_busy(False)


def _document_state(dialog):
    return (dialog.original_view.toPlainText(), dialog.translated_view.toPlainText(),
            dialog.translated_text, dialog.current_document, dialog.session_payload,
            list(dialog.translation_results), dialog.translation_error_message_visible,
            dialog._source_code(), dialog.target_combo.currentData(), dialog._provider_engine())


@pytest.mark.parametrize('kind', ['draft', 'file', 'session'])
@pytest.mark.parametrize('failure', ['parse', 'thread_start'])
def test_failed_attachment_keeps_previous_unsaved_work(document, monkeypatch, tmp_path, kind, failure):
    dialog = document
    _previous_document_state(dialog, kind)
    before = _document_state(dialog)
    path = tmp_path / 'Broken.docx'
    path.write_bytes(b'not a DOCX archive')
    jobs = []
    if failure == 'parse':
        monkeypatch.setattr(main.threading, 'Thread', lambda target, **kwargs:
                            SimpleNamespace(start=lambda: jobs.append(target)))
    else:
        monkeypatch.setattr(main.threading, 'Thread', lambda **kwargs:
                            SimpleNamespace(start=mock.Mock(side_effect=RuntimeError('Worker unavailable'))))
    with mock.patch.object(main.QFileDialog, 'getOpenFileName', return_value=(str(path), '')), \
            mock.patch.object(main.QMessageBox, 'warning') as warning:
        dialog.attach_button.click()
        if failure == 'parse':
            assert dialog._document_loading and not dialog.save_button.isEnabled()
            assert _document_state(dialog) == before
            jobs.pop()()
    warning.assert_called_once()
    assert _document_state(dialog) == before
    assert not dialog._document_loading and dialog.attach_button.isEnabled()
    assert dialog.save_button.isEnabled()


@pytest.mark.parametrize('dismiss', ['close', 'reject'])
def test_dismissing_pending_attachment_keeps_previous_work_and_ignores_late_result(loads, dismiss):
    dialog, jobs = loads
    _previous_document_state(dialog, 'session')
    before = _document_state(dialog)
    dialog.load_file('Replacement.txt')
    getattr(dialog, dismiss)()
    jobs.pop()()
    assert _document_state(dialog) == before
    assert not dialog._document_loading


def test_successful_attachment_replaces_previous_work_only_after_parsing(loads):
    dialog, jobs = loads
    _previous_document_state(dialog, 'session')
    before = _document_state(dialog)
    dialog.load_file('Replacement.txt')
    assert _document_state(dialog) == before
    jobs.pop()()
    assert dialog.original_view.toPlainText() == 'Text of Replacement.txt'
    assert dialog.current_document.file_name == 'Replacement.txt'
    assert dialog.session_payload is None
    assert dialog.translated_text == dialog.translated_view.toPlainText() == ''
    assert dialog.translation_results == []
    assert not dialog.translation_error_message_visible
    assert not dialog.save_button.isEnabled()
    assert (dialog._source_code(), dialog.target_combo.currentData(), dialog._provider_engine()) == before[-3:]


@pytest.mark.parametrize('kind', ['draft', 'file', 'session'])
def test_editing_source_cancels_translation_and_never_exports_an_old_result(loads, monkeypatch, kind):
    dialog, jobs = loads
    _previous_document_state(dialog, kind)
    monkeypatch.setattr(main, '_resolve_translation_provider', lambda owner, engine, *args: engine)
    monkeypatch.setattr(main, 'translate_document_text', lambda *args, **kw: ('Old translation', []))
    dialog.translate_file_button.click()
    old_cancel = dialog._translation_cancel_event
    assert dialog.translation_running and not dialog.original_view.isReadOnly()
    dialog.original_view.selectAll()
    QTest.keyClicks(dialog.original_view, 'My edited source draft')
    assert old_cancel.is_set() and not dialog.translation_running
    assert dialog.attach_button.isEnabled() and not dialog.save_button.isEnabled()
    jobs.pop()()
    payload = dialog._session_payload()
    assert payload['original_text'] == 'My edited source draft'
    assert payload['translated_text'] == dialog.translated_view.toPlainText() == ''
    main.save_translation_history.assert_not_called()


@pytest.mark.parametrize('kind', ['draft', 'file', 'session'])
def test_editing_a_completed_source_invalidates_its_saved_result(loads, kind):
    dialog, _jobs = loads
    _previous_document_state(dialog, kind)
    previous_file, previous_session = dialog.current_document, dialog.session_payload
    dialog.original_view.selectAll()
    QTest.keyClicks(dialog.original_view, 'A later source revision')
    assert dialog._session_payload()['original_text'] == 'A later source revision'
    assert dialog._session_payload()['translated_text'] == ''
    assert dialog.translated_view.toPlainText() == '' and not dialog.save_button.isEnabled()
    assert dialog.current_document is previous_file and dialog.session_payload is previous_session


@pytest.mark.parametrize('old_error', [False, True])
def test_late_translation_events_cannot_change_the_replacement_translation(loads, monkeypatch, old_error):
    dialog, jobs = loads
    monkeypatch.setattr(main, '_resolve_translation_provider', lambda owner, engine, *args: engine)
    def translate(text, *args, progress_callback, delta_callback, **kw):
        progress_callback(1, 2, 'Old progress')
        delta_callback('Old delta', 1, 2)
        if old_error and text == 'Old draft':
            raise RuntimeError('Old provider error')
        return 'Translation of ' + text, []
    monkeypatch.setattr(main, 'translate_document_text', translate)
    dialog.load_plain_text('Old draft')
    dialog.translate_file_button.click()
    old_cancel = dialog._translation_cancel_event
    dialog.original_view.setPlainText('New draft')
    dialog.translate_file_button.click()
    new_cancel = dialog._translation_cancel_event
    with mock.patch.object(main.QMessageBox, 'warning') as warning:
        jobs[0]()
    warning.assert_not_called()
    assert old_cancel.is_set() and not new_cancel.is_set()
    assert dialog.translation_running and dialog._translation_cancel_event is new_cancel
    assert dialog.progress_bar.value() == 0 and dialog.translated_view.toPlainText() == ''
    jobs[1]()
    assert not dialog.translation_running
    assert dialog.original_view.toPlainText() == 'New draft'
    assert dialog.translated_text == 'Translation of New draft'
    main.save_translation_history.assert_called_once_with('New draft', 'Translation of New draft',
                                                        dialog._active_translation_target_code)


def test_already_queued_worker_events_are_discarded_after_editing(loads, monkeypatch):
    dialog, jobs = loads
    monkeypatch.setattr(main, '_resolve_translation_provider', lambda owner, engine, *args: engine)
    def translate(*args, progress_callback, delta_callback, **kw):
        progress_callback(1, 1, 'Finishing old draft')
        delta_callback('Old delta', 1, 1)
        return 'Old final result', []
    monkeypatch.setattr(main, 'translate_document_text', translate)
    dialog.translate_file_button.click()
    worker = RealThread(target=jobs[0])
    worker.start()
    worker.join(2)
    assert not worker.is_alive()
    # The worker has emitted its signals, but the GUI has not delivered them.
    dialog.original_view.setPlainText('Draft typed before queued delivery')
    QtWidgets.QApplication.processEvents()
    assert not dialog.translation_running and dialog.translated_text == ''
    assert dialog.translated_view.toPlainText() == '' and dialog.progress_bar.value() == 0
    assert dialog.current_status == main.doc_text(dialog.lang, 'loaded')
    main.save_translation_history.assert_not_called()


def test_translation_thread_start_error_restores_the_editor_actions(loads, monkeypatch):
    dialog, _jobs = loads
    monkeypatch.setattr(main, '_resolve_translation_provider', lambda owner, engine, *args: engine)
    monkeypatch.setattr(main.threading, 'Thread', lambda **kw:
                        SimpleNamespace(start=mock.Mock(side_effect=RuntimeError('Worker unavailable'))))
    with mock.patch.object(main.QMessageBox, 'warning') as warning:
        dialog.translate_file_button.click()
    warning.assert_called_once()
    assert not dialog.translation_running and dialog._translation_cancel_event is None
    assert dialog.attach_button.isEnabled() and dialog.translate_file_button.isEnabled()
    assert dialog.original_view.toPlainText() == 'Existing draft'
