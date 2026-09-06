import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets, sip

import main
import platform_support
import translater
from window_appearance import install_window_appearance

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def appearance():
    app = _APP
    from qt_layout_test_support import ensure_layout_fonts
    ensure_layout_fonts(app)
    app.setQuitOnLastWindowClosed(False)
    manager = install_window_appearance(app, 100, 'Темная')
    with mock.patch.object(manager, 'available_geometry', return_value=QtCore.QRect(0, 0, 3840, 2160)):
        yield manager
    app.removeEventFilter(manager)
    del app._dialog_appearance
    app.setProperty('ui_theme', None)
    for window in list(manager._windows):
        if sip.isdeleted(window):
            continue
        window.close()
        window.deleteLater()
    manager.deleteLater()
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


def result_dialog():
    return main.TranslationResultDialog(None, 'Hello', auto_copy=False, lang='ru',
                                        source_text='Hola', source_lang='es', target_lang='en')


def test_dialogs_follow_global_scale_without_accumulating_changes(appearance):
    dialog = result_dialog()
    dialog.show()
    appearance.app.processEvents()
    baseline = appearance._windows[dialog]['size']
    for percent in (80, 100, 150, 100, 80):
        appearance.refresh(percent=percent)
        appearance.app.processEvents()
        expected = baseline * (percent / 80)
        assert abs(dialog.width() - expected.width()) <= 2
        assert abs(dialog.height() - expected.height()) <= 2
        assert dialog.text_edit.toPlainText() == 'Hello'
        assert dialog.scale_value.text() == f'{percent}%'
    assert dialog.title_close_button.size() == QtCore.QSize(32, 32)


def test_local_result_scale_keeps_global_setting_and_edits(appearance):
    dialog, other = result_dialog(), result_dialog()
    dialog.show()
    other.show()
    appearance.app.processEvents()
    original = other.size()
    dialog.text_edit.insertPlainText('Edited ')
    dialog.scale_value.setText('137')
    dialog.scale_value.editingFinished.emit()
    assert dialog.scale_value.text() == '137%'
    assert appearance.percent == 100
    assert other.size() == original
    assert dialog.text_edit.toPlainText() == 'Edited Hello'
    dialog.scale_increase.click()
    assert dialog.scale_value.text() == '142%'


def test_copy_uses_edited_result(appearance):
    dialog = result_dialog()
    dialog.show()
    dialog.text_edit.setPlainText('Дополненный перевод')
    with mock.patch.object(platform_support, 'copy_text') as copy, \
            mock.patch.object(main, 'save_copy_history'):
        dialog.copy_button.click()
    copy.assert_called_once_with('Дополненный перевод')


def test_source_can_be_extended_and_retranslated(appearance):
    dialog = result_dialog()
    dialog.show()
    dialog.source_edit.setPlainText('Hola mundo')
    assert dialog.translate_button.text() == 'Перевести'
    with mock.patch.object(main.threading, 'Thread', side_effect=lambda target, **kw: SimpleNamespace(start=target)), \
            mock.patch.object(main, 'save_translation_history'), \
            mock.patch.object(translater, 'translate_text', return_value='Hello world') as translate:
        dialog.translate_button.click()
    translate.assert_called_once_with('Hola mundo', 'es', 'en', engine=mock.ANY, cancel_callback=mock.ANY)
    assert dialog.text_edit.toPlainText() == 'Hello world'
    assert dialog.source_edit.isVisible() and dialog.text_edit.isVisible()
    assert not dialog.text_edit.isReadOnly()


def test_open_dialogs_and_hardcoded_surfaces_follow_light_theme(appearance):
    dialog = result_dialog()
    legacy = QtWidgets.QDialog()
    legacy.resize(500, 300)
    layout = QtWidgets.QVBoxLayout(legacy)
    label = QtWidgets.QLabel('Legacy title')
    label.setStyleSheet('color: #ffffff; background: #111216; font-size: 16px;')
    layout.addWidget(label)
    legacy.setStyleSheet('QDialog {background: #111216; color: #f5f2fb;}')
    dialog.show()
    legacy.show()
    appearance.refresh(theme='Светлая')
    appearance.app.processEvents()
    assert dialog.theme == 'Светлая'
    assert '#ece7f0' in dialog.styleSheet()
    assert '#111216' not in legacy.styleSheet()
    assert '#ffffff' not in label.styleSheet()
    assert dialog.text_edit.palette().color(QtGui.QPalette.Text).lightness() < 100


def test_small_screen_limits_dialog_size_and_capture_widgets_are_untouched(appearance):
    capture = QtWidgets.QWidget()
    capture.setGeometry(0, 0, 1920, 1080)
    geometry = capture.geometry()
    dialog = result_dialog()
    with mock.patch.object(appearance, 'available_geometry', return_value=QtCore.QRect(0, 0, 800, 600)):
        dialog.show()
        appearance.refresh(percent=200)
        appearance.app.processEvents()
        assert dialog.width() <= 800
        assert dialog.height() <= 600
        assert capture.geometry() == geometry
    capture.close()


def test_tray_menu_keeps_native_size_and_position_at_every_window_scale(appearance):
    menu = QtWidgets.QMenu()
    for key in ('tray_open', 'tray_copy', 'tray_translate', 'tray_translate_screen', 'tray_game_translate', 'tray_exit'):
        menu.addAction(main.ui_text('en', key))
    available = appearance.app.primaryScreen().availableGeometry()
    baseline = None
    for theme in ('Светлая', 'Темная', 'Светлая'):
        for percent in (80, 100, 150, 200, 80):
            appearance.refresh(percent, theme)
            menu.popup(available.bottomRight())
            appearance.app.processEvents()
            if baseline is None:
                baseline = (menu.size(), menu.font(), [menu.actionGeometry(action) for action in menu.actions()])
            assert menu.size() == baseline[0]
            assert menu.font() == baseline[1]
            assert [menu.actionGeometry(action) for action in menu.actions()] == baseline[2]
            # Qt positions a tray popup above the taskbar and inside the monitor.
            assert available.contains(menu.geometry())
            assert (menu.palette().color(QtGui.QPalette.WindowText).lightness() > 128) == (theme == 'Темная')
            menu.hide()


@pytest.mark.parametrize('mode', ['copy', 'translate', 'fullscreen', 'game'])
def test_capture_controls_ignore_window_scale_and_keep_language_labels_visible(appearance, mode):
    import ocr
    import game_mode
    from qt_layout_test_support import ensure_layout_fonts
    ensure_layout_fonts(appearance.app)
    config = dict(main.DEFAULT_CONFIG, interface_language='en', translator_engine='Google',
                  ocr_translate_source_language='tr', ocr_translate_target_language='ru')
    shot = QtGui.QPixmap(appearance.app.primaryScreen().geometry().size())
    shot.fill(QtCore.Qt.black)
    with mock.patch.object(ocr, 'get_cached_ocr_config', return_value=config), \
            mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=['en', 'ru', 'tr']), \
            mock.patch.object(ocr, '_translation_targets_for_source', return_value=['en', 'ru', 'tr']), \
            mock.patch.object(ocr, '_write_ocr_config_updates'), \
            mock.patch.object(ocr, 'grab_screen_pixmap', return_value=shot), \
            mock.patch.object(ocr.ScreenCaptureOverlay, '_force_topmost'), \
            mock.patch.object(ocr.ScreenCaptureOverlay, '_capture_frozen_background'), \
            mock.patch.object(ocr.FullScreenTranslateOverlay, '_restart_translation_from_controls'):
        baseline = None
        for theme in ('Светлая', 'Темная'):
            for percent in (80, 100, 150, 200):
                config.update(theme=theme, ui_scale_percent=percent)
                appearance.refresh(percent, theme)
                if mode == 'game':
                    overlay = game_mode.GameRegionSelector()
                    combos = [overlay.source_combo, overlay.target_combo]
                    swap = overlay.swap_button
                    controls = [*combos, swap, overlay.undo_button, overlay.start_button]
                else:
                    overlay = (ocr.FullScreenTranslateOverlay() if mode == 'fullscreen'
                               else ocr.ScreenCaptureOverlay(mode))
                    combos = [combo for combo in (overlay.lang_combo, overlay.target_lang_combo) if combo is not None]
                    swap = overlay.translate_arrow_label
                    controls = [*combos, *([swap] if swap is not None else [])]
                try:
                    appearance.app.processEvents()
                    geometry = [widget.geometry() for widget in controls]
                    if baseline is None:
                        baseline = geometry
                    assert geometry == baseline
                    assert overlay.geometry() == appearance.app.primaryScreen().geometry()
                    for widget in controls:
                        assert overlay.rect().contains(widget.geometry())
                        for other in controls:
                            if widget is not other:
                                assert not widget.geometry().intersects(other.geometry())
                    for combo in combos:
                        option = QtWidgets.QStyleOptionComboBox()
                        combo.initStyleOption(option)
                        edit = combo.style().subControlRect(QtWidgets.QStyle.CC_ComboBox, option,
                                                           QtWidgets.QStyle.SC_ComboBoxEditField, combo)
                        for row in range(combo.count()):
                            assert edit.width() >= combo.iconSize().width() + 4 + combo.fontMetrics().horizontalAdvance(combo.itemText(row))
                        assert (combo.palette().color(QtGui.QPalette.Text).lightness() > 128) == (theme == 'Темная')
                    if swap is not None:
                        assert not swap.icon().isNull()
                        # The middle button needs its own opaque surface: the
                        # screenshot underneath can have the same colour as its ink.
                        image = swap.grab().toImage()
                        assert image.pixelColor(image.width() // 2, 4).alpha() == 255
                finally:
                    overlay.close()
                    overlay.deleteLater()
                    appearance.app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_result_scale_steps_keep_the_arrow_under_the_pointer(appearance):
    from PyQt5.QtTest import QTest
    dialog = result_dialog()
    dialog.show()
    appearance.app.processEvents()
    dialog.move(800, 400)
    button = dialog.scale_increase
    point = button.mapToGlobal(button.rect().center())
    for value in (105, 110, 115, 120):
        QTest.mouseClick(button, QtCore.Qt.LeftButton, pos=button.mapFromGlobal(point))
        appearance.app.processEvents()
        assert dialog.scale_value.text() == f'{value}%'
        assert button.rect().contains(button.mapFromGlobal(point))


def test_light_language_popup_has_a_visible_outline(appearance):
    dialog = result_dialog()
    dialog.show()
    appearance.refresh(theme='Светлая')
    dialog.target_combo.showPopup()
    appearance.app.processEvents()
    popup = dialog.target_combo.view().window()
    image = popup.grab().toImage()
    edge = image.pixelColor(0, image.height() // 2)
    assert edge.lightness() < 175
    assert 'border: 1px solid #897397' in popup.styleSheet()
    dialog.target_combo.hidePopup()


def test_help_html_keeps_its_font_size_across_theme_and_scale_changes(appearance):
    dialog = QtWidgets.QDialog()
    dialog.resize(500, 350)
    layout = QtWidgets.QVBoxLayout(dialog)
    browser = QtWidgets.QTextBrowser(dialog)
    browser.setHtml('<p style="font-size:14pt; color:#ffffff">Help text</p>')
    layout.addWidget(browser)
    dialog.show()
    appearance.app.processEvents()
    for theme, percent in [('Светлая', 150), ('Темная', 80), ('Светлая', 100), ('Темная', 80)]:
        appearance.refresh(percent, theme)
        appearance.app.processEvents()
    cursor = browser.textCursor()
    cursor.movePosition(QtGui.QTextCursor.Start)
    cursor.movePosition(QtGui.QTextCursor.NextCharacter)
    assert cursor.charFormat().fontPointSize() == 14


def test_document_layout_and_private_qt_fonts_do_not_accumulate_scale(appearance):
    appearance.refresh(80)
    dialog = main.DocumentTranslationDialog(None)
    dialog.show()
    appearance.app.processEvents()

    def container_fonts():
        # Do not retain these Python wrappers: Qt owns the native containers.
        return sorted((w.objectName(), w.font().pixelSize(), w.font().pointSizeF())
                      for w in dialog.findChildren(QtWidgets.QWidget)
                      if w.objectName() in ('qt_scrollarea_hcontainer', 'qt_scrollarea_vcontainer'))

    baseline = container_fonts()
    assert baseline
    for cycle in range(6):
        dialog.refresh_language(('de', 'ru', 'fr')[cycle % 3])
        for percent in (150, 200, 80):
            appearance.refresh(percent, 'Светлая' if cycle % 2 else 'Темная')
            appearance.app.processEvents()
            splitter = dialog.document_splitter
            left, right = splitter.widget(0), splitter.widget(1)
            assert right.x() - left.width() >= round(14 * percent / 80)
            assert left.y() == right.y() and left.height() == right.height()
        assert container_fonts() == baseline


def test_new_theme_icon_replaces_the_scaled_previous_icon(appearance):
    dialog = QtWidgets.QDialog()
    layout = QtWidgets.QVBoxLayout(dialog)
    icon = QtWidgets.QLabel(dialog)
    layout.addWidget(icon)
    def refresh(theme):
        pixmap = QtGui.QPixmap(20, 20)
        pixmap.fill(QtGui.QColor('white' if theme == 'Темная' else 'black'))
        icon.setPixmap(pixmap)
    dialog.refresh_theme = refresh
    refresh('Темная')
    dialog.show()
    appearance.refresh(theme='Светлая')
    assert icon.pixmap().toImage().pixelColor(0, 0) == QtGui.QColor('black')
    assert icon.pixmap().width() == 25
