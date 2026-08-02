import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402


class _LanguageHarness:
    _configured_main_translation_pair = main.DarkThemeApp._configured_main_translation_pair
    _capture_main_translation_languages = main.DarkThemeApp._capture_main_translation_languages
    _restore_main_translation_languages = main.DarkThemeApp._restore_main_translation_languages
    _save_main_translation_languages = main.DarkThemeApp._save_main_translation_languages
    update_languages = main.DarkThemeApp.update_languages

    def __init__(self, config, interface_language="en"):
        self.config = dict(config)
        self.current_interface_language = interface_language
        self.source_lang = main.QComboBox()
        self.source_lang.addItems(main.LANGUAGES[interface_language])
        self.target_lang = main.QComboBox()
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


if __name__ == "__main__":
    unittest.main()
