"""Exercise release-scan failures without changing protection or creating malware."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/scan_windows_release.ps1"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows release scanner")


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def scan(tmp_path, *, exit_code=0, enabled=True, age_days=0, mutate=False,
         report_inside=False, existing_report=False, empty=False, file_target=False):
    package = tmp_path / "package with spaces"
    package.mkdir()
    payload = package / "payload.txt"
    if not empty:
        payload.write_text("release contents", encoding="utf-8")
    report = (package if report_inside else tmp_path) / "result.json"
    if existing_report:
        report.write_text("previous evidence", encoding="utf-8")
    marker = tmp_path / "scanner-called.txt"
    args = tmp_path / "scanner-args.txt"
    fake = tmp_path / "fake-scanner.cmd"
    fake.write_text(
        f'@echo off\necho called>"{marker}"\necho %*>"{args}"\n'
        + (f'echo changed>"{payload}"\n' if mutate else '')
        + f'echo Simulated diagnostic scan\nexit /b {exit_code}\n', encoding="ascii",
    )
    wrapper = tmp_path / "run.ps1"
    wrapper.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "function Get-MpComputerStatus { [pscustomobject]@{\n"
        f"AntivirusEnabled=${str(enabled).lower()}; RealTimeProtectionEnabled=$true;\n"
        "AntivirusSignatureVersion='test';\n"
        f"AntivirusSignatureLastUpdated=(Get-Date).AddDays(-{age_days}) }} }}\n"
        f"& {quote(SCRIPT)} -Path {quote(payload if file_target else package)} -ReportPath {quote(report)} "
        f"-DefenderPath {quote(fake)}\n", encoding="utf-8",
    )
    result = subprocess.run(
        [shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "RemoteSigned", "-File", str(wrapper)],
        capture_output=True, text=True, timeout=30,
    )
    return result, report, payload, marker, args


def test_success_records_the_exact_bytes_and_diagnostic_scan_options(tmp_path):
    import hashlib
    result, report, payload, marker, args = scan(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(report.read_text())
    assert data["Status"] == "NoThreatsFound"
    assert data["ExitCode"] == 0
    assert data["Files"] == [{"File": payload.name, "SHA256": hashlib.sha256(payload.read_bytes()).hexdigest()}]
    assert data["SignatureVersion"] == "test"
    assert marker.exists()
    assert '-Scan -ScanType 3 -File "' in args.read_text()
    assert '-DisableRemediation' in args.read_text()


@pytest.mark.parametrize("exit_code", [2, 5])
def test_detection_or_scanner_error_blocks_release_and_saves_evidence(tmp_path, exit_code):
    result, report, payload, marker, _ = scan(tmp_path, exit_code=exit_code)
    assert result.returncode != 0
    data = json.loads(report.read_text())
    assert data["Status"] == "Failed"
    assert data["ExitCode"] == exit_code
    assert "Simulated diagnostic scan" in data["Output"]
    assert payload.read_text() == "release contents"


@pytest.mark.parametrize("options", [{"enabled": False}, {"age_days": 3}, {"empty": True}])
def test_unavailable_protection_stale_definitions_and_empty_target_fail_closed(tmp_path, options):
    result, report, _, marker, _ = scan(tmp_path, **options)
    assert result.returncode != 0
    assert json.loads(report.read_text())["Status"] == "Failed"
    assert not marker.exists()


def test_files_changed_during_scan_cannot_be_reported_clean(tmp_path):
    result, report, _, _, _ = scan(tmp_path, mutate=True)
    assert result.returncode != 0
    data = json.loads(report.read_text())
    assert data["Status"] == "Failed"
    assert "changed during the scan" in data["Error"]


def test_report_cannot_be_written_into_the_release(tmp_path):
    result, report, _, marker, _ = scan(tmp_path, report_inside=True)
    assert result.returncode != 0
    assert not report.exists()
    assert not marker.exists()


def test_previous_report_is_never_overwritten(tmp_path):
    result, report, _, marker, _ = scan(tmp_path, existing_report=True)
    assert result.returncode != 0
    assert report.read_text() == "previous evidence"
    assert not marker.exists()


def test_single_archive_or_installer_can_be_scanned(tmp_path):
    result, report, payload, _, _ = scan(tmp_path, file_target=True)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(report.read_text())
    assert data["Status"] == "NoThreatsFound"
    assert data["Target"] == str(payload)
    assert len(data["Files"]) == 1
