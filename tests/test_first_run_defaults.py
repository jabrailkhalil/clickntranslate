"""New installs, reset and language selection share the 1.8 defaults."""
import pytest

import main
from capture_regions import memory_control_modes


FACTORY_FLAGS = {
    'history': True, 'copy_history': True,
    'autostart': False, 'start_minimized': False,
    'button_tooltips_enabled': True, 'update_check_on_launch': True,
    'copy_translated_text': False, 'replace_selection_select_all': False,
    'restore_clipboard_after_selection': False,
    'close_result_window_on_outside_click': True, 'ocr_join_paragraphs': True,
    'keep_visible_on_ocr': False, 'freeze_screen_on_ocr': False,
    'dim_screen_during_ocr': False, 'notifications': True,
    'remember_copy_area': False, 'remember_translate_area': False,
    'game_pause_when_inactive': True, 'game_show_toolbar': True,
    'game_manual_output': False, 'game_remember_template': False,
    'desktop_assistant_enabled': False, 'main_assistant_visible': True,
    'desktop_assistant_reactions': True,
}


@pytest.mark.parametrize('language', main.INTERFACE_LANGUAGE_BY_CODE)
def test_fresh_settings_translate_into_interface_language(language):
    config = main.fresh_config(language)
    assert config['theme'] == 'Светлая'
    assert config['main_assistant_visible'] is True
    assert config['desktop_assistant_enabled'] is False
    assert config['button_tooltips_enabled'] is True
    for key, expected in FACTORY_FLAGS.items():
        assert config[key] is expected, (language, key)
    assert not memory_control_modes(config)
    assert config['game_capture_interval_ms'] == 850
    assert config['game_overlay_opacity'] == 88
    assert config['update_check_on_launch'] is True
    for source, target in main.TRANSLATION_PAIR_KEYS:
        assert config[target] == language
        assert config[source] != language
    for key in ('copy_hotkey', 'translate_hotkey', 'fullscreen_translate_hotkey',
                'translate_selection_hotkey', 'translate_replace_selection_hotkey',
                'game_translate_hotkey', 'toggle_window_hotkey'):
        assert config[key] == main.DEFAULT_CONFIG[key] and config[key]


def test_welcome_language_choice_updates_untouched_pairs_only():
    config = main.fresh_config()
    config.update(main_translation_source_language='de', main_translation_target_language='fr')
    main.follow_default_translation_language(config, 'ru')
    assert (config['main_translation_source_language'], config['main_translation_target_language']) == ('de', 'fr')
    for source, target in main.TRANSLATION_PAIR_KEYS[1:]:
        assert (config[source], config[target]) == ('en', 'ru')
    main.follow_default_translation_language(config, 'zh')
    assert config['main_translation_target_language'] == 'fr'
    assert config['ocr_translate_target_language'] == 'zh'


def test_existing_choices_survive_upgrade_and_interface_switch():
    old = dict(main.DEFAULT_CONFIG, theme='Темная', notifications=True,
               main_assistant_visible=False, button_tooltips_enabled=False,
               update_check_on_launch=False)
    old.pop('translation_defaults_language')
    migrated, _ = main.merge_config_defaults(old)
    main.follow_default_translation_language(migrated, 'de')
    for key, value in old.items():
        assert migrated[key] == value


@pytest.mark.parametrize('value', [False, True])
def test_explicit_flags_survive_upgrade_and_language_switch(value):
    # Test both choices, especially old explicit OFF values for newly ON defaults.
    saved = {key: value for key in FACTORY_FLAGS}
    saved['interface_language'] = 'ar'
    migrated, _ = main.merge_config_defaults(saved)
    main.follow_default_translation_language(migrated, 'pt')
    for key in FACTORY_FLAGS:
        assert migrated[key] is value, key


def test_missing_flags_and_reset_use_factory_defaults_without_area_opt_in():
    upgraded, _ = main.merge_config_defaults({'interface_language': 'it'})
    reset = main.fresh_config('it')
    for config in (upgraded, reset):
        for key, expected in FACTORY_FLAGS.items():
            assert config[key] is expected, key
        assert not memory_control_modes(config)
    # Legacy opt-in must not be lost when the new per-mode key is absent.
    upgraded, _ = main.merge_config_defaults({'remember_translate_area': True})
    assert memory_control_modes(upgraded) == ('translate',)


@pytest.mark.parametrize('language', main.INTERFACE_LANGUAGE_BY_CODE)
def test_missing_pairs_use_saved_interface_language(language):
    config, _ = main.merge_config_defaults({'interface_language': language})
    for source, target in main.TRANSLATION_PAIR_KEYS:
        assert config[target] == language
        assert config[source] != language


def test_fresh_config_does_not_mutate_shared_defaults():
    original = dict(main.DEFAULT_CONFIG)
    config, _ = main.merge_config_defaults({})
    main.follow_default_translation_language(config, 'ru')
    assert main.DEFAULT_CONFIG == original


@pytest.mark.parametrize('language', main.INTERFACE_LANGUAGE_BY_CODE)
def test_intro_is_short_localized_and_has_current_version(language):
    text = main.welcome_text(language)
    assert main.APP_VERSION in text['body']
    assert '000' not in str(text)
    assert len(text['features']) == 5
    assert all(point.strip() and len(point) < 100 for point in text['features'])
    assert len(text['body']) < 190
    assert set(main.startup_news_text(language)) == {'window', 'title', 'intro', 'continue'}
