import unittest

import languages
import translater


class TestLanguages(unittest.TestCase):
    def test_language_lists_include_more_than_ru_en(self):
        codes = {language.code for language in languages.LANGUAGES}

        self.assertIn("ru", codes)
        self.assertIn("en", codes)
        self.assertIn("de", codes)
        self.assertIn("zh", codes)
        self.assertGreaterEqual(len(codes), 12)

    def test_display_name_round_trip(self):
        self.assertEqual(languages.language_code_from_name("Немецкий", "ru"), "de")
        self.assertEqual(languages.language_code_from_name("German", "en"), "de")

    def test_ocr_and_tesseract_codes_are_available(self):
        self.assertEqual(languages.windows_ocr_tag("de"), "de-DE")
        self.assertEqual(languages.tesseract_language_code("de"), "deu")
        self.assertEqual(languages.tesseract_language_code("universal"), "eng+rus")

    def test_default_translation_target_keeps_russian_as_hub(self):
        self.assertEqual(languages.default_target_for_source("de"), "ru")
        self.assertEqual(languages.default_target_for_source("ru"), "en")
        self.assertEqual(languages.default_target_for_source("de", "en"), "en")
        self.assertEqual(languages.default_target_for_source("de", "de"), "ru")

    def test_detection_handles_common_scripts(self):
        self.assertEqual(languages.detect_language_code("你好"), "zh")
        self.assertEqual(languages.detect_language_code("こんにちは"), "ja")
        self.assertEqual(languages.detect_language_code("Привет"), "ru")
        self.assertEqual(languages.detect_language_code("Мир"), "ru")
        self.assertEqual(languages.detect_language_code("Привіт"), "uk")

    def test_detection_handles_latin_languages_better_than_diacritics_only(self):
        self.assertEqual(languages.detect_language_code("The settings file is open and ready to translate."), "en")
        self.assertEqual(languages.detect_language_code("Die Datei ist offen und bereit zum Übersetzen."), "de")
        self.assertEqual(languages.detect_language_code("Le fichier est ouvert pour la traduction."), "fr")
        self.assertEqual(languages.detect_language_code("El archivo está abierto para la traducción."), "es")
        self.assertEqual(languages.detect_language_code("O arquivo está aberto para tradução."), "pt")
        self.assertEqual(languages.detect_language_code("Plik jest gotowy do tłumaczenia."), "pl")
        self.assertEqual(languages.detect_language_code("Dosya çeviri için hazır."), "tr")

    def test_default_translation_target_for_auto_detection(self):
        self.assertEqual(languages.default_target_for_source("auto"), "ru")
        self.assertEqual(languages.default_target_for_source("auto", "en"), "en")

    def test_online_code_mapping_for_chinese(self):
        self.assertEqual(languages.translator_api_code("zh", "google"), "zh-CN")
        self.assertEqual(languages.translator_api_code("zh", "lingva"), "zh-CN")


class TestTranslatorMultilingualHelpers(unittest.TestCase):
    def test_hymt_prompt_uses_language_names(self):
        prompt = translater._build_hymt_prompt("Hallo", "de", "ru")

        self.assertIn("German", prompt)
        self.assertIn("Russian", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
