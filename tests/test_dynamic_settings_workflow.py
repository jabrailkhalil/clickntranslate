"""The Dynamic settings page separates saved choices from creating a layout."""
import copy
from unittest import mock

import pytest
from PyQt5 import QtCore

import dynamic_templates
import dynamic_workspace as workspace
import ocr
from test_desktop_ux import app, window
from test_dynamic_workspace import isolated


def save_layout(store, name='Dialogue', source='en', target='ru'):
    return store.save(workspace.make_template(name, [QtCore.QRect(50, 300, 220, 70)],
        [QtCore.QRect(380, 400, 250, 90)], [{}], source, target))


def settings_page(window, store, monkeypatch):
    monkeypatch.setattr(dynamic_templates, 'TemplateStore', lambda: store)
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(2)
    return settings


def test_empty_template_catalog_has_an_action_instead_of_a_disabled_placeholder(window, isolated, monkeypatch):
    config, store = isolated
    settings = settings_page(window, store, monkeypatch)
    assert settings.game_template_combo.count() == 0
    assert settings.game_template_combo.isHidden()
    assert settings.game_create_template_button.isVisible()
    assert settings.game_create_template_button.text() == dynamic_templates.text(window.current_interface_language, 'create_template')
    assert dynamic_templates.text(window.current_interface_language, 'templates_empty') in settings.game_remember_template_checkbox.toolTip()
    settings.game_remember_template_checkbox.setChecked(True)
    assert settings.game_template_combo.isHidden()
    assert settings.game_create_template_button.isVisible()


def test_saved_template_picker_contains_real_names_and_only_shows_when_remembered(window, isolated, monkeypatch):
    _, store = isolated
    save_layout(store, 'Dialogue')
    save_layout(store, 'Subtitles')
    window.config.update(game_remember_template=False, game_last_template='Dialogue')
    settings = settings_page(window, store, monkeypatch)
    assert [settings.game_template_combo.itemText(i) for i in range(settings.game_template_combo.count())] == ['Dialogue', 'Subtitles']
    assert settings.game_template_combo.isHidden()
    settings.game_remember_template_checkbox.setChecked(True)
    assert settings.game_template_combo.isVisible()
    assert settings.game_template_combo.currentData() == 'Dialogue'
    index = settings.game_template_combo.findData('Subtitles')
    settings.game_template_combo.setCurrentIndex(index)
    settings.game_template_combo.activated.emit(index)
    assert window.config['game_last_template'] == 'Subtitles'
    settings.game_remember_template_checkbox.setChecked(False)
    assert settings.game_template_combo.isHidden()
    assert window.config['game_last_template'] == 'Subtitles'
    assert settings.game_create_template_button.isVisible()


def test_create_action_passes_owner_and_committed_save_refreshes_the_choice(window, isolated, monkeypatch):
    _, store = isolated
    settings = settings_page(window, store, monkeypatch)
    token = object()
    with mock.patch.object(workspace, 'open_template_builder', return_value=token) as open_builder:
        assert settings._create_dynamic_template() is token
        assert open_builder.call_args.args == (window,)
        saved = save_layout(store, 'New dialogue')
        open_builder.call_args.kwargs['on_saved'](saved)
    assert window.config['game_remember_template'] is True
    assert window.config['game_last_template'] == 'New dialogue'
    assert settings.game_remember_template_checkbox.isChecked()
    assert settings.game_template_combo.currentData() == 'New dialogue'
    assert settings.game_template_combo.isVisible()
    assert settings.game_source_combo.currentData() == window.config['game_translate_source_language'] == 'en'
    assert settings.game_target_combo.currentData() == window.config['game_translate_target_language'] == 'ru'


def test_cancelling_creation_preserves_existing_template_preferences(window, isolated, monkeypatch):
    _, store = isolated
    save_layout(store)
    window.config.update(game_remember_template=True, game_last_template='Dialogue')
    settings = settings_page(window, store, monkeypatch)
    before = copy.deepcopy(window.config)
    with mock.patch.object(workspace, 'open_template_builder', return_value=None):
        settings.game_create_template_button.click()
    assert window.config == before
    assert settings.game_template_combo.currentData() == 'Dialogue'


def test_refresh_keeps_missing_saved_name_disabled_without_replacing_preferences(window, isolated, monkeypatch):
    _, store = isolated
    save_layout(store, 'Available')
    window.config.update(game_remember_template=True, game_last_template='Unplugged layout')
    settings = settings_page(window, store, monkeypatch)
    before = copy.deepcopy(window.config)
    with mock.patch.object(window, 'save_config') as save:
        settings._refresh_game_templates()
    save.assert_not_called()
    assert window.config == before
    index = settings.game_template_combo.currentIndex()
    assert settings.game_template_combo.currentText() == 'Unplugged layout'
    assert not settings.game_template_combo.model().item(index).isEnabled()
    assert 'unavailable' in settings.game_template_combo.toolTip().lower()
    assert settings.game_create_template_button.isVisible()


def test_broken_template_file_is_not_overwritten_by_refresh_or_create_cancellation(window, isolated, monkeypatch):
    _, store = isolated
    store.path.write_text('{broken', encoding='utf-8')
    window.config.update(game_remember_template=True, game_last_template='Previous')
    settings = settings_page(window, store, monkeypatch)
    assert settings.game_template_combo.isHidden()
    assert window.config['game_last_template'] == 'Previous'
    with mock.patch.object(workspace, 'open_template_builder', return_value=None):
        settings._create_dynamic_template()
    assert store.path.read_text(encoding='utf-8') == '{broken'


def test_explicit_template_choice_applies_saved_languages_but_viewing_does_not(window, isolated, monkeypatch):
    _, store = isolated
    save_layout(store, 'Dialogue', 'ru', 'en')
    window.config.update(game_remember_template=True, game_last_template='Dialogue',
                         game_translate_source_language='en', game_translate_target_language='ru')
    settings = settings_page(window, store, monkeypatch)
    assert settings.game_source_combo.currentData() == 'en'
    assert window.config['game_translate_source_language'] == 'en'
    index = settings.game_template_combo.findData('Dialogue')
    settings.game_template_combo.activated.emit(index)
    assert settings.game_source_combo.currentData() == window.config['game_translate_source_language'] == 'ru'
    assert settings.game_target_combo.currentData() == window.config['game_translate_target_language'] == 'en'


def test_manual_pair_change_after_template_choice_is_used_when_opening_the_workspace(window, isolated, monkeypatch):
    _, store = isolated
    original = save_layout(store)
    settings = settings_page(window, store, monkeypatch)
    settings._remember_game_template(original)
    settings.game_swap_button.click()
    assert window.config['game_translate_source_language'] == 'ru'
    assert window.config['game_translate_target_language'] == 'en'
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: dict(window.config))
    selector = workspace.PairedRegionSelector()
    try:
        assert selector.source_combo.currentData() == 'ru'
        assert selector.target_combo.currentData() == 'en'
        assert selector._regions == [QtCore.QRect(50, 300, 220, 70)]
        assert store.load() == [original]
    finally:
        selector.close()


def test_unavailable_template_language_does_not_replace_the_visible_or_saved_choice(window, isolated, monkeypatch):
    _, store = isolated
    save_layout(store, 'Available')
    save_layout(store, 'Arabic', 'ar', 'ru')
    window.config.update(game_remember_template=True, game_last_template='Available',
                         game_translate_source_language='en', game_translate_target_language='ru')
    settings = settings_page(window, store, monkeypatch)
    before = copy.deepcopy(window.config)
    index = settings.game_template_combo.findData('Arabic')
    settings.game_template_combo.setCurrentIndex(index)
    settings.game_template_combo.activated.emit(index)
    assert window.config == before
    assert settings.game_template_combo.currentData() == 'Available'
    assert settings.game_source_combo.currentData() == 'en'
    assert 'unavailable' in settings.game_template_combo.toolTip().lower()


@pytest.mark.parametrize('locale', ('en','ru','ar','hi','fr','zh'))
def test_hidden_saved_choice_reflows_without_overlapping_create_button(window, app, isolated, monkeypatch, locale):
    _, store = isolated
    save_layout(store)
    window.set_interface_language(locale)
    window.config.update(game_remember_template=False, game_last_template='Dialogue')
    settings = settings_page(window, store, monkeypatch)
    for scale in (80, 100, 125, 150, 200):
        window.set_ui_scale_percent(scale)
        for remembered in (False, True, False, True):
            settings.game_remember_template_checkbox.setChecked(remembered)
            for _ in range(8): app.processEvents()
            row = settings.game_template_actions
            create = settings.game_create_template_button
            combo = settings.game_template_combo
            create_rect = QtCore.QRect(create.mapTo(row, QtCore.QPoint()), create.size())
            assert row.rect().contains(create_rect), (locale,scale,remembered,create_rect,row.rect())
            if remembered:
                combo_rect = QtCore.QRect(combo.mapTo(row, QtCore.QPoint()), combo.size())
                assert not combo_rect.intersects(create_rect), (locale,scale,combo_rect,create_rect,
                    combo.parentWidget(),create.parentWidget(),row.layout().geometry())
                assert row.rect().contains(combo_rect)
