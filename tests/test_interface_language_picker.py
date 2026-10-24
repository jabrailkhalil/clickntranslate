"""Language choices remain readable, searchable and bounded as the catalog grows."""
import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QSignalSpy, QTest

import main
from interface_language_picker import InterfaceLanguagePicker
from test_desktop_ux import app, window


def settle(app):
    for _ in range(5):
        app.processEvents()


@pytest.fixture
def make_picker(app):
    created = []
    def make(count=12, current='en'):
        options = list(main.INTERFACE_LANGUAGE_OPTIONS)
        options += [dict(code=f'lang_{i}', name=f'Language {i}', icon='icons/American_flag.png')
                    for i in range(12, count)]
        picker = InterfaceLanguagePicker(options, current, main.resource_path)
        picker.show()
        created.append(picker)
        settle(app)
        return picker
    yield make
    for picker in created:
        picker.close()
        picker.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


def test_picker_preserves_home_draft_size_and_language_pair(window, app):
    window.text_input.setPlainText('Unfinished draft')
    original = window.main_text_section
    pair = window._configured_main_translation_pair()
    settle(app)
    before = window.size()
    window.show_interface_language_menu()
    picker = window._interface_language_picker
    settle(app)
    assert window.size() == before and original.isVisible() and picker.isVisible()
    assert window.flag_button.isChecked() and picker.parentWidget() == original.parentWidget()
    assert picker.grid.count() == 12 and not hasattr(picker, 'pages')
    window.show_interface_language_menu()
    settle(app)
    assert window._interface_language_picker is None and not window.flag_button.isChecked()
    assert window.main_text_section is original
    assert window.text_input.toPlainText() == 'Unfinished draft'
    assert window._configured_main_translation_pair() == pair and window.size() == before


@pytest.mark.parametrize('page', [0, 1, 2, 3, 4])
def test_live_choice_preserves_settings_page_and_panel_geometry(window, app, page):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(page)
    settle(app)
    window.show_interface_language_menu()
    picker = window._interface_language_picker
    before = QtCore.QRect(picker.geometry())
    for locale in ('es', 'ar', 'pt', 'hi', 'en'):
        picker.buttons[locale].click()
        assert picker.geometry() == before
        settle(app)
        assert picker.geometry() == before and picker.height() == picker.PANEL_HEIGHT
        assert window.settings_window is settings and settings.settings_pages.currentIndex() == page
    QTest.keyClick(picker.buttons['en'], QtCore.Qt.Key_Escape)
    settle(app)
    assert window._interface_language_picker is None
    assert settings.settings_pages.currentIndex() == page


@pytest.mark.parametrize('count', [12, 20, 40])
def test_catalog_grows_by_scrolling_without_pages_or_empty_cells(make_picker, app, count):
    last = 'id' if count == 12 else f'lang_{count-1}'
    picker = make_picker(count, current=last)
    picker.focus_current_language(keyboard=True)
    settle(app)
    assert picker.size() == QtCore.QSize(672, 146)
    assert picker.COLUMNS == 4 and picker.header.height() == 28
    assert picker.search.size() == QtCore.QSize(206, 24)
    assert picker.close_button.size() == QtCore.QSize(24, 24)
    assert picker.grid.count() == count and len(picker.buttons) == count
    assert not hasattr(picker, 'pages') and not hasattr(picker, 'next_button')
    assert picker.scroll.horizontalScrollBar().maximum() == 0
    assert (picker.scroll.verticalScrollBar().maximum() > 0) == (count > 12), (
        picker.size(), picker.choices.size(), picker.scroll.size(), picker.scroll.viewport().size(),
        picker.catalog.size(), picker.scroll.frameWidth(), picker.scroll.contentsMargins())
    for index, code in enumerate(picker.visible_codes):
        cell = picker.buttons[code]
        assert cell.height() >= 38
        assert cell.y() == index//4*38
        assert picker.grid.getItemPosition(index)[:2] == (index//4, index % 4)
    assert picker.buttons[last].hasFocus() and picker.buttons[last].isChecked()
    header_y = picker.header.y()
    selected = QSignalSpy(picker.languageSelected)
    QTest.keyClick(picker.buttons[last], QtCore.Qt.Key_Home)
    settle(app)
    assert picker.buttons['en'].hasFocus() and picker.scroll.verticalScrollBar().value() == 0
    assert picker.header.y() == header_y and len(selected) == 0
    QTest.keyClick(picker.buttons['en'], QtCore.Qt.Key_End)
    settle(app)
    assert picker.buttons[last].hasFocus()
    assert picker.scroll.viewport().rect().contains(
        picker.buttons[last].mapTo(picker.scroll.viewport(), picker.buttons[last].rect().center()))


@pytest.mark.parametrize('query,expected', [
    ('Arabic', 'ar'), ('العربية', 'ar'), ('арабский', 'ar'),
    ('turkce', 'tr'), ('Französisch', 'fr'), ('Indonesian', 'id'), ('pt', 'pt'),
])
def test_filter_supports_native_english_localized_code_and_accents(make_picker, app, query, expected):
    picker = make_picker()
    picker.search.setFocus()
    picker.search.setText(query)
    settle(app)
    assert expected in picker.visible_codes and picker.search.hasFocus()
    assert picker.grid.count() == len(picker.visible_codes)
    assert all(picker.buttons[code].isHidden() == (code not in picker.visible_codes)
               for code in picker.buttons)
    before = picker.search.text()
    picker.set_language(expected)
    assert picker.search.text() == before and picker.search.hasFocus()
    assert picker.buttons[expected].isChecked()


def test_no_matches_keeps_search_and_close_accessible_then_recovers(make_picker, app):
    picker = make_picker(40)
    picker._focus_search()
    QTest.keyClicks(picker.search, 'not-a-language')
    settle(app)
    assert not picker.visible_codes and picker.empty.isVisible() and picker.grid.count() == 0
    assert picker.search.hasFocus()
    QTest.keyClick(picker.search, QtCore.Qt.Key_Tab)
    assert picker.close_button.hasFocus()
    QTest.keyClick(picker.close_button, QtCore.Qt.Key_Tab)
    assert picker.search.hasFocus()
    picker.search.clear()
    settle(app)
    assert len(picker.visible_codes) == 40 and not picker.empty.isVisible()
    assert picker.grid.count() == 40


def test_keyboard_roving_grid_and_filter_apply_only_on_activation(make_picker, app):
    picker = make_picker()
    picker.focus_current_language(keyboard=True)
    selected = QSignalSpy(picker.languageSelected)
    QTest.keyClick(picker.buttons['en'], QtCore.Qt.Key_Right)
    assert picker.buttons['ru'].hasFocus()
    QTest.keyClick(picker.buttons['ru'], QtCore.Qt.Key_Down)
    assert picker.buttons['zh'].hasFocus()
    QTest.keyClick(picker.buttons['zh'], QtCore.Qt.Key_Up)
    assert picker.buttons['ru'].hasFocus() and picker._current == 'en' and len(selected) == 0
    QTest.keyClick(picker.buttons['ru'], QtCore.Qt.Key_Tab)
    assert picker.close_button.hasFocus()
    QTest.keyClick(picker.close_button, QtCore.Qt.Key_Tab)
    assert picker.search.hasFocus()
    QTest.keyClick(picker.search, QtCore.Qt.Key_Tab)
    assert picker.buttons['ru'].hasFocus()
    QTest.keyClick(picker.buttons['ru'], QtCore.Qt.Key_F, QtCore.Qt.ControlModifier)
    assert picker.search.hasFocus()
    QTest.keyClicks(picker.search, 'port')
    assert picker.visible_codes == ('pt',) and picker.search.hasFocus()
    QTest.keyClick(picker.search, QtCore.Qt.Key_Down)
    assert picker.buttons['pt'].hasFocus() and len(selected) == 0
    QTest.keyClick(picker.buttons['pt'], QtCore.Qt.Key_Return)
    assert list(selected) == [['pt']] and picker._current == 'pt'
    assert picker.search.text() == 'port' and picker.buttons['pt'].hasFocus()
    assert picker.buttons['pt'].isChecked() and picker.ticks['pt'].width() == 12


def test_short_final_row_arrows_never_focus_an_empty_cell(make_picker, app):
    picker = make_picker(13)
    picker.focus_current_language(keyboard=True)
    QTest.keyClick(picker.buttons['en'], QtCore.Qt.Key_End)
    last = picker.buttons['lang_12']
    assert last.hasFocus()
    for key in (QtCore.Qt.Key_Right, QtCore.Qt.Key_Down, QtCore.Qt.Key_Left):
        QTest.keyClick(last, key)
        assert last.hasFocus()
    QTest.keyClick(last, QtCore.Qt.Key_Up)
    assert picker.buttons['ar'].hasFocus()


@pytest.mark.parametrize('dark', [True, False])
def test_rtl_names_flags_check_and_theme_do_not_rearrange_catalog(make_picker, app, dark):
    picker = make_picker()
    picker.set_theme(dark)
    picker.set_language('ar')
    settle(app)
    assert picker.layoutDirection() == QtCore.Qt.LeftToRight
    assert picker.name_labels['ar'].layoutDirection() == QtCore.Qt.RightToLeft
    assert picker.name_labels['en'].layoutDirection() == QtCore.Qt.LeftToRight
    assert picker.buttons['ar'].isChecked() and not picker.buttons['en'].isChecked()
    before = {code: button.geometry() for code, button in picker.buttons.items()}
    for code, label in picker.name_labels.items():
        assert label.fontMetrics().horizontalAdvance(label.text()) <= label.width()+1
        flag = picker.buttons[code].findChild(QtWidgets.QLabel, 'interfaceLanguageFlag')
        assert not flag.pixmap().isNull() and flag.pixmap().devicePixelRatio() == 4
        assert picker.ticks[code].width() == 12
    picker.set_language('pt')
    settle(app)
    assert before == {code: button.geometry() for code, button in picker.buttons.items()}
    area = picker.choices
    assert not area.mask().contains(QtCore.QPoint(0, area.height()-1))
    assert not area.mask().contains(QtCore.QPoint(area.width()-1, area.height()-1))


def test_navigating_away_closes_picker_cleanly(window, app):
    window.show_interface_language_menu()
    window.show_settings()
    settle(app)
    assert window._interface_language_picker is None and window.settings_window.isVisible()
    window.show_interface_language_menu()
    window.show_main_screen()
    settle(app)
    assert window._interface_language_picker is None and window.main_text_section.isVisible()


@pytest.mark.parametrize('dark', [True, False])
def test_actual_canvas_catalog_surface_matches_theme(window, app, dark):
    from button_styles import set_pointer_hover
    if (window.current_theme != 'Светлая') != dark:
        window.toggle_theme()
    window.set_interface_language('ru')
    window.show_interface_language_menu()
    picker = window._interface_language_picker
    picker._set_keyboard_mode(False)
    for button in picker.buttons.values():
        set_pointer_hover(button, False)
    settle(app)
    canvas = window.ui_root.grab()
    pixels = canvas.toImage()
    expected = '#121116' if dark else '#f8f5fb'
    for code in ('en', 'es', 'de', 'id'):
        point = picker.buttons[code].mapTo(window.ui_root, QtCore.QPoint(3, 3))
        point *= canvas.devicePixelRatio()
        assert pixels.pixelColor(point).name() == expected, (code, pixels.pixelColor(point).name())
    selected = picker.buttons['ru'].mapTo(window.ui_root, QtCore.QPoint(3, 3))
    selected *= canvas.devicePixelRatio()
    assert pixels.pixelColor(selected).name() != expected


@pytest.mark.parametrize('locale', list(main.INTERFACE_LANGUAGE_BY_CODE))
def test_picker_fits_at_all_interface_scales_in_both_themes(window, app, locale):
    window.set_interface_language(locale)
    for dark in (True, False):
        if (window.current_theme != 'Светлая') != dark:
            window.toggle_theme()
        for scale in (80, 100, 125, 150, 200):
            window.set_ui_scale_percent(scale)
            settle(app)
            before = window.size()
            window.show_interface_language_menu()
            picker = window._interface_language_picker
            settle(app)
            assert window.size() == before and picker.buttons[locale].isVisible()
            assert picker.title.fontMetrics().horizontalAdvance(picker.title.text()) <= picker.title.width()
            for label in picker.name_labels.values():
                assert label.fontMetrics().horizontalAdvance(label.text()) <= label.width()+1
            assert picker.grid.count() == 12 and picker.header.height() == 28
            picker.close_button.click()
            settle(app)
            assert not window.flag_button.isChecked() and window.size() == before
