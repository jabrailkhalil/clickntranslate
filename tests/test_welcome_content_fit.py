"""Wrapped welcome copy must fit the actual platform's font metrics."""
import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import main
from test_ui_polish import app, owner


@pytest.mark.parametrize('language', ['en', 'ru', 'de', 'es', 'fr', 'zh'])
def test_welcome_can_grow_for_wrapped_copy(app, owner, language):
    owner.current_interface_language = language
    dialog = main.WelcomeDialog(owner)
    dialog.show()
    QTest.qWait(30)
    try:
        assert dialog.minimumHeight() < dialog.maximumHeight()
        for name in ('welcomeTitle', 'welcomeBody'):
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
        for name in ('welcomeTitle', 'welcomeBody'):
            label = dialog.findChild(QtWidgets.QLabel, name)
            assert label.height() >= label.heightForWidth(label.width())
    finally:
        dialog.close()
        dialog.deleteLater()
