from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest

from component_catalog import ComponentError
from component_download import ComponentDownloader
from component_store import ComponentStore


@contextmanager
def artifact_server(data, mode='normal'):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            range_value = self.headers.get('Range')
            calls.append((range_value, self.headers.get('If-Range')))
            if self.path == '/missing':
                self.send_error(404)
                return
            start = int(range_value.removeprefix('bytes=').removesuffix('-')) if range_value else 0
            resumed = bool(range_value and mode != 'ignore-range')
            if not resumed:
                start = 0
            payload = data[start:]
            self.send_response(206 if resumed else 200)
            self.send_header('ETag', '"component-v1"')
            self.send_header('Content-Length', str(len(payload)))
            if resumed:
                offset = start + 1 if mode == 'bad-range' else start
                self.send_header('Content-Range', f'bytes {offset}-{len(data)-1}/{len(data)}')
            self.end_headers()
            if mode == 'disconnect-first' and len(calls) == 1:
                payload = payload[:16384]
                self.close_connection = True
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/artifact', calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def specification(data, *urls):
    return hashlib.sha256(data).hexdigest(), {'size':len(data), 'urls':list(urls)}


def test_canceled_download_resumes_exact_prefix_and_checks_full_digest(tmp_path):
    data = bytes(range(256)) * 1024
    canceled = []
    class Canceled(RuntimeError):
        pass
    def cancel():
        if canceled:
            raise Canceled()
    def progress(_url, done, _total):
        if done >= 8192:
            canceled.append(True)
    store = ComponentStore(tmp_path)
    with artifact_server(data) as (url, calls), store.lock():
        digest, item = specification(data, url)
        with pytest.raises(Canceled):
            store.obtain(digest, item, ComponentDownloader(cancel, progress), cancel)
        partial = store.root / 'downloads' / digest
        prefix = partial.stat().st_size
        assert 0 < prefix < len(data)
        canceled.clear()
        result = store.obtain(digest, item, ComponentDownloader(), lambda: None)
        assert result.read_bytes() == data
        assert calls[1] == (f'bytes={prefix}-', '"component-v1"')
        assert not partial.exists()
        assert not ComponentDownloader.metadata_path(partial).exists()


@pytest.mark.parametrize('mode', ['normal', 'ignore-range', 'bad-range'])
def test_resume_handles_standard_and_nonresuming_servers_without_mixing_bytes(tmp_path, mode):
    data = b'approved component bytes' * 4096
    store = ComponentStore(tmp_path)
    with artifact_server(data, mode) as (url, calls), store.lock():
        digest, item = specification(data, url)
        partial = store.root / 'downloads' / digest
        partial.parent.mkdir()
        partial.write_bytes(data[:100])
        result = store.obtain(digest, item, ComponentDownloader(), lambda: None)
        assert result.read_bytes() == data
        assert calls[0][0] == 'bytes=100-'
        if mode == 'bad-range':
            assert calls[1][0] is None


def test_network_interruption_is_retried_with_range(tmp_path):
    data = b'approved component bytes' * 4096
    store = ComponentStore(tmp_path)
    with artifact_server(data, 'disconnect-first') as (url, calls), store.lock():
        digest, item = specification(data, url)
        result = store.obtain(digest, item, ComponentDownloader(), lambda: None)
        assert result.read_bytes() == data
        assert len(calls) == 2 and calls[1][0] == 'bytes=16384-'


def test_completed_interrupted_transfer_is_reused_without_network(tmp_path):
    data = b'complete artifact'
    digest, item = specification(data, 'https://example.org/not-contacted')
    store = ComponentStore(tmp_path)
    partial = store.root / 'downloads' / digest
    partial.parent.mkdir(parents=True)
    partial.write_bytes(data)
    def unavailable(*_):
        pytest.fail('A complete verified partial must not be downloaded again')
    with store.lock():
        result = store.obtain(digest, item, unavailable, lambda: None)
    assert result.read_bytes() == data


def test_oversized_response_cannot_fill_disk_or_become_a_verified_object(tmp_path):
    approved = b'x' * 16384
    store = ComponentStore(tmp_path)
    with artifact_server(approved + b'extra bytes') as (url, _), store.lock():
        digest, item = specification(approved, url)
        with pytest.raises(ComponentError, match='exceeds approved size'):
            store.obtain(digest, item, ComponentDownloader(), lambda: None)
        assert not store.object_path(digest).exists()
        assert (store.root / 'downloads' / digest).stat().st_size <= len(approved)


def test_approved_mirror_is_tried_after_network_failure(tmp_path):
    data = b'approved mirrored bytes'
    store = ComponentStore(tmp_path)
    with artifact_server(data) as (url, calls), store.lock():
        missing = url.rsplit('/', 1)[0] + '/missing'
        digest, item = specification(data, missing, url)
        result = store.obtain(digest, item, ComponentDownloader(), lambda: None)
        assert result.read_bytes() == data
        assert len(calls) == 4
