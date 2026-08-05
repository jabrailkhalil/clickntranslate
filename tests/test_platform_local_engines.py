import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import platform_support  # noqa: E402
import translater  # noqa: E402


class HymtRunnerNameTest(unittest.TestCase):
    def test_runner_names_carry_the_platform_suffix(self):
        names = translater.hymt_runner_names()

        self.assertIn(platform_support.executable_name("llama-cli").lower(), names)
        if platform_support.IS_WINDOWS:
            self.assertTrue(all(name.endswith(".exe") for name in names))
        else:
            self.assertFalse(any(name.endswith(".exe") for name in names))

    def test_runner_is_found_by_its_platform_name(self):
        with tempfile.TemporaryDirectory() as root:
            runner = os.path.join(root, platform_support.executable_name("llama-cli"))
            with open(runner, "wb") as handle:
                handle.write(b"binary")

            self.assertEqual(translater._find_hymt_runner_under(root), runner)

    def test_runner_is_found_in_a_nested_folder(self):
        with tempfile.TemporaryDirectory() as root:
            nested = os.path.join(root, "build", "bin")
            os.makedirs(nested)
            runner = os.path.join(nested, platform_support.executable_name("llama-cli"))
            with open(runner, "wb") as handle:
                handle.write(b"binary")

            self.assertEqual(translater._find_hymt_runner_under(root), runner)

    def test_a_foreign_platform_binary_is_not_accepted(self):
        """A Windows .exe in the folder must not be offered to a Linux runtime."""
        if platform_support.IS_WINDOWS:
            self.skipTest("checks the non-Windows runner list")
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "llama-cli.exe"), "wb") as handle:
                handle.write(b"pe binary")

            self.assertEqual(translater._find_hymt_runner_under(root), "")


class HymtInstallPolicyTest(unittest.TestCase):
    def test_download_plan_is_windows_only(self):
        source = (ROOT / "settings_window.py").read_text(encoding="utf-8")
        plan_at = source.index("def _get_hymt_download_plan")
        body = source[plan_at:plan_at + 1400]

        self.assertIn("if not platform_support.IS_WINDOWS:", body)
        # The guard must come before the pinned Windows archive is returned.
        self.assertLess(body.index("IS_WINDOWS"), body.index("HYMT_RUNTIME_URL_WIN64"))

    def test_engine_selection_explains_manual_setup_off_windows(self):
        source = (ROOT / "settings_window.py").read_text(encoding="utf-8")
        handler_at = source.index("def _on_translator_changed")
        body = source[handler_at:handler_at + 1500]

        self.assertIn("_show_manual_hymt_hint", body)
        self.assertLess(body.index("_show_manual_hymt_hint"), body.index("hymt_prompt"))


if __name__ == "__main__":
    unittest.main()
