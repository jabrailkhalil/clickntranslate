"""Exercise a companion panel against two WPF editors and a read-only grid on hosted Windows."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
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


def wait_until(check, message, timeout=12):
    from PyQt5.QtTest import QTest

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        QTest.qWait(15)
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

        def command(op):
            nonlocal sequence
            request = exchange / f'request-{sequence}.json'
            reply = exchange / f'reply-{sequence}.json'
            sequence += 1
            temporary = request.with_suffix('.tmp')
            temporary.write_text(json.dumps(op), encoding='utf-8')
            temporary.replace(request)
            wait_until(lambda: reply.exists() or process.poll() is not None,
                       f'WPF did not answer {op}', timeout=20)
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
                    process.wait(timeout=5)
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


def exercise(report, directory, exchange):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from candidate_smoke import prepare_profile
    prepare_profile()
    import main
    import pyperclip
    import translater
    import windows_selection
    from PyQt5 import QtWidgets
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
            pyperclip.copy(CLIPBOARD)
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
            dialogs = main._live_translation_result_dialogs()
            assert len(dialogs) == 1 and dialogs[0].isVisible()
            assert dialogs[0].grab().save(str(directory / 'translation.png'))
            dialogs[0].close()
            QTest.qWait(100)

            command('first')
            command('clear-events')
            press_panel_button(menu, 'replace')
            wait_until(lambda: len(finished) == 2, 'The replacement did not complete')
            replaced = report['replacement'] = command('state')
            assert finished[-1] and requests == [SAMPLE, SAMPLE]
            assert replaced['first'] == 'First: translated span.' and replaced['second'] == first['second'], replaced
            assert action_keys(replaced) == [('First', 'C'), ('First', 'C'), ('First', 'V')], replaced
            assert all(e['key'] in ('LeftCtrl', 'RightCtrl', 'C', 'V') for e in replaced['keys']), replaced
            assert menu.isVisible() and pyperclip.paste() == CLIPBOARD

            original = command('reset-first')
            second = command('second')
            assert second['secondFocused']
            right = current_editor()
            assert left != right and left.window == right.window
            report['uia'] = dict(first=left.runtime_id, second=right.runtime_id, window=top)
            command('clear-events')
            delay = True
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
            report.update(status='passed', provider_inputs=requests, completions=finished,
                          grid_clipboard_sequence_preserved=True)
    finally:
        resume.set()
        window.force_quit = True
        window.close()
        app.processEvents()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    if (sys.platform != 'win32' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'
            or os.environ.get('GITHUB_ACTIONS') != 'true'):
        parser.error('This probe requires a disposable GitHub-hosted Windows desktop')
    options.output.parent.mkdir(parents=True, exist_ok=True)
    result = dict(status='failed', sha=os.environ.get('GITHUB_SHA'), provider='deterministic fixture')
    try:
        with tempfile.TemporaryDirectory(prefix='cnt-wpf-focus-') as folder:
            exercise(result, options.output.parent, Path(folder))
    except Exception:
        result['error'] = traceback.format_exc()
        raise
    finally:
        options.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
