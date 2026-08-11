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
                self.assertEqual({rect[2] for rect in rects}, {rects[0][2]})
                self.assertEqual({rect[3] for rect in rects}, {36})
                for button in row:
                    self.assertNotIn("padding-bottom: 6px", button.styleSheet())
                    self.assertNotIn("padding-bottom: 12px", button.styleSheet())
                    self.assertIn("font-size: 16px", button.styleSheet())
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


if __name__ == "__main__":
    unittest.main()
