"""The two new UI languages must cover real workflows, not English fallbacks."""
import json
import os
from pathlib import Path
from unittest import mock

import pytest
from PyQt5 import QtCore,QtWidgets

import main
import settings_window
from assistant_text import ASSISTANT_TEXT,assistant_text
from control_hints import HINTS,LANGUAGES as HINT_LANGUAGES,control_hint
from dialog_text import LANGUAGES as DIALOG_LANGUAGES
from dynamic_templates import _COPY,text as dynamic_text
from guide_setup import GUIDE_SETUP_ORDER
from languages import LOCALIZED_LANGUAGE_NAMES,language_code_from_name,language_display_name
from settings_window import settings_export_payload,validated_import_settings
from tools.audit_locale_catalogs import audit,LOCALES
from test_desktop_ux import app,window


def test_all_ui_catalogs_include_new_locales_and_keep_formatting():
    result=audit(Path(main.__file__).resolve().parent)
    assert result['issues'] == []
    assert len(result['messages']) >= 1191
    assert set(main.INTERFACE_LANGUAGE_BY_CODE)==set(LOCALES)==set(DIALOG_LANGUAGES)==set(HINT_LANGUAGES)
    assert set(LOCALIZED_LANGUAGE_NAMES)==set(LOCALES)


def test_queued_package_probe_cannot_run_after_dialog_destruction(window,app):
    window.show_settings()
    with (mock.patch.object(settings_window.OcrLanguageManagerDialog,'_start_runtime_probe') as probe,
          mock.patch.object(settings_window.OcrLanguageManagerDialog,'_start_argos_catalog_refresh') as catalog):
        dialog=settings_window.OcrLanguageManagerDialog(window.settings_window)
        dialog.deleteLater()
        app.sendPostedEvents(None,QtCore.QEvent.DeferredDelete)
        app.processEvents()
        probe.assert_not_called();catalog.assert_not_called()


@pytest.mark.parametrize('locale,close,resume,still',[
    ('pt','Fechar','Continuar','Sem animação'),
    ('it','Chiudi','Riprendi','Senza animazione'),
])
def test_guides_hints_actions_and_names_are_localized(locale,close,resume,still):
    from dialog_text import _ACTIONS
    from game_mode import game_text
    assert _ACTIONS['Close'][DIALOG_LANGUAGES.index(locale)]==close
    assert assistant_text(locale,'mode_static')==still
    assert game_text(locale,'resume')==resume
    assert set(ASSISTANT_TEXT[locale])==set(ASSISTANT_TEXT['en'])
    for key in HINTS:
        assert control_hint(locale,key).strip()
        assert control_hint(locale,key)!=control_hint('en',key)
    for key in _COPY:
        assert dynamic_text(locale,key).strip()
    guide=main.guide_text(locale)
    assert tuple(action for action,_title,_body in guide['steps'])==GUIDE_SETUP_ORDER
    assert len(guide['steps'])==32
    english={action:(title,body) for action,title,body in main.guide_text('en')['steps']}
    for action,title,body in guide['steps']:
        assert body.strip() and body!=english[action][1],action
        assert title.strip()
    assert main.HELP_CONTENT[locale]!=main.HELP_CONTENT['en']
    for code in ('en','ru','pt','it','ky','kk'):
        name=language_display_name(code,locale)
        assert language_code_from_name(name,locale)==code
    for option in main.INTERFACE_LANGUAGE_OPTIONS:
        assert (Path(main.__file__).parent/'src'/option['icon']).is_file()


@pytest.mark.parametrize('locale',['pt','it'])
def test_new_interface_language_survives_export_import(locale):
    restored=validated_import_settings(settings_export_payload(dict(main.DEFAULT_CONFIG,
        interface_language=locale)),main.DEFAULT_CONFIG)
    assert main.normalize_interface_language(restored['interface_language'])==locale


@pytest.mark.parametrize('locale',['pt','it'])
def test_invalid_api_settings_have_localized_feedback(window,app,locale):
    from provider_settings import show_provider_settings,connection_text
    window.set_interface_language(locale);window.show_settings()
    with (mock.patch('provider_secrets.get_key',return_value=''),
          mock.patch.object(settings_window.OcrLanguageManagerDialog,'_start_runtime_probe'),
          mock.patch.object(settings_window.OcrLanguageManagerDialog,'_start_argos_catalog_refresh')):
        page=show_provider_settings(window.settings_window,'openai-compatible')
        try:
            page.address.setText('http://example.test/v1');page.model.setText('qa-model')
            assert page.save_profile() is False
            assert 'HTTPS' in page.status.text()
            assert not page.status.text().startswith('Use an')
            page.address.setText('https://example.test/v1');page.model.clear()
            assert page.save_profile() is False
            assert page.status.text()==connection_text(locale,8)
        finally:
            window.settings_window._language_manager_dialog.close()


@pytest.mark.parametrize('locale',['pt','it'])
def test_invalid_settings_import_has_localized_feedback(window,app,tmp_path,locale):
    window.set_interface_language(locale);window.show_settings()
    source=tmp_path/'invalid.json';source.write_text('{broken json',encoding='utf-8')
    with (mock.patch('settings_window.QtWidgets.QFileDialog.getOpenFileName',return_value=(str(source),'')),
          mock.patch('settings_window.QMessageBox.warning') as warning):
        window.settings_window.import_settings()
    message=warning.call_args.args[2]
    assert ('inválido' if locale=='pt' else 'non valido') in message
    assert 'Expecting property' not in message


@pytest.mark.parametrize('locale',['pt','it'])
def test_new_locale_pages_render_offscreen(window,app,locale):
    """Optional saved renders use the existing offscreen regression runner."""
    output=os.environ.get('CNT_LOCALE_SCREENSHOTS')
    folder=Path(output)/locale if output else None
    if folder:folder.mkdir(parents=True,exist_ok=True)
    window.set_interface_language(locale)
    for theme in ('Темная','Светлая'):
        if window.current_theme!=theme:window.toggle_theme()
        window.show_settings();settings=window.settings_window
        for index,name in ((0,'general'),(1,'translation'),(2,'mascot'),(3,'dynamic')):
            settings._set_settings_page(index);app.processEvents()
            assert settings.settings_pages.currentIndex()==index
            if folder:assert window.grab().save(str(folder/f'{name}-{theme}.png'))
        from provider_settings import show_provider_settings
        with (mock.patch('provider_secrets.get_key',return_value=''),
              mock.patch.object(settings_window.OcrLanguageManagerDialog,'_start_runtime_probe'),
              mock.patch.object(settings_window.OcrLanguageManagerDialog,'_start_argos_catalog_refresh')):
            page=show_provider_settings(settings);app.processEvents()
            assert page.isVisible()
            if folder:assert settings._language_manager_dialog.grab().save(str(folder/f'api-{theme}.png'))
            settings._language_manager_dialog.close()
    window._guide_active=True
    window._guide_step_index=GUIDE_SETUP_ORDER.index('selection_behavior')
    window._show_guide_step();app.processEvents();window._guide_step_timer.stop()
    if folder:assert window.grab().save(str(folder/'guide.png'))
    window._guide_active=False
