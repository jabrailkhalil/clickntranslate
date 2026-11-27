"""Engine updates are in the shared menu, language actions stay by the table."""
from unittest import mock
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QPoint, QRect

from interface_language_picker import PICKER_TEXT
from settings_window import OcrLanguageManagerDialog
from component_texts import update_label, update_hint
from styled_dialogs import tooltip_text
from test_language_package_manager import _AppParent, _ManagerOwner


@pytest.mark.parametrize('language',tuple(PICKER_TEXT))
@pytest.mark.parametrize('theme',('Темная','Светлая'))
def test_easyocr_update_fits_and_is_localized_in_both_themes(tmp_path,language,theme):
    app=QApplication.instance()
    parent=_AppParent();parent.current_interface_language=language;parent.current_theme=theme
    owner=_ManagerOwner(parent);owner.easyocr_status=(True,'')
    with mock.patch('settings_window.QtCore.QTimer.singleShot'):
        dialog=OcrLanguageManagerDialog(owner)
    try:
        dialog._initial_probe_timer.stop();dialog._initial_catalog_timer.stop()
        dialog._easyocr_status_cache=(True,'')
        dialog._populate_easyocr_table(dialog.easyocr_table)
        dialog.tabs.setCurrentIndex(0)
        dialog.ocr_tabs.setCurrentWidget(dialog.easyocr_table.parentWidget())
        dialog.show();app.processEvents()
        buttons=dialog.easyocr_table._package_action_buttons
        update=next(button for button in dialog.easyocr_table._package_engine_actions if button.property('packageBaseText')==update_label(language,'EasyOCR'))
        from engine_center import text as center_text
        assert update.text()==center_text(language, 'check_updates')
        assert update.toolTip()==tooltip_text(center_text(language, 'check_help')) and update.toolTip().strip()
        dialog._populate_engine_menu(dialog.ocr_tabs)
        menu=dialog.ocr_tabs._tools_menu
        assert update in menu.actions()
        menu.show();app.processEvents()
        assert menu.rect().contains(menu.actionGeometry(update))
        assert not menu.grab().isNull()
        menu.hide()
        for button in buttons:
            assert button.isVisible()
            assert button.width()>=button.minimumSizeHint().width()
            assert button.parentWidget().rect().contains(button.geometry())
        for index,button in enumerate(buttons):
            rect = QRect(button.mapTo(dialog, QPoint()), button.size())
            assert not any(rect.intersects(QRect(other.mapTo(dialog, QPoint()), other.size())) for other in buttons[index+1:])
        assert dialog.grab().save(str(tmp_path/(language+'-'+('dark' if theme=='Темная' else 'light')+'.png')))
    finally:
        dialog.close();owner.close();parent.close();app.processEvents()
