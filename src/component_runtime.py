"""Bridge between the trusted component store and existing OCR UI/workers."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import csv
import io
from contextlib import contextmanager, nullcontext

from component_catalog import (ComponentError, choose_bundle, component_store_path,
                               trusted_catalog, safe_relative, materialize_bundle, runtime_command)
from component_store import ComponentStore


def managed_runtime(engine='rapidocr'):
    components = {'rapidocr':'ocr.rapidocr', 'tesseract':'ocr.tesseract', 'argos':'translation.argos',
                  'hymt':'translation.hymt', 'easyocr':'ocr.easyocr'}
    if engine not in components:
        return None
    try:
        runtime = ComponentStore(component_store_path()).active(components[engine])
        if runtime:
            from component_catalog import current_platform
            target = current_platform()
            if any(runtime['receipt'].get(key) != target[key] for key in ('os', 'arch')):
                return None  # copied portable profile from another operating system
        return runtime
    except ComponentError:
        # A damaged optional install must not prevent the settings UI opening.
        return None


def worker_environment():
    import platform_support
    environment = platform_support.system_subprocess_env()
    for name in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONUSERBASE',
                 'CLICKNTRANSLATE_RAPIDOCR_MODEL_DIR', 'CLICKNTRANSLATE_UPDATE_TOKEN',
                 'GITHUB_TOKEN', 'GH_TOKEN', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
                 'GEMINI_API_KEY', 'DEEPL_API_KEY'):
        environment.pop(name, None)
    environment['PYTHONNOUSERSITE'] = '1'
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    return environment


def validate_rapidocr(folder, receipt):
    folder = Path(folder)
    command = [str(folder / safe_relative(receipt['python'])),
               str(folder / safe_relative(receipt['worker']))]
    with tempfile.TemporaryDirectory(prefix='clickntranslate_component_probe_') as temporary:
        request = Path(temporary) / 'request.json'
        request.write_text(json.dumps({'action': 'validate', 'engine': 'rapidocr',
            'root_dir': str(folder), 'allow_download': False}), encoding='utf-8')
        result = subprocess.run([*command, str(request)], capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), env=worker_environment())
        try:
            payload = json.loads(result.stdout)
        except ValueError as exc:
            raise ComponentError('validation_failed', 'invalid worker response') from exc
        if result.returncode or payload.get('error'):
            raise ComponentError('validation_failed', str(payload.get('error') or 'worker exit')[:300])
        return payload


def install_rapidocr(download, *, check_cancel=lambda: None, progress=lambda *_: None,
                     channel=None, root=None, catalog_loader=trusted_catalog):
    from app_version import APP_VERSION
    store = ComponentStore(root or component_store_path())
    with store.lock():
        check_cancel()
        catalog = catalog_loader(store.root)
        try:
            old = store.active('ocr.rapidocr')
        except ComponentError:
            old = store.describe('ocr.rapidocr')  # keep the saved selection while repairing a runtime
        bundle = choose_bundle(catalog, 'ocr.rapidocr', APP_VERSION,
            channel=channel or os.environ.get('CLICKNTRANSLATE_COMPONENT_CHANNEL', 'stable'),
            languages=old['receipt']['languages'] if old else ())
        return store.install(catalog, bundle, download, validate_rapidocr, check_cancel, progress)


def tesseract_generation(command, root=None):
    """Identify an app-owned command, including a still-leased previous version."""
    store = ComponentStore(root or component_store_path())
    path = Path(command).resolve()
    parent = store.root / 'generations'
    if not path.is_relative_to(parent):
        return None
    relative = path.relative_to(parent)
    if len(relative.parts) < 3:
        raise ComponentError('invalid_generation')
    folder = store.generation(relative.parts[0])
    try:
        receipt = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
        if (receipt['component'] != 'ocr.tesseract' or receipt['generation'] != folder.name
                or Path(runtime_command(folder, receipt)[0]).resolve() != path):
            raise ComponentError('installed_component_damaged', 'Tesseract receipt')
    except (OSError, ValueError, KeyError) as error:
        raise ComponentError('installed_component_damaged', 'Tesseract receipt') from error
    return store, folder, receipt


@contextmanager
def tesseract_lease(command):
    generation = tesseract_generation(command)
    with generation[0].lease(generation[1].name) if generation else nullcontext():
        yield


def validate_tesseract(folder, receipt, check_cancel=lambda: None):
    """Actually initialize every installed recognizer before atomic activation."""
    from PIL import Image, ImageDraw
    folder = Path(folder)
    command = runtime_command(folder, receipt)
    data = folder / 'runtime/tessdata'
    if {path.stem for path in data.glob('*.traineddata')} != set(receipt['languages']):
        raise ComponentError('validation_failed', 'Tesseract model set')
    environment = worker_environment()
    environment.pop('TESSDATA_PREFIX', None)
    kwargs = dict(capture_output=True, text=True, encoding='utf-8', errors='replace',
                  timeout=45, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), env=environment)
    result = subprocess.run([*command, '--version'], **kwargs)
    prefix = receipt.get('version_prefix', 'tesseract ')
    if result.returncode or not result.stdout.startswith(prefix):
        raise ComponentError('validation_failed', 'Tesseract version')
    with tempfile.TemporaryDirectory(prefix='clickntranslate_tesseract_probe_') as temporary:
        image = Image.new('RGB', (500, 100), 'white')
        ImageDraw.Draw(image).text((20, 30), '12345 OCR test', fill='black')
        probe = Path(temporary) / 'probe.png'
        image.save(probe)
        for language in receipt['languages']:
            check_cancel()
            result = subprocess.run([*command, str(probe), 'stdout', '--tessdata-dir', str(data),
                '-l', language, '--oem', '1', '--psm', '6'], **kwargs)
            if result.returncode:
                raise ComponentError('validation_failed', f'Tesseract {language}')


def recognize_tesseract(image, command, data_dir, language, psm, positions=False):
    """Pass model paths as argv entries, including Windows paths with spaces.

    pytesseract's Windows config-string splitting can retain literal quotes in
    --tessdata-dir. A direct native call also avoids its global command/env state.
    """
    with tempfile.TemporaryDirectory(prefix='clickntranslate_tesseract_') as temporary:
        source = Path(temporary) / 'input.png'
        image.save(source)
        environment = worker_environment()
        environment.pop('TESSDATA_PREFIX', None)
        result = subprocess.run([command, str(source), 'stdout', '--tessdata-dir', str(data_dir),
            '-l', language, '--oem', '1', '--psm', str(psm), 'tsv' if positions else 'txt'],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), env=environment)
        if result.returncode:
            raise ComponentError('ocr_failed', f'Tesseract exit {result.returncode}')
        if not positions:
            return result.stdout
        rows = list(csv.DictReader(io.StringIO(result.stdout), delimiter='\t'))
        columns = ('text', 'left', 'top', 'width', 'height')
        if rows and not set(columns).issubset(rows[0]):
            raise ComponentError('ocr_failed', 'invalid TSV')
        columns += tuple(name for name in ('page_num', 'block_num', 'par_num', 'line_num')
                         if rows and name in rows[0])
        return {name: [(int(row[name]) if name in ('left', 'top', 'width', 'height') else row[name])
                       for row in rows] for name in columns}


def install_tesseract(download, *, languages=(), remove_languages=(), legacy_data_dirs=(),
                      check_cancel=lambda: None, progress=lambda *_: None,
                      channel=None, root=None, catalog_loader=trusted_catalog):
    """Update engine/languages as one immutable generation; legacy data stays intact."""
    from app_version import APP_VERSION
    store = ComponentStore(root or component_store_path())
    with store.lock():
        check_cancel()
        try:
            old = store.active('ocr.tesseract')
        except ComponentError:
            old = store.describe('ocr.tesseract')
        if old and remove_languages and not languages:
            return store.remove_languages('ocr.tesseract', remove_languages,
                lambda folder, receipt: validate_tesseract(folder, receipt, check_cancel), check_cancel, progress)
        catalog = catalog_loader(store.root)
        installed = set(old['receipt']['languages']) if old else set()
        if not old:
            for data_dir in legacy_data_dirs:
                installed.update(path.stem for path in Path(data_dir).glob('*.traineddata')
                                 if path.stem != 'osd')
        base = installed if old or installed else ({'eng', 'rus'} if not languages else set())
        selected = (base | set(languages)) - set(remove_languages)
        bundle = choose_bundle(catalog, 'ocr.tesseract', APP_VERSION,
            channel=channel or os.environ.get('CLICKNTRANSLATE_COMPONENT_CHANNEL', 'stable'),
            languages=selected)
        return store.install(catalog, materialize_bundle(bundle, selected), download,
                             lambda folder, receipt: validate_tesseract(folder, receipt, check_cancel),
                             check_cancel, progress)
