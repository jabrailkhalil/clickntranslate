"""Delete names its outcome and never acts on an ambiguous endpoint draft."""
import copy
from unittest import mock

import pytest

import api_providers as api
import provider_secrets as secrets
import provider_settings as providers
from test_provider_profile_failures import profile_editor


LANGUAGES = ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id')


@pytest.mark.parametrize('language', LANGUAGES)
def test_delete_reports_deletion_and_clears_only_the_saved_key(profile_editor, language):
    state = profile_editor
    before = copy.deepcopy(state.owner.config)
    state.page.lang = language
    state.page.delete.click()
    assert state.account not in state.stored
    assert api.credential('openai', state.owner.config) == ''
    assert state.owner.config == before
    assert state.page.key.text() == ''
    assert state.page.key.placeholderText() == providers.provider_text(language, 'empty')
    message = state.page.status.text()
    assert message and message not in (providers.provider_text(language, 'saved'), providers.provider_text(language, 'session'))
    if language == 'en':
        assert message == 'Key deleted.'
    elif language == 'ru':
        assert message == 'Ключ удалён.'
    else:
        assert message != 'Key deleted.'
    state.adapter._refresh_ready_engine_choices.assert_called_once()


@pytest.mark.parametrize('failure', ['factory', 'read', 'delete-before', 'delete-after'])
def test_failed_native_delete_disables_session_and_reports_uncertain_persistence(profile_editor, monkeypatch, failure):
    state = profile_editor
    before = copy.deepcopy(state.owner.config)

    class FaultyVault:
        def get_password(self, _service, name):
            if failure == 'read':
                raise RuntimeError('synthetic-private-vault-detail')
            return state.stored.get(name)

        def delete_password(self, _service, name):
            if failure == 'delete-after':
                state.stored.pop(name, None)
            raise RuntimeError('synthetic-private-vault-detail')

    with monkeypatch.context() as fault:
        factory = mock.Mock(side_effect=RuntimeError('synthetic-private-vault-detail')) if failure == 'factory' else lambda: FaultyVault()
        fault.setattr(secrets, '_vault', factory)
        state.page.delete.click()
        assert api.credential('openai', state.owner.config) == ''
    assert state.owner.config == before
    message = state.page.status.text()
    assert 'disabled for this session' in message
    assert 'could not' in message.lower() and 'may' in message.lower() and 'restart' in message.lower()
    assert 'synthetic-private-vault-detail' not in message
    assert message != providers.provider_text('en', 'session')
    # A native backend may fail before OR after removing its persistent copy.
    assert (state.account in state.stored) == (failure != 'delete-after')


def test_failed_delete_warning_is_localized(profile_editor, monkeypatch):
    state = profile_editor
    state.page.lang = 'ru'
    monkeypatch.setattr(secrets, '_vault', mock.Mock(side_effect=RuntimeError('synthetic locked vault')))
    state.page.delete.click()
    assert api.credential('openai', state.owner.config) == ''
    message = state.page.status.text()
    assert 'может' in message and 'перезапуск' in message
    assert message != providers.provider_text('ru', 'session')


def custom_profile(state):
    provider, a, b = 'openai-compatible', 'https://saved.test/v1', 'https://draft.test/v1'
    state.owner.config['api_providers'][provider] = dict(url=a, model='saved-model', vision=False, direct=False)
    state.stored.update({secrets.account(provider, a): 'synthetic-a', secrets.account(provider, b): 'synthetic-b'})
    state.page.service.setCurrentIndex(state.page.service.findData(provider))
    return provider, a, b


@pytest.mark.parametrize('draft', ['https://draft.test/v1', '', 'not-an-address'], ids=['different', 'empty', 'invalid'])
def test_changed_address_refuses_delete_before_any_key_or_draft_mutation(profile_editor, monkeypatch, draft):
    state = profile_editor
    provider, a, b = custom_profile(state)
    state.page.address.setText(draft)
    state.page.key.setText('typed-synthetic-draft')
    before = copy.deepcopy(state.owner.config)
    drafts = copy.deepcopy(state.page.drafts)
    stored = dict(state.stored)
    with mock.patch.object(secrets, 'set_key', wraps=secrets.set_key) as change:
        state.page.delete.click()
    change.assert_not_called()
    assert state.page.address.text() == draft and state.page.key.text() == 'typed-synthetic-draft'
    assert state.page.drafts == drafts and state.owner.config == before and state.stored == stored
    assert state.page.status.text() == 'Save or restore the API address before deleting its saved key.'
    state.adapter._refresh_ready_engine_choices.assert_not_called()
    assert secrets.get_key(provider, a) == 'synthetic-a' and secrets.get_key(provider, b) == 'synthetic-b'


@pytest.mark.parametrize('suffix', ['/', '///', '/  '], ids=['slash', 'slashes', 'slash-and-space'])
def test_equivalent_saved_address_keeps_existing_account_normalization(profile_editor, suffix):
    state = profile_editor
    provider, a, b = custom_profile(state)
    state.page.address.setText('  ' + a + suffix)
    state.page.delete.click()
    assert secrets.get_key(provider, a) == ''
    assert secrets.get_key(provider, b) == 'synthetic-b'


def test_locked_vault_delete_can_retry_after_unlock_without_reviving_the_session(profile_editor, monkeypatch):
    state = profile_editor
    with monkeypatch.context() as fault:
        fault.setattr(secrets, '_vault', mock.Mock(side_effect=RuntimeError('locked')))
        state.page.delete.click()
    assert api.credential('openai', state.owner.config) == ''
    assert state.account in state.stored
    state.page.delete.click()
    assert state.account not in state.stored
    assert api.credential('openai', state.owner.config) == ''
    assert state.page.status.text() == 'Key deleted.'


def test_explicitly_saving_changed_address_then_delete_only_deletes_its_saved_account(profile_editor):
    state = profile_editor
    provider, a, b = custom_profile(state)
    state.page.address.setText(b)
    state.page.key.clear()
    assert state.page.save_profile()
    before = copy.deepcopy(state.owner.config)
    state.page.delete.click()
    assert state.owner.config == before
    assert api.profile(provider, state.owner.config)['url'] == b
    assert secrets.get_key(provider, a) == 'synthetic-a'
    assert secrets.get_key(provider, b) == ''


def test_restoring_saved_address_after_refusal_allows_delete_without_saving(profile_editor):
    state = profile_editor
    provider, a, b = custom_profile(state)
    state.page.address.setText(b)
    state.page.delete.click()
    state.page.address.setText(a)
    state.page.delete.click()
    assert secrets.get_key(provider, a) == ''
    assert secrets.get_key(provider, b) == 'synthetic-b'


def test_switching_service_then_deleting_never_uses_the_previous_provider_account(profile_editor):
    state = profile_editor
    provider, a, b = custom_profile(state)
    state.page.delete.click()
    assert secrets.get_key(provider, a) == ''
    assert state.stored[state.account] == 'old-synthetic-key'
    state.page.service.setCurrentIndex(state.page.service.findData('openai'))
    assert api.credential('openai', state.owner.config) == 'old-synthetic-key'
    state.page.delete.click()
    assert state.account not in state.stored
    assert secrets.get_key(provider, b) == 'synthetic-b'
