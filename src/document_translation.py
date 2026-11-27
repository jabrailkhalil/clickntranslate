import threading
import time
from dataclasses import dataclass

import translater
from languages import detect_language_code, supports_auto_source
from translation_chunks import provider_chunks, split_text, restore_boundary_whitespace
from document_messages import document_message


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
    interface_language='en',
    delta_callback=None,
):
    text = str(text or '')
    if not text.strip():
        return "", []
    engine = (provider_engine or translater.get_cached_translator_config().get('translator_engine', 'Google')).lower()
    # Plan to the actual provider budget once. No intermediate 1800-character
    # blocks that the HTTP layer would split again at unrelated byte offsets.
    chunks = split_text_chunks(text, max_chars=max_chars, engine=engine)

    if source_code == "auto" and not supports_auto_source(engine):
        source_code = detect_language_code(text[:5000])

    results = []
    translated_parts = []
    pending_deltas = []
    pending_size = 0
    last_delta = time.monotonic()
    total = len(chunks)
    _emit_progress(progress_callback, 0, total, document_message(
        interface_language, 'translating', current=1, total=total))

    def status(message):
        _emit_progress(progress_callback, len(results), total, str(message))

    try:
        for index, translated, error in translater.iter_translate_texts(
            [chunk.text for chunk in chunks], source_code, target_code, engine=engine,
            status_callback=status, cancel_callback=cancel_event.is_set if cancel_event is not None else None,
        ):
            chunk = chunks[index]
            if error:
                # Keep raw diagnostics in result.error, out of the translated
                # document and exported text. The visible marker follows UI.
                translated = document_message(interface_language, 'chunk_failed', number=index+1)
            translated = restore_boundary_whitespace(chunk.text, translated)
            results.append(TranslationChunkResult(index, chunk.text, translated, error))
            translated_parts.append(translated)
            if delta_callback:
                pending_deltas.append(translated)
                pending_size += len(translated)
                now = time.monotonic()
                if len(results) == 1 or pending_size >= 65536 or now - last_delta >= .05:
                    delta_callback(''.join(pending_deltas), len(results), total)
                    pending_deltas.clear()
                    pending_size, last_delta = 0, now
            if partial_callback:
                partial_callback(''.join(translated_parts), len(results), total)
            _emit_progress(progress_callback, len(results), total, document_message(
                interface_language, 'translated', current=index+1, total=total))
    except translater.TranslationCancelledError:
        pass
    if delta_callback and pending_deltas:
        delta_callback(''.join(pending_deltas), len(results), total)
    return ''.join(translated_parts), results


def make_cancel_event():
    return threading.Event()


def _emit_progress(callback, done, total, message):
    if callback:
        callback(done, total, message)
