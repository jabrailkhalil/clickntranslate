import os
import tempfile
import types
import unittest
from unittest import mock
import zipfile

import settings_window as sw


class TestVersionHelpers(unittest.TestCase):
    def test_normalize_version(self):
        self.assertEqual(sw._normalize_version("v1.3.3"), "1.3.3")
        self.assertEqual(sw._normalize_version("1.3.3"), "1.3.3")
        self.assertEqual(sw._normalize_version(""), "0")

    def test_is_newer_version(self):
        self.assertTrue(sw._is_newer_version("1.3.4", "1.3.3"))
        self.assertTrue(sw._is_newer_version("v2.0.0", "1.9.9"))
        self.assertFalse(sw._is_newer_version("1.3.3", "1.3.3"))
        self.assertFalse(sw._is_newer_version("1.3.2", "1.3.3"))


class TestUpdateAssetSelection(unittest.TestCase):
    def test_pick_update_asset_prefers_windows_clickntranslate_zip(self):
        dummy = types.SimpleNamespace()
        assets = [
            {"name": "notes.txt", "browser_download_url": "https://example.com/notes.txt"},
            {"name": "tool-linux.zip", "browser_download_url": "https://example.com/linux.zip"},
            {"name": "ClicknTranslate-v1.3.3-win64.zip", "browser_download_url": "https://example.com/win.zip"},
        ]
        selected = sw.SettingsWindow._pick_update_asset(dummy, assets)
        self.assertIsNotNone(selected)
        self.assertEqual(selected["name"], "ClicknTranslate-v1.3.3-win64.zip")

    def test_pick_checksum_url_matches_expected_name(self):
        dummy = types.SimpleNamespace()
        assets = [
            {
                "name": "ClicknTranslate-v1.3.3-win64.zip.sha256",
                "browser_download_url": "https://example.com/win.zip.sha256",
            },
            {"name": "other.sha256", "browser_download_url": "https://example.com/other.sha256"},
        ]
        checksum_url = sw.SettingsWindow._pick_checksum_url(
            dummy,
            assets,
            "ClicknTranslate-v1.3.3-win64.zip",
        )
        self.assertEqual(checksum_url, "https://example.com/win.zip.sha256")


class TestUpdaterCommands(unittest.TestCase):
    def test_schedule_update_restart_fallback_builds_expected_cmd(self):
        dummy = types.SimpleNamespace()
        with mock.patch.object(sw.sys, "executable", r"C:\Apps\ClicknTranslate.exe"):
            with mock.patch.object(sw.os.path, "isfile", return_value=True):
                with mock.patch.object(sw.subprocess, "Popen") as popen_mock:
                    sw.SettingsWindow._schedule_update_restart_fallback(dummy, delay_seconds=4)

        popen_mock.assert_called_once()
        args, kwargs = popen_mock.call_args
        self.assertEqual(args[0][0:2], ["cmd", "/c"])
        self.assertIn('start "" "C:\\Apps\\ClicknTranslate.exe"', args[0][2])
        self.assertIn("ping -n 4", args[0][2])
        self.assertIn("creationflags", kwargs)

    def test_launch_zip_updater_generates_expected_script(self):
        dummy = types.SimpleNamespace()
        fd, script_path = tempfile.mkstemp(prefix="updater_test_", suffix=".ps1")
        try:
            with mock.patch.object(sw.sys, "frozen", True, create=True):
                with mock.patch.object(sw.sys, "executable", r"C:\Apps\ClicknTranslate.exe"):
                    with mock.patch.object(sw.os, "getpid", return_value=1234):
                        with mock.patch.object(sw.tempfile, "mkstemp", return_value=(fd, script_path)):
                            with mock.patch.object(sw.subprocess, "Popen") as popen_mock:
                                ok, err = sw.SettingsWindow._launch_zip_updater(
                                    dummy, r"C:\Temp\ClicknTranslate-v1.3.4-win64.zip"
                                )

            self.assertTrue(ok)
            self.assertIsNone(err)
            popen_mock.assert_called_once()

            with open(script_path, "r", encoding="utf-8") as f:
                script_text = f.read()

            self.assertIn("clickntranslate_update.log", script_text)
            self.assertIn("Stop-Process -Id $Pid -Force", script_text)
            self.assertIn("Start-Process -FilePath $targetExe -WorkingDirectory $AppDir", script_text)
            self.assertIn("if ($_.Name -ieq \"data\") { continue }", script_text)
        finally:
            try:
                os.remove(script_path)
            except OSError:
                pass

    def test_launch_zip_updater_rejects_non_frozen(self):
        dummy = types.SimpleNamespace()
        with mock.patch.object(sw.sys, "frozen", False, create=True):
            ok, err = sw.SettingsWindow._launch_zip_updater(dummy, r"C:\Temp\update.zip")
        self.assertFalse(ok)
        self.assertIn("packaged app", err)


class TestDownloadAndPrepareUpdate(unittest.TestCase):
    def test_download_prepare_success_invokes_restart_flow(self):
        class DummyUpdater:
            def __init__(self):
                self.fallback_called = False
                self.download_calls = 0

            def _download_file(self, _url, destination_path, timeout=120, progress_callback=None):
                self.download_calls += 1
                with zipfile.ZipFile(destination_path, "w") as zf:
                    zf.writestr("ClicknTranslate.exe", b"exe")
                if progress_callback:
                    progress_callback(1, 1)

            def _launch_zip_updater(self, _zip_path):
                return True, None

            def _schedule_update_restart_fallback(self):
                self.fallback_called = True

        dummy = DummyUpdater()
        invoke_calls = []

        def fake_invoke(_obj, method_name, *_args):
            invoke_calls.append(method_name)
            return True

        with mock.patch.object(sw.QMetaObject, "invokeMethod", side_effect=fake_invoke):
            with mock.patch.object(sw.QtCore, "Q_ARG", side_effect=lambda _t, v: v):
                sw.SettingsWindow._download_and_prepare_update(
                    dummy,
                    "https://example.com/update.zip",
                    "ClicknTranslate-v1.3.4-win64.zip",
                    "1.3.4",
                )

        self.assertEqual(dummy.download_calls, 1)
        self.assertTrue(dummy.fallback_called)
        self.assertIn("_on_update_ready_to_restart", invoke_calls)

    def test_download_prepare_failure_reports_error(self):
        class DummyUpdater:
            def _download_file(self, _url, destination_path, timeout=120, progress_callback=None):
                with zipfile.ZipFile(destination_path, "w") as zf:
                    zf.writestr("ClicknTranslate.exe", b"exe")
                if progress_callback:
                    progress_callback(1, 1)

            def _launch_zip_updater(self, _zip_path):
                return False, "Updater launch failed"

            def _schedule_update_restart_fallback(self):
                raise AssertionError("Fallback should not run when updater launch fails")

        dummy = DummyUpdater()
        invoke_calls = []

        def fake_invoke(_obj, method_name, *_args):
            invoke_calls.append(method_name)
            return True

        with mock.patch.object(sw.QMetaObject, "invokeMethod", side_effect=fake_invoke):
            with mock.patch.object(sw.QtCore, "Q_ARG", side_effect=lambda _t, v: v):
                sw.SettingsWindow._download_and_prepare_update(
                    dummy,
                    "https://example.com/update.zip",
                    "ClicknTranslate-v1.3.4-win64.zip",
                    "1.3.4",
                )

        self.assertIn("_on_update_failed", invoke_calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
