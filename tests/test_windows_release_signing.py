"""Exercise release gates without creating certificates or changing trust stores."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_version import APP_VERSION
from tools.windows_version_info import make_version_info

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows signing and PE resources")
POWERSHELL = shutil.which("powershell.exe")
SIGN_SCRIPT = ROOT / "tools/sign_windows.ps1"
PROJECT_EXES = (
    "ClicknTranslate.exe", "app/ClicknTranslateApp.exe",
    "app/_internal/ArgosWorker.exe", "app/_internal/OcrWorker.exe",
    "app/_internal/ClicknTranslateUpdater.exe",
)


def run_script(script, *args):
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(script), *map(str, args)],
        capture_output=True, text=True, timeout=90,
    )


@pytest.fixture(scope="module")
def executable(tmp_path_factory):
    path = tmp_path_factory.mktemp("signing gates") / "Launcher.exe"
    result = run_script(ROOT / "tools/build_launcher.ps1", "-OutputPath", path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert path.exists()
    return path


@pytest.fixture
def package(tmp_path, executable):
    root = tmp_path / "ClicknTranslate"
    for relative in PROJECT_EXES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(executable, path)
    (root / "app/_internal/upstream.dll").write_bytes(b"do not sign upstream binaries")
    return root


def test_signed_stage_requires_a_certificate_before_building():
    result = run_script(ROOT / "tools/stage_release.ps1", "-RequireSignature", "-SkipPyInstaller")
    assert result.returncode != 0
    assert "A signing certificate is required" in result.stderr


def test_audit_identifies_unsigned_exes_and_preserves_every_file(package, tmp_path):
    before = {path: path.read_bytes() for path in package.rglob("*") if path.is_file()}
    report = tmp_path / "signatures.json"
    result = run_script(SIGN_SCRIPT, "-Mode", "Audit", "-PackageRoot", package, "-ReportPath", report)
    assert result.returncode == 0, result.stdout + result.stderr
    rows = json.loads(report.read_text(encoding="utf-8"))
    assert {row["File"].replace("\\", "/") for row in rows} == set(PROJECT_EXES)
    for row in rows:
        assert row["Signature"] == "NotSigned"
        assert not row["Timestamped"]
        path = package / row["File"]
        assert row["SHA256"] == hashlib.sha256(before[path]).hexdigest()
    assert all(path.read_bytes() == content for path, content in before.items())


def test_missing_worker_cannot_produce_a_complete_audit(package, tmp_path):
    (package / "app/_internal/OcrWorker.exe").unlink()
    report = tmp_path / "signatures.json"
    result = run_script(SIGN_SCRIPT, "-Mode", "Audit", "-PackageRoot", package, "-ReportPath", report)
    assert result.returncode != 0
    assert "Required executable is missing" in result.stderr
    assert not report.exists()


def test_report_cannot_overwrite_an_executable(executable):
    original = executable.read_bytes()
    result = run_script(SIGN_SCRIPT, "-Mode", "Audit", "-FilePath", executable, "-ReportPath", executable)
    assert result.returncode != 0
    assert "ReportPath cannot overwrite" in result.stderr
    assert executable.read_bytes() == original


def test_signtool_rejects_an_actual_unsigned_executable(executable):
    result = run_script(SIGN_SCRIPT, "-Mode", "Verify", "-FilePath", executable)
    if "SignTool.exe was not found" in result.stderr:
        pytest.skip("Windows SDK is not installed on this runner")
    assert result.returncode != 0
    assert "Signature verification failed" in result.stderr


def test_inno_calls_the_signing_gate_and_cannot_complete_without_a_certificate(package, tmp_path):
    compiler = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Inno Setup 6/ISCC.exe"
    if not compiler.exists():
        pytest.skip("Inno Setup is not installed on this runner")
    # A small disposable package exercises the actual installer/uninstaller
    # signing hook without building or installing the full application.
    command = f'$q{POWERSHELL}$q -NoProfile -NonInteractive -File $q{SIGN_SCRIPT}$q -FilePath $f'
    result = subprocess.run([
        str(compiler), f"/DSourceDir={package}", f"/DReleaseDir={tmp_path / 'output'}",
        "/DSignRelease=1", "/Fsigning-gate-test", f"/Scntsign={command}",
        str(ROOT / "installer/ClicknTranslate.iss"),
    ], capture_output=True, text=True, timeout=90)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "A trusted code-signing certificate is required" in output
    assert "Running Sign Tool cntsign" in output


@pytest.mark.parametrize("missing_timestamp,wrong_signer", [(True, False), (False, True)])
def test_verification_checks_timestamp_and_certificate_even_after_tool_success(
    executable, tmp_path, missing_timestamp, wrong_signer
):
    # Simulate SignTool success to exercise the independent verification gate.
    # No test certificate is installed and no real file is signed.
    fake_tool = tmp_path / "fake-signtool.cmd"
    fake_tool.write_text("@echo off\nexit /b 0\n", encoding="ascii")
    wrapper = tmp_path / "verify.ps1"
    quote = lambda path: "'" + str(path).replace("'", "''") + "'"
    timestamp = "$null" if missing_timestamp else "[pscustomobject]@{Subject='Timestamp'}"
    signer = "B" * 40 if wrong_signer else "A" * 40
    wrapper.write_text(
        "function Get-AuthenticodeSignature { param($LiteralPath)\n"
        "[pscustomobject]@{ Status='Valid'; "
        f"SignerCertificate=[pscustomobject]@{{Subject='Publisher';Thumbprint='{signer}'}}; "
        f"TimeStamperCertificate={timestamp} }} }}\n"
        f"& {quote(SIGN_SCRIPT)} -Mode Verify -FilePath {quote(executable)} "
        f"-SignToolPath {quote(fake_tool)} -CertificateThumbprint {'A' * 40}\n",
        encoding="utf-8",
    )
    result = run_script(wrapper)
    assert result.returncode != 0
    expected = "trusted, timestamped signature" if missing_timestamp else "different certificate"
    assert expected in result.stderr


@pytest.mark.parametrize("name", ("ClicknTranslateApp.exe", "ArgosWorker.exe", "OcrWorker.exe"))
def test_windows_version_resources_roundtrip_through_real_pe(executable, tmp_path, name):
    versioninfo = pytest.importorskip("PyInstaller.utils.win32.versioninfo")
    path = tmp_path / name
    shutil.copyfile(executable, path)
    versioninfo.write_version_info_to_executable(str(path), make_version_info(APP_VERSION, name, "Translation"))
    result = versioninfo.read_version_info_from_executable(str(path))
    fields = {item.name: item.val for item in result.kids[0].kids[0].kids}
    assert fields["CompanyName"] == "Jabrail Digital"
    assert fields["ProductName"] == "Click'n'Translate"
    assert fields["FileVersion"] == APP_VERSION + ".0"
    assert fields["ProductVersion"] == APP_VERSION
    assert fields["OriginalFilename"] == name


@pytest.mark.parametrize("version", ("bad", "1.7", "1.7.1.2.3", "65536.1.0"))
def test_invalid_windows_versions_cannot_be_embedded(version):
    pytest.importorskip("PyInstaller.utils.win32.versioninfo")
    with pytest.raises(ValueError):
        make_version_info(version, "App.exe", "Translation")
