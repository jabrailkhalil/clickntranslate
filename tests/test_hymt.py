import os
import shutil
import threading
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest import mock

import cache_manager
import settings_window as sw
import translater


class TestHyMTInstallerHelpers(unittest.TestCase):
    def test_get_hymt_download_plan_uses_working_official_artifacts(self):
        dummy = object()

        plan = sw.SettingsWindow._get_hymt_download_plan(dummy, is_x64=True)

        self.assertEqual(plan["model"]["name"], "HY-MT1.5-1.8B-Q4_K_M.gguf")
        self.assertIn("huggingface.co/tencent/HY-MT1.5-1.8B-GGUF", plan["model"]["url"])
        self.assertEqual(len(plan["model"]["sha256"]), 64)
        self.assertTrue(plan["runtime"]["name"].startswith("llama-"))
        self.assertIn("github.com/ggml-org/llama.cpp", plan["runtime"]["url"])
        self.assertEqual(len(plan["runtime"]["sha256"]), 64)

    def test_find_hymt_model_and_runner_under_searches_recursively(self):
        dummy = object()
        root = tempfile.mkdtemp(prefix="hymt_find_")
        try:
            model_dir = os.path.join(root, "models")
            bin_dir = os.path.join(root, "bin")
            os.makedirs(model_dir, exist_ok=True)
            os.makedirs(bin_dir, exist_ok=True)
            model_path = os.path.join(model_dir, "HY-MT1.5-1.8B-Q4_K_M.gguf")
            runner_path = os.path.join(bin_dir, "llama-cli.exe")
            with open(model_path, "wb") as f:
                f.write(b"gguf")
            with open(runner_path, "wb") as f:
                f.write(b"exe")

            self.assertEqual(sw.SettingsWindow._find_hymt_model_under(dummy, root), model_path)
            self.assertEqual(sw.SettingsWindow._find_hymt_runner_under(dummy, root), runner_path)
        finally:
            try:
                import shutil
                shutil.rmtree(root, ignore_errors=True)
            except Exception:
                pass

    def test_install_hymt_worker_builds_local_package_atomically(self):
        root = tempfile.mkdtemp(prefix="hymt_install_")
        try:
            final_dir = os.path.join(root, "hymt")

            class DummyInstaller:
                def __init__(self):
                    self.parent = SimpleNamespace(current_interface_language="en")
                    self._hymt_cancel_requested = threading.Event()
                    self._hymt_temp_dir = ""
                    self._hymt_install_phase = "idle"
                    self.progress = []

                def _local_hymt_dir(self):
                    return final_dir

                def _get_hymt_download_plan(self, is_x64=True):
                    return {
                        "runtime": {"name": "runtime.zip", "url": "runtime", "sha256": ""},
                        "model": {"name": sw.HYMT_MODEL_FILE, "url": "model", "sha256": ""},
                        "docs": [{"name": "License.txt", "url": "license"}],
                    }

                def _emit_hymt_progress(self, text, percent=0, determinate=True):
                    self.progress.append((text, percent, determinate))

                def _download_file(self, url, destination_path, **_kwargs):
                    if url == "runtime":
                        with zipfile.ZipFile(destination_path, "w") as zf:
                            zf.writestr("llama-cli.exe", b"exe")
                    elif url == "model":
                        with open(destination_path, "wb") as f:
                            f.write(b"gguf")
                    else:
                        with open(destination_path, "w", encoding="utf-8") as f:
                            f.write("license")

            dummy = DummyInstaller()
            dummy._check_hymt_cancel_requested = lambda: sw.SettingsWindow._check_hymt_cancel_requested(dummy)
            dummy._verify_file_sha256 = lambda *_args, **_kwargs: None
            dummy._find_hymt_model_under = lambda path: sw.SettingsWindow._find_hymt_model_under(dummy, path)
            dummy._find_hymt_runner_under = lambda path: sw.SettingsWindow._find_hymt_runner_under(dummy, path)
            dummy._restore_hymt_backup = lambda final, backup: sw.SettingsWindow._restore_hymt_backup(dummy, final, backup)

            invoke_calls = []

            def fake_invoke(_obj, method_name, *_args):
                invoke_calls.append(method_name)
                return True

            with mock.patch.object(sw.QMetaObject, "invokeMethod", side_effect=fake_invoke):
                sw.SettingsWindow._install_hymt_worker(dummy)

            self.assertTrue(os.path.isfile(os.path.join(final_dir, sw.HYMT_MODEL_FILE)))
            self.assertTrue(sw.SettingsWindow._find_hymt_runner_under(dummy, final_dir).endswith("llama-cli.exe"))
            self.assertTrue(os.path.isfile(os.path.join(final_dir, "NOTICE.txt")))
            self.assertIn("_on_hymt_install_ready", invoke_calls)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestHyMTTranslatorHelpers(unittest.TestCase):
    def test_clean_hymt_output_removes_prompt_and_special_tokens(self):
        prompt = "<｜hy_begin▁of▁sentence｜><｜hy_User｜>Translate<｜hy_Assistant｜>"
        raw = prompt + " Hello world <｜hy_place▁holder▁no▁2｜>"

        self.assertEqual(translater._clean_hymt_output(raw, prompt), "Hello world")

    def test_clean_hymt_output_removes_llama_cli_banner(self):
        prompt = "<｜hy_begin▁of▁sentence｜><｜hy_User｜>Translate\n\nHello world<｜hy_Assistant｜>"
        raw = (
            "Loading model...\n\n"
            "build      : b9048\n"
            "model      : HY-MT1.5-1.8B-Q4_K_M.gguf\n"
            "available commands:\n"
            "  /exit or Ctrl+C     stop or exit\n\n"
            f"> {prompt}\n\n"
            "Привет, мир!\n\n"
            "Exiting...\n"
        )

        self.assertEqual(translater._clean_hymt_output(raw, prompt), "Привет, мир!")

    def test_argos_does_not_silently_fallback_online(self):
        with mock.patch.object(translater, "get_cached_translator_config", return_value={"translator_engine": "argos"}):
            with mock.patch.object(translater, "HAS_ARGOS", True):
                with mock.patch.object(translater, "_try_argos_translate", return_value=None):
                    with mock.patch.object(translater, "google_translate") as google_mock:
                        with self.assertRaises(Exception):
                            translater.translate_text("hello", "en", "ru")

        google_mock.assert_not_called()

    def test_online_provider_does_not_fallback_to_other_provider_by_default(self):
        with mock.patch.object(translater, "get_cached_translator_config", return_value={"translator_engine": "google"}):
            with mock.patch.object(translater, "google_translate", side_effect=RuntimeError("google down")):
                with mock.patch.object(translater, "lingva_translate") as lingva_mock:
                    with mock.patch.object(translater, "HAS_ARGOS", False):
                        with self.assertRaises(RuntimeError):
                            translater.translate_text("hello", "en", "ru")

        lingva_mock.assert_not_called()

    def test_translation_cache_is_engine_scoped(self):
        data_dir = tempfile.mkdtemp(prefix="cache_engine_")
        try:
            cache_manager.invalidate_translation_cache()
            cache_manager.save_cached_translation(data_dir, "hello", "en", "ru", "привет", engine="google")
            self.assertEqual(
                cache_manager.get_cached_translation(data_dir, "hello", "en", "ru", engine="google"),
                "привет",
            )
            self.assertIsNone(
                cache_manager.get_cached_translation(data_dir, "hello", "en", "ru", engine="hymt")
            )
        finally:
            try:
                import shutil
                shutil.rmtree(data_dir, ignore_errors=True)
            except Exception:
                pass

    def test_translation_cache_is_data_dir_scoped(self):
        data_dir_1 = tempfile.mkdtemp(prefix="cache_dir_1_")
        data_dir_2 = tempfile.mkdtemp(prefix="cache_dir_2_")
        try:
            cache_manager.invalidate_translation_cache()
            cache_manager.save_cached_translation(data_dir_1, "hello", "en", "ru", "dir1", engine="google")

            self.assertEqual(
                cache_manager.get_cached_translation(data_dir_1, "hello", "en", "ru", engine="google"),
                "dir1",
            )
            self.assertIsNone(
                cache_manager.get_cached_translation(data_dir_2, "hello", "en", "ru", engine="google")
            )
        finally:
            shutil.rmtree(data_dir_1, ignore_errors=True)
            shutil.rmtree(data_dir_2, ignore_errors=True)

    def test_translation_cache_key_does_not_contain_raw_text(self):
        data_dir = tempfile.mkdtemp(prefix="cache_privacy_")
        try:
            cache_manager.invalidate_translation_cache()
            cache_manager.save_cached_translation(
                data_dir,
                "secret screen text",
                "en",
                "ru",
                "секрет",
                engine="google",
            )
            cache = cache_manager._load_translation_cache(data_dir)

            self.assertTrue(cache)
            self.assertFalse(any("secret screen text" in key for key in cache))
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
