"""Selection capture restores only its own clipboard writes; all I/O is fake."""
from types import SimpleNamespace
from unittest import mock

import pytest

import clipboard_preservation
import main
import platform_support
import selection_platform
import translater
from test_desktop_ux import app
from test_translation_result_ui import _SelectionHarness, _immediate_thread
from selection_test_support import editable_editor


class FakeClipboard:
    def __init__(self):
        self.text = "Clipboard before selection"
        self.sequence = 1

    def copy(self, text):
        self.text = text
        self.sequence += 1
        return True

    def paste(self):
        return self.text


@pytest.fixture
def clipboard(monkeypatch, editable_editor):
    value = FakeClipboard()
    monkeypatch.setattr(platform_support, "IS_WINDOWS", True)
    monkeypatch.setattr(platform_support, "IS_MAC", False)
    monkeypatch.setattr(platform_support, "IS_LINUX", False)
    monkeypatch.setattr(main.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(keybd_event=mock.Mock())), raising=False)
    monkeypatch.setattr(platform_support, "copy_text", value.copy)
    monkeypatch.setattr(main.pyperclip, "paste", value.paste)
    monkeypatch.setattr(main, "_clipboard_sequence_number", lambda: value.sequence)
    monkeypatch.setattr(clipboard_preservation, "clipboard_sequence_number", lambda: value.sequence)
    monkeypatch.setattr(main, "simulate_copy", lambda: value.copy("Selected text"))
    monkeypatch.setattr(main.threading, "Thread", _immediate_thread)
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    monkeypatch.setattr(main, "save_translation_history", mock.Mock())
    return value


@pytest.mark.parametrize("completion", ["success", "empty", "error"])
@pytest.mark.parametrize("new_text", ["A newer user copy", "Selected text"])
def test_new_user_copy_survives_selection_completion_and_failure(clipboard, monkeypatch, completion, new_text):
    owner = _SelectionHarness({"copy_translated_text": False, "restore_clipboard_after_selection": True})

    def translate(*args, **kwargs):
        clipboard.copy(new_text)
        if completion == "error":
            raise RuntimeError("Fake provider failure")
        return "Translation" if completion == "success" else ""

    monkeypatch.setattr(translater, "translate_text", translate)
    owner.launch_translate_selection()
    assert clipboard.text == new_text
    assert bool(owner.shown_dialogs) == (completion == "success")


@pytest.mark.parametrize("completion", ["success", "empty", "error"])
def test_unchanged_capture_still_restores_previous_text(clipboard, monkeypatch, completion):
    owner = _SelectionHarness({"copy_translated_text": False, "restore_clipboard_after_selection": True})

    def translate(*args, **kwargs):
        if completion == "error":
            raise RuntimeError("Fake provider failure")
        return "Translation" if completion == "success" else ""

    monkeypatch.setattr(translater, "translate_text", translate)
    owner.launch_translate_selection()
    assert clipboard.text == "Clipboard before selection"


@pytest.mark.parametrize("new_text", ["A newer user copy", "Selected text"])
@pytest.mark.parametrize("lose_focus", [False, True])
def test_probe_keeps_a_user_copy_after_capturing_the_source_response(clipboard, monkeypatch, new_text, lose_focus):
    captured, changed = [False], [False]

    def key(vk, scan, flags, extra):
        if vk == 0x43 and flags == 0:
            clipboard.copy("Selected text")

    def paste():
        value = clipboard.paste()
        if value == "Selected text":
            captured[0] = True
        return value

    def validate():
        # The source app's copy has been read. A separate user copy then
        # arrives before completion/cleanup, with or without a focus change.
        if captured[0] and not changed[0]:
            clipboard.copy(new_text)
            changed[0] = True
        return not (changed[0] and lose_focus)

    main.ctypes.windll.user32.keybd_event = key
    monkeypatch.setattr(main.pyperclip, "paste", paste)
    result = selection_platform._read_selection_via_copy(validate_target=validate)
    assert result == ""
    assert changed[0]
    assert clipboard.text == new_text


@pytest.mark.parametrize("copy_delay", [.04, .12])
@pytest.mark.parametrize("native_identity", [True, False])
def test_probe_waits_for_the_source_app_to_publish_its_queued_copy(clipboard, monkeypatch, copy_delay, native_identity):
    now, queued = [0.0], []
    releases = []

    def key(vk, scan, flags, extra):
        if vk == 0x43:
            if flags == 0:
                queued.append(copy_delay)
            else:
                releases.append(now[0])

    def sleep(seconds):
        now[0] += seconds
        if queued and now[0] >= queued[0]:
            queued.clear()
            clipboard.copy("Selected text")

    main.ctypes.windll.user32.keybd_event = key
    if not native_identity:
        monkeypatch.setattr(clipboard_preservation, "clipboard_sequence_number", lambda: None)
    monkeypatch.setattr(main.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(main.time, "sleep", sleep)
    assert selection_platform._read_selection_via_copy(validate_target=lambda: True) == "Selected text"
    assert releases == [.02]  # The external app publishes after key-up.
    assert clipboard.text == "Clipboard before selection"


@pytest.mark.parametrize("cancel", [False, True])
def test_probe_polling_is_bounded_and_stops_when_target_is_invalid(clipboard, monkeypatch, cancel):
    now, focused = [0.0], [True]

    def sleep(seconds):
        now[0] += seconds
        if cancel and now[0] >= .04:
            focused[0] = False

    monkeypatch.setattr(main.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(main.time, "sleep", sleep)
    assert selection_platform._read_selection_via_copy(validate_target=lambda: focused[0]) == ""
    assert .02 <= now[0] <= .221
    if cancel:
        assert now[0] <= .041
    assert clipboard.text == "Clipboard before selection"


def test_probe_can_restore_by_native_identity_when_reading_text_fails(clipboard, monkeypatch):
    reads = [0]

    def paste():
        reads[0] += 1
        if reads[0] > 1:
            raise RuntimeError("Clipboard read temporarily unavailable")
        return clipboard.paste()

    def key(vk, scan, flags, extra):
        if vk == 0x43 and flags == 0:
            clipboard.copy("Selected text")

    main.ctypes.windll.user32.keybd_event = key
    monkeypatch.setattr(main.pyperclip, "paste", paste)
    assert selection_platform._read_selection_via_copy() == ""
    assert clipboard.text == "Clipboard before selection"


def test_identity_loss_never_falls_back_to_equal_text(clipboard):
    sequence = [clipboard.sequence]
    guard = clipboard_preservation.ClipboardPreservation(clipboard.paste, clipboard.copy, lambda: sequence[0])
    clipboard.copy("Selected text")
    sequence[0] = clipboard.sequence
    guard.claim("Selected text")
    sequence[0] = None
    assert not guard.restore()
    assert clipboard.text == "Selected text"


@pytest.mark.parametrize("changed", [False, True])
def test_platform_without_native_identity_compares_current_text(clipboard, changed):
    guard = clipboard_preservation.ClipboardPreservation(clipboard.paste, clipboard.copy, lambda: None)
    clipboard.copy("Selected text")
    guard.claim("Selected text")
    if changed:
        clipboard.copy("A newer user copy")
    assert guard.restore() is not changed
    assert clipboard.text == ("A newer user copy" if changed else "Clipboard before selection")


@pytest.mark.parametrize("new_copy", [False, True])
def test_successful_replacement_claims_its_paste_payload_before_restoring(clipboard, monkeypatch, new_copy):
    owner = _SelectionHarness({"copy_translated_text": False, "restore_clipboard_after_selection": True})
    monkeypatch.setattr(main, "_windows_foreground_window", lambda: 42)
    monkeypatch.setattr(main, "_wait_for_clipboard_change", lambda _: True)
    monkeypatch.setattr(translater, "translate_text", lambda *args, **kwargs: "Translation")

    def sleep(seconds):
        if new_copy and seconds == .08:
            clipboard.copy("A newer user copy")

    monkeypatch.setattr(main.time, "sleep", sleep)
    monkeypatch.setattr(main, "simulate_paste", mock.Mock())
    owner.launch_translate_replace_selection()
    main.simulate_paste.assert_called_once_with()
    assert clipboard.text == ("A newer user copy" if new_copy else "Clipboard before selection")


def test_replacement_preserves_a_copy_made_before_the_paste_transaction(clipboard, monkeypatch):
    owner = _SelectionHarness({"copy_translated_text": False, "restore_clipboard_after_selection": True})
    monkeypatch.setattr(main, "_windows_foreground_window", lambda: 42)
    monkeypatch.setattr(main, "_wait_for_clipboard_change", lambda _: True)
    monkeypatch.setattr(main, "simulate_paste", mock.Mock())

    def translate(*args, **kwargs):
        clipboard.copy("A newer user copy")
        return "Translation"

    monkeypatch.setattr(translater, "translate_text", translate)
    owner.launch_translate_replace_selection()
    main.simulate_paste.assert_called_once_with()
    assert clipboard.text == "A newer user copy"


@pytest.mark.parametrize('scenario', ['visible_result', 'successful_replace', 'provider_error',
                                      'new_rich_copy_before_replace', 'new_rich_copy_before_result'])
def test_office_formats_survive_selection_while_their_text_representation_remains_available(
        app, clipboard, isolated_clipboard, monkeypatch, scenario):
    from PyQt5 import QtCore

    board = isolated_clipboard
    generation = [1]
    board.dataChanged.connect(lambda: generation.__setitem__(0, generation[0] + 1))

    def rich(text):
        data = QtCore.QMimeData()
        data.setText(text)
        data.setHtml('<table><tr><td><b>' + text + '</b></td></tr></table>')
        data.setData('text/rtf', ('{\\rtf1\\ansi\\b ' + text + '}').encode())
        data.setData('application/x-synthetic-office-row', b'\x00\x0d\x14' + text.encode())
        board.setMimeData(data)
        return {kind: bytes(data.data(kind)) for kind in data.formats()}

    expected = [rich('First office cell')]
    monkeypatch.setattr(main, '_clipboard_sequence_number', lambda: generation[0])
    monkeypatch.setattr(clipboard_preservation, 'clipboard_sequence_number', lambda: generation[0])
    monkeypatch.setattr(platform_support, 'copy_text', lambda text: (board.setText(text) or True))
    monkeypatch.setattr(main.pyperclip, 'paste', board.text)
    monkeypatch.setattr(main, 'simulate_copy', lambda: board.setText('Selected source text'))
    monkeypatch.setattr(main, 'simulate_paste', mock.Mock())
    owner = _SelectionHarness({'copy_translated_text': False, 'restore_clipboard_after_selection': True})

    def translate(*_args, **_kwargs):
        if scenario.startswith('new_rich_copy'):
            expected[0] = rich('Later office cell')
        if scenario == 'provider_error':
            raise RuntimeError('synthetic provider failure')
        return 'Selected translation'

    monkeypatch.setattr(translater, 'translate_text', translate)
    if 'replace' in scenario:
        owner.launch_translate_replace_selection()
        main.simulate_paste.assert_called_once_with()
    else:
        owner.launch_translate_selection()
    actual = board.mimeData()
    assert {kind: bytes(actual.data(kind)) for kind in actual.formats()} == expected[0]


def test_delayed_gui_restoration_respects_the_copy_that_arrived_while_queued(app, isolated_clipboard):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from PyQt5 import QtCore
    from PyQt5.QtTest import QTest
    from clipboard_formats import application_clipboard_formats

    data = QtCore.QMimeData()
    data.setText('Spreadsheet cell')
    data.setHtml('<b>Spreadsheet cell</b>')
    isolated_clipboard.setMimeData(data)
    service = application_clipboard_formats()
    snapshot = service.capture()
    queued = Event()

    def scheduled(_operation):
        queued.set()

    service._requested.connect(scheduled, type=QtCore.Qt.DirectConnection)
    try:
        with ThreadPoolExecutor(max_workers=1) as worker:
            isolated_clipboard.setText('Temporary translation')
            result = worker.submit(service.restore, snapshot, lambda: isolated_clipboard.text() == 'Temporary translation')
            assert queued.wait(2)
            isolated_clipboard.setText('A newer user copy')
            for _ in range(100):
                if result.done():
                    break
                QTest.qWait(10)
            assert result.result(1) is False
    finally:
        service._requested.disconnect(scheduled)
    assert isolated_clipboard.text() == 'A newer user copy'


@pytest.mark.parametrize('restore', [False, True])
def test_translation_reads_an_accessible_selection_without_rendering_the_clipboard(
        app, clipboard, monkeypatch, restore):
    from clipboard_formats import application_clipboard_formats

    formats = application_clipboard_formats()
    snapshot = mock.Mock(side_effect=AssertionError('This clipboard must not be materialized'))
    monkeypatch.setattr(formats, 'capture', snapshot)
    monkeypatch.setattr(selection_platform, 'read_selected_text', lambda **_kwargs: 'Directly selected text')
    shortcut = mock.Mock()
    monkeypatch.setattr(main, 'simulate_copy', shortcut)
    owner = _SelectionHarness({'restore_clipboard_after_selection': restore, 'copy_translated_text': False})
    provider = mock.Mock(return_value='Translation')
    monkeypatch.setattr(translater, 'translate_text', provider)
    owner.launch_translate_selection()
    provider.assert_called_once_with('Directly selected text', 'es', 'en')
    assert len(owner.shown_dialogs) == 1
    shortcut.assert_not_called()
    snapshot.assert_not_called()
    assert clipboard.text == 'Clipboard before selection'


@pytest.mark.parametrize('unavailable', ['file_promise', 'unreadable', 'over_budget'])
def test_unavailable_rich_clipboard_stops_before_select_all_or_temporary_writes(
        app, clipboard, isolated_clipboard, monkeypatch, unavailable):
    from PyQt5 import QtCore
    import clipboard_formats

    reads = []
    kind = ('application/x-qt-windows-mime;value="FileContents";index=0'
            if unavailable == 'file_promise' else 'text/rtf')

    class OfficeMime(QtCore.QMimeData):
        def formats(self):
            return ['text/plain', kind]

        def data(self, requested):
            reads.append(requested)
            if requested == kind:
                return QtCore.QByteArray() if unavailable == 'unreadable' else QtCore.QByteArray(b'large format')
            return super().data(requested)

    data = OfficeMime()
    data.setText('cell')
    isolated_clipboard.setMimeData(data)
    if unavailable == 'over_budget':
        monkeypatch.setattr(clipboard_formats, 'MAX_SNAPSHOT_BYTES', 8)
    select_all, copy, provider = mock.Mock(), mock.Mock(), mock.Mock()
    monkeypatch.setattr(main, 'select_all_text_in_foreground', select_all)
    monkeypatch.setattr(main, 'simulate_copy', copy)
    monkeypatch.setattr(translater, 'translate_text', provider)
    owner = _SelectionHarness({'replace_selection_select_all': True, 'restore_clipboard_after_selection': True})
    owner.launch_translate_replace_selection()
    assert isolated_clipboard.mimeData() is data and clipboard.text == 'Clipboard before selection'
    assert (kind in reads) is (unavailable != 'file_promise')
    select_all.assert_not_called()
    copy.assert_not_called()
    provider.assert_not_called()


def test_qt_five_restores_office_data_under_its_original_windows_registration(app, isolated_clipboard, monkeypatch):
    from PyQt5 import QtCore
    from clipboard_formats import application_clipboard_formats

    service = application_clipboard_formats()
    monkeypatch.setattr(service, '_windows', True)
    original = QtCore.QMimeData()
    original.setText('Cell')
    first = 'application/x-qt-windows-mime;value="Rich Text Format"'
    second = 'application/x-qt-windows-mime;value="Custom Spreadsheet Row"'
    original.setData(first, b'{RTF}')
    original.setData(second, bytes((0, 13, 20)))
    isolated_clipboard.setMimeData(original)
    snapshot = service.capture()
    isolated_clipboard.setText('Temporary')
    assert service.restore(snapshot, lambda: True)
    restored = isolated_clipboard.mimeData()
    assert restored.formats() == ['text/plain', 'Rich Text Format', 'Custom Spreadsheet Row']
    assert bytes(restored.data('Rich Text Format')) == b'{RTF}'
    assert bytes(restored.data('Custom Spreadsheet Row')) == bytes((0, 13, 20))
