import os
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402


class _SignalRecorder:
    def __init__(self):
        self.values = []

    def emit(self, *values):
        self.values.append(values)


class _ImmediateThread:
    def __init__(self, target, daemon=True):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


class ArgosProgressUiTest(unittest.TestCase):
    def _dummy(self):
        return SimpleNamespace(
            current_interface_language="ru",
            _argos_translation_running=False,
            _argos_install_required=False,
            _argos_cancel_enabled=False,
            _argos_active_pair="",
            _argos_cancel_requested=threading.Event(),
            _argos_status_signal=_SignalRecorder(),
            _argos_progress_signal=_SignalRecorder(),
            _argos_translation_done_signal=_SignalRecorder(),
            _argos_translation_error_signal=_SignalRecorder(),
            _argos_translation_cancelled_signal=_SignalRecorder(),
            _confirm_argos_package_install=mock.Mock(return_value=True),
            _show_argos_progress=mock.Mock(),
            translate_button=mock.Mock(),
        )

    def test_missing_pair_prompts_and_starts_background_install(self):
        dummy = self._dummy()

        def fake_translate(*_args, **kwargs):
            kwargs["status_callback"]("Загрузка RU→EN…")
            kwargs["progress_callback"]("RU→EN", 40, 100)
            self.assertFalse(kwargs["cancel_callback"]())
            return "Hello"

        with mock.patch.object(main.translater, "argos_pair_installed", return_value=False):
            with mock.patch.object(main.translater, "translate_text", side_effect=fake_translate) as translate:
                with mock.patch.object(main.threading, "Thread", _ImmediateThread):
                    main.DarkThemeApp._start_argos_translation(dummy, "Привет", "ru", "en")

        dummy._confirm_argos_package_install.assert_called_once_with("RU→EN")
        dummy._show_argos_progress.assert_called_once()
        dummy.translate_button.setEnabled.assert_called_once_with(False)
        self.assertTrue(dummy._argos_install_required)
        self.assertEqual(dummy._argos_status_signal.values, [("Загрузка RU→EN…",)])
        self.assertEqual(dummy._argos_progress_signal.values, [("RU→EN", 40, 100)])
        self.assertEqual(dummy._argos_translation_done_signal.values, [("Hello",)])
        self.assertEqual(translate.call_args.kwargs["engine"], "argos")

    def test_installed_pair_skips_download_prompt_and_progress_window(self):
        dummy = self._dummy()
        with mock.patch.object(main.translater, "argos_pair_installed", return_value=True):
            with mock.patch.object(main.translater, "translate_text", return_value="Hello"):
                with mock.patch.object(main.threading, "Thread", _ImmediateThread):
                    main.DarkThemeApp._start_argos_translation(dummy, "Привет", "ru", "en")

        dummy._confirm_argos_package_install.assert_not_called()
        dummy._show_argos_progress.assert_not_called()
        self.assertFalse(dummy._argos_install_required)
        self.assertEqual(dummy._argos_translation_done_signal.values, [("Hello",)])

    def test_cancel_button_sets_worker_cancel_event(self):
        cancel_button = mock.Mock()
        close_button = mock.Mock()
        dummy = SimpleNamespace(
            current_interface_language="ru",
            _argos_translation_running=True,
            _argos_cancel_enabled=True,
            _argos_cancel_requested=threading.Event(),
            _argos_progress=SimpleNamespace(cancel_button=cancel_button, close_button=close_button),
            _show_argos_progress=mock.Mock(),
        )

        main.DarkThemeApp._request_argos_install_cancel(dummy)

        self.assertTrue(dummy._argos_cancel_requested.is_set())
        dummy._show_argos_progress.assert_called_once()
        cancel_button.setEnabled.assert_called_once_with(False)
        close_button.setEnabled.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
