"""Native window placement must use desktop coordinates after layout/scaling."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import main
import settings_window as settings
from ui_scaling import centered_window_geometry, center_window
from window_appearance import install_window_appearance


@pytest.fixture
def owner(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    previous = getattr(app, '_dialog_appearance', None)
    manager = install_window_appearance(app, 100, 'Темная')
    with (mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True),
          mock.patch.object(main, 'get_cached_config', return_value=dict(main.DEFAULT_CONFIG)),
          mock.patch.object(main.DarkThemeApp, 'save_config'),
          mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False),
          mock.patch.object(main, 'get_data_file', side_effect=lambda name: str(tmp_path / name))):
        window = main.DarkThemeApp()
        window.show()
        QTest.qWait(30)
        yield app, window
        window.force_quit = True
        window.close()
        window.deleteLater()
        if previous is None:
            app.removeEventFilter(manager)
            del app._dialog_appearance
            manager.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def expected_position(frame, target, bounds):
    x = target.center().x() - (frame.width() - 1) // 2
    y = target.center().y() - (frame.height() - 1) // 2
    return QtCore.QPoint(max(bounds.left(), min(x, bounds.right() - frame.width() + 1)),
                        max(bounds.top(), min(y, bounds.bottom() - frame.height() + 1)))


def test_main_first_show_is_centered_and_reopen_preserves_a_user_move(owner):
    app, window = owner
    bounds = window._ui_scale_controller.available_geometry()
    assert window.frameGeometry().topLeft() == expected_position(window.frameGeometry(), bounds, bounds)
    moved = bounds.topLeft() + QtCore.QPoint(40, 50)
    window.move(moved)
    window.hide()
    window.show()
    QTest.qWait(30)
    assert window.pos() == moved


@pytest.mark.parametrize('percent', [80, 100, 130])
@pytest.mark.parametrize('kind', ['packages', 'update', 'install', 'argos-confirm', 'argos-error'])
def test_secondary_windows_center_on_the_native_scaled_owner(owner, percent, kind):
    app, window = owner
    window.set_ui_scale_percent(percent)
    window.move(70, 85)
    window.show_settings()
    embedded = window.settings_window
    if kind == 'packages':
        with mock.patch.object(QtCore.QTimer, 'singleShot'):
            dialog = settings.OcrLanguageManagerDialog(embedded)
    elif kind == 'update':
        dialog = settings.UpdateProgressDialog(embedded)
    elif kind == 'install':
        dialog = settings.TesseractInstallProgressDialog(embedded)
    elif kind == 'argos-confirm':
        dialog = main.ArgosPackageInstallDialog(window, 'English → Русский')
    else:
        dialog = main.ArgosTranslationErrorDialog(window, 'English → Русский', 'Fixture error')
    try:
        dialog.show()
        QTest.qWait(60)
        assert dialog.graphicsProxyWidget() is None
        assert dialog.frameGeometry().topLeft() == expected_position(
            dialog.frameGeometry(), window.frameGeometry(), window.screen().availableGeometry())
    finally:
        dialog.close()
        dialog.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_explicit_dialog_position_and_popup_anchor_are_preserved(owner):
    app, window = owner
    for flags in (QtCore.Qt.Dialog, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint):
        dialog = QtWidgets.QDialog(window, flags)
        dialog.resize(200, 100)
        point = window.screen().availableGeometry().topLeft() + QtCore.QPoint(140, 160)
        dialog.move(point)
        dialog.show()
        QTest.qWait(40)
        assert dialog.pos() == point
        dialog.close()
        dialog.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_hidden_owner_centers_result_on_the_available_screen(owner):
    app, window = owner
    window.hide()
    dialog = QtWidgets.QDialog(window, QtCore.Qt.FramelessWindowHint)
    dialog.resize(260, 120)
    # Supplied bounds also exercise a monitor to the left of the primary one.
    bounds = QtCore.QRect(-1400, -100, 1400, 900)
    center_window(dialog, available=bounds)
    assert dialog.frameGeometry().topLeft() == expected_position(dialog.frameGeometry(), bounds, bounds)
    dialog.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('bounds', [QtCore.QRect(-1280, 25, 1280, 775), QtCore.QRect(0, 25, 1280, 775)])
def test_centering_keeps_large_window_inside_the_selected_monitor(bounds):
    target = QtCore.QRect(bounds.left() + 10, bounds.top() + 20, 400, 200)
    frame = QtCore.QRect(0, 0, 1000, 700)
    positioned = centered_window_geometry(frame, target, bounds)
    assert bounds.contains(positioned)
    assert positioned.topLeft() == expected_position(frame, target, bounds)
