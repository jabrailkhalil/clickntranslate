"""Waiting UI stays responsive, then releases controls on every terminal path."""
import threading
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from ui_operations import UiOperation, OperationIndicator, TEXT, FAILURE_TEXT, operation_for
from test_desktop_ux import app, window


def wait_until(app, condition, timeout=4000):
    timer = QtCore.QElapsedTimer()
    timer.start()
    while not condition() and timer.elapsed() < timeout:
        app.processEvents()
        QTest.qWait(5)
    assert condition()


@pytest.fixture
def owner(app):
    widget = QtWidgets.QWidget()
    widget.resize(700, 400)
    widget.current_theme = 'Темная'
    widget.current_interface_language = 'en'
    widget.show()
    yield widget
    operation = getattr(widget, '_ui_operation', None)
    if operation is not None:
        operation.cancel()
    widget.close()
    widget.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_idle_and_fast_operations_never_start_a_spinner_or_thread(owner, app, monkeypatch):
    thread = mock.Mock(side_effect=AssertionError('No file job was requested'))
    monkeypatch.setattr('ui_operations.threading.Thread', thread)
    operation = operation_for(owner)
    assert not operation.active and operation._indicator is None
    assert not operation._delay.isActive() and not operation._next.isActive()
    results = []
    def stages(_value):
        yield 'theme'
        return 42
    assert operation.start('theme', steps=stages, done=results.append)
    wait_until(app, lambda: not operation.active)
    assert results == [42] and owner.isEnabled()
    assert operation._result is None
    assert operation._indicator is None
    assert not operation._delay.isActive() and not operation._next.isActive()
    thread.assert_not_called()


def test_file_wait_animates_without_a_popup_and_completes_on_the_gui_thread(owner, app):
    started, release = threading.Event(), threading.Event()
    threads, results, pulses = [], [], []
    def work():
        threads.append(QtCore.QThread.currentThread())
        started.set()
        assert release.wait(3)
        return 'saved'
    operation = operation_for(owner)
    operation.DELAY_MS = 0
    original_cursor = owner.cursor().shape()
    original_cursor_attribute = owner.testAttribute(QtCore.Qt.WA_SetCursor)
    before = set(QtWidgets.QApplication.topLevelWidgets())
    heartbeat = QtCore.QTimer(owner)
    heartbeat.timeout.connect(lambda: pulses.append(1))
    heartbeat.start(10)
    try:
        assert operation.start('export', work=work,
            done=lambda result: results.append((result, QtCore.QThread.currentThread(), owner.isEnabled())))
        assert not operation.start('theme')  # Never enqueue another mutation while a file job owns the UI.
        wait_until(app, lambda: started.is_set() and operation._indicator is not None and operation._indicator.isVisible())
        indicator = operation._indicator
        assert indicator.parentWidget() is owner and not indicator.isWindow()
        assert set(QtWidgets.QApplication.topLevelWidgets()) == before
        first = indicator.grab().toImage()
        QTest.qWait(110)
        assert pulses and indicator.grab().toImage() != first
        assert indicator.accessibleName() == TEXT['en'][2]
        assert owner.isEnabled()  # Busy input is gated without dimming/repolishing the entire interface.
        clicks = []
        button = QtWidgets.QPushButton('Busy action', owner)
        button.clicked.connect(lambda: clicks.append(1))
        button.show()
        QTest.mouseClick(button, QtCore.Qt.LeftButton)
        assert clicks == []
        release.set()
        wait_until(app, lambda: not operation.active)
        assert results == [('saved', app.thread(), True)]
        assert operation._result is None
        assert threads[0] != app.thread()
        assert not indicator.isVisible() and not indicator._animation.isActive()
        QTest.mouseClick(button, QtCore.Qt.LeftButton)
        assert clicks == [1]
        assert owner.cursor().shape() == original_cursor
        assert owner.testAttribute(QtCore.Qt.WA_SetCursor) == original_cursor_attribute
    finally:
        release.set()
        heartbeat.stop()


@pytest.mark.parametrize('failure', ['file', 'stage', 'thread_start'])
def test_failures_restore_the_original_controls_cursor_and_report_once(owner, app, monkeypatch, failure):
    owner.setCursor(QtCore.Qt.CrossCursor)
    errors = []
    def explode():
        raise OSError('disk not available')
    def stages(_value):
        yield 'settings'
        explode()
    operation = operation_for(owner)
    if failure == 'thread_start':
        monkeypatch.setattr('ui_operations.threading.Thread', mock.Mock(side_effect=OSError('thread start')))
    assert operation.start('import', work=explode if failure != 'stage' else None,
                           steps=stages if failure == 'stage' else None, failed=errors.append)
    wait_until(app, lambda: not operation.active)
    assert len(errors) == 1 and isinstance(errors[0], OSError)
    assert owner.isEnabled() and owner.cursor().shape() == QtCore.Qt.CrossCursor
    assert not operation._delay.isActive() and not operation._next.isActive()


def test_a_cancelled_worker_cannot_finish_or_hide_a_new_operation(owner, app):
    first_release, second_release = threading.Event(), threading.Event()
    old_finished = threading.Event()
    results = []
    def old_work():
        assert first_release.wait(3)
        old_finished.set()
        return 'old'
    def new_work():
        assert second_release.wait(3)
        return 'new'
    operation = operation_for(owner)
    try:
        operation.start('import', work=old_work, done=results.append)
        operation.cancel()
        operation.start('export', work=new_work, done=results.append)
        first_release.set()
        wait_until(app, old_finished.is_set)
        QTest.qWait(25)
        assert operation.active and owner.isEnabled() and results == []
        second_release.set()
        wait_until(app, lambda: not operation.active)
        assert results == ['new'] and owner.isEnabled()
    finally:
        first_release.set()
        second_release.set()


def test_theme_button_keeps_feedback_alive_but_freezes_content_and_open_dialog(window, app):
    from runtime_metrics import snapshot
    window.show_settings()
    dialog = QtWidgets.QDialog(window)
    dialog.show()
    app.processEvents()
    observed = []
    original = window.settings_window.apply_theme
    count_before = snapshot().get('ui.theme', {}).get('count', 0)
    def inspect_theme_stage():
        observed.append((window.updatesEnabled(), window.ui_root.updatesEnabled(),
                         window.central_widget.updatesEnabled(), dialog.updatesEnabled()))
        original()
    try:
        with mock.patch.object(window.settings_window, 'apply_theme', side_effect=inspect_theme_stage):
            window.theme_button.click()
            wait_until(app, lambda: not window._ui_operation.active)
        assert observed == [(True, False, False, False)]
        assert snapshot()['ui.theme']['count'] == count_before+1
        assert window.central_widget.updatesEnabled() and dialog.updatesEnabled()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_modal_prompts_remain_dismissible_during_a_pending_operation(owner, app):
    release = threading.Event()
    operation = operation_for(owner)
    operation.start('import', work=lambda: release.wait(3))
    dialog = QtWidgets.QDialog(owner)
    dialog.setWindowModality(QtCore.Qt.WindowModal)
    button = QtWidgets.QPushButton('Continue', dialog)
    button.clicked.connect(dialog.accept)
    dialog.show()
    app.processEvents()
    try:
        assert QtWidgets.QApplication.activeModalWidget() is dialog
        QTest.mouseClick(button, QtCore.Qt.LeftButton)
        assert not dialog.isVisible()
    finally:
        dialog.close()
        dialog.deleteLater()
        release.set()
        wait_until(app, lambda: not operation.active)


def test_destroying_the_owner_cancels_its_feedback_and_ignores_the_file_reply(app, monkeypatch):
    import sys
    from PyQt5 import sip
    errors, results = [], []
    monkeypatch.setattr(sys, 'excepthook', lambda *error: errors.append(error))
    widget = QtWidgets.QWidget()
    widget.resize(700, 400)
    widget.show()
    release, finished = threading.Event(), threading.Event()
    def work():
        try:
            return release.wait(3)
        finally:
            finished.set()
    operation = operation_for(widget)
    operation.DELAY_MS = 0
    try:
        operation.start('export', work=work, done=results.append)
        wait_until(app, lambda: operation._indicator is not None and operation._indicator.isVisible())
        widget.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        assert sip.isdeleted(widget) and not operation.active
        release.set()
        wait_until(app, finished.is_set)
        QTest.qWait(20)
        assert results == [] and errors == []
    finally:
        release.set()


def test_theme_write_failure_keeps_the_previous_visible_theme_and_releases_input(window, app):
    import main
    original = window.current_theme
    stored = window.config.get('theme')
    background = window._ui_scale_controller.scene.backgroundBrush().color()
    def failed_write():
        window.config['theme'] = window.current_theme
        raise PermissionError('settings are locked')
    with (mock.patch.object(window, 'save_config', side_effect=failed_write),
          mock.patch.object(main.QMessageBox, 'warning') as warning):
        window.theme_button.click()
        wait_until(app, lambda: not window._ui_operation.active)
    assert window.current_theme == original and window.config.get('theme') == stored
    assert window._ui_scale_controller.scene.backgroundBrush().color() == background
    assert window.ui_root.updatesEnabled() and window.central_widget.updatesEnabled()
    warning.assert_called_once()


def test_theme_gui_stages_retain_cached_content_until_complete(window, app):
    if app.platformName().split(':')[0] != 'offscreen':
        pytest.skip('Reads only the isolated Qt offscreen backing store')
    from ui_scaling import widget_global_rect
    from ui_operations import consume_steps
    window.show_settings()
    app.processEvents()
    window.grab()  # Populate the backing store before starting the transaction.
    area = widget_global_rect(window.central_widget)
    area.translate(-window.mapToGlobal(QtCore.QPoint()))
    area.adjust(3, 3, -3, -3)
    screen = app.primaryScreen()
    before = screen.grabWindow(int(window.winId())).toImage().copy(area)
    assert not before.isNull()
    stages = window._theme_change_steps(keep_header_live=True)
    try:
        next(stages)  # Commit the preference.
        next(stages)  # Restyle the main window, before restyling Settings.
        for _ in range(4):
            app.processEvents()
        during = screen.grabWindow(int(window.winId())).toImage().copy(area)
        assert during == before, 'The title may update; content must retain one complete theme frame.'
        consume_steps(stages)
        for _ in range(4):
            app.processEvents()
        after = screen.grabWindow(int(window.winId())).toImage().copy(area)
        assert after != before
    finally:
        stages.close()


@pytest.mark.parametrize('locale', tuple(TEXT))
@pytest.mark.parametrize('theme', ('Темная', 'Светлая'))
def test_progress_labels_frames_and_animation_fit_both_directions(owner, app, locale, theme):
    owner.current_theme, owner.current_interface_language = theme, locale
    owner.setLayoutDirection(QtCore.Qt.RightToLeft if locale == 'ar' else QtCore.Qt.LeftToRight)
    indicator = OperationIndicator(owner)
    try:
        for phase in ('theme', 'import', 'export', 'settings'):
            indicator.phase = phase
            indicator.show()
            app.processEvents()
            assert owner.rect().contains(indicator.geometry())
            assert indicator.accessibleName().strip() and FAILURE_TEXT[locale].strip()
            image = indicator.grab().toImage()
            middle = image.height()//2
            assert image.pixelColor(0, middle) != image.pixelColor(image.width()//2, middle)
            assert image.pixelColor(image.width()-1, middle) != image.pixelColor(image.width()//2, middle)
            indicator.hide()
            assert not indicator._animation.isActive()
    finally:
        indicator.deleteLater()
