"""Lossless request planning shared by document and plain-text translation."""
import re


def completion_percent(done, total):
    """Progress by completed request parts, never an estimate of elapsed time."""
    return max(0, min(100, int(done * 100 // total))) if total > 0 else 0


# These are conservative client budgets, not claimed service-wide quotas.
# MyMemory's documented limit is specifically 500 UTF-8 bytes.
PROVIDER_BYTE_LIMITS = {
    'google': 1500, 'lingva': 1500, 'libretranslate': 1500,
    'mymemory': 500, 'hymt': 1000,
}
_PARAGRAPH_END = re.compile(r'(?:\r?\n[ \t]*){2,}')
_SENTENCE_END = re.compile(r'(?:[.!?]+["\'”’»)\]]*(?:\s+|$)|[。！？…]+["\'”’»)\]]*\s*)')
_ABBREVIATIONS = {
    'mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr', 'st', 'vs', 'etc',
    'e.g', 'i.e', 'т.д', 'т.п', 'т.е', 'т.к', 'г', 'ул', 'д', 'стр', 'рис',
}


def provider_chunks(text, engine, max_chars=None):
    engine = str(engine or 'google').lower()
    if engine == 'argos':
        return split_text(text, max_chars=1800 if max_chars is None else max_chars)
    return split_text(text, max_bytes=PROVIDER_BYTE_LIMITS.get(engine, 1500), max_chars=max_chars)


def _cut_at_boundary(window, limit):
    paragraphs = [m for m in _PARAGRAPH_END.finditer(window) if m.end() <= limit]
    if paragraphs:
        return paragraphs[-1].end()
    sentence_end = 0
    for match in _SENTENCE_END.finditer(window):
        if match.end() > limit:
            continue
        if window[match.start()] == '.':
            token = re.search(r'([\w.]+)$', window[:match.start()])
            token = token.group(1).lower() if token else ''
            if token in _ABBREVIATIONS or len(token) == 1:
                continue
        sentence_end = match.end()
    if sentence_end:
        return sentence_end
    for pattern in (r'\r?\n', r'\s+'):
        boundaries = [m for m in re.finditer(pattern, window) if m.end() <= limit]
        if boundaries:
            return boundaries[-1].end()
    return limit


def split_text(text, *, max_bytes=None, max_chars=None):
    """Pack whole paragraphs/sentences first; retain every input character.

    Oversized sentences fall back to line/word boundaries, then Unicode code
    points. Joining the returned pieces always recreates the input exactly.
    """
    for limit in (max_bytes, max_chars):
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
            raise ValueError('Translation chunk limits must be positive integers')
    if max_bytes is None and max_chars is None:
        raise ValueError('A translation chunk limit is required')
    text = str(text or '')
    parts = []
    offset = 0
    while offset < len(text):
        length = min(x for x in (max_bytes, max_chars, len(text) - offset) if x is not None)
        window = text[offset:offset + length]
        if max_bytes is not None:
            window = window.encode('utf-8')[:max_bytes].decode('utf-8', errors='ignore')
        if not window:
            raise ValueError('The byte limit cannot fit one Unicode character')
        cut = len(window)
        if offset + cut < len(text):
            # Include one lookahead character so punctuation at the budget's
            # edge isn't mistaken for the end of a decimal or abbreviation.
            inspected = text[offset:offset + cut + 1]
            cut = _cut_at_boundary(inspected, cut)
        parts.append(text[offset:offset + cut])
        offset += cut
    return parts


def restore_boundary_whitespace(source, translation):
    if not source.strip():
        return source
    leading = source[:len(source) - len(source.lstrip())]
    trailing = source[len(source.rstrip()):]
    return leading + translation.strip() + trailing
