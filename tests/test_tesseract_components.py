"""Language changes must have the same crash-safe semantics as engine updates."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import pytest

from component_catalog import ComponentError, materialize_bundle, parse_catalog
from component_store import ComponentStore
import component_runtime as runtime


@pytest.fixture
def native_catalog(tmp_path):
    archive = tmp_path / 'runtime.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('tesseract.exe', 'native runtime fixture')
        output.writestr('tessdata/configs/tsv', 'tsv=1')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    objects = {digest: archive}
    artifacts = {digest: {'size': archive.stat().st_size, 'unpacked_size': 10000,
                          'urls': ['https://example.org/' + digest]}}
    files = {}
    for code in ('eng', 'rus', 'ara'):
        data = tmp_path / (code + '.traineddata')
        data.write_text('model:' + code)
        sha = hashlib.sha256(data.read_bytes()).hexdigest()
        objects[sha] = data
        artifacts[sha] = {'size': data.stat().st_size, 'urls': ['https://example.org/' + sha]}
        files[code] = [{'sha256': sha, 'kind': 'file', 'destination': f'runtime/tessdata/{code}.traineddata'}]
    bundle = {'id': 'tesseract-win-r1', 'component': 'ocr.tesseract', 'revision': 1,
        'contract': 1, 'channel': 'preview', 'os': 'windows', 'arch': 'x86_64',
        'min_os': '10', 'app': '>=1.8.2,<2', 'runtime': 'native',
        'executable': 'runtime/tesseract.exe', 'languages': list(files),
        'language_files': files, 'files': [{'sha256': digest, 'kind': 'zip', 'destination': 'runtime'}]}
    catalog = parse_catalog(json.dumps({'schema': 1, 'revision': 4,
                                       'artifacts': artifacts, 'bundles': [bundle]}))
    return catalog, objects


def installer(tmp_path, monkeypatch, native_catalog):
    import component_catalog
    monkeypatch.setattr(component_catalog, 'current_platform', lambda: {
        'os': 'windows', 'arch': 'x86_64', 'os_version': '10'})
    catalog, objects = native_catalog
    root = tmp_path / 'store'
    downloads = []
    def download(url, destination):
        digest = url.rsplit('/', 1)[-1]
        downloads.append(digest)
        shutil.copyfile(objects[digest], destination)
    def validate(folder, receipt, check_cancel=lambda: None):
        for code in receipt['languages']:
            assert (folder / f'runtime/tessdata/{code}.traineddata').read_text() == 'model:' + code
    monkeypatch.setattr(runtime, 'validate_tesseract', validate)
    def install(**options):
        return runtime.install_tesseract(download, root=root, channel='preview',
                                         catalog_loader=lambda _: catalog, **options)
    return root, catalog, downloads, install


def test_language_add_remove_and_update_preserve_running_generation(tmp_path, monkeypatch, native_catalog):
    root, catalog, downloads, install = installer(tmp_path, monkeypatch, native_catalog)
    first = install()
    assert first['receipt']['languages'] == ['eng', 'rus']
    assert len(downloads) == 3
    with ComponentStore(root).lease(first['receipt']['generation']):
        second = install(languages=['ara'])
        assert second['receipt']['languages'] == ['ara', 'eng', 'rus']
        assert second['folder'] != first['folder']
        third = install(remove_languages=['rus'])
        assert third['receipt']['languages'] == ['ara', 'eng']
        assert (first['folder'] / 'runtime/tessdata/rus.traineddata').is_file()
    assert not first['folder'].exists()
    assert len(downloads) == 4  # runtime and existing languages reused from verified cache
    same = install()
    assert same['folder'] == third['folder']
    ComponentStore(root).rollback('ocr.tesseract', runtime.validate_tesseract, catalog)
    assert ComponentStore(root).active('ocr.tesseract')['receipt']['languages'] == ['ara', 'eng', 'rus']


def test_failed_model_activation_keeps_active_and_previous_data(tmp_path, monkeypatch, native_catalog):
    root, _, _, install = installer(tmp_path, monkeypatch, native_catalog)
    old = install()
    def fail(*_):
        raise ComponentError('validation_failed', 'invalid Arabic recognizer')
    monkeypatch.setattr(runtime, 'validate_tesseract', fail)
    with pytest.raises(ComponentError, match='validation_failed'):
        install(languages=['ara'])
    assert ComponentStore(root).active('ocr.tesseract')['folder'] == old['folder']
    assert (old['folder'] / 'runtime/tessdata/rus.traineddata').is_file()


def test_removed_languages_do_not_reappear_from_legacy_environment_or_defaults(tmp_path, monkeypatch, native_catalog):
    root, _, _, install = installer(tmp_path, monkeypatch, native_catalog)
    old = install()
    empty = install(remove_languages=['eng', 'rus'])
    assert empty['receipt']['languages'] == []
    assert install()['folder'] == empty['folder']
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR', str(root))
    monkeypatch.setenv('TESSDATA_PREFIX', str(old['folder'] / 'runtime/tessdata'))
    import ocr
    assert ocr._tesseract_installed_language_codes() == []
    assert ocr._tesseract_reported_languages(empty['command'][0]) == set()


def test_copied_windows_install_is_not_used_on_another_platform(tmp_path, monkeypatch, native_catalog):
    root, _, _, install = installer(tmp_path, monkeypatch, native_catalog)
    install()
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR', str(root))
    import component_catalog
    monkeypatch.setattr(component_catalog, 'current_platform', lambda: {
        'os':'macos', 'arch':'arm64', 'os_version':'15'})
    assert runtime.managed_runtime('tesseract') is None


def test_model_source_archive_does_not_convert_alias_into_fake_traineddata(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    from prepare_tesseract_component import extract_models
    source = tmp_path / 'source.zip'
    with zipfile.ZipFile(source, 'w') as output:
        output.writestr('tessdata_fast-commit/LICENSE', 'upstream license')
        output.writestr('tessdata_fast-commit/deu_latf.traineddata', b'actual model')
        alias = zipfile.ZipInfo('tessdata_fast-commit/frk.traineddata')
        alias.create_system = 3
        alias.external_attr = 0o120777 << 16
        output.writestr(alias, b'deu_latf.traineddata')
    target = tmp_path / 'models'
    extract_models(source, target, 'commit')
    assert (target / 'deu_latf.traineddata').read_bytes() == b'actual model'
    assert not (target / 'frk.traineddata').exists()


def test_migration_preserves_custom_legacy_models_and_blocks_incompatible_update(tmp_path, monkeypatch, native_catalog):
    root, _, _, install = installer(tmp_path, monkeypatch, native_catalog)
    legacy = tmp_path / 'legacy'
    legacy.mkdir()
    (legacy / 'ara.traineddata').write_bytes(b'old Arabic')
    (legacy / 'osd.traineddata').write_bytes(b'orientation is not a recognition language')
    new = install(legacy_data_dirs=[legacy])
    assert new['receipt']['languages'] == ['ara']
    assert (legacy / 'ara.traineddata').read_bytes() == b'old Arabic'
    ComponentStore(root).remove('ocr.tesseract')
    (legacy / 'custom.traineddata').write_bytes(b'user model')
    with pytest.raises(ComponentError, match='no_compatible_update'):
        install(legacy_data_dirs=[legacy])
    assert (legacy / 'custom.traineddata').read_bytes() == b'user model'
    assert ComponentStore(root).active('ocr.tesseract') is None


def test_cancellation_during_language_transaction_does_not_publish(tmp_path, monkeypatch, native_catalog):
    root, _, _, install = installer(tmp_path, monkeypatch, native_catalog)
    old = install()
    preparing = []
    def cancel():
        if preparing:
            raise InterruptedError('cancel')
    with pytest.raises(InterruptedError):
        install(languages=['ara'], check_cancel=cancel, progress=lambda *_: preparing.append(True))
    assert ComponentStore(root).active('ocr.tesseract')['folder'] == old['folder']


def test_managed_command_uses_its_own_models_and_holds_lease(tmp_path, monkeypatch, native_catalog):
    root, _, _, install = installer(tmp_path, monkeypatch, native_catalog)
    first = install(languages=['ara'])
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR', str(root))
    monkeypatch.setenv('TESSDATA_PREFIX', str(tmp_path / 'wrong-directory'))
    import ocr
    from PIL import Image
    monkeypatch.setattr(ocr.ScreenCaptureOverlay, '_tesseract_cmd_cache', 'old nonexistent command')
    assert ocr.ScreenCaptureOverlay.get_tesseract_cmd() == first['command'][0]
    data = str(first['folder'] / 'runtime/tessdata')
    assert ocr._configure_installed_tesseract_data(first['command'][0], 'ara') == data
    assert ocr._tesseract_data_directories(first['command'][0]) == [data]
    def recognize(image, command, data_dir, lang, psm, positions=False):
        assert lang == 'ara' and str(data_dir) == data
        ComponentStore(root).remove('ocr.tesseract')
        assert first['folder'].is_dir()  # running OCR still owns the generation
        return 'مرحبا'
    monkeypatch.setattr(runtime, 'recognize_tesseract', recognize)
    assert ocr._run_tesseract_ocr_image_with_cmd(Image.new('RGB', (500, 200)), first['command'][0],
                                               'ara', 'qa', 'qa') == 'مرحبا'
    assert not first['folder'].exists()


def test_managed_data_preparation_never_writes_or_downloads(tmp_path, monkeypatch, native_catalog):
    root, _, _, install = installer(tmp_path, monkeypatch, native_catalog)
    first = install(languages=['eng'])
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR', str(root))
    import ocr
    import requests
    monkeypatch.setattr(requests, 'get', lambda *_a, **_k: pytest.fail('OCR must not download models'))
    assert len(ocr._prepare_tesseract_data(first['command'][0], 'eng')) == 1
    with pytest.raises(RuntimeError, match='Language packages'):
        ocr._prepare_tesseract_data(first['command'][0], 'ara', raise_on_error=True)
    assert not (first['folder'] / 'runtime/tessdata/ara.traineddata').exists()


@pytest.mark.parametrize('mutation', ['command', 'code', 'destination', 'mismatch'])
def test_catalog_rejects_unsafe_native_descriptions(native_catalog, mutation):
    catalog = copy.deepcopy(native_catalog[0])
    bundle = catalog['bundles'][0]
    if mutation == 'command':
        bundle['executable'] = '../tesseract.exe'
    elif mutation == 'code':
        bundle['language_files']['../eng'] = bundle['language_files'].pop('eng')
    elif mutation == 'destination':
        bundle['language_files']['eng'][0]['destination'] = '../eng.traineddata'
    else:
        bundle['languages'].remove('eng')
    with pytest.raises(ComponentError):
        parse_catalog(json.dumps(catalog))


def test_materialization_does_not_change_signed_capabilities(native_catalog):
    bundle = native_catalog[0]['bundles'][0]
    before = copy.deepcopy(bundle)
    result = materialize_bundle(bundle, ['ara', 'ara'])
    assert result['languages'] == ['ara'] and len(result['files']) == 2
    assert bundle == before


def test_native_arguments_preserve_model_directory_with_spaces(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from PIL import Image
    seen = []
    def run(command, **kwargs):
        seen.append(command)
        assert command[command.index('--tessdata-dir') + 1] == str(tmp_path / 'models with spaces')
        assert 'TESSDATA_PREFIX' not in kwargs['env']
        return SimpleNamespace(returncode=0, stdout='recognized text')
    monkeypatch.setenv('TESSDATA_PREFIX', 'wrong global directory')
    monkeypatch.setattr(runtime.subprocess, 'run', run)
    assert runtime.recognize_tesseract(Image.new('RGB', (10, 10)), 'tesseract.exe',
                                      tmp_path / 'models with spaces', 'eng', 6) == 'recognized text'
    assert len(seen) == 1


def test_native_arabic_line_identity_does_not_turn_word_spaces_into_paragraphs():
    from ocr_paragraphs import tesseract_items
    from ocr_text_layout import ocr_text_from_items
    # Tesseract's logical RTL word order, with short-height words and wide spaces.
    words = [(240, 10, 50, 20, 'لقد'), (160, 14, 45, 13, 'حللت'), (95, 14, 25, 13, 'سر'),
             (180, 40, 110, 20, 'الأبجدية'), (95, 40, 60, 20, 'القديمة.')]
    data = {name: [row[index] for row in words]
            for index, name in enumerate(('left', 'top', 'width', 'height', 'text'))}
    data.update(page_num=[1]*5, block_num=[1]*5, par_num=[1]*5, line_num=[1]*3+[2]*2)
    assert ocr_text_from_items(tesseract_items(data), join_paragraphs=True) == 'لقد حللت سر الأبجدية القديمة.'


def test_native_line_identity_still_preserves_page_gutter():
    from ocr_paragraphs import tesseract_items
    from ocr_text_layout import ocr_text_from_items
    words = [(10, 10, 45, 20, 'Left'), (65, 10, 50, 20, 'page'),
             (300, 10, 55, 20, 'Right'), (365, 10, 50, 20, 'page')]
    data = {name: [row[index] for row in words]
            for index, name in enumerate(('left', 'top', 'width', 'height', 'text'))}
    data.update(page_num=[1]*4, block_num=[1]*4, par_num=[1]*4, line_num=[1]*4)
    assert ocr_text_from_items(tesseract_items(data), join_paragraphs=True) == 'Left page\n\nRight page'
