"""Named font steps update the preview/result and fit the fixed settings form."""
import pytest
from PyQt5 import QtCore
from PyQt5.QtTest import QTest

import main
from control_hints import LANGUAGES
from settings_window import settings_text
from test_desktop_ux import app, window


@pytest.mark.parametrize('language', LANGUAGES)
def test_named_result_font_steps_and_live_preview_fit_every_locale(window, app, language):
    window.set_interface_language(language)
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(0)
    app.processEvents()
    control = settings.translation_font_control
    preview = settings.translation_font_preview
    for key, pixels in main.TRANSLATION_RESULT_FONT_SIZE_PX.items():
        control.setValue(key)
        app.processEvents()
        assert window.config['translation_result_font_size'] == key
        assert preview.font().pixelSize() == pixels
        assert control.editor.text() == settings_text(language, f'translation_result_font_{key}')
        assert 'px' not in control.editor.text()
        assert f'{pixels} px' in control.toolTip()
        assert control.editor.fontMetrics().horizontalAdvance(control.editor.text()) <= control.editor.width() - 4
        bounds = preview.fontMetrics().boundingRect(preview.text())
        assert bounds.width() <= preview.contentsRect().width(), (language, key, bounds, preview.contentsRect())
        assert bounds.height() <= preview.contentsRect().height(), (language, key, bounds, preview.contentsRect())
        assert settings.settings_general_page.rect().contains(
            QtCore.QRect(preview.mapTo(settings.settings_general_page, QtCore.QPoint()), preview.size()))
        assert settings.translation_font_label.buddy() is control
    ordered = (settings.ui_scale_control, control, preview)
    for above, below in zip(ordered, ordered[1:]):
        assert above.geometry().bottom() < below.geometry().top()
    assert settings.ui_scale_field.size() == control.size()


@pytest.mark.parametrize('light', [False, True])
def test_settings_fields_share_painted_borders_and_heights_across_sections(window, app, light):
    if light:
        window.toggle_theme()
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(0)
    app.processEvents()
    fields = (settings.ocr_engine_combo, settings.translator_combo,
              settings.result_window_control, settings.ui_scale_field,
              settings.translation_font_control)
    border = '#d7cde7' if window.current_theme == 'Светлая' else '#3d3948'
    boxes = []
    for field in fields:
        settings._set_settings_page(4 if field is settings.ocr_engine_combo else
                                    1 if field in (settings.translator_combo, settings.result_window_control) else 0)
        app.processEvents()
        field.clearFocus()
        field.setAttribute(QtCore.Qt.WA_UnderMouse, False)
        image = field.grab().toImage()
        pixels = [(x, y) for y in range(image.height()) for x in range(image.width())
                  if image.pixelColor(x, y).name() == border]
        assert pixels, field.objectName()
        boxes.append((min(x for x, y in pixels), min(y for x, y in pixels),
                      field.width()-1-max(x for x, y in pixels),
                      field.height()-1-max(y for x, y in pixels)))
    # Proxy rasterization may round a fractional scene origin by one pixel.
    # The approved compact layout gives selectors and steppers the same width.
    assert {field.width() for field in fields} == {180}
    assert max(field.height() for field in fields) - min(field.height() for field in fields) <= 1
    for edge in zip(*boxes):
        assert max(edge) - min(edge) <= 1, boxes
    assert {field.font().pixelSize() for field in fields[:3]} == {
        settings.ui_scale_value.font().pixelSize(),
        settings.translation_font_control.editor.font().pixelSize(),
    }


def test_font_arrows_and_keyboard_are_bounded_and_refresh_an_open_result(window, app):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(0)
    app.processEvents()
    control = settings.translation_font_control
    dialog = main.show_translation_dialog(window, 'Result', source_text='Original', auto_copy=False)
    try:
        control.increase.click()
        app.processEvents()
        assert control.value() == 'large'
        assert window.config['translation_result_font_size'] == 'large'
        assert 'font-size:20px' in dialog.styleSheet()
        control.increase.click()
        assert control.value() == 'xlarge'
        assert not control.increase.isEnabled()
        assert control.decrease.isEnabled()
        control.stepBy(1)
        assert control.value() == 'xlarge'
        QTest.keyClick(control.decrease, QtCore.Qt.Key_Left)
        assert control.value() == 'large'
        QTest.keyClick(control.decrease, QtCore.Qt.Key_Home)
        assert control.value() == 'xsmall'
        assert not control.decrease.isEnabled()
        assert control.increase.isEnabled()
        control.stepBy(-1)
        assert control.value() == 'xsmall'
        QTest.keyClick(control.increase, QtCore.Qt.Key_Right)
        assert control.value() == 'small'
        app.processEvents()
        assert 'font-size:13px' in dialog.styleSheet()
        assert settings.translation_font_preview.font().pixelSize() == 13
    finally:
        dialog.close()


def test_font_choice_center_does_not_leave_a_text_selection(window, app):
    window.show_settings()
    window.settings_window._set_settings_page(0)
    app.processEvents()
    control = window.settings_window.translation_font_control
    controller = window._ui_scale_controller
    before = control.value()
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton,
                     pos=controller.map_widget_to_view(control.editor))
    app.processEvents()
    assert control.value() == before
    assert not control.editor.selectedText()


@pytest.mark.parametrize('direction,endpoint', [('decrease', 'xsmall'), ('increase', 'xlarge')])
def test_mouse_clicking_to_font_limit_does_not_transfer_keyboard_highlight(window, app, direction, endpoint):
    window.show_settings()
    window.settings_window._set_settings_page(0)
    app.processEvents()
    control = window.settings_window.translation_font_control
    controller = window._ui_scale_controller
    button = getattr(control, direction)
    other = control.increase if direction == 'decrease' else control.decrease
    while button.isEnabled():
        QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton,
                         pos=controller.map_widget_to_view(button))
        app.processEvents()
    QTest.mouseMove(controller.view.viewport(), QtCore.QPoint(2, 2))
    app.processEvents()
    assert control.value() == endpoint
    assert not other.property('keyboardFocus')
    assert not button.property('pointerHover')
    assert not button.isDown()


def test_keyboard_steps_after_a_mouse_click_keep_real_keyboard_focus(window, app):
    window.show_settings()
    window.settings_window._set_settings_page(0)
    app.processEvents()
    control = window.settings_window.translation_font_control
    controller = window._ui_scale_controller
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton,
                     pos=controller.map_widget_to_view(control.decrease))
    app.processEvents()
    assert control.value() == 'small'
    assert not control.decrease.property('keyboardFocus')
    QTest.keyClick(control.decrease, QtCore.Qt.Key_Home)
    app.processEvents()
    assert control.value() == 'xsmall'
    assert control.increase.hasFocus()
    assert control.increase.property('keyboardFocus')
