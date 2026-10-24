"""Independent UI boundary scenarios found during the 2026-10-24 audit."""
from PyQt5 import QtCore, QtGui, QtWidgets, sip
from PyQt5.QtTest import QTest
import pytest
import json
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
from pathlib import Path
import threading
import builtins
from types import SimpleNamespace

import keyboard_navigation as keyboard
import main
import ocr
import settings_window as settings_module
import history_storage
from test_desktop_ux import app, window
from test_capture_region_memory import capture
from test_dynamic_workspace import isolated, make_overlay


@pytest.fixture(autouse=True)
def clean_keyboard_context(app):
    direction = app.layoutDirection()
    yield
    app.setLayoutDirection(direction)
    navigation = getattr(app, '_keyboard_navigation', None)
    if navigation is not None:
        dialog = navigation._help_dialog
        if dialog is not None and not sip.isdeleted(dialog):
            dialog.close()
        navigation._help_dialog = None
        navigation.keyboard = False
        navigation._hide_ring()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


@pytest.mark.parametrize('direction', [-1, 1])
@pytest.mark.parametrize('busy', [False, True])
def test_ctrl_tab_does_not_crash_on_embedded_update_page(window, app, direction, busy):
    window.show_settings()
    settings = window.settings_window
    settings._show_update_progress('An isolated update status; no update job is running')
    settings._update_in_progress = busy
    settings._set_settings_page(settings.settings_pages.indexOf(settings._update_progress))
    app.processEvents()
    assert settings._settings_page_index not in (0, 1, 2, 3, 4)
    assert isinstance(app._keyboard_navigation._settings_tab(window, direction), bool)
    if busy:
        assert settings.settings_pages.currentWidget() is settings._update_progress
    settings._update_in_progress = False


@pytest.mark.parametrize('mode', ['copy', 'translate'])
@pytest.mark.parametrize('locale', keyboard.LANGUAGES)
def test_f1_capture_help_uses_the_capture_interface_language(capture, app, mode, locale):
    config, _, _, create = capture
    config['interface_language'] = locale
    value = create(mode)
    QTest.keyClick(value, QtCore.Qt.Key_F1)
    for _ in range(3):
        app.processEvents()
    dialog = app._keyboard_navigation._help_dialog
    assert dialog is not None and dialog.isVisible()
    assert dialog.windowTitle() == keyboard.text(locale, 'title')
    assert keyboard.text(locale, 'area') in dialog.text()
    from dialog_text import _ACTIONS
    assert dialog.title_bar.close_button.toolTip() == _ACTIONS['Close'][keyboard.LANGUAGES.index(locale)]
    QTest.keyClick(dialog, QtCore.Qt.Key_Escape)
    app.processEvents()
    assert value.isVisible()


def test_f1_output_toolbar_help_uses_its_interface_language(isolated, app):
    config, _ = isolated
    config['interface_language'] = 'ru'
    overlay = make_overlay(QtCore.QRect(40, 300, 240, 80), 'en', 'ru',
                           output_region=QtCore.QRect(400, 400, 300, 100))
    try:
        controls = overlay.controls
        QTest.keyClick(controls, QtCore.Qt.Key_F1)
        for _ in range(3):
            app.processEvents()
        dialog = app._keyboard_navigation._help_dialog
        assert dialog is not None and dialog.isVisible()
        assert dialog.windowTitle() == keyboard.text('ru', 'title')
    finally:
        overlay.close()


def test_closing_capture_before_queued_f1_does_not_leave_a_help_window(capture, app):
    _, _, _, create = capture
    value = create()
    navigation = app._keyboard_navigation
    QTest.keyClick(value, QtCore.Qt.Key_F1)
    assert navigation._help_pending
    value.close()
    app.processEvents()
    assert not navigation._help_pending
    assert navigation._help_dialog is None


def test_f1_real_dialog_releases_focus_after_the_originating_control_is_deleted(app):
    keyboard.install_keyboard_navigation(app)
    owner = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(owner)
    origin = QtWidgets.QPushButton('Origin')
    fallback = QtWidgets.QPushButton('Fallback')
    layout.addWidget(origin)
    layout.addWidget(fallback)
    owner.show()
    app.processEvents()
    keyboard.focus_control(origin)
    QTest.keyClick(origin, QtCore.Qt.Key_F1)
    for _ in range(3):
        app.processEvents()
    dialog = app._keyboard_navigation._help_dialog
    assert dialog is not None and dialog.isVisible()
    origin.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    QTest.keyClick(dialog, QtCore.Qt.Key_Escape)
    app.processEvents()
    assert app._keyboard_navigation._help_dialog is None
    assert owner.isVisible() and fallback.isEnabled()
    owner.close()
    owner.deleteLater()


@pytest.mark.parametrize('copy_mode', [False, True])
def test_deleting_displayed_history_after_retention_shift_removes_the_displayed_record(window, app, tmp_path, monkeypatch, copy_mode):
    def record(name):
        if copy_mode:
            return dict(timestamp='2026-10-24T12:00:'+name, text=name)
        return dict(timestamp='2026-10-24T12:00:'+name, original=name, translated='Translated '+name, language='en')
    path = tmp_path/('copy_history.json' if copy_mode else 'translation_history.json')
    first, displayed, newest = (record(name) for name in ('A','B','C'))
    path.write_text(json.dumps([first,displayed]), encoding='utf-8')
    monkeypatch.setattr(settings_module, 'get_data_file', lambda filename: str(path))
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(1)
    (settings.show_copy_history_view if copy_mode else settings.show_history_view)()
    app.processEvents()
    cards = settings.copy_history_record_cards if copy_mode else settings.history_record_cards
    # Another OCR result has evicted the oldest retained row while this UI is open.
    path.write_text(json.dumps([displayed,newest]), encoding='utf-8')
    cards[0].findChild(QtWidgets.QPushButton, 'historyDeleteButton').click()
    app.processEvents()
    assert json.loads(path.read_text(encoding='utf-8')) == [newest]


def test_history_save_preserves_an_unrelated_temporary_file(tmp_path):
    path = tmp_path/'translation_history.json'
    path.write_text('[]', encoding='utf-8')
    unrelated = tmp_path/'translation_history.json.tmp'
    unrelated.write_text('unrelated data', encoding='utf-8')
    settings_module.SettingsWindow._write_history_records(str(path), [dict(original='new')])
    assert json.loads(path.read_text(encoding='utf-8')) == [dict(original='new')]
    assert unrelated.read_text(encoding='utf-8') == 'unrelated data'


@pytest.mark.parametrize('copy_mode', [False, True])
def test_recording_new_history_does_not_replace_a_corrupt_existing_file(tmp_path, monkeypatch, copy_mode):
    path = tmp_path/'history.json'
    original = '{ an incomplete history from an interrupted write'
    path.write_text(original, encoding='utf-8')
    if copy_mode:
        monkeypatch.setattr(main, 'get_cached_config', lambda: {'copy_history':True})
        monkeypatch.setattr(main, 'get_data_file', lambda filename: str(path))
        main._save_copy_history_sync('New copy')
    else:
        monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: {'history':True})
        monkeypatch.setattr(ocr, 'get_data_file', lambda filename: str(path))
        ocr._save_translation_history_sync('New source','New translation','en')
    assert path.read_text(encoding='utf-8') == original


@pytest.mark.parametrize('copy_mode', [False, True])
def test_history_deletion_ignores_a_card_whose_record_has_already_gone(window, app, tmp_path, monkeypatch, copy_mode):
    path = tmp_path/'history.json'
    removed = dict(timestamp='2026-10-24T12:00:00', text='Already removed')
    remaining = dict(timestamp='2026-10-24T12:01:00', text='Keep me')
    path.write_text(json.dumps([removed]), encoding='utf-8')
    monkeypatch.setattr(settings_module, 'get_data_file', lambda _name: str(path))
    window.show_settings()
    settings = window.settings_window
    (settings.show_copy_history_view if copy_mode else settings.show_history_view)()
    app.processEvents()
    cards = settings.copy_history_record_cards if copy_mode else settings.history_record_cards
    path.write_text(json.dumps([remaining]), encoding='utf-8')
    cards[0].findChild(QtWidgets.QPushButton, 'historyDeleteButton').click()
    assert json.loads(path.read_text(encoding='utf-8')) == [remaining]


@pytest.mark.parametrize('payload', ['{broken', '{"unexpected":"object"}', '', 'null'])
def test_invalid_history_is_preserved_and_the_save_refusal_is_logged(tmp_path, monkeypatch, caplog, payload):
    path = tmp_path/'history.json'
    path.write_text(payload, encoding='utf-8')
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: {'history':True})
    monkeypatch.setattr(ocr, 'get_data_file', lambda _name: str(path))
    ocr._save_translation_history_sync('Sensitive source', 'Sensitive translation', 'ar')
    assert path.read_text(encoding='utf-8') == payload
    assert 'existing data preserved' in caplog.text
    assert 'Sensitive' not in caplog.text


@pytest.mark.parametrize('copy_mode', [False, True])
def test_real_history_writer_retains_the_newest_500_records(tmp_path, monkeypatch, copy_mode):
    path = tmp_path/'history.json'
    old = [dict(text=str(index), original=str(index)) for index in range(500)]
    path.write_text(json.dumps(old), encoding='utf-8')
    if copy_mode:
        monkeypatch.setattr(main, 'get_cached_config', lambda: {'copy_history':True})
        monkeypatch.setattr(main, 'get_data_file', lambda _name: str(path))
        main._save_copy_history_sync('Newest')
        main._save_copy_history_sync('Newest')  # Consecutive copies deduplicate.
    else:
        monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: {'history':True})
        monkeypatch.setattr(ocr, 'get_data_file', lambda _name: str(path))
        ocr._save_translation_history_sync('Newest', 'Translated', 'ar')
    records = json.loads(path.read_text(encoding='utf-8'))
    assert len(records) == 500
    assert records[:-1] == old[1:]
    assert records[-1]['text' if copy_mode else 'original'] == 'Newest'


def test_history_atomic_replace_failure_preserves_the_previous_document(tmp_path, monkeypatch):
    import atomic_storage
    path = tmp_path/'history.json'
    previous = '[{"original":"Keep this"}]'
    path.write_text(previous, encoding='utf-8')
    def refuse_replace(*_args):
        raise PermissionError('An isolated sharing violation')
    monkeypatch.setattr(atomic_storage.os, 'replace', refuse_replace)
    with pytest.raises(PermissionError):
        history_storage.append_record(path, dict(original='New'))
    assert path.read_text(encoding='utf-8') == previous
    assert not list(tmp_path.glob('.cnt-save-*.tmp'))


def test_concurrent_history_writers_do_not_lose_records(tmp_path):
    path = tmp_path/'history.json'
    def add(index):
        history_storage.append_record(path, dict(original=f'Record {index}'))
    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(add, range(120)))
    records = json.loads(path.read_text(encoding='utf-8'))
    assert len(records) == 120
    assert {record['original'] for record in records} == {f'Record {index}' for index in range(120)}


def test_independent_processes_share_the_history_lock(tmp_path):
    path = tmp_path/'history.json'
    source = str(Path(history_storage.__file__).parent)
    processes = []
    for worker in range(3):
        code = (f'import sys; sys.path.insert(0, {source!r}); '
                'from history_storage import append_record; '
                f'[append_record({str(path)!r}, {{"original": "{worker}:"+str(index)}}) for index in range(35)]')
        processes.append(subprocess.Popen([sys.executable, '-X', 'utf8', '-c', code],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
    try:
        for process in processes:
            _out, errors = process.communicate(timeout=20)
            assert process.returncode == 0, errors
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate()
    records = json.loads(path.read_text(encoding='utf-8'))
    assert len(records) == 105
    assert {record['original'] for record in records} == {f'{worker}:{index}' for worker in range(3) for index in range(35)}


@pytest.mark.parametrize('locale', ['en', 'ar', 'pt', 'it', 'tr', 'hi', 'id'])
def test_real_settings_export_and_import_round_trip(window, app, tmp_path, monkeypatch, locale):
    window.show_settings()
    settings = window.settings_window
    path = tmp_path/'exported-settings.json'
    notices = []
    monkeypatch.setattr(settings_module.QtWidgets.QFileDialog, 'getSaveFileName', lambda *_args: (str(path), ''))
    monkeypatch.setattr(settings_module.QtWidgets.QFileDialog, 'getOpenFileName', lambda *_args: (str(path), ''))
    monkeypatch.setattr(settings_module.QMessageBox, 'information', lambda *_args: notices.append(_args))
    monkeypatch.setattr(settings_module.QMessageBox, 'warning', lambda *_args: pytest.fail('Unexpected transfer warning'))
    monkeypatch.setattr(window, 'set_autostart', lambda _enabled: False)
    monkeypatch.setattr(window, 'restart_all_hotkey_listeners', lambda: None)
    window.config.update(interface_language=locale, theme='Светлая',
                         ui_scale_percent=100, history=False,
                         remember_translate_area=True,
                         provider_api_key='Never export this test credential')
    assert settings.export_settings() == path
    exported = json.loads(path.read_text(encoding='utf-8'))
    assert 'provider_api_key' not in exported['settings']
    assert exported['settings']['interface_language'] == locale
    window.config.update(interface_language='en', theme='Темная', history=True, remember_translate_area=False)
    assert settings.import_settings() == path
    app.processEvents()
    assert window.current_interface_language == locale
    assert window.current_theme == 'Светлая'
    assert window.config['history'] is False
    assert window.config['remember_translate_area'] is True
    assert settings.settings_pages.currentIndex() == 0
    assert len(notices) == 2


@pytest.mark.parametrize('content', [b'{invalid', b'[]', b'\xff', b'X'*(1024*1024+1)],
                         ids=['malformed-json', 'wrong-shape', 'invalid-utf8', 'over-one-mb'])
def test_real_import_rejects_bad_files_without_changing_live_preferences(window, tmp_path, monkeypatch, content):
    window.show_settings()
    settings = window.settings_window
    path = tmp_path/'invalid-settings.json'
    path.write_bytes(content)
    before = json.loads(json.dumps(window.config))
    notices = []
    monkeypatch.setattr(settings_module.QtWidgets.QFileDialog, 'getOpenFileName', lambda *_args: (str(path), ''))
    monkeypatch.setattr(settings_module.QMessageBox, 'warning', lambda *_args: notices.append(_args))
    assert settings.import_settings() is None
    assert window.config == before
    assert len(notices) == 1


@pytest.mark.parametrize('state', ['available', 'hidden', 'disabled', 'deleted'])
def test_f6_prefers_the_source_language_and_safely_falls_back(app, state):
    keyboard.install_keyboard_navigation(app)
    canvas = QtWidgets.QDialog()
    canvas.setProperty('keyboardCanvas', True)
    canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
    layout = QtWidgets.QHBoxLayout(canvas)
    first = QtWidgets.QToolButton(canvas)
    first.setText('Other tool')
    canvas.lang_combo = QtWidgets.QComboBox(canvas)
    canvas.lang_combo.addItem('English')
    layout.addWidget(first)
    layout.addWidget(canvas.lang_combo)
    canvas.show()
    app.processEvents()
    if state == 'hidden':
        canvas.lang_combo.hide()
    elif state == 'disabled':
        canvas.lang_combo.setEnabled(False)
    elif state == 'deleted':
        sip.delete(canvas.lang_combo)
    try:
        canvas.setFocus(QtCore.Qt.TabFocusReason)
        QTest.keyClick(canvas, QtCore.Qt.Key_F6)
        assert canvas.focusWidget() is (canvas.lang_combo if state == 'available' else first)
        QTest.keyClick(canvas.focusWidget(), QtCore.Qt.Key_F6)
        assert canvas.focusWidget() is canvas
    finally:
        canvas.close()
        canvas.deleteLater()


def test_two_first_copy_results_do_not_reinitialize_each_others_history(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'get_cached_config', lambda: {'copy_history':True})
    monkeypatch.setattr(main, 'get_portable_dir', lambda: str(tmp_path))
    late_creator_ready = threading.Event()
    first_result_saved = threading.Event()
    def delayed_initial_creation(path, mode='r', *args, **kwargs):
        if mode == 'w' and threading.current_thread().name == 'Late history creator':
            late_creator_ready.set()
            assert first_result_saved.wait(5)
        return builtins.open(path, mode, *args, **kwargs)
    monkeypatch.setattr(main, 'open', delayed_initial_creation, raising=False)
    late = threading.Thread(target=main._save_copy_history_sync, args=('Second result',),
                            name='Late history creator')
    late.start()
    try:
        late_creator_ready.wait(0.25)
        main._save_copy_history_sync('First result')
    finally:
        first_result_saved.set()
        late.join(5)
    assert not late.is_alive()
    path = tmp_path/'data'/'copy_history.json'
    assert {record['text'] for record in json.loads(path.read_text(encoding='utf-8'))} == {'First result', 'Second result'}


@pytest.mark.parametrize('copy_mode', [False, True])
def test_opening_an_empty_history_does_not_initialize_a_file_outside_the_writer_lock(window, tmp_path, monkeypatch, copy_mode):
    path = tmp_path/'history.json'
    monkeypatch.setattr(settings_module, 'get_data_file', lambda _name: str(path))
    window.show_settings()
    settings = window.settings_window
    (settings.show_copy_history_view if copy_mode else settings.show_history_view)()
    label = settings.copy_history_count_label if copy_mode else settings.history_count_label
    assert label.text() == '0'
    assert not path.exists()


@pytest.mark.parametrize('copy_mode', [False, True])
@pytest.mark.parametrize('payload', ['{incomplete', '{"unexpected":"object"}'])
def test_history_ui_reports_corruption_and_preserves_the_file_on_clear(window, tmp_path, monkeypatch, copy_mode, payload):
    path = tmp_path/'history.json'
    path.write_text(payload, encoding='utf-8')
    notices = []
    monkeypatch.setattr(settings_module, 'get_data_file', lambda _name: str(path))
    monkeypatch.setattr(settings_module.QMessageBox, 'warning', lambda *_args: notices.append(_args))
    window.show_settings()
    settings = window.settings_window
    (settings.show_copy_history_view if copy_mode else settings.show_history_view)()
    label = settings.copy_history_count_label if copy_mode else settings.history_count_label
    assert label.text() == '!'
    (settings.clear_copy_history if copy_mode else settings.clear_history)()
    assert len(notices) == 1
    assert path.read_text(encoding='utf-8') == payload


@pytest.mark.parametrize('target_name', ['view', 'text_input', 'flag_button'])
@pytest.mark.parametrize('command,key,native_vk,scan,text', [
    ('settings', 0x0411, 0xBC, 0x33, 'б'),  # Ctrl+, on the Russian layout.
    ('open', 0x0429, 0x4F, 0x18, 'щ'),      # Ctrl+O on the Russian layout.
])
def test_windows_internal_shortcuts_use_native_keys_on_a_non_latin_layout(window, app, monkeypatch, target_name, command, key, native_vk, scan, text):
    calls = []
    monkeypatch.setattr(window, '_choose_document_from_main', lambda: calls.append('open'))
    target = window._ui_scale_controller.view if target_name == 'view' else getattr(window, target_name)
    keyboard.focus_control(target)
    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.ControlModifier,
                           scan, native_vk, 0x0002, text)
    app.sendEvent(target, event)
    app.processEvents()
    if command == 'settings':
        assert window.settings_window is not None
        assert window.settings_window._settings_page_index == 0
        assert not calls
    else:
        assert calls == ['open']
        assert window.settings_window is None


@pytest.mark.parametrize('modifiers', [QtCore.Qt.NoModifier, QtCore.Qt.ShiftModifier,
    QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier,
    QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier,
    QtCore.Qt.ControlModifier | QtCore.Qt.MetaModifier],
    ids=['typing', 'shift-typing', 'altgr', 'ctrl-shift', 'ctrl-meta'])
@pytest.mark.parametrize('key,native_vk,text', [(0x0411, 0xBC, 'б'), (0x0429, 0x4F, 'щ')])
def test_native_app_shortcuts_do_not_hijack_typing_or_altgr(window, app, monkeypatch, modifiers, key, native_vk, text):
    calls = []
    monkeypatch.setattr(window, '_choose_document_from_main', lambda: calls.append('open'))
    window.text_input.clear()
    keyboard.focus_control(window.text_input)
    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, modifiers, 0, native_vk, 0, text)
    app.sendEvent(window.text_input, event)
    assert window.settings_window is None
    assert not calls
    if modifiers in (QtCore.Qt.NoModifier, QtCore.Qt.ShiftModifier):
        assert window.text_input.toPlainText() == text


@pytest.mark.parametrize('platform', ['darwin', 'linux'])
@pytest.mark.parametrize('logical_key,key,native_vk', [(QtCore.Qt.Key_Comma, 0x0411, 0xBC), (QtCore.Qt.Key_O, 0x0429, 0x4F)])
def test_windows_native_shortcut_codes_are_not_reinterpreted_on_other_platforms(monkeypatch, platform, logical_key, key, native_vk):
    monkeypatch.setattr(keyboard, 'sys', SimpleNamespace(platform=platform))
    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.ControlModifier, 0, native_vk, 0, '')
    assert not keyboard.matches_control_shortcut(event, logical_key)
    logical = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, logical_key, QtCore.Qt.ControlModifier)
    assert keyboard.matches_control_shortcut(logical, logical_key)


@pytest.mark.parametrize('key,native_vk,text', [(0x0411, 0xBC, 'б'), (0x0429, 0x4F, 'щ')])
def test_native_shortcut_recording_keeps_control_of_non_latin_keys(window, app, monkeypatch, key, native_vk, text):
    from settings_window import ClearableKeySequenceEdit
    calls = []
    monkeypatch.setattr(window, '_choose_document_from_main', lambda: calls.append('open'))
    window.show_settings()
    settings = window.settings_window
    settings.show_hotkeys_screen()
    app.processEvents()
    editor = settings.findChild(ClearableKeySequenceEdit)
    keyboard.focus_control(editor)
    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.ControlModifier, 0, native_vk, 0, text)
    app.sendEvent(editor, event)
    assert settings._secondary_view_kind == 'hotkeys'
    assert not calls
    assert 'Ctrl' in editor.hotkeyText()


def test_embedded_language_popup_keeps_its_native_arrow_and_end_navigation(window, app):
    keyboard.install_keyboard_navigation(app)
    window.set_ui_scale_percent(200)
    app.processEvents()
    controller = window._ui_scale_controller
    combo = window.target_lang
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton,
                     pos=controller.map_widget_to_view(combo))
    QTest.qWait(app.doubleClickInterval() + 20)
    popup = combo.view().window()
    assert popup.isVisible() and popup.graphicsProxyWidget() is not None
    assert app.activePopupWidget() is None  # The case the native-popup guard misses.
    try:
        QTest.keyClick(controller.view.viewport(), QtCore.Qt.Key_Down)
        QTest.keyClick(controller.view.viewport(), QtCore.Qt.Key_End)
        app.processEvents()
        last = combo.model().index(combo.count() - 1, 0)
        assert combo.view().currentIndex() == last
        assert combo.view().viewport().rect().contains(combo.view().visualRect(last).center())
        QTest.keyClick(controller.view.viewport(), QtCore.Qt.Key_Return)
        app.processEvents()
        assert combo.currentIndex() == last.row()
        assert not popup.isVisible()
    finally:
        combo.hidePopup()


@pytest.mark.parametrize('winerror', [5, 32, 33])
def test_history_publication_retries_only_transient_windows_busy_errors(tmp_path, monkeypatch, winerror):
    import atomic_storage
    path = tmp_path/'history.json'
    path.write_text('[]', encoding='utf-8')
    replace = atomic_storage.os.replace
    attempts, delays = [], []
    def transient_busy(source, target):
        attempts.append(source)
        if len(attempts) < 4:
            error = PermissionError('A temporary isolated Windows sharing/access conflict')
            error.winerror = winerror
            raise error
        return replace(source, target)
    monkeypatch.setattr(atomic_storage.os, 'replace', transient_busy)
    monkeypatch.setattr(atomic_storage, 'time', SimpleNamespace(sleep=delays.append))
    history_storage.append_record(path, dict(original='Keep new and old records'))
    assert len(attempts) == 4 and len(set(attempts)) == 1
    assert len(delays) == 3 and sum(delays) <= 0.5
    assert json.loads(path.read_text(encoding='utf-8')) == [dict(original='Keep new and old records')]
    assert not list(tmp_path.glob('.cnt-save-*.tmp'))


def test_history_publication_stops_retrying_and_preserves_the_original(tmp_path, monkeypatch):
    import atomic_storage
    path = tmp_path/'history.json'
    original = '[{"original":"Keep original data"}]'
    path.write_text(original, encoding='utf-8')
    attempts, delays = [], []
    def busy(source, target):
        attempts.append(source)
        error = PermissionError('An enduring isolated sharing conflict')
        error.winerror = 32
        raise error
    monkeypatch.setattr(atomic_storage.os, 'replace', busy)
    monkeypatch.setattr(atomic_storage, 'time', SimpleNamespace(sleep=delays.append))
    with pytest.raises(PermissionError):
        history_storage.append_record(path, dict(original='New'))
    assert len(attempts) == 8 and len(delays) == 7
    assert sum(delays) <= 0.5
    assert path.read_text(encoding='utf-8') == original
    assert not list(tmp_path.glob('.cnt-save-*.tmp'))


@pytest.mark.parametrize('platform_name,winerror', [('posix', 5), ('nt', 87), ('nt', None)])
def test_atomic_publication_does_not_retry_unrelated_errors(monkeypatch, platform_name, winerror):
    import atomic_storage
    attempts, delays = [], []
    def refused(*_args):
        attempts.append(True)
        error = OSError('An isolated non-retryable failure')
        if winerror is not None:
            error.winerror = winerror
        raise error
    monkeypatch.setattr(atomic_storage, 'os', SimpleNamespace(name=platform_name, replace=refused))
    monkeypatch.setattr(atomic_storage, 'time', SimpleNamespace(sleep=delays.append))
    with pytest.raises(OSError):
        atomic_storage._replace_complete_file('private-temporary', 'private-target')
    assert len(attempts) == 1 and not delays


@pytest.mark.skipif(sys.platform != 'win32', reason='Exercises a real Windows sharing violation')
def test_windows_history_publication_recovers_when_a_reader_releases_the_file(tmp_path, monkeypatch):
    import atomic_storage
    path = tmp_path/'history.json'
    path.write_text('[{"original":"Existing"}]', encoding='utf-8')
    replace = atomic_storage.os.replace
    busy, finished = threading.Event(), threading.Event()
    failures, errors = [], []
    def observed_replace(source, target):
        try:
            return replace(source, target)
        except OSError as error:
            failures.append(getattr(error, 'winerror', None))
            busy.set()
            raise
    monkeypatch.setattr(atomic_storage.os, 'replace', observed_replace)
    def publish():
        try:
            history_storage.append_record(path, dict(original='New'))
        except Exception as error:
            errors.append(error)
        finally:
            finished.set()
    worker = threading.Thread(target=publish)
    with path.open('r', encoding='utf-8'):
        worker.start()
        busy.wait(2)
    worker.join(5)
    assert not worker.is_alive() and finished.is_set()
    assert not errors
    assert failures and set(failures) <= {5, 32, 33}
    assert json.loads(path.read_text(encoding='utf-8')) == [dict(original='Existing'), dict(original='New')]
