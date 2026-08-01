import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

import ocr  # noqa: E402
import ocr_worker  # noqa: E402


class NativeOcrWorkerProtocolTest(unittest.TestCase):
    def test_request_uses_png_files_and_cleans_temporary_directory(self):
        captured = {}

        def fake_run(command, **_kwargs):
            request_path = Path(command[-1])
            captured["request_path"] = request_path
            captured["request"] = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertTrue(Path(captured["request"]["images"][0]["path"]).is_file())
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"results": [{"label": "real", "text": "Hello"}], "error": ""}),
                stderr="",
            )

        with mock.patch.object(ocr, "_native_ocr_worker_command", return_value=["OcrWorker.exe"]):
            with mock.patch.object(ocr.subprocess, "run", side_effect=fake_run):
                response = ocr._call_native_ocr_worker(
                    {"engine": "rapidocr", "root_dir": "portable"},
                    [("real", Image.new("RGB", (20, 10), "white"))],
                )

        self.assertEqual(response["results"][0]["text"], "Hello")
        self.assertEqual(captured["request"]["images"][0]["label"], "real")
        self.assertFalse(captured["request_path"].parent.exists())

    def test_rapidocr_dispatches_to_worker_when_enabled(self):
        with mock.patch.object(ocr, "_native_ocr_worker_enabled", return_value=True):
            with mock.patch.object(
                ocr,
                "_recognize_with_native_ocr_worker",
                return_value=("Hello", ""),
            ) as worker:
                result = ocr._recognize_rapidocr_variants([], "unit", "session")

        self.assertEqual(result, ("Hello", ""))
        worker.assert_called_once()

    def test_worker_import_probe_does_not_initialize_qt(self):
        request = {"action": "import", "engine": "rapidocr", "root_dir": ""}
        with mock.patch.object(ocr_worker, "_configure_runtime"):
            with mock.patch.object(ocr_worker, "_rapidocr_class", return_value=object):
                payload = ocr_worker.run_request(request)

        self.assertTrue(payload["available"])
        self.assertFalse(payload["error"])


class NativeOcrWorkerPackagingTest(unittest.TestCase):
    def test_spec_builds_non_qt_worker_and_excludes_optional_engines(self):
        spec_text = (ROOT / "ClicknTranslate.spec").read_text(encoding="utf-8")

        self.assertIn("'ocr_worker.py'", spec_text)
        self.assertIn("name='OcrWorker'", spec_text)
        for dynamic_dependency in ("'timeit'", "'pickletools'", "'configparser'"):
            self.assertIn(dynamic_dependency, spec_text)
        for excluded in ("'easyocr'", "'rapidocr'", "'rapidocr_onnxruntime'"):
            self.assertIn(excluded, spec_text)

    def test_main_enables_worker_only_for_real_app_entrypoint(self):
        main_text = (ROOT / "main.py").read_text(encoding="utf-8")
        entrypoint = main_text.index('if __name__ == "__main__":')
        worker_flag = main_text.index('os.environ["CLICKNTRANSLATE_USE_OCR_WORKER"] = "1"')
        self.assertGreater(worker_flag, entrypoint)


if __name__ == "__main__":
    unittest.main()
