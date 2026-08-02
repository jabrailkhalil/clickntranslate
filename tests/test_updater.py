import os
import shutil
import subprocess
import tempfile
import threading
import types
import unittest
from unittest import mock
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import ocr
import portable_paths
import settings_window as sw
import translater


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


class TestConfigCacheInvalidation(unittest.TestCase):
    def test_uses_already_loaded_main_module(self):
        called = []
        fake_main = types.ModuleType("main")
        fake_main.invalidate_config_cache = lambda: called.append(True)
        sentinel = object()
        old_main = sw.sys.modules.get("main", sentinel)
        sw.sys.modules["main"] = fake_main
        try:
            sw._invalidate_main_config_cache()
        finally:
            if old_main is sentinel:
                sw.sys.modules.pop("main", None)
            else:
                sw.sys.modules["main"] = old_main

        self.assertEqual(called, [True])


class TestPortableLayoutHelpers(unittest.TestCase):
    def test_launcher_layout_uses_parent_as_portable_base(self):
        temp_dir = tempfile.mkdtemp(prefix="cnt_portable_layout_")
        try:
            app_dir = os.path.join(temp_dir, "app")
            os.makedirs(app_dir)
            app_exe = os.path.join(app_dir, "ClicknTranslateApp.exe")
            launcher_exe = os.path.join(temp_dir, "ClicknTranslate.exe")
            open(app_exe, "w").close()
            open(launcher_exe, "w").close()

            with mock.patch.object(sw.sys, "frozen", True, create=True):
                with mock.patch.object(sw.sys, "executable", app_exe):
                    self.assertEqual(portable_paths.portable_base_dir(), temp_dir)
                    self.assertEqual(sw._portable_base_dir(), temp_dir)
                    self.assertEqual(ocr.get_portable_dir(), temp_dir)
                    self.assertEqual(ocr.get_log_dir(), os.path.join(temp_dir, "data", "logs"))
                    self.assertEqual(translater.get_portable_dir(), temp_dir)
                    self.assertEqual(sw._public_executable_path(), launcher_exe)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_standard_frozen_layout_uses_exe_dir(self):
        temp_dir = tempfile.mkdtemp(prefix="cnt_standard_layout_")
        try:
            app_exe = os.path.join(temp_dir, "ClicknTranslate.exe")
            open(app_exe, "w").close()

            with mock.patch.object(sw.sys, "frozen", True, create=True):
                with mock.patch.object(sw.sys, "executable", app_exe):
                    self.assertEqual(sw._portable_base_dir(), temp_dir)
                    self.assertEqual(sw._public_executable_path(), app_exe)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestUpdateProgressDialog(unittest.TestCase):
    def test_update_progress_dialog_supports_update_flow_methods(self):
        app = QApplication.instance() or QApplication([])
        dummy = types.SimpleNamespace(
            parent=types.SimpleNamespace(current_interface_language="en"),
            _update_in_progress=False,
            _handle_update_progress_close_attempt=mock.Mock(),
        )

        dialog = sw.UpdateProgressDialog(dummy)
        dialog.setWindowTitle("Update")
        dialog.setCancelButtonText("Cancel")
        dialog.setLabelText("Checking updates...")
        dialog.setRange(0, 100)
        dialog.setValue(42)
        dialog.show()
        app.processEvents()

        self.assertEqual(dialog.windowTitle(), "Update")
        self.assertIn("Checking", dialog.message_label.text())
        self.assertEqual(dialog.progress_bar.value(), 42)
        self.assertTrue(dialog.windowFlags() & sw.Qt.WindowStaysOnTopHint)
        self.assertTrue(dialog.testAttribute(sw.QtCore.Qt.WA_TranslucentBackground))
        self.assertEqual(dialog.frame.objectName(), "progressDialogFrame")
        dialog.close()

    def test_tesseract_progress_dialog_uses_same_topmost_rounded_frame(self):
        app = QApplication.instance() or QApplication([])
        dummy = types.SimpleNamespace(
            parent=types.SimpleNamespace(current_interface_language="en"),
            _tesseract_install_in_progress=False,
        )

        dialog = sw.TesseractInstallProgressDialog(dummy)
        dialog.setLabelText("Installing...")
        dialog.show()
        app.processEvents()

        self.assertTrue(dialog.windowFlags() & sw.Qt.WindowStaysOnTopHint)
        self.assertTrue(dialog.testAttribute(sw.QtCore.Qt.WA_TranslucentBackground))
        self.assertEqual(dialog.frame.objectName(), "progressDialogFrame")
        dialog.close()

    def test_package_progress_dialog_centers_on_its_owner(self):
        app = QApplication.instance() or QApplication([])
        owner = sw.QWidget()
        owner.setGeometry(180, 120, 640, 520)
        owner.show()
        app.processEvents()
        owner._tesseract_install_in_progress = False
        owner.current_interface_language = "en"

        dialog = sw.TesseractInstallProgressDialog(owner)
        dialog.setLabelText("Installing package...")
        dialog.show()
        app.processEvents()

        owner_center = owner.frameGeometry().center()
        dialog_center = dialog.frameGeometry().center()
        self.assertLessEqual(abs(owner_center.x() - dialog_center.x()), 2)
        self.assertLessEqual(abs(owner_center.y() - dialog_center.y()), 2)
        dialog.close()
        owner.close()


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

    def test_pick_update_asset_ignores_engine_bundles(self):
        dummy = types.SimpleNamespace()
        assets = [
            {
                "name": "ClicknTranslate-tesseract-win64.zip",
                "browser_download_url": "https://example.com/tesseract.zip",
            },
            {
                "name": "ClicknTranslate-v1.3.3-win64.zip",
                "browser_download_url": "https://example.com/app.zip",
            },
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
    def _generate_updater_script(self, app_exe, zip_path):
        fd, script_path = tempfile.mkstemp(prefix="updater_integration_", suffix=".ps1")
        with mock.patch.object(sw.sys, "frozen", True, create=True):
            with mock.patch.object(sw.sys, "executable", app_exe):
                with mock.patch.object(sw.os, "getpid", return_value=2147483000):
                    with mock.patch.object(sw.tempfile, "mkstemp", return_value=(fd, script_path)):
                        with mock.patch.object(sw.subprocess, "Popen"):
                            ok, err = sw.SettingsWindow._launch_zip_updater(
                                types.SimpleNamespace(), zip_path
                            )
        self.assertTrue(ok, err)
        return script_path

    def _run_updater_script(self, script_path, app_dir, zip_path):
        powershell = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"),
            "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
        )
        return subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden",
                "-File", script_path,
                "-AppDir", app_dir,
                "-ZipPath", zip_path,
                "-TargetPid", "2147483000",
                "-ExeName", "ClicknTranslate.exe",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

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
            self.assertIn("AddSeconds(30)", script_text)
            self.assertIn("[int]$TargetPid", script_text)
            self.assertIn("Stop-Process -Id $TargetPid -Force", script_text)
            self.assertIn("Start-Process -FilePath $targetExe -WorkingDirectory $AppDir", script_text)
            self.assertIn("if ($_.Name -ieq \"data\" -or $_.Name -ieq \"ocr\" -or $_.Name -ieq \"translators\") { return }", script_text)
            self.assertNotIn("{ continue }", script_text)
            self.assertIn("Moving existing program item to backup", script_text)
            self.assertIn("Previous version restored after updater failure", script_text)
            self.assertIn("Update payload has neither a flat _internal directory nor app\\ClicknTranslateApp.exe", script_text)
            self.assertIn("Copy-Item -LiteralPath $_.FullName -Destination $AppDir -Recurse -Force", script_text)
            self.assertIn("Update payload copy failed: _internal directory is missing", script_text)
            self.assertIn("Update payload copy failed: launcher app directory is incomplete", script_text)
            self.assertIn("Clear-PyInstallerEnv", script_text)
            self.assertIn("Update archive does not contain $ExeName", script_text)
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

    @unittest.skipUnless(os.name == "nt", "PowerShell updater is Windows-only")
    def test_updater_script_applies_payload_and_preserves_data(self):
        root = tempfile.mkdtemp(prefix="updater_apply_e2e_")
        try:
            app_dir = os.path.join(root, "install")
            os.makedirs(os.path.join(app_dir, "_internal"))
            os.makedirs(os.path.join(app_dir, "data"))
            old_exe = os.path.join(app_dir, "ClicknTranslate.exe")
            system_exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "whoami.exe")
            shutil.copy2(system_exe, old_exe)
            with open(os.path.join(app_dir, "_internal", "old.txt"), "w", encoding="utf-8") as stream:
                stream.write("old")
            with open(os.path.join(app_dir, "data", "marker.txt"), "w", encoding="utf-8") as stream:
                stream.write("preserve")

            zip_path = os.path.join(root, "update.zip")
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(system_exe, "ClicknTranslate/ClicknTranslate.exe")
                archive.writestr("ClicknTranslate/_internal/new.txt", "new")

            script_path = self._generate_updater_script(old_exe, zip_path)
            result = self._run_updater_script(script_path, app_dir, zip_path)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(app_dir, "_internal", "new.txt")))
            self.assertFalse(os.path.exists(os.path.join(app_dir, "_internal", "old.txt")))
            self.assertTrue(os.path.isfile(os.path.join(app_dir, "data", "marker.txt")))
            self.assertFalse(any(name.startswith(".clickntranslate_backup_") for name in os.listdir(root)))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    @unittest.skipUnless(os.name == "nt", "PowerShell updater is Windows-only")
    def test_updater_script_rolls_back_when_new_executable_cannot_start(self):
        root = tempfile.mkdtemp(prefix="updater_rollback_e2e_")
        try:
            app_dir = os.path.join(root, "install")
            os.makedirs(os.path.join(app_dir, "_internal"))
            os.makedirs(os.path.join(app_dir, "data"))
            old_exe = os.path.join(app_dir, "ClicknTranslate.exe")
            system_exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "whoami.exe")
            shutil.copy2(system_exe, old_exe)
            with open(os.path.join(app_dir, "_internal", "old.txt"), "w", encoding="utf-8") as stream:
                stream.write("old")
            with open(os.path.join(app_dir, "data", "marker.txt"), "w", encoding="utf-8") as stream:
                stream.write("preserve")

            zip_path = os.path.join(root, "broken-update.zip")
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("ClicknTranslate/ClicknTranslate.exe", "not a Windows executable")
                archive.writestr("ClicknTranslate/_internal/new.txt", "new")

            script_path = self._generate_updater_script(old_exe, zip_path)
            result = self._run_updater_script(script_path, app_dir, zip_path)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(app_dir, "_internal", "old.txt")))
            self.assertFalse(os.path.exists(os.path.join(app_dir, "_internal", "new.txt")))
            self.assertTrue(os.path.isfile(os.path.join(app_dir, "data", "marker.txt")))
            self.assertEqual(
                sw.SettingsWindow._compute_sha256(types.SimpleNamespace(), old_exe),
                sw.SettingsWindow._compute_sha256(types.SimpleNamespace(), system_exe),
            )
            self.assertFalse(any(name.startswith(".clickntranslate_backup_") for name in os.listdir(root)))
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestUpdateCancellation(unittest.TestCase):
    def test_update_ready_to_restart_uses_nonblocking_progress_dialog(self):
        dummy = types.SimpleNamespace(
            parent=types.SimpleNamespace(current_interface_language="en"),
            _update_in_progress=False,
            _update_phase="applying",
            _update_temp_dir=r"C:\Temp\update",
            _update_cancel_requested=threading.Event(),
        )
        dummy._set_update_controls_enabled = mock.Mock()
        dummy._show_update_progress = mock.Mock()
        dummy._exit_application_for_update_restart = mock.Mock()

        with mock.patch.object(sw.QMessageBox, "information") as info_mock:
            with mock.patch.object(sw.QtCore.QTimer, "singleShot") as timer_mock:
                sw.SettingsWindow._on_update_ready_to_restart(dummy, "1.4.5")

        self.assertTrue(dummy._update_in_progress)
        self.assertEqual(dummy._update_phase, "restarting")
        self.assertEqual(dummy._update_temp_dir, "")
        dummy._set_update_controls_enabled.assert_called_once_with(False, "Restarting...")
        dummy._show_update_progress.assert_called_once()
        info_mock.assert_not_called()
        timer_mock.assert_called_once_with(800, dummy._exit_application_for_update_restart)

    def test_restarting_phase_blocks_progress_close_attempt(self):
        dummy = types.SimpleNamespace(_update_phase="restarting")

        self.assertTrue(sw.SettingsWindow._is_update_apply_stage(dummy))

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

    def test_hide_tesseract_progress_hides_without_closing(self):
        class DummyProgress:
            def __init__(self):
                self.hidden = False
                self.closed = False
                self.blocked = []

            def blockSignals(self, value):
                self.blocked.append(value)

            def hide(self):
                self.hidden = True

            def close(self):
                self.closed = True

        progress = DummyProgress()
        dummy = types.SimpleNamespace(progress=progress)

        sw.SettingsWindow._hide_tesseract_progress(dummy)

        self.assertTrue(progress.hidden)
        self.assertFalse(progress.closed)
        self.assertEqual(progress.blocked, [True, False])


class TestDownloadAndPrepareUpdate(unittest.TestCase):
    def test_download_prepare_success_invokes_restart_flow(self):
        class DummyUpdater:
            def __init__(self):
                self.parent = types.SimpleNamespace(current_interface_language="en")
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
