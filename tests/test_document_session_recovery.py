"""Exercise saving and reopening documents through real Qt editors."""
import json
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import main
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
