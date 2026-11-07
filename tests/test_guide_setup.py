"""First-run actions exercise actual controls; rendering uses isolated app data."""
import os
from pathlib import Path
from unittest import mock

import pytest
from PyQt5.QtCore import QEvent, QRect, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import main
import ocr
from guide_scenarios import ORDER, COPY, INTRO, chat_shortcut_body
from qt_layout_test_support import ensure_layout_fonts


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    ensure_layout_fonts(app)
    with (mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True),
          mock.patch.object(main.DarkThemeApp, 'save_config'),
          mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False),
          mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=['en', 'ru', 'ar'])):
        w = main.DarkThemeApp()
        w.config.update(main.DEFAULT_CONFIG)
        w.show()
        settle()
        yield w
        w._guide_active = False
        w._guide_step_timer.stop()
        w.force_quit = True
        w.close()
        w.deleteLater()
        settle()


def settle():
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    for _ in range(4):
        QApplication.processEvents()


def show_step(window, action):
    actions = [step[0] for step in window._guide_steps()]
    window._guide_active = True
    window._guide_step_index = actions.index(action)
    for _ in range(3):
        window._show_guide_step()
        settle()
        window._guide_step_timer.stop()
    assert window._guide_current_action() == action
    assert window._guide_bubble.isVisible()
    return window._guide_target_widget(action)


def test_starts_with_language_and_theme_and_all_copy_is_localized():
    assert ORDER[:2] == ('language', 'theme')
    assert set(COPY) == set(INTRO) == set(main.GUIDE_TEXT)
    for lang, c in COPY.items():
        assert len(c) == 15
        assert all(value.strip() for value in c)
        assert main.GUIDE_SETUP_INTRO[lang][2] == c[14]
        if lang != 'en':
            assert not set(c) & set(COPY['en'])
            assert chat_shortcut_body(lang) != chat_shortcut_body('en')


def test_language_picker_changes_the_guide_then_advances_on_close(window):
    show_step(window, 'language')
    window.flag_button.click()
    settle()
    assert window._interface_language_picker is not None
    assert not window._guide_bubble.isVisible()
    window.set_interface_language('ar')
    settle()
    assert window.current_interface_language == 'ar'
    assert window._guide_current_action() == 'language'
    window._close_interface_language_picker()
    settle()
    window._guide_step_timer.stop()
    window._show_guide_step()
    assert window._guide_current_action() == 'theme'
    assert window._guide_title.text() == COPY['ar'][2]


def test_theme_can_be_kept_or_changed_without_automatic_toggling(window):
    before = window.current_theme
    show_step(window, 'theme')
    assert window.current_theme == before
    window._guide_primary_btn.click()
    assert window.current_theme == before
    assert window._guide_current_action() == 'replace_selection_select_all'
    show_step(window, 'theme')
    window.theme_button.click()
    from test_ui_operations import wait_until
    wait_until(QApplication.instance(), lambda: not window._ui_operation.active)
    assert window.current_theme != before
    assert window._guide_current_action() == 'replace_selection_select_all'


@pytest.mark.parametrize('previous', (False, True))
def test_skipping_chat_preserves_settings_and_skips_its_children(window, previous):
    window.config['replace_selection_select_all'] = previous
    before = dict(window.config)
    show_step(window, 'replace_selection_select_all')
    assert window.config == before
    window._guide_skip_btn.click()
    window._guide_skip_btn.click()
    assert window.config == before
    assert window._guide_current_action() == 'shortcut_ocr'


@pytest.mark.parametrize('manual', (False, True))
def test_chat_opt_in_uses_real_checkbox_and_advances_only_once(window, manual):
    window.config['replace_selection_select_all'] = False
    target = show_step(window, 'replace_selection_select_all')
    assert target is window.settings_window.replace_select_all_checkbox
    if manual:
        QTest.mouseClick(target, Qt.LeftButton, pos=target.rect().center())
    else:
        window._guide_primary_btn.click()
        window._guide_primary_btn.click()
    assert window.config['replace_selection_select_all'] is True
    assert window._guide_current_action() == 'chat_languages'


def test_chat_pair_edits_only_replacement_and_uses_real_saved_shortcut(window):
    before = {k: window.config.get(k) for mode, keys in main.HOTKEY_LANGUAGE_CONFIG_KEYS.items()
              if mode != 'replace' for k in keys}
    show_step(window, 'chat_languages')
    assert window.hotkey_mode_combo.currentData() == 'replace'
    source = window.hotkey_source_combo
    target = window.hotkey_target_combo
    source.setCurrentIndex(source.findData('en'))
    target.setCurrentIndex(target.findData('ar'))
    keys = main.HOTKEY_LANGUAGE_CONFIG_KEYS['replace']
    assert [window.config[k] for k in keys] == ['en', 'ar']
    assert {k: window.config.get(k) for k in before} == before
    window.config['translate_replace_selection_hotkey'] = 'Ctrl+Shift+J'
    show_step(window, 'shortcut_replace')
    assert window._guide_hint.text() == 'Ctrl+Shift+J'
    assert 'Ctrl+Shift+Q' not in window._guide_body.text()


def test_shortcut_editor_is_not_closed_and_resumes_the_chat_card(window):
    show_step(window, 'shortcut_replace')
    with mock.patch.object(window, '_confirm_open_hotkey_settings', return_value=True):
        window.main_hotkey_references['replace'].clicked.emit()
    settle()
    settings = window.settings_window
    assert settings._secondary_view_kind == 'hotkeys'
    window._show_guide_step()
    assert settings._secondary_view_kind == 'hotkeys'
    assert not window._guide_bubble.isVisible()
    settings.hotkey_back_button.click()
    settle()
    window._guide_step_timer.stop()
    window._show_guide_step()
    settle()
    window._guide_step_timer.stop()
    window._show_guide_step()
    assert window._guide_current_action() == 'shortcut_replace'
    assert window._guide_bubble.isVisible()


def test_next_is_locked_during_step_transition(window):
    show_step(window, 'shortcut_ocr')
    window._guide_primary_btn.click()
    window._guide_primary_btn.click()
    window.skip_current_guide_step()
    assert window._guide_current_action() == 'shortcut_fullscreen'


def test_linux_tour_does_not_offer_unsupported_automatic_replacement(window):
    with mock.patch.object(main.platform_support, 'IS_LINUX', True):
        actions = [step[0] for step in window._guide_steps()]
    assert actions[:2] == ['language', 'theme']
    assert not set(main.CHAT_STEPS) & set(actions)


def test_whole_tour_uses_choices_without_altering_unrelated_defaults(window):
    before = dict(window.config)
    show_step(window, 'language')
    for action in ORDER:
        show_step(window, action)
        window._guide_primary_btn.click()
    window._guide_step_timer.stop()
    window._show_guide_step()
    assert not window._guide_active
    assert window.config['replace_selection_select_all'] is True
    allowed = {'replace_selection_select_all', 'hotkey_language_editor_mode',
               'first_run_guide_completed', 'first_run_guide_pending'}
    assert {key for key in before if before[key] != window.config.get(key)} <= allowed


def test_done_does_not_measure_success_by_recommended_checkboxes(window):
    window._guide_active = True
    window._guide_step_index = len(window._guide_steps())
    window._show_guide_step()
    assert not window._guide_active
    assert window._guide_body.text() == COPY[window.current_interface_language][10]
    assert window.config['first_run_guide_completed'] is True
    assert not window._guide_bubble.companion.pixmap().isNull()
    window._guide_primary_btn.click()
    assert not window._guide_bubble.isVisible()


@pytest.mark.parametrize('locale', tuple(COPY))
def test_guide_follows_the_single_engine_entry_and_waits_until_center_closes(window, locale):
    from settings_window import OcrLanguageManagerDialog
    window.set_interface_language(locale)
    target = show_step(window, 'language_packages')
    assert target is window.settings_window.engines_button
    assert window.settings_window._settings_page_index == 0
    card = window._guide_bubble
    assert window.ui_root.rect().contains(card.geometry())
    assert not card.geometry().intersects(window._guide_target_rect(target))
    assert card.body.height() >= card.body.heightForWidth(card.body.width())
    with (mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        target.click()
        settle()
        window._guide_step_timer.stop()
        window._show_guide_step()
        dialog = window.settings_window._language_manager_dialog
        assert dialog.isVisible()
        assert not card.isVisible()
        assert window.settings_window._settings_page_index == 0
        dialog.close()
        settle()
        window._guide_step_timer.stop()
        window._show_guide_step()
        settle()
        window._guide_step_timer.stop()
        window._show_guide_step()
        assert window._guide_current_action() == 'companion_settings'
        assert card.isVisible()


@pytest.mark.parametrize('theme', ('Темная', 'Светлая'))
@pytest.mark.parametrize('locale', tuple(COPY))
@pytest.mark.parametrize('scale', (80, 100, 137))
def test_cards_are_rendered_inside_the_window_and_clear_the_target(window, theme, locale, scale):
    window.current_interface_language = locale
    window.current_theme = theme
    window.show_main_screen()
    window.update_interface_language_button()
    window.apply_theme()
    window.set_ui_scale_percent(scale)
    settle()
    folder = os.environ.get('CNT_ONBOARDING_IMAGES')
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
    for action, _title, _body in window._guide_steps():
        target = show_step(window, action)
        assert target is not None and target.isVisible(), action
        card = window._guide_bubble
        assert window.ui_root.rect().contains(card.geometry()), (action, card.geometry())
        controller = window._ui_scale_controller
        rendered_rect = QRect(controller.map_widget_to_view(card, card.rect().topLeft()),
                              controller.map_widget_to_view(card, card.rect().bottomRight()))
        assert controller.view.viewport().rect().contains(rendered_rect), (action, rendered_rect)
        assert not card.geometry().intersects(window._guide_target_rect(target)), (action, card.geometry())
        assert card.companion.isVisible()
        assert card.companion.pixmap() is not None and not card.companion.pixmap().isNull()
        for label in (card.title, card.body, card.hint):
            if label.isVisible():
                assert label.height() >= label.heightForWidth(label.width()), (action, label.text())
        for button in (card.skip_button, card.primary_button):
            if button.isVisible():
                assert button.width() >= button.sizeHint().width(), (action, button.text())
        if folder and action in {'language', 'replace_selection_select_all', 'chat_languages', 'game_controls'}:
            assert window.grab().save(str(Path(folder) / f'{locale}-{theme}-{scale}-{action}.png'))


@pytest.mark.parametrize('locale', tuple(COPY))
@pytest.mark.parametrize('theme', ('Темная', 'Светлая'))
def test_updated_dynamic_and_attachment_instructions_fit_their_real_controls(window, locale, theme):
    window.current_interface_language = locale
    window.current_theme = theme
    window.show_main_screen()
    window.update_interface_language_button()
    window.apply_theme()
    for action in ('game_controls', 'document_translation'):
        target = show_step(window, action)
        card = window._guide_bubble
        assert target.isVisible()
        assert window.ui_root.rect().contains(card.geometry())
        assert not card.geometry().intersects(window._guide_target_rect(target))
        assert card.body.height() >= card.body.heightForWidth(card.body.width())
        if action == 'document_translation':
            assert target is window.main_image_button
