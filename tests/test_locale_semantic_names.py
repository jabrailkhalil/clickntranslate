"""Visible language names describe languages, not countries or an English fallback."""
from types import SimpleNamespace

import pytest

from assistant_text import ASSISTANT_TEXT, assistant_text
from extended_languages import EXTRA_NAMES
from languages import language_code_from_name, language_display_name, LOCALIZED_LANGUAGE_NAMES
from settings_sections import PAGE_APPLICATION, PAGE_COMPANION, PAGE_DYNAMIC, page_caption
from settings_window import OcrLanguageManagerDialog, language_manager_text


@pytest.mark.parametrize('locale,code,expected', [
    ('es', 'hy', 'Armenio'), ('es', 'th', 'Tailandés'),
    ('es', 'id', 'Indonesio'), ('es', 'nb', 'Noruego bokmål'),
    ('es', 'cy', 'Galés'), ('es', 'be', 'Bielorruso'),
    ('de', 'ka', 'Georgisch'), ('de', 'sw', 'Suaheli'),
    ('de', 'cs', 'Tschechisch'), ('de', 'ga', 'Irisch'),
    ('fr', 'bs', 'Bosniaque'), ('fr', 'cy', 'Gallois'),
    ('fr', 'lv', 'Letton'), ('fr', 'ms', 'Malais'),
])
def test_corrected_labels_identify_the_language_and_round_trip(locale, code, expected):
    assert language_display_name(code, locale) == expected
    assert language_code_from_name(expected, locale) == code


@pytest.mark.parametrize('locale', tuple(ASSISTANT_TEXT))
def test_every_language_name_round_trips_without_collisions_in_each_interface(locale):
    names = LOCALIZED_LANGUAGE_NAMES[locale]
    assert len(set(value.casefold() for value in names.values())) == len(names)
    for code in EXTRA_NAMES['en']:
        label = language_display_name(code, locale)
        assert language_code_from_name(label, locale) == code, (locale, code, label)


@pytest.mark.parametrize('locale', tuple(ASSISTANT_TEXT))
def test_hide_hint_points_to_the_actual_companion_tab(locale):
    assert page_caption(locale, PAGE_COMPANION) in assistant_text(locale, 'hide_hint')


@pytest.mark.parametrize('locale', tuple(ASSISTANT_TEXT))
def test_current_guides_name_the_real_tabs_and_show_the_flag_as_language_entry(locale):
    from settings_guide_content import APPLICATION_SUMMARY, COPY, guide_updates
    import main
    updates = guide_updates(locale)
    assert updates['settings_page_game'][0] == page_caption(locale, PAGE_DYNAMIC)
    assert page_caption(locale, PAGE_DYNAMIC) in updates['settings_page_game'][1]
    assert updates['settings_page_main'][0] == page_caption(locale, PAGE_APPLICATION)
    assert COPY[locale][1] == COPY[locale][12] == APPLICATION_SUMMARY[locale]
    # The language entry now lives in the header, so the active guide must
    # mention that flag rather than leaving the old Application-only list.
    flag_words = {'en':'flag', 'ru':'флаг', 'es':'bandera', 'de':'Flagge', 'fr':'drapeau',
                  'zh':'国旗', 'pt':'bandeira', 'it':'bandiera', 'ar':'العلم',
                  'tr':'bayrak', 'hi':'झंडे', 'id':'bendera'}
    assert flag_words[locale].casefold() in APPLICATION_SUMMARY[locale].casefold()
    actual_steps = {step[0]:step[1:] for step in main.guide_text(locale)['steps']}
    assert actual_steps['settings_page_game'] == updates['settings_page_game']
    assert actual_steps['settings_page_main'] == updates['settings_page_main']


@pytest.mark.parametrize('locale', tuple(ASSISTANT_TEXT))
def test_rapidocr_model_description_uses_local_language_names_without_changing_package_ids(locale):
    collected = []
    owner = SimpleNamespace(lang=locale, _rapidocr_status_cache=(True, ''),
        _set_engine_missing_state=lambda *_: None,
        _status_installed=lambda: 'installed', _status_missing=lambda: 'missing',
        _status_checking=lambda: 'checking',
        _set_language_rows=lambda _table, rows: collected.extend(rows))
    OcrLanguageManagerDialog._populate_rapidocr_table(owner, object())
    rows = {row['code']: row for row in collected}
    assert rows['rapidocr-engine']['package'] == 'rapidocr'
    assert rows['rapidocr-runtime']['package'] == 'onnxruntime'
    assert rows['rapidocr-detector']['package'] == 'PP-OCR detector'
    assert rows['rapidocr-recognition']['package'] == (
        language_display_name('zh', locale) + ' + ' + language_display_name('en', locale))
    if locale != 'en':
        assert 'Chinese + English' not in language_manager_text(locale, 'rapidocr_note')
