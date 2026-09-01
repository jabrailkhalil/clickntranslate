import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import platform_support  # noqa: E402
from PyQt5.QtCore import QEvent, QPoint, Qt  # noqa: E402
from PyQt5.QtGui import QFontMetrics, QMouseEvent  # noqa: E402
from PyQt5.QtWidgets import QApplication, QComboBox, QStyle, QStyleOptionComboBox, QWidget  # noqa: E402

import main  # noqa: E402
from settings_window import (  # noqa: E402
    EASYOCR_ENGINE_DISPLAY,
    RAPIDOCR_ENGINE_DISPLAY,
    SettingsWindow,
    settings_text,
    _populate_grouped_ocr_combo,
    _populate_grouped_translator_combo,
)


class _SettingsParent(QWidget):
    def __init__(self):
        super().__init__()
        self.current_interface_language = "en"
        self.current_theme = "Темная"
        self.config = {
            "autostart": False,
            "start_minimized": False,
            "ocr_engine": "Tesseract",
            "translator_engine": "argos",
        }
        self.start_minimized = False
        self.autostart = False

    def save_config(self):
        pass

    def set_autostart(self, value):
        return bool(value)


class SettingsEngineLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _rect_in_settings(settings, widget):
        point = widget.mapTo(settings, QPoint(0, 0))
        return point.x(), point.y(), widget.width(), widget.height()

    def test_dynamic_page_note_never_hard_codes_the_configurable_shortcut(self):
        for language in ("en", "ru", "es", "de", "fr", "zh"):
            self.assertNotIn(
                "Ctrl+Alt+G",
                settings_text(language, "game_workflow_note"),
                language,
            )

    def test_installed_engines_are_first_inside_each_group(self):
        ocr_combo = QComboBox()
        _populate_grouped_ocr_combo(
            ocr_combo,
            "en",
            installed_engines={"EasyOCR", "Tesseract"},
        )
        ocr_values = [
            ocr_combo.itemData(index)
            for index in range(ocr_combo.count())
            if ocr_combo.itemData(index)
        ]
        self.assertEqual(ocr_values[:2], ["Tesseract", "EasyOCR"])
        expected_tail = ["Windows", "RapidOCR"] if platform_support.supports_windows_ocr() else ["RapidOCR"]
        self.assertEqual(ocr_values[2:], expected_tail)
        tesseract_index = ocr_combo.findData("Tesseract")
        self.assertIn("classic OCR", ocr_combo.itemData(tesseract_index, Qt.ToolTipRole))

        translator_combo = QComboBox()
        _populate_grouped_translator_combo(
            translator_combo,
            "en",
            installed_engines={"google", "hymt"},
        )
        offline_header = translator_combo.findText("  Offline")
        self.assertEqual(translator_combo.itemData(offline_header + 1), "hymt")
        self.assertGreater(translator_combo.findData("argos"), offline_header)
        self.assertIn("local LLM", translator_combo.itemData(offline_header + 1, Qt.ToolTipRole))

    def test_engine_rows_share_columns_and_vertical_centers(self):
        parent = _SettingsParent()
        parent.resize(700, 400)
        with mock.patch.object(SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"):
            settings = SettingsWindow(parent)
            settings.setGeometry(0, 0, 700, 400)
            parent.show()
            settings.show()
            self.app.processEvents()

            self.assertEqual(settings.translator_combo.itemText(0).strip(), "Online")
            self.assertFalse(settings.translator_combo.model().item(0).isEnabled())
            self.assertGreater(settings.translator_combo.findData("google"), 0)
            offline_header = settings.translator_combo.findText("  Offline")
            self.assertGreater(offline_header, 0)
            self.assertFalse(settings.translator_combo.model().item(offline_header).isEnabled())
            self.assertGreater(settings.translator_combo.findData("argos"), offline_header)
            self.assertEqual(settings._current_translator_engine_from_combo(), "argos")
            self.assertEqual(settings.ocr_engine_combo.itemText(0).strip(), "Offline")
            self.assertFalse(settings.ocr_engine_combo.model().item(0).isEnabled())
            if platform_support.supports_windows_ocr():
                self.assertGreater(settings.ocr_engine_combo.findData("Windows"), 0)
            else:
                self.assertEqual(settings.ocr_engine_combo.findData("Windows"), -1)

            ocr_label = self._rect_in_settings(settings, settings.ocr_engine_label)
            ocr_combo = self._rect_in_settings(settings, settings.ocr_engine_combo)
            tr_label = self._rect_in_settings(settings, settings.translator_engine_label)
            tr_combo = self._rect_in_settings(settings, settings.translator_combo)

            self.assertEqual(ocr_label[1] + ocr_label[3] / 2, ocr_combo[1] + ocr_combo[3] / 2)
            self.assertEqual(tr_label[1] + tr_label[3] / 2, tr_combo[1] + tr_combo[3] / 2)
            self.assertEqual(ocr_combo[0], tr_combo[0])
            self.assertEqual(ocr_combo[2], 180)
            self.assertEqual(tr_combo[2], 180)
            self.assertTrue(settings.ocr_engine_label.alignment() & Qt.AlignVCenter)
            self.assertTrue(settings.translator_engine_label.alignment() & Qt.AlignVCenter)
            # Engines are removed from their own tab in Language packages now.
            # The pickers carry no × of their own, so nothing sits over the
            # chevron and the combo needs no property to hide it.
            self.assertFalse(hasattr(settings, "ocr_engine_delete_btn"))
            self.assertFalse(hasattr(settings, "translator_engine_delete_btn"))
            self.assertIsNone(settings.ocr_engine_combo.property("engineDeleteVisible"))

            ocr_option = QStyleOptionComboBox()
            tr_option = QStyleOptionComboBox()
            settings.ocr_engine_combo.initStyleOption(ocr_option)
            settings.translator_combo.initStyleOption(tr_option)
            ocr_section = settings.ocr_engine_combo.style().subControlRect(
                QStyle.CC_ComboBox,
                ocr_option,
                QStyle.SC_ComboBoxArrow,
                settings.ocr_engine_combo,
            )
            tr_section = settings.translator_combo.style().subControlRect(
                QStyle.CC_ComboBox,
                tr_option,
                QStyle.SC_ComboBoxArrow,
                settings.translator_combo,
            )
            self.assertEqual(ocr_section, tr_section)
            # 24px is the drop-down width in _engine_combo_style; it was 31
            # while that area was a bordered divider with no arrow in it.
            self.assertEqual(ocr_section.width(), 24)

            action_rows = (
                (settings.clear_cache_btn, settings.reset_btn, settings.update_btn),
                (settings.ocr_languages_btn, settings.copy_history_btn, settings.translation_history_btn),
                (settings.hotkeys_button,),
            )
            action_rects = [
                [self._rect_in_settings(settings, button) for button in row]
                for row in action_rows
            ]
            for row, rects in zip(action_rows, action_rects):
                self.assertEqual({rect[1] for rect in rects}, {rects[0][1]})
                # Arbitrary host widths can leave one remainder pixel after
                # division into three columns. The real fixed 672px viewport
                # divides exactly; other test sizes may differ by at most one.
                self.assertLessEqual(max(rect[2] for rect in rects) - min(rect[2] for rect in rects), 1)
                self.assertEqual({rect[3] for rect in rects}, {29})
                for button in row:
                    self.assertNotIn("padding-bottom: 6px", button.styleSheet())
                    self.assertNotIn("padding-bottom: 12px", button.styleSheet())
                    self.assertIn("font-size: 16px", button.styleSheet())
                    self.assertEqual(button._label_offset_y, -3)
            self.assertEqual(
                [(rect[0], rect[2]) for rect in action_rects[0]],
                [(rect[0], rect[2]) for rect in action_rects[1]],
            )
            self.assertEqual(action_rects[2][0][0], action_rects[0][0][0])
            self.assertEqual(
                action_rects[2][0][0] + action_rects[2][0][2],
                action_rects[0][-1][0] + action_rects[0][-1][2],
            )
            settings.close()
            parent.close()
            self.app.processEvents()

    def _result_window_settings(self, lang="en", theme="Темная", hidden=()):
        parent = _SettingsParent()
        parent.current_interface_language = lang
        parent.current_theme = theme
        parent.config["result_window_hidden_modes"] = list(hidden)
        parent.setFixedSize(700, 400)
        settings = SettingsWindow(parent)
        settings.setFixedSize(690, 390)
        parent.show()
        settings.show()
        self.app.processEvents()
        return parent, settings

    def test_result_window_toggles_align_with_the_engine_rows(self):
        parent, settings = self._result_window_settings()
        control = settings.result_window_control

        ocr = self._rect_in_settings(settings, settings.ocr_engine_combo)
        translator = self._rect_in_settings(settings, settings.translator_combo)
        result = self._rect_in_settings(settings, control)
        # All three pickers are drop-downs now, so this one is exactly as wide
        # as an engine combo and the right column lines up.
        self.assertEqual(result[2], settings.ocr_engine_combo.width())
        self.assertEqual(result[3], settings.ocr_engine_combo.height())
        self.assertEqual(ocr[0] + ocr[2], result[0] + result[2])
        self.assertEqual(translator[0] + translator[2], result[0] + result[2])
        label = self._rect_in_settings(settings, settings.result_window_label)
        self.assertEqual(label[1] + label[3] / 2, result[1] + result[3] / 2)
        self.assertTrue(settings.result_window_label.alignment() & Qt.AlignVCenter)
        # It sits directly below the translator row and shares that row with
        # the next checkbox, so the left column no longer has a blank gap.
        self.assertGreater(result[1], translator[1])
        copy_translated = self._rect_in_settings(settings, settings.copy_translated_checkbox)
        self.assertLessEqual(
            abs((result[1] + result[3] / 2) -
                (copy_translated[1] + copy_translated[3] / 2)),
            3,
        )
        settings.close()
        parent.close()
        self.app.processEvents()

    def test_fixed_settings_rows_stay_top_anchored(self):
        """Adding a third selector must not push the checkbox stack down."""
        parent, settings = self._result_window_settings(lang="ru")
        try:
            autostart = self._rect_in_settings(settings, settings.autostart_checkbox)
            start_minimized = self._rect_in_settings(
                settings, settings.start_minimized_checkbox
            )
            copy_translated = self._rect_in_settings(
                settings, settings.copy_translated_checkbox
            )
            ocr = self._rect_in_settings(settings, settings.ocr_engine_combo)
            translator = self._rect_in_settings(settings, settings.translator_combo)
            result = self._rect_in_settings(settings, settings.result_window_control)

            self.assertEqual(autostart[1], settings.main_layout.contentsMargins().top())
            self.assertEqual(autostart[1], ocr[1])
            self.assertEqual(start_minimized[1], translator[1])
            self.assertEqual(copy_translated[1], result[1])
            self.assertTrue(settings.main_layout.alignment() & Qt.AlignTop)
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_the_three_modes_are_rows_in_the_dropdown(self):
        """The row used to be three inline buttons. It is a drop-down now, and
        the three actions stay independent switches rather than one choice."""
        parent, settings = self._result_window_settings()
        control = settings.result_window_control

        self.assertIsInstance(control, QComboBox)
        # Screen-area OCR and plain copy never open a result window, so they
        # must not be offered here; only these three modes actually show one.
        self.assertEqual(control.count(), len(main.RESULT_WINDOW_MODES) + 1)
        header = control.model().item(0)
        self.assertEqual(header.text(), settings_text("en", "result_window_modes_header"))
        self.assertFalse(header.isEnabled())
        self.assertIsNone(header.data(Qt.UserRole))

        for mode in main.RESULT_WINDOW_MODES:
            item = control._item(mode)
            self.assertIsNotNone(item, mode)
            # Rows spell the action out; "Text"/"Area"/"Main" only survive in
            # the closed summary, where there is no room for more.
            self.assertEqual(item.text(), settings_text("en", f"result_window_row_{mode}"))
            self.assertEqual(
                item.toolTip(), settings_text("en", f"result_window_mode_{mode}_tooltip")
            )
            # Every row carries its own indicator, so several can be on at once.
            self.assertFalse(item.icon().isNull(), mode)
        settings.close()
        parent.close()
        self.app.processEvents()

    def test_the_closed_dropdown_summarises_what_is_on(self):
        parent, settings = self._result_window_settings()
        control = settings.result_window_control

        self.assertEqual(control.summary_text(), settings_text("en", "result_window_summary_all"))

        control.toggle_mode("area")
        two_names = ", ".join((settings_text("en", "result_window_mode_selection"),
                               settings_text("en", "result_window_mode_main")))
        # Whether both names fit a 180px control depends on the font, so the
        # summary is the names when they fit and a count when they do not.
        # Either way it fits, and the tooltip always spells the names out.
        summary = control.summary_text()
        fits = QFontMetrics(control.font()).horizontalAdvance(two_names) <= control.available_text_width()
        self.assertEqual(
            summary,
            two_names if fits
            else settings_text("en", "result_window_summary_count").format(count=2, total=3),
        )
        # The tooltip is not width-bound, so it names the actions in full.
        long_names = ", ".join((settings_text("en", "result_window_row_selection"),
                                settings_text("en", "result_window_row_main")))
        self.assertEqual(control.detail_text(), long_names)
        self.assertIn(long_names, control.toolTip())

        for mode in main.RESULT_WINDOW_MODES:
            control.set_mode_checked(mode, False)
        self.assertEqual(control.summary_text(), settings_text("en", "result_window_summary_none"))
        settings.close()
        parent.close()
        self.app.processEvents()

    def test_a_ticked_row_means_show_and_saves_the_inverse_hidden_modes(self):
        parent, settings = self._result_window_settings()
        control = settings.result_window_control
        self.assertEqual(control.checked_modes(), main.RESULT_WINDOW_MODES)

        control.toggle_mode("selection")
        self.assertEqual(parent.config["result_window_hidden_modes"], ["selection"])

        control.toggle_mode("main")
        self.assertEqual(
            parent.config["result_window_hidden_modes"], ["selection", "main"]
        )

        control.toggle_mode("selection")
        self.assertEqual(parent.config["result_window_hidden_modes"], ["main"])
        settings.close()
        parent.close()
        self.app.processEvents()

    def test_every_language_says_what_the_row_controls(self):
        """"Show:" and one-word rows did not say show what, or after what."""
        for lang in ("en", "ru", "es", "de", "fr", "zh"):
            parent, settings = self._result_window_settings(lang=lang)
            control = settings.result_window_control

            header = settings_text(lang, "result_window_modes_header")
            self.assertTrue(header, lang)
            self.assertEqual(control.model().item(0).text(), header)
            for mode in main.RESULT_WINDOW_MODES:
                row = settings_text(lang, f"result_window_row_{mode}")
                short = settings_text(lang, f"result_window_mode_{mode}")
                self.assertTrue(row, (lang, mode))
                # A row says more than the abbreviation in the closed control.
                self.assertGreater(len(row), len(short), (lang, mode, row))
                self.assertEqual(control._item(mode).text(), row)
            # The label names the setting and still fits its own column.
            label = settings.result_window_label
            self.assertLessEqual(
                QFontMetrics(label.font()).horizontalAdvance(label.text()),
                label.width(),
                (lang, label.text()),
            )
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_the_copy_checkbox_label_is_never_clipped(self):
        """It shares its line with the Show-window picker, so anything past the
        box is drawn over by that control — which is what happened to the longer
        languages while the box was a flat 260px."""
        for lang in ("en", "ru", "es", "de", "fr", "zh"):
            parent, settings = self._result_window_settings(lang=lang)
            box = settings.copy_translated_checkbox
            self.assertGreaterEqual(box.width(), box.sizeHint().width(), (lang, box.text()))
            # Its own text must not be the thing that needs the room: the label
            # dropped "automatically", which was only ever restating the point.
            for word in ("automatically", "сразу", "automaticamente", "automatisch",
                         "automatiquement", "自动"):
                self.assertNotIn(word, box.text().lower(), (lang, box.text()))
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_the_rows_are_repainted_for_the_light_theme(self):
        """The ticks are pixmaps, so a theme switch has to redraw them rather
        than restyle them."""
        parent, settings = self._result_window_settings(hidden=("area",))
        control = settings.result_window_control
        # An unticked box is the one that carries the theme: a ticked one is
        # accent-filled in both palettes.
        before = control._item("area").icon().pixmap(18, 18).toImage()

        parent.current_theme = "Светлая"
        settings.apply_theme()
        self.app.processEvents()

        self.assertFalse(control._dark)
        after = control._item("area").icon().pixmap(18, 18).toImage()
        self.assertNotEqual(before, after)
        settings.close()
        parent.close()
        self.app.processEvents()

    def test_saved_modes_are_restored_when_the_screen_reopens(self):
        parent, settings = self._result_window_settings(hidden=("area", "main"))
        control = settings.result_window_control
        states = {
            mode: control.is_mode_checked(mode) for mode in main.RESULT_WINDOW_MODES
        }
        self.assertEqual(states, {"selection": True, "area": False, "main": False})
        settings.close()
        parent.close()
        self.app.processEvents()

    def test_the_summary_fits_the_closed_control_in_every_language(self):
        """The window cannot grow, so the summary has to fit at its widest."""
        for lang in ("en", "ru", "es", "de", "fr", "zh"):
            parent, settings = self._result_window_settings(lang=lang)
            label = settings.result_window_label
            control = settings.result_window_control
            metrics = QFontMetrics(control.font())
            usable = control.available_text_width()
            # Every combination the user can reach, including the ones whose
            # names are too long and have to collapse to a count.
            for bits in range(1 << len(main.RESULT_WINDOW_MODES)):
                on = [mode for index, mode in enumerate(main.RESULT_WINDOW_MODES)
                      if bits & (1 << index)]
                control.set_checked_modes(on)
                summary = control.summary_text()
                self.assertTrue(summary, (lang, on))
                self.assertLessEqual(
                    metrics.horizontalAdvance(summary), usable, (lang, on, summary)
                )
            self.assertLessEqual(
                QFontMetrics(label.font()).horizontalAdvance(label.text()),
                label.width(),
                (lang, label.text())
            )
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_the_new_row_does_not_push_content_out_of_the_fixed_window(self):
        for lang in ("en", "ru", "es", "de", "fr", "zh"):
            parent, settings = self._result_window_settings(lang=lang)
            lowest = max(
                child.mapTo(settings, child.rect().bottomLeft()).y()
                for child in settings.findChildren(QWidget)
                if child.isVisible()
            )
            self.assertLessEqual(lowest, settings.height(), lang)
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_update_check_lives_on_a_paged_settings_screen_and_is_saved(self):
        parent = _SettingsParent()
        parent.current_interface_language = "ru"
        parent.config["update_check_on_launch"] = False
        parent.setFixedSize(700, 400)
        with mock.patch.object(parent, "save_config") as save_config:
            settings = SettingsWindow(parent)
            # This is the actual viewport after the 700x400 main window pays
            # for its title bar and outer layout margins.
            settings.setFixedSize(672, 334)
            parent.show()
            settings.show()
            self.app.processEvents()

            self.assertEqual(settings._settings_page_index, 0)
            self.assertEqual(len(settings.settings_page_dots), 3)
            self.assertTrue(settings.settings_page_dots[0].isChecked())
            self.assertTrue(settings.settings_updates_page.isHidden())
            self.assertFalse(hasattr(settings, "version_label"))
            self.assertFalse(settings.update_check_on_launch_checkbox.isChecked())
            self.assertEqual(
                settings.update_check_on_launch_checkbox.text(),
                settings_text("ru", "update_check_on_launch"),
            )

            settings.settings_page_dots[1].click()
            self.app.processEvents()
            self.assertEqual(settings._settings_page_index, 1)
            self.assertTrue(settings.settings_page_dots[1].isChecked())
            self.assertTrue(settings.settings_updates_page.isVisible())
            self.assertTrue(settings.update_check_on_launch_checkbox.isVisible())
            self.assertTrue(settings.settings_action_panel.isHidden())

            settings.update_check_on_launch_checkbox.click()
            self.assertTrue(parent.config["update_check_on_launch"])
            save_config.assert_called_once()

            footer = self._rect_in_settings(settings, settings.settings_page_footer)
            self.assertLessEqual(footer[1] + footer[3], settings.height())
            overlay = self._rect_in_settings(settings, settings.settings_updates_page)
            self.assertLessEqual(overlay[1] + overlay[3], footer[1])

            settings.settings_page_dots[0].click()
            self.app.processEvents()
            hotkeys = self._rect_in_settings(settings, settings.hotkeys_button)
            self.assertLessEqual(hotkeys[1] + hotkeys[3], footer[1])
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_game_page_has_one_selected_area_workflow_and_saves_its_controls(self):
        parent = _SettingsParent()
        parent.config.update({
            "game_capture_mode": "region",
            "game_capture_interval_ms": 850,
            "game_overlay_opacity": 88,
            "game_pause_when_inactive": True,
            "game_show_original_text": False,
            "game_translate_source_language": "en",
            "game_translate_target_language": "ru",
        })
        with mock.patch.object(parent, "save_config"):
            settings = SettingsWindow(parent)
            settings.setFixedSize(672, 334)
            parent.show()
            settings.show()
            settings._set_settings_page(2)
            self.app.processEvents()
            try:
                self.assertTrue(settings.settings_game_page.isVisible())
                self.assertTrue(settings.settings_updates_page.isHidden())
                self.assertTrue(settings.settings_action_panel.isHidden())
                self.assertFalse(hasattr(settings, "game_capture_mode_combo"))
                self.assertIsInstance(settings.game_swap_button, main.LanguageSwapButton)
                self.assertEqual(settings.game_swap_button.text(), "")
                self.assertIn("foreground", settings.game_pause_inactive_checkbox.toolTip())
                settings.game_scan_interval_slider.setValue(1200)
                settings.game_overlay_opacity_slider.setValue(76)
                settings.game_pause_inactive_checkbox.click()
                settings.game_show_original_checkbox.click()
                self.assertEqual(parent.config["game_capture_interval_ms"], 1200)
                self.assertEqual(parent.config["game_overlay_opacity"], 76)
                self.assertFalse(parent.config["game_pause_when_inactive"])
                self.assertTrue(parent.config["game_show_original_text"])
                self.assertEqual(settings.game_scan_interval_slider.maximum(), 10000)
                settings.game_scan_interval_slider.setValue(10000)
                self.assertEqual(parent.config["game_capture_interval_ms"], 10000)
                self.assertEqual(settings.game_scan_interval_value.text(), "10.0 s")
                self.assertEqual(
                    settings.game_interval_controls.x(),
                    settings.game_opacity_controls.x(),
                )
            finally:
                settings.close()
                parent.close()
                self.app.processEvents()

    def test_secondary_page_controls_save_and_bug_report_uses_the_safe_creator(self):
        parent = _SettingsParent()
        parent.current_interface_language = "en"
        parent.config.update({
            "dim_screen_during_ocr": False,
            "ocr_dim_strength": 55,
            "restore_clipboard_after_selection": True,
            "notifications": False,
            "update_check_on_launch": True,
        })
        parent._create_bug_report = mock.Mock(return_value="report.zip")
        with mock.patch.object(
            SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"
        ):
            settings = SettingsWindow(parent)
        settings.setFixedSize(672, 334)
        parent.show()
        settings.show()
        settings._set_settings_page(1)
        self.app.processEvents()
        try:
            self.assertFalse(settings.ocr_dim_strength_slider.isEnabled())
            self.assertEqual(settings.ocr_dim_strength_slider.value(), 55)
            self.assertEqual(settings.ocr_dim_strength_value.text(), "55%")
            self.assertTrue(settings.restore_clipboard_checkbox.isChecked())
            self.assertFalse(settings.copy_notification_checkbox.isChecked())

            settings.dim_screen_during_ocr_checkbox.click()
            self.assertTrue(settings.ocr_dim_strength_slider.isEnabled())
            self.assertTrue(parent.config["dim_screen_during_ocr"])
            settings.ocr_dim_strength_slider.setValue(75)
            self.assertEqual(parent.config["ocr_dim_strength"], 75)
            self.assertEqual(settings.ocr_dim_strength_value.text(), "75%")

            settings.restore_clipboard_checkbox.click()
            settings.copy_notification_checkbox.click()
            self.assertFalse(parent.config["restore_clipboard_after_selection"])
            self.assertTrue(parent.config["notifications"])

            settings.create_bug_report_btn.click()
            parent._create_bug_report.assert_called_once_with(settings)
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_every_language_keeps_all_settings_pages_pixel_aligned(self):
        """Fixed-window geometry must survive a complete language rebuild."""
        parent = _SettingsParent()
        parent.setFixedSize(700, 400)
        with mock.patch.object(
            SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"
        ):
            settings = SettingsWindow(parent)
        settings.setFixedSize(672, 334)
        parent.show()
        settings.show()
        self.app.processEvents()

        action_names = (
            "clear_cache_btn",
            "reset_btn",
            "update_btn",
            "ocr_languages_btn",
            "copy_history_btn",
            "translation_history_btn",
            "hotkeys_button",
        )
        try:
            for theme in ("Темная", "Светлая"):
                parent.current_theme = theme
                theme_geometry = None
                for language in ("en", "ru", "es", "de", "fr", "zh"):
                    parent.current_interface_language = language
                    settings._set_settings_page(0)
                    settings.update_language()
                    self.app.processEvents()

                    geometry = tuple(
                        self._rect_in_settings(settings, getattr(settings, name))
                        for name in action_names
                    )
                    if theme_geometry is None:
                        theme_geometry = geometry
                    self.assertEqual(geometry, theme_geometry, (theme, language))

                    footer = self._rect_in_settings(
                        settings, settings.settings_page_footer
                    )
                    hotkeys = self._rect_in_settings(settings, settings.hotkeys_button)
                    self.assertLessEqual(hotkeys[1] + hotkeys[3], footer[1])
                    self.assertLessEqual(footer[1] + footer[3], settings.height())

                    rows = (
                        geometry[0:3],
                        geometry[3:6],
                        geometry[6:7],
                    )
                    for upper, lower in zip(rows, rows[1:]):
                        self.assertLessEqual(
                            max(rect[1] + rect[3] for rect in upper),
                            min(rect[1] for rect in lower),
                            (theme, language),
                        )

                    settings._set_settings_page(1)
                    self.app.processEvents()
                    overlay = self._rect_in_settings(
                        settings, settings.settings_updates_page
                    )
                    self.assertTrue(settings.settings_action_panel.isHidden())
                    self.assertLessEqual(overlay[1] + overlay[3], footer[1])
                    for widget in (
                        settings.keep_visible_checkbox,
                        settings.freeze_screen_checkbox,
                        settings.dim_screen_during_ocr_checkbox,
                        settings.ocr_dim_strength_value,
                        settings.ocr_dim_strength_slider,
                        settings.restore_clipboard_checkbox,
                        settings.copy_notification_checkbox,
                        settings.update_check_on_launch_checkbox,
                        settings.create_bug_report_btn,
                    ):
                        rect = self._rect_in_settings(settings, widget)
                        widget_name = (
                            widget.text() if hasattr(widget, "text")
                            else widget.objectName()
                        )
                        self.assertGreaterEqual(rect[0], overlay[0], (theme, language))
                        self.assertGreaterEqual(rect[1], overlay[1], (theme, language))
                        self.assertLessEqual(
                            rect[0] + rect[2], overlay[0] + overlay[2],
                            (theme, language, widget_name),
                        )
                        self.assertLessEqual(
                            rect[1] + rect[3], overlay[1] + overlay[3],
                            (theme, language, widget_name),
                        )

                    settings._set_settings_page(2)
                    self.app.processEvents()
                    game_page = self._rect_in_settings(
                        settings, settings.settings_game_page
                    )
                    self.assertTrue(settings.settings_game_page.isVisible())
                    self.assertTrue(settings.settings_updates_page.isHidden())
                    self.assertLessEqual(game_page[1] + game_page[3], footer[1])
                    for widget in (
                        settings.game_settings_heading,
                        settings.game_source_combo,
                        settings.game_swap_button,
                        settings.game_target_combo,
                        settings.game_scan_interval_slider,
                        settings.game_overlay_opacity_slider,
                        settings.game_pause_inactive_checkbox,
                        settings.game_show_original_checkbox,
                        settings.game_workflow_note,
                    ):
                        rect = self._rect_in_settings(settings, widget)
                        self.assertGreaterEqual(rect[0], game_page[0], (theme, language))
                        self.assertGreaterEqual(rect[1], game_page[1], (theme, language))
                        self.assertLessEqual(
                            rect[0] + rect[2], game_page[0] + game_page[2],
                            (theme, language, widget.objectName()),
                        )
                        self.assertLessEqual(
                            rect[1] + rect[3], game_page[1] + game_page[3],
                            (theme, language, widget.objectName()),
                        )

                    dot_centres = [
                        dot.mapTo(settings, QPoint(0, 0)).x() + dot.width() / 2
                        for dot in settings.settings_page_dots
                    ]
                    self.assertEqual(
                        sum(dot_centres) / len(dot_centres),
                        settings.width() / 2,
                        (theme, language, dot_centres),
                    )
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_neural_ocr_selection_never_runs_heavy_import_probe(self):
        parent, settings = self._result_window_settings()
        try:
            for engine, availability_name, heavy_probe_name in (
                (EASYOCR_ENGINE_DISPLAY, "_easyocr_runtime_installed", "_easyocr_importable_status"),
                (RAPIDOCR_ENGINE_DISPLAY, "_rapidocr_runtime_installed", "_rapidocr_importable_status"),
            ):
                parent.config["ocr_engine"] = "Windows"
                with mock.patch.object(settings, availability_name, return_value=True), mock.patch.object(
                    settings,
                    heavy_probe_name,
                    side_effect=AssertionError("heavy runtime probe reached the UI thread"),
                ) as heavy_probe:
                    settings.handle_ocr_engine_change(engine)
                heavy_probe.assert_not_called()
                self.assertEqual(parent.config["ocr_engine"], engine)
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_translator_combo_has_no_stale_delete_button_slot(self):
        parent, settings = self._result_window_settings()
        try:
            index = settings.translator_combo.findData("lingva")
            self.assertGreaterEqual(index, 0)
            settings.translator_combo.setCurrentIndex(index)
            self.app.processEvents()
            self.assertEqual(parent.config["translator_engine"], "lingva")
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
