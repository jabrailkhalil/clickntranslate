"""Idle lifetime of an explicitly selected/used local OCR model."""
import threading
import time

IDLE_SECONDS = 5 * 60
PRESSURE_INTERVAL = 30


class IdleLifetime:
    def __init__(self, idle_seconds=IDLE_SECONDS, clock=time.monotonic):
        self._idle = idle_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._pinned = False
        self._used = clock()

    def pin(self, enabled):
        with self._lock:
            if self._pinned and not enabled:
                self._used = self._clock()
            self._pinned = bool(enabled)

    def touch(self):
        with self._lock:
            self._used = self._clock()

    def remaining(self):
        with self._lock:
            return None if self._pinned else max(0., self._idle - (self._clock() - self._used))
