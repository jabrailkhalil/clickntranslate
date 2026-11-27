"""Diagnostics can be retried after a worker launch fails."""
import time
from unittest import mock

import pytest
from PyQt5 import QtCore
from PyQt5.QtTest import QTest

import diagnostic_job
from test_desktop_ux import app, window


@pytest.mark.parametrize('failure', ['construct', 'start'])
def test_failed_diagnostic_launch_reports_once_and_allows_retry(app, tmp_path, failure):
    parent = QtCore.QObject()
    job = diagnostic_job.DiagnosticJob(parent, output_dir=tmp_path)
    completed = []
    job.finished.connect(lambda path, error: completed.append((path, error)))

    class UnavailableThread:
        def __init__(self, **kwargs):
            if failure == 'construct':
                raise RuntimeError('temporary thread allocation failure')

        def start(self):
            raise RuntimeError('temporary thread launch failure')

    with mock.patch.object(diagnostic_job.threading, 'Thread', UnavailableThread):
        job.start()
    assert job.running is False
    assert len(completed) == 1
    assert completed[0][0] is None and 'temporary thread' in completed[0][1]

    expected = tmp_path / 'report.zip'
    with mock.patch('diagnostics.create_bug_report', return_value=expected) as create:
        job.start()
        deadline = time.monotonic() + 2
        while len(completed) < 2 and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(1)
        create.assert_called_once_with(output_dir=tmp_path)
    assert completed[1:] == [(expected, '')]
    assert job.running is False
    parent.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_report_button_recovers_after_launch_failure_and_can_be_clicked_again(window, app):
    window.show_settings()
    settings = window.settings_window
    with mock.patch.object(diagnostic_job.threading, 'Thread', side_effect=RuntimeError('no worker')):
        with mock.patch('main.QMessageBox.warning') as warning:
            first = window._create_bug_report(settings)
            assert window._diagnostic_job is None
            assert settings.create_bug_report_btn.isEnabled()
            second = window._create_bug_report(settings)
            assert second is not first
            assert window._diagnostic_job is None
            assert settings.create_bug_report_btn.isEnabled()
            assert warning.call_count == 2
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
