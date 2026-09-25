"""Native hit targets, translucent tips and explicit static/walking companions."""
from unittest import mock
import re

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import main
from assistant_settings import assistant_preferences
from test_desktop_ux import app, window
from test_window_appearance import appearance


@pytest.mark.parametrize('language', ['ru', 'en', 'de', 'fr', 'es', 'zh'])
@pytest.mark.parametrize('percent', [100, 150, 200])
@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
def test_welcome_skip_is_a_visible_opaque_click_target_after_language_change(app, appearance, language, percent, theme):
    appearance.refresh(percent=percent, theme=theme)
    owner = QtWidgets.QWidget()
    owner.current_interface_language = 'en'
    dialog = main.WelcomeDialog(owner)
    try:
        dialog.show()
        app.processEvents()
        old_card = dialog.findChild(QtWidgets.QFrame, 'welcomeCard')
        dialog.set_language(language)
        assert not old_card.isVisible()
        for _ in range(5):
            app.processEvents()
        button = dialog.skip_btn
        bounds = QtCore.QRect(button.mapTo(dialog, QtCore.QPoint()), button.size())
        assert dialog.rect().contains(bounds)
        assert dialog.childAt(bounds.center()) is button
        snapshot = dialog.grab().toImage()
        point = bounds.center() * snapshot.devicePixelRatio()
        assert snapshot.pixelColor(point).alpha() == 255
        QTest.mousePress(button, QtCore.Qt.LeftButton)
        app.processEvents()  # pending scaling must not eat the release
        QTest.mouseRelease(button, QtCore.Qt.LeftButton)
        assert dialog.result() == QtWidgets.QDialog.Accepted
        assert not dialog.isVisible() and not dialog.start_guide_requested
    finally:
        dialog.close()
        dialog.deleteLater()
        owner.deleteLater()


def test_main_composer_has_unified_frame_and_unframed_send_button(window, app):
    for theme in ('Темная', 'Светлая'):
        window.current_theme = theme
        window.apply_theme()
        app.processEvents()
        assert window.main_text_toolbar.parentWidget() is window.main_text_section
        for pane in (window.main_input_pane, window.main_result_pane):
            assert pane.parentWidget() is window.main_composer
        assert window.main_composer_divider.isVisible()
        assert 'QFrame#mainTextToolbar { background:transparent; border:0; }' in window.main_text_section.styleSheet()
        assert 'QFrame#mainInputPane, QFrame#mainResultPane { background:transparent; border:0; }' in window.main_composer.styleSheet()
        rules = re.findall(r'([^{}]+)\{([^{}]*)\}', window.translate_button.styleSheet())
        disabled = [body for selectors, body in rules
                    if any(selector.strip() == 'QPushButton:disabled' for selector in selectors.split(','))]
        assert disabled
        assert 'background:transparent' in disabled[-1] and 'border:0' in disabled[-1]
        assert window.main_input_pane.geometry().right() < window.main_result_pane.geometry().left()


def test_light_hover_tip_has_no_opaque_native_corners(app):
    import styled_dialogs
    owner = QtWidgets.QWidget()
    owner.current_theme = 'Светлая'
    button = QtWidgets.QPushButton('Hint', owner)
    layout = QtWidgets.QHBoxLayout(owner)
    layout.addWidget(button)
    old_theme = app.property('ui_theme')
    try:
        app.setProperty('ui_theme', 'Светлая')
        styled_dialogs.install_tooltip_style(app, False)
        owner.show()
        for text in ('A long explanatory hover tooltip that wraps onto multiple lines.', 'Short'):
            app.processEvents()
            QtWidgets.QToolTip.showText(button.mapToGlobal(QtCore.QPoint(10, 10)), text, button)
            QTest.qWait(40)
            tip = next(w for w in app.topLevelWidgets() if styled_dialogs._is_tooltip(w) and w.isVisible())
            assert tip.windowFlags() & QtCore.Qt.FramelessWindowHint
            assert tip.testAttribute(QtCore.Qt.WA_TranslucentBackground)
            snapshot = tip.grab().toImage()
            assert snapshot.pixelColor(0, 0).alpha() == 0
            assert snapshot.pixelColor(snapshot.width() - 1, 0).alpha() == 0
    finally:
        QtWidgets.QToolTip.hideText()
        QTest.qWait(300)
        owner.close()
        owner.deleteLater()
        app.setProperty('ui_theme', old_theme)
        styled_dialogs.install_tooltip_style(app)


@pytest.mark.parametrize('old_mode,new_appearance', [('idle', 'orb'), ('walk', 'walking'), ('sleep', 'sleep_icon'), ('look', 'orb'), ({}, 'orb')])
def test_legacy_companion_modes_migrate_without_fake_animation(old_mode, new_appearance):
    prefs = assistant_preferences({'desktop_assistant_appearance': 'animated', 'desktop_assistant_behavior': old_mode})
    assert prefs['desktop_assistant_appearance'] == new_appearance
    assert prefs['desktop_assistant_behavior'] in ('idle', 'walk')


def test_walking_sprite_stays_consistent_when_paused_and_ignores_hover_ticks(window, app):
    window.config.update(desktop_assistant_appearance='walking', desktop_assistant_behavior='walk')
    window.set_desktop_assistant_enabled(True)
    anchor = window._desktop_assistant.anchor
    anchor.move(200, 200)
    anchor.enterEvent(QtCore.QEvent(QtCore.QEvent.Enter))
    image, position = anchor.grab().toImage(), anchor.pos()
    anchor._advance(1.)
    assert anchor.pos() == position and anchor.grab().toImage() == image
    window._desktop_assistant.request_action('idle')
    assert anchor.grab().toImage() == image
    anchor.leaveEvent(QtCore.QEvent(QtCore.QEvent.Leave))
    assert not anchor._animation.isActive()
    window._desktop_assistant.request_action('walk')
    anchor._advance(.5)
    assert anchor.pos() != position
