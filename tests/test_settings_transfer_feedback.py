"""The visible file actions keep transactions atomic and never freeze the GUI."""
import copy
import json
import threading
from pathlib import Path
from unittest import mock

import pytest
from PyQt5 import QtCore
from PyQt5.QtTest import QTest

import settings_window as sw
from test_desktop_ux import app, window
from test_ui_operations import wait_until


def test_export_button_snapshots_without_credentials_and_keeps_the_old_file_on_failure(window, app, tmp_path, monkeypatch):
    window.show_settings()
    panel = window.settings_window
    target = tmp_path/'settings.json'
    target.write_text('previous valid export', encoding='utf-8')
    window.config.update(copy_history=True, api_key='private-key', nested={'password': 'private-password'})
    monkeypatch.setattr(sw.QtWidgets.QFileDialog, 'getSaveFileName', lambda *_args: (str(target), ''))
    entered, release = threading.Event(), threading.Event()
    original_write = sw._write_settings_payload
    snapshots = []
    def slow_write(path, payload):
        snapshots.append(copy.deepcopy(payload))
        entered.set()
        assert release.wait(3)
        return original_write(path, payload)
    monkeypatch.setattr(sw, '_write_settings_payload', slow_write)
    with mock.patch.object(sw.QMessageBox, 'information') as information, mock.patch.object(sw.QMessageBox, 'warning') as warning:
        try:
            panel.export_settings_btn.click()
            wait_until(app, entered.is_set)
            assert target.read_text() == 'previous valid export'
            window.config['copy_history'] = False
            assert window._ui_operation.active
            release.set()
            wait_until(app, lambda: not window._ui_operation.active)
            information.assert_called_once()
            warning.assert_not_called()
            result = json.loads(target.read_text(encoding='utf-8'))
            assert result['settings']['copy_history'] is True
            assert 'api_key' not in result['settings'] and 'password' not in result['settings']['nested']
            assert not list(tmp_path.glob('*.tmp'))
        finally:
            release.set()
        previous = target.read_bytes()
        with mock.patch.object(sw.os, 'replace', side_effect=PermissionError('locked export')):
            panel.export_settings_btn.click()
            wait_until(app, lambda: not window._ui_operation.active)
        assert target.read_bytes() == previous
        warning.assert_called_once()
        assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('malformed', [False, True])
def test_import_button_reads_in_background_before_committing_or_refreshing(window, app, tmp_path, monkeypatch, malformed):
    window.show_settings()
    panel = window.settings_window
    source = tmp_path/'import.json'
    source.write_text('{invalid' if malformed else json.dumps(sw.settings_export_payload({
        'interface_language': 'ar', 'theme': 'Светлая', 'copy_history': False,
        'autostart': window.autostart})), encoding='utf-8')
    monkeypatch.setattr(sw.QtWidgets.QFileDialog, 'getOpenFileName', lambda *_args: (str(source), ''))
    original_config = copy.deepcopy(window.config)
    entered, release = threading.Event(), threading.Event()
    original_read = sw._read_settings_payload
    def slow_read(path, lang):
        entered.set()
        assert release.wait(3)
        return original_read(path, lang)
    monkeypatch.setattr(sw, '_read_settings_payload', slow_read)
    with mock.patch.object(sw.QMessageBox, 'information') as information, mock.patch.object(sw.QMessageBox, 'warning') as warning:
        try:
            panel.import_settings_btn.click()
            wait_until(app, entered.is_set)
            assert window.config == original_config
            window.save_config.assert_not_called()
            release.set()
            wait_until(app, lambda: not window._ui_operation.active)
            if malformed:
                assert window.config == original_config
                window.save_config.assert_not_called()
                warning.assert_called_once()
                information.assert_not_called()
            else:
                assert window.current_interface_language == 'ar'
                assert window.current_theme == 'Светлая'
                assert window.config['copy_history'] is False
                assert window.ui_root.updatesEnabled()
                warning.assert_not_called()
                information.assert_called_once()
        finally:
            release.set()


def test_cancelled_file_picker_never_starts_work_or_changes_the_profile(window, app, monkeypatch):
    window.show_settings()
    panel = window.settings_window
    config = copy.deepcopy(window.config)
    monkeypatch.setattr(sw.QtWidgets.QFileDialog, 'getOpenFileName', lambda *_args: ('', ''))
    monkeypatch.setattr(sw.QtWidgets.QFileDialog, 'getSaveFileName', lambda *_args: ('', ''))
    with mock.patch('ui_operations.threading.Thread') as worker:
        panel.import_settings_btn.click()
        panel.export_settings_btn.click()
        app.processEvents()
        worker.assert_not_called()
    assert window.config == config and not window._ui_operation.active
