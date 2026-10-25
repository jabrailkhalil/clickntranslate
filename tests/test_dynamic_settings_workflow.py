"""The Dynamic settings page separates saved choices from creating a layout."""
import copy
from contextlib import nullcontext
from unittest import mock

import pytest
from PyQt5 import QtCore

import dynamic_templates
import dynamic_workspace as workspace
import ocr
import settings_window
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


def create_action(combo):
    return next(index for index in range(combo.count())
                if combo.itemData(index) == {'action': 'create_template'})


def test_empty_template_catalog_has_an_action_instead_of_a_disabled_placeholder(window, isolated, monkeypatch):
    config, store = isolated
    settings = settings_page(window, store, monkeypatch)
    assert settings.game_template_combo.count() == 1
    assert settings.game_template_combo.isVisible()
    assert settings.game_template_combo.isEnabled()
    assert settings.game_template_combo.itemText(create_action(settings.game_template_combo)) == dynamic_templates.text(window.current_interface_language, 'create_template')
    assert not settings.game_delete_template_button.isEnabled()
    assert dynamic_templates.text(window.current_interface_language, 'templates_empty') in settings.game_remember_template_checkbox.toolTip()
    settings.game_remember_template_checkbox.setChecked(True)
    assert settings.game_template_combo.isVisible()
    assert not settings.game_delete_template_button.isEnabled()


def test_saved_template_picker_keeps_current_choice_visible_when_memory_is_off(window, isolated, monkeypatch):
    _, store = isolated
    save_layout(store, 'Dialogue')
    save_layout(store, 'Subtitles')
    window.config.update(game_remember_template=False, game_last_template='Dialogue')
    settings = settings_page(window, store, monkeypatch)
    assert [settings.game_template_combo.itemText(i) for i in range(2)] == ['Dialogue', 'Subtitles']
    assert create_action(settings.game_template_combo) == 2
    assert settings.game_template_combo.isVisible()
    assert settings.game_template_combo.isEnabled()
    assert settings.game_template_combo.currentData() == 'Dialogue'
    settings.game_remember_template_checkbox.setChecked(True)
    assert settings.game_template_combo.isVisible()
    assert settings.game_template_combo.currentData() == 'Dialogue'
    index = settings.game_template_combo.findData('Subtitles')
    settings.game_template_combo.setCurrentIndex(index)
    settings.game_template_combo.activated.emit(index)
    assert window.config['game_last_template'] == 'Subtitles'
    settings.game_remember_template_checkbox.setChecked(False)
    assert settings.game_template_combo.isVisible()
    assert settings.game_template_combo.currentData() == 'Subtitles'
    assert window.config['game_last_template'] == 'Subtitles'
    assert settings.game_delete_template_button.isEnabled()


def test_create_action_passes_owner_and_committed_save_refreshes_the_choice(window, isolated, monkeypatch):
    _, store = isolated
    settings = settings_page(window, store, monkeypatch)
    token = object()
    with mock.patch.object(workspace, 'open_template_builder', return_value=token) as open_builder:
        assert settings._game_template_selected(create_action(settings.game_template_combo)) is token
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
    before_file = store.path.read_bytes()
    with mock.patch.object(workspace, 'open_template_builder', return_value=None):
        index = create_action(settings.game_template_combo)
        settings.game_template_combo.setCurrentIndex(index)
        settings.game_template_combo.activated.emit(index)
    assert window.config == before
    assert store.path.read_bytes() == before_file
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
    assert not settings.game_delete_template_button.isEnabled()
    assert create_action(settings.game_template_combo) == settings.game_template_combo.count()-1


def test_broken_template_file_is_not_overwritten_by_refresh_or_create_cancellation(window, isolated, monkeypatch):
    _, store = isolated
    store.path.write_text('{broken', encoding='utf-8')
    window.config.update(game_remember_template=True, game_last_template='Previous')
    settings = settings_page(window, store, monkeypatch)
    assert settings.game_template_combo.isVisible()
    assert settings.game_template_combo.count() == 1
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


def test_template_named_like_the_create_action_is_a_real_choice(window, isolated, monkeypatch):
    _, store = isolated
    name = dynamic_templates.text(window.current_interface_language, 'create_template')
    save_layout(store, name)
    settings = settings_page(window, store, monkeypatch)
    real_index = settings.game_template_combo.findData(name)
    assert real_index >= 0
    assert real_index != create_action(settings.game_template_combo)
    with mock.patch.object(workspace, 'open_template_builder') as builder:
        settings.game_template_combo.activated.emit(real_index)
    builder.assert_not_called()
    assert window.config['game_last_template'] == name
    assert settings.game_delete_template_button.isEnabled()


def test_deletion_cancellation_keeps_exact_file_preferences_and_selection(window, isolated, monkeypatch):
    _, store = isolated
    save_layout(store)
    window.config.update(game_remember_template=False, game_last_template='Dialogue')
    settings = settings_page(window, store, monkeypatch)
    before, raw = copy.deepcopy(window.config), store.path.read_bytes()
    with mock.patch.object(settings_window.QMessageBox, 'question', return_value=settings_window.QMessageBox.No) as question:
        assert settings._delete_game_template() is False
    assert question.call_args.args[-1] == settings_window.QMessageBox.No
    assert window.config == before
    assert store.path.read_bytes() == raw
    assert settings.game_template_combo.currentData() == 'Dialogue'


def test_deleting_only_current_template_preserves_languages_and_remember_setting(window, isolated, monkeypatch):
    _, store = isolated
    save_layout(store)
    save_layout(store, 'Subtitles')
    window.config.update(game_remember_template=False, game_last_template='Dialogue',
                         game_translate_source_language='ru', game_translate_target_language='en')
    settings = settings_page(window, store, monkeypatch)
    before = copy.deepcopy(window.config)
    with mock.patch.object(settings_window.QMessageBox, 'question', return_value=settings_window.QMessageBox.Yes):
        assert settings._delete_game_template() is True
    assert [value['name'] for value in store.load()] == ['Subtitles']
    assert window.config['game_last_template'] == ''
    for key in ('game_remember_template', 'game_translate_source_language', 'game_translate_target_language'):
        assert window.config[key] == before[key]
    assert settings.game_template_combo.currentIndex() == -1
    assert not settings.game_delete_template_button.isEnabled()
    # Explicitly select the remaining saved layout, then delete the final entry.
    settings.game_template_combo.activated.emit(settings.game_template_combo.findData('Subtitles'))
    with mock.patch.object(settings_window.QMessageBox, 'question', return_value=settings_window.QMessageBox.Yes):
        settings.game_delete_template_button.click()
    assert store.load() == []
    assert settings.game_template_combo.count() == 1
    assert settings.game_template_combo.currentIndex() == create_action(settings.game_template_combo)
    assert settings.game_template_combo.isEnabled()
    assert not settings.game_delete_template_button.isEnabled()


@pytest.mark.parametrize('failure', ('catalog_write', 'preference_write'))
def test_failed_deletion_restores_exact_catalog_and_preferences(window, isolated, monkeypatch, failure):
    _, store = isolated
    save_layout(store)
    window.config.update(game_remember_template=False, game_last_template='Dialogue')
    settings = settings_page(window, store, monkeypatch)
    before, raw = copy.deepcopy(window.config), store.path.read_bytes()
    if failure == 'catalog_write':
        monkeypatch.setattr(store, 'delete', mock.Mock(side_effect=OSError('read only')))
    save_failure = (mock.patch.object(window, 'save_config', side_effect=OSError('read only'))
                    if failure == 'preference_write' else nullcontext())
    with save_failure, mock.patch.object(settings_window.QMessageBox, 'question', return_value=settings_window.QMessageBox.Yes), \
            mock.patch.object(settings_window.QMessageBox, 'warning') as warning:
        assert settings._delete_game_template() is False
    warning.assert_called_once()
    assert window.config == before
    assert store.path.read_bytes() == raw
    assert settings.game_template_combo.currentData() == 'Dialogue'
    assert settings.game_delete_template_button.isEnabled()


@pytest.mark.parametrize('locale', ('en','ru','es','de','fr','zh','pt','it','ar','tr','hi','id'))
def test_delete_copy_is_localized_and_html_template_names_are_plain_content(window, isolated, monkeypatch, locale):
    from PyQt5.QtGui import QTextDocument
    _, store = isolated
    name = '<b>Dialogue & subtitles</b> ' + 'Long name ' * 8
    saved = save_layout(store, name)
    window.set_interface_language(locale)
    window.config.update(game_remember_template=True, game_last_template=saved['name'])
    settings = settings_page(window, store, monkeypatch)
    with mock.patch.object(settings_window.QMessageBox, 'question', return_value=settings_window.QMessageBox.No) as question:
        settings._delete_game_template()
    document = QTextDocument()
    document.setHtml(question.call_args.args[2])
    assert document.toPlainText() == dynamic_templates.text(locale, 'delete_template_question').format(name=saved['name'])
    assert settings.game_delete_template_button.accessibleName() == dynamic_templates.text(locale, 'delete_selected_template')
    assert settings.game_delete_template_button.toolTip()
    assert settings.game_template_combo.itemText(create_action(settings.game_template_combo)) == dynamic_templates.text(locale, 'create_template')
    for theme in ('Темная', 'Светлая'):
        if window.current_theme != theme:
            window.toggle_theme()
        document.setHtml(settings.game_template_combo.toolTip())
        assert document.toPlainText().startswith(saved['name'] + '\n')
        document.setHtml(settings.game_template_combo.itemData(settings.game_template_combo.currentIndex(), QtCore.Qt.ToolTipRole))
        assert document.toPlainText() == saved['name']


@pytest.mark.parametrize('locale', ('en','ru','es','de','fr','zh','pt','it','ar','tr','hi','id'))
def test_saved_choice_and_delete_action_fit_every_scale_theme_and_memory_state(window, app, isolated, monkeypatch, locale):
    _, store = isolated
    save_layout(store)
    window.set_interface_language(locale)
    window.config.update(game_remember_template=False, game_last_template='Dialogue')
    settings = settings_page(window, store, monkeypatch)
    for theme in ('Темная', 'Светлая'):
        if window.current_theme != theme:
            window.toggle_theme()
        for scale in (80, 100, 125, 150, 200):
            window.set_ui_scale_percent(scale)
            for remembered in (False, True, False):
                settings.game_remember_template_checkbox.setChecked(remembered)
                for _ in range(8): app.processEvents()
                row = settings.game_template_actions
                delete = settings.game_delete_template_button
                combo = settings.game_template_combo
                delete_rect = QtCore.QRect(delete.mapTo(row, QtCore.QPoint()), delete.size())
                combo_rect = QtCore.QRect(combo.mapTo(row, QtCore.QPoint()), combo.size())
                assert combo.isVisible() and combo.isEnabled()
                assert delete.isVisible() and delete.isEnabled()
                assert not combo_rect.intersects(delete_rect), (locale,theme,scale,combo_rect,delete_rect)
                assert row.rect().contains(delete_rect), (locale,theme,scale,delete_rect,row.rect())
                assert row.rect().contains(combo_rect)
                assert combo.currentData() == 'Dialogue'


@pytest.mark.parametrize('locale,theme', (('en','Темная'),('en','Светлая'),('ar','Темная'),('ar','Светлая')))
def test_template_dropdown_renders_names_and_create_action_inside_rounded_popup(window, app, isolated, monkeypatch, locale, theme):
    import os
    from pathlib import Path
    _, store = isolated
    save_layout(store, 'Dialogue — subtitles near the bottom of the screen')
    save_layout(store, '<b>Dialogue & narration</b>')
    window.set_interface_language(locale)
    if window.current_theme != theme:
        window.toggle_theme()
    window.config.update(game_remember_template=False,
                         game_last_template='Dialogue — subtitles near the bottom of the screen')
    settings = settings_page(window, store, monkeypatch)
    combo = settings.game_template_combo
    try:
        combo.showPopup()
        for _ in range(8): app.processEvents()
        view = combo.view()
        action_index = combo.model().index(create_action(combo), 0)
        assert view.viewport().rect().contains(view.visualRect(action_index))
        assert combo.currentData() == window.config['game_last_template']
        output = Path(os.environ['XDG_DATA_HOME']).parent / 'template-renders'
        output.mkdir(exist_ok=True)
        suffix = locale + ('-dark' if theme == 'Темная' else '-light')
        assert settings.grab().save(str(output / ('dynamic-' + suffix + '.png')))
        assert view.window().grab().save(str(output / ('template-popup-' + suffix + '.png')))
    finally:
        combo.hidePopup()
