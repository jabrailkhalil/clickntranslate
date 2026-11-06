"""Capture actions describe cancel/undo/stop and keep hints in the selected language."""
from unittest import mock

import pytest
from PyQt5 import QtCore
from PyQt5.QtTest import QTest

import dynamic_workspace as workspace
import game_mode
import ocr
from dynamic_templates import output_style, text
from test_dynamic_workspace import app, isolated


LANGUAGES = ('en', 'ru', 'es', 'de', 'fr', 'zh')


@pytest.mark.parametrize('language', LANGUAGES)
def test_selection_cancel_and_undo_have_distinct_action_labels(isolated, language):
    config, _ = isolated
    config['interface_language'] = language
    selector = workspace.PairedRegionSelector()
    try:
        assert selector.cancel_button.text() == '×'
        assert selector.cancel_button.toolTip() == game_mode.game_text(language, 'cancel_selection')
        assert selector.cancel_button.accessibleName() == selector.cancel_button.toolTip()
        assert selector.cancel_button.toolTip() != game_mode.game_text(language, 'close')
        assert selector.undo_button.accessibleName() == game_mode.game_text(language, 'undo_hint')
        assert selector.undo_button.width() >= selector.undo_button.sizeHint().width()
        for control, key in ((selector.source_combo, 'source_language'),
                             (selector.target_combo, 'target_language'),
                             (selector.swap_button, 'swap_languages')):
            assert control.toolTip() == ocr.ocr_ui_text(language, key)
            assert control.accessibleName() == control.toolTip()

        first, last = QtCore.QRect(30, 300, 140, 50), QtCore.QRect(230, 300, 140, 50)
        selector._regions = [first, last]
        selector._outputs = [QtCore.QRect(first), QtCore.QRect(last)]
        selector._styles = [output_style(), output_style()]
        selector._update_selection_controls()
        selector.undo_button.click()
        assert selector._regions == [first]  # Undo removes one selection, not the whole session.
        with mock.patch.object(game_mode, '_begin_game_session') as start:
            selector.cancel_button.click()
            assert not selector.isVisible()
            start.assert_not_called()
    finally:
        selector.close()


@pytest.mark.parametrize('language', LANGUAGES)
def test_session_controls_hint_the_current_pause_action_and_stop_session(isolated, language):
    config, _ = isolated
    config['interface_language'] = language
    overlay = workspace.PairedTranslationOverlay(QtCore.QRect(50, 50, 150, 80), 'en', 'ru',
        output_region=QtCore.QRect(300, 300, 200, 100))
    try:
        with mock.patch.object(game_mode, 'stop_game_mode') as stop:
            controls = workspace.OutputControls([overlay])
            assert controls.stop_button.toolTip() == game_mode.game_text(language, 'close')
            assert controls.stop_button.accessibleName() == controls.stop_button.toolTip()
            for paused in (True, False):
                controls.pause_button.click()
                key = 'resume' if paused else 'pause'
                assert overlay.paused == paused
                assert controls.pause_button.text() == controls.pause_button.toolTip() == game_mode.game_text(language, key)
                assert controls.pause_button.accessibleName() == controls.pause_button.toolTip()
            assert controls.save_button.accessibleName() == controls.save_button.toolTip() == text(language, 'save')
            assert controls.delete_button.accessibleName() == controls.delete_button.toolTip() == text(language, 'delete')
            assert controls.move_button.accessibleName() == controls.move_button.toolTip() == text(language, 'move')
            assert controls.resize_button.accessibleName() == controls.resize_button.toolTip() == text(language, 'resize')
            controls.stop_button.click()
            stop.assert_called_once()
    finally:
        overlay.close()


@pytest.mark.parametrize('language', LANGUAGES)
def test_ocr_language_roles_and_swap_have_localized_hints(isolated, language):
    config, _ = isolated
    config['interface_language'] = language
    overlay = ocr.ScreenCaptureOverlay('translate', defer_show=True)
    try:
        for control, key in ((overlay.lang_combo, 'source_language'),
                             (overlay.target_lang_combo, 'target_language'),
                             (overlay.translate_arrow_label, 'swap_languages')):
            assert control.toolTip() == control.accessibleName() == ocr.ocr_ui_text(language, key)
    finally:
        overlay.close()
        overlay.deleteLater()


@pytest.mark.parametrize('language', LANGUAGES)
def test_ocr_missing_language_dialog_uses_selected_interface_language(isolated, language):
    config, _ = isolated
    config['interface_language'] = language
    overlay = ocr.ScreenCaptureOverlay('translate', defer_show=True)
    try:
        overlay.lang_combo.clear()
        with mock.patch.object(ocr.QMessageBox, 'information') as dialog:
            QTest.mousePress(overlay, QtCore.Qt.LeftButton, pos=QtCore.QPoint(30, 300))
            QTest.mouseRelease(overlay, QtCore.Qt.LeftButton, pos=QtCore.QPoint(200, 400))
            dialog.assert_called_once_with(overlay, ocr.ocr_ui_text(language, 'language_packages'),
                                           ocr.ocr_ui_text(language, 'install_languages_first'))
    finally:
        overlay.close()
        overlay.deleteLater()


@pytest.mark.parametrize('language', ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id'))
def test_ocr_translation_error_dialog_uses_selected_interface_language(isolated, app, monkeypatch, language):
    import main
    from PyQt5 import sip

    config, _ = isolated
    config['interface_language'] = language
    monkeypatch.setattr(main, 'get_cached_config', lambda: config)
    history = mock.Mock()
    copy = mock.Mock()
    monkeypatch.setattr(main, 'save_translation_history', history)
    monkeypatch.setattr(ocr, 'save_translation_history', mock.Mock())
    monkeypatch.setattr(main.platform_support, 'copy_text', copy)
    created = []
    original_show = main.show_translation_dialog

    def show_result(*args, **kwargs):
        result = original_show(*args, **kwargs)
        created.append(result)
        return result

    overlay = ocr.ScreenCaptureOverlay('translate', defer_show=True)
    try:
        with (mock.patch('translater.translate_text', side_effect=[RuntimeError('engine failed'), 'Recovered translation']) as translate,
              mock.patch.object(main, 'show_translation_dialog', side_effect=show_result) as shown,
              mock.patch.object(overlay, 'close', wraps=overlay.close) as close_overlay,
              mock.patch.object(ocr.QMessageBox, 'warning') as warning):
            overlay.show()
            app.processEvents()
            assert overlay.isVisible()
            overlay.handle_ocr_result('Hello')
            for _ in range(200):
                if created and overlay._area_translation_worker is None:
                    break
                QTest.qWait(10)
            shown.assert_called_once()
            result = created[0]
            assert result.isVisible() and result.lang == language
            assert result.source_edit.toPlainText() == 'Hello'
            assert not result.source_edit.isReadOnly()
            assert result.source_panel.isVisible() and not result._source_collapsed
            assert result.text_edit.toPlainText() == ''
            assert result.source_code == 'en' and result.target_code == 'ru'
            assert result.engine_combo.currentData() == 'google'
            assert result.window_engine == config['translator_engine'] == 'Google'
            assert result._status_message == 'Google: ' + main.doc_text(language, 'provider_unavailable_online')
            assert result.status_label.isVisible() and result.status_label.toolTip()
            assert result.translate_button.isEnabled() and not result.copy_button.isEnabled()
            close_overlay.assert_called_once()
            assert not overlay.isVisible()
            assert not overlay._ocr_in_progress and overlay._area_translation_worker is None
            warning.assert_not_called()
            history.assert_not_called()
            copy.assert_not_called()

            result.translate_button.click()
            for _ in range(200):
                if result.text_edit.toPlainText() == 'Recovered translation' and not result._retranslating:
                    break
                QTest.qWait(10)
            assert translate.call_count == 2
            assert translate.call_args.args == ('Hello', 'en', 'ru')
            assert translate.call_args.kwargs['engine'] == 'google'
            assert result.source_edit.toPlainText() == 'Hello'
            assert result.text_edit.toPlainText() == 'Recovered translation'
            assert result.translate_button.isEnabled() and result.copy_button.isEnabled()
            assert result._status_message == result.text['ready']
            history.assert_called_once_with('Hello', 'Recovered translation', 'ru')
            warning.assert_not_called()
            copy.assert_not_called()
            assert config['translator_engine'] == 'Google'
    finally:
        for result in created:
            if not sip.isdeleted(result):
                result.close()
        overlay.close()
        overlay.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()
