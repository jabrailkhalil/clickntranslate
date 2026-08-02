import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402


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
        with mock.patch.object(main.pyperclip, "copy") as copy:
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
        dialog.exec_.return_value = main.QDialog.Accepted
        with mock.patch.object(main.pyperclip, "copy") as copy:
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
        )
        dialog.exec_.assert_called_once_with()
        self.assertEqual(result, main.QDialog.Accepted)


if __name__ == "__main__":
    unittest.main()
