import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "The update repair tool is Windows-only")
class TestUpdateRepair(unittest.TestCase):
    def test_repair_replaces_only_launcher_and_keeps_install_data(self):
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        self.assertIsNotNone(powershell)
        system_exe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "whoami.exe"

        with tempfile.TemporaryDirectory(prefix="update_repair_e2e_") as temporary:
            temporary_path = Path(temporary)
            build_path = temporary_path / "ClicknTranslate-Update-Repair.exe"
            install_root = temporary_path / "ClicknTranslate"
            inner_root = install_root / "app"
            data_root = install_root / "data"
            inner_root.mkdir(parents=True)
            data_root.mkdir()

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
            repair_path = install_root / build_path.name
            shutil.copy2(build_path, repair_path)

            old_launcher = launcher_path.read_bytes()
            repaired = subprocess.run(
                [str(repair_path), "/silent"],
                cwd=install_root,
                capture_output=True,
                timeout=15,
            )

            self.assertEqual(repaired.returncode, 0)
            self.assertNotEqual(launcher_path.read_bytes(), old_launcher)
            self.assertEqual(
                (install_root / "ClicknTranslate.exe.update-backup").read_bytes(),
                old_launcher,
            )
            self.assertEqual((data_root / "config.json").read_text(encoding="utf-8"), "settings")
            self.assertEqual(
                (install_root / "unins000.dat").read_text(encoding="utf-8"),
                "uninstall metadata",
            )
            self.assertTrue((install_root / "unins000.exe").is_file())
            self.assertGreater(launcher_path.stat().st_size, 32768)
            self.assertTrue(launcher_path.read_bytes().startswith(b"MZ"))


if __name__ == "__main__":
    unittest.main()
