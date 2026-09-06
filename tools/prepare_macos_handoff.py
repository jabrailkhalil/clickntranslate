"""Export the current application sources, including uncommitted dependencies.

The archive is a source snapshot, not a Mac binary or a replacement for Git.
Only application/build/test/documentation paths are eligible; user data, local
models, credentials, environments and marketing projects are excluded.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('icons', 'tests', 'tools', 'docs', 'packaging', '.github', 'installer', 'launcher', 'store')
EXCLUDED_PARTS = {'__pycache__', '.pytest_cache', 'data', 'build', 'dist', 'node_modules'}
SOURCE_SUFFIXES = {'.py', '.sh', '.ps1', '.bat', '.cmd', '.md', '.txt', '.ini', '.spec',
                   '.yml', '.yaml', '.json', '.plist', '.xml', '.svg', '.png', '.ico',
                   '.desktop', '.c', '.h', '.cpp', '.manifest', '.rc', '.iss', '.cff', '.bib',
                   '.in', '.ttf', '.otf', '.webp', '.jpg', '.jpeg', '.gif', '.qrc'}
REQUIRED = {'main.py', 'settings_window.py', 'ClicknTranslate-macos.spec',
            'requirements-macos.txt', 'docs/MACOS_HANDOFF.md',
            'tools/setup_macos_env.sh', 'tools/build_macos_release.sh',
            'tools/smoke_macos_bundle.py', '.github/workflows/macos.yml',
            'macos_desktop.py', 'macos_hotkeys.py', 'macos_ocr.py',
            'button_styles.py', 'ui_scaling.py', 'window_appearance.py',
            'icons/icon.png', 'packaging/macos/entitlements.plist'}


def source_files():
    candidates = [path for path in ROOT.iterdir() if path.is_file()]
    for directory in DIRECTORIES:
        candidates.extend((ROOT / directory).rglob('*'))
    for path in sorted(set(candidates)):
        relative = path.relative_to(ROOT)
        if path.is_symlink() or not path.is_file() or EXCLUDED_PARTS.intersection(relative.parts):
            continue
        if relative.as_posix() in {'HANDOFF.md', 'build.py'}:
            continue
        if relative.parts[0] in DIRECTORIES:
            eligible = path.suffix.lower() in SOURCE_SUFFIXES
        else:
            eligible = (path.suffix.lower() in {'.py', '.spec', '.txt', '.md', '.ini', '.cff', '.bib', '.bat'}
                        or path.name in {'LICENSE', '.gitignore', '.gitattributes'})
        if eligible:
            yield path, relative.as_posix()


def verify(archive):
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive entries')
        manifest = json.loads(bundle.read('HANDOFF_MANIFEST.json'))
        expected = manifest['files']
        if set(names) != set(expected) | {'HANDOFF_MANIFEST.json'}:
            raise ValueError('Archive entries do not match its manifest')
        if not REQUIRED.issubset(expected):
            raise ValueError('Required application sources are missing')
        for name, metadata in expected.items():
            if name.startswith('/') or '\\' in name or '..' in name.split('/'):
                raise ValueError(f'Invalid archive path: {name}')
            payload = bundle.read(name)
            if len(payload) != metadata['bytes'] or hashlib.sha256(payload).hexdigest() != metadata['sha256']:
                raise ValueError(f'Checksum mismatch: {name}')
    print(f'Verified {len(expected)} source files: {archive}')


def create(archive):
    files = list(source_files())
    if not REQUIRED.issubset(name for _, name in files):
        raise ValueError('The current working tree is missing required Mac files')
    try:
        revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                  capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    manifest = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'base_git_commit': revision,
        'source': 'Current working tree, including uncommitted application changes; not just the base Git commit.',
        'native_mac_build_verified': False,
        'instructions': 'docs/MACOS_HANDOFF.md',
        'files': {},
    }
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path, relative in files:
            payload = path.read_bytes()
            # Windows checkouts can contain CRLF; Bash needs LF on the Mac.
            if path.suffix == '.sh':
                payload = payload.replace(b'\r\n', b'\n')
            manifest['files'][relative] = {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
            info = zipfile.ZipInfo(relative)
            info.create_system = 3
            info.external_attr = (0o100755 if path.suffix == '.sh' else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, payload)
        bundle.writestr('HANDOFF_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    verify(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path, help='Verify an existing source snapshot without extracting it')
    parser.add_argument('--output', type=Path, help='Destination ZIP; defaults to releases/')
    args = parser.parse_args()
    if args.verify:
        verify(args.verify)
        return
    sys.path.insert(0, str(ROOT))
    from app_version import APP_VERSION
    create(args.output or ROOT / 'releases' / f'Click-n-Translate-{APP_VERSION}-macos-source.zip')


if __name__ == '__main__':
    main()
