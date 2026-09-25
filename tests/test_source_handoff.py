"""Source snapshots retain build inputs and only the public signing certificate."""
from tools import prepare_macos_handoff as handoff


def test_snapshot_includes_cross_platform_build_sources():
    names = {name for _, name in handoff.source_files()}
    assert handoff.REQUIRED <= names
    assert 'launcher/ClicknTranslateUpdateBootstrap.cs' in names
    assert 'packaging/macos/release-certificate.pem' in names
    assert not any(name.startswith(('data/', '.venv/', '.tmp/', 'releases/')) for name in names)


def test_snapshot_does_not_include_private_key_material(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, 'ROOT', tmp_path)
    folder = tmp_path / 'packaging/macos'
    folder.mkdir(parents=True)
    for name in ('release-certificate.pem', 'key.pem', 'identity.p12', 'signer.keychain-db'):
        (folder / name).write_text('fixture')
    assert {name for _, name in handoff.source_files()} == {'packaging/macos/release-certificate.pem'}
