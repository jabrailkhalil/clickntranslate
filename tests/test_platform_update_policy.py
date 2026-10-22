import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import platform_support  # noqa: E402


class UpdatePolicyTest(unittest.TestCase):
    """Only an owned packaged installation may replace itself."""

    def test_windows_keeps_its_verified_update_helper(self):
        with mock.patch.object(platform_support, "IS_WINDOWS", True):
            self.assertTrue(platform_support.supports_in_app_update())

    def test_portable_posix_install_can_update_but_managed_install_cannot(self):
        with mock.patch.object(platform_support, "IS_WINDOWS", False):
            for target, expected in ((None, False), (("macos", Path("/Applications/App.app")), True),
                                     (("appimage", Path("/home/me/app.AppImage")), True)):
                with mock.patch("posix_update.update_target", return_value=target):
                    self.assertEqual(platform_support.supports_in_app_update(), expected)

    def test_linux_build_does_not_ship_the_windows_update_helpers(self):
        spec = (ROOT / "tools/packaging/ClicknTranslate-linux.spec").read_text(encoding="utf-8")
        # Helper executables and the PE-only EXE() arguments (a prose mention in
        # the spec's own docstring is fine, an actual argument is not).
        for windows_only in ("ClicknTranslateUpdater", "ApplyUpdate", "manifest=", "icon=["):
            self.assertNotIn(windows_only, spec, windows_only)


if __name__ == "__main__":
    unittest.main()
