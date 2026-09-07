"""Focused checks for the managed Mac installer and its failure behavior."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

import macos_tesseract as installer
import platform_support


@pytest.fixture
def mac(monkeypatch):
    monkeypatch.setattr(platform_support, 'IS_MAC', True)
    monkeypatch.setattr(platform_support, 'IS_LINUX', False)
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', False)
    monkeypatch.setattr(installer.platform, 'machine', lambda: 'arm64')


def test_failed_install_preserves_existing_runtime_and_models(mac, tmp_path, monkeypatch):
    old = tmp_path / ('runtime-' + 'a' * 32)
    (old / 'bin').mkdir(parents=True)
    executable = old / 'bin/tesseract'
    executable.write_bytes(b'old runtime')
    executable.chmod(0o700)
    model = old / 'custom.traineddata'
    model.write_bytes(b'user model')
    manifest = tmp_path / 'installation.json'
    original = json.dumps({'runtime': old.name})
    manifest.write_text(original)
    payload = b'verified test installer'
    monkeypatch.setitem(installer.MICROMAMBA_SHA256, 'osx-arm64', hashlib.sha256(payload).hexdigest())
    def download(_url, target, **_kwargs):
        Path(target).write_bytes(payload)
    def fail(command, *_args):
        runtime = Path(command[command.index('--prefix') + 1])
        runtime.mkdir()
        (runtime / 'partial').write_bytes(b'incomplete')
        raise RuntimeError('network failure')
    monkeypatch.setattr(installer, '_run_install', fail)
    with pytest.raises(RuntimeError, match='network failure'):
        installer.install(tmp_path, download, lambda: None, lambda *_: None)
    assert manifest.read_text() == original
    assert model.read_bytes() == b'user model'
    assert installer.managed_command(tmp_path) == str(executable)
    assert list(tmp_path.glob('runtime-*')) == [old]


def test_settings_and_ocr_find_same_mac_runtime_without_shell_path(mac, tmp_path, monkeypatch):
    import ocr
    from settings_window import SettingsWindow
    root = tmp_path / 'ocr/tesseract'
    runtime = root / ('runtime-' + 'b' * 32)
    (runtime / 'bin').mkdir(parents=True)
    executable = runtime / 'bin/tesseract'
    executable.write_bytes(b'native executable')
    executable.chmod(0o700)
    (runtime / 'share/tessdata').mkdir(parents=True)
    (root / 'installation.json').write_text(json.dumps({'runtime': runtime.name}))
    monkeypatch.setattr(ocr, 'get_portable_dir', lambda: str(tmp_path))
    monkeypatch.setattr(ocr.ScreenCaptureOverlay, '_tesseract_cmd_cache', None)
    monkeypatch.setattr(platform_support, 'system_tesseract_command', lambda: '')
    owner = SimpleNamespace(_find_local_tesseract_exe=lambda:
                            SettingsWindow._find_tesseract_exe_under(None, str(root)))
    assert SettingsWindow._find_available_tesseract_exe(owner) == str(executable)
    assert ocr.ScreenCaptureOverlay.get_tesseract_cmd() == str(executable)
    assert ocr._tesseract_managed_data_dir(str(executable)) == str(runtime / 'share/tessdata')
    (root / 'installation.json').write_text(json.dumps({'runtime': '../outside'}))
    assert installer.managed_command(root) == ''


def test_mac_install_button_starts_worker_and_failure_keeps_selected_engine(mac, monkeypatch):
    import settings_window as sw
    owner = SimpleNamespace(
        parent=SimpleNamespace(current_interface_language='ru'),
        _tesseract_install_in_progress=False, _rapidocr_install_in_progress=False,
        _easyocr_install_in_progress=False, _hymt_install_in_progress=False,
        _tesseract_cancel_requested=mock.Mock(), ocr_engine_combo=mock.Mock(),
        _set_parent_topmost_for_tesseract_install=mock.Mock(), _show_tesseract_progress=mock.Mock(),
        _install_macos_tesseract_worker=mock.Mock(), _show_linux_tesseract_hint=mock.Mock(),
        _finish_tesseract_install_state=mock.Mock(), _hide_tesseract_progress=mock.Mock(),
        _restore_settings_view=mock.Mock(), save_ocr_engine=mock.Mock(),
    )
    thread = mock.Mock()
    monkeypatch.setattr(sw.threading, 'Thread', thread)
    sw.SettingsWindow.start_tesseract_install(owner)
    thread.assert_called_once_with(target=owner._install_macos_tesseract_worker, daemon=True)
    thread.return_value.start.assert_called_once()
    owner._show_linux_tesseract_hint.assert_not_called()
    warning = mock.Mock()
    monkeypatch.setattr(sw.QMessageBox, 'warning', warning)
    sw.SettingsWindow._on_tesseract_install_failed(owner, 'network failure')
    owner.save_ocr_engine.assert_not_called()
    assert 'network failure' in warning.call_args.args[-1]
