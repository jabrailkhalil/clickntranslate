import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import translater  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, payload=None, raises=None):
        self.status_code = status_code
        self._payload = payload
        self._raises = raises

    def json(self):
        if self._raises is not None:
            raise self._raises
        return self._payload


class LibreTranslateTest(unittest.TestCase):
    def test_key_gated_instance_is_skipped_for_a_working_one(self):
        calls = []

        def fake_post(url, json=None, timeout=None):
            calls.append(url)
            if "disroot" in url:
                return FakeResponse(200, {"translatedText": "привет"})
            return FakeResponse(400, {"error": "Visit https://portal.libretranslate.com to get an API key"})

        with mock.patch.object(translater, "_get_http_session", return_value=SimpleNamespace(post=fake_post)):
            self.assertEqual(translater.libretranslate("hello", "en", "ru"), "привет")

        self.assertTrue(calls)

    def test_server_error_text_reaches_the_user(self):
        def fake_post(url, json=None, timeout=None):
            return FakeResponse(400, {"error": "Visit https://portal.libretranslate.com to get an API key"})

        with mock.patch.object(translater, "_get_http_session", return_value=SimpleNamespace(post=fake_post)):
            with self.assertRaises(Exception) as ctx:
                translater.libretranslate("hello", "en", "ru")

        self.assertIn("API key", str(ctx.exception))

    def test_dead_instances_are_not_configured(self):
        source = (ROOT / "translater.py").read_text(encoding="utf-8")

        for dead in ("translate.argosopentech.com", "translate.terraprint.co", "lingva.pussthecat.org"):
            self.assertNotIn(f"'https://{dead}'", source)


class LingvaTest(unittest.TestCase):
    def test_failing_instance_falls_through_and_reports_status(self):
        def fake_get(url, timeout=None):
            if "vercel.app" in url or "lingva.ml" in url:
                return FakeResponse(500, {"error": "An error occurred while retrieving the translation"})
            return FakeResponse(200, {"translation": "привет"})

        with mock.patch.object(translater, "_get_http_session", return_value=SimpleNamespace(get=fake_get)):
            self.assertEqual(translater.lingva_translate("hello", "en", "ru"), "привет")

    def test_active_vercel_instance_is_configured_first(self):
        calls = []

        def fake_get(url, timeout=None):
            calls.append(url)
            return FakeResponse(200, {"translation": "привет"})

        with mock.patch.object(translater, "_get_http_session", return_value=SimpleNamespace(get=fake_get)):
            self.assertEqual(translater.lingva_translate("hello", "en", "ru"), "привет")

        self.assertTrue(calls[0].startswith("https://lingva.vercel.app/"))

    def test_all_instances_down_surfaces_server_message(self):
        def fake_get(url, timeout=None):
            return FakeResponse(500, {"error": "An error occurred while retrieving the translation"})

        with mock.patch.object(translater, "_get_http_session", return_value=SimpleNamespace(get=fake_get)):
            with self.assertRaises(Exception) as ctx:
                translater.lingva_translate("hello", "en", "ru")

        self.assertIn("An error occurred", str(ctx.exception))


class ServerErrorDetailTest(unittest.TestCase):
    def test_non_json_body_falls_back_to_status_code(self):
        response = FakeResponse(502, raises=ValueError("not json"))
        self.assertEqual(translater._server_error_detail(response), "HTTP 502")

    def test_message_field_is_used_when_error_is_absent(self):
        response = FakeResponse(429, {"message": "Too many requests"})
        self.assertEqual(translater._server_error_detail(response), "Too many requests")


class GoogleTranslateTest(unittest.TestCase):
    def test_rate_limited_primary_endpoint_uses_google_fallback(self):
        primary = mock.Mock(status_code=429)
        fallback = mock.Mock(status_code=200)
        fallback.json.return_value = ["Привет, мир"]
        session = SimpleNamespace(get=mock.Mock(side_effect=[primary, fallback]))

        with mock.patch.object(translater, "_get_http_session", return_value=session):
            result = translater.google_translate("Hello world", "en", "ru")

        self.assertEqual(result, "Привет, мир")
        self.assertEqual(session.get.call_count, 2)
        first_url = session.get.call_args_list[0].args[0]
        fallback_url = session.get.call_args_list[1].args[0]
        self.assertEqual(first_url, "https://translate.googleapis.com/translate_a/single")
        self.assertEqual(fallback_url, "https://clients5.google.com/translate_a/t")
        self.assertEqual(
            session.get.call_args_list[1].kwargs["params"]["client"],
            "dict-chrome-ex",
        )
        fallback.raise_for_status.assert_called_once_with()

    def test_non_rate_limit_error_does_not_change_google_endpoint(self):
        response = mock.Mock(status_code=500)
        response.raise_for_status.side_effect = RuntimeError("google down")
        session = SimpleNamespace(get=mock.Mock(return_value=response))

        with mock.patch.object(translater, "_get_http_session", return_value=session):
            with self.assertRaisesRegex(RuntimeError, "google down"):
                translater.google_translate("Hello world", "en", "ru")

        self.assertEqual(session.get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
