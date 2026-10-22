"""Missing local translation components lead to setup, never a silent fallback."""
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import main
import translater
import translation_availability as availability
from test_desktop_ux import app, window


@pytest.fixture
def missing_models(monkeypatch):
    monkeypatch.setattr(translater, 'argos_installed_translation_pairs_fast', lambda: set())
    monkeypatch.setattr(translater, 'hymt_installed', lambda: False)


def test_ready_checks_use_the_requested_pair_and_never_load_native_models(missing_models, monkeypatch):
    monkeypatch.setattr(translater, '_ensure_argos_available', mock.Mock(side_effect=AssertionError('native import')))
    monkeypatch.setattr(translater, '_run_argos_worker_request', mock.Mock(side_effect=AssertionError('worker probe')))
    monkeypatch.setattr(translater, 'argos_installed_translation_pairs_fast', lambda: {('en', 'ru')})
    assert availability.missing_provider('argos', 'en', 'ru') is None
    assert availability.missing_provider('argos', 'ru', 'en').engine == 'argos'
    assert availability.missing_provider('Hy-MT', 'en', 'ru').engine == 'hymt'
    assert availability.missing_provider('google', 'en', 'ru') is None
    assert availability.missing_provider('argos', 'ru', 'ru') is None


@pytest.mark.parametrize('language', ('en', 'ru', 'es', 'de', 'fr', 'zh'))
@pytest.mark.parametrize('download', (False, True))
def test_real_recovery_prompt_fits_and_lists_only_ready_choices(app, missing_models, language, download):
    from styled_dialogs import StyledMessageBox
    parent = QtWidgets.QWidget()
    parent.current_interface_language = language
    parent.current_theme = 'Темная' if download else 'Светлая'
    original_exec = StyledMessageBox.exec_
    observed = {}

    def choose(box):
        combo = next(widget for widget in box.findChildren(QtWidgets.QComboBox))

        def click():
            buttons = [button for button in box.findChildren(QtWidgets.QPushButton)
                       if box.buttonRole(button) != box.InvalidRole]
            observed.update(engines=[combo.itemData(i) for i in range(combo.count())],
                            fits=all(box.rect().contains(QtCore.QRect(button.mapTo(box, QtCore.QPoint()), button.size()))
                                     and button.fontMetrics().horizontalAdvance(button.text()) <= button.width() - 12
                                     for button in buttons), visible=box.isVisible())
            next(button for button in buttons if button.text() == availability.recovery_text(language, 'use')).click()
        QtCore.QTimer.singleShot(0, click)
        return original_exec(box)

    try:
        with mock.patch.object(StyledMessageBox, 'exec_', choose):
            selected = availability.offer_provider_recovery(parent, availability.MissingProvider('argos', 'en', 'ru'),
                                                            main.TRANSLATION_PROVIDER_OPTIONS, language,
                                                            allow_download=download)
        assert selected == 'google'
        assert observed == dict(engines=['google', 'mymemory', 'lingva', 'libretranslate'], fits=True, visible=True)
    finally:
        parent.close()
        parent.deleteLater()


@pytest.mark.parametrize('engine', ('argos', 'hymt'))
@pytest.mark.parametrize('choice', (None, 'install', 'google'))
def test_result_setup_preserves_drafts_until_a_ready_provider_is_explicitly_chosen(window, app, missing_models, engine, choice):
    window.config['translator_engine'] = 'lingva'
    dialog = main.TranslationResultDialog(window, 'Previous translation', auto_copy=False,
                                         source_text='Unsent draft', source_lang='en', target_lang='ru')
    dialog.set_window_engine(engine)
    dialog.show()
    jobs = []
    opener = mock.Mock(return_value=None)
    try:
        with (mock.patch.object(availability, 'offer_provider_recovery', return_value=choice),
              mock.patch.object(main, '_open_translation_packages', opener),
              mock.patch.object(main.threading, 'Thread', side_effect=lambda target, **kw: SimpleNamespace(start=lambda: jobs.append(target)))):
            dialog._start_retranslate()
        assert dialog.source_edit.toPlainText() == 'Unsent draft'
        assert dialog.text_edit.toPlainText() == 'Previous translation'
        assert window.config['translator_engine'].lower() == 'lingva'
        assert len(jobs) == (1 if choice == 'google' else 0)
        if choice == 'install':
            opener.assert_called_once_with(dialog, engine, 'en', 'ru')
        elif choice is None:
            assert 'href="install"' in dialog.status_label.text()
            assert availability.recovery_text('ru', 'install') in dialog.status_label.text()
            opener.assert_not_called()
        else:
            assert dialog.engine_combo.currentData() == 'google'
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize('stale', (False, True))
def test_worker_missing_component_only_prompts_for_its_current_draft(window, app, stale, monkeypatch):
    from translation_availability import OfflineProviderUnavailable
    dialog = main.TranslationResultDialog(window, 'Keep result', auto_copy=False,
                                         source_text='Keep source', source_lang='en', target_lang='ru')
    dialog.set_window_engine('Argos')
    jobs = []
    monkeypatch.setattr(availability, 'missing_provider', lambda *args: None)
    try:
        with (mock.patch.object(main.threading, 'Thread', side_effect=lambda target, **kw: SimpleNamespace(start=lambda: jobs.append(target))),
              mock.patch.object(translater, 'translate_text', side_effect=OfflineProviderUnavailable('argos', 'en', 'ru', 'missing worker', component='runtime')),
              mock.patch.object(availability, 'offer_provider_recovery', return_value=None) as prompt):
            dialog._start_retranslate()
            if stale:
                dialog.source_edit.setPlainText('Newer draft')
            jobs.pop()()
        assert prompt.call_count == (0 if stale else 1)
        assert dialog.text_edit.toPlainText() == 'Keep result'
        assert dialog.source_edit.toPlainText() == ('Newer draft' if stale else 'Keep source')
        if not stale:
            assert availability._RUNTIME['ru'] in dialog._status_message
            assert 'href="install"' in dialog.status_label.text()
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize('engine', ('argos', 'hymt'))
def test_install_link_opens_the_matching_package_tab(window, app, engine):
    import settings_window
    with (mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_argos_catalog_refresh'),
          mock.patch.object(settings_window.QtCore.QTimer, 'singleShot')):
        manager = main._open_translation_packages(window, engine, 'en', 'ru')
    assert manager.tabs.currentWidget() is manager.translation_section_page
    table = manager.argos_table if engine == 'argos' else manager.hymt_table
    assert manager.translation_tabs.currentWidget() is table.parentWidget()
    if engine == 'argos':
        assert manager._requested_argos_pair == ('en', 'ru')
    manager.close()


@pytest.mark.parametrize('choice', (None, 'install', 'lingva'))
def test_settings_missing_provider_does_not_persist_an_unusable_choice(window, app, missing_models, choice):
    source = window.config['main_translation_source_language']
    target = window.config['main_translation_target_language']
    window.show_settings()
    settings = window.settings_window
    with (mock.patch.object(availability, 'offer_provider_recovery', return_value=choice),
          mock.patch.object(settings, 'show_ocr_language_manager') as install):
        settings.translator_combo.setCurrentIndex(settings.translator_combo.findData('argos'))
    expected = 'lingva' if choice == 'lingva' else 'google'
    assert window.config['translator_engine'].lower() == expected
    assert settings.translator_combo.currentData() == expected
    if choice == 'install':
        install.assert_called_once_with('argos', source, target)
    else:
        install.assert_not_called()


def test_settings_only_host_does_not_start_other_background_services(app, monkeypatch):
    monkeypatch.setattr(main, 'LAYOUT_EDITOR_MODE', False)
    monkeypatch.setattr(main.DarkThemeApp, 'save_config', mock.Mock())
    with (mock.patch.object(main, 'WelcomeDialog') as welcome,
          mock.patch.object(main, 'HotkeyListenerThread') as listeners,
          mock.patch.object(main.DarkThemeApp, 'create_tray_icon') as tray,
          mock.patch.object(main.DarkThemeApp, 'sync_autostart_state') as autostart):
        host = main.DarkThemeApp(background_services=False)
    try:
        welcome.assert_not_called()
        listeners.assert_not_called()
        tray.assert_not_called()
        autostart.assert_not_called()
        assert not host.has_tray()
    finally:
        host.force_quit = True
        host.close()
        host.deleteLater()


def test_missing_selection_warns_even_before_text_is_entered(window, app, missing_models):
    dialog = main.TranslationResultDialog(window, '', auto_copy=False,
                                         source_text='', source_lang='en', target_lang='ru')
    try:
        with mock.patch.object(availability, 'offer_provider_recovery', return_value=None) as prompt:
            dialog.engine_combo.setCurrentIndex(dialog.engine_combo.findData('argos'))
        prompt.assert_called_once()
        assert dialog.status_label.textFormat() == QtCore.Qt.RichText
    finally:
        dialog.close()
        dialog.deleteLater()


def test_document_missing_provider_keeps_existing_text_and_provider_local(window, app, missing_models):
    dialog = main.DocumentTranslationDialog(window)
    dialog.original_view.setPlainText('Document draft')
    dialog.translated_view.setPlainText('Old document translation')
    dialog._populate_provider_combo('argos')
    try:
        with mock.patch.object(availability, 'offer_provider_recovery', return_value=None) as prompt:
            dialog._start_translation('Document draft')
        prompt.assert_called_once()
        assert not dialog.translation_running
        assert dialog.original_view.toPlainText() == 'Document draft'
        assert dialog.translated_view.toPlainText() == 'Old document translation'
        assert window.config['translator_engine'].lower() == 'google'
    finally:
        dialog.close()
        dialog.deleteLater()


def test_cached_hymt_paths_do_not_claim_deleted_models_are_ready(tmp_path, monkeypatch):
    model = tmp_path / 'model.gguf'
    runner = tmp_path / 'runner'
    model.write_text('fixture')
    runner.write_text('fixture')
    monkeypatch.setattr(translater, '_get_hymt_runtime', lambda: dict(model=str(model), runner=str(runner)))
    assert translater.hymt_installed()
    model.unlink()
    assert not translater.hymt_installed()
    with pytest.raises(availability.OfflineProviderUnavailable) as error:
        translater._hymt_translate_chunk('Hi', 'en', 'ru')
    assert error.value.issue.engine == 'hymt'


def test_main_argos_choices_can_open_setup_or_switch_explicitly(window, app, missing_models):
    with (mock.patch.object(availability, 'offer_provider_recovery', return_value='install'),
          mock.patch.object(main, '_open_translation_packages') as install):
        assert not window._confirm_argos_package_install('EN→RU')
    install.assert_called_once_with(window, 'argos', 'en', 'ru')
    with (mock.patch.object(availability, 'offer_provider_recovery', return_value='lingva'),
          mock.patch.object(window, 'translate_input_text') as retry):
        assert not window._confirm_argos_package_install('EN→RU')
    assert window.config['translator_engine'] == 'lingva'
    retry.assert_called_once()


def test_result_setup_link_is_owned_while_installation_is_open(window, app):
    dialog = main.TranslationResultDialog(window, 'Keep this', source_text='Draft')
    installer = QtWidgets.QWidget(window)
    installer.show()
    dialog._provider_settings_window = installer
    try:
        assert dialog._has_owned_popup()
    finally:
        installer.close()
        dialog.close()
        dialog.deleteLater()


def test_main_worker_missing_runtime_offers_recovery_and_keeps_the_draft(window, app):
    window.text_input.setPlainText('Unsent main draft')
    jobs = []
    error = availability.OfflineProviderUnavailable('argos', 'en', 'ru', 'worker missing', component='runtime')
    with (mock.patch.object(main.threading, 'Thread', side_effect=lambda target, **kw: SimpleNamespace(start=lambda: jobs.append(target))),
          mock.patch.object(translater, 'translate_text', side_effect=error),
          mock.patch.object(availability, 'offer_provider_recovery', return_value=None) as prompt):
        window._start_main_translation('Unsent main draft', 'en', 'ru', 'argos')
        jobs.pop()()
    prompt.assert_called_once()
    assert not window._main_translation_running
    assert window.text_input.toPlainText() == 'Unsent main draft'


def test_standalone_install_link_creates_a_services_free_settings_host(app, monkeypatch):
    import settings_window
    origin = QtWidgets.QWidget()
    monkeypatch.setattr(main, '_main_window_ref', None)
    with (mock.patch.object(QtWidgets.QApplication, 'topLevelWidgets', return_value=[]),
          mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_argos_catalog_refresh'),
          mock.patch.object(settings_window.QtCore.QTimer, 'singleShot')):
        manager = main._open_translation_packages(origin, 'argos', 'en', 'ru')
    host = origin._translation_settings_host
    try:
        assert not host._background_services
        assert not host.has_tray()
        assert manager.translation_tabs.currentWidget() is manager.argos_table.parentWidget()
    finally:
        manager.close()
        host.close()
        origin.close()
        origin.deleteLater()
