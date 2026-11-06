"""Synthetic vault races must not resurrect a replaced or deleted API key."""
import threading
from types import SimpleNamespace

import pytest

import provider_secrets as secrets


@pytest.fixture
def vault(monkeypatch):
    values, reads, writes = {}, [], []

    class Vault:
        def get_password(self, _service, name):
            reads.append(name)
            return values.get(name)

        def set_password(self, _service, name, value):
            writes.append((name, value))
            values[name] = value

        def delete_password(self, _service, name):
            writes.append((name, ''))
            values.pop(name, None)

    fake = Vault()
    monkeypatch.setattr(secrets, '_SESSION', {})
    monkeypatch.setattr(secrets, '_MISSING', {})
    monkeypatch.setattr(secrets, '_vault', lambda: fake)
    return SimpleNamespace(values=values, reads=reads, writes=writes, fake=fake)


@pytest.mark.parametrize('snapshot', ['old-key', 'missing', 'error'])
@pytest.mark.parametrize('replacement', ['rotated-synthetic-key', ''])
def test_inflight_vault_read_cannot_replace_newer_session_state(vault, snapshot, replacement):
    endpoint = 'https://synthetic.example.test/v1'
    name = secrets.account('openai-compatible', endpoint)
    vault.values[name] = 'old-synthetic-key'
    entered, release, changed = threading.Event(), threading.Event(), threading.Event()
    observed, errors = [], []
    get = vault.fake.get_password

    def stale_get(_service, account):
        value = vault.values.get(account) if snapshot == 'old-key' else ''
        entered.set()
        assert release.wait(3)
        if snapshot == 'error':
            raise RuntimeError('synthetic vault locked after the old read')
        return value

    vault.fake.get_password = stale_get

    def read():
        try:
            observed.append(secrets.get_key('openai-compatible', endpoint))
        except BaseException as error:
            errors.append(error)

    def change():
        try:
            assert secrets.set_key('openai-compatible', endpoint, replacement)
        except BaseException as error:
            errors.append(error)
        finally:
            changed.set()

    reader, writer = threading.Thread(target=read), threading.Thread(target=change)
    reader.start()
    try:
        assert entered.wait(3)
        vault.fake.get_password = get
        writer.start()
        assert changed.wait(3), 'A pending native read cannot block publishing a new session key'
    finally:
        release.set()
        reader.join(3)
        if writer.ident is not None:
            writer.join(3)
    assert not reader.is_alive() and not writer.is_alive() and not errors
    assert observed == [replacement]
    assert secrets.get_key('openai-compatible', endpoint) == replacement
    assert vault.values.get(name, '') == replacement
    assert name not in secrets._MISSING


def test_competing_writes_leave_the_vault_and_session_on_the_same_last_value(vault):
    endpoint = 'https://synthetic.example.test/v1'
    name = secrets.account('openai-compatible', endpoint)
    entered, release, second_done = threading.Event(), threading.Event(), threading.Event()
    errors = []
    store = vault.fake.set_password

    def delayed_store(service, account, value):
        if value == 'first-synthetic-key':
            entered.set()
            assert release.wait(3)
        store(service, account, value)

    vault.fake.set_password = delayed_store

    def set_value(value, done=None):
        try:
            assert secrets.set_key('openai-compatible', endpoint, value)
        except BaseException as error:
            errors.append(error)
        finally:
            if done is not None:
                done.set()

    first = threading.Thread(target=set_value, args=('first-synthetic-key',))
    second = threading.Thread(target=set_value, args=('second-synthetic-key', second_done))
    first.start()
    try:
        assert entered.wait(3)
        second.start()
        second_done.wait(.2)
    finally:
        release.set()
        first.join(3)
        if second.ident is not None:
            second.join(3)
    assert not first.is_alive() and not second.is_alive() and not errors
    assert secrets.get_key('openai-compatible', endpoint) == 'second-synthetic-key'
    assert vault.values[name] == 'second-synthetic-key'


def test_native_read_of_one_account_does_not_block_another_accounts_key_update(vault):
    first, other = 'https://first.example.test/v1', 'https://other.example.test/v1'
    first_name = secrets.account('openai-compatible', first)
    vault.values[first_name] = 'first-synthetic-key'
    entered, release, updated = threading.Event(), threading.Event(), threading.Event()
    observed = []
    read = vault.fake.get_password

    def blocking_read(service, account):
        if account == first_name:
            entered.set()
            assert release.wait(3)
        return read(service, account)

    vault.fake.get_password = blocking_read
    reader = threading.Thread(target=lambda: observed.append(secrets.get_key('openai-compatible', first)))
    writer = threading.Thread(target=lambda: (secrets.set_key('openai-compatible', other, 'other-synthetic-key'), updated.set()))
    reader.start()
    try:
        assert entered.wait(3)
        writer.start()
        assert updated.wait(1)
        assert secrets.get_key('openai-compatible', other) == 'other-synthetic-key'
    finally:
        release.set()
        reader.join(3)
        if writer.ident is not None:
            writer.join(3)
    assert observed == ['first-synthetic-key']
    assert not reader.is_alive() and not writer.is_alive()


@pytest.mark.parametrize('replacement', ['session-only-synthetic-key', ''])
def test_failed_native_write_keeps_its_new_session_value_and_clears_the_cached_miss(vault, monkeypatch, replacement):
    endpoint = 'https://synthetic.example.test/v1'
    name = secrets.account('openai-compatible', endpoint)
    assert secrets.get_key('openai-compatible', endpoint) == ''
    assert name in secrets._MISSING
    monkeypatch.setattr(secrets, '_vault', lambda: (_ for _ in ()).throw(RuntimeError('synthetic locked vault')))
    assert secrets.set_key('openai-compatible', endpoint, replacement) is False
    assert secrets.get_key('openai-compatible', endpoint) == replacement
    assert name not in secrets._MISSING
