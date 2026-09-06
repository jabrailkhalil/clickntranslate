"""Reject native libraries that require a newer OS than the app advertises."""

import argparse
import json
from pathlib import Path
import plistlib

from macholib.MachO import MachO
from macholib.mach_o import LC_BUILD_VERSION, LC_VERSION_MIN_MACOSX

MACHO_MAGIC = {bytes.fromhex(value) for value in (
    'feedface', 'cefaedfe', 'feedfacf', 'cffaedfe',
    'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca',
)}


def version_tuple(value):
    return (value >> 16, (value >> 8) & 255, value & 255)


def audit(application):
    application = Path(application)
    info = plistlib.loads((application / 'Contents/Info.plist').read_bytes())
    minimum = tuple(int(part) for part in info['LSMinimumSystemVersion'].split('.'))
    minimum = (minimum + (0, 0))[:3]
    libraries, incompatible = [], []
    for path in sorted(application.rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open('rb') as stream:
            if stream.read(4) not in MACHO_MAGIC:
                continue
        targets = []
        for header in MachO(str(path)).headers:
            for load, command, _ in header.commands:
                if load.cmd == LC_BUILD_VERSION:
                    targets.append(version_tuple(command.minos))
                elif load.cmd == LC_VERSION_MIN_MACOSX:
                    targets.append(version_tuple(command.version))
        if not targets:
            raise ValueError(f'Missing deployment target: {path}')
        entry = {'file': str(path.relative_to(application)),
                 'minimum_macos': '.'.join(map(str, max(targets)))}
        libraries.append(entry)
        if max(targets) > minimum:
            incompatible.append(entry)
    if not libraries:
        raise ValueError('No Mach-O binaries found')
    return {'declared_minimum': '.'.join(map(str, minimum)),
            'libraries': libraries, 'incompatible': incompatible}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('application', type=Path)
    parser.add_argument('--report', type=Path, default=Path('build/macos/compatibility.json'))
    args = parser.parse_args()
    report = audit(args.application)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    if report['incompatible']:
        raise SystemExit('Libraries exceed the declared macOS target: ' + json.dumps(report['incompatible']))
    print(f"Verified {len(report['libraries'])} Mach-O files for macOS {report['declared_minimum']}.")


if __name__ == '__main__':
    main()
