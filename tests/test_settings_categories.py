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


def assert_label_near_field(label, control):
    alignment = QStyle.visualAlignment(label.layoutDirection(), label.alignment())
    ink = label.style().itemTextRect(label.fontMetrics(), label.contentsRect(),
                                    alignment, label.isEnabled(), label.text())
    ink.moveTopLeft(label.mapTo(control.parentWidget(), ink.topLeft()))
    field = control.geometry()
    gap = (ink.left() - field.right() - 1 if label.isRightToLeft()
           else field.left() - ink.right() - 1)
    assert 0 <= gap <= 18, (label.text(), gap, ink, field)


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


@pytest.mark.parametrize('language', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
def test_translation_controls_fit_all_languages_and_scales(window, language, theme):
    if window.current_theme != theme:
        window.toggle_theme()
    window.set_interface_language(language)
    window.show_settings()
    settings = window.settings_window
    for scale in (80, 100, 125, 150, 200):
        window._ui_scale_controller.set_percent(scale)
        settings._set_settings_page(1)
        QApplication.processEvents()
        for label, control in ((settings.translator_engine_label, settings.translator_combo),
                               (settings.result_window_label, settings.result_window_control)):
            assert_label_near_field(label, control)
        scroll = settings.translation_settings_scroll
        assert scroll.horizontalScrollBar().maximum() == 0
        for control in (settings.translator_combo, settings.result_window_control,
                        settings.close_result_on_outside_click_checkbox):
            scroll.ensureWidgetVisible(control, 0, 0)
            QApplication.processEvents()
            rect = QRect(control.mapTo(scroll.viewport(), QPoint()), control.size())
            assert scroll.viewport().rect().contains(rect), (language, scale, control.objectName(), rect)
        for flag in (settings.copy_translated_checkbox, settings.restore_clipboard_checkbox,
                     settings.close_result_on_outside_click_checkbox):
            assert flag.fontMetrics().horizontalAdvance(flag.text()) + 30 <= flag.width() + 2, (language, flag.text())
        settings._set_settings_page(4)
        QApplication.processEvents()
        assert_label_near_field(settings.ocr_engine_label, settings.ocr_engine_combo)
        scroll = settings.ocr_settings_scroll
        assert scroll.horizontalScrollBar().maximum() == 0
        for control in (settings.ocr_engine_combo, settings.ocr_join_paragraphs_checkbox,
                        settings.freeze_screen_checkbox, settings.keep_visible_checkbox,
                        settings.copy_notification_checkbox):
            scroll.ensureWidgetVisible(control, 0, 0)
            QApplication.processEvents()
            rect = QRect(control.mapTo(scroll.viewport(), QPoint()), control.size())
            assert scroll.viewport().rect().contains(rect), (language, scale, control.objectName(), rect)
        settings._set_settings_page(0)
        QApplication.processEvents()
        page = settings.settings_general_page
        assert not hasattr(settings, 'interface_language_button')
        for control in (settings.translation_font_control,
                        settings.translation_font_preview, settings.ui_scale_control,
                        settings.copy_history_checkbox, settings.history_checkbox):
            rect = QRect(control.mapTo(page, QPoint()), control.size())
            assert page.rect().contains(rect), (language, scale, control.objectName(), rect)
            assert control.isVisible()


def test_flags_persist_and_ocr_options_are_reachable(window):
    window.show_settings()
    settings = window.settings_window
    for page, key, flag in (
        (1, 'close_result_window_on_outside_click', settings.close_result_on_outside_click_checkbox),
        (4, 'ocr_join_paragraphs', settings.ocr_join_paragraphs_checkbox),
        (4, 'freeze_screen_on_ocr', settings.freeze_screen_checkbox),
    ):
        settings._set_settings_page(page)
        flag.setChecked(False)
        flag.click()
        assert window.config[key] is True
    QApplication.processEvents()
    assert settings.keep_visible_checkbox.isVisible()
    assert not hasattr(settings, 'ocr_options_button')
    assert not hasattr(settings, 'selection_quick_translate_checkbox')
    settings._set_settings_page(4)
    settings.ocr_settings_scroll.ensureWidgetVisible(settings.copy_notification_checkbox)
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


@pytest.mark.parametrize('status', ['no_asset', 'invalid_asset'])
def test_unavailable_update_stays_in_app_without_a_release_download_link(window, status):
    window.show_settings()
    settings = window.settings_window
    with mock.patch('webbrowser.open') as browser, \
         mock.patch.object(settings, '_start_update_check') as retry:
        settings._on_update_check_result(json.dumps(dict(status=status, latest_version='9.9.9')))
        panel = settings._update_progress
        panel.primary.click()
        retry.assert_called_once()
        browser.assert_not_called()
        assert 'GitHub' not in panel.label.text()


@pytest.mark.parametrize('language', ['ru','en','es','de','fr','zh','pt','it','ar','tr','hi','id'])
def test_api_editor_lives_in_packages_and_fits(window, language):
    from provider_settings import show_provider_settings
    from api_providers import PROVIDERS
    window.set_interface_language(language)
    window.show_settings()
    settings=window.settings_window
    with mock.patch('provider_secrets.get_key',return_value=''), \
         mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_argos_catalog_refresh'):
        show_provider_settings(settings)
        page=settings.api_connections_page
        dialog=settings._language_manager_dialog
        assert dialog.tabs.currentWidget() is dialog.api_section_page
        assert settings.settings_pages.indexOf(page) == -1
        for spec in PROVIDERS:
            page.service.setCurrentIndex(page.service.findData(spec.key))
            QApplication.processEvents()
            assert page.isVisible()
            for control in (page.service,page.address,page.key,page.model,page.usage,page.save,page.use):
                assert control.isVisible()
                rect=QRect(control.mapTo(page, QPoint()), control.size())
                assert page.rect().contains(rect), (language, spec.key, rect)
            for label in page.labels:
                assert label.width() >= label.sizeHint().width()
            assert page.key.echoMode() == page.key.Password
        dialog.close_btn.click(); QApplication.processEvents()
        assert not dialog.isVisible()
        assert settings.isVisible()


def test_translation_footer_matches_general_button_rows(window):
    window.show_settings()
    settings=window.settings_window
    for button in (settings.ocr_languages_btn, settings.translation_offline_button,
                   settings.translation_api_button, settings.ocr_api_button):
        assert button.height() == settings.hotkeys_button.height()
        assert button.font().pixelSize() == settings.hotkeys_button.font().pixelSize()
        assert 'padding:0 6px' in button.styleSheet()


def test_api_theme_switch_refreshes_form_and_popups(window):
    from provider_settings import show_provider_settings
    from classic_style import classic_palette
    from PyQt5.QtGui import QPalette
    window.show_settings()
    settings=window.settings_window
    with mock.patch('provider_secrets.get_key',return_value=''), \
         mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_argos_catalog_refresh'):
        page=show_provider_settings(settings)
        for theme, field in (('Светлая','#e9e4ed'), ('Темная','#17181d'), ('Светлая','#e9e4ed')):
            if window.current_theme != theme:
                window.toggle_theme()
            QApplication.processEvents()
            assert field in page.styleSheet()
            for combo in (page.service, page.usage):
                assert field in combo.styleSheet()
                assert combo.popup_colors()['surface'] == field
            for editor in (page.address, page.key, page.model):
                assert editor.palette().color(QPalette.PlaceholderText).name() == classic_palette(theme != 'Светлая')['muted']
        settings._language_manager_dialog.close()


@pytest.mark.parametrize('language', ['en', 'ar'])
def test_api_inline_feedback_is_visible_while_permanent_help_stays_on_the_fields(window, language):
    from provider_settings import show_provider_settings, connection_text, provider_text
    window.set_interface_language(language)
    window.show_settings()
    settings = window.settings_window
    with (mock.patch('provider_secrets.get_key', return_value=''),
          mock.patch('provider_secrets.set_key', return_value=False) as save_key,
          mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        page = show_provider_settings(settings, 'openai-compatible')
        for theme in ('Темная', 'Светлая'):
            if window.current_theme != theme:
                window.toggle_theme()
            QApplication.processEvents()
            assert page.note.isHidden()
            assert page.note.text() in page.usage.accessibleDescription()
            assert provider_text(language, 'help') in page.usage.accessibleDescription()
            page.model.clear()
            page.address.setText('https://example.test/v1')
            page.save.click()
            QApplication.processEvents()
            assert page.status.isVisible()
            assert page.status.text() == connection_text(language, 8)
            page.model.setText('qa-model')
            page.key.setText('qa-only-key')
            page.save.click()
            QApplication.processEvents()
            assert page.status.isVisible()
            assert page.status.text() == provider_text(language, 'session')
            page.scroll.ensureWidgetVisible(page.status)
            QApplication.processEvents()
            assert page.status.heightForWidth(page.status.width()) <= page.status.height()
            assert 'qa-only-key' not in json.dumps(window.config)
            page.load_profile()
            assert page.status.isHidden()
        assert save_key.call_count == 2
        settings._language_manager_dialog.close()


def test_saving_and_selecting_uses_one_service_for_text_and_ocr(window):
    from provider_settings import show_provider_settings
    window.show_settings()
    settings=window.settings_window
    settings._set_settings_page(1)
    with mock.patch('provider_secrets.get_key',return_value='test-key'), \
         mock.patch('provider_secrets.set_key',return_value=True), \
         mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_argos_catalog_refresh'):
        page=show_provider_settings(settings, 'gemini')
        page.model.setText('test-vision-model')
        page.usage.setCurrentIndex(page.usage.findData('direct'))
        page.use.click()
        assert window.config['translator_engine'] == 'gemini'
        assert window.config['ocr_engine'] == 'Gemini API'
        assert window.config['api_providers']['gemini']['direct'] is True
        assert settings.translator_combo.currentData() == 'gemini'
        assert settings.ocr_engine_combo.currentData() == 'Gemini API'
        assert not settings.translator_combo.isEnabled()
        assert settings.provider_routing_note.isVisible()
        page.usage.setCurrentIndex(page.usage.findData('ocr'))
        page.save.click()
        assert settings.translator_combo.isEnabled()
        assert 'test-key' not in json.dumps(window.config)
        settings._language_manager_dialog.close()


def test_selection_trigger_is_one_choice_inside_existing_mode(window):
    from main import HotkeyLanguageDialog
    from selection_options import SelectionTriggerControl
    with mock.patch.object(window, '_sync_selection_quick_translate') as sync:
        dialog=HotkeyLanguageDialog(window)
        dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData('selection'))
        dialog.show(); QApplication.processEvents()
        trigger=dialog.selection_trigger
        assert isinstance(trigger, SelectionTriggerControl) and trigger.isVisible()
        for mode in ('automatic','button','hotkey'):
            trigger.combo.setCurrentIndex(trigger.combo.findData(mode))
            assert window.config['selection_quick_translate_enabled'] == (mode != 'hotkey')
        assert sync.call_count == 3
        dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData('ocr'))
        QApplication.processEvents()
        assert not trigger.isVisible()
        dialog.close()
