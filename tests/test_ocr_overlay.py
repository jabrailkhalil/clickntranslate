import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication

import ocr


class TestScreenCaptureOverlayWindowing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_overlay_is_tool_topmost_and_frameless(self):
        overlay = ocr.ScreenCaptureOverlay("copy", defer_show=True)
        try:
            flags = overlay.windowFlags()
            self.assertEqual(flags & Qt.WindowType_Mask, Qt.Tool)
            self.assertTrue(flags & Qt.WindowStaysOnTopHint)
            self.assertTrue(flags & Qt.FramelessWindowHint)
        finally:
            overlay.deleteLater()

    def test_translate_combo_data_keeps_configured_target(self):
        self.assertEqual(
            ocr._combo_data_to_translate_pair(("de", "fr"), {"ocr_translate_target_language": "ru"}),
            ("de", "fr"),
        )
        self.assertEqual(
            ocr._combo_data_to_translate_pair(("auto", "ru"), {"ocr_translate_target_language": "en"}),
            ("auto", "ru"),
        )
        self.assertEqual(
            ocr._combo_data_to_translate_pair("de", {"ocr_translate_target_language": "es"}),
            ("de", "es"),
        )

    def test_translate_overlay_has_separate_source_and_target_controls(self):
        overlay = ocr.ScreenCaptureOverlay("translate", defer_show=True)
        try:
            self.assertIsNotNone(overlay.target_lang_combo)
            self.assertEqual(overlay.lang_combo.itemData(0), "auto")
            source, target = overlay._current_translate_pair()

            self.assertEqual(source, overlay.lang_combo.currentData())
            self.assertEqual(target, overlay.target_lang_combo.currentData())
            self.assertNotEqual(source, target)
        finally:
            overlay.deleteLater()

    def test_plain_ocr_overlay_does_not_show_translate_target_controls(self):
        overlay = ocr.ScreenCaptureOverlay("ocr", defer_show=True)
        try:
            self.assertIsNone(overlay.target_lang_combo)
            self.assertIsNone(overlay.translate_arrow_label)
        finally:
            overlay.deleteLater()

    def test_mouse_release_accepts_zero_origin_selection(self):
        overlay = ocr.ScreenCaptureOverlay("copy", defer_show=True)
        captured = []
        flushed = []

        class Event:
            def button(self):
                return Qt.LeftButton

            def pos(self):
                return QPoint(24, 12)

            def globalPos(self):
                return QPoint(24, 12)

        try:
            overlay.start_point = QPoint(0, 0)
            overlay.end_point = QPoint(24, 12)
            overlay._selection_started_at = time.monotonic()
            overlay.capture_and_copy = lambda rect: captured.append(rect)
            overlay._flush_selection_paint_before_capture = lambda: flushed.append(True)

            overlay.mouseReleaseEvent(Event())

            self.assertEqual(len(captured), 1)
            self.assertEqual(flushed, [True])
            self.assertGreaterEqual(captured[0].width(), 24)
            self.assertGreaterEqual(captured[0].height(), 12)
            self.assertIsNone(overlay.start_point)
            self.assertIsNone(overlay.end_point)
            self.assertIsNone(overlay._selection_started_at)
        finally:
            overlay.deleteLater()

    def test_mouse_release_ignores_release_without_tracked_press(self):
        overlay = ocr.ScreenCaptureOverlay("copy", defer_show=True)
        captured = []

        class Event:
            def button(self):
                return Qt.LeftButton

            def pos(self):
                return QPoint(80, 30)

            def globalPos(self):
                return QPoint(80, 30)

        try:
            overlay.start_point = QPoint(0, 0)
            overlay.end_point = QPoint(80, 30)
            overlay._selection_started_at = None
            overlay.capture_and_copy = lambda rect: captured.append(rect)

            overlay.mouseReleaseEvent(Event())

            self.assertEqual(captured, [])
        finally:
            overlay.deleteLater()

    def test_mouse_release_rejects_area_below_minimum(self):
        overlay = ocr.ScreenCaptureOverlay("copy", defer_show=True)
        captured = []

        class Event:
            def button(self):
                return Qt.LeftButton

            def pos(self):
                return QPoint(13, 11)

            def globalPos(self):
                return QPoint(13, 11)

        try:
            overlay.start_point = QPoint(0, 0)
            overlay.end_point = QPoint(13, 11)
            overlay._selection_started_at = time.monotonic()
            overlay.capture_and_copy = lambda rect: captured.append(rect)

            overlay.mouseReleaseEvent(Event())

            self.assertEqual(captured, [])
        finally:
            overlay.deleteLater()

    def test_mouse_release_accepts_minimum_area_boundary(self):
        overlay = ocr.ScreenCaptureOverlay("copy", defer_show=True)
        captured = []

        class Event:
            def button(self):
                return Qt.LeftButton

            def pos(self):
                return QPoint(14, 11)

            def globalPos(self):
                return QPoint(14, 11)

        try:
            overlay.start_point = QPoint(0, 0)
            overlay.end_point = QPoint(14, 11)
            overlay._selection_started_at = time.monotonic()
            overlay.capture_and_copy = lambda rect: captured.append(rect)

            overlay.mouseReleaseEvent(Event())

            self.assertEqual(len(captured), 1)
            self.assertGreaterEqual(captured[0].width() * captured[0].height(), 180)
        finally:
            overlay.deleteLater()

    def test_tesseract_text_score_prefers_real_words_over_noise(self):
        self.assertGreater(
            ocr.ScreenCaptureOverlay._score_tesseract_text("STRANGER THINGS"),
            ocr.ScreenCaptureOverlay._score_tesseract_text("witone~ ~~"),
        )
        self.assertGreater(
            ocr.ScreenCaptureOverlay._score_tesseract_text("https://example.com/a-b?x=1"),
            ocr.ScreenCaptureOverlay._score_tesseract_text("~~~~~!!!!"),
        )

    def test_ocr_worker_selects_best_attempt_text(self):
        class Word:
            def __init__(self, text):
                self.text = text

        class Line:
            def __init__(self, text):
                self.text = text
                self.words = [Word(part) for part in text.split()]

        class Result:
            def __init__(self, *lines):
                self.lines = [Line(line) for line in lines]

        weak_bitmap = object()
        good_bitmap = object()
        old_engine_getter = ocr._get_windows_ocr_engine
        old_runner = ocr.run_ocr_with_engine

        async def fake_runner(bitmap, _engine):
            if bitmap is weak_bitmap:
                return Result("~~")
            if bitmap is good_bitmap:
                return Result("STRANGER THINGS")
            return Result("")

        try:
            ocr._get_windows_ocr_engine = lambda _tag: object()
            ocr.run_ocr_with_engine = fake_runner
            worker = ocr.OCRWorker(
                weak_bitmap,
                "en",
                attempts=[("weak", weak_bitmap), ("good", good_bitmap)],
                session_id="unit-test",
            )
            captured = []
            worker.result_ready.connect(captured.append)

            worker.run()

            self.assertEqual(captured, ["STRANGER THINGS"])
        finally:
            ocr._get_windows_ocr_engine = old_engine_getter
            ocr.run_ocr_with_engine = old_runner

    def test_ocr_worker_suppresses_result_after_interruption(self):
        class Word:
            def __init__(self, text):
                self.text = text

        class Line:
            def __init__(self, text):
                self.text = text
                self.words = [Word(part) for part in text.split()]

        class Result:
            def __init__(self, text):
                self.lines = [Line(text)]

        bitmap = object()
        old_engine_getter = ocr._get_windows_ocr_engine
        old_runner = ocr.run_ocr_with_engine
        worker = None

        async def fake_runner(_bitmap, _engine):
            worker.cancel()
            return Result("STALE TEXT")

        try:
            ocr._get_windows_ocr_engine = lambda _tag: object()
            ocr.run_ocr_with_engine = fake_runner
            worker = ocr.OCRWorker(bitmap, "en", attempts=[("raw", bitmap)], session_id="unit-test")
            captured = []
            worker.result_ready.connect(captured.append)

            worker.run()

            self.assertEqual(captured, [])
        finally:
            ocr._get_windows_ocr_engine = old_engine_getter
            ocr.run_ocr_with_engine = old_runner

    def test_ocr_worker_runs_tesseract_fallback_when_windows_is_empty(self):
        class Result:
            lines = []

        bitmap = object()
        old_engine_getter = ocr._get_windows_ocr_engine
        old_runner = ocr.run_ocr_with_engine
        old_tesseract = ocr._recognize_tesseract_variants_with_cmd

        async def fake_runner(_bitmap, _engine):
            return Result()

        def fake_tesseract(_variants, _cmd, _lang, context, _session_id, cancel_check=None):
            self.assertEqual(context, "windows-empty-fallback")
            self.assertFalse(cancel_check())
            return "fallback text"

        try:
            ocr._get_windows_ocr_engine = lambda _tag: object()
            ocr.run_ocr_with_engine = fake_runner
            ocr._recognize_tesseract_variants_with_cmd = fake_tesseract
            worker = ocr.OCRWorker(bitmap, "en", attempts=[("raw", bitmap)], session_id="unit-test")
            worker.tesseract_fallback_enabled = True
            worker.tesseract_cmd = r"C:\fake\tesseract.exe"
            worker.fallback_pil_variants = [("raw", object())]
            captured = []
            worker.result_ready.connect(captured.append)

            worker.run()

            self.assertEqual(captured, ["fallback text"])
            self.assertTrue(worker.tesseract_fallback_attempted)
        finally:
            ocr._get_windows_ocr_engine = old_engine_getter
            ocr.run_ocr_with_engine = old_runner
            ocr._recognize_tesseract_variants_with_cmd = old_tesseract

    def test_ocr_worker_retries_universal_before_tesseract_fallback(self):
        class Word:
            def __init__(self, text):
                self.text = text

        class Line:
            def __init__(self, text):
                self.text = text
                self.words = [Word(part) for part in text.split()]

        class Result:
            def __init__(self, *lines):
                self.lines = [Line(line) for line in lines]

        bitmap = object()
        primary_engine = object()
        universal_engine = object()
        old_engine_getter = ocr._get_windows_ocr_engine
        old_universal_getter = ocr._get_universal_ocr_engine
        old_runner = ocr.run_ocr_with_engine
        old_tesseract = ocr._recognize_tesseract_variants_with_cmd
        tesseract_calls = []

        async def fake_runner(_bitmap, engine):
            if engine is primary_engine:
                return Result()
            if engine is universal_engine:
                return Result("Русский текст")
            return Result()

        def fake_tesseract(*_args, **_kwargs):
            tesseract_calls.append(True)
            return "should not run"

        try:
            ocr._get_windows_ocr_engine = lambda _tag: primary_engine
            ocr._get_universal_ocr_engine = lambda: universal_engine
            ocr.run_ocr_with_engine = fake_runner
            ocr._recognize_tesseract_variants_with_cmd = fake_tesseract
            worker = ocr.OCRWorker(bitmap, "en", attempts=[("raw", bitmap)], session_id="unit-test")
            worker.tesseract_fallback_enabled = True
            worker.tesseract_cmd = r"C:\fake\tesseract.exe"
            worker.fallback_pil_variants = [("raw", object())]
            captured = []
            worker.result_ready.connect(captured.append)

            worker.run()

            self.assertEqual(captured, ["Русский текст"])
            self.assertEqual(tesseract_calls, [])
            self.assertFalse(worker.tesseract_fallback_attempted)
        finally:
            ocr._get_windows_ocr_engine = old_engine_getter
            ocr._get_universal_ocr_engine = old_universal_getter
            ocr.run_ocr_with_engine = old_runner
            ocr._recognize_tesseract_variants_with_cmd = old_tesseract

    def test_tesseract_worker_suppresses_result_after_interruption(self):
        old_tesseract = ocr._recognize_tesseract_variants_with_cmd
        worker = None

        def fake_tesseract(_variants, _cmd, _lang, _context, _session_id, cancel_check=None):
            worker.cancel()
            self.assertTrue(cancel_check())
            return "STALE TESSERACT TEXT"

        try:
            ocr._recognize_tesseract_variants_with_cmd = fake_tesseract
            worker = ocr.TesseractOCRWorker(
                [("raw", object())],
                "en",
                r"C:\fake\tesseract.exe",
                "unit",
                "unit-test",
            )
            captured = []
            worker.result_ready.connect(captured.append)

            worker.run()

            self.assertEqual(captured, [])
        finally:
            ocr._recognize_tesseract_variants_with_cmd = old_tesseract

    def test_ocr_language_score_prefers_matching_script(self):
        self.assertGreater(
            ocr._score_ocr_text_for_language("Привет мир", "ru"),
            ocr._score_ocr_text_for_language("Привет мир", "en"),
        )
        self.assertGreater(
            ocr._score_ocr_text_for_language("Hello world", "en"),
            ocr._score_ocr_text_for_language("Hello world", "ru"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
