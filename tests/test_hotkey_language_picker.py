"""Language choices in the shortcut editor should reflect the effective engine inventory."""
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

import main
from test_desktop_ux import app, window
from ui_scaling import widget_global_rect


@pytest.mark.parametrize('pairs', [set(), {('en', 'fr')}])
def test_open_and_mode_change_query_the_language_inventory_once(window, app, monkeypatch, pairs):
    window.config['hotkey_language_editor_mode'] = 'ocr'
    available = mock.Mock(return_value=pairs)
    monkeypatch.setattr(window, '_available_hotkey_translation_pairs', available)
    window.save_config.reset_mock()
    dialog = main.HotkeyLanguageDialog(window)
    try:
        assert available.call_args_list == [mock.call('ocr')]
        window.save_config.assert_not_called()
        assert dialog.mode_combo.accessibleName() == main.hotkey_language_text(window.current_interface_language, 'mode')
        available.reset_mock()
        dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData('game'))
        assert available.call_args_list == [mock.call('game')]
        window.save_config.assert_called_once()
        assert window.hotkey_mode_combo.currentData() == 'game'
        assert dialog.source_combo.isEnabled() == bool(pairs)
    finally:
        dialog.close()


def test_reverse_action_tracks_auto_source_and_one_way_language_pairs(window, monkeypatch):
    window.config['hotkey_language_editor_mode'] = 'selection'
    source_key, target_key = main.HOTKEY_LANGUAGE_CONFIG_KEYS['selection']
    window.config[source_key], window.config[target_key] = 'en', 'fr'
    pairs = {('auto', 'fr'), ('en', 'fr'), ('fr', 'en'), ('fr', 'de')}
    monkeypatch.setattr(window, '_available_hotkey_translation_pairs', lambda _mode: pairs)
    dialog = main.HotkeyLanguageDialog(window)
    try:
        dialog.source_combo.setCurrentIndex(dialog.source_combo.findData('auto'))
        assert dialog.target_combo.currentData() == 'fr'
        assert not dialog.swap_button.isEnabled()
        dialog.source_combo.setCurrentIndex(dialog.source_combo.findData('fr'))
        dialog.target_combo.setCurrentIndex(dialog.target_combo.findData('de'))
        assert not dialog.swap_button.isEnabled()
        dialog.target_combo.setCurrentIndex(dialog.target_combo.findData('en'))
        assert dialog.swap_button.isEnabled()
        dialog.swap_button.click()
        assert (dialog.source_combo.currentData(), dialog.target_combo.currentData()) == ('en', 'fr')
    finally:
        dialog.close()


def test_growing_shortcut_editor_keeps_done_button_on_anchor_screen(window, app, monkeypatch):
    window.config['hotkey_language_editor_mode'] = 'ocr'
    monkeypatch.setattr(window, '_available_hotkey_translation_pairs', lambda _mode: {('en', 'fr')})
    available = app.primaryScreen().availableGeometry()
    target_y = available.bottom() - 272
    origin = window.mapToGlobal(QtCore.QPoint(0, 60))
    window.move(window.x(), window.y() + target_y - origin.y())
    app.processEvents()
    window.show_hotkey_language_dialog()
    dialog = window._hotkey_language_dialog
    try:
        assert available.contains(dialog.frameGeometry())
        dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData('selection'))
        app.processEvents()
        assert available.contains(dialog.frameGeometry())
        done = dialog.findChild(QtWidgets.QPushButton, 'hotkeyLanguageDone')
        assert available.contains(widget_global_rect(done))
    finally:
        dialog.close()


def test_settings_opens_selection_at_its_button_and_persists_the_mode(window, app, monkeypatch):
    window.show_settings()
    settings = window.settings_window
    settings.show_hotkeys_screen()
    app.processEvents()
    point = widget_global_rect(settings.selection_mode_button).center()
    window.move(window.pos() + app.primaryScreen().availableGeometry().center() - point)
    app.processEvents()
    window.config['hotkey_language_editor_mode'] = 'game'
    available = mock.Mock(return_value={('en', 'fr')})
    monkeypatch.setattr(window, '_available_hotkey_translation_pairs', available)
    window.save_config.reset_mock()
    settings.selection_mode_button.click()
    dialog = window._hotkey_language_dialog
    try:
        app.processEvents()
        assert dialog.current_mode() == window.hotkey_mode_combo.currentData() == 'selection'
        assert dialog.selection_trigger.isVisible()
        assert dialog.mode_combo.toolTip()
        available.assert_called_once_with('selection')
        window.save_config.assert_called_once()
        anchor = widget_global_rect(settings.selection_mode_button)
        assert app.screenAt(anchor.center()).availableGeometry().contains(dialog.frameGeometry())
        assert dialog.geometry().left() <= anchor.center().x() <= dialog.geometry().right()
    finally:
        dialog.close()


def test_language_removed_while_editor_open_does_not_overwrite_the_saved_pair(window, monkeypatch):
    window.config['hotkey_language_editor_mode'] = 'selection'
    source_key, target_key = main.HOTKEY_LANGUAGE_CONFIG_KEYS['selection']
    window.config[source_key], window.config[target_key] = 'en', 'fr'
    pairs = {('en', 'fr'), ('fr', 'en')}
    probe = mock.Mock(return_value=pairs)
    monkeypatch.setattr(window, '_available_hotkey_translation_pairs', probe)
    dialog = main.HotkeyLanguageDialog(window)
    try:
        assert dialog.swap_button.isEnabled()
        pairs.clear()
        probe.reset_mock()
        dialog.swap_button.click()
        probe.assert_called_once_with('selection')
        assert not dialog.swap_button.isEnabled()
        assert not dialog.source_combo.isEnabled()
        assert dialog.status_label.text() == main.hotkey_language_text(window.current_interface_language, 'no_pairs')
        assert (window.config[source_key], window.config[target_key]) == ('en', 'fr')
    finally:
        dialog.close()


@pytest.mark.parametrize('locale', ['de', 'ar'])
def test_dense_desktop_fits_the_dialog_with_wrapped_instructions(window, app, monkeypatch, locale):
    bounds = QtCore.QRect(0, 0, 400, 300)
    monkeypatch.setattr(QtGui.QScreen, 'availableGeometry', lambda self: QtCore.QRect(bounds))
    window.set_interface_language(locale)
    window.config['hotkey_language_editor_mode'] = 'selection'
    monkeypatch.setattr(window, '_available_hotkey_translation_pairs', lambda _mode: set())
    window.show_hotkey_language_dialog()
    dialog = window._hotkey_language_dialog
    try:
        app.processEvents()
        assert bounds.contains(dialog.frameGeometry())
        for child in dialog.findChildren((QtWidgets.QLabel, QtWidgets.QAbstractButton, QtWidgets.QComboBox)):
            if child.isVisible():
                assert bounds.contains(widget_global_rect(child))
        body = dialog.findChild(QtWidgets.QLabel, 'hotkeyLanguageBody')
        text = body.fontMetrics().boundingRect(body.contentsRect(), int(body.alignment() | QtCore.Qt.TextWordWrap), body.text())
        assert text.height() <= body.contentsRect().height()
    finally:
        dialog.close()
