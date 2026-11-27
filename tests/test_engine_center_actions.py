"""Language mutations and engine maintenance are separate, visible actions."""
from pathlib import Path
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

from engine_center import MAINTENANCE, MAINTENANCE_KEYS, text
from settings_window import OcrLanguageManagerDialog
from test_language_package_manager import _AppParent, _ManagerOwner


@pytest.fixture
def center():
    app = QtWidgets.QApplication.instance()
    parent = _AppParent()
    owner = _ManagerOwner(parent)
    owner.easyocr_status = (True, '')
    with mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'):
        dialog = OcrLanguageManagerDialog(owner)
        dialog._initial_probe_timer.stop()
        dialog._initial_catalog_timer.stop()
    yield dialog, owner, parent
    dialog.close()
    owner.deleteLater()
    parent.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def _rows():
    return [dict(code=code, name=name, package=code + '.traineddata', status=status,
                 checked=installed, selectable=not installed)
            for code, name, status, installed in [('en', 'English', 'Installed', True),
                                                  ('fr', 'French', 'Missing', False)]]


def test_language_buttons_require_the_matching_selection(center):
    dialog, _, _ = center
    table = dialog.easyocr_table
    dialog._set_language_rows(table, _rows())
    buttons = {button.property('packageAction'): button for button in table._package_action_buttons}
    assert set(buttons) == {'install', 'remove'}
    assert not any(button.isEnabled() for button in buttons.values())
    table.item(1, 0).setCheckState(QtCore.Qt.Checked)
    assert buttons['install'].isEnabled()
    table.selectRow(1)
    assert not buttons['remove'].isEnabled(), 'checked missing packages cannot be removed'
    table.selectRow(0)
    assert buttons['remove'].isEnabled()
    table.clearSelection()
    assert not buttons['remove'].isEnabled()
    dialog._set_language_rows(table, _rows()[:1])
    assert buttons['install'].isEnabled(), 'a search keeps pending downloads'
    assert all(button.toolTip().strip() for button in buttons.values())


def test_engine_maintenance_is_only_in_current_engine_menu_and_respects_busy_state(center):
    dialog, _, _ = center
    table = dialog.easyocr_table
    dialog._set_engine_missing_state(table, False)
    dialog.ocr_tabs.setCurrentWidget(table.parentWidget())
    dialog._populate_engine_menu(dialog.ocr_tabs)
    menu = dialog.ocr_tabs._tools_menu
    maintenance = table._package_engine_actions
    remove = table._package_remove_engine_button
    assert maintenance and remove in menu.actions()
    assert all(isinstance(action, QtWidgets.QAction) for action in maintenance)
    assert all(action in menu.actions() for action in maintenance)
    assert dialog.refresh_btn in menu.actions()
    assert dialog.findChildren(QtWidgets.QPushButton, 'languagePackageEngineRemove') == []
    dialog._install_in_progress = True
    dialog._set_package_actions_busy(True)
    assert not any(action.isEnabled() for action in [*maintenance, remove, dialog.refresh_btn])
    dialog._install_in_progress = False
    dialog._set_package_actions_busy(False)
    assert all(action.isEnabled() for action in [*maintenance, remove, dialog.refresh_btn])
    dialog._set_engine_missing_state(table, True)
    dialog._populate_engine_menu(dialog.ocr_tabs)
    assert menu.actions() == [dialog.refresh_btn], 'no stale actions from the previous engine'


@pytest.mark.parametrize('locale', tuple(MAINTENANCE))
@pytest.mark.parametrize('dark', (True, False))
def test_center_footer_and_maintenance_menu_render_without_overlap(center, locale, dark):
    from classic_style import classic_palette
    dialog, owner, parent = center
    # Construct in the requested locale, as normal opening does. No desktop UI.
    parent.current_interface_language = locale
    parent.current_theme = 'Темная' if dark else 'Светлая'
    dialog.close()
    with mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'):
        rendered = OcrLanguageManagerDialog(owner)
        rendered._initial_probe_timer.stop()
        rendered._initial_catalog_timer.stop()
    try:
        app = QtWidgets.QApplication.instance()
        rendered._easyocr_status_cache = (True, '')
        rendered.ocr_tabs.setCurrentWidget(rendered.easyocr_table.parentWidget())
        rendered.show()
        app.processEvents()
        footer = [rendered.download_access_btn, rendered.close_btn]
        for button in footer:
            rect = QtCore.QRect(button.mapTo(rendered, QtCore.QPoint()), button.size())
            assert rendered.rect().contains(rect)
            assert button.width() >= button.minimumSizeHint().width()
        assert not footer[0].geometry().intersects(footer[1].geometry())
        for inner in (rendered.ocr_tabs, rendered.translation_tabs):
            rendered._populate_engine_menu(inner)
            menu = inner._tools_menu
            menu.ensurePolished()
            menu.resize(menu.sizeHint())
            menu.show()
            app.processEvents()
            for action in menu.actions():
                if not action.isSeparator() and action.isVisible():
                    assert menu.rect().contains(menu.actionGeometry(action))
            assert not menu.grab().isNull()
            menu.hide()
        image = rendered.grab().toImage()
        border = classic_palette(dark)['border']
        for point in ((0, 0), (image.width()-1, 0), (0, image.height()-1),
                      (image.width()-1, image.height()-1), (0, image.height()//2),
                      (image.width()-1, image.height()//2)):
            assert image.pixelColor(*point).name() == border
        # A former footer position must be cleared instead of painting twice.
        expected = classic_palette(dark)['background']
        x = rendered.content_widget.x() + 4
        for y in range(rendered.height() - 85, rendered.height() - 5):
            assert image.pixelColor(x, y).name() == expected
        output = Path('.tmp/engine-center-20261029')
        output.mkdir(parents=True, exist_ok=True)
        assert image.save(str(output / f'{locale}-{"dark" if dark else "light"}.png'))
        rendered._show_task_status('Preparing language packages: ' + 'Download details ' * 40, 45)
        rendered.task_show_button.show()
        app.processEvents()
        footer = [rendered.task_status_label, rendered.task_show_button,
                  rendered.download_access_btn, rendered.close_btn]
        rects = [QtCore.QRect(widget.mapTo(rendered, QtCore.QPoint()), widget.size()) for widget in footer]
        assert all(rendered.rect().contains(rect) for rect in rects)
        assert all(not rect.intersects(other) for i, rect in enumerate(rects) for other in rects[i+1:])
        assert rendered.task_status_label.toolTip().strip()
        assert not rendered.grab().isNull()
    finally:
        rendered.close()
        rendered.deleteLater()


def test_maintenance_copy_is_complete_for_every_interface_language():
    for locale, values in MAINTENANCE.items():
        assert len(values) == len(MAINTENANCE_KEYS)
        assert all(text(locale, key).strip() for key in MAINTENANCE_KEYS)


@pytest.mark.parametrize('percent', (80, 100, 125, 150, 200))
def test_engine_transitions_at_each_scale_keep_footer_and_children_inside(center, percent):
    from window_appearance import DialogAppearance
    dialog, _, _ = center
    app = QtWidgets.QApplication.instance()
    appearance = DialogAppearance(app, percent=percent, theme='Темная')
    try:
        with mock.patch.object(appearance, 'available_geometry',
                               return_value=QtCore.QRect(0, 0, 3840, 2160)):
            dialog.show()
            app.processEvents()
            appearance.apply(dialog)
            expected = dialog.size()
            for tabs in (dialog.ocr_tabs, dialog.translation_tabs):
                dialog.tabs.setCurrentWidget(tabs.parentWidget())
                for index in range(tabs.count()):
                    tabs.setCurrentIndex(index)
                    app.processEvents()
                    appearance.apply(dialog)
                    app.processEvents()
                    assert dialog.size() == expected
                    widgets = [dialog.download_access_btn, dialog.close_btn, tabs._activate_button,
                               tabs._tools_button]
                    table = dialog._active_engine_table()
                    if table is not None:
                        widgets += [table, table._package_missing_frame,
                                    table._package_missing_install_button, *table._package_action_buttons]
                    visible = [widget for widget in widgets if widget.isVisible()]
                    rects = [QtCore.QRect(widget.mapTo(dialog, QtCore.QPoint()), widget.size())
                             for widget in visible]
                    assert all(dialog.rect().contains(rect) for rect in rects)
                    for button in visible:
                        if isinstance(button, QtWidgets.QPushButton):
                            assert button.width() >= button.minimumSizeHint().width(), (
                                percent, tabs.tabText(index), button.objectName(), button.text(),
                                button.width(), button.minimumSizeHint().width())
                    # Nested missing-state frame/button intentionally overlap;
                    # sibling action controls may never overlap each other.
                    buttons = [widget for widget in visible if isinstance(widget, QtWidgets.QAbstractButton)]
                    for i, button in enumerate(buttons):
                        rect = QtCore.QRect(button.mapTo(dialog, QtCore.QPoint()), button.size())
                        assert all(not rect.intersects(QtCore.QRect(other.mapTo(dialog, QtCore.QPoint()), other.size()))
                                   for other in buttons[i+1:])
            output = Path('.tmp/engine-center-20261029')
            output.mkdir(parents=True, exist_ok=True)
            assert dialog.grab().save(str(output / f'scale-{percent}.png'))
    finally:
        app.removeEventFilter(appearance)
        appearance.deleteLater()
