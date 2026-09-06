import os
from pathlib import Path
import subprocess
import sys
import uuid
from unittest import mock

import psutil
import pytest

import instance_lifecycle as lifecycle


def info(script, pid=10, ppid=1, created=123):
    return {'pid': pid, 'ppid': ppid, 'name': 'pythonw.exe', 'exe': 'pythonw.exe',
            'cmdline': ['pythonw.exe', str(script)], 'create_time': created}


def test_python_identity_is_the_script_not_the_interpreter(tmp_path):
    script = tmp_path / 'main.py'
    assert lifecycle.application_path(info(script), str(script)) == str(script)
    assert lifecycle.application_path(info(tmp_path / 'other' / 'main.py'), str(script)) == ''
    assert lifecycle.application_path(info('main.py'), str(script), str(tmp_path)) == str(script)
    candidate = info(script)
    candidate['cmdline'] = ['pythonw.exe', '-c', 'main.py']
    assert lifecycle.application_path(candidate, str(script)) == ''


def test_other_source_checkout_requires_application_files(tmp_path):
    script = tmp_path / 'old' / 'main.py'
    script.parent.mkdir()
    current = str(tmp_path / 'new' / 'main.py')
    assert lifecycle.application_path(info(script), current) == ''
    for name in ('translater.py', 'single_instance.py', 'icons/icon.ico'):
        path = script.parent / name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    assert lifecycle.application_path(info(script), current) == str(script)


def test_launchers_own_ancestors_and_ocr_helpers_are_not_duplicate_guis(tmp_path):
    script = str(tmp_path / 'main.py')
    processes = [mock.Mock(info=info(script, 10)), mock.Mock(info=info(script, 11, 10)),
                 mock.Mock(info=info(script, 98)), mock.Mock(info=info(script, 99))]
    helper = info(script, 12)
    helper['cmdline'].append('ocr')
    processes.append(mock.Mock(info=helper))
    current = mock.Mock(pid=99)
    current.parents.return_value = [mock.Mock(pid=98)]
    with mock.patch.object(lifecycle.psutil, 'Process', return_value=current), \
            mock.patch.object(lifecycle.psutil, 'process_iter', return_value=processes), \
            mock.patch.object(lifecycle, '_active_gui_pids', return_value={11}):
        found = lifecycle.running_instances(script)
    assert [item['pid'] for item in found] == [11]
    assert found[0]['same_path']


def test_close_rechecks_pid_identity_and_does_not_touch_a_newer_launch():
    chosen = [{'pid': 10, 'create_time': 12}]
    current = [{'pid': 10, 'create_time': 13}, {'pid': 20, 'create_time': 12}]
    with mock.patch.object(lifecycle, 'running_instances', return_value=current), \
            mock.patch.object(lifecycle, 'post_close_requests') as post, \
            mock.patch.object(lifecycle.psutil, 'Process') as process:
        assert lifecycle.close_instances(chosen, 'main.py')
    post.assert_not_called()
    process.assert_not_called()


def test_shutdown_failure_does_not_claim_success():
    chosen = [{'pid': 10, 'create_time': 12}]
    process = mock.Mock(pid=10)
    process.create_time.return_value = 12
    process.terminate.side_effect = psutil.AccessDenied(10)
    with mock.patch.object(lifecycle, 'running_instances', return_value=chosen), \
            mock.patch.object(lifecycle, 'post_close_requests') as post, \
            mock.patch.object(lifecycle.psutil, 'Process', return_value=process), \
            mock.patch.object(lifecycle.psutil, 'wait_procs', return_value=([], [process])):
        assert not lifecycle.close_instances(chosen, 'main.py', 0, 0)
    post.assert_called_once_with({10})
    process.kill.assert_not_called()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows mutex and native messages')
@pytest.mark.parametrize('legacy', [False, True])
def test_real_windows_instance_can_be_replaced_and_releases_mutex(tmp_path, legacy):
    # Only this isolated helper receives a close request. It uses the real
    # application message filter, without creating settings, hotkeys or OCR.
    script = tmp_path / 'main.py'
    marker = tmp_path / 'closed.txt'
    name = 'ClicknTranslate_Test_' + uuid.uuid4().hex
    root = str(Path(__file__).resolve().parents[1])
    script.write_text(f'''
import os, sys
sys.path.insert(0, {root!r})
os.environ['QT_QPA_PLATFORM'] = 'windows'
import main
from instance_lifecycle import WindowsInstanceGuard
app = main.QApplication([])
app.setQuitOnLastWindowClosed(False)
window = main.QWidget()
window.setWindowTitle("Click'n'Translate")
window.winId()
class Target:
    def close(self):
        from pathlib import Path
        Path({str(marker)!r}).write_text('graceful')
main._main_window_ref = Target()
filter = main._SingleInstanceMessageFilter()
if not {legacy!r}:
    app.installNativeEventFilter(filter)
guard = WindowsInstanceGuard({name!r})
assert guard.acquire()
print(os.getpid(), flush=True)
app.exec_()
guard.close()
''', encoding='utf-8')
    process = subprocess.Popen([sys.executable, '-u', str(script)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    guard = lifecycle.WindowsInstanceGuard(name)
    try:
        # Importing optional OCR runtimes can print a notice before readiness.
        pid = None
        for _ in range(8):
            line = process.stdout.readline().strip()
            if line.isdigit():
                pid = int(line)
                break
            if process.poll() is not None:
                break
        assert pid, process.stderr.read() if process.poll() is not None else 'No ready PID'
        assert not guard.acquire()
        targets = [item for item in lifecycle.running_instances(str(script)) if item['pid'] == pid]
        assert len(targets) == 1
        assert lifecycle.close_instances(targets, str(script), 0.2 if legacy else 3.0, 3.0)
        process.wait(timeout=5)
        assert marker.exists() is not legacy
        assert guard.acquire()
        assert guard.acquire()  # Holding the guard is idempotent, not a second launch.
    finally:
        guard.close()
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
