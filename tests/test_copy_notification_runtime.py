"""Copy feedback through the actual app widgets, with an isolated clipboard."""
from unittest import mock
from types import SimpleNamespace

import pytest
from PyQt5 import QtCore, QtWidgets, sip
from PyQt5.QtTest import QTest

import main
from settings_window import settings_text
from ui_scaling import widget_global_rect
from test_desktop_ux import app, window


def settle(app):
    for _ in range(5):
        app.processEvents()


@pytest.fixture
def runtime(window, app, monkeypatch):
    window.config.update(notifications=True, copy_translated_text=False)
    monkeypatch.setattr(main, 'get_cached_config', lambda: window.config)
    monkeypatch.setattr(main.threading, 'Thread', mock.Mock())
    monkeypatch.setattr(main, 'save_translation_history', mock.Mock())
    # Unlike the general layout fixture's simulated large desktop, a native
    # Tool window is rendered by Qt's actual platform screen. Keep both the
    # source and its feedback on that real 800x600 offscreen desktop.
    window.set_ui_scale_percent(80)
    window.move(40, 80)
    window.activateWindow()
    app.setActiveWindow(window)
    settle(app)
    yield window
    window._copy_notice.hide()
    window._status_label.hide()


@pytest.mark.parametrize('locale', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
@pytest.mark.parametrize('dark', [True, False])
def test_notification_toggle_previews_its_real_location_without_copying(runtime, app, isolated_clipboard, locale, dark):
    runtime.set_interface_language(locale)
    if (runtime.current_theme != 'Светлая') != dark:
        runtime.toggle_theme()
    runtime.show_settings()
    settings = runtime.settings_window
    settings._set_settings_page(4)
    settle(app)
    checkbox = settings.copy_notification_checkbox
    isolated_clipboard.setText('previous contents')
    checkbox.setChecked(False)
    assert not runtime._copy_notice.isVisible()
    checkbox.click()
    settle(app)
    popup = runtime._copy_notice
    assert popup.isVisible()
    assert settings_text(locale, 'copy_notification_preview') in popup.text()
    assert main.TRANSLATION_RESULT_DIALOG_TEXT[locale]['copied'] not in popup.text()
    assert isolated_clipboard.text() == 'previous contents'
    main.threading.Thread.assert_not_called()
    assert widget_global_rect(runtime).contains(popup.geometry())
    assert popup._dismiss.interval() == 3000
    assert popup.width() >= popup.sizeHint().width(), (locale, popup.text())
    assert popup.height() >= popup.sizeHint().height(), (locale, popup.text())
    assert popup.windowFlags() & QtCore.Qt.WindowDoesNotAcceptFocus
    assert popup.windowType() == QtCore.Qt.Tool
    # The offscreen backend marks shown Tool windows active even with native
    # no-activation flags. The Windows probe separately checks actual focus.
    if app.platformName() != 'offscreen':
        assert not popup.isActiveWindow()
    assert not popup.grab().isNull()
    checkbox.click()
    assert not popup.isVisible()


@pytest.mark.parametrize('enabled', [False, True])
def test_real_main_copy_button_delivers_feedback_but_translation_alone_does_not(runtime, app, isolated_clipboard, enabled):
    runtime.config['notifications'] = enabled
    runtime._present_main_translation_result('Перевод', 'Source', 'en', 'ru')
    settle(app)
    assert not runtime._copy_notice.isVisible()
    runtime.main_result_copy_button.click()
    settle(app)
    assert isolated_clipboard.text() == 'Перевод'
    assert runtime._copy_notice.isVisible() is enabled
    if enabled:
        assert widget_global_rect(runtime).contains(runtime._copy_notice.geometry())


def test_copy_confirmation_is_independent_of_hover_tooltip_setting(runtime, app, isolated_clipboard):
    previous = app.property('buttonTooltipsEnabled')
    try:
        runtime.config['button_tooltips_enabled'] = False
        app.setProperty('buttonTooltipsEnabled', False)
        runtime._show_inline_main_result('Result', 'Source', 'en', 'ru')
        runtime.main_result_copy_button.click()
        settle(app)
        assert isolated_clipboard.text() == 'Result'
        assert runtime._copy_notice.isVisible()
    finally:
        app.setProperty('buttonTooltipsEnabled', previous)


def test_real_result_copy_button_notifies_inside_the_result_window(runtime, app, isolated_clipboard):
    dialog = main.TranslationResultDialog(runtime, 'ترجمة', auto_copy=False, lang='ar',
                                        source_text='Source', source_lang='en', target_lang='ar')
    legacy_close = dialog.close_button
    try:
        dialog.show()
        dialog.activateWindow()
        app.setActiveWindow(dialog)
        settle(app)
        dialog.copy_button.click()
        settle(app)
        assert isolated_clipboard.text() == 'ترجمة'
        assert runtime._copy_notice.isVisible()
        assert widget_global_rect(dialog).contains(runtime._copy_notice.geometry())
    finally:
        dialog.close()
        dialog.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        assert sip.isdeleted(legacy_close)


def test_history_copy_button_notifies_without_creating_another_history_entry(runtime, app, isolated_clipboard):
    runtime.show_settings()
    with mock.patch('history_storage.read_records', return_value=[{'text': 'Recorded text'}]):
        runtime.settings_window.show_copy_history_view()
        settle(app)
    buttons = runtime.settings_window.findChildren(QtWidgets.QPushButton, 'historyCopyButton')
    button = next(button for button in buttons if button.isVisible())
    app.setActiveWindow(runtime)
    button.click()
    settle(app)
    assert isolated_clipboard.text() == 'Recorded text'
    assert runtime._copy_notice.isVisible()
    main.threading.Thread.assert_not_called()


@pytest.mark.parametrize('target', ['main', 'result', 'history', 'hidden-main'])
def test_failed_clipboard_write_never_announces_success_or_records_a_copy(runtime, app, monkeypatch, target):
    monkeypatch.setattr(main.platform_support, 'copy_text', lambda _text: False)
    dialog = None
    try:
        if target == 'main':
            runtime._show_inline_main_result('Result', 'Source', 'en', 'ru')
            runtime.main_result_copy_button.click()
        elif target == 'result':
            dialog = main.TranslationResultDialog(runtime, 'Result', auto_copy=False)
            dialog.show()
            dialog.copy_button.click()
            assert dialog._status_message == dialog.text['copy_failed']
        elif target == 'history':
            runtime.show_settings()
            with mock.patch('history_storage.read_records', return_value=[{'text': 'Recorded text'}]):
                runtime.settings_window.show_copy_history_view()
                settle(app)
            next(button for button in runtime.settings_window.findChildren(
                QtWidgets.QPushButton, 'historyCopyButton') if button.isVisible()).click()
        else:
            runtime.config['result_window_hidden_modes'] = ['main']
            runtime._present_main_translation_result('Result', 'Source', 'en', 'ru')
            assert runtime._main_result_snapshot['translated_text'] == 'Result'
        settle(app)
        assert runtime._copy_notice.isVisible()
        assert runtime._copy_notice.text() == main.TRANSLATION_RESULT_DIALOG_TEXT[runtime.current_interface_language]['copy_failed']
        assert '✓' not in runtime._copy_notice.text()
        main.threading.Thread.assert_not_called()
    finally:
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()


@pytest.mark.parametrize('mode', ['selection', 'replacement'])
def test_clipboard_only_selection_failure_keeps_the_finished_translation(runtime, app, monkeypatch, mode):
    from test_translation_result_ui import _SelectionHarness, _immediate_thread
    harness = _SelectionHarness({'result_window_hidden_modes': ['selection']})
    user32 = SimpleNamespace(keybd_event=mock.Mock())
    with (mock.patch.multiple(main.platform_support, IS_WINDOWS=True, IS_MAC=False, IS_LINUX=False),
          mock.patch.object(main.ctypes, 'windll', SimpleNamespace(user32=user32), create=True),
          mock.patch.object(main.threading, 'Thread', _immediate_thread),
          mock.patch.object(main.time, 'sleep'),
          mock.patch.object(main, 'simulate_copy'),
          mock.patch.object(main.pyperclip, 'paste', return_value='Source'),
          mock.patch.object(main, '_windows_foreground_window', return_value=42),
          mock.patch.object(main, 'replace_selected_text_in_foreground', return_value=(False, 'focus_changed')),
          mock.patch('translater.translate_text', return_value='Result'),
          mock.patch.object(main.platform_support, 'copy_text', side_effect=lambda value: value == ''),
          mock.patch.object(main, 'save_copy_history') as history):
        (harness.launch_translate_replace_selection if mode == 'replacement'
         else harness.launch_translate_selection)()
    assert len(harness.shown_dialogs) == 1
    assert harness.shown_dialogs[0][0] == 'Result'
    assert harness.shown_dialogs[0][1] is False
    assert main.TRANSLATION_RESULT_DIALOG_TEXT['en']['copy_failed'] in harness.statuses
    history.assert_not_called()
    settle(app)
    assert runtime._copy_notice.text() == main.TRANSLATION_RESULT_DIALOG_TEXT['en']['copy_failed']
    assert runtime._copy_notice.isVisible()


def test_clipboard_only_area_failure_keeps_result_in_the_existing_window(runtime, app, monkeypatch):
    import ocr
    owner = SimpleNamespace(close=mock.Mock(), hide=mock.Mock())
    dialog = mock.Mock(text={'copy_failed': 'Copy failed'})
    config = dict(runtime.config, result_window_hidden_modes=['area'])
    with (mock.patch.object(ocr, 'get_cached_ocr_config', return_value=config),
          mock.patch.object(main.platform_support, 'copy_text', return_value=False),
          mock.patch.object(main, 'show_translation_dialog', return_value=dialog) as show,
          mock.patch.object(main, 'save_copy_history') as copy_history,
          mock.patch.object(ocr, 'save_translation_history') as history):
        assert ocr.ScreenCaptureOverlay._present_area_translation(owner, 'Source', 'Result', 'en', 'ar') is True
    assert show.call_args.kwargs['auto_copy'] is False
    dialog._set_status.assert_called_once_with('Copy failed')
    history.assert_called_once_with('Source', 'Result', 'ar')
    copy_history.assert_not_called()
    settle(app)
    assert runtime._copy_notice.isVisible()
    assert '✓' not in runtime._copy_notice.text()


@pytest.mark.parametrize('failed', [False, True])
def test_queued_feedback_is_discarded_when_its_owner_shuts_down(window, app, failed):
    probe = main.DarkThemeApp(background_services=False)
    probe.show()
    popup = probe._copy_notice
    try:
        from copy_feedback import emit_copy_feedback
        assert emit_copy_feedback('en', failed=failed) is True
        probe.force_quit = True
        probe.close()
        probe.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        settle(app)
        assert sip.isdeleted(probe)
        assert sip.isdeleted(popup)
        assert emit_copy_feedback('en', failed=failed) is False
    finally:
        if not sip.isdeleted(probe):
            probe.force_quit = True
            probe.close()
            probe.deleteLater()


def test_copy_only_status_timeout_cannot_outlive_its_owner(window, app, monkeypatch):
    probe = main.DarkThemeApp(background_services=False)
    probe.show()
    probe.config['result_window_hidden_modes'] = ['main']
    monkeypatch.setattr(main, 'get_cached_config', lambda: probe.config)
    monkeypatch.setattr(main, 'save_translation_history', mock.Mock())
    monkeypatch.setattr(main, 'save_copy_history', mock.Mock())
    monkeypatch.setattr(main.platform_support, 'copy_text', lambda _text: True)
    probe._present_main_translation_result('Result', 'Source', 'en', 'ru')
    timer = probe._status_dismiss
    assert timer.isActive()
    probe.force_quit = True
    probe.close()
    probe.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert sip.isdeleted(timer)
    # The old singleShot held pyqtBoundSignal.emit after native owner deletion.
    # Pump past that timeout to verify no callback can access the dead QObject.
    QTest.qWait(1350)
