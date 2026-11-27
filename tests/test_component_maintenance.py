"""Optional collection must not replace recognition results with launch errors."""
from contextlib import ExitStack
import errno
from pathlib import Path
import shutil
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

import component_store
from component_store import ComponentStore
from test_component_updates import fixture_catalog


@pytest.mark.parametrize('launch', ['constructor', 'start'])
@pytest.mark.parametrize('worker_failed', [False, True])
def test_collection_launch_failure_preserves_worker_result_and_allows_retry(tmp_path, monkeypatch, launch, worker_failed):
    finished = threading.Event()
    finished.set()
    monkeypatch.setattr(component_store, '_MAINTENANCE_ROOTS', set())
    monkeypatch.setattr(component_store, '_MAINTENANCE_RUNNING', False)
    monkeypatch.setattr(component_store, '_MAINTENANCE_DONE', finished)
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    with store.lock():
        active = store.install(catalog, catalog['bundles'][0],
                               lambda _, path: shutil.copyfile(archive, path), lambda *_: None)
    failure = RuntimeError('collector thread unavailable')
    factory = (mock.Mock(side_effect=failure) if launch == 'constructor' else
               mock.Mock(return_value=SimpleNamespace(start=mock.Mock(side_effect=failure))))
    def recognize():
        with store.lease(active['receipt']['generation']):
            store.remove('ocr.rapidocr')
            if worker_failed:
                raise TimeoutError('recognition timeout')
            return 'successful recognition'
    with mock.patch.object(component_store.threading, 'Thread', factory):
        if worker_failed:
            with pytest.raises(TimeoutError, match='recognition timeout'):
                recognize()
        else:
            assert recognize() == 'successful recognition'
    assert not component_store._MAINTENANCE_RUNNING
    assert active['folder'].is_dir() and (store.root / 'gc-pending').is_file()
    with store.lease(active['receipt']['generation']):
        pass
    assert finished.wait(3)
    assert not active['folder'].exists()


@pytest.mark.parametrize('failure', [errno.ENOSPC, errno.EACCES], ids=['disk-full', 'permission-denied'])
@pytest.mark.parametrize('readers', [1, 2])
def test_gc_marker_failure_cannot_report_a_committed_install_as_failed(tmp_path, monkeypatch, failure, readers):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    download = lambda _, path: shutil.copyfile(archive, path)
    with store.lock():
        first = store.install(catalog, catalog['bundles'][0], download, lambda *_: None)
    with ExitStack() as leases:
        for _ in range(readers):
            leases.enter_context(store.lease(first['receipt']['generation']))
        with store.lock():
            second = dict(catalog['bundles'][0], id='rapidocr-r2', revision=2)
            store.install(catalog, second, download, lambda *_: None)
            third = dict(catalog['bundles'][0], id='rapidocr-r3', revision=3)
            touch = Path.touch
            attempts = []

            def fail_marker(path, *args, **kwargs):
                if path == store.root / 'gc-pending':
                    attempts.append(path)
                    raise OSError(failure, 'injected optional GC marker failure')
                return touch(path, *args, **kwargs)

            with monkeypatch.context() as fault:
                fault.setattr(Path, 'touch', fail_marker)
                installed = store.install(catalog, third, download, lambda *_: None)
            assert attempts
            assert installed['receipt']['revision'] == 3
            assert store.active('ocr.rapidocr')['receipt']['generation'] == installed['receipt']['generation']
            assert first['folder'].is_dir(), 'Running workers must retain their leased generation'
            with store.database() as db:
                assert not db.execute('SELECT 1 FROM operations').fetchall()
    with store.lock():
        store.collect_unused()
    assert not first['folder'].exists()
    assert store.active('ocr.rapidocr')['receipt']['revision'] == 3
