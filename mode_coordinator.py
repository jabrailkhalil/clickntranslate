"""Single-owner coordinator for interactive translation modes.

Only one screen/selection mode may own the desktop at a time.  The coordinator
is deliberately Qt-free so OCR, Dynamic translation and the main window can share it without
creating import cycles.
"""

from __future__ import annotations

import threading
from collections.abc import Callable


_lock = threading.RLock()
_active_name: str | None = None
_stop_active: Callable[[], object] | None = None


def request_mode(name: str, stop_callback: Callable[[], object]) -> bool:
    """Claim the desktop for *name*.

    Returns ``False`` when the same mode was already active: its second hotkey
    press is treated as a toggle-off.  A different active mode is stopped
    before this function returns ``True`` to its replacement.
    """

    global _active_name, _stop_active
    requested = str(name or "").strip()
    if not requested:
        raise ValueError("mode name must not be empty")
    if not callable(stop_callback):
        raise TypeError("stop_callback must be callable")

    with _lock:
        previous_name = _active_name
        previous_stop = _stop_active
        if previous_name == requested:
            _active_name = None
            _stop_active = None
            should_start = False
        else:
            # Publish the new owner before stopping the old one.  A closeEvent
            # from the old QWidget can then release only its own stale name and
            # cannot accidentally clear the new mode.
            _active_name = requested
            _stop_active = stop_callback
            should_start = True

    if previous_stop is not None:
        try:
            previous_stop()
        except Exception:
            # Mode cleanup is best-effort.  The new hotkey must not become
            # unusable merely because a stale QWidget was already destroyed.
            pass
    return should_start


def release_mode(name: str) -> bool:
    """Release *name* if it is still the current owner."""

    global _active_name, _stop_active
    with _lock:
        if _active_name != str(name or "").strip():
            return False
        _active_name = None
        _stop_active = None
        return True


def stop_active_mode() -> str | None:
    """Stop and clear the current mode, returning its name when present."""

    global _active_name, _stop_active
    with _lock:
        name = _active_name
        callback = _stop_active
        _active_name = None
        _stop_active = None
    if callback is not None:
        try:
            callback()
        except Exception:
            pass
    return name


def active_mode() -> str | None:
    with _lock:
        return _active_name


def _reset_for_tests() -> None:
    """Clear process state without invoking application callbacks."""

    global _active_name, _stop_active
    with _lock:
        _active_name = None
        _stop_active = None
