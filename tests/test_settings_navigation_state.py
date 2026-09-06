"""Behavioral checks for cached settings and language controls."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication

import main
import ocr
from qt_layout_test_support import ensure_layout_fonts


class SettingsNavigationStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        ensure_layout_fonts(cls.app)

    def setUp(self):
        for patch in (
            mock.patch.object(main, "LAYOUT_EDITOR_MODE", True),
            mock.patch.object(main.DarkThemeApp, "save_config"),
            mock.patch.object(main.DarkThemeApp, "sync_autostart_state", return_value=False),
            mock.patch.object(ocr, "installed_ocr_language_codes", return_value=["en", "ru", "de", "fr"]),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.window = main.DarkThemeApp()
        self.window.config.update(
            translator_engine="google", game_translate_source_language="en",
            game_translate_target_language="ru",
        )
        self.window.show()
        self.settle()

    def tearDown(self):
        self.window.force_quit = True
        self.window.close()
        self.window.deleteLater()
        self.settle()

    def settle(self):
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        for _ in range(3):
            self.app.processEvents()

    def open_game_page(self):
        self.window.show_settings()
        settings = self.window.settings_window
        settings._set_settings_page(2)
        self.settle()
        settings._verify_game_language_controls()
        return settings

    def test_reopening_settings_after_hotkey_editor_returns_to_general_tab(self):
        self.window.show_settings()
        settings = self.window.settings_window
        settings.show_hotkeys_screen()
        self.settle()
        self.window.show_main_screen()
        self.settle()
        self.window.show_settings()
        self.settle()
        self.assertIs(self.window.settings_window, settings)
        self.assertIsNone(settings._secondary_view_kind)
        self.assertEqual(settings.settings_pages.currentIndex(), 0)
        self.assertTrue(settings.settings_general_page.isVisible())

    def test_reopening_settings_after_history_does_not_use_deleted_pages(self):
        self.window.show_settings()
        settings = self.window.settings_window
        with mock.patch.object(settings, "load_history_embedded"):
            settings.show_history_view()
            self.settle()
            self.window.show_main_screen()
            self.settle()
            self.window.show_settings()
            self.settle()
        self.assertIsNone(settings._secondary_view_kind)
        self.assertEqual(settings.settings_pages.currentIndex(), 0)

    def test_show_settings_is_safe_when_it_is_already_open(self):
        self.window.show_settings()
        settings = self.window.settings_window
        self.window.show_settings()
        self.settle()
        self.assertIs(self.window.settings_window, settings)
        self.assertTrue(settings.isVisible())

    def test_game_page_reads_the_pair_changed_from_the_main_menu(self):
        settings = self.open_game_page()
        self.window.show_main_screen()
        self.settle()
        self.assertTrue(self.window._set_hotkey_translation_pair("game", "de", "fr"))
        self.open_game_page()
        self.assertEqual(settings.game_source_combo.currentData(), "de")
        self.assertEqual(settings.game_target_combo.currentData(), "fr")

    def test_game_page_refreshes_when_the_app_returns_from_the_tray(self):
        settings = self.open_game_page()
        self.window.hide()
        self.window.config.update(game_translate_source_language="de", game_translate_target_language="fr")
        self.window.show()
        self.settle()
        settings._verify_game_language_controls()
        self.assertEqual(settings.game_source_combo.currentData(), "de")
        self.assertEqual(settings.game_target_combo.currentData(), "fr")

    def test_game_page_rechecks_languages_after_switching_ocr_engines(self):
        settings = self.open_game_page()
        settings._set_settings_page(0)
        settings.save_ocr_engine("RapidOCR")
        with mock.patch.object(ocr, "installed_ocr_language_codes", return_value=["en", "zh"]):
            settings._set_settings_page(2)
            self.settle()
            settings._verify_game_language_controls()
        self.assertEqual(
            [settings.game_source_combo.itemData(i) for i in range(settings.game_source_combo.count())],
            ["en", "zh"],
        )

    def test_secondary_screens_survive_theme_change_and_return_after_deletion(self):
        self.window.show_settings()
        settings = self.window.settings_window
        for open_name, back_name in (
            ("show_hotkeys_screen", "back_from_hotkeys"),
            ("show_history_view", "back_from_history"),
            ("show_copy_history_view", "back_from_history"),
        ):
            with self.subTest(screen=open_name), mock.patch.object(settings, "load_history_embedded"), mock.patch.object(settings, "load_copy_history_embedded"):
                getattr(settings, open_name)()
                self.settle()
                self.window.toggle_theme()
                self.settle()
                self.assertIsNotNone(settings._secondary_view_kind)
                getattr(settings, back_name)()
                self.settle()
                self.assertTrue(settings.settings_general_page.isVisible())

    def test_game_sources_require_an_installed_translation_direction(self):
        self.window.config["translator_engine"] = "argos"
        with mock.patch.object(ocr, "_translation_targets_for_source", side_effect=lambda source, config: ["fr"] if source == "de" else []):
            settings = self.open_game_page()
        self.assertEqual(settings.game_source_combo.currentData(), "de")
        self.assertEqual(settings.game_target_combo.currentData(), "fr")

    def test_choosing_a_mode_does_not_overwrite_its_temporarily_unavailable_pair(self):
        self.window.config.update(
            ocr_translate_source_language="de", ocr_translate_target_language="fr",
            hotkey_language_editor_mode="selection",
        )
        with mock.patch.object(self.window, "_available_hotkey_translation_pairs", return_value={("en", "ru")}):
            self.window._refresh_hotkey_language_controls()
            self.window.hotkey_mode_combo.setCurrentIndex(self.window.hotkey_mode_combo.findData("ocr"))
        self.assertEqual(self.window.config["hotkey_language_editor_mode"], "ocr")
        self.assertEqual(self.window.config["ocr_translate_source_language"], "de")
        self.assertEqual(self.window.config["ocr_translate_target_language"], "fr")

    def test_language_dialog_does_not_overwrite_the_pair_just_by_opening(self):
        self.window.config.update(
            ocr_translate_source_language="de", ocr_translate_target_language="fr",
            hotkey_language_editor_mode="ocr",
        )
        with mock.patch.object(self.window, "_available_hotkey_translation_pairs", return_value={("en", "ru")}):
            dialog = main.HotkeyLanguageDialog(self.window)
        dialog.close()
        dialog.deleteLater()
        self.assertEqual(self.window.config["ocr_translate_source_language"], "de")
        self.assertEqual(self.window.config["ocr_translate_target_language"], "fr")


if __name__ == "__main__":
    unittest.main()
