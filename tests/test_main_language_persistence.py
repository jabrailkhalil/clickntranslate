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


class _LanguageHarness:
    _available_main_translation_pairs = main.DarkThemeApp._available_main_translation_pairs
    _main_translation_source_codes = main.DarkThemeApp._main_translation_source_codes
    _main_translation_target_codes = main.DarkThemeApp._main_translation_target_codes
    _configured_main_translation_pair = main.DarkThemeApp._configured_main_translation_pair
    _capture_main_translation_languages = main.DarkThemeApp._capture_main_translation_languages
    _restore_main_translation_languages = main.DarkThemeApp._restore_main_translation_languages
    _save_main_translation_languages = main.DarkThemeApp._save_main_translation_languages
    _refresh_selection_pair_hint = main.DarkThemeApp._refresh_selection_pair_hint
    _selected_text_translation_pair = main.DarkThemeApp._selected_text_translation_pair
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

    def test_selected_text_uses_exact_pair_from_main_screen(self):
        harness = _LanguageHarness({
            "main_translation_source_language": "ru",
            "main_translation_target_language": "tr",
        })
        harness._restore_main_translation_languages()

        self.assertEqual(harness._selected_text_translation_pair(), ("ru", "tr"))

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

    def test_guide_explains_selected_text_language_pair(self):
        for language_code in main.GUIDE_TEXT:
            back_home = next(
                body
                for action, _title, body in main.guide_text(language_code)["steps"]
                if action == "back_home"
            )
            self.assertIn("Ctrl+Alt+Q", back_home)


if __name__ == "__main__":
    unittest.main()
