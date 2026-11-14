"""Real menu clicks must not swap a character to a smaller generated body."""
from pathlib import Path
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

from assistant_art import MASCOTS
from assistant_motion import PetMotion, paint_pet
from assistant_settings import ASSISTANT_ACTIONS, LEGACY_DEFAULT_ACTIONS, normalized_assistant_actions
from assistant_text import ASSISTANT_TEXT, assistant_action_text
from desktop_assistant import AssistantMenu, FOREGROUND_ACTIONS
from test_desktop_assistant import app, companion


def render(mascot, action='idle', time=0., state_time=0., gaze=None):
    image = QtGui.QImage(192, 208, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    paint_pet(painter, QtCore.QRectF(0, 0, 192, 208), mascot,
              action=action, time=time, state_time=state_time, gaze=gaze)
    painter.end()
    return image


def test_full_legacy_menu_gets_new_modes_but_custom_and_empty_choices_survive():
    assert normalized_assistant_actions(LEGACY_DEFAULT_ACTIONS) == list(ASSISTANT_ACTIONS)
    assert normalized_assistant_actions(['open', 'copy', 'guide']) == ['open', 'copy']
    assert normalized_assistant_actions([]) == []
    assert 'guide' not in ASSISTANT_ACTIONS


@pytest.mark.parametrize('language', tuple(ASSISTANT_TEXT))
def test_new_modes_have_real_localized_labels_and_explanations(language):
    for action in ('selection', 'replace'):
        title, description = assistant_action_text(language, action)
        assert title and description and title != action
        if language != 'en':
            assert (title, description) != assistant_action_text('en', action)


@pytest.mark.parametrize('mascot', [value for value in MASCOTS if value != 'click'])
def test_open_menu_and_hover_hold_the_same_body_without_replaying_poses(companion, mascot):
    companion.owner.config['desktop_assistant_mascot'] = mascot
    companion.owner.config['desktop_assistant_appearance'] = 'animated'
    companion.refresh()
    companion.anchor.motion.gesture = ''
    companion.anchor.motion.time = 2.
    resting = companion.anchor.grab().toImage()
    companion.toggle_menu()
    assert companion.menu.isVisible()
    assert companion.anchor.motion.action() == 'idle'
    idle = companion.anchor.grab().toImage()
    a = QtGui.QRegion(QtGui.QPixmap.fromImage(resting).mask()).boundingRect()
    b = QtGui.QRegion(QtGui.QPixmap.fromImage(idle).mask()).boundingRect()
    assert abs(a.height()-b.height()) <= 2
    assert abs(a.bottom()-b.bottom()) <= 1
    for seconds in (2.1, 3.3, 5.5, 8., 12.):
        companion.anchor.motion.time = seconds
        companion.anchor.motion.status_age = seconds
        companion.anchor.motion.gesture_age = seconds
        assert companion.anchor.grab().toImage() == idle
    for angle in range(0, 360, 22):
        # Hover is now intentional gaze, but the same direction never replays
        # the body/gesture animation while the menu is open.
        assert render(mascot, time=2., gaze=angle) == render(mascot, time=8., gaze=angle)


@pytest.mark.parametrize('mascot', [value for value in MASCOTS if value != 'click'])
def test_blink_is_rare_and_does_not_change_the_body_envelope(mascot):
    resting = render(mascot, time=1.)
    for seconds in (2., 3., 5., 10., 13.):
        assert render(mascot, time=seconds) == resting
    blinking = render(mascot, time=13.9)
    if mascot != 'orbit':
        assert blinking != resting
    a = QtGui.QRegion(QtGui.QPixmap.fromImage(resting).mask()).boundingRect()
    b = QtGui.QRegion(QtGui.QPixmap.fromImage(blinking).mask()).boundingRect()
    assert abs(a.width() - b.width()) <= 2
    assert abs(a.height() - b.height()) <= 2
    assert abs(a.bottom() - b.bottom()) <= 1
    assert render(mascot, time=14.2) == resting


def test_resting_animation_clock_does_not_queue_repaints_for_unchanged_frames(companion):
    companion.owner.config.update(desktop_assistant_mascot='pancake', desktop_assistant_appearance='animated')
    companion.refresh()
    companion.anchor.motion.gesture = ''
    companion.anchor.motion.time = 2.
    with mock.patch.object(companion.anchor, 'update') as update:
        for _ in range(30):
            companion.anchor._advance(.08)
    update.assert_not_called()
    assert companion.anchor._animation.interval() == 80


def test_activity_changes_remeasure_the_menu_without_clipping_its_footer(app):
    menu = AssistantMenu('de', True, factor=1.33)
    bounds = QtCore.QRect(-640, 0, 640, 480)
    try:
        menu.open_beside(QtCore.QRect(-100, 350, 84, 84), bounds)
        for activity in ('busy', 'error', 'idle'):
            menu.set_activity(activity)
            app.processEvents()
            assert bounds.contains(menu.geometry())
            for action in ('settings', 'hide'):
                button = menu.buttons[action]
                assert menu.rect().contains(QtCore.QRect(button.mapTo(menu, QtCore.QPoint()), button.size()))
    finally:
        menu.close()
        menu.deleteLater()


@pytest.mark.parametrize('action,method', [('selection', 'launch_translate_selection'), ('replace', 'launch_translate_replace_selection')])
def test_selection_modes_restore_external_focus_before_dispatch(companion, app, action, method):
    assert action in FOREGROUND_ACTIONS
    companion._selection_target = 123
    order = []
    getattr(companion.owner, method).side_effect = lambda **_kwargs: order.append('dispatch')
    with mock.patch.object(companion, '_remember_foreground'), \
            mock.patch.object(companion, '_restore_foreground', side_effect=lambda: order.append('restore') or True) as restore:
        companion.request_action(action)
        restore.assert_called_once()
        assert order == ['restore']
        # A persistent panel keeps the external selection focused. Dispatch
        # runs on the next Qt turn and needs no capture-surface hide delay.
        app.processEvents()
    assert order == ['restore', 'dispatch']
    getattr(companion.owner, method).assert_called_once_with(expected_target=123)


def test_unsupported_linux_replacement_is_clear_and_never_dispatched(companion):
    with mock.patch('desktop_assistant.sys.platform', 'linux'):
        companion.toggle_menu()
        assert not companion.menu.buttons['replace'].isEnabled()
        assert companion.menu.buttons['replace'].toolTip()
        companion.request_action('replace')
        assert not companion._dispatch_timer.isActive()
        companion.owner.launch_translate_replace_selection.assert_not_called()


@pytest.mark.parametrize('locale', tuple(ASSISTANT_TEXT))
@pytest.mark.parametrize('dark', (True, False))
def test_menu_renderer_keeps_all_actions_reachable_with_consistent_edges(app, locale, dark):
    menu = AssistantMenu(locale, dark)
    try:
        bounds = QtCore.QRect(-640, 0, 640, 480)
        menu.open_beside(QtCore.QRect(-100, 350, 84, 84), bounds)
        for _ in range(3):
            app.processEvents()
        assert bounds.contains(menu.geometry())
        assert menu.buttons['open'].width() > menu.buttons['area'].width() * 1.8
        assert 'guide' not in menu.buttons
        assert menu.layoutDirection() == (QtCore.Qt.RightToLeft if locale == 'ar' else QtCore.Qt.LeftToRight)
        for action in ASSISTANT_ACTIONS:
            button = menu.buttons[action]
            menu.scroll.ensureWidgetVisible(button)
            app.processEvents()
            assert menu.scroll.viewport().rect().intersects(QtCore.QRect(
                button.mapTo(menu.scroll.viewport(), QtCore.QPoint()), button.size()))
            for label in button.findChildren(QtWidgets.QLabel):
                assert label.height() >= label.heightForWidth(label.width())
        menu.scroll.verticalScrollBar().setValue(0)
        if locale in ('ru', 'ar'):
            out = Path('.tmp/companion-calm-images')
            out.mkdir(parents=True, exist_ok=True)
            assert menu.grab().save(str(out / f'menu-{locale}-{dark}.png'))
    finally:
        menu.close()
        menu.deleteLater()
