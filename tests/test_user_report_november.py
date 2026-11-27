"""Reproduce the reported restart, empty-source and portable-gallery workflows."""
from pathlib import Path
import os
import json
import shutil
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui

import main
import companion_images
from test_desktop_ux import app, window

SAVE_CONFIG = main.DarkThemeApp.save_config


@pytest.mark.parametrize('same_install', [True, False])
def test_posix_relaunch_only_offers_to_close_a_different_install(same_install):
    owner = [{'same_path': same_install}]
    with mock.patch.object(main.platform_support, 'IS_WINDOWS', False), \
         mock.patch.object(main, '_running_clickntranslate_instances', return_value=owner), \
         mock.patch.object(main, '_confirm_close_other_install', return_value=False) as confirm:
        assert not main._replace_existing_instance()
    if same_install:
        confirm.assert_not_called()
    else:
        confirm.assert_called_once_with(owner)


@pytest.mark.parametrize('autostart', [False, True])
@pytest.mark.parametrize('minimized', [False, True])
@pytest.mark.parametrize('updated', [False, True])
def test_shadow_preference_only_affects_automatic_startup(monkeypatch, autostart, minimized, updated):
    monkeypatch.setattr(main.sys, 'argv', ['main.py'] + (['--autostart'] if autostart else []))
    assert main._should_start_in_shadow_mode(minimized, updated) == (autostart and minimized and not updated)


def test_shortcut_restores_same_running_install_without_replacing_it():
    with mock.patch.object(main, '_started_from_autostart', return_value=False), \
         mock.patch.object(main, '_running_clickntranslate_instances', return_value=[{'same_path': True}]), \
         mock.patch.object(main, '_bring_existing_to_front') as show:
        assert main._restore_same_install()
        show.assert_called_once()


def test_hiding_desktop_companion_survives_recreation(window):
    window.set_desktop_assistant_enabled(True)
    with mock.patch.object(main.DarkThemeApp, 'save_config', SAVE_CONFIG):
        window.dismiss_desktop_assistant_until_restart()
    assert window.config['desktop_assistant_enabled'] is False
    saved = json.loads(Path(main.get_data_file('config.json')).read_text(encoding='utf-8'))
    assert saved['desktop_assistant_enabled'] is False
    window._desktop_assistant_suppressed_until_restart = False
    window._sync_desktop_assistant()
    assert window._desktop_assistant is None
    assert window.config['main_assistant_visible'] is True


def test_clearing_source_also_clears_main_result_and_late_reply(window):
    window.text_input.setPlainText('hello')
    window._show_inline_main_result('مرحبا', 'hello', 'en', 'ar')
    window._main_translation_running = True
    window._main_active_request = ('hello', 'en', 'ar')
    window.text_input.clear()
    assert not window.main_result_view.toPlainText()
    assert window._main_result_snapshot is None
    assert window._argos_cancel_requested.is_set()
    with mock.patch.object(main, 'save_translation_history') as history:
        window._on_main_translation_done('late result')
        assert not window._main_translation_running
        assert not window.main_result_view.toPlainText()
        history.assert_not_called()


def make_image(path, color='red'):
    image = QtGui.QImage(45, 70, QtGui.QImage.Format_ARGB32)
    image.fill(QtGui.QColor(color))
    assert image.save(str(path))


def test_gallery_copies_deduplicates_and_never_deletes_original(window, tmp_path):
    source = tmp_path / 'picture.png'
    make_image(source)
    saved = companion_images.import_image(source)
    assert Path(saved).parent == companion_images.gallery_dir()
    assert Path(saved).read_bytes() == source.read_bytes()
    assert companion_images.import_image(source) == saved
    assert len(companion_images.images()) == 1
    companion_images.remove_image(str(source))
    assert source.exists()
    companion_images.remove_image(saved)
    assert not Path(saved).exists() and source.exists()


def test_gallery_moves_with_the_portable_application(window, tmp_path):
    from assistant_art import load_custom_art
    from assistant_settings import assistant_preferences
    image = tmp_path / 'portable.png'
    make_image(image)
    saved = companion_images.import_image(image)
    reference = companion_images.image_reference(saved)
    assert reference.startswith('data/companion-images/')
    moved = tmp_path / 'moved-app'
    shutil.copytree(companion_images.gallery_dir(), moved / 'data' / 'companion-images')
    Path(saved).unlink()
    image.unlink()
    with mock.patch('portable_paths.portable_base_dir', return_value=str(moved)):
        resolved = companion_images.resolve_image(reference)
        assert Path(resolved).is_file()
        assert not load_custom_art(reference).isNull()
        assert assistant_preferences({'desktop_assistant_image': reference})['desktop_assistant_image'] == resolved


def test_gallery_selection_and_delete_survive_source_file_removal(window, tmp_path):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    source = tmp_path / 'first.png'
    make_image(source)
    with mock.patch.object(main.QFileDialog, 'getOpenFileName', return_value=(str(source), '')):
        page._choose_custom_image()
    first = companion_images.resolve_image(window.config['desktop_assistant_image'])
    source.unlink()
    assert Path(first).exists()
    other = tmp_path / 'second.png'
    make_image(other, 'blue')
    with mock.patch.object(main.QFileDialog, 'getOpenFileName', return_value=(str(other), '')):
        page._choose_custom_image()
    assert page.image_combo.count() == 2
    page.image_combo.setCurrentIndex(page.image_combo.findData(first))
    assert window.config['desktop_assistant_image'] == companion_images.image_reference(first)
    page.remove_image.click()
    assert not Path(first).exists()
    assert page.image_combo.count() == 1
    page.remove_image.click()
    assert window.config['desktop_assistant_image'] == ''
    assert window.config['desktop_assistant_appearance'] == 'portrait'


def test_failed_image_import_restores_the_previous_display_mode(window, tmp_path):
    window.show_assistant_settings()
    page = window.settings_window.settings_assistant_page
    previous = window.config.get('desktop_assistant_appearance', 'animated')
    image = tmp_path / 'photo.png'
    make_image(image)
    with mock.patch.object(main.QFileDialog, 'getOpenFileName', return_value=(str(image), '')), \
         mock.patch.object(companion_images, 'import_image', side_effect=OSError('No space')), \
         mock.patch('styled_dialogs.StyledMessageBox.warning') as warning:
        page.mode_combo.setCurrentIndex(page.mode_combo.findData('custom'))
    warning.assert_called_once()
    assert window.config.get('desktop_assistant_appearance', 'animated') == previous
    assert page.mode_combo.currentData() == previous


@pytest.mark.parametrize('locale', list(main.INTERFACE_TEXT))
def test_custom_gallery_controls_fit_fixed_viewport_at_all_scales(window, app, tmp_path, locale):
    from settings_sections import PAGE_COMPANION
    source = tmp_path / 'sample.png'
    make_image(source)
    window.config.update(desktop_assistant_appearance='custom',
                         desktop_assistant_image=companion_images.import_image(source))
    window.set_interface_language(locale)
    window.show_settings()
    settings = window.settings_window
    for scale in (80, 100, 160, 200):
        window.set_ui_scale_percent(scale)
        settings._set_settings_page(PAGE_COMPANION)
        for _ in range(4):
            app.processEvents()
        page = settings.settings_assistant_page
        scroll = settings.assistant_settings_scroll
        footer = settings.assistant_action_panel
        assert scroll.verticalScrollBar().maximum() == 0, (locale, scale, scroll.verticalScrollBar().maximum())
        for control in (page.image_combo, page.remove_image, page.appearance_buttons['custom'], page.menu_buttons):
            bounds = QtCore.QRect(control.mapTo(footer, QtCore.QPoint()), control.size())
            assert footer.rect().contains(bounds), (locale, scale, bounds, footer.rect())
        assert page.image_combo.width() >= 80
        if scale == 160 and os.environ.get('CNT_QA_RENDER'):
            output = Path(os.environ['CNT_QA_RENDER'])
            output.mkdir(parents=True, exist_ok=True)
            assert window.grab().save(str(output / ('companion-' + locale + '.png')))


def test_background_task_is_visible_on_main_page_without_a_popup(window, app):
    before = set(app.topLevelWidgets())
    state = dict(kind='running', percent=42, text='Hy-MT: model 42%')
    window.set_engine_task_status(state)
    assert window.main_engine_task_button.isVisible()
    assert '42%' in window.main_engine_task_button.text()
    assert 'Hy-MT' in window.main_engine_task_button.toolTip()
    assert set(app.topLevelWidgets()) == before
    window.set_engine_task_status(dict(kind='done'))
    assert not window.main_engine_task_button.isVisible()


def test_translator_category_order_is_online_then_offline_then_api(app):
    from settings_window import DropDownCombo, _populate_grouped_translator_combo
    combo = DropDownCombo()
    try:
        _populate_grouped_translator_combo(combo, lang='ru')
        assert [key for key, _ in combo._provider_categories] == ['online', 'offline', 'api']
    finally:
        combo.deleteLater()


def test_main_argos_download_cannot_overlap_engine_installation(window):
    window.show_settings()
    settings = window.settings_window
    settings._hymt_install_in_progress = True
    try:
        with mock.patch.object(settings, 'show_ocr_language_manager') as show, \
             mock.patch.object(main.threading, 'Thread') as thread:
            window._start_main_translation('hello', 'en', 'ar', 'argos', package_installed=False)
        show.assert_called_once_with('argos', 'en', 'ar')
        thread.assert_not_called()
        assert not window._main_translation_running
    finally:
        settings._hymt_install_in_progress = False
