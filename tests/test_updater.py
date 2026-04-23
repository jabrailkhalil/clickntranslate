import os
import shutil
import tempfile
import threading
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
    def test_schedule_update_restart_fallback_builds_expected_powershell_script(self):
        dummy = types.SimpleNamespace()
        generated_script = None
        with mock.patch.object(sw.sys, "executable", r"C:\Apps\ClicknTranslate.exe"):
            with mock.patch.object(sw.os.path, "isfile", return_value=True):
                with mock.patch.object(sw.os, "getpid", return_value=999):
                    with mock.patch.object(sw.tempfile, "mkstemp", return_value=tempfile.mkstemp(prefix="restart_fallback_", suffix=".ps1")):
                        with mock.patch.object(sw.subprocess, "Popen") as popen_mock:
                            sw.SettingsWindow._schedule_update_restart_fallback(dummy, delay_seconds=6, attempts=5, interval_seconds=2)

        popen_mock.assert_called_once()
        args, kwargs = popen_mock.call_args
        self.assertIn("-File", args[0])
        self.assertIn("-TargetPid", args[0])
        generated_script = args[0][args[0].index("-File") + 1]
        self.assertTrue(generated_script.lower().endswith(".ps1"))

        with open(generated_script, "r", encoding="utf-8") as f:
            script_text = f.read()

        self.assertIn("[string]$ExePath", script_text)
        self.assertIn("[int]$TargetPid", script_text)
        self.assertIn("Get-Process -Id $TargetPid", script_text)
        self.assertIn("Start-Process -FilePath $ExePath -WorkingDirectory $ExeDir", script_text)
        self.assertIn("creationflags", kwargs)
        try:
            os.remove(generated_script)
        except OSError:
            pass

    def test_schedule_update_restart_fallback_skips_missing_exe(self):
        dummy = types.SimpleNamespace()
        with mock.patch.object(sw.sys, "executable", r"C:\Apps\Missing.exe"):
            with mock.patch.object(sw.os.path, "isfile", return_value=False):
                with mock.patch.object(sw.subprocess, "Popen") as popen_mock:
                    sw.SettingsWindow._schedule_update_restart_fallback(dummy)
        popen_mock.assert_not_called()

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
            self.assertIn("[int]$TargetPid", script_text)
            self.assertIn("Stop-Process -Id $TargetPid -Force", script_text)
            self.assertIn("Start-Process -FilePath $targetExe -WorkingDirectory $AppDir", script_text)
            self.assertIn("if ($_.Name -ieq \"data\") { continue }", script_text)
            self.assertIn("-TargetPid", popen_mock.call_args.args[0])
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


class TestUpdateCancellation(unittest.TestCase):
    def test_handle_update_progress_close_attempt_requests_cancel_before_apply(self):
        dummy = types.SimpleNamespace(
            parent=types.SimpleNamespace(current_interface_language="ru"),
            _update_in_progress=True,
            _update_phase="downloading",
            _update_cancel_requested=threading.Event(),
        )
        dummy._show_update_progress = mock.Mock()
        dummy._set_update_controls_enabled = mock.Mock()
        dummy._is_update_apply_stage = lambda: False

        sw.SettingsWindow._handle_update_progress_close_attempt(dummy)

        self.assertTrue(dummy._update_cancel_requested.is_set())
        dummy._set_update_controls_enabled.assert_called_once_with(False, "Отмена...")
        dummy._show_update_progress.assert_called_once()

    def test_handle_update_progress_close_attempt_blocks_during_apply(self):
        dummy = types.SimpleNamespace(
            parent=types.SimpleNamespace(current_interface_language="en"),
            _update_in_progress=True,
            _update_phase="applying",
            _update_cancel_requested=threading.Event(),
        )
        dummy._show_update_progress = mock.Mock()
        dummy._set_update_controls_enabled = mock.Mock()
        dummy._is_update_apply_stage = lambda: True

        with mock.patch.object(sw.QMessageBox, "information") as info_mock:
            sw.SettingsWindow._handle_update_progress_close_attempt(dummy)

        self.assertFalse(dummy._update_cancel_requested.is_set())
        dummy._set_update_controls_enabled.assert_not_called()
        dummy._show_update_progress.assert_called_once()
        info_mock.assert_called_once()

    def test_download_file_cancellation_raises(self):
        class FakeResponse:
            headers = {"Content-Length": "4"}

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size=1024 * 1024):
                yield b"test"

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        dummy = types.SimpleNamespace()
        fd, temp_path = tempfile.mkstemp(prefix="cancel_update_", suffix=".bin")
        os.close(fd)
        try:
            with mock.patch.object(sw.requests, "get", return_value=FakeResponse()):
                with self.assertRaises(sw.UpdateCancelledError):
                    sw.SettingsWindow._download_file(
                        dummy,
                        "https://example.com/update.zip",
                        temp_path,
                        cancel_callback=lambda: True,
                    )
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass


class TestTesseractInstallerHelpers(unittest.TestCase):
    def test_get_tesseract_bundle_url_uses_release_asset(self):
        dummy = types.SimpleNamespace()

        url = sw.SettingsWindow._get_tesseract_bundle_url(dummy, is_x64=True)

        self.assertIn("/releases/download/v1.3.2/", url)
        self.assertTrue(url.endswith("ClicknTranslate-tesseract-win64.zip"))

    def test_find_tesseract_exe_under_searches_recursively(self):
        dummy = types.SimpleNamespace()
        root = tempfile.mkdtemp(prefix="tess_find_")
        try:
            nested = os.path.join(root, "bin")
            os.makedirs(nested, exist_ok=True)
            exe_path = os.path.join(nested, "tesseract.exe")
            with open(exe_path, "wb") as f:
                f.write(b"exe")

            found = sw.SettingsWindow._find_tesseract_exe_under(dummy, root)

            self.assertEqual(found, exe_path)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_check_tesseract_cancel_requested_raises(self):
        dummy = types.SimpleNamespace(_tesseract_cancel_requested=threading.Event())
        dummy._tesseract_cancel_requested.set()

        with self.assertRaises(sw.TesseractInstallCancelledError):
            sw.SettingsWindow._check_tesseract_cancel_requested(dummy)


class TestDownloadAndPrepareUpdate(unittest.TestCase):
    def test_download_prepare_success_invokes_restart_flow(self):
        class DummyUpdater:
            def __init__(self):
                self.parent = types.SimpleNamespace(current_interface_language="en")
                self.fallback_called = False
                self.download_calls = 0
                self._update_cancel_requested = threading.Event()
                self._update_phase = "idle"
                self._update_temp_dir = ""

            def _download_file(self, _url, destination_path, timeout=120, progress_callback=None, cancel_callback=None):
                self.download_calls += 1
                with zipfile.ZipFile(destination_path, "w") as zf:
                    zf.writestr("ClicknTranslate.exe", b"exe")
                if progress_callback:
                    progress_callback(1, 1)

            def _check_update_cancel_requested(self):
                return None

            def _launch_zip_updater(self, _zip_path):
                return True, None

            def _schedule_update_restart_fallback(self):
                self.fallback_called = True

            def _cleanup_update_temp_dir(self):
                return None

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
            def __init__(self):
                self.parent = types.SimpleNamespace(current_interface_language="en")
                self._update_cancel_requested = threading.Event()
                self._update_phase = "idle"
                self._update_temp_dir = ""

            def _download_file(self, _url, destination_path, timeout=120, progress_callback=None, cancel_callback=None):
                with zipfile.ZipFile(destination_path, "w") as zf:
                    zf.writestr("ClicknTranslate.exe", b"exe")
                if progress_callback:
                    progress_callback(1, 1)

            def _check_update_cancel_requested(self):
                return None

            def _launch_zip_updater(self, _zip_path):
                return False, "Updater launch failed"

            def _schedule_update_restart_fallback(self):
                raise AssertionError("Fallback should not run when updater launch fails")

            def _cleanup_update_temp_dir(self):
                return None

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
