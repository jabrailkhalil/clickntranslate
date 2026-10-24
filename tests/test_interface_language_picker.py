"""Language choices remain readable, searchable and bounded as the catalog grows."""
import math

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
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
    assert picker.choices.mask().isEmpty()  # Rounded clipping is antialiased, not a QRegion.


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


@pytest.mark.parametrize('dark', [True, False])
def test_outer_contour_covers_corner_cell_fills_at_fractional_scales(window, app, dark, tmp_path):
    from button_styles import set_pointer_hover
    if (window.current_theme != 'Светлая') != dark:
        window.toggle_theme()
    window.set_interface_language('ar')
    edge = QtGui.QColor('#62566e' if dark else '#927cab')
    controller = window._ui_scale_controller
    viewport = controller.view.viewport()
    for percent in (80, 110, 125, 150, 200):
        window.set_ui_scale_percent(percent)
        settle(app)
        before = viewport.grab().toImage()
        window.show_interface_language_menu()
        picker = window._interface_language_picker
        picker._set_keyboard_mode(False)
        for button in picker.buttons.values():
            set_pointer_hover(button, False)
        set_pointer_hover(picker.buttons['id'], True)
        settle(app)
        pixels = viewport.grab()
        image = pixels.toImage()
        image.save(str(tmp_path/f'language-contour-{dark}-{percent}.png'))
        origin = picker.mapTo(window.ui_root, QtCore.QPoint())
        def device_point(x, y):
            point = controller.proxy.mapToScene(QtCore.QPointF(origin)+QtCore.QPointF(x, y))
            return controller.view.viewportTransform().map(point)*pixels.devicePixelRatio()
        assert picker.scroll.verticalScrollBar().maximum() == 0
        catalog_viewport = picker.scroll.viewport()
        for code in ('en', 'de', 'ar', 'id'):
            button = picker.buttons[code]
            assert catalog_viewport.rect().contains(
                QtCore.QRect(button.mapTo(catalog_viewport, QtCore.QPoint()), button.size()))
        # Selected and hover fills at the bottom must leave the outer tips
        # exactly as the underlying application canvas painted them.
        width, height = picker.width(), picker.height()
        for x, y in ((0, 0), (width-.2, 0), (0, height-.2), (width-.2, height-.2)):
            point = device_point(x, y)
            point = QtCore.QPoint(math.floor(point.x()), math.floor(point.y()))
            color, backdrop = image.pixelColor(point), before.pixelColor(point)
            assert sum(abs(a-b) for a, b in zip(color.getRgb(), backdrop.getRgb())) <= 8, (
                dark, percent, x, y, color.getRgb(), backdrop.getRgb())
        # Trace all four corner arcs through their joins with the straight
        # edges. Cell fills must never cover a section of the outline.
        for cx, cy, sx, sy in ((10, 10, -1, -1), (width-10, 10, 1, -1),
                               (10, height-10, -1, 1), (width-10, height-10, 1, 1)):
            for degrees in range(0, 91, 10):
                angle = math.radians(degrees)
                point = device_point(cx+sx*9.5*math.cos(angle), cy+sy*9.5*math.sin(angle))
                x, y = math.floor(point.x()), math.floor(point.y())
                distance = min(sum(abs(a-b) for a, b in zip(image.pixelColor(px, py).getRgb()[:3], edge.getRgb()[:3]))
                               for px in range(max(0, x-1), min(image.width(), x+2))
                               for py in range(max(0, y-1), min(image.height(), y+2)))
                # A 0.8-device-pixel stroke blends more strongly at a curve.
                assert distance <= (100 if percent == 80 else 75), (dark, percent, cx, cy, degrees, distance)
        # The outline must preserve the native proxy-rendered text exactly.
        # No effect may rasterize the whole panel a second time.
        label = picker.name_labels['en']
        start = controller.map_widget_to_view(label, QtCore.QPoint())
        end = controller.map_widget_to_view(label, QtCore.QPoint(label.width(), label.height()))
        text_rect = QtCore.QRect(start*pixels.devicePixelRatio(), end*pixels.devicePixelRatio())
        assert picker.graphicsEffect() is None
        picker._outline.hide()
        settle(app)
        unclipped = viewport.grab().toImage()
        assert image.copy(text_rect) == unclipped.copy(text_rect), (dark, percent)
        picker._outline.show()
        picker.close_button.click()
        settle(app)



@pytest.mark.parametrize('locale', list(main.INTERFACE_LANGUAGE_BY_CODE))
def test_picker_fits_at_all_interface_scales_in_both_themes(window, app, locale):
    window.set_interface_language(locale)
    for dark in (True, False):
        if (window.current_theme != 'Светлая') != dark:
            window.toggle_theme()
        for scale in (80, 100, 110, 125, 150, 200):
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


@pytest.mark.parametrize('count', [20, 40])
@pytest.mark.parametrize('dark', [True, False])
def test_scrolled_intermediate_row_cannot_cover_bottom_outline(window, app, monkeypatch, count, dark):
    from button_styles import set_pointer_hover
    options = list(main.INTERFACE_LANGUAGE_OPTIONS)
    options += [dict(code=f'lang_{i}', name=f'Language {i}', icon='icons/American_flag.png')
                for i in range(12, count)]
    monkeypatch.setattr(main, 'INTERFACE_LANGUAGE_OPTIONS', options)
    if (window.current_theme != 'Светлая') != dark:
        window.toggle_theme()
    window.set_ui_scale_percent(125)
    settle(app)
    controller = window._ui_scale_controller
    before = controller.view.viewport().grab().toImage()
    window.show_interface_language_menu()
    settle(app)  # Finish the opener's deferred focus before simulating a scroll.
    picker = window._interface_language_picker
    picker.set_language('lang_12')
    for button in picker.buttons.values():
        set_pointer_hover(button, False)
    set_pointer_hover(picker.buttons['lang_15'], True)
    picker.scroll.verticalScrollBar().setValue(13)
    settle(app)
    assert picker.scroll.verticalScrollBar().value() == 13
    assert picker.buttons['lang_12'].height() == 38
    image = controller.view.viewport().grab().toImage()
    edge = QtGui.QColor('#62566e' if dark else '#927cab')
    origin = picker.mapTo(window.ui_root, QtCore.QPoint())
    def point_at(x, y):
        point = controller.proxy.mapToScene(QtCore.QPointF(origin)+QtCore.QPointF(x, y))
        return controller.view.viewportTransform().map(point)
    for cx, sx in ((10, -1), (picker.width()-10, 1)):
        for degrees in range(0, 91, 10):
            angle = math.radians(degrees)
            point = point_at(cx+sx*9.5*math.cos(angle), picker.height()-10+9.5*math.sin(angle))
            x, y = math.floor(point.x()), math.floor(point.y())
            distance = min(sum(abs(a-b) for a, b in zip(image.pixelColor(px, py).getRgb()[:3], edge.getRgb()[:3]))
                           for px in range(x-1, x+2) for py in range(y-1, y+2))
            assert distance <= 75, (count, dark, degrees, distance)
    for x in (0, picker.width()-.2):
        point = point_at(x, picker.height()-.2)
        point = QtCore.QPoint(math.floor(point.x()), math.floor(point.y()))
        assert image.pixelColor(point) == before.pixelColor(point)
