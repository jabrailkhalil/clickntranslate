import threading
from dataclasses import dataclass

import translater
from languages import detect_language_code
from translation_chunks import provider_chunks, split_text, restore_boundary_whitespace


DEFAULT_CHUNK_SIZE = 1800


@dataclass(frozen=True)
class TranslationChunk:
    index: int
    text: str


@dataclass(frozen=True)
class TranslationChunkResult:
    index: int
    source_text: str
    translated_text: str
    error: str = ""


def split_text_chunks(text, max_chars=DEFAULT_CHUNK_SIZE, engine=None):
    chunks = (provider_chunks(text, engine, max_chars=max_chars) if engine is not None
              else split_text(text, max_chars=max_chars))
    return [TranslationChunk(index=i, text=chunk) for i, chunk in enumerate(chunks)]


def translate_document_text(
    text,
    source_code,
    target_code,
    provider_engine=None,
    progress_callback=None,
    cancel_event=None,
    max_chars=None,
    partial_callback=None,
):
    text = str(text or '')
    if not text.strip():
        return "", []
    engine = (provider_engine or translater.get_cached_translator_config().get('translator_engine', 'Google')).lower()
    # Plan to the actual provider budget once. No intermediate 1800-character
    # blocks that the HTTP layer would split again at unrelated byte offsets.
    chunks = split_text_chunks(text, max_chars=max_chars, engine=engine)

    if source_code == "auto":
        source_code = detect_language_code(text[:5000])

    results = []
    translated_parts = []
    total = len(chunks)
    _emit_progress(progress_callback, 0, total, f"Translating chunk 1/{total}")

    def status(message):
        _emit_progress(progress_callback, len(results), total, str(message))

    try:
        for index, translated, error in translater.iter_translate_texts(
            [chunk.text for chunk in chunks], source_code, target_code, engine=engine,
            status_callback=status, cancel_callback=cancel_event.is_set if cancel_event is not None else None,
        ):
            chunk = chunks[index]
            if error:
                translated = f"[Translation failed for chunk {index + 1}: {error}]"
            translated = restore_boundary_whitespace(chunk.text, translated)
            results.append(TranslationChunkResult(index, chunk.text, translated, error))
            translated_parts.append(translated)
            if partial_callback:
                partial_callback(''.join(translated_parts), len(results), total)
            _emit_progress(progress_callback, len(results), total, f"Translated chunk {index + 1}/{total}")
    except translater.TranslationCancelledError:
        pass
    return ''.join(translated_parts), results


def make_cancel_event():
    return threading.Event()


def _emit_progress(callback, done, total, message):
    if callback:
        callback(done, total, message)
