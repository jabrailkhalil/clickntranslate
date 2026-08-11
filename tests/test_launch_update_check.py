"""The start-up check must be quiet unless it has something to offer.

It runs once per launch, says nothing when the app is current, never offers a
version the user skipped, and never runs where updating is not ours to do — a
dev checkout or a Microsoft Store install.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication  # noqa: E402

import main  # noqa: E402
from app_version import APP_VERSION  # noqa: E402
from settings_window import update_text  # noqa: E402

LANGUAGES = ("en", "ru", "es", "de", "fr", "zh")


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _App:
    """Just enough of the window for the check: it touches config, the signal
    and the interface language, nothing else."""

    def __init__(self, config=None):
        self.config = dict(main.DEFAULT_CONFIG)
        self.config.update(config or {})
        self.current_interface_language = "en"
        self.saved = 0
        self.emitted = []
        self._launch_update_signal = mock.Mock()
        self._launch_update_signal.emit = self.emitted.append

    def save_config(self):
        self.saved += 1

    _maybe_check_updates_on_launch = main.DarkThemeApp._maybe_check_updates_on_launch
    _launch_update_worker = main.DarkThemeApp._launch_update_worker


class LaunchUpdateCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _run_worker(self, tag):
        app = _App()
        with mock.patch("requests.get", return_value=_Response({"tag_name": tag})) as get:
            app._launch_update_worker()
        return app, get

    def test_a_newer_release_is_reported(self):
        app, get = self._run_worker("v99.9.9")
        self.assertEqual(app.emitted, ["99.9.9"])
        self.assertEqual(get.call_count, 1)

    def test_the_current_version_says_nothing(self):
        app, _get = self._run_worker(f"v{APP_VERSION}")
        self.assertEqual(app.emitted, [])

    def test_an_older_release_says_nothing(self):
        app, _get = self._run_worker("v0.0.1")
        self.assertEqual(app.emitted, [])

    def test_a_failed_check_is_swallowed(self):
        app = _App()
        with mock.patch("requests.get", side_effect=OSError("no network")):
            app._launch_update_worker()  # must not raise
        self.assertEqual(app.emitted, [])

    def test_it_only_reads_the_feed(self):
        """The check asks for the release JSON. It does not pull the release
        itself: a download nobody asked for costs the user bandwidth and would
        report a download that never happened."""
        app, get = self._run_worker("v99.9.9")
        url = get.call_args[0][0]
        self.assertIn("api.github.com", url)
        self.assertNotIn("/releases/download/", url)
        self.assertNotIn("/zipball", url)
        self.assertNotIn("/tarball", url)


class LaunchCheckGatesTest(unittest.TestCase):
    """Which builds are allowed to run it at all."""

    def _thread_starts(self, frozen=True, packaged=False, config=None):
        app = _App(config)
        app._launch_update_checked = False
        started = []
        with mock.patch.object(main.threading, "Thread") as thread, \
             mock.patch.object(main.portable_paths, "is_windows_packaged", return_value=packaged), \
             mock.patch.object(main.sys, "frozen", frozen, create=True):
            thread.side_effect = lambda *a, **k: started.append(k) or mock.Mock()
            app._maybe_check_updates_on_launch()
        return bool(started), app

    def test_a_packaged_build_checks(self):
        started, _app = self._thread_starts()
        self.assertTrue(started)

    def test_a_dev_checkout_does_not_check(self):
        started, _app = self._thread_starts(frozen=False)
        self.assertFalse(started)

    def test_a_store_install_does_not_check(self):
        """The Store updates itself; a second prompt would be wrong."""
        started, _app = self._thread_starts(packaged=True)
        self.assertFalse(started)

    def test_the_setting_turns_it_off(self):
        started, _app = self._thread_starts(config={"update_check_on_launch": False})
        self.assertFalse(started)

    def test_it_runs_once_per_launch(self):
        app = _App()
        calls = []
        with mock.patch.object(main.threading, "Thread") as thread, \
             mock.patch.object(main.portable_paths, "is_windows_packaged", return_value=False), \
             mock.patch.object(main.sys, "frozen", True, create=True):
            thread.side_effect = lambda *a, **k: calls.append(k) or mock.Mock()
            app._maybe_check_updates_on_launch()
            app._maybe_check_updates_on_launch()
            app._maybe_check_updates_on_launch()
        self.assertEqual(len(calls), 1)


class LaunchPromptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_every_language_has_the_prompt(self):
        for lang in LANGUAGES:
            for key in ("launch_title", "launch_update", "launch_skip", "launch_later"):
                value = update_text(lang, key)
                self.assertTrue(value and value != key, (lang, key))
            prompt = update_text(lang, "launch_prompt", latest="9.9.9", current=APP_VERSION)
            self.assertIn("9.9.9", prompt, lang)
            self.assertIn(APP_VERSION, prompt, lang)

    def test_a_skipped_version_is_not_offered_again(self):
        app = _App({"skipped_update_version": "9.9.9"})
        app.current_interface_language = "en"
        with mock.patch.object(main, "QMessageBox") as box:
            main.DarkThemeApp._on_launch_update_found(app, "9.9.9")
        box.assert_not_called()

    def test_a_newer_version_is_still_offered_after_a_skip(self):
        app = _App({"skipped_update_version": "9.9.9"})
        with mock.patch.object(main, "QMessageBox") as box:
            main.DarkThemeApp._on_launch_update_found(app, "10.0.0")
        self.assertTrue(box.called)

    def test_manual_settings_update_owns_the_ui_without_a_second_prompt(self):
        for marker in ("settings", "manual-flow"):
            app = _App()
            app.settings_window = object() if marker == "settings" else None
            app._update_flow_active = marker == "manual-flow"
            with mock.patch.object(main, "QMessageBox") as box:
                main.DarkThemeApp._on_launch_update_found(app, "10.0.0")
            box.assert_not_called()


if __name__ == "__main__":
    unittest.main()
