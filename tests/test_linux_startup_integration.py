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


class AutostartSyncTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='cnt_autostart_sync_')
        self.addCleanup(folder.cleanup)
        environment = mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': folder.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.window = mock.Mock(config={'autostart': True})

    def sync(self):
        with (mock.patch.object(platform_support, 'IS_LINUX', True),
              mock.patch.object(platform_support, 'IS_MAC', False),
              mock.patch.object(main.portable_paths, 'public_executable_path', return_value='/opt/new.AppImage')):
            return main.DarkThemeApp.sync_autostart_state(self.window, repair_stale=True)

    def test_moved_appimage_repairs_enabled_entry_and_preserves_desktop_options(self):
        linux_desktop.set_autostart(True, '/opt/old.AppImage')
        path = Path(linux_desktop.autostart_path())
        with path.open('a', encoding='utf-8') as stream:
            stream.write('X-GNOME-Autostart-Delay=12\nOnlyShowIn=GNOME;\n')
        self.assertTrue(self.sync())
        content = path.read_text(encoding='utf-8')
        self.assertIn('Exec=/opt/new.AppImage', content)
        self.assertNotIn('old.AppImage', content)
        self.assertIn('X-GNOME-Autostart-Delay=12', content)
        self.assertIn('OnlyShowIn=GNOME;', content)

    def test_os_disabled_entry_is_not_reenabled_by_saved_settings(self):
        for marker in ('Hidden=true', 'X-GNOME-Autostart-enabled=false'):
            with self.subTest(marker=marker):
                path = Path(linux_desktop.autostart_path())
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('[Desktop Entry]\nExec=/opt/old.AppImage\n' + marker + '\n', encoding='utf-8')
                previous = path.read_bytes()
                self.assertFalse(self.sync())
                self.assertEqual(path.read_bytes(), previous)
                self.assertFalse(self.window.config['autostart'])
                self.window.config['autostart'] = True

    def test_missing_enabled_entry_is_restored(self):
        self.assertTrue(self.sync())
        self.assertIn('Exec=/opt/new.AppImage', Path(linux_desktop.autostart_path()).read_text())

    def test_missing_disabled_entry_stays_absent(self):
        self.window.config['autostart'] = False
        self.assertFalse(self.sync())
        self.assertFalse(Path(linux_desktop.autostart_path()).exists())

    def test_matching_entry_is_not_rewritten(self):
        linux_desktop.set_autostart(True, '/opt/new.AppImage')
        with mock.patch.object(linux_desktop, '_write_entry') as write:
            self.assertTrue(self.sync())
        write.assert_not_called()

    def test_failed_repair_preserves_existing_entry_and_does_not_stop_startup(self):
        linux_desktop.set_autostart(True, '/opt/old.AppImage')
        path = Path(linux_desktop.autostart_path())
        previous = path.read_bytes()
        import atomic_storage
        with mock.patch.object(atomic_storage.os, 'replace', side_effect=OSError('read-only directory')):
            self.assertTrue(self.sync())
        self.assertEqual(path.read_bytes(), previous)


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
                target = linux_desktop.install_icon(str(ROOT / "src/icons" / "icon.ico"))

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
        from types import SimpleNamespace
        from unittest.mock import Mock
        import main

        window = SimpleNamespace(has_tray=lambda: False,
                                 minimize_to_taskbar=Mock(), hide=Mock())
        main.DarkThemeApp.minimize_to_tray(window)
        window.minimize_to_taskbar.assert_called_once_with()
        window.hide.assert_not_called()

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
