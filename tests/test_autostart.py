import os
import types
import tempfile
import unittest
from unittest import mock

import main
import platform_support


# The Startup folder shortcut and the MSIX StartupTask are Windows mechanisms;
# Linux autostart lives in linux_desktop and is covered by test_linux_desktop.py.
@unittest.skipUnless(platform_support.IS_WINDOWS, "Windows autostart mechanisms")
class TestStartupShortcutAutostart(unittest.TestCase):
    def test_background_probe_accepts_the_current_shortcut_without_rewriting_it(self):
        current = main._current_autostart_shortcut_info()
        with mock.patch("main._read_autostart_shortcut", return_value=current), \
             mock.patch("main._write_autostart_command") as write:
            enabled = main.DarkThemeApp._probe_portable_windows_autostart(False, None)

        self.assertTrue(enabled)
        write.assert_not_called()

    def test_background_probe_repairs_a_legacy_enabled_configuration(self):
        current = main._current_autostart_shortcut_info()
        with mock.patch(
            "main._read_autostart_shortcut",
            side_effect=[None, current],
        ), mock.patch("main._write_autostart_command") as write:
            enabled = main.DarkThemeApp._probe_portable_windows_autostart(
                True,
                "legacy_registry",
            )

        self.assertTrue(enabled)
        write.assert_called_once_with(True)

    def test_deferred_probe_applies_on_dispatcher_without_blocking_the_caller(self):
        saved = []
        dummy = types.SimpleNamespace(
            _autostart_sync_pending=True,
            _autostart_probe_stored_value=False,
            _autostart_probe_stored_backend=main.AUTOSTART_BACKEND,
            config={"autostart": False, "autostart_backend": main.AUTOSTART_BACKEND},
            autostart=False,
            _probe_portable_windows_autostart=lambda *_args: True,
            save_config=lambda: saved.append(True),
        )

        class ImmediateThread:
            def __init__(self, target, **_kwargs):
                self.target = target

            def start(self):
                self.target()

        dispatcher = types.SimpleNamespace(
            triggered=types.SimpleNamespace(emit=lambda callback: callback())
        )
        with mock.patch("main.threading.Thread", ImmediateThread), mock.patch(
            "main.hotkey_dispatcher",
            dispatcher,
        ):
            main.DarkThemeApp._start_deferred_autostart_sync(dummy)

        self.assertFalse(dummy._autostart_sync_pending)
        self.assertTrue(dummy.autostart)
        self.assertTrue(dummy.config["autostart"])
        self.assertEqual(saved, [True])

    def test_deferred_probe_does_not_overwrite_a_new_user_choice(self):
        saved = []
        dummy = types.SimpleNamespace(
            _autostart_sync_pending=True,
            _autostart_probe_stored_value=False,
            _autostart_probe_stored_backend=main.AUTOSTART_BACKEND,
            config={"autostart": True, "autostart_backend": main.AUTOSTART_BACKEND},
            autostart=True,
            _probe_portable_windows_autostart=lambda *_args: False,
            save_config=lambda: saved.append(True),
        )

        class ImmediateThread:
            def __init__(self, target, **_kwargs):
                self.target = target

            def start(self):
                self.target()

        dispatcher = types.SimpleNamespace(
            triggered=types.SimpleNamespace(emit=lambda callback: callback())
        )
        with mock.patch("main.threading.Thread", ImmediateThread), mock.patch(
            "main.hotkey_dispatcher",
            dispatcher,
        ):
            main.DarkThemeApp._start_deferred_autostart_sync(dummy)

        self.assertTrue(dummy.autostart)
        self.assertTrue(dummy.config["autostart"])
        self.assertEqual(saved, [])

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
