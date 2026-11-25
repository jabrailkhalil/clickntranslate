"""Bundle downloads and language jobs keep one visible, cancellable lane."""
from pathlib import Path
import sys
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

from test_desktop_ux import app, window
from test_engine_center_workflow import _manager
from settings_window import OcrLanguageManagerDialog, SettingsWindow
from window_appearance import install_window_appearance


@pytest.fixture
def downloads(window, app):
    window.show_settings()
    settings = window.settings_window
    dialog = _manager(settings)
    settings._language_manager_dialog = dialog
    dialog.show()
    app.processEvents()
    yield settings, dialog
    for engine in ('tesseract', 'rapidocr', 'easyocr', 'hymt'):
        setattr(settings, '_' + engine + '_install_in_progress', False)
    dialog._install_in_progress = False
    for attr in ('progress', 'rapidocr_progress', 'easyocr_progress', 'hymt_progress'):
        popup = getattr(settings, attr, None)
        if popup is not None:
            popup.hide()
    dialog.close()


def test_bundle_progress_survives_background_and_switching_sections(downloads, app):
    settings, dialog = downloads
    with mock.patch('settings_window.threading.Thread.start'):
        settings.start_hymt_install(progress_owner=dialog, select_on_success=False)
    settings._on_hymt_progress('Downloading model: 40 MB / 100 MB', 40, True)
    settings.hymt_progress._continue_in_background()
    for section in (0, 2, 1):
        dialog.tabs.setCurrentIndex(section)
        app.processEvents()
        assert dialog.task_status_label.isVisible()
        assert '40 MB' in dialog.task_status_label.text()
        assert dialog.task_progress.isVisible() and dialog.task_progress.value() == 40
        assert dialog.task_cancel_button.isVisible() and dialog.task_cancel_button.isEnabled()
        assert not settings.hymt_progress.isVisible()
        assert not dialog.refresh_btn.isEnabled()
    dialog.task_show_button.click()
    assert settings.hymt_progress.isVisible()
    settings.hymt_progress._continue_in_background()
    dialog.task_cancel_button.click()
    assert settings._hymt_cancel_requested.is_set()
    assert not dialog.task_cancel_button.isEnabled()
    assert not settings.hymt_progress.isVisible()


def test_bundle_blocks_language_job_and_other_bundle_until_finish(downloads):
    settings, dialog = downloads
    with mock.patch('settings_window.threading.Thread.start') as start:
        settings.start_hymt_install(progress_owner=dialog, select_on_success=False)
        assert start.call_count == 1
        settings.start_rapidocr_install(progress_owner=dialog)
        dialog._run_language_task('Argos', ['es_en'], lambda codes: None)
        assert start.call_count == 1
        assert not dialog._install_in_progress
    settings._finish_hymt_install_state()
    settings._hide_hymt_progress()
    settings._report_engine_task('hymt', 'Cancelled', kind='idle')
    assert not dialog.task_cancel_button.isVisible()
    assert not dialog.task_progress.isVisible()
    assert dialog.refresh_btn.isEnabled()


def test_language_job_blocks_all_bundle_install_entry_points(downloads):
    settings, dialog = downloads
    dialog._install_in_progress = True
    with mock.patch('settings_window.threading.Thread.start') as start:
        for engine in ('tesseract', 'rapidocr', 'easyocr', 'hymt'):
            getattr(settings, 'start_' + engine + '_install')()
        start.assert_not_called()
    assert not any(getattr(settings, '_' + engine + '_install_in_progress')
                   for engine in ('tesseract', 'rapidocr', 'easyocr', 'hymt'))


def test_direct_main_argos_package_download_blocks_bundle_installs(downloads):
    settings, dialog = downloads
    settings.parent._main_translation_running = True
    settings.parent._argos_install_required = True
    try:
        with mock.patch('settings_window.threading.Thread.start') as start:
            settings.start_hymt_install(progress_owner=dialog)
            dialog._run_language_task('Tesseract', ['eng'], lambda codes: None)
            start.assert_not_called()
        assert not settings._hymt_install_in_progress
        assert not dialog._install_in_progress
    finally:
        settings.parent._main_translation_running = False
        settings.parent._argos_install_required = False


def test_main_argos_download_uses_the_same_background_cancel_and_restore(downloads):
    settings, dialog = downloads
    main = settings.parent
    main._main_translation_running = True
    main._argos_install_required = True
    main._argos_cancel_enabled = True
    main._argos_cancel_requested.clear()
    try:
        main._show_argos_progress('Argos: downloading model', 50, True)
        main._argos_progress._continue_in_background()
        dialog._show_task_status('Argos: downloading model', 50)
        assert dialog.task_cancel_button.isEnabled()
        main._argos_cancel_enabled = False
        dialog._show_task_status('Argos: applying model')
        assert not dialog.task_cancel_button.isEnabled()
        dialog._cancel_active_task()
        assert not main._argos_cancel_requested.is_set()
        assert 'Canceling' not in dialog.task_cancel_button.text()
        main._argos_cancel_enabled = True
        dialog._show_task_status('Argos: downloading model', 50)
        dialog.task_show_button.click()
        assert main._argos_progress.isVisible()
        main._argos_progress._continue_in_background()
        dialog.task_cancel_button.click()
        assert main._argos_cancel_requested.is_set()
        assert not dialog.task_cancel_button.isEnabled()
        assert not main._argos_progress.isVisible()
    finally:
        main._main_translation_running = False
        main._argos_install_required = False
        if main._argos_progress is not None:
            main._argos_progress.hide()


def test_failed_worker_launch_releases_busy_state(downloads):
    settings, dialog = downloads
    with mock.patch('settings_window.threading.Thread.start', side_effect=RuntimeError('No worker available')), \
         mock.patch('settings_window.QMessageBox.warning'):
        settings.start_hymt_install(progress_owner=dialog, select_on_success=False)
    assert not settings._hymt_install_in_progress
    assert dialog.refresh_btn.isEnabled()
    assert not dialog.task_cancel_button.isVisible()
    assert settings._language_package_task_state['kind'] == 'failed'
    assert 'No worker available' in dialog.task_status_label.text()


@pytest.mark.parametrize('terminal', ['success', 'failure', 'unavailable', 'cancelled'])
def test_cancelled_background_argos_ignores_late_delivery(downloads, terminal):
    settings, dialog = downloads
    app = settings.parent
    with (mock.patch('main.threading.Thread.start'),
          mock.patch.object(app, '_present_main_translation_result') as present,
          mock.patch.object(app, '_show_argos_translation_error') as error,
          mock.patch('translation_availability.offer_provider_recovery') as recover,
          mock.patch('main.QMessageBox.information') as notice):
        app._start_main_translation('hello', 'en', 'es', 'argos', package_installed=False)
        app._argos_progress._continue_in_background()
        dialog.task_cancel_button.click()
        assert app._argos_cancel_requested.is_set()
        before = dialog.task_status_label.text()
        app._on_argos_progress('EN→ES', 900, 1000)
        app._on_argos_status('install')
        after = dialog.task_status_label.text()
        if terminal == 'success':
            app._on_main_translation_done('hola')
        elif terminal == 'failure':
            app._on_main_translation_error('late network failure')
        elif terminal == 'unavailable':
            app._on_main_provider_unavailable(app._main_provider_request_id, mock.Mock())
        else:
            app._on_argos_translation_cancelled()
        assert after == before
        assert not app._main_translation_running
        assert settings._language_package_task_state['kind'] == 'idle'
        for modal_or_delivery in (present, error, recover, notice):
            modal_or_delivery.assert_not_called()


@pytest.mark.parametrize('provider_unavailable', [False, True])
def test_background_argos_failure_stays_in_the_download_center(downloads, provider_unavailable):
    settings, dialog = downloads
    app = settings.parent
    with (mock.patch('main.threading.Thread.start'),
          mock.patch.object(app, '_show_argos_translation_error') as error,
          mock.patch('translation_availability.offer_provider_recovery') as recover):
        app._start_main_translation('hello', 'en', 'es', 'argos', package_installed=False)
        app._argos_progress._continue_in_background()
        if provider_unavailable:
            issue = mock.Mock()
            issue.message.return_value = 'Package download interrupted'
            app._on_main_provider_unavailable(app._main_provider_request_id, issue)
        else:
            app._on_main_translation_error('Package download interrupted')
    error.assert_not_called()
    recover.assert_not_called()
    assert settings._language_package_task_state['kind'] == 'failed'
    assert 'Package download interrupted' in dialog.task_status_label.text()


def test_current_version_check_remains_metadata_only(downloads):
    settings, dialog = downloads
    table = dialog.easyocr_table
    action = next(item for item in table._package_engine_actions
                  if item.property('packageAction') == 'update')
    dialog._on_update_plan_ready('easyocr', dict(current=True, installed='1.7 · r2',
                                               available='1.7 · r2', size=123000000))
    assert '1.7' in table._package_size_label.text()
    assert table._package_size_label.toolTip().strip()
    with mock.patch('settings_window.threading.Thread.start') as check, \
         mock.patch.object(settings, 'start_easyocr_install') as install:
        action.trigger()
        check.assert_called_once()
        install.assert_not_called()


@pytest.mark.parametrize('kind', ('done', 'failed', 'idle'))
def test_terminal_bundle_status_restores_actions_and_hides_cancel(downloads, kind):
    settings, dialog = downloads
    settings._hymt_install_in_progress = True
    settings._report_engine_task('hymt', 'Downloading', 20)
    assert not dialog.refresh_btn.isEnabled()
    settings._hymt_install_in_progress = False
    settings._report_engine_task('hymt', 'Completed status', kind=kind)
    assert dialog.refresh_btn.isEnabled()
    assert not dialog.task_progress.isVisible()
    assert not dialog.task_cancel_button.isVisible()
    assert not dialog.task_show_button.isVisible()
    assert 'Completed status' in dialog.task_status_label.text()
    assert settings._language_package_task_state['kind'] == kind


@pytest.mark.parametrize('locale', ('en', 'ru', 'ar', 'fr', 'de', 'es', 'pt', 'it', 'zh', 'tr', 'hi', 'id'))
@pytest.mark.parametrize('percent', (80, 100, 160, 200))
def test_background_footer_fits_all_locales(downloads, app, locale, percent):
    settings, old = downloads
    old.hide()
    settings.parent.current_interface_language = locale
    dialog = _manager(settings)
    settings._language_manager_dialog = dialog
    settings._hymt_install_in_progress = True
    owns_appearance = not hasattr(app, '_dialog_appearance')
    appearance = install_window_appearance(app)
    old_percent, old_theme = appearance.percent, appearance.theme
    bounds = mock.patch.object(appearance, 'available_geometry', return_value=QtCore.QRect(0, 0, 3840, 2160))
    bounds.start()
    appearance.refresh(percent=percent, theme=settings.parent.current_theme)
    def apply_scale():
        appearance.apply(dialog)
        # Native scaling queues row/viewport fitting after the layout turn.
        for _ in range(6):
            app.processEvents()
    try:
        dialog.show()
        apply_scale()
        anchors = [dialog.download_access_btn, dialog.close_btn, dialog.tabs.tabBar()]
        before = [QtCore.QRect(widget.mapTo(dialog, QtCore.QPoint()), widget.size()) for widget in anchors]
        settings._report_engine_task('hymt', 'Long download message ' * 10, 60)
        apply_scale()
        assert [QtCore.QRect(widget.mapTo(dialog, QtCore.QPoint()), widget.size()) for widget in anchors] == before
        actions = [dialog.task_show_button, dialog.task_progress, dialog.task_cancel_button,
                   dialog.download_access_btn, dialog.close_btn]
        assert len({widget.height() for widget in actions if widget is not dialog.task_progress}) == 1
        table = dialog.windows_table
        if table is not None and table.rowCount():
            factor = float(dialog.property('ui_effective_scale'))
            assert table.iconSize() == QtCore.QSize(22, 22) * factor
            option = table.viewOptions()
            index = table.model().index(0, 0)
            table.itemDelegate().initStyleOption(option, index)
            option.rect = table.visualRect(index)
            indicator = table.style().subElementRect(QtWidgets.QStyle.SE_ItemViewItemCheckIndicator, option, table)
            assert indicator.width() >= round(16 * factor)
            assert option.rect.contains(indicator)
            # A larger icon can change the row height after the first native
            # layout. The bottom edge must still end on a complete row.
            assert table.viewport().height() % table.rowHeight(0) == 0, (
                table.height(), table.maximumHeight(), table.viewport().height(), table.rowHeight(0))
        for widget in actions:
            rect = QtCore.QRect(widget.mapTo(dialog, QtCore.QPoint()), widget.size())
            assert dialog.rect().contains(rect), (locale, widget.objectName(), rect, dialog.rect())
        for left, right in zip(actions, actions[1:]):
            assert not QtCore.QRect(left.mapTo(dialog, QtCore.QPoint()), left.size()).intersects(
                QtCore.QRect(right.mapTo(dialog, QtCore.QPoint()), right.size()))
        output = Path(sys.argv[0]).parent / 'engine-progress'
        output.mkdir(parents=True, exist_ok=True)
        assert dialog.grab().save(str(output / f'{locale}-{percent}.png'))
    finally:
        settings._hymt_install_in_progress = False
        dialog.close()
        settings._language_manager_dialog = old
        appearance.refresh(percent=old_percent, theme=old_theme)
        bounds.stop()
        if owns_appearance:
            app.removeEventFilter(appearance)
            del app._dialog_appearance
            appearance.deleteLater()
