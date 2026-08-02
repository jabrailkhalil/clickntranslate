import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget  # noqa: E402

import argos_worker  # noqa: E402
import ocr  # noqa: E402
import translater  # noqa: E402
from settings_window import OcrLanguageManagerDialog  # noqa: E402
from languages import LANGUAGES  # noqa: E402


class _AppParent(QWidget):
    def __init__(self):
        super().__init__()
        self.current_interface_language = "en"
        self.current_theme = "Темная"


class _ManagerOwner(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.tesseract_path = ""
        self.easyocr_status = (False, "missing")
        self.rapidocr_status = (False, "missing")
        self.tesseract_installs = 0
        self.easyocr_installs = 0
        self.rapidocr_installs = 0
        self._tesseract_install_in_progress = False
        self._easyocr_install_in_progress = False
        self._rapidocr_install_in_progress = False

    def _find_available_tesseract_exe(self):
        return self.tesseract_path

    def _easyocr_importable_status(self):
        return self.easyocr_status

    def _rapidocr_importable_status(self):
        return self.rapidocr_status

    def _local_easyocr_dir(self):
        return str(ROOT / "ocr" / "easyocr")

    def start_tesseract_install(self):
        self.tesseract_installs += 1

    def start_easyocr_install(self):
        self.easyocr_installs += 1

    def start_rapidocr_install(self):
        self.rapidocr_installs += 1


class LanguagePackageDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = _AppParent()
        self.owner = _ManagerOwner(self.parent)
        timer_patch = mock.patch("settings_window.QtCore.QTimer.singleShot")
        self.addCleanup(timer_patch.stop)
        timer_patch.start()
        self.dialog = OcrLanguageManagerDialog(self.owner)

    def tearDown(self):
        self.dialog.close()
        self.owner.close()
        self.parent.close()

    def test_manager_contains_argos_and_complete_rapidocr_bundle(self):
        titles = [self.dialog.tabs.tabText(index) for index in range(self.dialog.tabs.count())]
        self.assertEqual(titles, ["Windows", "Tesseract", "EasyOCR", "RapidOCR", "Argos"])
        self.assertEqual(self.dialog.rapidocr_table.rowCount(), 4)
        packages = {
            self.dialog.rapidocr_table.item(row, 2).text()
            for row in range(self.dialog.rapidocr_table.rowCount())
        }
        self.assertIn("rapidocr", packages)
        self.assertIn("onnxruntime", packages)
        self.assertIn("PP-OCR detector", packages)
        self.assertIn("Chinese + English", packages)
        self.assertTrue(self.dialog.rapidocr_table.isColumnHidden(0))
        self.assertIn("QScrollBar::handle:vertical", self.dialog.styleSheet())

    def test_every_ocr_language_is_present_in_each_per_language_table(self):
        expected = {language.code for language in LANGUAGES}
        for table in (
            self.dialog.windows_table,
            self.dialog.tesseract_table,
            self.dialog.easyocr_table,
        ):
            actual = {
                table.item(row, 0).data(Qt.UserRole)
                for row in range(table.rowCount())
            }
            self.assertEqual(actual, expected)
            self.assertIn("ru", actual)

    def test_missing_tesseract_engine_action_is_reachable_without_language_selection(self):
        self.assertFalse(self.dialog._selected_codes(self.dialog.tesseract_table))
        self.dialog._install_selected_tesseract()
        self.assertEqual(self.owner.tesseract_installs, 1)

    def test_missing_easyocr_engine_action_is_reachable_without_language_selection(self):
        self.dialog._install_easyocr_engine()
        self.assertEqual(self.owner.easyocr_installs, 1)

    def test_argos_rows_are_directional_and_only_missing_packages_are_tickable(self):
        self.dialog._argos_catalog_loading = False
        self.dialog._argos_catalog = [
            {
                "source_code": "en",
                "target_code": "ru",
                "version": "1.9",
                "installed": True,
                "available": True,
                "package_name": "translate-en_ru-1_9",
            },
            {
                "source_code": "ru",
                "target_code": "en",
                "version": "1.9",
                "installed": True,
                "available": True,
                "package_name": "translate-ru_en-1_9",
            },
            {
                "source_code": "en",
                "target_code": "de",
                "version": "1.3",
                "installed": False,
                "available": True,
                "package_name": "translate-en_de-1_3",
            },
        ]
        self.dialog._populate_argos_table(self.dialog.argos_table)

        self.assertEqual(self.dialog.argos_table.rowCount(), 3)
        self.assertIn("English → Russian", self.dialog.argos_table.item(0, 1).text())
        self.assertIn("Russian → English", self.dialog.argos_table.item(1, 1).text())
        self.assertIn("English → German", self.dialog.argos_table.item(2, 1).text())
        self.assertEqual(self.dialog._selected_codes(self.dialog.argos_table), [])
        self.dialog.argos_table.item(2, 0).setCheckState(2)
        self.assertEqual(self.dialog._selected_codes(self.dialog.argos_table), ["en->de"])

        search = self.dialog.argos_table._package_filter_edit
        search.setText("Russian")
        self.assertEqual(self.dialog.argos_table.rowCount(), 2)
        self.assertEqual(
            {
                self.dialog.argos_table.item(row, 0).data(Qt.UserRole)
                for row in range(self.dialog.argos_table.rowCount())
            },
            {"en->ru", "ru->en"},
        )
        search.setText("ru→en")
        self.assertEqual(self.dialog.argos_table.rowCount(), 1)
        self.assertEqual(self.dialog.argos_table.item(0, 0).data(Qt.UserRole), "ru->en")

    def test_argos_table_does_not_drop_any_catalog_direction(self):
        codes = [language.code for language in LANGUAGES]
        self.dialog._argos_catalog_loading = False
        self.dialog._argos_catalog = [
            {
                "source_code": source,
                "target_code": target,
                "version": "test",
                "installed": False,
                "available": True,
                "package_name": f"translate-{source}_{target}",
            }
            for source in codes
            for target in codes
            if source != target
        ]
        self.dialog._populate_argos_table(self.dialog.argos_table)

        self.assertEqual(self.dialog.argos_table.rowCount(), len(codes) * (len(codes) - 1))
        actual = {
            self.dialog.argos_table.item(row, 0).data(Qt.UserRole)
            for row in range(self.dialog.argos_table.rowCount())
        }
        self.assertIn("en->ru", actual)
        self.assertIn("ru->en", actual)

        self.dialog.argos_table._package_filter_edit.setText("Russian")
        self.assertEqual(self.dialog.argos_table.rowCount(), 2 * (len(codes) - 1))

    def test_all_manager_buttons_are_connected_and_safe_to_click(self):
        expected_action_counts = {
            self.dialog.windows_table: 2,
            self.dialog.tesseract_table: 2,
            self.dialog.easyocr_table: 2,
            self.dialog.rapidocr_table: 1,
            self.dialog.argos_table: 2,
        }
        for table, expected_count in expected_action_counts.items():
            self.assertEqual(len(table._package_action_buttons), expected_count)

        # Keep the EasyOCR "install selected" path non-modal in this wiring test.
        self.owner.easyocr_status = (True, "")
        self.dialog._populate_easyocr_table(self.dialog.easyocr_table)
        self.dialog._argos_catalog_request_active = True
        with mock.patch("settings_window.QMessageBox.information"):
            with mock.patch("settings_window.os.startfile") as startfile:
                for table in expected_action_counts:
                    for button in table._package_action_buttons:
                        button.click()
                self.dialog.refresh_btn.click()
                self.dialog.close_btn.click()

        startfile.assert_called_once_with("ms-settings:regionlanguage")
        self.assertGreaterEqual(self.owner.tesseract_installs, 1)
        self.assertGreaterEqual(self.owner.rapidocr_installs, 1)
        self.assertEqual(self.dialog.result(), self.dialog.Accepted)


class TesseractLanguageDownloadTest(unittest.TestCase):
    class _Response:
        headers = {"Content-Length": "4"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            yield b"data"

    def test_strict_download_returns_verified_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tessdata = Path(temp_dir) / "tessdata"
            tessdata.mkdir()
            executable = Path(temp_dir) / "tesseract.exe"
            executable.touch()
            with mock.patch("requests.get", return_value=self._Response()):
                prepared = ocr._prepare_tesseract_data(
                    str(executable), "deu", raise_on_error=True
                )

            self.assertEqual(prepared, [str(tessdata / "deu.traineddata")])
            self.assertEqual((tessdata / "deu.traineddata").read_bytes(), b"data")
            self.assertFalse((tessdata / "deu.traineddata.tmp").exists())

    def test_strict_download_raises_and_removes_partial_file(self):
        class BrokenResponse(self._Response):
            def iter_content(self, chunk_size):
                yield b"partial"
                raise RuntimeError("connection lost")

        with tempfile.TemporaryDirectory() as temp_dir:
            tessdata = Path(temp_dir) / "tessdata"
            tessdata.mkdir()
            executable = Path(temp_dir) / "tesseract.exe"
            executable.touch()
            with mock.patch("requests.get", return_value=BrokenResponse()):
                with self.assertRaisesRegex(RuntimeError, "connection lost"):
                    ocr._prepare_tesseract_data(
                        str(executable), "deu", raise_on_error=True
                    )

            self.assertFalse((tessdata / "deu.traineddata").exists())
            self.assertFalse((tessdata / "deu.traineddata.tmp").exists())

    def test_strict_download_rejects_incomplete_response(self):
        class IncompleteResponse(self._Response):
            headers = {"Content-Length": "8"}

        with tempfile.TemporaryDirectory() as temp_dir:
            tessdata = Path(temp_dir) / "tessdata"
            tessdata.mkdir()
            executable = Path(temp_dir) / "tesseract.exe"
            executable.touch()
            with mock.patch("requests.get", return_value=IncompleteResponse()):
                with self.assertRaisesRegex(RuntimeError, "received 4 of 8"):
                    ocr._prepare_tesseract_data(
                        str(executable), "deu", raise_on_error=True
                    )

            self.assertFalse((tessdata / "deu.traineddata").exists())
            self.assertFalse((tessdata / "deu.traineddata.tmp").exists())


class ArgosPackageManagerApiTest(unittest.TestCase):
    def test_catalog_merges_installed_and_available_packages(self):
        installed = SimpleNamespace(
            from_code="en", to_code="ru", package_version="1.9"
        )
        available = SimpleNamespace(
            from_code="en", to_code="de", package_version="1.3"
        )
        package_api = SimpleNamespace(
            get_installed_packages=lambda: [installed],
            get_available_packages=lambda: [available],
            argospm_package_name=lambda package: f"translate-{package.from_code}_{package.to_code}",
        )
        with mock.patch.object(translater, "_ensure_argos_available", return_value=True):
            with mock.patch.object(translater, "arg_pkg", package_api):
                rows = translater._argos_package_catalog_local()

        self.assertEqual(
            [(row["source_code"], row["target_code"]) for row in rows],
            [("en", "de"), ("en", "ru")],
        )
        self.assertTrue(rows[1]["installed"])
        self.assertFalse(rows[1]["available"])

    def test_worker_exposes_catalog_install_and_uninstall_actions(self):
        with mock.patch.object(argos_worker.translater, "_ensure_argos_available", return_value=True):
            with mock.patch.object(
                argos_worker.translater,
                "_argos_package_catalog_local",
                return_value=[{"source_code": "en", "target_code": "ru"}],
            ):
                catalog = argos_worker.run_request({"action": "catalog"})
            with mock.patch.object(
                argos_worker.translater,
                "_install_argos_packages_local",
                return_value=[("en", "de")],
            ):
                installed = argos_worker.run_request(
                    {"action": "install_packages", "pairs": [["en", "de"]]}
                )
            with mock.patch.object(
                argos_worker.translater,
                "_uninstall_argos_packages_local",
                return_value=[("en", "de")],
            ):
                removed = argos_worker.run_request(
                    {"action": "uninstall_packages", "pairs": [["en", "de"]]}
                )

        self.assertFalse(catalog["error"])
        self.assertEqual(installed["installed"], [["en", "de"]])
        self.assertEqual(removed["removed"], [["en", "de"]])


if __name__ == "__main__":
    unittest.main()
