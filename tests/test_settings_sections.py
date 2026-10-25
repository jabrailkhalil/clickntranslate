"""Settings destinations stay reachable in the real fixed, scaled viewport."""
from unittest import mock
from contextlib import ExitStack

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QFontMetrics

import main
from settings_window import SettingsWindow
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
         ('ui_scale_control', 'translation_font_control',
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


@pytest.mark.parametrize('locale', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
def test_all_seven_program_tools_stay_visible_in_the_general_footer(window, app, locale):
    window.set_interface_language(locale)
    window.show_settings()
    settings = window.settings_window
    for theme in ('Темная', 'Светлая'):
        if window.current_theme != theme:
            window.toggle_theme()
        for scale in (80, 110, 125, 150, 200):
            window.set_ui_scale_percent(scale)
            settings._set_settings_page(PAGE_APPLICATION)
            settle(app)
            page, panel = settings.settings_general_page, settings.settings_action_panel
            assert panel is settings.application_action_panel
            scroll = settings.application_settings_scroll
            buttons = [getattr(settings, name) for name in (
                'clear_cache_btn', 'reset_btn', 'update_btn', 'export_settings_btn',
                'import_settings_btn', 'create_bug_report_btn', 'hotkeys_button')]
            context = (locale, theme, scale)
            assert panel.layout().rowCount() == 3 and panel.layout().columnCount() == 3
            assert len(panel.findChildren(QtWidgets.QAbstractButton)) == 7
            assert page.rect().contains(rect_in(panel, page)), context
            assert not settings.application_settings_scroll.isAncestorOf(panel)
            assert scroll.horizontalScrollBar().maximum() == 0, context
            footer_position = rect_in(panel, page)
            scroll.ensureWidgetVisible(settings.update_check_on_launch_checkbox, 0, 0)
            settle(app)
            assert scroll.viewport().rect().contains(rect_in(
                settings.update_check_on_launch_checkbox, scroll.viewport())), context
            assert rect_in(panel, page) == footer_position
            for button in buttons:
                assert button.isVisible(), (context, button.text())
                assert panel.rect().contains(rect_in(button, panel)), (context, button.text())
                font, area = button.label_layout()
                metrics = QFontMetrics(font)
                assert metrics.horizontalAdvance(button.text()) <= area.width(), (context, button.text())
                assert metrics.height() <= area.height(), (context, button.text())
            assert settings.settings_pages.count() == PAGE_COUNT
            assert settings.findChild(QtWidgets.QWidget, 'maintenancePage') is None
            assert not hasattr(settings, 'maintenance_button')


def test_general_tool_buttons_keep_their_existing_connected_actions(window, app):
    # Patch before the first Settings construction: existing Qt signal
    # connections retain their callable even if the attribute is later patched.
    assert getattr(window, '_cached_settings_window', None) is None
    bindings = (
        ('clear_cache_btn', 'clear_all_cache'), ('reset_btn', 'reset_settings'),
        ('update_btn', 'check_for_updates'), ('export_settings_btn', 'export_settings'),
        ('import_settings_btn', 'import_settings'), ('hotkeys_button', 'show_hotkeys_screen'),
    )
    with ExitStack() as stack:
        callbacks = [(button, stack.enter_context(mock.patch.object(SettingsWindow, handler)))
                     for button, handler in bindings]
        report = stack.enter_context(mock.patch.object(window, '_create_bug_report'))
        window.show_settings()
        settle(app)
        settings = window.settings_window
        for name, callback in callbacks:
            button = getattr(settings, name)
            assert button.isVisible()
            button.click()
            callback.assert_called_once()
        settings.create_bug_report_btn.click()
        report.assert_called_once_with(settings)


@pytest.mark.parametrize('locale', ['en', 'ar'])
def test_inline_updater_returns_directly_to_general_without_an_extra_tools_page(window, app, locale):
    window.set_interface_language(locale)
    window.show_settings()
    settings = window.settings_window
    for theme in ('Темная', 'Светлая'):
        if window.current_theme != theme:
            window.toggle_theme()
        settle(app)
        top_levels = set(app.topLevelWidgets())
        settings._show_update_progress('Checking')
        panel = settings._update_progress
        settings._on_update_failed('Simulated offline update check')
        settle(app)
        panel.secondary.click()
        settle(app)
        assert set(app.topLevelWidgets()) == top_levels
        assert settings._secondary_view_kind is None
        assert settings.settings_pages.currentWidget() is settings.settings_general_page
        assert settings.update_btn.isVisible() and settings.hotkeys_button.isVisible()


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

