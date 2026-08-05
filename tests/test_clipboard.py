import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import platform_support  # noqa: E402


class FakeProcess:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stdin_payload = None

    def communicate(self, input=None, timeout=None):
        self.stdin_payload = input
        return b"", b""


class ClipboardHelperTest(unittest.TestCase):
    def test_wayland_uses_wl_copy_first(self):
        started = []

        def fake_popen(command, **kwargs):
            started.append((command, kwargs))
            return FakeProcess()

        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.object(platform_support.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"):
                with mock.patch.object(platform_support.subprocess, "Popen", side_effect=fake_popen):
                    self.assertTrue(platform_support.copy_text("hello"))

        self.assertEqual(started[0][0][0], "wl-copy")

    def test_helper_runs_detached_so_the_selection_outlives_us(self):
        started = []

        def fake_popen(command, **kwargs):
            started.append((command, kwargs))
            return FakeProcess()

        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.object(platform_support.shutil, "which", side_effect=lambda name: "/usr/bin/xclip" if name == "xclip" else None):
                with mock.patch.object(platform_support.subprocess, "Popen", side_effect=fake_popen):
                    platform_support.copy_text("hello")

        command, kwargs = started[0]
        self.assertEqual(command[:3], ["xclip", "-selection", "clipboard"])
        self.assertTrue(kwargs["start_new_session"])

    def test_text_is_sent_as_utf8(self):
        process = FakeProcess()
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.object(platform_support.shutil, "which", side_effect=lambda name: "/usr/bin/xsel" if name == "xsel" else None):
                with mock.patch.object(platform_support.subprocess, "Popen", return_value=process):
                    platform_support.copy_text("Привет")

        self.assertEqual(process.stdin_payload, "Привет".encode("utf-8"))

    def test_failing_helper_falls_through_to_the_next_one(self):
        attempts = []

        def fake_popen(command, **_kwargs):
            attempts.append(command[0])
            # xclip cannot reach the display; xsel can.
            return FakeProcess(returncode=1 if command[0] == "xclip" else 0)

        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.object(platform_support.shutil, "which", side_effect=lambda name: None if name == "wl-copy" else f"/usr/bin/{name}"):
                with mock.patch.object(platform_support.subprocess, "Popen", side_effect=fake_popen):
                    self.assertTrue(platform_support.copy_text("hello"))

        self.assertEqual(attempts, ["xclip", "xsel"])

    def test_without_helpers_it_falls_back_to_pyperclip(self):
        copied = []
        fake_pyperclip = type("FakePyperclip", (), {"copy": staticmethod(lambda text: copied.append(text))})

        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.object(platform_support.shutil, "which", return_value=None):
                with mock.patch.dict(sys.modules, {"pyperclip": fake_pyperclip}):
                    self.assertTrue(platform_support.copy_text("hello"))

        self.assertEqual(copied, ["hello"])

    def test_a_clipboard_failure_is_reported_not_raised(self):
        def explode(_text):
            raise RuntimeError("no clipboard here")

        fake_pyperclip = type("FakePyperclip", (), {"copy": staticmethod(explode)})
        with mock.patch.object(platform_support, "IS_LINUX", False):
            with mock.patch.dict(sys.modules, {"pyperclip": fake_pyperclip}):
                self.assertFalse(platform_support.copy_text("hello"))

    def test_windows_does_not_shell_out(self):
        with mock.patch.object(platform_support, "IS_LINUX", False):
            with mock.patch.object(platform_support.subprocess, "Popen") as popen:
                with mock.patch.dict(sys.modules, {"pyperclip": type("P", (), {"copy": staticmethod(lambda _t: None)})}):
                    platform_support.copy_text("hello")

        popen.assert_not_called()


class ClipboardCallSiteTest(unittest.TestCase):
    def test_no_module_writes_the_clipboard_directly(self):
        """A direct pyperclip.copy would lose the text when the overlay exits."""
        for name in ("ocr.py", "main.py"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("pyperclip.copy(", source, name)

    def test_missing_helper_is_named_for_the_session_type(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.object(platform_support, "is_wayland", return_value=True):
                with mock.patch.object(platform_support.shutil, "which", return_value=None):
                    self.assertEqual(platform_support.missing_clipboard_helper(), "wl-clipboard")
            with mock.patch.object(platform_support, "is_wayland", return_value=False):
                with mock.patch.object(platform_support.shutil, "which", return_value=None):
                    self.assertEqual(platform_support.missing_clipboard_helper(), "xclip")


if __name__ == "__main__":
    unittest.main()
