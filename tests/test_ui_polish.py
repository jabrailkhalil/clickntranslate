"""September UI fixes: real events, lifetime, provider isolation and rendering."""
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets, sip
from PyQt5.QtTest import QTest, QSignalSpy

import main
from assistant_preview import AssistantPreview, preview_frames
from capture_widgets import CaptureLanguageCombo
from languages import LANGUAGES, language_icon_path
from qt_layout_test_support import ensure_layout_fonts


@pytest.fixture
def app():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    ensure_layout_fonts(app)
    yield app
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


@pytest.fixture
def owner(app):
    widget = QtWidgets.QWidget()
    widget.config = dict(main.DEFAULT_CONFIG, show_update_info=True, translator_engine='Lingva')
    widget.current_interface_language = 'ru'
    widget.current_theme = 'Темная'
    widget.save_config = mock.Mock()
    yield widget
    widget.close()
    app.processEvents()
    widget.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('dismiss', ['accept', 'reject', 'close', 'skip_guide', 'start_guide'])
def test_welcome_checkbox_click_has_a_tick_and_survives_every_exit(app, owner, dismiss):
    dialog = main.WelcomeDialog(owner)
    dialog.show()
    app.processEvents()
    checkbox = dialog.checkbox
    original = checkbox.grab().toImage()
    # The far end of the row used to start dragging the dialog instead.
    QTest.mouseClick(checkbox, QtCore.Qt.LeftButton,
                     pos=QtCore.QPoint(checkbox.width() - 3, checkbox.height() // 2))
    assert checkbox.isChecked()
    assert checkbox.grab().toImage() != original
    option = QtWidgets.QStyleOptionButton()
    checkbox.initStyleOption(option)
    rect = checkbox.style().subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, option, checkbox)
    image = checkbox.grab().toImage()
    # Actual dark stroke on a light selected indicator, not only a changed bool.
    colors = [image.pixelColor(x, y).lightness() for x in range(rect.left()+3, rect.right()-2)
              for y in range(rect.top()+3, rect.bottom()-2)]
    assert max(colors) > 160 and min(colors) < 70
    assert not dialog.findChildren(QtCore.QPropertyAnimation)
    getattr(dialog, dismiss)()
    assert owner.config['show_update_info'] is False
    owner.save_config.assert_called_once()
    assert dialog.start_guide_requested == (dismiss == 'start_guide')
    dialog.deleteLater()


def test_welcome_keyboard_and_language_rebuild_keep_choice(app, owner):
    dialog = main.WelcomeDialog(owner)
    dialog.show()
    dialog.checkbox.setFocus()
    QTest.keyClick(dialog.checkbox, QtCore.Qt.Key_Space)
    assert dialog.checkbox.isChecked()
    dialog.set_language('en')
    app.processEvents()
    assert dialog.checkbox.isChecked()
    QTest.keyClick(dialog, QtCore.Qt.Key_Escape)
    assert owner.config['show_update_info'] is False
    dialog.deleteLater()


def test_welcome_links_are_icons_and_point_to_the_author(app, owner, monkeypatch):
    opened = mock.Mock()
    monkeypatch.setattr(main.webbrowser, 'open', opened)
    dialog = main.WelcomeDialog(owner)
    for button in (dialog.telegram_btn, dialog.github_btn):
        assert not button.text()
        assert not button.icon().isNull()
        assert button.accessibleName()
        assert button.toolTip()
        pixmap = button.icon().pixmap(32, 32)
        assert not pixmap.isNull()
        button.click()
    assert opened.call_args_list == [mock.call('https://t.me/jabrail_digital'),
                                     mock.call('https://github.com/jabrailkhalil')]
    dialog.close()
    dialog.deleteLater()


@pytest.fixture
def workspaces(app, owner, monkeypatch):
    jobs = []
    monkeypatch.setattr(main.threading, 'Thread', lambda target, **kw: SimpleNamespace(start=lambda: jobs.append(target)))
    monkeypatch.setattr(main, 'save_translation_history', mock.Mock())
    monkeypatch.setattr(main, 'save_copy_history', mock.Mock())
    monkeypatch.setattr(main.platform_support, 'copy_text', mock.Mock())
    dialogs = [main.TranslationResultDialog(owner, 'Старый перевод', auto_copy=False, lang='ru',
               source_text='Original', source_lang='en', target_lang='ru') for _ in range(2)]
    for dialog in dialogs:
        dialog.show()
    app.processEvents()
    yield (*dialogs, jobs)
    for dialog in dialogs:
        dialog.close()
        dialog.deleteLater()


def test_workspace_engine_is_local_and_survives_global_changes(owner, workspaces, monkeypatch):
    first, second, jobs = workspaces
    assert not jobs  # Opening a window never starts a provider/download request.
    first.engine_combo.setCurrentIndex(first.engine_combo.findData('google'))
    assert first.window_engine == 'Google'
    assert second.window_engine == 'Lingva'
    assert owner.config['translator_engine'] == 'Lingva'
    owner.config['translator_engine'] = 'MyMemory'
    import translater
    translate = mock.Mock(return_value='Локальный перевод')
    monkeypatch.setattr(translater, 'translate_text', translate)
    jobs.pop()()
    assert translate.call_args.kwargs['engine'] == 'google'
    second.translate_button.click()
    jobs.pop()()
    assert translate.call_args.kwargs['engine'] == 'lingva'
    assert owner.config['translator_engine'] == 'MyMemory'
    first.translate_button.click()
    jobs.pop()()
    assert translate.call_args.kwargs['engine'] == 'google'


def test_switch_engine_cancels_old_reply_and_main_stream(workspaces, monkeypatch):
    dialog, _, jobs = workspaces
    dialog.translate_button.click()
    old_id, old_cancel = dialog._request_id, dialog._cancel_event
    dialog._following_main_translation = True
    dialog.engine_combo.setCurrentIndex(dialog.engine_combo.findData('mymemory'))
    assert old_cancel.is_set()
    assert not dialog._following_main_translation
    dialog._on_retranslated(old_id, 'Stale reply', '')
    assert dialog.text_edit.toPlainText() != 'Stale reply'
    import translater
    monkeypatch.setattr(translater, 'translate_text', mock.Mock(return_value='Current provider'))
    jobs[-1]()
    assert dialog.text_edit.toPlainText() == 'Current provider'
    assert translater.translate_text.call_args.kwargs['engine'] == 'mymemory'


@pytest.mark.parametrize('theme', ['Светлая', 'Темная'])
def test_workspace_engine_header_fits_narrow_and_wide_windows(app, workspaces, theme):
    dialog, _, _ = workspaces
    dialog.refresh_theme(theme)
    for width in (410, 760, 460, 900):
        dialog.resize(width, 650)
        app.processEvents()
        rectangles = [QtCore.QRect(w.mapTo(dialog.frame, QtCore.QPoint()), w.size())
                      for w in (dialog.title_label, dialog.engine_combo, dialog.scale_control, dialog.title_close_button)]
        for rectangle in rectangles:
            assert dialog.frame.rect().contains(rectangle)
        for i, rectangle in enumerate(rectangles):
            assert all(not rectangle.intersects(other) for other in rectangles[i+1:])
        assert dialog.engine_combo.isVisible()


def test_followed_or_unknown_provider_never_falls_back_to_online(workspaces):
    dialog, _, jobs = workspaces
    dialog.set_window_engine('Hy-MT')
    assert dialog.window_engine == 'Hy-MT'
    assert dialog.engine_combo.currentData() == 'hymt'
    dialog.set_window_engine('Local experimental provider')
    assert dialog.window_engine == 'Local experimental provider'
    assert dialog.engine_combo.currentText() == 'Local experimental provider'
    assert not jobs


def test_preview_cache_is_shared_small_and_no_per_frame_loading(app, owner, monkeypatch):
    rail = AssistantPreview(owner, parent=owner)
    second = AssistantPreview(owner, parent=owner)
    assert not rail.frames[0]  # No eagerly loaded animation for a hidden page.
    owner.resize(250, 100)
    owner.show()
    rail.show()
    second.show()
    app.processEvents()
    assert rail.frames is second.frames
    assert len(rail.frames[0]) == 10
    memory = sum(p.width() * p.height() * 4 for row in rail.frames for p in row)
    assert memory <= 80 * 1024
    monkeypatch.setattr(QtGui, 'QImageReader', mock.Mock(side_effect=AssertionError('read during animation')))
    for _ in range(200):
        rail._advance(80)
        assert 0 <= rail.button.x() <= rail.width() - rail.button.width()
    rail.hide()
    second.hide()


def test_preview_has_no_idle_timer_and_pauses_for_hover_focus_minimize(app, owner):
    owner.resize(300, 100)
    rail = AssistantPreview(owner, parent=owner)
    rail.resize(260, 18)
    owner.show()
    rail.show()
    rail.button.clearFocus()
    rail._hovered = False
    rail._application_state_changed(QtCore.Qt.ApplicationActive)
    assert rail.timer.isActive()
    spy = QSignalSpy(rail.timer.timeout)
    rail.hide()
    QTest.qWait(200)
    assert not rail.timer.isActive() and len(spy) == 0
    rail.show()
    rail._application_state_changed(QtCore.Qt.ApplicationInactive)
    assert not rail.timer.isActive()
    rail._application_state_changed(QtCore.Qt.ApplicationActive)
    rail._hovered = True
    rail._sync_animation()
    assert not rail.timer.isActive()
    rail._hovered = False
    rail._sync_animation()
    assert rail.timer.isActive()
    owner.showMinimized()
    app.processEvents()
    assert not rail.timer.isActive()
    owner.showNormal()
    rail.button.setParent(owner)  # Visual layout editor detaches widgets.
    rail._application_state_changed(QtCore.Qt.ApplicationActive)
    assert not rail.timer.isActive()


def test_preview_click_and_keyboard_open_settings_without_desktop_overlay(app, owner):
    rail = AssistantPreview(owner, parent=owner)
    owner.show()
    rail.show()
    spy = QSignalSpy(rail.settings_requested)
    rail.button.click()
    rail.button.setFocus()
    QTest.keyClick(rail.button, QtCore.Qt.Key_Space)
    assert len(spy) == 2
    assert owner.config['desktop_assistant_enabled'] is False


@pytest.mark.parametrize('dark', [True, False])
def test_capture_closed_label_never_changes_to_full_name_and_effect_is_restored(app, owner, dark):
    combo = CaptureLanguageCombo(owner)
    owner.language_combo = combo
    for language in LANGUAGES:
        combo.addItem(QtGui.QIcon(language_icon_path(language.code)), language.short_label, language.code)
    combo.set_capture_theme(dark, 'en')
    combo.setCurrentIndex(combo.findData('ru'))
    owner.show()
    combo.show()
    app.processEvents()
    original_effect = app.isEffectEnabled(QtCore.Qt.UI_AnimateCombo)
    expected_effect = app.isEffectEnabled(QtCore.Qt.UI_AnimateCombo)  # Offscreen can disable all effects.
    try:
        for _ in range(4):
            before = combo.currentText()
            combo.showPopup()
            QTest.qWait(30)
            assert app.isEffectEnabled(QtCore.Qt.UI_AnimateCombo) == expected_effect
            option = QtWidgets.QStyleOptionComboBox()
            combo.initStyleOption(option)
            assert option.currentText == before == 'RU'
            popup = combo.view().window()
            anchor = QtCore.QRect(combo.mapToGlobal(QtCore.QPoint()), combo.size())
            assert not popup.geometry().intersects(anchor)
            assert combo.itemDelegate().label(combo.model().index(combo.currentIndex(), 0)) == 'Russian'
            combo.hidePopup()
            app.processEvents()
            combo.initStyleOption(option)
            assert option.currentText == 'RU'
    finally:
        combo.hidePopup()
        QTest.qWait(30)
        app.setEffectEnabled(QtCore.Qt.UI_AnimateCombo, original_effect)


@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
def test_faq_scrollbar_keeps_contrast_while_held(app, owner, monkeypatch, theme):
    owner.current_theme = theme
    owner._complete_guide_step = mock.Mock()
    captured = []
    def inspect(dialog):
        dialog.show()
        app.processEvents()
        editor = dialog.findChild(QtWidgets.QTextEdit)
        bar = editor.verticalScrollBar()
        assert bar.maximum() > 0
        option = QtWidgets.QStyleOptionSlider()
        option.initFrom(bar)
        option.orientation = bar.orientation()
        option.minimum, option.maximum = bar.minimum(), bar.maximum()
        option.sliderPosition, option.sliderValue = bar.sliderPosition(), bar.value()
        option.singleStep, option.pageStep = bar.singleStep(), bar.pageStep()
        handle = bar.style().subControlRect(QtWidgets.QStyle.CC_ScrollBar, option,
                                            QtWidgets.QStyle.SC_ScrollBarSlider, bar)
        point = handle.center()
        QTest.mouseMove(bar, point)
        QTest.mousePress(bar, QtCore.Qt.LeftButton, pos=point)
        QTest.qWait(40)
        image = bar.grab().toImage()
        handle_color = image.pixelColor(point)
        track = image.pixelColor(point.x(), min(image.height()-3, handle.bottom()+12))
        assert abs(handle_color.lightness() - track.lightness()) > 35
        QTest.mouseRelease(bar, QtCore.Qt.LeftButton, pos=point)
        captured.append(dialog)
        return QtWidgets.QDialog.Rejected
    monkeypatch.setattr(main.CenteredFramelessDialog, 'exec_', inspect)
    main.DarkThemeApp.show_help_dialog(owner)
    assert captured
    for dialog in captured:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
def test_translation_result_scrollbar_keeps_contrast_while_held(app, owner, theme):
    dialog = main.TranslationResultDialog(
        owner, '', auto_copy=False, lang='ru', theme=theme,
        source_text='\n'.join(f'Строка {index}' for index in range(80)),
    )
    dialog.resize(700, 420)
    dialog.show()
    app.processEvents()
    try:
        bar = dialog.source_edit.verticalScrollBar()
        assert bar.maximum() > 0
        bar.setValue(bar.maximum() // 2)
        app.processEvents()
        option = QtWidgets.QStyleOptionSlider()
        option.initFrom(bar)
        option.orientation = bar.orientation()
        option.minimum, option.maximum = bar.minimum(), bar.maximum()
        option.sliderPosition, option.sliderValue = bar.sliderPosition(), bar.value()
        option.singleStep, option.pageStep = bar.singleStep(), bar.pageStep()
        handle = bar.style().subControlRect(
            QtWidgets.QStyle.CC_ScrollBar, option,
            QtWidgets.QStyle.SC_ScrollBarSlider, bar,
        )
        point = handle.center()
        QTest.mouseMove(bar, point)
        QTest.mousePress(bar, QtCore.Qt.LeftButton, pos=point)
        QTest.qWait(40)
        image = bar.grab().toImage()
        handle_color = image.pixelColor(point)
        track_y = 2 if handle.top() > bar.height() // 2 else image.height() - 3
        track = image.pixelColor(point.x(), track_y)
        assert abs(handle_color.lightness() - track.lightness()) > 35, (
            f'bar={bar.size()}, handle={handle}, handle_color={handle_color.name()}, '
            f'track_y={track_y}, track_color={track.name()}'
        )
        QTest.mouseRelease(bar, QtCore.Qt.LeftButton, pos=point)
    finally:
        dialog.close()
        dialog.deleteLater()


def test_tray_toggle_and_settings_use_one_state(app, owner, monkeypatch):
    import desktop_assistant
    factory = mock.Mock()
    monkeypatch.setattr(desktop_assistant, 'DesktopAssistant', factory)
    owner.settings_window = None
    owner._cached_settings_window = None
    owner.tray_icon = mock.Mock()
    for name in ('show_window_from_tray', 'launch_copy', 'launch_translate', 'launch_fullscreen_translate',
                 'launch_game_translate', 'exit_app'):
        setattr(owner, name, mock.Mock())
    owner._sync_desktop_assistant = lambda: main.DarkThemeApp._sync_desktop_assistant(owner)
    owner.set_desktop_assistant_enabled = lambda enabled: main.DarkThemeApp.set_desktop_assistant_enabled(owner, enabled)
    main.DarkThemeApp.update_tray_menu(owner)
    action = owner._tray_assistant_action
    assert action.isCheckable() and not action.isChecked()
    action.trigger()
    assert owner.config['desktop_assistant_enabled'] is True
    assert action.isChecked()
    factory.assert_called_once_with(owner)
    owner.set_desktop_assistant_enabled(False)
    assert not action.isChecked()
    factory.return_value.dispose.assert_called_once()
    assert owner.save_config.call_count == 2  # No toggled -> save -> toggled recursion.


def test_capture_animation_setting_is_restored_even_on_popup_error(app, owner, monkeypatch):
    from settings_window import DropDownCombo
    combo = CaptureLanguageCombo(owner)
    calls = mock.Mock()
    monkeypatch.setattr(QtWidgets.QApplication, 'isEffectEnabled', lambda effect: True)
    monkeypatch.setattr(QtWidgets.QApplication, 'setEffectEnabled', calls)
    monkeypatch.setattr(DropDownCombo, 'showPopup', mock.Mock(side_effect=RuntimeError('test popup error')))
    with pytest.raises(RuntimeError, match='test popup error'):
        combo.showPopup()
    assert calls.call_args_list == [mock.call(QtCore.Qt.UI_AnimateCombo, False),
                                   mock.call(QtCore.Qt.UI_AnimateCombo, True)]


def test_main_scaling_uses_local_dirty_rectangles_and_full_theme_refresh(app, owner):
    from ui_scaling import MainWindowScaleController
    window = QtWidgets.QMainWindow()
    controller = MainWindowScaleController(window)
    assert controller.view.viewportUpdateMode() == QtWidgets.QGraphicsView.BoundingRectViewportUpdate
    with mock.patch.object(controller.view.viewport(), 'update') as update:
        controller.apply_theme('QWidget { color: white; }', '#111111')
        update.assert_called()
    window.close()
    window.deleteLater()


def test_main_screen_has_translation_heading_and_larger_preview(app, owner):
    owner.resize(920, 760)
    with mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False), \
            mock.patch.object(main.DarkThemeApp, '_maybe_check_updates_on_launch'):
        window = main.DarkThemeApp()
    window.show()
    app.processEvents()
    title = window.main_text_section.findChild(QtWidgets.QLabel, 'mainTextSectionTitle')
    assert title is not None
    assert len(window.main_text_section.findChildren(QtWidgets.QLabel, 'mainTextSectionTitle')) == 1
    assert title.text() == main.hotkey_language_text(window.current_interface_language, 'text_section')
    assert title.alignment() & QtCore.Qt.AlignCenter
    assert window.assistant_preview.height() >= 24
    assert window.assistant_preview.button.width() >= 28
    line_y = window.assistant_preview.height() - 7
    image = window.assistant_preview.grab().toImage()
    non_transparent = [image.pixelColor(x, line_y).alpha() for x in range(12, max(13, image.width()-12), 8)]
    assert any(alpha > 0 for alpha in non_transparent)
    window.force_quit = True
    window.close()
    window.deleteLater()


def test_assistant_can_be_shooed_until_restart_without_persisting(app, owner):
    class AssistantStub:
        def __init__(self):
            self.disposed = False
        def dispose(self):
            self.disposed = True
    owner.config['desktop_assistant_enabled'] = True
    owner._desktop_assistant = AssistantStub()
    owner._cached_settings_window = None
    owner.settings_window = None
    owner.assistant_preview = QtWidgets.QWidget(owner)
    owner.assistant_preview.show()
    owner._sync_desktop_assistant = lambda: main.DarkThemeApp._sync_desktop_assistant(owner)
    main.DarkThemeApp.dismiss_desktop_assistant_until_restart(owner)
    assert owner.config['desktop_assistant_enabled'] is True
    assert owner._desktop_assistant is None
    assert owner._desktop_assistant_suppressed_until_restart is True
    assert not owner.assistant_preview.isVisible()
    owner.save_config.assert_not_called()


def test_title_flag_is_smaller_and_left_aligned(app, monkeypatch):
    with mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False), \
            mock.patch.object(main.DarkThemeApp, '_maybe_check_updates_on_launch'):
        window = main.DarkThemeApp()
    try:
        assert window.flag_button.geometry().left() == 6
        assert window.flag_button.iconSize() == QtCore.QSize(20, 20)
        assert window.theme_button.iconSize() == QtCore.QSize(24, 24)
    finally:
        window.force_quit = True
        window.close()
        window.deleteLater()


def test_preview_click_opens_current_assistant_settings(app, monkeypatch):
    with mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False), \
            mock.patch.object(main.DarkThemeApp, '_maybe_check_updates_on_launch'):
        window = main.DarkThemeApp()
    window.show()
    app.processEvents()
    try:
        preview = window.assistant_preview
        preview.button.click()
        app.processEvents()
        assert window.settings_window is not None
        assert window.settings_window.settings_assistant_page.isVisible()
        assert window.settings_window.desktop_assistant_checkbox is window.settings_window.settings_assistant_page.toggle
        assert window.settings_window.desktop_assistant_checkbox.isVisible()
        assert window.settings_window.desktop_assistant_dismiss_button.isVisible()
        assert window.settings_window.desktop_assistant_checkbox.hasFocus()
        assert window.config.get('desktop_assistant_enabled') is not True
        config = dict(window.config)
        with mock.patch.object(window, 'save_config') as save:
            window.settings_window.desktop_assistant_dismiss_button.click()
            assert not window.settings_window.desktop_assistant_dismiss_button.isEnabled()
            assert window.config == config
            save.assert_not_called()
            window.show_main_screen()
            app.processEvents()
            assert window.assistant_preview.isHidden()
            window.show_desktop_assistant_settings()
            app.processEvents()
            assert not window.settings_window.desktop_assistant_dismiss_button.isEnabled()
    finally:
        window.force_quit = True
        window.close()
        window.deleteLater()
