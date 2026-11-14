"""Creating a reusable area layout must never start recognition or translation."""
import copy
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import dynamic_templates
import dynamic_workspace as workspace
import game_mode
import mode_coordinator
import ocr
from styled_dialogs import StyledMessageBox
from test_dynamic_workspace import app, isolated, select
from test_desktop_ux import window


@pytest.fixture(autouse=True)
def modes():
    mode_coordinator._reset_for_tests()
    yield
    game_mode.stop_game_mode()
    mode_coordinator._reset_for_tests()


def areas(selector):
    select(selector, QtCore.QRect(50, 300, 220, 70))
    if selector._manual_output:
        select(selector, QtCore.QRect(380, 400, 250, 90))


def stored(store, name='Dialogue'):
    return store.save(workspace.make_template(name, [QtCore.QRect(50, 300, 220, 70)],
        [QtCore.QRect(380, 400, 250, 90)], [{}], 'en', 'ru'))


def test_builder_starts_empty_names_and_saves_without_starting_translation(isolated):
    config, store = isolated
    stored(store)
    config.update(game_remember_template=True, game_last_template='Dialogue')
    before = copy.deepcopy(config)
    selector = workspace.PairedRegionSelector(template_builder=True)
    captured = []
    selector.template_saved.connect(captured.append)
    try:
        assert selector._regions == []
        assert not selector.template_combo.isVisible()
        assert not selector.start_button.isEnabled()
        assert selector.template_name.isVisible()
        areas(selector)
        assert not selector.start_button.isEnabled()
        selector.template_name.setText(' New dialogue ')
        assert selector.start_button.isEnabled()
        assert selector.start_button.text() == dynamic_templates.text('ru', 'save')
        with mock.patch.object(game_mode, '_begin_game_session') as start:
            selector.start_button.click()
            start.assert_not_called()
        assert captured[0]['name'] == 'New dialogue'
        assert captured[0]['source_language'] == 'en'
        assert len(captured[0]['pairs']) == 1
        assert store.load()[-1] == captured[0]
        assert not selector.isVisible()
        assert config == before
    finally:
        selector.close()


def test_manual_builder_requires_a_complete_pair(isolated):
    isolated[0]['game_manual_output'] = True
    selector = workspace.PairedRegionSelector(template_builder=True)
    try:
        selector.template_name.setText('Subtitles')
        select(selector, QtCore.QRect(50, 300, 220, 70))
        assert selector._outputs == [None]
        assert not selector.start_button.isEnabled()
        QTest.keyClick(selector, QtCore.Qt.Key_Return)
        assert not isolated[1].load()
        select(selector, QtCore.QRect(380, 400, 250, 90))
        assert selector.start_button.isEnabled()
    finally:
        selector.close()


@pytest.mark.parametrize('answer', [StyledMessageBox.No, StyledMessageBox.Yes])
def test_existing_name_needs_explicit_replace_confirmation(isolated, answer):
    config, store = isolated
    previous = stored(store, 'Dialogue')
    selector = workspace.PairedRegionSelector(template_builder=True)
    try:
        areas(selector)
        selector.template_name.setText('dialogue')
        with mock.patch.object(StyledMessageBox, 'question', return_value=answer) as question:
            selector.start_button.click()
            assert question.call_args.args[-1] == StyledMessageBox.No
            assert 'Dialogue' in question.call_args.args[2]
        if answer == StyledMessageBox.No:
            assert store.load() == [previous]
            assert selector.isVisible()
        else:
            assert len(store.load()) == 1
            assert store.load()[0]['name'] == 'dialogue'
            assert not selector.isVisible()
    finally:
        selector.close()


def test_failed_save_keeps_the_areas_and_form_open(isolated, monkeypatch):
    _, store = isolated
    selector = workspace.PairedRegionSelector(template_builder=True)
    try:
        areas(selector)
        selector.template_name.setText('Dialogue')
        monkeypatch.setattr(store, 'save', mock.Mock(side_effect=OSError('read only')))
        selector.start_button.click()
        assert selector.selection_note.text() == dynamic_templates.text('ru', 'save_error')
        assert selector.isVisible() and selector._complete()
        assert selector.template_name.text() == 'Dialogue'
        assert not store.load()
    finally:
        selector.close()


def test_enter_does_not_repeat_a_declined_overwrite_question(isolated):
    _, store = isolated
    previous = stored(store)
    selector = workspace.PairedRegionSelector(template_builder=True)
    try:
        areas(selector)
        selector.template_name.setText('Dialogue')
        with mock.patch.object(StyledMessageBox, 'question', return_value=StyledMessageBox.No) as question:
            QTest.keyClick(selector.template_name, QtCore.Qt.Key_Return)
            question.assert_called_once()
        assert store.load() == [previous]
        assert selector.isVisible()
    finally:
        selector.close()


def test_cancel_does_not_change_language_or_template_preferences(isolated):
    config, store = isolated
    before = copy.deepcopy(config)
    selector = workspace.PairedRegionSelector(template_builder=True)
    selector.source_combo.setCurrentIndex(selector.source_combo.findData('ru'))
    areas(selector)
    selector.template_name.setText('Draft')
    QTest.keyClick(selector, QtCore.Qt.Key_Escape)
    assert config == before
    assert not store.load()
    ocr._write_ocr_config_updates.assert_not_called()


def test_builder_keyboard_area_editing_and_name_enter_save(isolated):
    selector = workspace.PairedRegionSelector(template_builder=True)
    try:
        QTest.keyClick(selector, QtCore.Qt.Key_N)
        initial = QtCore.QRect(selector._regions[0])
        QTest.keyClick(selector, QtCore.Qt.Key_Right, QtCore.Qt.ControlModifier)
        assert selector._regions[0].x() == initial.x() + 10
        selector.template_name.setText('Keyboard layout')
        with mock.patch.object(game_mode, '_begin_game_session') as start:
            QTest.keyClick(selector.template_name, QtCore.Qt.Key_Return)
            start.assert_not_called()
        assert isolated[1].load()[0]['name'] == 'Keyboard layout'
    finally:
        selector.close()


def test_missing_recognition_languages_cannot_save_a_fake_pair(isolated, monkeypatch):
    monkeypatch.setattr(ocr, 'installed_ocr_language_codes', lambda **_: [])
    selector = workspace.PairedRegionSelector(template_builder=True)
    try:
        areas(selector)
        selector.template_name.setText('Unavailable')
        assert not selector.start_button.isEnabled()
        selector._save_template()
        assert not isolated[1].load()
    finally:
        selector.close()


def test_mismatched_area_lists_do_not_silently_save_a_partial_template(isolated):
    with pytest.raises(ValueError):
        workspace.make_template('Broken', [QtCore.QRect(50, 300, 220, 70)]*2,
                                [QtCore.QRect(50, 300, 220, 70)], [{}]*2, 'en', 'ru')


class Owner(QtWidgets.QWidget):
    def _ensure_capture_permission(self):
        return getattr(self, 'allowed', True)


def test_builder_owns_desktop_mode_and_returns_to_settings_after_cancel(isolated, app):
    owner = Owner()
    owner.show()
    app.processEvents()
    try:
        selector = workspace.open_template_builder(owner)
        app.processEvents()
        assert mode_coordinator.active_mode() == 'game'
        assert not owner.isVisible()
        assert selector.isVisible() and selector.windowHandle().isExposed()
        assert selector.toolbar.isVisible()
        assert workspace.open_template_builder(owner) is selector
        QTest.keyClick(selector, QtCore.Qt.Key_Escape)
        app.processEvents()
        assert owner.isVisible()
        assert mode_coordinator.active_mode() is None
        assert owner._dynamic_template_builder is None
    finally:
        owner.close()
        owner.deleteLater()


def test_real_application_owner_leaves_a_visible_exposed_constructor_and_returns_to_dynamic(window, isolated, app):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(2)
    for _ in range(4): app.processEvents()
    selector = workspace.open_template_builder(window)
    try:
        for _ in range(4): app.processEvents()
        assert not window.isVisible()
        assert selector is game_mode._game_selector_ref
        assert selector in app.topLevelWidgets()
        assert selector.isWindow() and selector.isVisible() and not selector.isHidden()
        assert selector.windowHandle().isVisible() and selector.windowHandle().isExposed()
        assert selector.toolbar.isVisibleTo(selector)
        assert selector.windowFlags() & QtCore.Qt.Tool
        selector.close()
        for _ in range(4): app.processEvents()
        assert window.isVisible()
        assert window.settings_window._settings_page_index == 2
        assert mode_coordinator.active_mode() is None
    finally:
        if window._dynamic_template_builder is not None:
            window._dynamic_template_builder.close()


def test_replacement_capture_does_not_raise_main_window_above_it(isolated, app):
    owner = Owner()
    owner.show()
    app.processEvents()
    try:
        selector = workspace.open_template_builder(owner)
        mode_coordinator.request_mode('ocr', lambda: None)
        app.processEvents()
        assert not owner.isVisible()
        assert mode_coordinator.active_mode() == 'ocr'
        assert owner._dynamic_template_builder is None
    finally:
        owner.close()
        owner.deleteLater()


def test_permission_failure_keeps_window_and_existing_mode(isolated):
    owner = Owner()
    owner.allowed = False
    owner.show()
    mode_coordinator.request_mode('ocr', lambda: None)
    try:
        assert workspace.open_template_builder(owner) is None
        assert owner.isVisible()
        assert mode_coordinator.active_mode() == 'ocr'
    finally:
        owner.close()
        owner.deleteLater()


@pytest.mark.parametrize('locale', ('en','ru','es','de','fr','zh','pt','it','ar','tr','hi','id'))
@pytest.mark.parametrize('theme', ('Темная','Светлая'))
@pytest.mark.parametrize('dpi', (1, 1.5, 2))
def test_builder_text_is_localized_and_fits_its_toolbar(isolated, app, monkeypatch, locale, theme, dpi):
    monkeypatch.setattr('ui_scaling.desktop_control_scale', lambda *args: dpi)
    isolated[0].update(interface_language=locale, theme=theme)
    selector = workspace.PairedRegionSelector(template_builder=True)
    try:
        selector.template_name.setText('Example')
        areas(selector)
        app.processEvents()
        assert selector.start_button.text() == dynamic_templates.text(locale, 'save')
        assert selector.start_button.fontMetrics().horizontalAdvance(selector.start_button.text()) <= selector.start_button.width()-8
        assert selector.toolbar.rect().contains(selector.template_name_row.geometry())
        assert selector.rect().contains(selector.toolbar.geometry())
        assert selector.template_name.width() >= 120
        assert selector.template_name.placeholderText() == dynamic_templates.text(locale, 'templates')
        assert '{name}' in dynamic_templates.text(locale, 'replace_question')
        assert all(dynamic_templates.text(locale, key) for key in ('create_template', 'create_template_hint', 'templates_empty'))
    finally:
        selector.close()
