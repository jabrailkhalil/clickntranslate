"""User-visible settings must fit the actual scaled application viewport."""
from unittest import mock
import json
import pytest
from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QStyle, QStyleOptionComboBox
import main
import settings_window
from qt_layout_test_support import ensure_layout_fonts


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    ensure_layout_fonts(app)
    with mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True), \
         mock.patch.object(main.DarkThemeApp, 'save_config'), \
         mock.patch.object(main.DarkThemeApp, 'ensure_mac_accessibility_for_selection', return_value=True), \
         mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False), \
         mock.patch('ui_scaling.MainWindowScaleController.available_geometry', return_value=QRect(0, 0, 3000, 2000)):
        owner = main.DarkThemeApp()
        owner.show()
        yield owner
        owner.force_quit = True
        owner.close()
        owner.deleteLater()
        app.processEvents()


@pytest.mark.parametrize('language', ['ru', 'en', 'es', 'de', 'fr', 'zh'])
@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
def test_translation_controls_fit_all_languages_and_scales(window, language, theme):
    if window.current_theme != theme:
        window.toggle_theme()
    window.set_interface_language(language)
    window.show_settings()
    settings = window.settings_window
    for scale in (80, 100, 120, 150):
        window._ui_scale_controller.set_percent(scale)
        settings._set_settings_page(1)
        QApplication.processEvents()
        scroll = settings.translation_settings_scroll
        assert scroll.horizontalScrollBar().maximum() == 0
        for control in (settings.ocr_engine_combo, settings.translator_combo,
                        settings.selection_quick_translate_checkbox,
                        settings.selection_quick_translate_mode_automatic):
            rect = QRect(control.mapTo(scroll.viewport(), QPoint()), control.size())
            assert scroll.viewport().rect().contains(rect), (language, scale, control.objectName(), rect)
        for flag in (settings.copy_translated_checkbox, settings.restore_clipboard_checkbox,
                     settings.selection_quick_translate_mode_automatic):
            assert flag.fontMetrics().horizontalAdvance(flag.text()) + 30 <= flag.width() + 2, (language, flag.text())
        settings._set_settings_page(0)
        QApplication.processEvents()
        page = settings.settings_general_page
        for control in (settings.result_window_control, settings.translation_font_control,
                        settings.translation_font_preview, settings.ui_scale_control,
                        settings.copy_history_checkbox, settings.history_checkbox,
                        settings.close_result_on_outside_click_checkbox):
            rect = QRect(control.mapTo(page, QPoint()), control.size())
            assert page.rect().contains(rect), (language, scale, control.objectName(), rect)
            assert control.isVisible()


def test_flags_persist_and_ocr_options_are_reachable(window):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(1)
    for key, flag in (
        ('close_result_window_on_outside_click', settings.close_result_on_outside_click_checkbox),
        ('selection_quick_translate_enabled', settings.selection_quick_translate_checkbox),
    ):
        flag.setChecked(False)
        flag.click()
        assert window.config[key] is True
    settings.selection_quick_translate_mode_automatic.setChecked(True)
    assert window.config['selection_quick_translate_mode'] == 'automatic'
    settings.ocr_options_button.click()
    QApplication.processEvents()
    assert settings.keep_visible_checkbox.isVisible()
    settings.translation_settings_scroll.ensureWidgetVisible(settings.copy_notification_checkbox)
    QApplication.processEvents()
    assert not settings.copy_notification_checkbox.visibleRegion().isEmpty()
    settings.show_hotkeys_screen()
    QApplication.processEvents()
    assert settings.hotkey_back_button.isVisible()
    assert settings.toggle_window_hotkey_input.isVisible()


def test_update_flow_uses_one_embedded_page_and_no_message_boxes(window):
    window.show_settings()
    settings = window.settings_window
    top_levels = set(QApplication.topLevelWidgets())
    with mock.patch.object(settings_window.platform_support, 'supports_in_app_update', return_value=True), \
         mock.patch.object(settings, '_start_update_download') as download:
        settings._show_update_progress('Checking')
        panel = settings._update_progress
        settings._on_update_check_result(json.dumps(dict(status='ready', latest_version='9.9.9',
            asset_name='app.zip', asset_url='https://example.test/app.zip', checksum_url='https://example.test/hash')))
        assert settings._update_progress is panel
        panel.primary.click()
        download.assert_called_once()
        settings._on_update_download_progress('Downloading', 25, 100)
        assert settings._update_progress is panel
        settings._on_update_failed('checksum mismatch')
        assert settings._update_progress is panel
        assert 'checksum' not in panel.label.text() or window.current_interface_language == 'en'
        assert set(QApplication.topLevelWidgets()) == top_levels


def test_active_update_survives_settings_rebuild_and_blocks_duplicate_navigation(window):
    window.show_settings()
    settings = window.settings_window
    settings._update_in_progress = True
    settings._show_update_progress('Downloading')
    panel = settings._update_progress
    settings.init_ui()
    settings._set_settings_page(1)
    QApplication.processEvents()
    assert settings.settings_pages.currentWidget() is panel
    assert settings._update_progress is panel
    settings._update_in_progress = False
    settings._on_update_failed('Network interrupted')
    panel.secondary.click()
    assert settings.settings_pages.currentWidget() is settings.settings_general_page


@pytest.mark.parametrize('language', ['ru','en','es','de','fr','zh'])
def test_api_editor_fits_and_back_returns_to_translation(window, language):
    from provider_settings import show_provider_settings
    from api_providers import PROVIDERS
    window.set_interface_language(language)
    window.show_settings()
    settings=window.settings_window
    with mock.patch('provider_secrets.get_key',return_value=''):
        show_provider_settings(settings)
        page=settings.api_connections_page
        for spec in PROVIDERS:
            page.service.setCurrentIndex(page.service.findData(spec.key))
            QApplication.processEvents()
            assert page.isVisible()
            for control in (page.service,page.address,page.key,page.model,page.back,page.save):
                assert control.isVisible()
            assert page.key.echoMode() == page.key.Password
        page.back.click(); QApplication.processEvents()
        assert settings.settings_pages.currentWidget() is settings.settings_updates_page


def test_translation_footer_matches_general_button_rows(window):
    window.show_settings()
    settings=window.settings_window
    assert settings.translation_action_panel.height() == settings.settings_action_panel.height()
    for button in (settings.ocr_languages_btn,settings.copy_history_btn,settings.translation_history_btn,
                   settings.api_connections_button,settings.ocr_options_button):
        assert button.height() == settings.clear_cache_btn.height()
        assert button.font().pixelSize() == settings.clear_cache_btn.font().pixelSize()
        assert 'padding:0 6px' in button.styleSheet()
