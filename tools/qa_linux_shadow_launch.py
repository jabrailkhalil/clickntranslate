"""Exercise both generated launchers on an isolated X11 desktop with Openbox and trayer."""

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

import psutil


ROOT = Path(__file__).resolve().parents[1]


def wait_for(description, probe, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = probe()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f'Timed out waiting for {description}')


def output_of(*command):
    return subprocess.run(command, text=True, capture_output=True, timeout=5).stdout.strip()


def socket_owner(path):
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(1)
            client.connect(path)
            return struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[0]
    except OSError:
        return None


def fixture_processes(script):
    return [p for p in psutil.process_iter(['cmdline']) if str(script) in (p.info['cmdline'] or [])]


def stop_applications(script):
    processes = fixture_processes(script)
    for process in processes:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, remaining = psutil.wait_procs(processes, timeout=3)
    for process in remaining:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(remaining, timeout=3)


def stop_helper(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def tray_clients():
    tree = output_of('xwininfo', '-root', '-tree')
    clients = {}
    for window in re.findall(r'^\s*(0x[0-9a-f]+)\s', tree, re.MULTILINE | re.IGNORECASE):
        properties = output_of('xprop', '-id', window, '_XEMBED_INFO', '_NET_WM_PID')
        if re.search(r'^_XEMBED_INFO\([^)]*\) = ', properties, re.MULTILINE):
            pid = re.search(r'_NET_WM_PID\(CARDINAL\) = (\d+)', properties)
            clients[window] = int(pid.group(1)) if pid else None
    return clients


def main_windows(owner, only_visible=False):
    options = ['--onlyvisible'] if only_visible else []
    ids = output_of('xdotool', 'search', '--all', *options, '--pid', str(owner),
                    '--name', "^Click'n'Translate$").splitlines()
    return {int(window) for window in ids}


def screenshot(app, path):
    app.processEvents()
    if not app.primaryScreen().grabWindow(0).save(str(path)):
        raise AssertionError(f'Could not save X11 root image to {path.name}')


def exercise(folder, output, report):
    installation = folder / 'QA installation'
    script = installation / 'src' / 'main.py'
    shutil.copytree(ROOT / 'src', script.parent, ignore=shutil.ignore_patterns('__pycache__'))
    for key in ('HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_RUNTIME_DIR',
                'XDG_STATE_HOME'):
        path = folder / key.lower()
        path.mkdir(mode=0o700)
        os.environ[key] = str(path)
    os.environ.update(QT_QPA_PLATFORM='xcb', XDG_SESSION_TYPE='x11', XDG_CURRENT_DESKTOP='Openbox')
    sys.path.insert(0, str(script.parent))
    import linux_desktop
    import single_instance
    from PyQt5.QtWidgets import QApplication, QSystemTrayIcon

    config = {
        'interface_language': 'en', 'start_minimized': True, 'autostart': True,
        'show_update_info': False, 'update_check_on_launch': False,
        'first_run_guide_completed': True, 'first_run_guide_pending': False,
        'last_seen_startup_news_id': 'version-1.8.3-engines', 'desktop_assistant_enabled': False,
    }
    data = installation / 'data'
    data.mkdir()
    (data / 'config.json').write_text(json.dumps(config), encoding='utf-8')
    assert linux_desktop.set_autostart(True, str(script))
    login = Path(linux_desktop.autostart_path())
    menu = Path(linux_desktop.application_entry_path())
    channel = single_instance.socket_path()
    app = QApplication([])

    with ExitStack() as stack:
        log = stack.enter_context((output / 'session.log').open('w', encoding='utf-8'))
        for command in (['openbox'], ['trayer', '--edge', 'top', '--align', 'right', '--height', '28']):
            process = subprocess.Popen(command, stdout=log, stderr=log, cwd=folder)
            stack.callback(stop_helper, process)
        stack.callback(stop_applications, script)
        wait_for('Openbox', lambda: 'window id #' in output_of('xprop', '-root', '_NET_SUPPORTING_WM_CHECK'))
        def tray_available():
            app.processEvents()
            return QSystemTrayIcon.isSystemTrayAvailable()
        wait_for('the native XEmbed system tray', tray_available)
        initial_clients = tray_clients()

        def launch(entry):
            command = next(line[5:] for line in entry.read_text(encoding='utf-8').splitlines()
                           if line.startswith('Exec='))
            subprocess.run(['gio', 'launch', str(entry)], check=True, timeout=10, stdout=log, stderr=log,
                           cwd=installation)
            return command

        report['login_exec'] = launch(login)
        owner = wait_for('the login process to listen on its private IPC socket', lambda: socket_owner(channel))
        report['owner_after_login'] = owner
        def application_tray_clients():
            return {window: pid for window, pid in tray_clients().items()
                    if window not in initial_clients and pid in (owner, None)}
        report['embedded_tray_clients'] = wait_for('the new application tray icon', application_tray_clients)
        # Observe the fully started application for several WM dispatch cycles.
        # The absence of a mapped main window alone could also mean an early startup failure.
        hidden_until = time.monotonic() + 1.5
        while time.monotonic() < hidden_until:
            assert socket_owner(channel) == owner
            assert not main_windows(owner, only_visible=True), 'Login displayed the main window'
            managed = {int(value, 16) for value in re.findall(r'0x[0-9a-f]+',
                       output_of('xprop', '-root', '_NET_CLIENT_LIST'), re.IGNORECASE)}
            assert not main_windows(owner) & managed, 'The main window was minimized to the taskbar'
            time.sleep(0.1)
        report['visible_main_windows_after_login'] = []
        screenshot(app, output / 'login.png')
        report['menu_exec'] = launch(menu)
        visible = wait_for('the original main window to be mapped', lambda: main_windows(owner, only_visible=True))
        assert len(visible) == 1
        window = next(iter(visible))
        wait_for('the main window to receive focus', lambda: output_of('xdotool', 'getactivewindow') == str(window))
        wait_for('the second launcher to exit', lambda: [p.pid for p in fixture_processes(script)] == [owner])
        report['owner_after_menu'] = socket_owner(channel)
        assert report['owner_after_menu'] == owner
        report['visible_main_window_after_menu'] = window
        report['remaining_application_pids'] = [owner]
        screenshot(app, output / 'menu.png')
        assert single_instance.send_command_status('quit', channel, target_pid=owner) is single_instance.CommandStatus.ACCEPTED
        wait_for('the original application to exit', lambda: not fixture_processes(script))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not sys.platform.startswith('linux') or not os.environ.get('DISPLAY'):
        parser.error('Run inside a fresh Linux Xvfb session')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {'platform': 'Linux X11', 'window_manager': 'Openbox', 'tray': 'trayer', 'passed': False}
    try:
        with tempfile.TemporaryDirectory(prefix='cnt-login-') as temporary:
            exercise(Path(temporary), output, report)
        report['passed'] = True
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
