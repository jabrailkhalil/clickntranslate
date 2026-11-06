from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest
import pytest

from capture_widgets import CaptureLanguageCombo
from languages import LANGUAGES, language_icon_path, language_display_name
from project_paths import resource_root
from styled_dialogs import install_tooltip_style


@pytest.mark.parametrize('dark', [True, False])
def test_capture_popup_direction_follows_locale_inside_a_fixed_ltr_toolbar(dark):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    toolbar = QtWidgets.QWidget()
    toolbar.setLayoutDirection(QtCore.Qt.LeftToRight)
    combo = CaptureLanguageCombo(toolbar)
    for language in LANGUAGES:
        combo.addItem(language.english_name, language.code)
    toolbar.resize(400, 200)
    toolbar.show()
    try:
        for locale, direction in (('en', QtCore.Qt.LeftToRight), ('ar', QtCore.Qt.RightToLeft),
                                  ('ru', QtCore.Qt.LeftToRight)):
            combo.set_capture_theme(dark, locale, 1.37)
            combo.showPopup()
            app.processEvents()
            assert toolbar.layoutDirection() == QtCore.Qt.LeftToRight
            assert combo.layoutDirection() == direction
            assert combo.view().layoutDirection() == direction
            search = combo._language_search
            assert search.layoutDirection() == direction
            search.setText('Vietnamese')
            app.processEvents()
            row = combo.findData('vi')
            assert row >= 0 and not combo.view().isRowHidden(row)
            combo.hidePopup()
    finally:
        combo.hidePopup()
        toolbar.close()
        toolbar.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('dark', [True, False])
def test_capture_picker_keeps_codes_and_reopens_inside_screen(dark):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    install_tooltip_style(app)
    owner = QtWidgets.QWidget()
    combo = CaptureLanguageCombo(owner)
    for language in LANGUAGES:
        icon = QtGui.QIcon(str(resource_root() / language_icon_path(language.code)))
        assert not icon.isNull(), language.code
        assert not icon.pixmap(24, 18).isNull(), language.code
        combo.addItem(icon, language.short_label, language.code)
    combo.set_capture_theme(dark, 'ru')
    combo.setCurrentIndex(combo.findData('en'))
    owner.resize(160, 90)
    bounds = app.primaryScreen().availableGeometry()
    owner.move(bounds.right() - 160, bounds.bottom() - 90)
    owner.show()
    QTest.qWait(30)
    try:
        geometries = []
        for _ in range(2):
            combo.showPopup()
            QTest.qWait(30)
            popup = combo.view().window()
            assert bounds.contains(popup.geometry())
            assert popup.width() > combo.width()
            assert popup.testAttribute(QtCore.Qt.WA_TranslucentBackground)
            picture = popup.grab().toImage()
            surface = picture.pixelColor(picture.width() // 2, 4)
            assert surface.alpha() > 240
            assert (surface.lightness() < 128) == dark
            geometries.append(popup.geometry())
            last = combo.model().index(combo.count() - 1, 0)
            combo.view().scrollTo(last, QtWidgets.QAbstractItemView.PositionAtBottom)
            app.processEvents()
            assert combo.view().viewport().rect().intersects(combo.view().visualRect(last))
            combo.hidePopup()
        assert geometries[0] == geometries[1]
        index = combo.model().index(combo.findData('ru'), 0)
        assert combo.itemDelegate().label(index) == language_display_name('ru', 'ru')
        combo.showPopup()
        combo.view().scrollTo(index)
        QTest.qWait(30)
        QTest.mouseClick(combo.view().viewport(), QtCore.Qt.LeftButton,
                         pos=combo.view().visualRect(index).center())
        assert combo.currentData() == 'ru'
    finally:
        combo.hidePopup()
        owner.close()
        owner.deleteLater()
