"""Optional readiness admission survives thread startup faults without models."""
import threading
from unittest import mock

import pytest

from native_worker_client import NativeWorkerClient
import ocr_readiness


@pytest.fixture
def service():
    client = NativeWorkerClient()
    client.refresh_policy = mock.Mock(wraps=client.refresh_policy)
    client.retire_engine = mock.Mock(wraps=client.retire_engine)
    instance = ocr_readiness.ReadinessService(client, mock.Mock())
    yield instance
    # A failing pre-fix admission has no actual worker to join. Do not spend
    # the normal shutdown grace period waiting for that nonexistent thread.
    if instance._running and not instance.idle.is_set():
        instance.idle.set()
    instance.shutdown()


def request(service, operation):
    if operation == 'select':
        service.select('RapidOCR', 'ar')
    elif operation == 'activity':
        service.activity('region-fixture', 'RapidOCR')
    else:
        service.invalidate('RapidOCR')


@pytest.mark.parametrize('operation', ['select', 'activity', 'invalidate'])
@pytest.mark.parametrize('stage', ['construct', 'start'])
def test_failed_readiness_thread_is_idle_and_an_identical_request_can_retry(service, operation, stage):
    if stage == 'construct':
        factory = mock.Mock(side_effect=OSError('fixture thread constructor unavailable'))
    else:
        factory = mock.Mock(return_value=mock.Mock(start=mock.Mock(
            side_effect=RuntimeError('fixture thread start unavailable'))))
    with mock.patch.object(ocr_readiness.threading, 'Thread', factory):
        request(service, operation)
    assert service.idle.is_set()
    assert not service._running
    service.prepare.assert_not_called()
    request(service, operation)
    assert service.idle.wait(2)
    assert not service._running
    if operation == 'select':
        service.prepare.assert_called_once()
        assert service.prepare.call_args.args[:2] == ('rapidocr', 'ar')
    elif operation == 'activity':
        assert service.client.is_pinned('rapidocr')
        service.client.refresh_policy.assert_called()
        service.prepare.assert_not_called()
    else:
        service.client.retire_engine.assert_called_once_with('rapidocr')
        service.prepare.assert_not_called()


@pytest.mark.parametrize('operation', ['select', 'invalidate'])
@pytest.mark.parametrize('stage', ['construct', 'start'])
def test_newer_revision_is_not_stranded_while_a_previous_thread_launch_fails(
        service, operation, stage):
    real_thread = threading.Thread
    entered, release, newer_entered = threading.Event(), threading.Event(), threading.Event()
    errors, calls = [], []

    def fail():
        entered.set()
        assert release.wait(2)
        raise RuntimeError('fixture first launch rejected')

    def factory(*args, **kwargs):
        calls.append(True)
        if len(calls) == 1:
            if stage == 'construct':
                fail()
            return mock.Mock(start=fail)
        return real_thread(*args, **kwargs)

    def first():
        try:
            service.select('RapidOCR', 'en')
        except Exception as error:
            errors.append(error)

    def newer():
        newer_entered.set()
        try:
            if operation == 'select':
                service.select('RapidOCR', 'ar')
            else:
                service.invalidate('RapidOCR')
        except Exception as error:
            errors.append(error)

    older = real_thread(target=first, name='readiness-first-fixture')
    latest = real_thread(target=newer, name='readiness-newer-fixture')
    with mock.patch.object(ocr_readiness.threading, 'Thread', factory):
        try:
            older.start()
            assert entered.wait(2)
            latest.start()
            assert newer_entered.wait(2)
        finally:
            release.set()
            older.join(2)
            if latest.ident is not None:
                latest.join(2)
    assert not older.is_alive() and not latest.is_alive()
    assert not errors
    assert service.idle.wait(2)
    assert not service._running
    if operation == 'select':
        service.prepare.assert_called_once()
        assert service.prepare.call_args.args[:2] == ('rapidocr', 'ar')
    else:
        service.prepare.assert_not_called()
        service.client.retire_engine.assert_called_once_with('rapidocr')
