"""Create/sign component metadata. Private keys always live outside repositories.

This is a publisher, never imported by the GUI. Requires tuf and its crypto extra.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

from tuf.api.metadata import Metadata, Root, Targets, Snapshot, Timestamp, TargetFile, MetaFile
from securesystemslib.signer import CryptoSigner


def signer(path):
    from cryptography.hazmat.primitives import serialization
    return CryptoSigner(serialization.load_pem_private_key(path.read_bytes(), password=None))


def keys(directory):
    directory.mkdir(parents=True, exist_ok=True)
    output = {}
    for role in ('root', 'targets', 'snapshot', 'timestamp'):
        path = directory / (role + '.pem')
        if not path.exists():
            value = CryptoSigner.generate_ed25519()
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(value.private_bytes)
        output[role] = signer(path)
    return output


def publish(catalog_path, output, key_dir):
    signing = keys(key_dir)
    metadata = output / 'metadata'
    target_dir = output / 'targets'
    metadata.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    root_path = metadata / 'root.json'
    if root_path.exists():
        root = Metadata.from_file(str(root_path))
        for role, value in signing.items():
            if value.public_key.keyid not in root.signed.roles[role].keyids:
                raise RuntimeError('Existing root does not trust publisher key: ' + role)
    else:
        root = Metadata(Root(expires=now + timedelta(days=730), consistent_snapshot=True))
        for role, value in signing.items():
            root.signed.add_key(value.public_key, role)
        root.sign(signing['root'])
        root.to_file(str(root_path))
        root.to_file(str(metadata / '1.root.json'))
    content = catalog_path.read_bytes()
    catalog_file = target_dir / 'catalog.json'
    catalog_file.write_bytes(content)
    def next_version(role):
        previous = metadata / (role + '.json')
        return Metadata.from_file(str(previous)).signed.version + 1 if previous.exists() else 1
    version = next_version('targets')
    targets = Metadata(Targets(version=version, expires=now + timedelta(days=90)))
    info = TargetFile.from_file('catalog.json', str(catalog_file), ['sha256'])
    targets.signed.targets['catalog.json'] = info
    targets.sign(signing['targets'])
    targets.to_file(str(metadata / f'{version}.targets.json'))
    targets.to_file(str(metadata / 'targets.json'))
    # consistent_snapshot clients prefix targets with a digest.
    (target_dir / (info.hashes['sha256'] + '.catalog.json')).write_bytes(content)
    snapshot = Metadata(Snapshot(version=next_version('snapshot'), expires=now + timedelta(days=30)))
    snapshot.signed.meta['targets.json'] = MetaFile.from_data(version, targets.to_bytes(), ['sha256'])
    snapshot.sign(signing['snapshot'])
    snapshot.to_file(str(metadata / f'{snapshot.signed.version}.snapshot.json'))
    snapshot.to_file(str(metadata / 'snapshot.json'))
    timestamp = Metadata(Timestamp(version=next_version('timestamp'), expires=now + timedelta(days=7)))
    timestamp.signed.snapshot_meta = MetaFile.from_data(snapshot.signed.version, snapshot.to_bytes(), ['sha256'])
    timestamp.sign(signing['timestamp'])
    timestamp.to_file(str(metadata / 'timestamp.json'))
    return root_path


def refresh_online(output, key_dir):
    """Refresh expiry only; an online key cannot change approved catalog/targets."""
    now = datetime.now(timezone.utc)
    metadata = output / 'metadata'
    root = Metadata.from_file(str(metadata / 'root.json'))
    targets = Metadata.from_file(str(metadata / 'targets.json'))
    root.signed.verify_delegate('targets', targets.signed_bytes, targets.signatures)
    if targets.signed.expires <= now or root.signed.expires <= now:
        raise RuntimeError('Offline root/targets approval must be renewed before expiry')
    if targets.signed.expires - now < timedelta(days=14):
        print('::warning::Offline targets approval expires within 14 days; renew with the maintainer key.')
    if root.signed.expires - now < timedelta(days=30):
        print('::warning::Offline root expires within 30 days; perform an authenticated root rotation.')
    snapshot = Metadata.from_file(str(metadata / 'snapshot.json'))
    snapshot.signed.version += 1
    snapshot.signed.expires = min(now + timedelta(days=30), targets.signed.expires)
    snapshot.signed.meta['targets.json'] = MetaFile.from_data(targets.signed.version, targets.to_bytes(), ['sha256'])
    snapshot.sign(signer(key_dir / 'snapshot.pem'))
    snapshot.to_file(str(metadata / f'{snapshot.signed.version}.snapshot.json'))
    snapshot.to_file(str(metadata / 'snapshot.json'))
    timestamp = Metadata.from_file(str(metadata / 'timestamp.json'))
    timestamp.signed.version += 1
    timestamp.signed.expires = min(now + timedelta(days=7), targets.signed.expires)
    timestamp.signed.snapshot_meta = MetaFile.from_data(snapshot.signed.version, snapshot.to_bytes(), ['sha256'])
    timestamp.sign(signer(key_dir / 'timestamp.pem'))
    timestamp.to_file(str(metadata / 'timestamp.json'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--keys', type=Path, required=True)
    parser.add_argument('--refresh-online', action='store_true')
    args = parser.parse_args()
    # Refuse a caller's accidental attempt to write private keys into the project.
    project = Path(__file__).resolve().parents[1]
    if args.keys.resolve().is_relative_to(project):
        parser.error('Private keys must be outside the repository')
    if args.refresh_online:
        refresh_online(args.output, args.keys)
    elif args.catalog:
        publish(args.catalog, args.output, args.keys)
    else:
        parser.error('--catalog or --refresh-online is required')
