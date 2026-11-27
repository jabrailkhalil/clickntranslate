"""All native input APIs are blocked or replaced before listener construction."""
from threading import Thread
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets, sip
from PyQt5.QtTest import QTest

import main


@pytest.fixture
def scanner(monkeypatch):
    scans = {ord('?'): 0x01BF, ord('@'): 0x0232, ord('+'): 0x01BB,
             ord('É'): 0x0145, ord('€'): 0x0645, ord('İ'): 0x0149, ord('ß'): 0x0153}
    scan = mock.Mock(side_effect=lambda value: scans.get(value, -1))
    monkeypatch.setattr(main.platform_support, 'IS_MAC', False)
    monkeypatch.setattr(main.ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(VkKeyScanW=scan)), raising=False)
    return scan


@pytest.mark.parametrize('shortcut', ['Ctr+V', 'Ctrl+Unknown+A', 'Ctrl++A', 'Ctrl+F25+A',
                                     'Ctrl+K,Ctrl+C', 'Ctrl+Alt+garbage+Q'])
def test_malformed_imported_shortcut_does_not_become_another_global_chord(scanner, shortcut, monkeypatch):
    listener = main.HotkeyListenerThread(shortcut, lambda: None)
    assert listener.vk is None
    errors = []
    monkeypatch.setattr(main, 'hotkey_error_dispatcher',
                        SimpleNamespace(
                            registration_failed=SimpleNamespace(emit=errors.append),
                            registration_failed_owned=SimpleNamespace(
                                emit=lambda token, text: errors.append((token, text)))))
    # The fake user32 has no registration API at all: invalid text must return
    # before a native registration/message-pump route could be reached.
    listener.run()
    assert errors == [(listener._stop_event, shortcut)]


@pytest.mark.parametrize('shortcut,mods,key', [
    ('Ctrl+A', main.MOD_CONTROL, ord('A')),
    ('Ctrl+a', main.MOD_CONTROL, ord('A')),
    ('Ctrl+Alt+Q', main.MOD_CONTROL | main.MOD_ALT, ord('Q')),
    ('Ctrl+ф', main.MOD_CONTROL, ord('A')),
    ('Ctrl+É', main.MOD_CONTROL, 0x45),
    ('Ctrl+é', main.MOD_CONTROL, 0x45),
    ('Ctrl+?', main.MOD_CONTROL | main.MOD_SHIFT, 0xBF),
    ('Shift+€', main.MOD_SHIFT | main.MOD_CONTROL | main.MOD_ALT, 0x45),
    ('Ctrl+@', main.MOD_CONTROL, 0x32),
    ('Ctrl++', main.MOD_CONTROL | main.MOD_SHIFT, 0xBB),
])
def test_punctuation_implied_modifiers_do_not_turn_letter_labels_into_shifted_shortcuts(scanner, shortcut, mods, key):
    listener = main.HotkeyListenerThread(shortcut, lambda: None)
    assert listener.vk == key
    assert listener.modifiers == mods | 0x4000


@pytest.mark.parametrize('key', ['copy_hotkey', 'translate_hotkey', 'fullscreen_translate_hotkey',
                                'translate_selection_hotkey', 'translate_replace_selection_hotkey',
                                'toggle_window_hotkey', 'game_translate_hotkey'])
def test_all_normal_default_bindings_keep_their_letter_and_modifier_meaning(scanner, key):
    shortcut = main.fresh_config()[key]
    listener = main.HotkeyListenerThread(shortcut, lambda: None)
    assert listener.vk is not None
    assert bool(listener.modifiers & main.MOD_SHIFT) == ('shift' in shortcut.lower().split('+'))
    scanner.assert_not_called()


@pytest.mark.parametrize('symbol,key', [('Х', 0xDB), ('Ъ', 0xDD), ('Ж', 0xBA),
                                      ('Э', 0xDE), ('Б', 0xBC), ('Ю', 0xBE), ('Ё', 0xC0)])
@pytest.mark.parametrize('scan_value', [0x0134, -1], ids=['different-layout-symbol', 'unmapped-symbol'])
def test_cyrillic_oem_alias_is_physical_even_if_the_symbol_scan_differs(scanner, symbol, key, scan_value):
    scanner.side_effect = lambda _point: scan_value
    listener = main.HotkeyListenerThread('Ctrl+' + symbol, lambda: None)
    assert listener.vk == key
    assert listener.modifiers == main.MOD_CONTROL | 0x4000
    scanner.assert_not_called()


@pytest.mark.parametrize('symbol,scan_value,mods,key', [
    (';', 0x0134, main.MOD_CONTROL | main.MOD_SHIFT, 0x34),
    ('/', 0x0137, main.MOD_CONTROL | main.MOD_SHIFT, 0x37),
    ('[', -1, None, None),
    ('.', 0x06BE, main.MOD_CONTROL | main.MOD_ALT, 0xBE),
])
def test_literal_punctuation_keeps_the_stubbed_layout_gesture_instead_of_a_cyrillic_alias(scanner, symbol, scan_value, mods, key):
    scanner.side_effect = lambda _point: scan_value
    listener = main.HotkeyListenerThread('Ctrl+' + symbol, lambda: None)
    assert listener.vk == key
    if key is not None:
        assert listener.modifiers == mods | 0x4000


@pytest.mark.parametrize('symbol,key', [('İ', 0x49), ('ß', 0x53)])
def test_single_unicode_key_survives_case_expansion_without_implicit_shift(scanner, symbol, key):
    listener = main.HotkeyListenerThread('Ctrl+' + symbol, lambda: None)
    assert listener.vk == key
    assert listener.modifiers == main.MOD_CONTROL | 0x4000


@pytest.mark.parametrize('text', ['i\u0307', 'SS'])
def test_multicodepoint_keys_are_not_treated_as_a_single_expanding_unicode_key(scanner, text):
    assert main.HotkeyListenerThread('Ctrl+' + text, lambda: None).vk is None


@pytest.mark.parametrize('stage', ['constructor', 'start'])
@pytest.mark.parametrize('failure', [OSError, RuntimeError])
def test_one_refused_listener_does_not_abandon_the_remaining_reload(stage, failure, monkeypatch):
    events, created, errors = [], [], []
    methods = ['launch_copy', 'launch_translate', 'launch_fullscreen_translate', 'launch_translate_selection',
               'launch_translate_replace_selection', 'toggle_window_visibility', 'launch_game_translate']
    keys = ['copy_hotkey', 'translate_hotkey', 'fullscreen_translate_hotkey', 'translate_selection_hotkey',
            'translate_replace_selection_hotkey', 'toggle_window_hotkey', 'game_translate_hotkey']
    attributes = ['copy_hotkey_thread', 'translate_hotkey_thread', 'fullscreen_translate_hotkey_thread',
                  'translate_selection_hotkey_thread', 'translate_replace_selection_hotkey_thread',
                  'toggle_window_hotkey_thread', 'game_translate_hotkey_thread']
    failed_shortcut = 'Ctrl+Alt+F15'

    class Listener:
        def __init__(self, shortcut, callback, hotkey_id):
            if stage == 'constructor' and shortcut == failed_shortcut:
                raise failure('synthetic listener allocation failure')
            self.shortcut, self.stopped = shortcut, False
            created.append(self)

        def start(self):
            if stage == 'start' and self.shortcut == failed_shortcut:
                raise failure('synthetic listener admission failure')
            events.append(('start', self.shortcut))

        def stop(self):
            self.stopped = True

        def join(self, timeout=None):
            pass

        def is_alive(self):
            return False

    owner = SimpleNamespace(_hotkey_services_enabled=True, HotkeyListenerThread=Listener,
                            config={key: f'Ctrl+Alt+F{13+i}' for i, key in enumerate(keys)})
    for method in methods:
        setattr(owner, method, mock.Mock())
    for attribute in attributes:
        setattr(owner, attribute, SimpleNamespace(stop=lambda: events.append(('stop', None)), join=lambda **_kwargs: None))
    monkeypatch.setattr(main, 'hotkey_error_dispatcher', SimpleNamespace(registration_failed=SimpleNamespace(emit=errors.append)))
    escaped = []
    try:
        main.DarkThemeApp.restart_all_hotkey_listeners(owner)
    except BaseException as error:
        escaped.append(error)
    assert escaped == []
    assert events[:7] == [('stop', None)] * 7
    assert [key for event, key in events if event == 'start'] == [
        value for value in owner.config.values() if value != failed_shortcut]
    assert errors == [failed_shortcut]
    assert getattr(owner, attributes[2]) is None
    assert all(item.stopped for item in created if item.shortcut == failed_shortcut)


def test_a_real_queued_old_listener_callback_is_ignored_after_reload(scanner, monkeypatch):
    old, current = mock.Mock(), mock.Mock()
    previous = main.HotkeyListenerThread('Ctrl+Alt+F23', old)
    replacement = main.HotkeyListenerThread('Ctrl+Alt+F24', current)
    queued = []
    main.hotkey_dispatcher.triggered.connect(queued.append)
    try:
        worker = Thread(target=lambda: main.hotkey_dispatcher.triggered.emit(previous._invoke))
        worker.start()
        worker.join(3)
        assert not worker.is_alive()
        previous.stop()
        QtWidgets.QApplication.processEvents()
        with mock.patch.object(main.QApplication, 'focusWidget', return_value=None):
            for callback in queued:
                callback()
            replacement._invoke()
        old.assert_not_called()
        current.assert_called_once_with()
    finally:
        main.hotkey_dispatcher.triggered.disconnect(queued.append)
        previous.stop()
        replacement.stop()


class ErrorOwner(QtCore.QObject):
    _on_hotkey_registration_failed = main.DarkThemeApp._on_hotkey_registration_failed

    def __init__(self):
        super().__init__()
        self.current_interface_language = 'en'
        self.force_quit = False
        self.dialogs = []
        self._show_hotkey_error_dialog = lambda *args: self.dialogs.append(args)

    def _flush_hotkey_registration_errors(self):
        # Keep this regression importable before the new flush helper exists.
        return main.DarkThemeApp._flush_hotkey_registration_errors(self)


def test_seven_real_queued_failures_share_one_dialog_and_a_later_failure_still_reports():
    owner = ErrorOwner()
    dispatcher = main._HotkeyErrorDispatcher()
    dispatcher.registration_failed.connect(owner._on_hotkey_registration_failed)
    shortcuts = [f'Ctrl+Alt+F{13+i}' for i in range(7)]
    thread = Thread(target=lambda: [dispatcher.registration_failed.emit(value) for value in shortcuts])
    try:
        thread.start()
        thread.join(3)
        assert not thread.is_alive() and owner.dialogs == []
        QtWidgets.QApplication.processEvents()
        QTest.qWait(150)
        assert len(owner.dialogs) == 1
        assert all(shortcut in owner.dialogs[0][1] for shortcut in shortcuts)
        dispatcher.registration_failed.emit('Ctrl+Alt+F24')
        QTest.qWait(150)
        assert len(owner.dialogs) == 2
        assert 'Ctrl+Alt+F24' in owner.dialogs[-1][1]
    finally:
        owner.deleteLater()
        QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('retire', ['delete', 'quit'])
def test_pending_registration_warning_cannot_outlive_its_owner(retire):
    owner = ErrorOwner()
    dialogs = owner.dialogs
    owner._on_hotkey_registration_failed('Ctrl+Alt+F23')
    if retire == 'delete':
        sip.delete(owner)
    else:
        owner.force_quit = True
    QTest.qWait(150)
    assert dialogs == []
    if not sip.isdeleted(owner):
        owner.deleteLater()


def test_shortcut_error_renders_symbol_text_without_interpreting_it_as_html():
    owner = ErrorOwner()
    try:
        owner._on_hotkey_registration_failed('Ctrl+<fixture>&')
        QTest.qWait(150)
        assert len(owner.dialogs) == 1
        assert 'Ctrl+&lt;fixture&gt;&amp;' in owner.dialogs[0][1]
        assert '<fixture>' not in owner.dialogs[0][1]
    finally:
        owner.deleteLater()


def test_failures_arriving_during_a_modal_dialog_wait_until_it_closes():
    owner = ErrorOwner()
    depth, maximum = 0, 0

    def modal(title, message):
        nonlocal depth, maximum
        depth += 1
        maximum = max(maximum, depth)
        owner.dialogs.append((title, message))
        if len(owner.dialogs) == 1:
            owner._on_hotkey_registration_failed('Ctrl+Alt+F24')
            # QMessageBox.exec_ runs a nested Qt event loop. No actual dialog
            # is created here; let its already-scheduled timer become eligible.
            QTest.qWait(150)
        depth -= 1

    owner._show_hotkey_error_dialog = modal
    try:
        owner._on_hotkey_registration_failed('Ctrl+Alt+F23')
        QTest.qWait(420)
        assert maximum == 1
        assert len(owner.dialogs) == 2
        assert 'Ctrl+Alt+F23' in owner.dialogs[0][1]
        assert 'Ctrl+Alt+F24' in owner.dialogs[1][1]
    finally:
        owner.deleteLater()


@pytest.mark.parametrize('retire', ['delete', 'quit'])
def test_retiring_owner_during_the_modal_dialog_discards_its_late_pending_failures(retire):
    owner = ErrorOwner()
    dialogs = owner.dialogs

    def modal(*args):
        dialogs.append(args)
        owner._on_hotkey_registration_failed('Ctrl+Alt+F24')
        if retire == 'delete':
            owner.deleteLater()
            QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        else:
            owner.force_quit = True

    owner._show_hotkey_error_dialog = modal
    owner._on_hotkey_registration_failed('Ctrl+Alt+F23')
    QTest.qWait(300)
    assert len(dialogs) == 1
    if not sip.isdeleted(owner):
        owner.deleteLater()


def test_all_listener_admissions_can_fail_then_recover_on_the_next_reload(monkeypatch):
    keys = ['copy_hotkey', 'translate_hotkey', 'fullscreen_translate_hotkey',
            'translate_selection_hotkey', 'translate_replace_selection_hotkey',
            'toggle_window_hotkey', 'game_translate_hotkey']
    methods = ['launch_copy', 'launch_translate', 'launch_fullscreen_translate',
               'launch_translate_selection', 'launch_translate_replace_selection',
               'toggle_window_visibility', 'launch_game_translate']
    errors, started = [], []
    failing = True

    class Listener:
        def __init__(self, shortcut, callback, hotkey_id):
            self.shortcut = shortcut

        def start(self):
            if failing:
                raise OSError('synthetic exhausted worker capacity')
            started.append(self.shortcut)

        def stop(self):
            pass

        def is_alive(self):
            return False

    owner = SimpleNamespace(_hotkey_services_enabled=True, HotkeyListenerThread=Listener,
                            config={key: f'Ctrl+Alt+F{13+i}' for i, key in enumerate(keys)})
    for method in methods:
        setattr(owner, method, mock.Mock())
    monkeypatch.setattr(main, 'hotkey_error_dispatcher',
                        SimpleNamespace(registration_failed=SimpleNamespace(emit=errors.append)))
    main.DarkThemeApp.restart_all_hotkey_listeners(owner)
    assert errors == list(owner.config.values()) and started == []
    failing = False
    main.DarkThemeApp.restart_all_hotkey_listeners(owner)
    assert started == list(owner.config.values())
