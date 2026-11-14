"""Selection probes must not block the UI or apply an obsolete selection."""
import ctypes
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets, sip
from PyQt5.QtTest import QTest

import mode_coordinator
import platform_support
import selection_platform
import selection_quick_translate as quick


def wait_probe(controller):
    deadline = time.monotonic() + 3
    while controller._inflight is not None:
        QtWidgets.QApplication.processEvents()
        assert time.monotonic() < deadline, 'Probe did not finish'
        QTest.qWait(1)


@pytest.fixture
def controller():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    owner = QtCore.QObject()
    with (mock.patch.multiple(platform_support, IS_WINDOWS=False, IS_MAC=False, IS_LINUX=True),
          mock.patch.object(quick, 'is_foreign_foreground', return_value=True),
          mock.patch.object(quick, 'foreground_token', return_value=42),
          mock.patch.object(mode_coordinator, 'active_mode', return_value=None)):
        value = quick.SelectionQuickTranslateController(owner)
        value.configure(True, 'button')
        value._stop_monitor()
        try:
            yield value
        finally:
            value.dispose()
            assert QtCore.QThreadPool.globalInstance().waitForDone(3000)
            app.processEvents()
            owner.deleteLater()


@pytest.mark.parametrize('previous', ['', 'Clipboard before probing'])
@pytest.mark.parametrize('failure', [None, 'copy', 'read'])
def test_clipboard_restored_on_success_and_exception(previous, failure):
    state = [previous]
    reads = [0]
    keys = []

    def paste():
        reads[0] += 1
        if failure == 'read' and reads[0] > 1:
            raise RuntimeError('Clipboard temporarily busy')
        return state[0]

    def copy(text):
        state[0] = text
        return True

    def key(vk, scan, flags, extra):
        keys.append((vk, flags))
        if vk == 0x43 and flags == 0:
            if failure == 'copy':
                raise RuntimeError('Copy failed')
            state[0] = 'Selected text'

    with (mock.patch.multiple(platform_support, IS_WINDOWS=True, IS_MAC=False, IS_LINUX=False),
          mock.patch.object(ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(keybd_event=key)), create=True),
          mock.patch.object(platform_support, 'copy_text', side_effect=copy),
          mock.patch('pyperclip.paste', side_effect=paste), mock.patch('time.sleep')):
        text = selection_platform._read_selection_via_copy()
    assert text == ('Selected text' if failure is None else '')
    # Without native sequence identity an unreadable clipboard cannot safely
    # be overwritten: it may already contain a newer user copy. The dedicated
    # preservation tests also cover restoration through native identity.
    assert state[0] == ('Selected text' if failure == 'read' else previous)
    assert keys[-2:] == [(0x43, 2), (0x11, 2)]


def test_lost_foreground_aborts_before_changing_clipboard():
    with (mock.patch('pyperclip.paste', return_value='Clipboard'),
          mock.patch.object(platform_support, 'copy_text') as copy):
        assert selection_platform._read_selection_via_copy(validate_target=lambda: False) == ''
    copy.assert_not_called()


@pytest.mark.parametrize('replace', [False, True])
def test_failed_selection_clipboard_clear_never_translates_previous_contents(replace):
    import main
    from test_translation_result_ui import _SelectionHarness, _immediate_thread
    harness = _SelectionHarness({})
    user32 = SimpleNamespace(keybd_event=mock.Mock())
    with (mock.patch.multiple(platform_support, IS_WINDOWS=True, IS_MAC=False, IS_LINUX=False),
          mock.patch.object(main.ctypes, 'windll', SimpleNamespace(user32=user32), create=True),
          mock.patch.object(main.threading, 'Thread', _immediate_thread),
          mock.patch.object(main.time, 'sleep'),
          mock.patch.object(main, '_windows_foreground_window', return_value=42),
          mock.patch.object(main.pyperclip, 'paste', return_value='Unrelated previous clipboard'),
          mock.patch.object(platform_support, 'copy_text', return_value=False) as clear,
          mock.patch.object(main, 'simulate_copy') as copy,
          mock.patch('translater.translate_text') as translate,
          mock.patch.object(main, 'notify_copy_failed') as notify,
          mock.patch.object(main, 'save_translation_history') as history):
        harness._launch_translate_selection(replace_selection=replace)
    clear.assert_called_once_with('')
    copy.assert_not_called()
    translate.assert_not_called()
    history.assert_not_called()
    notify.assert_called_once_with(harness.config)
    assert not harness.shown_dialogs


def test_selection_clear_hides_button_and_discards_pending_text(controller):
    results = []
    controller.translate_requested.connect(results.append)
    with mock.patch.object(quick, 'read_selected_text', side_effect=['First selection', '']):
        controller._complete_probe()
        wait_probe(controller)
        assert controller._button.isVisible()
        controller._complete_probe()
        wait_probe(controller)
    assert sip.isdeleted(controller._button) or not controller._button.isVisible()
    assert controller._pending_text == ''
    controller._on_button_clicked()
    assert results == []


@pytest.mark.parametrize('current', ['', 'Different selection', 'First selection'])
def test_button_rechecks_selection_before_translating(controller, current):
    results = []
    controller.translate_requested.connect(results.append)
    with mock.patch.object(quick, 'read_selected_text', side_effect=['First selection', current]):
        controller._complete_probe()
        wait_probe(controller)
        controller._on_button_clicked()
        wait_probe(controller)
    assert results == (['First selection'] if current == 'First selection' else [])


def test_slow_probe_keeps_gui_responsive_and_coalesces_repeated_requests(controller):
    entered, release = threading.Event(), threading.Event()
    worker_threads, ticks, results = [], [], []
    controller.configure(True, 'automatic')
    controller._stop_monitor()
    controller.translate_requested.connect(results.append)

    def read(**kwargs):
        worker_threads.append(threading.get_ident())
        entered.set()
        assert release.wait(2)
        return 'Hello there'

    with mock.patch.object(quick, 'read_selected_text', side_effect=read):
        try:
            controller._complete_probe()
            assert entered.wait(1)
            QtCore.QTimer.singleShot(0, lambda: ticks.append('GUI still running'))
            QtWidgets.QApplication.processEvents()
            assert ticks == ['GUI still running']
            for _ in range(25):
                controller._complete_probe()
            release.set()
            wait_probe(controller)
        finally:
            release.set()
            wait_probe(controller)
    assert len(worker_threads) == 2
    assert all(thread != threading.get_ident() for thread in worker_threads)
    assert results == ['Hello there']


@pytest.mark.parametrize('change', ['disabled', 'disposed', 'foreground', 'mode', 'new_selection'])
def test_late_worker_result_cannot_translate_after_context_changes(controller, change):
    entered, release = threading.Event(), threading.Event()
    results = []
    controller.configure(True, 'automatic')
    controller._stop_monitor()
    controller.translate_requested.connect(results.append)

    def read(**kwargs):
        entered.set()
        assert release.wait(2)
        return 'Obsolete selection'

    with mock.patch.object(quick, 'read_selected_text', side_effect=read):
        try:
            controller._complete_probe()
            assert entered.wait(1)
            if change == 'disabled':
                controller.configure(False, 'automatic')
            elif change == 'disposed':
                controller.dispose()
                controller.dispose()
            elif change == 'foreground':
                quick.foreground_token.return_value = 99
            elif change == 'mode':
                mode_coordinator.active_mode.return_value = 'ocr'
                controller._on_mode_changed()
            else:
                controller._schedule_probe()
            release.set()
            wait_probe(controller)
        finally:
            release.set()
            wait_probe(controller)
    assert results == []
    assert sip.isdeleted(controller._button) or not controller._button.isVisible()
