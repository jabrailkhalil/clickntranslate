import os
import types
import tempfile
import unittest
from unittest import mock

import main


class TestStartupShortcutAutostart(unittest.TestCase):
    def test_autostart_shortcut_lifecycle_uses_startup_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(os.environ, {"APPDATA": temp_dir}):
                shortcut_path = main._autostart_shortcut_path()

                self.assertFalse(os.path.exists(shortcut_path))
                main._write_autostart_command(True)

                self.assertTrue(os.path.exists(shortcut_path))
                self.assertTrue(
                    main._autostart_shortcut_matches_current(
                        main._read_autostart_shortcut()
                    )
                )

                main._write_autostart_command(False)
                self.assertFalse(os.path.exists(shortcut_path))

    def test_stale_shortcut_does_not_match_current_command(self):
        stale = {
            "target": r"C:\OldClicknTranslate\ClicknTranslate.exe",
            "arguments": "",
            "working_dir": r"C:\OldClicknTranslate",
        }

        self.assertFalse(main._autostart_shortcut_matches_current(stale))

    def test_legacy_config_autostart_is_migrated_to_startup_shortcut(self):
        dummy = types.SimpleNamespace(config={"autostart": True}, autostart=False)
        calls = []

        def fake_set_autostart(enable):
            calls.append(enable)
            dummy.autostart = bool(enable)
            dummy.config["autostart"] = bool(enable)
            return bool(enable)

        dummy.set_autostart = fake_set_autostart

        with mock.patch("main._read_autostart_shortcut", return_value=None):
            enabled = main.DarkThemeApp.sync_autostart_state(dummy, repair_stale=True)

        self.assertTrue(enabled)
        self.assertEqual(calls, [True])
        self.assertEqual(dummy.config["autostart_backend"], main.AUTOSTART_BACKEND)

    def test_store_autostart_uses_manifest_startup_task(self):
        dummy = types.SimpleNamespace(
            config={"autostart": False},
            autostart=False,
        )

        with mock.patch("main.portable_paths.is_windows_packaged", return_value=True):
            with mock.patch("main._write_store_autostart_state", return_value=True) as write:
                enabled = main.DarkThemeApp.set_autostart(dummy, True)

        self.assertTrue(enabled)
        self.assertEqual(dummy.config["autostart_backend"], main.AUTOSTART_BACKEND)
        write.assert_called_once_with(True)

    def test_store_autostart_sync_does_not_touch_startup_shortcut(self):
        dummy = types.SimpleNamespace(config={"autostart": False}, autostart=False)

        with mock.patch("main.portable_paths.is_windows_packaged", return_value=True):
            with mock.patch("main._read_store_autostart_state", return_value=True):
                with mock.patch("main._read_autostart_shortcut") as read_shortcut:
                    enabled = main.DarkThemeApp.sync_autostart_state(dummy, repair_stale=True)

        self.assertTrue(enabled)
        read_shortcut.assert_not_called()


if __name__ == "__main__":
    unittest.main()
