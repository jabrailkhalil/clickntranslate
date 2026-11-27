"""Dynamic remembers the user's template choice, not an implicit last session."""
import copy
from unittest import mock

import pytest
from PyQt5 import QtCore

import dynamic_templates
import dynamic_workspace as workspace
import game_mode
import ocr
from capture_regions import text as region_text, LANGUAGES
from test_dynamic_workspace import isolated, app, make_overlay
from test_desktop_ux import window


def saved(store, name='Dialogue'):
    value = workspace.make_template(name, [QtCore.QRect(40, 300, 240, 80)],
                                    [QtCore.QRect(400, 400, 300, 100)], [{}], 'en', 'ru')
    return store.save(value)


def test_template_reopens_for_review_without_starting_or_overwriting_choices(isolated, monkeypatch):
    config, store = isolated
    saved(store)
    config.update(game_remember_template=True, game_last_template='Dialogue')
    with mock.patch.object(game_mode, '_begin_game_session') as start:
        selector = workspace.PairedRegionSelector()
        try:
            assert selector.template_combo.currentText() == 'Dialogue'
            assert selector._regions == [QtCore.QRect(40, 300, 240, 80)]
            assert selector._outputs == [QtCore.QRect(400, 400, 300, 100)]
            assert selector.start_button.isEnabled()
            start.assert_not_called()
            selector.close()
            assert config['game_last_template'] == 'Dialogue'
        finally:
            selector.close()


@pytest.mark.parametrize('enabled', [False, True])
def test_only_a_started_session_remembers_the_selected_template(isolated, monkeypatch, enabled):
    config, store = isolated
    saved(store, 'First')
    saved(store, 'Second')
    config.update(game_remember_template=enabled, game_last_template='First')
    def write(values):
        config.update(values)
        return True
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', write)
    selector = workspace.PairedRegionSelector()
    try:
        if not enabled:
            assert not selector._regions
        selector._load_template(selector.template_combo.findText('Second'))
        assert config['game_last_template'] == 'First'
        with mock.patch.object(game_mode, '_begin_game_session') as start:
            selector._start_selected_regions()
            start.assert_called_once()
        assert config['game_last_template'] == ('Second' if enabled else 'First')
    finally:
        selector.close()


def test_new_layout_clears_previous_starting_template_after_start(isolated, monkeypatch):
    config, store = isolated
    saved(store)
    config.update(game_remember_template=True, game_last_template='Dialogue')
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', lambda values: config.update(values) or True)
    selector = workspace.PairedRegionSelector()
    try:
        selector._load_template(0)
        assert config['game_last_template'] == 'Dialogue'
        assert not selector._regions
        selector._regions = [QtCore.QRect(40, 300, 200, 80)]
        selector._outputs = [QtCore.QRect(40, 300, 200, 80)]
        selector._styles = [{}]
        selector._update_selection_controls()
        with mock.patch.object(game_mode, '_begin_game_session'):
            selector._start_selected_regions()
        assert config['game_last_template'] == ''
    finally:
        selector.close()


@pytest.mark.parametrize('kind', ['missing_name', 'missing_screen', 'missing_output_screen'])
def test_unavailable_template_is_reported_without_partial_restore_or_fallback(isolated, kind):
    config, store = isolated
    value = saved(store)
    config.update(game_remember_template=True, game_last_template='Dialogue')
    if kind == 'missing_name':
        config['game_last_template'] = 'Removed template'
    else:
        key = 'source' if kind == 'missing_screen' else 'output'
        value['pairs'][0][key]['screen'] = 'unplugged display'
        store.save(value)
    old = copy.deepcopy(config)
    selector = workspace.PairedRegionSelector()
    try:
        assert not selector._regions and not selector._outputs
        assert not selector.start_button.isEnabled()
        assert selector.selection_note.text() == region_text('ru', 'dynamic_missing')
        assert config == old
        assert selector.template_combo.currentIndex() == 0
    finally:
        selector.close()


def test_dynamic_settings_offer_template_memory_and_explicit_choice(window, isolated, monkeypatch):
    config, store = isolated
    saved(store)
    monkeypatch.setattr(dynamic_templates, 'TemplateStore', lambda: store)
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(2)
    assert not settings.game_remember_template_checkbox.isChecked()
    assert settings.game_template_combo.isEnabled()
    assert settings.game_template_combo.isVisible()
    settings.game_remember_template_checkbox.setChecked(True)
    assert settings.game_template_combo.isEnabled()
    index = settings.game_template_combo.findData('Dialogue')
    settings.game_template_combo.setCurrentIndex(index)
    settings.game_template_combo.activated.emit(index)
    assert window.config['game_last_template'] == 'Dialogue'
    assert window.config['game_remember_template'] is True
    settings._set_settings_page(0)
    settings._set_settings_page(2)
    assert settings.game_template_combo.currentData() == 'Dialogue'
    settings.game_remember_template_checkbox.setChecked(False)
    assert settings.game_template_combo.isEnabled()
    assert settings.game_template_combo.currentData() == 'Dialogue'
    assert window.config['game_last_template'] == 'Dialogue'


def test_restoring_template_geometry_keeps_the_current_pair_and_cancelling_keeps_config(isolated, monkeypatch):
    config, store = isolated
    value = saved(store)
    value.update(source_language='ru', target_language='en')
    store.save(value)
    config.update(game_remember_template=True, game_last_template='Dialogue')
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', lambda values: config.update(values) or True)
    before = copy.deepcopy(config)
    selector = workspace.PairedRegionSelector()
    try:
        assert selector.source_combo.currentData() == 'en'
        assert selector.target_combo.currentData() == 'ru'
        assert config == before
        selector.close()
        assert config == before
    finally:
        selector.close()


def test_failed_second_template_keeps_the_previous_name_and_geometry(isolated):
    config, store = isolated
    saved(store, 'First')
    value = saved(store, 'Broken')
    value['pairs'][0]['output']['screen'] = 'unplugged monitor'
    store.save(value)
    selector = workspace.PairedRegionSelector()
    try:
        selector._load_template(selector.template_combo.findText('First'))
        regions = copy.deepcopy(selector._regions)
        selector.template_combo.setCurrentIndex(selector.template_combo.findText('Broken'))
        assert selector._load_template(selector.template_combo.currentIndex()) is False
        assert selector.template_combo.currentText() == 'First'
        assert selector._regions == regions
        with mock.patch.object(game_mode, '_begin_game_session') as start:
            selector._start_selected_regions()
            assert start.call_args.kwargs['template_name'] == 'First'
    finally:
        selector.close()


@pytest.mark.parametrize('enabled', [False, True])
def test_saving_active_layout_remembers_it_only_when_enabled_and_deleting_clears_it(isolated, monkeypatch, enabled):
    config, store = isolated
    config.update(game_remember_template=enabled, game_last_template='Previous')
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', lambda values: config.update(values) or True)
    overlay = make_overlay(QtCore.QRect(40, 300, 240, 80), 'en', 'ru',
                           output_region=QtCore.QRect(400, 400, 300, 100))
    try:
        controls = overlay.controls
        controls.template_name.setEditText('New dialogue')
        controls._save()
        assert store.load()[0]['name'] == 'New dialogue'
        assert config['game_last_template'] == ('New dialogue' if enabled else 'Previous')
        controls._delete_template()
        assert not store.load()
        assert config['game_last_template'] == ('' if enabled else 'Previous')
    finally:
        overlay.close()


def test_failed_active_template_save_never_changes_remembered_choice(isolated, monkeypatch):
    config, store = isolated
    config.update(game_remember_template=True, game_last_template='Previous')
    write = mock.Mock()
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', write)
    monkeypatch.setattr(store, 'save', mock.Mock(side_effect=OSError('read only')))
    overlay = make_overlay(QtCore.QRect(40, 300, 240, 80), 'en', 'ru',
                           output_region=QtCore.QRect(400, 400, 300, 100))
    try:
        overlay.controls.template_name.setEditText('New dialogue')
        overlay.controls._save()
        write.assert_not_called()
        assert config['game_last_template'] == 'Previous'
    finally:
        overlay.close()


def test_deleting_template_reads_current_preferences_after_config_cache_replacement(isolated, monkeypatch):
    config, store = isolated
    config.update(game_remember_template=True, game_last_template='Previous')
    current = [dict(config)]
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: current[0])
    def write(values):
        current[0] = dict(current[0], **values)
        return True
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', write)
    overlay = make_overlay(QtCore.QRect(40, 300, 240, 80), 'en', 'ru',
                           output_region=QtCore.QRect(400, 400, 300, 100))
    try:
        overlay.controls.template_name.setEditText('New dialogue')
        overlay.controls._save()
        assert current[0]['game_last_template'] == 'New dialogue'
        assert overlay.config['game_last_template'] == 'Previous'
        overlay.controls._delete_template()
        assert current[0]['game_last_template'] == ''
        assert not store.load()
    finally:
        overlay.close()


@pytest.mark.parametrize('locale', LANGUAGES)
@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
def test_dynamic_memory_settings_fit_the_fixed_page_in_all_languages(window, app, locale, theme):
    window.set_interface_language(locale)
    if window.current_theme != theme:
        window.toggle_theme()
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(2)
    for _ in range(5):
        app.processEvents()
    page = settings.settings_game_page
    controls = [settings.game_pause_inactive_checkbox, settings.game_manual_output_checkbox,
                settings.game_toolbar_checkbox, settings.game_remember_template_checkbox,
                settings.game_template_combo, settings.game_delete_template_button,
                settings.game_help_button, settings.game_launch_button]
    for widget in controls:
        rect = QtCore.QRect(widget.mapTo(page, QtCore.QPoint()), widget.size())
        assert page.rect().contains(rect), (locale, theme, widget.objectName(), rect, page.rect())
        assert widget.isVisible()
    for checkbox in controls[:4]:
        assert checkbox.width() >= checkbox.sizeHint().width(), (locale, checkbox.text())
    assert settings.game_remember_template_checkbox.toolTip()
    assert settings.game_template_combo.toolTip()
