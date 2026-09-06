"""Check the rendered controls across real windows, including Qt inheritance."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QPalette
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QPushButton, QToolButton, QWidget

import main
from button_styles import button_palette, button_qss
from qt_layout_test_support import ensure_layout_fonts
from styled_dialogs import StyledMessageBox


@pytest.fixture
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setQuitOnLastWindowClosed(False)
    ensure_layout_fonts(instance)
    return instance


@pytest.mark.parametrize("dark", [True, False])
@pytest.mark.parametrize("button_type", [QPushButton, QToolButton])
def test_mouse_click_clears_the_ring_but_tab_focus_remains_visible(app, dark, button_type):
    owner = QWidget()
    owner.resize(160, 80)
    button = button_type(owner)
    button.setText("×")
    button.setGeometry(12, 12, 32, 32)
    button.setFocusPolicy(Qt.StrongFocus)
    button.setStyleSheet(button_qss(dark, "quiet", selector=button_type.__name__, icon=True))
    try:
        owner.show()
        app.processEvents()
        button.clearFocus()
        button.setFocus(Qt.TabFocusReason)
        app.processEvents()
        assert button.property("keyboardFocus") is True
        focus = button_palette(dark)["focus"]
        assert button.grab().toImage().pixelColor(0, 16).name() == focus
        QTest.mouseClick(button, Qt.LeftButton)
        app.processEvents()
        assert not button.property("keyboardFocus")
        assert button.grab().toImage().pixelColor(0, 16).name() != focus
        # Moving the pointer away must not reveal a lingering focus outline.
        app.sendEvent(button, QEvent(QEvent.Leave))
        assert button.grab().toImage().pixelColor(0, 16).name() != focus
    finally:
        owner.close()
        owner.deleteLater()


@pytest.mark.parametrize("theme", ["Темная", "Светлая"])
def test_primary_and_secondary_actions_match_across_windows(app, theme):
    owner = QWidget()
    owner.current_theme = theme
    colors = button_palette(theme != "Светлая")
    installer = main.ArgosPackageInstallDialog(owner, "RU → EN", "ru", theme)
    result = main.TranslationResultDialog(
        owner, "Пример перевода", auto_copy=False, lang="ru", theme=theme, source_text="Example",
    )
    message = StyledMessageBox(owner)
    accept = message.addButton("Установить", message.AcceptRole)
    cancel = message.addButton("Отмена", message.RejectRole)
    groups = (
        (colors["accent"], [installer.install_button, result.translate_button, accept]),
        (colors["surface"], [installer.cancel_button, result.copy_button, result.close_button, cancel]),
    )
    try:
        for window in (installer, result, message):
            window.show()
        app.processEvents()
        for expected, buttons in groups:
            for button in buttons:
                button.clearFocus()
                app.sendEvent(button, QEvent(QEvent.Leave))
                assert button.font().pixelSize() == 13
                assert button.palette().color(QPalette.Button).name() == expected
                assert button.width() >= button.sizeHint().width(), button.text()
                # The fill must also survive each window's stylesheet cascade.
                rendered = button.grab().toImage()
                assert rendered.pixelColor(button.width() // 2, 5).name() == expected
                before = button.geometry()
                button.setFocus(Qt.TabFocusReason)
                button.setEnabled(False)
                app.processEvents()
                assert button.geometry() == before
                assert button.palette().color(QPalette.Disabled, QPalette.Button).name() == colors["disabled_surface"]
    finally:
        for window in (installer, result, message, owner):
            window.close()
            window.deleteLater()
        app.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.mark.parametrize("theme", ["Темная", "Светлая"])
def test_destructive_confirmation_keeps_its_role_when_default(app, theme):
    owner = QWidget()
    owner.current_theme = theme
    box = StyledMessageBox(owner)
    remove = box.addButton("Удалить", box.DestructiveRole)
    box.setDefaultButton(remove)
    box.addButton("Отмена", box.RejectRole)
    try:
        box.show()
        app.processEvents()
        colors = button_palette(theme != "Светлая")
        assert remove.palette().color(QPalette.ButtonText).name() == colors["danger"]
        assert remove.palette().color(QPalette.Button).name() == colors["surface"]
        assert remove.font().pixelSize() == 13
        assert box.buttonRole(remove) == box.DestructiveRole
    finally:
        box.close()
        owner.close()
