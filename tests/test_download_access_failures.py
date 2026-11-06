"""Download-access failures must leave an operable check button and permit retry."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore

import download_access
from engine_center import text
from test_desktop_ux import app


@contextmanager
def controlled_check(stage):
    def thread(*, target, **_kwargs):
        if stage == 'outer-constructor':
            raise RuntimeError('synthetic outer thread allocation failure')
        def start():
            if stage == 'outer-start':
                raise RuntimeError('synthetic outer thread start failure')
            target()
            if stage == 'late-outer-start':
                raise RuntimeError('synthetic launch error after completion')
        return SimpleNamespace(start=start)

    class Executor:
        def __init__(self, **_kwargs):
            if stage == 'executor-constructor':
                raise RuntimeError('synthetic executor allocation failure')
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            pass
        def submit(self, function, url):
            if stage == 'submit' or stage == 'one-submit' and url == download_access.sources()[0][1]:
                raise RuntimeError('synthetic executor thread start failure')
            def result():
                if stage == 'future' or stage == 'one-future' and url == download_access.sources()[0][1]:
                    raise RuntimeError('synthetic transport future failure')
                return function(url)
            return SimpleNamespace(result=result)

    def probe(url):
        return {'status': 'unchecked' if url is None else 'ok',
                'code': None if url is None else 200, 'ms': 1, 'host': ''}

    with mock.patch.object(download_access.threading, 'Thread', thread), \
            mock.patch.object(download_access, 'ThreadPoolExecutor', Executor), \
            mock.patch.object(download_access, 'probe', side_effect=probe):
        yield


@pytest.mark.parametrize('stage', [
    'outer-constructor', 'outer-start', 'executor-constructor', 'submit', 'future', 'healthy',
])
def test_check_releases_busy_once_after_failure_and_can_retry(app, stage):
    page = download_access.DownloadAccessPage('en')
    completed = []
    page.completed.connect(completed.append)
    try:
        with controlled_check(stage):
            page.start()
        assert page._busy is False
        assert page.check.isEnabled()
        assert len(completed) == 1
        for key in ('catalog', 'api'):
            expected = 'ok' if stage == 'healthy' else 'failed'
            assert completed[0][key]['status'] == expected
            assert text('en', expected) in page.rows[key][0].text()
        assert completed[0]['files']['status'] == 'unchecked'
        assert text('en', 'unchecked') in page.rows['files'][0].text()
        assert all('synthetic' not in label.text() for label, _address in page.rows.values())
        with controlled_check('healthy'):
            page.check.click()
        assert page._busy is False and page.check.isEnabled()
        assert len(completed) == 2
        assert completed[1]['catalog']['status'] == completed[1]['api']['status'] == 'ok'
    finally:
        page.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('stage', ['one-submit', 'one-future'])
def test_a_failed_source_keeps_other_successful_source_results(app, stage):
    page = download_access.DownloadAccessPage('en')
    completed = []
    page.completed.connect(completed.append)
    try:
        with controlled_check(stage):
            page.start()
        assert page._busy is False and page.check.isEnabled()
        assert len(completed) == 1
        assert completed[0]['catalog']['status'] == 'failed'
        assert completed[0]['api']['status'] == 'ok'
        assert completed[0]['files']['status'] == 'unchecked'
    finally:
        page.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_a_late_launch_error_cannot_deliver_a_second_terminal_result(app):
    page = download_access.DownloadAccessPage('en')
    completed = []
    page.completed.connect(completed.append)
    try:
        with controlled_check('late-outer-start'):
            page.start()
        assert len(completed) == 1 and completed[0]['catalog']['status'] == 'ok'
        assert page._busy is False and page.check.isEnabled()
    finally:
        page.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('stage', ['healthy', 'future'])
def test_a_disposed_page_ignores_late_worker_completion(app, stage):
    from PyQt5 import sip
    page = download_access.DownloadAccessPage('en')
    completed, pending = [], []
    page.completed.connect(completed.append)
    with controlled_check(stage):
        def deferred_thread(*, target, **_kwargs):
            return SimpleNamespace(start=lambda: pending.append(target))
        with mock.patch.object(download_access.threading, 'Thread', deferred_thread):
            page.start()
        assert page._busy and len(pending) == 1
        page.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        assert sip.isdeleted(page)
        pending[0]()
    assert completed == []
