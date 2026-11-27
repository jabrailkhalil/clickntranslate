"""Exercise a local native Tesseract candidate using an isolated QA store.

Models are fetched from their real pinned upstream URLs. The not-yet-published
runtime candidate is copied locally. Nothing is promoted or built for release.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT), str(PROJECT / 'src')]
from component_catalog import ComponentError, parse_catalog
from component_store import ComponentStore
from component_runtime import install_tesseract, validate_tesseract


def run(candidate, output, fixtures):
    sys.argv[0] = str(output / 'main.py')  # keep OCR diagnostic logs in the QA profile
    import requests
    from PIL import Image
    from ocr import _run_tesseract_ocr_image_with_cmd, _recognize_image_layout, ScreenCaptureOverlay
    catalog = parse_catalog((candidate / 'catalog-candidate.json').read_bytes())
    runtime_file = candidate / json.loads((candidate / 'runtime-artifact.json').read_bytes())['filename']
    store = ComponentStore(output / 'store')
    os.environ['CLICKNTRANSLATE_COMPONENTS_DIR'] = str(store.root)
    downloads = []
    def download(url, destination):
        downloads.append(url)
        if url.endswith(runtime_file.name):
            shutil.copyfile(runtime_file, destination)
        else:
            with requests.get(url, stream=True, timeout=120) as response:
                response.raise_for_status()
                with open(destination, 'wb') as stream:
                    for block in response.iter_content(1024 * 1024):
                        stream.write(block)
    def install(**kwargs):
        return install_tesseract(download, root=store.root, channel='preview',
                                  catalog_loader=lambda _: catalog, **kwargs)
    started = time.perf_counter()
    first = install()
    first_seconds = time.perf_counter() - started
    assert first['receipt']['languages'] == ['eng', 'rus']
    added = install(languages=['ara'])
    assert added['receipt']['languages'] == ['ara', 'eng', 'rus']
    after_add = len(downloads)
    assert after_add == 4
    newer = copy.deepcopy(catalog['bundles'][0])
    newer.update(id='tesseract-windows-x64-fast-lifecycle-r2', revision=2)
    catalog['bundles'].append(newer)
    second = install()
    assert second['receipt']['revision'] == 2
    assert second['receipt']['languages'] == ['ara', 'eng', 'rus']
    assert len(downloads) == after_add
    store.rollback('ocr.tesseract', validate_tesseract, catalog)
    assert store.active('ocr.tesseract')['receipt']['revision'] == 1
    second = install()
    assert len(downloads) == after_add
    recognition = []
    for name, code in [('hilal-en', 'eng'), ('control-ru-clear', 'rus'),
                        ('control-ar-clear', 'ara'), ('hilal-ar', 'ara')]:
        image = Image.open(fixtures / (name + '.png')).convert('RGB')
        started = time.perf_counter()
        text = _run_tesseract_ocr_image_with_cmd(image, second['command'][0], code, 'component-qa', name,
                                               join_paragraphs=True)
        assert text.strip(), name
        layout = _recognize_image_layout(image, 'tesseract', {'eng':'en', 'rus':'ru', 'ara':'ar'}[code])
        assert layout and all(row[4].strip() for row in layout), name
        recognition.append({'fixture': name, 'language': code, 'text': text,
                            'fullscreen_layout_lines': len(layout),
                            'milliseconds': round((time.perf_counter() - started) * 1000, 2)})
    # A language edit with the same bundle id must create a new generation.
    removed = install(remove_languages=['ara'])
    assert removed['receipt']['languages'] == ['eng', 'rus']
    assert not (removed['folder'] / 'runtime/tessdata/ara.traineddata').exists()
    assert len(downloads) == after_add
    store.rollback('ocr.tesseract', validate_tesseract, catalog)
    assert 'ara' in store.active('ocr.tesseract')['receipt']['languages']
    # A failed real DLL/model initialization cannot change the active pointer.
    active = store.active('ocr.tesseract')
    original = validate_tesseract
    import component_runtime
    def invalid_model(folder, receipt, check_cancel=lambda: None):
        (folder / 'runtime/tessdata/ara.traineddata').write_bytes(b'invalid traineddata')
        original(folder, receipt, check_cancel)
    component_runtime.validate_tesseract = invalid_model
    newer = copy.deepcopy(newer)
    newer.update(id='tesseract-invalid-qa-r3', revision=3)
    catalog['bundles'].append(newer)
    try:
        try:
            install()
        except ComponentError as error:
            assert error.code == 'validation_failed'
        else:
            raise AssertionError('Invalid recognizer was activated')
    finally:
        component_runtime.validate_tesseract = original
    assert store.active('ocr.tesseract')['folder'] == active['folder']
    assert ScreenCaptureOverlay.get_tesseract_cmd() == active['command'][0]
    report = {'engine': active['receipt']['upstream'], 'models': active['receipt']['models'],
        'runtime_sha256': active['receipt']['files'][0]['sha256'],
        'first_install_seconds': round(first_seconds, 2), 'artifact_downloads': after_add,
        'language_add_remove': 'passed', 'update_preserves_languages': 'passed',
        'update_additional_downloads': 0, 'rollback': 'passed', 'bad_model_preserves_active': 'passed',
        'recognition': recognition, 'runtime_source': 'local unpublished candidate',
        'model_source': 'real HTTPS pinned upstream', 'frozen_application_tested': False}
    (output / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'recognition'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if 'ClicknTranslate-QA' not in output.parts or output.exists():
        parser.error('Use a fresh output directory below ClicknTranslate-QA')
    output.mkdir(parents=True)
    run(args.candidate, output, args.fixtures)
