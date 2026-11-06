"""Actual tab clicks keep API usable; package navigation has one tab row."""
from unittest import mock
import sys
import pytest
from PyQt5 import QtCore, QtWidgets, QtTest

from package_presentation import TEXT
from settings_window import OcrLanguageManagerDialog
from test_desktop_ux import app, window
from ui_scaling import widget_global_rect


@pytest.mark.parametrize('language', tuple(TEXT))
@pytest.mark.parametrize('dark', (False, True))
def test_api_tab_click_retains_navigation_and_editable_draft(window, app, language, dark):
    window.set_interface_language(language)
    if (window.current_theme != 'Светлая') != dark:
        window.toggle_theme()
    window.show_settings()
    settings = window.settings_window
    with (mock.patch('provider_secrets.get_key', return_value=''),
          mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        settings.show_ocr_language_manager()
        dialog = settings._language_manager_dialog
        bar = dialog.tabs.tabBar()
        app.processEvents()
        before = bar.geometry()
        QtTest.QTest.mouseClick(bar, QtCore.Qt.LeftButton, pos=bar.tabRect(2).center())
        app.processEvents()
        assert dialog.api_page is not None
        page = dialog.api_page
        assert page.isVisible() and page.service.isVisible() and page.key.isVisible()
        assert dialog.intro_label.isVisible() and bar.geometry() == before
        page.service.setCurrentIndex(page.service.findData('openai-compatible'))
        page.address.setText('https://example.org/v1')
        QtTest.QTest.mouseClick(bar, QtCore.Qt.LeftButton, pos=bar.tabRect(0).center())
        app.processEvents()
        assert dialog._engine_selectors[0].isVisible()
        assert dialog.ocr_tabs.tabBar().isHidden()
        dialog._engine_selectors[0].setCurrentIndex(1)
        assert dialog.ocr_tabs.currentIndex() == 1
        QtTest.QTest.mouseClick(bar, QtCore.Qt.LeftButton, pos=bar.tabRect(2).center())
        app.processEvents()
        assert page.address.text() == 'https://example.org/v1'
        assert bar.geometry() == before
        assert page.rect().contains(QtCore.QRect(page.key.mapTo(page, QtCore.QPoint()), page.key.size()))
        dialog.close()


@pytest.mark.parametrize('percent', (80, 100, 137))
@pytest.mark.skipif(sys.platform != 'win32', reason='Windows native popup policy')
def test_lower_main_language_lists_open_below_the_field_when_desktop_space_exists(window, app, percent):
    window.set_ui_scale_percent(percent)
    window.show_main_screen()
    app.processEvents()
    for name in ('target_lang', 'hotkey_source_combo', 'hotkey_target_combo'):
        combo = getattr(window, name)
        with mock.patch.object(combo, '_available_screen_rect', return_value=QtCore.QRect(0, 0, 3200, 2000)):
            combo.showPopup()
            for _ in range(4):
                app.processEvents()
            popup = combo.view().window()
            try:
                assert popup.graphicsProxyWidget() is None
                assert popup.geometry().top() > widget_global_rect(combo).bottom()
                assert popup.width() >= widget_global_rect(combo).width()
                if hasattr(combo, '_language_search'):
                    before = popup.geometry()
                    combo._language_search.setText('Russian')
                    app.processEvents()
                    assert popup.geometry().topLeft() == before.topLeft()
                    assert popup.width() == before.width()
                    assert popup.height() < before.height()
            finally:
                combo.hidePopup()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows native popup policy')
def test_real_lower_list_follows_its_owner_on_each_connected_screen(window, app):
    if app.platformName() == 'offscreen':
        pytest.skip('Native monitor coordinates require the Windows backend')
    window.show_main_screen()
    combo = window.hotkey_target_combo
    for screen in app.screens():
        bounds = screen.availableGeometry()
        window._ui_scale_controller.available_geometry.return_value = bounds
        window.set_ui_scale_percent(100)
        window.move(bounds.topLeft() + QtCore.QPoint(35, 35))
        QtTest.QTest.qWait(100)
        combo.showPopup()
        QtTest.QTest.qWait(60)
        try:
            popup = combo.view().window()
            assert bounds.contains(popup.frameGeometry())
            assert popup.windowHandle().screen().name() == screen.name()
            anchor = widget_global_rect(combo)
            if bounds.bottom() - anchor.bottom() >= 100:
                assert popup.geometry().top() > anchor.bottom()
        finally:
            combo.hidePopup()
