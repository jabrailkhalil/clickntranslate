"""Compare identical approved OCR bytes with one-shot and demand reuse.

Uses a locally installed component read-only. No downloads, user profile,
clipboard, visible windows or modifications of approved component generations.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import threading

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from component_runtime import worker_environment
from native_worker_client import NativeWorkerClient, WorkerCancelled


def equivalent(response):
    # Wall-clock time is intentionally excluded; text, confidence, reading
    # order and all polygon coordinates must remain identical.
    return {key: [{k:v for k,v in item.items() if k != 'elapsed_ms'} for item in value]
            if key == 'results' else value for key,value in response.items()}


def run(component, output, reference=None, repeats=3, lifecycle=False):
    from PyQt5 import QtCore, QtGui
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    if sys.platform == 'win32':
        for filename in ('segoeui.ttf','arial.ttf'):
            QtGui.QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/filename))
    output.mkdir(parents=True, exist_ok=True)
    runtime = component / 'runtime' / 'python.exe'
    old = component / 'runtime' / 'adapter' / 'ocr_worker.py'
    # Same entry point as source previews; no system Python or component edits.
    new_command = [str(runtime), str(PROJECT / 'src' / 'ocr_runtime_entry.py')]
    samples = {'en': 'Hello portable translation\nKeep the same words and positions.',
               'ru': 'Проверка распознавания текста\nСохраняем качество и расположение.',
               'ar': 'مرحبا بالعالم\nهذا اختبار للتعرف على النص العربي'}
    reports = []
    for code, text in samples.items():
        image_path = output / (code + '.png')
        image = QtGui.QImage(1100, 240, QtGui.QImage.Format_RGB32)
        image.fill(QtCore.Qt.white)
        painter = QtGui.QPainter(image)
        painter.setPen(QtCore.Qt.black)
        painter.setFont(QtGui.QFont('Segoe UI', 26))
        painter.drawText(QtCore.QRect(24, 24, 1050, 200),
                         QtCore.Qt.TextWordWrap | QtCore.Qt.AlignVCenter, text)
        painter.end()
        assert image.save(str(image_path))
        reports.append(compare(code, image_path, component, output, runtime, old, new_command, repeats))
    if reference:
        reports.append(compare('en-reference', reference, component, output, runtime, old, new_command, repeats))
    result = {'platform': sys.platform, 'kind':'native RapidOCR, same installed component bytes',
              'component':component.name, 'repeats':repeats, 'samples':reports}
    if lifecycle:
        result['lifecycle'] = check_lifecycle(new_command, component, output)
    (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2),encoding='utf-8')
    print(json.dumps({'samples':[{k:v for k,v in item.items() if k != 'output'} for item in reports],
                      'lifecycle':result.get('lifecycle')}, indent=2))
    return all(item['identical'] and item['text_present'] for item in reports)


def process_cpu_seconds(process):
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes
    values = [wintypes.FILETIME() for _ in range(4)]
    query = ctypes.WinDLL('kernel32').GetProcessTimes
    query.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    if not query(wintypes.HANDLE(process._handle), *[ctypes.byref(value) for value in values]):
        raise ctypes.WinError()
    return sum((value.dwHighDateTime << 32) + value.dwLowDateTime for value in values[2:]) / 1e7


def check_lifecycle(command, component, output):
    client = NativeWorkerClient()
    path = output / 'en.json'
    identity = (str(component),'en')
    environment = worker_environment()
    try:
        prepare_path = output / 'prepare-en.json'
        request = json.loads(path.read_text(encoding='utf-8'))
        request['action'] = 'prepare'
        request['images'] = []
        prepare_path.write_text(json.dumps(request), encoding='utf-8')
        started = time.monotonic()
        prepared = client.request(command,identity,prepare_path,environment=environment,timeout=30,
                                  engine='rapidocr',prepare_only=True,background=True)
        prepare_ms = (time.monotonic() - started) * 1000
        assert prepared['prepared']
        prepared_pid = client._process.pid
        started = time.monotonic()
        first = client.request(command,identity,path,environment=environment,timeout=30,engine='rapidocr')
        first_ms = (time.monotonic() - started) * 1000
        assert client._process.pid == prepared_pid
        assert client._process is not None, 'Reference model was not retained'
        process = client._process
        idle_started = time.monotonic()
        time.sleep(.5)  # exclude the unchanged native pool's post-inference spin
        cpu_before = process_cpu_seconds(process)
        time.sleep(1)
        cpu_after = process_cpu_seconds(process)
        # Uses the production five-minute policy, with no override. This CLI
        # stays hidden; its caller can continue working while it waits.
        process.wait(timeout=310)
        idle_exit = time.monotonic() - idle_started
        restarted = client.request(command,identity,path,environment=environment,timeout=30)
        assert equivalent(first) == equivalent(restarted)
        process = client._process
        cancel = threading.Event()
        timer = threading.Timer(.04, cancel.set)
        started = time.monotonic()
        timer.start()
        try:
            client.request(command,identity,path,environment=environment,timeout=30,cancel=cancel.is_set)
        except WorkerCancelled:
            pass
        else:
            raise AssertionError('Cancellation did not interrupt recognition')
        finally:
            timer.join()
        canceled_ms = (time.monotonic() - started) * 1000
        assert process.poll() is not None and client._process is None
        return dict(idle_cpu_seconds=round(cpu_after-cpu_before,6) if cpu_before is not None else None,
                    idle_exit_seconds=round(idle_exit,3), restart_identical=True,
                    cancel_ms=round(canceled_ms,2), canceled_child_reaped=True,
                    prepare_ms=round(prepare_ms,2), first_ocr_after_prepare_ms=round(first_ms,2),
                    prepared_child_reused=True, idle_policy_seconds=300)
    finally:
        client.close()


def compare(code, image, component, output, runtime, old, command, repeats):
    request_path = output / (code + '.json')
    language = code.split('-')[0]
    request_path.write_text(json.dumps({'engine':'rapidocr', 'action':'recognize',
        'root_dir':str(component), 'language_code':language, 'allow_download':False,
        'images':[{'label':'native-corpus', 'path':str(image)}]}), encoding='utf-8')
    environment=worker_environment()
    one_shot, reused, actual = [], [], []
    for _ in range(repeats):
        started=time.perf_counter()
        result=subprocess.run([str(runtime),str(old),str(request_path)],capture_output=True,
            text=True, encoding='utf-8', errors='replace', timeout=120, env=environment,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        one_shot.append((time.perf_counter()-started)*1000)
        payload=json.loads(result.stdout)
        if result.returncode or payload.get('error'):
            raise RuntimeError(payload.get('error') or result.stderr[-1000:])
        actual.append(equivalent(payload))
    client=NativeWorkerClient()
    retained=[]
    memory=[]
    try:
        for _ in range(repeats):
            started=time.perf_counter()
            payload=client.request(command,(str(component),language),request_path,environment=environment,timeout=120)
            reused.append((time.perf_counter()-started)*1000)
            if payload.get('error'):
                raise RuntimeError(payload['error'])
            actual.append(equivalent(payload))
            retained.append(client._process is not None)
            memory.append(client.last_memory_bytes)
    finally:
        client.close()
    reference=actual[0]
    prepared_path = output / (code + '-prepare.json')
    prepare_request = json.loads(request_path.read_text(encoding='utf-8'))
    prepare_request.update(action='prepare', images=[])
    prepared_path.write_text(json.dumps(prepare_request), encoding='utf-8')
    prepared_client = NativeWorkerClient()
    try:
        result = prepared_client.request(command, (str(component), language), prepared_path,
            environment=environment, timeout=120, engine='rapidocr', prepare_only=True, background=True)
        assert result['prepared']
        pid = prepared_client._process.pid
        started = time.perf_counter()
        prepared_result = prepared_client.request(command, (str(component), language), request_path,
            environment=environment, timeout=120, engine='rapidocr')
        prepared_ms = (time.perf_counter() - started) * 1000
        assert prepared_client._process.pid == pid
        actual.append(equivalent(prepared_result))
    finally:
        prepared_client.close()
    return {'case':code, 'identical':all(value==reference for value in actual),
            'first_after_prepare_ms':round(prepared_ms,2),
            'text_present':bool(reference.get('results') and reference['results'][0].get('text')),
            'one_shot_ms':one_shot,'demand_ms':reused,'retained':retained,'memory_bytes':memory,
            'one_shot_median_ms':round(statistics.median(one_shot),2),
            'warm_median_ms':round(statistics.median(reused[1:] or reused),2), 'output':reference}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--lifecycle', action='store_true')
    args=parser.parse_args()
    raise SystemExit(0 if run(args.component.resolve(),args.output.resolve(),
                             args.reference.resolve() if args.reference else None,args.repeats,args.lifecycle) else 1)
