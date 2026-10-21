"""Asset, selection and capture lifecycle checks for the six companions."""
from pathlib import Path

import pytest
from PyQt5 import QtCore, QtGui
from PyQt5.QtTest import QTest

from assistant_art import MASCOTS, DEFAULT_MASCOT, APPEARANCES, companion_art, walking_art_path
from assistant_motion import skin
from assistant_text import assistant_text
from assistant_settings import assistant_preferences
from test_desktop_ux import app, window
import mode_coordinator


@pytest.mark.parametrize('mascot', MASCOTS)
def test_each_character_has_transparent_atlas_and_distinct_emotions(app, mascot):
    for pose in APPEARANCES[:-2]:
        image = companion_art(pose, mascot=mascot).toImage()
        assert not image.isNull() and image.hasAlphaChannel()
        assert image.pixelColor(0, 0).alpha() == 0
        assert image.pixelColor(image.width()-1, image.height()-1).alpha() == 0
    artwork = skin(mascot)
    assert artwork.pixmap.size() == QtCore.QSize(1536, 2288)
    directions = [artwork.source(gaze=angle)[1] for angle in range(0, 360, 90)]
    assert len({(r.x(), r.y()) for r in directions}) == 4
    emotions = [companion_art(pose, mascot=mascot).toImage() for pose in APPEARANCES[:7]]
    assert all(emotions[a] != emotions[b] for a in range(7) for b in range(a+1, 7))


@pytest.mark.parametrize('invalid', [None, [], {}, 'removed-character', 23, True])
def test_unknown_character_keeps_legacy_pose_and_other_preferences(invalid):
    config = {'desktop_assistant_mascot': invalid, 'desktop_assistant_appearance': 'walking',
              'desktop_assistant_behavior': 'idle', 'desktop_assistant_size': 137}
    prefs = assistant_preferences(config)
    assert prefs['desktop_assistant_mascot'] == DEFAULT_MASCOT
    assert prefs['desktop_assistant_appearance'] == 'animated'
    assert prefs['desktop_assistant_behavior'] == 'idle'
    assert prefs['desktop_assistant_size'] == 137
    assert config['desktop_assistant_mascot'] == invalid


def test_removed_appearance_falls_back_to_new_character(window):
    window.config['desktop_assistant_appearance'] = 'orb'
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    prefs = assistant_preferences(window.config)
    assert prefs['desktop_assistant_appearance'] == 'portrait'
    assert prefs['desktop_assistant_mascot'] == DEFAULT_MASCOT
    assert 'orb' not in page.appearance_buttons
    assert page.mode_combo.currentData() == 'portrait'
    page.toggle.click()
    assert window._desktop_assistant.anchor.appearance == 'portrait'


def test_switching_character_keeps_position_pause_and_capture_ownership(window, app):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    page.choose_appearance('animated')
    page.toggle.click()
    helper = window._desktop_assistant
    helper.anchor.move(220, 220)
    position = helper.anchor.pos()
    for mascot in MASCOTS:
        page.choose_mascot(mascot)
        assert window.config['desktop_assistant_mascot'] == mascot
        assert helper.anchor.mascot == mascot
        assert helper.anchor.motion.mascot == mascot
        assert helper.anchor.pos() == position
        assert helper.anchor._animation.isActive()
        position = helper.anchor.pos()
        helper.anchor._advance(.1)
        assert helper.anchor.pos() == position
    mode_coordinator.request_mode('mascot-test', lambda: None)
    try:
        page.choose_mascot('bubu')
        assert not helper.anchor.isVisible()
        assert not helper.anchor._animation.isActive()
    finally:
        mode_coordinator.release_mode('mascot-test')
    assert helper.anchor.isVisible()
    assert helper.anchor._animation.isActive()
    window.show_main_screen()
    app.processEvents()
    assert window.assistant_preview.mascot == 'bubu'
    from assistant_preview import preview_art
    assert window.assistant_preview.art is preview_art('bubu')


def test_character_choice_before_enable_and_after_custom_image(window, tmp_path):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    page.choose_mascot('mochi')
    assert getattr(window, '_desktop_assistant', None) is None
    page.choose_appearance('waiting')
    page.choose_mascot('orbit')
    assert window.config['desktop_assistant_appearance'] == 'waiting'
    custom = tmp_path / 'image.png'
    companion_art('portrait').save(str(custom))
    window.config['desktop_assistant_image'] = str(custom)
    page.choose_appearance('custom')
    page.choose_mascot('momo')
    assert window.config['desktop_assistant_appearance'] == 'portrait'
    assert window.config['desktop_assistant_image'] == str(custom)
    page.toggle.click()
    assert window._desktop_assistant.anchor.mascot == 'momo'


def test_stage_arrows_cycle_all_characters_wrap_and_accept_keyboard(window, app):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    stage = page.mascot_preview
    assert not hasattr(page, 'mascot_combo')
    for mascot in MASCOTS:
        stage.next_button.click()
        assert window.config['desktop_assistant_mascot'] == stage.mascot == mascot
        assert stage.accessibleName() == assistant_text(window.current_interface_language, mascot)
    stage.next_button.setFocus(QtCore.Qt.TabFocusReason)
    QTest.keyClick(stage.next_button, QtCore.Qt.Key_Right)
    assert stage.mascot == 'pancake'
    QTest.keyClick(stage.next_button, QtCore.Qt.Key_Left)
    assert stage.mascot == 'click'
    stage.previous_button.click()
    assert stage.mascot == 'orbit'
    # The first global Qt animation tick can be delayed by font/atlas work in
    # a complete suite. Wait for completion with a bound, not one exact frame.
    elapsed = QtCore.QElapsedTimer()
    elapsed.start()
    while stage.transition.state() != QtCore.QAbstractAnimation.Stopped and elapsed.elapsed() < 2000:
        QTest.qWait(20)
    assert stage.transition.state() == QtCore.QAbstractAnimation.Stopped
    assert stage._previous_layer is None
    assert stage._progress == 1


@pytest.mark.parametrize('theme', ['Светлая', 'Темная'])
def test_carousel_moves_platform_and_name_then_settles_and_stops_when_hidden(window, app, theme):
    window.current_theme = theme
    window.show_assistant_settings()
    stage = window.settings_window.settings_assistant_page.mascot_preview
    app.processEvents()
    stage.next_button.click()
    assert stage.transition.state() == QtCore.QAbstractAnimation.Running
    start = stage.grab().toImage()
    stage.transition.setCurrentTime(stage.TRANSITION_MS//2)
    middle = stage.grab().toImage()
    assert start != middle
    stage.next_button.click()  # A rapid second click starts from the current composition.
    assert stage.mascot == 'mochi'
    window.show_main_screen()
    assert stage.transition.state() == QtCore.QAbstractAnimation.Stopped
    assert stage._previous_layer is None
    assert not stage.timer.isActive()
    window.show_assistant_settings()
    assert stage.mascot == 'mochi' and stage._progress == 1


@pytest.mark.parametrize('language', ['ru', 'en', 'de', 'es', 'fr', 'zh'])
def test_settings_use_one_left_checkbox_column_and_aligned_right_fields(window, app, language):
    window.current_interface_language = language
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    app.processEvents()
    checks = (page.main_visible, page.toggle, page.topmost)
    fields = (page.mode_combo, page.values['size'], page.values['opacity'])
    assert len({checkbox.mapTo(page, QtCore.QPoint()).x() for checkbox in checks}) == 1
    assert len({field.mapTo(page, QtCore.QPoint()).x() for field in fields}) == 1
    assert len({field.width() for field in fields}) == 1
    for checkbox, field in zip(checks, fields):
        left = QtCore.QRect(checkbox.mapTo(page, QtCore.QPoint()), checkbox.size())
        right = QtCore.QRect(field.mapTo(page, QtCore.QPoint()), field.size())
        assert left.right() < right.left()
        assert abs(left.center().y()-right.center().y()) <= 1
        assert page.rect().contains(left) and page.rect().contains(right)


@pytest.mark.parametrize('theme', ['Светлая', 'Темная'])
def test_preview_stage_is_themed_reacts_to_clicks_and_stops_when_hidden(window, app, theme):
    from assistant_motion import notify_activity
    window.current_theme = theme
    window.show_assistant_settings()
    stage = window.settings_window.settings_assistant_page.mascot_preview
    app.processEvents()
    image = stage.grab().toImage()
    assert image.pixelColor(10, 10) != image.pixelColor(10, image.height()-10)
    assert stage.timer.isActive()
    QTest.mouseClick(stage, QtCore.Qt.LeftButton)
    assert stage.motion.action() == 'success'
    notify_activity(window, 'busy')
    assert stage.motion.action() == 'work'
    QTest.mouseClick(stage, QtCore.Qt.LeftButton)
    assert stage.motion.action() == 'work'
    assert all(motion.action() == 'work' for motion in window.assistant_preview.motions.values())
    window.show_main_screen()
    app.processEvents()
    assert not stage.timer.isActive()


def test_selected_main_character_opens_settings_without_a_desktop_menu(window, app):
    window.set_desktop_assistant_enabled(True)
    helper = window._desktop_assistant
    for mascot in MASCOTS:
        window.config['desktop_assistant_mascot'] = mascot
        window.show_main_screen()
        app.processEvents()
        rail = window.assistant_preview
        assert tuple(rail.buttons) == (mascot,)
        rail.buttons[mascot].click()
        app.processEvents()
        assert window.settings_window.settings_assistant_page.isVisible()
        assert helper.menu is None
        assert rail._choice_dialog is None
