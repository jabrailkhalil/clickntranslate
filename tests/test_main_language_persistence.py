import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
from PyQt5.QtCore import QEvent  # noqa: E402


def test_main_language_popup_uses_the_app_scrollbar_style():
    source = Path(main.__file__).read_text(encoding="utf-8")
    assert "self.source_lang = DropDownCombo()" in source
    assert "self.target_lang = DropDownCombo()" in source
    assert source.count("setMaxVisibleItems(9)") >= 2
    assert "QComboBox QAbstractItemView QScrollBar:vertical" in source
    assert "QComboBox QAbstractItemView QScrollBar::handle:vertical" in source
    assert "QComboBox QAbstractItemView QScrollBar::add-line:vertical" in source


class _LanguageHarness:
    _available_main_translation_pairs = main.DarkThemeApp._available_main_translation_pairs
    _main_translation_source_codes = main.DarkThemeApp._main_translation_source_codes
    _main_translation_target_codes = main.DarkThemeApp._main_translation_target_codes
    _configured_main_translation_pair = main.DarkThemeApp._configured_main_translation_pair
    _capture_main_translation_languages = main.DarkThemeApp._capture_main_translation_languages
    _restore_main_translation_languages = main.DarkThemeApp._restore_main_translation_languages
    _save_main_translation_languages = main.DarkThemeApp._save_main_translation_languages
    _hotkey_language_editor_mode = main.DarkThemeApp._hotkey_language_editor_mode
    _hotkey_for_translation_mode = main.DarkThemeApp._hotkey_for_translation_mode
    _available_hotkey_translation_pairs = (
        main.DarkThemeApp._available_hotkey_translation_pairs
    )
    _configured_hotkey_translation_pair = (
        main.DarkThemeApp._configured_hotkey_translation_pair
    )
    _set_hotkey_translation_pair = main.DarkThemeApp._set_hotkey_translation_pair
    _fill_hotkey_target_control = main.DarkThemeApp._fill_hotkey_target_control
    _refresh_hotkey_language_controls = (
        main.DarkThemeApp._refresh_hotkey_language_controls
    )
    # Borrowed too, because the pair setters refresh the line under the
    # Translate button; without it the harness raises where the app does not.
    _refresh_direction_summary = main.DarkThemeApp._refresh_direction_summary
    _direction_summary_text = main.DarkThemeApp._direction_summary_text
    _stored_hotkey_pair = main.DarkThemeApp._stored_hotkey_pair
    HOTKEY_MODE_CAPTION_KEYS = main.DarkThemeApp.HOTKEY_MODE_CAPTION_KEYS
    _refresh_selection_pair_hint = main.DarkThemeApp._refresh_selection_pair_hint
    _selected_text_translation_pair = main.DarkThemeApp._selected_text_translation_pair
    _replace_selected_text_translation_pair = (
        main.DarkThemeApp._replace_selected_text_translation_pair
    )
    update_languages = main.DarkThemeApp.update_languages

    def __init__(self, config, interface_language="en"):
        self.config = dict(config)
        self.current_interface_language = interface_language
        self.source_lang = main.QComboBox()
        self.source_lang.addItems(main.LANGUAGES[interface_language])
        self.target_lang = main.QComboBox()
        self.label = main.QLabel()
        self.save_count = 0

    def save_config(self):
        self.save_count += 1


class _LayoutHarness:
    clear_layout = main.DarkThemeApp.clear_layout
    _clear_nested_layout = main.DarkThemeApp._clear_nested_layout

    def __init__(self, host):
        self.main_layout = main.QVBoxLayout(host)


class MainLanguagePersistenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = main.QApplication.instance() or main.QApplication([])

    def test_saved_pair_is_restored_in_main_combos(self):
        harness = _LanguageHarness({
            "main_translation_source_language": "pt",
            "main_translation_target_language": "it",
        })
        harness._restore_main_translation_languages()

        self.assertEqual(harness.source_lang.currentText(), "Portuguese")
        self.assertEqual(harness.target_lang.currentText(), "Italian")
        self.assertEqual(harness.config["main_translation_source_language"], "pt")
        self.assertEqual(harness.config["main_translation_target_language"], "it")

    def test_pair_survives_interface_language_change_as_codes(self):
        config = {
            "main_translation_source_language": "ru",
            "main_translation_target_language": "pt",
        }
        english = _LanguageHarness(config, "en")
        english._restore_main_translation_languages()
        english._capture_main_translation_languages()

        russian = _LanguageHarness(english.config, "ru")
        russian._restore_main_translation_languages()

        self.assertEqual(russian.source_lang.currentText(), "Русский")
        self.assertEqual(russian.target_lang.currentText(), "Португальский")
        self.assertEqual(russian.config["main_translation_source_language"], "ru")
        self.assertEqual(russian.config["main_translation_target_language"], "pt")

    def test_changing_source_keeps_valid_target_and_saves_once(self):
        harness = _LanguageHarness({
            "main_translation_source_language": "pt",
            "main_translation_target_language": "it",
        })
        harness._restore_main_translation_languages()
        harness.source_lang.setCurrentText("Italian")
        harness.update_languages()

        self.assertNotEqual(harness.source_lang.currentText(), harness.target_lang.currentText())
        self.assertEqual(harness.config["main_translation_source_language"], "it")
        self.assertEqual(harness.config["main_translation_target_language"], "ru")
        self.assertEqual(harness.save_count, 1)

    def test_invalid_or_identical_codes_fall_back_to_valid_pair(self):
        invalid = _LanguageHarness({
            "main_translation_source_language": "unknown",
            "main_translation_target_language": "unknown",
        })
        self.assertEqual(invalid._configured_main_translation_pair(), ("en", "ru"))

        identical = _LanguageHarness({
            "main_translation_source_language": "ru",
            "main_translation_target_language": "ru",
        })
        self.assertEqual(identical._configured_main_translation_pair(), ("ru", "en"))

    def test_selected_text_uses_its_own_pair_not_the_main_screen_pair(self):
        harness = _LanguageHarness({
            "main_translation_source_language": "ru",
            "main_translation_target_language": "tr",
            "selection_translate_source_language": "es",
            "selection_translate_target_language": "de",
        })
        harness._restore_main_translation_languages()

        self.assertEqual(harness._selected_text_translation_pair(), ("es", "de"))

    def test_selection_and_replace_keep_independent_language_pairs(self):
        harness = _LanguageHarness({
            "selection_translate_source_language": "en",
            "selection_translate_target_language": "ru",
            "replace_selection_source_language": "de",
            "replace_selection_target_language": "fr",
        })

        self.assertEqual(harness._selected_text_translation_pair(), ("en", "ru"))
        self.assertEqual(
            harness._replace_selected_text_translation_pair(), ("de", "fr")
        )
        self.assertTrue(
            harness._set_hotkey_translation_pair("selection", "it", "es")
        )
        self.assertEqual(harness._selected_text_translation_pair(), ("it", "es"))
        self.assertEqual(
            harness._replace_selected_text_translation_pair(), ("de", "fr")
        )

    def test_hotkey_language_hint_exists_in_every_interface_language(self):
        for language_code in main.HOTKEY_LANGUAGE_TEXT:
            text = main.hotkey_language_text(language_code, "hint").format(
                mode=main.hotkey_language_text(language_code, "selection"),
                src="English",
                tgt="Russian",
                hotkey="Ctrl+Alt+Q",
            )
            self.assertIn("Ctrl+Alt+Q", text)
            self.assertIn("English", text)
            self.assertIn("Russian", text)
            self.assertIn("▾", text)

    def test_selection_pair_hint_exists_in_every_interface_language(self):
        for language_code in main.INTERFACE_TEXT:
            text = main.ui_text(language_code, "selection_pair_hint").format(
                src="English",
                tgt="Russian",
                hotkey="Ctrl+Alt+Q",
            )
            self.assertIn("Ctrl+Alt+Q", text)
            self.assertIn("English", text)
            self.assertIn("Russian", text)

    def test_main_hotkey_pairs_keep_every_character_visible(self):
        sequences = ("Ctrl+Alt+C", "Ctrl+Alt+T", "Ctrl+Alt+F", "Ctrl+Alt+Q", "Ctrl+Shift+Space")
        keys = ("hotkey_copy", "hotkey_ocr_translate", "hotkey_fullscreen", "hotkey_selection", "hotkey_toggle")
        for language_code in main.INTERFACE_TEXT:
            pairs = [
                main.DarkThemeApp._create_main_hotkey_pair(
                    main.ui_text(language_code, key), sequence
                )
                for key, sequence in zip(keys, sequences)
            ]
            for pair, sequence in zip(pairs, sequences):
                required = (
                    pair.caption_label.sizeHint().width()
                    + pair.value_label.sizeHint().width()
                    + pair.layout().spacing()
                    + pair.trailing_glyph_room
                )
                self.assertGreaterEqual(pair.width(), required, language_code)
                self.assertEqual(pair.value_label.text(), sequence)

            for pair in pairs:
                pair.close()

    def test_hotkey_keycap_frames_align_inside_each_grid_column(self):
        for language_code in main.INTERFACE_TEXT:
            first = [
                main.DarkThemeApp._create_main_hotkey_pair(
                    main.ui_text(language_code, key), sequence
                )
                for key, sequence in (
                    ("hotkey_copy", "Ctrl+Alt+C"),
                    ("hotkey_fullscreen", "Ctrl+Alt+F"),
                )
            ]
            second = [
                main.DarkThemeApp._create_main_hotkey_pair(
                    main.ui_text(language_code, key), sequence
                )
                for key, sequence in (
                    ("hotkey_ocr_translate", "Ctrl+Alt+T"),
                    ("hotkey_selection", "Ctrl+Alt+Q"),
                )
            ]
            try:
                for group in (first, second):
                    main.DarkThemeApp._align_main_hotkey_pair_group(*group)
                    self.assertEqual(len({pair.width() for pair in group}), 1)
                    self.assertEqual(
                        len({pair.value_label.width() for pair in group}), 1
                    )
                    self.assertEqual(
                        len({pair.caption_label.width() for pair in group}), 1
                    )
            finally:
                for pair in first + second:
                    pair.close()

    def test_switching_pages_hides_old_widgets_before_deferred_delete(self):
        host = main.QWidget()
        harness = _LayoutHarness(host)
        direct = main.QPushButton("old page")
        nested_layout = main.QHBoxLayout()
        nested = main.QLabel("old nested row")
        nested_layout.addWidget(nested)
        harness.main_layout.addWidget(direct)
        harness.main_layout.addLayout(nested_layout)
        host.show()
        self.app.processEvents()
        self.assertTrue(direct.isVisible())
        self.assertTrue(nested.isVisible())

        harness.clear_layout()

        self.assertFalse(direct.isVisible())
        self.assertFalse(nested.isVisible())
        host.close()
        self.app.processEvents()

    def test_language_popup_is_capped_and_scrollable_on_native_popup_styles(self):
        combo = main.DropDownCombo()
        combo.resize(320, 36)
        combo.setMaxVisibleItems(9)
        combo.addItems(main.LANGUAGES["en"])
        combo.set_popup_background("#1e1e1e")
        combo.show()
        combo.showPopup()
        self.app.processEvents()

        popup = combo.view().window()
        row_height = max(24, combo.view().sizeHintForRow(0))
        self.assertLessEqual(popup.height(), row_height * 9 + 12)
        self.assertGreater(combo.view().verticalScrollBar().maximum(), 0)
        self.assertIn("selection-background-color: #7A5FA1", combo.view().styleSheet())
        self.assertIn("QScrollBar::handle:vertical", combo.view().styleSheet())

        combo.hidePopup()
        combo.close()
        self.app.processEvents()

    def test_theme_switch_ignores_main_selectors_deleted_on_the_settings_page(self):
        stale = main.DropDownCombo()
        live = main.DropDownCombo()
        stale.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        harness = SimpleNamespace(
            source_lang=stale,
            target_lang=live,
            _apply_main_translate_button_theme=lambda _is_dark: None,
        )

        main.DarkThemeApp._apply_main_combo_theme(harness, False)

        self.assertIsNone(harness.source_lang)
        self.assertIn("background-color: #f6f3fa", live.styleSheet())
        live.close()
        self.app.processEvents()

    def test_active_guide_card_is_retranslated_immediately(self):
        harness = SimpleNamespace(
            current_interface_language="ru",
            _guide_active=True,
            _show_guide_step=mock.Mock(),
            settings_window=None,
        )
        with mock.patch.object(main.QTimer, "singleShot") as single_shot:
            main.DarkThemeApp.refresh_interface_language_ui(harness)

        single_shot.assert_called_once_with(0, harness._show_guide_step)

    def test_guide_says_the_shortcuts_carry_their_own_pair(self):
        """It used to say the main screen's pair drove Ctrl+Alt+Q and
        Ctrl+Shift+Q. Each of the four shortcut modes keeps its own pair, set
        in the shortcut row, and the line under Translate spells out which is
        which. Telling people otherwise is what makes the window look broken
        when the top row and the shortcut row disagree.
        """
        clues = {
            "en": "shortcut",
            "ru": "клавиш",
            "es": "atajo",
            "de": "Kürzel",
            "fr": "raccourci",
            "zh": "快捷键",
        }
        self.assertEqual(set(clues), set(main.GUIDE_TEXT))
        for language_code, clue in clues.items():
            back_home = next(
                body
                for action, _title, body in main.guide_text(language_code)["steps"]
                if action == "back_home"
            )
            self.assertIn(clue, back_home, language_code)

    def test_guide_and_faq_explain_the_window_hotkey(self):
        clues = {
            "en": "Window",
            "ru": "Окно",
            "es": "Ventana",
            "de": "Fenster",
            "fr": "Fenêtre",
            "zh": "窗口",
        }
        for language_code, clue in clues.items():
            guide = "\n".join(
                f"{title}\n{body}"
                for _action, title, body in main.guide_text(language_code)["steps"]
            )
            faq = "\n".join(
                item for _title, items in main.HELP_CONTENT[language_code] for item in items
            )
            self.assertIn(clue, guide)
            # The guide quotes only the two shortcuts whose difference matters
            # here. Other combinations are user-configurable and their current
            # values are already visible in the main-window chips.
            self.assertIn("Ctrl+Alt+Q", guide)
            self.assertIn("Ctrl+Shift+Q", guide)
            self.assertIn(clue, faq)

    def test_guide_explains_result_window_picker_in_every_language(self):
        for language_code in main.GUIDE_TEXT:
            actions = [
                action
                for action, _title, _body in main.guide_text(language_code)["steps"]
            ]
            self.assertIn("result_window", actions)
            self.assertLess(actions.index("translator"), actions.index("result_window"))
            self.assertLess(actions.index("result_window"), actions.index("language_packages"))

    def test_guide_explains_every_main_shortcut_before_opening_settings(self):
        shortcut_steps = [
            "shortcut_overview",
            "shortcut_copy",
            "shortcut_ocr",
            "shortcut_fullscreen",
            "shortcut_selection",
            "shortcut_replace",
            "shortcut_toggle",
            "document_translation",
        ]
        for language_code in main.GUIDE_TEXT:
            actions = [
                action
                for action, _title, _body in main.guide_text(language_code)["steps"]
            ]
            first_shortcut = actions.index(shortcut_steps[0])
            self.assertEqual(
                actions[first_shortcut:first_shortcut + len(shortcut_steps)],
                shortcut_steps,
                language_code,
            )
            self.assertLess(actions.index("help"), first_shortcut, language_code)
            self.assertLess(
                actions.index("document_translation"),
                actions.index("settings"),
                language_code,
            )
            self.assertEqual(actions[-1], "back_home", language_code)

    def test_russian_tour_uses_next_instead_of_skip(self):
        self.assertEqual(main.guide_text("ru")["skip"], "Далее")

    def test_lower_settings_guide_card_stays_above_action_buttons(self):
        host = main.QWidget()
        host.resize(700, 400)
        host._guide_waiting_action = "language_packages"
        host._guide_bubble = main.QFrame(host)
        host._guide_bubble.setFixedSize(430, 190)
        buttons = []
        for index in range(3):
            button = main.QPushButton(host)
            button.setGeometry(5 + index * 225, 278, 225, 36)
            button.show()
            buttons.append(button)
        target = buttons[0]
        host.show()
        self.app.processEvents()

        main.DarkThemeApp._position_guide_bubble(host, target)

        self.assertLess(host._guide_bubble.geometry().bottom(), target.geometry().top())
        for button in buttons:
            self.assertFalse(host._guide_bubble.geometry().intersects(button.geometry()))
        host.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
