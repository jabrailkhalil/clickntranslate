"""Avoid redundant Qt repolish and keep bulk package updates transactional."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import settings_window
from test_desktop_ux import app, window


def test_reapplying_the_same_theme_keeps_native_and_proxy_stylesheets(window, app):
    window.show_settings()
    window.apply_theme()
    app.processEvents()
    controller = window._ui_scale_controller
    before = window.grab().toImage()
    with (mock.patch.object(window, 'setStyleSheet', wraps=window.setStyleSheet) as native,
          mock.patch.object(controller.canvas, 'setStyleSheet', wraps=controller.canvas.setStyleSheet) as canvas,
          mock.patch.object(controller.view, 'setStyleSheet', wraps=controller.view.setStyleSheet) as view):
        window.apply_theme()
        app.processEvents()
        assert native.call_count == canvas.call_count == view.call_count == 0
        assert window.grab().toImage() == before
        window.toggle_theme()
        app.processEvents()
        assert native.call_count == canvas.call_count == view.call_count == 1
        assert window.grab().toImage() != before


@pytest.fixture
def manager(window):
    window.show_settings()
    with (mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        dialog = settings_window.OcrLanguageManagerDialog(window.settings_window)
        yield dialog
        dialog.close()
        dialog.deleteLater()
        QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        QtWidgets.QApplication.processEvents()


def row(code, name):
    return dict(code=code, name=name, package='package-' + code,
                status='ready-' + code, checked=False, selectable=True)


def test_sorted_bulk_update_keeps_codes_and_package_columns_in_the_same_row(manager):
    table = manager.easyocr_table
    table.setSortingEnabled(True)
    table.sortItems(1, QtCore.Qt.AscendingOrder)
    changed = []
    table.itemChanged.connect(lambda item: changed.append(item.text()))
    manager._set_language_rows(table, [row('z', 'Zulu'), row('a', 'Alpha')])
    assert table.isSortingEnabled()
    assert not table.signalsBlocked()
    assert table.updatesEnabled()
    assert changed == []
    assert table.item(0, 1).text() == 'Alpha'
    for index in range(table.rowCount()):
        code = table.item(index, 0).data(QtCore.Qt.UserRole)
        assert table.item(index, 2).text() == 'package-' + code
        assert table.item(index, 3).text() == 'ready-' + code


@pytest.mark.parametrize('updates', (False, True))
@pytest.mark.parametrize('signals', (False, True))
def test_bulk_update_restores_explicit_state_even_when_population_fails(manager, updates, signals):
    table = manager.easyocr_table
    table.setUpdatesEnabled(updates)
    table.blockSignals(signals)
    table.setSortingEnabled(True)
    with pytest.raises(KeyError):
        manager._set_language_rows(table, [{'name': 'No package identity'}])
    assert table.updatesEnabled() is updates
    assert table.signalsBlocked() is signals
    assert table.isSortingEnabled()


def test_bulk_refresh_does_not_turn_inherited_paint_freeze_into_a_permanent_child_freeze(manager):
    table = manager.easyocr_table
    manager.setUpdatesEnabled(False)
    assert not table.updatesEnabled()
    assert not table.testAttribute(QtCore.Qt.WA_ForceUpdatesDisabled)
    manager._set_language_rows(table, [row('en', 'English')])
    assert not table.updatesEnabled()
    assert not table.testAttribute(QtCore.Qt.WA_ForceUpdatesDisabled)
    manager.setUpdatesEnabled(True)
    assert table.updatesEnabled()
