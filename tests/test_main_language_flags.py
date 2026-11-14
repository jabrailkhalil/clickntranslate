"""Language flags survive the main window's normal repopulation paths."""
from unittest import mock

import pytest
from PyQt5 import QtCore,QtWidgets

import main
from languages import get_language, language_code_from_name, language_display_name
from settings_window import CompactDynamicLanguageCombo
from test_desktop_ux import app, window


def assert_flags(window):
    for combo in (window.source_lang, window.target_lang,
                  window.hotkey_source_combo, window.hotkey_target_combo):
        assert not isinstance(combo, CompactDynamicLanguageCombo)
        for row in range(combo.count()):
            code = combo.itemData(row) or language_code_from_name(combo.itemText(row), window.current_interface_language)
            if code == 'auto':
                continue  # Automatic detection has no country flag.
            assert get_language(code) is not None, (combo.itemText(row), code)
            assert not combo.itemIcon(row).isNull(), (window.current_interface_language, code)
            assert combo.itemText(row) == language_display_name(code,window.current_interface_language)
        assert combo.count() > 0


def assert_pair_flags(dialog, locale):
    for combo in (dialog.source_combo, dialog.target_combo):
        assert combo.count() > 0
        assert combo.iconSize() == QtCore.QSize(20, 20)
        for row in range(combo.count()):
            code = combo.itemData(row) or language_code_from_name(combo.itemText(row), locale)
            if code == 'auto':
                assert combo.itemIcon(row).isNull()
            else:
                assert not combo.itemIcon(row).isNull(), (locale, type(dialog).__name__, code)
            assert combo.itemText(row) == language_display_name(code, locale)


@pytest.mark.parametrize('locale', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
def test_result_document_and_pair_editor_keep_flags_after_repopulation(window, app, locale):
    window.config['translator_engine'] = 'Google'
    window.set_interface_language(locale)
    result = main.TranslationResultDialog(window, 'Translation', auto_copy=False, lang=locale,
                                         source_text='Source', source_lang='en', target_lang='ar')
    document = main.DocumentTranslationDialog(window)
    pair = main.HotkeyLanguageDialog(window)
    try:
        for theme in ('Темная', 'Светлая'):
            if window.current_theme != theme:
                window.toggle_theme()
            result.refresh_theme(theme)
            document.refresh_theme(theme)
            pair._apply_theme()
            with mock.patch.object(result, '_start_retranslate'):
                result.source_combo.setCurrentIndex(result.source_combo.findData('ru'))
                result._fill_target_combo('ar')
            result.refresh_language(locale)
            document.refresh_language(locale)
            document._refresh_document_provider_languages()
            for mode in main.HOTKEY_LANGUAGE_MODES:
                pair.mode_combo.setCurrentIndex(pair.mode_combo.findData(mode))
                pair._load_mode()
                assert_pair_flags(pair, locale)
            assert_pair_flags(result, locale)
            assert_pair_flags(document, locale)
        # Language changes clear and rebuild the document fields too.
        other = 'ar' if locale != 'ar' else 'en'
        result.refresh_language(other)
        document.refresh_language(other)
        assert_pair_flags(result, other)
        assert_pair_flags(document, other)
        result.show()
        app.processEvents()
        for combo in (result.source_combo, result.target_combo):
            assert not combo.grab().isNull()
    finally:
        for dialog in (result, document, pair):
            dialog.close()
            dialog.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()


@pytest.mark.parametrize('locale', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
def test_main_flags_survive_pair_modes_themes_and_returning_from_settings(window, app, locale):
    with mock.patch('ocr.installed_ocr_language_codes',return_value=['en','ru']):
        window.config['translator_engine']='google'
        window.set_interface_language(locale)
        window.show_main_screen()
        app.processEvents()
        assert_flags(window)
        window.source_lang.setCurrentText(language_display_name('ru',locale))
        app.processEvents()
        assert_flags(window)
        for mode in main.HOTKEY_LANGUAGE_MODES:
            index=window.hotkey_mode_combo.findData(mode)
            assert index >= 0
            window.hotkey_mode_combo.setCurrentIndex(index)
            app.processEvents()
            assert_flags(window)
        for theme in ('Светлая','Темная'):
            if window.current_theme != theme:
                window.toggle_theme()
            app.processEvents()
            assert_flags(window)
        window.show_settings()
        window.show_main_screen()
        app.processEvents()
        assert_flags(window)


@pytest.mark.parametrize('theme',['Темная','Светлая'])
def test_arabic_flagged_fields_paint_the_whole_label_instead_of_a_sliver(window,app,theme):
    from collections import Counter
    window.set_interface_language('ar')
    if window.current_theme != theme:
        window.toggle_theme()
    window.show_main_screen()
    combo=window.source_lang
    index=combo.findText(language_display_name('ru','ar'))
    assert index>=0
    combo.setCurrentIndex(index)
    app.processEvents()
    option=QtWidgets.QStyleOptionComboBox()
    combo.initStyleOption(option)
    field=combo.style().subControlRect(QtWidgets.QStyle.CC_ComboBox,option,
                                      QtWidgets.QStyle.SC_ComboBoxEditField,combo)
    text_rect=field.adjusted(0,0,-option.iconSize.width()-6,0)
    original=combo.currentText()
    assert combo.fontMetrics().horizontalAdvance(original) <= text_rect.width()
    full=combo.grab().toImage().copy(text_rect)
    with QtCore.QSignalBlocker(combo):
        combo.setItemText(index,original[:2])
        short=combo.grab().toImage().copy(text_rect)
        combo.setItemText(index,original)
    def ink(picture):
        pixels=Counter(picture.pixel(x,y) for x in range(picture.width()) for y in range(picture.height()))
        return picture.width()*picture.height()-pixels.most_common(1)[0][1]
    assert ink(full)>ink(short)*1.5,(theme,ink(full),ink(short),original)
    pixels=Counter(full.pixel(x,y) for x in range(full.width()) for y in range(full.height()))
    background=pixels.most_common(1)[0][0]
    right=max(x for x in range(full.width()) for y in range(full.height())
              if full.pixel(x,y)!=background)
    assert full.width()-1-right < combo.fontMetrics().height(),(theme,right,full.width())


@pytest.mark.parametrize('locale',['ru','ar'])
@pytest.mark.parametrize('theme',['Темная','Светлая'])
def test_compact_field_paints_the_code_beside_its_flag(window,app,locale,theme):
    with mock.patch('ocr.installed_ocr_language_codes',return_value=['en','ru']):
        window.set_interface_language(locale)
        if window.current_theme != theme:
            window.toggle_theme()
        window.show_settings()
        settings=window.settings_window
        settings._set_settings_page(2)
        settings._populate_game_language_controls()
        combo=settings.game_source_combo
        app.processEvents()
        option=QtWidgets.QStyleOptionComboBox()
        combo.initStyleOption(option)
        assert option.currentText in ('RU','EN')
        assert not option.currentIcon.isNull()
        field=combo.style().subControlRect(QtWidgets.QStyle.CC_ComboBox,option,
                                          QtWidgets.QStyle.SC_ComboBoxEditField,combo)
        text_rect=field.adjusted(option.iconSize.width()+6,0,0,0)
        painted=combo.grab().toImage().copy(text_rect)
        original=combo.initStyleOption
        def blank(option):
            original(option)
            option.currentText=''
        with mock.patch.object(combo,'initStyleOption',side_effect=blank):
            empty=combo.grab().toImage().copy(text_rect)
        changed=sum(painted.pixel(x,y)!=empty.pixel(x,y)
                    for x in range(painted.width()) for y in range(painted.height()))
        assert changed>10,(locale,theme,changed,text_rect)


@pytest.mark.parametrize('locale',['ru','ar'])
def test_unavailable_compact_languages_keep_the_reason_in_help_and_the_saved_pair(window,app,locale):
    window.set_interface_language(locale)
    window.config.update(ocr_engine='Windows',translator_engine='google',
                         game_translate_source_language='en',game_translate_target_language='ru')
    window.show_settings()
    settings=window.settings_window
    with mock.patch('ocr.installed_ocr_language_codes',return_value=[]):
        settings._populate_game_language_controls()
    for combo in (settings.game_source_combo,settings.game_target_combo):
        assert not combo.isEnabled() and combo.currentData() is None
        option=QtWidgets.QStyleOptionComboBox()
        combo.initStyleOption(option)
        assert option.currentText=='—'
        assert len(combo.elided_value_tooltip())>len(combo.currentText())
    assert window.config['game_translate_source_language']=='en'
    assert window.config['game_translate_target_language']=='ru'
