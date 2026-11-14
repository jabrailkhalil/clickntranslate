"""Mouse actions must not manufacture a keyboard-navigation focus ring."""
import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

from button_styles import button_qss
import keyboard_navigation as keyboard
from test_desktop_ux import app, window


def settle(app):
    for _ in range(5):
        app.processEvents()


def ring_visible(root):
    ring = getattr(root, '_keyboard_focus_ring', None)
    return ring is not None and ring.isVisible()


@pytest.fixture(autouse=True)
def restore_input_mode(app):
    keyboard.install_keyboard_navigation(app)
    navigation = app._keyboard_navigation
    navigation.keyboard = False
    navigation._hide_ring()
    yield
    navigation.keyboard = False
    navigation._hide_ring()


@pytest.mark.parametrize('operation', ['disable', 'hide'])
def test_mouse_action_that_transfers_focus_does_not_enter_keyboard_mode(app, operation):
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    first = QtWidgets.QPushButton('Use this setting')
    second = QtWidgets.QPushButton('Another setting')
    for button in (first, second):
        button.setStyleSheet(button_qss(True))
        layout.addWidget(button)
    first.clicked.connect(lambda: first.setEnabled(False) if operation == 'disable' else first.hide())
    dialog.show()
    settle(app)
    try:
        QTest.mouseClick(first, QtCore.Qt.LeftButton)
        settle(app)
        assert dialog.focusWidget() is second
        assert not app._keyboard_navigation.keyboard
        assert not second.property('keyboardFocus')
        assert not ring_visible(dialog)
        QTest.keyClick(second, QtCore.Qt.Key_Tab)
        assert app._keyboard_navigation.keyboard
        assert ring_visible(dialog)
    finally:
        dialog.close()
        dialog.deleteLater()


def test_typing_in_a_mouse_focused_editor_keeps_pointer_mode(window, app):
    settle(app)
    editor = window.text_input
    controller = window._ui_scale_controller
    point = controller.map_widget_to_view(editor)
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton, pos=point)
    QTest.keyClicks(editor, 'A draft typed with the mouse focus')
    settle(app)
    assert editor.toPlainText().endswith('A draft typed with the mouse focus')
    assert not app._keyboard_navigation.keyboard
    assert not ring_visible(window.ui_root)
    QTest.keyClick(editor, QtCore.Qt.Key_Tab)
    assert app._keyboard_navigation.keyboard
    assert ring_visible(window.ui_root)


def test_mouse_click_clears_previous_keyboard_decoration_even_if_focus_is_retained(app):
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    button = QtWidgets.QPushButton('Action')
    button.setStyleSheet(button_qss(True))
    layout.addWidget(button)
    dialog.show()
    settle(app)
    try:
        keyboard.focus_control(button)
        assert button.property('keyboardFocus') and ring_visible(dialog)
        QTest.mouseClick(button, QtCore.Qt.LeftButton)
        settle(app)
        assert dialog.focusWidget() is button
        assert not button.property('keyboardFocus')
        assert not app._keyboard_navigation.keyboard
        assert not ring_visible(dialog)
    finally:
        dialog.close()
        dialog.deleteLater()


def test_keyboard_typing_keeps_a_deliberate_tab_focus_visible(window, app):
    settle(app)
    editor = window.text_input
    keyboard.focus_control(editor)
    QTest.keyClicks(editor, 'A keyboard draft')
    assert app._keyboard_navigation.keyboard
    assert ring_visible(window.ui_root)


def test_mouse_focus_reason_from_native_activation_clears_keyboard_state(app):
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    first, second = QtWidgets.QPushButton('First'), QtWidgets.QPushButton('Second')
    for button in (first, second):
        button.setStyleSheet(button_qss(True))
        layout.addWidget(button)
    dialog.show()
    settle(app)
    try:
        keyboard.focus_control(first)
        second.setFocus(QtCore.Qt.MouseFocusReason)
        assert not app._keyboard_navigation.keyboard
        assert not second.property('keyboardFocus')
        assert not ring_visible(dialog)
    finally:
        dialog.close()
        dialog.deleteLater()


def test_clicking_a_numeric_bound_never_focus_highlights_the_opposite_arrow(app):
    from numeric_stepper import NumericStepper
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    value = NumericStepper()
    value.setRange(0, 1)
    value.setValue(1)
    layout.addWidget(value)
    dialog.show()
    settle(app)
    try:
        QTest.mouseClick(value.decrease, QtCore.Qt.LeftButton)
        settle(app)
        assert value.value() == 0 and not value.decrease.isEnabled()
        assert not app._keyboard_navigation.keyboard
        assert not value.increase.property('keyboardFocus')
        assert not ring_visible(dialog)
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize('scale', [80, 100, 125])
def test_mouse_step_and_blank_click_leave_no_selected_numeric_text(window, app, scale):
    window.show_settings()
    window.set_ui_scale_percent(scale)
    settings = window.settings_window
    settings._set_settings_page(4)
    settings.dim_screen_during_ocr_checkbox.setChecked(True)
    settle(app)
    field = settings.ocr_dim_strength_control
    view = window._ui_scale_controller
    point = view.map_widget_to_view(field.increase)
    QTest.mouseClick(view.view.viewport(), QtCore.Qt.LeftButton, pos=point)
    settle(app)
    assert field.value() == 65
    assert not field.lineEdit().hasSelectedText()
    viewport = settings.ocr_settings_scroll.viewport()
    blank = QtCore.QPoint(viewport.width()//2, viewport.height()-8)
    target = viewport.childAt(blank)
    assert target is settings.ocr_settings_content or target is None
    position = view.map_widget_to_view(viewport, blank)
    QTest.mouseClick(view.view.viewport(), QtCore.Qt.LeftButton, pos=position)
    settle(app)
    assert not field.lineEdit().hasSelectedText()
    assert not field.editor.hasFocus() and not field.lineEdit().hasFocus()
    assert not field.increase.property('pointerHover')


@pytest.mark.parametrize('kind', ['interval', 'background', 'companion_size', 'companion_opacity'])
def test_other_numeric_arrows_do_not_select_unfocused_editor_text(window, app, kind):
    window.show_settings()
    settings = window.settings_window
    if kind.startswith('companion_'):
        settings._set_settings_page(3)
        field = settings.settings_assistant_page.values[kind.removeprefix('companion_')]
    else:
        settings._set_settings_page(2)
        field = (settings.game_scan_interval_control if kind == 'interval'
                 else settings.game_overlay_opacity_control)
    settle(app)
    arrow = field.decrease if kind == 'companion_opacity' else field.increase
    before = field.value()
    controller = window._ui_scale_controller
    point = controller.map_widget_to_view(arrow)
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton, pos=point)
    settle(app)
    assert field.value() != before
    assert not field.lineEdit().hasSelectedText()
    # Choosing the center is still an explicit text-editing action.
    point = controller.map_widget_to_view(field.editor)
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton, pos=point)
    settle(app)
    assert field.lineEdit().hasSelectedText()


@pytest.mark.parametrize('method', ['mouse', 'keyboard'])
def test_companion_menu_dialog_keeps_the_opening_input_modality(window, app, method):
    window.show_assistant_settings()
    settle(app)
    page = window.settings_window.settings_assistant_page
    if method == 'keyboard':
        keyboard.focus_control(page.menu_buttons)
        QTest.keyClick(page.menu_buttons, QtCore.Qt.Key_Return)
    else:
        controller = window._ui_scale_controller
        point = controller.map_widget_to_view(page.menu_buttons)
        QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton, pos=point)
    settle(app)
    dialog = page._actions_dialog
    assert dialog is not None and dialog.isVisible()
    assert dialog.focusWidget() is dialog.checkboxes['open']
    assert app._keyboard_navigation.keyboard == (method == 'keyboard')
    assert ring_visible(dialog) == (method == 'keyboard')
    QTest.keyClick(dialog.checkboxes['open'], QtCore.Qt.Key_Tab)
    assert app._keyboard_navigation.keyboard and ring_visible(dialog)
    QTest.mouseClick(dialog.done_button, QtCore.Qt.LeftButton)
    settle(app)
    assert page._actions_dialog is None
    assert not app._keyboard_navigation.keyboard
    assert not ring_visible(window.ui_root)


@pytest.mark.parametrize('scale', [80, 100, 125, 150, 200])
@pytest.mark.parametrize('locale', ['ru', 'ar'])
@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
def test_main_source_and_result_have_matching_editable_bounds(window, app, scale, locale, theme):
    window.set_interface_language(locale)
    if window.current_theme != theme:
        window.toggle_theme()
    window.set_ui_scale_percent(scale)
    window.show_main_screen()
    settle(app)
    source, result = window.text_input, window.main_result_view
    assert abs(source.width() - result.width()) <= 1
    assert source.height() == result.height()
    assert source.viewport().height() == result.viewport().height()
    assert window.main_input_actions.height() == window.main_result_actions.height()
    left = window.translate_button.mapTo(window.ui_root, QtCore.QPoint()).y()
    right = window.main_result_copy_button.mapTo(window.ui_root, QtCore.QPoint()).y()
    assert left == right
