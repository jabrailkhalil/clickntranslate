import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import QPoint  # noqa: E402
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

import settings_window as sw  # noqa: E402


class _SettingsParent(QWidget):
    def __init__(self):
        super().__init__()
        self.current_interface_language = "en"
        self.current_theme = "Темная"
        self.config = {
            "autostart": False,
            "start_minimized": False,
            "ocr_engine": "Windows",
            "translator_engine": "google",
            "copy_hotkey": "Ctrl+Alt+C",
            "translate_hotkey": "Ctrl+Alt+T",
            "fullscreen_translate_hotkey": "Ctrl+Alt+F",
            "translate_selection_hotkey": "Ctrl+Alt+Q",
            "toggle_window_hotkey": "Ctrl+Alt+M",
            "copy_history": True,
            "history": True,
        }
        self.start_minimized = False
        self.autostart = False

    def save_config(self):
        pass

    def set_autostart(self, value):
        return bool(value)


class SettingsSecondaryViewsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="cnt_secondary_views_")
        with open(os.path.join(self.temp_dir, "translation_history.json"), "w", encoding="utf-8") as stream:
            json.dump(
                [
                    {
                        "timestamp": "2026-08-02T12:25:00",
                        "language": "ru -> pt",
                        "original": "Доброе утро",
                        "translated": "Bom dia.",
                    },
                    {
                        "timestamp": "2026-08-02T12:26:00",
                        "language": "en -> ru",
                        "original": "The window is ready.",
                        "translated": "Окно готово.",
                    },
                ],
                stream,
                ensure_ascii=False,
            )
        with open(os.path.join(self.temp_dir, "copy_history.json"), "w", encoding="utf-8") as stream:
            json.dump([], stream)

        self.parent = _SettingsParent()
        self.parent.resize(700, 350)
        self.data_patch = mock.patch.object(
            sw,
            "get_data_file",
            side_effect=lambda name: os.path.join(self.temp_dir, name),
        )
        self.tesseract_patch = mock.patch.object(
            sw.SettingsWindow,
            "_find_local_tesseract_exe",
            return_value=None,
        )
        self.data_patch.start()
        self.tesseract_patch.start()
        self.settings = sw.SettingsWindow(self.parent)
        self.settings.setGeometry(0, 0, 690, 350)
        self.parent.show()
        self.settings.show()
        self.app.processEvents()

    def tearDown(self):
        self.settings.close()
        self.parent.close()
        self.app.processEvents()
        self.tesseract_patch.stop()
        self.data_patch.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _rect_in(widget, child):
        point = child.mapTo(widget, QPoint(0, 0))
        return point.x(), point.y(), child.width(), child.height()

    def test_hotkeys_are_five_aligned_rows_inside_one_card(self):
        self.settings.show_hotkeys_screen()
        self.app.processEvents()

        inputs = (
            self.settings.copy_hotkey_input,
            self.settings.translate_hotkey_input,
            self.settings.fullscreen_translate_hotkey_input,
            self.settings.translate_selection_hotkey_input,
            self.settings.toggle_window_hotkey_input,
        )
        input_rects = [self._rect_in(self.settings, field) for field in inputs]
        label_rects = [self._rect_in(self.settings, label) for label in self.settings.hotkey_labels]

        self.assertEqual(len(label_rects), 5)
        self.assertEqual({rect[0] for rect in input_rects}, {input_rects[0][0]})
        self.assertEqual({rect[2] for rect in input_rects}, {input_rects[0][2]})
        self.assertEqual({rect[3] for rect in input_rects}, {36})
        for label_rect, input_rect in zip(label_rects, input_rects):
            self.assertEqual(label_rect[1] + label_rect[3] // 2, input_rect[1] + input_rect[3] // 2)
        self.assertEqual(
            [field.keySequence().toString() for field in inputs],
            ["Ctrl+Alt+C", "Ctrl+Alt+T", "Ctrl+Alt+F", "Ctrl+Alt+Q", "Ctrl+Alt+M"],
        )
        self.assertTrue(all(field.objectName() == "secondaryHotkeyInput" for field in inputs))
        self.assertEqual(self.settings.hotkey_back_button.objectName(), "secondaryBackButton")
        self.assertIn("QKeySequenceEdit#secondaryHotkeyInput QLineEdit", self.settings.secondary_view_shell.styleSheet())
        self.assertLessEqual(
            self.settings.hotkey_back_button.geometry().bottom(),
            self.settings.secondary_view_shell.height(),
        )

    def test_reset_defaults_keep_all_five_hotkeys(self):
        class FakeMessageBox:
            Question = 1
            Warning = 2
            Information = 3
            YesRole = 4
            NoRole = 5
            Yes = 6
            No = 7

            calls = 0

            def __init__(self, _parent=None):
                type(self).calls += 1
                self._yes_button = object()
                self._clicked = None

            def setWindowTitle(self, _value):
                pass

            def setText(self, _value):
                pass

            def setIcon(self, _value):
                pass

            def setWindowIcon(self, _value):
                pass

            def addButton(self, _text, role):
                if role == self.YesRole:
                    return self._yes_button
                return object()

            def exec_(self):
                # Accept reset, decline clearing history, then close the info box.
                self._clicked = self._yes_button if type(self).calls == 1 else None

            def clickedButton(self):
                return self._clicked

        self.parent.apply_theme = lambda: None
        with mock.patch.object(sw, "QMessageBox", FakeMessageBox):
            self.settings.reset_settings()

        self.assertEqual(self.parent.config["copy_hotkey"], "Ctrl+Alt+C")
        self.assertEqual(self.parent.config["translate_hotkey"], "Ctrl+Alt+T")
        self.assertEqual(self.parent.config["fullscreen_translate_hotkey"], "Ctrl+Alt+F")
        self.assertEqual(self.parent.config["translate_selection_hotkey"], "Ctrl+Alt+Q")
        self.assertEqual(self.parent.config["toggle_window_hotkey"], "Ctrl+Alt+M")

    def test_translation_history_uses_styled_records_and_balanced_footer(self):
        self.settings.show_history_view()
        self.app.processEvents()

        self.assertEqual(self.settings.history_count_label.text(), "2")
        self.assertEqual(self.settings.history_scroll_area.objectName(), "historyScroll")
        self.assertGreaterEqual(self.settings.history_scroll_area.minimumHeight(), 190)
        self.assertEqual(len(self.settings.history_record_cards), 2)
        rendered = "\n".join(
            label.text()
            for card in self.settings.history_record_cards
            for label in card.findChildren(QLabel)
        )
        self.assertIn("Bom dia.", rendered)
        self.assertIn("The window is ready.", rendered)
        for card in self.settings.history_record_cards:
            self.assertEqual(card.objectName(), "historyRecordCard")
            self.assertEqual(len(card.findChildren(QPushButton, "historyCopyButton")), 2)
            self.assertEqual(len(card.findChildren(QPushButton, "historyDeleteButton")), 2)
            self.assertEqual(len(card.findChildren(sw.QFrame, "historyTextBlock")), 2)
        self.assertNotIn("━", rendered)
        self.assertEqual(self.settings.history_clear_button.objectName(), "secondaryClearButton")
        self.assertEqual(self.settings.history_back_button.objectName(), "secondaryBackButton")
        clear_rect = self._rect_in(self.settings, self.settings.history_clear_button)
        back_rect = self._rect_in(self.settings, self.settings.history_back_button)
        self.assertEqual(clear_rect[1], back_rect[1])
        self.assertEqual(clear_rect[3], back_rect[3])
        self.assertLess(clear_rect[0], back_rect[0])

    def test_copy_history_reuses_the_same_secondary_view_style(self):
        self.settings.show_copy_history_view()
        self.app.processEvents()

        self.assertEqual(self.settings.copy_history_count_label.text(), "0")
        self.assertEqual(self.settings.copy_history_scroll_area.objectName(), "historyScroll")
        self.assertEqual(self.settings.copy_history_clear_button.objectName(), "secondaryClearButton")
        self.assertEqual(self.settings.copy_history_back_button.objectName(), "secondaryBackButton")
        empty = self.settings.copy_history_scroll_area.findChild(QLabel, "historyEmptyState")
        self.assertIsNotNone(empty)
        self.assertIn("History is empty", empty.text())

    def test_history_card_copy_and_delete_actions_update_real_data(self):
        self.settings.show_history_view()
        self.app.processEvents()

        with open(os.path.join(self.temp_dir, "translation_history.json"), "r", encoding="utf-8") as stream:
            expected_latest = json.load(stream)[-1]["translated"]
        latest_card = self.settings.history_record_cards[0]
        translated_copy = next(
            button
            for button in latest_card.findChildren(QPushButton, "historyCopyButton")
            if button.property("historyField") == "translated"
        )
        translated_copy.click()
        self.assertEqual(self.app.clipboard().text(), expected_latest)

        latest_card.findChild(QPushButton, "historyDeleteButton").click()
        self.app.processEvents()
        self.assertEqual(self.settings.history_count_label.text(), "1")
        with open(os.path.join(self.temp_dir, "translation_history.json"), "r", encoding="utf-8") as stream:
            remaining = json.load(stream)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["translated"], "Bom dia.")

    def test_theme_refresh_restyles_the_open_history_without_losing_records(self):
        self.settings.show_history_view()
        self.parent.current_theme = "Светлая"
        self.settings.apply_theme()
        self.app.processEvents()

        style = self.settings.secondary_view_shell.styleSheet()
        self.assertIn("#f6f3fa", style)
        self.assertEqual(self.settings.history_count_label.text(), "2")
        rendered = "\n".join(
            label.text()
            for card in self.settings.history_record_cards
            for label in card.findChildren(QLabel)
        )
        self.assertIn("Bom dia.", rendered)


if __name__ == "__main__":
    unittest.main()
