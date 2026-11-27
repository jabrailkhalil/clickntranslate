"""Reset commits a complete profile before touching runtime or OS services."""
import copy
import json
import threading
from unittest import mock

import pytest

import atomic_storage
import history_storage
import main
import settings_window as sw
from test_settings_import_reliability import import_context
from test_desktop_ux import app


class ResetMessages:
    Question, Warning, Information, YesRole, NoRole, Yes, No = range(7)
    records = []

    def __init__(self, parent=None):
        self.index = len(self.records)
        self.icon, self.text, self.yes = None, '', object()
        self.records.append(self)

    def setIcon(self, value):
        self.icon = value

    def setText(self, value):
        self.text = value

    def __getattr__(self, name):
        if name.startswith('set'):
            return lambda *_: None
        raise AttributeError(name)

    def addButton(self, label, role):
        return self.yes if role == self.YesRole else object()

    def exec_(self):
        return None

    def clickedButton(self):
        return self.yes if self.index == 0 else None


@pytest.mark.parametrize('failure', ('disk_full', 'replace_denied'))
def test_failed_reset_preserves_complete_profile_and_running_services(import_context, app, monkeypatch, failure):
    owner, panel, path, _warning, _information = import_context
    owner.config.update(copy_history=False, autostart=True)
    owner.autostart = True
    path.write_text(json.dumps(owner.config), encoding='utf-8')
    previous = copy.deepcopy(owner.config)
    identity, original = owner.config, path.read_bytes()
    tooltip_state = app.property('buttonTooltipsEnabled')
    ResetMessages.records = []
    monkeypatch.setattr(sw, 'QMessageBox', ResetMessages)
    monkeypatch.setattr(sw, 'get_data_file', lambda _name: str(path))
    owner.save_config = mock.Mock()
    if failure == 'disk_full':
        def interrupted(self, value, *args, **kwargs):
            yield '{"partial":'
            raise OSError('audit-only disk full')
        monkeypatch.setattr(json.JSONEncoder, 'iterencode', interrupted)
    else:
        monkeypatch.setattr(atomic_storage.os, 'replace', mock.Mock(side_effect=PermissionError('audit-only locked file')))
    sw.SettingsWindow.reset_settings(panel)
    assert path.read_bytes() == original
    assert owner.config is identity and owner.config == previous
    assert owner.autostart is True
    assert app.property('buttonTooltipsEnabled') == tooltip_state
    owner.set_autostart.assert_not_called()
    owner.save_config.assert_not_called()
    owner.restart_all_hotkey_listeners.assert_not_called()
    owner._sync_selection_quick_translate.assert_not_called()
    panel.init_ui.assert_not_called()
    assert [item.icon for item in ResetMessages.records] == [ResetMessages.Question, ResetMessages.Warning]


def test_successful_reset_uses_one_atomic_commit_before_runtime_changes(import_context, monkeypatch):
    owner, panel, path, _warning, _information = import_context
    owner.config.update(copy_history=False, main_translation_target_language='ja')
    owner.autostart = True
    owner.config['autostart'] = True
    ResetMessages.records = []
    monkeypatch.setattr(sw, 'QMessageBox', ResetMessages)
    monkeypatch.setattr(sw, 'get_data_file', lambda _name: str(path))
    owner.save_config = mock.Mock()
    def apply_autostart(enabled):
        committed = json.loads(path.read_text(encoding='utf-8'))
        assert committed['copy_history'] is main.DEFAULT_CONFIG['copy_history']
        assert committed['autostart'] is False
        assert committed['main_translation_target_language'] == owner.current_interface_language
        return False
    owner.set_autostart.side_effect = apply_autostart
    with mock.patch.object(atomic_storage, 'write_json', wraps=atomic_storage.write_json) as publish:
        sw.SettingsWindow.reset_settings(panel)
    publish.assert_called_once()
    owner.save_config.assert_not_called()
    owner.restart_all_hotkey_listeners.assert_called_once_with()
    owner._sync_selection_quick_translate.assert_called_once_with()
    panel.init_ui.assert_called_once_with()
    assert owner.config['main_translation_target_language'] == 'en'
    assert json.loads(path.read_text(encoding='utf-8')) == json.loads(json.dumps(owner.config))


@pytest.mark.parametrize('failure', ('declined', 'raised', 'correction_write'))
def test_reset_autostart_followup_still_applies_defaults_and_warns(import_context, monkeypatch, failure):
    owner, panel, path, _warning, _information = import_context
    owner.config.update(autostart=True, copy_history=False)
    owner.autostart = True
    owner.current_interface_language = 'ar'
    owner.set_autostart.return_value = True
    if failure == 'raised':
        owner.set_autostart.side_effect = OSError('audit-only OS reset failure')
    ResetMessages.records = []
    monkeypatch.setattr(sw, 'QMessageBox', ResetMessages)
    monkeypatch.setattr(sw, 'get_data_file', lambda _name: str(path))
    writer = main.write_json
    def correction(*args, **kwargs):
        if failure == 'correction_write':
            raise PermissionError('audit-only reset correction failure')
        return writer(*args, **kwargs)
    with mock.patch.object(main, 'write_json', side_effect=correction):
        sw.SettingsWindow.reset_settings(panel)
    persisted = json.loads(path.read_text(encoding='utf-8'))
    assert owner.config['copy_history'] is main.DEFAULT_CONFIG['copy_history']
    assert owner.config['interface_language'] == persisted['interface_language'] == 'ar'
    assert owner.autostart is True and owner.config['autostart'] is True
    assert persisted['autostart'] is (failure != 'correction_write')
    owner.restart_all_hotkey_listeners.assert_called_once_with()
    owner._sync_selection_quick_translate.assert_called_once_with()
    panel.init_ui.assert_called_once_with()
    assert ResetMessages.records[-1].icon == ResetMessages.Warning
    assert sw.settings_text('ar', 'settings_reset_done') in ResetMessages.records[-1].text


def test_reset_history_clear_serializes_with_an_append_already_in_progress(import_context, monkeypatch, tmp_path):
    owner, panel, path, _warning, _information = import_context
    owner.set_autostart.return_value = False
    histories = [tmp_path / name for name in ('translation_history.json', 'copy_history.json')]
    for history in histories:
        history.write_text('[{"text":"previous record"}]', encoding='utf-8')
    ResetMessages.records = []
    monkeypatch.setattr(sw, 'QMessageBox', ResetMessages)
    monkeypatch.setattr(ResetMessages, 'clickedButton', lambda self: self.yes if self.index in (0, 1) else None)
    monkeypatch.setattr(sw, 'get_data_file', lambda name: str(tmp_path / name))
    read, release = threading.Event(), threading.Event()
    mutate = history_storage.update_records
    def append(records):
        read.set()
        assert release.wait(5)
        return records + [{'text': 'append before clear'}]
    worker = threading.Thread(target=lambda: mutate(str(histories[0]), append))
    worker.start()
    assert read.wait(3)
    def clear(history, update):
        release.set()
        return mutate(history, update)
    try:
        with mock.patch.object(history_storage, 'update_records', side_effect=clear):
            sw.SettingsWindow.reset_settings(panel)
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive()
    assert all(json.loads(history.read_text(encoding='utf-8')) == [] for history in histories)
    assert all(history.with_name(history.name + '.lock').is_file() for history in histories)
