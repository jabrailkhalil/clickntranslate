"""A rejected settings import must leave the running profile and OS state intact."""
import copy
import json
from unittest import mock

import pytest
from PyQt5 import QtWidgets, QtCore

import main
import settings_window as sw
from test_desktop_ux import app


class ImportOwner(QtWidgets.QWidget):
    save_config = main.DarkThemeApp.save_config

    def __init__(self):
        super().__init__()
        self.config = main.fresh_config('en')
        self.current_theme = self.config['theme']
        self.current_interface_language = 'en'
        self.start_minimized = False
        self.translation_mode = self.config['translation_mode']
        self.autostart = False
        self.set_autostart = mock.Mock(return_value=True)
        self.restart_all_hotkey_listeners = mock.Mock()
        self.apply_theme = mock.Mock()
        self.refresh_interface_language_ui = mock.Mock()
        self._sync_selection_quick_translate = mock.Mock()


class ImportPanel(QtWidgets.QWidget):
    import_settings = sw.SettingsWindow.import_settings

    def __init__(self, owner, export_path):
        super().__init__(owner)
        self.parent = owner
        self._settings_default_export_path = lambda: str(export_path)
        self.init_ui = mock.Mock()
        self.apply_theme = mock.Mock()
        self._set_settings_page = mock.Mock()


@pytest.fixture
def import_context(app, tmp_path, monkeypatch):
    export_path = tmp_path/'import.json'
    export_path.write_text(json.dumps(sw.settings_export_payload({
        'interface_language': 'ar', 'theme': 'Темная',
        'button_tooltips_enabled': False, 'autostart': True,
        'copy_history': False,
    })), encoding='utf-8')
    config_path = tmp_path/'config.json'
    owner = ImportOwner()
    panel = ImportPanel(owner, export_path)
    config_path.write_text(json.dumps(owner.config), encoding='utf-8')
    old_tooltips = app.property('buttonTooltipsEnabled')
    app.setProperty('buttonTooltipsEnabled', True)
    monkeypatch.setattr(main, 'get_data_file', lambda _name: str(config_path))
    monkeypatch.setattr(sw.QtWidgets.QFileDialog, 'getOpenFileName', lambda *_args: (str(export_path), ''))
    with mock.patch.object(sw.QMessageBox, 'warning') as warning, \
            mock.patch.object(sw.QMessageBox, 'information') as information:
        yield owner, panel, config_path, warning, information
    app.setProperty('buttonTooltipsEnabled', old_tooltips)
    owner.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


@pytest.mark.parametrize('error', [OSError('disk full'), PermissionError('locked config')])
def test_failed_import_restores_runtime_profile_without_changing_autostart(import_context, app, error):
    owner, panel, path, warning, information = import_context
    original_config = owner.config
    original_values = copy.deepcopy(owner.config)
    original_bytes = path.read_bytes()
    with mock.patch.object(main, 'write_json', side_effect=error):
        assert panel.import_settings() is None
    warning.assert_called_once()
    information.assert_not_called()
    assert path.read_bytes() == original_bytes
    assert owner.config is original_config
    assert owner.config == original_values
    assert owner.current_interface_language == 'en'
    assert owner.current_theme == original_values['theme']
    assert owner.autostart is False
    assert app.property('buttonTooltipsEnabled') is True
    owner.set_autostart.assert_not_called()
    owner.restart_all_hotkey_listeners.assert_not_called()
    owner.apply_theme.assert_not_called()
    panel.init_ui.assert_not_called()


def test_successful_import_commits_before_changing_autostart_and_refreshing_ui(import_context, app):
    owner, panel, path, warning, information = import_context
    def apply_autostart(enabled):
        persisted = json.loads(path.read_text(encoding='utf-8'))
        assert persisted['interface_language'] == 'ar'
        assert persisted['autostart'] is enabled
        return enabled
    owner.set_autostart.side_effect = apply_autostart
    assert panel.import_settings().name == 'import.json'
    warning.assert_not_called()
    information.assert_called_once()
    assert owner.config['interface_language'] == 'ar'
    assert owner.config['copy_history'] is False
    assert owner.current_theme == 'Темная'
    assert app.property('buttonTooltipsEnabled') is False
    owner.set_autostart.assert_called_once_with(True)
    owner.restart_all_hotkey_listeners.assert_called_once_with()
    panel.init_ui.assert_called_once_with()


def test_declined_autostart_persists_the_actual_disabled_state(import_context):
    owner, panel, path, warning, information = import_context
    owner.set_autostart.return_value = False
    assert panel.import_settings() is not None
    assert owner.autostart is False
    assert owner.config['autostart'] is False
    assert json.loads(path.read_text(encoding='utf-8'))['autostart'] is False
    warning.assert_not_called()
    information.assert_called_once()


def test_unchanged_autostart_is_not_written_to_the_operating_system(import_context):
    owner, panel, path, warning, information = import_context
    payload = sw.settings_export_payload({'interface_language': 'ar', 'autostart': False})
    path.with_name('import.json').write_text(json.dumps(payload), encoding='utf-8')
    assert panel.import_settings() is not None
    owner.set_autostart.assert_not_called()
    assert json.loads(path.read_text(encoding='utf-8'))['autostart'] is False
    warning.assert_not_called()
    information.assert_called_once()
