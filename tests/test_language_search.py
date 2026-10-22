"""Long language catalogs stay searchable, bounded, and index-stable."""
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
import pytest
from settings_window import DropDownCombo
from languages import LANGUAGES,language_code_from_name


@pytest.mark.parametrize('locale',['ru','en','es','de','fr','zh'])
def test_search_preserves_original_indexes_and_keyboard_choice(locale):
    app=QApplication.instance() or QApplication([])
    combo=DropDownCombo()
    combo.resize(200,32)
    for language in LANGUAGES:
        combo.addItem(language.display_name(locale),language.code)
    combo.show()
    try:
        original=combo.findData('vi')
        combo.showPopup(); app.processEvents()
        search=combo._language_search
        search.setText('Vietnamese'); app.processEvents()
        visible=[i for i in range(combo.count()) if not combo.view().isRowHidden(i)]
        assert visible == [original]
        assert combo.count() == len(LANGUAGES)
        QTest.keyClick(search,Qt.Key_Return); app.processEvents()
        assert combo.currentData() == 'vi'
        assert language_code_from_name(combo.currentText(),locale) == 'vi'
        combo.showPopup(); app.processEvents()
        assert not search.text()
        assert not any(combo.view().isRowHidden(i) for i in range(combo.count()))
        assert combo.maxVisibleItems() == 8
        assert combo.view().verticalScrollBar().maximum() > 0
        assert combo.view().window().height() < 450
    finally:
        combo.hidePopup(); combo.close(); combo.deleteLater(); app.processEvents()


def test_engine_popup_does_not_gain_language_search():
    app=QApplication.instance() or QApplication([])
    combo=DropDownCombo()
    combo.addItems(['Provider '+str(i) for i in range(20)])
    combo.show()
    try:
        combo.showPopup(); app.processEvents()
        assert not hasattr(combo,'_language_search')
    finally:
        combo.hidePopup(); combo.close(); combo.deleteLater(); app.processEvents()
