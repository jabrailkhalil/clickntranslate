import os
import errno
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import platform_support  # noqa: E402
import single_instance  # noqa: E402

# AF_UNIX sockets are the Linux single-instance mechanism; Windows keeps its
# named mutex and never loads this module.
requires_unix_sockets = unittest.skipUnless(
    hasattr(socket, "AF_UNIX"), "AF_UNIX sockets are not available on this platform"
)


class CommandSetTest(unittest.TestCase):
    def test_every_shortcut_action_is_accepted_plus_show(self):
        self.assertEqual(set(single_instance.COMMANDS), set(platform_support.SHORTCUT_ACTIONS) | {"show"})

    def test_unknown_command_is_rejected_before_touching_the_socket(self):
        with self.assertRaises(ValueError):
            single_instance.send_command("rm-rf")


@requires_unix_sockets
class CommandServerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="cnt_ipc_")
        self.path = os.path.join(self.temp_dir, "test.sock")
        self.received = []
        self.event = threading.Event()
        self.server = None

    def tearDown(self):
        if self.server is not None:
            self.server.stop()
            self.server.join(timeout=2)
        for name in os.listdir(self.temp_dir):
            try:
                os.unlink(os.path.join(self.temp_dir, name))
            except OSError:
                pass
        os.rmdir(self.temp_dir)

    def _start_server(self):
        def handler(command):
            self.received.append(command)
            self.event.set()

        self.server = single_instance.CommandServer(handler, path=self.path)
        self.assertTrue(self.server.bind())
        self.server.start()
        return self.server

    def test_command_reaches_the_running_instance(self):
        self._start_server()

        self.assertTrue(single_instance.send_command("ocr", path=self.path))
        self.assertTrue(self.event.wait(timeout=5))
        self.assertEqual(self.received, ["ocr"])

    def test_every_command_round_trips(self):
        self._start_server()

        for command in single_instance.COMMANDS:
            self.event.clear()
            self.assertTrue(single_instance.send_command(command, path=self.path), command)
            self.assertTrue(self.event.wait(timeout=5), command)

        self.assertEqual(self.received, list(single_instance.COMMANDS))

    def test_quit_only_reaches_the_explicitly_selected_process(self):
        self._start_server()
        if sys.platform.startswith('linux'):
            from instance_lifecycle import _active_gui_pids
            with mock.patch.object(single_instance, 'socket_path', return_value=self.path):
                self.assertEqual(_active_gui_pids({os.getpid()}), {os.getpid()})
        status = single_instance.send_command_status('quit', self.path, target_pid=os.getpid() + 1000000)
        self.assertIs(status, single_instance.CommandStatus.FAILED)
        self.assertEqual(self.received, [])
        status = single_instance.send_command_status('quit', self.path, target_pid=os.getpid())
        self.assertIs(status, single_instance.CommandStatus.ACCEPTED)
        self.assertTrue(self.event.wait(timeout=2))
        self.assertEqual(self.received, ['quit'])

    def test_send_reports_false_when_nothing_is_listening(self):
        self.assertFalse(single_instance.send_command("show", path=self.path))

    def test_second_server_cannot_claim_a_live_socket(self):
        self._start_server()

        rival = single_instance.CommandServer(lambda _command: None, path=self.path)
        try:
            self.assertFalse(rival.bind())
        finally:
            rival.stop()
        self.assertTrue(single_instance.send_command("show", path=self.path))
        self.assertTrue(self.event.wait(timeout=2))

    def test_socket_left_by_a_crashed_instance_is_reclaimed(self):
        # A socket file with no listener is what a crash leaves behind.
        stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stale.bind(self.path)
        stale.close()
        self.assertTrue(os.path.exists(self.path))

        self._start_server()
        self.assertTrue(single_instance.send_command("show", path=self.path))
        self.assertTrue(self.event.wait(timeout=5))

    def test_stopping_removes_the_socket_file(self):
        server = self._start_server()
        self.assertTrue(os.path.exists(self.path))

        server.stop()
        server.join(timeout=2)
        self.assertFalse(os.path.exists(self.path))

    def test_socket_is_private_to_the_user(self):
        self._start_server()
        mode = os.stat(self.path).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_garbage_input_does_not_kill_the_server(self):
        self._start_server()

        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(self.path)
        client.sendall(b"not-a-command\n")
        self.assertEqual(client.recv(16).strip(), b"unknown")
        client.close()

        self.assertTrue(single_instance.send_command("translate", path=self.path))
        self.assertTrue(self.event.wait(timeout=5))
        self.assertEqual(self.received, ["translate"])


@requires_unix_sockets
class RuntimeDirTest(unittest.TestCase):
    def test_xdg_runtime_dir_is_used_when_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": temp_dir}, clear=False):
                self.assertEqual(single_instance.runtime_dir(), temp_dir)
                self.assertEqual(
                    single_instance.socket_path(),
                    os.path.join(temp_dir, single_instance.SOCKET_NAME),
                )

    def test_missing_runtime_dir_falls_back_to_a_private_tmp_dir(self):
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/nonexistent-runtime-dir"}, clear=False):
            path = single_instance.runtime_dir()
            self.assertTrue(path.startswith("/tmp/clickntranslate-"))
            self.assertTrue(os.path.isdir(path))


class CommandStatusTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(single_instance.socket, "AF_UNIX", 1, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(single_instance.socket, "socket")
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.client = self.factory.return_value

    def test_fragmented_ack_is_accepted(self):
        self.client.recv.side_effect = [b"o", b"k"]
        self.assertIs(single_instance.send_command_status("show", "unused"),
                      single_instance.CommandStatus.ACCEPTED)
        self.client.close.assert_called_once()

    def test_busy_is_not_reported_as_success(self):
        self.client.recv.return_value = b"busy"
        self.assertIs(single_instance.send_command_status("show", "unused"),
                      single_instance.CommandStatus.BUSY)
        self.assertFalse(single_instance.send_command("show", "unused"))

    def test_busy_reply_survives_listener_closing_before_client_write(self):
        self.client.sendall.side_effect = BrokenPipeError(errno.EPIPE, "listener closed")
        self.client.recv.side_effect = [b"bu", b"sy"]
        self.assertIs(single_instance.send_command_status("ocr", "unused"),
                      single_instance.CommandStatus.BUSY)
        self.client.connect.assert_called_once()
        self.client.sendall.assert_called_once_with(b"ocr\n")

    def test_broken_write_without_reply_remains_ambiguous(self):
        self.client.sendall.side_effect = ConnectionResetError(errno.ECONNRESET, "listener closed")
        self.client.recv.return_value = b""
        self.assertIs(single_instance.send_command_status("ocr", "unused"),
                      single_instance.CommandStatus.FAILED)
        self.client.sendall.assert_called_once_with(b"ocr\n")

    def test_only_missing_or_refused_connect_means_no_listener(self):
        for code in (errno.ENOENT, errno.ECONNREFUSED, errno.EAGAIN, errno.EACCES, errno.ETIMEDOUT):
            with self.subTest(code=code):
                self.client.connect.side_effect = OSError(code, "injected")
                expected = (single_instance.CommandStatus.UNAVAILABLE
                            if code in (errno.ENOENT, errno.ECONNREFUSED)
                            else single_instance.CommandStatus.FAILED)
                self.assertIs(single_instance.send_command_status("ocr", "unused"), expected)

    def test_lost_ack_is_ambiguous_and_never_replayed(self):
        self.client.recv.side_effect = TimeoutError()
        self.assertIs(single_instance.send_command_status("ocr", "unused"),
                      single_instance.CommandStatus.FAILED)
        self.factory.assert_called_once()
        self.client.connect.assert_called_once()
        self.client.sendall.assert_called_once_with(b"ocr\n")

    def test_post_connect_refusal_does_not_mean_safe_to_replay(self):
        self.client.sendall.side_effect = ConnectionRefusedError(errno.ECONNREFUSED, "after connect")
        self.assertIs(single_instance.send_command_status("ocr", "unused"),
                      single_instance.CommandStatus.FAILED)

    def test_unknown_or_incomplete_reply_is_failure(self):
        for reply in (b"unknown", b"o", b"bad"):
            with self.subTest(reply=reply):
                self.client.recv.side_effect = [reply, b""]
                self.assertIs(single_instance.send_command_status("show", "unused"),
                              single_instance.CommandStatus.FAILED)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux ownership and AF_UNIX tests")
class CommandReliabilityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cnt_ipc_reliability_")
        self.path = os.path.join(self.temp.name, "command.sock")
        self.servers = []
        self.release = threading.Event()

    def tearDown(self):
        self.release.set()
        for server in self.servers:
            server.stop()
        for server in self.servers:
            if server.ident is not None:
                server.join(timeout=3)
                self.assertFalse(server.is_alive(), "IPC thread leaked")
        self.temp.cleanup()

    def start(self, handler, **options):
        server = single_instance.CommandServer(handler, self.path, **options)
        self.servers.append(server)
        self.assertTrue(server.bind())
        server.start()
        return server

    def test_slow_handler_does_not_block_admission_and_queue_is_bounded(self):
        entered = threading.Event()
        received = []

        def handler(command):
            received.append(command)
            entered.set()
            self.release.wait(timeout=3)

        server = self.start(handler, queue_size=2)
        self.assertTrue(single_instance.send_command("show", self.path))
        self.assertTrue(entered.wait(1))
        self.assertTrue(single_instance.send_command("ocr", self.path))
        self.assertTrue(single_instance.send_command("copy", self.path))
        self.assertIs(single_instance.send_command_status("translate", self.path),
                      single_instance.CommandStatus.BUSY)
        self.assertEqual(received, ["show"])
        self.release.set()
        server.stop()
        server.join(3)
        self.assertEqual(received, ["show", "ocr", "copy"])

    def test_burst_128_waits_for_ui_then_drains_in_memory(self):
        received = []
        server = self.start(received.append, start_ready=False)
        gate = threading.Event()

        def send(_index):
            gate.wait(2)
            return single_instance.send_command("show", self.path)

        with ThreadPoolExecutor(max_workers=128) as pool:
            futures = [pool.submit(send, i) for i in range(128)]
            gate.set()
            self.assertTrue(all(f.result(5) for f in futures))
        self.assertEqual(received, [])
        self.assertIs(single_instance.send_command_status("show", self.path),
                      single_instance.CommandStatus.BUSY)
        server.set_ready()
        server.stop()
        server.join(3)
        self.assertEqual(received, ["show"] * 128)

    def test_slow_fragmented_sender_does_not_block_other_commands(self):
        received = []
        server = self.start(received.append)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect(self.path)
            client.sendall(b"sh")
            self.assertTrue(single_instance.send_command("ocr", self.path))
            client.sendall(b"ow\n")
            self.assertEqual(client.recv(16), b"ok")
        server.stop()
        server.join(3)
        self.assertEqual(received, ["ocr", "show"])

    def test_partial_frame_expires(self):
        with mock.patch.object(single_instance, "_READ_TIMEOUT", 0.1):
            self.start(lambda _c: None)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(1)
                client.connect(self.path)
                client.sendall(b"sh")
                self.assertEqual(client.recv(16), b"")
            self.assertTrue(single_instance.send_command("show", self.path))

    def test_pending_client_limit_rejects_and_recovers(self):
        server = single_instance.CommandServer(lambda _c: None, self.path, max_clients=1)
        self.servers.append(server)
        self.assertTrue(server.bind())
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as slow:
            slow.settimeout(1)
            slow.connect(self.path)
            slow.sendall(b"sh")
            server.start()
            self.assertIs(single_instance.send_command_status("ocr", self.path),
                          single_instance.CommandStatus.BUSY)
            slow.sendall(b"ow\n")
            self.assertEqual(slow.recv(16), b"ok")
        self.assertTrue(single_instance.send_command("copy", self.path))

    def test_aborted_accept_does_not_stop_listener(self):
        server = single_instance.CommandServer(lambda _c: None, self.path)
        self.servers.append(server)
        self.assertTrue(server.bind())
        original_accept = socket.socket.accept
        aborted = threading.Event()

        def accept(connection):
            if connection is server._server and not aborted.is_set():
                aborted.set()
                raise ConnectionAbortedError(errno.ECONNABORTED, "injected accept failure")
            return original_accept(connection)

        with mock.patch.object(socket.socket, "accept", accept):
            server.start()
            self.assertTrue(single_instance.send_command("show", self.path))
            self.assertTrue(aborted.is_set())
            server.stop()
            server.join(3)

    def test_invalid_and_oversize_frames_are_not_admitted(self):
        received = []
        server = self.start(received.append)
        for data in (b"x" * 64, b"show\nocr\n", b"\xff\n", b"bogus\n"):
            with self.subTest(data=data), socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(1)
                client.connect(self.path)
                client.sendall(data)
                self.assertEqual(client.recv(16), b"unknown")
        self.assertTrue(single_instance.send_command("copy", self.path))
        server.stop()
        server.join(3)
        self.assertEqual(received, ["copy"])

    def test_handler_exception_does_not_kill_dispatch(self):
        done = threading.Event()

        def handler(command):
            if command == "show":
                raise ValueError("injected callback failure")
            done.set()

        self.start(handler)
        with self.assertLogs("single_instance", level="ERROR"):
            self.assertTrue(single_instance.send_command("show", self.path))
            self.assertTrue(single_instance.send_command("copy", self.path))
            self.assertTrue(done.wait(2))

    def test_bound_but_not_started_owner_cannot_be_replaced(self):
        first = single_instance.CommandServer(lambda _c: None, self.path)
        self.servers.append(first)
        self.assertTrue(first.bind())
        rival = single_instance.CommandServer(lambda _c: None, self.path)
        self.assertFalse(rival.bind())
        rival.stop()
        first.start()
        self.assertTrue(single_instance.send_command("show", self.path))

    def test_stop_keeps_owner_lock_until_inflight_handler_finishes(self):
        entered = threading.Event()

        def handler(_command):
            entered.set()
            self.release.wait(3)

        server = self.start(handler)
        self.assertTrue(single_instance.send_command("show", self.path))
        self.assertTrue(entered.wait(1))
        server.stop()
        rival = single_instance.CommandServer(lambda _c: None, self.path)
        try:
            self.assertFalse(rival.bind())
            self.release.set()
            server.join(3)
            self.assertFalse(server.is_alive())
            self.assertTrue(rival.bind())
        finally:
            rival.stop()

    def test_stop_preserves_replacement_socket(self):
        server = self.start(lambda _c: None)
        os.unlink(self.path)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as replacement:
            replacement.bind(self.path)
            replacement.listen(1)
            identity = os.lstat(self.path).st_ino
            with self.assertLogs("single_instance", level="WARNING"):
                server.stop()
                server.join(3)
            self.assertEqual(os.lstat(self.path).st_ino, identity)

    def test_arbitrary_path_and_symlink_are_preserved(self):
        target = Path(self.temp.name) / "data"
        target.write_text("keep")
        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                if symlink:
                    os.symlink(target, self.path)
                else:
                    Path(self.path).write_text("keep")
                server = single_instance.CommandServer(lambda _c: None, self.path)
                self.assertFalse(server.bind())
                server.stop()
                self.assertTrue(os.path.lexists(self.path))
                self.assertEqual(Path(self.path).read_text(), "keep")
                os.unlink(self.path)

    def test_owner_lock_symlink_is_not_followed(self):
        target = Path(self.temp.name) / "data"
        target.write_text("keep")
        os.symlink(target, self.path + ".lock")
        server = single_instance.CommandServer(lambda _c: None, self.path)
        self.assertFalse(server.bind())
        server.stop()
        self.assertEqual(target.read_text(), "keep")

    def test_ambiguous_probe_failures_never_unlink(self):
        stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stale.bind(self.path)
        stale.close()
        for failure in (TimeoutError(), OSError(errno.EAGAIN, "busy"), PermissionError(errno.EACCES, "denied")):
            with self.subTest(failure=failure), mock.patch.object(single_instance.socket, "socket") as factory:
                factory.return_value.connect.side_effect = failure
                self.assertFalse(single_instance._remove_stale_socket(self.path))
                self.assertTrue(os.path.exists(self.path))

    def test_bind_failure_releases_lock_and_owned_socket(self):
        first = single_instance.CommandServer(lambda _c: None, self.path)
        with mock.patch.object(single_instance.os, "chmod", side_effect=PermissionError(errno.EACCES, "denied")):
            self.assertFalse(first.bind())
        self.assertFalse(os.path.exists(self.path))
        second = self.start(lambda _c: None)
        first.stop()
        self.assertTrue(single_instance.send_command("show", self.path))
        self.assertTrue(second.listening)

    def test_stop_before_start_is_idempotent(self):
        server = single_instance.CommandServer(lambda _c: None, self.path)
        self.assertTrue(server.bind())
        server.stop()
        server.stop()
        self.assertFalse(os.path.exists(self.path))
        self.assertFalse(server.bind())
        self.assertTrue(os.path.isfile(self.path + ".lock"))

    def test_shutdown_before_ui_ready_is_bounded_and_logged(self):
        received = []
        server = self.start(received.append, start_ready=False)
        self.assertTrue(single_instance.send_command("show", self.path))
        with self.assertLogs("single_instance", level="WARNING"):
            server.stop()
            server.join(2)
        self.assertFalse(server.is_alive())
        self.assertEqual(received, [])

    def test_two_processes_cannot_win_startup_together(self):
        script = ("import single_instance,sys; "
                  "s=single_instance.CommandServer(lambda c:None,sys.argv[1]); "
                  "print('ready',flush=True); input(); "
                  "print('won' if s.bind() else 'lost',flush=True); input(); s.stop()")
        processes = [subprocess.Popen([sys.executable, "-c", script, self.path], cwd=ROOT,
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for _ in range(2)]
        try:
            for process in processes:
                self.assertEqual(process.stdout.readline().strip(), "ready")
            for process in processes:
                process.stdin.write("go\n")
                process.stdin.flush()
            self.assertCountEqual([p.stdout.readline().strip() for p in processes], ["won", "lost"])
            for process in processes:
                _out, err = process.communicate("stop\n", timeout=3)
                self.assertEqual(process.returncode, 0, err)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=3)

    def test_killed_owner_lock_is_released_and_stale_path_reclaimed(self):
        script = ("import single_instance,sys,threading; "
                  "s=single_instance.CommandServer(lambda c:None,sys.argv[1]); "
                  "assert s.bind(); s.start(); print('ready',flush=True); threading.Event().wait()")
        process = subprocess.Popen([sys.executable, "-c", script, self.path], cwd=ROOT,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), "ready")
            process.kill()
            process.communicate(timeout=3)
            self.assertTrue(os.path.exists(self.path))
            event = threading.Event()
            self.start(lambda _c: event.set())
            self.assertTrue(single_instance.send_command("show", self.path))
            self.assertTrue(event.wait(2))
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)


if __name__ == "__main__":
    unittest.main()
