"""Signed-plan ownership and archive-name boundaries using only tiny fixtures."""
import copy
import hashlib
import shutil
from unittest import mock
import zipfile

import pytest

from component_catalog import ComponentError, materialize_bundle, safe_relative
from component_store import ComponentStore
from test_component_updates import fixture_catalog
from test_tesseract_components import native_catalog


@pytest.mark.parametrize('split_languages', [False, True], ids=['monolithic', 'language-files'])
@pytest.mark.parametrize('edit', ['core-file', 'model-versions', 'languages'])
def test_materialized_plan_edits_never_change_signed_catalog_or_another_plan(native_catalog, split_languages, edit):
    catalog, _ = native_catalog
    bundle = catalog['bundles'][0]
    bundle['model_versions'] = {'eng': 'approved-v1', 'ara': 'approved-v1'}
    if not split_languages:
        bundle.pop('language_files')
    before = copy.deepcopy(catalog)
    selected = materialize_bundle(bundle, ['eng'])
    other = materialize_bundle(bundle, ['ara'])
    other_before = copy.deepcopy(other)
    assert selected['languages'] == (['eng'] if split_languages else bundle['languages'])
    if edit == 'core-file':
        selected['files'][0]['destination'] = 'a-local-plan-edit'
    elif edit == 'model-versions':
        selected['model_versions']['eng'] = 'a-local-plan-edit'
    else:
        selected['languages'].append('a-local-plan-edit')
    assert catalog == before
    assert other == other_before


@pytest.mark.parametrize('path', ['runtime/python.exe\x00shadow', 'models/\x00file', 'runtime\x00'])
def test_component_paths_reject_embedded_nul_before_filesystem_use(path):
    with pytest.raises(ComponentError, match='invalid_path'):
        safe_relative(path)


def archive_with_nul_member(path, member, *, worker=False):
    placeholder = member.replace('\x00', 'X')
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(placeholder, b'test interpreter')
        if worker:
            archive.writestr('adapter/ocr_worker.py', b'test worker')
    encoded = path.read_bytes()
    assert encoded.count(placeholder.encode()) == 2  # local and central headers
    path.write_bytes(encoded.replace(placeholder.encode(), member.encode()))
    with zipfile.ZipFile(path) as archive:
        assert archive.infolist()[0].orig_filename == member
        assert archive.infolist()[0].filename != member  # zipfile truncates NUL
    return path


@pytest.mark.parametrize('member', ['runtime.bin\x00hidden', 'nested\x00hidden/worker.py'])
def test_nul_archive_name_is_rejected_instead_of_extracting_its_truncated_alias(tmp_path, member):
    archive = archive_with_nul_member(tmp_path / 'nul.zip', member)
    with pytest.raises(ComponentError, match='invalid_path|unsafe_archive'):
        ComponentStore.extract(archive, tmp_path / 'candidate', 1024)


@pytest.mark.parametrize('member', ['runtime/adapter/worker.py', 'models/العربية.bin', 'models/русский файл.bin'])
def test_valid_component_paths_and_unicode_archive_members_are_preserved(tmp_path, member):
    assert safe_relative(member) == member
    archive = tmp_path / 'valid.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr(member, b'synthetic fixture')
    destination = tmp_path / 'candidate'
    ComponentStore.extract(archive, destination, 1024)
    assert (destination / member).read_bytes() == b'synthetic fixture'


def test_nul_archive_cannot_activate_an_alias_of_the_approved_runtime(tmp_path, record_testsuite_property):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    with store.lock():
        active = store.install(catalog, catalog['bundles'][0],
                               lambda _, path: shutil.copyfile(archive, path), lambda *_: None)
        malformed = archive_with_nul_member(tmp_path / 'new.zip', 'python.exe\x00hidden', worker=True)
        digest = hashlib.sha256(malformed.read_bytes()).hexdigest()
        catalog['artifacts'][digest] = {'size': malformed.stat().st_size, 'unpacked_size': 1024,
                                        'urls': ['https://example.invalid/not-downloaded.zip']}
        candidate = dict(catalog['bundles'][0], id='rapidocr-r2', revision=2,
                         files=[{'sha256': digest, 'kind': 'zip', 'destination': 'runtime'}])
        validate = mock.Mock()
        try:
            with pytest.raises(ComponentError, match='invalid_path|unsafe_archive'):
                store.install(catalog, candidate, lambda _, path: shutil.copyfile(malformed, path), validate)
        finally:
            record_testsuite_property('actual_active_revision', store.active('ocr.rapidocr')['receipt']['revision'])
        validate.assert_not_called()
        assert store.active('ocr.rapidocr')['folder'] == active['folder']
        with store.database() as database:
            assert not database.execute('SELECT 1 FROM operations').fetchall()
