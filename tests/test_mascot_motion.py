"""Check contact in screen coordinates, jelly hops, and real application events."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui

import main
from assistant_art import MASCOTS
from assistant_motion import PetMotion, STRIDE, foot_pose, paint_pet, skin, notify_activity
from test_desktop_ux import app, window


@pytest.mark.parametrize('extent', [60, 84, 150])
@pytest.mark.parametrize('speed', [20, 40, 100])
@pytest.mark.parametrize('facing', [-1, 1])
def test_contact_foot_stays_fixed_in_world_at_all_speeds_and_sizes(extent, speed, facing):
    pet = PetMotion('pancake')
    pet.reactions = False
    x, remainder = 200, 0.
    contacts = {}
    samples = 0
    for _ in range(300):
        remainder += pet.advance(.02, speed, extent)
        step = int(remainder)
        remainder -= step
        x += step * facing
        pet.moved(step, extent)
        for leg in (0, 1):
            offset, lift, planted = foot_pose(pet.phase, leg)
            cycle = int(pet.distance / STRIDE + leg * .5)
            if planted:
                world = x + facing * offset * extent / 128
                key = leg, cycle
                if key in contacts:
                    assert world == pytest.approx(contacts[key], abs=1e-8)
                    samples += 1
                contacts[key] = world
                assert lift == 0
            else:
                assert lift < 0
    assert samples > 150


def test_jelly_compresses_without_sliding_then_travels_in_flight():
    pet = PetMotion('bubu')
    pet.reactions = False
    distances = []
    for _ in range(100):
        distances.append(pet.advance(.01, 26, 128))
    assert sum(distances[:19]) == pytest.approx(0)
    assert sum(distances[83:]) == pytest.approx(0)
    assert sum(distances[20:80]) > 24
    assert sum(distances) == pytest.approx(26)


def render(mascot, **kwargs):
    canvas = QtGui.QImage(128, 128, QtGui.QImage.Format_ARGB32)
    canvas.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(canvas)
    paint_pet(painter, QtCore.QRectF(0, 0, 128, 128), mascot, **kwargs)
    painter.end()
    return canvas


def test_jelly_never_renders_limbs_and_hop_is_visible(app):
    poses = [render('bubu', action='walk', hop_phase=p) for p in (.0, .1, .5, .9)]
    assert all(poses[a] != poses[b] for a in range(4) for b in range(a+1, 4))
    wrong_limb = QtGui.QPixmap(200, 200)
    wrong_limb.fill(QtCore.Qt.red)
    replacement = {key: wrong_limb for key in ('foot-left', 'foot-right', 'arm-left', 'arm-right')}
    with mock.patch.dict(skin('bubu'), replacement):
        assert [render('bubu', action='walk', hop_phase=p) for p in (.0, .1, .5, .9)] == poses


@pytest.mark.parametrize('mascot', MASCOTS)
def test_busy_reactions_rest_and_sleep_have_intentional_transitions(mascot):
    pet = PetMotion(mascot)
    pet.set_activity('busy')
    for _ in range(250):
        assert pet.advance(.2, 40, 84) == 0
        assert pet.action() == 'work'
    assert pet.time > 49 and pet.quiet == 0
    pet.set_activity('success')
    assert pet.action() == 'success'
    for _ in range(16):
        pet.advance(.2, 40, 84)
    assert pet.action() == 'walk'
    pet.set_activity('error')
    assert pet.action() == 'error'
    for _ in range(230):
        pet.advance(.2, 40, 84)
    assert pet.action() == 'sleep'
    pet.interact()
    assert pet.action() == 'walk'
    pet.quiet = 6.5
    assert pet.action() == 'wave'
    pet.quiet = 8.5
    assert pet.action() == 'curious'
    pet.reactions = False
    pet.set_activity('busy')
    assert pet.action() == 'walk'


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


def test_emotion_selector_and_reaction_preference_persist(window):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    assert page.pose_combo.count() == 11
    page.choose_appearance('walking')
    page.show_category('static')
    page.pose_combo.activated.emit(0)
    assert window.config['desktop_assistant_appearance'] == 'portrait'
    page.pose_combo.setCurrentIndex(page.pose_combo.findData('thinking'))
    assert window.config['desktop_assistant_appearance'] == 'thinking'
    assert window.config['desktop_assistant_behavior'] == 'idle'
    page.choose_appearance('walking')
    page.reactions.setChecked(False)
    assert window.config['desktop_assistant_reactions'] is False
    page.toggle.click()
    assert window._desktop_assistant.anchor.motion.reactions is False
    assert window.assistant_preview.motion.reactions is False
