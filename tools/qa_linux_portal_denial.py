"""Check a real saved screenshot denial on a disposable Sway desktop and private D-Bus."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
STORE = 'org.freedesktop.impl.portal.PermissionStore'
STORE_PATH = '/org/freedesktop/impl/portal/PermissionStore'
PORTAL = '/org/freedesktop/portal/desktop'


def dbus_call(destination, path, method, *arguments):
    reply = subprocess.run(['gdbus', 'call', '--session', '--dest', destination,
                            '--object-path', path, '--method', method, *arguments],
                           text=True, capture_output=True, timeout=35)
    if reply.returncode:
        raise RuntimeError(f'{destination} {method}: {reply.stderr.strip()}')
    return reply.stdout.strip()


def private_check(output, report):
    # The private bus launches GNOME's real backend on Xvfb. On Wayland
    # that backend requires Mutter's privileged service-connection protocol.
    # The tested Qt client still connects to the synthetic Sway desktop.
    os.environ['XDG_SESSION_TYPE'] = 'wayland'
    sys.path.insert(0, str(ROOT / 'src'))
    from PyQt5.QtWidgets import QApplication
    import linux_capture

    app = QApplication([])
    report['qt_platform'] = app.platformName()
    report['backend_display'] = 'GNOME Screenshot on private Xvfb'
    assert app.platformName().startswith('wayland')
    report['backend_version'] = dbus_call('org.freedesktop.impl.portal.desktop.gnome', PORTAL,
                                          'org.freedesktop.DBus.Properties.Get',
                                          'org.freedesktop.impl.portal.Screenshot', 'version')
    assert 'uint32 2' in report['backend_version'], report['backend_version']
    # The native process has the empty host application ID in this private session.
    dbus_call(STORE, STORE_PATH, STORE + '.SetPermission', 'screenshot', 'true', 'screenshot', '', "['no']")
    report['stored_permission'] = dbus_call(STORE, STORE_PATH, STORE + '.Lookup', 'screenshot', 'screenshot')
    assert "'no'" in report['stored_permission'], report['stored_permission']
    assert linux_capture.portal_available()

    helpers = {name for name, _ in linux_capture.HELPERS}
    report['external_capture_attempts'] = []
    def observe_process(event, arguments):
        if event == 'subprocess.Popen' and Path(os.fsdecode(arguments[0])).name in helpers:
            report['external_capture_attempts'].append(os.fsdecode(arguments[0]))
            raise AssertionError('The application attempted a capture helper after denial')
    sys.addaudithook(observe_process)
    trace_path = output / 'portal-bus.log'
    filters = [
        "type='signal',interface='org.freedesktop.portal.Request',member='Response'",
        "type='method_call',interface='org.freedesktop.impl.portal.Screenshot',member='Screenshot'",
        "type='method_call',interface='org.freedesktop.impl.portal.Access',member='AccessDialog'",
        "type='method_call',interface='org.freedesktop.impl.portal.PermissionStore',member='Lookup'",
    ]
    with trace_path.open('w') as trace:
        monitor = subprocess.Popen(['stdbuf', '-oL', 'dbus-monitor', '--session', *filters],
                                   stdout=trace, stderr=subprocess.STDOUT)
        try:
            end = time.monotonic() + 5
            while not trace_path.stat().st_size and time.monotonic() < end and monitor.poll() is None:
                time.sleep(.05)
            assert trace_path.stat().st_size and monitor.poll() is None, 'D-Bus observer did not start'
            try:
                linux_capture.grab_screen(app.primaryScreen())
            except linux_capture.CaptureDeclined as error:
                report['capture_result'] = str(error)
            else:
                raise AssertionError('The stored denial did not stop the screenshot')
            end = time.monotonic() + 3
            while 'uint32 2' not in trace_path.read_text() and time.monotonic() < end:
                time.sleep(.05)
        finally:
            monitor.terminate()
            monitor.wait(timeout=5)
    traffic = trace_path.read_text()
    assert re.search(r'member=Response\s+uint32 2\b', traffic), 'No real portal Response(2)'
    assert 'interface=org.freedesktop.impl.portal.PermissionStore; member=Lookup' in traffic
    assert 'interface=org.freedesktop.impl.portal.Screenshot; member=Screenshot' not in traffic
    assert 'interface=org.freedesktop.impl.portal.Access; member=AccessDialog' not in traffic
    report['portal_response'] = 2
    report['passed'] = True


def launch_private_session(output):
    sway_runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    sway_socket = sway_runtime / os.environ['WAYLAND_DISPLAY']
    if not sway_socket.is_socket():
        raise RuntimeError('Run this probe within the disposable Wayland QA session')
    with tempfile.TemporaryDirectory(prefix='cnt-portal-denied-') as temporary:
        root = Path(temporary)
        env = dict(os.environ, XDG_CURRENT_DESKTOP='GNOME', XDG_SESSION_TYPE='x11',
                   GDK_BACKEND='x11', QT_QPA_PLATFORM='wayland', WAYLAND_DISPLAY='wayland-qa')
        for name in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_RUNTIME_DIR', 'HOME'):
            folder = root / name.lower()
            folder.mkdir(mode=0o700)
            env[name] = str(folder)
        env['CNT_QA_DENIAL_PROFILE'] = str(root)
        runtime = Path(env['XDG_RUNTIME_DIR'])
        (runtime / 'wayland-qa').symlink_to(sway_socket)
        portal_config = Path(env['XDG_CONFIG_HOME']) / 'xdg-desktop-portal'
        portal_config.mkdir()
        (portal_config / 'portals.conf').write_text(
            '[preferred]\ndefault=gtk\norg.freedesktop.impl.portal.Screenshot=gnome\n'
            'org.freedesktop.impl.portal.Access=gtk\n', encoding='utf-8')
        try:
            return subprocess.run(['xvfb-run', '-a', '-s', '-screen 0 640x480x24',
                                   'dbus-run-session', '--', sys.executable, __file__,
                                   '--private-check', '--output', str(output)], env=env, timeout=100).returncode
        finally:
            # A D-Bus-activated document portal can momentarily outlive the private bus.
            if (runtime / 'doc').is_mount():
                unmount = shutil.which('fusermount3') or shutil.which('fusermount')
                if unmount:
                    subprocess.run([unmount, '-u', str(runtime / 'doc')], timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--private-check', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if not args.private_check:
        raise SystemExit(launch_private_session(destination))
    if Path(os.environ.get('CNT_QA_DENIAL_PROFILE', '/')) / 'xdg_runtime_dir' != Path(os.environ['XDG_RUNTIME_DIR']):
        parser.error('The permission check requires its own temporary session')
    result = {'passed': False}
    try:
        private_check(destination, result)
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        (destination / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
