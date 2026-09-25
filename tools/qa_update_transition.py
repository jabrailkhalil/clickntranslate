"""Exercise a released Windows updater against a candidate in disposable folders.

Uses the OLD archive's updater and real GUI, never a mock startup acknowledgement.
The helper is invoked through its public CLI; this does not test the download UI.
Every invocation preserves its evidence and refuses to reuse an existing case.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

import psutil


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def owned_processes(root):
    root = str(Path(root).resolve()).casefold() + os.sep
    result = []
    for process in psutil.process_iter(['exe', 'name']):
        if (process.info['exe'] or '').casefold().startswith(root):
            result.append(process)
    return result


def stop_owned(root):
    processes = owned_processes(root)
    for process in processes:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(processes, timeout=10)
    for process in alive:
        process.kill()
    psutil.wait_procs(alive, timeout=10)


def wait_ready(ack, version, install, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ack.is_file() and ack.read_text(encoding='utf-8').strip() == version:
            time.sleep(8)
            gui = [p for p in owned_processes(install)
                   if p.name().casefold() == 'clickntranslateapp.exe']
            if not gui:
                raise RuntimeError('GUI acknowledged but did not remain running')
            return gui[0].pid
        time.sleep(.25)
    raise RuntimeError('Real GUI did not acknowledge startup; inspect the preserved case')


def compare_archive(archive_path, install):
    count = 0
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            relative = Path(info.filename).relative_to('ClicknTranslate')
            if relative.parts[0] in ('data', 'ocr', 'translators'):
                raise RuntimeError('Release archive includes user data')
            actual = install / relative
            expected = hashlib.sha256(archive.read(info)).hexdigest()
            if not actual.is_file() or digest(actual) != expected:
                raise RuntimeError('Program file differs from archive: ' + str(relative))
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-zip', type=Path, required=True)
    parser.add_argument('--old-sha256', required=True)
    parser.add_argument('--old-version', required=True)
    parser.add_argument('--new-zip', type=Path, required=True)
    parser.add_argument('--new-sha256', required=True)
    parser.add_argument('--new-version', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--long-temp', action='store_true')
    parser.add_argument('--expect-rollback', action='store_true')
    parser.add_argument('--helper', type=Path, help='Override only for candidate-helper tests; recorded in evidence')
    parser.add_argument('--old-setup', type=Path)
    parser.add_argument('--old-setup-sha256')
    parser.add_argument('--new-setup', type=Path)
    parser.add_argument('--new-setup-sha256')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Windows only')
    if not args.case or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.case):
        parser.error('Case must be a lowercase filesystem slug')
    setup_mode = any((args.old_setup, args.new_setup, args.old_setup_sha256, args.new_setup_sha256))
    if setup_mode:
        if not all((args.old_setup, args.new_setup, args.old_setup_sha256, args.new_setup_sha256)):
            parser.error('Both original installers and both hashes are required')
        import winreg
        registry_key = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{70f13ecd-bf6d-4c9d-bba6-3fb112272e36}_is1'
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
                try:
                    with winreg.OpenKey(hive, registry_key, 0, winreg.KEY_READ | view):
                        raise RuntimeError('An installed copy exists; use a clean Windows account/VM for installer QA')
                except FileNotFoundError:
                    pass
        for path, expected in ((args.old_setup, args.old_setup_sha256), (args.new_setup, args.new_setup_sha256)):
            if digest(path) != expected.removeprefix('sha256:'):
                raise RuntimeError('Installer hash mismatch: ' + str(path))
    for path, expected in ((args.old_zip, args.old_sha256), (args.new_zip, args.new_sha256)):
        if digest(path) != expected.removeprefix('sha256:'):
            raise RuntimeError('Archive hash mismatch: ' + str(path))
    for process in psutil.process_iter(['name', 'cmdline']):
        name = (process.info['name'] or '').lower()
        if 'clickntranslate' in name or ('python' in name and any(
                Path(arg).name == 'main.py' for arg in process.info['cmdline'] or [])):
            raise RuntimeError('Close existing app before this isolated test: ' + str(process.pid))
    case = ROOT / 'build/update-audit' / args.case
    case.mkdir(parents=True, exist_ok=False)
    install = case / 'Копия с пробелами' / 'ClicknTranslate'
    install.parent.mkdir()
    with zipfile.ZipFile(args.old_zip) as archive:
        for info in archive.infolist():
            target = (install.parent / info.filename).resolve()
            if install.parent.resolve() not in target.parents:
                raise RuntimeError('Unsafe archive path')
        archive.extractall(install.parent)
    compare_archive(args.old_zip, install)
    env = dict(os.environ)
    for key in ('QT_QPA_PLATFORM', 'CLICKNTRANSLATE_UPDATE_TOKEN', 'CLICKNTRANSLATE_UPDATE_API_URL'):
        env.pop(key, None)
    for key in ('APPDATA', 'LOCALAPPDATA'):
        folder = case / 'profile' / key
        folder.mkdir(parents=True)
        env[key] = str(folder)
    temp = case / 'profile' / 'deliberately-long-temporary-directory' if args.long_temp else Path(tempfile.mkdtemp(prefix='cntqa-'))
    temp.mkdir(parents=True, exist_ok=True)
    env['TEMP'] = env['TMP'] = str(temp)
    data = install / 'data'
    data.mkdir(exist_ok=True)
    config = dict(interface_language='en', ui_scale_percent=100, theme='Светлая',
                  update_check_on_launch=False, show_update_info=False,
                  first_run_guide_completed=True, first_run_guide_pending=False,
                  autostart=False, start_minimized=False, hotkey_defaults_revision=5,
                  last_seen_startup_news_id='community-1000-downloads-gaming',
                  desktop_assistant_enabled=False, audit_marker=args.case)
    for key in ('copy_hotkey', 'translate_hotkey', 'fullscreen_translate_hotkey',
                'translate_selection_hotkey', 'translate_replace_selection_hotkey',
                'game_translate_hotkey', 'toggle_window_hotkey'):
        config[key] = ''
    (data / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
    markers = {}
    for relative in ('data/update-test-marker.bin', 'ocr/update-test-model.bin', 'translators/update-test-model.bin'):
        path = install / relative
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(('preserve:' + relative).encode())
        markers[relative] = digest(path)
    old_helper = install / 'app/_internal/ClicknTranslateUpdater.exe'
    runner = temp / 'ClicknTranslateUpdater.exe'
    shutil.copy2(args.helper or old_helper, runner)
    package_source = args.new_setup if setup_mode else args.new_zip
    package = case / package_source.name
    shutil.copy2(package_source, package)
    result = dict(case=args.case, status='running', old_version=args.old_version,
                  new_version=args.new_version, old_sha256=digest(args.old_zip),
                  new_sha256=digest(args.new_zip), old_helper_sha256=digest(old_helper),
                  invoked_helper_sha256=digest(runner), helper_override=bool(args.helper),
                  install=str(install), temp=str(temp), markers=markers,
                  scope='Old released helper CLI, real released GUIs; no download/UI automation')
    result['mode'] = 'setup' if setup_mode else 'zip'
    if setup_mode:
        result['old_setup_sha256'] = digest(args.old_setup)
        result['new_setup_sha256'] = digest(args.new_setup)
    receipt = case / 'result.json'
    receipt.write_text(json.dumps(result, indent=2), encoding='utf-8')
    log = (case / 'application.log').open('w', encoding='utf-8')
    helper_process = None
    try:
        if setup_mode:
            subprocess.run([str(args.old_setup.resolve()), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                            '/NOICONS', '/GROUP=ClicknTranslate QA ' + args.case,
                            '/DIR=' + str(install), '/LOG=' + str(case / 'old-setup.log')],
                           env=env, cwd=temp, check=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
            # Published 1.7 ZIP and installer have different dependency inventories.
            # The migration must use the helper actually installed by that EXE.
            result['old_helper_sha256'] = digest(old_helper)
            shutil.copy2(args.helper or old_helper, runner)
            result['invoked_helper_sha256'] = digest(runner)
        old_ack = case / 'old-ready.txt'
        subprocess.Popen([str(install / 'ClicknTranslate.exe'), '--show-after-update', '--update-ack=' + str(old_ack)],
                         cwd=install, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        old_pid = wait_ready(old_ack, args.old_version, install)
        result['old_gui_pid'] = old_pid
        encode = lambda value: base64.b64encode(str(value).encode()).decode()
        command = [str(runner), '--mode', result['mode'], '--app-dir', encode(install), '--package', encode(package),
                   '--exe', encode('ClicknTranslate.exe'), '--version', args.new_version, '--pid', str(old_pid)]
        helper_process = subprocess.Popen(command, cwd=temp, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        stop_owned(install)  # Mirrors the application's exit after handing off to its updater.
        deadline = time.monotonic() + 180
        update_log = temp / 'clickntranslate_update.log'
        while time.monotonic() < deadline:
            if helper_process.poll() is not None:
                break
            if update_log.exists() and 'Updater failed:' in update_log.read_text(encoding='utf-8-sig', errors='replace'):
                break
            time.sleep(.5)
        result['helper_exit_code'] = helper_process.poll()
        failed_log = update_log.exists() and 'Updater failed:' in update_log.read_text(encoding='utf-8-sig', errors='replace')
        result['helper_failure_reported'] = failed_log
        if helper_process.poll() is None and not failed_log:
            raise TimeoutError('Helper did not finish or report failure within 180 seconds')
        updater_failed = helper_process.poll() != 0
        if update_log.exists():
            shutil.copy2(update_log, case / 'updater.log')
        if updater_failed != args.expect_rollback:
            raise RuntimeError('Unexpected helper outcome; inspect updater.log')
        expected_archive = args.old_zip if args.expect_rollback else args.new_zip
        result['verified_program_files'] = compare_archive(expected_archive, install)
        if not owned_processes(install):
            raise RuntimeError('Application is not running after helper completed')
        for relative, expected in markers.items():
            if digest(install / relative) != expected:
                raise RuntimeError('User data changed: ' + relative)
        actual_config = json.loads((data / 'config.json').read_text(encoding='utf-8'))
        for key in ('interface_language', 'ui_scale_percent', 'theme', 'autostart', 'audit_marker'):
            if actual_config[key] != config[key]:
                raise RuntimeError('Preference changed: ' + key)
        result['preferences_preserved'] = True
        stop_owned(install)
        ack = case / 'restart-ready.txt'
        subprocess.Popen([str(install / 'ClicknTranslate.exe'), '--show-after-update', '--update-ack=' + str(ack)],
                         cwd=install, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        result['restarted_gui_pid'] = wait_ready(ack, args.old_version if args.expect_rollback else args.new_version, install)
        result['status'] = 'passed'
    except Exception as error:
        result['status'] = 'failed'
        result['error'] = repr(error)
        raise
    finally:
        result['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        receipt.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        stop_owned(install)
        if helper_process is not None and helper_process.poll() is None:
            helper_process.terminate()
            helper_process.wait(timeout=10)
        if setup_mode:
            uninstaller = install / 'unins000.exe'
            if uninstaller.exists():
                subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'],
                               env=env, cwd=temp, check=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
        log.close()
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
