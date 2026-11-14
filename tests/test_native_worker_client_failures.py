"""Protocol and launch faults never leave a reusable half-started OCR client."""
import io
import json
import threading
from unittest import mock

import pytest

import native_worker_client as native


class ScriptedProcess:
    def __init__(self, response=None):
        self.stdin = io.BytesIO()
        lines = [{'protocol': native.PROTOCOL}]
        if response is not None:
            lines.append(response)
        self.stdout = io.BytesIO(b''.join(json.dumps(line).encode() + b'\n' for line in lines))
        self.returncode = None
        self.killed = self.waited = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -1

    def wait(self, timeout=None):
        self.waited = True
        return self.returncode


def assert_retired(client, process):
    assert process.killed and process.waited
    assert process.stdin.closed and process.stdout.closed
    assert client._process is client._reader is client._responses is None
    assert client._identity is None and client._has_model is False


@pytest.mark.parametrize('failure', ['construct', 'start'])
def test_reader_launch_failure_preserves_original_error_closes_pipes_and_can_retry(monkeypatch, tmp_path, failure):
    client = native.NativeWorkerClient()
    process = ScriptedProcess()
    job_closed = mock.Mock()
    monkeypatch.setattr(native.subprocess, 'Popen', lambda *args, **kwargs: process)
    monkeypatch.setattr('worker_lease.owned_job', lambda process: job_closed)
    thread_class = threading.Thread

    def unavailable_thread(**kwargs):
        if failure == 'construct':
            raise RuntimeError('reader launch unavailable')
        reader = thread_class(**kwargs)
        reader.start = mock.Mock(side_effect=RuntimeError('reader launch unavailable'))
        return reader

    try:
        with mock.patch.object(native.threading, 'Thread', unavailable_thread):
            with pytest.raises(RuntimeError, match='reader launch unavailable'):
                client.request(['fake-worker'], ('en',), tmp_path/'request.json', timeout=1)
        assert_retired(client, process)
        job_closed.assert_called_once_with()
        fresh = ScriptedProcess({'id': 1, 'retain': False, 'result': {'text': 'fresh'}})
        monkeypatch.setattr(native.subprocess, 'Popen', lambda *args, **kwargs: fresh)
        assert client.request(['fake-worker'], ('en',), tmp_path/'request.json', timeout=1) == {'text': 'fresh'}
        assert_retired(client, fresh)
    finally:
        client.close()


@pytest.mark.parametrize('response', [
    {'id': 1, 'retain': True, 'result': None},
    {'id': 1, 'retain': True, 'result': []},
    {'id': 1, 'retain': True, 'result': 'wrong payload'},
    {'id': 1, 'retain': True, 'result': 9},
    {'id': True, 'retain': True, 'result': {'text': 'wrong id'}},
    {'id': 1.0, 'retain': True, 'result': {'text': 'wrong id'}},
    {'id': '1', 'retain': True, 'result': {'text': 'wrong id'}},
    {'id': 1, 'retain': 'false', 'result': {'text': 'wrong retention'}},
    {'id': 1, 'retain': 1, 'result': {'text': 'wrong retention'}},
    {'id': 1, 'retain': [], 'result': {'text': 'wrong retention'}},
    {'id': 1, 'retain': True},
], ids=['null', 'list', 'text', 'number', 'bool-id', 'float-id', 'text-id',
        'text-retain', 'int-retain', 'list-retain', 'missing-result'])
def test_malformed_response_retires_model_before_it_can_be_reused(monkeypatch, tmp_path, response):
    client = native.NativeWorkerClient()
    process = ScriptedProcess(response)
    monkeypatch.setattr(native.subprocess, 'Popen', lambda *args, **kwargs: process)
    monkeypatch.setattr('worker_lease.owned_job', lambda process: lambda: None)
    try:
        with pytest.raises(ValueError):
            client.request(['fake-worker'], ('en',), tmp_path/'request.json', timeout=1,
                           engine='rapidocr', prepare_only=True)
        assert_retired(client, process)
        fresh = ScriptedProcess({'id': 2, 'retain': False, 'result': {'text': 'fresh', 'error': ''}})
        monkeypatch.setattr(native.subprocess, 'Popen', lambda *args, **kwargs: fresh)
        assert client.request(['fake-worker'], ('en',), tmp_path/'request.json', timeout=1) == {'text': 'fresh', 'error': ''}
        assert_retired(client, fresh)
    finally:
        client.close()


def test_valid_nonretained_response_without_optional_retention_field_remains_compatible(monkeypatch, tmp_path):
    client = native.NativeWorkerClient()
    process = ScriptedProcess({'id': 1, 'result': {'text': 'accepted'}})
    monkeypatch.setattr(native.subprocess, 'Popen', lambda *args, **kwargs: process)
    monkeypatch.setattr('worker_lease.owned_job', lambda process: lambda: None)
    try:
        assert client.request(['fake-worker'], ('en',), tmp_path/'request.json', timeout=1) == {'text': 'accepted'}
        assert_retired(client, process)
    finally:
        client.close()
