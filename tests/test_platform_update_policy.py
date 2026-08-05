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
    """Self-replacement is Windows-only; other systems only announce a version."""

    def test_only_windows_replaces_itself(self):
        self.assertEqual(platform_support.supports_in_app_update(), platform_support.IS_WINDOWS)

    def test_download_path_is_guarded_by_the_policy(self):
        source = (ROOT / "settings_window.py").read_text(encoding="utf-8")
        guard = "if status == \"ready\" and not platform_support.supports_in_app_update():"
        self.assertIn(guard, source)
        # The guard has to come before the branch that starts a download.
        self.assertLess(source.index(guard), source.index("self._start_update_download(asset_url"))

    def test_linux_offers_the_release_page_instead(self):
        source = (ROOT / "settings_window.py").read_text(encoding="utf-8")
        guard_at = source.index("if status == \"ready\" and not platform_support.supports_in_app_update():")
        block = source[guard_at:guard_at + 1200]
        self.assertIn("webbrowser.open(GITHUB_RELEASES_PAGE)", block)

    def test_linux_build_does_not_ship_the_windows_update_helpers(self):
        spec = (ROOT / "ClicknTranslate-linux.spec").read_text(encoding="utf-8")
        # Helper executables and the PE-only EXE() arguments (a prose mention in
        # the spec's own docstring is fine, an actual argument is not).
        for windows_only in ("ClicknTranslateUpdater", "ApplyUpdate", "manifest=", "icon=["):
            self.assertNotIn(windows_only, spec, windows_only)


if __name__ == "__main__":
    unittest.main()
