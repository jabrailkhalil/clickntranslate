"""Late document parsers cannot replace a newer file, draft or translation."""
import threading
from threading import Thread as RealThread
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets, sip

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
