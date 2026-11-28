"""A rejected worker launch must release update controls and permit retry."""
import threading
import time
from types import MethodType, SimpleNamespace
from unittest import mock

import pytest

from engine_center import text
import settings_window as settings
from settings_window import OcrLanguageManagerDialog
from test_desktop_ux import app
from test_language_package_manager import _AppParent, _ManagerOwner


def test_check_updates_reuses_a_catalog_being_loaded_when_the_center_opens(app, tmp_path, monkeypatch):
    from PyQt5.QtTest import QTest
    from component_texts import error_text
    from component_catalog import ComponentError

    started, release, waiting = threading.Event(), threading.Event(), threading.Event()
    catalog = {'schema': 1, 'revision': 1, 'artifacts': {}, 'bundles': []}

    def load_catalog(root):
        started.set()
        assert release.wait(5)
        return catalog

    parent = _AppParent()
    owner = _ManagerOwner(parent)
    with mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'):
        dialog = OcrLanguageManagerDialog(owner)
    dialog._initial_probe_timer.stop()
    dialog._initial_catalog_timer.stop()
    lock = dialog._catalog_read_lock

    class ObserveWait:
        def __enter__(self):
            if lock.locked():
                waiting.set()
            lock.acquire()

        def __exit__(self, *_args):
            lock.release()

    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR', str(tmp_path))
    dialog._catalog_read_lock = ObserveWait()
    table = dialog.tesseract_table
    button = next(action for action in table._package_engine_actions if action.property('packageAction') == 'update')
    try:
        with mock.patch('component_catalog.trusted_catalog', side_effect=load_catalog) as load, \
             mock.patch.object(settings, 'managed_install_supported', return_value=True), \
             mock.patch('translater.argos_package_catalog', return_value=[]):
            dialog._start_argos_catalog_refresh(True)
            assert started.wait(3)
            button.trigger()
            assert waiting.wait(3) and not button.isEnabled()
            release.set()
            deadline = time.monotonic() + 5
            while (button.property('packageUpdateChecking') or dialog._argos_catalog_request_active) and time.monotonic() < deadline:
                QTest.qWait(10)
            load.assert_called_once()
            assert button.isEnabled() and not button.property('packageUpdateChecking')
            assert error_text(dialog.lang, ComponentError('no_compatible_update')) in table._package_size_label.text()
    finally:
        release.set()
        dialog.close()
        owner.close()
        parent.close()


def test_package_inventory_does_not_import_or_start_easyocr_to_list_its_languages(app):
    from PyQt5 import QtWidgets
    from settings_window import SettingsWindow

    class Inventory(SettingsWindow):
        def __init__(self):
            QtWidgets.QWidget.__init__(self)

    owner = Inventory()
    probe = SimpleNamespace(owner=owner, _engine_states_ready=mock.Mock(),
                            _emit_runtime_probe_payload=mock.Mock(),
                            _available_windows_tags=mock.Mock(return_value=[]),
                            _windows_ocr_capability_catalog=mock.Mock(return_value={}))
    try:
        with (mock.patch.object(owner, '_easyocr_runtime_installed', return_value=True) as files,
              mock.patch.object(owner, '_easyocr_importable_status', side_effect=AssertionError('loaded EasyOCR')) as heavy,
              mock.patch.object(owner, '_rapidocr_runtime_status', return_value=(False, 'missing')),
              mock.patch('engine_center.installed_states', return_value={})):
            OcrLanguageManagerDialog._runtime_probe_worker(probe)
        heavy.assert_not_called()
        files.assert_called_once_with()
        probe._emit_runtime_probe_payload.assert_any_call({'easyocr': (True, '')})
    finally:
        owner.deleteLater()


def unavailable_thread(point):
    failure = RuntimeError('worker thread unavailable')
    return (mock.Mock(side_effect=failure) if point == 'constructor' else
            mock.Mock(return_value=SimpleNamespace(start=mock.Mock(side_effect=failure))))


@pytest.mark.parametrize('point', ['constructor', 'start'])
def test_engine_update_check_launch_failure_releases_the_button_and_allows_retry(app, point):
    parent = _AppParent()
    owner = _ManagerOwner(parent)
    owner.easyocr_status = (True, '')
    with mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'):
        dialog = OcrLanguageManagerDialog(owner)
    dialog._initial_probe_timer.stop()
    dialog._initial_catalog_timer.stop()
    try:
        table = dialog.easyocr_table
        button = next(action for action in table._package_engine_actions if action.property('packageAction') == 'update')
        install = mock.Mock()
        with mock.patch.object(settings.threading, 'Thread', unavailable_thread(point)):
            dialog._request_update_check(table, button, install)
        app.processEvents()
        assert not button.property('packageUpdateChecking')
        assert button.isEnabled() and button.text() == text('en', 'check_updates')
        assert table._package_update_status and table._package_size_label.text().strip()
        retry = mock.Mock(return_value=SimpleNamespace(start=mock.Mock()))
        with mock.patch.object(settings.threading, 'Thread', retry):
            dialog._request_update_check(table, button, install)
        retry.assert_called_once()
        retry.return_value.start.assert_called_once_with()
        assert button.property('packageUpdateChecking') and not button.isEnabled()
        install.assert_not_called()
        dialog._on_update_plan_ready('easyocr', {'error': 'test cleanup'})
    finally:
        dialog.close()
        owner.close()
        parent.close()


def update_owner():
    owner = SimpleNamespace(parent=SimpleNamespace(current_interface_language='en', _update_flow_active=False),
        _update_cancel_requested=threading.Event(), _update_in_progress=False, _update_phase='idle',
        _update_temp_dir='', _set_update_controls_enabled=mock.Mock(), _show_update_progress=mock.Mock(),
        _check_latest_release_worker=mock.Mock(), _download_and_prepare_update=mock.Mock(),
        _cleanup_update_temp_dir=mock.Mock(), _hide_update_progress=mock.Mock(), _leave_update_page=mock.Mock())
    for name in ('_set_parent_update_flow_active', '_start_update_check', '_start_update_download',
                 '_on_update_check_result', '_on_update_failed', '_on_update_cancelled', '_friendly_update_error'):
        setattr(owner, name, MethodType(getattr(settings.SettingsWindow, name), owner))
    return owner


@pytest.mark.parametrize('operation', ['check', 'download'])
@pytest.mark.parametrize('point', ['constructor', 'start'])
def test_application_update_launch_failure_releases_busy_state_and_allows_retry(operation, point):
    owner = update_owner()
    def start():
        if operation == 'check':
            owner._start_update_check()
        else:
            owner._start_update_download('https://example.invalid/app.zip', 'app.zip', '9.9.9',
                                         'https://example.invalid/app.zip.sha256')
    with mock.patch('inline_update.result') as shown, \
         mock.patch.object(settings.threading, 'Thread', unavailable_thread(point)):
        start()
    assert owner._update_in_progress is False and owner._update_phase == 'idle'
    assert owner.parent._update_flow_active is False
    assert owner._set_update_controls_enabled.call_args.args == (True,)
    shown.assert_called_once()
    retry = mock.Mock(return_value=SimpleNamespace(start=mock.Mock()))
    with mock.patch.object(settings.threading, 'Thread', retry):
        start()
    retry.assert_called_once()
    retry.return_value.start.assert_called_once_with()
    assert owner._update_in_progress and owner.parent._update_flow_active
    assert owner._update_phase == ('checking' if operation == 'check' else 'preparing_download')
    with mock.patch('inline_update.result'):
        owner._on_update_cancelled()
