"""Collect only signed distribution files for an unpublished Actions artifact."""

import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SIGNER = 'E5E6A8042F96479E560AED29881A6F06D4D374A2'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stage():
    app = ROOT / 'dist/ClicknTranslate.app'
    metadata = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    version = metadata['CFBundleShortVersionString']
    architecture = platform.machine()
    if platform.system() != 'Darwin' or architecture not in {'arm64', 'x86_64'}:
        raise RuntimeError('Prepare the artifacts on their native Mac architecture.')
    signature = json.loads((ROOT / 'build/macos/release-signature.json').read_text())
    if signature['sha1'] != EXPECTED_SIGNER or signature['architecture'] != architecture:
        raise RuntimeError('The verification report does not match the permanent signer and architecture.')
    subprocess.run([
        '/usr/bin/codesign', '--verify', '--deep', '--strict', '-R',
        '=identifier "io.github.jabrailkhalil.clickntranslate" and certificate root = '
        f'H"{EXPECTED_SIGNER.lower()}"', str(app),
    ], check=True)
    stem = f'Click-n-Translate-{version}-macos-{architecture}'
    sources = [ROOT / 'releases' / f'{stem}.{extension}' for extension in ('dmg', 'zip')]
    checksums = {}
    for line in (ROOT / 'releases' / f'{stem}.sha256').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        checksums[Path(name.strip().lstrip('*')).name] = digest
    files = []
    for source in sources:
        digest = sha256(source)
        if checksums.get(source.name) != digest:
            raise RuntimeError(f'Build checksum mismatch: {source.name}')
        files.append({'name': source.name, 'bytes': source.stat().st_size, 'sha256': digest})

    # Refuse an existing directory rather than mixing different builds.
    destination = ROOT / 'build/macos/prepared'
    destination.mkdir(parents=True, exist_ok=False)
    for source in sources:
        shutil.copyfile(source, destination / source.name)
    # Basenames make the checksum file usable after downloading on another OS.
    (destination / f'{stem}.sha256').write_text(''.join(
        f"{item['sha256']}  {item['name']}\n" for item in files))
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    manifest = {
        'version': version,
        'architecture': architecture,
        'source_commit': commit,
        'source_ref': os.environ.get('GITHUB_REF', ''),
        'workflow_run': os.environ.get('GITHUB_RUN_ID', ''),
        'build_macos': platform.mac_ver()[0],
        'minimum_macos': metadata.get('LSMinimumSystemVersion'),
        'signer_sha1': EXPECTED_SIGNER,
        'signature': 'permanent self-signed',
        'notarized': bool(signature.get('notarized', False)),
        'runtime_tested': False,
        'tests_skipped': 'Explicit prepare_release workflow mode',
        'published_release': False,
        'files': files,
    }
    (destination / 'BUILD.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (destination / 'README.txt').write_text(
        f"Click'n'Translate {version} / macOS {architecture}\n"
        f"Source commit: {commit}\n\n"
        'Prepared for a later coordinated release. No release has been published.\n'
        'Permanent self-signed certificate; no Apple Developer ID or notarization.\n'
        'Runtime tests were skipped. See BUILD.json and docs/MACOS_QA.md.\n\n'
        'Upload the .dmg, .zip and .sha256 files unchanged to the future release.\n'
        'On Windows, keep the inner .zip intact to preserve Mac permissions and symlinks.\n'
        'The .app is inside the .dmg and .zip; it is not a separate Windows executable.\n'
        'Download these files before the Actions artifact expires (90 days).\n'
    )
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    stage()
