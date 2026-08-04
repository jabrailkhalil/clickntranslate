"""End-to-end update checks for Click'n'Translate 1.5.2 -> 1.5.3.

The test uses only disposable directories and a disposable Inno AppId.  It
exercises both the portable ZIP updater script and an installed-copy update.
"""

from __future__ import annotations

import atexit
import base64
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

import psutil


ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = (ROOT / "build").resolve()
OLD_STAGE = ROOT / "releases" / "ClicknTranslate-v1.5.2-win64-stage" / "ClicknTranslate"
NEW_STAGE = ROOT / "releases" / "ClicknTranslate-v1.5.3-win64-stage" / "ClicknTranslate"
NEW_ZIP = ROOT / "releases" / "Click-n-Translate-1.5.3-windows-portable-x64.zip"
UPDATER = NEW_STAGE / "app" / "_internal" / "ClicknTranslateUpdater.exe"
ISS = ROOT / "installer" / "ClicknTranslate.iss"
ISCC = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_remove_tree(path: Path) -> None:
    resolved = path.resolve()
    if BUILD_ROOT not in resolved.parents:
        raise RuntimeError(f"Refusing to remove a path outside build: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def file_version(path: Path) -> str:
    escaped = str(path).replace("'", "''")
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            f"(Get-Item -LiteralPath '{escaped}').VersionInfo.FileVersion",
        ],
        check=True,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return result.stdout.strip()


def processes_from_install(install: Path) -> list[psutil.Process]:
    prefix = os.path.normcase(str(install.resolve()) + os.sep)
    matches = []
    for process in psutil.process_iter(["pid", "exe"]):
        try:
            executable = process.info.get("exe") or ""
            if os.path.normcase(executable).startswith(prefix):
                matches.append(process)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    return matches


def stop_install_processes(install: Path) -> None:
    matches = processes_from_install(install)
    for process in matches:
        try:
            process.terminate()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    _gone, alive = psutil.wait_procs(matches, timeout=10)
    for process in alive:
        try:
            process.kill()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass


def terminate_process_tree(process_id: int) -> None:
    subprocess.run(
        ["taskkill.exe", "/PID", str(process_id), "/T", "/F"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def write_user_markers(install: Path) -> None:
    for folder in ("data", "ocr", "translators"):
        target = install / folder
        target.mkdir(exist_ok=True)
        (target / "update-e2e-marker.txt").write_text(folder, encoding="utf-8")


def assert_user_markers(install: Path) -> None:
    for folder in ("data", "ocr", "translators"):
        marker = install / folder / "update-e2e-marker.txt"
        if marker.read_text(encoding="utf-8") != folder:
            raise RuntimeError(f"User data was not preserved: {marker}")


def assert_new_payload(install: Path) -> None:
    checks = (
        "ClicknTranslate.exe",
        "app/ClicknTranslateApp.exe",
        "app/_internal/ArgosWorker.exe",
        "app/_internal/OcrWorker.exe",
        "app/_internal/base_library.zip",
    )
    for relative in checks:
        actual = install / relative
        expected = NEW_STAGE / relative
        if not actual.is_file() or sha256(actual) != sha256(expected):
            raise RuntimeError(f"Installed file differs from the 1.5.3 stage: {relative}")
    if not file_version(install / "ClicknTranslate.exe").startswith("1.5.3."):
        raise RuntimeError("Updated launcher does not report version 1.5.3")


def encoded(value: str | Path) -> str:
    return base64.b64encode(str(value).encode("utf-8")).decode("ascii")


def run_update_helper(mode: str, install: Path, package: Path) -> None:
    runner_dir = install.parent / ("runner-" + mode)
    runner_dir.mkdir(exist_ok=True)
    runner = runner_dir / "ClicknTranslateUpdater.exe"
    shutil.copy2(UPDATER, runner)
    result = subprocess.run(
        [
            str(runner),
            "--mode", mode,
            "--app-dir", encoded(install),
            "--package", encoded(package),
            "--exe", encoded("ClicknTranslate.exe"),
            "--version", "1.5.3",
            "--pid", "2147483000",
        ],
        cwd=tempfile.gettempdir(),
        timeout=240,
    )
    if result.returncode != 0:
        log_path = Path(tempfile.gettempdir()) / "clickntranslate_update.log"
        log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        raise RuntimeError(f"Update helper failed with {result.returncode}: {log[-5000:]}")


def run_portable_update(test_root: Path) -> None:
    install = test_root / "portable-install"
    update_zip = test_root / NEW_ZIP.name
    shutil.copytree(OLD_STAGE, install)
    shutil.copy2(NEW_ZIP, update_zip)
    write_user_markers(install)

    worker = install / "app" / "_internal" / "OcrWorker.exe"
    shutil.copy2(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "cmd.exe", worker)
    blocker = subprocess.Popen(
        [str(worker), "/d", "/c", "ping.exe -n 240 127.0.0.1 >nul"],
        cwd=install,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    atexit.register(terminate_process_tree, blocker.pid)

    run_update_helper("zip", install, update_zip)

    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            assert_new_payload(install)
            if processes_from_install(install):
                break
        except (OSError, RuntimeError, subprocess.SubprocessError):
            pass
        time.sleep(0.5)
    else:
        raise RuntimeError("Portable updater did not install and start 1.5.3")

    assert_user_markers(install)
    if blocker.poll() is None:
        raise RuntimeError("Portable updater left the locked OCR worker running")
    atexit.unregister(terminate_process_tree)
    stop_install_processes(install)
    print("PORTABLE_UPDATE_152_TO_153=OK")


def compile_test_setup(version: str, source: Path, output: Path, app_id: str) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            str(ISCC),
            f"/DMyAppVersion={version}",
            f"/DSourceDir={source}",
            f"/DReleaseDir={output}",
            f"/DMyAppId={{{{{app_id}}}",
            str(ISS),
        ],
        capture_output=True,
        text=True,
        timeout=240,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Test setup compilation failed: {result.stdout!r} {result.stderr!r}")
    setup = output / f"ClicknTranslate-Setup-v{version}-win64.exe"
    if not setup.is_file():
        raise FileNotFoundError(setup)
    return setup


def run_setup(setup: Path, install: Path, update: bool = False) -> None:
    arguments = [
        str(setup),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        f"/DIR={install}",
    ]
    if update:
        arguments.extend(
            [
                "/CLOSEAPPLICATIONS",
                "/FORCECLOSEAPPLICATIONS",
                "/NORESTARTAPPLICATIONS",
                "/LOGCLOSEAPPLICATIONS",
            ]
        )
    result = subprocess.run(arguments, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"Setup exited with code {result.returncode}: {setup}")


def uninstall_test_copy(install: Path) -> None:
    uninstaller = install / "unins000.exe"
    if uninstaller.is_file():
        subprocess.run(
            [str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            check=True,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def run_installed_update(test_root: Path) -> None:
    install = test_root / "installed-copy"
    setup_root = test_root / "setups"
    app_id = str(uuid.uuid4()).upper()
    old_setup = compile_test_setup("1.5.2", OLD_STAGE, setup_root / "old", app_id)
    new_setup = compile_test_setup("1.5.3", NEW_STAGE, setup_root / "new", app_id)
    try:
        run_setup(old_setup, install)
        write_user_markers(install)
        subprocess.Popen([str(install / "ClicknTranslate.exe")], cwd=install)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not processes_from_install(install):
            time.sleep(0.25)
        if not processes_from_install(install):
            raise RuntimeError("Disposable installed 1.5.2 copy did not start")

        update_package = test_root / "new-test-setup.exe"
        shutil.copy2(new_setup, update_package)
        run_update_helper("setup", install, update_package)
        assert_new_payload(install)
        assert_user_markers(install)
        subprocess.Popen([str(install / "ClicknTranslate.exe")], cwd=install)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not processes_from_install(install):
            time.sleep(0.25)
        if not processes_from_install(install):
            raise RuntimeError("Updated installed 1.5.3 copy did not start")
        print("INSTALLED_UPDATE_152_TO_153=OK")
    finally:
        stop_install_processes(install)
        uninstall_test_copy(install)


def main() -> int:
    if not OLD_STAGE.is_dir() or not NEW_STAGE.is_dir() or not NEW_ZIP.is_file() or not UPDATER.is_file():
        raise RuntimeError("The 1.5.2 and 1.5.3 release artifacts are required")
    if not ISCC.is_file():
        raise FileNotFoundError(ISCC)
    test_root = BUILD_ROOT / "update-e2e-152-to-153"
    safe_remove_tree(test_root)
    test_root.mkdir(parents=True)
    run_portable_update(test_root)
    run_installed_update(test_root)
    print("USER_DATA_PRESERVED=YES")
    print("LOCKED_OCR_WORKER_STOPPED=YES")
    print("APPLICATION_RESTARTED=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
