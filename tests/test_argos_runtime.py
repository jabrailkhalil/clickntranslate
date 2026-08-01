import contextlib
import importlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cache_manager  # noqa: E402
import translater  # noqa: E402


@contextlib.contextmanager
def no_translation_cache():
    """Keeps these tests away from the on-disk translation cache."""
    with mock.patch.object(cache_manager, "get_cached_translation", return_value=None):
        with mock.patch.object(cache_manager, "save_cached_translation"):
            yield


# Reproduces the packaged app: both native sentence-splitting stacks are excluded,
# so importing and using Argos must work through our self-contained splitter.
FROZEN_ENVIRONMENT_SCRIPT = """
import importlib.abc, sys

BLOCKED = ("torch", "stanza", "minisbd", "onnxruntime", "spacy", "thinc")


class BlockFrozenExcludes(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        root = name.split(".")[0]
        if root in BLOCKED and not getattr(sys.modules.get(root), "__argos_stub__", False):
            raise ModuleNotFoundError(f"No module named '{name}'", name=name)
        return None


sys.meta_path.insert(0, BlockFrozenExcludes())

sys.path.insert(0, r"__PROJECT_ROOT__")
import translater

assert translater._ensure_argos_available(), translater.argos_unavailable_reason()

import argostranslate.settings as argos_settings

print("CHUNK_TYPE=" + argos_settings.chunk_type.name)
print("REASON=" + translater.argos_unavailable_reason())
"""


class ArgosRuntimeTest(unittest.TestCase):
    def test_argos_imports_without_torch_stanza_or_spacy(self):
        script = FROZEN_ENVIRONMENT_SCRIPT.replace("__PROJECT_ROOT__", str(ROOT))
        env = dict(os.environ)
        env.pop("ARGOS_CHUNK_TYPE", None)

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            env=env,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CHUNK_TYPE=MINISBD", result.stdout)
        self.assertIn("REASON=\n", result.stdout + "\n")

    def test_packaged_environment_overrides_unsupported_chunk_type(self):
        with mock.patch.dict(os.environ, {"ARGOS_CHUNK_TYPE": "STANZA"}, clear=False):
            with mock.patch.dict(sys.modules):
                sys.modules.pop("stanza", None)
                translater._prepare_argos_environment()
                self.assertEqual(os.environ["ARGOS_CHUNK_TYPE"], "MINISBD")
                self.assertTrue(getattr(sys.modules["stanza"], "__argos_stub__", False))

    def test_prepare_environment_defaults_to_minisbd_and_stubs_stanza(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("ARGOS_CHUNK_TYPE", None)
            with mock.patch.dict(sys.modules):
                sys.modules.pop("stanza", None)
                translater._prepare_argos_environment()
                self.assertEqual(os.environ["ARGOS_CHUNK_TYPE"], "MINISBD")
                self.assertTrue(getattr(sys.modules["stanza"], "__argos_stub__", False))

    def test_sentence_splitter_preserves_terminal_quotes_and_punctuation(self):
        self.assertEqual(
            translater.split_sentences('He said "Hello!" Then left. Next?'),
            ['He said "Hello!"', "Then left.", "Next?"],
        )

    def test_sentence_splitter_chunks_long_unpunctuated_text(self):
        chunks = translater.split_sentences("word " * 120)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= translater._MAX_SENTENCE_CHARS for chunk in chunks))

    def test_packaged_dispatch_uses_utf8_worker_request(self):
        captured = {}

        def fake_run(command, **_kwargs):
            captured["command"] = command
            captured["request"] = json.loads(Path(command[1]).read_text(encoding="utf-8"))
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"result": "Hello", "statuses": ["Ready"], "error": ""}),
                stderr="",
            )

        statuses = []
        with mock.patch.object(translater, "_argos_worker_path", return_value="ArgosWorker.exe"):
            with mock.patch.object(translater.subprocess, "run", side_effect=fake_run):
                result = translater._try_argos_translate(
                    "Привет", "ru", "en", status_callback=statuses.append, allow_install=False
                )

        self.assertEqual(result, "Hello")
        self.assertEqual(captured["request"]["text"], "Привет")
        self.assertFalse(captured["request"]["allow_install"])
        self.assertIn("Ready", statuses)
        self.assertFalse(Path(captured["command"][1]).exists())

    def test_worker_runs_local_argos_path_without_redispatch(self):
        with mock.patch.dict(os.environ, {"CLICKNTRANSLATE_ARGOS_WORKER": "1"}, clear=False):
            argos_worker = importlib.import_module("argos_worker")
        request = {"text": "Привет", "source_code": "ru", "target_code": "en", "allow_install": False}
        with mock.patch.object(argos_worker.translater, "_try_argos_translate_local", return_value="Hello"):
            with mock.patch.object(argos_worker.translater, "_ensure_argos_available", return_value=True):
                payload = argos_worker.run_request(request)

        self.assertEqual(payload["result"], "Hello")
        self.assertFalse(payload["error"])


class ArgosErrorReportingTest(unittest.TestCase):
    def test_unavailable_runtime_is_not_reported_as_missing_package(self):
        error = ModuleNotFoundError("No module named 'torch'")
        with no_translation_cache():
            with mock.patch.object(translater, "get_cached_translator_config", return_value={"translator_engine": "argos"}):
                with mock.patch.object(translater, "_ensure_argos_available", return_value=False):
                    with mock.patch.object(translater, "_argos_import_error", error):
                        with self.assertRaises(Exception) as ctx:
                            translater.translate_text("hello", "en", "ru")

        message = str(ctx.exception)
        self.assertIn("runtime is unavailable", message)
        self.assertIn("torch", message)
        self.assertNotIn("package is not installed", message)

    def test_missing_package_error_explains_how_to_install(self):
        with no_translation_cache():
            with mock.patch.object(translater, "get_cached_translator_config", return_value={"translator_engine": "argos"}):
                with mock.patch.object(translater, "_ensure_argos_available", return_value=True):
                    with mock.patch.object(translater, "_try_argos_translate", return_value=None):
                        with self.assertRaises(Exception) as ctx:
                            translater.translate_text("hello", "en", "ru")

        message = str(ctx.exception)
        self.assertIn("Argos offline translation package is not installed", message)
        self.assertIn("en->ru", message)

    def test_packages_are_only_downloaded_when_progress_can_be_shown(self):
        with no_translation_cache():
            with mock.patch.object(translater, "get_cached_translator_config", return_value={"translator_engine": "argos"}):
                with mock.patch.object(translater, "_ensure_argos_available", return_value=True):
                    with mock.patch.object(translater, "_try_argos_translate", return_value="ok") as argos_mock:
                        translater.translate_text("hello", "en", "ru")
                        self.assertFalse(argos_mock.call_args.kwargs["allow_install"])

                        argos_mock.reset_mock()
                        translater.translate_text("hello", "en", "ru", status_callback=lambda _message: None)
                        self.assertTrue(argos_mock.call_args.kwargs["allow_install"])


class ArgosOnlineFallbackTest(unittest.TestCase):
    def test_failed_online_engine_does_not_reach_another_online_provider(self):
        config = {"translator_engine": "mymemory"}
        with no_translation_cache():
            with mock.patch.object(translater, "get_cached_translator_config", return_value=config):
                with mock.patch.object(translater, "mymemory_translate", side_effect=RuntimeError("mymemory down")):
                    with mock.patch.object(translater, "_try_argos_translate", return_value=None):
                        with mock.patch.object(translater, "google_translate") as google_mock:
                            with self.assertRaises(RuntimeError):
                                translater.translate_text("hello", "en", "ru")

        google_mock.assert_not_called()

    def test_failed_online_engine_falls_back_to_installed_argos_package(self):
        config = {"translator_engine": "google"}
        with no_translation_cache():
            with mock.patch.object(translater, "get_cached_translator_config", return_value=config):
                with mock.patch.object(translater, "google_translate", side_effect=RuntimeError("google down")):
                    with mock.patch.object(translater, "_try_argos_translate", return_value="привет") as argos_mock:
                        self.assertEqual(translater.translate_text("hello", "en", "ru"), "привет")

        self.assertFalse(argos_mock.call_args.kwargs["allow_install"])


class ArgosLanguagePairPlanTest(unittest.TestCase):
    AVAILABLE = {
        ("ru", "en"), ("en", "ru"), ("en", "de"), ("de", "en"),
        ("en", "ja"), ("ja", "en"), ("en", "hi"), ("hi", "en"),
    }

    def test_direct_package_is_preferred(self):
        plan = translater._plan_language_pair("en", "de", self.AVAILABLE, set())
        self.assertEqual(plan, [("en", "de")])

    def test_pair_without_direct_package_pivots_through_english(self):
        plan = translater._plan_language_pair("ru", "de", self.AVAILABLE, set())
        self.assertEqual(plan, [("ru", "en"), ("en", "de")])

    def test_already_installed_packages_are_skipped(self):
        plan = translater._plan_language_pair("ru", "de", self.AVAILABLE, {("ru", "en")})
        self.assertEqual(plan, [("en", "de")])

        plan = translater._plan_language_pair("en", "de", self.AVAILABLE, {("en", "de")})
        self.assertEqual(plan, [])

    def test_unsupported_pair_returns_empty_plan(self):
        plan = translater._plan_language_pair("ja", "xx", self.AVAILABLE, set())
        self.assertEqual(plan, [])

    def test_identical_languages_need_no_package(self):
        self.assertEqual(translater._plan_language_pair("en", "en", self.AVAILABLE, set()), [])


class ArgosPackagingTest(unittest.TestCase):
    def test_spec_excludes_stanza_stack_and_keeps_argos_runtime(self):
        spec_text = (ROOT / "ClicknTranslate.spec").read_text(encoding="utf-8")

        for excluded in ("'torch'", "'stanza'", "'minisbd'", "'onnxruntime'", "'spacy'", "'thinc'"):
            self.assertIn(excluded, spec_text)
        for required in ("argostranslate.package", "argostranslate.translate", "filelock"):
            self.assertIn(required, spec_text)
        self.assertIn("ArgosWorker", spec_text)
        self.assertIn("'argos_worker.py'", spec_text)
        for optional_ocr in ("'easyocr'", "'rapidocr'", "'rapidocr_onnxruntime'"):
            self.assertIn(optional_ocr, spec_text)

    def test_main_preloads_argos_before_qt(self):
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")
        preload_at = main_source.index("translater.preload_argos_runtime()")
        qt_at = main_source.index("from PyQt5 import QtCore")
        self.assertLess(preload_at, qt_at)


if __name__ == "__main__":
    unittest.main()
