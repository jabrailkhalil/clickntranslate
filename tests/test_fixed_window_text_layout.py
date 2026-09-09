"""Exercise the fixed viewport with real fonts, including Linux fallbacks."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QFontDatabase, QFontMetricsF
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QLabel, QStyle, QStyleOptionComboBox

import main
from settings_window import OpticallyCenteredPushButton
from qt_layout_test_support import ensure_layout_fonts


class FixedWindowTextLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        ensure_layout_fonts(cls.app)
        if not QFontDatabase().families():
            raise unittest.SkipTest("Geometry checks require real installed fonts")

    def setUp(self):
        for patch in (
            mock.patch.object(main, "LAYOUT_EDITOR_MODE", True),
            mock.patch.object(main.DarkThemeApp, "save_config"),
            mock.patch.object(main.DarkThemeApp, "sync_autostart_state", return_value=False),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.window = main.DarkThemeApp()
        self.window.config.update(ocr_engine="Tesseract", translator_engine="libretranslate")
        cached = mock.patch.object(main, "get_cached_config", return_value=self.window.config)
        cached.start()
        self.addCleanup(cached.stop)
        self.window.show()

    def tearDown(self):
        self.window.force_quit = True
        self.window.close()
        self.window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def settle(self):
        for _ in range(4):
            self.app.processEvents()

    @staticmethod
    def rect_in(root, widget):
        rect = widget.rect()
        rect.moveTopLeft(widget.mapTo(getattr(root, 'ui_root', root), QPoint()))
        return rect

    def test_main_reference_text_fits_with_the_longest_provider_name(self):
        for theme in ("Темная", "Светлая"):
            self.window.current_theme = theme
            for language in ("en", "ru", "de", "fr", "es", "zh"):
                with self.subTest(theme=theme, language=language):
                    self.window.current_interface_language = language
                    self.window.show_main_screen()
                    self.settle()
                    self.assertEqual((self.window.ui_root.width(), self.window.ui_root.height()), (700, 400))
                    self.assertEqual(self.rect_in(self.window, self.window.source_lang).left(),
                                     self.rect_in(self.window, self.window.hotkey_mode_combo).left())
                    self.assertEqual(self.rect_in(self.window, self.window.target_lang).right(),
                                     self.rect_in(self.window, self.window.hotkey_target_combo).right())
                    composer = self.rect_in(self.window, self.window.main_composer)
                    language_bottom = max(
                        self.rect_in(self.window, widget).bottom()
                        for widget in (self.window.source_lang, self.window.target_lang)
                    )
                    self.assertGreaterEqual(composer.top() - language_bottom - 1, 6)
                    mode_bar = self.rect_in(self.window, self.window.hotkey_language_bar)
                    shortcuts = self.rect_in(self.window, self.window.main_hotkey_area)
                    self.assertGreaterEqual(shortcuts.top() - mode_bar.bottom() - 1, 6)
                    bar = self.window.hotkey_language_bar
                    controls = (self.window.hotkey_mode_combo, self.window.hotkey_source_combo,
                                self.window.hotkey_language_swap, self.window.hotkey_target_combo)
                    rects = [self.rect_in(bar, control) for control in controls]
                    self.assertEqual(len({rect.top() for rect in rects}), 1)
                    self.assertEqual(len({rect.height() for rect in rects}), 1)
                    for rect in rects:
                        self.assertTrue(bar.rect().contains(rect))
                    for left, right in zip(rects, rects[1:]):
                        self.assertLess(left.right(), right.left())
                    combo = self.window.hotkey_mode_combo
                    option = QStyleOptionComboBox()
                    combo.initStyleOption(option)
                    text_area = combo.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, combo)
                    for index in range(combo.count()):
                        self.assertLessEqual(combo.fontMetrics().horizontalAdvance(combo.itemText(index)), text_area.width(), combo.itemText(index))
                    for name in ("mainOcrSummary", "mainTranslatorSummary"):
                        label = self.window.main_footer.findChild(QLabel, name)
                        self.assertLessEqual(label.sizeHint().width(), label.width(), label.text())
                        self.assertLessEqual(label.sizeHint().height(), label.height(), label.text())
                    for panel, name in (
                        (self.window.main_text_section, "mainTextSectionTitle"),
                        (self.window.main_shortcut_section, "mainShortcutSectionTitle"),
                    ):
                        label = panel.findChild(QLabel, name)
                        self.assertLessEqual(label.sizeHint().width(), label.width(), label.text())
                        self.assertLessEqual(label.sizeHint().height(), label.height(), label.text())
                        self.assertEqual(label.alignment(), Qt.AlignCenter)
                        self.assertAlmostEqual(self.rect_in(self.window, label).center().x(), 349, delta=1)
                        picker = self.window.source_lang if name == "mainTextSectionTitle" else self.window.hotkey_mode_combo
                        self.assertGreaterEqual(self.rect_in(self.window, picker).top() -
                                                self.rect_in(self.window, label).bottom() - 1, 6)
                    footer = self.window.main_footer
                    action = self.rect_in(self.window, self.window.start_button)
                    self.assertAlmostEqual(action.center().x(), 349, delta=1)
                    left = self.rect_in(self.window, footer.findChild(QLabel, "mainTranslatorSummary"))
                    right = self.rect_in(self.window, footer.findChild(QLabel, "mainOcrSummary"))
                    self.assertLess(left.right(), action.left())
                    self.assertLess(action.right(), right.left())
                    self.assertTrue(self.window.main_shortcut_section.rect().contains(
                        self.rect_in(self.window.main_shortcut_section, self.window.main_hotkey_area)))
                    area = self.window.main_hotkey_area
                    for pair in self.window.main_hotkey_references.values():
                        self.assertTrue(area.rect().contains(self.rect_in(area, pair)))
                        self.assertLess(pair.caption_label.geometry().right(), pair.value_label.geometry().left())
                        self.assertEqual(pair.caption_label.geometry().center().y(), pair.value_label.geometry().center().y())
                        for label in (pair.caption_label, pair.value_label):
                            if label.wordWrap():
                                self.assertLessEqual(label.heightForWidth(label.width()), label.height(), label.text())
                            else:
                                self.assertLessEqual(label.sizeHint().width(), label.width(), label.text())

    def test_multiline_input_keeps_the_expand_action_available_in_both_themes(self):
        for theme in ("Темная", "Светлая"):
            with self.subTest(theme=theme):
                self.window.current_theme = theme
                self.window.show_main_screen()
                self.settle()
                editor = self.window.text_input
                expand = self.window.main_result_expand_button
                editor.setFocus()
                for index, line in enumerate(("one", "two", "three", "four")):
                    if index:
                        QTest.keyClick(editor, Qt.Key_Return, Qt.ShiftModifier)
                    QTest.keyClicks(editor, line)
                self.settle()
                self.assertEqual(editor.toPlainText(), "one\ntwo\nthree\nfour")
                self.assertTrue(expand.isVisible())
                self.assertFalse(expand.icon().isNull())
                button_rect = self.rect_in(self.window.main_composer, expand)
                self.assertTrue(self.window.main_composer.rect().contains(button_rect))
                self.assertFalse(button_rect.intersects(
                    self.rect_in(self.window.main_composer, self.window.translate_button)
                ))
                with mock.patch.object(main, "show_translation_dialog") as opened:
                    QTest.mouseClick(expand, Qt.LeftButton)
                    self.assertEqual(opened.call_args.kwargs['source_text'], "one\ntwo\nthree\nfour")

                editor.setPlainText("A long paragraph with automatic line wrapping. " * 12)
                self.settle()
                self.assertEqual(editor.document().blockCount(), 1)
                self.assertTrue(expand.isVisible())
                self.assertTrue(expand.isEnabled())

                for text in ("one\ntwo", ""):
                    editor.setPlainText(text)
                    self.settle()
                    self.assertTrue(expand.isVisible())
                    self.assertTrue(expand.isEnabled())

    def test_main_panels_and_shadow_action_remain_visible_in_both_themes(self):
        def luminance(color):
            channels = [value / 255 for value in (color.red(), color.green(), color.blue())]
            linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
                      for value in channels]
            return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))

        def contrast(first, second):
            a, b = sorted((luminance(first), luminance(second)))
            return (b + .05) / (a + .05)

        for theme in ("Темная", "Светлая"):
            self.window.current_theme = theme
            self.window.show_main_screen()
            self.settle()
            screenshot = self.window.ui_root.grab().toImage()
            scale = screenshot.devicePixelRatio()
            for panel in (self.window.main_text_section, self.window.main_shortcut_section,
                          self.window.start_button):
                edge = panel.mapTo(self.window.ui_root, QPoint(0, panel.height() // 2))
                border = screenshot.pixelColor(round(edge.x() * scale), round(edge.y() * scale))
                outside = screenshot.pixelColor(round((edge.x() - 2) * scale), round(edge.y() * scale))
                self.assertGreaterEqual(contrast(border, outside), 2, (theme, panel.objectName()))
            button = self.window.start_button
            self.assertGreaterEqual(button.width(), button.sizeHint().width())
            fill = button.grab().toImage().pixelColor(button.width() // 2, 5)
            self.assertGreaterEqual(contrast(button.palette().buttonText().color(), fill), 4.5, theme)

    def test_settings_text_and_page_regions_fit_after_language_and_theme_changes(self):
        self.window.show_settings()
        settings = self.window.settings_window
        for theme in ("Темная", "Светлая"):
            self.window.current_theme = theme
            for language in ("en", "ru", "de", "fr", "es", "zh"):
                with self.subTest(theme=theme, language=language):
                    self.window.current_interface_language = language
                    settings.update_language()
                    self.settle()
                    self.assertEqual((settings.width(), settings.height()), (672, 346))
                    navigation = self.rect_in(self.window, settings.settings_page_navigation)
                    self.assertEqual(navigation.top(), self.window.title_bar.geometry().bottom() + 1)
                    self.assertLessEqual(abs(navigation.center().x() - self.window.ui_root.rect().center().x()), 1)
                    image = self.window.ui_root.grab().toImage()
                    ratio = image.devicePixelRatio()
                    # Just below the seam and above the tab buttons: this
                    # must be the same surface as the title bar, with no gap.
                    expected = main.window_header_color(theme != "Светлая")
                    self.assertEqual(image.pixelColor(
                        round((navigation.left() + 12) * ratio),
                        round((navigation.top() + 1) * ratio),
                    ).name(), expected)
                    rows = (
                        (settings.autostart_checkbox, settings.ocr_engine_label, settings.ocr_engine_combo),
                        (settings.start_minimized_checkbox, settings.translator_engine_label, settings.translator_combo),
                        (settings.copy_translated_checkbox, settings.result_window_label, settings.result_window_control),
                    )
                    for checkbox, label, combo in rows:
                        self.assertLessEqual(checkbox.sizeHint().width(), checkbox.width(), checkbox.text())
                        self.assertLessEqual(label.sizeHint().width(), label.width(), label.text())
                        box_rect, label_rect, combo_rect = [self.rect_in(settings, w) for w in (checkbox, label, combo)]
                        self.assertLess(box_rect.right(), label_rect.left())
                        self.assertLess(label_rect.right(), combo_rect.left())
                        self.assertEqual(box_rect.center().y(), combo_rect.center().y())
                    self.assertLess(
                        self.rect_in(settings, settings.history_checkbox).bottom(),
                        self.rect_in(settings, settings.settings_action_panel).top(),
                    )
                    for page in range(3):
                        settings._set_settings_page(page)
                        self.settle()
                        self.assertEqual(settings.settings_general_page.isVisible(), page == 0)
                        current = settings.settings_pages.currentWidget()
                        page_rect = self.rect_in(settings, current)
                        footer = self.rect_in(settings, settings.settings_page_footer)
                        self.assertGreaterEqual(page_rect.top() - footer.bottom() - 1, 12)
                        for tab in settings.settings_page_tabs:
                            self.assertTrue(tab.text())
                            font, area = tab.label_layout()
                            self.assertLessEqual(QFontMetricsF(font).boundingRect(tab.text()).width(), area.width())
                        buttons = current.findChildren(OpticallyCenteredPushButton)
                        for button in buttons:
                            font, area = button.label_layout()
                            bounds = QFontMetricsF(font).boundingRect(button.text())
                            self.assertLessEqual(bounds.width(), area.width(), button.text())
                            self.assertLessEqual(bounds.height(), area.height(), button.text())
                            self.assertTrue(current.rect().contains(self.rect_in(current, button)))

    def test_dynamic_tab_explains_the_mode_and_launches_the_real_action(self):
        self.window.show_settings()
        settings = self.window.settings_window
        settings.settings_page_tabs[2].click()
        self.settle()
        self.assertEqual(settings._settings_page_index, 2)
        self.assertTrue(settings.game_workflow_note.isVisible())
        self.assertTrue(settings.game_launch_button.isVisible())
        self.assertLess(
            self.rect_in(settings, settings.game_workflow_note).bottom(),
            self.rect_in(settings, settings.game_language_controls).top(),
        )
        with mock.patch.object(self.window, 'launch_game_translate') as launch:
            settings.game_launch_button.click()
        launch.assert_called_once_with()

    def test_attached_navigation_does_not_change_main_screen_spacing(self):
        self.settle()
        original_composer = self.rect_in(self.window, self.window.main_composer)
        for visit_hotkeys in (False, True):
            self.window.show_settings()
            self.settle()
            settings = self.window.settings_window
            if visit_hotkeys:
                settings.show_hotkeys_screen()
                self.settle()
                settings.back_from_hotkeys()
                self.settle()
            navigation = self.rect_in(self.window, settings.settings_page_navigation)
            self.assertEqual(navigation.top(), self.window.title_bar.geometry().bottom() + 1)
            self.window.show_main_screen()
            self.settle()
            self.assertEqual(self.rect_in(self.window, self.window.main_composer), original_composer)
            self.assertFalse(settings.settings_page_navigation.isVisible())

    def test_tab_selection_changes_painted_text_contrast_without_moving_the_strip(self):
        self.window.show_settings()
        settings = self.window.settings_window

        def text_contrast(tab, dark):
            image = self.window.ui_root.grab().toImage()
            ratio = image.devicePixelRatio()
            area = tab._label_area().translated(tab.mapTo(self.window.ui_root, QPoint()))
            levels = [
                image.pixelColor(x, y).lightness()
                for x in range(round(area.left() * ratio), round((area.right() + 1) * ratio))
                for y in range(round(area.top() * ratio), round((area.bottom() + 1) * ratio))
            ]
            return max(levels) if dark else 255 - min(levels)

        for theme in ("Темная", "Светлая"):
            self.window.current_theme = theme
            self.window.apply_theme()
            settings.update_language()
            self.settle()
            tabs = settings.settings_page_tabs
            positions = [tab.geometry() for tab in tabs]
            tabs[0].click()
            tabs[0].clearFocus()
            self.settle()
            active_contrast = text_contrast(tabs[0], theme == "Темная")
            tabs[2].click()
            self.settle()
            self.assertGreater(active_contrast, text_contrast(tabs[0], theme == "Темная") + 20)
            self.assertEqual(positions, [tab.geometry() for tab in tabs])
            self.assertEqual([tab.isChecked() for tab in tabs], [False, False, True])

    def test_main_action_captions_use_full_words(self):
        self.window.current_interface_language = 'ru'
        self.window.show_main_screen()
        for action, pair in self.window.main_hotkey_references.items():
            self.assertEqual(pair.caption_label.text(), main.main_hotkey_compact_caption('ru', action))
            self.assertNotIn('.', pair.caption_label.text())
            self.assertFalse(pair.caption_label.wordWrap())
            self.assertIs(pair.caption_label.parentWidget(), pair.value_label.parentWidget())


if __name__ == "__main__":
    unittest.main()
