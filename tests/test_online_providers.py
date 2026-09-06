import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import unquote, urlsplit

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


class MyMemoryTest(unittest.TestCase):
    def test_long_unicode_input_respects_byte_limit_and_preserves_boundaries(self):
        for text in (
            "Hello world. " * 150,
            "  Проверка перевода. " * 80 + "\n\nКонец.  ",
            "你好世界" * 180,
            "🙂" * 251,
            "a" * 499 + "\r\n\r\n" + "b" * 501,
            "x" * 501,
        ):
            with self.subTest(text=text[:30]):
                calls = []

                def fake_get(url, params, timeout):
                    segment = params['q']
                    self.assertLessEqual(len(segment.encode('utf-8')), 500)
                    self.assertTrue(segment.strip())
                    self.assertEqual(params['langpair'], 'en|ru')
                    calls.append(segment)
                    response = mock.Mock()
                    response.json.return_value = {
                        'responseStatus': 200,
                        'responseData': {'translatedText': segment},
                    }
                    return response

                with mock.patch.object(translater, '_get_http_session', return_value=SimpleNamespace(get=fake_get)):
                    self.assertEqual(translater.mymemory_translate(text, 'en', 'ru'), text)
                self.assertGreater(len(calls), 1)

    def test_empty_input_does_not_contact_provider(self):
        with mock.patch.object(translater, '_get_http_session') as session:
            for text in ('', ' \n\t ', ' ' * 1500):
                self.assertEqual(translater.mymemory_translate(text, 'en', 'ru'), text)
            session.assert_not_called()

    def test_later_chunk_failure_does_not_return_partial_translation(self):
        good = mock.Mock()
        good.json.return_value = {'responseStatus': 200, 'responseData': {'translatedText': 'перевод'}}
        bad = mock.Mock()
        bad.json.return_value = {'responseStatus': 403, 'responseDetails': 'Daily quota exceeded'}
        session = SimpleNamespace(get=mock.Mock(side_effect=[good, bad]))
        with mock.patch.object(translater, '_get_http_session', return_value=session):
            with self.assertRaisesRegex(Exception, 'Daily quota exceeded'):
                translater.mymemory_translate('A sentence. ' * 100, 'en', 'ru')
        self.assertEqual(session.get.call_count, 2)


class LingvaTest(unittest.TestCase):
    def test_paths_are_sent_intact_in_graphql_variables(self):
        text = 'Open /home/user/file?name=тест#part & 100% ready'

        def fake_post(url, json, timeout):
            self.assertTrue(url.endswith('/api/graphql'))
            self.assertEqual(json['variables'], {'source': 'en', 'target': 'ru', 'text': text})
            self.assertNotIn(text, json['query'])
            return FakeResponse(200, {'data': {'translation': {'target': {'text': 'Открой файл'}}}})

        with mock.patch.object(translater, '_get_http_session', return_value=SimpleNamespace(post=fake_post)):
            self.assertEqual(translater.lingva_translate(text, 'en', 'ru'), 'Открой файл')

    def test_graphql_errors_try_the_next_instance(self):
        session = SimpleNamespace(post=mock.Mock(side_effect=[
            FakeResponse(200, {'errors': [{'message': 'Unavailable'}], 'data': None}),
            FakeResponse(200, {'data': {'translation': {'target': {'text': 'Чтение/запись'}}}}),
        ]))
        with mock.patch.object(translater, '_get_http_session', return_value=session):
            self.assertEqual(translater.lingva_translate('Read/write', 'en', 'ru'), 'Чтение/запись')
        self.assertEqual(session.post.call_count, 2)

    def test_reserved_characters_remain_one_rest_query_segment(self):
        text = 'Read?name=тест#part & 100% ready'

        def fake_get(url, timeout):
            parsed = urlsplit(url)
            segments = parsed.path.split('/')
            self.assertEqual(len(segments), 6)
            self.assertEqual(unquote(segments[-1]), text)
            self.assertEqual(parsed.query, '')
            self.assertEqual(parsed.fragment, '')
            return FakeResponse(200, {'translation': 'Открой файл'})

        with mock.patch.object(translater, '_get_http_session', return_value=SimpleNamespace(get=fake_get)):
            self.assertEqual(translater.lingva_translate(text, 'en', 'ru'), 'Открой файл')

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
