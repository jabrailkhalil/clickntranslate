"""Page changes reuse widgets and never decode companion atlases on the home page."""
from unittest import mock

from PyQt5 import QtCore, QtGui

import main
from test_desktop_ux import app, window


def test_unchanged_navigation_reuses_controls_and_preserves_draft(window, app):
    window.text_input.setPlainText('An unfinished message')
    editor = window.text_input
    window.show_settings()
    settings = window.settings_window
    window.show_main_screen()
    app.processEvents()
    pages = window._main_page_widgets
    with (mock.patch.object(window, '_apply_main_hotkey_theme', side_effect=AssertionError('Controls restyled')),
          mock.patch('assistant_preview.art_path', side_effect=AssertionError('Preview image reloaded'))):
        for _ in range(8):
            window.show_settings()
            assert window.settings_window is settings
            window.show_main_screen()
            app.processEvents()
            assert window.text_input is editor
            assert window._main_page_widgets == pages
            assert editor.toPlainText() == 'An unfinished message'


def test_changed_configuration_rebuilds_cached_main_controls(window, app):
    window.show_settings()
    old_editor = window.text_input
    window.config['desktop_assistant_mascot'] = 'mochi'
    window.show_main_screen()
    app.processEvents()
    assert window.text_input is not old_editor
    assert window.assistant_preview.mascot == 'mochi'
    assert tuple(window.assistant_preview.buttons) == ('mochi',)
    assert not window.assistant_preview.timer.isActive()


def test_page_change_freezes_paint_until_new_layout_is_ready(window, app):
    original = window.clear_layout
    states = []
    def clearing(*args, **kwargs):
        states.append((window.updatesEnabled(), window.ui_root.updatesEnabled()))
        original(*args, **kwargs)
    with mock.patch.object(window, 'clear_layout', side_effect=clearing):
        window.show_settings()
        window.show_main_screen()
    assert states == [(False, False), (False, False)]
    assert window.updatesEnabled() and window.ui_root.updatesEnabled()


def test_home_shortcut_uses_only_small_static_asset(window, app):
    from assistant_sprites import atlas
    atlas.cache_clear()
    with (mock.patch.object(QtGui, 'QImageReader', side_effect=AssertionError('Animation decoded')),
          mock.patch('assistant_preview.PetMotion.advance', side_effect=AssertionError('Animation advanced'))):
        window.show_main_screen()
        preview = window.assistant_preview
        app.processEvents()
        preview.grab()
        assert preview.art.size() == QtCore.QSize(192, 208)
        assert preview.button.value_label.pixmap().devicePixelRatio() >= 2
        assert atlas.cache_info().currsize == 0
        assert not preview.timer.isActive()
