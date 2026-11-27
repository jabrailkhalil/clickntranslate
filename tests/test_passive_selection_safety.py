"""No real UIA, keystrokes, clipboard access, providers or visible windows."""
from types import SimpleNamespace
from unittest import mock

import pytest

import main
import platform_support
import selection_platform
import selection_quick_translate as quick
import windows_selection as selection
from selection_safety_text import EDIT_TARGET_UNAVAILABLE, PASSIVE_SELECTION_HELP
from test_windows_uia_contract import scenario
from selection_test_support import editable_editor
from test_companion_selection_target import capture, SelectionRequest


@pytest.mark.parametrize('mode,clicked', [('button', ''), ('button', 'Selected words'), ('automatic', '')])
@pytest.mark.parametrize('result', ['', 'Selected words'])
def test_passive_probe_never_uses_copy_fallback_or_changes_clipboard(monkeypatch, mode, clicked, result):
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(platform_support, 'IS_MAC', False)
    monkeypatch.setattr(platform_support, 'IS_LINUX', False)
    monkeypatch.setattr(quick, 'foreground_token', lambda: 42)
    monkeypatch.setattr(selection, 'read_windows_selected_text', lambda: result)
    fallback, clipboard = mock.Mock(side_effect=AssertionError('No background copy')), mock.Mock()
    monkeypatch.setattr(selection_platform, '_read_selection_via_copy', fallback)
    monkeypatch.setattr(platform_support, 'copy_text', clipboard)
    task = quick._SelectionProbe(dict(target=42, revision=0, clicked=clicked, mode=mode), None)
    outcomes = []
    task.signals.completed.connect(outcomes.append)
    task.run()
    assert outcomes[0]['text'] == result
    fallback.assert_not_called()
    clipboard.assert_not_called()


def test_explicit_read_can_still_use_copy_compatibility(monkeypatch):
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(platform_support, 'IS_MAC', False)
    monkeypatch.setattr(platform_support, 'IS_LINUX', False)
    monkeypatch.setattr(selection, 'read_windows_selected_text', lambda: '')
    fallback = mock.Mock(return_value='Explicitly copied cell')
    monkeypatch.setattr(selection_platform, '_read_selection_via_copy', fallback)
    assert selection_platform.read_selected_text(allow_copy_fallback=True) == 'Explicitly copied cell'
    fallback.assert_called_once()


@pytest.mark.parametrize('empty', ['caret', 'pattern', 'count', 'element'])
def test_uia_absence_does_not_invent_text_from_a_cell(scenario, empty):
    scenario.empty = empty
    assert selection.read_windows_selected_text() == ''
    assert scenario.events[-1][0] == 'uninit'
    assert not any(scenario.live.values())


@pytest.mark.parametrize('changed', ['password', 'focus'])
def test_password_or_changed_focus_is_not_a_selection(scenario, changed):
    if changed == 'password':
        scenario.password = True
    else:
        scenario.same_focus = False
    assert selection.read_windows_selected_text() == ''
    assert not any(scenario.live.values())


@pytest.mark.parametrize('value_pattern', [True, False])
@pytest.mark.parametrize('control_type', [50003, 50004, 50030])
def test_editable_target_contains_only_plain_identity_and_balances_com(scenario, monkeypatch, value_pattern, control_type):
    scenario.value_pattern = value_pattern
    scenario.control_type = control_type
    monkeypatch.setattr(selection, '_foreground_process', lambda expected: 77 if expected == 42 else 0)
    assert selection.read_windows_edit_target(42) == selection.WindowsEditTarget(42, 77, (42, 1, 8))
    assert scenario.events[-1] == ('uninit', __import__('threading').get_ident(), 0)
    assert not any(scenario.live.values())


@pytest.mark.parametrize('attribute,value', [
    ('password', True), ('enabled', False), ('focused', False), ('readonly', True),
    ('readonly', object()), ('same_focus', False), ('runtime_id', ()),
    ('process_id', 99), ('control_type', 50029),  # Selected Excel cell
    ('control_type', 50000), ('control_type', 50020),  # Button/static text
])
def test_non_editors_and_unknown_properties_fail_closed(scenario, monkeypatch, attribute, value):
    setattr(scenario, attribute, value)
    monkeypatch.setattr(selection, '_foreground_process', lambda expected: 77)
    assert selection.read_windows_edit_target(42) is None
    assert not any(scenario.live.values())


@pytest.mark.parametrize('failure', ['typelib', 'create', 'element', 'pattern', 'qi', 'identity', 'compare'])
def test_editor_provider_failure_releases_com_before_return(scenario, monkeypatch, failure):
    scenario.fail_at = failure
    monkeypatch.setattr(selection, '_foreground_process', lambda expected: 77)
    assert selection.read_windows_edit_target(42) is None
    assert scenario.events[-1][0] == 'uninit'
    assert not any(scenario.live.values())


def test_editor_focus_change_during_uia_read_is_rejected(scenario, monkeypatch):
    check = mock.Mock(side_effect=[77, 0])
    monkeypatch.setattr(selection, '_foreground_process', check)
    assert selection.read_windows_edit_target(42) is None
    assert not any(scenario.live.values())


def test_generic_browser_document_is_not_assumed_to_be_an_input(scenario, monkeypatch):
    scenario.control_type, scenario.text_edit_pattern = 50030, False
    monkeypatch.setattr(selection, '_foreground_process', lambda expected: 77)
    assert selection.read_windows_edit_target(42) is None
    assert not any(scenario.live.values())


def test_replacement_feedback_covers_every_interface_language():
    assert set(EDIT_TARGET_UNAVAILABLE) == {entry['code'] for entry in main.INTERFACE_LANGUAGE_OPTIONS}
    assert all(text.strip() for text in EDIT_TARGET_UNAVAILABLE.values())
    assert set(PASSIVE_SELECTION_HELP) == set(EDIT_TARGET_UNAVAILABLE)


@pytest.mark.parametrize('locale', list(PASSIVE_SELECTION_HELP))
def test_selection_tooltip_explains_the_no_shortcut_detection(locale, monkeypatch):
    from PyQt5 import QtWidgets, QtGui
    from selection_options import SelectionTriggerControl
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', True)
    owner = SimpleNamespace(current_interface_language=locale, config={})
    control = SelectionTriggerControl(owner)
    document = QtGui.QTextDocument()
    document.setHtml(control.toolTip())
    assert PASSIVE_SELECTION_HELP[locale] in document.toPlainText()
    control.deleteLater()
    app.processEvents()


def test_null_com_value_pattern_can_use_a_confirmed_text_editor(scenario, monkeypatch):
    from test_windows_uia_contract import Element
    original = Element.GetCurrentPattern
    class NullInterface:
        def __bool__(self):
            return False
        def QueryInterface(self, _interface):
            raise AssertionError('A null COM interface must not be dereferenced')
    monkeypatch.setattr(Element, 'GetCurrentPattern', lambda element, pattern: (
        NullInterface() if pattern == 10002 else original(element, pattern)))
    monkeypatch.setattr(selection, '_foreground_process', lambda expected: 77)
    assert selection.read_windows_edit_target(42) is not None
    assert not any(scenario.live.values())


@pytest.mark.parametrize('hresult,allowed', [(0x80040204, True), (0x80070005, False)])
def test_only_unsupported_value_pattern_allows_a_text_pattern_fallback(scenario, monkeypatch, hresult, allowed):
    from test_windows_uia_contract import Element
    original = Element.GetCurrentPattern
    class ProviderError(Exception):
        pass
    def pattern(element, pattern_id):
        if pattern_id == 10002:
            error = ProviderError('Synthetic provider response')
            error.hresult = hresult
            raise error
        return original(element, pattern_id)
    monkeypatch.setattr(Element, 'GetCurrentPattern', pattern)
    monkeypatch.setattr(selection, '_foreground_process', lambda expected: 77)
    assert (selection.read_windows_edit_target(42) is not None) is allowed
    assert not any(scenario.live.values())


@pytest.mark.parametrize('select_all', [False, True])
def test_replacement_in_terminal_or_unverified_control_sends_no_keys_or_clipboard_writes(
        capture, monkeypatch, select_all):
    monkeypatch.setattr(main, '_windows_edit_target', lambda expected: None)
    owner = SelectionRequest(replace_selection_select_all=select_all)
    owner.launch_translate_replace_selection(expected_target=42)
    capture.keys.assert_not_called()
    capture.copy_shortcut.assert_not_called()
    capture.copy.assert_not_called()
    capture.provider.assert_not_called()
    assert EDIT_TARGET_UNAVAILABLE['en'] in owner.statuses
    assert owner.finished == [False]


@pytest.mark.parametrize('when', ['before_copy', 'during_translation', 'before_paste'])
def test_changing_editors_in_the_same_window_never_receives_a_paste(capture, monkeypatch, when):
    first = selection.WindowsEditTarget(42, 77, (42, 1, 8))
    second = selection.WindowsEditTarget(42, 77, (42, 1, 9))
    current = [first]
    monkeypatch.setattr(main, '_windows_edit_target', lambda expected: current[0])
    paste = mock.Mock()
    monkeypatch.setattr(main, 'simulate_paste', paste)
    monkeypatch.setattr(main, '_wait_for_clipboard_change', lambda previous: True)
    if when == 'before_copy':
        def sleep(seconds):
            if seconds == .35:
                current[0] = second
        monkeypatch.setattr(main.time, 'sleep', sleep)
    elif when == 'during_translation':
        def translate(*args, **kwargs):
            current[0] = second
            return 'Translated selection'
        capture.provider.side_effect = translate
    else:
        def copy(text):
            if text == 'Translated selection':
                current[0] = second
            return capture.clipboard.copy(text)
        capture.copy.side_effect = copy
    owner = SelectionRequest()
    owner.launch_translate_replace_selection(expected_target=42)
    paste.assert_not_called()
    if when == 'before_copy':
        capture.copy_shortcut.assert_not_called()
        capture.copy.assert_not_called()
        capture.provider.assert_not_called()
    else:
        assert capture.clipboard.text == 'Translated selection'
        assert main.ui_text('en', 'selection_replace_fallback') in owner.statuses


@pytest.mark.parametrize('select_all', [False, True])
def test_confirmed_editor_preserves_explicit_chat_replacement(capture, monkeypatch, select_all):
    paste = mock.Mock()
    monkeypatch.setattr(main, 'simulate_paste', paste)
    monkeypatch.setattr(main, '_wait_for_clipboard_change', lambda previous: True)
    owner = SelectionRequest(replace_selection_select_all=select_all)
    owner.launch_translate_replace_selection(expected_target=42)
    paste.assert_called_once_with()
    assert owner.finished == [True]
    assert capture.clipboard.text == 'Clipboard before selection'
    if select_all:
        assert mock.call(0x41, 0, 0, 0) in capture.keys.call_args_list


def test_ordinary_hotkey_rejects_a_new_foreground_before_copy(capture, monkeypatch):
    def sleep(seconds):
        if seconds == .35:
            capture.foreground = 99
    monkeypatch.setattr(main.time, 'sleep', sleep)
    owner = SelectionRequest()
    owner.launch_translate_selection()
    capture.copy_shortcut.assert_not_called()
    capture.copy.assert_not_called()
    capture.provider.assert_not_called()


@pytest.mark.parametrize('action', ['select_all', 'paste'])
def test_editing_helpers_reject_non_editors_without_sending_any_shortcut(capture, monkeypatch, action):
    monkeypatch.setattr(main, '_windows_edit_target', lambda expected: None)
    paste = mock.Mock()
    monkeypatch.setattr(main, 'simulate_paste', paste)
    if action == 'select_all':
        assert main.select_all_text_in_foreground(42) is False
    else:
        assert main.replace_selected_text_in_foreground('Source', 'Result', 42) == (False, 'not_editable')
    capture.keys.assert_not_called()
    capture.copy_shortcut.assert_not_called()
    capture.copy.assert_not_called()
    paste.assert_not_called()


def test_foreground_process_uses_full_width_hwnd_without_touching_an_application(monkeypatch):
    import ctypes
    from test_windows_uia_contract import NativeCall
    hwnd = 0x1234567800000042
    def process_id(window, pointer):
        assert window == hwnd
        pointer._obj.value = 77
        return 8
    api = SimpleNamespace(GetForegroundWindow=NativeCall(lambda: hwnd),
                          GetWindowThreadProcessId=NativeCall(process_id))
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *_args, **_kwargs: api, raising=False)
    assert selection._foreground_process(hwnd) == 77
    assert selection._foreground_process(hwnd + 1) == 0
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(main.ctypes, 'windll', SimpleNamespace(user32=api), raising=False)
    assert main._windows_foreground_window() == hwnd


@pytest.mark.parametrize('reader', ['selection', 'editor'])
def test_chained_provider_exceptions_cannot_keep_com_values_alive(scenario, monkeypatch, reader):
    from test_windows_uia_contract import Element
    def broken_pattern(element, _pattern_id):
        try:
            raise RuntimeError('Nested provider failure')
        except RuntimeError as cause:
            error = ValueError('Provider failed while holding its element')
            raise error from cause
    monkeypatch.setattr(Element, 'GetCurrentPattern', broken_pattern)
    monkeypatch.setattr(selection, '_foreground_process', lambda expected: 77)
    result = (selection.read_windows_selected_text() if reader == 'selection'
              else selection.read_windows_edit_target(42))
    assert result == ('' if reader == 'selection' else None)
    assert not any(scenario.live.values())
