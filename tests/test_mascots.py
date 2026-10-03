"""Asset, selection and capture lifecycle checks for the five companions."""
from pathlib import Path

import pytest
from PyQt5 import QtCore, QtGui
from PyQt5.QtTest import QTest

from assistant_art import MASCOTS, DEFAULT_MASCOT, APPEARANCES, companion_art, walking_art_path
from assistant_motion import skin
from assistant_settings import assistant_preferences
from test_desktop_ux import app, window
import mode_coordinator


@pytest.mark.parametrize('mascot', MASCOTS)
def test_each_character_has_transparent_rig_and_distinct_emotions(app, mascot):
    movie = QtGui.QMovie(walking_art_path(mascot))
    assert movie.isValid() and movie.frameCount() == 20
    images = []
    for index in range(20):
        assert movie.jumpToFrame(index)
        image = movie.currentImage()
        assert image.size() == QtCore.QSize(192, 192)
        assert image.pixelColor(0, 0).alpha() == 0
        assert movie.nextFrameDelay() == 50
        images.append(image)
    assert all(images[0] != image for image in images[1:])
    for pose in APPEARANCES[:-2]:
        image = companion_art(pose, mascot=mascot).toImage()
        assert not image.isNull() and image.hasAlphaChannel()
        assert image.pixelColor(0, 0).alpha() == 0
        assert image.pixelColor(image.width()-1, image.height()-1).alpha() == 0
    layers = skin(mascot)
    assert len(layers) == 16
    assert all(not p.isNull() and p.hasAlphaChannel() for p in layers.values())
    assert sum(p.width()*p.height()*4 for p in layers.values()) <= 4*1024*1024
    emotions = [companion_art(pose, mascot=mascot).toImage() for pose in APPEARANCES[:7]]
    assert all(emotions[a] != emotions[b] for a in range(7) for b in range(a+1, 7))


@pytest.mark.parametrize('invalid', [None, [], {}, 'removed-character', 23, True])
def test_unknown_character_keeps_legacy_pose_and_other_preferences(invalid):
    config = {'desktop_assistant_mascot': invalid, 'desktop_assistant_appearance': 'walking',
              'desktop_assistant_behavior': 'idle', 'desktop_assistant_size': 137}
    prefs = assistant_preferences(config)
    assert prefs['desktop_assistant_mascot'] == DEFAULT_MASCOT
    assert prefs['desktop_assistant_appearance'] == 'walking'
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
    assert page.pose_combo.currentData() == 'portrait'
    page.toggle.click()
    assert window._desktop_assistant.anchor.appearance == 'portrait'


def test_switching_character_keeps_position_pause_and_capture_ownership(window, app):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    page.choose_appearance('walking')
    page.toggle.click()
    helper = window._desktop_assistant
    helper.anchor.move(220, 220)
    position = helper.anchor.pos()
    page.pause_walk.setChecked(True)
    for mascot in MASCOTS:
        page.mascot_combo.setCurrentIndex(page.mascot_combo.findData(mascot))
        assert window.config['desktop_assistant_mascot'] == mascot
        assert helper.anchor.mascot == mascot
        assert helper.anchor.motion.mascot == mascot
        assert helper.anchor.pos() == position
        assert not helper.anchor._animation.isActive()
    mode_coordinator.request_mode('mascot-test', lambda: None)
    try:
        page.choose_mascot('bubu')
        page.pause_walk.setChecked(False)
        assert not helper.anchor.isVisible()
        assert not helper.anchor._animation.isActive()
    finally:
        mode_coordinator.release_mode('mascot-test')
    assert helper.anchor.isVisible()
    assert helper.anchor._animation.isActive()
    window.show_main_screen()
    app.processEvents()
    assert window.assistant_preview.mascot == 'bubu'
    assert window.assistant_preview.art is skin('bubu')


def test_character_choice_before_enable_and_after_custom_image(window, tmp_path):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    page.choose_mascot('mochi')
    assert getattr(window, '_desktop_assistant', None) is None
    page.choose_appearance('sleep_alt')
    page.choose_mascot('orbit')
    assert window.config['desktop_assistant_appearance'] == 'sleep_alt'
    custom = tmp_path / 'image.png'
    companion_art('portrait').save(str(custom))
    window.config['desktop_assistant_image'] = str(custom)
    page.choose_appearance('custom')
    page.choose_mascot('momo')
    assert window.config['desktop_assistant_appearance'] == 'portrait'
    assert window.config['desktop_assistant_image'] == str(custom)
    page.toggle.click()
    assert window._desktop_assistant.anchor.mascot == 'momo'


def test_dropdown_has_all_characters_and_supports_keyboard(window, app):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    combo = page.mascot_combo
    assert tuple(combo.itemData(i) for i in range(combo.count())) == MASCOTS
    assert all(not combo.itemIcon(i).isNull() for i in range(combo.count()))
    combo.showPopup()
    app.processEvents()
    view = combo.view()
    for index in range(combo.count()):
        assert view.viewport().rect().contains(view.visualRect(combo.model().index(index, 0)))
    combo.hidePopup()
    QTest.keyClick(combo, QtCore.Qt.Key_Down)
    assert combo.currentData() == 'mochi'
    assert window.config['desktop_assistant_mascot'] == 'mochi'
