"""A page explanation must never move the engine center's shared navigation."""
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import main
from engine_center import MAINTENANCE
from settings_window import OcrLanguageManagerDialog
from test_desktop_assistant import app
from test_language_package_manager import _AppParent, _ManagerOwner
from window_appearance import DialogAppearance


def _rect_in(widget, parent):
    return QtCore.QRect(widget.mapTo(parent, QtCore.QPoint()), widget.size())


def _chrome(dialog):
    # bar.geometry() alone is relative to QTabWidget. It misses a jump of the
    # entire tab widget caused by content inserted above it in the dialog.
    return (dialog.size(), _rect_in(dialog.tabs.tabBar(), dialog),
            _rect_in(dialog.download_access_btn, dialog), _rect_in(dialog.close_btn, dialog))


@pytest.mark.parametrize('locale', tuple(MAINTENANCE))
@pytest.mark.parametrize('theme', ('Темная', 'Светлая'))
@pytest.mark.parametrize('percent', (80, 100, 125, 150, 200))
def test_real_section_clicks_keep_navigation_and_footer_stationary(app, locale, theme, percent):
    parent = _AppParent()
    parent.current_interface_language = locale
    parent.current_theme = theme
    parent.config = deepcopy(main.DEFAULT_CONFIG)
    owner = _ManagerOwner(parent)
    appearance = DialogAppearance(app, percent=percent, theme=theme)
    dialog = None
    with mock.patch.object(appearance, 'available_geometry', return_value=QtCore.QRect(0, 0, 3840, 2160)), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'), \
         mock.patch('provider_secrets.get_key', return_value=''), \
         mock.patch('download_access.DownloadAccessPage.start'):
        try:
            dialog = OcrLanguageManagerDialog(owner)
            dialog._initial_probe_timer.stop()
            dialog._initial_catalog_timer.stop()
            dialog.show()
            app.processEvents()
            appearance.apply(dialog)
            app.processEvents()
            before = _chrome(dialog)
            bar = dialog.tabs.tabBar()
            for section in (2, 1, 0, 2):
                QTest.mouseClick(bar, QtCore.Qt.LeftButton, pos=bar.tabRect(section).center())
                app.processEvents()
                appearance.apply(dialog)
                app.processEvents()
                assert dialog.tabs.currentIndex() == section
                assert _chrome(dialog) == before, (locale, theme, percent, section, before, _chrome(dialog))
                assert all(dialog.rect().contains(rect) for rect in before[1:])
                if section != 2:
                    inner = (dialog.ocr_tabs, dialog.translation_tabs)[section]
                    for control in (inner._activate_button, inner._tools_button,
                                    dialog._engine_selectors[section]):
                        assert dialog.rect().contains(_rect_in(control, dialog)), (
                            locale, theme, percent, control.objectName(), _rect_in(control, dialog))
                if section == 2:
                    assert dialog.intro_label.isVisible()
                    assert dialog.api_section_page.isAncestorOf(dialog.intro_label)
                    assert _rect_in(dialog.intro_label, dialog).top() > _rect_in(bar, dialog).bottom()
                    page = dialog.api_page
                    for button in (page.delete, page.save, page.use):
                        assert dialog.rect().contains(_rect_in(button, dialog))
                        assert button.width() >= button.minimumSizeHint().width()
                    assert page.scroll.viewport().rect().contains(_rect_in(page.key, page.scroll.viewport()))
                if locale in ('en', 'ar', 'ru') and percent in (100, 200):
                    output = Path('.tmp/engine-center-stationary-20261104')
                    output.mkdir(parents=True, exist_ok=True)
                    assert dialog.grab().save(str(output/f'{locale}-{theme}-{percent}-{section}.png'))
                    if percent == 100 and (locale, theme) in (('ru', 'Темная'), ('en', 'Светлая')):
                        name = ('ocr', 'translation', 'api')[section]
                        shade = 'dark' if theme == 'Темная' else 'light'
                        assert dialog.grab().save(str(output/f'{locale}-{shade}-{name}.png'))
            # An unusually long routing note takes space inside its page.
            # It cannot insert height before the navigation or below the body.
            api_actions = [_rect_in(button, dialog) for button in
                           (dialog.api_page.delete, dialog.api_page.save, dialog.api_page.use)]
            dialog.intro_label.setText(dialog.intro_label.text() * 4)
            app.processEvents()
            assert _chrome(dialog) == before
            assert [_rect_in(button, dialog) for button in
                    (dialog.api_page.delete, dialog.api_page.save, dialog.api_page.use)] == api_actions
            dialog.download_access_btn.click()
            app.processEvents()
            assert _rect_in(dialog.download_access_btn, dialog) == before[2]
            assert _rect_in(dialog.close_btn, dialog) == before[3]
            assert dialog.body_stack.currentWidget() is dialog._download_access_page
            dialog.download_access_btn.click()
            app.processEvents()
            assert _chrome(dialog) == before
            assert dialog.api_page.isVisible()
        finally:
            if dialog is not None:
                dialog.close()
                dialog.deleteLater()
            app.removeEventFilter(appearance)
            appearance.deleteLater()
            parent.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_reference_previews_keep_api_and_ocr_the_same_size(app):
    for locale, theme in (('ru', 'Темная'), ('en', 'Светлая')):
        test_real_section_clicks_keep_navigation_and_footer_stationary(app, locale, theme, 100)


@pytest.mark.parametrize('theme', ('Темная', 'Светлая'))
@pytest.mark.parametrize('percent', (100, 125, 200))
@pytest.mark.parametrize('locale', ('en', 'ar'))
def test_language_action_buttons_stay_at_bottom_when_notes_wrap(app, theme, percent, locale):
    parent = _AppParent()
    parent.current_interface_language = locale
    parent.current_theme = theme
    parent.config = deepcopy(main.DEFAULT_CONFIG)
    owner = _ManagerOwner(parent)
    owner.easyocr_status = (True, '')
    appearance = DialogAppearance(app, percent=percent, theme=theme)
    dialog = None
    with mock.patch.object(appearance, 'available_geometry', return_value=QtCore.QRect(0, 0, 3840, 2160)), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'), \
         mock.patch('provider_secrets.get_key', return_value=''):
        try:
            dialog = OcrLanguageManagerDialog(owner)
            dialog._initial_probe_timer.stop()
            dialog._initial_catalog_timer.stop()
            dialog._easyocr_status_cache = (True, '')
            dialog.ocr_tabs.setCurrentWidget(dialog.easyocr_table.parentWidget())
            dialog.show()
            app.processEvents()
            appearance.apply(dialog)
            app.processEvents()
            table = dialog.easyocr_table
            before = [_rect_in(button, dialog) for button in table._package_action_buttons]
            chrome = _chrome(dialog)
            table._package_note_label.setText(table._package_note_label.text() * 4)
            table._package_size_label.setText('Installed component · available version · ' * 4)
            app.processEvents()
            assert _chrome(dialog) == chrome
            assert [_rect_in(button, dialog) for button in table._package_action_buttons] == before
            page = dialog.show_api()
            app.processEvents()
            appearance.apply(dialog)
            app.processEvents()
            before = [_rect_in(button, dialog) for button in (page.delete, page.save, page.use)]
            chrome = _chrome(dialog)
            dialog.intro_label.setText(dialog.intro_label.text() * 4)
            app.processEvents()
            assert _chrome(dialog) == chrome
            assert [_rect_in(button, dialog) for button in (page.delete, page.save, page.use)] == before
        finally:
            if dialog is not None:
                dialog.close()
                dialog.deleteLater()
            app.removeEventFilter(appearance)
            appearance.deleteLater()
            parent.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
