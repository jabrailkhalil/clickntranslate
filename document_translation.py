import threading
from dataclasses import dataclass

import translater
from languages import detect_language_code


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


def split_text_chunks(text, max_chars=DEFAULT_CHUNK_SIZE):
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    chunks = []
    current = []
    current_len = 0

    for paragraph in _paragraph_units(text):
        paragraph_len = len(paragraph)
        if paragraph_len > max_chars:
            if current:
                chunks.append("\n\n".join(current).strip())
                current = []
                current_len = 0
            chunks.extend(_split_long_unit(paragraph, max_chars))
            continue

        extra = 2 if current else 0
        if current and current_len + paragraph_len + extra > max_chars:
            chunks.append("\n\n".join(current).strip())
            current = [paragraph]
            current_len = paragraph_len
        else:
            current.append(paragraph)
            current_len += paragraph_len + extra

    if current:
        chunks.append("\n\n".join(current).strip())

    return [TranslationChunk(index=i, text=chunk) for i, chunk in enumerate(chunks)]


def translate_document_text(
    text,
    source_code,
    target_code,
    provider_engine=None,
    progress_callback=None,
    cancel_event=None,
    max_chars=DEFAULT_CHUNK_SIZE,
):
    chunks = split_text_chunks(text, max_chars=max_chars)
    if not chunks:
        return "", []

    if source_code == "auto":
        source_code = detect_language_code(text[:5000])

    results = []
    translated_parts = []
    total = len(chunks)
    for position, chunk in enumerate(chunks, start=1):
        if cancel_event is not None and cancel_event.is_set():
            break

        _emit_progress(progress_callback, position - 1, total, f"Translating chunk {position}/{total}")
        try:
            if provider_engine:
                translated = translater.translate_text(chunk.text, source_code, target_code, engine=provider_engine)
            else:
                translated = translater.translate_text(chunk.text, source_code, target_code)
            error = ""
        except Exception as exc:
            error = str(exc)
            translated = f"[Translation failed for chunk {position}: {error}]"

        result = TranslationChunkResult(
            index=chunk.index,
            source_text=chunk.text,
            translated_text=translated,
            error=error,
        )
        results.append(result)
        translated_parts.append(translated)
        _emit_progress(progress_callback, position, total, f"Translated chunk {position}/{total}")

    return "\n\n".join(translated_parts).strip(), results


def make_cancel_event():
    return threading.Event()


def _paragraph_units(text):
    parts = []
    current = []
    for line in text.split("\n"):
        if line.strip():
            current.append(line.rstrip())
        elif current:
            parts.append("\n".join(current).strip())
            current = []
    if current:
        parts.append("\n".join(current).strip())
    return parts or [text]


def _split_long_unit(text, max_chars):
    result = []
    remaining = text.strip()
    while len(remaining) > max_chars:
        cut = _best_cut(remaining, max_chars)
        result.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        result.append(remaining)
    return result


def _best_cut(text, max_chars):
    window = text[:max_chars]
    for marker in (". ", "! ", "? ", "; ", "\n", " "):
        cut = window.rfind(marker)
        if cut >= max_chars // 2:
            return cut + len(marker)
    return max_chars


def _emit_progress(callback, done, total, message):
    if callback:
        callback(done, total, message)
