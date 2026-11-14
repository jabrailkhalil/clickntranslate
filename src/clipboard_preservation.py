"""Restore temporary clipboard text only while that operation still owns it."""

from __future__ import annotations


_UNKNOWN = object()


def clipboard_sequence_number():
    """Use native change identities; text comparison is a fallback only."""
    import platform_support

    try:
        if platform_support.IS_MAC:
            from macos_desktop import clipboard_sequence
            return clipboard_sequence()
        if platform_support.IS_WINDOWS:
            import ctypes
            return int(ctypes.windll.user32.GetClipboardSequenceNumber()) or None
    except Exception:
        pass
    return None


class ClipboardPreservation:
    """A text snapshot and the identity of this operation's last clipboard write.

    Every write/capture must be claimed before waiting for unrelated work.
    Failed reads or a changed sequence fail closed: a newer user copy is kept.
    """

    def __init__(self, read_text, copy_text, sequence_number=None):
        self._read_text = read_text
        self._copy_text = copy_text
        self._sequence_number = sequence_number or clipboard_sequence_number
        self._owned_sequence = None
        self._owned_text = _UNKNOWN
        try:
            self.previous = str(read_text() or "")
        except Exception:
            self.previous = None

    def _sequence(self):
        try:
            return self._sequence_number()
        except Exception:
            return None

    def claim(self, text=_UNKNOWN):
        """Remember a just-completed app write or read, before yielding control."""
        before = self._sequence()
        if text is _UNKNOWN:
            try:
                text = str(self._read_text() or "")
            except Exception:
                text = _UNKNOWN
        after = self._sequence()
        if before != after:
            return False
        self._owned_sequence = after
        self._owned_text = text
        return after is not None or text is not _UNKNOWN

    def owns_clipboard(self):
        if self._owned_sequence is not None:
            # Do not fall back to equal text when native identity became
            # unavailable: another copy may contain exactly the same text.
            if self._sequence() != self._owned_sequence:
                return False
        elif self._owned_text is not _UNKNOWN:
            try:
                if str(self._read_text() or "") != self._owned_text:
                    return False
            except Exception:
                return False
        else:
            return False
        return True

    def claim_changed(self):
        """Claim the first copy response: None means pending, False uncertain.

        Read and verify the changed identity together, so a second clipboard
        writer racing with that read cannot be claimed as this operation's.
        """
        before = self._sequence()
        if self._owned_sequence is not None:
            if before is None:
                return False
            if before == self._owned_sequence:
                return None
        try:
            text = str(self._read_text() or "")
        except Exception:
            text = _UNKNOWN
        if self._owned_sequence is None:
            if text is _UNKNOWN:
                return False
            if text == self._owned_text:
                return None
        after = self._sequence()
        if before != after:
            return False
        self._owned_sequence = after
        self._owned_text = text
        return True

    def preserve_current_if_changed(self):
        """Keep a newer user copy before another temporary write, e.g. paste."""
        if self.owns_clipboard():
            return
        try:
            self.previous = str(self._read_text() or "")
        except Exception:
            self.previous = None
        self._owned_sequence = None
        self._owned_text = _UNKNOWN

    def restore(self):
        if self.previous is None or not self.owns_clipboard():
            return False
        try:
            return self._copy_text(self.previous) is not False
        except Exception:
            return False
