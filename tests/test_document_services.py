import json
import os
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest import mock

import document_parser
import document_storage
import document_translation
import main


class TestDocumentParser(unittest.TestCase):
    def test_parse_txt_detects_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "note.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("Hello\n\nWorld")

            parsed = document_parser.parse_document(path)

        self.assertEqual(parsed.file_name, "note.txt")
        self.assertIn("Hello", parsed.text)
        self.assertEqual(parsed.detected_language, "en")

    def test_parse_docx_preserves_paragraphs(self):
        xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Heading</w:t></w:r></w:p>
    <w:p><w:r><w:t>First paragraph.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Second paragraph.</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "sample.docx")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", xml)

            parsed = document_parser.parse_document(path)

        self.assertIn("Heading\n\nFirst paragraph.\n\nSecond paragraph.", parsed.text)

    def test_unsupported_file_has_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "data.bin")
            with open(path, "wb") as f:
                f.write(b"abc")

            with self.assertRaises(document_parser.DocumentParseError) as ctx:
                document_parser.parse_document(path)

        self.assertIn("Unsupported file type", str(ctx.exception))


class TestDocumentTranslation(unittest.TestCase):
    def test_split_text_chunks_keeps_order(self):
        text = "One paragraph.\n\n" + ("word " * 500) + "\n\nLast paragraph."
        chunks = document_translation.split_text_chunks(text, max_chars=120)

        self.assertGreater(len(chunks), 2)
        self.assertEqual([chunk.index for chunk in chunks], list(range(len(chunks))))
        self.assertTrue(chunks[0].text.startswith("One paragraph."))

    def test_translate_document_text_returns_partial_failures(self):
        calls = []

        def fake_translate(text, source, target):
            calls.append(text)
            if len(calls) == 2:
                raise RuntimeError("provider down")
            return text.upper()

        with mock.patch("document_translation.translater.translate_text", side_effect=fake_translate):
            translated, results = document_translation.translate_document_text(
                "first paragraph\n\nsecond paragraph",
                "en",
                "ru",
                max_chars=20,
            )

        self.assertIn("FIRST PARAGRAPH", translated)
        self.assertIn("Translation failed", translated)
        self.assertEqual(len(results), 2)
        self.assertTrue(results[1].error)

    def test_translate_document_text_can_override_provider(self):
        seen_engines = []

        def fake_translate(text, source, target, engine=None):
            seen_engines.append(engine)
            return text

        with mock.patch("document_translation.translater.translate_text", side_effect=fake_translate):
            document_translation.translate_document_text(
                "first paragraph",
                "en",
                "ru",
                provider_engine="argos",
            )

        self.assertEqual(seen_engines, ["argos"])


class TestDocumentTranslationWindowMessages(unittest.TestCase):
    def test_provider_failure_message_guides_user_to_settings_or_another_provider(self):
        dialog = SimpleNamespace(
            lang="en",
            _provider_engine=lambda: "argos",
            _provider_name=lambda: "Argos",
        )
        results = [
            document_translation.TranslationChunkResult(
                index=0,
                source_text="Hello",
                translated_text="[Translation failed for chunk 1: missing package]",
                error="Argos offline translation package is not installed",
            )
        ]

        message = main.DocumentTranslationDialog._friendly_provider_failure_text(dialog, results)

        self.assertIn("Open Settings", message)
        self.assertIn("choose another provider", message)
        self.assertNotIn("Translation failed for chunk", message)

    def test_partial_failures_keep_regular_chunk_result(self):
        dialog = SimpleNamespace(
            lang="en",
            _provider_engine=lambda: "google",
            _provider_name=lambda: "Google",
        )
        results = [
            document_translation.TranslationChunkResult(
                index=0,
                source_text="Hello",
                translated_text="Hi",
            ),
            document_translation.TranslationChunkResult(
                index=1,
                source_text="World",
                translated_text="[Translation failed for chunk 2: provider down]",
                error="provider down",
            ),
        ]

        message = main.DocumentTranslationDialog._friendly_provider_failure_text(dialog, results)

        self.assertEqual("", message)


class TestDocumentStorage(unittest.TestCase):
    def test_save_and_load_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = document_storage.default_output_paths(temp_dir, "My File.md")
            document_storage.save_text(paths["txt"], "translated")
            document_storage.save_session(paths["session"], {"file_name": "My File.md", "translated_text": "translated"})

            loaded = document_storage.load_session(paths["session"])

        self.assertEqual(loaded["file_name"], "My File.md")
        self.assertEqual(loaded["translated_text"], "translated")
        self.assertTrue(paths["txt"].endswith(".txt"))


if __name__ == "__main__":
    unittest.main()
