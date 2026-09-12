import os
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import dynamic_workspace as workspace
import game_mode
import ocr
from dynamic_templates import TemplateStore, decode_rect, encode_rect, output_style


@pytest.fixture(scope='module')
def app():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from qt_layout_test_support import ensure_layout_fonts
    ensure_layout_fonts(app)
    return app


@pytest.fixture
def isolated(app, monkeypatch, tmp_path):
    config = {'theme': 'Темная', 'interface_language': 'ru', 'translator_engine': 'Google', 'ocr_engine': 'Windows',
              'game_translate_source_language': 'en', 'game_translate_target_language': 'ru', 'game_show_original_text': True,
              'history': False, 'game_pause_when_inactive': False}
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: config)
    monkeypatch.setattr(ocr, 'installed_ocr_language_codes', lambda **kwargs: ['en', 'ru'])
    monkeypatch.setattr(ocr, '_translation_targets_for_source', lambda source, config: ['ru'] if source == 'en' else ['en'])
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', mock.Mock())
    monkeypatch.setattr(game_mode, '_exclude_from_windows_capture', lambda widget: True)
    monkeypatch.setattr(game_mode.GameTranslationOverlay, '_start_scanning', lambda self: None)
    store = TemplateStore(tmp_path/'templates.json')
    monkeypatch.setattr(workspace, 'TemplateStore', lambda: store)
    yield config, store
    game_mode.stop_game_mode()


def select(selector, rect):
    QTest.mousePress(selector, QtCore.Qt.LeftButton, pos=rect.topLeft())
    QTest.mouseRelease(selector, QtCore.Qt.LeftButton, pos=rect.bottomRight())


def test_source_requires_a_separate_output_and_enter_routes_both_bounds(isolated):
    selector = workspace.PairedRegionSelector()
    try:
        source, output = QtCore.QRect(50, 250, 220, 70), QtCore.QRect(380, 370, 260, 90)
        with mock.patch.object(game_mode, '_begin_game_session') as start:
            select(selector, source)
            assert selector._regions == [source]
            assert selector._outputs == [None]
            assert not selector.start_button.isEnabled()
            QTest.keyClick(selector, QtCore.Qt.Key_Return)
            start.assert_not_called()
            select(selector, output)
            assert selector.start_button.isEnabled()
            origin = selector.geometry().topLeft()
            QTest.keyClick(selector, QtCore.Qt.Key_Return)
            assert start.call_args.args[:3] == ([source.translated(origin)], 'en', 'ru')
            assert start.call_args.kwargs['output_regions'] == [output.translated(origin)]
    finally:
        selector.close()


def test_output_can_overlap_source_and_move_independently_then_delete_pair(isolated):
    selector = workspace.PairedRegionSelector()
    try:
        source = QtCore.QRect(100, 260, 280, 100)
        output = QtCore.QRect(150, 280, 180, 60)
        select(selector, source)
        select(selector, output)
        assert selector._outputs == [output]
        QTest.mousePress(selector, QtCore.Qt.LeftButton, pos=output.center())
        QTest.mouseRelease(selector, QtCore.Qt.LeftButton, pos=output.center()+QtCore.QPoint(35, 20))
        assert selector._outputs == [output.translated(35, 20)]
        assert selector._regions == [source]
        QTest.keyClick(selector, QtCore.Qt.Key_Delete)
        assert not selector._regions and not selector._outputs and not selector._styles
        assert not selector.start_button.isEnabled()
    finally:
        selector.close()


def test_templates_survive_new_selector_and_keep_both_areas_languages_and_style(isolated):
    _, store = isolated
    selector = workspace.PairedRegionSelector(store=store)
    source, output = QtCore.QRect(60, 240, 240, 70), QtCore.QRect(390, 380, 220, 80)
    try:
        select(selector, source)
        select(selector, output)
        selector._styles[0] = output_style({'font_size': 27, 'opacity': 35, 'locked': False})
        selector.template_combo.setEditText('Subtitles')
        selector.save_template_button.click()
        assert store.path.exists()
    finally:
        selector.close()
    restored = workspace.PairedRegionSelector(store=TemplateStore(store.path))
    try:
        restored._load_template(0)
        assert restored._regions == [source]
        assert restored._outputs == [output]
        assert restored._styles == [{'font_size': 27, 'opacity': 35, 'locked': False}]
        assert restored.source_combo.currentData() == 'en'
        assert restored.target_combo.currentData() == 'ru'
        restored._delete_template()
        assert store.load() == []
    finally:
        restored.close()


def screen(name, rect):
    return SimpleNamespace(name=lambda: name, geometry=lambda: QtCore.QRect(*rect))


def test_template_coordinates_survive_negative_origin_resolution_change_and_missing_monitor():
    original = screen('left', (-1920, 0, 1920, 1080))
    rect = QtCore.QRect(-1728, 108, 960, 216)
    value = encode_rect(rect, [original])
    assert decode_rect(value, [screen('left', (-1280, 0, 1280, 720))]) == QtCore.QRect(-1152, 72, 640, 144)
    moved = decode_rect(value, [screen('replacement', (0, 0, 800, 600))])
    assert QtCore.QRect(0, 0, 800, 600).contains(moved)


def test_malformed_template_file_is_not_overwritten_by_save(tmp_path):
    store = TemplateStore(tmp_path/'templates.json')
    original = '{broken'
    store.path.write_text(original, encoding='utf-8')
    area = {'screen': 'A', 'rect': [0, 0, .3, .2]}
    with pytest.raises(ValueError):
        store.save({'name': 'A', 'source_language': 'en', 'target_language': 'ru', 'pairs': [{'source': area, 'output': area}]})
    assert store.path.read_text(encoding='utf-8') == original


def test_output_contains_translation_only_and_reads_source_not_destination(isolated):
    source, output = QtCore.QRect(30, 260, 220, 70), QtCore.QRect(410, 370, 260, 90)
    overlay = workspace.PairedTranslationOverlay(source, 'en', 'ru', output_region=output)
    try:
        assert overlay.geometry() == output
        assert overlay.region == source
        assert overlay.translation_label.text() == ''
        for status in ('waiting', 'scanning', 'translating', 'capture_error'):
            overlay._set_status(status)
            assert overlay.card.isHidden()
            assert overlay.status_label.isHidden()
        with mock.patch.object(ocr, 'grab_screen_pixmap', return_value=QtGui.QPixmap(220, 70)) as capture:
            overlay._grab_region()
            screen_origin = QtWidgets.QApplication.primaryScreen().geometry().topLeft()
            assert capture.call_args.args[1:] == source.translated(-screen_origin).getRect()
        overlay._apply_translation(0, 'Source caption', 'Only <b>translated</b> text', '')
        assert overlay.translation_label.text() == 'Only <b>translated</b> text'
        assert overlay.translation_label.textFormat() == QtCore.Qt.PlainText
        assert overlay.original_label.isHidden() and overlay.title_label.isHidden() and overlay.pair_label.isHidden()
        assert overlay.geometry() == output
        overlay.controls.font_size.setValue(30)
        overlay.controls.opacity.setValue(0)
        assert overlay.output_style['font_size'] == 30 and overlay.output_style['opacity'] == 0
        assert overlay.region == source
    finally:
        overlay.close()


def test_micro_controls_resize_unlock_and_save_current_layout(isolated):
    _, store = isolated
    overlay = workspace.PairedTranslationOverlay(QtCore.QRect(20, 250, 200, 60), 'en', 'ru', output_region=QtCore.QRect(350, 350, 250, 90))
    try:
        controls = overlay.controls
        assert controls.width() == 30 and controls.panel.isHidden()
        controls.gear.click()
        assert not controls.panel.isHidden() and controls.height() > 100
        assert not controls.move_button.isEnabled()
        controls.locked.setChecked(False)
        assert controls.move_button.isEnabled()
        before = QtCore.QRect(overlay.output_rect)
        for button, delta in ((controls.move_button, QtCore.QPoint(20, 10)), (controls.resize_button, QtCore.QPoint(20, 10))):
            destination = button.mapToGlobal(button.rect().center())+delta
            QTest.mousePress(button, QtCore.Qt.LeftButton, pos=button.rect().center())
            QTest.mouseRelease(button, QtCore.Qt.LeftButton, pos=button.mapFromGlobal(destination))
        assert overlay.output_rect == QtCore.QRect(before.x()+20, before.y()+10, before.width()+20, before.height()+10)
        controls.font_size.setValue(24)
        controls.opacity.setValue(42)
        controls.template_name.setText('Game')
        controls.save_button.click()
        value = store.load()[0]
        assert value['pairs'][0]['style'] == {'font_size': 24, 'opacity': 42, 'locked': False}
        assert decode_rect(value['pairs'][0]['output'], QtWidgets.QApplication.screens()) == overlay.output_rect
        controls.gear.click()
        assert controls.width() == 30 and controls.height() < 40
    finally:
        overlay.close()


def test_public_entry_uses_paired_selector(isolated):
    selector = game_mode._show_game_selector()
    assert isinstance(selector, workspace.PairedRegionSelector)
    assert selector.template_combo.isVisible()
    assert selector.save_template_button.isVisible()
    assert selector.delete_template_button.isVisible()
    selector.close()
