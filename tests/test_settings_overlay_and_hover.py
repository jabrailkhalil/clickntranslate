"""Language overlays, physical action borders and pointer feedback regressions."""
import re
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

import main
from button_styles import button_palette, set_pointer_hover
from interface_language_picker import PICKER_TEXT
from test_desktop_ux import app, window
from ui_scaling import widget_global_rect


def settle(app):
    for _ in range(4):
        app.processEvents()


def move(view, point, app):
    global_point = view.viewport().mapToGlobal(point)
    event = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(point),
                             QtCore.QPointF(global_point), QtCore.Qt.NoButton,
                             QtCore.Qt.NoButton, QtCore.Qt.NoModifier)
    app.sendEvent(view.viewport(), event)
    settle(app)


@pytest.mark.parametrize('page', range(4))
def test_language_picker_preserves_the_settings_underneath(window, app, page):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(page)
    settle(app)
    active = settings.settings_pages.currentWidget()
    before = settings.geometry(), active.geometry(), window.size()
    image = settings.grab().toImage()
    window.show_interface_language_menu()
    picker = window._interface_language_picker
    settle(app)
    assert settings.isVisible() and active.isVisible()
    assert (settings.geometry(), active.geometry(), window.size()) == before
    # Below the overlay, the current page still paints exactly the same pixels.
    edge = picker.y()+picker.height()-settings.y()+3
    after = settings.grab().toImage()
    for y in range(edge, settings.height(), 10):
        assert image.pixelColor(10, y) == after.pixelColor(10, y)
    picker.close_button.click()
    assert settings.settings_pages.currentIndex() == page


@pytest.mark.parametrize('page', [None, 0, 1, 2, 3])
def test_language_changes_live_while_the_same_overlay_stays_open(window, app, page):
    window.text_input.setPlainText('Keep the draft')
    if page is not None:
        window.show_settings()
        window.settings_window._set_settings_page(page)
    window.show_interface_language_menu()
    picker = window._interface_language_picker
    for index, locale in enumerate(main.INTERFACE_LANGUAGE_BY_CODE):
        picker.set_page(index//10)
        picker.buttons[locale].click()
        settle(app)
        assert window.current_interface_language == locale
        assert window._interface_language_picker is picker and picker.isVisible()
        assert picker.title.text() == PICKER_TEXT[locale][0]
        assert picker.buttons[locale].property('current')
        assert sum(bool(button.property('current')) for button in picker.buttons.values()) == 1
        if page is not None:
            assert window.settings_window.isVisible()
            assert window.settings_window.settings_pages.currentIndex() == page
            assert window.settings_window._ui_language == locale
    picker.close_button.click()
    window.show_main_screen()
    assert window.text_input.toPlainText() == 'Keep the draft'


@pytest.mark.parametrize('locale', list(main.INTERFACE_LANGUAGE_BY_CODE))
@pytest.mark.parametrize('dark', [True, False])
def test_connected_button_corners_and_dividers_follow_the_physical_grid(window, app, locale, dark):
    window.set_interface_language(locale)
    if (window.current_theme != 'Светлая') != dark:
        window.toggle_theme()
    window.show_settings()
    settings = window.settings_window
    for page, panel_name in ((0, 'settings_action_panel'), (1, 'translation_action_panel')):
        settings._set_settings_page(page)
        settle(app)
        panel = getattr(settings, panel_name)
        grid = panel.layout()
        for index in range(grid.count()):
            button = grid.itemAt(index).widget()
            rect = button.geometry()
            top = rect.top() == 1
            bottom = rect.bottom() == panel.height()-2
            left = rect.left() == 1
            right = rect.right() == panel.width()-2
            for corner, expected in (('top-left', top and left), ('top-right', top and right),
                                     ('bottom-left', bottom and left), ('bottom-right', bottom and right)):
                values = re.findall(r'border-'+corner+r'-radius:(\d+)px', button.styleSheet())
                assert values and int(values[-1]) == (6 if expected else 0), (locale, corner, rect)
            assert ('border-left:1px solid' in button.styleSheet()) == (not left)
        # Outer border remains continuous at all four straight edges.
        image = panel.grab().toImage()
        border = button_palette(dark)['border']
        for x, y in ((panel.width()//2, 0), (panel.width()//2, panel.height()-1),
                     (0, panel.height()//2), (panel.width()-1, panel.height()//2)):
            assert image.pixelColor(x, y).name() == border, (locale, dark, x, y)


@pytest.mark.parametrize('locale', ['ru', 'ar', 'hi'])
@pytest.mark.parametrize('scale', [80, 100, 125, 180])
def test_hover_recovers_without_an_enter_event_and_tracks_both_directions(window, app, locale, scale):
    window.set_interface_language(locale)
    window.show_settings()
    window.set_ui_scale_percent(scale)
    settle(app)
    settings = window.settings_window
    view = window._ui_scale_controller.view
    buttons = [settings.clear_cache_btn, settings.reset_btn, settings.update_btn,
               settings.export_settings_btn, settings.import_settings_btn,
               settings.create_bug_report_btn, settings.hotkeys_button]
    for button in buttons+list(reversed(buttons)):
        point = window._ui_scale_controller.map_widget_to_view(button)
        # Simulate a missing Enter while Qt still considers the pointer inside.
        set_pointer_hover(button, False)
        button.setAttribute(QtCore.Qt.WA_UnderMouse, True)
        move(view, point, app)
        assert button.property('pointerHover'), (locale, scale, button.text())
        assert button.underMouse()
        assert button.grab().toImage().pixelColor(button.width()//2, 5).name() != button_palette(True)['surface']
        assert all(not other.property('pointerHover') for other in buttons if other is not button)
    app.sendEvent(view.viewport(), QtCore.QEvent(QtCore.QEvent.Leave))
    assert all(not button.property('pointerHover') for button in buttons)


def test_overlay_occludes_hover_only_where_it_covers_buttons(window, app):
    window.show_settings()
    window.show_interface_language_menu()
    settle(app)
    view = window._ui_scale_controller.view
    picker = window._interface_language_picker
    button = picker.buttons['en']
    move(view, window._ui_scale_controller.map_widget_to_view(button), app)
    assert button.property('pointerHover')
    lower = window.settings_window.reset_btn
    assert widget_global_rect(picker).bottom() < widget_global_rect(lower).top()
    move(view, window._ui_scale_controller.map_widget_to_view(lower), app)
    assert lower.property('pointerHover') and not button.property('pointerHover')


@pytest.mark.parametrize('kind,open_method,back_method', [
    ('history', 'show_history_view', 'back_from_history'),
    ('copy_history', 'show_copy_history_view', 'back_from_copy_history'),
    ('hotkeys', 'show_hotkeys_screen', 'back_from_hotkeys'),
])
def test_language_overlay_keeps_secondary_screen_and_its_back_destination(window, app, kind, open_method, back_method):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(1)
    with (mock.patch('settings_window.ensure_json_file'),
          mock.patch('settings_window.open', mock.mock_open(read_data='[]'))):
        getattr(settings, open_method)()
        settle(app)
        window.show_interface_language_menu()
        picker = window._interface_language_picker
        for locale in ('ar', 'tr', 'en'):
            picker.buttons[locale].click()
            settle(app)
            assert window._interface_language_picker is picker
            assert settings._secondary_view_kind == kind
            assert settings.secondary_view_shell.isVisible()
            assert settings._secondary_return_page == 1
        picker.close_button.click()
        getattr(settings, back_method)()
        settle(app)
        assert settings.settings_pages.currentIndex() == 1


def test_hover_releases_when_target_is_disabled_or_covered_and_does_not_repolish_on_every_move(window, app):
    window.show_settings()
    settle(app)
    button = window.settings_window.reset_btn
    view = window._ui_scale_controller.view
    point = window._ui_scale_controller.map_widget_to_view(button)
    move(view, point, app)
    assert button.property('pointerHover')
    button.setEnabled(False)
    move(view, point, app)
    assert not button.property('pointerHover')
    button.setEnabled(True)
    move(view, point, app)
    assert button.property('pointerHover')
    # Once the target is stable, subsequent pointer moves need no stylesheet walk.
    with mock.patch.object(button.style(), 'polish', wraps=button.style().polish) as polish:
        move(view, point+QtCore.QPoint(1, 0), app)
        move(view, point+QtCore.QPoint(2, 0), app)
        assert not polish.called
