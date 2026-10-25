"""Slider replacements retain actual settings units, saves and keyboard editing."""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from keyboard_navigation import focus_control, install_keyboard_navigation, tab_stops
from number_controls import NumberStepper
from numeric_stepper import NumericStepper
from test_desktop_ux import app, window


def _settings(window, app, page):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(page)
    app.processEvents()
    return settings


def _enter(control, text):
    edit = control.lineEdit()
    edit.setFocus()
    edit.selectAll()
    QTest.keyClicks(edit, text)
    QTest.keyClick(edit, QtCore.Qt.Key_Return)


def test_dynamic_seconds_load_step_type_and_save_real_milliseconds(window, app):
    window.config['game_capture_interval_ms'] = 850
    settings = _settings(window, app, 2)
    control = settings.game_scan_interval_control
    assert isinstance(control, NumericStepper)
    assert control.value() == .85
    assert control.suffix().strip() == 's'
    assert control.singleStep() == .05
    QTest.mouseClick(control.increase, QtCore.Qt.LeftButton)
    assert control.value() == .9
    assert window.config['game_capture_interval_ms'] == 900
    assert type(window.config['game_capture_interval_ms']) is int
    _enter(control, '1.20')
    assert control.value() == 1.2
    assert window.config['game_capture_interval_ms'] == 1200


def test_dynamic_opacity_and_ocr_dim_save_percent_integers(window, app):
    window.config.update(game_overlay_opacity=88, ocr_dim_strength=60, dim_screen_during_ocr=True)
    settings = _settings(window, app, 2)
    control = settings.game_overlay_opacity_control
    assert isinstance(control, NumericStepper) and control.value() == 88
    assert control.suffix().strip() == '%'
    QTest.mouseClick(control.decrease, QtCore.Qt.LeftButton)
    assert window.config['game_overlay_opacity'] == 87
    assert type(window.config['game_overlay_opacity']) is int
    _enter(control, '72')
    assert window.config['game_overlay_opacity'] == 72
    settings._set_settings_page(4)
    app.processEvents()
    dim = settings.ocr_dim_strength_control
    assert isinstance(dim, NumericStepper) and dim.value() == 60
    assert dim.isEnabled()
    QTest.mouseClick(dim.increase, QtCore.Qt.LeftButton)
    assert window.config['ocr_dim_strength'] == 65
    assert type(window.config['ocr_dim_strength']) is int
    settings.dim_screen_during_ocr_checkbox.setChecked(False)
    assert not dim.isEnabled()
    assert not window.config['dim_screen_during_ocr']
    assert window.config['ocr_dim_strength'] == 65
    settings.dim_screen_during_ocr_checkbox.setChecked(True)
    assert dim.isEnabled() and dim.value() == 65
    _enter(dim, '45')
    assert window.config['ocr_dim_strength'] == 45


def test_all_five_settings_pages_have_no_sliders_and_companion_uses_explicit_values(window, app):
    settings = _settings(window, app, 0)
    assert not settings.findChildren(QtWidgets.QSlider)
    settings._set_settings_page(3)
    app.processEvents()
    fields = settings.settings_assistant_page.findChildren(NumberStepper)
    assert len(fields) >= 2
    assert all(field.lineEdit().text().endswith('%') for field in fields)
    assert all(field.minimum() <= field.value() <= field.maximum() for field in fields)


def test_native_numeric_editing_is_not_stolen_by_arrow_navigation(window, app):
    install_keyboard_navigation(app)
    settings = _settings(window, app, 2)
    control = settings.game_scan_interval_control
    control.setValue(.85)
    root = settings.window()
    assert control.editor in tab_stops(root)
    assert control.lineEdit() not in tab_stops(root)
    focus_control(control.editor)
    QTest.keyClick(control.editor, QtCore.Qt.Key_Up)
    assert control.value() == .9
    assert control.editor.hasFocus()
    assert window.config['game_capture_interval_ms'] == 900
    control.lineEdit().setCursorPosition(2)
    QTest.keyClick(control.lineEdit(), QtCore.Qt.Key_Left)
    assert control.lineEdit().cursorPosition() == 1
    assert control.editor.hasFocus()
    edit = control.lineEdit()
    edit.selectAll()
    QTest.keyClicks(edit, '1.20')
    QTest.keyClick(edit, QtCore.Qt.Key_Escape)
    assert settings._settings_page_index == 2
    assert control.value() == .9
    assert window.config['game_capture_interval_ms'] == 900


@pytest.mark.parametrize('control_class', [NumberStepper, NumericStepper])
def test_unfocused_settings_percent_fields_ignore_wheel(app, control_class):
    owner = QtWidgets.QWidget()
    control = control_class(owner)
    control.setRange(40, 100)
    control.setSuffix('%')
    control.setValue(80)
    control.setGeometry(5, 5, 180, 28)
    owner.resize(300, 100)
    try:
        owner.show()
        app.processEvents()
        control.editor.clearFocus()
        control.lineEdit().clearFocus()
        event = QtGui.QWheelEvent(QtCore.QPointF(20, 10), QtCore.QPointF(20, 10),
                                 QtCore.QPoint(), QtCore.QPoint(0, -120), QtCore.Qt.NoButton,
                                 QtCore.Qt.NoModifier, QtCore.Qt.NoScrollPhase, False)
        control.editor.wheelEvent(event)
        assert control.value() == 80
        assert not event.isAccepted()
    finally:
        owner.close()
        owner.deleteLater()
