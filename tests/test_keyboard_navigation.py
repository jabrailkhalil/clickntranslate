"""Operate real widgets without clipboard changes, global hooks or mouse input."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import keyboard_navigation as keyboard
from settings_sections import VISUAL_PAGE_ORDER, PAGE_OCR, PAGE_COMPANION
from test_desktop_ux import app, window
from test_capture_region_memory import capture
from test_dynamic_workspace import isolated, make_overlay


@pytest.fixture(autouse=True)
def restore_application_keyboard_state(app):
    direction = app.layoutDirection()
    yield
    app.setLayoutDirection(direction)
    navigation = getattr(app, '_keyboard_navigation', None)
    if navigation is not None:
        dialog = navigation._help_dialog
        if dialog is not None:
            from PyQt5 import sip
            if not sip.isdeleted(dialog):
                dialog.close()
        navigation._help_dialog = None
        navigation.keyboard = False
        navigation._hide_ring()


def focused(root):
    return root.focusWidget()


def test_tab_uses_visible_reading_order_and_skips_disabled_and_internal_controls(app):
    keyboard.install_keyboard_navigation(app)
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    last = QtWidgets.QPushButton('Last', dialog)  # Created out of reading order.
    first = QtWidgets.QCheckBox('First', dialog)
    editor = QtWidgets.QPlainTextEdit(dialog)
    number = QtWidgets.QSpinBox(dialog)
    hidden = QtWidgets.QPushButton('Hidden', dialog)
    disabled = QtWidgets.QPushButton('Disabled', dialog)
    disabled.setEnabled(False)
    for widget in (first, editor, number, disabled, hidden, last):
        layout.addWidget(widget)
    hidden.hide()
    dialog.show()
    app.processEvents()
    try:
        controls = keyboard.tab_stops(dialog)
        assert controls == [first, editor, number, last]
        keyboard.focus_control(first)
        for widget in (editor, number, last, first):
            QTest.keyClick(focused(dialog), QtCore.Qt.Key_Tab)
            assert focused(dialog) is widget
        QTest.keyClick(first, QtCore.Qt.Key_Backtab)
        assert focused(dialog) is last
        QTest.keyClick(last, QtCore.Qt.Key_Return)
        QTest.keyClick(first, QtCore.Qt.Key_Return)
        assert first.isChecked()
        assert editor.toPlainText() == ''
    finally:
        dialog.close()
        dialog.deleteLater()


def test_keyboard_focus_ring_disappears_on_mouse_input(app):
    keyboard.install_keyboard_navigation(app)
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    button = QtWidgets.QPushButton('Action')
    layout.addWidget(button)
    dialog.show()
    app.processEvents()
    try:
        keyboard.focus_control(button)
        QTest.keyClick(button, QtCore.Qt.Key_Tab)
        assert dialog._keyboard_focus_ring.isVisible()
        QTest.mouseClick(button, QtCore.Qt.LeftButton)
        assert not dialog._keyboard_focus_ring.isVisible()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_radio_group_has_one_tab_stop_and_arrows_select_the_other_option(app):
    keyboard.install_keyboard_navigation(app)
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    first = QtWidgets.QRadioButton('First')
    second = QtWidgets.QRadioButton('Second')
    after = QtWidgets.QPushButton('Next')
    for widget in (first, second, after):
        layout.addWidget(widget)
    first.setChecked(True)
    dialog.show()
    app.processEvents()
    try:
        assert keyboard.tab_stops(dialog) == [first, after]
        keyboard.focus_control(first)
        QTest.keyClick(first, QtCore.Qt.Key_Down)
        assert second.isChecked()
        assert keyboard.tab_stops(dialog) == [second, after]
        QTest.keyClick(second, QtCore.Qt.Key_Tab)
        assert focused(dialog) is after
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize('locale', keyboard.LANGUAGES)
def test_all_main_and_settings_controls_are_reachable_in_each_locale(window, app, locale):
    window.set_interface_language(locale)
    window.show_main_screen()
    root = window.ui_root
    for page in (None, *VISUAL_PAGE_ORDER):
        if page is not None:
            if window.settings_window is None:
                window.show_settings()
            window.settings_window._set_settings_page(page)
        app.processEvents()
        controls = keyboard.tab_stops(root)
        assert window.flag_button in controls
        assert window.settings_button in controls
        assert window.close_button in controls
        assert len(controls) >= 12
        keyboard.focus_control(controls[0])
        visited = []
        for _ in controls:
            visited.append(focused(root))
            QTest.keyClick(focused(root), QtCore.Qt.Key_Tab)
        assert visited == controls, (locale, page)
        assert focused(root) is controls[0]


def test_settings_shortcuts_back_and_secondary_history_return(window, app):
    root = window.ui_root
    keyboard.focus_control(window.text_input)
    QTest.keyClick(window.text_input, QtCore.Qt.Key_Comma, QtCore.Qt.ControlModifier)
    settings = window.settings_window
    assert settings is not None and settings._settings_page_index == 0
    for page in (*VISUAL_PAGE_ORDER[1:], VISUAL_PAGE_ORDER[0]):
        QTest.keyClick(focused(root), QtCore.Qt.Key_Tab, QtCore.Qt.ControlModifier)
        assert settings._settings_page_index == page
    QTest.keyClick(focused(root), QtCore.Qt.Key_Backtab, QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier)
    assert settings._settings_page_index == PAGE_COMPANION
    settings.show_history_view()
    app.processEvents()
    QTest.keyClick(root, QtCore.Qt.Key_Left, QtCore.Qt.AltModifier)
    assert not settings._secondary_view_kind and settings._settings_page_index == PAGE_COMPANION
    QTest.keyClick(window.settings_button, QtCore.Qt.Key_Escape)
    assert window.settings_window is None


def test_scaled_window_routes_native_view_keys_to_the_current_control(window, app):
    root = window.ui_root
    view = window._ui_scale_controller.view
    keyboard.focus_control(window.flag_button)
    controls = keyboard.tab_stops(root)
    expected = controls[(controls.index(window.flag_button)+1) % len(controls)]
    QTest.keyClick(view, QtCore.Qt.Key_Tab)
    assert focused(root) is expected
    QTest.keyClick(view, QtCore.Qt.Key_Comma, QtCore.Qt.ControlModifier)
    assert window.settings_window is not None
    QTest.keyClick(view, QtCore.Qt.Key_Tab, QtCore.Qt.ControlModifier)
    assert window.settings_window._settings_page_index == 1


def test_settings_tab_arrows_follow_visual_order(window, app):
    window.show_settings()
    settings = window.settings_window
    app.processEvents()
    keyboard.focus_control(settings.settings_page_tabs[0])
    for page in (*VISUAL_PAGE_ORDER[1:], VISUAL_PAGE_ORDER[0]):
        QTest.keyClick(focused(window.ui_root), QtCore.Qt.Key_Right)
        assert settings._settings_page_index == page


def test_enter_opens_combo_and_escape_only_closes_its_popup(window, app):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(PAGE_OCR)
    combo = settings.ocr_engine_combo
    keyboard.focus_control(combo)
    QTest.keyClick(combo, QtCore.Qt.Key_Return)
    assert combo.view().isVisible()
    QTest.keyClick(combo.view(), QtCore.Qt.Key_Escape)
    assert not combo.view().isVisible()
    assert window.settings_window is settings


def test_header_language_button_restores_focus_after_live_language_change_from_settings(window, app):
    window.show_settings()
    settings = window.settings_window
    app.processEvents()
    assert not hasattr(settings, 'interface_language_button')
    keyboard.focus_control(window.flag_button)
    QTest.keyClick(window.flag_button, QtCore.Qt.Key_Return)
    app.processEvents()
    picker = window._interface_language_picker
    assert picker is not None and window.flag_button.isChecked()
    QTest.keyClick(picker.focusWidget(), QtCore.Qt.Key_Home)
    for _ in range(2):
        QTest.keyClick(picker.focusWidget(), QtCore.Qt.Key_Down)
    QTest.keyClick(picker.focusWidget(), QtCore.Qt.Key_Return)
    for _ in range(4):
        app.processEvents()
    assert window.current_interface_language == 'ar'
    QTest.keyClick(picker.focusWidget(), QtCore.Qt.Key_Escape)
    app.processEvents()
    assert window._interface_language_picker is None
    assert settings._settings_page_index == 0
    assert window.flag_button.hasFocus()


def test_result_window_modes_support_arrow_selection_and_space_toggle(window, app):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(1)
    combo = settings.result_window_control
    keyboard.focus_control(combo)
    QTest.keyClick(combo, QtCore.Qt.Key_Return)
    assert combo.view().isVisible()
    QTest.keyClick(combo.view(), QtCore.Qt.Key_Home)
    mode = combo.itemData(combo.view().currentIndex().row())
    before = combo.is_mode_checked(mode)
    QTest.keyClick(combo.view(), QtCore.Qt.Key_Space)
    assert combo.is_mode_checked(mode) is not before
    assert combo.view().isVisible()
    QTest.keyClick(combo.view(), QtCore.Qt.Key_Escape)
    assert not combo.view().isVisible()


def test_shortcut_recording_keeps_keyboard_commands_for_the_editor(window, app):
    from settings_window import ClearableKeySequenceEdit
    window.show_settings()
    settings = window.settings_window
    settings.show_hotkeys_screen()
    app.processEvents()
    editor = settings.findChild(ClearableKeySequenceEdit)
    keyboard.focus_control(editor)
    QTest.keyClick(editor, QtCore.Qt.Key_Comma, QtCore.Qt.ControlModifier)
    assert settings._secondary_view_kind == 'hotkeys'
    assert 'Ctrl' in editor.hotkeyText()
    controls = keyboard.tab_stops(window.ui_root)
    next_control = controls[(controls.index(editor)+1) % len(controls)]
    QTest.keyClick(editor, QtCore.Qt.Key_Tab)
    assert focused(window.ui_root) is next_control


def test_help_is_localized_and_opens_from_the_active_window(window, app):
    from styled_dialogs import StyledMessageBox
    window.set_interface_language('ar')
    with mock.patch.object(QtWidgets.QMessageBox, 'information', side_effect=AssertionError('Native message boxes must not be used')):
        QTest.keyClick(window.flag_button, QtCore.Qt.Key_F1)
        app.processEvents()
        box = app._keyboard_navigation._help_dialog
        assert isinstance(box, StyledMessageBox)
        assert not isinstance(box, QtWidgets.QMessageBox)
        assert box.parentWidget() is window
        assert box.isVisible() and box.graphicsProxyWidget() is None
        assert box.windowTitle() == keyboard.text('ar', 'title')
        assert 'Ctrl+Tab' in box.text()
        QTest.keyClick(box, QtCore.Qt.Key_Escape)
        app.processEvents()
        assert app._keyboard_navigation._help_dialog is None
        assert window.isVisible()


@pytest.mark.parametrize('locale', keyboard.LANGUAGES)
@pytest.mark.parametrize('dark', [True, False])
def test_real_f1_help_can_be_opened_closed_and_reopened_without_nested_dialogs(window, app, locale, dark):
    window.set_interface_language(locale)
    if (window.current_theme != 'Светлая') != dark:
        window.toggle_theme()
    navigation = app._keyboard_navigation
    for _ in range(2):
        keyboard.focus_control(window.theme_button)
        QTest.keyClick(window._ui_scale_controller.view, QtCore.Qt.Key_F1)
        for _ in range(3):
            app.processEvents()
        box = navigation._help_dialog
        assert box is not None and box.isVisible()
        assert box.windowTitle() == keyboard.text(locale, 'title')
        QTest.keyClick(box, QtCore.Qt.Key_F1)
        app.processEvents()
        assert navigation._help_dialog is box
        assert len([widget for widget in app.topLevelWidgets()
                    if widget.isVisible() and widget.objectName() == 'styledMessageBox']) == 1
        QTest.keyClick(box, QtCore.Qt.Key_Escape)
        app.processEvents()
        assert navigation._help_dialog is None and window.isVisible()
        assert focused(window.ui_root) is window.theme_button


def test_arrow_keys_follow_the_grid_without_activating_buttons(app):
    keyboard.install_keyboard_navigation(app)
    dialog = QtWidgets.QDialog()
    dialog.setLayoutDirection(QtCore.Qt.LeftToRight)
    layout = QtWidgets.QGridLayout(dialog)
    buttons = [QtWidgets.QPushButton(name) for name in ('Top left', 'Top right', 'Bottom left', 'Bottom right')]
    clicks = []
    for index, button in enumerate(buttons):
        layout.addWidget(button, index//2, index % 2)
        button.clicked.connect(lambda checked, index=index: clicks.append(index))
    dialog.show()
    app.processEvents()
    try:
        keyboard.focus_control(buttons[0])
        for key, index in ((QtCore.Qt.Key_Right, 1), (QtCore.Qt.Key_Down, 3),
                           (QtCore.Qt.Key_Left, 2), (QtCore.Qt.Key_Up, 0)):
            QTest.keyClick(focused(dialog), key)
            assert focused(dialog) is buttons[index]
        QTest.keyClick(buttons[0], QtCore.Qt.Key_Up)
        assert focused(dialog) is buttons[0]
        assert not clicks
    finally:
        dialog.close()
        dialog.deleteLater()


def test_arrows_from_closed_combos_navigate_without_changing_the_selected_engine(window, app):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(PAGE_OCR)
    app.processEvents()
    combo = settings.ocr_engine_combo
    before = combo.currentData()
    keyboard.focus_control(combo)
    target = keyboard.spatial_target(window.ui_root, combo, QtCore.Qt.Key_Down)
    assert target is not None
    QTest.keyClick(combo, QtCore.Qt.Key_Down)
    assert focused(window.ui_root) is target
    assert combo.currentData() == before and not combo.view().isVisible()


def test_arrows_from_title_bar_navigate_through_the_scaled_native_view(window):
    keyboard.focus_control(window.flag_button)
    QTest.keyClick(window._ui_scale_controller.view, QtCore.Qt.Key_Right)
    assert focused(window.ui_root) is window.theme_button


@pytest.mark.parametrize('locale', keyboard.LANGUAGES)
def test_settings_arrows_reach_nearby_controls_and_scroll_without_changing_values(window, app, locale):
    import copy
    window.set_interface_language(locale)
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(1)
    app.processEvents()
    root = window.ui_root
    controls = keyboard.tab_stops(root)
    before = copy.deepcopy(window.config)
    for control in controls:
        if not keyboard._uses_arrow_navigation(control) or keyboard._inside(control, 'keyboardTabs') is not None:
            continue
        for key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            keyboard.focus_control(control)
            target = keyboard.spatial_target(root, control, key)
            QTest.keyClick(control, key)
            assert focused(root) is (target or control), (locale, control.objectName(), key)
    assert window.config == before


def test_text_editing_and_value_arrows_keep_their_native_meaning(app):
    from number_controls import ChoiceStepper
    keyboard.install_keyboard_navigation(app)
    dialog = QtWidgets.QDialog()
    dialog.setLayoutDirection(QtCore.Qt.LeftToRight)
    layout = QtWidgets.QVBoxLayout(dialog)
    editor = QtWidgets.QLineEdit('abcd')
    slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
    slider.setValue(30)
    choices = ChoiceStepper([('small','Small'),('large','Large')])
    for widget in (editor, slider, choices):
        layout.addWidget(widget)
    dialog.show()
    app.processEvents()
    try:
        keyboard.focus_control(editor)
        editor.setCursorPosition(2)
        QTest.keyClick(editor, QtCore.Qt.Key_Left)
        assert editor.cursorPosition() == 1 and focused(dialog) is editor
        keyboard.focus_control(slider)
        QTest.keyClick(slider, QtCore.Qt.Key_Right)
        assert slider.value() == 31 and focused(dialog) is slider
        keyboard.focus_control(choices.increase)
        QTest.keyClick(choices.increase, QtCore.Qt.Key_Right)
        assert choices.value() == 'large'
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize('mode', ['copy', 'translate'])
def test_ocr_memory_is_inline_to_the_right_of_languages_on_a_wide_screen(capture, mode):
    config, _, _, create = capture
    value = create(mode)
    languages = [value.lang_combo] + ([value.target_lang_combo] if mode == 'translate' else [])
    def bounds(widget):
        return QtCore.QRect(widget.mapTo(value, QtCore.QPoint()), widget.size())
    assert bounds(value.memory_panel).left() > max(bounds(combo).right() for combo in languages)
    assert abs(bounds(value.memory_panel).center().y()-bounds(value.lang_combo).center().y()) <= 1


def test_ocr_area_can_be_created_moved_resized_and_confirmed_without_mouse(capture, app):
    _, _, captures, create = capture
    value = create()
    QTest.keyClick(value, QtCore.Qt.Key_Right)
    original = QtCore.QRect(value._preview_rect)
    assert original.isValid() and value.rect().contains(original)
    QTest.keyClick(value, QtCore.Qt.Key_Down, QtCore.Qt.ControlModifier)
    assert value._preview_rect == original.translated(0, 10)
    QTest.keyClick(value, QtCore.Qt.Key_Right, QtCore.Qt.ShiftModifier)
    assert value._preview_rect.width() == original.width()+1
    QTest.keyClick(value, QtCore.Qt.Key_F6)
    assert focused(value) is value.lang_combo
    QTest.keyClick(value.lang_combo, QtCore.Qt.Key_F6)
    assert value.hasFocus()
    QTest.keyClick(value, QtCore.Qt.Key_Return)
    assert len(captures) == 1


def test_dynamic_regions_support_keyboard_source_output_multiple_areas_and_cancel(isolated):
    import dynamic_workspace
    config, _ = isolated
    config['game_manual_output'] = True
    selector = dynamic_workspace.PairedRegionSelector()
    try:
        QTest.keyClick(selector, QtCore.Qt.Key_Insert)
        source = QtCore.QRect(selector._regions[0])
        assert selector._outputs == [None]
        assert not selector.start_button.isEnabled()
        QTest.keyClick(selector, QtCore.Qt.Key_Space)
        assert selector._outputs[0] == source and selector.start_button.isEnabled()
        QTest.keyClick(selector, QtCore.Qt.Key_Right, QtCore.Qt.ControlModifier)
        assert selector._outputs[0] == source.translated(10, 0)
        assert selector._regions[0] == source
        QTest.keyClick(selector, QtCore.Qt.Key_N)
        assert len(selector._regions) == 2
        QTest.keyClick(selector, QtCore.Qt.Key_PageUp)
        assert selector._selected_region == 0
        QTest.keyClick(selector, QtCore.Qt.Key_Delete)
        assert len(selector._regions) == 1
        QTest.keyClick(selector, QtCore.Qt.Key_Escape)
        assert not selector.isVisible()
    finally:
        selector.close()


def test_dynamic_output_move_and_resize_buttons_support_arrows_and_lock(isolated):
    overlay = make_overlay(QtCore.QRect(40, 300, 240, 80), 'en', 'ru',
                           output_region=QtCore.QRect(400, 400, 300, 100), style={'locked': False})
    try:
        controls = overlay.controls
        controls.gear.click()
        keyboard.focus_control(controls.move_button)
        QTest.keyClick(controls.move_button, QtCore.Qt.Key_Right)
        assert overlay.output_rect.x() == 401
        keyboard.focus_control(controls.resize_button)
        QTest.keyClick(controls.resize_button, QtCore.Qt.Key_Down)
        assert overlay.output_rect.height() == 101
        controls.locked.setChecked(True)
        QTest.keyClick(controls.move_button, QtCore.Qt.Key_Right)
        assert overlay.output_rect.x() == 401
    finally:
        overlay.close()
