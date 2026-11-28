"""Exercise a companion panel against two WPF editors and a read-only grid on hosted Windows."""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import faulthandler
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from unittest.mock import patch


SAMPLE = 'identical selection'
TRANSLATION = 'translated span'
CLIPBOARD = 'Clipboard before the fixture action'


def wait_until(check, message, timeout=12, *, process_qt=True):
    from PyQt5.QtTest import QTest

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        if process_qt:
            QTest.qWait(15)
        else:
            time.sleep(.015)
    raise AssertionError(message)


@contextmanager
def wpf_fixture(exchange, directory):
    fixture = Path(__file__).with_name('qa_windows_selection_fixture.ps1')
    with (directory / 'fixture.log').open('wb') as log:
        process = subprocess.Popen(
            ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-STA',
             '-ExecutionPolicy', 'Bypass', '-File', str(fixture), '-Exchange', str(exchange)],
            stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        sequence = 0

        def command(op, *, process_qt=True):
            nonlocal sequence
            request = exchange / f'request-{sequence}.json'
            reply = exchange / f'reply-{sequence}.json'
            sequence += 1
            temporary = request.with_suffix('.tmp')
            temporary.write_text(json.dumps(op), encoding='utf-8')
            temporary.replace(request)
            wait_until(lambda: reply.exists() or process.poll() is not None,
                       f'WPF did not answer {op}', timeout=20, process_qt=process_qt)
            if not reply.exists():
                raise RuntimeError(f'WPF exited with {process.returncode} during {op}')
            state = json.loads(reply.read_text(encoding='utf-8-sig'))
            if 'error' in state:
                raise RuntimeError(state['error'])
            assert state['pid'] == process.pid
            return state

        try:
            yield command
        finally:
            if process.poll() is None:
                try:
                    command('quit')
                    # WPF may release an OLE data object owned by this Qt window.
                    # Keep the owning STA pumping messages until the fixture exits.
                    wait_until(lambda: process.poll() is not None, 'The WPF fixture did not close', timeout=8)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)


def press_panel_button(menu, action):
    """Send a native click to the panel as in the secondary-monitor selection test."""
    from PyQt5 import QtWidgets

    user = ctypes.WinDLL('user32', use_last_error=True)
    send = user.SendMessageW
    send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    send.restype = ctypes.c_ssize_t
    button = menu.buttons[action]
    menu.scroll.ensureWidgetVisible(button)
    QtWidgets.QApplication.processEvents()
    assert button.isEnabled() and button.isVisible()
    point = button.mapTo(menu, button.rect().center())
    hwnd = int(menu.winId())
    assert send(hwnd, 0x0021, hwnd, (0x0201 << 16) | 1) == 3  # WM_MOUSEACTIVATE: MA_NOACTIVATE
    coordinates = ((point.y() & 0xffff) << 16) | (point.x() & 0xffff)
    send(hwnd, 0x0201, 1, coordinates)
    send(hwnd, 0x0202, 0, coordinates)


def click_grid(state):
    """The real mouse poller must see a press and release over this fixture's HWND."""
    from PyQt5.QtTest import QTest

    api = ctypes.WinDLL('user32', use_last_error=True)
    api.WindowFromPoint.argtypes = [wintypes.POINT]
    api.WindowFromPoint.restype = wintypes.HWND
    api.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    api.GetAncestor.restype = wintypes.HWND
    x, y = state['gridPoint']
    assert api.SetCursorPos(x, y)
    assert api.GetAncestor(api.WindowFromPoint(wintypes.POINT(x, y)), 2) == state['hwnd']
    api.mouse_event(0x0002, 0, 0, 0, 0)
    try:
        QTest.qWait(320)
    finally:
        api.mouse_event(0x0004, 0, 0, 0, 0)


def action_keys(state):
    return [(event['focus'], event['key']) for event in state['keys']
            if event['event'] == 'PreviewKeyDown' and event['key'] in ('A', 'C', 'V')]


def check_office_clipboard(original, restored):
    formats = {'UnicodeText', 'Rich Text Format', 'HTML Format', 'ClicknTranslate Office Row'}
    for data in (original, restored):
        assert formats <= set(data['formats']), data
        fragment = '<table><tr><td><b>' + original['text'] + '</b></td></tr></table>'
        assert fragment in data['html'] and r'\b ' + original['text'] in data['rtf'], data
        assert base64.b64decode(data['row']).startswith(bytes((0, 13, 20, 25))), data
    assert (restored['text'], restored['rtf'], restored['row']) == (original['text'], original['rtf'], original['row'])


def release_fixture_profile():
    ocr = sys.modules.get('ocr')
    if ocr is not None:
        ocr.close_ocr_diagnostics_logging()
    profile = getattr(sys.modules.get('candidate_smoke'), '_startup_profile', None)
    if profile is not None:
        folder = Path(profile.name).resolve()
        assert folder.parent == Path(tempfile.gettempdir()).resolve() and folder.name.startswith('cnt-candidate-startup-')
        profile.cleanup()
        assert not folder.exists()


def check_global_hotkeys(window, command, top, requests, results, actions):
    import main
    import pyperclip
    from assistant_text import assistant_text
    from PyQt5 import QtCore

    user = ctypes.WinDLL('user32', use_last_error=True)
    for function in (user.GetClipboardOwner, user.GetOpenClipboardWindow):
        function.argtypes = []
        function.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    received = threading.Event()
    deliveries = []
    statuses = []
    hidden = []
    failures = []

    def received_on_listener(_callback):
        deliveries.append(dict(thread=threading.get_ident(), hwnd=main._windows_foreground_window()))
        received.set()

    def press(listener):
        assert main._windows_foreground_window() == top
        received.clear()
        modifiers = ((main.MOD_CONTROL, 0x11), (main.MOD_SHIFT, 0x10), (main.MOD_ALT, 0x12))
        chord = [key for mask, key in modifiers if listener.modifiers & mask] + [listener.vk]
        try:
            for key in chord:
                user.keybd_event(key, 0, 0, 0)
            assert received.wait(5), 'The registered global chord did not produce WM_HOTKEY'
        finally:
            for key in reversed(chord):
                user.keybd_event(key, 0, 2, 0)
        assert deliveries[-1]['thread'] != threading.get_ident() and deliveries[-1]['hwnd'] == top, deliveries
        wait_until(lambda: all(not user.GetAsyncKeyState(key) & 0x8000 for key in chord),
                   'The fixture keyboard chord remained down', process_qt=False)

    @contextmanager
    def scenario(label, listener):
        statuses.clear()
        hidden.clear()
        deliveries.clear()
        initial = command('first')
        command('clear-events')
        observed = actions[label] = dict(shortcut=listener.hotkey_str, before=initial)
        count = len(requests)
        events = observed['clipboard_observations'] = []
        native_sequence = main._clipboard_sequence_number
        native_read = pyperclip.paste

        def process(hwnd):
            pid = wintypes.DWORD()
            if hwnd:
                user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return int(pid.value)

        def sample(site, sequence, text=None):
            point = dict(site=site, sequence=sequence, owner_pid=process(user.GetClipboardOwner()),
                         open_pid=process(user.GetOpenClipboardWindow()))
            if text is not None:
                point['text'] = text
            if not events or events[-1] != point:
                events.append(point)

        def sequence():
            frame = sys._getframe(1)
            if frame.f_code.co_name == '_sequence':
                frame = frame.f_back
            value = native_sequence()
            sample(frame.f_code.co_name, value)
            return value

        def read():
            sample('before_read', native_sequence())
            value = native_read()
            sample('after_read', native_sequence(), value)
            return value

        try:
            assert initial['firstFocused'] and initial['selected'][0] == SAMPLE, initial
            with patch.object(main, '_clipboard_sequence_number', sequence), patch.object(pyperclip, 'paste', read):
                yield observed
            observed['passed'] = True
        except AssertionError as error:
            observed.update(passed=False, error=str(error))
            failures.append(label + ': ' + str(error))
        finally:
            observed.update(after=command('state'), deliveries=list(deliveries), statuses=list(statuses),
                            source_hwnd=top, final_hwnd=main._windows_foreground_window(),
                            clipboard_sequence=main._clipboard_sequence_number(), provider=requests[count:])

    def status_hidden():
        hidden.append(True)

    def status_shown(message):
        statuses.append(message)

    window._show_status_signal.connect(status_shown)
    window._hide_status_signal.connect(status_hidden)
    main.hotkey_dispatcher.triggered.connect(received_on_listener, type=QtCore.Qt.DirectConnection)
    try:
        for identifier, name, shortcut in ((4, 'launch_translate_selection', main.DEFAULT_SELECTION_HOTKEY),
                                           (6, 'launch_translate_replace_selection', main.DEFAULT_REPLACE_SELECTION_HOTKEY)):
            listener = main.HotkeyListenerThread(shortcut, getattr(window, name), hotkey_id=identifier)
            listener.start()
            try:
                wait_until(lambda: listener._registered, 'The fixture chord could not register')
                if identifier == 4:
                    # WPF can publish several formats while the copy shortcut is
                    # returning. Repeat the actual registered chord to observe both schedules.
                    for attempt in range(4):
                        label = 'stable_window' if attempt == 0 else f'stable_window_repeat_{attempt + 1}'
                        with scenario(label, listener) as observation:
                            count = len(results)
                            request_count = len(requests)
                            press(listener)
                            observation['before_dispatch'] = command('state', process_qt=False)
                            wait_until(lambda: len(results) == count + 1, 'The stable global selection did not complete')
                            normal = command('state')
                            assert action_keys(normal) == [('First', 'C')] and requests[request_count:] == [SAMPLE], normal
                            assert results[-1][4] == SAMPLE and results[-1][0] == TRANSLATION
                        for dialog in main._live_translation_result_dialogs():
                            dialog.close()

                    with scenario('different_field_during_copy', listener) as observation:
                        command('switch-on-copy')
                        request_count = len(requests)
                        press(listener)
                        observation['before_dispatch'] = command('state', process_qt=False)
                        wait_until(lambda: assistant_text('en', 'selection_focus_lost') in statuses and hidden,
                                   'Plain selection did not reject the editor that took focus during Ctrl+C')
                        moved = command('state')
                        assert moved['secondFocused'] and moved['selected'][1] == 'Second', moved
                        assert action_keys(moved) == [('First', 'C')] and len(requests) == request_count, moved
                        assert pyperclip.paste() == 'Second'

                with scenario(name, listener) as observation:
                    pyperclip.copy(CLIPBOARD)
                    before = main._clipboard_sequence_number()
                    assert before is not None
                    request_count = len(requests)
                    press(listener)
                    # Switch documents before Qt consumes the listener's queued callback.
                    other = observation['before_dispatch'] = command('other-document', process_qt=False)
                    assert other['otherHwnd'] != top and other['otherFocused'], other
                    assert main._windows_foreground_window() == other['otherHwnd']
                    wait_until(lambda: assistant_text('en', 'selection_focus_lost') in statuses and hidden,
                               'The global selection request did not finish after switching windows')
                    after = command('state')
                    assert action_keys(after) == [] and not any(e['focus'] == 'OtherDocument' for e in after['keys']), after
                    assert (after['first'], after['second'], after['other']) == (other['first'], other['second'], other['other'])
                    assert len(requests) == request_count
                    assert main._clipboard_sequence_number() == before and pyperclip.paste() == CLIPBOARD
            finally:
                listener.stop()
                listener.join(timeout=2)
                assert not listener.is_alive()
    finally:
        main.hotkey_dispatcher.triggered.disconnect(received_on_listener)
        window._show_status_signal.disconnect(status_shown)
        window._hide_status_signal.disconnect(status_hidden)
    assert not failures, failures


def exercise(report, directory, exchange):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from candidate_smoke import prepare_profile
    prepare_profile()
    import main
    import pyperclip
    import translater
    import windows_selection
    from PyQt5 import QtCore, QtWidgets, sip
    from PyQt5.QtTest import QTest

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app.platformName() == 'windows'
    app.setQuitOnLastWindowClosed(False)
    main.ensure_data_dir_and_files()
    config = dict(main.DEFAULT_CONFIG, interface_language='en', show_update_info=False,
                  desktop_assistant_enabled=True, desktop_assistant_actions=['selection', 'replace'],
                  selection_quick_translate_enabled=False, selection_quick_translate_mode='automatic',
                  restore_clipboard_after_selection=True, copy_translated_text=False,
                  replace_selection_select_all=False, notifications=False)
    Path(main.get_data_file('config.json')).write_text(json.dumps(config), encoding='utf-8')
    window = main.DarkThemeApp(background_services=False)
    window.create_tray_icon()
    window.show()
    window.start_button.click()
    report['shadow'] = dict(destination=window._window_hide_destination,
                            hidden=window.isHidden(), minimized=window.isMinimized())
    assert window.isHidden() or window.isMinimized(), report['shadow']
    window._sync_desktop_assistant()
    companion = window._desktop_assistant
    assert windows_selection.prepare_windows_selection()
    results, finished, requests = [], [], []
    window._show_selection_signal.connect(lambda *args: results.append(args))
    window._companion_selection_finished_signal.connect(lambda _, success: finished.append(success))
    entered, resume = threading.Event(), threading.Event()
    delay = False

    def translate(source, *_pair, **_options):
        requests.append(source)
        if delay:
            entered.set()
            if not resume.wait(10):
                raise AssertionError('Fixture did not resume translation after switching fields')
        return TRANSLATION

    try:
        with (wpf_fixture(exchange, directory) as command, ThreadPoolExecutor(max_workers=1) as mta,
              patch.object(translater, 'translate_text', side_effect=translate)):
            first = command('first')
            report['initial'] = first
            top = first['hwnd']
            assert first['firstFocused'] and main._windows_foreground_window() == top, first

            def current_editor():
                target = mta.submit(windows_selection.read_windows_edit_target, top).result(10)
                assert target is not None and target.process_id == first['pid'], target
                assert mta.submit(windows_selection.read_windows_selected_text).result(10) == SAMPLE
                return target

            left = current_editor()
            companion.toggle_menu()
            QTest.qWait(100)
            menu = companion.menu
            assert menu.isVisible() and main._windows_foreground_window() == top
            assert menu.grab().save(str(directory / 'panel.png'))
            assert app.primaryScreen().grabWindow(top).save(str(directory / 'fixture.png'))
            office = report['office_before'] = command('office-copy')['office']
            assert office['text'] == CLIPBOARD
            check_office_clipboard(office, office)
            command('clear-events')
            press_panel_button(menu, 'selection')
            wait_until(lambda: finished, 'The companion selection did not complete')
            assert finished == [True] and results and results[-1][0] == TRANSLATION
            assert results[-1][4] == SAMPLE and requests == [SAMPLE]
            read = report['selection'] = command('state')
            assert action_keys(read) == [('First', 'C')], read
            assert all(e['key'] in ('LeftCtrl', 'RightCtrl', 'C') for e in read['keys']), read
            assert (read['first'], read['second']) == (first['first'], first['second'])
            assert pyperclip.paste() == CLIPBOARD and menu.isVisible()
            report['office_after_selection'] = command('office-state')['office']
            check_office_clipboard(office, report['office_after_selection'])
            dialogs = main._live_translation_result_dialogs()
            assert len(dialogs) == 1 and dialogs[0].isVisible()
            assert dialogs[0].grab().save(str(directory / 'translation.png'))

            result_hwnd = int(dialogs[0].winId())
            wait_until(lambda: main._windows_foreground_window() == result_hwnd,
                       'The translation result did not become the active window')
            assert not command('state')['active']
            command('clear-events')
            delay = True
            press_panel_button(menu, 'replace')
            wait_until(entered.is_set, 'Replace from the active result did not reach its source')
            restored = report['source_restored_from_result'] = command('state')
            assert restored['active'] and restored['firstFocused'] and restored['selected'][0] == SAMPLE, restored
            assert main._windows_foreground_window() == top and current_editor() == left
            assert menu.isVisible()
            report['result_visible_after_source_restoration'] = bool(main._live_translation_result_dialogs())
            resume.set()
            wait_until(lambda: len(finished) == 2, 'The replacement did not complete')
            replaced = report['replacement'] = command('state')
            assert finished[-1] and requests == [SAMPLE, SAMPLE]
            assert replaced['first'] == 'First: translated span.' and replaced['second'] == first['second'], replaced
            assert action_keys(replaced) == [('First', 'C'), ('First', 'C'), ('First', 'V')], replaced
            assert all(e['key'] in ('LeftCtrl', 'RightCtrl', 'C', 'V') for e in replaced['keys']), replaced
            assert menu.isVisible() and pyperclip.paste() == CLIPBOARD
            report['office_after_replacement'] = command('office-state')['office']
            check_office_clipboard(office, report['office_after_replacement'])
            for dialog in main._live_translation_result_dialogs():
                dialog.close()
            QTest.qWait(100)

            original = command('reset-first')
            second = command('second')
            assert second['secondFocused']
            right = current_editor()
            assert left != right and left.window == right.window
            report['uia'] = dict(first=left.runtime_id, second=right.runtime_id, window=top)
            command('clear-events')
            entered.clear()
            resume.clear()
            press_panel_button(menu, 'replace')
            wait_until(entered.is_set, 'The second field never reached the provider')
            # Preserve the same spelling in a different editor within this top-level window.
            command('first')
            resume.set()
            wait_until(lambda: len(finished) == 3, 'The focus-switch fallback did not complete')
            switched = report['switched'] = command('state')
            assert requests == [SAMPLE] * 3 and finished[-1]
            assert action_keys(switched) == [('Second', 'C')], switched
            assert (switched['first'], switched['second']) == (original['first'], original['second'])
            assert pyperclip.paste() == TRANSLATION and menu.isVisible()

            window.config.update(selection_quick_translate_enabled=True, replace_selection_select_all=True)
            window._sync_selection_quick_translate()
            quick = window._selection_quick_translate
            assert quick._enabled
            before = main._clipboard_sequence_number()
            assert before is not None
            grid = command('clear-events')
            with patch.object(quick, '_accept_probe', wraps=quick._accept_probe) as accepted:
                click_grid(grid)
                wait_until(lambda: accepted.called, 'The real mouse poller never finished a grid selection probe')
                probe = accepted.call_args.args[0]
                assert probe['target'] == top and probe['text'] == '', probe
            idle = report['passive_grid'] = command('state')
            assert idle['gridFocused'] and idle['selectedRow'] == 0, idle
            assert idle['keys'] == [] and not quick._button.isVisible()
            assert main._clipboard_sequence_number() == before and pyperclip.paste() == TRANSLATION
            assert len(requests) == 3
            press_panel_button(menu, 'replace')
            wait_until(lambda: len(finished) == 4, 'The read-only grid replacement request did not finish')
            refused = report['grid_replacement_refused'] = command('state')
            assert not finished[-1] and refused['gridFocused'] and refused['keys'] == [], refused
            assert main._clipboard_sequence_number() == before and len(requests) == 3

            command('second')
            command('clear-events')
            entered.clear()
            resume.clear()
            window.config['replace_selection_select_all'] = False
            press_panel_button(menu, 'replace')
            wait_until(entered.is_set, 'The cancellable replacement did not reach its source')
            captured_sequence = main._clipboard_sequence_number()
            assert pyperclip.paste() == SAMPLE
            # The external application copies the same characters independently.
            # Its generation must survive cancellation of the companion request.
            external = report['office_external'] = command('external-copy')['office']
            foreign_sequence = main._clipboard_sequence_number()
            assert foreign_sequence is not None and foreign_sequence != captured_sequence
            companion.request_action('hide')
            resume.set()
            wait_until(lambda: len(finished) == 5, 'The disposed companion request did not finish')
            cancelled = report['cancelled_after_external_copy'] = command('state')
            assert not finished[-1] and action_keys(cancelled) == [('Second', 'C')], cancelled
            assert (cancelled['first'], cancelled['second']) == (original['first'], original['second'])
            assert main._clipboard_sequence_number() == foreign_sequence and pyperclip.paste() == SAMPLE
            report['office_after_cancel'] = command('office-state')['office']
            check_office_clipboard(external, report['office_after_cancel'])
            delay = False
            report['global_hotkeys'] = {}
            check_global_hotkeys(window, command, top, requests, results, report['global_hotkeys'])
            report.update(status='passed', provider_inputs=requests, completions=finished,
                          grid_clipboard_sequence_preserved=True, external_copy_sequence=foreign_sequence)
    finally:
        resume.set()
        # This probe starts these services explicitly on a no-background-services
        # window. Its normal close handler leaves those test-owned services alone.
        quick = getattr(window, '_selection_quick_translate', None)
        if quick is not None:
            quick.dispose()
        assistant = getattr(window, '_desktop_assistant', None)
        if assistant is not None and not sip.isdeleted(assistant):
            assistant.dispose()
        window.tray_icon.hide()
        window.force_quit = True
        window.close()
        assert QtCore.QThreadPool.globalInstance().waitForDone(5000)
        for widget in app.topLevelWidgets():
            if not sip.isdeleted(widget) and widget.parentWidget() is None and widget.graphicsProxyWidget() is None:
                widget.hide()
                widget.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()
        sip.delete(app)
        report['shutdown'] = 'Stopped native pollers, disposed fixture windows, drained Qt workers and destroyed QApplication'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    if (sys.platform != 'win32' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'
            or os.environ.get('GITHUB_ACTIONS') != 'true'):
        parser.error('This probe requires a disposable GitHub-hosted Windows desktop')
    faulthandler.enable()
    options.output.parent.mkdir(parents=True, exist_ok=True)
    result = dict(status='failed', sha=os.environ.get('GITHUB_SHA'), provider='deterministic fixture')
    try:
        with tempfile.TemporaryDirectory(prefix='cnt-wpf-focus-') as folder:
            try:
                exercise(result, options.output.parent, Path(folder))
            finally:
                release_fixture_profile()
                result['profile_cleaned'] = True
    except Exception:
        result['status'] = 'failed'
        result['error'] = traceback.format_exc()
        raise
    finally:
        options.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
