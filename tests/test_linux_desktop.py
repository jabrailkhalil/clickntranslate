import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import linux_desktop  # noqa: E402
import platform_support  # noqa: E402


class DesktopEntryTest(unittest.TestCase):
    def test_entry_has_the_keys_a_launcher_needs(self):
        text = linux_desktop.desktop_entry_text("/opt/clickntranslate")

        self.assertTrue(text.startswith("[Desktop Entry]"))
        for key in ("Type=Application", "Name=", "Exec=/opt/clickntranslate", "Icon=clickntranslate", "Terminal=false"):
            self.assertIn(key, text)

        self.assertIn("GenericName=Screen translator", text)
        self.assertIn("Categories=Utility;Qt;", text)
        self.assertIn("Keywords=translation;translator;OCR;screen;capture;text;", text)

    def test_paths_with_spaces_are_quoted(self):
        text = linux_desktop.desktop_entry_text("/home/a b/clickntranslate")
        self.assertIn('Exec="/home/a b/clickntranslate"', text)

    def test_actions_cover_the_capture_commands(self):
        text = linux_desktop.desktop_entry_text("/opt/clickntranslate")

        self.assertIn("Actions=Toggle;Capture;Copy;Translate;Fullscreen;Game;", text)
        self.assertIn("Exec=/opt/clickntranslate --toggle", text)
        self.assertIn("[Desktop Action Capture]", text)
        self.assertIn("Exec=/opt/clickntranslate --ocr", text)
        self.assertIn("Exec=/opt/clickntranslate --fullscreen", text)
        self.assertIn("Exec=/opt/clickntranslate --game", text)

    def test_every_action_maps_to_a_real_shortcut_action(self):
        for _name, _label, action in linux_desktop.DESKTOP_ACTIONS:
            self.assertIn(action, platform_support.SHORTCUT_ACTIONS)

    def test_autostart_entry_is_marked_for_gnome_and_has_no_actions(self):
        text = linux_desktop.desktop_entry_text("/opt/clickntranslate", autostart=True, include_actions=False)

        self.assertIn("X-GNOME-Autostart-enabled=true", text)
        self.assertNotIn("[Desktop Action", text)

    def test_newlines_cannot_break_out_of_a_value(self):
        text = linux_desktop.desktop_entry_text("/opt/app\nExec=/usr/bin/evil")
        exec_lines = [line for line in text.splitlines() if line.startswith("Exec=")]
        self.assertTrue(all("evil" not in line or line.count("=") >= 2 for line in exec_lines))
        self.assertEqual(len([line for line in text.splitlines() if line == "Exec=/usr/bin/evil"]), 0)


class AutostartTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="cnt_xdg_")
        patcher = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_enabling_writes_an_entry_and_disabling_removes_it(self):
        self.assertFalse(linux_desktop.autostart_enabled())

        self.assertTrue(linux_desktop.set_autostart(True, "/opt/clickntranslate"))
        self.assertTrue(linux_desktop.autostart_enabled())
        self.assertTrue(os.path.isfile(linux_desktop.autostart_path()))

        self.assertFalse(linux_desktop.set_autostart(False, "/opt/clickntranslate"))
        self.assertFalse(linux_desktop.autostart_enabled())

    def test_autostart_entry_lands_in_the_xdg_autostart_directory(self):
        linux_desktop.set_autostart(True, "/opt/clickntranslate")
        self.assertEqual(
            linux_desktop.autostart_path(),
            os.path.join(self.temp_dir, "autostart", platform_support.DESKTOP_ENTRY_NAME),
        )

    def test_enabling_twice_is_harmless(self):
        self.assertTrue(linux_desktop.set_autostart(True, "/opt/clickntranslate"))
        self.assertTrue(linux_desktop.set_autostart(True, "/opt/clickntranslate"))
        self.assertTrue(linux_desktop.autostart_enabled())

    def test_enabling_migrates_the_old_short_name(self):
        os.makedirs(platform_support.autostart_dir(), exist_ok=True)
        legacy = os.path.join(
            platform_support.autostart_dir(),
            linux_desktop.LEGACY_DESKTOP_ENTRY_NAME,
        )
        with open(legacy, "w", encoding="utf-8") as handle:
            handle.write("[Desktop Entry]\n")

        self.assertTrue(linux_desktop.autostart_enabled())
        self.assertTrue(linux_desktop.set_autostart(True, "/opt/clickntranslate"))
        self.assertFalse(os.path.exists(legacy))
        self.assertTrue(os.path.isfile(linux_desktop.autostart_path()))

    def test_disabling_when_absent_is_harmless(self):
        self.assertFalse(linux_desktop.set_autostart(False, "/opt/clickntranslate"))

    def test_entry_records_the_executable_it_was_given(self):
        linux_desktop.set_autostart(True, "/opt/some/clickntranslate")
        with open(linux_desktop.autostart_path(), encoding="utf-8") as handle:
            self.assertIn("Exec=/opt/some/clickntranslate", handle.read())


class ApplicationEntryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="cnt_xdgdata_")
        patcher = mock.patch.dict(os.environ, {"XDG_DATA_HOME": self.temp_dir}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_install_writes_the_menu_entry(self):
        path = linux_desktop.install_desktop_entry("/opt/clickntranslate")

        self.assertTrue(os.path.isfile(path))
        self.assertEqual(path, os.path.join(self.temp_dir, "applications", platform_support.DESKTOP_ENTRY_NAME))

    def test_install_removes_the_legacy_menu_entry(self):
        applications = os.path.join(self.temp_dir, "applications")
        os.makedirs(applications, exist_ok=True)
        legacy = os.path.join(applications, linux_desktop.LEGACY_DESKTOP_ENTRY_NAME)
        with open(legacy, "w", encoding="utf-8") as handle:
            handle.write("[Desktop Entry]\n")

        linux_desktop.install_desktop_entry("/opt/clickntranslate")

        self.assertFalse(os.path.exists(legacy))
        self.assertTrue(os.path.isfile(linux_desktop.application_entry_path()))

    def test_icon_is_copied_into_the_hicolor_theme(self):
        source = os.path.join(self.temp_dir, "icon.png")
        with open(source, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\n")

        target = linux_desktop.install_icon(source)

        self.assertTrue(os.path.isfile(target))
        self.assertTrue(target.endswith(os.path.join("hicolor", "256x256", "apps", "clickntranslate.png")))

    def test_remove_clears_both_entries(self):
        linux_desktop.install_desktop_entry("/opt/clickntranslate")
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir}, clear=False):
            linux_desktop.set_autostart(True, "/opt/clickntranslate")
            linux_desktop.remove_desktop_entry()

            self.assertFalse(os.path.exists(linux_desktop.application_entry_path()))
            self.assertFalse(os.path.exists(linux_desktop.autostart_path()))


if __name__ == "__main__":
    unittest.main()
