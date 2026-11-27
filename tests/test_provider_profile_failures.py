"""API profile publication is complete before keys or active routing change."""
import copy
import errno
import json
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import api_providers as api
import atomic_storage
import provider_secrets as secrets
import provider_settings as providers
import settings_window as settings


@pytest.fixture
def profile_editor(tmp_path, monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app.platformName().split(':')[0] == 'offscreen'
    stored, writes = {}, []

    class Vault:
        def get_password(self, _service, name):
            return stored.get(name)

        def set_password(self, _service, name, value):
            writes.append((name, value))
            stored[name] = value

        def delete_password(self, _service, name):
            writes.append((name, ''))
            stored.pop(name, None)

    monkeypatch.setattr(secrets, '_SESSION', {})
    monkeypatch.setattr(secrets, '_MISSING', {})
    monkeypatch.setattr(secrets, '_vault', lambda: Vault())

    class Owner(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.current_interface_language, self.current_theme = 'en', 'Темная'
            self.config = dict(api_providers={'openai': {
                'url': api.BY_KEY['openai'].url, 'model': 'old-model', 'vision': False, 'direct': False}},
                translator_engine='Google', ocr_engine='Windows')

        def save_config(self):
            atomic_storage.write_json(path, self.config)

    class Adapter(QtWidgets.QWidget):
        auto_save_setting = settings.SettingsWindow.auto_save_setting

        def __init__(self, owner):
            super().__init__(owner)
            self.parent = owner
            self._refresh_ready_engine_choices = mock.Mock()
            self._set_translator_combo_silently = mock.Mock()
            self._set_ocr_combo_silently = mock.Mock()

    path = tmp_path / 'config.json'
    owner = Owner()
    adapter = Adapter(owner)
    owner.save_config()
    account = secrets.account('openai', api.BY_KEY['openai'].url)
    stored[account] = 'old-synthetic-key'
    page = providers.ProviderSettingsPage(adapter)
    page.model.setText('new-model')
    page.key.setText('new-synthetic-key')
    try:
        yield SimpleNamespace(owner=owner, adapter=adapter, page=page, path=path,
                              stored=stored, writes=writes, account=account)
    finally:
        page.deleteLater()
        owner.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()


@pytest.mark.parametrize('action', ['save', 'select'])
@pytest.mark.parametrize('failure', [errno.ENOSPC, errno.EACCES], ids=['disk-full', 'access-denied'])
def test_failed_profile_save_preserves_persisted_runtime_and_secret_state_then_retries(profile_editor, monkeypatch, action, failure):
    state = profile_editor
    before, old_bytes = copy.deepcopy(state.owner.config), state.path.read_bytes()
    with monkeypatch.context() as fault:
        def refuse(*_args):
            raise OSError(failure, 'synthetic config publication failure')
        fault.setattr(atomic_storage.os, 'replace', refuse)
        (state.page.save_profile if action == 'save' else state.page.select_profile)()
    assert state.owner.config == before and state.path.read_bytes() == old_bytes
    assert state.stored[state.account] == 'old-synthetic-key' and state.writes == []
    assert secrets.get_key('openai', api.BY_KEY['openai'].url) == 'old-synthetic-key'
    assert state.page.key.text() == 'new-synthetic-key' and state.page.model.text() == 'new-model'
    assert state.page.status.text() and state.page.status.text() != providers.provider_text('en', 'saved')
    state.adapter._set_translator_combo_silently.assert_not_called()
    state.adapter._set_ocr_combo_silently.assert_not_called()
    assert not list(state.path.parent.glob('.cnt-save-*.tmp'))
    state.page.save.click()
    saved = json.loads(state.path.read_text(encoding='utf-8'))
    assert saved['api_providers']['openai']['model'] == 'new-model'
    assert 'new-synthetic-key' not in state.path.read_text(encoding='utf-8')
    assert state.stored[state.account] == 'new-synthetic-key'
    assert state.page.key.text() == ''


def test_direct_routing_is_published_together_and_the_failed_selection_can_retry(profile_editor, monkeypatch):
    state = profile_editor
    state.page.usage.setCurrentIndex(state.page.usage.findData('direct'))
    assert state.page.save_profile()
    before, old_bytes = copy.deepcopy(state.owner.config), state.path.read_bytes()
    replace = atomic_storage.os.replace
    attempts = []

    def refuse_routing(source, target):
        attempts.append(source)
        # select_profile first republishes the connection, then its routing.
        if len(attempts) > 1:
            raise OSError(errno.ENOSPC, 'synthetic routing publication failure')
        return replace(source, target)

    with monkeypatch.context() as fault:
        fault.setattr(atomic_storage.os, 'replace', refuse_routing)
        state.page.select_profile()
    assert state.owner.config == before
    assert state.path.read_bytes() == old_bytes
    state.adapter._set_translator_combo_silently.assert_not_called()
    state.adapter._set_ocr_combo_silently.assert_not_called()
    state.page.select_profile()
    saved = json.loads(state.path.read_text(encoding='utf-8'))
    assert saved['translator_engine'] == 'openai' and saved['ocr_engine'] == 'OpenAI API'
    state.adapter._set_translator_combo_silently.assert_called_once_with('openai')
    state.adapter._set_ocr_combo_silently.assert_called_once_with('OpenAI API')


def test_successful_profile_with_unavailable_vault_keeps_the_existing_session_only_policy(profile_editor, monkeypatch):
    state = profile_editor
    monkeypatch.setattr(secrets, '_vault', mock.Mock(side_effect=RuntimeError('synthetic locked vault')))
    assert state.page.save_profile()
    assert secrets.get_key('openai', api.BY_KEY['openai'].url) == 'new-synthetic-key'
    assert state.stored[state.account] == 'old-synthetic-key'
    assert state.page.status.text() == providers.provider_text('en', 'session')
    assert json.loads(state.path.read_text(encoding='utf-8'))['api_providers']['openai']['model'] == 'new-model'
    assert 'new-synthetic-key' not in state.path.read_text(encoding='utf-8')


@pytest.mark.parametrize('language', ['en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id'])
def test_failed_profile_save_shows_a_localized_nonsecret_error(profile_editor, monkeypatch, language):
    state = profile_editor
    state.page.lang = language
    with monkeypatch.context() as fault:
        fault.setattr(state.owner, 'save_config', mock.Mock(side_effect=OSError('synthetic-key/private-path')))
        assert state.page.save_profile() is False
    message = state.page.status.text()
    assert message and 'synthetic-key' not in message and 'private-path' not in message
    if language != 'en':
        state.page.lang = 'en'
        with monkeypatch.context() as fault:
            fault.setattr(state.owner, 'save_config', mock.Mock(side_effect=OSError('failed')))
            assert state.page.save_profile() is False
        assert state.page.status.text() != message
