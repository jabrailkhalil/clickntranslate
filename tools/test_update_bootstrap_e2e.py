"""Exercise the exact v1.5.0 ZIP updater through the installer bootstrap.

This is intentionally not part of the fast pytest suite.  It installs into a
disposable directory and expects the supplied setup to use a disposable AppId.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

import psutil


ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = (ROOT / "build").resolve()
OLD_STAGE = ROOT / "releases" / "ClicknTranslate-v1.5.0-win64-stage" / "ClicknTranslate"
NEW_STAGE = ROOT / "releases" / "ClicknTranslate-v1.5.1-win64-stage" / "ClicknTranslate"
TEST_UNINSTALL_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    r"\{8E2481C0-EC65-47A7-9151-51E2E1510001}_is1"
)


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


def extract_v150_updater_script(destination: Path) -> None:
    result = subprocess.run(
        ["git", "show", "v1.5.0:settings_window.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    function_start = result.stdout.index("    def _launch_zip_updater")
    function_end = result.stdout.index("    @QtCore.pyqtSlot()", function_start)
    function_source = result.stdout[function_start:function_end]
    match = re.search(
        r'(?ms)^\s{8}script = r"""(.*?)^"""\s*$',
        function_source,
    )
    if not match:
        raise RuntimeError("Could not extract the exact v1.5.0 updater script")
    destination.write_text(match.group(1), encoding="utf-8")


def file_version(path: Path) -> str:
    command = f"(Get-Item -LiteralPath '{str(path).replace(chr(39), chr(39) * 2)}').VersionInfo.FileVersion"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
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
            continue
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


def registered_install_location() -> str:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, TEST_UNINSTALL_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, "InstallLocation")
            return os.path.normcase(os.path.realpath(value))
    except OSError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge", type=Path, required=True)
    parser.add_argument("--test-root", type=Path, default=ROOT / "build" / "bootstrap-e2e-151")
    args = parser.parse_args()

    bridge = args.bridge.resolve()
    test_root = args.test_root.resolve()
    install = test_root / "install"
    update_zip = test_root / bridge.name
    updater_script = test_root / "v1.5.0-updater.ps1"

    if not bridge.is_file():
        raise FileNotFoundError(bridge)
    if not OLD_STAGE.is_dir() or not NEW_STAGE.is_dir():
        raise RuntimeError("Both v1.5.0 and v1.5.1 release stages are required")

    safe_remove_tree(test_root)
    test_root.mkdir(parents=True)
    shutil.copytree(OLD_STAGE, install)
    shutil.copy2(bridge, update_zip)
    (install / "data").mkdir(exist_ok=True)
    (install / "ocr").mkdir(exist_ok=True)
    (install / "translators").mkdir(exist_ok=True)
    (install / "data" / "update-e2e-marker.txt").write_text("preserved", encoding="utf-8")
    extract_v150_updater_script(updater_script)

    worker = install / "app" / "OcrWorker.exe"
    shutil.copy2(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "cmd.exe", worker)
    blocker = subprocess.Popen(
        [str(worker), "/d", "/c", "ping.exe -n 240 127.0.0.1 >nul"],
        cwd=install,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    atexit.register(terminate_process_tree, blocker.pid)

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(updater_script),
            "-AppDir",
            str(install),
            "-ZipPath",
            str(update_zip),
            "-TargetPid",
            "2147483000",
            "-ExeName",
            "ClicknTranslate.exe",
        ],
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        timeout=90,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError(f"v1.5.0 updater failed: {result.stdout!r} {result.stderr!r}")

    deadline = time.monotonic() + 240
    started = False
    while time.monotonic() < deadline:
        launcher = install / "ClicknTranslate.exe"
        inner = install / "app" / "ClicknTranslateApp.exe"
        if launcher.is_file() and inner.is_file():
            try:
                payload_is_complete = (
                    file_version(launcher).startswith("1.5.1.")
                    and sha256(launcher) == sha256(NEW_STAGE / "ClicknTranslate.exe")
                    and sha256(inner) == sha256(NEW_STAGE / "app" / "ClicknTranslateApp.exe")
                )
                if payload_is_complete:
                    started = bool(processes_from_install(install))
                    if started:
                        break
            except (OSError, subprocess.SubprocessError):
                pass
        time.sleep(1)
    else:
        raise RuntimeError("Bootstrap did not install and start v1.5.1 within 240 seconds")

    checks = (
        ("ClicknTranslate.exe", "ClicknTranslate.exe"),
        ("app/ClicknTranslateApp.exe", "app/ClicknTranslateApp.exe"),
        ("app/ArgosWorker.exe", "app/ArgosWorker.exe"),
        ("app/OcrWorker.exe", "app/OcrWorker.exe"),
        ("app/_internal/base_library.zip", "app/_internal/base_library.zip"),
    )
    for installed_relative, staged_relative in checks:
        actual = install / installed_relative
        expected = NEW_STAGE / staged_relative
        if sha256(actual) != sha256(expected):
            raise RuntimeError(f"Installed file differs from the v1.5.1 stage: {installed_relative}")

    marker = install / "data" / "update-e2e-marker.txt"
    if marker.read_text(encoding="utf-8") != "preserved":
        raise RuntimeError("The update did not preserve user data")
    if registered_install_location() != os.path.normcase(os.path.realpath(install)):
        raise RuntimeError("The disposable Inno installation was not registered at the test path")
    if blocker.poll() is None:
        raise RuntimeError("The bridge left the old OCR worker running")
    atexit.unregister(terminate_process_tree)

    print("BOOTSTRAP_UPDATE_E2E_OK")
    print("SOURCE_VERSION=1.5.0")
    print(f"INSTALLED_VERSION={file_version(install / 'ClicknTranslate.exe')}")
    print(f"BRIDGE_SHA256={sha256(bridge)}")
    print("USER_DATA=PRESERVED")
    print("LOCKED_OCR_WORKER=STOPPED")
    print("APPLICATION_RESTARTED=YES")

    stop_install_processes(install)
    uninstaller = install / "unins000.exe"
    subprocess.run(
        [str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        check=True,
        timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if registered_install_location():
        raise RuntimeError("The disposable test registration was not removed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"BOOTSTRAP_UPDATE_E2E_FAILED: {error}", file=sys.stderr)
        raise
