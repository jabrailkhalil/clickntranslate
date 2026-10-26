"""Render the new EasyOCR action beside existing package controls in every locale."""
from unittest import mock
import pytest
from PyQt5.QtWidgets import QApplication

from interface_language_picker import PICKER_TEXT
from settings_window import OcrLanguageManagerDialog
from component_texts import update_label, update_hint
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
        update=next(button for button in buttons if button.text()==update_label(language,'EasyOCR'))
        assert update.toolTip()==update_hint(language,'EasyOCR') and update.toolTip().strip()
        for button in buttons:
            assert button.isVisible()
            assert button.width()>=button.minimumSizeHint().width()
            assert button.parentWidget().rect().contains(button.geometry())
        for index,button in enumerate(buttons):
            assert not any(button.geometry().intersects(other.geometry()) for other in buttons[index+1:])
        assert dialog.grab().save(str(tmp_path/(language+'-'+('dark' if theme=='Темная' else 'light')+'.png')))
    finally:
        dialog.close();owner.close();parent.close();app.processEvents()
