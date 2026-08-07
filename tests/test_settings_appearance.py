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
    """The fields have no outline, on purpose.

    A hairline never rendered evenly: at fractional display scaling a 1px border
    is 2.5 device pixels, so Qt lit two rows fully and a third at half strength
    and one edge came out thicker and softer than the rest. The window is a
    fixed size, so the field could not be given room to fix it either. The field
    now reads from its own darker fill, and hover/focus change that fill.
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

    def test_no_visible_border_is_styled(self):
        parent, settings = self._settings()
        try:
            field_rule = settings._engine_combo_style().split("QComboBox::drop-down")[0]
            self.assertIn("border: 1px solid transparent", field_rule)
            # A coloured border in any state is the thing that looked crooked.
            self.assertNotIn("solid #", field_rule)
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

    def test_the_field_is_one_flat_colour_to_its_edges(self):
        """No stroke means the first row of pixels matches the middle."""
        for theme in ("Темная", "Светлая"):
            parent, settings = self._settings(theme)
            try:
                image = settings.translator_combo.grab().toImage()
                middle_x = image.width() // 2
                fill = image.pixel(middle_x, image.height() // 2) & 0xFFFFFF
                for y in (0, 1, image.height() - 2, image.height() - 1):
                    self.assertEqual(image.pixel(middle_x, y) & 0xFFFFFF, fill, (theme, y))
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


if __name__ == "__main__":
    unittest.main()
