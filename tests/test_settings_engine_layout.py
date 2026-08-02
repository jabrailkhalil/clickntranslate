import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import QPoint, Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QStyle, QStyleOptionComboBox, QWidget  # noqa: E402

from settings_window import SettingsWindow  # noqa: E402


class _SettingsParent(QWidget):
    def __init__(self):
        super().__init__()
        self.current_interface_language = "en"
        self.current_theme = "Темная"
        self.config = {
            "autostart": False,
            "start_minimized": False,
            "ocr_engine": "Tesseract",
            "translator_engine": "argos",
        }
        self.start_minimized = False
        self.autostart = False

    def save_config(self):
        pass

    def set_autostart(self, value):
        return bool(value)


class SettingsEngineLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _rect_in_settings(settings, widget):
        point = widget.mapTo(settings, QPoint(0, 0))
        return point.x(), point.y(), widget.width(), widget.height()

    def test_engine_rows_share_columns_and_vertical_centers(self):
        parent = _SettingsParent()
        parent.resize(700, 400)
        with mock.patch.object(SettingsWindow, "_find_local_tesseract_exe", return_value="tesseract.exe"):
            settings = SettingsWindow(parent)
            settings.setGeometry(0, 0, 700, 400)
            parent.show()
            settings.show()
            self.app.processEvents()

            ocr_label = self._rect_in_settings(settings, settings.ocr_engine_label)
            ocr_combo = self._rect_in_settings(settings, settings.ocr_engine_combo)
            ocr_delete = self._rect_in_settings(settings, settings.ocr_engine_delete_btn)
            tr_label = self._rect_in_settings(settings, settings.translator_engine_label)
            tr_combo = self._rect_in_settings(settings, settings.translator_combo)
            tr_delete = self._rect_in_settings(settings, settings.translator_engine_delete_btn)

            self.assertEqual(ocr_label[1] + ocr_label[3] / 2, ocr_combo[1] + ocr_combo[3] / 2)
            self.assertEqual(ocr_combo[1] + ocr_combo[3] / 2, ocr_delete[1] + ocr_delete[3] / 2)
            self.assertEqual(tr_label[1] + tr_label[3] / 2, tr_combo[1] + tr_combo[3] / 2)
            self.assertEqual(tr_combo[1] + tr_combo[3] / 2, tr_delete[1] + tr_delete[3] / 2)
            self.assertEqual(ocr_combo[0], tr_combo[0])
            self.assertEqual(ocr_combo[2], 160)
            self.assertEqual(tr_combo[2], 160)
            self.assertEqual(ocr_delete[0], tr_delete[0])
            self.assertGreaterEqual(ocr_delete[0], ocr_combo[0] + ocr_combo[2] - 30)
            self.assertLessEqual(ocr_delete[0] + ocr_delete[2], ocr_combo[0] + ocr_combo[2])
            self.assertIs(settings.ocr_engine_delete_btn.parentWidget(), settings.ocr_engine_combo)
            self.assertIs(settings.translator_engine_delete_btn.parentWidget(), settings.translator_combo)
            self.assertTrue(settings.ocr_engine_label.alignment() & Qt.AlignVCenter)
            self.assertTrue(settings.translator_engine_label.alignment() & Qt.AlignVCenter)
            self.assertEqual(settings.ocr_engine_delete_btn.size().width(), 16)
            self.assertEqual(settings.ocr_engine_delete_btn.size().height(), 16)
            self.assertTrue(settings.ocr_engine_combo.property("engineDeleteVisible"))
            self.assertFalse(settings.translator_combo.property("engineDeleteVisible"))

            ocr_option = QStyleOptionComboBox()
            tr_option = QStyleOptionComboBox()
            settings.ocr_engine_combo.initStyleOption(ocr_option)
            settings.translator_combo.initStyleOption(tr_option)
            ocr_section = settings.ocr_engine_combo.style().subControlRect(
                QStyle.CC_ComboBox,
                ocr_option,
                QStyle.SC_ComboBoxArrow,
                settings.ocr_engine_combo,
            )
            tr_section = settings.translator_combo.style().subControlRect(
                QStyle.CC_ComboBox,
                tr_option,
                QStyle.SC_ComboBoxArrow,
                settings.translator_combo,
            )
            self.assertEqual(ocr_section, tr_section)
            self.assertEqual(ocr_section.width(), 31)

            action_rows = (
                (settings.clear_cache_btn, settings.reset_btn, settings.update_btn),
                (settings.ocr_languages_btn, settings.hotkeys_button, settings.translation_history_btn),
                (settings.copy_history_btn,),
            )
            action_rects = [
                [self._rect_in_settings(settings, button) for button in row]
                for row in action_rows
            ]
            for row, rects in zip(action_rows, action_rects):
                self.assertEqual({rect[1] for rect in rects}, {rects[0][1]})
                self.assertEqual({rect[2] for rect in rects}, {rects[0][2]})
                self.assertEqual({rect[3] for rect in rects}, {36})
                for button in row:
                    self.assertNotIn("padding-bottom: 6px", button.styleSheet())
                    self.assertNotIn("padding-bottom: 12px", button.styleSheet())
            self.assertEqual(
                [(rect[0], rect[2]) for rect in action_rects[0]],
                [(rect[0], rect[2]) for rect in action_rects[1]],
            )
            self.assertEqual(action_rects[2][0][0], action_rects[0][0][0])
            self.assertEqual(
                action_rects[2][0][0] + action_rects[2][0][2],
                action_rects[0][-1][0] + action_rects[0][-1][2],
            )

            settings.close()
            parent.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
