"""Verify focus moves between two Cocoa-hosted editors when AX access is already granted."""

import argparse
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time


SAMPLE = 'Identical synthetic selection'
SOURCE = Path(__file__).resolve().parents[1] / 'src'


def write_private_text(board, text):
    from AppKit import NSPasteboardTypeString

    board.clearContents()
    assert board.setString_forType_(text, NSPasteboardTypeString)
    return int(board.changeCount())


def office_records(label):
    return [{
        'public.utf8-plain-text': f'{label} {row}'.encode(),
        'public.html': f'<table><tr><td><b>{label} {row}</b></td></tr></table>'.encode(),
        'public.rtf': (r'{\rtf1\ansi\b ' + f'{label} {row}' + '}').encode(),
        'com.clickntranslate.qa-office-row': bytes((0, 13, 20, row)),
    } for row in (1, 2)]


def write_private_office(board, label):
    from AppKit import NSPasteboardItem
    from Foundation import NSData

    items = []
    for record in office_records(label):
        item = NSPasteboardItem.alloc().init()
        for kind, value in record.items():
            assert item.setData_forType_(NSData.dataWithBytes_length_(value, len(value)), kind)
        items.append(item)
    board.clearContents()
    assert board.writeObjects_(items)
    return int(board.changeCount())


def pasteboard_writer(pipe, name):
    from AppKit import NSPasteboard

    board = NSPasteboard.pasteboardWithName_(name)
    try:
        while (text := pipe.recv()) is not None:
            if isinstance(text, tuple):
                pipe.send(write_private_office(board, text[1]))
            else:
                pipe.send(write_private_text(board, text))
    finally:
        pipe.close()


def exercise_private_clipboard():
    """Test real Cocoa change counts and an independent writer without AX or the general pasteboard."""
    from AppKit import NSPasteboard, NSPasteboardTypeString
    from clipboard_formats import capture_cocoa_items, restore_cocoa_items
    from clipboard_preservation import ClipboardPreservation
    from types import SimpleNamespace

    board = NSPasteboard.pasteboardWithUniqueName()
    context = multiprocessing.get_context('spawn')
    control, child = context.Pipe()
    process = context.Process(target=pasteboard_writer, args=(child, str(board.name())))
    process.start()
    child.close()

    def publish(text):
        control.send(text)
        assert control.poll(10), 'The separate pasteboard writer did not reply'
        return control.recv()

    def read():
        return str(board.stringForType_(NSPasteboardTypeString) or '')

    def copy(text):
        write_private_text(board, text)
        return True

    records = []
    try:
        for timing in ('stable', 'before_read', 'during_validation'):
            values = (SAMPLE,) if timing == 'stable' else (SAMPLE, 'A newer external copy')
            for value in values:
                copy('Original fixture clipboard')
                guard = ClipboardPreservation(read, copy, lambda: int(board.changeCount()))
                copy('')
                assert guard.claim('')
                source_sequence = publish(SAMPLE)
                newer = publish(value) if timing == 'before_read' else None

                def still_focused():
                    nonlocal newer
                    if timing == 'during_validation':
                        newer = publish(value)
                    return True

                captured = guard.read_and_claim(still_focused, source_sequence)
                restored = guard.restore()  # The same cleanup runs on cancelled selection requests.
                final_sequence = int(board.changeCount())
                if timing == 'stable':
                    assert captured == SAMPLE and restored and read() == 'Original fixture clipboard'
                else:
                    assert newer != source_sequence and final_sequence == newer
                    assert captured is None and not restored and read() == value
                records.append(dict(timing=timing, identical_text=value == SAMPLE, restored=restored,
                                    source_sequence=source_sequence, foreign_sequence=newer,
                                    final_sequence=final_sequence))
        rich_results = []
        formats = SimpleNamespace(capture=lambda: capture_cocoa_items(board),
                                  restore=lambda data, owned: restore_cocoa_items(board, data, owned))

        def observed_items():
            return [{str(kind): bytes(item.dataForType_(kind)) for kind in item.types()}
                    for item in board.pasteboardItems()]

        for scenario in ('restore_original', 'restore_newer_before_replacement', 'cancel_after_newer'):
            label = 'Original spreadsheet'
            publish(('office', label))
            baseline = observed_items()
            guard = ClipboardPreservation(read, copy, lambda: int(board.changeCount()), formats=formats)
            copy('Temporarily selected source')
            assert guard.claim('Temporarily selected source')
            other = None
            if scenario != 'restore_original':
                label = 'Newer spreadsheet'
                other = publish(('office', label))
                baseline = observed_items()
            if scenario == 'restore_newer_before_replacement':
                assert guard.preserve_current_if_changed()
                copy('Translated result')
                assert guard.claim('Translated result')
            restored = guard.restore()
            assert restored == (scenario != 'cancel_after_newer')
            if not restored:
                assert int(board.changeCount()) == other
            items = observed_items()
            expected = office_records(label)
            assert items == baseline and len(items) == len(expected)
            for item, record in zip(items, expected):
                assert all(item[kind] == value for kind, value in record.items())
            rich_results.append(dict(scenario=scenario, item_count=len(items), formats=sorted(expected[0]),
                                     restored=restored, final_sequence=int(board.changeCount())))
        return dict(status='passed', private_board=True, reader_pid=os.getpid(),
                    external_writer_pid=process.pid, cases=records, office=rich_results)
    finally:
        if process.is_alive():
            control.send(None)
            process.join(5)
        if process.is_alive():
            process.terminate()
            process.join(5)
        control.close()
        board.releaseGlobally()


def editor_fixture(pipe):
    from AppKit import NSApplication, NSApplicationActivationPolicyRegular, NSApplicationActivateIgnoringOtherApps
    from AppKit import NSRunningApplication
    from PyQt5 import QtCore, QtWidgets

    app = QtWidgets.QApplication([])
    assert app.platformName() == 'cocoa'
    native = NSApplication.sharedApplication()
    native.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    window = QtWidgets.QWidget()
    window.setWindowTitle('ClicknTranslate accessibility fixture')
    layout = QtWidgets.QVBoxLayout(window)
    fields = []
    for name in ('First fixture editor', 'Second fixture editor'):
        editor = QtWidgets.QLineEdit(SAMPLE)
        editor.setAccessibleName(name)
        layout.addWidget(editor)
        fields.append(editor)
    window.show()
    NSRunningApplication.currentApplication().activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
    window.raise_()
    window.activateWindow()
    def focus(index):
        fields[index].setFocus()
        fields[index].selectAll()
    def step():
        if pipe.poll():
            command = pipe.recv()
            if command == 'quit':
                app.quit()
            elif command in (0, 1):
                focus(command)
                pipe.send([field.hasFocus() for field in fields])
            elif command == 'contents':
                pipe.send([field.text() for field in fields])
    timer = QtCore.QTimer()
    timer.timeout.connect(step)
    timer.start(25)
    app.exec_()


def wait_target(desktop, pid, previous=None):
    import CoreFoundation

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        target = desktop.foreground_target()
        if (target is not None and target.pid == pid and target.focused_element is not None
                and desktop.read_foreground_selected_text() == SAMPLE):
            if previous is None:
                return target
            if (CoreFoundation.CFEqual(target.window, previous.window)
                    and not CoreFoundation.CFEqual(target.focused_element, previous.focused_element)):
                return target
        time.sleep(.05)
    raise AssertionError('The two fixture fields were not distinguishable through native Accessibility')


def exercise(report):
    import ApplicationServices
    sys.path.insert(0, str(SOURCE))
    report['private_clipboard'] = exercise_private_clipboard()
    if not ApplicationServices.AXIsProcessTrusted():
        report.update(status='skipped', reason='Accessibility is not granted to this Python process')
        return
    import macos_desktop as desktop
    import main

    context = multiprocessing.get_context('spawn')
    control, child = context.Pipe()
    process = context.Process(target=editor_fixture, args=(child,))
    process.start()
    child.close()
    def command(value):
        control.send(value)
        assert control.poll(10), f'No response from fixture for {value}'
        return control.recv()
    try:
        assert command(0) == [True, False]
        first = wait_target(desktop, process.pid)
        assert desktop.same_foreground_target(first, require_focused_element=True)
        assert command(1) == [False, True]
        second = wait_target(desktop, process.pid, first)
        assert desktop.same_foreground_target(second, require_focused_element=True)
        assert not desktop.same_foreground_target(first, require_focused_element=True)
        sequence = desktop.clipboard_sequence()
        assert not main.select_all_text_in_foreground(first)
        success, reason = main.replace_selected_text_in_foreground(SAMPLE, 'Fixture translation', first)
        assert not success and reason == 'focus_changed'
        assert desktop.clipboard_sequence() == sequence
        assert command('contents') == [SAMPLE, SAMPLE]
        report.update(status='passed', fixture_pid=process.pid, same_window=True,
                      distinct_ax_elements=True, clipboard_sequence_preserved=True, replacement=reason)
    finally:
        if process.is_alive():
            control.send('quit')
            process.join(5)
        if process.is_alive():
            process.terminate()
            process.join(5)
        control.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('This probe requires a disposable macOS desktop')
    os.environ['QT_QPA_PLATFORM'] = 'cocoa'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {'status': 'failed'}
    try:
        with tempfile.TemporaryDirectory(prefix='cnt-ax-focus-') as temporary:
            for name in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME'):
                folder = Path(temporary) / name.lower()
                folder.mkdir()
                os.environ[name] = str(folder)
            exercise(result)
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
