import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QAbstractItemView, QWidget  # noqa: E402

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
        self.easyocr_status_checks = 0
        self.rapidocr_status_checks = 0
        self.last_progress_owner = None
        self._tesseract_install_in_progress = False
        self._easyocr_install_in_progress = False
        self._rapidocr_install_in_progress = False

    def _find_available_tesseract_exe(self):
        return self.tesseract_path

    def _easyocr_importable_status(self):
        self.easyocr_status_checks += 1
        return self.easyocr_status

    def _rapidocr_importable_status(self):
        self.rapidocr_status_checks += 1
        return self.rapidocr_status

    def _local_easyocr_dir(self):
        return str(ROOT / "ocr" / "easyocr")

    def start_tesseract_install(self, progress_owner=None):
        self.tesseract_installs += 1
        self.last_progress_owner = progress_owner

    def start_easyocr_install(self, progress_owner=None):
        self.easyocr_installs += 1
        self.last_progress_owner = progress_owner

    def start_rapidocr_install(self, progress_owner=None):
        self.rapidocr_installs += 1
        self.last_progress_owner = progress_owner


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
        section_titles = [
            self.dialog.tabs.tabText(index)
            for index in range(self.dialog.tabs.count())
        ]
        ocr_titles = [
            self.dialog.ocr_tabs.tabText(index)
            for index in range(self.dialog.ocr_tabs.count())
        ]
        translation_titles = [
            self.dialog.translation_tabs.tabText(index)
            for index in range(self.dialog.translation_tabs.count())
        ]
        self.assertEqual(section_titles, ["OCR", "Translation"])
        self.assertEqual(ocr_titles, ["Windows", "Tesseract", "EasyOCR", "RapidOCR"])
        self.assertEqual(translation_titles, ["Argos"])
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

    def test_constructor_does_not_run_native_engine_probes_on_the_ui_thread(self):
        self.assertEqual(self.owner.easyocr_status_checks, 0)
        self.assertEqual(self.owner.rapidocr_status_checks, 0)
        self.assertEqual(self.dialog.easyocr_table.item(0, 3).text(), "Checking…")
        self.assertEqual(self.dialog.rapidocr_table.item(0, 3).text(), "Checking…")

    def test_missing_engine_replaces_language_table_with_install_action(self):
        self.assertTrue(self.dialog.tesseract_table.isHidden())
        self.assertFalse(self.dialog.tesseract_table._package_missing_frame.isHidden())
        self.assertIn(
            "not installed",
            self.dialog.tesseract_table._package_missing_title.text(),
        )
        self.assertEqual(self.dialog.tesseract_table.rowCount(), 0)

        self.dialog._easyocr_status_cache = (False, "missing")
        self.dialog._populate_easyocr_table(self.dialog.easyocr_table)
        self.assertTrue(self.dialog.easyocr_table.isHidden())
        self.assertFalse(self.dialog.easyocr_table._package_missing_frame.isHidden())
        self.assertEqual(self.dialog.easyocr_table.rowCount(), 0)
        self.assertEqual(
            self.dialog.tesseract_table._package_missing_frame.styleSheet(),
            self.dialog.easyocr_table._package_missing_frame.styleSheet(),
        )
        self.assertIn(
            "QLabel#languagePackageEmptyTitle",
            self.dialog.tesseract_table._package_missing_frame.styleSheet(),
        )
        self.assertIn(
            "background: transparent",
            self.dialog.tesseract_table._package_missing_frame.styleSheet(),
        )

    def test_package_tables_allow_row_highlight_for_removal(self):
        for table in (
            self.dialog.windows_table,
            self.dialog.tesseract_table,
            self.dialog.easyocr_table,
            self.dialog.rapidocr_table,
            self.dialog.argos_table,
        ):
            self.assertEqual(table.selectionMode(), QAbstractItemView.ExtendedSelection)
            self.assertEqual(table.selectionBehavior(), QAbstractItemView.SelectRows)

    def test_installed_windows_row_can_be_highlighted_for_removal(self):
        self.dialog._windows_tags_cache = ["en-US", "ru"]
        self.dialog._windows_capabilities_cache = {
            "en-us": "Installed",
            "ru-ru": "Installed",
        }
        self.dialog._windows_ready_codes_cache = {"en", "ru"}
        self.dialog._populate_windows_table(self.dialog.windows_table)
        table = self.dialog.windows_table
        installed_row = next(
            row
            for row in range(table.rowCount())
            if table.item(row, 0).checkState() == Qt.Checked
        )
        table.selectRow(installed_row)
        self.app.processEvents()

        self.assertEqual(
            self.dialog._highlighted_installed_codes(table),
            [table.item(installed_row, 0).data(Qt.UserRole)],
        )

    def test_windows_removal_uses_windows_specific_success_message(self):
        with mock.patch.object(
            self.dialog, "_highlighted_installed_codes", return_value=["de"]
        ), mock.patch.object(
            self.dialog, "_confirm_package_removal", return_value=True
        ), mock.patch.object(self.dialog, "_run_language_task") as run_task:
            self.dialog._remove_selected_windows()

        self.assertEqual(run_task.call_args.args[:2], ("Windows OCR", ["de"]))
        self.assertEqual(
            run_task.call_args.kwargs["success_message"],
            "Selected Windows OCR language packages were removed.",
        )
        self.assertNotIn("Argos", run_task.call_args.kwargs["success_message"])

    def test_windows_probe_updates_without_waiting_for_optional_ocr_imports(self):
        self.dialog._runtime_probe_active = True
        self.dialog._on_runtime_probe_ready({
            "windows_tags": ["en-US", "ru"],
            "windows_capabilities": {
                "en-us": "Installed",
                "ru-ru": "Installed",
                "de-de": "NotPresent",
            },
        })

        german_row = next(
            row for row in range(self.dialog.windows_table.rowCount())
            if self.dialog.windows_table.item(row, 0).data(Qt.UserRole) == "de"
        )
        self.assertTrue(self.dialog.windows_table.item(german_row, 0).flags() & Qt.ItemIsEnabled)
        self.assertEqual(self.dialog.easyocr_table.item(0, 3).text(), "Checking…")
        self.assertEqual(self.dialog.rapidocr_table.item(0, 3).text(), "Checking…")
        self.assertTrue(self.dialog._runtime_probe_active)

        self.dialog._on_runtime_probe_ready({"rapidocr": (True, ""), "complete": True})
        self.assertFalse(self.dialog._runtime_probe_active)
        self.assertEqual(self.dialog.rapidocr_table.item(0, 3).text(), "Installed")

    def test_manager_uses_black_custom_title_bar_and_centers_on_owner(self):
        self.parent.setGeometry(140, 90, 700, 600)
        self.parent.show()
        self.owner.show()
        self.dialog.show()
        self.app.processEvents()
        # The fixture suppresses all zero-delay timers used by the dialog, so
        # invoke the same post-show centering pass directly here.
        self.dialog._center_on_owner()
        self.app.processEvents()

        self.assertTrue(self.dialog.windowFlags() & Qt.FramelessWindowHint)
        self.assertEqual(self.dialog.objectName(), "languageManagerDialog")
        self.assertEqual(self.dialog.title_bar.objectName(), "languageManagerTitleBar")
        self.assertEqual(self.dialog.title_bar.height(), 38)
        self.assertEqual(self.dialog.title_close_btn.objectName(), "languageManagerTitleClose")
        self.assertEqual(self.dialog.title_label.text(), "Language packages")
        self.assertIn("background-color: #090a0d", self.dialog.styleSheet())
        self.assertEqual(self.dialog.size().width(), 640)
        self.assertEqual(self.dialog.size().height(), 558)

        owner_center = self.parent.frameGeometry().center()
        available = self.app.primaryScreen().availableGeometry()
        expected_x = max(
            available.left(),
            min(owner_center.x() - self.dialog.width() // 2, available.right() - self.dialog.width() + 1),
        )
        expected_y = max(
            available.top(),
            min(owner_center.y() - self.dialog.height() // 2, available.bottom() - self.dialog.height() + 1),
        )
        self.assertLessEqual(abs(expected_x - self.dialog.frameGeometry().left()), 2)
        self.assertLessEqual(abs(expected_y - self.dialog.frameGeometry().top()), 2)

        self.dialog.title_close_btn.click()
        self.app.processEvents()
        self.assertFalse(self.dialog.isVisible())

    def test_every_ocr_language_is_present_in_each_per_language_table(self):
        expected = {language.code for language in LANGUAGES}
        self.owner.tesseract_path = r"C:\Tesseract\tesseract.exe"
        self.dialog._easyocr_status_cache = (True, "")
        self.dialog._populate_tesseract_table(self.dialog.tesseract_table)
        self.dialog._populate_easyocr_table(self.dialog.easyocr_table)
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

    def test_easyocr_compatible_english_does_not_require_second_model(self):
        self.assertEqual(
            self.dialog._easyocr_model_groups_for_language("ru"),
            ["cyrillic_g2"],
        )
        self.assertEqual(
            self.dialog._easyocr_model_groups_for_language("zh"),
            ["zh_sim_g2"],
        )

    def test_windows_package_selection_uses_the_whole_row_and_survives_refresh(self):
        self.dialog._windows_tags_cache = ["en-US", "ru"]
        self.dialog._windows_capabilities_cache = {
            "en-us": "Installed",
            "ru-ru": "Installed",
            "de-de": "NotPresent",
        }
        self.dialog._populate_windows_table(self.dialog.windows_table)
        table = self.dialog.windows_table
        german_row = next(
            row for row in range(table.rowCount())
            if table.item(row, 0).data(Qt.UserRole) == "de"
        )
        checkbox = table.item(german_row, 0)
        self.assertTrue(checkbox.flags() & Qt.ItemIsEnabled)
        self.assertTrue(checkbox.flags() & Qt.ItemIsSelectable)
        self.assertTrue(checkbox.flags() & Qt.ItemIsUserCheckable)

        self.dialog._on_package_row_clicked(table, german_row, 2)
        self.assertEqual(checkbox.checkState(), Qt.Checked)
        self.assertEqual(self.dialog._selected_codes(table), ["de"])

        self.dialog._populate_windows_table(table)
        german_row = next(
            row for row in range(table.rowCount())
            if table.item(row, 0).data(Qt.UserRole) == "de"
        )
        self.assertEqual(table.item(german_row, 0).checkState(), Qt.Checked)
        self.assertEqual(self.dialog._selected_codes(table), ["de"])

    def test_installed_languages_are_sorted_before_missing_languages(self):
        self.dialog._windows_tags_cache = ["de-DE", "zh-Hans-CN"]
        self.dialog._windows_capabilities_cache = {
            "de-de": "Installed",
            "zh-cn": "Installed",
            "en-us": "NotPresent",
            "ru-ru": "NotPresent",
        }
        self.dialog._windows_ready_codes_cache = {"de", "zh"}
        self.dialog._populate_windows_table(self.dialog.windows_table)

        table = self.dialog.windows_table
        checked_states = [
            table.item(row, 0).checkState() == Qt.Checked
            for row in range(table.rowCount())
        ]
        first_missing = checked_states.index(False)
        self.assertTrue(all(checked_states[:first_missing]))
        self.assertFalse(any(checked_states[first_missing:]))
        self.assertEqual(
            {table.item(row, 0).data(Qt.UserRole) for row in range(first_missing)},
            {"de", "zh"},
        )

    def test_windows_table_disables_capabilities_missing_from_this_windows_build(self):
        self.dialog._windows_tags_cache = ["en-US", "ru"]
        self.dialog._windows_capabilities_cache = {
            "en-us": "Installed",
            "ru-ru": "Installed",
            "de-de": "NotPresent",
        }
        self.dialog._populate_windows_table(self.dialog.windows_table)
        table = self.dialog.windows_table
        hindi_row = next(
            row for row in range(table.rowCount())
            if table.item(row, 0).data(Qt.UserRole) == "hi"
        )
        self.assertFalse(table.item(hindi_row, 0).flags() & Qt.ItemIsEnabled)
        self.assertIn("Not available", table.item(hindi_row, 3).text())

    def test_windows_table_marks_one_sided_install_state_for_repair(self):
        self.dialog._windows_tags_cache = []
        self.dialog._windows_capabilities_cache = {"zh-cn": "Installed"}
        self.dialog._populate_windows_table(self.dialog.windows_table)
        table = self.dialog.windows_table
        chinese_row = next(
            row for row in range(table.rowCount())
            if table.item(row, 0).data(Qt.UserRole) == "zh"
        )
        checkbox = table.item(chinese_row, 0)
        self.assertEqual(checkbox.checkState(), Qt.Unchecked)
        self.assertTrue(checkbox.flags() & Qt.ItemIsEnabled)
        self.assertIn("repair", table.item(chinese_row, 3).text().lower())

    def test_all_package_action_buttons_share_the_same_explicit_style(self):
        for table in (
            self.dialog.windows_table,
            self.dialog.tesseract_table,
            self.dialog.easyocr_table,
            self.dialog.rapidocr_table,
            self.dialog.argos_table,
        ):
            for button in table._package_action_buttons:
                self.assertEqual(button.objectName(), "languagePackageAction")
                self.assertGreaterEqual(button.minimumHeight(), 32)
                self.assertIn("background-color: #7A5FA1", button.styleSheet())
        self.assertIn("QPushButton#languagePackageAction", self.dialog.styleSheet())
        for table in (
            self.dialog.windows_table,
            self.dialog.tesseract_table,
            self.dialog.easyocr_table,
            self.dialog.rapidocr_table,
            self.dialog.argos_table,
        ):
            scrollbar_style = table.verticalScrollBar().styleSheet()
            self.assertIn("QScrollBar::handle:vertical", scrollbar_style)
            self.assertIn("height: 0px", scrollbar_style)
            self.assertEqual(table.verticalScrollBar().width(), 10)

    def test_windows_capability_catalog_parses_supported_and_installed_states(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout=(
                "Language.OCR~~~en-US~0.0.1.0|Installed\n"
                "Language.OCR~~~de-DE~0.0.1.0|NotPresent\n"
            ),
        )
        with mock.patch("settings_window.sys.platform", "win32"):
            with mock.patch("settings_window.subprocess.run", return_value=completed):
                catalog = self.dialog._windows_ocr_capability_catalog()
        self.assertEqual(catalog, {"en-us": "Installed", "de-de": "NotPresent"})

    def test_windows_install_script_and_result_are_both_verified(self):
        completed = SimpleNamespace(returncode=0, stdout="")
        self.dialog._windows_capabilities_cache = {"de-de": "NotPresent"}
        captured = {}
        def read_script(path, elevated=False):
            captured["text"] = Path(path).read_text(encoding="utf-8")
            return completed
        with mock.patch.object(self.dialog, "_run_powershell_script", side_effect=read_script):
            with mock.patch.object(
                self.dialog,
                "_windows_ocr_capability_catalog",
                return_value={"de-de": "Installed"},
            ):
                with mock.patch.object(ocr, "_get_available_windows_ocr_language_tags", return_value=["de-DE"]):
                    with mock.patch.object(ocr, "_get_windows_ocr_engine", return_value=object()):
                        with mock.patch.object(self.dialog, "_finish_language_task") as finish:
                            self.dialog._install_windows_ocr_worker(["de"])
        self.assertIn("Get-WindowsCapability", captured["text"])
        self.assertIn("/Add-Capability", captured["text"])
        self.assertNotIn("Stop-Process -Id $process.Id", captured["text"])
        self.assertIn("Write-OcrStatus 'cancel_pending'", captured["text"])
        self.assertIn("elapsed =", captured["text"])
        self.assertIn("State -ne 'Installed'", captured["text"])
        self.assertIn("rolling_back", captured["text"])
        self.assertIn("/Remove-Capability", captured["text"])
        self.assertIn("[System.IO.File]::WriteAllText", captured["text"])
        self.assertIn("Move-Item -LiteralPath $statusTemp", captured["text"])
        self.assertIn("'(\\d+)(?:[.,]\\d+)?%'", captured["text"])
        self.assertNotIn("'(\\\\d+)", captured["text"])
        self.assertNotIn("Set-Content -LiteralPath $StatusPath", captured["text"])
        finish.assert_called_once_with("Windows OCR")

    def test_windows_remove_script_is_observable_and_cancelable(self):
        script = self.dialog._windows_ocr_remover_script(
            ["zh"],
            [self.dialog._windows_ocr_capability_name("zh")],
            "status.json",
            "cancel.request",
            "result.txt",
            "output",
        )
        self.assertIn("/Remove-Capability", script)
        self.assertIn("Write-OcrStatus 'removing'", script)
        self.assertNotIn("Stop-Process -Id $process.Id", script)
        self.assertIn("Write-OcrStatus 'cancel_pending'", script)
        self.assertIn("State -eq 'Installed'", script)
        self.assertIn("$process.WaitForExit()", script)
        self.assertIn("$afterRemoval.State -ne 'Installed'", script)
        self.assertIn("[System.IO.File]::WriteAllText", script)
        self.assertIn("Move-Item -LiteralPath $statusTemp", script)
        self.assertNotIn("Set-Content -LiteralPath $StatusPath", script)

    def test_windows_remove_accepts_real_removed_state_after_false_dism_error(self):
        completed = SimpleNamespace(
            returncode=1,
            stdout="The operation completed successfully.",
        )
        with mock.patch.object(
            self.dialog,
            "_run_powershell_script",
            return_value=completed,
        ):
            with mock.patch.object(
                self.dialog,
                "_wait_for_windows_ocr_removal",
                return_value=[],
            ) as verify:
                with mock.patch.object(self.dialog, "_finish_language_task") as finish:
                    self.dialog._remove_windows_ocr_worker(["de"])

        verify.assert_called_once()
        finish.assert_called_once_with("Windows OCR")

    def test_tesseract_language_package_can_be_removed(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            tessdata = root_path / "tessdata"
            tessdata.mkdir()
            traineddata = tessdata / "deu.traineddata"
            traineddata.write_bytes(b"model")
            self.owner.tesseract_path = str(root_path / "tesseract.exe")
            with mock.patch.object(self.dialog, "_finish_language_task") as finish:
                self.dialog._remove_tesseract_worker(["de"])
            self.assertFalse(traineddata.exists())
            finish.assert_called_once_with("Tesseract")

    def test_easyocr_shared_language_model_can_be_removed(self):
        with tempfile.TemporaryDirectory() as root:
            model_root = Path(root)
            model_file = model_root / "cyrillic_g2.pth"
            model_file.write_bytes(b"model")
            with mock.patch.object(
                self.dialog,
                "_easyocr_model_dir",
                return_value=str(model_root),
            ):
                with mock.patch.object(self.dialog, "_finish_language_task") as finish:
                    self.dialog._remove_easyocr_worker(["ru"])
            self.assertFalse(model_file.exists())
            finish.assert_called_once_with("EasyOCR")

    def test_windows_install_verification_waits_for_dism_state_propagation(self):
        capability = self.dialog._windows_ocr_capability_name("de")
        with mock.patch.object(
            self.dialog,
            "_windows_ocr_capability_catalog",
            side_effect=[{"de-de": "NotPresent"}, {"de-de": "Installed"}],
        ) as catalog:
            with mock.patch("settings_window.time.sleep") as sleep:
                missing = self.dialog._wait_for_windows_ocr_capabilities(
                    [capability], attempts=3, delay=0.01
                )

        self.assertEqual(missing, [])
        self.assertEqual(catalog.call_count, 2)
        sleep.assert_called_once_with(0.01)

    def test_windows_status_file_parser_handles_powershell_utf8_bom(self):
        with tempfile.TemporaryDirectory() as root:
            status_path = Path(root, "status.json")
            status_path.write_text(
                '{"phase":"installing","percent":37,"current":1,"total":2,"code":"zh"}',
                encoding="utf-8-sig",
            )
            status = self.dialog._read_windows_ocr_status(status_path)
        self.assertEqual(status["phase"], "installing")
        self.assertEqual(status["percent"], 37)
        self.assertEqual(status["code"], "zh")

    def test_windows_cancel_creates_marker_seen_by_elevated_installer(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root, "cancel.request")
            self.dialog._windows_ocr_cancel_marker = str(marker)
            self.dialog._request_install_cancel()
            self.assertTrue(self.dialog._cancel_requested.is_set())
            self.assertTrue(marker.exists())

    def test_windows_worker_reports_cancel_without_waiting_for_verification(self):
        self.dialog._cancel_requested.set()

        def canceled_installer(_path, elevated=False):
            deadline = time.time() + 2
            while time.time() < deadline:
                marker = self.dialog._windows_ocr_cancel_marker
                if marker and Path(marker).exists():
                    return SimpleNamespace(returncode=2, stdout="")
                time.sleep(0.01)
            raise AssertionError("cancel marker was not created")

        with mock.patch.object(self.dialog, "_run_powershell_script", side_effect=canceled_installer):
            with mock.patch.object(self.dialog, "_wait_for_windows_ocr_capabilities") as verify:
                with mock.patch.object(self.dialog, "_finish_language_task") as finish:
                    self.dialog._install_windows_ocr_worker(["zh"])

        verify.assert_not_called()
        finish.assert_called_once_with("Windows OCR", canceled=True)

    def test_optional_language_worker_reports_cancel_as_cancel_not_failure(self):
        self.dialog._cancel_requested.set()
        with mock.patch.object(self.dialog, "_finish_language_task") as finish:
            self.dialog._install_easyocr_worker(["zh"])

        finish.assert_called_once_with("EasyOCR", canceled=True)

    def test_easyocr_models_download_only_from_package_manager(self):
        with mock.patch.object(ocr, "easyocr_available", return_value=True) as available:
            with mock.patch.object(self.dialog, "_finish_language_task") as finish:
                self.dialog._install_easyocr_worker(["zh"])

        available.assert_called_once_with("zh", download_enabled=True)
        finish.assert_called_once_with("EasyOCR")

    def test_missing_tesseract_engine_action_is_reachable_without_language_selection(self):
        self.assertFalse(self.dialog._selected_codes(self.dialog.tesseract_table))
        self.dialog._install_selected_tesseract()
        self.assertEqual(self.owner.tesseract_installs, 1)

    def test_missing_easyocr_engine_action_is_reachable_without_language_selection(self):
        self.dialog._easyocr_status_cache = (False, "missing")
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
            self.dialog.windows_table: 3,
            self.dialog.tesseract_table: 2,
            self.dialog.easyocr_table: 2,
            self.dialog.rapidocr_table: 0,
            self.dialog.argos_table: 2,
        }
        for table, expected_count in expected_action_counts.items():
            self.assertEqual(len(table._package_action_buttons), expected_count)

        # Keep the EasyOCR "install selected" path non-modal in this wiring test.
        self.owner.easyocr_status = (True, "")
        self.dialog._easyocr_status_cache = (True, "")
        self.dialog._rapidocr_status_cache = (False, "missing")
        self.dialog._populate_easyocr_table(self.dialog.easyocr_table)
        self.dialog._argos_catalog_request_active = True
        with mock.patch("settings_window.QMessageBox.information"):
            with mock.patch("settings_window.os.startfile") as startfile:
                for table in expected_action_counts:
                    for button in table._package_action_buttons:
                        button.click()
                self.dialog.rapidocr_table._package_missing_install_button.click()
                self.dialog.refresh_btn.click()
                self.dialog.close_btn.click()

        startfile.assert_called_once_with("ms-settings:regionlanguage")
        self.assertGreaterEqual(self.owner.tesseract_installs, 1)
        self.assertGreaterEqual(self.owner.rapidocr_installs, 1)
        self.assertIs(self.owner.last_progress_owner, self.dialog)
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
