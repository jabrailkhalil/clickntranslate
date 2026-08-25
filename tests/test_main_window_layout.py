"""The main window has to say where to start.

It used to open with three stacked rows of language pickers — the hotkey pair
first, then the text pair — a 56px text box, an outlined Translate button and a
solid accent "Shadow mode" bar underneath it. Measured: 126px of language
pickers against 56px for the thing the window is for, and the only filled button
sent the window away.

The order now follows the task: pick a direction, type, translate. Everything
below the divider is settings and reference.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import QEvent, Qt  # noqa: E402
from PyQt5.QtGui import QImage, QTextCursor  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication, QFrame, QWidget  # noqa: E402

import main  # noqa: E402

LANGUAGES = ("en", "ru", "es", "de", "fr", "zh")


class MainScreenSourceTest(unittest.TestCase):
    """Assertions about how the screen is built, without building the app."""

    @staticmethod
    def _source():
        import inspect

        return inspect.getsource(main.DarkThemeApp.show_main_screen)

    def test_the_blocks_are_added_in_task_order(self):
        source = self._source()
        order = [
            "self.main_layout.addLayout(language_picker_layout)",
            "self.main_layout.addWidget(self.main_composer)",
            "self.main_layout.addWidget(divider)",
            "self.main_layout.addWidget(self.hotkey_language_bar)",
            "self.main_layout.addLayout(hotkey_grid)",
            "self.main_layout.addWidget(self.start_button)",
        ]
        positions = []
        for marker in order:
            self.assertIn(marker, source, marker)
            positions.append(source.index(marker))
        self.assertEqual(positions, sorted(positions), "the blocks are out of order")

    def test_the_direction_pair_is_one_row(self):
        source = self._source()
        self.assertIn("language_picker_layout = QHBoxLayout()", source)
        # Two stacked full-width combos read as two unrelated settings.
        self.assertNotIn("language_picker_layout = QVBoxLayout()", source)

    def test_translate_is_inside_the_chat_composer(self):
        source = self._source()
        translate = source[source.index("mainTranslateButton"):source.index("mainSectionDivider")]
        shadow = source[source.index("mainShadowButton"):]

        self.assertIn("composer_actions_layout.addWidget", translate)
        self.assertIn("Qt.AlignHCenter | Qt.AlignBottom", translate)
        self.assertIn("self.text_input.setViewportMargins(0, 0, 0, 0)", source)
        self.assertIn("self.text_input.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)", source)
        self.assertIn("self.main_layout.addWidget(self.main_composer)", translate)
        self.assertNotIn("self.main_layout.addWidget(self.translate_button)", translate)
        self.assertIn("self.translate_button = QPushButton()", source)
        self.assertIn("self.translate_button.setFixedSize(32, 32)", translate)
        self.assertIn("self.document_expand_button.hide()", source)
        self.assertIn("_apply_main_translate_button_theme", translate)
        self.assertIn("background: transparent", shadow)
        self.assertNotIn("background-color: #C5B3E9", shadow)

    def test_main_reference_text_keeps_a_readable_size(self):
        # The helper lives outside show_main_screen, so inspect it directly.
        import inspect

        helper = inspect.getsource(main.DarkThemeApp._create_main_hotkey_pair)
        theme = inspect.getsource(main.DarkThemeApp._apply_main_combo_theme)
        self.assertIn('font-size: 14px', helper)
        self.assertIn('font-size: 13px', helper)
        self.assertIn('font-size: 13px', theme)

    def test_the_text_box_has_room_to_be_the_focus(self):
        source = self._source()
        # 96 until the direction line went in under the Translate button; the
        # window is fixed at 700x400, so the line was paid for from here. Still
        # three lines of text, and still the tallest block on the screen.
        self.assertIn("self.main_composer.setFixedHeight(76)", source)
        self.assertIn("self.text_input.setFixedHeight(68)", source)


class HotkeyBarTextTest(unittest.TestCase):
    def test_every_language_has_a_short_caption_and_keeps_the_full_sentence(self):
        for language in LANGUAGES:
            caption = main.hotkey_language_text(language, "bar_caption")
            hint = main.hotkey_language_text(language, "bar_hint")
            self.assertTrue(caption, language)
            self.assertLessEqual(len(caption), 14, (language, caption))
            # The sentence is not lost: it became the bar's tooltip.
            self.assertGreater(len(hint), len(caption), language)

    def test_every_shortcut_has_localized_hover_help(self):
        for language in LANGUAGES:
            for action in ("copy", "ocr", "fullscreen", "selection", "replace", "toggle"):
                self.assertTrue(main.main_hotkey_tooltip(language, action), (language, action))


class MainWindowGeometryTest(unittest.TestCase):
    """Built for real, because heights are the whole point.

    Stop the app before running this: a live instance owns the single-instance
    handshake, and a second window built here waits on it forever.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        # The window opens its welcome dialog on a fresh config, and a modal
        # dialog in a test run waits for a click that never comes.
        welcome = mock.patch.object(main, "WelcomeDialog")
        welcome.start()
        self.addCleanup(welcome.stop)
        update_check = mock.patch.object(
            main.DarkThemeApp, "_maybe_check_updates_on_launch"
        )
        update_check.start()
        self.addCleanup(update_check.stop)
        guide = mock.patch.object(main.DarkThemeApp, "_maybe_start_first_run_guide")
        guide.start()
        self.addCleanup(guide.stop)
        hotkey_listener = mock.patch.object(main, "HotkeyListenerThread")
        hotkey_listener.start()
        self.addCleanup(hotkey_listener.stop)

        try:
            self.window = main.DarkThemeApp()
        except Exception as error:                      # pragma: no cover
            self.skipTest(f"the main window cannot be built here: {error}")
        self.window.show()
        for _ in range(6):
            self.app.processEvents()

    def tearDown(self):
        # closeEvent normally minimizes a live application to the tray. Tests
        # need a real shutdown so the next window does not inherit Qt objects
        # and background workers from the previous case.
        self.window.force_quit = True
        self.window.close()
        self.window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def _blocks(self):
        layout = self.window.main_layout
        return [layout.itemAt(index) for index in range(layout.count())]

    def test_the_chat_composer_stays_compact(self):
        # A Telegram-style composer is deliberately shorter than the settings
        # panel below it, while still fitting two placeholder/text lines.
        self.assertEqual(self.window.text_input.height(), 68)
        self.assertEqual(self.window.main_composer.height(), 76)

    def test_send_action_sits_below_and_to_the_right_of_the_text_view(self):
        button = self.window.translate_button
        text = self.window.text_input
        button_top_left = button.mapTo(self.window, button.rect().topLeft())
        text_top_left = text.mapTo(self.window, text.rect().topLeft())
        button_left = button_top_left.x()
        button_bottom = button_top_left.y() + button.height() - 1
        text_right = text_top_left.x() + text.width() - 1
        text_bottom = text_top_left.y() + text.height() - 1

        self.assertGreaterEqual(button_left, text_right)
        self.assertLessEqual(abs(button_bottom - text_bottom), 2)

    def test_long_input_offers_document_mode_without_a_scrollbar(self):
        editor = self.window.text_input
        expand = self.window.document_expand_button

        self.assertEqual(editor.verticalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)
        editor.setPlainText("one\ntwo")
        for _ in range(3):
            self.app.processEvents()
        self.assertFalse(expand.isVisible())

        editor.setPlainText("one\ntwo\nthree")
        for _ in range(3):
            self.app.processEvents()
        self.assertTrue(expand.isVisible())

    def test_document_workspace_reopens_and_receives_composer_text(self):
        text = "one\ntwo\nthree"
        self.window.text_input.setPlainText(text)
        for _ in range(3):
            self.app.processEvents()

        QTest.mouseClick(self.window.document_expand_button, Qt.LeftButton)
        self.app.processEvents()
        dialog = self.window.document_dialog
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.original_view.toPlainText(), text)

        dialog.close()
        self.app.processEvents()
        self.assertFalse(dialog.isVisible())
        reopened = self.window.open_document_translation()
        self.app.processEvents()
        self.assertIs(reopened, dialog)
        self.assertTrue(reopened.isVisible())

    def test_cached_document_workspace_uses_the_current_light_theme_when_reopened(self):
        dialog = self.window.open_document_translation()
        self.app.processEvents()
        dialog.close()
        self.app.processEvents()

        self.window.current_theme = "Светлая"
        reopened = self.window.open_document_translation()
        self.app.processEvents()

        self.assertIs(reopened, dialog)
        self.assertEqual(reopened.theme_name, "Светлая")
        style = reopened.styleSheet().lower()
        self.assertIn("background-color: #f3f5f8", style)
        self.assertIn("background-color: #ffffff", style)
        self.assertNotIn("background-color: #0e1116", style)

    def test_the_two_language_pickers_sit_on_one_line(self):
        source = self.window.source_lang
        target = self.window.target_lang

        self.assertEqual(source.y(), target.y())
        self.assertLess(source.x(), target.x())

    def test_document_workspace_has_a_persistent_title_bar_entry(self):
        button = self.window.document_button
        self.assertFalse(button.icon().isNull())
        self.assertEqual(
            button.accessibleName(),
            main.doc_text(self.window.current_interface_language, "title"),
        )
        self.assertLess(button.x(), self.window.help_button.x())
        self.assertLess(self.window.help_button.x(), self.window.settings_button.x())

    def test_document_icon_uses_black_and_white_variants_of_docs_png(self):
        def visible_rgb(icon):
            image = icon.pixmap(64, 64).toImage().convertToFormat(
                QImage.Format_ARGB32
            )
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    if color.alpha() >= 240:
                        return color.red(), color.green(), color.blue()
            self.fail("docs.png produced no opaque icon pixels")

        self.assertEqual(visible_rgb(main.document_translation_icon("Светлая")), (0, 0, 0))
        self.assertEqual(visible_rgb(main.document_translation_icon("Темная")), (255, 255, 255))

    def test_the_hotkey_bar_comes_after_the_translate_button(self):
        self.assertGreater(
            self.window.hotkey_language_bar.y(), self.window.translate_button.y()
        )

    def test_a_divider_separates_the_task_from_the_reference(self):
        dividers = [
            child for child in self.window.findChildren(QFrame)
            if child.objectName() == "mainSectionDivider"
        ]
        self.assertEqual(len(dividers), 1)
        divider = dividers[0]
        self.assertLess(divider.y(), self.window.hotkey_language_bar.y())
        self.assertGreater(divider.y(), self.window.translate_button.y())

    def test_the_mode_picker_is_sized_by_qt_not_by_a_guess(self):
        """The picker contains short action names while Qt chooses their width.

        The pixel result cannot be asserted here — the offscreen platform draws
        no text, so its metrics are fiction. This checks the sizing rule and the
        upper bound which preserves room for both language selectors.
        """
        import inspect

        source = inspect.getsource(main.DarkThemeApp._fit_hotkey_mode_combo)

        self.assertIn("AdjustToContents", source)
        self.assertIn("sizeHint().width()", source)
        self.assertGreaterEqual(self.window.hotkey_mode_combo.width(), 160)
        self.assertLessEqual(self.window.hotkey_mode_combo.width(), 200)
        for index in range(self.window.hotkey_mode_combo.count()):
            self.assertTrue(
                self.window.hotkey_mode_combo.itemData(index, Qt.ToolTipRole),
                index,
            )

    def test_the_shortcut_legend_keeps_six_chips_on_three_rows(self):
        """The old three-column minimum width exceeded the fixed main window.

        Two columns keep the full labels and key sequences readable while
        leaving the engine divider a real gutter instead of an overlap.
        """
        chips = self.window.findChildren(QWidget, "mainHotkeyPair")
        # Six hotkeys are registered, so six are listed. The legend showed five
        # and left translate-and-replace invisible.
        self.assertEqual(len(chips), 6)
        self.assertTrue(all(chip.toolTip() for chip in chips))
        self.assertIn(self.window.replace_hotkey_reference, chips)
        self.assertEqual(
            set(self.window.main_hotkey_references),
            {"copy", "ocr", "fullscreen", "selection", "replace", "toggle"},
        )
        self.assertEqual(set(self.window.main_hotkey_references.values()), set(chips))
        rows = {chip.mapTo(self.window, chip.rect().topLeft()).y() for chip in chips}
        self.assertEqual(len(rows), 3, "the legend should be three rows")

    def test_next_button_cannot_skip_multiple_cards_during_transition(self):
        self.window._guide_active = True
        self.window._guide_step_index = 3  # shortcut overview on the main screen
        self.window._show_guide_step()
        start = self.window._guide_step_index

        self.window.skip_current_guide_step()
        self.window.skip_current_guide_step()

        self.assertEqual(self.window._guide_step_index, start + 1)
        self.assertFalse(self.window._guide_skip_btn.isEnabled())
        self.window._guide_active = False
        self.window._guide_step_timer.stop()
        self.window._clear_guide_spotlight()
        self.window._guide_bubble.hide()

    def test_clicking_a_highlighted_control_also_locks_next_until_new_card(self):
        self.window._guide_active = True
        self.window._guide_step_index = 3
        self.window._show_guide_step()
        action = self.window._guide_current_action()

        self.window._complete_guide_step(action)
        self.window.skip_current_guide_step()

        self.assertEqual(self.window._guide_step_index, 4)
        self.assertFalse(self.window._guide_skip_btn.isEnabled())
        self.window._guide_active = False
        self.window._guide_step_timer.stop()
        self.window._clear_guide_spotlight()
        self.window._guide_bubble.hide()

    def test_every_tour_target_exists_in_the_view_where_it_is_explained(self):
        actions = [
            action
            for action, _title, _body in main.guide_text(
                self.window.current_interface_language
            )["steps"]
        ]
        settings_index = actions.index("settings")
        for action in actions[:settings_index + 1]:
            target = self.window._guide_target_widget(action)
            self.assertIsNotNone(target, action)
            self.assertTrue(target.isVisible(), action)

        self.window.show_settings()
        self.app.processEvents()
        for action in actions[settings_index + 1:-1]:
            target = self.window._guide_target_widget(action)
            self.assertIsNotNone(target, action)
            self.assertTrue(target.isVisible(), action)

        target = self.window._guide_target_widget("back_home")
        self.assertIsNotNone(target)
        self.assertTrue(target.isVisible())


class DirectionSummaryTest(unittest.TestCase):
    """The window shows two direction rows; this line says which is which.

    The pair at the top belongs to the typed text, the pair in the shortcut bar
    belongs to whichever shortcut mode is being edited, and each of the four
    modes keeps its own. Nothing on screen said so — a window reading
    "Russian to English" at the top and "English to Russian" below looks broken.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        welcome = mock.patch.object(main, "WelcomeDialog")
        welcome.start()
        self.addCleanup(welcome.stop)
        update_check = mock.patch.object(
            main.DarkThemeApp, "_maybe_check_updates_on_launch"
        )
        update_check.start()
        self.addCleanup(update_check.stop)
        guide = mock.patch.object(main.DarkThemeApp, "_maybe_start_first_run_guide")
        guide.start()
        self.addCleanup(guide.stop)
        hotkey_listener = mock.patch.object(main, "HotkeyListenerThread")
        hotkey_listener.start()
        self.addCleanup(hotkey_listener.stop)
        try:
            self.window = main.DarkThemeApp()
        except Exception as error:                      # pragma: no cover
            self.skipTest(f"the main window cannot be built here: {error}")
        # In-memory only: these tests never save, so the user's config is safe.
        self.window.config["main_translation_source_language"] = "ru"
        self.window.config["main_translation_target_language"] = "en"

    def tearDown(self):
        self.window.force_quit = True
        self.window.close()
        self.window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def _set_every_mode(self, source, target):
        for mode in main.HOTKEY_LANGUAGE_MODES:
            source_key, target_key = main.HOTKEY_LANGUAGE_CONFIG_KEYS[mode]
            self.window.config[source_key] = source
            self.window.config[target_key] = target

    def test_it_heads_the_mode_controls_inside_their_panel(self):
        import inspect

        source = inspect.getsource(main.DarkThemeApp.show_main_screen)
        heading = source.index("hotkey_bar_layout.addWidget(self.direction_summary)")
        controls = source.index("hotkey_bar_layout.addLayout(hotkey_row)")
        self.assertLess(heading, controls)

    def test_one_direction_everywhere_is_said_once(self):
        self._set_every_mode("ru", "en")

        text = self.window._direction_summary_text()

        self.assertIn("Russian", text)
        self.assertIn("English", text)
        # Four modes agreeing must not print four identical pairs.
        self.assertEqual(text.count("→"), 2)
        self.assertNotIn("(", text)

    def test_a_mode_that_differs_is_named(self):
        self._set_every_mode("ru", "en")
        source_key, target_key = main.HOTKEY_LANGUAGE_CONFIG_KEYS["fullscreen"]
        self.window.config[source_key] = "en"
        self.window.config[target_key] = "ru"

        text = self.window._direction_summary_text()

        fullscreen = main.ui_text(self.window.current_interface_language, "hotkey_fullscreen")
        self.assertIn(fullscreen, text)
        self.assertEqual(text.count("→"), 3)

    def test_it_names_the_typed_pair_and_the_shortcut_pair_apart(self):
        self._set_every_mode("en", "ru")

        text = self.window._direction_summary_text()
        language = self.window.current_interface_language

        self.assertIn(main.ui_text(language, "direction_typed"), text)
        self.assertIn(main.ui_text(language, "direction_shortcuts"), text)

    def test_the_short_form_keeps_the_modes_and_drops_the_spelling(self):
        """Which mode does what is the point of the line; "English" is not."""
        self._set_every_mode("ru", "en")
        source_key, target_key = main.HOTKEY_LANGUAGE_CONFIG_KEYS["selection"]
        self.window.config[source_key] = "en"
        self.window.config[target_key] = "ru"

        short = self.window._direction_summary_text(names=False)

        self.assertIn("RU", short)
        self.assertIn("EN", short)
        self.assertIn(
            main.ui_text(self.window.current_interface_language, "hotkey_selection"),
            short,
        )

    def test_reading_it_asks_no_engine_anything(self):
        """It redraws whenever a combo changes; inspecting installed OCR
        languages on every keystroke is not acceptable there."""
        with mock.patch.object(
            main.DarkThemeApp,
            "_available_hotkey_translation_pairs",
            side_effect=AssertionError("the summary must not probe the engines"),
        ):
            self.window._direction_summary_text()

    def test_main_and_hotkey_arrows_swap_their_own_language_pairs(self):
        for button in (
            self.window.main_language_swap,
            self.window.hotkey_language_swap,
        ):
            self.assertIsInstance(button, main.LanguageSwapButton)
            self.assertEqual(button.text(), "")

        self.window.config["translator_engine"] = "Google"
        self.window.config["main_translation_source_language"] = "en"
        self.window.config["main_translation_target_language"] = "ru"
        self.window._restore_main_translation_languages()

        self.window.main_language_swap.click()

        self.assertEqual(
            self.window._configured_main_translation_pair(),
            ("ru", "en"),
        )

        source_key, target_key = main.HOTKEY_LANGUAGE_CONFIG_KEYS["selection"]
        self.window.config["hotkey_language_editor_mode"] = "selection"
        self.window.config[source_key] = "en"
        self.window.config[target_key] = "ru"
        self.window._refresh_hotkey_language_controls()

        self.window.hotkey_language_swap.click()

        self.assertEqual(
            self.window._configured_hotkey_translation_pair("selection"),
            ("ru", "en"),
        )

    def test_the_label_carries_the_tooltip_style(self):
        """A widget with its own stylesheet resolves its tooltip against that
        sheet, so the app-wide purple QToolTip rule never reaches it."""
        self.assertIn("QToolTip", self.window.direction_summary.styleSheet())
        self.assertTrue(self.window.direction_summary.toolTip())

    def test_every_language_has_the_words(self):
        for language in LANGUAGES:
            for key in ("direction_typed", "direction_shortcuts", "direction_hint"):
                value = main.ui_text(language, key)
                self.assertTrue(value and value != key, (language, key))
            # The two labels share a line with two language pairs.
            self.assertLessEqual(
                len(main.ui_text(language, "direction_typed")), 16, language
            )
            self.assertLessEqual(
                len(main.ui_text(language, "direction_shortcuts")), 16, language
            )
            # The tooltip is where the explanation lives, so it is a sentence.
            self.assertGreater(len(main.ui_text(language, "direction_hint")), 40, language)


class TranslateOnEnterTest(unittest.TestCase):
    """Enter translates; Shift+Enter is how you get a new line.

    The box used to swallow Enter, so after typing you had to leave the
    keyboard and find the button.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.box = main.TranslateOnEnterTextEdit()
        self.asked = []
        self.box.translation_requested.connect(lambda: self.asked.append(True))

    def _press(self, key, modifiers=Qt.NoModifier):
        QTest.keyClick(self.box, key, modifiers)

    def test_enter_asks_for_a_translation_and_types_nothing(self):
        self.box.setPlainText("hola")
        self._press(Qt.Key_Return)

        self.assertEqual(len(self.asked), 1)
        self.assertEqual(self.box.toPlainText(), "hola")

    def test_shift_enter_makes_a_new_line_and_translates_nothing(self):
        self.box.setPlainText("hola")
        self.box.moveCursor(QTextCursor.End)
        self._press(Qt.Key_Return, Qt.ShiftModifier)

        self.assertEqual(self.asked, [])
        self.assertEqual(self.box.toPlainText().splitlines(), ["hola"])
        self.assertTrue(self.box.toPlainText().endswith("\n"))

    def test_the_keypad_enter_behaves_like_the_main_one(self):
        self._press(Qt.Key_Enter)

        self.assertEqual(len(self.asked), 1)

    def test_ctrl_enter_still_translates(self):
        """It was the only keyboard way to do it before; it still works."""
        self._press(Qt.Key_Return, Qt.ControlModifier)

        self.assertEqual(len(self.asked), 1)

    def test_ordinary_typing_is_untouched(self):
        QTest.keyClicks(self.box, "hola")

        self.assertEqual(self.asked, [])
        self.assertEqual(self.box.toPlainText(), "hola")

    def test_the_main_window_uses_this_box(self):
        import inspect

        source = inspect.getsource(main.DarkThemeApp.show_main_screen)
        self.assertIn("self.text_input = TranslateOnEnterTextEdit()", source)
        self.assertIn(
            "self.text_input.translation_requested.connect(self.translate_input_text)",
            source,
        )


class EngineDividerSpacingTest(unittest.TestCase):
    """The divider gets the same room on both sides, in every language.

    Two separate defects produced "the separator is right next to the words":
    the gap before it was 10 against 17 after it, and fixed column widths
    measured in English pushed the French and Spanish shortcuts past the line
    entirely. Pixels are measured on a real display by .tmp/check_separator.py —
    the offscreen platform draws no text, so its metrics are fiction. What is
    checkable here is the rule that produced them.
    """

    @staticmethod
    def _source():
        import inspect

        return inspect.getsource(main.DarkThemeApp.show_main_screen)

    def test_the_gap_before_the_divider_matches_the_gap_after_it(self):
        import re

        source = self._source()
        before = re.search(r"hotkey_grid\.setHorizontalSpacing\((\d+)\)", source)
        after = re.search(
            r"engine_status_layout\.setContentsMargins\((\d+),", source
        )
        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertEqual(int(before.group(1)), int(after.group(1)))
        self.assertGreaterEqual(int(before.group(1)), 12)

    def test_no_column_is_pinned_to_a_width_measured_in_one_language(self):
        self.assertNotIn("setColumnMinimumWidth", self._source())


class WindowEdgeTest(unittest.TestCase):
    """Content that touches the frame reads as a rendering fault.

    It sat 5px from every edge, and 5px under a 40px title bar.
    """

    TITLE_BAR_HEIGHT = 40

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_margins_leave_the_frame_alone(self):
        import inspect
        import re

        source = inspect.getsource(main.DarkThemeApp.__init__)
        found = re.search(
            r"self\.main_layout\.setContentsMargins\((\d+), (\d+), (\d+), (\d+)\)",
            source,
        )
        self.assertIsNotNone(found)
        left, top, right, bottom = (int(value) for value in found.groups())

        self.assertEqual(left, right)
        for name, value in (("left", left), ("right", right), ("bottom", bottom)):
            self.assertGreaterEqual(value, 12, name)
        # And the first row is not pressed against the title.
        self.assertGreaterEqual(top - self.TITLE_BAR_HEIGHT, 8)


class HotkeyLegendCoverageTest(unittest.TestCase):
    """Every hotkey the app registers has to be visible on the main screen.

    Six are registered; the legend listed five, so translate-and-replace
    (Ctrl+Shift+Q) existed and worked with nothing on screen saying so.
    """

    #: Every hotkey setting the app reads when it registers them.
    REGISTERED = (
        "copy_hotkey",
        "translate_hotkey",
        "fullscreen_translate_hotkey",
        "translate_selection_hotkey",
        "translate_replace_selection_hotkey",
        "toggle_window_hotkey",
    )

    def test_the_registration_list_is_what_this_test_thinks_it_is(self):
        """If a seventh hotkey is added, this fails before the legend does."""
        import inspect
        import re

        # The hotkeys are registered inline in the constructor.
        source = inspect.getsource(main.DarkThemeApp.__init__)
        found = set(re.findall(r'self\.config\.get\("([a-z_]+_hotkey)"', source))

        self.assertEqual(found, set(self.REGISTERED))

    def test_the_main_screen_shows_every_registered_hotkey(self):
        import inspect
        import re

        source = inspect.getsource(main.DarkThemeApp.show_main_screen)
        shown = set(re.findall(r'self\.config\.get\("([a-z_]+_hotkey)"', source))

        missing = sorted(set(self.REGISTERED) - shown)
        self.assertEqual(missing, [], f"registered but not shown: {missing}")

    def test_every_language_has_a_caption_for_each_one(self):
        captions = (
            "hotkey_copy",
            "hotkey_ocr_translate",
            "hotkey_fullscreen",
            "hotkey_selection",
            "hotkey_replace",
            "hotkey_toggle",
        )
        self.assertEqual(len(captions), len(self.REGISTERED))
        for language in LANGUAGES:
            for key in captions:
                caption = main.ui_text(language, key)
                self.assertTrue(caption and caption != key, (language, key))
                # Chips sit three to a row: a sentence does not fit.
                self.assertLessEqual(len(caption), 16, (language, key, caption))


if __name__ == "__main__":
    unittest.main()
