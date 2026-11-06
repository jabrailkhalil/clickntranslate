"""A rejected worker launch must release update controls and permit retry."""
import threading
from types import MethodType, SimpleNamespace
from unittest import mock

import pytest

from engine_center import text
import settings_window as settings
from settings_window import OcrLanguageManagerDialog
from test_desktop_ux import app
from test_language_package_manager import _AppParent, _ManagerOwner


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
