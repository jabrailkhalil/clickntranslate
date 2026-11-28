"""Companion selection capture is tied to its source; all native I/O is fake."""
from types import SimpleNamespace
from unittest import mock
import sys

import pytest

import assistant_text
import clipboard_preservation
import main
from main import simulate_copy as native_copy_action
import macos_desktop
import platform_support
import translater
from test_selection_clipboard_preservation import FakeClipboard
from test_translation_result_ui import _SelectionHarness, _immediate_thread
from selection_test_support import editable_editor


class SelectionRequest(_SelectionHarness):
    def __init__(self, **config):
        super().__init__({'copy_translated_text': False,
                          'restore_clipboard_after_selection': True, **config})
        self.finished = []
        self._selection_finished_signal = SimpleNamespace(emit=self.finished.append)


@pytest.fixture
def capture(monkeypatch, editable_editor):
    clipboard = FakeClipboard()
    state = SimpleNamespace(clipboard=clipboard, foreground=42)
    state.read = mock.Mock(side_effect=clipboard.paste)
    state.copy = mock.Mock(side_effect=clipboard.copy)
    state.foreground_read = mock.Mock(side_effect=lambda: state.foreground)
    state.copy_shortcut = mock.Mock(side_effect=lambda: clipboard.copy('Source selection'))
    state.provider = mock.Mock(return_value='Translated selection')
    state.thread = mock.Mock(side_effect=_immediate_thread)
    state.keys = mock.Mock()
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(platform_support, 'IS_MAC', False)
    monkeypatch.setattr(platform_support, 'IS_LINUX', False)
    monkeypatch.setattr(main.ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(
        keybd_event=state.keys)), raising=False)
    monkeypatch.setattr(platform_support, 'copy_text', state.copy)
    monkeypatch.setattr(main.pyperclip, 'paste', state.read)
    monkeypatch.setattr(main, '_windows_foreground_window', state.foreground_read)
    monkeypatch.setattr(main, '_clipboard_sequence_number', lambda: clipboard.sequence)
    monkeypatch.setattr(clipboard_preservation, 'clipboard_sequence_number', lambda: clipboard.sequence)
    monkeypatch.setattr(main, 'simulate_copy', state.copy_shortcut)
    monkeypatch.setattr(main.threading, 'Thread', state.thread)
    monkeypatch.setattr(main.time, 'sleep', lambda _: None)
    monkeypatch.setattr(main, 'save_translation_history', mock.Mock())
    monkeypatch.setattr(main, 'save_copy_history', mock.Mock())
    monkeypatch.setattr(main, 'notify_copy_failed', mock.Mock())
    monkeypatch.setattr(translater, 'translate_text', state.provider)
    monkeypatch.setattr(assistant_text, 'assistant_text', lambda language, key: f'{language}:{key}')
    return state


def assert_focus_rejected(owner, capture):
    capture.provider.assert_not_called()
    assert owner.finished == [False]
    assert not owner.shown_dialogs
    assert 'en:selection_focus_lost' in owner.statuses


def test_existing_wrong_target_is_rejected_before_any_clipboard_change(capture):
    owner = SelectionRequest()
    capture.foreground = 99
    assert owner.launch_translate_selection(expected_target=42) is True
    assert_focus_rejected(owner, capture)
    capture.read.assert_not_called()
    capture.copy.assert_not_called()
    capture.copy_shortcut.assert_not_called()
    capture.keys.assert_not_called()
    assert capture.clipboard.text == 'Clipboard before selection'


def test_focus_is_rechecked_after_releasing_modifiers(capture, monkeypatch):
    owner = SelectionRequest()

    def sleep(seconds):
        if seconds == .35:
            capture.foreground = 99

    monkeypatch.setattr(main.time, 'sleep', sleep)
    owner.launch_translate_selection(expected_target=42)
    assert_focus_rejected(owner, capture)
    capture.copy.assert_not_called()
    capture.copy_shortcut.assert_not_called()


def test_focus_change_while_clearing_clipboard_does_not_send_copy_to_another_app(capture):
    owner = SelectionRequest()

    def copy(text):
        result = capture.clipboard.copy(text)
        if text == '':
            capture.foreground = 99
        return result

    capture.copy.side_effect = copy
    owner.launch_translate_selection(expected_target=42)
    assert_focus_rejected(owner, capture)
    capture.copy_shortcut.assert_not_called()
    assert capture.clipboard.text == 'Clipboard before selection'


@pytest.mark.parametrize('when', ('copy_shortcut', 'copy_publication', 'clipboard_read'))
def test_lost_focus_after_copy_never_translates_another_window(capture, monkeypatch, when):
    owner = SelectionRequest()

    if when == 'copy_shortcut':
        def copy_shortcut():
            capture.clipboard.copy('Source selection')
            capture.foreground = 99
        capture.copy_shortcut.side_effect = copy_shortcut
    elif when == 'copy_publication':
        def sleep(seconds):
            if seconds == .25:
                capture.foreground = 99
        monkeypatch.setattr(main.time, 'sleep', sleep)
    else:
        def read():
            if capture.clipboard.text == 'Source selection':
                capture.foreground = 99
            return capture.clipboard.paste()
        capture.read.side_effect = read

    owner.launch_translate_selection(expected_target=42)
    assert_focus_rejected(owner, capture)
    capture.copy_shortcut.assert_called_once_with()


def test_retry_checks_the_target_before_reading_again(capture, monkeypatch):
    owner = SelectionRequest()
    capture.copy_shortcut.side_effect = lambda: capture.clipboard.copy('')

    def sleep(seconds):
        if seconds == .3:
            capture.foreground = 99

    monkeypatch.setattr(main.time, 'sleep', sleep)
    owner.launch_translate_selection(expected_target=42)
    assert_focus_rejected(owner, capture)
    # The initial snapshot and first empty copy are the only reads.
    assert capture.read.call_count == 2
    assert capture.clipboard.text == 'Clipboard before selection'


def test_success_reports_completion_and_preserves_normal_result_behavior(capture):
    owner = SelectionRequest()
    assert owner.launch_translate_selection(expected_target=42) is True
    capture.copy_shortcut.assert_called_once_with()
    capture.provider.assert_called_once_with('Source selection', 'es', 'en')
    assert owner.finished == [True]
    assert len(owner.shown_dialogs) == 1
    assert owner.shown_dialogs[0][0] == 'Translated selection'
    assert capture.clipboard.text == 'Clipboard before selection'


@pytest.mark.parametrize('result', ('', None, '   '))
def test_empty_provider_result_reports_failure_once(capture, result):
    owner = SelectionRequest()
    capture.provider.return_value = result
    owner.launch_translate_selection(expected_target=42)
    assert owner.finished == [False]
    assert not owner.shown_dialogs
    assert capture.clipboard.text == 'Clipboard before selection'


def test_provider_error_reports_failure_once(capture):
    owner = SelectionRequest()
    capture.provider.side_effect = RuntimeError('Fake provider failure')
    owner.launch_translate_selection(expected_target=42)
    assert owner.finished == [False]
    assert not owner.shown_dialogs
    assert capture.clipboard.text == 'Clipboard before selection'


def test_no_selected_text_reports_failure_once(capture):
    owner = SelectionRequest()
    capture.copy_shortcut.side_effect = lambda: capture.clipboard.copy('')
    owner.launch_translate_selection(expected_target=42)
    capture.provider.assert_not_called()
    assert 'en:selection_empty' in owner.statuses
    assert owner.finished == [False]
    assert capture.clipboard.text == 'Clipboard before selection'


def test_busy_clipboard_reports_completion_without_sending_ctrl_c(capture):
    owner = SelectionRequest()
    capture.copy.return_value = False
    capture.copy.side_effect = None
    owner.launch_translate_selection(expected_target=42)
    capture.copy_shortcut.assert_not_called()
    capture.provider.assert_not_called()
    main.notify_copy_failed.assert_called_once_with(owner.config)
    assert owner.finished == [False]
    assert capture.clipboard.text == 'Clipboard before selection'


def test_hotkey_pins_its_source_window_without_panel_completion(capture):
    owner = SelectionRequest()
    assert owner.launch_translate_selection() is True
    assert capture.foreground_read.call_count >= 2
    capture.copy_shortcut.assert_called_once_with()
    assert len(owner.shown_dialogs) == 1
    assert owner.finished == []


def test_hotkey_without_selected_text_keeps_its_existing_localized_message(capture):
    owner = SelectionRequest()
    capture.copy_shortcut.side_effect = lambda: capture.clipboard.copy('')
    owner.launch_translate_selection()
    assert main.ui_text('en', 'no_text_selected') in owner.statuses
    assert 'en:selection_empty' not in owner.statuses
    assert owner.finished == []


def test_explicit_missing_windows_target_never_synthesizes_a_key(capture):
    owner = SelectionRequest()
    capture.foreground = 0
    owner.launch_translate_selection(expected_target=0)
    assert_focus_rejected(owner, capture)
    capture.keys.assert_not_called()
    capture.copy_shortcut.assert_not_called()


def test_replacement_uses_the_explicit_source_instead_of_a_later_focus_snapshot(capture, monkeypatch):
    owner = SelectionRequest()
    replace = mock.Mock(return_value=(True, 'replaced'))
    monkeypatch.setattr(main, 'replace_selected_text_in_foreground', replace)
    assert owner.launch_translate_replace_selection(expected_target=42) is True
    assert replace.call_args.args == ('Source selection', 'Translated selection', 42)
    assert owner.finished == [True]
    assert not owner.shown_dialogs


def test_select_all_revalidates_focus_before_copying(capture, monkeypatch):
    owner = SelectionRequest(replace_selection_select_all=True)

    def select_all(_target, **_kwargs):
        capture.foreground = 99
        return True

    monkeypatch.setattr(main, 'select_all_text_in_foreground', select_all)
    owner.launch_translate_replace_selection(expected_target=42)
    assert_focus_rejected(owner, capture)
    capture.copy_shortcut.assert_not_called()
    capture.copy.assert_not_called()


def setup_fake_mac(capture, monkeypatch, *, permission=True):
    target = macos_desktop.ForegroundTarget(1234, 'Fake accessibility window', 'Source field')
    capture.foreground = target
    native = SimpleNamespace(
        ensure_permission=mock.Mock(return_value=permission),
        same_foreground_target=mock.Mock(side_effect=lambda expected, **_: capture.foreground == expected),
        foreground_target=mock.Mock(side_effect=lambda: capture.foreground))
    def send_shortcut(key, validate_target=None):
        if validate_target is not None and not validate_target():
            return False
        assert key == 'c'
        capture.copy_shortcut()
        return True
    native.send_edit_shortcut = mock.Mock(side_effect=send_shortcut)
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', False)
    monkeypatch.setattr(platform_support, 'IS_MAC', True)
    monkeypatch.setitem(sys.modules, 'macos_desktop', native)
    return target, native


def test_mac_target_checks_use_the_accessibility_window_identity(capture, monkeypatch):
    owner = SelectionRequest()
    target, native = setup_fake_mac(capture, monkeypatch)
    assert owner.launch_translate_selection(expected_target=target) is True
    capture.foreground_read.assert_not_called()
    assert native.same_foreground_target.call_count >= 4
    assert all(call.args == (target,) for call in native.same_foreground_target.call_args_list)
    assert owner.finished == [True]


def test_mac_focus_change_does_not_copy(capture, monkeypatch):
    owner = SelectionRequest()
    target, _native = setup_fake_mac(capture, monkeypatch)
    capture.foreground = (9999, 'Another application')
    owner.launch_translate_selection(expected_target=target)
    assert_focus_rejected(owner, capture)
    capture.copy_shortcut.assert_not_called()


@pytest.mark.parametrize('replace', [False, True])
def test_mac_hotkey_does_not_copy_from_the_window_activated_during_worker_start(capture, monkeypatch, replace):
    owner = SelectionRequest()
    _target, native = setup_fake_mac(capture, monkeypatch)
    def change_window(seconds):
        if seconds == .35:
            capture.foreground = (9999, 'Other window')
    monkeypatch.setattr(main.time, 'sleep', change_window)
    action = owner.launch_translate_replace_selection if replace else owner.launch_translate_selection
    assert action() is True
    native.foreground_target.assert_called_once_with()
    capture.copy_shortcut.assert_not_called()
    capture.copy.assert_not_called()
    capture.provider.assert_not_called()
    assert owner.finished == []  # A hotkey is independent of the companion panel.


@pytest.mark.parametrize('verification', [False, True])
def test_mac_copy_rechecks_the_source_after_waiting_for_held_modifiers(capture, monkeypatch, verification):
    owner = SelectionRequest()
    target, native = setup_fake_mac(capture, monkeypatch)
    monkeypatch.setattr(main, 'simulate_copy', native_copy_action)
    delivered = []
    def send_after_modifiers(key, validate_target=None):
        capture.foreground = (9999, 'Other window')
        if validate_target is not None and not validate_target():
            return False
        delivered.append((key, capture.foreground))
        return True
    native.send_edit_shortcut.side_effect = send_after_modifiers
    if verification:
        replaced, _reason = main.replace_selected_text_in_foreground('Source selection', 'Result', target)
        assert not replaced
    else:
        owner.launch_translate_selection(expected_target=target)
        assert capture.clipboard.text == 'Clipboard before selection'
    native.send_edit_shortcut.assert_called_once()
    assert delivered == []
    capture.provider.assert_not_called()


@pytest.fixture
def ax_fields(capture, monkeypatch):
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', False)
    monkeypatch.setattr(platform_support, 'IS_MAC', True)
    state = SimpleNamespace(focused='Field A', delivered=[])
    front = SimpleNamespace(processIdentifier=lambda: 1234)
    workspace = SimpleNamespace(frontmostApplication=lambda: front)
    appkit = SimpleNamespace(NSWorkspace=SimpleNamespace(sharedWorkspace=lambda: workspace))
    def attribute(_application, name, _out):
        if name == 'window':
            return 0, 'Source window'
        assert name == 'focused element'
        return (0, state.focused) if state.focused is not None else (-25205, None)
    accessibility = SimpleNamespace(AXUIElementCreateApplication=lambda pid: pid,
                                    AXUIElementCopyAttributeValue=attribute,
                                    kAXFocusedWindowAttribute='window', kAXFocusedUIElementAttribute='focused element')
    monkeypatch.setitem(sys.modules, 'AppKit', appkit)
    monkeypatch.setitem(sys.modules, 'ApplicationServices', accessibility)
    monkeypatch.setitem(sys.modules, 'CoreFoundation', SimpleNamespace(CFEqual=lambda a, b: a == b))
    monkeypatch.setattr(macos_desktop, 'ensure_permission', lambda *_: True)
    def send(key, validate_target=None):
        if validate_target is not None and not validate_target():
            return False
        state.delivered.append((key, state.focused))
        if key == 'c':
            # Both editors contain the same highlighted string.
            capture.copy_shortcut()
        return True
    monkeypatch.setattr(macos_desktop, 'send_edit_shortcut', send)
    return state


@pytest.mark.parametrize('new_focus', ['Field B', None])
@pytest.mark.parametrize('operation', ['select_all', 'replace'])
def test_mac_replacement_never_targets_a_different_control_with_identical_text(capture, ax_fields, new_focus, operation):
    original = macos_desktop.foreground_target()
    ax_fields.focused = new_focus
    if operation == 'select_all':
        assert not main.select_all_text_in_foreground(original)
    else:
        replaced, _ = main.replace_selected_text_in_foreground('Source selection', 'Translation', original)
        assert not replaced
    assert ax_fields.delivered == []
    capture.copy.assert_not_called()


def test_mac_window_only_accessibility_preserves_reading_but_refuses_replacement(capture, ax_fields):
    ax_fields.focused = None
    owner = SelectionRequest()
    owner.launch_translate_selection()
    assert ax_fields.delivered == [('c', None)]
    assert len(owner.shown_dialogs) == 1
    ax_fields.delivered.clear()
    capture.provider.reset_mock()
    owner.launch_translate_replace_selection()
    assert ax_fields.delivered == []
    capture.provider.assert_not_called()


def test_mac_replacement_still_verifies_selection_and_pastes_in_the_original_control(capture, ax_fields):
    original = macos_desktop.foreground_target()
    assert main.select_all_text_in_foreground(original)
    assert main.replace_selected_text_in_foreground('Source selection', 'Translation', original) == (True, 'replaced')
    assert ax_fields.delivered == [('a', 'Field A'), ('c', 'Field A'), ('v', 'Field A')]


def test_mac_permission_denial_returns_false_without_starting_a_worker(capture, monkeypatch):
    owner = SelectionRequest()
    target, _native = setup_fake_mac(capture, monkeypatch, permission=False)
    assert owner.launch_translate_selection(expected_target=target) is False
    capture.thread.assert_not_called()
    capture.provider.assert_not_called()
    assert owner.finished == []


def test_mac_identity_check_failure_fails_closed(capture, monkeypatch):
    owner = SelectionRequest()
    target, native = setup_fake_mac(capture, monkeypatch)
    native.same_foreground_target.side_effect = RuntimeError('Fake accessibility failure')
    owner.launch_translate_selection(expected_target=target)
    assert_focus_rejected(owner, capture)
    capture.copy_shortcut.assert_not_called()


def test_linux_primary_selection_with_zero_target_still_signals_completion(capture, monkeypatch):
    owner = SelectionRequest()
    owner._read_primary_selection = mock.Mock(return_value='Linux PRIMARY selection')
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', False)
    monkeypatch.setattr(platform_support, 'IS_LINUX', True)
    assert owner.launch_translate_selection(expected_target=0) is True
    capture.foreground_read.assert_not_called()
    capture.read.assert_not_called()
    capture.copy.assert_not_called()
    capture.copy_shortcut.assert_not_called()
    capture.provider.assert_called_once_with('Linux PRIMARY selection', 'es', 'en')
    assert owner.finished == [True]


def test_already_captured_text_needs_no_foreground_or_clipboard_access(capture):
    owner = SelectionRequest()
    capture.foreground = 99
    assert owner._launch_translate_selection(preloaded_text='Captured text', expected_target=42) is True
    capture.foreground_read.assert_not_called()
    capture.read.assert_not_called()
    capture.copy_shortcut.assert_not_called()
    capture.provider.assert_called_once_with('Captured text', 'es', 'en')
    assert owner.finished == [True]
