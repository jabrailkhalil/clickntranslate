"""Caption changes must not shift buttons through fractional font rounding."""
from copy import deepcopy
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import main
from engine_center import text
from engine_center_widgets import EngineActivationButton
from settings_window import OcrLanguageManagerDialog
from test_desktop_ux import app, window
from test_language_package_manager import _AppParent, _ManagerOwner
from window_appearance import DialogAppearance


def _rect(button, parent):
    return QtCore.QRect(button.mapTo(parent, QtCore.QPoint()), button.size())


@pytest.mark.parametrize('locale', ('en', 'ru', 'ar'))
@pytest.mark.parametrize('keys', (('connection', 'back'), ('activate', 'active')))
@pytest.mark.parametrize('points', (8.25, 9.5, 10.75, 12.375))
def test_mouse_caption_changes_keep_size_with_fractional_point_fonts(app, locale, keys, points):
    container = QtWidgets.QWidget()
    row = QtWidgets.QHBoxLayout(container)
    row.addStretch(1)
    captions = tuple(text(locale, key) for key in keys)
    button = EngineActivationButton(captions[0], container)
    button.captions = captions
    button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
    button.setStyleSheet('QPushButton { padding:4px 10px; border:1px solid #776585; border-radius:5px; }')
    font = QtGui.QFont('Segoe UI')
    font.setPointSizeF(points)
    button.setFont(font)
    row.addWidget(button)
    button.clicked.connect(lambda: button.setText(captions[1] if button.text() == captions[0] else captions[0]))
    container.resize(600, 100)
    try:
        container.show()
        app.processEvents()
        before, hint = button.geometry(), button.sizeHint()
        assert button.font().pointSizeF() == points
        for index in range(4):
            QTest.mouseClick(button, QtCore.Qt.LeftButton)
            app.processEvents()
            assert button.text() == captions[(index+1) % 2]
            assert button.geometry() == before
            assert button.sizeHint() == hint
            assert button.width() >= button.minimumSizeHint().width()
            assert container.rect().contains(button.geometry())
    finally:
        container.close()
        container.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def _exercise_center(app, owner, appearance):
    dialog = OcrLanguageManagerDialog(owner)
    dialog._initial_probe_timer.stop()
    dialog._initial_catalog_timer.stop()
    try:
        dialog.show()
        app.processEvents()
        appearance.apply(dialog)
        app.processEvents()
        before = _rect(dialog.download_access_btn, dialog)
        close = _rect(dialog.close_btn, dialog)
        for _ in range(2):
            QTest.mouseClick(dialog.download_access_btn, QtCore.Qt.LeftButton)
            app.processEvents()
            assert dialog.body_stack.currentWidget() is dialog._download_access_page
            assert _rect(dialog.download_access_btn, dialog) == before
            assert _rect(dialog.close_btn, dialog) == close
            QTest.mouseClick(dialog.download_access_btn, QtCore.Qt.LeftButton)
            app.processEvents()
            assert dialog.body_stack.currentWidget() is dialog.tabs
            assert _rect(dialog.download_access_btn, dialog) == before
        dialog.focus_translation_engine('mymemory')
        app.processEvents()
        appearance.apply(dialog)
        app.processEvents()
        button = dialog.translation_tabs._activate_button
        engine = _rect(button, dialog)
        assert button.isEnabled()
        QTest.mouseClick(button, QtCore.Qt.LeftButton)
        app.processEvents()
        assert button.text() == text(dialog.lang, 'active')
        assert not button.isEnabled()
        assert _rect(button, dialog) == engine
    finally:
        dialog.close()
        dialog.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('percent', (81, 103, 137))
@pytest.mark.parametrize('locale', ('en', 'ru', 'ar'))
def test_real_footer_and_activation_clicks_at_fractional_scales(app, percent, locale):
    parent = _AppParent()
    parent.current_interface_language = locale
    parent.config = deepcopy(main.DEFAULT_CONFIG)
    owner = _ManagerOwner(parent)
    owner.auto_save_setting = mock.Mock(side_effect=parent.config.__setitem__)
    owner._refresh_ready_engine_choices = mock.Mock()
    appearance = DialogAppearance(app, percent=percent, theme='Темная')
    with mock.patch.object(appearance, 'available_geometry', return_value=QtCore.QRect(0, 0, 3840, 2160)), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'), \
         mock.patch('download_access.DownloadAccessPage.start'), \
         mock.patch('provider_settings.refresh_provider_routing'):
        try:
            _exercise_center(app, owner, appearance)
        finally:
            app.removeEventFilter(appearance)
            appearance.deleteLater()
            parent.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('percent', (81, 103, 137))
def test_dark_theme_app_uses_stationary_buttons_at_fractional_scales(window, app, percent):
    window.set_interface_language('en')
    window.show_settings()
    appearance = DialogAppearance(app, percent=percent, theme=window.current_theme)
    with mock.patch.object(appearance, 'available_geometry', return_value=QtCore.QRect(0, 0, 3840, 2160)), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'), \
         mock.patch('download_access.DownloadAccessPage.start'):
        try:
            _exercise_center(app, window.settings_window, appearance)
        finally:
            app.removeEventFilter(appearance)
            appearance.deleteLater()
