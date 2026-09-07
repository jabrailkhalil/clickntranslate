import os
import sys
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
import pytest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import platform_support  # noqa: E402
import settings_window as sw  # noqa: E402


def test_easyocr_install_is_pinned_to_cpu_packages():
    assert "easyocr==1.7.2" in sw.EASYOCR_PIP_PACKAGES
    assert "torch==2.12.1+cpu" in sw.EASYOCR_PIP_PACKAGES
    assert "torchvision==0.27.1+cpu" in sw.EASYOCR_PIP_PACKAGES
    assert sw.EASYOCR_EXTRA_INDEX_URL == "https://download.pytorch.org/whl/cpu"


@pytest.mark.skipif(
    not platform_support.IS_WINDOWS, reason="the embedded Python bootstrap is Windows-only"
)
def test_portable_bootstrap_plan_uses_verified_official_downloads():
    plan = sw.SettingsWindow._portable_pip_bootstrap_plan(SimpleNamespace(), is_x64=True)

    assert plan["python"]["url"].startswith("https://www.python.org/ftp/python/")
    assert plan["python"]["name"].endswith("-embed-amd64.zip")
    assert len(plan["python"]["sha256"]) == 64
    assert plan["pip"]["url"].startswith("https://files.pythonhosted.org/")
    assert plan["pip"]["name"].endswith(".whl")
    assert len(plan["pip"]["sha256"]) == 64


def test_portable_bootstrap_produces_pip_command_without_system_python():
    with tempfile.TemporaryDirectory(prefix="easyocr_bootstrap_test_") as temp_dir:
        downloads = []
        progress = []

        def fake_download(url, destination, **kwargs):
            downloads.append(url)
            if destination.endswith(".zip"):
                with zipfile.ZipFile(destination, "w") as archive:
                    archive.writestr("python.exe", b"test")
            else:
                Path(destination).write_bytes(b"wheel")
            callback = kwargs.get("progress_callback")
            if callback:
                callback(10, 10)

        dummy = SimpleNamespace(
            _portable_pip_bootstrap_plan=lambda is_x64: {
                "python": {"name": "python.zip", "url": "https://python.test/python.zip", "sha256": "a" * 64},
                "pip": {"name": "pip.whl", "url": "https://pypi.test/pip.whl", "sha256": "b" * 64},
            },
            _download_file=fake_download,
            _verify_file_sha256=lambda *_args: None,
            _python_command_version=lambda _command: f"{sys.version_info.major}.{sys.version_info.minor}",
        )

        with mock.patch.object(sw.platform, "machine", return_value="AMD64"):
            command = sw.SettingsWindow._prepare_portable_pip_command(
                dummy,
                temp_dir,
                "EasyOCR",
                cancel_callback=lambda: False,
                progress_callback=lambda percent, determinate: progress.append((percent, determinate)),
            )

        assert len(downloads) == 2
        assert os.path.isfile(command[0])
        assert command[1].endswith(os.path.join("pip.whl", "pip"))
        assert progress[-1] == (11, True)


def test_engine_installer_falls_back_when_matching_python_is_missing(monkeypatch):
    monkeypatch.setattr(platform_support, "IS_WINDOWS", True)
    monkeypatch.setattr(platform_support, "IS_MAC", False)
    monkeypatch.setattr(platform_support, "IS_LINUX", False)
    portable_command = [r"C:\Temp\python.exe", r"C:\Temp\pip.whl\pip"]
    dummy = SimpleNamespace(
        _find_rapidocr_install_python_command=mock.Mock(side_effect=RuntimeError("missing")),
        _prepare_portable_pip_command=mock.Mock(return_value=portable_command),
    )

    result = sw.SettingsWindow._prepare_engine_pip_command(
        dummy,
        r"C:\Temp\work",
        "EasyOCR",
        r"C:\App\ocr\easyocr",
        cancel_callback=lambda: False,
        progress_callback=mock.Mock(),
    )

    assert result == portable_command
    dummy._prepare_portable_pip_command.assert_called_once()


def test_engine_installer_prefers_existing_matching_python():
    dummy = SimpleNamespace(
        _find_rapidocr_install_python_command=mock.Mock(return_value=[r"C:\Python312\python.exe"]),
        _prepare_portable_pip_command=mock.Mock(),
    )

    result = sw.SettingsWindow._prepare_engine_pip_command(
        dummy,
        r"C:\Temp\work",
        "EasyOCR",
        r"C:\App\ocr\easyocr",
    )

    assert result == [r"C:\Python312\python.exe", "-m", "pip"]
    dummy._prepare_portable_pip_command.assert_not_called()


def test_mac_installer_prepares_private_python_when_system_python_is_missing(monkeypatch):
    monkeypatch.setattr(platform_support, 'IS_MAC', True)
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', False)
    command = ['/private/temporary/python', '-I', '-m', 'pip']
    owner = SimpleNamespace(
        _find_rapidocr_install_python_command=mock.Mock(side_effect=RuntimeError('missing')),
        _prepare_macos_pip_command=mock.Mock(return_value=command),
        _prepare_portable_pip_command=mock.Mock(),
    )
    cancel, progress = mock.Mock(), mock.Mock()
    result = sw.SettingsWindow._prepare_engine_pip_command(
        owner, '/private/temporary', 'EasyOCR', '/app-data/ocr/easyocr', cancel, progress)
    assert result == command
    owner._prepare_macos_pip_command.assert_called_once_with(
        '/private/temporary', 'EasyOCR', cancel_callback=cancel, progress_callback=progress)
    owner._prepare_portable_pip_command.assert_not_called()


@pytest.mark.parametrize('identity', [
    {'version': '3.11', 'architecture': 'arm64'},
    {'version': f'{sys.version_info.major}.{sys.version_info.minor}', 'architecture': 'x86_64'},
])
def test_mac_bootstrap_rejects_wrong_python_version_or_rosetta(tmp_path, monkeypatch, identity):
    import hashlib
    import json
    import macos_python as bootstrap
    monkeypatch.setattr(platform_support, 'IS_MAC', True)
    monkeypatch.setattr(bootstrap.platform, 'machine', lambda: 'arm64')
    payload = b'verified test micromamba'
    monkeypatch.setitem(bootstrap.MICROMAMBA_SHA256, 'osx-arm64', hashlib.sha256(payload).hexdigest())
    def download(_url, destination, **_kwargs):
        Path(destination).write_bytes(payload)
    execute = mock.Mock()
    monkeypatch.setattr(bootstrap, '_run_install', execute)
    monkeypatch.setattr(bootstrap.subprocess, 'run', mock.Mock(return_value=SimpleNamespace(
        returncode=0, stdout=json.dumps(identity), stderr='')))
    with pytest.raises(RuntimeError, match='does not match'):
        bootstrap.prepare_pip_command(tmp_path, 'EasyOCR', download, lambda: None)
    command = execute.call_args.args[0]
    assert command[command.index('--platform') + 1] == 'osx-arm64'


def test_mac_easyocr_install_error_does_not_select_another_ocr(monkeypatch):
    monkeypatch.setattr(platform_support, 'IS_MAC', True)
    owner = SimpleNamespace(
        parent=SimpleNamespace(current_interface_language='ru'),
        _finish_easyocr_install_state=mock.Mock(), _hide_easyocr_progress=mock.Mock(),
        _restore_settings_view=mock.Mock(), save_ocr_engine=mock.Mock(),
    )
    warning = mock.Mock()
    monkeypatch.setattr(sw.QMessageBox, 'warning', warning)
    sw.SettingsWindow._on_easyocr_install_failed(owner, 'download failed')
    owner.save_ocr_engine.assert_not_called()
    assert 'download failed' in warning.call_args.args[-1]


@pytest.mark.parametrize('code,expected', [('ru', ['ru', 'en']), ('en', ['en']),
                                         ('auto', ['ru', 'en'])])
def test_mac_easyocr_install_prepares_active_language_models(monkeypatch, code, expected):
    import ocr
    available = mock.Mock(return_value=True)
    monkeypatch.setattr(ocr, 'easyocr_available', available)
    owner = SimpleNamespace(parent=SimpleNamespace(current_interface_language='ru',
        config={'last_ocr_language': code}), _check_easyocr_cancel_requested=mock.Mock(),
        _emit_easyocr_progress=mock.Mock())
    sw.SettingsWindow._prepare_easyocr_models(owner)
    assert available.call_args_list == [mock.call(code, download_enabled=True) for code in expected]


def test_native_easyocr_model_error_reaches_installer(monkeypatch):
    import ocr
    monkeypatch.setattr(ocr, '_native_ocr_worker_enabled', lambda: True)
    monkeypatch.setattr(ocr, '_probe_native_ocr_worker', lambda *a, **kw: (False, 'Download checksum mismatch'))
    monkeypatch.setattr(ocr, '_EASY_OCR_IMPORT_ERROR', None)
    owner = SimpleNamespace(parent=SimpleNamespace(current_interface_language='en', config={}),
        _check_easyocr_cancel_requested=mock.Mock(), _emit_easyocr_progress=mock.Mock())
    with pytest.raises(RuntimeError, match='Download checksum mismatch'):
        sw.SettingsWindow._prepare_easyocr_models(owner)
