import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import linux_capture  # noqa: E402
import platform_support  # noqa: E402


class BackendSelectionTest(unittest.TestCase):
    def test_non_wayland_sessions_use_qt(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.object(platform_support, "is_wayland", return_value=False):
                self.assertEqual(linux_capture.backend_name(), "qt")

    def test_wayland_prefers_the_portal(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.object(platform_support, "is_wayland", return_value=True):
                with mock.patch.object(linux_capture, "portal_available", return_value=True):
                    self.assertEqual(linux_capture.backend_name(), "portal")

    def test_wayland_falls_back_to_an_installed_helper(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.object(platform_support, "is_wayland", return_value=True):
                with mock.patch.object(linux_capture, "portal_available", return_value=False):
                    with mock.patch.object(linux_capture.shutil, "which", side_effect=lambda name: "/usr/bin/grim" if name == "grim" else None):
                        self.assertEqual(linux_capture.backend_name(), "grim")

    def test_wayland_without_portal_or_helper_has_no_backend(self):
        with mock.patch.object(platform_support, "IS_LINUX", True):
            with mock.patch.object(platform_support, "is_wayland", return_value=True):
                with mock.patch.object(linux_capture, "portal_available", return_value=False):
                    with mock.patch.object(linux_capture.shutil, "which", return_value=None):
                        self.assertEqual(linux_capture.backend_name(), "")

    def test_helpers_are_tried_in_a_deterministic_order(self):
        self.assertEqual(
            [name for name, _command in linux_capture.HELPERS],
            ["grim", "gnome-screenshot", "spectacle", "import"],
        )


class HelperCaptureTest(unittest.TestCase):
    def test_helper_output_is_returned_when_the_command_succeeds(self):
        def fake_run(command, **_kwargs):
            with open(command[-1], "wb") as handle:
                handle.write(b"PNG-ish bytes")
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(linux_capture.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}" if name == "grim" else None):
            with mock.patch.object(linux_capture.subprocess, "run", side_effect=fake_run):
                path = linux_capture.capture_with_helper()

        try:
            self.assertTrue(os.path.isfile(path))
        finally:
            os.unlink(path)

    def test_failing_helper_reports_its_error(self):
        def fake_run(command, **_kwargs):
            return subprocess.CompletedProcess(command, 1, "", "compositor said no")

        with mock.patch.object(linux_capture.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}" if name == "grim" else None):
            with mock.patch.object(linux_capture.subprocess, "run", side_effect=fake_run):
                with self.assertRaises(linux_capture.CaptureError) as ctx:
                    linux_capture.capture_with_helper()

        self.assertIn("compositor said no", str(ctx.exception))

    def test_empty_output_file_counts_as_failure(self):
        def fake_run(command, **_kwargs):
            open(command[-1], "wb").close()  # zero bytes
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(linux_capture.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}" if name == "grim" else None):
            with mock.patch.object(linux_capture.subprocess, "run", side_effect=fake_run):
                with self.assertRaises(linux_capture.CaptureError):
                    linux_capture.capture_with_helper()

    def test_no_helper_installed_is_reported_clearly(self):
        with mock.patch.object(linux_capture.shutil, "which", return_value=None):
            with self.assertRaises(linux_capture.CaptureError) as ctx:
                linux_capture.capture_with_helper()

        self.assertIn("No screenshot helper", str(ctx.exception))

    def test_a_crashing_helper_does_not_escape_as_oserror(self):
        with mock.patch.object(linux_capture.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}" if name == "grim" else None):
            with mock.patch.object(linux_capture.subprocess, "run", side_effect=OSError("boom")):
                with self.assertRaises(linux_capture.CaptureError):
                    linux_capture.capture_with_helper()


class UriTest(unittest.TestCase):
    def test_file_uri_is_decoded(self):
        self.assertEqual(
            linux_capture.uri_to_path("file:///tmp/my%20screenshot.png"),
            "/tmp/my screenshot.png",
        )

    def test_plain_path_is_passed_through(self):
        self.assertEqual(linux_capture.uri_to_path("/tmp/shot.png"), "/tmp/shot.png")

    def test_empty_uri_is_empty(self):
        self.assertEqual(linux_capture.uri_to_path(""), "")


class MessageTest(unittest.TestCase):
    def test_gnome_is_told_which_portal_package_to_install(self):
        with mock.patch.object(platform_support, "desktop_environment", return_value="gnome"):
            message = linux_capture.unavailable_message()
        self.assertIn("xdg-desktop-portal-gnome", message)

    def test_kde_is_told_which_portal_package_to_install(self):
        with mock.patch.object(platform_support, "desktop_environment", return_value="kde"):
            message = linux_capture.unavailable_message()
        self.assertIn("xdg-desktop-portal-kde", message)

    def test_unknown_desktop_gets_generic_advice_and_the_x11_way_out(self):
        with mock.patch.object(platform_support, "desktop_environment", return_value=""):
            message = linux_capture.unavailable_message(["portal: timed out"])
        self.assertIn("xdg-desktop-portal", message)
        self.assertIn("X11", message)
        self.assertIn("portal: timed out", message)


if __name__ == "__main__":
    unittest.main()
