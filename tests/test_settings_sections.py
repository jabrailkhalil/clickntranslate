"""Settings destinations stay reachable in the real fixed, scaled viewport."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QFontMetrics

import main
from settings_sections import (
    PAGE_APPLICATION, PAGE_TRANSLATION, PAGE_DYNAMIC, PAGE_COMPANION, PAGE_OCR,
    PAGE_COUNT, PAGE_CAPTIONS, VISUAL_PAGE_ORDER, page_caption,
)
from test_desktop_ux import app, window


def settle(app):
    for _ in range(3):
        app.processEvents()


def rect_in(widget, parent):
    return QtCore.QRect(widget.mapTo(parent, QtCore.QPoint()), widget.size())


def test_legacy_destinations_have_a_separate_visual_order_and_complete_captions():
    assert (PAGE_APPLICATION, PAGE_TRANSLATION, PAGE_DYNAMIC, PAGE_COMPANION, PAGE_OCR) == (0, 1, 2, 3, 4)
    assert VISUAL_PAGE_ORDER == (0, 1, 4, 2, 3)
    assert PAGE_COUNT == 5
    assert set(PAGE_CAPTIONS) == set(main.INTERFACE_LANGUAGE_BY_CODE)
    for locale in main.INTERFACE_LANGUAGE_BY_CODE:
        captions = [page_caption(locale, page) for page in VISUAL_PAGE_ORDER]
        assert len(set(captions)) == PAGE_COUNT and all(captions), locale


def test_settings_controls_are_in_the_page_their_behavior_belongs_to(window, app):
    window.show_settings()
    settings = window.settings_window
    owners = (
        (PAGE_APPLICATION, settings.settings_general_page,
         ('interface_language_button', 'ui_scale_control', 'translation_font_control',
          'translation_font_preview', 'autostart_checkbox', 'start_minimized_checkbox',
          'button_tooltips_checkbox', 'update_check_on_launch_checkbox')),
        (PAGE_TRANSLATION, settings.settings_updates_page,
         ('translator_combo', 'result_window_control', 'copy_translated_checkbox',
          'replace_select_all_checkbox', 'restore_clipboard_checkbox',
          'close_result_on_outside_click_checkbox', 'translation_offline_button',
          'translation_api_button')),
        (PAGE_OCR, settings.settings_ocr_page,
         ('ocr_engine_combo', 'ocr_join_paragraphs_checkbox', 'keep_visible_checkbox',
          'freeze_screen_checkbox', 'dim_screen_during_ocr_checkbox',
          'ocr_languages_btn', 'ocr_api_button')),
        (PAGE_DYNAMIC, settings.settings_game_page,
         ('game_source_combo', 'game_target_combo', 'game_remember_template_checkbox',
          'game_template_combo', 'game_launch_button')),
        (PAGE_COMPANION, settings.settings_assistant_page,
         ('desktop_assistant_checkbox',)),
    )
    for page_id, page, names in owners:
        settings._set_settings_page(page_id)
        settle(app)
        assert settings.settings_pages.currentWidget() is page
        for name in names:
            control = getattr(settings, name)
            assert page.isAncestorOf(control), (page_id, name)
            assert control.isVisible(), (page_id, name)


@pytest.mark.parametrize('locale', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
def test_five_pages_fit_every_theme_and_scale_and_overflow_is_reachable(window, app, locale):
    """One window per locale covers 600 page states without 600 app startups."""
    window.set_interface_language(locale)
    window.show_settings()
    settings = window.settings_window
    for theme in ('Темная', 'Светлая'):
        if window.current_theme != theme:
            window.toggle_theme()
        for scale in (80, 100, 125, 150, 200):
            window.set_ui_scale_percent(scale)
            settle(app)
            for page_id in VISUAL_PAGE_ORDER:
                settings._set_settings_page(page_id)
                settle(app)
                page = settings.settings_pages.currentWidget()
                context = (locale, theme, scale, page_id)
                assert settings.rect().contains(rect_in(page, settings)), context
                assert settings.settings_pages.count() == PAGE_COUNT
                for tab in settings.settings_page_tabs:
                    font, area = tab.label_layout()
                    assert QFontMetrics(font).horizontalAdvance(tab.text()) <= area.width(), (context, tab.text())
                    assert QFontMetrics(font).height() <= area.height(), (context, tab.text())

                scrolls = page.findChildren(QtWidgets.QScrollArea)
                for scroll in scrolls:
                    assert scroll.horizontalScrollBar().maximum() == 0, (context, scroll.objectName())
                    assert page.rect().contains(rect_in(scroll, page)), context
                    body = scroll.widget()
                    # Every focusable control can be brought fully into view;
                    # a scrollbar extending over the footer cannot satisfy it.
                    controls = [control for control in body.findChildren(QtWidgets.QWidget)
                                if isinstance(control, (QtWidgets.QAbstractButton, QtWidgets.QComboBox,
                                                        QtWidgets.QAbstractSlider))
                                and control.isVisible() and control.height() > 0]
                    assert controls, context
                    for control in controls:
                        assert body.rect().contains(rect_in(control, body)), (context, control.objectName())
                        scroll.ensureWidgetVisible(control, 0, 0)
                        settle(app)
                        assert scroll.viewport().rect().contains(rect_in(control, scroll.viewport())), (context, control.objectName())
                    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                    settle(app)
                    assert scroll.verticalScrollBar().value() == scroll.verticalScrollBar().maximum()

                for name in ('settings_action_panel', 'translation_action_panel', 'ocr_action_panel',
                             'game_action_panel', 'assistant_action_panel'):
                    footer = getattr(settings, name, None)
                    if footer is None or not footer.isVisible() or not page.isAncestorOf(footer):
                        continue
                    assert page.rect().contains(rect_in(footer, page)), (context, name)
                    for scroll in scrolls:
                        assert not scroll.isAncestorOf(footer), (context, name)
                        assert not rect_in(scroll, page).intersects(rect_in(footer, page)), (context, name)

                for control in page.findChildren(QtWidgets.QWidget):
                    if not control.isVisible() or control.height() == 0:
                        continue
                    if isinstance(control, QtWidgets.QCheckBox):
                        assert control.sizeHint().width() <= control.width(), (context, control.text())
                        assert control.fontMetrics().height() <= control.contentsRect().height(), (context, control.text())
                    elif isinstance(control, QtWidgets.QLabel) and control.text():
                        if control.wordWrap():
                            assert control.heightForWidth(control.width()) <= control.height(), (context, control.text())
                        else:
                            assert control.fontMetrics().horizontalAdvance(control.text()) <= control.contentsRect().width(), (context, control.text())
                            assert control.fontMetrics().height() <= control.contentsRect().height(), (context, control.text())


@pytest.mark.parametrize('origin', VISUAL_PAGE_ORDER)
def test_maintenance_and_nested_updater_return_to_the_origin_after_relabeling(window, app, origin):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(origin)
    with mock.patch.object(settings, '_start_update_check'):
        settings.show_maintenance_view()
        settle(app)
        assert settings._secondary_view_kind == 'maintenance'
        for locale in ('ar', 'en'):
            window.set_interface_language(locale)
            window.toggle_theme()
            settle(app)
            assert settings._secondary_view_kind == 'maintenance'
        top_levels = set(app.topLevelWidgets())
        settings._show_update_progress('Checking')
        panel = settings._update_progress
        settings._on_update_failed('Simulated offline update check')
        settle(app)
        panel.secondary.click()
        settle(app)
        assert settings._secondary_view_kind == 'maintenance'
        assert set(app.topLevelWidgets()) == top_levels
        settings.maintenance_back_button.click()
        settle(app)
        assert settings._secondary_view_kind is None
        assert settings.settings_pages.currentIndex() == origin


@pytest.mark.parametrize('locale', ['ru', 'ar'])
def test_companion_custom_image_row_scrolls_without_moving_its_actions(window, app, locale):
    window.config.update(desktop_assistant_appearance='custom',
                         desktop_assistant_image=main.resource_path(main.INTERFACE_LANGUAGE_OPTIONS[0]['icon']))
    window.set_interface_language(locale)
    window.show_settings()
    settings = window.settings_window
    for theme in ('Темная', 'Светлая'):
        if window.current_theme != theme:
            window.toggle_theme()
        for scale in (80, 200):
            window.set_ui_scale_percent(scale)
            settings._set_settings_page(PAGE_COMPANION)
            settle(app)
            page = settings.settings_assistant_page
            scroll = settings.assistant_settings_scroll
            footer = settings.assistant_action_panel
            row = page.custom_image_row
            assert row.isVisible()
            assert page.mascot_preview.height() >= 110
            assert scroll.verticalScrollBar().maximum() > 0
            original = rect_in(footer, page)
            scroll.ensureWidgetVisible(row, 0, 0)
            settle(app)
            assert scroll.viewport().rect().contains(rect_in(row, scroll.viewport()))
            assert page.rect().contains(original)
            assert not scroll.isAncestorOf(footer)
            assert rect_in(footer, page) == original

