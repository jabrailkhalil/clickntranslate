import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication, QComboBox  # noqa: E402

import platform_support  # noqa: E402
import settings_window as sw  # noqa: E402


class OcrEngineComboTest(unittest.TestCase):
    """The WinRT engine must not be offered where it cannot exist."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _engines_in_combo(self, combo):
        return [combo.itemData(index) for index in range(combo.count()) if combo.itemData(index)]

    def test_windows_lists_every_engine(self):
        combo = QComboBox()
        with mock.patch.object(platform_support, "supports_windows_ocr", return_value=True):
            sw._populate_grouped_ocr_combo(combo, "en")

        self.assertEqual(self._engines_in_combo(combo), ["Windows", "Tesseract", "RapidOCR", "EasyOCR"])

    def test_linux_drops_the_windows_engine(self):
        combo = QComboBox()
        with mock.patch.object(platform_support, "supports_windows_ocr", return_value=False):
            sw._populate_grouped_ocr_combo(combo, "en")

        engines = self._engines_in_combo(combo)
        self.assertNotIn("Windows", engines)
        self.assertEqual(engines, ["Tesseract", "RapidOCR", "EasyOCR"])

    def test_installed_engines_are_listed_first(self):
        combo = QComboBox()
        with mock.patch.object(platform_support, "supports_windows_ocr", return_value=False):
            sw._populate_grouped_ocr_combo(combo, "en", installed_engines={"EasyOCR"})

        self.assertEqual(self._engines_in_combo(combo)[0], "EasyOCR")


class DefaultEngineTest(unittest.TestCase):
    def test_default_engine_matches_the_platform(self):
        expected = "Windows" if platform_support.IS_WINDOWS else "Tesseract"
        self.assertEqual(platform_support.default_ocr_engine(), expected)

    def test_default_engine_is_always_offered(self):
        self.assertIn(
            platform_support.default_ocr_engine().lower(),
            [engine.lower() for engine in platform_support.available_ocr_engines()],
        )

    def test_no_module_hardcodes_a_windows_ocr_default(self):
        """A hardcoded "Windows" default would pick a nonexistent engine on Linux."""
        for name in ("ocr.py", "main.py", "settings_window.py"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn('"ocr_engine", "Windows"', source, name)
            self.assertNotIn('"ocr_engine": "Windows"', source, name)


class TesseractDataDiscoveryTest(unittest.TestCase):
    """Distribution packages keep tessdata far from the binary.

    Debian puts it in /usr/share/tesseract-ocr/<version>/tessdata. Looking only
    beside the executable — which is right for the portable Windows layout —
    made the app refuse to run its default Linux engine at all.
    """

    def setUp(self):
        import ocr

        self.ocr = ocr
        self.temp_dir = tempfile.mkdtemp(prefix="cnt_tessdata_")
        with open(os.path.join(self.temp_dir, "eng.traineddata"), "wb") as handle:
            handle.write(b"data")
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("TESSDATA_PREFIX", None)

    def test_distribution_tessdata_directory_is_found(self):
        with mock.patch.object(self.ocr, "_system_tessdata_dirs", return_value=[self.temp_dir]):
            resolved = self.ocr._configure_installed_tesseract_data("/usr/bin/tesseract", "eng")

        self.assertEqual(resolved, self.temp_dir)
        self.assertEqual(os.environ["TESSDATA_PREFIX"], self.temp_dir)

    def test_binary_that_reports_the_language_is_trusted(self):
        """A packaged Tesseract may hide its data somewhere we cannot guess."""
        with mock.patch.object(self.ocr, "_system_tessdata_dirs", return_value=[]):
            with mock.patch.object(self.ocr, "_tesseract_reported_languages", return_value={"eng", "rus"}):
                self.assertTrue(self.ocr._configure_installed_tesseract_data("/usr/bin/tesseract", "eng"))

    def test_missing_language_is_still_reported_as_missing(self):
        with mock.patch.object(self.ocr, "_system_tessdata_dirs", return_value=[self.temp_dir]):
            with mock.patch.object(self.ocr, "_tesseract_reported_languages", return_value={"eng"}):
                self.assertEqual(
                    self.ocr._configure_installed_tesseract_data("/usr/bin/tesseract", "jpn"), ""
                )

    def test_multi_language_requests_need_every_file(self):
        with mock.patch.object(self.ocr, "_system_tessdata_dirs", return_value=[self.temp_dir]):
            with mock.patch.object(self.ocr, "_tesseract_reported_languages", return_value=set()):
                self.assertEqual(
                    self.ocr._configure_installed_tesseract_data("/usr/bin/tesseract", "eng+rus"), ""
                )

    def test_windows_does_not_scan_unix_locations(self):
        with mock.patch.object(platform_support, "IS_WINDOWS", True):
            self.assertEqual(self.ocr._system_tessdata_dirs(), [])


class TesseractDiscoveryTest(unittest.TestCase):
    def test_path_lookup_comes_before_the_windows_install_locations(self):
        """On Linux the distribution package on PATH is the only candidate."""
        source = (ROOT / "settings_window.py").read_text(encoding="utf-8")
        start = source.index("def _find_available_tesseract_exe")
        body = source[start:start + 900]

        which_index = body.index('shutil.which("tesseract")')
        program_files_index = body.index("Program Files")
        self.assertLess(which_index, program_files_index)


if __name__ == "__main__":
    unittest.main()
