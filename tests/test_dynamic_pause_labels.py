"""Manual pause must not claim the target app lost focus."""
from types import SimpleNamespace, MethodType
from unittest import mock
import threading

import pytest
from PyQt5 import QtWidgets

import game_mode
from test_desktop_ux import app


LOCALES = tuple(game_mode.GAME_TEXT)


@pytest.mark.parametrize('locale', LOCALES)
def test_region_pause_uses_its_own_reason_without_changing_resume_or_activity(app, locale):
    button = QtWidgets.QToolButton()
    owner = SimpleNamespace(paused=False, language=locale, pause_button=button,
                            _set_status=mock.Mock())
    try:
        with mock.patch.object(game_mode, 'notify_current_activity') as activity:
            game_mode.GameTranslationOverlay._toggle_pause(owner)
            assert owner.paused
            owner._set_status.assert_called_once_with('paused_manual', active=False)
            assert button.toolTip() == game_mode.game_text(locale, 'resume')
            activity.assert_called_once_with('idle', f'live:{id(owner)}', only_if_busy=True)
            game_mode.GameTranslationOverlay._toggle_pause(owner)
            assert not owner.paused
            assert button.toolTip() == game_mode.game_text(locale, 'pause')
            assert owner._set_status.call_args == mock.call('waiting', active=True)
            assert activity.call_count == 1
    finally:
        button.deleteLater()


@pytest.mark.parametrize('locale', LOCALES)
def test_fullscreen_pause_caption_retains_cancel_and_resume_semantics(app, locale):
    button, label = QtWidgets.QPushButton(), QtWidgets.QLabel()
    owner = SimpleNamespace(paused=False, language=locale,
        controls=SimpleNamespace(pause_button=button, label=label),
        _settle_timer=mock.Mock(), _live=mock.Mock(), _translation_cancel=threading.Event(),
        _status='Previous text', _status_is_error=True, _blocks=['old'],
        _last_frame=('old',), _pending_lines=['old'], update=mock.Mock(), _scan_once=mock.Mock())
    owner._set_status = MethodType(game_mode.GameFullscreenOverlay._set_status, owner)
    try:
        with mock.patch.object(game_mode, 'notify_current_activity') as activity:
            game_mode.GameFullscreenOverlay._toggle_pause(owner)
            assert owner.paused and owner._translation_cancel.is_set()
            assert owner._blocks == [] and owner._pending_lines is None
            assert owner._status == '' and owner._status_is_error is False
            assert label.toolTip() == game_mode.game_text(locale, 'paused_manual')
            assert label.toolTip() != game_mode.game_text(locale, 'paused')
            assert button.text() == game_mode.game_text(locale, 'resume')
            owner._scan_once.assert_not_called()
            activity.assert_called_once_with('idle', f'live:{id(owner)}', only_if_busy=True)
            game_mode.GameFullscreenOverlay._toggle_pause(owner)
            assert not owner.paused
            assert button.text() == game_mode.game_text(locale, 'pause')
            owner._scan_once.assert_called_once_with()
            assert activity.call_count == 1
    finally:
        button.deleteLater()
        label.deleteLater()


@pytest.mark.parametrize('locale', LOCALES)
def test_region_pause_is_not_treated_as_a_new_translation_start(app, locale):
    status, dot = QtWidgets.QLabel(), QtWidgets.QLabel()
    owner = SimpleNamespace(language=locale, target_window=0, _has_shown_translation=False,
        _startup_frame_visible=True, status_label=status, status_dot=dot, card=mock.Mock(),
        update=mock.Mock(), _update_capture_shape=mock.Mock())
    try:
        game_mode.GameTranslationOverlay._set_status(owner, 'paused_manual', active=False)
        assert owner._startup_frame_visible is False
        assert status.text() == game_mode.game_text(locale, 'paused_manual')
        assert owner._diagnostic_status == 'paused_manual'
        owner.card.show.assert_not_called()
    finally:
        status.deleteLater()
        dot.deleteLater()
