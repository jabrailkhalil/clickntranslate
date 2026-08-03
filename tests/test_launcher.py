import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestLauncher(unittest.TestCase):
    def test_launcher_uses_install_root_as_child_working_directory(self):
        source = (ROOT / "launcher" / "ClicknTranslateLauncher.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("WorkingDirectory = root", source)
        self.assertIn("UseShellExecute = false", source)
        self.assertNotIn("WorkingDirectory = Path.GetDirectoryName(innerExecutable)", source)

    @unittest.skipUnless(os.name == "nt", "The release launcher is Windows-only")
    def test_built_launcher_runs_child_from_root_and_recovers_installer_files(self):
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        self.assertIsNotNone(powershell)

        with tempfile.TemporaryDirectory(prefix="launcher_e2e_") as temporary:
            temporary_path = Path(temporary)
            install_root = temporary_path / "ClicknTranslate"
            inner_dir = install_root / "app"
            backup_dir = temporary_path / ".clickntranslate_backup_launcher_test"
            inner_dir.mkdir(parents=True)
            backup_dir.mkdir()

            launcher_path = install_root / "ClicknTranslate.exe"
            build = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "tools" / "build_launcher.ps1"),
                    "-Version",
                    "1.4.7.0",
                    "-OutputPath",
                    str(launcher_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(build.returncode, 0, build.stderr)

            shutil.copy2(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"), inner_dir / "ClicknTranslateApp.exe")
            (backup_dir / "unins000.dat").write_text("metadata", encoding="utf-8")
            shutil.copy2(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"), backup_dir / "unins000.exe")

            marker = install_root / "working-directory.txt"
            launch = subprocess.run(
                [str(launcher_path), "/d", "/c", f"cd>{marker}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(launch.returncode, 0, launch.stderr)

            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.05)

            self.assertTrue(marker.exists(), "The launcher did not start the inner executable")
            self.assertEqual(
                os.path.normcase(marker.read_text(encoding="utf-8").strip()),
                os.path.normcase(str(install_root)),
            )
            self.assertEqual((install_root / "unins000.dat").read_text(encoding="utf-8"), "metadata")
            self.assertTrue((install_root / "unins000.exe").is_file())


if __name__ == "__main__":
    unittest.main()
