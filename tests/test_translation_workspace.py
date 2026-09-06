"""Exercise editable translation drafts and real Qt reflow, without network."""

import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets, sip
from PyQt5.QtTest import QTest, QSignalSpy

import main
import translater
from qt_layout_test_support import ensure_layout_fonts
from window_appearance import install_window_appearance


@pytest.fixture
def app():
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    application.setQuitOnLastWindowClosed(False)
    ensure_layout_fonts(application)
    return application


@pytest.fixture
def workspace(app, monkeypatch):
    monkeypatch.setattr(main, 'get_cached_config', lambda: dict(main.DEFAULT_CONFIG, translator_engine='Lingva'))
    monkeypatch.setattr(main, 'save_translation_history', mock.Mock())
    monkeypatch.setattr(main, 'save_copy_history', mock.Mock())
    monkeypatch.setattr(main.platform_support, 'copy_text', mock.Mock())
    dialog = main.TranslationResultDialog(None, 'Привет, мир', auto_copy=True, lang='ru',
                                         source_text='Hello world', source_lang='en', target_lang='ru')
    dialog.show()
    app.processEvents()
    yield dialog
    if not sip.isdeleted(dialog):
        dialog.close()
        dialog.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


@pytest.fixture
def requests(monkeypatch):
    jobs = []
    monkeypatch.setattr(main.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=lambda: jobs.append(target)))
    return jobs


def test_translate_uses_the_current_draft_and_selected_engine(workspace, requests, monkeypatch):
    translate = mock.Mock(return_value='Дополненный перевод')
    monkeypatch.setattr(translater, 'translate_text', translate)
    workspace.source_edit.setPlainText('A revised source\nwith another paragraph')
    assert not requests  # Typing alone must not send every edit to a server.
    workspace.translate_button.click()
    assert not workspace.translate_button.isEnabled()
    assert not workspace.source_edit.isReadOnly()
    assert not workspace.text_edit.isReadOnly()
    requests.pop()()
    args, kwargs = translate.call_args
    assert args == ('A revised source\nwith another paragraph', 'en', 'ru')
    assert kwargs['engine'] == 'Lingva'
    assert callable(kwargs['cancel_callback'])
    assert workspace.source_edit.toPlainText() == args[0]
    assert workspace.text_edit.toPlainText() == 'Дополненный перевод'
    main.save_translation_history.assert_called_once_with(args[0], 'Дополненный перевод', 'ru')
    main.platform_support.copy_text.assert_called_once_with('Дополненный перевод')


def test_worker_thread_delivers_result_to_the_gui(app, workspace, monkeypatch):
    monkeypatch.setattr(translater, 'translate_text', mock.Mock(return_value='Ответ из рабочего потока'))
    responses = QSignalSpy(workspace._retranslated_signal)
    workspace.translate_button.click()
    if not responses:
        assert responses.wait(3000)
    app.processEvents()
    assert workspace.text_edit.toPlainText() == 'Ответ из рабочего потока'
    assert workspace.translate_button.isEnabled()
    main.save_translation_history.assert_called_once()


def test_clearing_source_keeps_result_and_disables_empty_requests(workspace, requests):
    workspace.source_edit.clear()
    workspace.translate_button.click()
    workspace._start_retranslate()  # The keyboard shortcut has the same guard.
    assert not requests
    assert not workspace.translate_button.isEnabled()
    assert workspace.copy_button.isEnabled()
    assert workspace.text_edit.toPlainText() == 'Привет, мир'


def test_swap_exchanges_the_edited_texts_as_well_as_languages(workspace, requests, monkeypatch):
    workspace.source_edit.setPlainText('An edited original')
    workspace.text_edit.setPlainText('Отредактированный перевод')
    translate = mock.Mock(return_value='Back translation')
    monkeypatch.setattr(translater, 'translate_text', translate)
    workspace.swap_button.click()
    assert workspace.source_edit.toPlainText() == 'Отредактированный перевод'
    assert workspace.text_edit.toPlainText() == 'An edited original'
    assert (workspace.source_code, workspace.target_code) == ('ru', 'en')
    requests.pop()()
    assert translate.call_args.args == ('Отредактированный перевод', 'ru', 'en')
    assert workspace.text_edit.toPlainText() == 'Back translation'


@pytest.mark.parametrize('field', ['source_edit', 'text_edit'])
def test_late_answer_cannot_overwrite_edits_or_copy_to_clipboard(workspace, requests, monkeypatch, field):
    cancelled = []
    translate = mock.Mock(side_effect=lambda *args, **kw: cancelled.append(kw['cancel_callback']()) or 'Stale answer')
    monkeypatch.setattr(translater, 'translate_text', translate)
    workspace.translate_button.click()
    old_request = workspace._request_id
    getattr(workspace, field).setPlainText('A new draft')
    requests.pop()()
    # Also cover a response that was already queued on the GUI thread.
    workspace._retranslated_signal.emit(old_request, 'Queued stale answer', '')
    assert cancelled == [True]
    assert getattr(workspace, field).toPlainText() == 'A new draft'
    assert workspace.text_edit.toPlainText() != 'Queued stale answer'
    main.platform_support.copy_text.assert_not_called()
    main.save_translation_history.assert_not_called()
    assert workspace.translate_button.isEnabled()


def test_new_language_request_wins_when_old_answer_arrives_last(workspace, requests, monkeypatch):
    translate = mock.Mock(side_effect=lambda text, source, target, **kw: {'de': 'Hallo Welt', 'ru': 'Старый ответ'}[target])
    monkeypatch.setattr(translater, 'translate_text', translate)
    workspace.translate_button.click()
    old_request = workspace._request_id
    workspace.target_combo.setCurrentIndex(workspace.target_combo.findData('de'))
    assert len(requests) == 2
    requests[1]()
    requests[0]()
    workspace._retranslated_signal.emit(old_request, 'An old queued answer', '')
    assert workspace.text_edit.toPlainText() == 'Hallo Welt'
    assert workspace.target_combo.currentData() == 'de'
    main.save_translation_history.assert_called_once_with('Hello world', 'Hallo Welt', 'de')
    main.platform_support.copy_text.assert_called_once_with('Hallo Welt')


def test_close_cancels_pending_translation_without_history_or_copy(workspace, requests, monkeypatch):
    monkeypatch.setattr(translater, 'translate_text', lambda *args, **kw: 'Late answer')
    workspace.translate_button.click()
    request_id = workspace._request_id
    workspace.close()
    requests.pop()()
    workspace._retranslated_signal.emit(request_id, 'Queued answer', '')
    main.platform_support.copy_text.assert_not_called()
    main.save_translation_history.assert_not_called()


def test_appearance_changes_do_not_cancel_an_active_translation(app, workspace, requests, monkeypatch):
    translate = mock.Mock(return_value='Ответ после смены оформления')
    monkeypatch.setattr(translater, 'translate_text', translate)
    workspace.translate_button.click()
    for theme in ['Светлая', 'Темная', 'Светлая']:
        workspace.refresh_theme(theme)
        for editor in (workspace.source_edit, workspace.text_edit):
            editor.zoomIn(1)
            editor.zoomOut(1)
        workspace.resize(440, 650)
        app.processEvents()
        assert not workspace.translate_button.isEnabled()
    requests.pop()()
    assert not translate.call_args.kwargs['cancel_callback']()
    assert workspace.text_edit.toPlainText() == 'Ответ после смены оформления'
    main.save_translation_history.assert_called_once()


def test_error_preserves_both_fields_and_exposes_full_details(workspace, requests, monkeypatch):
    error = 'Service unavailable ' + 'detail ' * 300
    monkeypatch.setattr(translater, 'translate_text', mock.Mock(side_effect=RuntimeError(error)))
    size = workspace.size()
    workspace.translate_button.click()
    requests.pop()()
    assert workspace.source_edit.toPlainText() == 'Hello world'
    assert workspace.text_edit.toPlainText() == 'Привет, мир'
    assert error in workspace.status_label.toolTip()
    assert workspace.size() == size
    assert workspace.translate_button.isEnabled()
    main.platform_support.copy_text.assert_not_called()


def test_plain_enter_inserts_a_line_and_control_enter_translates(app, workspace, requests):
    workspace.activateWindow()
    workspace.source_edit.setFocus()
    workspace.source_edit.moveCursor(QtGui.QTextCursor.End)
    app.processEvents()
    QTest.keyClick(workspace.source_edit, QtCore.Qt.Key_Return)
    assert workspace.source_edit.toPlainText().endswith('\n')
    assert not requests
    QTest.keyClick(workspace.source_edit, QtCore.Qt.Key_Return, QtCore.Qt.ControlModifier)
    app.processEvents()
    assert len(requests) == 1


def test_source_and_translation_have_independent_undo_histories(workspace):
    source, result = workspace.source_edit.toPlainText(), workspace.text_edit.toPlainText()
    workspace.source_edit.insertPlainText('Source edit ')
    workspace.text_edit.insertPlainText('Result edit ')
    workspace.source_edit.undo()
    assert workspace.source_edit.toPlainText() == source
    assert workspace.text_edit.toPlainText() != result
    workspace.text_edit.undo()
    assert workspace.text_edit.toPlainText() == result


@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
@pytest.mark.parametrize('lang', ['ru', 'en', 'de', 'fr', 'es', 'zh'])
def test_both_editors_wrap_and_remain_accessible_after_reflow(app, monkeypatch, theme, lang):
    monkeypatch.setattr(main, 'get_cached_config', lambda: dict(main.DEFAULT_CONFIG))
    text = ('Long text without losing words. Длинный текст. 一段需要换行的文字。\n' + 'W' * 240 + '\n') * 15
    dialog = main.TranslationResultDialog(None, text, auto_copy=False, lang=lang, theme=theme,
                                         source_text=text, source_lang='en', target_lang='ru')
    dialog.show()
    try:
        for width, height, horizontal in [(900, 580, True), (420, 620, False), (760, 470, True)]:
            dialog.resize(width, height)
            for _ in range(3): app.processEvents()
            assert dialog._panel_orientation is horizontal
            assert not dialog.source_panel.geometry().intersects(dialog.result_panel.geometry())
            for editor in (dialog.source_edit, dialog.text_edit):
                assert editor.isVisible() and editor.toPlainText() == text
                assert editor.viewport().height() >= 60
                assert not editor.horizontalScrollBar().isVisible()
                assert editor.document().size().width() <= editor.viewport().width() + 1
                assert editor.verticalScrollBar().maximum() > 0
                editor.verticalScrollBar().setValue(editor.verticalScrollBar().maximum())
                rect = QtCore.QRect(editor.mapTo(dialog, QtCore.QPoint()), editor.size())
                assert dialog.rect().contains(rect)
            for button in (dialog.translate_button, dialog.copy_button, dialog.close_button):
                assert button.width() >= button.sizeHint().width(), (lang, button.text())
                rect = QtCore.QRect(button.mapTo(dialog, QtCore.QPoint()), button.size())
                assert dialog.rect().contains(rect)
            dialog.hide()
            dialog.show()
            app.processEvents()
            assert dialog.source_edit.toPlainText() == text
            assert dialog.text_edit.toPlainText() == text
    finally:
        dialog.close()
        dialog.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_scale_and_theme_changes_preserve_drafts_and_fit_a_small_screen(app, workspace):
    appearance = install_window_appearance(app, 100, 'Темная')
    drafts = (workspace.source_edit.toPlainText(), workspace.text_edit.toPlainText())
    try:
        for available in [QtCore.QRect(0, 0, 1920, 1080), QtCore.QRect(0, 0, 800, 600)]:
            with mock.patch.object(appearance, 'available_geometry', return_value=available):
                for theme in ['Светлая', 'Темная', 'Светлая']:
                    for percent in [80, 100, 150, 200, 80]:
                        appearance.refresh(percent, theme)
                        app.processEvents()
                        assert workspace.width() <= available.width()
                        assert workspace.height() <= available.height()
                        assert (workspace.source_edit.toPlainText(), workspace.text_edit.toPlainText()) == drafts
                        for editor in (workspace.source_edit, workspace.text_edit):
                            assert (editor.palette().color(QtGui.QPalette.Text).lightness() > 128) == (theme == 'Темная')
                            assert editor.isVisible()
    finally:
        workspace.close()
        app.processEvents()
        app.removeEventFilter(appearance)
        del app._dialog_appearance
        app.setProperty('ui_theme', None)
        appearance.deleteLater()
