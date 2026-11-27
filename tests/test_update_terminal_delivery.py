"""An updater operation keeps its controls until its terminal event is delivered."""
import threading
from types import MethodType, SimpleNamespace
from unittest import mock

import pytest
from PyQt5.QtWidgets import QApplication, QPushButton, QStackedWidget, QVBoxLayout, QWidget

import settings_window as settings


@pytest.mark.parametrize('terminal', ['failure', 'cancel'])
def test_download_terminal_delivery_blocks_early_retry_then_allows_a_new_check(tmp_path, monkeypatch, terminal):
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    layout = QVBoxLayout(host)
    update_button = QPushButton('Update', host)
    pages = QStackedWidget(host)
    layout.addWidget(update_button)
    layout.addWidget(pages)
    owner = SimpleNamespace(
        parent=SimpleNamespace(current_interface_language='en', current_theme='Dark', _update_flow_active=False),
        settings_pages=pages, settings_page_tabs=(), update_btn=update_button,
        _update_cancel_requested=threading.Event(), _update_in_progress=False,
        _update_phase='idle', _update_temp_dir='', _update_progress=None,
        _set_settings_page=pages.setCurrentIndex, _leave_update_page=mock.Mock(),
        _check_latest_release_worker=mock.Mock(),
        _launch_apply_updater=mock.Mock(side_effect=AssertionError('real updater forbidden')))
    failure = (OSError('synthetic local download failure') if terminal == 'failure'
               else settings.UpdateCancelledError('synthetic user cancellation'))
    owner._download_file = mock.Mock(side_effect=failure)
    for name in ('_start_update_check', '_start_update_download', '_download_and_prepare_update',
                 '_restore_update_button_after_download', '_on_update_failed', '_on_update_cancelled',
                 '_friendly_update_error', '_cleanup_update_temp_dir', '_set_parent_update_flow_active',
                 '_check_update_cancel_requested', '_set_update_controls_enabled', '_show_update_progress',
                 '_hide_update_progress', '_is_update_cancelable', '_is_update_apply_stage',
                 '_handle_update_progress_close_attempt', '_on_update_progress_text'):
        setattr(owner, name, MethodType(getattr(settings.SettingsWindow, name), owner))
    update_button.clicked.connect(lambda: owner._start_update_check())

    queued, delivered, launches, worker_errors = [], [], [], []
    terminal_name = '_on_update_failed' if terminal == 'failure' else '_on_update_cancelled'
    terminal_post_started, permit_terminal_post = threading.Event(), threading.Event()
    original_mkdtemp = settings.tempfile.mkdtemp
    monkeypatch.setattr(settings.tempfile, 'mkdtemp',
                        lambda *args, **kwargs: original_mkdtemp(*args, **dict(kwargs, dir=tmp_path)))
    monkeypatch.setattr(settings.requests, 'get', mock.Mock(side_effect=AssertionError('network forbidden')))
    monkeypatch.setattr(settings.QtCore, 'Q_ARG', lambda _kind, value: value)

    def invoke(receiver, name, _connection, *values):
        assert receiver is owner
        if name == terminal_name:
            terminal_post_started.set()
            assert permit_terminal_post.wait(5), 'test delivery gate timed out'
        queued.append((name, values))
        return True
    monkeypatch.setattr(settings.QMetaObject, 'invokeMethod', invoke)

    def deliver():
        while queued:
            name, values = queued.pop(0)
            delivered.append(name)
            getattr(owner, name)(*values)
        app.processEvents()

    def fake_thread(*, target, args=(), **_kwargs):
        launches.append((target, args))
        return SimpleNamespace(start=mock.Mock())

    worker = None
    try:
        host.show()  # The regression runner uses the offscreen Qt platform.
        with mock.patch.object(settings.threading, 'Thread', fake_thread):
            owner._start_update_download('https://example.invalid/app.zip', 'app.zip', '9.9.9',
                                         'https://example.invalid/app.zip.sha256')
        app.processEvents()
        assert owner._update_progress.progress.isVisible()
        assert not update_button.isEnabled()
        target, arguments = launches.pop()

        def old_worker():
            try:
                target(*arguments)
            except BaseException as error:
                worker_errors.append(error)
        worker = threading.Thread(target=old_worker, name='private-updater-delivery-probe')
        worker.start()
        assert terminal_post_started.wait(5)
        deliver()
        with mock.patch.object(settings.threading, 'Thread', fake_thread):
            update_button.click()
        prematurely_accepted = bool(launches)
        before_old_terminal = owner._update_in_progress, owner._update_phase
        permit_terminal_post.set()
        worker.join(6)
        assert not worker.is_alive() and not worker_errors
        deliver()
        page = owner._update_progress
        assert not prematurely_accepted, {
            'new_check_before_old_terminal': before_old_terminal,
            'new_check_after_old_terminal': (owner._update_in_progress, owner._update_phase),
            'visible_result': page.label.text()}
        assert delivered.count(terminal_name) == 1
        assert not owner._update_in_progress and owner._update_phase == 'idle'
        assert not owner.parent._update_flow_active
        assert update_button.isEnabled() and page.progress.isHidden()
        assert page.label.isVisible() and page.label.text().strip()
        assert page.primary.isVisible() and page.primary.isEnabled()
        if terminal == 'failure':
            assert page.primary.text() == settings.settings_text('en', 'update')
            assert 'synthetic local download failure' not in page.label.text()
            assert page.secondary.isVisible() and page.secondary.isEnabled()
        else:
            assert page.label.text() == settings.update_text('en', 'cancelled')
        with mock.patch.object(settings.threading, 'Thread', fake_thread):
            (page.primary if terminal == 'failure' else update_button).click()
        assert len(launches) == 1
        assert owner._update_in_progress and owner._update_phase == 'checking'
        assert owner.parent._update_flow_active and not update_button.isEnabled()
        assert page.progress.isVisible()
        assert page.label.text() == settings.update_text('en', 'checking')
        assert not queued and delivered.count(terminal_name) == 1
        owner._launch_apply_updater.assert_not_called()
    finally:
        permit_terminal_post.set()
        if worker is not None:
            worker.join(6)
            assert not worker.is_alive()
        host.close()
        host.deleteLater()
        app.processEvents()
