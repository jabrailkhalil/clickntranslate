"""Exercise the real pytesseract entry points used by frozen Linux builds."""

import os
import subprocess
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image

import ocr
import platform_support


@pytest.fixture
def frozen_tesseract(monkeypatch, tmp_path):
    import pytesseract

    module = pytesseract.pytesseract
    # Restore every library object that the app's configuration may replace.
    monkeypatch.setattr(module, "subprocess", module.subprocess)
    monkeypatch.setattr(module, "subprocess_args", module.subprocess_args)
    monkeypatch.setattr(module, "tesseract_cmd", "/usr/bin/tesseract")
    monkeypatch.setattr(module.get_tesseract_version, "_result", module.get_tesseract_version)
    appdir = str(tmp_path / "runtime.AppDir")
    private_libraries = os.path.join(appdir, "usr", "bin", "_internal")
    user_libraries = str(tmp_path / "user-libraries")
    inherited = os.pathsep.join((private_libraries, user_libraries))
    monkeypatch.setenv("APPDIR", appdir)
    monkeypatch.setenv("LD_LIBRARY_PATH", inherited)
    monkeypatch.setenv("DISPLAY", ":77")
    monkeypatch.setattr(platform_support, "IS_LINUX", True)
    monkeypatch.setattr(platform_support, "IS_WINDOWS", False)
    monkeypatch.setattr(platform_support, "IS_MAC", False)
    return pytesseract, user_libraries, inherited


@pytest.mark.parametrize("entry_point", ["version", "fullscreen", "paragraphs"])
def test_real_pytesseract_version_probe_uses_system_environment(
    frozen_tesseract, monkeypatch, entry_point,
):
    pytesseract, user_libraries, inherited = frozen_tesseract
    module = pytesseract.pytesseract
    seen = []

    def version_output(_command, **kwargs):
        seen.append(dict(kwargs["env"]))
        return b"tesseract 5.3.4\n"

    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t10\t20\t30\t15\t95\tHello\n"
    )
    monkeypatch.setattr(subprocess, "check_output", version_output)
    monkeypatch.setattr(module, "run_and_get_output", lambda *_args, **_kwargs: tsv)
    monkeypatch.setattr(ocr, "_configure_installed_tesseract_data", lambda *_args: "tessdata")
    monkeypatch.setattr(ocr.ScreenCaptureOverlay, "get_tesseract_cmd", lambda: "/usr/bin/tesseract")
    image = Image.new("RGB", (400, 200), "white")
    if entry_point == "version":
        ocr._configure_pytesseract_system_environment(pytesseract)
        assert str(module.get_tesseract_version(cached=True)) == "5.3.4"
        assert str(module.get_tesseract_version(cached=True)) == "5.3.4"
    elif entry_point == "fullscreen":
        assert ocr._recognize_image_layout(image, "tesseract", "en") == [(10, 20, 30, 15, "Hello")]
    else:
        assert "Hello" in ocr._run_tesseract_ocr_image_with_cmd(
            image, "/usr/bin/tesseract", "eng", "qa", "qa", join_paragraphs=True,
        )

    assert len(seen) == 1  # The library's cached version probe retains its semantics.
    assert seen[0].get("LD_LIBRARY_PATH") == user_libraries
    assert seen[0]["DISPLAY"] == ":77"
    assert os.environ["LD_LIBRARY_PATH"] == inherited


def test_real_pytesseract_language_probe_uses_system_environment(frozen_tesseract, monkeypatch):
    pytesseract, user_libraries, inherited = frozen_tesseract
    module = pytesseract.pytesseract
    monkeypatch.setattr(module.get_languages, "_result", module.get_languages)
    seen = []

    def languages_output(command, **kwargs):
        seen.append(dict(kwargs.get("env", os.environ)))
        output = module.linesep.join(("List of available languages (1):", "eng", ""))
        return subprocess.CompletedProcess(command, 0, output.encode("utf-8"))

    monkeypatch.setattr(subprocess, "run", languages_output)
    ocr._configure_pytesseract_system_environment(pytesseract)
    assert module.get_languages() == ["eng"]
    assert seen[0].get("LD_LIBRARY_PATH") == user_libraries
    assert os.environ["LD_LIBRARY_PATH"] == inherited


def test_pytesseract_environment_adapter_is_local_and_idempotent(frozen_tesseract):
    pytesseract, user_libraries, inherited = frozen_tesseract
    module = pytesseract.pytesseract
    original_run = subprocess.run
    original_check_output = subprocess.check_output
    original_popen = subprocess.Popen
    ocr._configure_pytesseract_system_environment(pytesseract)
    configured = module.subprocess
    ocr._configure_pytesseract_system_environment(pytesseract)
    assert module.subprocess is configured
    assert subprocess.run is original_run
    assert subprocess.check_output is original_check_output
    assert subprocess.Popen is original_popen
    assert module.subprocess.PIPE == subprocess.PIPE
    assert module.subprocess.TimeoutExpired is subprocess.TimeoutExpired
    assert module.subprocess_args()["env"]["LD_LIBRARY_PATH"] == user_libraries
    assert os.environ["LD_LIBRARY_PATH"] == inherited


def test_real_pytesseract_ocr_child_reads_current_environment(frozen_tesseract, monkeypatch):
    pytesseract, user_libraries, inherited = frozen_tesseract
    seen = []

    def recognize(command, **kwargs):
        seen.append(dict(kwargs["env"]))
        Path(command[2] + ".txt").write_text("Recognized text", encoding="utf-8")
        return SimpleNamespace(
            communicate=lambda **_kwargs: (b"", b""), returncode=0,
            stdin=BytesIO(), stdout=BytesIO(), stderr=BytesIO(),
        )

    monkeypatch.setattr(subprocess, "Popen", recognize)
    ocr._configure_pytesseract_system_environment(pytesseract)
    image = Image.new("RGB", (400, 200), "white")
    assert pytesseract.image_to_string(image, lang="eng") == "Recognized text"
    updated_libraries = user_libraries + "-updated"
    monkeypatch.setenv("LD_LIBRARY_PATH", inherited + os.pathsep + updated_libraries)
    assert pytesseract.image_to_string(image, lang="eng") == "Recognized text"
    assert [env["LD_LIBRARY_PATH"] for env in seen] == [
        user_libraries, os.pathsep.join((user_libraries, updated_libraries)),
    ]


def test_real_pytesseract_version_failure_can_be_retried(frozen_tesseract, monkeypatch):
    pytesseract, user_libraries, _inherited = frozen_tesseract
    module = pytesseract.pytesseract
    failure = subprocess.CalledProcessError(1, ["tesseract", "--version"])
    calls = []

    def version_output(_command, **kwargs):
        calls.append(dict(kwargs["env"]))
        if len(calls) == 1:
            raise failure
        return b"tesseract 5.3.4\n"

    monkeypatch.setattr(subprocess, "check_output", version_output)
    ocr._configure_pytesseract_system_environment(pytesseract)
    with pytest.raises(subprocess.CalledProcessError) as result:
        module.get_tesseract_version(cached=True)
    assert result.value is failure
    assert str(module.get_tesseract_version(cached=True)) == "5.3.4"
    assert str(module.get_tesseract_version(cached=False)) == "5.3.4"
    assert len(calls) == 3
    assert all(env["LD_LIBRARY_PATH"] == user_libraries for env in calls)
