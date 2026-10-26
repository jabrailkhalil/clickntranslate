"""Prepare one standalone Windows engine runtime, never an application build.

Dependency resolution runs here, on the maintainer/CI machine. The client never
asks PyPI to select packages. Files under output are public artifacts only.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from component_store import ComponentStore, file_digest
from component_catalog import safe_relative


def prepare(output, recipe_path=None):
    import requests
    recipe = json.loads((recipe_path or PROJECT / 'components/recipes/rapidocr-windows-x64.json').read_text())
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'python-embed.zip'
    if not archive.exists():
        with requests.get(recipe['python_url'], stream=True, timeout=60) as response:
            response.raise_for_status()
            with archive.open('wb') as target:
                for block in response.iter_content(1024 * 1024):
                    target.write(block)
    if file_digest(archive) != recipe['python_sha256']:
        raise RuntimeError('CPython archive checksum mismatch')
    wheels = output / 'wheelhouse'
    wheels.mkdir(exist_ok=True)
    subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
        '--dest', str(wheels), *recipe['requirements']], check=True)
    if recipe.get('requirements_no_deps'):
        subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
            '--no-deps', '--dest', str(wheels), *recipe['requirements_no_deps']], check=True)
    locks = []
    for wheel in sorted(wheels.glob('*.whl')):
        with zipfile.ZipFile(wheel) as bundle:
            metadata_path = next(n for n in bundle.namelist() if n.endswith('.dist-info/METADATA'))
            from email.parser import BytesParser
            metadata = BytesParser().parsebytes(bundle.read(metadata_path))
            locks.append(f"{metadata['Name']}=={metadata['Version']} --hash=sha256:{file_digest(wheel)}")
    locked = output / 'requirements.lock'
    locked.write_text('\n'.join(locks) + '\n', encoding='utf-8')
    runtime = output / 'runtime'
    if runtime.exists():
        raise RuntimeError('Use a fresh output directory for packaging; runtime already exists')
    ComponentStore.extract(archive, runtime, 100 * 1024**2)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps',
        '--find-links', str(wheels), '--require-hashes', '--only-binary=:all:',
        '--target', str(runtime / 'site-packages'), '-r', str(locked)], check=True)
    # pip's generated command launchers reference the maintainer interpreter.
    # Components use only their explicit adapter; retain libraries and licenses.
    generated = runtime / 'site-packages' / 'bin'
    if generated.exists():
        if generated.is_symlink() or not generated.resolve().is_relative_to(runtime.resolve()):
            raise RuntimeError('Unsafe generated scripts directory')
        shutil.rmtree(generated)
    if recipe.get('msvc'):
        from prepare_msvc import prepare as prepare_msvc
        prepare_msvc(output, runtime, recipe['msvc'])
    from runtime_dlls import audit
    native_audit = audit(runtime)
    (runtime / 'NATIVE-DEPENDENCIES.json').write_text(json.dumps(native_audit, indent=2), encoding='utf-8')
    adapter = runtime / 'adapter'
    adapter.mkdir()
    for name in recipe.get('adapter_files', ('ocr_worker.py', 'rapidocr_models.py', 'ocr_text_layout.py', 'ocr_paragraphs.py', 'runtime_bootstrap.py')):
        safe_relative(name)
        source = (PROJECT / 'src' / name).resolve()
        if source.suffix != '.py' or not source.is_relative_to((PROJECT / 'src').resolve()):
            raise RuntimeError('Unsafe adapter source path')
        (adapter / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, adapter / name)
    pth = runtime / 'python312._pth'
    pth.write_text('python312.zip\n.\nsite-packages\nadapter\n', encoding='utf-8')
    shutil.copy2(locked, runtime / 'requirements.lock')
    shutil.copy2(PROJECT / 'LICENSE', runtime / 'LICENSE-ClicknTranslate.txt')
    (runtime / 'COMPONENT.json').write_text(json.dumps(recipe, indent=2), encoding='utf-8')
    # Preserve upstream wheel licenses/notices in the archived dist-info folders.
    notices = ['CPython: LICENSE.txt in this package.',
               'Python libraries: licenses and METADATA in each site-packages/*.dist-info/.',
               'Requirements and exact wheel hashes: requirements.lock.',
               'Microsoft Visual C++ runtime: pinned official source and individual hashes in MICROSOFT-RUNTIME.json; license: https://aka.ms/vc14/license.',
               'Application adapter: https://github.com/jabrailkhalil/clickntranslate (project LICENSE).']
    (runtime / 'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(notices)+'\n', encoding='utf-8')
    runtime_archive = output / safe_relative(recipe.get('filename', 'rapidocr-windows-x64-cp312-runtime.zip'))
    expanded = 0
    with zipfile.ZipFile(runtime_archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(runtime.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                expanded += path.stat().st_size
                bundle.write(path, path.relative_to(runtime).as_posix())
    summary = {'filename': runtime_archive.name, 'sha256': file_digest(runtime_archive),
               'size': runtime_archive.stat().st_size, 'unpacked_size': expanded,
               'recipe': recipe, 'wheel_lock': locked.read_text(encoding='utf-8')}
    (output / 'runtime-artifact.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('filename', 'sha256', 'size', 'unpacked_size')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recipe', type=Path)
    args = parser.parse_args()
    if (sys.platform != 'win32' or sys.version_info[:2] != (3, 12)
            or platform.machine().lower() not in ('amd64', 'x86_64')):
        parser.error('Run Windows x64 CPython 3.12; other profiles require their own native preparation')
    prepare(args.output.resolve(), args.recipe)
