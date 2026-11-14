"""Resource lifetime and correctness gates for demand-only optimization."""
import json
import os
from pathlib import Path
import random
import sys
import threading
import time
from unittest import mock
from types import SimpleNamespace

import pytest
from PIL import Image
from PyQt5 import QtGui

import ocr
import translater
from background_tasks import IdleExecutor
from native_worker_client import NativeWorkerClient, WorkerCancelled, WorkerBusy

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def child_adapter(tmp_path):
    # Actual child/pipe/PNG/lease lifecycle, with a deterministic model stand-in.
    # No user clipboard, API, native models or settings are touched.
    script = tmp_path / 'worker adapter.py'
    script.write_text(
        'import sys, os, time\n'
        f'sys.path.insert(0, {str(ROOT / "src")!r})\n'
        'import ocr_worker as w\n'
        'import worker_lease\nworker_lease.memory_pressure_high=lambda:False\n'
        'w.IDLE_SECONDS=.25\n'
        'count=0\n'
        'def request(r):\n'
        ' global count\n'
        ' count+=1\n'
        ' time.sleep(r.get("delay",0))\n'
        ' if r.get("fail"): raise RuntimeError("test failure")\n'
        ' return {"pid":os.getpid(),"count":count,"language":r["language_code"]}\n'
        'w.run_request=request\n'
        'raise SystemExit(w.main())\n', encoding='utf-8')
    request = tmp_path / 'request.json'
    request.write_text(json.dumps(dict(engine='rapidocr', action='recognize', language_code='ar')),
                       encoding='utf-8')
    return [sys.executable, str(script)], request


def test_client_does_not_spawn_at_construction():
    with mock.patch('native_worker_client.subprocess.Popen') as spawn:
        client = NativeWorkerClient()
        client.close()
    spawn.assert_not_called()


def test_reuse_then_language_switch_replaces_the_only_child(child_adapter):
    command, request = child_adapter
    client = NativeWorkerClient()
    try:
        first = client.request(command, ('ar',), request)
        second = client.request(command, ('ar',), request)
        assert second['pid'] == first['pid']
        assert second['count'] == 2
        previous = client._process
        request.write_text(json.dumps(dict(engine='rapidocr', action='recognize', language_code='ru')))
        switched = client.request(command, ('ru',), request)
        assert switched['pid'] != first['pid']
        assert switched['count'] == 1 and switched['language'] == 'ru'
        assert previous.poll() is not None
    finally:
        client.close()


def test_idle_child_releases_its_model_and_response_thread(child_adapter):
    command, request = child_adapter
    client = NativeWorkerClient()
    try:
        client.request(command, ('ar',), request)
        process, reader = client._process, client._reader
        process.wait(timeout=5)
        reader.join(timeout=2)
        assert not reader.is_alive()
        # No timer or monitor restarts the exited model.
        assert process.poll() is not None
        result = client.request(command, ('ar',), request)
        assert result['count'] == 1
    finally:
        client.close()


def test_cancel_kills_and_reaps_busy_child_before_return(child_adapter):
    command, request = child_adapter
    client = NativeWorkerClient()
    cancel = threading.Event()
    try:
        client.request(command, ('ar',), request)
        process = client._process
        request.write_text(json.dumps(dict(engine='rapidocr', action='recognize', language_code='ar', delay=10)))
        timer = threading.Timer(.15, cancel.set)
        timer.start()
        started = time.monotonic()
        with pytest.raises(WorkerCancelled):
            client.request(command, ('ar',), request, cancel=cancel.is_set)
        timer.join()
        assert time.monotonic() - started < 2
        assert process.poll() is not None and client._process is None
    finally:
        client.close()


def test_child_holds_generation_lease_until_idle_exit(child_adapter, tmp_path):
    from component_store import _file_lock
    from component_catalog import ComponentError
    command, request = child_adapter
    lease = tmp_path / 'generation.lock'
    client = NativeWorkerClient()
    try:
        with _file_lock(lease, shared=True):
            client.request(command, ('ar',), request,
                           environment=dict(os.environ, CLICKNTRANSLATE_OCR_LEASE=str(lease)))
        with pytest.raises(ComponentError):
            with _file_lock(lease):
                pass
        client._process.wait(timeout=5)
        with _file_lock(lease):
            pass
    finally:
        client.close()


def test_model_cache_is_lazy_and_retains_only_current_language(monkeypatch):
    import ocr_worker
    import rapidocr_models
    made = []
    def create(*args):
        made.append(args)
        return object()
    monkeypatch.setattr(rapidocr_models, 'create_engine', create)
    monkeypatch.setattr(ocr_worker, '_rapidocr_class', lambda: object)
    monkeypatch.setattr(ocr_worker, '_SERVING', True)
    monkeypatch.setattr(ocr_worker, '_RESIDENT_ENGINE', None)
    monkeypatch.setattr(ocr_worker, '_RESIDENT_KEY', None)
    assert not made
    first = ocr_worker._rapidocr_engine({'language_code':'ar'})
    assert ocr_worker._rapidocr_engine({'language_code':'ar'}) is first
    assert ocr_worker._rapidocr_engine({'language_code':'ru'}) is not first
    assert len(made) == 2


def test_frozen_linux_uses_its_bundled_worker(monkeypatch):
    import component_runtime
    monkeypatch.setattr(component_runtime, 'managed_runtime', lambda *args: None)
    monkeypatch.setattr(ocr.platform_support, 'IS_WINDOWS', False)
    monkeypatch.setattr(ocr.platform_support, 'IS_MAC', False)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(ocr, '_native_ocr_worker_path', lambda: '/portable/_internal/OcrWorker')
    assert ocr._native_ocr_worker_enabled()


def test_position_pixels_are_converted_on_run_not_construction(monkeypatch):
    from PyQt5.QtCore import QThread
    monkeypatch.setattr(ocr, 'usable_ocr_engine', lambda engine: engine)
    conversion_threads = []
    def convert(image, engine):
        conversion_threads.append(QThread.currentThread())
        return Image.new('RGB', (2,2))
    monkeypatch.setattr(ocr, '_position_ocr_bitmap', convert)
    monkeypatch.setattr(ocr, '_recognize_image_layout', lambda *args, **kwargs: [])
    image = QtGui.QImage(2, 2, QtGui.QImage.Format_RGB32)
    worker = ocr.create_position_ocr_worker(image, 'en', 'rapidocr')
    assert conversion_threads == []
    worker.start()
    assert worker.wait(3000)
    assert conversion_threads == [worker]


def test_background_executor_is_lazy_bounded_and_expires():
    cleanup = []
    executor = IdleExecutor(workers=1, pending=1, idle_seconds=.1, cleanup=lambda: cleanup.append(True))
    assert executor._workers == 0
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    def first():
        started.set()
        release.wait(2)
    assert executor.submit(first)
    assert started.wait(2)
    assert executor.submit(finished.set)
    assert not executor.submit(lambda: None)
    release.set()
    assert finished.wait(2)
    deadline = time.monotonic() + 2
    while not cleanup and time.monotonic() < deadline:
        time.sleep(.01)
    assert cleanup == [True] and executor._workers == 0


def test_executor_preserves_parallel_independent_requests_and_reuses_idle_workers():
    executor=IdleExecutor(workers=3,pending=4,idle_seconds=.1)
    release=threading.Event()
    entered=[threading.Event() for _ in range(3)]
    for event in entered:
        assert executor.submit(lambda event=event:(event.set(),release.wait(2)))
    try:
        assert all(event.wait(1) for event in entered)
        assert executor._workers==3
    finally:
        release.set()
    deadline=time.monotonic()+2
    while executor._workers and time.monotonic()<deadline:
        time.sleep(.01)
    assert executor._workers==0


def test_other_model_does_not_wait_behind_unrelated_busy_ocr(child_adapter):
    command,path=child_adapter
    client=NativeWorkerClient()
    client._identity=('en',)
    client._lock.acquire()
    try:
        started=time.monotonic()
        with pytest.raises(WorkerBusy):
            client.request(command,('ar',),path,fallback_for_other_model=True)
        assert time.monotonic()-started<.04
    finally:
        client._lock.release()
        client.close()


def test_source_adapter_uses_private_python_only_for_known_sdk(monkeypatch):
    from component_runtime import source_ocr_adapter_command
    monkeypatch.delattr(sys,'frozen',raising=False)
    runtime=dict(command=['private runtime/python.exe','private runtime/adapter/ocr_worker.py'],
                 receipt=dict(component='ocr.rapidocr',upstream='3.10.0'))
    command=source_ocr_adapter_command(runtime)
    assert command[0]==runtime['command'][0]
    assert Path(command[1])==ROOT/'src/ocr_runtime_entry.py'
    runtime['receipt']['upstream']='unknown'
    assert source_ocr_adapter_command(runtime) is None
    runtime['receipt']['upstream']='3.10.0'
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    assert source_ocr_adapter_command(runtime) is None


def test_document_delta_payload_is_linear_and_exact(monkeypatch):
    from document_translation import translate_document_text
    import document_translation
    parts = ['Hello.\n'] * 200
    monkeypatch.setattr(document_translation, 'split_text_chunks', lambda *a, **k:
        [document_translation.TranslationChunk(i,text) for i,text in enumerate(parts)])
    monkeypatch.setattr(translater, 'iter_translate_texts', lambda *a, **k:
        ((i, 'Bonjour.\n', '') for i in range(len(parts))))
    deltas = []
    completed = []
    result, chunks = translate_document_text(''.join(parts), 'en', 'fr', provider_engine='google',
        delta_callback=lambda text, done, total: (deltas.append(text), completed.append(done)))
    assert ''.join(deltas) == result
    assert sum(map(len,deltas)) == len(result)
    assert len(chunks) == len(parts)
    assert completed[0] == 1


def _old_group(lines):
    # Frozen pre-optimization grouping: preserve geometry/tie-break semantics.
    groups=[]
    for line in sorted(lines,key=lambda item:(item[1],item[0])):
        x,y,w,h,_ = line
        best,gap=None,None
        for i,group in enumerate(groups):
            left=min(t[0] for t in group); right=max(t[0]+t[2] for t in group)
            top=min(t[1] for t in group); bottom=max(t[1]+t[3] for t in group)
            overlap=max(0,min(y+h,bottom)-max(y,top))/max(1,min(h,bottom-top))
            distance=max(0,max(left,x)-min(right,x+w))
            if overlap>=.58 and distance<=max(18,1.25*max(h,bottom-top)) and (gap is None or distance<gap):
                best,gap=i,distance
        if best is None: groups.append([line])
        else: groups[best].append(line)
    result=[]
    for group in groups:
        x=min(t[0] for t in group);y=min(t[1] for t in group)
        result.append((x,y,max(t[0]+t[2] for t in group)-x,max(t[1]+t[3] for t in group)-y,
                       ' '.join(t[4] for t in sorted(group,key=lambda t:t[0]))))
    return sorted(result,key=lambda t:(t[1],t[0]))


def test_grouping_preserves_geometry_and_order_over_seeded_layouts():
    rng=random.Random(834013)
    for _ in range(300):
        lines=[(float(rng.randrange(-40,600)),float(rng.randrange(-30,400)),
                float(rng.randrange(1,180)),float(rng.randrange(1,130)),f'Word{i}')
               for i in range(rng.randrange(1,80))]
        assert ocr._group_screen_ocr_lines(lines) == _old_group(lines)


def test_grouping_joins_arabic_in_logical_reading_order():
    blocks=ocr._group_screen_ocr_lines([(0.,0.,35.,20.,'بكم'), (40.,0.,35.,20.,'مرحبا')])
    assert blocks == [(0.,0.,75.,20.,'مرحبا بكم')]


def test_source_startup_does_not_import_argos_native_runtime(monkeypatch):
    monkeypatch.delenv('CLICKNTRANSLATE_ARGOS_WORKER', raising=False)
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.setattr(translater, '_managed_argos_runtime', lambda: None)
    monkeypatch.setattr('importlib.util.find_spec',lambda name:SimpleNamespace())
    with mock.patch.object(translater, '_ensure_argos_available') as native:
        assert translater.preload_argos_runtime()
    native.assert_not_called()


def test_missing_argos_sdk_does_not_become_available_just_because_adapter_exists(monkeypatch):
    monkeypatch.delenv('CLICKNTRANSLATE_ARGOS_WORKER',raising=False)
    monkeypatch.delattr(sys,'frozen',raising=False)
    monkeypatch.setattr(translater,'_managed_argos_runtime',lambda:None)
    monkeypatch.setattr('importlib.util.find_spec',lambda name:None)
    with mock.patch.object(translater,'_ensure_argos_available') as native:
        assert not translater.preload_argos_runtime()
    native.assert_not_called()


def test_worker_protocol_accepts_spaces_and_unicode_paths(child_adapter, tmp_path):
    command,path=child_adapter
    folder=tmp_path/'путь с пробелами العربية'
    folder.mkdir()
    renamed=folder/'адаптер.py'
    renamed.write_bytes(Path(command[1]).read_bytes())
    request=folder/'запрос.json'
    request.write_bytes(path.read_bytes())
    client=NativeWorkerClient()
    try:
        result=client.request([command[0],str(renamed)],('unicode',),request)
        assert result['language']=='ar'
    finally:
        client.close()


def test_idle_exit_notifies_retirement_without_a_polling_thread(child_adapter):
    command,path=child_adapter
    client=NativeWorkerClient()
    retired=threading.Event()
    try:
        client.request(command,('retire',),path,on_exit=retired.set)
        assert retired.wait(3)
        assert client._process.wait(timeout=2)==0
    finally:
        client.close()


def test_libre_server_switch_cannot_relabel_in_flight_result(monkeypatch, tmp_path):
    monkeypatch.setenv('CLICKNTRANSLATE_LIBRETRANSLATE_URL', 'https://a.example.test')
    monkeypatch.setattr(translater, 'get_cached_translator_config', lambda: {})
    operation = translater._TranslationCache('en', 'ru')
    operation.data_dir = str(tmp_path)
    calls=[]
    def post(url, **kwargs):
        calls.append(url)
        monkeypatch.setenv('CLICKNTRANSLATE_LIBRETRANSLATE_URL', 'https://b.example.test')
        return SimpleNamespace(status_code=200, json=lambda:{'translatedText':'Ответ сервера A'})
    monkeypatch.setattr(translater, '_get_http_session', lambda:SimpleNamespace(post=post))
    result = translater.translate_text('Hello', 'en', 'ru', engine='libretranslate', _context=operation)
    assert calls == ['https://a.example.test/translate']
    assert operation.get('Hello', 'libretranslate') == result
    next_operation = translater._TranslationCache('en','ru')
    next_operation.data_dir = str(tmp_path)
    assert next_operation.get('Hello', 'libretranslate') is None


def test_argos_document_keeps_one_worker_and_exact_chunk_mapping(monkeypatch):
    calls=[]
    saved=[]
    cache=SimpleNamespace(get=lambda text, engine: 'cached' if text=='existing' else None,
                          save=lambda *args:saved.append(args))
    def request(payload, **kwargs):
        calls.append(payload)
        for piece in payload['pieces']:
            kwargs['chunk_callback']({'index':piece['index'], 'text':piece['text'].upper()})
        return {'completed':len(payload['pieces']), 'error':''}
    monkeypatch.setattr(translater, '_run_argos_worker_request', request)
    results=list(translater._iter_argos_document(['one','existing','three'], 'en','ru',cache,None,None))
    assert results == [(0,'ONE',''),(1,'cached',''),(2,'THREE','')]
    assert len(calls)==1 and [p['index'] for p in calls[0]['pieces']]==[0,2]
    assert len(saved)==2


def test_argos_document_stops_after_wrong_chunk_instead_of_shifting_results(monkeypatch):
    def request(payload, **kwargs):
        kwargs['chunk_callback']({'index':1, 'text':'WRONG'})
        return {'completed':1, 'error':''}
    monkeypatch.setattr(translater, '_run_argos_worker_request', request)
    save=mock.Mock()
    cache=SimpleNamespace(get=lambda *args:None, save=save)
    results=list(translater._iter_argos_document(['one','two'], 'en','ru',cache,None,None))
    assert all(not value and error for _,value,error in results)
    save.assert_not_called()


def test_model_over_retention_budget_exits_after_delivering_result(child_adapter, tmp_path):
    command, request = child_adapter
    script=Path(command[1])
    text=script.read_text(encoding='utf-8').replace('import ocr_worker as w',
        'import worker_lease\nworker_lease.resident_bytes=lambda:512*1024*1024\nimport ocr_worker as w')
    script.write_text(text,encoding='utf-8')
    client=NativeWorkerClient()
    try:
        result=client.request(command,('ar',),request)
        assert result['language']=='ar' and client._process is None
    finally:
        client.close()


def test_owner_pipe_closure_stops_child_even_during_native_work(child_adapter):
    command, request=child_adapter
    client=NativeWorkerClient()
    try:
        client.request(command,('ar',),request)
        process=client._process
        request.write_text(json.dumps(dict(engine='rapidocr', action='recognize',language_code='ar',delay=10)))
        process.stdin.write(json.dumps({'id':2,'path':str(request)}).encode()+b'\n')
        process.stdin.flush()
        process.stdin.close()
        process.wait(timeout=2)
        assert process.poll() is not None
    finally:
        client.close()


def test_package_status_does_not_load_a_model(monkeypatch):
    import component_runtime
    import rapidocr_models
    monkeypatch.setattr(component_runtime,'managed_runtime',lambda *a:{'folder':'verified'})
    monkeypatch.setattr(rapidocr_models,'installed_languages',lambda *a:['en'])
    monkeypatch.setattr(ocr,'_easyocr_installed_language_codes',lambda:['en'])
    with mock.patch.object(ocr,'rapidocr_available') as rapid, mock.patch.object(ocr,'easyocr_available') as easy:
        assert ocr.rapidocr_status()==(True,'')
        assert ocr.easyocr_status('en')==(True,'')
    rapid.assert_not_called()
    easy.assert_not_called()


@pytest.mark.skipif(not ocr._WINRT_AVAILABLE, reason='Windows OCR is not installed on this test host')
def test_real_windows_ocr_accepts_pixels_prepared_in_worker_thread(monkeypatch):
    from PyQt5.QtCore import Qt
    monkeypatch.setattr(ocr,'usable_ocr_engine',lambda value:value)
    image=QtGui.QImage(1200,180,QtGui.QImage.Format_RGB32)
    image.fill(Qt.white)
    painter=QtGui.QPainter(image)
    painter.setPen(Qt.black)
    painter.setFont(QtGui.QFont('Segoe UI',32))
    painter.drawText(20,100,'Hello portable translation')
    painter.end()
    worker=ocr.create_position_ocr_worker(image,'en','windows')
    results=[]
    worker.result_ready.connect(results.append)
    worker.start()
    assert worker.wait(15000)
    from PyQt5.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    assert not getattr(worker,'error_message','')
    assert results and 'portable' in ' '.join(item[4] for item in results[0]).lower()
