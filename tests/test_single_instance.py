import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

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

    def test_send_reports_false_when_nothing_is_listening(self):
        self.assertFalse(single_instance.send_command("show", path=self.path))

    def test_second_server_cannot_claim_a_live_socket(self):
        self._start_server()

        rival = single_instance.CommandServer(lambda _command: None, path=self.path)
        try:
            self.assertFalse(rival.bind())
        finally:
            rival.stop()

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


if __name__ == "__main__":
    unittest.main()
