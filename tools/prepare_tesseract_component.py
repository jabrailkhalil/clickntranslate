"""Prepare a local Tesseract component candidate, never run its NSIS installer.

The caller extracts the official, digest-pinned installer with 7-Zip. This tool
copies no registry entries, shortcuts, installer plugins or uninstaller. Public
promotion additionally requires a complete third-party DLL license inventory.
"""
import argparse
import json
from pathlib import Path
import shutil
import stat
import sys
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from component_catalog import parse_catalog, safe_relative
from component_store import file_digest


def runtime_files(extracted):
    """Keep the transitive native dependency closure, excluding training UI DLLs."""
    import pefile  # maintainer/CI dependency, never required by the client
    dlls = {path.name.lower(): path for path in extracted.glob('*.dll')}
    system = {'advapi32.dll', 'bcrypt.dll', 'crypt32.dll', 'gdi32.dll', 'iphlpapi.dll',
              'kernel32.dll', 'msvcrt.dll', 'secur32.dll', 'user32.dll', 'wldap32.dll',
              'ws2_32.dll', 'ntdll.dll', 'ole32.dll', 'shell32.dll', 'ucrtbase.dll'}
    pending = [extracted / 'tesseract.exe']
    selected = {}
    while pending:
        path = pending.pop()
        if path.name.lower() in selected:
            continue
        selected[path.name.lower()] = path
        binary = pefile.PE(str(path), fast_load=True)
        try:
            binary.parse_data_directories(directories=[1, 13])
            for entry in [*getattr(binary, 'DIRECTORY_ENTRY_IMPORT', []),
                          *getattr(binary, 'DIRECTORY_ENTRY_DELAY_IMPORT', [])]:
                name = entry.dll.decode('ascii').lower()
                if name in dlls:
                    pending.append(dlls[name])
                elif name not in system and not name.startswith(('api-ms-win-', 'ext-ms-win-')):
                    raise RuntimeError('Unresolved native dependency: ' + name)
        finally:
            binary.close()
    return [selected[name] for name in sorted(selected)]


def extract_models(archive, destination, commit):
    """Read only flat model/license files from a checksum-verified source ZIP.

    Git archives contain a historical frk -> deu_latf alias. On Windows that
    becomes a 20-byte text file, not traineddata. Do not advertise/install it as
    a recognizer. The canonical deu_latf model remains available.
    """
    destination.mkdir(parents=True)
    prefix = 'tessdata_fast-' + commit + '/'
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            if not info.filename.startswith(prefix):
                continue
            name = info.filename[len(prefix):]
            if '/' in name or '\\' in name or not (name == 'LICENSE' or name.endswith('.traineddata')):
                continue
            safe_relative(name)
            if stat.S_ISLNK(info.external_attr >> 16):
                continue
            if info.file_size > 100 * 1024**2:
                raise RuntimeError('Unexpected model size')
            with source.open(info) as stream, (destination / name).open('xb') as output:
                shutil.copyfileobj(stream, output)


def prepare(extracted, models, sources, output):
    sources = {'runtime': {key: value for key, value in sources['runtime'].items()
                           if key in ('url', 'sha256', 'size')}, 'models': sources['models']}
    if output.exists():
        raise RuntimeError('Use a fresh output directory')
    output.mkdir(parents=True)
    runtime = output / 'runtime'
    runtime.mkdir()
    inventory = []
    for source in runtime_files(extracted):
        shutil.copy2(source, runtime / source.name)
        inventory.append({'file':source.name, 'size':source.stat().st_size, 'sha256':file_digest(source)})
    (runtime / 'DEPENDENCIES.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    for name in ('configs', 'tessconfigs'):
        shutil.copytree(extracted / 'tessdata' / name, runtime / 'tessdata' / name)
    shutil.copytree(extracted / 'doc', runtime / 'doc')
    shutil.copy2(models / 'LICENSE', runtime / 'doc/LICENSE-tessdata-fast.txt')
    (runtime / 'PROVENANCE.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    archive = output / 'tesseract-windows-x64-5.5.3-runtime.zip'
    expanded = 0
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for source in sorted(runtime.rglob('*')):
            if source.is_file():
                expanded += source.stat().st_size
                bundle.write(source, source.relative_to(runtime).as_posix())
    artifact = {'filename': archive.name, 'sha256': file_digest(archive),
                'size': archive.stat().st_size, 'unpacked_size': expanded,
                'redistribution_review': False}
    artifacts = {artifact['sha256']: {key: artifact[key] for key in ('size', 'unpacked_size')}}
    artifacts[artifact['sha256']]['urls'] = [
        'https://github.com/jabrailkhalil/clickntranslate-components/releases/download/'
        'tesseract-windows-x64-r1/' + archive.name]
    language_files = {}
    model_files = output / 'models'
    model_files.mkdir()
    for source in sorted(models.glob('*.traineddata')):
        if source.stem in ('osd', 'frk') or source.is_symlink():
            continue  # orientation data is not a text recognition language
        digest = file_digest(source)
        artifacts[digest] = {'size': source.stat().st_size, 'urls': [
            f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{sources["models"]["commit"]}/{source.name}']}
        language_files[source.stem] = [{'sha256': digest, 'kind': 'file',
                                       'destination': f'runtime/tessdata/{source.name}'}]
        # Local QA uses the very same bytes as the pinned upstream URL.
        shutil.copy2(source, model_files / digest)
    catalog = parse_catalog(json.dumps({'schema': 1, 'revision': 4, 'artifacts': artifacts,
        'bundles': [{'id': 'tesseract-windows-x64-fast-r1', 'component': 'ocr.tesseract',
            'revision': 1, 'contract': 1, 'channel': 'preview', 'os': 'windows', 'arch': 'x86_64',
            'min_os': '10', 'app': '>=1.8.2,<2', 'upstream': '5.5.3.20260724',
            'runtime': 'native', 'executable': 'runtime/tesseract.exe',
            'version_prefix': 'tesseract v5.5.3', 'languages': sorted(language_files),
            'language_files': language_files, 'models': 'tessdata_fast@' + sources['models']['commit'],
            'files': [{'sha256': artifact['sha256'], 'kind': 'zip', 'destination': 'runtime'}],
            'validation': {'standalone_windows': False, 'frozen_application': False,
                           'macos': False, 'linux': False, 'redistribution_review': False}}]}))
    for filename, value in (('catalog-candidate.json', catalog), ('runtime-artifact.json', artifact)):
        (output / filename).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(artifact))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extracted', type=Path, required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.extracted, args.models, json.loads(args.sources.read_text(encoding='utf-8')), args.output)
