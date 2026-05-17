import os
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

    def test_mouse_release_accepts_zero_origin_selection(self):
        overlay = ocr.ScreenCaptureOverlay("copy", defer_show=True)
        captured = []

        class Event:
            def button(self):
                return Qt.LeftButton

            def pos(self):
                return QPoint(12, 9)

            def globalPos(self):
                return QPoint(12, 9)

        try:
            overlay.start_point = QPoint(0, 0)
            overlay.end_point = QPoint(12, 9)
            overlay.capture_and_copy = lambda rect: captured.append(rect)

            overlay.mouseReleaseEvent(Event())

            self.assertEqual(len(captured), 1)
            self.assertGreaterEqual(captured[0].width(), 12)
            self.assertGreaterEqual(captured[0].height(), 9)
        finally:
            overlay.deleteLater()

    def test_tesseract_text_score_prefers_real_words_over_noise(self):
        self.assertGreater(
            ocr.ScreenCaptureOverlay._score_tesseract_text("STRANGER THINGS"),
            ocr.ScreenCaptureOverlay._score_tesseract_text("witone~ ~~"),
        )

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
