"""The home mascot uses the same prompt-and-settings flow as hotkey rows."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import main
from assistant_text import assistant_text
from test_desktop_ux import app, window


@pytest.mark.parametrize('language', ('en', 'ru', 'es', 'de', 'fr', 'zh'))
@pytest.mark.parametrize('accept', (False, True))
def test_mascot_caption_and_real_prompt_navigate_only_after_accepting(window, app, language, accept):
    window.set_interface_language(language)
    window.show_main_screen()
    app.processEvents()
    preview = window.assistant_preview
    button = preview.button
    assert isinstance(button, main.HotkeyReferenceRow)
    assert button.caption_label.text() == assistant_text(language, 'companion_section')
    assert button.caption_label.x() < button.value_label.x()
    assert button.value_label.pixmap() is not None
    assert button.caption_label.sizeHint().width() <= button.caption_label.width()
    reference = window.main_hotkey_references['game']
    assert button.caption_label.styleSheet() == reference.caption_label.styleSheet()
    window.text_input.setPlainText('Unsent draft')
    observed = {}
    original_exec = main.QMessageBox.exec_

    def execute_prompt(box):
        primary = next(button for button in box.findChildren(QtWidgets.QPushButton)
                       if box.buttonRole(button) == main.QMessageBox.AcceptRole)
        cancel = next(button for button in box.findChildren(QtWidgets.QPushButton)
                      if box.buttonRole(button) == main.QMessageBox.RejectRole)

        def choose():
            observed.update(title=box.windowTitle(), visible=box.isVisible(),
                            primary=primary.text(), cancel=cancel.text(),
                            fits=primary.fontMetrics().horizontalAdvance(primary.text()) <= primary.width() - 12)
            (primary if accept else cancel).click()

        QtCore.QTimer.singleShot(0, choose)
        return original_exec(box)

    with mock.patch.object(main.QMessageBox, 'exec_', execute_prompt):
        button.click()
    app.processEvents()
    assert observed == dict(title=assistant_text(language, 'companion_section'), visible=True,
                           primary=assistant_text(language, 'preview_open_settings'),
                           cancel=main.hotkey_settings_prompt_text(language, 'cancel'), fits=True)
    if accept:
        assert window.settings_window.settings_assistant_page.isVisible()
        assert window.settings_window.settings_assistant_page.mascot_preview.next_button.hasFocus()
    else:
        assert window.settings_window is None
        assert window.text_input.toPlainText() == 'Unsent draft'
        assert preview.isVisible()
    assert not preview.timer.isActive()


@pytest.mark.parametrize('mascot', ('click', 'orbit', 'pancake', 'mochi', 'bubu', 'momo'))
def test_home_companion_is_recognizable_without_animation_or_full_atlas_cache(window, app, mascot):
    preview = window.assistant_preview
    preview.show()
    preview.set_mascot(mascot)
    app.processEvents()
    thumbnail = preview.button.value_label.pixmap()
    assert thumbnail is not None and not thumbnail.isNull()
    assert max(thumbnail.width(), thumbnail.height()) >= 18
    assert thumbnail.devicePixelRatio() >= 2
    assert thumbnail.height()/thumbnail.devicePixelRatio() <= preview.button.value_label.height()
    assert preview.button.height() == window.main_hotkey_references['game'].height()
    assert preview.height() == preview.button.height()
    assert preview.rect().contains(preview.button.geometry())
    assert not preview.timer.isActive()


def test_closing_mascot_prompt_keeps_the_main_window(window, app):
    original_exec = main.QMessageBox.exec_

    def close_prompt(box):
        QtCore.QTimer.singleShot(0, box.close)
        return original_exec(box)

    with mock.patch.object(main.QMessageBox, 'exec_', close_prompt):
        window.assistant_preview.button.click()
    assert window.settings_window is None
