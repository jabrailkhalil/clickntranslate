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


@pytest.mark.parametrize('codes_in_model', (True, False), ids=('iso-values', 'translated-labels'))
@pytest.mark.parametrize('query,expected', [
    ('AR', 'ar'), ('francais', 'fr'), ('espanol', 'es'), ('turkce', 'tr'),
    ('العَرَبِيَّة', 'ar'), ('auto', 'auto'), ('Detect language', 'auto'),
])
def test_typing_a_language_and_confirming_selects_the_intended_option(codes_in_model, query, expected):
    from languages import language_display_name

    app = QApplication.instance() or QApplication([])
    combo = DropDownCombo()
    combo.interface_language = 'ru'
    codes = ['auto', *(language.code for language in LANGUAGES)]
    for code in codes:
        combo.addItem(language_display_name(code, 'ru'), code if codes_in_model else None)
    combo.show()
    try:
        combo.setCurrentIndex(codes.index('zh'))
        combo.showPopup()
        app.processEvents()
        search = combo._language_search
        search.setText(query)
        app.processEvents()
        visible = [codes[i] for i in range(combo.count()) if not combo.view().isRowHidden(i)]
        assert visible == [expected]
        QTest.keyClick(search, Qt.Key_Return)
        assert not combo.view().window().isVisible()
        assert combo.currentText() == language_display_name(expected, 'ru')
    finally:
        combo.hidePopup()
        combo.close()
        combo.deleteLater()


def test_open_language_menu_adapts_to_deferred_catalog_and_refilters_changed_rows():
    app = QApplication.instance() or QApplication([])
    combo = DropDownCombo()
    combo.addItem('English', 'en')
    combo.show()
    try:
        combo.showPopup()
        app.processEvents()
        popup = combo.view().window()
        assert not hasattr(combo, '_language_search')
        for language in LANGUAGES[1:]:
            combo.addItem(language.english_name, language.code)
        QTest.qWait(20)
        assert popup.isVisible() and combo._language_search.isVisible()
        search = combo._language_search
        search.setText('Vietnamese')
        hidden_code_row = combo.findData('ru')
        matching_row = combo.findData('vi')
        combo.setItemText(hidden_code_row, 'Updated option')
        combo.addItem('Extra choice', 'custom')
        QTest.qWait(20)
        assert [r for r in range(combo.count()) if not combo.view().isRowHidden(r)] == [matching_row]
        combo.removeItem(matching_row)
        QTest.qWait(20)
        assert search.text() == 'Vietnamese' and combo._language_empty.isVisible()
        assert all(combo.view().isRowHidden(r) for r in range(combo.count()))
        combo.addItem('Vietnamese', 'vi')
        QTest.qWait(20)
        assert search.text() == 'Vietnamese' and not combo._language_empty.isVisible()
        assert not combo.view().isRowHidden(combo.findData('vi'))
        search.clear()
        combo.clear()
        combo.addItem('Russian', 'ru')
        QTest.qWait(20)
        assert popup.isVisible() and not search.isVisible()
        assert not combo.view().isRowHidden(0)
    finally:
        combo.hidePopup()
        combo.close()
        combo.deleteLater()


def test_exact_code_of_an_unavailable_language_cannot_select_a_different_language():
    app = QApplication.instance() or QApplication([])
    combo = DropDownCombo()
    for language in LANGUAGES:
        if language.code != 'ar':
            combo.addItem(language.english_name, language.code)
    combo.show()
    try:
        combo.setCurrentIndex(combo.findData('ru'))
        combo.showPopup()
        app.processEvents()
        combo._language_search.setText('ar')
        QTest.keyClick(combo._language_search, Qt.Key_Return)
        assert combo._language_empty.isVisible()
        assert combo.view().window().isVisible() and combo.currentData() == 'ru'
    finally:
        combo.hidePopup()
        combo.close()
        combo.deleteLater()
