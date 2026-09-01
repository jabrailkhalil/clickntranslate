import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5 import QtCore, QtGui, QtWidgets  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402

import game_mode  # noqa: E402
import ocr  # noqa: E402
import mode_coordinator  # noqa: E402


class GameModeAlgorithmsTest(unittest.TestCase):
    def test_ocr_text_normalization_keeps_dialogue_lines(self):
        value = game_mode.normalize_game_ocr_text("  Hello   there  \n\n  General Kenobi! ")
        self.assertEqual(value, "Hello there\nGeneral Kenobi!")

    def test_small_ocr_jitter_is_skipped_but_new_dialogue_is_not(self):
        self.assertTrue(
            game_mode.game_texts_are_similar(
                "The gates are closed.",
                "The gates are cIosed.",
                threshold=0.90,
            )
        )
        self.assertFalse(
            game_mode.game_texts_are_similar(
                "The gates are closed.",
                "Meet me beyond the bridge.",
                threshold=0.90,
            )
        )

    def test_frame_fingerprint_avoids_ocr_for_an_identical_frame(self):
        black = QtGui.QImage(320, 90, QtGui.QImage.Format_RGB32)
        black.fill(QtGui.QColor("black"))
        white = QtGui.QImage(320, 90, QtGui.QImage.Format_RGB32)
        white.fill(QtGui.QColor("white"))

        first = game_mode.game_frame_fingerprint(black)
        same = game_mode.game_frame_fingerprint(black.copy())
        changed = game_mode.game_frame_fingerprint(white)

        self.assertFalse(game_mode.game_frames_are_different(first, same))
        self.assertTrue(game_mode.game_frames_are_different(first, changed))

    def test_overlay_cards_stay_inside_the_monitor(self):
        bounds = QtCore.QRectF(0, 0, 1920, 1080)
        source = QtCore.QRectF(1880, 1060, 35, 16)
        card = game_mode.game_overlay_block_geometry(bounds, source, 420, 80)
        self.assertTrue(bounds.contains(card))
        self.assertGreaterEqual(card.width(), source.width())
        self.assertGreaterEqual(card.height(), source.height())

    def test_bad_ocr_rectangle_cannot_create_a_huge_empty_card(self):
        bounds = QtCore.QRectF(0, 0, 1920, 1080)
        # A real failure seen with animated game text: OCR returns nearly a
        # quarter-screen rectangle although the recognized line is tiny.
        source = QtCore.QRectF(240, 300, 900, 320)
        card = game_mode.game_overlay_block_geometry(bounds, source, 82, 36)

        self.assertLessEqual(card.width(), 130)
        self.assertLessEqual(card.height(), 52)
        self.assertTrue(bounds.contains(card))

    def test_normal_ocr_rectangle_can_still_cover_the_source_line(self):
        bounds = QtCore.QRectF(0, 0, 1920, 1080)
        source = QtCore.QRectF(240, 300, 118, 28)
        card = game_mode.game_overlay_block_geometry(bounds, source, 112, 38)

        self.assertGreaterEqual(card.width(), source.width())
        self.assertGreaterEqual(card.height(), source.height())

    def test_every_supported_language_has_the_same_game_copy(self):
        expected = set(game_mode.GAME_TEXT["en"])
        for language, texts in game_mode.GAME_TEXT.items():
            self.assertEqual(set(texts), expected, language)
            self.assertTrue(all(str(value).strip() for value in texts.values()), language)


class GameModeWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        mode_coordinator._reset_for_tests()

    def tearDown(self):
        game_mode.stop_game_mode()
        mode_coordinator._reset_for_tests()

    def _overlay(self, **updates):
        config = {
            "theme": "Темная",
            "interface_language": "en",
            "ocr_engine": "Windows",
            "translator_engine": "Google",
            "game_capture_interval_ms": 850,
            "game_text_similarity": 0.90,
            "history": False,
        }
        config.update(updates)
        with mock.patch.object(ocr, "get_cached_ocr_config", return_value=config), mock.patch.object(
            game_mode, "_exclude_from_windows_capture", return_value=True
        ):
            overlay = game_mode.GameTranslationOverlay(
                QtCore.QRect(100, 100, 400, 100), "en", "ru"
            )
        overlay._timer.stop()
        return overlay

    def _fullscreen_overlay(self, **updates):
        config = {
            "theme": "Темная",
            "interface_language": "en",
            "translator_engine": "Google",
            "game_capture_interval_ms": 850,
            "game_text_similarity": 0.90,
            "game_overlay_opacity": 88,
            "game_pause_when_inactive": True,
            "history": False,
        }
        config.update(updates)
        with mock.patch.object(ocr, "get_cached_ocr_config", return_value=config), mock.patch.object(
            game_mode, "_exclude_from_windows_capture", return_value=True
        ):
            overlay = game_mode.GameFullscreenOverlay("en", "ru")
        overlay._timer.stop()
        return overlay

    def test_selected_area_overlay_replaces_the_same_region_and_is_click_through(self):
        overlay = self._overlay()
        try:
            self.assertEqual(overlay.geometry(), overlay.region)
            self.assertTrue(overlay.testAttribute(QtCore.Qt.WA_TransparentForMouseEvents))
            self.assertTrue(overlay.reselect_button.isHidden())
            self.assertTrue(overlay.pause_button.isHidden())
            self.assertTrue(overlay.close_button.isHidden())
        finally:
            overlay.close()

    def test_selected_area_mode_accepts_multiple_regions_before_starting(self):
        config = {
            "interface_language": "en",
            "translator_engine": "Google",
            "game_translate_source_language": "en",
            "game_translate_target_language": "ru",
        }
        with mock.patch.object(ocr, "get_cached_ocr_config", return_value=config), mock.patch.object(
            ocr, "installed_ocr_language_codes", return_value=["en", "ru"]
        ), mock.patch.object(
            ocr, "_translation_targets_for_source", side_effect=lambda source, _config: ["ru"] if source == "en" else ["en"]
        ), mock.patch.object(ocr, "_write_ocr_config_updates"):
            selector = game_mode.GameRegionSelector()
        try:
            first = QtCore.QRect(200, 200, 240, 90)
            second = QtCore.QRect(500, 300, 260, 100)
            selector._regions.extend((first, second))
            selector._update_selection_controls()
            self.assertEqual(len(selector._regions), 2)
            self.assertIn("(2)", selector.start_button.text())
            self.assertTrue(selector.start_button.isEnabled())
            QTest.keyClick(selector, QtCore.Qt.Key_Backspace)
            self.assertEqual(selector._regions, [first])
        finally:
            selector.close()

    def test_multiple_regions_create_independent_staggered_overlays(self):
        regions = [QtCore.QRect(10, 20, 220, 80), QtCore.QRect(300, 200, 240, 90)]
        created = []

        def build(region, source, target, target_window, start_delay_ms=0):
            overlay = mock.Mock()
            overlay.region = QtCore.QRect(region)
            created.append((overlay, source, target, target_window, start_delay_ms))
            return overlay

        game_mode._game_overlay_refs = []
        with mock.patch.object(game_mode, "GameTranslationOverlay", side_effect=build):
            result = game_mode._begin_game_session(regions, "en", "ru", 42)
        try:
            self.assertEqual(len(result), 2)
            self.assertEqual([item[4] for item in created], [0, 160])
            self.assertEqual([item[0].region for item in created], regions)
        finally:
            game_mode._game_overlay_refs = []

    def test_game_translation_never_changes_clipboard_and_honors_history_flag(self):
        clipboard = self.app.clipboard()
        clipboard.setText("sentinel")
        overlay = self._overlay(history=False)
        overlay._revision = 1
        try:
            with mock.patch.object(ocr, "save_translation_history") as save_history:
                overlay._apply_translation(1, "Hello", "Привет", "")
            self.assertEqual(overlay.translation_label.text(), "Привет")
            self.assertEqual(clipboard.text(), "sentinel")
            save_history.assert_not_called()
        finally:
            overlay.close()

    def test_region_mode_respects_original_text_and_focus_settings(self):
        overlay = self._overlay(
            game_show_original_text=False,
            game_pause_when_inactive=False,
        )
        overlay._revision = 1
        overlay.target_window = 123
        try:
            with mock.patch.object(game_mode, "_window_is_minimized", return_value=True):
                self.assertTrue(overlay._target_is_active())
            overlay._apply_translation(1, "Hello", "Привет", "")
            self.assertTrue(overlay.original_label.isHidden())
        finally:
            overlay.close()

    def test_pause_when_target_app_is_inactive_and_resume_on_return(self):
        overlay = self._overlay(game_pause_when_inactive=True)
        overlay.target_window = 123
        overlay._created_at = 0
        try:
            with mock.patch.object(game_mode, "_window_is_minimized", return_value=True):
                self.assertFalse(overlay._target_is_active())
            with mock.patch.object(game_mode, "_window_is_minimized", return_value=False), mock.patch.object(
                game_mode, "_foreground_window", return_value=999
            ):
                self.assertFalse(overlay._target_is_active())
            with mock.patch.object(game_mode, "_window_is_minimized", return_value=False), mock.patch.object(
                game_mode, "_foreground_window", return_value=123
            ):
                self.assertTrue(overlay._target_is_active())
        finally:
            overlay.close()

    def test_fullscreen_overlay_is_click_through_and_never_uses_clipboard(self):
        clipboard = self.app.clipboard()
        clipboard.setText("sentinel")
        overlay = self._fullscreen_overlay(history=False)
        try:
            self.assertTrue(overlay.testAttribute(QtCore.Qt.WA_TransparentForMouseEvents))
            overlay._revision = 1
            with mock.patch.object(ocr, "save_translation_history") as save_history:
                overlay._apply_translation(
                    1,
                    [(10.0, 20.0, 120.0, 28.0, "Hello", "Привет")],
                    "",
                    False,
                )
            self.assertEqual(clipboard.text(), "sentinel")
            self.assertEqual(overlay._blocks[0][5], "Привет")
            self.assertTrue(overlay._has_shown_translation)
            self.assertTrue(overlay._translation_busy)
            overlay._apply_translation(
                1,
                [(10.0, 20.0, 120.0, 28.0, "Hello", "Привет")],
                "",
                True,
            )
            self.assertFalse(overlay._translation_busy)
            save_history.assert_not_called()

            overlay._last_layout_signature = ((1, 2, "hello"),)
            overlay._apply_translation(1, [], "rate limited", True)
            self.assertEqual(
                overlay._last_layout_signature,
                (),
                "a static screen must be eligible for retry after provider failure",
            )
        finally:
            overlay.close()

    def test_fullscreen_translates_every_line_immediately_and_clears_stale_cards(self):
        overlay = self._fullscreen_overlay(
            history=False, game_capture_interval_ms=850
        )
        line = (100.0, 200.0, 180.0, 28.0, "Open the gate")
        try:
            with mock.patch.object(overlay, "_start_block_translation") as start:
                overlay._on_position_ocr_result([line])
                start.assert_called_once()

            overlay._blocks = [(100, 200, 180, 28, "Open", "Открыть")]
            overlay._on_position_ocr_result([])
            self.assertEqual(overlay._blocks, [])
        finally:
            overlay.close()

    def test_scan_interval_supports_a_ten_second_low_frequency_mode(self):
        region = self._overlay(game_capture_interval_ms=10000)
        fullscreen = self._fullscreen_overlay(game_capture_interval_ms=10000)
        try:
            self.assertEqual(region.interval_ms, 10000)
            self.assertEqual(fullscreen.interval_ms, 10000)
        finally:
            region.close()
            fullscreen.close()

    def test_fullscreen_text_rich_frame_is_published_as_one_coherent_screen(self):
        overlay = self._fullscreen_overlay(history=False)
        lines = [
            (float(index * 10), 20.0, 90.0, 24.0, f"Line {index}")
            for index in range(25)
        ]
        events = []
        overlay.translation_ready.connect(
            lambda revision, blocks, error, final: events.append(
                (revision, len(blocks), error, final)
            )
        )
        try:
            with mock.patch.object(
                ocr,
                "_translate_screen_texts",
                side_effect=lambda texts, *_args: [f"T:{text}" for text in texts],
            ):
                overlay._start_block_translation(lines)
                for _ in range(100):
                    self.app.processEvents()
                    if events and events[-1][3]:
                        break
                    QTest.qWait(10)

            self.assertEqual([event[1] for event in events], [25])
            self.assertEqual([event[3] for event in events], [True])
            self.assertTrue(all(not event[2] for event in events))
        finally:
            overlay.close()

    def test_dynamic_fullscreen_reuses_the_ordinary_screen_replacement_renderer(self):
        import inspect

        source = inspect.getsource(game_mode.GameFullscreenOverlay.paintEvent)
        self.assertIn("FullScreenTranslateOverlay._translation_block_layout", source)
        self.assertIn("FullScreenTranslateOverlay._paint_block", source)
        self.assertNotIn("drawRoundedRect(card", source)

    def test_one_entry_always_launches_selected_areas_and_second_press_stops(self):
        stale_fullscreen_config = {
            "game_capture_mode": "fullscreen",
            "game_translate_source_language": "en",
            "game_translate_target_language": "ru",
        }
        with mock.patch.object(game_mode, "game_mode_active", return_value=False), mock.patch.object(
            game_mode.platform_support, "IS_LINUX", False
        ), mock.patch.object(
            ocr, "get_cached_ocr_config", return_value=stale_fullscreen_config
        ), mock.patch.object(
            game_mode, "_foreground_window", return_value=321
        ), mock.patch.object(
            game_mode, "_window_belongs_to_this_process", return_value=False
        ), mock.patch.object(
            game_mode, "_show_game_selector", return_value="region"
        ) as show_region:
            self.assertEqual(game_mode.toggle_game_mode(), "region")
            show_region.assert_called_once_with(321)
            # The coordinator owns the toggle even while the selector factory
            # is mocked: the same hotkey must stop, never launch a second copy.
            self.assertIsNone(game_mode.toggle_game_mode())
            show_region.assert_called_once_with(321)

if __name__ == "__main__":
    unittest.main()
