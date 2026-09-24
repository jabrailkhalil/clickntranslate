"""New installs, reset and language selection share the 1.8 defaults."""
import pytest

import main


@pytest.mark.parametrize('language', main.INTERFACE_LANGUAGE_BY_CODE)
def test_fresh_settings_translate_into_interface_language(language):
    config = main.fresh_config(language)
    assert config['theme'] == 'Светлая'
    assert config['main_assistant_visible'] is True
    assert config['desktop_assistant_enabled'] is False
    assert config['button_tooltips_enabled'] is True
    assert config['notifications'] is False
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
    assert '000' in text['body'] and '000' in text['feature_updates']
    assert len(text['body']) < 190
    assert set(main.startup_news_text(language)) == {'window', 'title', 'intro', 'continue'}
