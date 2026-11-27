"""An individual callback cannot strand already accepted translation jobs."""
import asyncio
import threading

import pytest

from background_tasks import IdleExecutor


@pytest.mark.parametrize('failure', [SystemExit, GeneratorExit, asyncio.CancelledError])
def test_aborted_callback_does_not_strand_the_next_accepted_job(failure):
    started, release, finished, cleaned = (threading.Event() for _ in range(4))
    executor = IdleExecutor(workers=1, pending=2, idle_seconds=.02, cleanup=cleaned.set)

    def abort():
        started.set()
        assert release.wait(5)
        raise failure('synthetic callback abort')

    assert executor.submit(abort)
    try:
        assert started.wait(5)
        assert executor.submit(finished.set)
    finally:
        release.set()
    assert finished.wait(2), 'An accepted successor must not depend on another user submission'
    assert cleaned.wait(2)
    with executor._lock:
        assert executor._workers == executor._outstanding == 0
        assert not executor._jobs


def test_callback_abort_does_not_leave_a_phantom_worker_for_a_later_submission():
    first_cleanup, second_done, second_cleanup = (threading.Event() for _ in range(3))

    def cleanup():
        (second_cleanup if first_cleanup.is_set() else first_cleanup).set()

    executor = IdleExecutor(workers=1, idle_seconds=.02, cleanup=cleanup)

    def abort():
        raise SystemExit('synthetic dependency exit')

    assert executor.submit(abort)
    assert first_cleanup.wait(2)
    with executor._lock:
        assert executor._workers == 0
        assert executor._outstanding == 0
    assert executor.submit(second_done.set)
    assert second_done.wait(2)
    assert second_cleanup.wait(2)


def test_ordinary_task_error_still_keeps_the_worker_and_queue_usable():
    completed, cleaned = threading.Event(), threading.Event()
    executor = IdleExecutor(workers=1, idle_seconds=.02, cleanup=cleaned.set)

    def fail():
        raise ValueError('synthetic ordinary failure')

    assert executor.submit(fail)
    assert executor.submit(completed.set)
    assert completed.wait(2)
    assert cleaned.wait(2)
    with executor._lock:
        assert executor._workers == executor._outstanding == 0
