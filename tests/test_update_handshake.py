"""Real Windows executables must not acknowledge an old or unready child."""
import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest
import psutil
import zipfile
import base64
import uuid

from update_handshake import acknowledge_ready
from release_manifest import write_manifest, verify_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_application_ack_is_atomic_and_uses_runtime_version(tmp_path, monkeypatch):
    import update_handshake
    ack = tmp_path / 'with spaces' / 'ready.txt'
    replace = os.replace
    published = []

    def check_publish(source, destination):
        assert not ack.exists()
        published.append(Path(source).read_text(encoding='utf-8'))
        replace(source, destination)

    monkeypatch.setattr(update_handshake.os, 'replace', check_publish)
    assert acknowledge_ready(['--show-after-update', f'--update-ack={ack}'], '1.7.1')
    assert published == ['1.7.1']
    assert ack.read_text(encoding='utf-8') == '1.7.1'
    assert list(ack.parent.iterdir()) == [ack]


def test_failed_ack_does_not_leave_an_empty_confirmation(tmp_path, monkeypatch):
    import update_handshake
    ack = tmp_path / 'ready.txt'
    def fail(*args):
        raise PermissionError('simulated publication failure')
    monkeypatch.setattr(update_handshake.os, 'replace', fail)
    assert not acknowledge_ready([f'--update-ack={ack}'], '1.7.1')
    assert not list(tmp_path.iterdir())
    assert not acknowledge_ready([], '1.7.1')


@pytest.fixture(scope='module')
def windows_binaries(tmp_path_factory):
    if os.name != 'nt':
        pytest.skip('Windows executable integration')
    folder = tmp_path_factory.mktemp('update_handshake')
    compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if not compiler.exists():
        pytest.skip('.NET Framework compiler unavailable')
    powershell = shutil.which('powershell.exe')
    for script, name in [('build_launcher.ps1', 'launcher.exe'), ('build_apply_updater.ps1', 'updater.exe')]:
        build = subprocess.run([powershell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                str(ROOT / 'tools' / script), '-Version', '1.7.1.0',
                                '-OutputPath', str(folder / name)],
                               capture_output=True, text=True, timeout=45)
        assert build.returncode == 0, build.stdout + build.stderr

    def compile_program(name, source):
        path = folder / f'{name}.cs'
        path.write_text(source, encoding='utf-8')
        target = 'exe' if name in {'verify', 'apply'} else 'winexe'
        build = subprocess.run([str(compiler), '/nologo', f'/target:{target}', f'/out:{folder / (name + ".exe")}', str(path)],
                               capture_output=True, text=True, timeout=30)
        assert build.returncode == 0, build.stdout + build.stderr

    for label, version in [('current', '1.7.1.0'), ('old', '1.7.0.0')]:
        compile_program(label, '''
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
[assembly: AssemblyFileVersion("VERSION")]
class Child {
    static void Main(string[] args) {
        string started = args.FirstOrDefault(a => a.StartsWith("--started="));
        if (started != null) File.WriteAllText(started.Substring(10), "started");
        if (args.Contains("--ready")) {
            Thread.Sleep(200);
            string ack = args.First(a => a.StartsWith("--update-ack=")).Substring(13);
            File.WriteAllText(ack, "1.7.1");
        }
    }
}
'''.replace('VERSION', version))
    compile_program('verify', '''
using System;
using System.Reflection;
class Verify {
    static int Main(string[] args) {
        var method = Assembly.LoadFrom(args[0]).GetType("ClicknTranslateApplyUpdate")
            .GetMethod("VerifyInstalledFiles", BindingFlags.Static | BindingFlags.NonPublic);
        try { method.Invoke(null, new object[] {args[1], "ClicknTranslate.exe", "1.7.1"}); return 0; }
        catch (TargetInvocationException e) { Console.WriteLine(e.InnerException.Message); return 7; }
    }
}
''')
    compile_program('updatable', '''
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
[assembly: AssemblyFileVersion("1.7.1.0")]
class Updatable {
    static void Main(string[] args) {
        string argument = args.FirstOrDefault(a => a.StartsWith("--update-ack="));
        if (argument != null) File.WriteAllText(argument.Substring(13), "1.7.1");
        Thread.Sleep(60000);
    }
}
''')
    compile_program('apply', '''
using System;
using System.Linq;
using System.Reflection;
class Apply {
    [STAThread] static int Main(string[] args) {
        var assembly = Assembly.LoadFrom(args[0]);
        var requestType = assembly.GetType("ClicknTranslateApplyUpdate+UpdateRequest");
        var windowType = assembly.GetType("ClicknTranslateApplyUpdate+UpdateWindow");
        object window = null;
        try {
            var request = requestType.GetMethod("Parse", BindingFlags.Static | BindingFlags.NonPublic)
                .Invoke(null, new object[] {args.Skip(1).ToArray()});
            window = Activator.CreateInstance(windowType, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic,
                null, new object[] {request}, null);
            windowType.GetMethod("ApplyUpdate", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(window, null);
            return 0;
        } catch (TargetInvocationException e) { Console.WriteLine(e.InnerException); return 7; }
        finally { if (window != null) ((IDisposable)window).Dispose(); }
    }
}
''')
    return folder


@pytest.mark.parametrize('ready', [False, True])
def test_launcher_waits_for_child_readiness_without_creating_ack(tmp_path, windows_binaries, ready):
    (tmp_path / 'app').mkdir()
    launcher = tmp_path / 'ClicknTranslate.exe'
    shutil.copy2(windows_binaries / 'launcher.exe', launcher)
    shutil.copy2(windows_binaries / 'current.exe', tmp_path / 'app/ClicknTranslateApp.exe')
    ack, started = tmp_path / 'ready.txt', tmp_path / 'started.txt'
    args = [str(launcher), f'--update-ack={ack}', f'--started={started}']
    if ready:
        args.append('--ready')
    result = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not started.exists():
        time.sleep(.02)
    assert started.exists()
    if ready:
        while time.monotonic() < deadline and not ack.exists():
            time.sleep(.02)
        assert ack.read_text(encoding='utf-8') == '1.7.1'
    else:
        assert not ack.exists(), 'Launching an unready child is not update success'


def test_missing_application_report_identifies_modules_and_interrupted_update(tmp_path, windows_binaries):
    install = tmp_path / 'ClicknTranslate'
    (install / 'data').mkdir(parents=True)
    (install / 'data/config.json').write_text('private settings must not be read', encoding='utf-8')
    (install / 'data/.update-in-progress').touch()
    backup = tmp_path / '.clickntranslate_backup_report_test' / 'app'
    backup.mkdir(parents=True)
    shutil.copy2(windows_binaries / 'old.exe', backup / 'ClicknTranslateApp.exe')
    launcher = install / 'ClicknTranslate.exe'
    shutil.copy2(windows_binaries / 'launcher.exe', launcher)
    report_path = tmp_path / 'startup-report.txt'
    result = subprocess.run([str(launcher), f'--create-bug-report={report_path}'],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding='utf-8')
    assert 'application: missing' in report
    assert 'python_library: missing' in report
    assert 'program_inventory: missing' in report
    assert 'update_marker: present' in report
    assert 'application_present=True' in report
    assert 'version=1.7.1.0' in report
    assert 'private settings must not be read' not in report


@pytest.mark.parametrize('child', ['old', 'current'])
def test_update_rejects_old_app_under_new_launcher(tmp_path, windows_binaries, child):
    (tmp_path / 'app').mkdir()
    shutil.copy2(windows_binaries / 'launcher.exe', tmp_path / 'ClicknTranslate.exe')
    shutil.copy2(windows_binaries / f'{child}.exe', tmp_path / 'app/ClicknTranslateApp.exe')
    add_runtime(tmp_path, windows_binaries)
    write_manifest(tmp_path, '1.7.1')
    result = subprocess.run([str(windows_binaries / 'verify.exe'), str(windows_binaries / 'updater.exe'), str(tmp_path)],
                            capture_output=True, text=True, timeout=10)
    if child == 'old':
        assert result.returncode == 7
        assert 'ClicknTranslateApp.exe has the wrong version' in result.stdout
    else:
        assert result.returncode == 0, result.stdout


def add_runtime(root, binaries):
    runtime = root / 'app/_internal'
    runtime.mkdir(parents=True, exist_ok=True)
    for name in ['OcrWorker.exe', 'ArgosWorker.exe']:
        shutil.copy2(binaries / 'current.exe', runtime / name)
    shutil.copy2(binaries / 'updater.exe', runtime / 'ClicknTranslateUpdater.exe')
    (runtime / 'base_library.zip').write_bytes(b'new standard library')
    (runtime / 'provider.dll').write_bytes(b'new provider runtime')
    (runtime / 'icons').mkdir()
    (runtime / 'icons/theme.dat').write_bytes(b'new icons')


@pytest.mark.parametrize('mode', ['zip', 'setup'])
@pytest.mark.parametrize('damage', [None, 'app/_internal/provider.dll', 'app/_internal/OcrWorker.exe', 'locked_backup'])
def test_real_updater_replaces_all_files_or_restores_all_old_files(tmp_path, windows_binaries, damage, mode):
    new = tmp_path / 'new'
    new.mkdir()
    shutil.copy2(windows_binaries / 'launcher.exe', new / 'ClicknTranslate.exe')
    add_runtime(new, windows_binaries)
    shutil.copy2(windows_binaries / 'updatable.exe', new / 'app/ClicknTranslateApp.exe')
    write_manifest(new, '1.7.1')
    if damage and damage != 'locked_backup':
        (new / damage).unlink()
    # Even a misplaced data folder in an archive may not overwrite user data.
    (new / 'data').mkdir()
    (new / 'data/config.json').write_bytes(b'package default settings')
    archive = tmp_path / 'update.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        for file in new.rglob('*'):
            if file.is_file():
                output.write(file, 'ClicknTranslate/' + file.relative_to(new).as_posix())
    if mode == 'setup':
        compiler = Path(os.environ['LOCALAPPDATA']) / 'Programs/Inno Setup 6/ISCC.exe'
        if not compiler.exists():
            pytest.skip('Inno Setup is unavailable')
        compilation = subprocess.run([str(compiler), '/DMyAppVersion=1.7.1', f'/DSourceDir={new}',
            f'/DReleaseDir={tmp_path}', '/DMyAppId={{' + str(uuid.uuid4()).upper() + '}',
            str(ROOT / 'installer/ClicknTranslate.iss')], capture_output=True, timeout=45)
        assert compilation.returncode == 0, compilation.stdout
        archive = tmp_path / 'ClicknTranslate-Setup-v1.7.1-win64.exe'
    install = tmp_path / 'installed'
    install.mkdir()
    old = {'ClicknTranslate.exe': (windows_binaries / 'old.exe').read_bytes(),
           'app/_internal/OcrWorker.exe': (windows_binaries / 'updatable.exe').read_bytes(),
           'app/_internal/ArgosWorker.exe': b'old Argos',
           'app/_internal/base_library.zip': b'old Python', 'app/_internal/provider.dll': b'old provider',
           'app/obsolete.py': b'old module', 'legacy.py': b'old root module'}
    if damage == 'locked_backup':
        old['zz-locked.dll'] = b'locked original module'
    user = {'data/config.json': b'my settings', 'data/history.json': b'my history',
            'ocr/model.bin': b'my OCR model', 'translators/model.bin': b'my translator'}
    for relative, content in dict(old, **user).items():
        path = install / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    encoded = lambda value: base64.b64encode(str(value).encode('utf-8')).decode('ascii')
    lock = (install / 'zz-locked.dll').open('rb') if damage == 'locked_backup' else None
    old_worker = subprocess.Popen([str(install / 'app/_internal/OcrWorker.exe')],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        log = tmp_path / 'apply.log'
        # The application inherits stdout. A pipe would stay open while that
        # healthy app runs, making communicate() wait after the updater exits.
        with log.open('w') as output:
            result = subprocess.run([str(windows_binaries / 'apply.exe'), str(windows_binaries / 'updater.exe'),
                '--mode', mode, '--app-dir', encoded(install), '--package', encoded(archive),
                '--exe', encoded('ClicknTranslate.exe'), '--version', '1.7.1', '--pid', '2147483000'],
                stdout=output, stderr=subprocess.STDOUT, timeout=75, creationflags=subprocess.CREATE_NO_WINDOW)
        details = log.read_text(encoding='utf-8', errors='replace')
        if damage:
            assert result.returncode == 7, details
            for relative, content in old.items():
                assert (install / relative).read_bytes() == content
        else:
            assert result.returncode == 0, details
            assert verify_manifest(install, '1.7.1') == 8
            assert not (install / 'app/obsolete.py').exists()
            assert not (install / 'legacy.py').exists()
        for relative, content in user.items():
            assert (install / relative).read_bytes() == content
        assert old_worker.poll() is not None, 'The old OCR process still holds the previous modules'
        assert not (install / 'data/.update-in-progress').exists()
        assert not list(tmp_path.glob('.clickntranslate_backup_*'))
    finally:
        if lock:
            lock.close()
        prefix = os.path.normcase(str(install.resolve()) + os.sep)
        for process in psutil.process_iter(['exe']):
            if process.info['exe'] and os.path.normcase(process.info['exe']).startswith(prefix):
                process.kill()
                process.wait(5)
        uninstaller = install / 'unins000.exe'
        if mode == 'setup' and uninstaller.exists():
            subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'],
                           timeout=30, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
