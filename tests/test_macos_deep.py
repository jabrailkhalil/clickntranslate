"""Mac integration failures that can be reproduced without native frameworks."""

import hashlib
import json
from pathlib import Path
import plistlib
from types import SimpleNamespace
from unittest import mock

import pytest

import macos_desktop as desktop
import macos_tesseract as tesseract
import platform_support


@pytest.fixture
def mac(monkeypatch, tmp_path):
    monkeypatch.setattr(platform_support, 'IS_MAC', True)
    monkeypatch.setattr(platform_support, 'IS_LINUX', False)
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', False)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(desktop, 'launch_arguments', lambda: ['/usr/bin/open', '-a', '/Applications/Current.app', '--args', '--autostart'])
    return tmp_path


def synchronize_login():
    import main
    owner = SimpleNamespace(config={'autostart': True}, autostart=True)
    return main.DarkThemeApp.sync_autostart_state(owner, repair_stale=True)


@pytest.mark.parametrize('override', [{'Disabled': True}, {'RunAtLoad': False}])
def test_saved_preference_does_not_reenable_disabled_launchagent(mac, override):
    desktop.set_autostart(True)
    path = desktop.autostart_path()
    entry = plistlib.loads(path.read_bytes())
    entry.update(override)
    path.write_bytes(plistlib.dumps(entry))
    before = path.read_bytes()
    assert synchronize_login() is False
    assert path.read_bytes() == before


def test_moved_bundle_repairs_only_launch_arguments_and_preserves_options(mac):
    desktop.set_autostart(True)
    path = desktop.autostart_path()
    entry = plistlib.loads(path.read_bytes())
    entry['ProgramArguments'] = ['/usr/bin/open', '-a', '/Applications/Old.app']
    entry['ProcessType'] = 'Background'
    entry['EnvironmentVariables'] = {'USER_OPTION': 'preserved'}
    path.write_bytes(plistlib.dumps(entry))
    assert synchronize_login() is True
    repaired = plistlib.loads(path.read_bytes())
    assert repaired['ProgramArguments'] == desktop.launch_arguments()
    assert repaired['EnvironmentVariables'] == entry['EnvironmentVariables']
    assert repaired['ProcessType'] == 'Background'


def test_failed_launchagent_repair_does_not_abort_app_startup(mac, monkeypatch):
    desktop.set_autostart(True)
    path = desktop.autostart_path()
    before = path.read_bytes()
    monkeypatch.setattr(desktop, 'launch_arguments', lambda: ['/new/app'])
    monkeypatch.setattr(desktop.os, 'replace', mock.Mock(side_effect=PermissionError('read-only LaunchAgents')))
    assert synchronize_login() is False
    assert path.read_bytes() == before


@pytest.mark.parametrize('contents', [b'not a plist', b'<?xml version="1.0"?><plist><dict>',
                                     plistlib.dumps(['wrong type']),
                                     plistlib.dumps({'Label': 'another.application', 'RunAtLoad': True})],
                         ids=['malformed', 'truncated-xml', 'wrong-root', 'foreign'])
def test_invalid_or_foreign_launchagent_is_not_overwritten_at_startup(mac, contents):
    path = desktop.autostart_path()
    path.parent.mkdir(parents=True)
    path.write_bytes(contents)
    assert synchronize_login() is False
    assert path.read_bytes() == contents


@pytest.fixture
def managed_install(mac, tmp_path, monkeypatch):
    monkeypatch.setattr(tesseract.platform, 'machine', lambda: 'arm64')
    root = tmp_path / 'ocr/tesseract'
    old = root / ('runtime-' + 'a' * 32)
    (old / 'bin').mkdir(parents=True)
    binary = old / 'bin/tesseract'
    binary.write_bytes(b'old runtime')
    binary.chmod(0o700)
    data = old / 'share/tessdata'
    data.mkdir(parents=True)
    (data / 'eng.traineddata').write_bytes(b'old English')
    (data / 'rus.traineddata').write_bytes(b'user Russian model')
    (data / 'script').mkdir()
    (data / 'script/Latin.traineddata').write_bytes(b'user Latin model')
    (root / 'installation.json').write_text(json.dumps({'runtime': old.name}))
    payload = b'verified fixture installer'
    monkeypatch.setitem(tesseract.MICROMAMBA_SHA256, 'osx-arm64', hashlib.sha256(payload).hexdigest())
    def download(_url, target, **_kwargs):
        Path(target).write_bytes(payload)
    def create(command, *_args):
        runtime = Path(command[command.index('--prefix') + 1])
        (runtime / 'bin').mkdir(parents=True)
        (runtime / 'bin/tesseract').write_bytes(b'new runtime')
        (runtime / 'bin/tesseract').chmod(0o700)
        (runtime / 'share/tessdata').mkdir(parents=True)
        (runtime / 'share/tessdata/eng.traineddata').write_bytes(b'new English')
    monkeypatch.setattr(tesseract, '_run_install', create)
    monkeypatch.setattr(tesseract.subprocess, 'run', lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout='tesseract 5.5.3', stderr=''))
    return root, old, download


def test_successful_tesseract_reinstall_retains_downloaded_languages(managed_install):
    root, old, download = managed_install
    executable = tesseract.install(root, download, lambda: None, lambda *_: None)
    current = Path(executable).parent.parent / 'share/tessdata'
    assert (current / 'rus.traineddata').read_bytes() == b'user Russian model'
    assert (current / 'script/Latin.traineddata').read_bytes() == b'user Latin model'
    assert (current / 'eng.traineddata').read_bytes() == b'new English'
    assert (old / 'share/tessdata/rus.traineddata').read_bytes() == b'user Russian model'
    assert tesseract.managed_command(root) == executable


@pytest.mark.parametrize('failure', ['copy', 'publish'])
def test_tesseract_model_copy_or_publish_failure_keeps_old_install(managed_install, monkeypatch, failure):
    root, old, download = managed_install
    original = (root / 'installation.json').read_bytes()
    error = OSError('storage failure')
    if failure == 'copy':
        monkeypatch.setattr(tesseract.shutil, 'copy2', mock.Mock(side_effect=error))
    else:
        monkeypatch.setattr(tesseract.os, 'replace', mock.Mock(side_effect=error))
    with pytest.raises(OSError, match='storage failure'):
        tesseract.install(root, download, lambda: None, lambda *_: None)
    assert (root / 'installation.json').read_bytes() == original
    assert list(root.glob('runtime-*')) == [old]
    assert not list(root.glob('.installation-*'))


def test_cancelling_while_preserving_models_keeps_old_install(managed_install, monkeypatch):
    root, old, download = managed_install
    before = (root / 'installation.json').read_bytes()
    cancelled = []
    copy = tesseract.shutil.copy2
    def copying(*args, **kwargs):
        result = copy(*args, **kwargs)
        cancelled.append(True)
        return result
    def check():
        if cancelled:
            raise RuntimeError('cancelled by user')
    monkeypatch.setattr(tesseract.shutil, 'copy2', copying)
    with pytest.raises(RuntimeError, match='cancelled by user'):
        tesseract.install(root, download, check, lambda *_: None)
    assert (root / 'installation.json').read_bytes() == before
    assert list(root.glob('runtime-*')) == [old]


@pytest.mark.parametrize('phase', ['terminate', 'kill'])
def test_installer_process_exit_race_preserves_original_cancellation(tmp_path, monkeypatch, phase):
    import subprocess
    process = mock.Mock(pid=1234)
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired('installer', 5), 0] if phase == 'kill' else [0]
    monkeypatch.setattr(tesseract.subprocess, 'Popen', mock.Mock(return_value=process))
    kill = mock.Mock(side_effect=[None, ProcessLookupError()] if phase == 'kill' else ProcessLookupError())
    monkeypatch.setattr(tesseract.os, 'killpg', kill, raising=False)
    monkeypatch.setattr(tesseract.signal, 'SIGKILL', 9, raising=False)
    cancelled = RuntimeError('cancelled by user')
    def check():
        raise cancelled
    with pytest.raises(RuntimeError) as raised:
        tesseract._run_install(['fixture'], {}, tmp_path / 'install.log', check)
    assert raised.value is cancelled
    process.wait.assert_called()


@pytest.mark.parametrize('engine', ['tesseract', 'python'])
def test_bootstrap_checksum_failure_never_executes_download(mac, tmp_path, monkeypatch, engine):
    import macos_python
    module = tesseract if engine == 'tesseract' else macos_python
    monkeypatch.setattr(module.platform, 'machine', lambda: 'arm64')
    execute = mock.Mock()
    monkeypatch.setattr(module, '_run_install', execute)
    def download(_url, target, **_kwargs):
        Path(target).write_bytes(b'wrong executable')
    with pytest.raises(RuntimeError, match='SHA-256'):
        if engine == 'tesseract':
            module.install(tmp_path, download, lambda: None, lambda *_: None)
        else:
            module.prepare_pip_command(tmp_path, 'EasyOCR', download, lambda: None)
    execute.assert_not_called()
