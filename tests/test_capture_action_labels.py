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


@pytest.mark.parametrize('language', LANGUAGES)
def test_ocr_translation_error_dialog_uses_selected_interface_language(isolated, language):
    config, _ = isolated
    config['interface_language'] = language
    overlay = ocr.ScreenCaptureOverlay('translate', defer_show=True)
    try:
        with mock.patch('translater.translate_text', side_effect=RuntimeError('engine failed')):
            with mock.patch.object(ocr.QMessageBox, 'warning') as dialog:
                assert not overlay._handle_ocr_result_inner('Hello')
                dialog.assert_called_once_with(None, ocr.ocr_ui_text(language, 'translation_failed'), 'engine failed')
    finally:
        overlay.close()
        overlay.deleteLater()
