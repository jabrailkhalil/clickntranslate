"""Companion names, menu settings and focus work consistently in every UI language."""
import re

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

import keyboard_navigation
from assistant_art import MASCOTS
from assistant_settings import ASSISTANT_ACTIONS, AssistantActionsDialog
from assistant_text import ASSISTANT_TEXT, COMPANION_NAMES, assistant_action_text, assistant_text
from desktop_assistant import AssistantMenu
from test_desktop_ux import app, window


def settle(app):
    for _ in range(4):
        app.processEvents()


@pytest.mark.parametrize('language', tuple(ASSISTANT_TEXT))
def test_all_active_companion_copy_exists_in_each_locale(language):
    keys = ('main_visible_short', 'enabled', 'topmost', 'reactions', 'reactions_hint',
            'display_mode', 'mode_animated', 'mode_static', 'display_mode_hint', 'size',
            'opacity', 'menu_buttons', 'menu_buttons_hint', 'menu_buttons_note',
            'change_image', 'choose_image', 'custom', 'custom_name', 'image_files', 'previous_mascot',
            'next_mascot', 'companion_settings', 'companion_section', 'close_menu',
            'activity_idle', 'activity_busy', 'activity_waiting', 'activity_success',
            'activity_error', 'tray_hide', 'settings', 'guide_hint')
    for key in keys:
        assert key in ASSISTANT_TEXT[language] and ASSISTANT_TEXT[language][key], (language, key)
    for action in ASSISTANT_ACTIONS:
        title, hint = assistant_action_text(language, action)
        assert title and hint and title != action and hint != action + '_hint', (language, action)


def test_companion_display_names_are_complete_and_use_native_scripts_consistently():
    assert set(COMPANION_NAMES) == set(MASCOTS)
    for values in COMPANION_NAMES.values():
        assert len(values) == len(ASSISTANT_TEXT)
        assert all(isinstance(value, str) and value.strip() for value in values)
    for language in ('zh', 'ar', 'hi'):
        for mascot in MASCOTS:
            name = assistant_text(language, mascot)
            assert not re.search('[a-zA-Z]', name), (language, mascot, name)
    assert assistant_text('fr', 'pancake') == 'Crêpe'
    assert assistant_text('fr', 'click') == 'Clic'
    assert assistant_text('fr', 'mochi') == 'Chester'  # Proper names keep their identity.
    assert len({assistant_text('zh', mascot) for mascot in MASCOTS}) == len(MASCOTS)


@pytest.mark.parametrize('language', tuple(ASSISTANT_TEXT))
def test_names_agree_between_main_shortcut_stage_and_desktop_menu(window, app, language):
    window.set_interface_language(language)
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(3)
    page = settings.settings_assistant_page
    settle(app)
    for mascot in MASCOTS:
        window.config['desktop_assistant_mascot'] = mascot
        page.refresh()
        preview = window.assistant_preview
        preview.set_mascot(mascot)
        expected = assistant_text(language, mascot)
        assert page.mascot_preview.accessibleName() == expected
        assert preview.button.toolTip().startswith(expected + ' — ')
        assert preview.button.accessibleName().startswith(expected + ' — ')
        menu = AssistantMenu(language, True, mascot=mascot)
        try:
            assert any(label.text() == expected for label in menu.findChildren(QtWidgets.QLabel))
        finally:
            menu.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('keyboard', [False, True])
def test_opening_menu_preferences_uses_focus_reason_of_the_actual_input_method(window, app, keyboard):
    keyboard_navigation.install_keyboard_navigation(app)
    navigation = app._keyboard_navigation
    navigation.keyboard = keyboard
    dialog = AssistantActionsDialog(window)
    try:
        dialog.open()
        settle(app)
        assert dialog.focusWidget() is dialog.checkboxes['open']
        ring = getattr(dialog, '_keyboard_focus_ring', None)
        assert bool(ring is not None and ring.isVisible()) is keyboard
    finally:
        dialog.close()
        dialog.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        navigation.keyboard = False


def test_closing_menu_preferences_before_deferred_focus_does_not_reopen_or_focus_them(window, app):
    dialog = AssistantActionsDialog(window)
    dialog.open()
    dialog.close()
    settle(app)
    assert not dialog.isVisible()
    dialog.deleteLater()


@pytest.mark.parametrize('language', ['en', 'ru', 'fr', 'zh', 'ar', 'hi'])
def test_custom_art_uses_a_neutral_title_and_leaving_it_restores_character_name(window, app, tmp_path, language):
    window.set_interface_language(language)
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(3)
    page = settings.settings_assistant_page
    picture = tmp_path/'own-companion.png'
    image = QtGui.QImage(8, 8, QtGui.QImage.Format_ARGB32)
    image.fill(QtGui.QColor('#a8c0e4'))
    assert image.save(str(picture))
    window.config['desktop_assistant_mascot'] = 'orbit'
    window.config['desktop_assistant_image'] = str(picture)
    page.choose_appearance('custom')
    settle(app)
    own_name = assistant_text(language, 'custom_name')
    assert page.mascot_preview.accessibleName() == own_name
    assert window.assistant_preview.button.toolTip().startswith(own_name + ' — ')
    assert window.config['desktop_assistant_mascot'] == 'orbit'
    window.show_main_screen()
    settle(app)
    assert window.assistant_preview._custom_art is True
    assert window.assistant_preview.art.toImage().pixelColor(4, 4).name() == '#a8c0e4'
    assert window.assistant_preview.timer.isActive() is False
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(3)
    page = settings.settings_assistant_page
    menu = AssistantMenu(language, True, appearance='custom', mascot='orbit')
    try:
        assert any(label.text() == own_name for label in menu.findChildren(QtWidgets.QLabel))
    finally:
        menu.deleteLater()
    page.choose_appearance('animated')
    settle(app)
    restored_name = assistant_text(language, 'orbit')
    assert page.mascot_preview.accessibleName() == restored_name
    assert window.assistant_preview.button.toolTip().startswith(restored_name + ' — ')
    assert window.config['desktop_assistant_mascot'] == 'orbit'
    window.show_main_screen()
    settle(app)
    assert window.assistant_preview._custom_art is False


@pytest.mark.parametrize('contents', [None, b'not an image'])
def test_missing_or_corrupt_custom_art_falls_back_to_static_preview_without_opening_a_picker(window, app, tmp_path, contents):
    from assistant_preview import preview_art
    from unittest import mock
    picture = tmp_path/'missing-or-corrupt.png'
    if contents is not None:
        picture.write_bytes(contents)
    window.config.update(desktop_assistant_appearance='custom', desktop_assistant_mascot='orbit',
                         desktop_assistant_image=str(picture))
    with mock.patch.object(QtWidgets.QFileDialog, 'getOpenFileName') as picker:
        window.show_main_screen()
        window.assistant_preview.set_mascot('orbit')
        settle(app)
        assert window.assistant_preview._custom_art is False
        assert window.assistant_preview.art.cacheKey() == preview_art('orbit').cacheKey()
        assert window.assistant_preview.timer.isActive() is False
        picker.assert_not_called()


@pytest.mark.parametrize('language', tuple(ASSISTANT_TEXT))
def test_companion_page_controls_fit_all_themes_and_scales(window, app, language):
    window.set_interface_language(language)
    window.show_settings()
    settings = window.settings_window
    for theme in ('Темная', 'Светлая'):
        if window.current_theme != theme:
            window.toggle_theme()
        for scale in (80, 100, 125, 150, 200):
            window.set_ui_scale_percent(scale)
            settings._set_settings_page(3)
            settle(app)
            page = settings.settings_assistant_page
            button = page.menu_buttons
            context = (language, theme, scale)
            assert button.text() == assistant_text(language, 'menu_buttons')
            assert button.isVisible(), context
            assert button.fontMetrics().horizontalAdvance(button.text()) + 24 <= button.width(), context
            assert button.toolTip() and button.accessibleDescription()
            assert button.objectName() == 'assistantMenuButton'
            assert button.property('buttonRole') == 'secondary'
            assert ('#302938' if theme == 'Темная' else '#e2d8ec') in button.styleSheet(), context
            assert ('#8c739f' if theme == 'Темная' else '#927aa8') in button.styleSheet(), context
            scroll = settings.assistant_settings_scroll
            assert scroll.horizontalScrollBar().maximum() == 0, context
            for field in (page.mode_combo, *page.values.values()):
                scroll.ensureWidgetVisible(field, 0, 0)
                settle(app)
                bounds = QtCore.QRect(field.mapTo(scroll.viewport(), QtCore.QPoint()), field.size())
                assert scroll.viewport().rect().contains(bounds), (context, field.objectName())
