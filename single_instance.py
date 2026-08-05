"""Single-instance guard and command channel for the Linux build.

Windows keeps its named mutex and `RegisterHotKey` listeners. Linux cannot rely
on global hotkeys — X11 grabs conflict with the desktop and Wayland forbids them
outright — so the app follows the convention used by NormCap and Flameshot: the
user binds a command such as `clickntranslate --ocr` to a key in their desktop
environment, and that second launch hands the action to the instance already
running in the tray through this socket.

The socket lives in XDG_RUNTIME_DIR, which is per-user and cleaned up on logout.
"""

import errno
import os
import socket
import threading

import platform_support


SOCKET_NAME = "clickntranslate.sock"
#: Commands the running instance accepts. "show" raises the main window, the
#: rest mirror the Windows hotkey actions.
COMMANDS = ("show",) + platform_support.SHORTCUT_ACTIONS

_CONNECT_TIMEOUT = 2.0
_READ_TIMEOUT = 5.0


def runtime_dir():
    """Per-user runtime directory for the command socket."""
    runtime = str(os.environ.get("XDG_RUNTIME_DIR", "") or "").strip()
    if runtime and os.path.isdir(runtime):
        return runtime
    # Fall back to a per-user directory in /tmp when the session has no
    # XDG_RUNTIME_DIR (bare X sessions, some containers, WSL).
    fallback = os.path.join("/tmp", f"clickntranslate-{os.getuid()}")
    os.makedirs(fallback, mode=0o700, exist_ok=True)
    return fallback


def socket_path():
    return os.path.join(runtime_dir(), SOCKET_NAME)


def send_command(command, path=None):
    """Hand a command to the running instance.

    Returns True when a running instance accepted it, False when there is none.
    """
    if command not in COMMANDS:
        raise ValueError(f"Unknown command: {command}")
    path = path or socket_path()
    if not os.path.exists(path):
        return False
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(_CONNECT_TIMEOUT)
    try:
        client.connect(path)
        client.sendall(f"{command}\n".encode("utf-8"))
        return client.recv(16).strip() == b"ok"
    except (ConnectionRefusedError, FileNotFoundError, TimeoutError, socket.timeout, OSError):
        return False
    finally:
        try:
            client.close()
        except OSError:
            pass


def _remove_stale_socket(path):
    """Delete a socket file left behind by a crashed instance.

    A socket nobody is listening on refuses connections; one with a live owner
    accepts them, and is left alone.
    """
    if not os.path.exists(path):
        return True
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.settimeout(_CONNECT_TIMEOUT)
    try:
        probe.connect(path)
        return False  # somebody is listening: not stale
    except OSError:
        try:
            os.unlink(path)
        except OSError:
            return False
        return True
    finally:
        try:
            probe.close()
        except OSError:
            pass


class CommandServer(threading.Thread):
    """Listens for commands from second launches and dispatches them.

    `handler` is called on this thread, so it must be thread safe. The app hands
    it a callable that emits a Qt signal, the same way the Windows hotkey
    listener delivers its callbacks.
    """

    def __init__(self, handler, path=None):
        super().__init__(daemon=True)
        self.handler = handler
        self.path = path or socket_path()
        self._server = None
        self._stop_event = threading.Event()
        self.listening = False

    def bind(self):
        """Claim the socket. Returns False when another instance owns it."""
        if not _remove_stale_socket(self.path):
            return False
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(self.path)
        except OSError as exc:
            server.close()
            if exc.errno in (errno.EADDRINUSE, errno.EACCES):
                return False
            raise
        os.chmod(self.path, 0o600)
        server.listen(8)
        server.settimeout(0.5)
        self._server = server
        self.listening = True
        return True

    def run(self):
        if self._server is None and not self.bind():
            return
        while not self._stop_event.is_set():
            try:
                connection, _address = self._server.accept()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                break
            with connection:
                try:
                    connection.settimeout(_READ_TIMEOUT)
                    command = connection.recv(64).decode("utf-8", "replace").strip()
                    if command in COMMANDS:
                        connection.sendall(b"ok")
                        self.handler(command)
                    else:
                        connection.sendall(b"unknown")
                except OSError:
                    continue

    def stop(self):
        self._stop_event.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        self.listening = False
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
        except OSError:
            pass
