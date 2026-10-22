"""Bounded in-memory timings, without inputs, results, URLs or credentials."""
from collections import deque
from functools import wraps
import threading
import time

_LOCK = threading.Lock()
_SAMPLES = {}
_LIMIT = 64


def measure(operation):
    def decorate(function):
        @wraps(function)
        def measured(*args, **kwargs):
            started = time.perf_counter()
            failed = False
            try:
                return function(*args, **kwargs)
            except Exception:
                failed = True
                raise
            finally:
                elapsed = (time.perf_counter() - started) * 1000
                with _LOCK:
                    if operation not in _SAMPLES and len(_SAMPLES) < 32:
                        _SAMPLES[operation] = (deque(maxlen=_LIMIT), [0, 0])
                    if operation in _SAMPLES:
                        values, totals = _SAMPLES[operation]
                        values.append(elapsed)
                        totals[0] += 1
                        totals[1] += int(failed)
        return measured
    return decorate


def snapshot():
    with _LOCK:
        result = {}
        for operation, (samples, totals) in _SAMPLES.items():
            values = sorted(samples)
            result[operation] = dict(count=totals[0], failures=totals[1], sample_count=len(values),
                median_ms=round((values[(len(values)-1)//2] + values[len(values)//2]) / 2, 2),
                p95_ms=round(values[min(len(values)-1, int(len(values)*.95))], 2),
                max_ms=round(values[-1], 2))
        return result
