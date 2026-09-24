"""Regression coverage for the 1.8 controls and clipped settings popup."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import main
from number_controls import NumberStepper
from test_desktop_ux import app, window


@pytest.mark.parametrize('language', ['en', 'ru', 'de', 'es', 'fr', 'zh'])
@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
def test_result_actions_fit_canvas_at_every_scale_and_toggle(window, app, language, theme):
    window.current_interface_language = language
    window.current_theme = theme
    window.show_settings()
    window.apply_theme()
    combo = window.settings_window.result_window_control
    for percent in (80, 100, 150, 200):
        window.set_ui_scale_percent(percent)
        combo.showPopup()
        QTest.qWait(20)
        popup = combo.view().window()
        proxy = popup.graphicsProxyWidget()
        assert proxy is not None
        assert window._ui_scale_controller.view.sceneRect().contains(proxy.sceneBoundingRect())
        for mode in combo._modes:
            item = combo._item(mode)
            font = item.data(QtCore.Qt.FontRole) or combo.view().font()
            required = QtGui.QFontMetrics(font).horizontalAdvance(item.text()) + combo.iconSize().width() + 6
            assert combo.view().viewport().width() >= required
        before = combo.is_mode_checked('selection')
        combo._toggle_pressed(combo.model().index(1, 0))
        assert combo.is_mode_checked('selection') != before
        assert combo.view().window().isVisible()
        combo.hidePopup()


def test_companion_settings_have_no_document_context_menu_or_explanatory_labels(window, app):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    page.show_category('static')
    assert not page.findChildren(QtWidgets.QLabel, 'assistantSection')
    assert not [label for label in page.findChildren(QtWidgets.QLabel, 'assistantNote') if label.wordWrap()]
    with mock.patch.object(main.QMenu, 'exec_') as menu:
        QTest.mouseClick(window._ui_scale_controller.view.viewport(), QtCore.Qt.RightButton,
                         pos=window._ui_scale_controller.map_widget_to_view(page.appearance_buttons['custom']))
        window.central_widget.customContextMenuRequested.emit(QtCore.QPoint(5, 5))
        menu.assert_not_called()
        window.show_main_screen()
        window.show_main_context_menu(QtCore.QPoint(5, 5))
        menu.assert_called_once()


def test_number_entry_above_one_hundred_arrow_steps_and_limits(app):
    field = NumberStepper()
    field.setRange(60, 180)
    field.setSuffix('%')
    field.setValue(100)
    field.show()
    try:
        field.lineEdit().selectAll()
        QTest.keyClicks(field.lineEdit(), '150')
        assert field.value() == 100  # Drafts apply on commit.
        QTest.keyClick(field.lineEdit(), QtCore.Qt.Key_Return)
        assert field.value() == 150
        field.increase.click()
        assert field.value() == 151
        field.decrease.click()
        assert field.value() == 150
        field.lineEdit().selectAll()
        QTest.keyClicks(field.lineEdit(), '999')
        QTest.keyClick(field.lineEdit(), QtCore.Qt.Key_Return)
        assert field.value() == 180 and not field.increase.isEnabled()
        field.setValue(60)
        assert not field.decrease.isEnabled()
    finally:
        field.close()
        field.deleteLater()


def test_welcome_language_changes_actual_new_install_translation_pairs(window, app):
    window.config = main.fresh_config()
    dialog = main.WelcomeDialog(window)
    try:
        dialog.set_language('ru')
        for source, target in main.TRANSLATION_PAIR_KEYS:
            assert (window.config[source], window.config[target]) == ('en', 'ru')
    finally:
        dialog.close()
        dialog.deleteLater()
