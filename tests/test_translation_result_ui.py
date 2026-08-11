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
import platform_support  # noqa: E402
import translater  # noqa: E402
from PyQt5.QtWidgets import QWidget  # noqa: E402


def _immediate_thread(target=None, daemon=None, **_kwargs):
    """Run a worker body inline so re-translation is synchronous under test."""
    return SimpleNamespace(start=target)


class _SelectionHarness:
    """Drives the real selection worker from DarkThemeApp without a full window."""

    launch_translate_selection = main.DarkThemeApp.launch_translate_selection
    launch_translate_replace_selection = (
        main.DarkThemeApp.launch_translate_replace_selection
    )
    _launch_translate_selection = main.DarkThemeApp._launch_translate_selection

    def __init__(self, config, interface_language="en"):
        self.config = {"interface_language": interface_language}
        self.config.update(config)
        self.current_interface_language = interface_language
        self.selection_skip_dialog_checkbox = None
        self.save_count = 0
        self.statuses = []
        self.shown_dialogs = []
        self._show_status_signal = SimpleNamespace(emit=self.statuses.append)
        self._hide_status_signal = SimpleNamespace(emit=lambda: None)
        self._show_selection_signal = SimpleNamespace(
            emit=lambda *args: self.shown_dialogs.append(args)
        )

    def save_config(self):
        self.save_count += 1

    def _selected_text_translation_pair(self):
        return "es", "en"

    def _replace_selected_text_translation_pair(self):
        return "es", "en"

    def run_selection_worker(self, selected_text, translated_text):
        """Run the worker body synchronously, with the OS-specific bits stubbed.

        Pretending to be Linux takes the PRIMARY-selection branch, which avoids
        the Windows key simulation and leaves copy_text called only by the
        skip-the-dialog path under test.
        """
        self._read_primary_selection = lambda: selected_text

        def fake_thread(target=None, daemon=None, **_kwargs):
            return SimpleNamespace(start=target)

        with mock.patch.object(platform_support, "IS_LINUX", True), \
                mock.patch.object(main.threading, "Thread", fake_thread), \
                mock.patch.object(main.time, "sleep", lambda _seconds: None), \
                mock.patch.object(
                    translater, "translate_text", return_value=translated_text
                ):
            self.launch_translate_selection()


class _MainResultHarness:
    """Drives the main-window Translate result path without a full window."""

    _present_main_translation_result = (
        main.DarkThemeApp._present_main_translation_result
    )

    def __init__(self):
        self.statuses = []
        self._show_status_signal = SimpleNamespace(emit=self.statuses.append)
        self._hide_status_signal = SimpleNamespace(emit=lambda: None)


class _PairMemoryParent(QWidget):
    """Use the app's real persistence method without constructing the full UI."""

    _remember_translation_result_pair = (
        main.DarkThemeApp._remember_translation_result_pair
    )

    def __init__(self):
        super().__init__()
        self.config = {}
        self.settings_window = object()
        self.save_count = 0

    def save_config(self):
        self.save_count += 1


class TranslationResultUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = main.QApplication.instance() or main.QApplication([])

    def test_result_dialog_is_frameless_themed_and_localized(self):
        for index, lang in enumerate(main.TRANSLATION_RESULT_DIALOG_TEXT):
            theme = "Темная" if index % 2 == 0 else "Светлая"
            dialog = main.TranslationResultDialog(
                None,
                "A translated sentence.",
                auto_copy=index % 2 == 0,
                lang=lang,
                theme=theme,
            )
            dialog.show()
            self.app.processEvents()

            self.assertEqual(dialog.text_edit.toPlainText(), "A translated sentence.")
            self.assertEqual(dialog.title_label.text(), main.TRANSLATION_RESULT_DIALOG_TEXT[lang]["title"])
            self.assertTrue(dialog.windowFlags() & main.Qt.FramelessWindowHint)
            self.assertTrue(dialog.windowFlags() & main.Qt.WindowStaysOnTopHint)
            self.assertTrue(dialog.testAttribute(main.Qt.WA_TranslucentBackground))
            self.assertEqual(dialog.width(), 480)
            self.assertFalse(dialog.copy_button.autoDefault())
            self.assertFalse(dialog.google_button.autoDefault())
            self.assertFalse(dialog.close_button.autoDefault())
            for button in (dialog.copy_button, dialog.google_button, dialog.close_button):
                self.assertGreaterEqual(button.width(), button.sizeHint().width())
            if theme == "Темная":
                self.assertIn("background: #111216", dialog.styleSheet())
            else:
                self.assertIn("background: #fbfafc", dialog.styleSheet())
            dialog.close()

    def test_copy_and_google_buttons_work_without_closing_the_result(self):
        dialog = main.TranslationResultDialog(
            None,
            "кореец → Coreano",
            auto_copy=False,
            lang="ru",
            theme="Темная",
        )
        with mock.patch.object(platform_support, "copy_text") as copy:
            dialog.copy_button.click()
        copy.assert_called_once_with("кореец → Coreano")
        self.assertEqual(dialog.status_label.text(), main.TRANSLATION_RESULT_DIALOG_TEXT["ru"]["copied"])

        with mock.patch.object(main.webbrowser, "open") as browser:
            dialog.google_button.click()
        browser.assert_called_once()
        self.assertIn("%D0%BA%D0%BE%D1%80%D0%B5%D0%B5%D1%86", browser.call_args.args[0])
        self.assertEqual(dialog.result(), 0)
        dialog.close()

    def test_wrapper_uses_new_dialog_and_preserves_auto_copy(self):
        dialog = mock.Mock()
        dialog.isVisible.return_value = True
        main._translation_result_dialogs.clear()
        with mock.patch.object(platform_support, "copy_text") as copy:
            with mock.patch.object(main, "TranslationResultDialog", return_value=dialog) as dialog_class:
                result = main.show_translation_dialog(
                    None,
                    "Coreano",
                    auto_copy=True,
                    lang="en",
                    theme="Темная",
                )

        copy.assert_called_once_with("Coreano")
        dialog_class.assert_called_once_with(
            None,
            "Coreano",
            auto_copy=True,
            lang="en",
            theme="Темная",
            source_text="",
            source_lang="",
            target_lang="",
        )
        dialog.exec_.assert_not_called()
        dialog.show.assert_called_once_with()
        dialog.raise_.assert_called_once_with()
        dialog.activateWindow.assert_called_once_with()
        self.assertIs(result, dialog)

    def test_skip_dialog_copies_without_opening_the_result_window(self):
        harness = _SelectionHarness({"result_window_hidden_modes": ["selection"]})

        with mock.patch.object(platform_support, "copy_text") as copy:
            with mock.patch.object(main, "save_copy_history") as history:
                harness.run_selection_worker("Hola mundo", "Hello world")

        copy.assert_called_once_with("Hello world")
        history.assert_called_once_with("Hello world")
        self.assertEqual(harness.shown_dialogs, [])
        self.assertIn(
            main.TRANSLATION_RESULT_DIALOG_TEXT["en"]["copied"], harness.statuses
        )

    def test_safe_selection_replacement_revalidates_then_pastes(self):
        copied = []
        with mock.patch.object(platform_support, "IS_WINDOWS", True), \
                mock.patch.object(main, "_windows_foreground_window", return_value=42), \
                mock.patch.object(platform_support, "copy_text",
                                  side_effect=lambda value: copied.append(value) or True), \
                mock.patch.object(main, "_clipboard_sequence_number", return_value=7), \
                mock.patch.object(main, "_wait_for_clipboard_change", return_value=True), \
                mock.patch.object(main, "simulate_copy") as simulate_copy, \
                mock.patch.object(main, "simulate_paste") as simulate_paste, \
                mock.patch.object(main.pyperclip, "paste", return_value="Hello world"), \
                mock.patch.object(main.time, "sleep"):
            success, reason = main.replace_selected_text_in_foreground(
                "Hello world", "Привет, мир", 42
            )

        self.assertTrue(success)
        self.assertEqual(reason, "replaced")
        self.assertEqual(copied[-1], "Привет, мир")
        self.assertTrue(copied[0].startswith("__CLICKNTRANSLATE_SELECTION_"))
        simulate_copy.assert_called_once_with()
        simulate_paste.assert_called_once_with()

    def test_selection_replacement_never_pastes_after_focus_changes(self):
        with mock.patch.object(platform_support, "IS_WINDOWS", True), \
                mock.patch.object(main, "_windows_foreground_window", return_value=99), \
                mock.patch.object(platform_support, "copy_text") as copy, \
                mock.patch.object(main, "simulate_paste") as paste:
            success, reason = main.replace_selected_text_in_foreground(
                "Hello", "Привет", 42
            )

        self.assertFalse(success)
        self.assertEqual(reason, "focus_changed")
        copy.assert_not_called()
        paste.assert_not_called()

    def test_selection_replacement_never_pastes_over_changed_text(self):
        with mock.patch.object(platform_support, "IS_WINDOWS", True), \
                mock.patch.object(main, "_windows_foreground_window", return_value=42), \
                mock.patch.object(platform_support, "copy_text", return_value=True), \
                mock.patch.object(main, "_clipboard_sequence_number", return_value=7), \
                mock.patch.object(main, "_wait_for_clipboard_change", return_value=True), \
                mock.patch.object(main, "simulate_copy"), \
                mock.patch.object(main, "simulate_paste") as paste, \
                mock.patch.object(main.pyperclip, "paste", return_value="Different text"):
            success, reason = main.replace_selected_text_in_foreground(
                "Hello", "Привет", 42
            )

        self.assertFalse(success)
        self.assertEqual(reason, "selection_changed")
        paste.assert_not_called()

    def test_replace_hotkey_uses_one_history_entry_and_can_hide_dialog(self):
        harness = _SelectionHarness({
            "result_window_hidden_modes": ["selection"],
        })
        fake_user32 = SimpleNamespace(keybd_event=mock.Mock())

        def fake_thread(target=None, daemon=None, **_kwargs):
            return SimpleNamespace(start=target)

        with mock.patch.object(platform_support, "IS_LINUX", False), \
                mock.patch.object(platform_support, "IS_WINDOWS", True), \
                mock.patch.object(main.ctypes, "windll",
                                  SimpleNamespace(user32=fake_user32), create=True), \
                mock.patch.object(main.threading, "Thread", fake_thread), \
                mock.patch.object(main.time, "sleep", lambda _seconds: None), \
                mock.patch.object(main, "simulate_copy"), \
                mock.patch.object(main.pyperclip, "paste", return_value="Hola mundo"), \
                mock.patch.object(main, "_windows_foreground_window", return_value=42), \
                mock.patch.object(main, "replace_selected_text_in_foreground",
                                  return_value=(True, "replaced")) as replace, \
                mock.patch.object(translater, "translate_text", return_value="Hello world"), \
                mock.patch.object(platform_support, "copy_text"), \
                mock.patch.object(main, "save_copy_history") as history:
            harness.launch_translate_replace_selection()

        replace.assert_called_once_with("Hola mundo", "Hello world", 42)
        history.assert_called_once_with("Hello world")
        self.assertEqual(harness.shown_dialogs, [])
        self.assertIn(main.ui_text("en", "selection_replaced"), harness.statuses)

    def test_regular_selection_hotkey_never_attempts_replacement(self):
        harness = _SelectionHarness({"result_window_hidden_modes": ["selection"]})

        with mock.patch.object(
            main, "replace_selected_text_in_foreground"
        ) as replace:
            harness.run_selection_worker("Hola mundo", "Hello world")

        replace.assert_not_called()

    def test_unchecked_still_opens_the_result_window(self):
        harness = _SelectionHarness({"result_window_hidden_modes": []})

        with mock.patch.object(platform_support, "copy_text") as copy:
            harness.run_selection_worker("Hola mundo", "Hello world")

        copy.assert_not_called()
        self.assertEqual(len(harness.shown_dialogs), 1)
        shown = harness.shown_dialogs[0]
        self.assertEqual(shown[0], "Hello world")
        # The original text and pair travel with the result so the dialog can
        # re-translate without asking the caller again.
        self.assertEqual(shown[4], "Hola mundo")
        self.assertEqual((shown[5], shown[6]), ("es", "en"))

    def test_only_the_listed_modes_are_hidden(self):
        config = {"result_window_hidden_modes": ["area"]}
        self.assertFalse(main.result_window_hidden_for(config, "selection"))
        self.assertTrue(main.result_window_hidden_for(config, "area"))
        self.assertFalse(main.result_window_hidden_for(config, "main"))

    def test_mode_list_survives_junk_from_a_hand_edited_config(self):
        # Unknown names, casing, padding, a bare string and nonsense types must
        # never crash the hotkey worker that reads this on every translation.
        self.assertEqual(
            main.result_window_hidden_modes({"result_window_hidden_modes": ["  AREA ", "ocr", "bogus"]}),
            ("area",),
        )
        self.assertEqual(
            main.result_window_hidden_modes({"result_window_hidden_modes": "selection"}),
            ("selection",),
        )
        for junk in (None, 42, {}, [], ()):
            self.assertEqual(
                main.result_window_hidden_modes({"result_window_hidden_modes": junk}), ()
            )
        self.assertEqual(main.result_window_hidden_modes({}), ())

    def test_returned_modes_keep_a_stable_order(self):
        self.assertEqual(
            main.result_window_hidden_modes(
                {"result_window_hidden_modes": ["main", "area", "selection"]}
            ),
            main.RESULT_WINDOW_MODES,
        )

    def test_hiding_the_main_window_result_copies_exactly_once(self):
        for auto_copy in (False, True):
            harness = _MainResultHarness()
            config = {
                "copy_translated_text": auto_copy,
                "interface_language": "en",
                "theme": "Темная",
                "copy_history": True,
                "result_window_hidden_modes": ["main"],
            }
            with mock.patch.object(main, "get_cached_config", return_value=config), \
                    mock.patch.object(platform_support, "copy_text") as copy, \
                    mock.patch.object(main, "save_copy_history") as history, \
                    mock.patch.object(main, "show_translation_dialog") as dialog, \
                    mock.patch.object(main.QTimer, "singleShot"):
                harness._present_main_translation_result("Привет", "Hello", "en", "ru")

            dialog.assert_not_called()
            # Auto-copy must not turn into a double copy or a duplicate history row.
            self.assertEqual(copy.call_count, 1, auto_copy)
            self.assertEqual(history.call_count, 1, auto_copy)
            self.assertIn(
                main.TRANSLATION_RESULT_DIALOG_TEXT["en"]["copied"], harness.statuses
            )

    def test_main_window_result_still_opens_when_the_mode_is_not_listed(self):
        harness = _MainResultHarness()
        config = {
            "copy_translated_text": False,
            "interface_language": "en",
            "theme": "Темная",
            "copy_history": True,
            "result_window_hidden_modes": ["selection", "area"],
        }
        with mock.patch.object(main, "get_cached_config", return_value=config), \
                mock.patch.object(platform_support, "copy_text"), \
                mock.patch.object(main, "save_copy_history"), \
                mock.patch.object(main, "show_translation_dialog") as dialog:
            harness._present_main_translation_result("Привет", "Hello", "en", "ru")

        dialog.assert_called_once()
        self.assertEqual(harness.statuses, [])

    def test_the_default_is_shown_everywhere_and_is_immutable(self):
        self.assertEqual(main.result_window_hidden_modes(main.DEFAULT_CONFIG), ())
        # DEFAULT_CONFIG is shallow-copied in several places, so an in-place edit
        # of a mutable default would leak into every later config.
        self.assertIsInstance(main.DEFAULT_CONFIG["result_window_hidden_modes"], tuple)

    def _pair_dialog(self, **kwargs):
        options = {
            "auto_copy": False,
            "lang": "en",
            "theme": "Темная",
            "source_text": "Hola mundo",
            "source_lang": "es",
            "target_lang": "en",
        }
        options.update(kwargs)
        return main.TranslationResultDialog(None, "Hello world", **options)

    def test_pair_row_appears_only_when_the_original_text_and_pair_are_known(self):
        with_pair = self._pair_dialog()
        self.assertTrue(with_pair.pair_row_available)
        self.assertEqual(with_pair.source_combo.currentData(), "es")
        self.assertEqual(with_pair.target_combo.currentData(), "en")
        # The target list never offers the source language back.
        targets = [with_pair.target_combo.itemData(i) for i in range(with_pair.target_combo.count())]
        self.assertNotIn("es", targets)
        with_pair.close()

        for missing in ({"source_text": "  "}, {"source_lang": ""}, {"target_lang": "es"}):
            plain = self._pair_dialog(**missing)
            self.assertFalse(plain.pair_row_available, missing)
            self.assertIsNone(plain.source_combo)
            plain.close()

    def test_changing_the_target_retranslates_the_original_text(self):
        dialog = self._pair_dialog()
        calls = []

        def fake_translate(text, source, target):
            calls.append((text, source, target))
            return "Hallo Welt"

        with mock.patch.object(main.threading, "Thread", _immediate_thread), \
                mock.patch.object(translater, "translate_text", fake_translate):
            dialog.target_combo.setCurrentIndex(dialog.target_combo.findData("de"))
        self.app.processEvents()

        self.assertEqual(calls, [("Hola mundo", "es", "de")])
        self.assertEqual(dialog.text_edit.toPlainText(), "Hallo Welt")
        self.assertEqual(dialog.translated_text, "Hallo Welt")
        self.assertTrue(dialog.target_combo.isEnabled())
        # Copy now yields the re-translated text, not the original result.
        with mock.patch.object(platform_support, "copy_text") as copy:
            dialog.copy_button.click()
        copy.assert_called_once_with("Hallo Welt")
        dialog.close()

    def test_changed_pair_is_remembered_for_main_selection_and_area_translation(self):
        parent = _PairMemoryParent()
        dialog = main.TranslationResultDialog(
            parent,
            "Hello world",
            auto_copy=False,
            lang="en",
            theme="Темная",
            source_text="Hola mundo",
            source_lang="es",
            target_lang="en",
        )

        with mock.patch.object(main.threading, "Thread", _immediate_thread), \
                mock.patch.object(translater, "translate_text", return_value="Hallo Welt"):
            dialog.target_combo.setCurrentIndex(dialog.target_combo.findData("de"))
        self.app.processEvents()

        self.assertEqual(parent.config["main_translation_source_language"], "es")
        self.assertEqual(parent.config["main_translation_target_language"], "de")
        self.assertEqual(parent.config["ocr_translate_source_language"], "es")
        self.assertEqual(parent.config["ocr_translate_target_language"], "de")
        self.assertEqual(parent.save_count, 1)
        dialog.close()
        parent.close()

    def test_swap_flips_the_pair_and_retranslates(self):
        dialog = self._pair_dialog()
        calls = []

        with mock.patch.object(main.threading, "Thread", _immediate_thread), \
                mock.patch.object(
                    translater,
                    "translate_text",
                    lambda text, src, tgt: calls.append((text, src, tgt)) or "Hola mundo",
                ):
            dialog.swap_button.click()
        self.app.processEvents()

        self.assertEqual(dialog.source_combo.currentData(), "en")
        self.assertEqual(dialog.target_combo.currentData(), "es")
        self.assertEqual(calls, [("Hola mundo", "en", "es")])
        dialog.close()

    def test_changing_the_source_keeps_a_valid_target_and_retranslates(self):
        dialog = self._pair_dialog(source_lang="es", target_lang="en")
        calls = []

        with mock.patch.object(main.threading, "Thread", _immediate_thread), \
                mock.patch.object(
                    translater,
                    "translate_text",
                    lambda text, src, tgt: calls.append((src, tgt)) or "ok",
                ):
            dialog.source_combo.setCurrentIndex(dialog.source_combo.findData("en"))
        self.app.processEvents()

        # Source became the old target, so the target has to move off "en".
        self.assertEqual(dialog.source_combo.currentData(), "en")
        self.assertNotEqual(dialog.target_combo.currentData(), "en")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "en")
        dialog.close()

    def test_failed_retranslate_keeps_the_previous_result_and_reports_it(self):
        dialog = self._pair_dialog()

        def boom(_text, _source, _target):
            raise RuntimeError("no network")

        with mock.patch.object(main.threading, "Thread", _immediate_thread), \
                mock.patch.object(translater, "translate_text", boom):
            dialog.target_combo.setCurrentIndex(dialog.target_combo.findData("de"))
        self.app.processEvents()

        self.assertEqual(dialog.text_edit.toPlainText(), "Hello world")
        self.assertIn(main.ui_text("en", "translation_error"), dialog.status_label.text())
        self.assertIn("no network", dialog.status_label.text())
        # The row is usable again so another pair can be tried.
        self.assertTrue(dialog.target_combo.isEnabled())
        self.assertTrue(dialog.swap_button.isEnabled())
        dialog.close()

    def test_swap_tooltip_is_localized_in_every_language(self):
        for lang in main.TRANSLATION_RESULT_DIALOG_TEXT:
            dialog = self._pair_dialog(lang=lang)
            self.assertIn(
                main.TRANSLATION_RESULT_DIALOG_TEXT[lang]["swap"],
                dialog.swap_button.toolTip(),
            )
            dialog.close()

    def test_multiple_results_stay_open_and_are_cascaded_downward(self):
        main._translation_result_dialogs.clear()
        first = main.show_translation_dialog(None, "First", auto_copy=False, lang="en", theme="Темная")
        second = main.show_translation_dialog(None, "Second", auto_copy=False, lang="en", theme="Темная")
        self.app.processEvents()

        self.assertTrue(first.isVisible())
        self.assertTrue(second.isVisible())
        self.assertGreater(second._stack_offset.y(), first._stack_offset.y())

        first.close()
        second.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
