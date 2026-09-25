"""Package a verified Windows stage, retaining the legacy manifest's hidden flag."""
import argparse
from pathlib import Path
import shutil
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_manifest import MANIFEST, program_files, verify_manifest


def package(root, destination, version):
    root = Path(root).resolve()
    destination = Path(destination).resolve()
    if destination.is_relative_to(root):
        raise ValueError('The output archive must be outside the program folder')
    count = verify_manifest(root, version)
    files = program_files(root)
    files[MANIFEST] = root / MANIFEST
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for relative, path in sorted(files.items()):
            info = zipfile.ZipInfo.from_file(path, 'ClicknTranslate/' + relative)
            info.create_system = 0  # DOS attributes are understood by Windows Explorer.
            info.compress_type = zipfile.ZIP_DEFLATED
            if relative == MANIFEST:
                info.external_attr |= 0x02  # FILE_ATTRIBUTE_HIDDEN
            with path.open('rb') as source, archive.open(info, 'w') as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError('Archive CRC verification failed')
        info = archive.getinfo('ClicknTranslate/' + MANIFEST)
        if not info.external_attr & 0x02:
            raise ValueError('Archive lost the manifest hidden attribute')
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    parser.add_argument('destination')
    parser.add_argument('version')
    args = parser.parse_args()
    print(f'Packaged {package(args.root, args.destination, args.version)} verified program files.')
