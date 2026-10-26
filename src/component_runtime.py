"""Bridge between the trusted component store and existing OCR UI/workers."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from component_catalog import (ComponentError, choose_bundle, component_store_path,
                               trusted_catalog, safe_relative)
from component_store import ComponentStore


def managed_runtime(engine='rapidocr'):
    if engine != 'rapidocr':
        return None
    try:
        return ComponentStore(component_store_path()).active('ocr.rapidocr')
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
            old = None  # allow Update to repair a damaged optional installation
        bundle = choose_bundle(catalog, 'ocr.rapidocr', APP_VERSION,
            channel=channel or os.environ.get('CLICKNTRANSLATE_COMPONENT_CHANNEL', 'stable'),
            languages=old['receipt']['languages'] if old else ())
        return store.install(catalog, bundle, download, validate_rapidocr, check_cancel, progress)
