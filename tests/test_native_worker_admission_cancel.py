"""A canceled admission cannot retire a different request's retained model."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from native_worker_client import NativeWorkerClient, WorkerCancelled
import native_worker_client as native


@pytest.fixture
def model(tmp_path, monkeypatch):
    script = tmp_path / 'synthetic worker.py'
    script.write_text(
        'import json,os,sys,time\nfrom pathlib import Path\n'
        'print(json.dumps({"protocol":2}),flush=True)\ncount=0\n'
        'for line in sys.stdin:\n'
        ' message=json.loads(line)\n'
        ' if message.get("control"):continue\n'
        ' data=json.loads(Path(message["path"]).read_text(encoding="utf-8"))\n'
        ' if data.get("entered"):Path(data["entered"]).touch()\n'
        ' if data.get("hold"):time.sleep(30)\n'
        ' count+=1\n'
        ' result={"pid":os.getpid(),"count":count,"text":data.get("text","")}\n'
        ' print(json.dumps({"id":message["id"],"retain":True,"result":result}),flush=True)\n',
        encoding='utf-8')
    request_path = tmp_path / 'request.json'
    request_path.write_text('{"text":"first"}', encoding='utf-8')
    environment = {name: os.environ[name] for name in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if name in os.environ}
    environment.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
                       TEMP=str(tmp_path), TMP=str(tmp_path))
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
                 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS', 'NUMBA_NUM_THREADS'):
        environment[name] = '1'
    original_spawn = subprocess.Popen

    def hidden_low_priority(*args, **kwargs):
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
        return original_spawn(*args, **kwargs)

    monkeypatch.setattr(native.subprocess, 'Popen', hidden_low_priority)
    client = NativeWorkerClient()
    def request(**kwargs):
        return client.request([sys.executable, str(script)], ('synthetic-model',), request_path,
                              environment=environment, engine='rapidocr', timeout=5,
                              fallback_for_other_model=True, **kwargs)
    try:
        yield client, request, request_path, tmp_path
    finally:
        client.close()


@pytest.mark.parametrize('pinned', [False, True], ids=['idle-model', 'active-session'])
def test_pre_cancelled_request_preserves_existing_model_and_sends_nothing(model, pinned):
    client, request, path, _root = model
    first = request()
    process = client._process
    if pinned:
        client.activity('another-session', 'rapidocr')
    with pytest.raises(WorkerCancelled):
        request(cancel=lambda: True)
    assert client._process is process and process.poll() is None
    path.write_text('{"text":"next"}', encoding='utf-8')
    following = request()
    assert following == {'pid': first['pid'], 'count': 2, 'text': 'next'}


def test_cancellation_at_lock_admission_keeps_the_preexisting_worker(model):
    client, request, _path, _root = model
    first = request()
    process = client._process
    granted, continue_admission, canceled = threading.Event(), threading.Event(), threading.Event()
    owner = threading.get_ident()
    underlying = client._lock

    class AdmissionGate:
        def acquire(self, *args, **kwargs):
            result = underlying.acquire(*args, **kwargs)
            if result and threading.get_ident() != owner:
                granted.set()
                assert continue_admission.wait(5)
            return result
        def release(self):
            underlying.release()
        def locked(self):
            return underlying.locked()
        def __enter__(self):
            self.acquire()
            return self
        def __exit__(self, *_args):
            self.release()

    client._lock = AdmissionGate()
    errors = []
    def waiting():
        try:
            request(cancel=canceled.is_set)
        except BaseException as error:
            errors.append(error)
    thread = threading.Thread(target=waiting)
    thread.start()
    try:
        assert granted.wait(5)
        canceled.set()
    finally:
        continue_admission.set()
        thread.join(6)
    assert not thread.is_alive() and len(errors) == 1 and isinstance(errors[0], WorkerCancelled)
    assert client._process is process and process.poll() is None
    following = request()
    assert following['pid'] == first['pid'] and following['count'] == 2


def test_cancellation_after_request_dispatch_still_retires_reaps_and_can_retry(model):
    client, request, path, root = model
    first = request()
    process = client._process
    entered, canceled = root / 'entered', threading.Event()
    path.write_text(json.dumps({'hold': True, 'entered': str(entered)}), encoding='utf-8')
    errors = []
    def busy():
        try:
            request(cancel=canceled.is_set)
        except BaseException as error:
            errors.append(error)
    thread = threading.Thread(target=busy)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not entered.exists() and time.monotonic() < deadline:
            threading.Event().wait(.01)
        assert entered.exists()
    finally:
        canceled.set()
        thread.join(6)
    assert not thread.is_alive() and len(errors) == 1 and isinstance(errors[0], WorkerCancelled)
    assert client._process is None and process.poll() is not None
    path.write_text('{"text":"fresh"}', encoding='utf-8')
    fresh = request()
    assert fresh['pid'] != first['pid'] and fresh['count'] == 1 and fresh['text'] == 'fresh'
