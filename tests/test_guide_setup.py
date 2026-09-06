"""Exercise real onboarding controls without writing settings or OS startup."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5.QtCore import QEvent, QPoint, QRect
from PyQt5.QtWidgets import QApplication

import main
import ocr
from guide_setup import GUIDE_SETTING_STEPS, GUIDE_SETUP_ORDER, setup_labels
from qt_layout_test_support import ensure_layout_fonts


class GuideSetupTest(unittest.TestCase):
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
        patch = mock.patch.object(main.DarkThemeApp, "set_autostart", side_effect=lambda enabled: enabled)
        self.autostart = patch.start()
        self.addCleanup(patch.stop)
        self.window = main.DarkThemeApp()
        self.window.config.update(main.DEFAULT_CONFIG)
        self.window.show()
        self.settle()

    def tearDown(self):
        self.window._guide_active = False
        self.window._guide_step_timer.stop()
        self.window.force_quit = True
        self.window.close()
        self.window.deleteLater()
        self.settle()

    def settle(self):
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        for _ in range(3):
            self.app.processEvents()

    def show_step(self, action):
        self.window._guide_active = True
        self.window._guide_step_index = GUIDE_SETUP_ORDER.index(action)
        self.window._show_guide_step()
        self.settle()
        self.window._guide_step_timer.stop()
        return self.window._guide_target_widget(action)

    def test_opening_and_skipping_never_enable_settings(self):
        before = dict(self.window.config)
        self.show_step("autostart")
        self.assertEqual(self.window.config, before)
        self.window._guide_skip_btn.click()
        self.autostart.assert_not_called()
        self.assertFalse(self.window.config["autostart"])
        self.assertEqual(self.window._guide_current_action(), "start_minimized")

    def test_primary_enables_via_backend_and_advances_once(self):
        self.show_step("autostart")
        self.window._guide_primary_btn.click()
        self.window._guide_primary_btn.click()
        self.window._guide_skip_btn.click()
        self.autostart.assert_called_once_with(True)
        self.assertTrue(self.window.config["autostart"])
        self.assertEqual(self.window._guide_current_action(), "start_minimized")

    def test_failed_os_registration_stays_on_the_step(self):
        self.autostart.side_effect = lambda enabled: False
        target = self.show_step("autostart")
        self.window._guide_primary_btn.click()
        self.assertFalse(target.isChecked())
        self.assertFalse(self.window.config["autostart"])
        self.assertEqual(self.window._guide_current_action(), "autostart")
        self.assertEqual(self.window._guide_hint.text(), setup_labels(self.window.current_interface_language)["failed"])
        self.assertTrue(self.window._guide_primary_btn.isEnabled())

    def test_already_configured_setting_is_not_toggled_off(self):
        self.window.config["autostart"] = True
        target = self.show_step("autostart")
        self.window._guide_primary_btn.click()
        self.assertTrue(target.isChecked())
        self.autostart.assert_not_called()
        self.assertEqual(self.window._guide_current_action(), "start_minimized")

    def test_manual_checkbox_change_advances_only_after_saving(self):
        target = self.show_step("copy_translated_text")
        self.window._complete_guide_step("copy_translated_text")
        self.assertEqual(self.window._guide_current_action(), "copy_translated_text")
        target.click()
        self.assertTrue(self.window.config["copy_translated_text"])
        self.assertEqual(self.window._guide_current_action(), "history")

    def test_result_window_applies_every_mode(self):
        self.window.config["result_window_hidden_modes"] = main.RESULT_WINDOW_MODES
        target = self.show_step("result_window")
        self.window._guide_primary_btn.click()
        self.assertEqual(set(target.checked_modes()), set(main.RESULT_WINDOW_MODES))
        self.assertFalse(main.result_window_hidden_modes(self.window.config))
        self.assertEqual(self.window._guide_current_action(), "language_packages")

    def test_full_primary_flow_configures_all_recommendations(self):
        self.show_step("settings")
        for action in GUIDE_SETUP_ORDER:
            self.assertEqual(self.window._guide_current_action(), action)
            self.window._guide_primary_btn.click()
            self.window._guide_step_timer.stop()
            self.settle()
            self.window._show_guide_step()
            self.settle()
        self.assertFalse(self.window._guide_active)
        for action, (_widget, _page, desired) in GUIDE_SETTING_STEPS.items():
            self.assertEqual(self.window.config[action], desired, action)
        self.assertEqual(self.window._guide_progress.text(), "29 / 29")
        self.assertEqual(self.window._guide_bubble.progress_bar.maximum(), 29)
        self.assertEqual(self.window._guide_bubble.progress_bar.value(), 29)
        self.assertEqual(self.window._guide_body.text(), setup_labels(
            self.window.current_interface_language
        )["done_body"].format(ready=14, total=14))
        self.assertTrue(self.window._guide_bubble.isVisible())
        self.window._guide_primary_btn.click()
        self.assertFalse(self.window._guide_bubble.isVisible())

    def test_completion_keeps_step_count_separate_from_skipped_settings(self):
        self.window.config.update({
            key: not desired for key, (_widget, _page, desired) in GUIDE_SETTING_STEPS.items()
        })
        self.window.config["result_window_hidden_modes"] = main.RESULT_WINDOW_MODES
        self.window._guide_active = True
        self.window._guide_step_index = len(GUIDE_SETUP_ORDER)
        self.window._show_guide_step()
        self.assertEqual(self.window._guide_progress.text(), "29 / 29")
        self.assertEqual(self.window._guide_bubble.progress_bar.value(), 29)
        self.assertEqual(self.window._guide_body.text(), setup_labels(
            self.window.current_interface_language
        )["done_body"].format(ready=0, total=14))

    def test_hotkey_editor_is_not_closed_before_user_finishes(self):
        self.show_step("hotkeys")
        self.window.settings_window.hotkeys_button.click()
        self.window._guide_step_timer.stop()
        self.settle()
        self.window._show_guide_step()
        self.assertEqual(self.window.settings_window._secondary_view_kind, "hotkeys")
        self.assertFalse(self.window._guide_bubble.isVisible())
        self.window.show_main_screen()
        self.assertEqual(self.window._guide_current_action(), "shortcut_overview")

    def test_hotkey_editor_back_button_resumes_guide(self):
        self.show_step("hotkeys")
        self.window.settings_window.hotkeys_button.click()
        self.window._guide_step_timer.stop()
        self.settle()
        self.window._show_guide_step()
        self.window.settings_window.hotkey_back_button.click()
        self.settle()
        self.assertTrue(self.window._guide_bubble.isVisible())
        self.assertEqual(self.window._guide_current_action(), "back_home")

    def _check_card_layout(self, configured):
        for theme in ("Темная", "Светлая"):
            for language in ("ru", "en", "de", "fr", "es", "zh"):
                self.window._guide_active = False
                self.window.config.update({
                    key: desired if configured else not desired
                    for key, (_widget, _page, desired) in GUIDE_SETTING_STEPS.items()
                })
                self.window.current_theme = theme
                self.window.current_interface_language = language
                self.window.show_main_screen()
                self.settle()
                for action in GUIDE_SETUP_ORDER:
                    with self.subTest(theme=theme, language=language, action=action):
                        target = self.show_step(action)
                        self.assertIsNotNone(target)
                        self.assertTrue(target.isVisible())
                        card = self.window._guide_bubble
                        self.assertTrue(card.isVisible())
                        self.assertTrue(self.window.rect().contains(card.geometry()), card.geometry())
                        target_rect = self.window._guide_target_rect(target)
                        self.assertFalse(card.geometry().intersects(target_rect), (card.geometry(), target_rect))
                        for label in (card.title, card.body, card.hint):
                            if label.isVisible():
                                self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()), label.text())
                        for button in (card.skip_button, card.primary_button):
                            if button.isVisible():
                                self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())
                self.window._guide_active = False

    def test_recommendation_cards_fit_in_every_language_and_theme(self):
        self._check_card_layout(configured=False)

    def test_already_configured_cards_fit_in_every_language_and_theme(self):
        self._check_card_layout(configured=True)


if __name__ == "__main__":
    unittest.main()
