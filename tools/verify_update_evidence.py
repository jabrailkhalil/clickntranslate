"""Fail unless the exact Windows candidate passed every required legacy transition.

This check is read-only. It does not promote, replace or publish any release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

REQUIRED = {('1.6.0', 'zip'), ('1.6.1', 'zip'), ('1.7.0', 'zip'),
            ('1.7.0', 'setup'), ('1.8.0', 'zip'), ('1.8.0', 'setup')}


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(candidate, version, receipts):
    archive = candidate / f'Click-n-Translate-{version}-windows-portable-x64.zip'
    setup = candidate / f'Click-n-Translate-{version}-windows-x64-installer.exe'
    zip_hash, setup_hash = sha256(archive), sha256(setup)
    with zipfile.ZipFile(archive) as package:
        count = sum(not item.is_dir() for item in package.infolist())
    accepted = {}
    rejected = []
    for path in receipts:
        receipt = json.loads(path.read_text(encoding='utf-8'))
        key = (receipt.get('old_version'), receipt.get('mode'))
        if key not in REQUIRED:
            continue
        valid = (
            receipt.get('status') == 'passed'
            and receipt.get('new_version') == version
            and receipt.get('new_sha256') == zip_hash
            and receipt.get('helper_override') is False
            and receipt.get('invoked_helper_sha256') == receipt.get('old_helper_sha256')
            and bool(receipt.get('old_helper_sha256'))
            and receipt.get('helper_exit_code') == 0
            and receipt.get('helper_failure_reported') is not True
            and receipt.get('preferences_preserved') is True
            and receipt.get('verified_program_files') == count
            and bool(receipt.get('restarted_gui_pid'))
            and (key[1] != 'setup' or receipt.get('new_setup_sha256') == setup_hash)
        )
        ack = path.parent / 'restart-ready.txt'
        valid = valid and ack.is_file() and ack.read_text(encoding='utf-8').strip() == version
        if valid:
            accepted[key] = str(path)
        else:
            rejected.append(str(path))
    missing = REQUIRED - accepted.keys()
    return {'passed': not missing, 'version': version, 'zip_sha256': zip_hash,
            'setup_sha256': setup_hash, 'program_files': count,
            'accepted': {old + '/' + mode: path for (old, mode), path in sorted(accepted.items())},
            'missing': [old + '/' + mode for old, mode in sorted(missing)], 'rejected': rejected}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.candidate, args.version, args.receipts.rglob('result.json'))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
