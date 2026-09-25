"""Identity selection must never overwrite an existing private signing key."""
import pytest

from tools import macos_signing


@pytest.mark.parametrize('name', ['', 'x\nO = another', '${HOME}', 'a' * 65, '/tmp/key', ' x'])
def test_rejects_unsafe_subject_before_creating_files(monkeypatch, tmp_path, name):
    target = tmp_path / 'signer'
    monkeypatch.setenv('CLICKNTRANSLATE_SIGNING_DIR', str(target))
    with pytest.raises(ValueError):
        macos_signing.setup(name)
    assert not target.exists()


def test_keeps_existing_identity_with_same_name(monkeypatch, tmp_path):
    (tmp_path / 'identity.json').write_text('{}')
    monkeypatch.setenv('CLICKNTRANSLATE_SIGNING_DIR', str(tmp_path))
    identity = {'name': 'jabrailkhalil', 'sha1': 'original'}
    monkeypatch.setattr(macos_signing, 'load_identity', lambda: identity)
    assert macos_signing.setup('jabrailkhalil') is identity


def test_refuses_to_replace_differently_named_identity(monkeypatch, tmp_path):
    (tmp_path / 'identity.json').write_text('{}')
    monkeypatch.setenv('CLICKNTRANSLATE_SIGNING_DIR', str(tmp_path))
    monkeypatch.setattr(macos_signing, 'load_identity', lambda: {'name': 'previous'})
    with pytest.raises(RuntimeError, match='another signing identity'):
        macos_signing.setup('jabrailkhalil')
