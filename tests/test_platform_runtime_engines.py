import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import platform_support  # noqa: E402


class PythonInstallHintTest(unittest.TestCase):
    def test_debian_hint_names_the_versioned_package(self):
        with mock.patch.object(platform_support.shutil, "which", side_effect=lambda name: "/usr/bin/apt-get" if name == "apt-get" else None):
            hint = platform_support.python_install_hint("3.12")

        self.assertIn("apt install python3.12", hint)

    def test_fedora_hint_is_used_when_dnf_is_present(self):
        with mock.patch.object(platform_support.shutil, "which", side_effect=lambda name: "/usr/bin/dnf" if name == "dnf" else None):
            self.assertIn("dnf install python3.12", platform_support.python_install_hint("3.12"))

    def test_suse_hint_drops_the_dot(self):
        with mock.patch.object(platform_support.shutil, "which", side_effect=lambda name: "/usr/bin/zypper" if name == "zypper" else None):
            self.assertIn("python312", platform_support.python_install_hint("3.12"))

    def test_unknown_package_manager_still_produces_a_command(self):
        with mock.patch.object(platform_support.shutil, "which", return_value=None):
            self.assertIn("python3.12", platform_support.python_install_hint("3.12"))


class RuntimeEngineInstallerTest(unittest.TestCase):
    """The optional OCR engines need an interpreter matching the frozen build."""

    def setUp(self):
        self.source = (ROOT / "settings_window.py").read_text(encoding="utf-8")

    def test_versioned_interpreter_is_probed_before_the_generic_one(self):
        start = self.source.index("def _find_rapidocr_install_python_command")
        body = self.source[start:start + 1200]

        self.assertIn('f"python{required}"', body)
        self.assertLess(body.index('f"python{required}"'), body.index('"python3"'))

    def test_linux_failure_points_at_the_package_manager(self):
        start = self.source.index("def _find_rapidocr_install_python_command")
        body = self.source[start:start + 2500]

        self.assertIn("platform_support.IS_LINUX", body)
        self.assertIn("platform_support.python_install_hint(required)", body)

    def test_windows_only_python_bootstrap_is_refused_on_linux(self):
        start = self.source.index("def _portable_pip_bootstrap_plan")
        body = self.source[start:start + 900]

        self.assertIn("platform_support.IS_LINUX", body)
        self.assertLess(body.index("IS_LINUX"), body.index("EASYOCR_PYTHON_ARCHIVE"))


if __name__ == "__main__":
    unittest.main()
