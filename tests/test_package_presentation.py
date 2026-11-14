"""Provider navigation and catalog sizes as seen by the user before downloading."""
from unittest import mock
import copy
import pytest
from PyQt5 import QtCore, QtWidgets, QtTest

from settings_window import DropDownCombo, _populate_grouped_translator_combo, _populate_grouped_ocr_combo, OcrLanguageManagerDialog
from provider_categories import CATEGORY_ROLE
from package_presentation import PackageSizes, TEXT, text, format_size
from test_language_package_manager import _AppParent, _ManagerOwner
from component_catalog import current_platform


def size_catalog():
    bundle = dict(id='easyocr-test', component='ocr.easyocr', channel='stable', revision=1,
                  contract=3, os='windows', arch='x86_64', min_os='10', app='>=1.8.2,<2',
                  languages=['latin_g2', 'english_g2'], files=[dict(sha256='runtime', destination='runtime'),
                  dict(sha256='craft', destination='models/craft.pth')], language_files={
                      'latin_g2': [dict(sha256='latin', destination='models/latin.pth')],
                      'english_g2': [dict(sha256='english', destination='models/english.pth')]})
    return dict(bundles=[bundle], artifacts={name: {'size': value} for name, value in
                                           [('runtime', 200000000), ('craft', 77000000), ('latin', 15000000), ('english', 10000000)]})


def test_shared_languages_and_detector_are_not_counted_twice():
    sizes = PackageSizes(size_catalog(), target=dict(os='windows', arch='x86_64', os_version='10'))
    assert sizes.split_base('easyocr') == (200000000, 77000000)
    assert sizes.size('easyocr', ['latin_g2', 'latin_g2', 'english_g2']) == 302000000
    assert sizes.size('easyocr', ['latin_g2', 'latin_g2'], base=False) == 15000000
    shared = size_catalog()
    shared['bundles'][0]['language_files']['latin_g2'].append(dict(sha256='craft', destination='models/alias.pth'))
    assert PackageSizes(shared, target=dict(os='windows', arch='x86_64', os_version='10')).breakdown('easyocr', ['latin_g2']) == (200000000, 92000000)
    assert sizes.size('hymt') is None
    assert format_size(1133080512) == '1.13 GB'
    assert PackageSizes(size_catalog(), target=dict(os='macos', arch='arm64', os_version='15')).size('easyocr') is None


def platform_size_catalog():
    catalog = size_catalog()
    target = current_platform()
    catalog['bundles'][0].update(os=target['os'], arch=target['arch'], min_os='0')
    return catalog


@pytest.mark.parametrize('lang', tuple(TEXT))
@pytest.mark.parametrize('dark', (True, False))
def test_category_tabs_switch_visible_providers_without_committing_a_selection(lang, dark, tmp_path):
    app = QtWidgets.QApplication.instance()
    host = QtWidgets.QWidget()
    host.resize(360, 340)
    combo = DropDownCombo(host)
    combo.setGeometry(15, 10, 260, 32)
    combo.set_popup_background('#17181d' if dark else '#e9e4ed')
    combo.setLayoutDirection(QtCore.Qt.RightToLeft if lang == 'ar' else QtCore.Qt.LeftToRight)
    _populate_grouped_translator_combo(combo, lang)
    combo.setCurrentIndex(combo.findData('google'))
    selected = combo.currentIndex()
    host.show()
    try:
        combo.showPopup()
        app.processEvents()
        bar = combo._provider_category_bar
        assert [bar.tabData(i) for i in range(bar.count())] == ['offline', 'online', 'api']
        assert bar.tabData(bar.currentIndex()) == 'online'
        for category in range(bar.count()):
            QtTest.QTest.mouseClick(bar, QtCore.Qt.LeftButton, pos=bar.tabRect(category).center())
            app.processEvents()
            assert combo.view().window().isVisible()
            assert combo.currentIndex() == selected
            visible = [i for i in range(combo.count()) if not combo.view().isRowHidden(i)]
            assert visible and all(combo.itemData(i, CATEGORY_ROLE) == bar.tabData(category) for i in visible)
            assert all(not combo.itemData(i, combo.GROUP_HEADER_ROLE) for i in visible)
            assert combo.view().window().rect().contains(bar.geometry())
            for i in range(bar.count()):
                assert bar.fontMetrics().horizontalAdvance(bar.tabText(i)) + 12 <= bar.tabRect(i).width()
        QtTest.QTest.keyClick(combo.view(), QtCore.Qt.Key_Left)
        app.processEvents()
        assert bar.currentIndex() != 2
        combo.hidePopup()
        assert combo.currentIndex() == selected
        combo.showPopup()
        app.processEvents()
        assert bar.tabData(bar.currentIndex()) == 'online'
        assert combo.view().window().grab().save(str(tmp_path / f'picker-{lang}-{dark}.png'))
    finally:
        combo.hidePopup()
        host.close()
        host.deleteLater()
        app.processEvents()


def test_ocr_picker_has_only_supported_categories():
    combo = DropDownCombo()
    _populate_grouped_ocr_combo(combo, 'ru')
    assert [key for key, label in combo._provider_categories] == ['offline', 'api']
    combo.deleteLater()


@pytest.mark.parametrize('lang', tuple(TEXT))
@pytest.mark.parametrize('theme', ('Темная', 'Светлая'))
def test_package_sizes_and_navigation_fit_the_fixed_window(lang, theme, tmp_path):
    app = QtWidgets.QApplication.instance()
    parent = _AppParent()
    parent.current_interface_language = lang
    parent.current_theme = theme
    owner = _ManagerOwner(parent)
    with mock.patch('settings_window.QtCore.QTimer.singleShot'):
        dialog = OcrLanguageManagerDialog(owner)
    dialog.setLayoutDirection(QtCore.Qt.RightToLeft if lang == 'ar' else QtCore.Qt.LeftToRight)
    dialog._initial_probe_timer.stop()
    dialog._initial_catalog_timer.stop()
    try:
        dialog._easyocr_status_cache = (True, '')
        dialog._populate_easyocr_table(dialog.easyocr_table)
        russian = next(row for row in range(dialog.easyocr_table.rowCount())
                       if dialog.easyocr_table.item(row, 0).data(QtCore.Qt.UserRole) == 'ru')
        dialog.easyocr_table.item(russian, 0).setCheckState(QtCore.Qt.Checked)
        dialog._on_package_sizes_ready(platform_size_catalog())
        dialog.ocr_tabs.setCurrentWidget(dialog.easyocr_table.parentWidget())
        dialog.show()
        app.processEvents()
        table = dialog.easyocr_table
        assert table.columnCount() == 5
        assert table.item(russian, 0).checkState() == QtCore.Qt.Unchecked
        assert not table.item(russian, 0).flags() & QtCore.Qt.ItemIsEnabled
        expanded = copy.deepcopy(platform_size_catalog())
        expanded['bundles'][0]['languages'].append('cyrillic_g2')
        expanded['bundles'][0]['language_files']['cyrillic_g2'] = [dict(sha256='cyrillic', destination='models/cyrillic.pth')]
        expanded['artifacts']['cyrillic'] = dict(size=12000000)
        dialog._on_package_sizes_ready(expanded)
        assert table.item(russian, 0).flags() & QtCore.Qt.ItemIsEnabled
        assert table.item(russian, 4).text() == '12.0 MB'
        assert table.item(russian, 3).text() != text(lang, 'unsupported')
        for code in ('fr', 'de'):
            row = next(row for row in range(table.rowCount()) if table.item(row, 0).data(QtCore.Qt.UserRole) == code)
            assert table.item(row, 4).text() == '15.0 MB'
            table.item(row, 0).setCheckState(QtCore.Qt.Checked)
        assert '92.0 MB' in table._package_size_label.text()
        install = next(button for button in table._package_action_buttons if button.property('packageAction') == 'install')
        assert '15.0 MB' in install.text()
        assert '30.0 MB' not in table._package_size_label.text()
        app.processEvents()
        table.fit_columns()
        assert table.columnWidth(4) >= table.horizontalHeader().fontMetrics().horizontalAdvance(table.horizontalHeaderItem(4).text()) + 12
        for tabs in (dialog.tabs, dialog.ocr_tabs):
            bar = tabs.tabBar()
            if bar.isHidden():
                continue
            for i in range(bar.count()):
                assert bar.fontMetrics().horizontalAdvance(bar.tabText(i)) + 12 <= bar.tabRect(i).width()
        summary = table._package_size_label
        assert summary.height() >= summary.heightForWidth(summary.width())
        assert summary.parentWidget().rect().contains(summary.geometry())
        assert table.horizontalScrollBar().maximum() == 0
        assert table.parentWidget().rect().contains(table.geometry())
        assert table.parentWidget().rect().contains(table._package_action_widget.geometry())
        assert dialog.grab().save(str(tmp_path / f'packages-{lang}-{theme}.png'))
    finally:
        dialog.close()
        owner.close()
        parent.close()
        app.processEvents()
