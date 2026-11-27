"""Only visible engine rows are built; cached results populate before painting."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import settings_window
from settings_window import OcrLanguageManagerDialog
from test_desktop_ux import app, window


@pytest.fixture
def manager(window, app):
    window.show_settings()
    with (mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        dialog = OcrLanguageManagerDialog(window.settings_window)
        dialog.show()
        app.processEvents()
        yield dialog
        dialog.close()
        dialog.deleteLater()
        QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()


def test_constructor_leaves_hidden_tables_unpopulated(manager):
    active = manager._active_engine_table()
    assert active is not None
    assert not active._package_rows_dirty
    assert active.rowCount() > 0
    for name in ('tesseract_table', 'easyocr_table', 'rapidocr_table', 'hymt_table', 'argos_table'):
        table = getattr(manager, name)
        if table is not active:
            assert table._package_rows_dirty
            assert table.rowCount() == 0


def test_selecting_an_engine_populates_once_before_returning_from_the_click(manager, app):
    table = manager.rapidocr_table
    callback = mock.Mock(wraps=table._package_populate)
    table._package_populate = callback
    manager._rapidocr_status_cache = (True, '')
    picker = manager._engine_selectors[0]
    page_index = manager.ocr_tabs.indexOf(table.parentWidget())
    picker.setCurrentIndex(page_index)
    assert callback.call_count == 1
    assert not table._package_rows_dirty
    assert table.rowCount() > 0
    assert table.isVisible()
    manager._snap_visible_table()
    manager._on_tab_changed(page_index)
    app.processEvents()
    assert callback.call_count == 1
    assert table.isVisible()


def test_runtime_results_are_cached_without_constructing_hidden_rows(manager, app):
    table = manager.rapidocr_table
    callback = mock.Mock(wraps=table._package_populate)
    table._package_populate = callback
    manager._on_runtime_probe_ready({'rapidocr': (True, ''), 'complete': True})
    assert manager._rapidocr_status_cache == (True, '')
    assert table.rowCount() == 0
    callback.assert_not_called()
    manager.ocr_tabs.setCurrentWidget(table.parentWidget())
    assert callback.call_count == 1
    assert table.rowCount() > 0
    assert not table._package_rows_dirty


def test_refresh_marks_hidden_rows_dirty_but_preserves_pending_selection(manager, app):
    table = manager.easyocr_table
    table._pending_package_codes.add('ru')
    callback = mock.Mock(wraps=table._package_populate)
    table._package_populate = callback
    manager.refresh_all()
    callback.assert_not_called()
    assert table._pending_package_codes == {'ru'}
    manager._easyocr_status_cache = (True, '')
    manager.ocr_tabs.setCurrentWidget(table.parentWidget())
    assert callback.call_count == 1
    assert not table._package_rows_dirty
    assert table.rowCount() > 0


def test_api_and_diagnostics_do_not_fill_unrelated_engine_tables(manager, app):
    from download_access import DownloadAccessPage
    table = manager.argos_table
    callback = mock.Mock(wraps=table._package_populate)
    table._package_populate = callback
    with mock.patch('provider_secrets.get_key', return_value=''):
        bar = manager.tabs.tabBar()
        QTest.mouseClick(bar, QtCore.Qt.LeftButton, pos=bar.tabRect(2).center())
        app.processEvents()
    assert manager.api_page.isVisible()
    assert manager._active_engine_table() is None
    manager.refresh_all()
    manager._snap_visible_table()
    callback.assert_not_called()
    with mock.patch.object(DownloadAccessPage, 'start'):
        manager.download_access_btn.click()
        assert manager.body_stack.currentWidget() is not manager.tabs
        manager.refresh_all()
        callback.assert_not_called()
        manager.download_access_btn.click()
    assert manager.api_page.isVisible()
    assert table.rowCount() == 0


def test_argos_catalog_refresh_defers_rows_until_its_tab_is_opened(manager, app):
    table = manager.argos_table
    callback = mock.Mock(wraps=table._package_populate)
    table._package_populate = callback
    manager._argos_catalog = [{'from_code': 'en', 'to_code': 'ru', 'package_version': '1'}]
    manager._on_argos_catalog_ready('')
    callback.assert_not_called()
    assert table.rowCount() == 0
    manager.focus_translation_engine('argos', 'en', 'ru')
    assert callback.call_count == 1
    assert table.rowCount() > 0
    assert table.isVisible()
