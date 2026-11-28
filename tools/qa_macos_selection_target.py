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
    if not ApplicationServices.AXIsProcessTrusted():
        report.update(status='skipped', reason='Accessibility is not granted to this Python process')
        return
    sys.path.insert(0, str(SOURCE))
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
