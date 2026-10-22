"""Native update integration: source Settings UI -> HTTP -> real frozen GUI.

This deliberately tests current source before rebuilding distribution packages.
Only frozen-install discovery and the current version are simulated in the
source controller; release requests, downloads, checksums, staging, detached
replacement, shutdown, native GUI readiness and rollback are production code.
It does NOT establish that an older released GUI contains the new updater.
All installations, profiles and IPC sockets are private disposable copies.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def controller(options):
    """Drive the actual buttons in a native Qt window, with no network mocks."""
    sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
    import main
    import settings_window as settings
    import posix_update
    import webbrowser
    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtTest import QTest

    case = options.output.resolve()
    target = Path(os.environ['CNT_QA_TARGET'])
    binary = target / 'Contents/MacOS/ClicknTranslate' if options.kind == 'macos' else (
        target / 'clickntranslate' if options.kind == 'linux-dir' else target)
    # There is no release or version mutation. Only the source test controller
    # compares itself as 0.0.0 so an already built candidate can be exercised.
    settings.APP_VERSION = '0.0.0'
    sys.executable = str(binary)
    sys.frozen = True
    if options.kind == 'appimage':
        os.environ['APPIMAGE'] = str(target)
    assert posix_update.update_target() == (options.kind, target)
    # Any accidental browser fallback is a hard failure, not a manual step.
    def forbidden_browser(*args, **kwargs):
        raise AssertionError('The updater attempted to open a browser')
    webbrowser.open = forbidden_browser
    app = main._ensure_startup_application()
    app.setQuitOnLastWindowClosed(False)
    owner = main.DarkThemeApp(background_services=False)
    owner.show()
    owner.show_settings()
    window = owner.settings_window
    seen = []
    installed = False
    started = time.monotonic()
    terminal_since = None

    def record():
        panel = getattr(window, '_update_progress', None)
        item = dict(phase=window._update_phase,
                    label=panel.label.text() if panel else '',
                    windows=[w.windowTitle() for w in app.topLevelWidgets() if w.isVisible()])
        if not seen or item != seen[-1]:
            seen.append(item)
            write_json(case / 'ui.json', seen)

    def poll():
        nonlocal installed, terminal_since
        try:
            record()
            if time.monotonic() - started > 150:
                raise RuntimeError('Update UI timed out')
            panel = getattr(window, '_update_progress', None)
            phase = window._update_phase
            if panel is None:
                return
            if options.scenario == 'cancel' and phase == 'downloading':
                QTest.mouseClick(panel.secondary, Qt.LeftButton)
            if not installed and phase == 'idle' and options.version in panel.label.text():
                installed = True
                QTest.mouseClick(panel.primary, Qt.LeftButton)
            if phase == 'restarting':
                # The original application must exit through its real callback.
                assert options.scenario in ('success', 'rollback')
            elif not window._update_in_progress and seen:
                is_terminal = (installed or options.scenario in ('no-asset', 'offline'))
                if is_terminal:
                    terminal_since = terminal_since or time.monotonic()
                    if time.monotonic() - terminal_since > .5:
                        expected = options.scenario not in ('success', 'rollback')
                        assert expected, panel.label.text()
                        if options.scenario == 'cancel':
                            assert panel.label.text() == settings.update_text('ru', 'cancelled')
                        elif options.scenario == 'checksum':
                            assert panel.label.text() == window._friendly_update_error('checksum mismatch', 'ru')
                        elif options.scenario == 'no-asset':
                            assert panel.label.text() == settings.update_text('ru', 'no_asset')
                        elif options.scenario == 'offline':
                            assert '503' in panel.label.text()
                        write_json(case / 'controller.json', dict(status='terminal', scenario=options.scenario))
                        app.exit(0)
        except BaseException as error:
            write_json(case / 'controller.json', dict(status='failed', error=repr(error)))
            app.exit(2)

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(50)
    QTimer.singleShot(200, lambda: QTest.mouseClick(window.update_btn, Qt.LeftButton))
    code = app.exec_()
    record()
    return code


def supervise(options):
    assert sys.platform in ('darwin', 'linux'), 'Run on the native target OS'
    assert (options.kind == 'macos') == (sys.platform == 'darwin')
    package = options.package.resolve(strict=True)
    installed = options.installed.resolve(strict=True)
    case = options.output.resolve()
    case.mkdir(parents=True, exist_ok=False)
    home = case / 'home'
    home.mkdir()
    runtime = Path(tempfile.mkdtemp(prefix='cnt-upd-'))
    runtime.chmod(0o700)
    env = dict(os.environ, HOME=str(home), XDG_RUNTIME_DIR=str(runtime),
               APPIMAGE_EXTRACT_AND_RUN='1', PYTHONUTF8='1')
    for key in ('XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME'):
        env[key] = str(home / key.lower())
        Path(env[key]).mkdir()
    target = case / ('Test app.app' if options.kind == 'macos' else (
        'Test app.AppImage' if options.kind == 'appimage' else "test app's folder"))
    if installed.is_dir():
        shutil.copytree(installed, target, symlinks=True)
    else:
        shutil.copy2(installed, target)
    env['CNT_QA_TARGET'] = str(target)
    data_root = (home / 'Library/Application Support/ClicknTranslate' if options.kind == 'macos'
                 else target if options.kind == 'linux-dir'
                 else Path(env['XDG_DATA_HOME']) / 'clickntranslate')
    data = data_root / 'data'
    data.mkdir(parents=True, exist_ok=True)
    config = dict(interface_language='ru', theme='Светлая', ui_scale_percent=100,
                  update_check_on_launch=False, first_run_guide_completed=True,
                  first_run_guide_pending=False, autostart=False, start_minimized=False,
                  desktop_assistant_enabled=False, hotkey_defaults_revision=5,
                  show_update_info=options.welcome_enabled,
                  last_seen_startup_news_id='version-1.8-3000-downloads',
                  audit_marker='private-native-update-integration')
    for name in ('copy_hotkey', 'translate_hotkey', 'fullscreen_translate_hotkey',
                 'translate_selection_hotkey', 'translate_replace_selection_hotkey',
                 'game_translate_hotkey', 'toggle_window_hotkey'):
        config[name] = ''
    write_json(data / 'config.json', config)
    markers = {}
    for relative in ('data/personal.bin', 'ocr/model.bin', 'translators/model.bin', '.personal'):
        path = data_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(('keep:' + relative).encode())
        markers[relative] = digest(path)
    binary = target / 'Contents/MacOS/ClicknTranslate' if options.kind == 'macos' else (
        target / 'clickntranslate' if options.kind == 'linux-dir' else target)
    old_digest = digest(binary)
    old_inode = target.stat().st_ino
    requests = []
    extension = {'macos': '.zip', 'appimage': '.AppImage', 'linux-dir': '.tar.gz'}[options.kind]
    import platform
    name = 'Click-n-Translate-' + options.version + '-' + (
        'macos' if options.kind == 'macos' else 'linux') + '-' + platform.machine() + extension
    checksum = '0' * 64 if options.scenario == 'checksum' else digest(package)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append(self.path)
            if self.path == '/latest':
                if options.scenario == 'offline':
                    self.send_error(503)
                    return
                prefix = f'http://127.0.0.1:{self.server.server_port}'
                assets = [] if options.scenario == 'no-asset' else [
                    dict(name=name, browser_download_url=prefix + '/package'),
                    dict(name=name + '.sha256', browser_download_url=prefix + '/checksum')]
                body = json.dumps(dict(tag_name=options.version, assets=assets)).encode()
            elif self.path == '/checksum':
                body = (checksum + '  ' + name + '\n').encode()
            elif self.path == '/package':
                self.send_response(200)
                self.send_header('Content-Length', str(package.stat().st_size))
                self.end_headers()
                try:
                    with package.open('rb') as source:
                        while chunk := source.read(128 * 1024):
                            self.wfile.write(chunk)
                            if options.scenario == 'cancel':
                                time.sleep(.03)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env['CLICKNTRANSLATE_UPDATE_API_URL'] = f'http://127.0.0.1:{server.server_port}/latest'
    report = dict(status='running', kind=options.kind, scenario=options.scenario,
                  scope=__doc__, package_sha256=digest(package), requests=requests)
    process = None
    try:
        with (case / 'controller.log').open('w') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                '--controller', '--output', str(case), '--kind', options.kind,
                '--version', options.version, '--scenario', options.scenario],
                cwd=case, env=env, stdout=log, stderr=log)
            assert process.wait(timeout=180) == 0, 'Inspect controller.log and ui.json'
        assert '/latest' in requests
        terminal = options.scenario not in ('success', 'rollback')
        if terminal:
            assert not list(case.glob('.cnt-stage-*'))
            assert digest(binary) == old_digest
            if options.scenario in ('offline', 'no-asset'):
                assert requests == ['/latest']
            elif options.scenario == 'checksum':
                assert requests == ['/latest', '/package', '/checksum']
            elif options.scenario == 'cancel':
                assert requests == ['/latest', '/package']
        else:
            deadline = time.monotonic() + 120
            ack_seen = False
            killed = False
            crashed_pid = None
            while time.monotonic() < deadline:
                stages = list(case.glob('.cnt-stage-*'))
                for stage in stages:
                    ack = stage / 'ready'
                    if ack.is_file():
                        assert ack.read_text() == options.version
                        ack_seen = True
                        if options.scenario == 'rollback' and not killed:
                            # Crash a candidate that has already shown its GUI.
                            # The production five-second stability check must
                            # reject it and restore/reopen the prior install.
                            if sys.platform == 'linux':
                                # An AppImage's GUI runs from an extracted
                                # mount; its outer runtime is a different PID.
                                with socket.socket(socket.AF_UNIX) as channel:
                                    channel.connect(str(runtime / 'clickntranslate.sock'))
                                    crashed_pid, _, _ = struct.unpack('3i', channel.getsockopt(
                                        socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                                import signal
                                os.kill(crashed_pid, signal.SIGKILL)
                                killed = True
                            else:
                                import psutil
                                for candidate in psutil.process_iter(['exe']):
                                    if candidate.info['exe'] == str(binary):
                                        crashed_pid = candidate.pid
                                        candidate.kill()
                                        killed = True
                failure = data / 'update-failure.txt'
                if options.scenario == 'success' and ack_seen and not stages:
                    break
                if options.scenario == 'rollback' and killed and (
                        failure.exists() or any((s / 'recovery.log').exists() for s in stages)):
                    assert digest(binary) == old_digest
                    assert target.stat().st_ino == old_inode
                    break
                time.sleep(.05)
            else:
                raise RuntimeError('Native update transaction did not complete')
            report['real_gui_acknowledged'] = ack_seen
            assert ack_seen
            sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
            import single_instance
            channel = str(runtime / single_instance.SOCKET_NAME)
            # An AppImage rollback may need to extract the restored runtime
            # before the old GUI can answer. Do not confuse that with failure.
            deadline = time.monotonic() + 90
            while not single_instance.send_command('show', channel):
                if time.monotonic() > deadline:
                    raise RuntimeError('Native GUI command channel is not ready')
                time.sleep(.1)
            if options.scenario == 'success':
                assert target.stat().st_ino != old_inode
            report['atomic_replacement_verified'] = True
            if sys.platform == 'linux' and crashed_pid:
                with socket.socket(socket.AF_UNIX) as client:
                    client.connect(channel)
                    recovered_pid, _, _ = struct.unpack('3i', client.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                assert recovered_pid != crashed_pid
                report['crashed_gui_pid'] = crashed_pid
                report['recovered_gui_pid'] = recovered_pid
            report['real_gui_running'] = True
        actual = json.loads((data / 'config.json').read_text())
        for key in ('audit_marker', 'interface_language', 'theme', 'ui_scale_percent', 'show_update_info'):
            assert actual[key] == config[key], key
        for relative, expected in markers.items():
            assert digest(data_root / relative) == expected, relative
        report['preferences_and_models_preserved'] = True
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        # Limit cleanup strictly to native processes whose executable is inside
        # this newly created case. Never signal an installed user application.
        import psutil
        for candidate in psutil.process_iter(['exe']):
            try:
                if candidate.info['exe'] and Path(candidate.info['exe']).is_relative_to(case):
                    for child in candidate.children(recursive=True):
                        child.terminate()
                    candidate.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        server.shutdown()
        report['requests'] = requests
        write_json(case / 'report.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=('macos', 'linux-dir', 'appimage'), required=True)
    parser.add_argument('--installed', type=Path)
    parser.add_argument('--package', type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scenario', choices=('success', 'rollback', 'checksum', 'cancel', 'no-asset', 'offline'), default='success')
    parser.add_argument('--controller', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--welcome-enabled', action='store_true',
                        help='Keep Welcome enabled to verify it cannot block update readiness')
    options = parser.parse_args()
    if options.controller:
        raise SystemExit(controller(options))
    if not options.installed or not options.package:
        parser.error('--installed and --package are required')
    supervise(options)
