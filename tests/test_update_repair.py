import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import hashlib
import zipfile


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "The update repair tool is Windows-only")
class TestUpdateRepair(unittest.TestCase):
    def test_repair_installs_full_package_and_keeps_user_data(self):
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        self.assertIsNotNone(powershell)
        system_exe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "whoami.exe"

        with tempfile.TemporaryDirectory(prefix="update_repair_e2e_") as temporary:
            temporary_path = Path(temporary)
            build_path = temporary_path / "ClicknTranslate-Update-Repair.exe"
            package_path = temporary_path / "ClicknTranslate-v1.4.7-win64.zip"
            install_root = temporary_path / "ClicknTranslate"
            inner_root = install_root / "app"
            data_root = install_root / "data"
            inner_root.mkdir(parents=True)
            data_root.mkdir()

            payload_root = temporary_path / "payload" / "ClicknTranslate"
            (payload_root / "app").mkdir(parents=True)
            shutil.copy2(system_exe, payload_root / "ClicknTranslate.exe")
            shutil.copy2(system_exe, payload_root / "app" / "ClicknTranslateApp.exe")
            (payload_root / "README.md").write_text("new package", encoding="utf-8")
            with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for item in payload_root.rglob("*"):
                    if item.is_file():
                        archive.write(item, item.relative_to(payload_root.parent))
            package_sha256 = hashlib.sha256(package_path.read_bytes()).hexdigest()

            build = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "tools" / "build_update_repair.ps1"),
                    "-Version",
                    "1.4.7.0",
                    "-OutputPath",
                    str(build_path),
                    "-PackageUrl",
                    package_path.as_uri(),
                    "-PackageSha256",
                    package_sha256,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(build.returncode, 0, build.stderr)

            launcher_path = install_root / "ClicknTranslate.exe"
            shutil.copy2(system_exe, launcher_path)
            shutil.copy2(system_exe, inner_root / "ClicknTranslateApp.exe")
            shutil.copy2(system_exe, install_root / "unins000.exe")
            (install_root / "unins000.dat").write_text("uninstall metadata", encoding="utf-8")
            (data_root / "config.json").write_text("settings", encoding="utf-8")
            ocr_root = install_root / "ocr"
            translator_root = install_root / "translators"
            ocr_root.mkdir()
            translator_root.mkdir()
            (ocr_root / "language.bin").write_text("ocr package", encoding="utf-8")
            (translator_root / "model.bin").write_text("translation model", encoding="utf-8")
            (install_root / "README.md").write_text("old package", encoding="utf-8")
            repair_path = install_root / build_path.name
            shutil.copy2(build_path, repair_path)

            repaired = subprocess.run(
                [str(repair_path), "/silent"],
                cwd=install_root,
                capture_output=True,
                timeout=15,
            )

            self.assertEqual(repaired.returncode, 0)
            self.assertEqual(launcher_path.read_bytes(), system_exe.read_bytes())
            self.assertEqual((data_root / "config.json").read_text(encoding="utf-8"), "settings")
            self.assertEqual((ocr_root / "language.bin").read_text(encoding="utf-8"), "ocr package")
            self.assertEqual(
                (translator_root / "model.bin").read_text(encoding="utf-8"),
                "translation model",
            )
            self.assertEqual(
                (install_root / "unins000.dat").read_text(encoding="utf-8"),
                "uninstall metadata",
            )
            self.assertTrue((install_root / "unins000.exe").is_file())
            self.assertEqual((install_root / "README.md").read_text(encoding="utf-8"), "new package")
            self.assertTrue(repair_path.is_file())
            self.assertFalse(list(temporary_path.glob(".clickntranslate_repair_backup_*")))
            self.assertTrue(launcher_path.read_bytes().startswith(b"MZ"))

    def test_release_repair_uses_pinned_https_package(self):
        source = (ROOT / "tools" / "build_update_repair.ps1").read_text(encoding="utf-8")
        repair_source = (ROOT / "launcher" / "ClicknTranslateUpdateRepair.cs").read_text(encoding="utf-8")
        repair_manifest = (ROOT / "launcher" / "ClicknTranslateUpdateRepair.manifest").read_text(encoding="utf-8")
        self.assertIn("https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.4.7/", source)
        self.assertIn("37C0BDF4B88BBB3DF0E12C838BDA517E5F3FF4C1032A7AA88642DC6C5EFEEF0E", source)
        self.assertIn("ClicknTranslateUpdateRepair.manifest", source)
        self.assertIn('level="requireAdministrator"', repair_manifest)
        self.assertIn('Verb = "runas"', repair_source)
        self.assertIn("CanWriteInstallRoot(installRoot)", repair_source)

    def test_checksum_failure_leaves_installed_version_untouched(self):
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        self.assertIsNotNone(powershell)
        system_exe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "whoami.exe"

        with tempfile.TemporaryDirectory(prefix="update_repair_checksum_") as temporary:
            temporary_path = Path(temporary)
            install_root = temporary_path / "ClicknTranslate"
            (install_root / "app").mkdir(parents=True)
            shutil.copy2(system_exe, install_root / "ClicknTranslate.exe")
            shutil.copy2(system_exe, install_root / "app" / "ClicknTranslateApp.exe")
            (install_root / "data").mkdir()
            (install_root / "data" / "config.json").write_text("keep me", encoding="utf-8")

            package_path = temporary_path / "invalid.zip"
            package_path.write_bytes(b"not a trusted update")
            repair_path = install_root / "ClicknTranslate-Update-Repair.exe"
            build = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "tools" / "build_update_repair.ps1"),
                    "-Version",
                    "1.4.7.0",
                    "-OutputPath",
                    str(repair_path),
                    "-PackageUrl",
                    package_path.as_uri(),
                    "-PackageSha256",
                    "0" * 64,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(build.returncode, 0, build.stderr)

            launcher_before = (install_root / "ClicknTranslate.exe").read_bytes()
            repaired = subprocess.run([str(repair_path), "/silent"], timeout=15)

            self.assertEqual(repaired.returncode, 1)
            self.assertEqual((install_root / "ClicknTranslate.exe").read_bytes(), launcher_before)
            self.assertEqual(
                (install_root / "data" / "config.json").read_text(encoding="utf-8"),
                "keep me",
            )


if __name__ == "__main__":
    unittest.main()
