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
    def test_helper_uses_the_system_subprocess_environment(self):
        seen = {}

        def fake_run(command, **kwargs):
            seen.update(kwargs)
            with open(command[-1], "wb") as handle:
                handle.write(b"PNG-ish bytes")
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(
            linux_capture.shutil,
            "which",
            side_effect=lambda name: f"/usr/bin/{name}" if name == "grim" else None,
        ):
            with mock.patch.object(
                platform_support,
                "system_subprocess_env",
                return_value={"CNT_SYSTEM": "1"},
            ):
                with mock.patch.object(linux_capture.subprocess, "run", side_effect=fake_run):
                    path = linux_capture.capture_with_helper()

        try:
            self.assertEqual(seen["env"], {"CNT_SYSTEM": "1"})
        finally:
            os.unlink(path)

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


class PortalProtocolTest(unittest.TestCase):
    """Guards for details that only a real portal signal exposes."""

    def test_response_receiver_uses_the_exact_dbus_signal_signature(self):
        import inspect

        source = inspect.getsource(linux_capture.capture_with_portal)
        self.assertIn('@QtCore.pyqtSlot("uint", "QVariantMap")', source)

    def test_response_listener_is_connected_before_request_is_sent(self):
        import inspect

        source = inspect.getsource(linux_capture.capture_with_portal)
        self.assertLess(
            source.index("connected = bus.connect"),
            source.index('interface.call("Screenshot"'),
        )


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


class BlankGrabTest(unittest.TestCase):
    """An X11 grab that succeeds and returns nothing.

    Found by running the real Linux build on a WSLg desktop: the grab reported
    the full 2560x1440 screen and every pixel was black, because an X11 client
    on an Xwayland session sees a root window with nothing in it — each app is
    its own Wayland surface. Passing that on as a screenshot makes OCR answer
    "no text found", which hides the actual problem.
    """

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _pixmap(colour):
        from PyQt5.QtGui import QColor, QPixmap

        pixmap = QPixmap(120, 80)
        pixmap.fill(QColor(colour))
        return pixmap

    @staticmethod
    def _pixmap_with_content():
        from PyQt5.QtGui import QColor, QPainter, QPixmap

        pixmap = QPixmap(120, 80)
        pixmap.fill(QColor("black"))
        painter = QPainter(pixmap)
        painter.fillRect(10, 10, 60, 40, QColor("white"))
        painter.end()
        return pixmap

    def test_an_all_black_grab_is_blank(self):
        self.assertTrue(linux_capture.looks_blank(self._pixmap("black")))

    def test_a_null_pixmap_is_blank(self):
        from PyQt5.QtGui import QPixmap

        self.assertTrue(linux_capture.looks_blank(QPixmap()))
        self.assertTrue(linux_capture.looks_blank(None))

    def test_a_plain_coloured_desktop_is_not_blank(self):
        """Only black counts. A solid wallpaper is a real screenshot."""
        for colour in ("#2b5797", "white", "#1e1e1e"):
            self.assertFalse(linux_capture.looks_blank(self._pixmap(colour)), colour)

    def test_anything_drawn_on_it_is_not_blank(self):
        self.assertFalse(linux_capture.looks_blank(self._pixmap_with_content()))

    def test_a_black_grab_is_still_returned_when_nothing_better_exists(self):
        """Two things produce an all-black grab and they cannot be told apart
        here: an X11 client on a Wayland desktop reading an empty root, and a
        desktop that is simply black — no wallpaper, and the app hides itself
        before capturing. Refusing to capture a dark screen is the worse guess."""
        screen = mock.Mock()
        black = self._pixmap("black")
        screen.grabWindow.return_value = black
        with mock.patch.object(platform_support, "IS_LINUX", True),              mock.patch.object(linux_capture, "qt_platform_name", return_value="xcb"),              mock.patch.object(linux_capture, "portal_available", return_value=False),              mock.patch.object(linux_capture.shutil, "which", return_value=None):
            self.assertIs(linux_capture.grab_screen(screen), black)

    def test_the_black_grab_is_explained_in_the_log(self):
        screen = mock.Mock()
        screen.grabWindow.return_value = self._pixmap("black")
        with mock.patch.object(platform_support, "IS_LINUX", True),              mock.patch.object(linux_capture, "qt_platform_name", return_value="xcb"),              mock.patch.object(linux_capture, "portal_available", return_value=False),              mock.patch.object(linux_capture.shutil, "which", return_value=None),              self.assertLogs(level="WARNING") as logs:
            linux_capture.grab_screen(screen)
        joined = " ".join(logs.output)
        self.assertIn("black", joined.lower())
        self.assertIn("xdg-desktop-portal", joined)

    def test_a_real_x11_grab_is_passed_through(self):
        screen = mock.Mock()
        expected = self._pixmap_with_content()
        screen.grabWindow.return_value = expected
        with mock.patch.object(platform_support, "IS_LINUX", True),              mock.patch.object(linux_capture, "qt_platform_name", return_value="xcb"):
            self.assertIs(linux_capture.grab_screen(screen), expected)

    def test_an_x11_client_on_a_wayland_desktop_falls_back_to_the_portal(self):
        """Every Xwayland app is an X11 client on a Wayland desktop: the root
        grab returns an empty screen, and only the portal can help."""
        screen = mock.Mock()
        screen.grabWindow.return_value = self._pixmap("black")
        portal_image = self._pixmap_with_content()

        with mock.patch.object(platform_support, "IS_LINUX", True),              mock.patch.object(linux_capture, "qt_platform_name", return_value="xcb"),              mock.patch.object(linux_capture, "portal_available", return_value=True),              mock.patch.object(linux_capture, "capture_with_portal", return_value="/tmp/shot.png"),              mock.patch("PyQt5.QtGui.QPixmap", return_value=portal_image),              mock.patch.object(linux_capture, "crop_to_screen", side_effect=lambda pixmap, _screen: pixmap),              mock.patch.object(linux_capture, "_discard"):
            self.assertIs(linux_capture.grab_screen(screen), portal_image)

    def test_the_decision_follows_qt_not_the_environment(self):
        """A session can export WAYLAND_DISPLAY while this process talks X11 —
        reading the environment alone sent a working display to the portal."""
        import inspect

        source = inspect.getsource(linux_capture.grab_screen)
        self.assertIn("qt_platform_name()", source)
        self.assertNotIn("platform_support.is_wayland()", source)

    def test_windows_is_never_second_guessed(self):
        """The check is Linux-only: this same call is the Windows capture path."""
        screen = mock.Mock()
        screen.grabWindow.return_value = self._pixmap("black")
        with mock.patch.object(platform_support, "IS_LINUX", False):
            with mock.patch.object(platform_support, "is_wayland", return_value=False):
                self.assertIsNotNone(linux_capture.grab_screen(screen))


class OverlayFreezeTest(unittest.TestCase):
    """The selection overlay must not rely on translucency on Linux.

    A translucent window only looks translucent where a compositing manager
    runs. GNOME and KDE composite; openbox, i3 and a bare XFCE do not, and there
    the overlay came out solid black — verified on a nested X11 desktop with no
    compositor, where a capture taken while the overlay was up returned a single
    colour. Flameshot and NormCap both select on a frozen screenshot instead.
    """

    @staticmethod
    def _overlay(freeze_setting):
        import ocr

        overlay = ocr.ScreenCaptureOverlay.__new__(ocr.ScreenCaptureOverlay)
        overlay._freeze_screen_on_ocr = freeze_setting
        return overlay

    def test_linux_always_freezes(self):
        import ocr

        overlay = self._overlay(False)
        with mock.patch.object(platform_support, "IS_LINUX", True):
            self.assertTrue(ocr.ScreenCaptureOverlay._freeze_required(overlay))

    def test_windows_keeps_the_users_setting(self):
        import ocr

        with mock.patch.object(platform_support, "IS_LINUX", False):
            self.assertFalse(ocr.ScreenCaptureOverlay._freeze_required(self._overlay(False)))
            self.assertTrue(ocr.ScreenCaptureOverlay._freeze_required(self._overlay(True)))


if __name__ == "__main__":
    unittest.main()
