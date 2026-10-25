"""The OCR toolbar must contain painted captions and language fields at DPI."""
import pytest
from PyQt5 import QtCore, QtWidgets
from test_capture_region_memory import capture
from test_desktop_ux import app
from capture_regions import LANGUAGES


@pytest.mark.parametrize('locale', LANGUAGES)
@pytest.mark.parametrize('dark', [True, False])
@pytest.mark.parametrize('dpi', [96, 144, 192])
@pytest.mark.parametrize('mode', ['copy', 'translate'])
@pytest.mark.parametrize('width', [480, 1200])
def test_unselected_modes_have_a_compact_language_only_toolbar(capture, app, monkeypatch, locale, dark, dpi, mode, width):
    from PyQt5 import QtGui
    config, _, _, create = capture
    config.update(interface_language=locale, theme='Темная' if dark else 'Светлая',
                  capture_area_memory_modes=[], remember_translate_area=True, remember_copy_area=True)
    desktop = QtCore.QRect(-width, -100, width, 800)
    monkeypatch.setattr(QtGui.QScreen, 'geometry', lambda self: QtCore.QRect(desktop))
    monkeypatch.setattr(QtGui.QScreen, 'availableGeometry', lambda self: QtCore.QRect(desktop))
    monkeypatch.setattr(QtGui.QScreen, 'logicalDotsPerInch', lambda self: dpi)
    value = create(mode)
    assert not value.remember_area_checkbox.isVisible()
    assert not value.memory_panel.isVisible()
    assert not value.repeat_area_button.isVisible()
    assert not value.capture_separator.isVisible()
    assert value._preview_rect is None
    toolbar = value.capture_toolbar
    rectangles = []
    for control in (value.lang_combo, value.translate_arrow_label, value.target_lang_combo, value.capture_close_button):
        if control is None:
            continue
        rect = QtCore.QRect(control.mapTo(toolbar, QtCore.QPoint()), control.size())
        assert toolbar.contentsRect().contains(rect), (locale, dark, dpi, mode, rect, toolbar.rect())
        assert not any(previous.intersects(rect) for previous in rectangles)
        rectangles.append(rect)
    assert len({rect.center().y() for rect in rectangles}) <= 2


@pytest.mark.parametrize('locale', LANGUAGES)
@pytest.mark.parametrize('dark', [True, False])
@pytest.mark.parametrize('dpi', [96, 144, 192])
@pytest.mark.parametrize('mode', ['copy', 'translate'])
@pytest.mark.parametrize('width', [480, 640, 1200])
@pytest.mark.parametrize('preview', [False, True])
def test_toolbar_contains_caption_flags_and_language_fields(capture, app, monkeypatch, locale, dark, dpi, mode, width, preview):
    config, _, _, create = capture
    config.update(interface_language=locale, theme='Темная' if dark else 'Светлая')
    from PyQt5 import QtGui
    desktop = QtCore.QRect(-width, -100, width, 800)
    monkeypatch.setattr(QtGui.QScreen, 'geometry', lambda self: QtCore.QRect(desktop))
    monkeypatch.setattr(QtGui.QScreen, 'availableGeometry', lambda self: QtCore.QRect(desktop))
    monkeypatch.setattr(QtGui.QScreen, 'logicalDotsPerInch', lambda self: dpi)
    value = create(mode)
    value._preview_rect = QtCore.QRect(100, 300, 300, 100) if preview else None
    value._update_memory_actions()
    value.update_combo_position()
    app.processEvents()
    toolbar = value.capture_toolbar
    assert value.rect().contains(toolbar.geometry()), (locale, dark, dpi, mode, width)
    rectangles = []
    for control in (value.lang_combo, value.target_lang_combo, value.translate_arrow_label,
                    value.remember_area_checkbox, value.repeat_area_button, value.capture_close_button):
        if control is None or control.isHidden():
            continue
        rect = QtCore.QRect(control.mapTo(toolbar, QtCore.QPoint()), control.size())
        assert toolbar.contentsRect().contains(rect), (locale, dark, dpi, control, rect, toolbar.rect())
        assert not any(previous.intersects(rect) for previous in rectangles)
        rectangles.append(rect)
        parent = control.parentWidget()
        local = QtCore.QRect(control.mapTo(parent, QtCore.QPoint()), control.size())
        assert parent.contentsRect().contains(local), (locale, dark, dpi, control, local, parent.rect())
    box = value.remember_area_checkbox
    option = QtWidgets.QStyleOptionButton()
    box.initStyleOption(option)
    contents = box.style().subElementRect(QtWidgets.QStyle.SE_CheckBoxContents, option, box)
    ink = box.fontMetrics().boundingRect(contents, QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter, box.text())
    assert contents.contains(ink), (locale, dark, dpi, contents, ink, box.width(), box.sizeHint())
    for combo in (value.lang_combo, value.target_lang_combo):
        if combo is None:
            continue
        option = QtWidgets.QStyleOptionComboBox()
        combo.initStyleOption(option)
        field = combo.style().subControlRect(QtWidgets.QStyle.CC_ComboBox, option,
                                            QtWidgets.QStyle.SC_ComboBoxEditField, combo)
        required = combo.fontMetrics().horizontalAdvance(combo.currentText()) + combo.iconSize().width() + 6
        assert field.width() >= required, (locale, dark, dpi, field, required, combo.geometry())
