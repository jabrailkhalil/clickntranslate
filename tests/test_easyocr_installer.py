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


def test_engine_installer_falls_back_when_matching_python_is_missing():
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
