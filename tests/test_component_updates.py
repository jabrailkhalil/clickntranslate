"""Exercise trust, compatibility, recoverability and immutable reuse."""
from contextlib import contextmanager
import copy
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import threading
import zipfile

import pytest
from component_catalog import ComponentError, choose_bundle, parse_catalog, trusted_catalog
from component_store import ComponentStore


def fixture_catalog(tmp_path):
    archive = tmp_path / 'runtime.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('python.exe', 'test interpreter')
        output.writestr('adapter/ocr_worker.py', 'test worker')
    data = archive.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    bundle = {'id': 'rapidocr-win-r1', 'component': 'ocr.rapidocr', 'revision': 1,
        'contract': 1, 'channel': 'preview', 'os': 'windows', 'arch': 'x86_64',
        'min_os': '10', 'app': '>=1.8.2,<2', 'python': 'runtime/python.exe',
        'worker': 'runtime/adapter/ocr_worker.py', 'languages': ['en', 'ru', 'ar'],
        'files': [{'sha256': digest, 'kind': 'zip', 'destination': 'runtime'}]}
    catalog = {'schema': 1, 'revision': 1, 'artifacts': {digest: {'size': len(data),
        'unpacked_size': 1000, 'urls': ['https://example.org/runtime.zip']}}, 'bundles': [bundle]}
    return parse_catalog(json.dumps(catalog)), archive


def test_select_checks_platform_app_channel_and_languages(tmp_path):
    catalog, _ = fixture_catalog(tmp_path)
    target = {'os': 'windows', 'arch': 'x86_64', 'os_version': '10'}
    assert choose_bundle(catalog, 'ocr.rapidocr', '1.8.2', channel='preview', target=target)['revision'] == 1
    for arguments in ({'channel': 'stable'}, {'languages': ['ja']},
                      {'target': dict(target, arch='arm64')}, {'target': dict(target, os_version='8.1')}):
        options = {'channel': 'preview', 'target': target, **arguments}
        with pytest.raises(ComponentError, match='no_compatible_update'):
            choose_bundle(catalog, 'ocr.rapidocr', '1.8.2', **options)
    with pytest.raises(ComponentError):
        choose_bundle(catalog, 'ocr.rapidocr', '2.0', channel='preview', target=target)


def test_future_adapter_contract_does_not_block_compatible_existing_updates(tmp_path):
    catalog, _ = fixture_catalog(tmp_path)
    # Its layout is deliberately unknown to this client: it must not attempt to
    # parse or launch the future adapter as a Python worker.
    catalog['bundles'].append({'id':'future-rapidocr', 'component':'ocr.rapidocr',
                              'contract':2, 'revision':100, 'channel':'preview',
                              'future_runtime':{'opaque':'future schema'}})
    loaded = parse_catalog(json.dumps(catalog))
    selected = choose_bundle(loaded, 'ocr.rapidocr', '1.8.2', channel='preview',
        target={'os':'windows', 'arch':'x86_64', 'os_version':'10'})
    assert selected['id'] == 'rapidocr-win-r1'


def test_failed_install_keeps_previous_and_reuses_bytes(tmp_path):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    downloads = []
    def download(url, target):
        downloads.append(url)
        shutil.copyfile(archive, target)
    def validate(folder, receipt):
        assert (folder / receipt['worker']).read_text() == 'test worker'
    with store.lock():
        first = store.install(catalog, catalog['bundles'][0], download, validate)
        second = copy.deepcopy(catalog['bundles'][0])
        second.update(id='rapidocr-win-r2', revision=2)
        with pytest.raises(RuntimeError, match='native crash'):
            store.install(catalog, second, download, lambda *_: (_ for _ in ()).throw(RuntimeError('native crash')))
        assert store.active('ocr.rapidocr')['receipt']['bundle'] == first['receipt']['bundle']
        store.install(catalog, second, download, validate)
    assert len(downloads) == 1
    assert store.active('ocr.rapidocr')['receipt']['revision'] == 2
    store.rollback('ocr.rapidocr', validate, catalog)
    assert store.active('ocr.rapidocr')['receipt']['revision'] == 1


def test_crash_recovery_removes_only_uncommitted_generation(tmp_path):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    with store.lock():
        active = store.install(catalog, catalog['bundles'][0], lambda _, dest: shutil.copyfile(archive, dest), lambda *_: None)
        orphan = store.generation('abandoned')
        orphan.mkdir()
        with store.database() as db:
            db.execute('INSERT INTO operations VALUES (?,?,?,?)', ('op', 'ocr.rapidocr', 'abandoned', 'preparing'))
        store.recover()
        assert not orphan.exists()
        assert store.active('ocr.rapidocr')['folder'] == active['folder']


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/escape', 'test\\escape', 'CON.txt', 'trailing.'])
def test_archive_rejects_unsafe_names(tmp_path, name):
    archive = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        info = zipfile.ZipInfo('entry')
        info.filename = name
        output.writestr(info, b'unsafe')
    with pytest.raises(ComponentError):
        ComponentStore.extract(archive, tmp_path / 'target', 100)


def test_writer_lock_prevents_parallel_install(tmp_path):
    with ComponentStore(tmp_path).lock():
        with pytest.raises(ComponentError, match='operation_busy'):
            with ComponentStore(tmp_path).lock():
                pytest.fail('parallel writer entered')


def test_removal_waits_for_running_worker_and_reclaims_cache(tmp_path):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    with store.lock():
        active = store.install(catalog, catalog['bundles'][0], lambda _, dest: shutil.copyfile(archive, dest), lambda *_: None)
    with store.lease(active['receipt']['generation']):
        store.remove('ocr.rapidocr')
        assert store.active('ocr.rapidocr') is None
        assert active['folder'].is_dir()
        assert (store.root / 'gc-pending').is_file()
    assert not active['folder'].exists()
    assert not list((store.root / 'objects').glob('*'))


def test_two_workers_can_share_a_generation_and_cleanup_after_timeout(tmp_path):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    with store.lock():
        active = store.install(catalog, catalog['bundles'][0], lambda _, dest: shutil.copyfile(archive, dest), lambda *_: None)
    generation = active['receipt']['generation']
    with pytest.raises(TimeoutError):
        with store.lease(generation), store.lease(generation):
            store.remove('ocr.rapidocr')
            assert active['folder'].is_dir()
            raise TimeoutError()
    assert not active['folder'].exists()


def test_checksum_failure_never_activates(tmp_path):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    def corrupt(_, target):
        Path(target).write_bytes(b'corrupt')
    with store.lock(), pytest.raises(ComponentError, match='checksum_mismatch'):
        store.install(catalog, catalog['bundles'][0], corrupt, lambda *_: pytest.fail('validated corrupt data'))
    assert store.active('ocr.rapidocr') is None


@contextmanager
def serve(folder):
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(folder)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_real_tuf_verification_rejects_tampered_catalog(tmp_path):
    pytest.importorskip('tuf')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
    from component_repository import publish
    catalog, _ = fixture_catalog(tmp_path)
    file = tmp_path / 'catalog.json'
    file.write_text(json.dumps(catalog), encoding='utf-8')
    site = tmp_path / 'site'
    bootstrap = publish(file, site, tmp_path / 'keys').read_bytes()
    with serve(site) as base:
        loaded = trusted_catalog(tmp_path / 'client', metadata_url=base+'metadata/', target_url=base+'targets/', bootstrap=bootstrap)
        assert loaded['revision'] == 1
        for target in (site / 'targets').glob('*catalog.json'):
            target.write_text('{}', encoding='utf-8')
        with pytest.raises(ComponentError, match='catalog_unavailable'):
            trusted_catalog(tmp_path / 'other-client', metadata_url=base+'metadata/', target_url=base+'targets/', bootstrap=bootstrap)


def test_revoked_previous_version_cannot_be_activated(tmp_path):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    with store.lock():
        download = lambda _, dest: shutil.copyfile(archive, dest)
        store.install(catalog, catalog['bundles'][0], download, lambda *_: None)
        newer = dict(catalog['bundles'][0], id='rapidocr-r2', revision=2)
        store.install(catalog, newer, download, lambda *_: None)
    catalog['bundles'][0]['revoked'] = True
    with pytest.raises(ComponentError, match='previous_version_not_approved'):
        store.rollback('ocr.rapidocr', lambda *_: None, catalog)
    assert store.active('ocr.rapidocr')['receipt']['revision'] == 2


def test_cancellation_preserves_active_generation(tmp_path):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    class Cancelled(Exception):
        pass
    with store.lock():
        store.install(catalog, catalog['bundles'][0], lambda _, dest: shutil.copyfile(archive, dest), lambda *_: None)
        newer = dict(catalog['bundles'][0], id='rapidocr-r2', revision=2)
        calls = []
        def cancel():
            calls.append(True)
            if len(calls) == 2:
                raise Cancelled()
        with pytest.raises(Cancelled):
            store.install(catalog, newer, lambda *_: None, lambda *_: None, check_cancel=cancel)
    assert store.active('ocr.rapidocr')['receipt']['revision'] == 1


def test_archive_expansion_and_symlinks_are_rejected(tmp_path):
    archive = tmp_path / 'large.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        output.writestr('large', b'x' * 4096)
    with pytest.raises(ComponentError, match='unsafe_archive'):
        ComponentStore.extract(archive, tmp_path / 'too-large', 1024)
    archive = tmp_path / 'link.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        info = zipfile.ZipInfo('link')
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        output.writestr(info, '../outside')
    with pytest.raises(ComponentError, match='unsafe_archive'):
        ComponentStore.extract(archive, tmp_path / 'symlink', 1024)


@pytest.mark.parametrize('value', ['[]', 'null', '"text"', '{}'])
def test_invalid_catalog_shape_is_a_controlled_error(value):
    with pytest.raises(ComponentError, match='invalid_catalog'):
        parse_catalog(value)


def test_real_tuf_rejects_expiry_and_rollback(tmp_path):
    pytest.importorskip('tuf')
    from datetime import datetime, timedelta, timezone
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
    from component_repository import publish, refresh_online, signer
    from tuf.api.metadata import Metadata
    catalog, _ = fixture_catalog(tmp_path)
    file = tmp_path / 'catalog.json'
    file.write_text(json.dumps(catalog), encoding='utf-8')
    site, keydir = tmp_path / 'site', tmp_path / 'keys'
    bootstrap = publish(file, site, keydir).read_bytes()
    timestamp_path = site / 'metadata/timestamp.json'
    initial = timestamp_path.read_bytes()
    refresh_online(site, keydir)
    with serve(site) as base:
        options = dict(metadata_url=base+'metadata/', target_url=base+'targets/', bootstrap=bootstrap)
        trusted_catalog(tmp_path / 'client', **options)
        timestamp_path.write_bytes(initial)
        with pytest.raises(ComponentError, match='catalog_unavailable'):
            trusted_catalog(tmp_path / 'client', **options)
        timestamp = Metadata.from_file(str(timestamp_path))
        timestamp.signed.expires = datetime.now(timezone.utc) - timedelta(days=1)
        timestamp.sign(signer(keydir / 'timestamp.pem'))
        timestamp.to_file(str(timestamp_path))
        with pytest.raises(ComponentError, match='catalog_unavailable'):
            trusted_catalog(tmp_path / 'fresh-client', **options)
