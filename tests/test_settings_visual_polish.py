"""Compact section links and full dynamic language names in the real canvas."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

import main
import ocr
from button_styles import set_pointer_hover
from settings_sections import PAGE_DYNAMIC, VISUAL_PAGE_ORDER
from test_desktop_ux import app, window


def settle(app):
    for _ in range(3):
        app.processEvents()


def rect_in(widget, parent):
    return QtCore.QRect(widget.mapTo(parent, QtCore.QPoint()), widget.size())


def assert_language_text_fits(combo, context):
    option = QtWidgets.QStyleOptionComboBox()
    combo.initStyleOption(option)
    field = combo.style().subControlRect(QtWidgets.QStyle.CC_ComboBox, option,
                                        QtWidgets.QStyle.SC_ComboBoxEditField, combo)
    assert combo.rect().contains(field), (context, field, combo.rect())
    icon_width = 0 if option.currentIcon.isNull() else option.iconSize.width() + 6
    widest = max(combo.fontMetrics().horizontalAdvance(combo.itemText(index))
                 for index in range(combo.count()))
    assert widest + icon_width <= field.width() - 2, (context, widest, icon_width, field)
    assert combo.fontMetrics().height() <= field.height(), (context, combo.fontMetrics().height(), field)
    assert combo.font().pixelSize() == 14


@pytest.mark.parametrize('locale', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
def test_section_buttons_and_longest_dynamic_names_fit_every_theme_and_zoom(window, app, locale):
    """120 real scaled states, with every catalog item available to both fields."""
    catalog = tuple(language.code for language in main.APP_LANGUAGES)
    with (mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=catalog),
          mock.patch.object(ocr, '_translation_targets_for_source', return_value=list(catalog))):
        window.config['translator_engine'] = 'google'
        window.set_interface_language(locale)
        window.show_settings()
        settings = window.settings_window
        for theme in ('Темная', 'Светлая'):
            if window.current_theme != theme:
                window.toggle_theme()
            for scale in (80, 110, 125, 150, 200):
                window.set_ui_scale_percent(scale)
                settings._set_settings_page(PAGE_DYNAMIC)
                settings._populate_game_language_controls(fast=False)
                settle(app)
                source, target = settings.game_source_combo, settings.game_target_combo
                assert source.count() == len(catalog)
                assert target.count() == len(catalog) - 1
                scroll = settings.game_settings_scroll
                row = settings.game_language_row
                scroll.ensureWidgetVisible(row, 0, 0)
                settle(app)
                context = (locale, theme, scale)
                before = (window.size(), settings.geometry(), settings.settings_game_page.geometry(),
                          row.geometry(), settings.game_action_panel.geometry())
                # Selection triggers the actual target refresh and save path.
                source.setCurrentIndex(max(range(source.count()),
                    key=lambda index: source.fontMetrics().horizontalAdvance(source.itemText(index))))
                target.setCurrentIndex(max(range(target.count()),
                    key=lambda index: target.fontMetrics().horizontalAdvance(target.itemText(index))))
                settle(app)
                assert_language_text_fits(source, context + ('source',))
                assert_language_text_fits(target, context + ('target',))
                assert (window.size(), settings.geometry(), settings.settings_game_page.geometry(),
                        row.geometry(), settings.game_action_panel.geometry()) == before, context
                assert abs(source.width() - target.width()) <= 1, context
                assert scroll.horizontalScrollBar().maximum() == 0, context
                assert scroll.viewport().rect().contains(rect_in(row, scroll.viewport())), context
                assert row.rect().contains(rect_in(settings.game_languages_label, row)), context
                assert settings.game_languages_label.fontMetrics().horizontalAdvance(
                    settings.game_languages_label.text()) <= settings.game_languages_label.width(), context
                for control in (source, target, settings.game_swap_button):
                    assert row.rect().contains(rect_in(control, row)), (context, control.objectName())
                footer = settings.game_action_panel
                assert footer.isVisible() and not scroll.isAncestorOf(footer)
                assert settings.settings_game_page.rect().contains(rect_in(footer, settings.settings_game_page))

                navigation = settings.settings_page_navigation
                tabs = sorted(settings.settings_page_tabs, key=lambda tab: tab.geometry().left())
                assert len(tabs) == len(VISUAL_PAGE_ORDER)
                assert navigation.height() == 32
                assert navigation.contentsRect() == navigation.rect().adjusted(1, 0, -1, -1)
                assert abs(rect_in(navigation, settings).center().x() - settings.rect().center().x()) <= 1
                assert navigation.width() == sum(tab.sizeHint().width() for tab in tabs) + 18 + 2*(len(tabs)-1)
                nav_global = rect_in(navigation, window.ui_root)
                header_global = rect_in(window.title_bar, window.ui_root)
                assert nav_global.top() - header_global.bottom() - 1 == 0, context
                for tab in tabs:
                    assert tab.height() == 26 and tab.y() == 3, (context, tab.geometry())
                    assert navigation.rect().contains(tab.geometry())
                    font, area = tab.label_layout()
                    metrics = QtGui.QFontMetrics(font)
                    assert font.pixelSize() == 13
                    assert tab.width() == tab.sizeHint().width(), (context, tab.text(), tab.geometry())
                    assert metrics.horizontalAdvance(tab.text()) <= area.width(), (context, tab.text())
                    assert metrics.height() <= area.height(), (context, tab.text())
                    ink = QtGui.QFontMetricsF(font).boundingRect(tab.text())
                    assert ink.width() <= area.width(), (context, tab.text(), ink, area)
                    assert ink.height() <= area.height(), (context, tab.text(), ink, area)
                for left, right in zip(tabs, tabs[1:]):
                    assert right.x() - (left.x() + left.width()) == 2, context

                template = settings.game_template_combo
                remember = settings.game_remember_template_checkbox
                template_rect, remember_rect = rect_in(template, settings.settings_game_page), rect_in(remember, settings.settings_game_page)
                assert not settings.game_template_label.isVisible(), context
                assert template_rect.center().y() == remember_rect.center().y(), context
                assert remember.sizeHint().width() <= remember.width(), context
                assert template.width() == settings.game_interval_controls.width(), context
                assert rect_in(row, settings.settings_game_page).bottom() < template_rect.top(), context
                assert template_rect.bottom() < rect_in(settings.game_interval_controls, settings.settings_game_page).top(), context


@pytest.mark.parametrize('dark', [True, False])
def test_active_section_uses_text_and_underline_without_a_filled_button(window, app, dark):
    if (window.current_theme != 'Светлая') != dark:
        window.toggle_theme()
    window.show_settings()
    settings = window.settings_window
    first, second = settings.settings_page_tabs[:2]
    for button in settings.settings_page_tabs:
        set_pointer_hover(button, False)
        button.clearFocus()
    first.click()
    settle(app)
    geometry = [tab.geometry() for tab in settings.settings_page_tabs]
    navigation = settings.settings_page_navigation
    selected = navigation.grab().toImage()
    second.click()
    settle(app)
    inactive = navigation.grab().toImage()
    assert geometry == [tab.geometry() for tab in settings.settings_page_tabs]
    assert not first.isChecked() and second.isChecked()
    # Above the text the surface stays unchanged: no selected pill/card fill.
    assert all(selected.pixel(x, first.y()+2) == inactive.pixel(x, first.y()+2)
               for x in range(first.x()+10, first.x()+first.width()-10))
    changed_line = sum(selected.pixel(x, y) != inactive.pixel(x, y)
                       for y in range(navigation.height()-3, navigation.height())
                       for x in range(first.x()+10, first.x()+first.width()-10))
    changed_text = sum(selected.pixel(x, y) != inactive.pixel(x, y)
                       for y in range(first.y()+5, first.y()+first.height()-5)
                       for x in range(first.x()+10, first.x()+first.width()-10))
    assert changed_line > 20 and changed_text > 10


@pytest.mark.parametrize('locale', ['ru', 'ar'])
@pytest.mark.parametrize('dark', [True, False])
def test_field_outlines_share_the_full_row_bounds(window, app, locale, dark):
    """Equal widget heights must also give equal visible, uninset outlines."""
    window.set_interface_language(locale)
    if (window.current_theme != 'Светлая') != dark:
        window.toggle_theme()
    window.show_settings()
    settings = window.settings_window
    edges = ({'#3d3948', '#6f598d', '#9a7fc1', '#9b78c8'} if dark else
             {'#d7cde7', '#ad97cb', '#8063a8', '#9b78c8'})
    companion = settings.settings_assistant_page
    for page, fields in (
            (0, (settings.interface_language_button, settings.ui_scale_field,
                 settings.translation_font_control)),
            (1, (settings.translator_combo, settings.result_window_control)),
            (4, (settings.ocr_engine_combo,)),
            (2, (settings.game_source_combo, settings.game_target_combo,
                 settings.game_template_combo)),
            (3, (companion.mode_combo, *companion.values.values()))):
        settings._set_settings_page(page)
        settings.settings_page_tabs[page].setFocus()
        settle(app)
        for field in fields:
            picture = field.grab().toImage()
            w, h = picture.width(), picture.height()
            for x, y in ((w//2, 0), (0, h//2), (w-1, h//2), (w//2, h-1)):
                assert picture.pixelColor(x, y).name() in edges, (locale, dark, page,
                    field.objectName(), x, y, picture.pixelColor(x, y).name())
