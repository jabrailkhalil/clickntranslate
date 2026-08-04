import os
import shutil
import subprocess
import tempfile
import threading
import types
import unittest
from unittest import mock
import zipfile
from pathlib import Path

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

    def test_internal_worker_uses_application_root_for_portable_data(self):
        temp_dir = tempfile.mkdtemp(prefix="cnt_internal_worker_layout_")
        try:
            internal_dir = os.path.join(temp_dir, "_internal")
            os.makedirs(internal_dir)
            worker_exe = os.path.join(internal_dir, "OcrWorker.exe")
            app_exe = os.path.join(temp_dir, "ClicknTranslate.exe")
            open(worker_exe, "w").close()
            open(app_exe, "w").close()

            with mock.patch.object(sw.sys, "frozen", True, create=True):
                with mock.patch.object(sw.sys, "executable", worker_exe):
                    self.assertEqual(portable_paths.portable_base_dir(), temp_dir)
                    self.assertEqual(portable_paths.public_executable_path(), app_exe)
                    self.assertEqual(ocr.get_portable_dir(), temp_dir)
                    self.assertEqual(translater.get_portable_dir(), temp_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_store_layout_uses_package_local_state(self):
        with tempfile.TemporaryDirectory(prefix="cnt_store_layout_") as local_app_data:
            family = "JabrailDigital.ClicknTranslate_test123"
            with mock.patch.dict(
                os.environ,
                {
                    portable_paths.PACKAGE_MODE_ENV: "1",
                    portable_paths.PACKAGE_FAMILY_ENV: family,
                    "LOCALAPPDATA": local_app_data,
                },
                clear=False,
            ):
                expected = os.path.join(
                    local_app_data,
                    "Packages",
                    family,
                    "LocalState",
                )
                self.assertTrue(portable_paths.is_windows_packaged())
                self.assertEqual(portable_paths.portable_base_dir(), expected)
                self.assertEqual(sw._portable_base_dir(), expected)
                self.assertEqual(ocr.get_portable_dir(), expected)
                self.assertEqual(translater.get_portable_dir(), expected)


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
    def test_release_1_4_7_detects_1_5_0_portable_update(self):
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "tag_name": "v1.5.0",
            "assets": [
                {
                    "name": "ClicknTranslate-Setup-v1.5.0-win64.exe",
                    "browser_download_url": "https://example.com/setup.exe",
                },
                {
                    "name": "ClicknTranslate-v1.5.0-win64.zip",
                    "browser_download_url": "https://example.com/app.zip",
                },
                {
                    "name": "ClicknTranslate-v1.5.0-win64.zip.sha256",
                    "browser_download_url": "https://example.com/app.zip.sha256",
                },
            ],
        }
        posted = []
        dummy = types.SimpleNamespace(
            parent=types.SimpleNamespace(current_interface_language="en"),
            _update_cancel_requested=threading.Event(),
            _post_update_check_result=posted.append,
        )
        dummy._pick_update_asset = types.MethodType(sw.SettingsWindow._pick_update_asset, dummy)
        dummy._pick_checksum_url = types.MethodType(sw.SettingsWindow._pick_checksum_url, dummy)

        with mock.patch("settings_window.APP_VERSION", "1.4.7"), mock.patch(
            "settings_window.requests.get", return_value=response
        ) as get_mock:
            sw.SettingsWindow._check_latest_release_worker(dummy)

        self.assertEqual(
            posted,
            [
                {
                    "status": "ready",
                    "latest_version": "1.5.0",
                    "asset_name": "ClicknTranslate-v1.5.0-win64.zip",
                    "asset_url": "https://example.com/app.zip",
                    "checksum_url": "https://example.com/app.zip.sha256",
                }
            ],
        )
        self.assertEqual(
            get_mock.call_args.kwargs["headers"]["User-Agent"],
            "ClicknTranslate/1.4.7",
        )
        self.assertNotIn("Authorization", get_mock.call_args.kwargs["headers"])

    def test_private_update_feed_uses_environment_url_and_bearer_token(self):
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"tag_name": "v1.5.3", "assets": []}
        posted = []
        dummy = types.SimpleNamespace(
            parent=types.SimpleNamespace(current_interface_language="en"),
            _update_cancel_requested=threading.Event(),
            _post_update_check_result=posted.append,
        )
        dummy._pick_update_asset = types.MethodType(sw.SettingsWindow._pick_update_asset, dummy)
        dummy._pick_checksum_url = types.MethodType(sw.SettingsWindow._pick_checksum_url, dummy)
        private_api = "https://api.github.com/repos/example/private-update-lab/releases/latest"

        with mock.patch.dict(
            os.environ,
            {
                sw.UPDATE_API_ENV: private_api,
                sw.UPDATE_TOKEN_ENV: "test-token-not-committed",
            },
        ), mock.patch("settings_window.requests.get", return_value=response) as get_mock:
            sw.SettingsWindow._check_latest_release_worker(dummy)

        self.assertEqual(get_mock.call_args.args[0], private_api)
        self.assertEqual(
            get_mock.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-token-not-committed",
        )
        self.assertEqual(posted[0]["status"], "no_asset")

    def test_update_token_is_not_sent_to_non_github_downloads(self):
        with mock.patch.dict(os.environ, {sw.UPDATE_TOKEN_ENV: "secret-test-token"}):
            github_headers = sw._update_request_headers(
                "https://github.com/example/private/releases/download/v1/app.zip"
            )
            external_headers = sw._update_request_headers(
                "https://huggingface.co/example/model.bin"
            )

        self.assertEqual(github_headers["Authorization"], "Bearer secret-test-token")
        self.assertNotIn("Authorization", external_headers)

    def test_private_asset_uses_authenticated_api_download_url(self):
        asset = {
            "url": "https://api.github.com/repos/example/private/releases/assets/123",
            "browser_download_url": "https://github.com/example/private/releases/download/v1/app.zip",
        }
        with mock.patch.dict(os.environ, {sw.UPDATE_TOKEN_ENV: "secret-test-token"}):
            selected_url = sw._update_asset_download_url(asset)
            headers = sw._update_request_headers(selected_url)

        self.assertEqual(selected_url, asset["url"])
        self.assertEqual(headers["Authorization"], "Bearer secret-test-token")
        self.assertEqual(headers["Accept"], "application/octet-stream")

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

    def test_installed_copy_prefers_setup_executable(self):
        assets = [
            {
                "name": "ClicknTranslate-v1.5.2-win64.zip",
                "browser_download_url": "https://example.com/portable.zip",
            },
            {
                "name": "ClicknTranslate-Setup-v1.5.2-win64.exe",
                "browser_download_url": "https://example.com/setup.exe",
            },
        ]

        with mock.patch("settings_window._is_inno_installed_copy", return_value=True):
            selected = sw.SettingsWindow._pick_update_asset(types.SimpleNamespace(), assets)

        self.assertEqual(selected["name"], "ClicknTranslate-Setup-v1.5.2-win64.exe")

    def test_installed_copy_prefers_full_installer_over_legacy_setup_bridge(self):
        assets = [
            {
                "name": "ClicknTranslate-Setup-v1.5.2-win64.exe",
                "browser_download_url": "https://example.com/bridge.exe",
            },
            {
                "name": "Click-n-Translate-1.5.2-windows-x64-installer.exe",
                "browser_download_url": "https://example.com/full.exe",
            },
        ]

        with mock.patch("settings_window._is_inno_installed_copy", return_value=True):
            selected = sw.SettingsWindow._pick_update_asset(types.SimpleNamespace(), assets)

        self.assertEqual(
            selected["name"],
            "Click-n-Translate-1.5.2-windows-x64-installer.exe",
        )

    def test_portable_copy_ignores_legacy_bootstrap_asset(self):
        assets = [
            {
                "name": "ClicknTranslate-v1.5.2-win64-portable-bootstrap.zip",
                "browser_download_url": "https://example.com/bootstrap.zip",
            },
            {
                "name": "ClicknTranslate-v1.5.2-win64.zip",
                "browser_download_url": "https://example.com/portable.zip",
            },
        ]

        with mock.patch("settings_window._is_inno_installed_copy", return_value=False):
            selected = sw.SettingsWindow._pick_update_asset(types.SimpleNamespace(), assets)

        self.assertEqual(selected["name"], "ClicknTranslate-v1.5.2-win64.zip")

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

    def test_store_package_never_launches_github_zip_updater(self):
        with mock.patch("settings_window.portable_paths.is_windows_packaged", return_value=True):
            ok, error = sw.SettingsWindow._launch_zip_updater(
                types.SimpleNamespace(),
                r"C:\Temp\ClicknTranslate-v1.5.0-win64.zip",
            )

        self.assertFalse(ok)
        self.assertIn("Microsoft Store", error)

    def _run_updater_script(self, script_path, app_dir, zip_path, cwd=None):
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
            cwd=cwd,
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
            self.assertEqual(popen_mock.call_args.kwargs["cwd"], tempfile.gettempdir())

            with open(script_path, "r", encoding="utf-8") as f:
                script_text = f.read()

            self.assertIn("clickntranslate_update.log", script_text)
            self.assertIn("AddSeconds(30)", script_text)
            self.assertIn("[int]$TargetPid", script_text)
            self.assertIn("taskkill.exe /PID $TargetPid /T /F", script_text)
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
            self.assertIn("Set-Location -LiteralPath ([System.IO.Path]::GetTempPath())", script_text)
            self.assertIn("Move-UpdateItemWithRetry", script_text)
            self.assertIn("Get-DescendantProcessIds", script_text)
            self.assertIn("Stop-InstallProcesses", script_text)
            self.assertIn("^unins\\d*\\.(exe|dat|msg)$", script_text)
            self.assertIn("Update archive does not contain $ExeName", script_text)
            self.assertIn("-TargetPid", popen_mock.call_args.args[0])
        finally:
            try:
                os.remove(script_path)
            except OSError:
                pass

    def test_installed_updater_runs_inno_setup_with_restart_manager(self):
        fd, script_path = tempfile.mkstemp(prefix="setup_updater_test_", suffix=".ps1")
        try:
            with mock.patch.object(sw.sys, "frozen", True, create=True), mock.patch(
                "settings_window._is_inno_installed_copy", return_value=True
            ), mock.patch(
                "settings_window._portable_base_dir", return_value=r"C:\Apps\ClicknTranslate"
            ), mock.patch(
                "settings_window._public_executable_path",
                return_value=r"C:\Apps\ClicknTranslate\ClicknTranslate.exe",
            ), mock.patch.object(
                sw.os, "getpid", return_value=1234
            ), mock.patch.object(
                sw.tempfile, "mkstemp", return_value=(fd, script_path)
            ), mock.patch.object(
                sw.SettingsWindow, "_install_dir_requires_elevation", return_value=False
            ), mock.patch.object(
                sw.SettingsWindow, "_launch_hidden_powershell_script", return_value=(True, None)
            ) as launch_mock:
                ok, error = sw.SettingsWindow._launch_setup_updater(
                    types.SimpleNamespace(),
                    r"C:\Temp\ClicknTranslate-Setup-v1.5.2-win64.exe",
                    "1.5.2",
                )

            self.assertTrue(ok, error)
            script_text = Path(script_path).read_text(encoding="utf-8")
            self.assertIn("Starting Inno Setup with Windows Restart Manager", script_text)
            self.assertEqual(script_text.count("function Clear-PyInstallerEnv {"), 1)
            self.assertIn('"/CLOSEAPPLICATIONS"', script_text)
            self.assertIn('"/FORCECLOSEAPPLICATIONS"', script_text)
            self.assertIn('"/LOGCLOSEAPPLICATIONS"', script_text)
            self.assertIn("Installed version $fileVersion does not match expected version", script_text)
            launch_mock.assert_called_once()
            arguments = launch_mock.call_args.args[2]
            self.assertIn("-ExpectedVersion", arguments)
            self.assertIn("1.5.2", arguments)
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

    def test_install_dir_permission_probe_requests_elevation_on_access_denied(self):
        with tempfile.TemporaryDirectory(prefix="updater_permission_probe_") as app_dir:
            with mock.patch("settings_window.os.open", side_effect=PermissionError(13, "denied")):
                requires_elevation = sw.SettingsWindow._install_dir_requires_elevation(
                    types.SimpleNamespace(), app_dir
                )
        self.assertTrue(requires_elevation)

    def test_hidden_powershell_uses_run_as_path_when_elevation_is_required(self):
        dummy = types.SimpleNamespace()
        with mock.patch.object(
            sw.SettingsWindow,
            "_powershell_launch_candidates",
            return_value=["powershell.exe"],
        ), mock.patch.object(
            sw.SettingsWindow,
            "_launch_elevated_process",
            return_value=(True, None),
        ) as elevated_mock, mock.patch("settings_window.subprocess.Popen") as popen_mock:
            ok, error = sw.SettingsWindow._launch_hidden_powershell_script(
                dummy,
                r"C:\Temp\updater.ps1",
                ["-AppDir", r"C:\Program Files\ClicknTranslate"],
                elevated=True,
            )

        self.assertTrue(ok, error)
        popen_mock.assert_not_called()
        elevated_mock.assert_called_once()
        self.assertIn("-File", elevated_mock.call_args.args[2])
        self.assertIn(r"C:\Temp\updater.ps1", elevated_mock.call_args.args[2])

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
    def test_updater_uses_external_cwd_and_preserves_installer_metadata(self):
        root = tempfile.mkdtemp(prefix="updater_launcher_cwd_e2e_")
        try:
            app_dir = os.path.join(root, "install")
            inner_dir = os.path.join(app_dir, "app")
            os.makedirs(os.path.join(inner_dir, "_internal"))
            os.makedirs(os.path.join(app_dir, "data"))
            system_exe = os.path.join(
                os.environ.get("SystemRoot", r"C:\Windows"),
                "System32",
                "whoami.exe",
            )
            old_exe = os.path.join(app_dir, "ClicknTranslate.exe")
            shutil.copy2(system_exe, old_exe)
            shutil.copy2(system_exe, os.path.join(inner_dir, "ClicknTranslateApp.exe"))
            with open(os.path.join(inner_dir, "_internal", "old.txt"), "w", encoding="utf-8") as stream:
                stream.write("old")
            with open(os.path.join(app_dir, "data", "marker.txt"), "w", encoding="utf-8") as stream:
                stream.write("preserve")
            with open(os.path.join(app_dir, "unins000.dat"), "w", encoding="utf-8") as stream:
                stream.write("installer metadata")
            shutil.copy2(system_exe, os.path.join(app_dir, "unins000.exe"))

            zip_path = os.path.join(root, "update.zip")
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(system_exe, "ClicknTranslate/ClicknTranslate.exe")
                archive.write(system_exe, "ClicknTranslate/app/ClicknTranslateApp.exe")
                archive.writestr("ClicknTranslate/app/_internal/new.txt", "new")

            script_path = self._generate_updater_script(old_exe, zip_path)
            result = self._run_updater_script(
                script_path,
                app_dir,
                zip_path,
                # This is the critical regression guard. PowerShell must be
                # created outside ``app``; changing directory from inside an
                # already-created PowerShell process does not release every
                # Windows directory handle reliably.
                cwd=tempfile.gettempdir(),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(inner_dir, "_internal", "new.txt")))
            self.assertFalse(os.path.exists(os.path.join(inner_dir, "_internal", "old.txt")))
            self.assertTrue(os.path.isfile(os.path.join(app_dir, "data", "marker.txt")))
            self.assertTrue(os.path.isfile(os.path.join(app_dir, "unins000.exe")))
            self.assertEqual(
                Path(os.path.join(app_dir, "unins000.dat")).read_text(encoding="utf-8"),
                "installer metadata",
            )
            self.assertFalse(any(name.startswith(".clickntranslate_backup_") for name in os.listdir(root)))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    @unittest.skipUnless(os.name == "nt", "PowerShell updater is Windows-only")
    def test_updater_stops_locked_worker_before_replacing_install(self):
        root = tempfile.mkdtemp(prefix="updater_locked_worker_e2e_")
        blocker = None
        try:
            app_dir = os.path.join(root, "install")
            inner_dir = os.path.join(app_dir, "app")
            os.makedirs(os.path.join(inner_dir, "_internal"))
            os.makedirs(os.path.join(app_dir, "data"))
            system_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
            system_exe = os.path.join(system_dir, "whoami.exe")
            command_exe = os.path.join(system_dir, "cmd.exe")
            old_exe = os.path.join(app_dir, "ClicknTranslate.exe")
            worker_exe = os.path.join(inner_dir, "_internal", "OcrWorker.exe")
            shutil.copy2(system_exe, old_exe)
            shutil.copy2(system_exe, os.path.join(inner_dir, "ClicknTranslateApp.exe"))
            shutil.copy2(command_exe, worker_exe)
            with open(os.path.join(inner_dir, "_internal", "old.txt"), "w", encoding="utf-8") as stream:
                stream.write("old")
            with open(os.path.join(app_dir, "data", "marker.txt"), "w", encoding="utf-8") as stream:
                stream.write("preserve")

            blocker = subprocess.Popen(
                [worker_exe, "/d", "/c", "ping.exe -n 120 127.0.0.1 >nul"],
                cwd=app_dir,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            zip_path = os.path.join(root, "update.zip")
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(system_exe, "ClicknTranslate/ClicknTranslate.exe")
                archive.write(system_exe, "ClicknTranslate/app/ClicknTranslateApp.exe")
                archive.writestr("ClicknTranslate/app/_internal/new.txt", "new")

            script_path = self._generate_updater_script(old_exe, zip_path)
            result = self._run_updater_script(
                script_path,
                app_dir,
                zip_path,
                cwd=tempfile.gettempdir(),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(inner_dir, "_internal", "new.txt")))
            self.assertFalse(os.path.exists(os.path.join(inner_dir, "_internal", "old.txt")))
            self.assertTrue(os.path.isfile(os.path.join(app_dir, "data", "marker.txt")))
            self.assertIsNotNone(blocker.poll(), "Locked OCR worker was left running")
        finally:
            if blocker is not None and blocker.poll() is None:
                subprocess.run(
                    ["taskkill.exe", "/PID", str(blocker.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
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

            def _launch_apply_updater(self, _package_path, package_kind, version):
                self.apply_call = (package_kind, version)
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
        self.assertEqual(dummy.apply_call, (".zip", "1.3.4"))
        self.assertIn("_on_update_ready_to_restart", invoke_calls)

    def test_installed_copy_downloads_and_launches_setup_package(self):
        class DummyUpdater:
            def __init__(self):
                self.parent = types.SimpleNamespace(current_interface_language="en")
                self._update_cancel_requested = threading.Event()
                self._update_phase = "idle"
                self._update_temp_dir = ""
                self.apply_calls = []

            def _download_file(self, _url, destination_path, timeout=120, progress_callback=None, cancel_callback=None):
                Path(destination_path).write_bytes(b"MZ" + b"setup")
                if progress_callback:
                    progress_callback(7, 7)

            def _check_update_cancel_requested(self):
                return None

            def _launch_apply_updater(self, setup_path, package_kind, version):
                self.apply_calls.append((setup_path, package_kind, version))
                return True, None

            def _cleanup_update_temp_dir(self):
                return None

        dummy = DummyUpdater()
        invoke_calls = []

        with mock.patch("settings_window._is_inno_installed_copy", return_value=True), mock.patch.object(
            sw.QMetaObject, "invokeMethod", side_effect=lambda _obj, method_name, *_args: invoke_calls.append(method_name) or True
        ), mock.patch.object(sw.QtCore, "Q_ARG", side_effect=lambda _t, value: value):
            sw.SettingsWindow._download_and_prepare_update(
                dummy,
                "https://example.com/setup.exe",
                "ClicknTranslate-Setup-v1.5.2-win64.exe",
                "1.5.2",
            )

        self.assertEqual(len(dummy.apply_calls), 1)
        self.assertTrue(dummy.apply_calls[0][0].endswith(".exe"))
        self.assertEqual(dummy.apply_calls[0][1:], (".exe", "1.5.2"))
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

            def _launch_apply_updater(self, _package_path, _package_kind, _version):
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
