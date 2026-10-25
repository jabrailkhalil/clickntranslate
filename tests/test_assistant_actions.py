"""Configurable companion actions, without capture, clipboard or OS hooks."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import main
from assistant_settings import (ASSISTANT_ACTIONS, ASSISTANT_DEFAULTS, AssistantActionsDialog,
                                assistant_preferences, normalized_assistant_actions)
from assistant_text import ASSISTANT_TEXT, assistant_action_text, assistant_text
from settings_window import settings_export_payload, validated_import_settings
from test_desktop_assistant import app, companion
from desktop_assistant import AssistantMenu
from test_desktop_ux import window


@pytest.mark.parametrize('value,expected', [
    (None, list(ASSISTANT_ACTIONS)), ('area', list(ASSISTANT_ACTIONS)),
    (True, list(ASSISTANT_ACTIONS)), ({'area': True}, list(ASSISTANT_ACTIONS)),
    ([], []), ((), []), (['text', 'area', 'text', 'obsolete', None, {}, ['open']], ['area', 'text']),
    (['hide', 'settings'], []), (['guide', 'open'], ['open', 'guide']),
])
def test_action_preferences_accept_only_stable_ids_without_restoring_an_empty_choice(value, expected):
    assert normalized_assistant_actions(value) == expected
    assert assistant_preferences({'desktop_assistant_actions': value})['desktop_assistant_actions'] == expected


@pytest.mark.parametrize('selected', [[], ['open'], ['area', 'guide'], list(ASSISTANT_ACTIONS)])
def test_action_preferences_survive_export_import_and_configuration_migration(selected):
    config = dict(main.DEFAULT_CONFIG, desktop_assistant_actions=selected)
    exported = settings_export_payload(config)
    restored = validated_import_settings(exported, main.DEFAULT_CONFIG)
    migrated, _missing = main.merge_config_defaults(restored)
    assert migrated['desktop_assistant_actions'] == selected
    assert exported['settings']['desktop_assistant_actions'] == selected
    assert ASSISTANT_DEFAULTS['desktop_assistant_actions'] == list(ASSISTANT_ACTIONS)


def test_unknown_imported_ids_and_duplicates_are_removed_by_configuration_migration():
    payload = settings_export_payload({'desktop_assistant_actions': ['guide', 'old', 'open', 'open', {}]})
    migrated, _missing = main.merge_config_defaults(validated_import_settings(payload, main.DEFAULT_CONFIG))
    assert migrated['desktop_assistant_actions'] == ['open', 'guide']


def test_open_restores_the_existing_owner_without_resetting_its_page(companion):
    companion.owner.page = 'settings:translation'
    companion.request_action('open')
    QTest.qWait(50)
    companion.owner.show_window_from_tray.assert_called_once_with(force_show=True)
    companion.owner.show_main_screen.assert_not_called()
    companion.owner.open_text_translation.assert_not_called()
    companion.owner.show_settings.assert_not_called()
    assert companion.owner.page == 'settings:translation'


def test_changing_actions_rebuilds_the_open_menu_and_empty_selection_keeps_footer(companion):
    companion.toggle_menu()
    previous = companion.menu
    companion.owner.config['desktop_assistant_actions'] = ['open', 'guide']
    companion.refresh()
    assert not previous.isVisible()
    assert companion.menu.isVisible()
    assert set(companion.menu.buttons) == {'open', 'guide', 'settings', 'hide'}
    companion.owner.config['desktop_assistant_actions'] = []
    companion.refresh()
    assert set(companion.menu.buttons) == {'settings', 'hide'}
    assert companion.menu.isVisible()


@pytest.mark.parametrize('language', tuple(ASSISTANT_TEXT))
@pytest.mark.parametrize('dpi_factor', [1., 1.5, 2.])
def test_menu_with_all_actions_fits_a_small_high_dpi_screen(app, language, dpi_factor):
    bounds = QtCore.QRect(-640, 0, 640, 480)
    menu = AssistantMenu(language, True, factor=min(dpi_factor, bounds.width()/360, bounds.height()/360))
    try:
        menu.open_beside(QtCore.QRect(-100, 350, 84, 84), bounds)
        app.processEvents()
        assert bounds.contains(menu.geometry()), (language, dpi_factor, menu.geometry())
        assert all(menu.rect().contains(button.geometry()) for button in menu.buttons.values())
    finally:
        menu.close()
        menu.deleteLater()


@pytest.mark.parametrize('language', tuple(ASSISTANT_TEXT))
@pytest.mark.parametrize('dark', [True, False])
def test_actions_dialog_translations_layout_theme_and_keyboard(app, companion, language, dark):
    owner = companion.owner
    owner.current_interface_language = language
    owner.current_theme = 'Темная' if dark else 'Светлая'
    dialog = AssistantActionsDialog(owner)
    changes = []
    dialog.actions_changed.connect(changes.append)
    try:
        dialog.open()
        app.processEvents()
        assert dialog.windowTitle() == assistant_text(language, 'menu_buttons').rstrip('…')
        assert len(dialog.checkboxes) == 8
        assert all(isinstance(assistant_action_text(language, action), tuple) for action in ASSISTANT_ACTIONS)
        assert dialog.layoutDirection() == (QtCore.Qt.RightToLeft if language == 'ar' else QtCore.Qt.LeftToRight)
        assert '#111111' in dialog.styleSheet() if dark else '#f0ecf3' in dialog.styleSheet()
        for action, checkbox in dialog.checkboxes.items():
            title, hint = assistant_action_text(language, action)
            assert checkbox.text() == title and checkbox.accessibleDescription() == hint
            assert checkbox.toolTip()
            assert checkbox.width() >= checkbox.sizeHint().width(), (language, title, checkbox.size(), checkbox.sizeHint())
            assert checkbox.height() >= checkbox.sizeHint().height()
        assert dialog.done_button.isVisible()
        assert dialog.rect().contains(dialog.done_button.mapTo(dialog, dialog.done_button.rect().bottomRight()))
        first, second = dialog.checkboxes['open'], dialog.checkboxes['area']
        first.setFocus(QtCore.Qt.TabFocusReason)
        QTest.keyClick(first, QtCore.Qt.Key_Space)
        assert 'open' not in changes[-1]
        QTest.keyClick(first, QtCore.Qt.Key_Down)
        assert dialog.focusWidget() is second
        QTest.keyClick(second, QtCore.Qt.Key_Return)
        assert 'area' not in changes[-1]
        QTest.keyClick(second, QtCore.Qt.Key_Escape)
        assert not dialog.isVisible()
    finally:
        dialog.close()
        dialog.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('language', tuple(ASSISTANT_TEXT))
def test_actions_dialog_large_scale_keeps_footer_visible_and_uses_only_vertical_scrolling(app, companion, language):
    owner = companion.owner
    owner.current_interface_language = language
    with mock.patch('ui_scaling.interface_scale_factor', return_value=2.):
        dialog = AssistantActionsDialog(owner)
    try:
        dialog.open()
        app.processEvents()
        bounds = owner.screen().availableGeometry()
        assert dialog.width() <= bounds.width()-32 and dialog.height() <= bounds.height()-32
        assert dialog.scroll.horizontalScrollBar().maximum() == 0
        assert dialog.done_button.isVisible()
        assert dialog.rect().contains(dialog.done_button.mapTo(dialog, dialog.done_button.rect().bottomRight()))
        dialog.scroll.ensureWidgetVisible(dialog.checkboxes['guide'])
        assert dialog.scroll.verticalScrollBar().value() == dialog.scroll.verticalScrollBar().maximum()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_menu_buttons_action_uses_the_footer_and_changes_apply_live(window, app):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(3)
    page = settings.settings_assistant_page
    panel = settings.assistant_action_panel
    assert panel.layout().itemAt(1).widget() is page.menu_buttons
    assert page.menu_buttons.parentWidget() is panel
    assert abs(page.menu_buttons.geometry().center().x() - panel.rect().center().x()) <= 1
    assert page.menu_buttons.width() < panel.width()
    assert 'background:transparent; border:0;' in panel.styleSheet()
    assert not settings.assistant_settings_scroll.isAncestorOf(page.menu_buttons)
    assert not hasattr(page, 'dismiss_button')
    assert not hasattr(page, 'action_buttons')
    with mock.patch.object(page, 'save', wraps=page.save) as save:
        page.configure_menu()
        dialog = page._actions_dialog
        app.processEvents()
        for checkbox in dialog.checkboxes.values():
            checkbox.setChecked(False)
        assert window.config['desktop_assistant_actions'] == []
        save.assert_called_with('actions', [])
        dialog.done_button.click()
        assert page._actions_dialog is None
