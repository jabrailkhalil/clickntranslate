import os
import types
import tempfile
import unittest
import uuid
from unittest import mock

import main
import platform_support


# The Startup folder shortcut and the MSIX StartupTask are Windows mechanisms;
# Linux autostart lives in linux_desktop and is covered by test_linux_desktop.py.
@unittest.skipUnless(platform_support.IS_WINDOWS, "Windows autostart mechanisms")
class TestStartupShortcutAutostart(unittest.TestCase):
    def setUp(self):
        import winreg

        self.winreg = winreg
        # Exercise real registry operations without touching the user's Run key.
        self.registry_path = rf"Software\ClicknTranslateAutostartTest-{uuid.uuid4().hex}"
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.registry_path).Close()
        self.addCleanup(winreg.DeleteKey, winreg.HKEY_CURRENT_USER, self.registry_path)
        registry_patch = mock.patch("main.LEGACY_AUTOSTART_RUN_KEY", self.registry_path)
        registry_patch.start()
        self.addCleanup(registry_patch.stop)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        environment_patch = mock.patch.dict(os.environ, {"APPDATA": self.temp_dir.name})
        environment_patch.start()
        self.addCleanup(environment_patch.stop)

    def put_run_value(self, name=main.LEGACY_AUTOSTART_RUN_VALUE):
        with self.winreg.OpenKey(
            self.winreg.HKEY_CURRENT_USER, self.registry_path, 0, self.winreg.KEY_SET_VALUE
        ) as key:
            self.winreg.SetValueEx(key, name, 0, self.winreg.REG_SZ, r'"C:\Old App\ClicknTranslate.exe"')

    def assert_legacy_removed(self):
        with self.winreg.OpenKey(self.winreg.HKEY_CURRENT_USER, self.registry_path) as key:
            with self.assertRaises(FileNotFoundError):
                self.winreg.QueryValueEx(key, main.LEGACY_AUTOSTART_RUN_VALUE)

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
        self.put_run_value()
        enabled = main.DarkThemeApp.sync_autostart_state(dummy, repair_stale=True)

        self.assertTrue(enabled)
        self.assertTrue(main._autostart_shortcut_matches_current(main._read_autostart_shortcut()))
        self.assert_legacy_removed()
        self.assertEqual(dummy.config["autostart_backend"], main.AUTOSTART_BACKEND)

    def test_existing_shortcut_removes_duplicate_run_value_without_rewriting(self):
        main._write_autostart_shortcut()
        self.put_run_value()
        self.put_run_value("AnotherApp")
        shortcut_path = main._autostart_shortcut_path()
        original_mtime = os.stat(shortcut_path).st_mtime_ns

        enabled = main.DarkThemeApp._probe_portable_windows_autostart(True, main.AUTOSTART_BACKEND)

        self.assertTrue(enabled)
        self.assert_legacy_removed()
        self.assertEqual(os.stat(shortcut_path).st_mtime_ns, original_mtime)
        with self.winreg.OpenKey(self.winreg.HKEY_CURRENT_USER, self.registry_path) as key:
            self.assertTrue(self.winreg.QueryValueEx(key, "AnotherApp")[0])

    def test_registry_only_installation_is_migrated_without_saved_config(self):
        self.put_run_value()

        enabled = main.DarkThemeApp._probe_portable_windows_autostart(False, None)

        self.assertTrue(enabled)
        self.assert_legacy_removed()
        self.assertTrue(main._autostart_shortcut_matches_current(main._read_autostart_shortcut()))

    def test_explicit_off_state_does_not_reenable_a_leftover_run_entry(self):
        self.put_run_value()

        enabled = main.DarkThemeApp._probe_portable_windows_autostart(False, main.AUTOSTART_BACKEND)

        self.assertFalse(enabled)
        self.assert_legacy_removed()
        self.assertFalse(os.path.exists(main._autostart_shortcut_path()))

    def test_enable_and_disable_remove_legacy_entry_idempotently(self):
        self.put_run_value()
        main._write_autostart_command(True)
        self.assert_legacy_removed()
        self.assertTrue(os.path.exists(main._autostart_shortcut_path()))

        self.put_run_value()
        main._write_autostart_command(False)
        main._write_autostart_command(False)
        self.assert_legacy_removed()
        self.assertFalse(os.path.exists(main._autostart_shortcut_path()))

    def test_failed_shortcut_creation_preserves_legacy_autostart(self):
        self.put_run_value()
        with mock.patch("main._write_autostart_shortcut", side_effect=PermissionError("read-only Startup")):
            with self.assertRaises(PermissionError):
                main._write_autostart_command(True)
        self.assertTrue(main._read_legacy_autostart_command())

    def test_failed_legacy_removal_rolls_back_new_shortcut(self):
        self.put_run_value()
        with mock.patch("main._remove_legacy_autostart_command", side_effect=PermissionError("read-only Run")):
            with self.assertRaises(PermissionError):
                main._write_autostart_command(True)
        self.assertTrue(main._read_legacy_autostart_command())
        self.assertFalse(os.path.exists(main._autostart_shortcut_path()))

    def test_failed_shortcut_removal_reports_error_and_keeps_enabled_state(self):
        dummy = types.SimpleNamespace(config={"autostart": True}, autostart=True)
        with mock.patch("main.os.remove", side_effect=PermissionError("shortcut is locked")):
            enabled = main.DarkThemeApp.set_autostart(dummy, False)
        self.assertTrue(enabled)
        self.assertIn("shortcut is locked", dummy._autostart_error)

    def test_deferred_migration_does_not_run_after_user_disables_autostart(self):
        pending = []
        probe = mock.Mock(return_value=True)
        dummy = types.SimpleNamespace(
            _autostart_sync_pending=True,
            config={"autostart": True},
            autostart=True,
            _probe_portable_windows_autostart=probe,
        )

        class DeferredThread:
            def __init__(self, target, **_kwargs):
                pending.append(target)

            def start(self):
                pass

        with mock.patch("main.threading.Thread", DeferredThread):
            main.DarkThemeApp._start_deferred_autostart_sync(dummy)
        main.DarkThemeApp.set_autostart(dummy, False)
        pending[0]()

        probe.assert_not_called()
        self.assertFalse(dummy.autostart)
        self.assertFalse(os.path.exists(main._autostart_shortcut_path()))

    def test_late_probe_result_does_not_undo_off_then_on_choice(self):
        callbacks = []
        dummy = types.SimpleNamespace(
            _autostart_sync_pending=True,
            config={"autostart": True},
            autostart=True,
            _probe_portable_windows_autostart=lambda *_args: False,
            save_config=mock.Mock(),
        )

        class ImmediateThread:
            def __init__(self, target, **_kwargs):
                self.target = target

            def start(self):
                self.target()

        dispatcher = types.SimpleNamespace(triggered=types.SimpleNamespace(emit=callbacks.append))
        with mock.patch("main.threading.Thread", ImmediateThread), mock.patch("main.hotkey_dispatcher", dispatcher):
            main.DarkThemeApp._start_deferred_autostart_sync(dummy)
        with mock.patch("main._write_autostart_command"), mock.patch(
            "main._read_autostart_shortcut", side_effect=[None, main._current_autostart_shortcut_info()]
        ):
            main.DarkThemeApp.set_autostart(dummy, False)
            main.DarkThemeApp.set_autostart(dummy, True)
        callbacks[0]()

        self.assertTrue(dummy.autostart)
        self.assertTrue(dummy.config["autostart"])
        dummy.save_config.assert_not_called()

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
