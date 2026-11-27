"""An unreadable optional component database must never be reset implicitly."""
import hashlib
import shutil
import sqlite3
from unittest import mock

import pytest

import component_runtime
import component_store
from component_catalog import ComponentError
from component_store import ComponentStore
from test_component_updates import fixture_catalog


def populated_store(tmp_path):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    with store.lock():
        store.install(catalog, catalog['bundles'][0],
                      lambda _, path: shutil.copyfile(archive, path), lambda *_: None)
    return store, catalog


def file_fingerprints(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def check_entry_point(store, catalog, action, monkeypatch):
    monkeypatch.setattr(component_runtime, 'component_store_path', lambda: store.root)
    if action == 'describe':
        with pytest.raises(ComponentError, match='installed_component_damaged'):
            store.describe('ocr.rapidocr')
    elif action == 'runtime':
        assert component_runtime.managed_runtime('rapidocr') is None
    elif action == 'startup':
        import ocr
        import translater
        monkeypatch.setattr(ocr.sys, 'frozen', True, raising=False)
        monkeypatch.setattr(ocr, '_native_ocr_worker_path', lambda: '')
        monkeypatch.delenv('CLICKNTRANSLATE_ARGOS_WORKER', raising=False)
        assert not ocr._native_ocr_worker_enabled()
        assert translater._managed_argos_runtime() is None
    else:
        with store.lock(), pytest.raises(ComponentError, match='installed_component_damaged'):
            store.install(catalog, catalog['bundles'][0],
                          lambda *_: pytest.fail('Damaged state must not start a download'),
                          lambda *_: pytest.fail('Damaged state must not activate a candidate'))


@pytest.mark.parametrize('action', ['describe', 'runtime', 'startup', 'install'])
def test_corrupt_database_is_controlled_and_preserves_all_existing_files(tmp_path, monkeypatch, action):
    store, catalog = populated_store(tmp_path)
    (store.root / 'state.sqlite').write_bytes(b'not a SQLite database; retain for recovery')
    before = file_fingerprints(store.root)
    try:
        check_entry_point(store, catalog, action, monkeypatch)
    finally:
        assert file_fingerprints(store.root) == before


@pytest.mark.parametrize('failure_type', [sqlite3.OperationalError, PermissionError])
@pytest.mark.parametrize('action', ['describe', 'runtime', 'startup', 'install'])
def test_database_open_permission_failure_preserves_the_saved_install(tmp_path, monkeypatch, action, failure_type):
    store, catalog = populated_store(tmp_path)
    before = file_fingerprints(store.root)
    with mock.patch.object(component_store.sqlite3, 'connect', side_effect=failure_type('injected database access denied')):
        check_entry_point(store, catalog, action, monkeypatch)
    assert file_fingerprints(store.root) == before
