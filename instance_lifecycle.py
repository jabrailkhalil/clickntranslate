"""Identify application instances and replace only the processes the user chose."""

import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import sys

import psutil


MUTEX_NAME = 'ClicknTranslate_SingleInstance_Mutex'
CLOSE_MESSAGE = 'ClicknTranslate_CloseInstance_Message'
APP_NAMES = {'clickntranslate', 'clickntranslateapp', 'clickntranslate.exe', 'clickntranslateapp.exe'}


def _active_gui_pids(candidates):
    """Exclude other launches that are still displaying their startup prompt."""
    if sys.platform != 'win32':
        import socket
        import struct
        import single_instance
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(1.0)
                client.connect(single_instance.socket_path())
                if sys.platform == 'darwin':
                    # Darwin: SOL_LOCAL / LOCAL_PEERPID; Linux SO_PEERCRED is absent.
                    pid = client.getsockopt(0, 2)
                else:
                    pid, _, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                return {pid} & candidates
        except OSError:
            return set()
    return {pid for _, pid in _windows_gui_handles(candidates)}


def _windows_gui_handles(candidates):
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    found = []

    @callback_type
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in candidates:
            title = ctypes.create_unicode_buffer(128)
            user32.GetWindowTextW(hwnd, title, len(title))
            if title.value == "Click'n'Translate":
                found.append((hwnd, pid.value))
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows(visit, 0)
    return found


def normalized_path(path):
    return os.path.normcase(os.path.realpath(path)) if path else ''


def application_path(info, current_path, cwd=''):
    """A Python interpreter or an unrelated main.py is not an app identity."""
    executable = info.get('exe') or info.get('name') or ''
    name = os.path.basename(executable).lower()
    arguments = info.get('cmdline') or []
    if any(arg in ('ocr', 'copy', 'translate', '--layout-editor') for arg in arguments[1:]):
        return ''
    if name in APP_NAMES:
        return executable
    if not name.startswith(('python', 'pypy')):
        return ''
    for argument in arguments[1:]:
        if argument in ('-c', '-m'):
            return ''
        if argument.startswith('-'):
            continue
        script = Path(argument)
        if script.name.lower() != 'main.py':
            return ''
        if not script.is_absolute():
            if not cwd:
                return ''
            script = Path(cwd) / script
        if normalized_path(script) == normalized_path(current_path):
            return str(script)
        root = script.parent
        if all((root / part).is_file() for part in ('translater.py', 'single_instance.py', 'icons/icon.ico')):
            return str(script)
        return ''
    return ''


def running_instances(current_path):
    current = psutil.Process()
    excluded = {current.pid, *(parent.pid for parent in current.parents())}
    instances = []
    for process in psutil.process_iter(['pid', 'name']):
        try:
            info = dict(process.info)
            if info['pid'] in excluded:
                continue
            name = str(info.get('name') or '').lower()
            if name not in APP_NAMES and not name.startswith(('python', 'pypy')):
                continue
            if 'exe' not in info:
                info['exe'] = process.exe()
            if 'cmdline' not in info:
                info['cmdline'] = process.cmdline()
            path = application_path(info, current_path)
            if not path and any(Path(arg).name.lower() == 'main.py' for arg in info.get('cmdline') or []):
                path = application_path(info, current_path, process.cwd())
            if not path:
                continue
            if 'ppid' not in info:
                info['ppid'] = process.ppid()
            if 'create_time' not in info:
                info['create_time'] = process.create_time()
            instances.append({'pid': info['pid'], 'ppid': info['ppid'], 'path': path,
                              'create_time': info['create_time'],
                              'same_path': normalized_path(path) == normalized_path(current_path)})
        except (psutil.Error, OSError, ValueError):
            continue
    # venv launchers and one-file bootloaders wait for their actual GUI child.
    # Closing that child lets the wrapper exit normally; don't list it twice.
    parents = {item['ppid'] for item in instances}
    active = _active_gui_pids({item['pid'] for item in instances})
    return [item for item in instances if item['pid'] not in parents and item['pid'] in active]


def show_instances(instances):
    """Also bring legacy builds forward when they cannot understand IPC."""
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
    user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    for hwnd, pid in _windows_gui_handles({item['pid'] for item in instances}):
        user32.AllowSetForegroundWindow(pid)
        user32.ShowWindowAsync(hwnd, 9)
        user32.SetForegroundWindow(hwnd)


def post_close_requests(pids):
    """Address the chosen processes, never broadcast an exit to newer launches."""
    if sys.platform != 'win32':
        import single_instance
        for pid in pids:
            single_instance.send_command_status('quit', target_pid=pid)
        return
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
    message = user32.RegisterWindowMessageW(CLOSE_MESSAGE)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            user32.PostMessageW(hwnd, message, 0, 0)
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows(visit, 0)


def close_instances(instances, current_path, graceful_timeout=5.0, exit_timeout=3.0):
    """Prefer ordinary shutdown; legacy builds may need explicit termination."""
    chosen = {(item['pid'], item['create_time']) for item in instances}
    processes = []
    # Recheck identities after the confirmation, including PID reuse and the
    # current launcher's ancestry. Never act on a broad process-name match.
    for item in running_instances(current_path):
        if (item['pid'], item['create_time']) not in chosen:
            continue
        try:
            process = psutil.Process(item['pid'])
            if process.create_time() == item['create_time']:
                processes.append(process)
        except psutil.Error:
            continue
    if not processes:
        return True
    try:
        post_close_requests({process.pid for process in processes})
    except Exception:
        logging.exception('Could not request graceful instance shutdown')
    _, alive = psutil.wait_procs(processes, timeout=graceful_timeout)
    for process in alive:
        try:
            # psutil's terminate() also checks the captured process identity.
            process.terminate()
        except psutil.NoSuchProcess:
            pass
        except (psutil.AccessDenied, OSError):
            logging.warning('Cannot close selected instance %s', process.pid)
    _, alive = psutil.wait_procs(alive, timeout=exit_timeout)
    return not alive


class WindowsInstanceGuard:
    def __init__(self, name=MUTEX_NAME):
        self.name = name
        self.handle = None
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.api.CreateMutexW.restype = wintypes.HANDLE
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL

    def acquire(self):
        if self.handle is not None:
            return True
        handle = self.api.CreateMutexW(None, False, self.name)
        error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(error)
        if error == 183:
            self.api.CloseHandle(handle)
            return False
        self.handle = handle
        return True

    def close(self):
        if self.handle is not None:
            self.api.CloseHandle(self.handle)
            self.handle = None
