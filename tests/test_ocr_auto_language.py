import asyncio
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

import ocr  # noqa: E402


class FakeRecognized:
    def __init__(self, text):
        self.text = text


class WindowsAutoRecognitionTest(unittest.TestCase):
    """AUTO language mode used to call a helper that no longer existed."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _fake_engine_for(tag):
        return f"engine:{tag}"

    def test_auto_mode_picks_the_best_scoring_language(self):
        results = {"engine:en-US": "Hello world", "engine:ru-RU": "Хелло ворлд"}

        async def fake_run(bitmap, engine):
            return FakeRecognized(results[engine])

        with mock.patch.object(ocr, "_windows_auto_ocr_candidates", return_value=[("en", "en-US"), ("ru", "ru-RU")]):
            with mock.patch.object(ocr, "_get_windows_ocr_engine", side_effect=self._fake_engine_for):
                with mock.patch.object(ocr, "run_ocr_with_engine", side_effect=fake_run):
                    with mock.patch.object(ocr, "_windows_ocr_result_to_text", side_effect=lambda r: r.text):
                        text = ocr._recognize_with_windows_auto(object())

        self.assertEqual(text, "Hello world")

    def test_auto_mode_without_candidates_uses_universal_engine(self):
        async def fake_run(bitmap, engine):
            return FakeRecognized("universal text")

        with mock.patch.object(ocr, "_windows_auto_ocr_candidates", return_value=[]):
            with mock.patch.object(ocr, "_get_universal_ocr_engine", return_value="engine:universal"):
                with mock.patch.object(ocr, "run_ocr_with_engine", side_effect=fake_run):
                    with mock.patch.object(ocr, "_windows_ocr_result_to_text", side_effect=lambda r: r.text):
                        text = ocr._recognize_with_windows_auto(object())

        self.assertEqual(text, "universal text")

    def test_auto_mode_without_any_engine_returns_empty(self):
        with mock.patch.object(ocr, "_windows_auto_ocr_candidates", return_value=[]):
            with mock.patch.object(ocr, "_get_universal_ocr_engine", return_value=None):
                self.assertEqual(ocr._recognize_with_windows_auto(object()), "")

    def test_auto_mode_breaks_cross_alphabet_tie_with_language_likelihood(self):
        results = {
            "engine:en-US": "npneT, MI/IP! KaK nena?",
            "engine:ru": "Привет, мир! Как дела?",
        }

        async def fake_run(bitmap, engine):
            return FakeRecognized(results[engine])

        with mock.patch.object(ocr, "_windows_auto_ocr_candidates", return_value=[("en", "en-US"), ("ru", "ru")]):
            with mock.patch.object(ocr, "_get_windows_ocr_engine", side_effect=self._fake_engine_for):
                with mock.patch.object(ocr, "run_ocr_with_engine", side_effect=fake_run):
                    with mock.patch.object(ocr, "_windows_ocr_result_to_text", side_effect=lambda r: r.text):
                        text = ocr._recognize_with_windows_auto(object())

        self.assertEqual(text, "Привет, мир! Как дела?")

    def test_each_recognition_run_closes_its_event_loop(self):
        created = []
        real_new_event_loop = asyncio.new_event_loop

        def make_loop():
            loop = real_new_event_loop()
            created.append(loop)
            return loop

        with mock.patch.object(ocr.asyncio, "new_event_loop", side_effect=make_loop):
            with mock.patch.object(ocr, "_windows_auto_ocr_candidates", return_value=[]):
                with mock.patch.object(ocr, "_get_universal_ocr_engine", return_value=None):
                    self.assertEqual(ocr._recognize_with_windows_auto(object()), "")

        self.assertEqual(len(created), 1)
        self.assertTrue(created[0].is_closed())
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()

    def test_event_loop_is_released_even_when_recognition_raises(self):
        created = []
        real_new_event_loop = asyncio.new_event_loop

        def make_loop():
            loop = real_new_event_loop()
            created.append(loop)
            return loop

        async def boom(bitmap, engine):
            raise RuntimeError("winrt failure")

        with mock.patch.object(ocr.asyncio, "new_event_loop", side_effect=make_loop):
            with mock.patch.object(ocr, "_windows_auto_ocr_candidates", return_value=[("en", "en-US")]):
                with mock.patch.object(ocr, "_get_windows_ocr_engine", side_effect=self._fake_engine_for):
                    with mock.patch.object(ocr, "_get_universal_ocr_engine", return_value=None):
                        with mock.patch.object(ocr, "run_ocr_with_engine", side_effect=boom):
                            self.assertEqual(ocr._recognize_with_windows_auto(object()), "")

        self.assertEqual(len(created), 1)
        self.assertTrue(created[0].is_closed())
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()


if __name__ == "__main__":
    unittest.main()
