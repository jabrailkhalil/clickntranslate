"""Desktop DPI, companion behavior and hover hints are explicit UI contracts."""
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets, sip
from PyQt5.QtTest import QTest

import main
import mode_coordinator
from assistant_settings import assistant_preferences
from desktop_assistant import DesktopAssistant
from ui_scaling import desktop_control_scale, MainWindowScaleController, ScaleArrowButton, retain_scale_click


@pytest.fixture
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def window(app, tmp_path):
    import portable_paths
    with (mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True),
          mock.patch.object(main, 'get_cached_config', return_value=dict(main.DEFAULT_CONFIG)),
          mock.patch.object(main.DarkThemeApp, 'save_config'),
          mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False),
          mock.patch.object(portable_paths, 'portable_base_dir', return_value=str(tmp_path)),
          mock.patch.object(MainWindowScaleController, 'available_geometry', return_value=QtCore.QRect(0, 0, 2560, 1400))):
        window = main.DarkThemeApp()
        window.show()
        yield window
        window.force_quit = True
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()


@pytest.mark.parametrize('dpi,dpr,expected', [(96, 1, 1), (144, 1, 1.5), (192, 1, 2), (96, 2, 1)])
def test_desktop_controls_use_monitor_logical_dpi_not_double_dpr(dpi, dpr, expected):
    screen = SimpleNamespace(logicalDotsPerInch=lambda: dpi, devicePixelRatio=lambda: dpr)
    with mock.patch('ui_scaling.sys.platform', 'win32'):
        assert desktop_control_scale(screen) == expected


def test_compact_capture_flags_follow_dpi_but_ignore_main_zoom(app):
    from capture_widgets import CaptureLanguageCombo
    from window_appearance import style_capture_controls
    overlay = QtWidgets.QWidget()
    overlay.resize(2560, 1440)
    combo = CaptureLanguageCombo(overlay)
    combo.addItem('EN', 'en')
    try:
        for dpi_factor in (1., 1.5, 2.):
            with mock.patch('ui_scaling.desktop_control_scale', return_value=dpi_factor):
                for percent in (80, 100, 150, 200):
                    before = overlay.geometry()
                    style_capture_controls(overlay, {'ui_scale_percent': percent}, [combo])
                    assert combo.iconSize() == QtCore.QSize(20, 20) * dpi_factor
                    assert combo.size() == QtCore.QSize(108, 36) * dpi_factor
                    assert overlay.geometry() == before
    finally:
        overlay.deleteLater()


def test_tooltip_font_and_padding_follow_owner_scale_without_double_scaling(window, app):
    from styled_dialogs import _hover_tooltip_document
    label = QtWidgets.QLabel('A readable explanation of this control')
    label.setProperty('_q_stylesheet_parent', window.text_input)
    try:
        heights = []
        for percent in (80, 100, 150, 200, 100):
            window.set_ui_scale_percent(percent)
            document, size = _hover_tooltip_document(label, QtCore.QPoint(100, 100))
            factor = window._ui_scale_controller.effective_percent / main.BASE_SCALE
            assert document.defaultFont().pixelSize() == max(12, round(13 * factor))
            assert label.property('tooltip_padding').x() == round(8 * factor)
            heights.append(size.height())
        assert heights[-1] == heights[1]
        assert heights[3] > heights[1]
    finally:
        label.deleteLater()


def test_companion_preferences_can_be_edited_before_enabling(window, app):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    assert not page.toggle.isChecked()
    assert page.options.isEnabled()
    assert 'speed' not in page.values and not hasattr(page, 'pause_walk')
    page.mode_combo.setCurrentIndex(page.mode_combo.findData('animated'))
    assert 'speed' not in page.values and not hasattr(page, 'pause_walk')
    page.values['size'].setValue(130)
    assert window.config['desktop_assistant_size'] == 130
    assert getattr(window, '_desktop_assistant', None) is None
    page.toggle.click()
    assert window._desktop_assistant.anchor.behavior == 'idle'
    page.toggle.click()
    assert window._desktop_assistant is None
    assert page.options.isEnabled()
    page.toggle.click()
    assert page.values['size'].value() == 130
    page.mode_combo.setCurrentIndex(page.mode_combo.findData('portrait'))
    assert page.mode_combo.currentData() == 'portrait'
    assert window._desktop_assistant.anchor.behavior == 'idle'


def test_hover_and_menu_keep_reactions_running_and_capture_hides_pet(window, app):
    window.config['desktop_assistant_appearance'] = 'walking'
    window.set_desktop_assistant_enabled(True)
    helper = window._desktop_assistant
    anchor = helper.anchor
    before = anchor.grab().toImage()
    anchor.enterEvent(QtCore.QEvent(QtCore.QEvent.Enter))
    assert anchor.grab().toImage() == before
    assert anchor._animation.isActive()
    helper.request_action('walk')
    assert anchor._animation.isActive()
    anchor.leaveEvent(QtCore.QEvent(QtCore.QEvent.Leave))
    assert anchor._animation.isActive()
    start = anchor.pos()
    anchor._advance(.25)
    assert anchor.pos() == start
    helper.toggle_menu()
    assert anchor._animation.isActive()
    helper.menu.hide()
    assert anchor._animation.isActive()
    mode_coordinator.request_mode('ux-qa', lambda: None)
    assert not anchor.isVisible() and not anchor._animation.isActive()
    mode_coordinator.release_mode('ux-qa')
    assert anchor.isVisible() and anchor._animation.isActive()
    helper.request_action('idle')
    assert anchor._animation.isActive()
    position = anchor.pos()
    helper.request_action('hop')  # Removed pseudo-animation cannot reactivate it.
    anchor._advance(1.)
    assert anchor._animation.isActive()
    assert anchor.pos() == position


def test_companion_does_not_write_config_every_walk_frame_and_returns_home(window):
    window.config['desktop_assistant_appearance'] = 'walking'
    window.set_desktop_assistant_enabled(True)
    helper = window._desktop_assistant
    helper.anchor.move(200, 200)
    helper.save_position()
    origin = helper.anchor.pos()
    helper.request_action('walk')
    with mock.patch.object(window, 'save_config') as save:
        for _ in range(20):
            helper.anchor._advance(.05)
        save.assert_not_called()
    assert helper.anchor.pos() == origin
    helper.request_action('home')
    assert helper.anchor.pos() == origin


def test_companion_invalid_preferences_are_safe():
    values = assistant_preferences({'desktop_assistant_behavior': [], 'desktop_assistant_size': float('nan'),
                                   'desktop_assistant_opacity': 999, 'desktop_assistant_speed': True})
    assert values['desktop_assistant_behavior'] == 'idle'
    assert values['desktop_assistant_size'] == 100
    assert values['desktop_assistant_opacity'] == 100
    assert values['desktop_assistant_speed'] == 40


def test_pointer_compensation_only_runs_for_an_explicit_native_scale_click(app):
    button = ScaleArrowButton()
    try:
        with (mock.patch.object(QtWidgets.QApplication, 'platformName', return_value='windows'),
              mock.patch.object(QtGui.QCursor, 'pos', return_value=QtCore.QPoint(0, 0)),
              mock.patch.object(QtGui.QCursor, 'setPos') as move):
            retain_scale_click(button, QtCore.QPoint(100, 100))
            move.assert_not_called()
            button.click_global = QtCore.QPoint(0, 0)
            retain_scale_click(button, QtCore.QPoint(100, 100))
            move.assert_called_once_with(QtCore.QPoint(100, 100))
    finally:
        button.deleteLater()


def test_scale_arrow_counts_the_second_click_in_a_double_click(app):
    button = ScaleArrowButton()
    button.resize(40, 30)
    button.show()
    clicks = []
    button.clicked.connect(lambda: clicks.append(button.click_global))
    point = button.rect().center()
    try:
        QTest.mouseClick(button, QtCore.Qt.LeftButton, pos=point)
        # Qt sends a double-click press instead of the second ordinary press.
        QTest.mouseDClick(button, QtCore.Qt.LeftButton, pos=point)
        QTest.mouseRelease(button, QtCore.Qt.LeftButton, pos=point)
        assert len(clicks) == 2
        assert all(position == button.mapToGlobal(point) for position in clicks)
        assert button.click_global is None
    finally:
        button.close()
        button.deleteLater()


def test_status_tip_uses_desktop_dpi_not_main_zoom(app):
    from styled_dialogs import StatusPopup
    tip = StatusPopup()
    try:
        with mock.patch('ui_scaling.desktop_control_scale', return_value=1.5):
            tip._refresh_theme()
            initial = tip.styleSheet()
            assert 'font-size: 20px' in initial
            app.setProperty('ui_scale_percent', 200)
            tip._refresh_theme()
            assert tip.styleSheet() == initial
    finally:
        app.setProperty('ui_scale_percent', 100)
        tip.deleteLater()


@pytest.mark.parametrize('choice', ['start', 'shortcut', 'cancel'])
def test_dynamic_help_runs_only_the_explicit_action(window, choice):
    box = mock.MagicMock()
    start, shortcut, cancel = object(), object(), object()
    box.addButton.side_effect = [start, shortcut, cancel]
    box.clickedButton.return_value = {'start': start, 'shortcut': shortcut, 'cancel': cancel}[choice]
    with (mock.patch.object(main, 'QMessageBox', return_value=box),
          mock.patch.object(window, 'launch_game_translate') as launch,
          mock.patch.object(window, '_offer_hotkey_settings') as hotkey):
        window.show_dynamic_translation_help()
        assert launch.call_count == int(choice == 'start')
        assert hotkey.call_count == int(choice == 'shortcut')
        assert 'Ctrl' in box.setText.call_args.args[0]



def test_clicking_empty_scaled_canvas_clears_number_selection_and_tab_arrow_focus(window, app):
    window.show_assistant_settings()
    app.processEvents()
    page = window.settings_window.settings_assistant_page
    field = page.values['opacity']
    editor = field.lineEdit()
    controller = window._ui_scale_controller
    editor.setFocus(QtCore.Qt.MouseFocusReason)
    editor.selectAll()
    QTest.keyClicks(editor, '77')
    blank = controller.map_widget_to_view(page.mascot_preview, QtCore.QPoint(8, 8))
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton, pos=blank)
    app.processEvents()
    assert field.value() == 77
    assert window.config['desktop_assistant_opacity'] == 77
    assert not editor.hasSelectedText() and not editor.hasFocus()
    field.decrease.setFocus(QtCore.Qt.TabFocusReason)
    assert field.decrease.property('keyboardFocus')
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton, pos=blank)
    app.processEvents()
    assert not field.decrease.property('keyboardFocus')
    assert not field.decrease.hasFocus()


def test_background_click_finishes_scale_edit_in_real_proxy(window, app):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(0)
    app.processEvents()
    editor = settings.ui_scale_value
    editor.setFocus(QtCore.Qt.MouseFocusReason)
    editor.selectAll()
    QTest.keyClicks(editor, '125')
    controller = window._ui_scale_controller
    blank = controller.map_widget_to_view(settings.settings_general_page, QtCore.QPoint(400, 170))
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton, pos=blank)
    app.processEvents()
    assert window.config['ui_scale_percent'] == 125
    assert not editor.hasSelectedText() and not editor.hasFocus()


@pytest.mark.parametrize('deactivate', [False, True])
def test_arrow_hover_clears_even_if_qt_keeps_native_under_mouse_state(app, deactivate):
    from number_controls import NumberStepper
    field = NumberStepper()
    field.setRange(0, 200)
    field.setValue(100)
    field.resize(180, 30)
    field.show()
    app.processEvents()
    arrow = field.decrease
    try:
        arrow.set_pointer_hover(True)
        # Reproduce the stale proxy :hover flag from the screenshot.
        arrow.setAttribute(QtCore.Qt.WA_UnderMouse, True)
        outside = field.mapToGlobal(QtCore.QPoint(170, 15))
        event = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(170, 15),
                                 QtCore.QPointF(outside), QtCore.Qt.NoButton,
                                 QtCore.Qt.NoButton, QtCore.Qt.NoModifier)
        if deactivate:
            arrow.setDown(True)
            app.sendEvent(app, QtCore.QEvent(QtCore.QEvent.ApplicationDeactivate))
            assert not arrow.isDown()
        else:
            app.sendEvent(field, event)
        app.processEvents()
        assert not arrow.property('pointerHover')
        color = arrow.grab().toImage().pixelColor(4, 4).name()
        from button_styles import button_palette
        assert color != button_palette(True)['hover']
    finally:
        field.close()
        field.deleteLater()


@pytest.mark.parametrize('percent', [80, 125, 180])
def test_reset_hover_clears_outside_moved_scaled_canvas(window, app, percent):
    from ui_scaling import widget_global_rect
    window.set_ui_scale_percent(percent)
    window.move(320, 90)
    window.show_settings()
    settings = window.settings_window
    app.processEvents()
    button = settings.reset_btn
    app.sendEvent(button, QtCore.QEvent(QtCore.QEvent.Enter))
    button.setAttribute(QtCore.Qt.WA_UnderMouse, True)
    assert button.underMouse()
    # The native viewport receives the move even when the embedded button
    # misses its Leave event. Its old mapFromGlobal ignores the proxy scale.
    outside = widget_global_rect(settings.ocr_engine_combo).center()
    viewport = window._ui_scale_controller.view.viewport()
    event = QtGui.QMouseEvent(QtCore.QEvent.MouseMove,
                             QtCore.QPointF(viewport.mapFromGlobal(outside)),
                             QtCore.QPointF(outside), QtCore.Qt.NoButton,
                             QtCore.Qt.NoButton, QtCore.Qt.NoModifier)
    app.sendEvent(viewport, event)
    assert not button.underMouse()
    assert not button.property('pointerHover')
    assert not button.property('keyboardFocus')


@pytest.mark.parametrize('header_height', [32, 54])
def test_package_scrollbar_only_spans_rows_and_reaches_last_package(app, header_height):
    from package_table import PackageTable
    table = PackageTable()
    table.setColumnCount(4)
    table.setHorizontalHeaderLabels(['', 'Language', 'Package', 'Status'])
    table.horizontalHeader().setFixedHeight(header_height)
    table.setRowCount(60)
    table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
    for row in range(60):
        for column in range(4):
            table.setItem(row, column, QtWidgets.QTableWidgetItem(str(row)))
    table.resize(500, 260)
    try:
        table.show()
        for _ in range(3):
            app.processEvents()
        bar = table.verticalScrollBar()
        top = bar.mapTo(table, QtCore.QPoint()).y()
        bottom = top + bar.height()
        rows_top = table.viewport().mapTo(table, QtCore.QPoint()).y()
        assert top >= rows_top
        assert bottom <= rows_top + table.viewport().height()
        bar.setValue(bar.maximum())
        assert table.visualItemRect(table.item(59, 1)).intersects(table.viewport().rect())
        table.horizontalHeader().setFixedHeight(header_height + 12)
        for _ in range(3):
            app.processEvents()
        assert bar.mapTo(table, QtCore.QPoint()).y() >= table.viewport().mapTo(table, QtCore.QPoint()).y()
    finally:
        table.close()
        table.deleteLater()
