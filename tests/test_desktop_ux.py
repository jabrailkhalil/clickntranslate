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
    assert page.motion_options.isHidden()
    page.show_category('dynamic')
    page.appearance_buttons['walking'].click()
    assert page.motion_options.isVisible()
    page.values['size'].setValue(130)
    assert window.config['desktop_assistant_size'] == 130
    assert getattr(window, '_desktop_assistant', None) is None
    page.toggle.click()
    assert window._desktop_assistant.anchor.behavior == 'walk'
    page.toggle.click()
    assert window._desktop_assistant is None
    assert page.options.isEnabled()
    page.toggle.click()
    assert page.values['size'].value() == 130
    page.show_category('static')
    page.appearance_buttons['sleep_icon'].click()
    assert page.motion_options.isHidden()
    assert window._desktop_assistant.anchor.behavior == 'idle'


def test_idle_hover_has_no_outline_and_walking_pauses_for_menu_capture_and_drag(window, app):
    window.config['desktop_assistant_appearance'] = 'walking'
    window.set_desktop_assistant_enabled(True)
    helper = window._desktop_assistant
    anchor = helper.anchor
    before = anchor.grab().toImage()
    anchor.enterEvent(QtCore.QEvent(QtCore.QEvent.Enter))
    assert anchor.grab().toImage() == before
    assert not anchor._animation.isActive()
    helper.request_action('walk')
    assert not anchor._animation.isActive()
    anchor.leaveEvent(QtCore.QEvent(QtCore.QEvent.Leave))
    assert anchor._animation.isActive()
    start = anchor.pos()
    anchor._advance(.25)
    assert anchor.pos() != start
    helper.toggle_menu()
    assert not anchor._animation.isActive()
    helper.menu.hide()
    assert anchor._animation.isActive()
    mode_coordinator.request_mode('ux-qa', lambda: None)
    assert not anchor.isVisible() and not anchor._animation.isActive()
    mode_coordinator.release_mode('ux-qa')
    assert anchor.isVisible() and anchor._animation.isActive()
    helper.request_action('idle')
    assert not anchor._animation.isActive()
    helper.request_action('hop')  # Removed pseudo-animation cannot reactivate it.
    anchor._advance(1.)
    assert not anchor._animation.isActive()


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
    assert helper.anchor.pos() != origin
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
