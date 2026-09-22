"""Track current screen text separately from asynchronous translation results."""
from collections import OrderedDict


class LiveTextState:
    """One session, one language pair and provider; no persistent screen text.

    Coordinates are always taken from the latest OCR frame. A response may be
    useful for the cache after scrolling, but cannot resurrect its old layout.
    Two observations allow typewriter text to settle; a bounded wait still
    makes progress on continuously changing dialogue.
    """

    def __init__(self, stable_after=0.16, max_wait=1.2, max_entries=512, max_chars=524288):
        self.stable_after = stable_after
        self.max_wait = max_wait
        self.max_entries = max_entries
        self.max_chars = max_chars
        self.lines = []
        self._seen = {}
        self._wave_started = None
        self._cache = OrderedDict()
        self._cache_chars = 0

    def observe(self, lines, now):
        previous = {}
        for item in self.lines:
            previous.setdefault(item[4], []).append(item)
        stable_lines = []
        for item in lines:
            candidates = previous.get(item[4], [])
            match = next((index for index, old in enumerate(candidates)
                          if all(abs(a - b) <= 2 for a, b in zip(item[:4], old[:4]))), None)
            stable_lines.append(candidates.pop(match) if match is not None else item)
        self.lines = stable_lines
        seen = {}
        for *_, text in self.lines:
            if text not in seen:
                first, count = self._seen.get(text, (now, 0))
                seen[text] = (first, count + 1)
        self._seen = seen
        if any(text not in self._cache for text in seen):
            if self._wave_started is None:
                self._wave_started = now
        else:
            self._wave_started = None

    def pending(self, now):
        return [text for text, (first, count) in self._seen.items()
                if text not in self._cache and (
                    (count >= 2 and now - first >= self.stable_after)
                    or (self._wave_started is not None and now - self._wave_started >= self.max_wait))]

    def settling(self, now):
        ready = set(self.pending(now))
        return any(text not in self._cache and text not in ready for text in self._seen)

    def remember(self, pairs):
        for source, translated in pairs:
            if not source or not translated:
                continue
            size = len(source) + len(translated)
            if size > self.max_chars:
                continue
            previous = self._cache.pop(source, None)
            if previous is not None:
                self._cache_chars -= len(source) + len(previous)
            self._cache[source] = translated
            self._cache_chars += size
            while len(self._cache) > self.max_entries or self._cache_chars > self.max_chars:
                old_source, old_translation = self._cache.popitem(last=False)
                self._cache_chars -= len(old_source) + len(old_translation)
        if all(text in self._cache for text in self._seen):
            self._wave_started = None

    def blocks(self):
        blocks = []
        for *rect, source in self.lines:
            if source in self._cache:
                self._cache.move_to_end(source)
                blocks.append((*rect, source, self._cache[source]))
        return blocks

    def reset_visible(self):
        self.lines = []
        self._seen = {}
        self._wave_started = None


def live_frame_changed(previous, current):
    """Catch small label edits that a whole-monitor mean would wash out."""
    if not previous or len(previous) != len(current):
        return True
    differences = [abs(a - b) for a, b in zip(previous, current)]
    return (sum(differences) / max(1, len(differences)) > 3.0
            or sum(value >= 12 for value in differences) >= 2)
