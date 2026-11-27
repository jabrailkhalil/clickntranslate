"""A failed mirror's unverified prefix cannot disable a healthy approved mirror."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from unittest import mock

import pytest

from component_download import ComponentDownloader
from component_store import ComponentStore


@contextmanager
def interrupted_mirrors(data, corrupt_prefix, ignore_range=False):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            saved_range = self.headers.get('Range')
            resumed = bool(saved_range and not (ignore_range and self.path == '/secondary'))
            offset = int(saved_range.removeprefix('bytes=').removesuffix('-')) if resumed else 0
            calls.append((self.path, saved_range))
            self.send_response(206 if resumed else 200)
            self.send_header('Content-Length', str(len(data) - offset))
            self.send_header('ETag', '"fixture-same-artifact"')
            if resumed:
                self.send_header('Content-Range', f'bytes {offset}-{len(data) - 1}/{len(data)}')
            self.end_headers()
            if self.path == '/primary':
                # A CDN can fail after persisting a full transfer chunk. The
                # signed digest is still required before any bytes are trusted.
                payload = b'!' * 8192 if corrupt_prefix else data[offset:offset + 8192]
                self.close_connection = True
            else:
                payload = data[offset:]
            try:
                self.wfile.write(payload)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


@pytest.mark.parametrize('corrupt_prefix', [False, True], ids=['valid-partial', 'corrupt-partial'])
def test_a_healthy_mirror_recovers_after_a_truncated_primary(tmp_path, corrupt_prefix):
    data = bytes(range(256)) * 512
    digest = hashlib.sha256(data).hexdigest()
    store = ComponentStore(tmp_path / 'store')
    with interrupted_mirrors(data, corrupt_prefix) as (base, calls), store.lock():
        specification = {'size': len(data), 'urls': [base + '/primary', base + '/secondary']}
        artifact = store.obtain(digest, specification, ComponentDownloader(), lambda: None)
        assert artifact.read_bytes() == data
        assert len(calls) == 4
        assert [name for name, _saved_range in calls] == ['/primary'] * 3 + ['/secondary']
        assert calls[1][1] == 'bytes=8192-' and calls[2][1] == 'bytes=16384-'
        partial = store.root / 'downloads' / digest
        assert not partial.exists()
        assert not ComponentDownloader.metadata_path(partial).exists()


@pytest.mark.parametrize('state', [None, b'not JSON', b'[]', b'{"etag":"old"}',
                                 b'{"url":null}', b'{"url":17}',
                                 b'{"url":"http://127.0.0.1/another-origin"}', b'\xff\xfe'],
                         ids=['missing', 'malformed', 'wrong-shape', 'missing-url',
                              'null-url', 'number-url', 'different-url', 'invalid-encoding'])
def test_unknown_partial_origin_restarts_without_poisoning_a_valid_source(tmp_path, state):
    data = bytes(range(256)) * 512
    digest = hashlib.sha256(data).hexdigest()
    store = ComponentStore(tmp_path / 'store')
    partial = store.root / 'downloads' / digest
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b'!' * 8192)
    if state is not None:
        ComponentDownloader.metadata_path(partial).write_bytes(state)
    with interrupted_mirrors(data, False) as (base, calls), store.lock():
        url = base + '/secondary'
        artifact = store.obtain(digest, {'size': len(data), 'urls': [url]}, ComponentDownloader(), lambda: None)
        assert artifact.read_bytes() == data
        assert calls == [('/secondary', None)]
        assert not partial.exists() and not ComponentDownloader.metadata_path(partial).exists()


@pytest.mark.parametrize('ignore_range', [False, True], ids=['resume-206', 'ignore-range-200'])
def test_same_origin_partial_still_resumes_or_accepts_a_full_restart(tmp_path, ignore_range):
    data = bytes(range(256)) * 512
    digest = hashlib.sha256(data).hexdigest()
    store = ComponentStore(tmp_path / 'store')
    partial = store.root / 'downloads' / digest
    partial.parent.mkdir(parents=True)
    partial.write_bytes(data[:8192])
    with interrupted_mirrors(data, False, ignore_range) as (base, calls), store.lock():
        url = base + '/secondary'
        ComponentDownloader.metadata_path(partial).write_text(json.dumps({'url': url}), encoding='utf-8')
        artifact = store.obtain(digest, {'size': len(data), 'urls': [url]}, ComponentDownloader(), lambda: None)
        assert artifact.read_bytes() == data
        assert calls == [('/secondary', 'bytes=8192-')]


@pytest.mark.parametrize('origin', [None, 'different', 'same'])
def test_cancelled_origin_switch_preserves_partial_and_does_not_contact_a_source(tmp_path, origin):
    url = 'http://127.0.0.1:1/never-contacted'
    partial = tmp_path / 'partial'
    partial.write_bytes(b'preserve the cancelled prefix')
    metadata = ComponentDownloader.metadata_path(partial)
    if origin is not None:
        metadata.write_text(json.dumps({'url': url if origin == 'same' else 'http://127.0.0.1/old'}), encoding='utf-8')
    before = partial.read_bytes(), metadata.read_bytes() if metadata.exists() else None
    def cancel():
        raise InterruptedError('synthetic user cancellation')
    with mock.patch('requests.get') as request, pytest.raises(InterruptedError):
        ComponentDownloader(cancel).artifact(url, partial, {'size': 100})
    request.assert_not_called()
    assert (partial.read_bytes(), metadata.read_bytes() if metadata.exists() else None) == before


def test_a_fresh_caller_reuses_the_verified_mirror_result_without_repeating_the_bad_source(tmp_path):
    data = bytes(range(256)) * 512
    digest = hashlib.sha256(data).hexdigest()
    root = tmp_path / 'store'
    with interrupted_mirrors(data, True) as (base, calls):
        specification = {'size': len(data), 'urls': [base + '/primary', base + '/secondary']}
        for _ in range(2):
            store = ComponentStore(root)
            with store.lock():
                artifact = store.obtain(digest, specification, ComponentDownloader(), lambda: None)
            assert artifact.read_bytes() == data
            assert len(calls) == 4
