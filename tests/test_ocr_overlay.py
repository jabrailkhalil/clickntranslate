import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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
            ("en", "ru"),
        )
        self.assertEqual(
            ocr._combo_data_to_translate_pair("de", {"ocr_translate_target_language": "es"}),
            ("de", "es"),
        )

    def test_translate_overlay_has_separate_source_and_target_controls(self):
        overlay = ocr.ScreenCaptureOverlay("translate", defer_show=True)
        try:
            self.assertIsNotNone(overlay.target_lang_combo)
            self.assertNotEqual(overlay.lang_combo.itemData(0), "auto")
            source, target = overlay._current_translate_pair()

            self.assertEqual(source, overlay.lang_combo.currentData())
            self.assertEqual(target, overlay.target_lang_combo.currentData())
            self.assertNotEqual(source, target)
        finally:
            overlay.deleteLater()

    def test_fullscreen_overlay_remembers_independent_chinese_to_english_pair(self):
        config = {
            "interface_language": "en",
            "translator_engine": "Google",
            "fullscreen_translate_from": "zh",
            "fullscreen_translate_to": "en",
        }
        with mock.patch.object(ocr, "get_cached_ocr_config", return_value=config), \
                mock.patch.object(ocr, "installed_ocr_language_codes", return_value=["en", "zh"]), \
                mock.patch.object(ocr, "_write_ocr_config_updates") as save_pair:
            overlay = ocr.FullScreenTranslateOverlay()
            try:
                self.assertEqual(overlay.lang_combo.currentData(), "zh")
                self.assertEqual(overlay.target_lang_combo.currentData(), "en")
                self.assertIsNotNone(overlay.translate_arrow_label)

                with mock.patch.object(overlay, "_start_ocr"):
                    overlay._on_go_clicked()

                self.assertEqual((overlay.src_lang, overlay.tgt_lang), ("zh", "en"))
                save_pair.assert_called_with({
                    "fullscreen_translate_from": "zh",
                    "fullscreen_translate_to": "en",
                })
            finally:
                overlay.close()
                overlay.deleteLater()

    def test_copy_overlay_does_not_offer_auto_language(self):
        overlay = ocr.ScreenCaptureOverlay("copy", defer_show=True)
        try:
            values = [overlay.lang_combo.itemData(i) for i in range(overlay.lang_combo.count())]
            self.assertNotIn("auto", values)
            self.assertNotIn("universal", values)
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

    def test_auto_ocr_rejects_noise_before_passing_text_on(self):
        self.assertEqual(
            ocr._auto_ocr_rejection_reason("~~~~!!!!", ocr._score_recognized_text("~~~~!!!!")),
            "no_text_signal",
        )
        self.assertEqual(
            ocr._auto_ocr_rejection_reason(
                "Привет мир",
                ocr._score_ocr_text_for_language("Привет мир", "ru"),
            ),
            "",
        )
        self.assertEqual(
            ocr._auto_ocr_rejection_reason("404", ocr._score_recognized_text("404")),
            "",
        )

    def test_parse_rapidocr_legacy_output_orders_text_lines(self):
        output = (
            [
                [[[10, 30], [50, 30], [50, 45], [10, 45]], "second", 0.92],
                [[[10, 5], [50, 5], [50, 20], [10, 20]], "first", 0.95],
            ],
            [1.0, 2.0, 3.0],
        )

        items = ocr._parse_rapidocr_output(output)

        self.assertEqual([item[1] for item in items], ["first", "second"])
        self.assertEqual([item[2] for item in items], [0.95, 0.92])

    def test_parse_rapidocr_dataclass_style_output(self):
        class Output:
            boxes = [
                [[10, 20], [50, 20], [50, 35], [10, 35]],
                [[10, 2], [50, 2], [50, 17], [10, 17]],
            ]
            txts = ["bottom", "top"]
            scores = [0.8, 0.9]

        items = ocr._parse_rapidocr_output(Output())

        self.assertEqual([item[1] for item in items], ["top", "bottom"])

    def test_parse_easyocr_output_orders_text_lines(self):
        output = [
            ([[10, 30], [50, 30], [50, 45], [10, 45]], "second", 0.92),
            ([[10, 5], [50, 5], [50, 20], [10, 20]], "first", 0.95),
        ]

        items = ocr._parse_easyocr_output(output)

        self.assertEqual([item[1] for item in items], ["first", "second"])
        self.assertEqual([item[2] for item in items], [0.95, 0.92])

    def test_easyocr_recognition_uses_selected_language(self):
        from PIL import Image

        calls = []

        class Reader:
            def readtext(self, image, detail=1, paragraph=False):
                calls.append((image.shape[:2], detail, paragraph))
                return [
                    ([[0, 0], [50, 0], [50, 20], [0, 20]], "Привет мир", 0.91),
                ]

        old_reader = ocr._get_easyocr_reader
        try:
            requested_languages = []

            def fake_reader(language_code):
                requested_languages.append(language_code)
                return Reader()

            ocr._get_easyocr_reader = fake_reader
            text, failure = ocr._recognize_easyocr_variants(
                [("raw", Image.new("RGB", (80, 24), "white"))],
                "ru",
                "unit",
                "unit-test",
            )

            self.assertEqual(text, "Привет мир")
            self.assertEqual(failure, "")
            self.assertEqual(requested_languages, ["ru"])
            self.assertEqual(calls, [((24, 80), 1, False)])
        finally:
            ocr._get_easyocr_reader = old_reader

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

        def fake_tesseract(_variants, _cmd, _lang, context, _session_id, status_callback=None, cancel_check=None):
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

    def test_windows_auto_ocr_tries_all_image_attempts(self):
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

        raw_bitmap = object()
        enhanced_bitmap = object()
        ru_engine = object()
        en_engine = object()
        old_candidates = ocr._windows_auto_ocr_candidates
        old_engine_getter = ocr._get_windows_ocr_engine
        old_runner = ocr.run_ocr_with_engine

        async def fake_runner(bitmap, engine):
            if bitmap is raw_bitmap:
                return Result()
            if bitmap is enhanced_bitmap and engine is ru_engine:
                return Result("Привет мир")
            if bitmap is enhanced_bitmap and engine is en_engine:
                return Result("~~")
            return Result()

        try:
            ocr._windows_auto_ocr_candidates = lambda: [("en", "en-US"), ("ru", "ru-RU")]
            ocr._get_windows_ocr_engine = lambda tag: ru_engine if tag == "ru-RU" else en_engine
            ocr.run_ocr_with_engine = fake_runner

            text = ocr._recognize_with_windows_auto(
                [("raw", raw_bitmap), ("enhanced", enhanced_bitmap)],
                session_id="unit-test",
            )

            self.assertEqual(text, "Привет мир")
        finally:
            ocr._windows_auto_ocr_candidates = old_candidates
            ocr._get_windows_ocr_engine = old_engine_getter
            ocr.run_ocr_with_engine = old_runner

    def test_auto_worker_runs_tesseract_fallback_when_windows_auto_is_empty(self):
        class Result:
            lines = []

        bitmap = object()
        old_candidates = ocr._windows_auto_ocr_candidates
        old_engine_getter = ocr._get_windows_ocr_engine
        old_universal_getter = ocr._get_universal_ocr_engine
        old_runner = ocr.run_ocr_with_engine
        old_tesseract = ocr._recognize_tesseract_variants_with_cmd

        async def fake_runner(_bitmap, _engine):
            return Result()

        def fake_tesseract(_variants, _cmd, lang, context, _session_id, status_callback=None, cancel_check=None):
            self.assertEqual(lang, "eng+rus")
            self.assertEqual(context, "windows-auto-empty-fallback")
            self.assertFalse(cancel_check())
            return "fallback auto text"

        try:
            ocr._windows_auto_ocr_candidates = lambda: [("en", "en-US")]
            ocr._get_windows_ocr_engine = lambda _tag: object()
            ocr._get_universal_ocr_engine = lambda: None
            ocr.run_ocr_with_engine = fake_runner
            ocr._recognize_tesseract_variants_with_cmd = fake_tesseract
            worker = ocr.OCRWorker(bitmap, "universal", use_universal=True, attempts=[("raw", bitmap)], session_id="unit-test")
            worker.tesseract_fallback_enabled = True
            worker.tesseract_cmd = r"C:\fake\tesseract.exe"
            worker.fallback_pil_variants = [("raw", object())]
            captured = []
            worker.result_ready.connect(captured.append)

            worker.run()

            self.assertEqual(captured, ["fallback auto text"])
            self.assertTrue(worker.tesseract_fallback_attempted)
        finally:
            ocr._windows_auto_ocr_candidates = old_candidates
            ocr._get_windows_ocr_engine = old_engine_getter
            ocr._get_universal_ocr_engine = old_universal_getter
            ocr.run_ocr_with_engine = old_runner
            ocr._recognize_tesseract_variants_with_cmd = old_tesseract

    def test_tesseract_worker_suppresses_result_after_interruption(self):
        old_tesseract = ocr._recognize_tesseract_variants_with_cmd
        worker = None

        def fake_tesseract(_variants, _cmd, _lang, _context, _session_id, status_callback=None, cancel_check=None):
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

    def test_windows_language_filter_returns_only_installed_recognizers(self):
        with mock.patch.object(
            ocr,
            "_get_available_windows_ocr_language_tags",
            return_value=["en-US", "zh-Hans-CN"],
        ):
            self.assertEqual(
                ocr.installed_ocr_language_codes("Windows", {}),
                ["en", "zh"],
            )

    def test_windows_engine_uses_exact_installed_chinese_tag(self):
        created_tags = []

        class Language:
            def __init__(self, tag):
                self.tag = tag

        class OcrEngine:
            @staticmethod
            def is_language_supported(_language):
                return True

            @staticmethod
            def try_create_from_language(language):
                created_tags.append(language.tag)
                return object()

        with mock.patch.object(ocr, "_WINRT_AVAILABLE", True):
            with mock.patch.object(ocr, "winrt_glob", SimpleNamespace(Language=Language)):
                with mock.patch.object(ocr, "winrt_ocr", SimpleNamespace(OcrEngine=OcrEngine)):
                    with mock.patch.object(
                        ocr,
                        "_get_available_windows_ocr_language_tags",
                        return_value=["zh-Hans-CN"],
                    ):
                        ocr._OCR_ENGINE_CACHE.clear()
                        self.assertIsNotNone(ocr._get_windows_ocr_engine("zh-CN"))

        self.assertEqual(created_tags, ["zh-Hans-CN"])

    def test_tesseract_language_filter_reads_local_traineddata_only(self):
        with tempfile.TemporaryDirectory() as root:
            exe = Path(root, "tesseract.exe")
            exe.write_bytes(b"exe")
            tessdata = Path(root, "tessdata")
            tessdata.mkdir()
            tessdata.joinpath("eng.traineddata").write_bytes(b"model")
            tessdata.joinpath("rus.traineddata").write_bytes(b"model")
            with mock.patch.object(ocr.ScreenCaptureOverlay, "get_tesseract_cmd", return_value=str(exe)):
                self.assertEqual(
                    ocr.installed_ocr_language_codes("Tesseract", {}),
                    ["en", "ru"],
                )

    def test_easyocr_and_rapidocr_filters_match_their_real_model_families(self):
        with tempfile.TemporaryDirectory() as root:
            easy_root = Path(root, "easy")
            easy_package = easy_root / "site-packages" / "easyocr"
            easy_package.mkdir(parents=True)
            easy_package.joinpath("__init__.py").write_text("", encoding="utf-8")
            models = easy_root / "models"
            models.mkdir()
            for name in ("craft_mlt_25k.pth", "english_g2.pth", "cyrillic_g2.pth"):
                models.joinpath(name).write_bytes(b"model")
            with mock.patch.object(ocr, "_easyocr_local_root", return_value=str(easy_root)):
                easy_codes = ocr.installed_ocr_language_codes("EasyOCR", {})
            self.assertIn("en", easy_codes)
            self.assertIn("ru", easy_codes)
            self.assertNotIn("zh", easy_codes)

            rapid_root = Path(root, "rapid")
            rapid_package = rapid_root / "site-packages" / "rapidocr"
            rapid_package.mkdir(parents=True)
            rapid_package.joinpath("__init__.py").write_text("", encoding="utf-8")
            with mock.patch.object(ocr, "_rapidocr_local_root", return_value=str(rapid_root)):
                self.assertEqual(
                    ocr.installed_ocr_language_codes("RapidOCR", {}),
                    ["en", "zh"],
                )

    def test_frozen_build_exposes_rapidocr_bundled_in_worker(self):
        with tempfile.TemporaryDirectory() as root:
            app_exe = Path(root, "ClicknTranslate.exe")
            app_exe.write_bytes(b"app")
            internal = Path(root, "_internal")
            internal.mkdir()
            internal.joinpath("OcrWorker.exe").write_bytes(b"worker")
            with mock.patch.object(ocr.sys, "frozen", True, create=True):
                with mock.patch.object(ocr.sys, "executable", str(app_exe)):
                    self.assertEqual(
                        ocr.installed_ocr_language_codes("RapidOCR", {}),
                        ["en", "zh"],
                    )

    def test_easyocr_chinese_does_not_require_separate_english_model(self):
        with tempfile.TemporaryDirectory() as root:
            easy_root = Path(root, "easy")
            easy_package = easy_root / "site-packages" / "easyocr"
            easy_package.mkdir(parents=True)
            easy_package.joinpath("__init__.py").write_text("", encoding="utf-8")
            models = easy_root / "models"
            models.mkdir()
            for name in ("craft_mlt_25k.pth", "zh_sim_g2.pth"):
                models.joinpath(name).write_bytes(b"model")

            with mock.patch.object(ocr, "_easyocr_local_root", return_value=str(easy_root)):
                easy_codes = ocr.installed_ocr_language_codes("EasyOCR", {})

            self.assertIn("zh", easy_codes)
            self.assertNotIn("en", easy_codes)

    def test_fullscreen_lines_stay_separate_and_do_not_merge_side_by_side_columns(self):
        blocks = ocr._group_screen_ocr_lines([
            (10, 10, 180, 20, "First line"),
            (12, 34, 170, 20, "Second line"),
            (320, 12, 160, 20, "Other column"),
        ])
        self.assertEqual(len(blocks), 3)
        texts = {block[4] for block in blocks}
        self.assertIn("First line", texts)
        self.assertIn("Second line", texts)
        self.assertIn("Other column", texts)

    def test_fullscreen_only_same_baseline_fragments_become_one_visual_line(self):
        blocks = ocr._group_screen_ocr_lines([
            (10, 10, 80, 22, "First"),
            (96, 11, 90, 20, "setting"),
            (12, 38, 175, 22, "Second setting"),
        ])

        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0][4], "First setting")
        self.assertEqual(blocks[1][4], "Second setting")

    def test_fullscreen_translation_mapping_falls_back_when_markers_change(self):
        calls = []

        def translate(text, source, target):
            calls.append((text, source, target))
            if text.startswith("[[["):
                return "markers were removed"
            return "T:" + text

        result = ocr._translate_screen_texts(["one", "two"], translate, "en", "ru")
        self.assertEqual(result, ["T:one", "T:two"])
        self.assertEqual(len(calls), 3)

    def test_fullscreen_translation_splits_text_rich_screen_into_safe_batches(self):
        calls = []

        def translate(text, _source, _target):
            calls.append(text)
            return text

        values = [f"block {index}" for index in range(30)]
        result = ocr._translate_screen_texts(values, translate, "en", "ru")

        self.assertEqual(result, values)
        self.assertEqual(len(calls), 2)

    def test_fullscreen_translation_layout_stays_inside_screen(self):
        dummy = SimpleNamespace(width=lambda: 800, height=lambda: 500)
        bg_rect, draw_rect, font, _flags = ocr.FullScreenTranslateOverlay._translation_block_layout(
            dummy,
            ocr.QtCore.QRectF(740, 460, 50, 20),
            "short",
            "A much longer translated sentence that must wrap inside the screen.",
        )
        self.assertGreaterEqual(bg_rect.left(), 8)
        self.assertGreaterEqual(bg_rect.top(), 8)
        self.assertLessEqual(bg_rect.right(), 792)
        self.assertLessEqual(bg_rect.bottom(), 492)
        self.assertTrue(bg_rect.intersects(ocr.QtCore.QRectF(740, 460, 50, 20)))
        self.assertGreater(bg_rect.width(), 50)
        self.assertLessEqual(bg_rect.width(), 214)
        self.assertGreater(draw_rect.width(), 0)
        self.assertGreaterEqual(font.pointSize(), 6)
        self.assertTrue(_flags & ocr.QtCore.Qt.TextSingleLine)

    def test_fullscreen_translation_layout_never_moves_away_from_source(self):
        dummy = SimpleNamespace(width=lambda: 800, height=lambda: 500)
        first = ocr.QtCore.QRectF(10, 50, 330, 330)
        second, _draw, _font, _flags = ocr.FullScreenTranslateOverlay._translation_block_layout(
            dummy,
            ocr.QtCore.QRectF(300, 320, 150, 30),
            "source",
            "translated text",
            occupied=[first],
        )

        source = ocr.QtCore.QRectF(300, 320, 150, 30)
        self.assertTrue(source.intersects(second))
        self.assertLessEqual(abs(second.center().x() - source.center().x()), 2.1)
        self.assertLessEqual(abs(second.center().y() - source.center().y()), 2.1)

    def test_fullscreen_translation_expands_only_inside_free_corridor(self):
        dummy = SimpleNamespace(width=lambda: 800, height=lambda: 500)
        source = ocr.QtCore.QRectF(300, 100, 60, 20)
        left_text = ocr.QtCore.QRectF(210, 98, 80, 24)
        right_text = ocr.QtCore.QRectF(375, 98, 90, 24)
        bg_rect, draw_rect, font, flags = ocr.FullScreenTranslateOverlay._translation_block_layout(
            dummy,
            source,
            "small",
            "A longer translated line",
            obstacles=[left_text, right_text],
        )

        self.assertTrue(bg_rect.contains(source))
        self.assertGreaterEqual(bg_rect.left(), left_text.right() + 2.9)
        self.assertLessEqual(bg_rect.right(), right_text.left() - 2.9)
        self.assertFalse(bg_rect.intersects(left_text))
        self.assertFalse(bg_rect.intersects(right_text))
        self.assertGreater(draw_rect.width(), 0)
        self.assertGreaterEqual(font.pointSize(), 6)
        self.assertTrue(flags & ocr.QtCore.Qt.TextSingleLine)

    def test_fullscreen_replacement_palette_matches_local_background(self):
        screenshot = ocr.QtGui.QPixmap(120, 60)
        screenshot.fill(ocr.QtGui.QColor("#f4f4f4"))
        dummy = SimpleNamespace(
            screenshot=screenshot,
            width=lambda: 120,
            height=lambda: 60,
        )
        background, foreground = ocr.FullScreenTranslateOverlay._replacement_palette(
            dummy,
            ocr.QtCore.QRectF(10, 10, 80, 24),
        )
        self.assertGreater(background.red(), 230)
        self.assertLess(foreground.red(), 60)


if __name__ == "__main__":
    unittest.main(verbosity=2)
