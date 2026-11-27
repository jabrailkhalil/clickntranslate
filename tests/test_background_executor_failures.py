"""Failed thread creation must not poison later dynamic translations."""
import threading
import time
from unittest import mock

import pytest

import background_tasks


def wait_idle(executor):
    deadline = time.monotonic() + 3
    while executor._workers and time.monotonic() < deadline:
        time.sleep(.005)
    assert executor._workers == executor._outstanding == 0
    assert not executor._jobs


@pytest.mark.parametrize('failure', ['construct', 'start'])
def test_failed_first_worker_rejects_its_job_and_allows_immediate_retry(failure):
    executor = background_tasks.IdleExecutor(workers=1, pending=1, idle_seconds=.03)
    rejected = mock.Mock()

    class UnavailableThread:
        def __init__(self, **kwargs):
            if failure == 'construct':
                raise RuntimeError('temporary thread allocation failure')

        def start(self):
            raise RuntimeError('temporary thread start failure')

    with mock.patch.object(background_tasks.threading, 'Thread', UnavailableThread):
        assert executor.submit(rejected) is False
    assert executor._workers == executor._outstanding == 0
    completed = threading.Event()
    assert executor.submit(completed.set)
    assert completed.wait(2)
    wait_idle(executor)
    rejected.assert_not_called()


def test_failed_pool_expansion_preserves_running_jobs_and_rejects_only_new_work():
    executor = background_tasks.IdleExecutor(workers=2, pending=1, idle_seconds=.03)
    entered, release = threading.Event(), threading.Event()
    rejected = mock.Mock()

    def first():
        entered.set()
        assert release.wait(2)

    assert executor.submit(first)
    try:
        assert entered.wait(2)
        with mock.patch.object(background_tasks.threading, 'Thread', side_effect=OSError('no threads')):
            assert executor.submit(rejected) is False
        assert executor._workers == executor._outstanding == 1
        completed = threading.Event()
        assert executor.submit(completed.set)
        assert completed.wait(2)
    finally:
        release.set()
    wait_idle(executor)
    rejected.assert_not_called()


def test_job_taken_by_an_existing_worker_is_not_rejected_or_run_twice():
    executor = background_tasks.IdleExecutor(workers=2, pending=1, idle_seconds=.03)
    entered, release, second_ran, finish_second = (threading.Event() for _ in range(4))
    calls = []

    def first():
        entered.set()
        assert release.wait(2)

    def second():
        calls.append('second')
        second_ran.set()
        assert finish_second.wait(2)

    class FailedExpansion:
        def __init__(self, **kwargs):
            pass

        def start(self):
            release.set()
            assert second_ran.wait(2)
            raise RuntimeError('pool expansion failed after an existing worker woke')

    assert executor.submit(first)
    try:
        assert entered.wait(2)
        with mock.patch.object(background_tasks.threading, 'Thread', FailedExpansion):
            assert executor.submit(second) is True
        assert executor._workers == executor._outstanding == 1
    finally:
        release.set()
        finish_second.set()
    wait_idle(executor)
    assert calls == ['second']


def test_concurrent_submission_during_failed_first_launch_gets_a_real_worker():
    executor = background_tasks.IdleExecutor(workers=1, pending=2, idle_seconds=.03)
    native_thread = threading.Thread
    launching, release, second_submitting, second_ran = (threading.Event() for _ in range(4))
    attempts = []
    results = {}
    rejected = mock.Mock()

    class FirstLaunchFails:
        def __init__(self, **kwargs):
            pass

        def start(self):
            launching.set()
            assert release.wait(2)
            raise RuntimeError('first worker cannot start')

    def factory(**kwargs):
        attempts.append(True)
        return FirstLaunchFails(**kwargs) if len(attempts) == 1 else native_thread(**kwargs)

    def submit_second():
        second_submitting.set()
        results['second'] = executor.submit(second_ran.set)

    first = native_thread(target=lambda: results.update(first=executor.submit(rejected)))
    second = native_thread(target=submit_second)
    with mock.patch.object(background_tasks.threading, 'Thread', factory):
        first.start()
        try:
            assert launching.wait(2)
            second.start()
            assert second_submitting.wait(2)
        finally:
            release.set()
        first.join(2)
        second.join(2)
        assert not first.is_alive() and not second.is_alive()
        assert second_ran.wait(2)
    wait_idle(executor)
    assert results == {'first': False, 'second': True}
    assert len(attempts) == 2
    rejected.assert_not_called()
