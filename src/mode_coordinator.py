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
_listeners: set[Callable[[], object]] = set()
_request_generation = 0
_deferred_name: str | None = None


def defer_mode_request(name: str) -> int | None:
    """Reserve a delayed hotkey; repeating the pending hotkey cancels it."""
    global _request_generation, _deferred_name
    requested = str(name or "").strip()
    if not requested:
        raise ValueError("mode name must not be empty")
    with _lock:
        previous = _deferred_name
        _request_generation += 1
        _deferred_name = None if previous == requested else requested
        return _request_generation if _deferred_name is not None else None


def mode_request_is_current(token: int) -> bool:
    with _lock:
        return _deferred_name is not None and token == _request_generation


def cancel_deferred_mode_request() -> None:
    """Invalidate queued capture work when a newer non-capture action starts."""
    global _request_generation, _deferred_name
    with _lock:
        _request_generation += 1
        _deferred_name = None


def subscribe(callback: Callable[[], object]) -> Callable[[], None]:
    """Observe capture ownership before a new owner takes its first screenshot."""
    with _lock:
        _listeners.add(callback)

    def unsubscribe():
        with _lock:
            _listeners.discard(callback)
    return unsubscribe


def _notify_listeners():
    with _lock:
        listeners = tuple(_listeners)
    for callback in listeners:
        try:
            callback()
        except Exception:
            # Optional UI must not prevent capture or cleanup.
            pass


def request_mode(name: str, stop_callback: Callable[[], object]) -> bool:
    """Claim the desktop for *name*.

    Returns ``False`` when the same mode was already active: its second hotkey
    press is treated as a toggle-off.  A different active mode is stopped
    before this function returns ``True`` to its replacement.
    """

    global _active_name, _stop_active, _request_generation, _deferred_name
    requested = str(name or "").strip()
    if not requested:
        raise ValueError("mode name must not be empty")
    if not callable(stop_callback):
        raise TypeError("stop_callback must be callable")

    with _lock:
        _request_generation += 1
        _deferred_name = None
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

    _notify_listeners()
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

    global _active_name, _stop_active, _request_generation, _deferred_name
    with _lock:
        if _active_name != str(name or "").strip():
            return False
        _active_name = None
        _stop_active = None
        _request_generation += 1
        _deferred_name = None
    _notify_listeners()
    return True


def stop_active_mode() -> str | None:
    """Stop and clear the current mode, returning its name when present."""

    global _active_name, _stop_active, _request_generation, _deferred_name
    with _lock:
        name = _active_name
        callback = _stop_active
        _active_name = None
        _stop_active = None
        _request_generation += 1
        _deferred_name = None
    _notify_listeners()
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

    global _active_name, _stop_active, _request_generation, _deferred_name
    with _lock:
        _active_name = None
        _stop_active = None
        _request_generation += 1
        _deferred_name = None
