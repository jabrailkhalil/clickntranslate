"""Font choices identify their scope and preview every saved size without clipping."""
import pytest
from PyQt5 import QtCore

import main
from control_hints import LANGUAGES
from test_desktop_ux import app, window


@pytest.mark.parametrize('language', LANGUAGES)
def test_result_font_sizes_have_numeric_values_and_a_fitting_live_preview(window, app, language):
    window.set_interface_language(language)
    window.show_settings()
    settings = window.settings_window
    combo = settings.translation_font_combo
    preview = settings.translation_font_preview
    for key, pixels in main.TRANSLATION_RESULT_FONT_SIZE_PX.items():
        index = combo.findData(key)
        assert f'{pixels} px' in combo.itemText(index)
        assert combo.itemData(index, QtCore.Qt.ToolTipRole)
        combo.setCurrentIndex(index)
        app.processEvents()
        assert window.config['translation_result_font_size'] == key
        assert preview.font().pixelSize() == pixels
        assert f'{pixels} px' in combo.toolTip()
        assert combo.fontMetrics().horizontalAdvance(combo.currentText()) < combo.width() - 40
        bounds = preview.fontMetrics().boundingRect(preview.text())
        assert bounds.width() <= preview.width(), (language, key, bounds, preview.size())
        assert bounds.height() <= preview.height(), (language, key, bounds, preview.size())
        assert settings.settings_general_page.rect().contains(
            QtCore.QRect(preview.mapTo(settings.settings_general_page, QtCore.QPoint()), preview.size()))
        assert settings.translation_font_label.buddy() is combo
