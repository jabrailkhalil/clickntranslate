"""Inventory every immutable Windows package file after building/signing."""
import argparse
import hashlib
from pathlib import Path

MANIFEST = 'program-files.sha256'
PRESERVED = {'data', 'ocr', 'translators'}
REQUIRED = {
    'clickntranslate.exe', 'app/clickntranslateapp.exe',
    'app/_internal/ocrworker.exe', 'app/_internal/argosworker.exe',
    'app/_internal/clickntranslateupdater.exe', 'app/_internal/base_library.zip',
}


def preserved(relative):
    parts = relative.replace('\\', '/').lower().split('/')
    return parts[0] in PRESERVED or (len(parts) == 1 and parts[0].startswith('unins')
                                    and Path(parts[0]).suffix in {'.exe', '.dat', '.msg'})


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def program_files(root):
    files = {}
    for item in root.iterdir():
        if preserved(item.name) or item.name.lower() == MANIFEST:
            continue
        for file in item.rglob('*') if item.is_dir() else [item]:
            if file.is_file():
                files[file.relative_to(root).as_posix()] = file
    return files


def write_manifest(root, version):
    root = Path(root).resolve()
    files = program_files(root)
    missing = REQUIRED - {name.lower() for name in files}
    if missing:
        raise ValueError('Incomplete package: ' + ', '.join(sorted(missing)))
    lines = [f'# ClicknTranslate {version}']
    lines.extend(f'{digest(path)} *{name}' for name, path in sorted(files.items()))
    (root / MANIFEST).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return len(files)


def verify_manifest(root, version):
    root = Path(root).resolve()
    lines = (root / MANIFEST).read_text(encoding='utf-8-sig').splitlines()
    if not lines or lines[0] != f'# ClicknTranslate {version}':
        raise ValueError('Missing or mismatched program manifest version')
    expected = set()
    for line in lines[1:]:
        if len(line) < 67 or line[64:66] != ' *':
            raise ValueError('Malformed program manifest entry')
        checksum, relative = line[:64], line[66:].replace('\\', '/')
        parts = relative.replace('\\', '/').split('/')
        path = (root / relative).resolve()
        if (any(part in {'', '.', '..'} for part in parts) or ':' in relative
                or not path.is_relative_to(root) or preserved(relative)
                or relative.lower() == MANIFEST or relative.lower() in expected):
            raise ValueError('Invalid program manifest path: ' + relative)
        expected.add(relative.lower())
        if not path.is_file() or digest(path) != checksum.lower():
            raise ValueError('Missing or damaged program file: ' + relative)
    if REQUIRED - expected:
        raise ValueError('Program manifest omits required runtime files')
    actual = {name.lower() for name in program_files(root)}
    if actual != expected:
        raise ValueError('Unexpected program files: ' + ', '.join(sorted(actual - expected)))
    return len(expected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['write', 'verify'])
    parser.add_argument('root')
    parser.add_argument('version')
    args = parser.parse_args()
    count = (write_manifest if args.mode == 'write' else verify_manifest)(args.root, args.version)
    print(f'{args.mode}: {count} program files')
