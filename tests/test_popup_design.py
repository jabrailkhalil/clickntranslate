"""Dropdown cards fit their real labels, search chrome and monitor boundaries."""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from capture_widgets import CaptureLanguageCombo
from combo_popup import PopupRowDelegate
from language_search import SEARCH_TEXT
from languages import LANGUAGES, language_icon_path
from project_paths import resource_root
from settings_window import DropDownCombo
from test_desktop_ux import app, window


@pytest.fixture
def show_picker(app):
    widgets = []
    def show(combo):
        widgets.append(combo)
        combo.move(100, 60)
        combo.show()
        app.processEvents()
        combo.showPopup()
        app.processEvents()
        app.processEvents()
        return combo.view(), combo.view().window()
    yield show
    for widget in widgets:
        widget.hidePopup()
        widget.close()
        widget.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('dark', [True, False])
def test_single_template_uses_an_inset_card_without_explicit_popup_setup(app, show_picker, dark):
    combo = DropDownCombo()
    combo.setFixedSize(460, 32)
    combo.setStyleSheet(f'''QComboBox {{ background:{'#211d28' if dark else '#faf8fc'};
        color:{'#eee7f5' if dark else '#302639'}; border:1px solid #584963; padding:3px 8px; }}''')
    combo.addItem('New layout')
    view, popup = show_picker(combo)
    assert isinstance(combo.itemDelegate(), PopupRowDelegate)
    row = view.visualRect(combo.model().index(0, 0))
    bounds = QtCore.QRect(view.viewport().mapTo(popup, row.topLeft()), row.size())
    assert bounds.top() >= 5 and bounds.left() >= 5
    assert bounds.bottom() < popup.height()-5 and bounds.right() < popup.width()-5
    assert row.height() >= combo.fontMetrics().height()+10
    assert popup.width() == combo.width()
    picture = popup.grab().toImage()
    assert picture.pixelColor(0, 0).alpha() < 100
    assert picture.pixelColor(picture.width()//2, 2).alpha() > 240
    assert (picture.pixelColor(picture.width()//2, 2).lightness() < 128) == dark


def test_embedded_popup_corner_keeps_actual_owner_backdrop_instead_of_black(window, app):
    from settings_sections import PAGE_OCR
    from ui_scaling import widget_global_rect
    window.set_interface_language('ar')
    if window.current_theme != 'Светлая':
        window.toggle_theme()
    window.set_ui_scale_percent(125)
    window.show_settings()
    window.settings_window._set_settings_page(PAGE_OCR)
    for _ in range(8):
        app.processEvents()
    backdrop = window.grab().toImage()
    combo = window.settings_window.ocr_engine_combo
    combo.showPopup()
    for _ in range(8):
        app.processEvents()
    popup = combo.view().window()
    assert popup.graphicsProxyWidget() is not None
    picture = window.grab()
    image = picture.toImage()
    bounds = widget_global_rect(popup)
    origin = window.mapFromGlobal(bounds.topLeft()) * picture.devicePixelRatio()
    width = round(bounds.width()*picture.devicePixelRatio())
    height = round(bounds.height()*picture.devicePixelRatio())
    radius = round(10*bounds.width()/popup.width()*picture.devicePixelRatio())
    black_holes = []
    for left, top in ((origin.x(), origin.y()), (origin.x()+width-radius, origin.y()),
                      (origin.x(), origin.y()+height-radius),
                      (origin.x()+width-radius, origin.y()+height-radius)):
        for x in range(left, min(image.width(), left+radius)):
            for y in range(top, min(image.height(), top+radius)):
                # These small corner patches contain chrome, never row text.
                # popup.grab() alone misses Source-mode holes in the scene.
                if backdrop.pixelColor(x, y).lightness() > 220 and image.pixelColor(x, y).lightness() < 50:
                    black_holes.append((x, y, image.pixelColor(x, y).getRgb()))
    combo.hidePopup()
    assert not black_holes, black_holes[:10]


@pytest.mark.parametrize('dark', [True, False])
def test_nonembedded_popup_retains_transparent_corners_when_content_shrinks(app, show_picker, dark):
    from settings_window import modern_combo_style
    combo = DropDownCombo()
    combo.setFixedSize(300, 28)
    combo.setStyleSheet(modern_combo_style(dark, font_size=14))
    combo.set_popup_background('#20212a' if dark else '#f1edf4')
    combo.addItem('Initial choice')
    view, popup = show_picker(combo)
    assert popup.graphicsProxyWidget() is None
    for count in (1, 5, 2):
        combo.hidePopup()
        combo.clear()
        combo.addItems([f'Choice {row}' for row in range(count)])
        combo.showPopup()
        for _ in range(5):
            app.processEvents()
        image = popup.grab().toImage()
        for point in (QtCore.QPoint(), QtCore.QPoint(image.width()-1, 0),
                      QtCore.QPoint(0, image.height()-1), QtCore.QPoint(image.width()-1, image.height()-1)):
            assert image.pixelColor(point).alpha() <= 8
        surface = image.pixelColor(image.width()//2, 2)
        assert surface.alpha() >= 240 and (surface.lightness() < 128) == dark


@pytest.mark.parametrize('locale', SEARCH_TEXT)
@pytest.mark.parametrize('factor', [1., 1.5, 2.])
@pytest.mark.parametrize('dark', [True, False])
def test_capture_popup_measures_full_localized_names_including_flags_and_check(app, show_picker, locale, factor, dark):
    combo = CaptureLanguageCombo()
    for language in LANGUAGES:
        combo.addItem(QtGui.QIcon(str(resource_root()/language_icon_path(language.code))),
                      language.short_label, language.code)
    combo.set_capture_theme(dark, locale, factor)
    bounds = QtCore.QRect(0, 0, 1800, 1400)
    combo._available_screen_rect = lambda: bounds
    view, popup = show_picker(combo)
    assert bounds.contains(popup.geometry())
    assert combo._language_search.placeholderText() == SEARCH_TEXT[locale][0]
    assert popup.width() > combo.width()
    option = QtWidgets.QStyleOptionViewItem()
    option.initFrom(view)
    largest = max(combo.itemDelegate().sizeHint(option, combo.model().index(row, 0)).width()
                  for row in range(combo.count()))
    assert view.viewport().width() >= largest
    assert view.verticalScrollBar().isVisible()
    # The search input and the first visible item must never overlap.
    first = view.visualRect(view.indexAt(QtCore.QPoint(2, 2)))
    item_top = view.viewport().mapTo(popup, first.topLeft()).y()
    assert item_top > combo._language_search.geometry().bottom()
    last = combo.model().index(combo.count()-1, 0)
    view.scrollTo(last, QtWidgets.QAbstractItemView.PositionAtBottom)
    app.processEvents()
    assert view.viewport().rect().contains(view.visualRect(last))
    geometry = popup.geometry()
    combo.hidePopup()
    combo.showPopup()
    app.processEvents()
    assert popup.geometry() == geometry


@pytest.mark.parametrize('locale', SEARCH_TEXT)
def test_search_empty_state_is_localized_and_clearing_preserves_indexes(app, show_picker, locale):
    combo = CaptureLanguageCombo()
    for language in LANGUAGES:
        combo.addItem(language.short_label, language.code)
    combo.set_capture_theme(True, locale)
    show_picker(combo)
    original = combo.findData('ru')
    combo._language_search.setText('zzzz-no-language')
    app.processEvents()
    assert combo._language_empty.isVisible()
    assert combo._language_empty.text() == SEARCH_TEXT[locale][1]
    assert combo.view().window().height() <= combo._language_search.height()+combo._language_empty.height()+30
    assert all(combo.view().isRowHidden(i) for i in range(combo.count()))
    QTest.keyClick(combo._language_search, QtCore.Qt.Key_Return)
    assert combo.view().window().isVisible()
    combo._language_search.setText('Russian')
    app.processEvents()
    assert not combo._language_empty.isVisible()
    QTest.keyClick(combo._language_search, QtCore.Qt.Key_Return)
    assert combo.currentIndex() == original and combo.currentData() == 'ru'
    assert not combo.view().window().isVisible()


def test_search_header_disappears_when_provider_reduces_languages(app, show_picker):
    combo = CaptureLanguageCombo()
    for language in LANGUAGES:
        combo.addItem(language.short_label, language.code)
    show_picker(combo)
    combo._language_search.setText('Russian')
    combo.hidePopup()
    combo.clear()
    combo.addItems(['EN', 'RU'])
    combo.showPopup()
    app.processEvents()
    assert not combo._language_search.isVisible() and not combo._language_empty.isVisible()
    assert not combo.view().isRowHidden(0) and not combo.view().isRowHidden(1)
    assert combo.view().window().height() < 110


@pytest.mark.parametrize('locale', SEARCH_TEXT)
def test_all_language_options_have_flags_even_when_original_field_has_no_icons(app, show_picker, locale):
    combo = DropDownCombo()
    combo.interface_language = locale
    for language in LANGUAGES:
        combo.addItem(language.display_name(locale), language.code)
    show_picker(combo)
    delegate = combo.itemDelegate()
    for row, language in enumerate(LANGUAGES):
        flag = delegate.icon(combo.model().index(row, 0))
        assert not flag.isNull(), language.code
        assert not flag.pixmap(60, 60).isNull(), language.code
    # Adding flags to the list must not change ISO values or selected indexes.
    assert [combo.itemData(i) for i in range(combo.count())] == [language.code for language in LANGUAGES]


def test_legacy_localized_names_get_flags_without_assigning_a_flag_to_unknown_choices(app, show_picker):
    combo = DropDownCombo()
    combo.addItems([language.display_name('fr') for language in LANGUAGES])
    combo.addItem('A custom unavailable option')
    show_picker(combo)
    assert not combo.itemDelegate().icon(combo.model().index(0, 0)).isNull()
    assert combo.itemDelegate().icon(combo.model().index(combo.count()-1, 0)).isNull()
