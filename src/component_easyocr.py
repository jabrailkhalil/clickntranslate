"""EasyOCR shared-model transactions without importing Torch into the GUI."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from component_catalog import (ComponentError, choose_bundle, component_store_path,
                               materialize_bundle, runtime_command, trusted_catalog)
from component_runtime import worker_environment
from component_store import ComponentStore
from easyocr_models import installed_groups

COMPONENT = 'ocr.easyocr'


def legacy_disabled(root=None):
    return (Path(root or component_store_path())/'easyocr-legacy-disabled').exists()


def remove(root=None):
    store = ComponentStore(root or component_store_path())
    store.root.mkdir(parents=True,exist_ok=True)
    (store.root/'easyocr-legacy-disabled').touch()
    store.remove(COMPONENT)


def validate(folder, receipt, check_cancel=lambda:None):
    command = runtime_command(Path(folder),receipt)
    with tempfile.TemporaryDirectory(prefix='clickntranslate_easyocr_validate_') as temporary:
        work = Path(temporary)
        request = work/'request.json'
        request.write_text(json.dumps({'engine':'easyocr','action':'validate','root_dir':str(folder),
            'groups':receipt['languages'],'allow_download':False,'work_dir':temporary}),encoding='utf-8')
        with (work/'stdout.json').open('w',encoding='utf-8') as stdout, (work/'stderr.txt').open('w',encoding='utf-8') as stderr:
            process = subprocess.Popen([*command,str(request)],stdout=stdout,stderr=stderr,
                env=worker_environment(),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                deadline = time.monotonic()+max(120,120*len(receipt['languages']))
                while process.poll() is None:
                    check_cancel()
                    if time.monotonic()>deadline:
                        raise ComponentError('validation_failed','EasyOCR timeout')
                    time.sleep(.05)
                check_cancel()
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
        try:
            if (work/'stdout.json').stat().st_size>1024**2:
                raise ValueError('response too large')
            result = json.loads((work/'stdout.json').read_text(encoding='utf-8'))
        except (ValueError,OSError) as error:
            raise ComponentError('validation_failed','EasyOCR response') from error
        if process.returncode or result.get('error') or set(result.get('validated',()))!=set(receipt['languages']):
            raise ComponentError('validation_failed',str(result.get('error') or 'EasyOCR model set')[:300])
        return result


def install(download, *, groups=(), remove_groups=(), legacy_dir=None, root=None,
            channel=None, check_cancel=lambda:None, progress=lambda *_:None, catalog_loader=trusted_catalog):
    from app_version import APP_VERSION
    store = ComponentStore(root or component_store_path())
    with store.lock():
        check_cancel()
        try:
            old = store.active(COMPONENT)
        except ComponentError:
            old = store.describe(COMPONENT)
        if old and remove_groups and not groups:
            return store.remove_languages(COMPONENT,remove_groups,
                lambda folder,receipt:validate(folder,receipt,check_cancel),check_cancel,progress)
        catalog = catalog_loader(store.root)
        selected = set(old['receipt']['languages']) if old else set()
        if not old and legacy_dir and not legacy_disabled(store.root):
            selected.update(installed_groups(legacy_dir,legacy=True))
        if not old and not selected and not groups:
            selected.add('english_g2')
        selected.update(groups)
        selected.difference_update(remove_groups)
        bundle = choose_bundle(catalog,COMPONENT,APP_VERSION,languages=selected,
            channel=channel or os.environ.get('CLICKNTRANSLATE_COMPONENT_CHANNEL','stable'))
        return store.install(catalog,materialize_bundle(bundle,selected),download,
            lambda folder,receipt:validate(folder,receipt,check_cancel),check_cancel,progress)
