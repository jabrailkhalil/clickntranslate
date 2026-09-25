"""Wrapped welcome copy must fit the actual platform's font metrics."""
import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import main
from test_ui_polish import app, owner


@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
@pytest.mark.parametrize('percent', [80, 150])
def test_welcome_tick_contrasts_after_shared_theme_and_scaling(app, owner, theme, percent):
    from window_appearance import install_window_appearance
    appearance = install_window_appearance(app, percent, theme)
    dialog = main.WelcomeDialog(owner)
    try:
        dialog.show()
        app.processEvents()
        dialog.checkbox.click()
        checkbox = dialog.checkbox
        option = QtWidgets.QStyleOptionButton()
        checkbox.initStyleOption(option)
        rect = checkbox.style().subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, option, checkbox)
        image = checkbox.grab().toImage()
        ratio = image.devicePixelRatio()
        lights = [image.pixelColor(round(x*ratio), round(y*ratio)).lightness()
                  for x in range(rect.left()+3, rect.right()-2)
                  for y in range(rect.top()+3, rect.bottom()-2)]
        assert sum(light > 230 for light in lights) >= 3
        assert sum(light < 150 for light in lights) >= 3
    finally:
        dialog.close()
        dialog.deleteLater()
        app.removeEventFilter(appearance)
        del app._dialog_appearance
        app.setProperty('ui_theme', None)
        appearance.deleteLater()


@pytest.mark.parametrize('language', ['en', 'ru', 'de', 'es', 'fr', 'zh'])
def test_welcome_can_grow_for_wrapped_copy(app, owner, language):
    owner.current_interface_language = language
    dialog = main.WelcomeDialog(owner)
    dialog.show()
    QTest.qWait(30)
    try:
        assert dialog.minimumHeight() < dialog.maximumHeight()
        for name in ('welcomeTitle', 'welcomeBody', 'welcomeSupport'):
            label = dialog.findChild(QtWidgets.QLabel, name)
            assert label is not None
            required = label.heightForWidth(label.width())
            assert label.height() >= required, (language, name, label.height(), required)
        card = dialog.findChild(QtWidgets.QFrame, 'welcomeCard')
        assert card.rect().contains(dialog.guide_btn.geometry())
        dialog.checkbox.setChecked(True)
        dialog.set_language('ru' if language != 'ru' else 'de')
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        QTest.qWait(30)
        assert dialog.checkbox.isChecked()
        for name in ('welcomeTitle', 'welcomeBody', 'welcomeSupport'):
            label = dialog.findChild(QtWidgets.QLabel, name)
            assert label.height() >= label.heightForWidth(label.width())
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize('language', ['en', 'ru', 'de', 'es', 'fr', 'zh'])
def test_welcome_invites_support_in_each_language(app, owner, language):
    owner.current_interface_language = language
    dialog = main.WelcomeDialog(owner)
    try:
        label = dialog.findChild(QtWidgets.QLabel, 'welcomeSupport')
        assert label.text() == main.welcome_text(language)['support']
        assert 'Telegram' in label.text() and 'GitHub' in label.text()
        assert dialog.github_btn.accessibleName() == main.welcome_text(language)['github']
    finally:
        dialog.close()
        dialog.deleteLater()
