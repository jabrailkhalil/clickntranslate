import os
from pathlib import Path
from unittest import mock

import pytest
from PyQt5.QtWidgets import QApplication, QLabel

from settings_window import OcrLanguageManagerDialog, language_manager_text, engine_text, _ocr_combo_tooltip
from test_language_package_manager import _AppParent, _ManagerOwner


LOCALES = ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id')


@pytest.mark.parametrize('locale', LOCALES)
@pytest.mark.parametrize('theme', ('Темная', 'Светлая'))
def test_rapidocr_v5_notes_and_model_table_render_in_supported_locales(locale, theme, tmp_path):
    app = QApplication.instance()
    parent = _AppParent()
    parent.current_interface_language = locale
    parent.current_theme = theme
    owner = _ManagerOwner(parent)
    with mock.patch('settings_window.QtCore.QTimer.singleShot'), \
         mock.patch('rapidocr_models.installed_languages', return_value=['en', 'ru', 'ar', 'zh', 'es']):
        dialog = OcrLanguageManagerDialog(owner)
        try:
            dialog._initial_probe_timer.stop()
            dialog._initial_catalog_timer.stop()
            dialog._rapidocr_status_cache = (True, '')
            dialog._populate_rapidocr_table(dialog.rapidocr_table)
            dialog.tabs.setCurrentIndex(0)
            index = next(i for i in range(dialog.ocr_tabs.count()) if dialog.ocr_tabs.tabText(i) == 'RapidOCR')
            dialog.ocr_tabs.setCurrentIndex(index)
            dialog.show()
            app.processEvents()
            note_text = language_manager_text(locale, 'rapidocr_note')
            assert 'PP-OCRv5' in note_text
            assert 'PP-OCRv5' in engine_text(locale, 'rapidocr_prompt')
            assert 'PP-OCRv5' in _ocr_combo_tooltip('RapidOCR', locale)
            note = next(w for w in dialog.findChildren(QLabel) if w.text() == note_text)
            assert note.isVisible()
            assert note.height() >= note.heightForWidth(note.width())
            assert dialog.rapidocr_table.viewport().height() >= 80
            packages = [dialog.rapidocr_table.item(row, 2).text() for row in range(dialog.rapidocr_table.rowCount())]
            assert packages.count('PP-OCRv5 mobile') == 2
            capture = os.environ.get('CNT_RAPID_QA_CAPTURES')
            if capture:
                output = Path(capture)
                output.mkdir(parents=True, exist_ok=True)
                assert dialog.grab().save(str(output / f'{locale}-{theme}.png'))
        finally:
            dialog.close()
            dialog.deleteLater()
            owner.close()
            parent.close()
