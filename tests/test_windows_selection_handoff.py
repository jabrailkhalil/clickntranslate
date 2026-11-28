"""Focus transitions and replacement boundaries with in-memory Windows providers."""
import ctypes
from types import SimpleNamespace
from threading import Event
from unittest import mock

import pytest

import main
import platform_support
import selection_quick_translate as quick
import windows_selection
from selection_test_support import editable_editor
from test_companion_selection_target import SelectionRequest, capture
from test_windows_uia_contract import NativeCall


@pytest.mark.parametrize('window', [None, 42])
def test_releasing_the_mouse_during_a_foreground_handoff_ignores_the_missing_owner(monkeypatch, window):
    api = SimpleNamespace(GetAsyncKeyState=lambda key: 0,
                          GetForegroundWindow=NativeCall(lambda: window),
                          GetWindowThreadProcessId=NativeCall(lambda *_args: 0))
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(ctypes, 'windll', SimpleNamespace(user32=api), raising=False)
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *_args, **_kwargs: api, raising=False)
    poller = quick._WindowsMouseReleasePoller()
    activity = []
    poller.activity.connect(lambda: activity.append(True))
    poller._left_down = True
    poller._poll()
    assert activity == [] and not poller._left_down


@pytest.mark.parametrize('second,paste_expected', [
    ('\tSource selection ', True), ('Source selection ', False), ('\tSource selection', False)])
def test_replacement_requires_the_exact_original_whitespace(capture, monkeypatch, second, paste_expected):
    reads = iter(('\tSource selection ', second))
    capture.copy_shortcut.side_effect = lambda: capture.clipboard.copy(next(reads))
    paste = mock.Mock()
    monkeypatch.setattr(main, 'simulate_paste', paste)
    owner = SelectionRequest()
    owner.launch_translate_replace_selection(expected_target=42)
    capture.provider.assert_called_once_with('Source selection', 'es', 'en')
    assert paste.called is paste_expected
    assert capture.clipboard.text == ('Clipboard before selection' if paste_expected else 'Translated selection')


@pytest.mark.parametrize('new_copy', ['A newer user copy', 'Translated selection'])
def test_a_new_clipboard_owner_during_final_focus_verification_keeps_their_copy(
        capture, editable_editor, monkeypatch, new_copy):
    original = editable_editor.return_value
    clipboard = capture.clipboard
    changed = []

    def check_editor(_window):
        if clipboard.text == 'Translated selection' and not changed:
            changed.append(clipboard.copy(new_copy))
        return original

    editable_editor.side_effect = check_editor
    delivered = []
    monkeypatch.setattr(main, 'simulate_paste', lambda: delivered.append(clipboard.paste()))
    owner = SelectionRequest()
    owner.launch_translate_replace_selection(expected_target=42)
    assert changed and delivered == []
    assert clipboard.text == new_copy
    assert len(owner.shown_dialogs) == 1 and owner.shown_dialogs[0][0] == 'Translated selection'


def test_disposing_a_companion_request_during_final_focus_verification_cancels_its_paste(
        capture, editable_editor, monkeypatch):
    owner = SelectionRequest()
    token = Event()
    for name in ('_companion_selection_status_signal', '_companion_selection_hide_status_signal',
                 '_companion_selection_result_signal', '_companion_selection_finished_signal'):
        setattr(owner, name, SimpleNamespace(emit=mock.Mock()))
    original = editable_editor.return_value

    def check_editor(_window):
        if capture.clipboard.text == 'Translated selection':
            token.set()
        return original

    editable_editor.side_effect = check_editor
    paste = mock.Mock()
    monkeypatch.setattr(main, 'simulate_paste', paste)
    owner.launch_translate_replace_selection(expected_target=42, _request_token=token)
    assert token.is_set()
    paste.assert_not_called()
    assert capture.clipboard.text == 'Clipboard before selection'
    assert owner.finished == [False]


@pytest.mark.parametrize('held_for,should_translate', [(0, True), (.12, True), (3, False)])
def test_copy_waits_for_the_actual_shortcut_modifiers_without_releasing_the_users_keys(
        capture, monkeypatch, held_for, should_translate):
    elapsed = [0.0]
    monkeypatch.setattr(main.time, 'monotonic', lambda: elapsed[0])
    monkeypatch.setattr(main.time, 'sleep', lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
    monkeypatch.setattr(windows_selection, '_modifiers_down', lambda: elapsed[0] < held_for, raising=False)
    delivered = []

    def copy():
        delivered.append(elapsed[0])
        return capture.clipboard.copy('Source selection')

    capture.copy_shortcut.side_effect = copy
    owner = SelectionRequest()
    owner.launch_translate_selection(expected_target=42)
    capture.keys.assert_not_called()
    assert bool(delivered) is should_translate
    if should_translate:
        assert delivered[0] >= held_for
    else:
        capture.copy.assert_not_called()
        capture.provider.assert_not_called()
        assert owner.finished == [False]


@pytest.mark.parametrize('when', ['copy_dispatch', 'clipboard_read', 'delayed_publication'])
def test_replacement_does_not_translate_another_field_which_published_its_clipboard_response(
        capture, editable_editor, monkeypatch, when):
    first = editable_editor.return_value
    second = windows_selection.WindowsEditTarget(first.window, first.process_id, (42, 9))
    editor = [first]
    editable_editor.side_effect = lambda _window: editor[0]

    def move():
        editor[0] = second
        capture.clipboard.copy('Different field in the same window')

    def copy():
        if when == 'copy_dispatch':
            move()

    def read():
        if when == 'clipboard_read' and capture.clipboard.text == '':
            move()
        return capture.clipboard.paste()

    def sleep(seconds):
        if when == 'delayed_publication' and seconds == .3:
            move()

    capture.copy_shortcut.side_effect = copy
    capture.read.side_effect = read
    monkeypatch.setattr(main.time, 'sleep', sleep)
    monkeypatch.setattr(main, 'simulate_paste', mock.Mock())
    owner = SelectionRequest()
    owner.launch_translate_replace_selection(expected_target=42)
    assert editor[0] is second
    capture.provider.assert_not_called()
    main.simulate_paste.assert_not_called()
    assert owner.finished == [False]
