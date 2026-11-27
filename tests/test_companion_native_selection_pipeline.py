"""Real Windows palette -> selection worker -> result dialog, with fake data I/O.

Only this process's windows receive native messages. Clipboard, key injection,
history and provider calls are fake; foreground/window activation is real.
"""
import ctypes
import os
from ctypes import wintypes
from unittest import mock

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import clipboard_preservation
import game_mode
import main
import platform_support
import translater
from desktop_assistant import DesktopAssistant
from test_dropdown_native_secondary import native_secondary
from test_selection_clipboard_preservation import FakeClipboard


def test_native_selected_text_reaches_the_result_without_losing_its_source(native_secondary, monkeypatch, tmp_path):
    app, owner, screen, bounds = native_secondary
    api = ctypes.WinDLL('user32', use_last_error=True)
    api.GetForegroundWindow.restype = wintypes.HWND
    api.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    api.SendMessageW.restype = ctypes.c_ssize_t
    before = int(api.GetForegroundWindow() or 0)
    if not before or game_mode._window_belongs_to_this_process(before):
        import pytest
        pytest.skip('Keep the user foreground intact; do not activate another app to create a target')

    class SecondaryPlacement(QtCore.QObject):
        def eventFilter(self, widget, event):
            if event.type() == QtCore.QEvent.Show and isinstance(widget, QtWidgets.QWidget) and widget.isWindow():
                widget.winId()
                widget.windowHandle().setScreen(screen)
                frame = widget.frameGeometry()
                if not bounds.contains(frame):
                    frame.moveCenter(bounds.center())
                    widget.move(frame.topLeft())
            return False

    placement = SecondaryPlacement(app)
    app.installEventFilter(placement)
    clipboard = FakeClipboard()
    source = 'A selected sentence for the companion translation check.'
    translated = 'Предложение для проверки перевода через компаньона.'
    foregrounds = []

    def copy_selection():
        foregrounds.append(int(api.GetForegroundWindow() or 0))
        return clipboard.copy(source)

    monkeypatch.setattr(main.ctypes.windll.user32, 'keybd_event', mock.Mock())
    monkeypatch.setattr(platform_support, 'copy_text', clipboard.copy)
    monkeypatch.setattr(main.pyperclip, 'paste', clipboard.paste)
    monkeypatch.setattr(main, '_clipboard_sequence_number', lambda: clipboard.sequence)
    monkeypatch.setattr(clipboard_preservation, 'clipboard_sequence_number', lambda: clipboard.sequence)
    monkeypatch.setattr(main, 'simulate_copy', copy_selection)
    monkeypatch.setattr(main, 'save_translation_history', mock.Mock())
    live_google = os.environ.get('CNT_COMPANION_LIVE_GOOGLE') == '1'
    original_translate = translater.translate_text
    provider = mock.Mock(side_effect=(lambda *args: original_translate(*args, engine='Google'))
                         if live_google else None, return_value=translated)
    monkeypatch.setattr(translater, 'translate_text', provider)
    monkeypatch.setattr(owner, '_selected_text_translation_pair', lambda: ('en', 'ru'))
    owner.config.update(desktop_assistant_enabled=True, copy_translated_text=False,
                        restore_clipboard_after_selection=True, hide_translation_window=[],
                        interface_language='en')
    helper = DesktopAssistant(owner)
    owner._desktop_assistant = helper
    results = []
    owner._show_selection_signal.connect(lambda *values: results.append(values))
    dialogs_before = set(main._live_translation_result_dialogs())
    try:
        helper.toggle_menu()
        QTest.qWait(30)
        menu = helper.menu
        assert menu.windowHandle().screen() is screen
        assert bounds.contains(menu.frameGeometry())
        assert menu.windowFlags() & QtCore.Qt.WindowDoesNotAcceptFocus
        assert int(api.GetForegroundWindow() or 0) == before
        # Even a Qt activation request must not steal the source's focus.
        menu.activateWindow()
        app.processEvents()
        assert int(api.GetForegroundWindow() or 0) == before
        point = menu.buttons['selection'].mapTo(menu, menu.buttons['selection'].rect().center())
        coordinates = (point.y() << 16) | (point.x() & 0xffff)
        assert api.SendMessageW(int(menu.winId()), 0x0021, int(menu.winId()), (0x0201 << 16) | 1) == 3
        api.SendMessageW(int(menu.winId()), 0x0201, 1, coordinates)
        api.SendMessageW(int(menu.winId()), 0x0202, 0, coordinates)
        for _ in range(1200 if live_google else 80):
            QTest.qWait(25)
            if results and not helper._selection_pending:
                break
        assert results, (menu.activity_label.text(), foregrounds, helper._selection_request_target)
        provider.assert_called_once()
        assert provider.call_args.args[0] == source
        if live_google:
            assert results[0][0].strip() and results[0][0] != source
            assert any('\u0400' <= letter <= '\u052f' for letter in results[0][0])
        else:
            assert results[0][0] == translated
        assert results[0][4] == source
        assert provider.call_args.args[1:] == ('en', 'ru')
        assert foregrounds == [before]
        assert clipboard.text == 'Clipboard before selection'
        dialogs = [dialog for dialog in main._live_translation_result_dialogs() if dialog not in dialogs_before]
        assert len(dialogs) == 1 and dialogs[0].isVisible()
        assert dialogs[0].windowHandle().screen() is screen
        assert bounds.contains(dialogs[0].frameGeometry())
        assert menu.isVisible() and not helper._selection_pending
        assert dialogs[0].grab().save(str(tmp_path / 'native-selection-result.png'))
        assert menu.grab().save(str(tmp_path / 'native-selection-panel.png'))
    finally:
        for dialog in list(main._live_translation_result_dialogs()):
            if dialog not in dialogs_before:
                dialog.close()
        helper.dispose()
        owner._desktop_assistant = None
        app.removeEventFilter(placement)
        placement.deleteLater()
