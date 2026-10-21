"""Check whole-frame playback, state transitions and real application events."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui

import main
from assistant_art import MASCOTS
from assistant_motion import PetMotion, paint_pet, skin, notify_activity, notify_current_activity
from assistant_sprites import frame_index, look_index
from test_desktop_ux import app, window


def test_frame_cadence_and_clockwise_cardinal_selection():
    assert frame_index((100, 200, 300), 0) == 0
    assert frame_index((100, 200, 300), .1) == 1
    assert frame_index((100, 200, 300), .3) == 2
    assert frame_index((100, 200, 300), .6) == 0
    assert [look_index(a) for a in (0, 90, 180, 270, 360, -90)] == [0, 4, 8, 12, 0, 12]


@pytest.mark.parametrize('extent', [60, 84, 150])
@pytest.mark.parametrize('speed', [20, 40, 100])
def test_legacy_speed_and_size_never_move_the_pet(extent, speed):
    pet = PetMotion('pancake')
    pet.reactions = False
    distances = [pet.advance(.02, speed, extent) for _ in range(50)]
    assert sum(distances) == 0
    assert pet.walk_time == 0
    assert pet.advance(.1, speed, extent, locomotion=False) == 0
    assert pet.walk_time == 0


def render(mascot, **kwargs):
    canvas = QtGui.QImage(128, 128, QtGui.QImage.Format_ARGB32)
    canvas.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(canvas)
    paint_pet(painter, QtCore.QRectF(0, 0, 128, 128), mascot, **kwargs)
    painter.end()
    return canvas


@pytest.mark.parametrize('mascot', MASCOTS)
def test_whole_frames_animate_without_using_directional_gaits(app, mascot):
    poses = [render(mascot, action='wave', time=t) for t in (0., .15, .3, .45)]
    assert len({image.cacheKey() for image in poses}) == 4
    assert poses[0] != poses[1]
    assert render(mascot, action='walk') == render(mascot, action='idle')
    assert render(mascot, action='idle', facing=-1) == render(mascot, action='idle')
    assert skin(mascot) is skin(mascot)

def test_activity_clock_starts_at_first_frame_and_success_transitions_to_review():
    pet = PetMotion('click')
    pet.time = 103.3
    pet.set_activity('success')
    assert pet.seconds(pet.action()) == 0
    for _ in range(4):
        pet.advance(.21, 40, 84)
    assert pet.action() == 'review'
    assert pet.seconds('review') == pytest.approx(0)


def test_gui_activity_bridge_keeps_concurrent_sources_and_ignores_late_cancel(window):
    with mock.patch.object(main, '_main_window_ref', window):
        notify_current_activity('busy', 'ocr:one')
        notify_current_activity('busy', 'live:two')
        notify_current_activity('success', 'ocr:one')
        assert window._companion_activity == 'busy'
        notify_current_activity('error', 'live:two')
        assert window._companion_activity == 'error'
        notify_current_activity('idle', 'ocr:one', only_if_busy=True)
        assert window._companion_activity == 'error'


@pytest.mark.parametrize('result', ['success', 'error', 'cancel'])
def test_live_translation_drives_reactions_and_stale_results_cannot_replace_them(window, result):
    import game_mode
    import ocr
    with (mock.patch.object(main, '_main_window_ref', window),
          mock.patch.object(ocr, 'get_cached_ocr_config', return_value=dict(window.config)),
          mock.patch.object(game_mode, '_exclude_from_windows_capture', return_value=True),
          mock.patch.object(game_mode.threading, 'Thread')):
        overlay = game_mode.GameTranslationOverlay(QtCore.QRect(100, 100, 300, 100), 'en', 'ru')
        overlay._timer.stop()
        try:
            with mock.patch.object(overlay, '_target_is_active', return_value=True):
                overlay._start_translation('Hello')
                revision = overlay._revision
                assert window._companion_activity == 'busy'
                overlay._has_ocr_source = False
                if result == 'cancel':
                    overlay.close()
                else:
                    overlay._apply_translation(revision, 'Hello', 'Привет' if result == 'success' else '',
                                               'Unavailable' if result == 'error' else '')
                assert window._companion_activity == ('idle' if result == 'cancel' else result)
                overlay._apply_translation(revision - 1, 'Old text', '', 'Old failure')
                assert window._companion_activity == ('idle' if result == 'cancel' else result)
                assert not window._companion_jobs
        finally:
            overlay.close()


@pytest.mark.parametrize('mascot', MASCOTS)
def test_native_reactions_have_intentional_stationary_transitions(mascot):
    pet = PetMotion(mascot)
    pet.set_activity('busy')
    for _ in range(250):
        assert pet.advance(.2, 40, 84, locomotion=True) == 0
        assert pet.action() == 'work'
    assert not pet.play('jumping')  # Do not obscure an active translation.
    pet.set_activity('success')
    assert pet.action() == 'success'
    for _ in range(5): pet.advance(.2)
    assert pet.action() == 'review'
    for _ in range(11): pet.advance(.2)
    assert pet.action() == 'idle'
    pet.set_activity('error')
    assert pet.action() == 'error'
    for _ in range(230): pet.advance(.2)
    assert pet.action() == 'idle'  # No spontaneous walking, sleep or extra poses.
    pet.reactions = False
    pet.set_activity('busy')
    assert pet.action() == 'idle'
    pet.set_activity('idle')
    pet.greet()
    assert pet.action() == 'wave'  # Explicit clicks also work with auto reactions off.
    for _ in range(4): pet.advance(.2)
    assert pet.action() == 'idle'

def test_notifications_reach_both_pets_and_concurrent_jobs_hold_busy(window):
    window.config.update(desktop_assistant_appearance='walking', desktop_assistant_behavior='walk')
    window.set_desktop_assistant_enabled(True)
    notify_activity(window, 'busy')
    notify_activity(window, 'busy', 'document:1')
    notify_activity(window, 'success')
    anchor = window._desktop_assistant.anchor
    assert anchor.motion.action() == window.assistant_preview.motion.action() == 'work'
    position = anchor.pos()
    anchor._advance(.1)
    assert anchor.pos() == position
    notify_activity(window, 'error', 'document:1')
    assert anchor.motion.action() == window.assistant_preview.motion.action() == 'error'


@pytest.mark.parametrize('result', ['success', 'error', 'cancel'])
def test_main_translation_signals_drive_reactions_without_network(window, result):
    with mock.patch.object(main.threading, 'Thread'):
        window._start_main_translation('Hello', 'en', 'ru', 'google')
    assert window.assistant_preview.motion.action() == 'work'
    if result == 'cancel':
        window._argos_cancel_requested.set()
    window._finish_main_translation_state('Привет' if result == 'success' else None,
                                           error='Unavailable' if result != 'success' else '')
    assert window._companion_activity == ('idle' if result == 'cancel' else result)
    assert not window._companion_jobs


def test_document_translation_cancel_and_completion_drive_reactions(window, app):
    dialog = main.DocumentTranslationDialog(window)
    try:
        with mock.patch.object(main.threading, 'Thread'):
            dialog._start_translation('One page')
        assert window._companion_activity == 'busy'
        dialog._request_translation_cancel()
        assert window._companion_activity == 'idle'
        dialog._on_translation_done('', [])
        assert window._companion_activity == 'idle'
        with mock.patch.object(main.threading, 'Thread'):
            dialog._start_translation('Second page')
        with mock.patch.object(main, 'save_translation_history'):
            dialog._on_translation_done('Вторая страница', [])
        assert window._companion_activity == 'success'
    finally:
        dialog.close()
        dialog.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_display_mode_and_event_reactions_persist_without_manual_emotion_choices(window):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    assert tuple(page.mode_combo.itemData(i) for i in range(page.mode_combo.count())) == ('animated', 'portrait', 'custom')
    assert not hasattr(page, 'pose_combo')
    page.mode_combo.setCurrentIndex(page.mode_combo.findData('portrait'))
    assert window.config['desktop_assistant_appearance'] == 'portrait'
    page.mode_combo.setCurrentIndex(page.mode_combo.findData('animated'))
    page.reactions.setChecked(False)
    page.toggle.click()
    assert window.config['desktop_assistant_reactions'] is False
    assert window._desktop_assistant.anchor.motion.reactions is False
    assert all(not motion.reactions for motion in window.assistant_preview.motions.values())
    assert page.mascot_preview.motion.reactions is False

@pytest.mark.parametrize('state', ['idle', 'waving', 'jumping', 'running', 'waiting', 'review', 'failed'])
def test_explicit_native_reaction_plays_once_then_waits_for_menu_choice(state):
    pet = PetMotion('click')
    pet.menu_open = True
    assert pet.play(state)
    assert pet.seconds(pet.action()) == 0
    for _ in range(10): pet.advance(.2)
    assert pet.action() == 'waiting'
    pet.menu_open = False
    assert pet.action() == 'idle'
    assert not pet.play('sleep') and not pet.play('running-right')
