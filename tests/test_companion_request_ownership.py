"""Companion callbacks belong to the request which started their worker."""
from types import MethodType, SimpleNamespace
from threading import Event, Thread
from unittest import mock

import pytest
from PyQt5 import QtCore

import main
import translater
from desktop_assistant import DesktopAssistant
import test_companion_persistent_panel as persistent


class RequestOwner(persistent.FakeOwner):
    _hide_status_signal = QtCore.pyqtSignal()
    _show_selection_signal = QtCore.pyqtSignal(str, bool, str, str, str, str, str)
    _companion_selection_status_signal = QtCore.pyqtSignal(object, str)
    _companion_selection_finished_signal = QtCore.pyqtSignal(object, bool)
    _companion_selection_hide_status_signal = QtCore.pyqtSignal(object)
    _companion_selection_result_signal = QtCore.pyqtSignal(object, object)

    def _launch_translate_selection(self, **kwargs):
        return main.DarkThemeApp._launch_translate_selection(
            self, preloaded_text=self.next_source, **kwargs)

    def _selected_text_translation_pair(self):
        return 'en', 'ru'

    def _replace_selected_text_translation_pair(self):
        return 'en', 'ru'


@pytest.fixture
def requests(monkeypatch, request):
    # The existing palette fixture replaces native foreground calls before
    # constructing the helper. The selection text below is already supplied;
    # no clipboard, key injection, OS worker, or SDK is ever invoked.
    monkeypatch.setattr(persistent, 'FakeOwner', RequestOwner)
    jobs = []

    class DeferredThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            jobs.append(self)

        def run(self):
            self.target()

    monkeypatch.setattr(main.threading, 'Thread', DeferredThread)
    monkeypatch.setattr(main.time, 'sleep', lambda _seconds: None)
    provider = mock.Mock(side_effect=lambda text, *_args, **_kwargs: 'Translated ' + text)
    monkeypatch.setattr(translater, 'translate_text', provider)
    monkeypatch.setattr(main, 'save_translation_history', mock.Mock())
    monkeypatch.setattr(main, 'save_copy_history', mock.Mock())
    monkeypatch.setattr(main, 'copy_result_text', mock.Mock(return_value=True))
    monkeypatch.setattr(main, 'replace_selected_text_in_foreground', mock.Mock(return_value=(True, 'replaced')))
    value = request.getfixturevalue('palette')
    owner = value.owner
    owner.config.update(interface_language='en', theme='Темная', copy_translated_text=False)
    owner.next_source = 'First source'
    owner.launch_translate_selection = MethodType(main.DarkThemeApp.launch_translate_selection, owner)
    owner.launch_translate_replace_selection = MethodType(main.DarkThemeApp.launch_translate_replace_selection, owner)
    owner.results, owner.statuses, owner.hidden = [], [], []
    owner._show_selection_signal.connect(lambda *args: owner.results.append(args))
    owner._show_status_signal.connect(owner.statuses.append)
    owner._hide_status_signal.connect(lambda: owner.hidden.append(True))
    for signal_name, method_name in (
            ('_companion_selection_status_signal', '_show_companion_selection_status'),
            ('_companion_selection_hide_status_signal', '_hide_companion_selection_status'),
            ('_companion_selection_result_signal', '_show_companion_selection_result')):
        method = getattr(main.DarkThemeApp, method_name, None)
        if method is not None:
            getattr(owner, signal_name).connect(lambda *args, method=method: method(owner, *args))
    value.jobs, value.provider = jobs, provider
    return value


@pytest.fixture
def palette(monkeypatch):
    # Expose the existing safe fixture for request.getfixturevalue above.
    yield from persistent.palette.__wrapped__(monkeypatch)


@pytest.mark.parametrize('next_action', ['selection', 'replace'])
def test_retired_companion_request_cannot_complete_or_notify_its_replacement(requests, next_action):
    value = requests
    owner, old = value.owner, value.helper
    old.request_action('selection')
    persistent.dispatch_now(old)
    assert old._selection_pending and len(value.jobs) == 1
    old_token = getattr(old, '_selection_request_token', None)
    old.dispose()
    value.app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    current = DesktopAssistant(owner)
    try:
        current.toggle_menu()
        value.native.current = 202
        owner.next_source = 'Second source'
        current.request_action(next_action)
        persistent.dispatch_now(current)
        assert current._selection_pending and len(value.jobs) == 2
        message = current._selection_message
        owner._companion_selection_status_signal.emit(old_token, 'Old request failed')
        owner._companion_selection_finished_signal.emit(old_token, False)
        owner._selection_finished_signal.emit(False)  # Unowned legacy callback.
        assert current._selection_pending and current._dispatching
        assert current._selection_message == message
        value.jobs[0].run()
        assert not value.provider.called and not owner.results and not owner.statuses
        assert current._selection_pending and current._dispatching
        value.jobs[1].run()
        assert value.provider.call_count == 1
        assert value.provider.call_args.args == ('Second source', 'en', 'ru')
        assert not current._selection_pending and not current._dispatching
        assert current.menu.buttons['selection'].isEnabled()
        if next_action == 'selection':
            assert len(owner.results) == 1 and owner.results[0][0] == 'Translated Second source'
        else:
            assert owner.results == []
    finally:
        current.dispose()


@pytest.mark.parametrize('replace', [False, True])
def test_no_token_selection_callers_keep_the_legacy_result_and_completion_contract(requests, replace):
    owner = requests.owner
    finished, tagged = [], []
    owner._selection_finished_signal.connect(finished.append)
    owner._companion_selection_finished_signal.connect(lambda *args: tagged.append(args))
    method = owner.launch_translate_replace_selection if replace else owner.launch_translate_selection
    assert method(expected_target=101) is True
    requests.jobs[-1].run()
    assert requests.provider.call_args.args == ('First source', 'en', 'ru')
    assert requests.provider.call_args.kwargs == {}
    assert finished == [True] and tagged == []
    if not replace:
        assert owner.results[0][0] == 'Translated First source'


def test_dispose_during_provider_work_discards_the_returned_result_and_all_late_status(requests):
    owner, helper = requests.owner, requests.helper
    helper.request_action('selection')
    persistent.dispatch_now(helper)

    def complete_after_disposal(*_args, **_kwargs):
        helper.dispose()
        owner.statuses.clear()
        owner.hidden.clear()
        return 'Late completed source'

    requests.provider.side_effect = complete_after_disposal
    requests.jobs[-1].run()
    assert owner.results == []
    assert owner.statuses == [] and owner.hidden == []
    main.copy_result_text.assert_not_called()
    main.save_translation_history.assert_not_called()


def test_queued_result_and_status_are_rechecked_when_the_gui_delivers_them(requests):
    owner, helper = requests.owner, requests.helper
    helper.request_action('selection')
    persistent.dispatch_now(helper)
    # The backend is fake, but the thread and Qt queued delivery are real.
    # Do not pump the GUI until the worker has posted all its callbacks.
    worker = Thread(target=requests.jobs[-1].run)
    worker.start()
    worker.join(3)
    assert not worker.is_alive()
    assert owner.statuses == [] and owner.results == [] and owner.hidden == []
    helper.dispose()
    for _ in range(4):
        requests.app.processEvents()
    assert owner.statuses == [] and owner.results == [] and owner.hidden == []


def test_native_owner_disposal_cannot_leave_worker_emitting_into_a_deleted_qobject(monkeypatch):
    jobs = []
    monkeypatch.setattr(main.threading, 'Thread',
                        lambda *, target, **_kwargs: SimpleNamespace(start=lambda: jobs.append(target)))
    provider = mock.Mock(return_value='A late result')
    monkeypatch.setattr(translater, 'translate_text', provider)
    monkeypatch.setattr(main, 'save_translation_history', mock.Mock())
    owner = RequestOwner()
    owner.config = {'interface_language': 'en'}
    token = Event()
    assert main.DarkThemeApp._launch_translate_selection(
        owner, preloaded_text='Preloaded selection', expected_target=101, _request_token=token)
    from PyQt5 import sip
    sip.delete(owner)
    jobs[-1]()
    provider.assert_not_called()
    main.save_translation_history.assert_not_called()
