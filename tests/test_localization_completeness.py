import inspect

import languages
import main
import ocr
import settings_window


SUPPORTED_INTERFACES = ("en", "ru", "es", "de", "fr", "zh")


def test_every_translation_dictionary_has_the_same_keys_for_all_interfaces():
    dictionaries = (
        main.INTERFACE_TEXT,
        main.HOTKEY_ERROR_TEXT,
        main.DOCUMENT_TEXT,
        main.WELCOME_TEXT,
        main.GUIDE_TEXT,
        main.HELP_ACTION_TEXT,
        main.ARGOS_PACKAGE_DIALOG_TEXT,
        main.ARGOS_ERROR_DIALOG_TEXT,
        main.TRANSLATION_RESULT_DIALOG_TEXT,
        settings_window.SETTINGS_TEXT,
        settings_window.TRANSLATOR_DETAIL_TEXT,
        settings_window.UPDATE_TEXT,
        settings_window.ENGINE_TEXT,
        settings_window.LANGUAGE_MANAGER_TEXT,
        ocr.OCR_UI_TEXT,
    )
    for dictionary in dictionaries:
        expected = set(dictionary["en"])
        assert expected
        for language in SUPPORTED_INTERFACES:
            assert set(dictionary[language]) == expected


def test_every_working_language_name_is_localized_for_every_interface():
    expected_codes = {language.code for language in languages.LANGUAGES}
    for interface_language in SUPPORTED_INTERFACES:
        assert set(languages.LOCALIZED_LANGUAGE_NAMES[interface_language]) == expected_codes


def test_package_manager_does_not_use_two_language_inline_fallbacks():
    source = inspect.getsource(settings_window.OcrLanguageManagerDialog)
    assert 'if self.lang == "ru" else' not in source
    assert "language_manager_text" in source


def test_previously_missing_chinese_controls_are_localized():
    assert settings_window.settings_text("zh", "ocr_language_packs") == "语言包"
    assert settings_window.language_manager_text("zh", "install_selected") == "安装所选项"
    assert main.ui_text("zh", "argos_package_missing_title") == "需要 Argos 语言包"
