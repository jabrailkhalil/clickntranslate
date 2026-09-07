import io
import os
import tarfile
from types import SimpleNamespace
from unittest import mock

import pytest

import macos_hymt
import platform_support
import settings_window as sw


@pytest.mark.parametrize('arch,suffix', [('arm64', 'arm64'), ('x86_64', 'x64')])
def test_mac_hymt_plan_selects_verified_native_runtime(monkeypatch, arch, suffix):
    monkeypatch.setattr(platform_support, 'IS_MAC', True)
    monkeypatch.setattr(macos_hymt.platform, 'mac_ver', lambda: ('14.3', (), ''))
    monkeypatch.setattr(macos_hymt.platform, 'machine', lambda: arch)
    plan = sw.SettingsWindow._get_hymt_download_plan(object(), is_x64=arch == 'x86_64')
    assert plan['runtime']['name'] == f'llama-b9048-bin-macos-{suffix}.tar.gz'
    assert plan['runtime']['sha256'] == macos_hymt.RUNTIME_SHA256[arch]
    assert plan['model']['sha256'] == sw.HYMT_MODEL_SHA256


def test_mac_hymt_checks_os_before_downloading(monkeypatch):
    monkeypatch.setattr(macos_hymt.platform, 'mac_ver', lambda: ('13.4', (), ''))
    with pytest.raises(RuntimeError, match='macOS 14 or newer'):
        macos_hymt.runtime_plan()


def test_mac_runtime_archive_preserves_executable_and_local_library_link(tmp_path):
    path = tmp_path / 'runtime.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        for name, payload, mode in [('bin/llama-cli', b'executable', 0o755),
                                    ('lib/libggml.0.dylib', b'library', 0o644)]:
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(payload), mode
            archive.addfile(entry, io.BytesIO(payload))
        entry = tarfile.TarInfo('lib/libggml.dylib')
        entry.type, entry.linkname = tarfile.SYMTYPE, 'libggml.0.dylib'
        archive.addfile(entry)
    macos_hymt.extract_runtime(path, tmp_path / 'unpacked')
    assert os.access(tmp_path / 'unpacked/bin/llama-cli', os.X_OK)
    assert (tmp_path / 'unpacked/lib/libggml.dylib').read_bytes() == b'library'


@pytest.mark.parametrize('link', [False, True])
def test_mac_runtime_archive_rejects_escaping_paths(tmp_path, link):
    path = tmp_path / 'runtime.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        entry = tarfile.TarInfo('escape' if link else '../escape')
        if link:
            entry.type, entry.linkname = tarfile.SYMTYPE, '../escape'
        archive.addfile(entry)
    with pytest.raises(tarfile.FilterError):
        macos_hymt.extract_runtime(path, tmp_path / 'unpacked')
    assert not (tmp_path / 'escape').exists()


def test_mac_hymt_failure_keeps_selected_translator(monkeypatch):
    monkeypatch.setattr(platform_support, 'IS_MAC', True)
    owner = SimpleNamespace(parent=SimpleNamespace(current_interface_language='ru'),
        _finish_hymt_install_state=mock.Mock(), _hide_hymt_progress=mock.Mock(),
        _restore_settings_view=mock.Mock(), auto_save_setting=mock.Mock())
    warning = mock.Mock()
    monkeypatch.setattr(sw.QMessageBox, 'warning', warning)
    sw.SettingsWindow._on_hymt_install_failed(owner, 'checksum mismatch')
    owner.auto_save_setting.assert_not_called()
    assert 'checksum mismatch' in warning.call_args.args[-1]
