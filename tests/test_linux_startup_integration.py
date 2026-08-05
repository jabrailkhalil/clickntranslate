import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import linux_desktop  # noqa: E402
import main  # noqa: E402
import platform_support  # noqa: E402


class DesktopEntryInstallTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="cnt_startup_")
        patcher = mock.patch.dict(
            os.environ,
            {"XDG_DATA_HOME": self.temp_dir, "XDG_CONFIG_HOME": self.temp_dir},
            clear=False,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_entry_is_written_on_first_run(self):
        with mock.patch.object(main.portable_paths, "public_executable_path", return_value="/opt/cnt"):
            with mock.patch.object(linux_desktop, "install_icon") as install_icon:
                main._install_linux_desktop_entry()

        path = linux_desktop.application_entry_path()
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as handle:
            self.assertIn("Exec=/opt/cnt", handle.read())
        install_icon.assert_called_once()

    def test_unchanged_entry_is_not_rewritten(self):
        with mock.patch.object(main.portable_paths, "public_executable_path", return_value="/opt/cnt"):
            with mock.patch.object(linux_desktop, "install_icon"):
                main._install_linux_desktop_entry()
                with mock.patch.object(linux_desktop, "install_desktop_entry") as install:
                    main._install_linux_desktop_entry()

        install.assert_not_called()

    def test_a_moved_executable_rewrites_the_entry(self):
        """A new AppImage lives at a new path; the launcher must follow it."""
        with mock.patch.object(linux_desktop, "install_icon"):
            with mock.patch.object(main.portable_paths, "public_executable_path", return_value="/opt/old.AppImage"):
                main._install_linux_desktop_entry()
            with mock.patch.object(main.portable_paths, "public_executable_path", return_value="/opt/new.AppImage"):
                main._install_linux_desktop_entry()

        with open(linux_desktop.application_entry_path(), encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Exec=/opt/new.AppImage", content)
        self.assertNotIn("old.AppImage", content)

    def test_a_failure_never_stops_startup(self):
        with mock.patch.object(main.portable_paths, "public_executable_path", side_effect=OSError("no path")):
            main._install_linux_desktop_entry()  # must not raise


class IconConversionTest(unittest.TestCase):
    def test_ico_is_converted_to_png(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": temp_dir}, clear=False):
                target = linux_desktop.install_icon(str(ROOT / "icons" / "icon.ico"))

                self.assertTrue(target.endswith(".png"))
                from PIL import Image

                with Image.open(target) as image:
                    self.assertEqual(image.format, "PNG")
                    self.assertEqual(image.size, (256, 256))


class HighDpiTest(unittest.TestCase):
    def test_linux_enables_high_dpi_before_the_application_exists(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        scaling_at = source.index("AA_EnableHighDpiScaling")
        app_at = source.index("app = QApplication([])")

        self.assertLess(scaling_at, app_at)

    def test_desktop_file_name_is_set_for_the_dock_icon(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("app.setDesktopFileName(", source)


class TrayFallbackTest(unittest.TestCase):
    def test_minimize_without_a_tray_keeps_the_window_reachable(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        minimize_at = source.index("def minimize_to_tray")
        body = source[minimize_at:minimize_at + 400]

        self.assertIn("if not self.has_tray():", body)
        self.assertIn("showMinimized()", body)
        self.assertLess(body.index("has_tray"), body.index("self.hide()"))

    def test_closing_without_a_tray_quits_instead_of_vanishing(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        close_at = source.index("    def closeEvent(self, event):\n        if not self.force_quit")
        body = source[close_at:close_at + 800]

        self.assertIn("self.has_tray()", body)
        self.assertIn("self.force_quit = True", body)


class StartupOrderTest(unittest.TestCase):
    def test_desktop_entry_is_installed_before_the_window(self):
        """The first run opens a modal welcome dialog; the launcher entry must
        not wait for the user to dismiss it."""
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        install_at = source.index("_install_linux_desktop_entry()")
        window_at = source.index("window = DarkThemeApp()")

        self.assertLess(install_at, window_at)


if __name__ == "__main__":
    unittest.main()
