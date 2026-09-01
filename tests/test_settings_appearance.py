"""The settings controls must match the application's palette.

Two things looked unfinished in the shipped window: the check boxes were the
platform's bright white squares on a dark purple window, and each engine combo
ended in an empty bordered rectangle where its arrow should be — a stylesheet
that touches ``QComboBox::drop-down`` suppresses the platform arrow, and Qt
fills a box instead of mitering CSS borders into a triangle.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import QPoint, QRect  # noqa: E402
from PyQt5.QtGui import QFontMetrics, QImage, QPainter  # noqa: E402
from PyQt5.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QStyle,
    QStyleOptionButton,
    QWidget,
)

import styled_dialogs  # noqa: E402
from settings_window import (  # noqa: E402
    DropDownCombo,
    OcrLanguageManagerDialog,
    SettingsWindow,
)


class _Parent(QWidget):
    def __init__(self, theme="Темная"):
        super().__init__()
        self.current_interface_language = "en"
        self.current_theme = theme
        self.config = {"autostart": False, "start_minimized": False,
                       "ocr_engine": "Tesseract", "translator_engine": "google"}
        self.start_minimized = False
        self.autostart = False

    def save_config(self):
        pass

    def set_autostart(self, value):
        return bool(value)


def _paint_indicator(checked, dark=True, size=20):
    """Render just the check box indicator and return the image."""
    style = styled_dialogs.AccentControlStyle(dark)
    option = QStyleOptionButton()
    option.rect = QRect(0, 0, size, size)
    option.state = QStyle.State_Enabled
    option.state |= QStyle.State_On if checked else QStyle.State_Off

    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    style.drawPrimitive(QStyle.PE_IndicatorCheckBox, option, painter, None)
    painter.end()
    return image


def _colors(image):
    return {image.pixelColor(x, y).name()
            for x in range(image.width()) for y in range(image.height())
            if image.pixelColor(x, y).alpha() > 40}


class CheckBoxIndicatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_checked_indicator_uses_the_accent_not_system_white(self):
        colors = _colors(_paint_indicator(checked=True))

        self.assertIn(styled_dialogs.ACCENT.lower(), colors)
        # The old native indicator was a white box; only the tick may be white.
        white = sum(1 for color in colors if color == "#ffffff")
        self.assertLessEqual(white, 1)

    def test_checked_indicator_draws_a_visible_tick(self):
        image = _paint_indicator(checked=True)
        ticks = sum(
            1
            for x in range(image.width())
            for y in range(image.height())
            if image.pixelColor(x, y).name() == "#ffffff"
        )
        self.assertGreater(ticks, 8, "the check mark disappeared")

    def test_unchecked_indicator_is_dark_on_the_dark_theme(self):
        colors = _colors(_paint_indicator(checked=False, dark=True))

        self.assertNotIn("#ffffff", colors)
        self.assertIn("#17181d", colors)

    def test_unchecked_indicator_is_light_on_the_light_theme(self):
        colors = _colors(_paint_indicator(checked=False, dark=False))

        self.assertIn("#ffffff", colors)

    def test_a_real_settings_check_box_paints_in_the_accent(self):
        """End to end: Qt wraps the style when a stylesheet is set, so assert on
        the pixels a check box actually produces rather than on its style object."""
        parent = _Parent()
        with mock.patch.object(SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"):
            settings = SettingsWindow(parent)
        try:
            self.assertIsInstance(
                getattr(settings, "_accent_control_style", None),
                styled_dialogs.AccentControlStyle,
                "the accent style was not installed or was garbage collected",
            )
            box = settings.findChild(QCheckBox)
            self.assertIsNotNone(box, "the settings window has no check boxes")
            box.setChecked(True)
            box.resize(box.sizeHint())

            image = QImage(box.size(), QImage.Format_ARGB32)
            image.fill(0)
            box.render(image)
            painted = _colors(image)

            self.assertIn(styled_dialogs.ACCENT.lower(), painted,
                          "the indicator is not drawn in the accent colour")
        finally:
            settings.close()
            parent.close()

    def test_language_rebuild_repaints_every_ocr_checkbox_in_the_accent(self):
        """Changing UI language rebuilds the settings widget tree.

        The rebuilt/reparented OCR boxes must not fall back to the native
        Windows white indicator seen in the regression screenshot.
        """
        parent = _Parent("Темная")
        with mock.patch.object(
            SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"
        ):
            settings = SettingsWindow(parent)
        try:
            settings.setFixedSize(672, 334)
            settings.show()
            self.app.processEvents()
            for language in ("ru", "en", "de", "fr", "es", "zh"):
                parent.current_interface_language = language
                settings.update_language()
                settings._set_settings_page(1)
                self.app.processEvents()

                for box in (
                    settings.keep_visible_checkbox,
                    settings.freeze_screen_checkbox,
                    settings.dim_screen_during_ocr_checkbox,
                    settings.restore_clipboard_checkbox,
                    settings.copy_notification_checkbox,
                    settings.update_check_on_launch_checkbox,
                ):
                    box.setChecked(True)
                    self.app.processEvents()
                    option = QStyleOptionButton()
                    box.initStyleOption(option)
                    indicator = box.style().subElementRect(
                        QStyle.SE_CheckBoxIndicator, option, box
                    )
                    painted = _colors(box.grab().toImage().copy(indicator))
                    self.assertIn(
                        styled_dialogs.ACCENT.lower(),
                        painted,
                        (language, box.text(), painted),
                    )
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()


class EngineComboTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _style_sheet(self, theme="Темная"):
        parent = _Parent(theme)
        with mock.patch.object(SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"):
            settings = SettingsWindow(parent)
        try:
            return settings._engine_combo_style()
        finally:
            settings.close()
            parent.close()

    def test_drop_down_carries_a_chevron_image(self):
        style = self._style_sheet()

        self.assertIn("QComboBox::drop-down", style)
        self.assertIn("chevron_down_dark.png", style)
        # A url() with backslashes is read as escapes and silently draws nothing.
        self.assertNotIn("\\", style.split("image: url(")[1].split(")")[0])

    def test_light_theme_uses_the_darker_chevron(self):
        self.assertIn("chevron_down_light.png", self._style_sheet("Светлая"))

    def test_the_chevron_images_exist_and_are_transparent_pngs(self):
        for name in ("chevron_down_dark.png", "chevron_down_light.png"):
            path = ROOT / "icons" / name
            self.assertTrue(path.is_file(), f"{name} is missing")
            image = QImage(str(path))
            self.assertFalse(image.isNull(), f"{name} is not a readable image")
            self.assertTrue(image.hasAlphaChannel(), f"{name} needs transparency")

    def test_the_empty_divider_box_is_gone(self):
        style = self._style_sheet()
        drop_down = style.split("QComboBox::drop-down")[1].split("}")[0]

        self.assertIn("border: none", drop_down)
        self.assertNotIn("border-left", drop_down)

    def test_the_spec_ships_the_icons_folder(self):
        for name in ("ClicknTranslate.spec", "ClicknTranslate-linux.spec"):
            self.assertIn("('icons', 'icons')", (ROOT / name).read_text(encoding="utf-8"), name)


class DropDownPlacementTest(unittest.TestCase):
    """The open list used to start one pixel inside the field, cutting through
    the coloured outline; with a long list it covered the field completely."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _settings(self):
        parent = _Parent()
        parent.config["result_window_hidden_modes"] = ["area"]
        with mock.patch.object(SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"):
            settings = SettingsWindow(parent)
        settings.show()
        self.app.processEvents()
        return parent, settings

    def test_every_drop_down_opens_clear_of_its_own_border(self):
        parent, settings = self._settings()
        try:
            for name in ("ocr_engine_combo", "translator_combo", "result_window_control"):
                combo = getattr(settings, name)
                combo.showPopup()
                self.app.processEvents()
                popup = combo.view().window()
                field_bottom = combo.mapToGlobal(QPoint(0, combo.height())).y()
                popup_top = popup.mapToGlobal(QPoint(0, 0)).y()

                self.assertGreaterEqual(popup_top, field_bottom, name)
                self.assertEqual(
                    popup.mapToGlobal(QPoint(0, 0)).x(),
                    combo.mapToGlobal(QPoint(0, 0)).x(),
                    name,
                )
                combo.hidePopup()
                self.app.processEvents()
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_all_three_pickers_share_the_placement(self):
        parent, settings = self._settings()
        try:
            for name in ("ocr_engine_combo", "translator_combo", "result_window_control"):
                self.assertIsInstance(getattr(settings, name), DropDownCombo, name)
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()


class DropDownFrameTest(unittest.TestCase):
    """Selectors stay visible on both bright and dark backgrounds."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _settings(self, theme="Темная"):
        parent = _Parent(theme)
        parent.config["result_window_hidden_modes"] = []
        with mock.patch.object(SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"):
            settings = SettingsWindow(parent)
        settings.show()
        self.app.processEvents()
        return parent, settings

    def test_a_subtle_visible_border_is_styled_in_both_themes(self):
        for theme, expected in (("Темная", "#3d3948"), ("Светлая", "#d7cde7")):
            parent, settings = self._settings(theme)
            try:
                field_rule = settings._engine_combo_style().split("QComboBox:hover")[0]
                self.assertIn(f"border: 1px solid {expected}", field_rule)
                self.assertNotIn("solid transparent", field_rule)
            finally:
                settings.close()
                parent.close()
                self.app.processEvents()

    def test_nothing_paints_a_frame_any_more(self):
        parent, settings = self._settings()
        try:
            for name in ("ocr_engine_combo", "translator_combo", "result_window_control"):
                combo = getattr(settings, name)
                self.assertIsInstance(combo, DropDownCombo, name)
                self.assertFalse(hasattr(combo, "_paint_crisp_frame"), name)
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_light_field_has_a_tinted_surface_and_focus_outline(self):
        parent, settings = self._settings("Светлая")
        try:
            style = settings._engine_combo_style()
            self.assertIn("background-color: #e9e4ed", style)
            self.assertIn("border-color: #8063a8", style)
            self.assertIn("border-radius: 7px", style)
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_opening_the_list_lifts_the_fill_instead(self):
        parent, settings = self._settings()
        try:
            combo = settings.translator_combo
            middle = (combo.width() // 2, combo.height() // 2)
            closed = combo.grab().toImage()
            closed_fill = closed.pixel(
                middle[0] * closed.width() // max(1, combo.width()),
                middle[1] * closed.height() // max(1, combo.height()),
            ) & 0xFFFFFF

            combo.showPopup()
            self.app.processEvents()
            opened = combo.grab().toImage()
            opened_fill = opened.pixel(
                middle[0] * opened.width() // max(1, combo.width()),
                middle[1] * opened.height() // max(1, combo.height()),
            ) & 0xFFFFFF
            combo.hidePopup()
            self.app.processEvents()

            self.assertNotEqual(closed_fill, opened_fill, "an open list must be visible somehow")
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_rebuilding_settings_hides_the_old_page_immediately(self):
        parent, settings = self._settings()
        try:
            old_widgets = [
                settings.autostart_checkbox,
                settings.ocr_engine_combo,
                settings.clear_cache_btn,
            ]
            self.assertTrue(all(not widget.isHidden() for widget in old_widgets))

            settings.clear_main_layout()

            self.assertTrue(all(widget.isHidden() for widget in old_widgets))
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()


class LanguagePackageTabsTest(unittest.TestCase):
    """Tab labels ran over each other: a tab bar measures its tabs with its own
    font but paints them with the stylesheet's, and only the stylesheet said
    14px, so every tab was sized for the 6pt default."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, lang="en"):
        parent = _Parent()
        parent.current_interface_language = lang
        with mock.patch.object(SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"):
            settings = SettingsWindow(parent)
        dialog = OcrLanguageManagerDialog(settings)
        dialog.show()
        self.app.processEvents()
        return parent, settings, dialog

    def _bars(self, dialog):
        return (
            ("sections", dialog.tabs),
            ("ocr", dialog.ocr_tabs),
            ("translation", dialog.translation_tabs),
        )

    def test_each_tab_is_wide_enough_for_its_own_label(self):
        for lang in ("en", "ru", "es", "de", "fr", "zh"):
            parent, settings, dialog = self._dialog(lang)
            try:
                for name, tab_widget in self._bars(dialog):
                    bar = tab_widget.tabBar()
                    metrics = QFontMetrics(bar.font())
                    for index in range(bar.count()):
                        label = bar.tabText(index)
                        self.assertGreaterEqual(
                            bar.tabRect(index).width(),
                            metrics.horizontalAdvance(label),
                            (lang, name, label),
                        )
                    # Tabs that do not fit get scroll arrows over them, which is
                    # the same unreadable row in another form. The dialog is a
                    # fixed width, so that is what they have to fit inside.
                    total = sum(bar.tabRect(i).width() for i in range(bar.count()))
                    self.assertLessEqual(total, dialog.width() - 24, (lang, name))
            finally:
                dialog.close()
                settings.close()
                parent.close()
                self.app.processEvents()

    def test_the_font_lives_on_the_bar_not_only_in_the_stylesheet(self):
        parent, settings, dialog = self._dialog()
        try:
            for name, tab_widget in self._bars(dialog):
                bar = tab_widget.tabBar()
                self.assertGreater(bar.font().pixelSize(), 8, name)
                # A font-size only in the stylesheet is what caused the overlap.
                self.assertNotIn("font-size", bar.styleSheet(), name)
                self.assertNotIn("font-family", bar.styleSheet(), name)
        finally:
            dialog.close()
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_the_table_ends_on_a_whole_row(self):
        """A half-drawn row against the bottom border reads as a glitch."""
        parent, settings, dialog = self._dialog()
        try:
            for _ in range(3):
                self.app.processEvents()
            table = dialog.windows_table or dialog.tesseract_table
            if table is None or table.rowCount() == 0:
                self.skipTest("no package table on this platform")
            inner = table.height() - table.horizontalHeader().height() - 2 * table.frameWidth()
            self.assertGreater(inner, 0)
            self.assertEqual(inner % table.rowHeight(0), 0)
            # The cap must not creep down each time the table is measured.
            height = table.height()
            for _ in range(4):
                dialog._snap_table_to_whole_rows(table)
                self.app.processEvents()
            self.assertEqual(table.height(), height)
        finally:
            dialog.close()
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_selecting_a_tab_does_not_change_its_text_width(self):
        parent, settings, dialog = self._dialog()
        try:
            for name, tab_widget in self._bars(dialog):
                style = tab_widget.tabBar().styleSheet()
                selected = style.split("::tab:selected")[1].split("}")[0]
                # A heavier selected tab would outgrow the width already
                # measured for it.
                self.assertNotIn("font-weight", selected, name)
        finally:
            dialog.close()
            settings.close()
            parent.close()
            self.app.processEvents()


class PopupFrameTest(unittest.TestCase):
    """The list is a window of its own, and its frame is not the list.

    On Linux that frame kept the platform default and showed as white bands down
    both sides of the drop-down. Windows never showed it because the frame there
    happens to match the list colour.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _settings(self, theme="Темная"):
        parent = _Parent(theme)
        parent.config["result_window_hidden_modes"] = []
        with mock.patch.object(SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"):
            settings = SettingsWindow(parent)
        settings.show()
        self.app.processEvents()
        return parent, settings

    def test_every_picker_knows_its_popup_colour(self):
        for theme, expected in (("Темная", "#20212a"), ("Светлая", "#f1edf4")):
            parent, settings = self._settings(theme)
            try:
                for name in ("ocr_engine_combo", "translator_combo", "result_window_control"):
                    combo = getattr(settings, name)
                    self.assertEqual(combo._popup_background, expected, (theme, name))
            finally:
                settings.close()
                parent.close()
                self.app.processEvents()

    def test_the_frame_is_painted_when_the_list_opens(self):
        parent, settings = self._settings()
        try:
            combo = settings.translator_combo
            combo.showPopup()
            self.app.processEvents()
            popup = combo.view().window()

            self.assertIn("#20212a", popup.styleSheet())
            self.assertTrue(popup.autoFillBackground())
            combo.hidePopup()
            self.app.processEvents()
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()

    def test_the_frame_follows_a_theme_change(self):
        parent, settings = self._settings()
        try:
            combo = settings.ocr_engine_combo
            self.assertEqual(combo._popup_background, "#20212a")

            parent.current_theme = "Светлая"
            settings.apply_theme()
            self.app.processEvents()

            self.assertEqual(combo._popup_background, "#f1edf4")
        finally:
            settings.close()
            parent.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
