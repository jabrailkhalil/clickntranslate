"""Language selection covers the intended panel without exposed border strips."""
import pytest
from PyQt5 import QtCore

import main
from settings_sections import VISUAL_PAGE_ORDER
from test_desktop_ux import app, window
from ui_scaling import widget_global_rect


def settle(app):
    for _ in range(4):
        app.processEvents()


def mapped_rect(widget, parent):
    return QtCore.QRect(widget.mapTo(parent, QtCore.QPoint()), widget.size())


def assert_home_cover(window, picker):
    expected = mapped_rect(window.main_text_section, picker.parentWidget())
    assert picker.geometry() == expected, (picker.geometry(), expected)
    # Both paths must use the same scaled scene, including native window moves.
    assert widget_global_rect(picker) == widget_global_rect(window.main_text_section)


@pytest.mark.parametrize('locale', list(main.INTERFACE_LANGUAGE_BY_CODE))
def test_home_picker_matches_text_panel_at_every_zoom_and_theme(window, app, locale):
    window.set_interface_language(locale)
    window.text_input.setPlainText('Keep this unfinished text')
    for dark in (True, False):
        if (window.current_theme != 'Светлая') != dark:
            window.toggle_theme()
        for percent in (80, 100, 125, 150, 200):
            window.set_ui_scale_percent(percent)
            settle(app)
            original_size = window.size()
            lower = QtCore.QRect(window.main_shortcut_section.geometry())
            window.show_interface_language_menu()
            settle(app)
            picker = window._interface_language_picker
            assert_home_cover(window, picker)
            assert window.size() == original_size
            assert window.main_shortcut_section.geometry() == lower
            assert window.main_text_section.isVisible()
            assert window.text_input.toPlainText() == 'Keep this unfinished text'
            picker.close_button.click()
            settle(app)
            assert window.text_input.toPlainText() == 'Keep this unfinished text'


@pytest.mark.parametrize('dark', [True, False])
def test_picker_owns_continuous_side_and_bottom_edges(window, app, dark):
    if (window.current_theme != 'Светлая') != dark:
        window.toggle_theme()
    window.show_interface_language_menu()
    settle(app)
    picker = window._interface_language_picker
    scrollbar = picker.scroll.verticalScrollBar()
    for position in (scrollbar.minimum(), scrollbar.maximum()):
        scrollbar.setValue(position)
        settle(app)
        image = picker.grab().toImage()
        width, height = image.width(), image.height()
        for outer, inner in (((0, height//2), (4, height//2)),
                             ((width-1, height//2), (width-5, height//2)),
                             ((width//2, height-1), (width//2, height-5))):
            edge = image.pixelColor(*outer)
            fill = image.pixelColor(*inner)
            assert edge.alpha() >= 240, (dark, position, outer, edge.getRgb())
            contrast = sum(abs(a-b) for a, b in zip(edge.getRgb()[:3], fill.getRgb()[:3]))
            assert contrast >= 12, (dark, position, outer, edge.getRgb(), fill.getRgb())


def test_live_language_changes_do_not_expand_before_home_layout_settles(window, app):
    window.show_interface_language_menu()
    settle(app)
    picker = window._interface_language_picker
    for code in ('es', 'ar', 'hi', 'id', 'en', 'ru'):
        previous = QtCore.QRect(picker.geometry())
        picker.scroll.ensureWidgetVisible(picker.buttons[code], 0, 0)
        picker.buttons[code].click()
        # Relabeling can briefly create an unlaid 640x480 QWidget. Retain the
        # last valid overlay rectangle until the actual layout is settled.
        assert picker.geometry() == previous
        settle(app)
        assert_home_cover(window, picker)


def test_open_picker_tracks_native_window_movement_and_scale_changes(window, app):
    window.show_interface_language_menu()
    settle(app)
    picker = window._interface_language_picker
    for point, percent in ((QtCore.QPoint(240, 100), 125),
                           (QtCore.QPoint(-320, 30), 80),
                           (QtCore.QPoint(80, 60), 150)):
        window.move(point)
        window.set_ui_scale_percent(percent)
        settle(app)
        assert window._interface_language_picker is picker
        assert_home_cover(window, picker)


@pytest.mark.parametrize('page', VISUAL_PAGE_ORDER)
def test_settings_picker_is_a_stable_top_excerpt_without_replacing_the_page(window, app, page):
    settle(app)
    remembered_height = window.main_text_section.height()
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(page)
    settle(app)
    original = QtCore.QRect(settings.geometry())
    active = settings.settings_pages.currentWidget()
    active_geometry = QtCore.QRect(active.geometry())
    window.show_interface_language_menu()
    settle(app)
    picker = window._interface_language_picker
    for locale in ('ar', 'hi', 'pt', 'tr', 'en', 'ru'):
        picker.scroll.ensureWidgetVisible(picker.buttons[locale], 0, 0)
        picker.buttons[locale].click()
        settle(app)
        active = settings.settings_pages.currentWidget()
        frame = mapped_rect(settings, picker.parentWidget())
        assert picker.geometry() == QtCore.QRect(frame.x(), frame.y(), frame.width(), remembered_height)
        assert settings.geometry() == original
        assert active.geometry() == active_geometry
        assert settings.settings_pages.currentIndex() == page
        assert settings.isVisible() and active.isVisible()
        assert picker.height() < settings.height()
    picker.close_button.click()
    settle(app)
    assert window.settings_window is settings and settings.settings_pages.currentIndex() == page


def test_settings_excerpt_uses_last_laid_out_home_height_at_every_scale(window, app):
    settle(app)
    remembered_height = window.main_text_section.height()
    window.show_settings()
    settle(app)
    window.show_interface_language_menu()
    for percent in (80, 100, 125, 150, 200):
        window.set_ui_scale_percent(percent)
        settle(app)
        picker = window._interface_language_picker
        settings = mapped_rect(window.settings_window, picker.parentWidget())
        assert picker.geometry() == QtCore.QRect(settings.x(), settings.y(), settings.width(), remembered_height)


def test_unlaid_hidden_home_widget_cannot_expand_settings_picker(window, app):
    settle(app)
    remembered_height = window.main_text_section.height()
    window.show_settings()
    settle(app)
    # A rebuilt, hidden QWidget starts at 640x480 before layout. This used to
    # expand language selection over most of the application after relabeling.
    window.main_text_section.setGeometry(0, 0, 640, 480)
    window.show_interface_language_menu()
    settle(app)
    picker = window._interface_language_picker
    settings = mapped_rect(window.settings_window, picker.parentWidget())
    assert picker.geometry() == QtCore.QRect(settings.x(), settings.y(), settings.width(), remembered_height)


def test_flat_picker_keeps_the_pressed_flag_and_icon_visible(window, app):
    window.set_interface_language('ru')
    settle(app)
    rect = mapped_rect(window.flag_button, window.ui_root)
    def icon_pixels():
        image = window.ui_root.grab(rect).toImage()
        return sum(1 for y in range(image.height()) for x in range(image.width())
                   if (image.pixelColor(x, y).alpha() > 220
                       and image.pixelColor(x, y).saturation() > 150
                       and (image.pixelColor(x, y).hue() < 15
                            or 205 <= image.pixelColor(x, y).hue() <= 245)))
    before = icon_pixels()
    assert before > 20
    window.show_interface_language_menu()
    settle(app)
    assert window.flag_button.isChecked()
    assert icon_pixels() >= before*.9
