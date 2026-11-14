"""Real signed catalog refresh/rotation with a portable temporary trust cache."""
import errno
import json
import os
from pathlib import Path

import pytest

from component_catalog import ComponentError, trusted_catalog
from test_component_updates import fixture_catalog, serve


@pytest.mark.parametrize('symlink_failure', [None, 'privilege', 'unsupported'])
def test_authenticated_root_rotation_and_restart_do_not_require_symlink_privileges(tmp_path, monkeypatch, symlink_failure):
    pytest.importorskip('tuf')
    from securesystemslib.signer import CryptoSigner
    from tuf.api.metadata import Metadata
    from tools.component_repository import keys, publish

    catalog, _ = fixture_catalog(tmp_path)
    source = tmp_path / 'catalog.json'
    source.write_text(json.dumps(catalog), encoding='utf-8')
    site, key_dir, client = tmp_path / 'site', tmp_path / 'keys', tmp_path / 'client'
    bootstrap = publish(source, site, key_dir).read_bytes()
    original_signers = keys(key_dir)
    symlink = os.symlink

    def constrained_symlink(target, destination, *args, **kwargs):
        if Path(destination).name == 'root.json' and symlink_failure:
            failure = PermissionError(errno.EPERM, 'Symlink privilege is unavailable')
            if symlink_failure == 'privilege':
                failure.winerror = 1314  # ERROR_PRIVILEGE_NOT_HELD
            else:
                failure = OSError(errno.ENOTSUP, 'The cache filesystem has no symlink support')
            raise failure
        return symlink(target, destination, *args, **kwargs)

    monkeypatch.setattr(os, 'symlink', constrained_symlink)
    with serve(site) as base:
        options = dict(metadata_url=base + 'metadata/', target_url=base + 'targets/', bootstrap=bootstrap)
        assert trusted_catalog(client, **options)['revision'] == 1

        # Rotate every role. Root v2 is authorized by both the old root and its
        # own new key, while subsequent online metadata uses only the new keys.
        rotated = Metadata.from_bytes(bootstrap)
        rotated.signed.version = 2
        replacement = {role: CryptoSigner.generate_ed25519() for role in original_signers}
        for role, signing in replacement.items():
            rotated.signed.add_key(signing.public_key, role)
            rotated.signed.revoke_key(original_signers[role].public_key.keyid, role)
            (key_dir / (role + '.pem')).write_bytes(signing.private_bytes)
        rotated.sign(original_signers['root'])
        rotated.sign(replacement['root'], append=True)
        rotated.to_file(str(site / 'metadata' / '2.root.json'))
        rotated.to_file(str(site / 'metadata' / 'root.json'))
        catalog['revision'] = 2
        source.write_text(json.dumps(catalog), encoding='utf-8')
        publish(source, site, key_dir)
        assert trusted_catalog(client, **options)['revision'] == 2

        # A new client object begins with the embedded v1 root, then authenticates
        # cached root history. Never trust the alias as an unsigned replacement.
        assert trusted_catalog(client, **options)['revision'] == 2
        current = client / 'trust' / 'root.json'
        assert Metadata.from_file(str(current)).signed.version == 2
        trusted_root = current.read_bytes()
        assert trusted_root == (client / 'trust' / 'root_history' / '2.root.json').read_bytes()

        timestamp_path = site / 'metadata' / 'timestamp.json'
        valid_timestamp = timestamp_path.read_bytes()
        unauthorized = Metadata.from_bytes(valid_timestamp)
        unauthorized.signed.version += 1
        unauthorized.sign(original_signers['timestamp'])
        unauthorized.to_file(str(timestamp_path))
        with pytest.raises(ComponentError, match='catalog_unavailable'):
            trusted_catalog(client, **options)
        assert current.read_bytes() == trusted_root
        timestamp_path.write_bytes(valid_timestamp)
        assert trusted_catalog(client, **options)['revision'] == 2

    # The portable alias may be an ordinary atomically replaced file; clients
    # must not need link creation merely to use their authenticated catalog.
    if symlink_failure:
        assert not (client / 'trust' / 'root.json').is_symlink()


@pytest.mark.parametrize('failure', [errno.ENOSPC, errno.EACCES], ids=['disk-full', 'permission-denied'])
def test_failed_root_alias_publication_preserves_the_previous_complete_envelope(tmp_path, monkeypatch, failure):
    pytest.importorskip('tuf')
    from tools.component_repository import publish

    catalog, _ = fixture_catalog(tmp_path)
    source = tmp_path / 'catalog.json'
    source.write_text(json.dumps(catalog), encoding='utf-8')
    site, client = tmp_path / 'site', tmp_path / 'client'
    bootstrap = publish(source, site, tmp_path / 'keys').read_bytes()
    with serve(site) as base:
        options = dict(metadata_url=base + 'metadata/', target_url=base + 'targets/', bootstrap=bootstrap)
        assert trusted_catalog(client, **options)['revision'] == 1
        alias = client / 'trust' / 'root.json'
        before = alias.read_bytes()
        replace = os.replace

        def rejected_alias(source, target, *args, **kwargs):
            if Path(target) == alias:
                raise OSError(failure, 'injected root alias write failure')
            return replace(source, target, *args, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(os, 'replace', rejected_alias)
            with pytest.raises(ComponentError, match='catalog_unavailable'):
                trusted_catalog(client, **options)
        assert alias.read_bytes() == before
        assert not list((client / 'trust').glob('tmp*'))
        assert trusted_catalog(client, **options)['revision'] == 1
