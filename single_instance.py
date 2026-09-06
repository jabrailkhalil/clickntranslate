"""Single-instance guard and command channel for Linux and macOS builds.

Windows keeps its named mutex and `RegisterHotKey` listeners. Linux cannot rely
on global hotkeys — X11 grabs conflict with the desktop and Wayland forbids them
outright — so the app follows the convention used by NormCap and Flameshot: the
user binds a command such as `clickntranslate --ocr` to a key in their desktop
environment, and that second launch hands the action to the instance already
running in the tray through this socket.

The socket lives in XDG_RUNTIME_DIR, which is per-user and cleaned up on logout.
"""

import errno
import logging
import os
import queue
import selectors
import socket
import stat
import threading
import time
from enum import Enum

import platform_support


SOCKET_NAME = "clickntranslate.sock"
#: Commands the running instance accepts. "show" raises the main window, the
#: rest mirror the Windows hotkey actions.
COMMANDS = ("show",) + platform_support.SHORTCUT_ACTIONS

_CONNECT_TIMEOUT = 2.0
_READ_TIMEOUT = 5.0
_LISTEN_BACKLOG = 128
_QUEUE_SIZE = 128
_MAX_CLIENTS = 128
_MAX_COMMAND_BYTES = 64
_POLL_INTERVAL = 0.05
_logger = logging.getLogger(__name__)


class CommandStatus(Enum):
    ACCEPTED = "ok"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


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
    """Return True only for admission, not completion of the requested action.

    False can also mean overload or an ambiguous transport error. It does not
    prove that no instance exists, or that retrying the command is safe.
    """
    return send_command_status(command, path) is CommandStatus.ACCEPTED


def send_command_status(command, path=None, *, target_pid=None):
    """Forward once, distinguishing no listener from rejection/uncertain delivery.

    Never automatically replay after a write: a lost ACK can coexist with an
    admitted command. The legacy boolean API remains available above.
    """
    if command == 'quit' and isinstance(target_pid, int) and target_pid > 0:
        wire_command = f'quit:{target_pid}'
    elif command in COMMANDS:
        wire_command = command
    else:
        raise ValueError(f"Unknown command: {command}")
    path = path or socket_path()
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(_CONNECT_TIMEOUT)
    try:
        try:
            client.connect(path)
        except OSError as exc:
            if exc.errno in (errno.ENOENT, errno.ECONNREFUSED):
                return CommandStatus.UNAVAILABLE
            return CommandStatus.FAILED
        try:
            client.sendall(f"{wire_command}\n".encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            # An overloaded listener sends BUSY and closes before reading.
            # Its reply can still be buffered even when our write loses that
            # race. Read it once; never reconnect or resend the command.
            pass
        reply = bytearray()
        deadline = time.monotonic() + _CONNECT_TIMEOUT
        while len(reply) < 16:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            client.settimeout(remaining)
            chunk = client.recv(16 - len(reply))
            if not chunk:
                break
            reply.extend(chunk)
            if reply.strip() == b"ok":
                return CommandStatus.ACCEPTED
            if reply.strip() == b"busy":
                return CommandStatus.BUSY
        return CommandStatus.FAILED
    except OSError:
        return CommandStatus.FAILED
    finally:
        try:
            client.close()
        except OSError:
            pass


def _socket_identity(path):
    info = os.lstat(path)
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise OSError(errno.EACCES, "Not a socket owned by this user", path)
    return info.st_dev, info.st_ino


def _unlink_owned_socket(path, identity):
    try:
        if _socket_identity(path) != identity:
            return False
        os.unlink(path)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _remove_stale_socket(path):
    """Reclaim only a refused, unchanged socket while holding the owner lock."""
    try:
        identity = _socket_identity(path)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.settimeout(_CONNECT_TIMEOUT)
    try:
        probe.connect(path)
        return False  # somebody is listening: not stale
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return not os.path.lexists(path)
        if exc.errno == errno.ECONNREFUSED:
            return _unlink_owned_socket(path, identity)
        # A timeout, full backlog or permission failure does not prove death.
        return False
    finally:
        try:
            probe.close()
        except OSError:
            pass


class CommandServer(threading.Thread):
    """Listens for commands from second launches and dispatches them.

    One listener admits bounded, newline-terminated commands and one worker
    calls the thread-safe handler in FIFO order. ACK means queued in memory,
    not completed, durable, or identity-specific exactly-once delivery.
    """

    def __init__(self, handler, path=None, *, queue_size=_QUEUE_SIZE,
                 max_clients=_MAX_CLIENTS, start_ready=True):
        super().__init__(daemon=True, name="ClicknTranslateCommandListener")
        if queue_size < 1 or max_clients < 1:
            raise ValueError("Queue and client limits must be positive")
        self.handler = handler
        self.path = path or socket_path()
        self._server = None
        self._stop_event = threading.Event()
        self._listener_done = threading.Event()
        self._ready_event = threading.Event()
        if start_ready:
            self._ready_event.set()
        self._commands = queue.Queue(maxsize=queue_size)
        self._max_clients = max_clients
        self._owner_fd = None
        self._identity = None
        self._lifecycle_lock = threading.RLock()
        self.listening = False

    def _claim_owner_lock(self):
        # Keep this inode on disk: unlinking a lock file lets two processes lock
        # different inodes for the same pathname during a startup race.
        import fcntl

        flags = os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
        fd = os.open(self.path + ".lock", flags, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise OSError(errno.EACCES, "Invalid command owner lock")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                return False
            os.fchmod(fd, 0o600)
        except BaseException:
            os.close(fd)
            raise
        self._owner_fd = fd
        return True

    def _cleanup(self):
        with self._lifecycle_lock:
            if self._server is not None:
                self._server.close()
                self._server = None
            self.listening = False
            if self._identity is not None:
                if not _unlink_owned_socket(self.path, self._identity):
                    _logger.warning("Command socket changed or could not be removed: %s", self.path)
                self._identity = None
            if self._owner_fd is not None:
                os.close(self._owner_fd)
                self._owner_fd = None

    def bind(self):
        """Claim ownership through shutdown; never remove another owner's path."""
        with self._lifecycle_lock:
            if self._stop_event.is_set():
                return False
            if self._server is not None:
                return True
            try:
                if not self._claim_owner_lock():
                    return False
                if not _remove_stale_socket(self.path):
                    self._cleanup()
                    return False
                self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._server.bind(self.path)
                self._identity = _socket_identity(self.path)
                os.chmod(self.path, 0o600)
                self._server.listen(_LISTEN_BACKLOG)
                self._server.setblocking(False)
            except OSError as exc:
                self._cleanup()
                if exc.errno in (errno.EADDRINUSE, errno.EACCES, errno.EPERM, errno.ELOOP):
                    return False
                raise
            self.listening = True
            return True

    def set_ready(self):
        """Allow dispatch once the application has installed its UI handler."""
        self._ready_event.set()

    def _dispatch(self):
        while True:
            if not self._ready_event.wait(_POLL_INTERVAL):
                if self._listener_done.is_set():
                    cancelled = 0
                    while True:
                        try:
                            self._commands.get_nowait()
                        except queue.Empty:
                            break
                        self._commands.task_done()
                        cancelled += 1
                    if cancelled:
                        _logger.warning("Startup stopped before dispatching %d commands", cancelled)
                    return
                continue
            try:
                command = self._commands.get(timeout=_POLL_INTERVAL)
            except queue.Empty:
                if self._listener_done.is_set():
                    return
                continue
            try:
                self.handler(command)
            except Exception:
                _logger.exception("Command handler failed: %s", command)
            finally:
                self._commands.task_done()

    @staticmethod
    def _reply(connection, message):
        try:
            connection.sendall(message)
        except OSError:
            # Work already queued remains admitted even if the client lost ACK.
            pass

    def _admit(self, data):
        line, separator, extra = data.partition(b"\n")
        if not separator or extra.strip():
            return b"unknown"
        try:
            command = line.decode("utf-8").strip()
        except UnicodeDecodeError:
            return b"unknown"
        if command == f'quit:{os.getpid()}':
            command = 'quit'
        elif command not in COMMANDS:
            return b"unknown"
        with self._lifecycle_lock:
            if self._stop_event.is_set():
                return b"busy"
            try:
                self._commands.put_nowait(command)
            except queue.Full:
                return b"busy"
        return b"ok"

    def run(self):
        if self._server is None and not self.bind():
            return
        worker = threading.Thread(target=self._dispatch, daemon=True,
                                  name="ClicknTranslateCommandDispatcher")
        clients = {}
        with selectors.DefaultSelector() as selector:
            def close_client(connection):
                selector.unregister(connection)
                clients.pop(connection, None)
                connection.close()

            try:
                selector.register(self._server, selectors.EVENT_READ)
                worker.start()
                while not self._stop_event.is_set():
                    for key, _events in selector.select(_POLL_INTERVAL):
                        if self._stop_event.is_set():
                            break
                        if key.fileobj is self._server:
                            # Bound each accept batch so partial senders cannot
                            # starve already-connected clients or shutdown.
                            for _ in range(self._max_clients):
                                try:
                                    connection, _address = self._server.accept()
                                except BlockingIOError:
                                    break
                                except ConnectionAbortedError:
                                    continue
                                connection.setblocking(False)
                                if len(clients) >= self._max_clients:
                                    self._reply(connection, b"busy")
                                    connection.close()
                                    continue
                                clients[connection] = [bytearray(), time.monotonic() + _READ_TIMEOUT]
                                selector.register(connection, selectors.EVENT_READ)
                        else:
                            connection = key.fileobj
                            data, _deadline = clients[connection]
                            try:
                                chunk = connection.recv(_MAX_COMMAND_BYTES - len(data))
                            except BlockingIOError:
                                continue
                            except OSError:
                                close_client(connection)
                                continue
                            if not chunk:
                                close_client(connection)
                                continue
                            data.extend(chunk)
                            if b"\n" in data or len(data) >= _MAX_COMMAND_BYTES:
                                self._reply(connection, self._admit(data))
                                close_client(connection)
                    now = time.monotonic()
                    for connection, (_data, deadline) in list(clients.items()):
                        if now >= deadline:
                            close_client(connection)
            except OSError:
                _logger.exception("Command listener failed")
            finally:
                self._stop_event.set()
                for connection in list(clients):
                    close_client(connection)
                self._listener_done.set()
                if worker.ident is not None:
                    worker.join()
                self._cleanup()

    def stop(self):
        """Stop admission without blocking the caller; join() waits for draining.

        A ready handler drains admitted commands before ownership is released.
        A failed startup cancels queued work with a warning. Like the previous
        protocol, neither normal shutdown nor ACK guarantees a completed GUI action.
        """
        with self._lifecycle_lock:
            self._stop_event.set()
            if self.ident is None:
                self._listener_done.set()
                self._cleanup()
