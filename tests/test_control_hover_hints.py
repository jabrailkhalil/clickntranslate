"""Hover help covers controls on every settings page and follows locale changes."""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from control_hints import HINTS, LANGUAGES, control_hint
from styled_dialogs import _ensure_control_tooltip, tooltip_text
from test_desktop_ux import app, window


CONTROLS = (QtWidgets.QAbstractButton, QtWidgets.QComboBox, QtWidgets.QLineEdit,
            QtWidgets.QAbstractSpinBox, QtWidgets.QAbstractSlider,
            QtWidgets.QKeySequenceEdit, QtWidgets.QTextEdit)


@pytest.mark.parametrize('language', LANGUAGES)
def test_all_visible_main_settings_and_hotkey_controls_have_hover_help(window, app, language):
    window.set_interface_language(language)

    def assert_coverage():
        app.processEvents()
        controls = [widget for widget in window.ui_root.findChildren(QtWidgets.QWidget)
                    if isinstance(widget, CONTROLS) and widget.isVisible()]
        assert controls
        for control in controls:
            assert control.toolTip(), (language, type(control).__name__, control.objectName())
            assert '&lt;qt&gt;' not in control.toolTip(), control.toolTip()

    assert_coverage()
    window.show_settings()
    settings = window.settings_window
    assert settings.autostart_checkbox.toolTip() != settings.autostart_checkbox.text()
    assert settings.button_tooltips_checkbox.accessibleDescription() == control_hint(language, 'hover_tips')
    for index in range(5):
        settings._set_settings_page(index)
        assert_coverage()
    settings.show_hotkeys_screen()
    assert_coverage()
    for control in settings.findChildren(QtWidgets.QKeySequenceEdit):
        assert control.accessibleName()
        assert control.toolTip()


def test_generated_hover_help_follows_changed_labels_and_preserves_explicit_help(app):
    button = QtWidgets.QPushButton('&Open')
    try:
        _ensure_control_tooltip(button)
        assert button.toolTip() == 'Open'
        button.setText('&Ouvrir')
        _ensure_control_tooltip(button)
        assert button.toolTip() == 'Ouvrir'
        button.setToolTip(tooltip_text('Open a saved translation session.'))
        button.setText('Changed')
        _ensure_control_tooltip(button)
        assert button.toolTip() == 'Open a saved translation session.'
    finally:
        button.deleteLater()


def test_control_help_is_translated_for_every_interface_language():
    for key, translations in HINTS.items():
        assert len(translations) == len(LANGUAGES), key
        assert all(isinstance(text, str) and text.strip() for text in translations), key


def test_native_hover_help_is_visible_inside_each_monitor_and_can_be_disabled(window, app):
    from ui_scaling import widget_global_point, widget_global_rect
    if app.platformName() == 'offscreen':
        pytest.skip('Real hover delivery requires the native Qt backend')
    old_cursor = QtGui.QCursor.pos()
    original_setting = app.property('buttonTooltipsEnabled')
    window.show_settings()
    controller = window._ui_scale_controller
    try:
        app.setProperty('buttonTooltipsEnabled', True)
        for screen in app.screens():
            bounds = screen.availableGeometry()
            controller.available_geometry.return_value = bounds
            window.move(bounds.topLeft()+QtCore.QPoint(100, 100))
            window.set_ui_scale_percent(100)
            window.raise_()
            window.activateWindow()
            QTest.qWait(100)
            settings = window.settings_window
            controls = [settings.autostart_checkbox, settings.translation_font_control,
                        settings.clear_cache_btn, settings.ui_scale_decrease]
            for control in controls:
                QtWidgets.QToolTip.hideText()
                QTest.mouseMove(controller.view.viewport(), QtCore.QPoint(1, 1))
                QTest.qWait(50)
                QTest.mouseMove(controller.view.viewport(), controller.map_widget_to_view(control))
                QTest.qWait(850)
                assert QtWidgets.QToolTip.isVisible(), (
                    control.objectName() or control.text(), screen.name(),
                    window.isActiveWindow(), app.activePopupWidget(),
                    controller.view._hover_timer.isActive(),
                    controller.view._hover_target() if controller.view._hover_target else None,
                    QtGui.QCursor.pos(), int(app.mouseButtons()))
                assert QtWidgets.QToolTip.text() == control.toolTip()
                tip = next(widget for widget in app.allWidgets()
                           if widget.isVisible() and widget.metaObject().className() == 'QTipLabel')
                assert bounds.contains(widget_global_rect(tip))
            app.setProperty('buttonTooltipsEnabled', False)
            QTest.qWait(350)  # QToolTip.hideText uses Qt's short hide delay.
            assert not QtWidgets.QToolTip.isVisible()
            control = settings.copy_history_checkbox
            event = QtGui.QHelpEvent(QtCore.QEvent.ToolTip, control.rect().center(),
                                    widget_global_point(control, control.rect().center()))
            app.sendEvent(control, event)
            assert not QtWidgets.QToolTip.isVisible()
            app.setProperty('buttonTooltipsEnabled', True)
    finally:
        QtWidgets.QToolTip.hideText()
        QtGui.QCursor.setPos(old_cursor)
        app.setProperty('buttonTooltipsEnabled', original_setting)
