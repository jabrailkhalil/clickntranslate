"""Last-area reuse never starts capture until confirmed or changes languages."""
import copy
from types import SimpleNamespace

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import ocr
from capture_regions import encode_area, resolve_area, memory_keys, screen_identity, LANGUAGES
from test_desktop_ux import app


def screen(name='left', bounds=(-1600, -100, 1600, 900), dpi=96):
    return SimpleNamespace(name=lambda: name, geometry=lambda: QtCore.QRect(*bounds), logicalDotsPerInch=lambda: dpi)


def test_geometry_is_screen_relative_and_never_falls_back_or_scales_with_ui():
    original = screen()
    rect = QtCore.QRect(-1500, 100, 500, 180)
    saved = encode_area(rect, original)
    assert saved['rect'] == [100, 200, 500, 180]
    assert resolve_area(saved, original) == rect
    assert resolve_area(saved, screen(bounds=(500, 0, 1600, 900))) == QtCore.QRect(600, 200, 500, 180)
    assert resolve_area(saved, screen(name='other')) is None
    assert resolve_area(saved, screen(dpi=144)) is None
    assert resolve_area(saved, screen(bounds=(-1600, 0, 1200, 900))) is None
    assert encode_area(QtCore.QRect(-100, 0, 600, 300), original) is None


@pytest.mark.parametrize('data', [None, {}, [], {'version': 2}, {'version': 1, 'screen': {}, 'rect': [0, 0, 10, 20]}])
def test_invalid_geometry_is_ignored_without_rewriting_it(data):
    before = copy.deepcopy(data)
    assert resolve_area(data, screen()) is None
    assert data == before


def test_area_memory_settings_round_trip_without_screen_access():
    import main
    from settings_window import settings_export_payload, validated_import_settings
    area = encode_area(QtCore.QRect(-1500, 100, 500, 180), screen())
    settings = dict(remember_copy_area=True, remember_translate_area=False,
                    last_copy_area=area, last_translate_area=None,
                    game_remember_template=True, game_last_template='Dialogue')
    restored = validated_import_settings(settings_export_payload(settings), main.DEFAULT_CONFIG)
    assert restored == settings
    restored['last_copy_area']['rect'][0] = 777
    assert area['rect'][0] == 100


@pytest.mark.parametrize('changes', [
    {'rect': [0, 0, True, 20]}, {'rect': [-1, 0, 20, 20]},
    {'rect': [0, 0, 99999, 20]}, {'screen': {'name': 'left', 'size': [1600, 900], 'dpi': float('nan')}},
])
def test_malformed_imported_area_is_ignored(changes):
    import main
    from settings_window import settings_export_payload, validated_import_settings
    area = encode_area(QtCore.QRect(-1500, 100, 500, 180), screen())
    area.update(changes)
    restored = validated_import_settings(settings_export_payload(dict(theme='Темная', last_copy_area=area)), main.DEFAULT_CONFIG)
    assert restored == {'theme': 'Темная'}


@pytest.fixture
def capture(app, monkeypatch):
    desktop = QtCore.QRect(-1200, 0, 1200, 800)
    monkeypatch.setattr(QtGui.QScreen, 'geometry', lambda self: QtCore.QRect(desktop))
    monkeypatch.setattr(QtGui.QScreen, 'availableGeometry', lambda self: QtCore.QRect(desktop))
    config = {'theme': 'Темная', 'interface_language': 'ru', 'ocr_engine': 'Windows',
              'translator_engine': 'Google', 'last_ocr_language': 'en',
              'ocr_translate_source_language': 'en', 'ocr_translate_target_language': 'ru'}
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: config)
    monkeypatch.setattr(ocr, 'installed_ocr_language_codes', lambda **kw: ['en', 'ru'])
    monkeypatch.setattr(ocr, '_translation_targets_for_source', lambda source, config: ['ru'] if source == 'en' else ['en'])
    monkeypatch.setattr(ocr, '_safe_prepare_overlay', lambda *args: None)
    monkeypatch.setattr(ocr.ScreenCaptureOverlay, '_capture_frozen_background', lambda *args: None)
    monkeypatch.setattr(ocr.ScreenCaptureOverlay, '_force_topmost', lambda *args: None)
    monkeypatch.setattr(ocr.ScreenCaptureOverlay, '_flush_selection_paint_before_capture', lambda *args: None)
    writes, captures, overlays = [], [], []
    def write(updates):
        config.update(copy.deepcopy(updates))
        writes.append(copy.deepcopy(updates))
        return True
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', write)
    monkeypatch.setattr(ocr.ScreenCaptureOverlay, 'capture_and_copy', lambda self, rect: captures.append(QtCore.QRect(rect)))
    def create(mode='translate'):
        value = ocr.ScreenCaptureOverlay(mode, defer_show=True)
        overlays.append(value)
        value.show_overlay()
        app.processEvents()
        return value
    yield config, writes, captures, create
    for overlay in overlays:
        overlay.close()
        overlay.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


@pytest.mark.parametrize('mode', ['copy', 'translate'])
def test_capture_restores_only_when_enabled_and_repeat_is_explicit(capture, mode):
    config, writes, captures, create = capture
    first = create(mode)
    assert not first.remember_area_checkbox.isChecked()
    first.remember_area_checkbox.setChecked(True)
    local = QtCore.QRect(100, 300, 260, 120)
    QTest.mousePress(first, QtCore.Qt.LeftButton, pos=local.topLeft())
    QTest.mouseRelease(first, QtCore.Qt.LeftButton, pos=local.bottomRight())
    assert captures == [local]
    enabled_key, area_key = memory_keys(mode)
    assert config[enabled_key] is True and config[area_key]['rect'] == list(local.getRect())
    first.close()
    restored = create(mode)
    assert restored._preview_rect == local
    assert restored.repeat_area_button.isVisible()
    assert captures == [local]
    assert config['ocr_translate_target_language'] == 'ru'
    restored.repeat_area_button.click()
    assert captures == [local, local]
    assert not restored.memory_panel.isVisible()
    QTest.keyClick(restored, QtCore.Qt.Key_Return)
    assert len(captures) == 2  # A queued Enter cannot start a second OCR job.
    other = create('copy' if mode == 'translate' else 'translate')
    assert other._preview_rect is None
    assert not other.remember_area_checkbox.isChecked()


def test_cancel_and_frame_edits_do_not_overwrite_the_accepted_area(capture):
    config, writes, captures, create = capture
    initial = create()
    initial.remember_area_checkbox.setChecked(True)
    local = QtCore.QRect(100, 300, 260, 120)
    initial._accept_capture_region(local)
    initial.close()
    before = copy.deepcopy(config['last_translate_area'])
    value = create()
    QTest.mousePress(value, QtCore.Qt.LeftButton, pos=local.center())
    QTest.mouseRelease(value, QtCore.Qt.LeftButton, pos=local.center()+QtCore.QPoint(30, 20))
    assert value._preview_rect == local.translated(30, 20)
    assert config['last_translate_area'] == before
    QTest.keyClick(value, QtCore.Qt.Key_Escape)
    assert config['last_translate_area'] == before and len(captures) == 1
    value = create()
    QTest.mousePress(value, QtCore.Qt.LeftButton, pos=local.bottomRight())
    QTest.mouseRelease(value, QtCore.Qt.LeftButton, pos=local.bottomRight()+QtCore.QPoint(40, 20))
    assert value._preview_rect.size() == QtCore.QSize(300, 140)
    QTest.keyClick(value, QtCore.Qt.Key_Return)
    assert captures[-1].size() == QtCore.QSize(300, 140)


def test_new_selection_replaces_saved_area_and_unchecking_removes_preview(capture):
    config, _, captures, create = capture
    first = create()
    first.remember_area_checkbox.setChecked(True)
    first._accept_capture_region(QtCore.QRect(50, 300, 200, 80))
    first.close()
    value = create()
    rect = QtCore.QRect(500, 400, 300, 100)
    QTest.mousePress(value, QtCore.Qt.LeftButton, pos=rect.topLeft())
    QTest.mouseRelease(value, QtCore.Qt.LeftButton, pos=rect.bottomRight())
    assert captures[-1] == rect and config['last_translate_area']['rect'] == list(rect.getRect())
    value.close()
    value = create()
    value.remember_area_checkbox.setChecked(False)
    assert value._preview_rect is None and not value.repeat_area_button.isVisible()
    assert config['last_translate_area'] is None


def test_unavailable_or_changed_monitor_never_captures(capture, monkeypatch):
    config, _, captures, create = capture
    config['remember_translate_area'] = True
    config['last_translate_area'] = encode_area(QtCore.QRect(-1500, 100, 400, 100), screen())
    value = create()
    assert value._preview_rect is None and value.memory_hint.isVisible()
    QTest.keyClick(value, QtCore.Qt.Key_Return)
    assert not captures
    value._preview_rect = QtCore.QRect(100, 300, 300, 100)
    value._preview_screen_identity = screen_identity(value._active_screen)
    value._update_memory_actions()
    monkeypatch.setattr(QtGui.QScreen, 'logicalDotsPerInch', lambda self: 192.)
    value.repeat_area_button.click()
    assert not captures and value._preview_rect is None


def test_enter_in_a_language_popup_does_not_repeat(capture):
    config, _, captures, create = capture
    value = create()
    value._preview_rect = QtCore.QRect(100, 300, 300, 100)
    value._preview_screen_identity = screen_identity(value._active_screen)
    value.lang_combo.showPopup()
    QTest.keyClick(value, QtCore.Qt.Key_Return)
    assert not captures
    value.lang_combo.hidePopup()


def test_monitor_repositioned_during_preview_never_captures(capture, monkeypatch):
    _, _, captures, create = capture
    value = create()
    value._preview_rect = QtCore.QRect(100, 300, 300, 100)
    value._preview_screen_identity = screen_identity(value._active_screen)
    monkeypatch.setattr(QtGui.QScreen, 'geometry', lambda self: QtCore.QRect(0, 0, 1200, 800))
    value._repeat_area()
    assert not captures and value._preview_rect is None


def test_failed_area_save_warns_only_after_capture_overlay_closes(capture, monkeypatch, app):
    import capture_regions
    _, _, captures, create = capture
    warnings = []
    monkeypatch.setattr(capture_regions, 'show_save_warning', warnings.append)
    value = create()
    value.remember_area_checkbox.setChecked(True)
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', lambda values: False)
    area = QtCore.QRect(100, 300, 300, 100)
    value._accept_capture_region(area)
    assert captures == [area] and not warnings
    value.close()
    app.processEvents()
    assert warnings == ['ru']


@pytest.mark.parametrize('locale', LANGUAGES)
@pytest.mark.parametrize('dark', [True, False])
def test_capture_memory_controls_fit_and_have_hints_in_every_locale(capture, locale, dark):
    config, _, _, create = capture
    config.update(interface_language=locale, theme='Темная' if dark else 'Светлая')
    value = create()
    value._preview_rect = QtCore.QRect(100, 300, 300, 100)
    value._update_memory_actions()
    value.update_combo_position()
    assert value.rect().contains(value.capture_toolbar.geometry())
    assert value.capture_toolbar.rect().contains(value.memory_panel.geometry())
    assert value.rect().contains(value.memory_hint.geometry())
    box = value.remember_area_checkbox
    assert box.width() >= box.sizeHint().width()
    assert box.toolTip() and value.repeat_area_button.toolTip()


@pytest.mark.parametrize('locale', LANGUAGES)
@pytest.mark.parametrize('dpi', [96, 144, 192])
def test_unified_toolbar_wraps_without_clipping_on_narrow_secondary_monitor(capture, app, monkeypatch, locale, dpi):
    config, _, _, create = capture
    config['interface_language'] = locale
    desktop = QtCore.QRect(-700, -100, 640, 720)
    monkeypatch.setattr(QtGui.QScreen, 'geometry', lambda self: QtCore.QRect(desktop))
    monkeypatch.setattr(QtGui.QScreen, 'availableGeometry', lambda self: QtCore.QRect(desktop))
    monkeypatch.setattr(QtGui.QScreen, 'logicalDotsPerInch', lambda self: dpi)
    value = create()
    value._preview_rect = QtCore.QRect(100, 300, 300, 100)
    value._update_memory_actions()
    value.update_combo_position()
    app.processEvents()
    assert value.rect().contains(value.capture_toolbar.geometry())
    controls = (value.lang_combo, value.translate_arrow_label, value.target_lang_combo,
                value.remember_area_checkbox, value.repeat_area_button, value.capture_close_button)
    rectangles = []
    for control in controls:
        bounds = QtCore.QRect(control.mapTo(value.capture_toolbar, QtCore.QPoint()), control.size())
        assert value.capture_toolbar.rect().contains(bounds)
        assert all(not previous.intersects(bounds) for previous in rectangles)
        rectangles.append(bounds)
    assert value.lang_combo.height() == value.remember_area_checkbox.height()
    assert value.capture_close_button.toolTip().endswith('Esc')


def test_clicking_blank_toolbar_does_not_select_screen(capture, app):
    _, _, captures, create = capture
    value = create()
    QTest.mouseClick(value.capture_toolbar, QtCore.Qt.LeftButton, pos=QtCore.QPoint(3, 3))
    assert value.start_point is None and not captures


def test_corrupt_config_is_not_replaced_when_saving_an_area(tmp_path, monkeypatch):
    path = tmp_path/'config.json'
    path.write_text('{broken', encoding='utf-8')
    monkeypatch.setattr(ocr, 'get_data_file', lambda name: str(path))
    assert not ocr._write_ocr_config_updates({'remember_copy_area': True})
    assert path.read_text(encoding='utf-8') == '{broken'
