"""Native bundle smoke check; invoked explicitly by the macOS build workflow."""

import json
import os
import platform
from pathlib import Path
import tempfile
from unittest import mock


def hotkey_dispatch_check():
    """Deliver Carbon events to this process's installed handler, without input synthesis."""
    import ctypes as C
    from macos_hotkeys import registry, _HotkeyID, _fourcc

    owner = registry()
    lib = owner.library
    for name, result, args in (
        ('CreateEvent', C.c_int32, [C.c_void_p, C.c_uint32, C.c_uint32, C.c_double,
                                  C.c_uint32, C.POINTER(C.c_void_p)]),
        ('SetEventParameter', C.c_int32, [C.c_void_p, C.c_uint32, C.c_uint32, C.c_uint32, C.c_void_p]),
        ('SendEventToEventTarget', C.c_int32, [C.c_void_p, C.c_void_p]),
        ('ReleaseEvent', None, [C.c_void_p]),
    ):
        function = getattr(lib, name)
        function.restype, function.argtypes = result, args
    calls = []

    def send(identifier, kind):
        event = C.c_void_p()
        identity = _HotkeyID(owner.signature, identifier)
        assert lib.CreateEvent(None, _fourcc('keyb'), kind, 0, 0, C.byref(event)) == 0
        try:
            assert lib.SetEventParameter(event, _fourcc('----'), _fourcc('hkid'),
                                         C.sizeof(identity), C.byref(identity)) == 0
            return lib.SendEventToEventTarget(event, lib.GetApplicationEventTarget())
        finally:
            lib.ReleaseEvent(event)

    # Event numbers below come from Apple's CarbonEvents.h, independently of
    # the implementation. Registration alone never tests handler delivery.
    for generation in range(2):
        identifier = owner.register('Ctrl+Alt+Shift+F18', lambda: calls.append('pressed'))
        try:
            assert send(identifier, 6) == 0  # release before any press is harmless
            assert len(calls) == generation * 5
            for press in range(5):
                assert send(identifier, 5) == 0
                assert len(calls) == generation * 5 + press + 1, 'Press was not delivered'
                assert send(identifier, 5) == 0  # held key does not repeat the action
                assert len(calls) == generation * 5 + press + 1
                assert send(identifier, 6) == 0
                assert identifier not in owner.pressed, 'Release left shortcut stuck'
        finally:
            owner.unregister(identifier)
        assert send(identifier, 5) != 0  # removed IDs cannot trigger callbacks
    assert len(calls) == 10
    return {'callbacks': 10, 'registrations': 2, 'repeat_suppression': 'passed',
            'release_and_reregister': 'passed', 'delivery': 'Carbon SendEventToEventTarget, own process'}


def shadow_mode_check(main, app, window):
    """Check real Dock policies and the live status item across window actions."""
    import AppKit
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QSystemTrayIcon

    nsapp = AppKit.NSApplication.sharedApplication()
    position = window.pos()
    providers = {key: window.config.get(key) for key in ('ocr_engine', 'translator_engine')}
    results = []

    def check(name, policy, visible, minimized=False):
        QTest.qWait(160)
        assert int(nsapp.activationPolicy()) == policy, (name, nsapp.activationPolicy())
        assert window.isVisible() == visible, name
        assert window.isMinimized() == minimized, name
        assert window.tray_icon.isVisible() and not window.tray_icon.icon().isNull(), name
        rect = window.tray_icon.geometry()
        assert not rect.isEmpty(), (name, rect)
        menu = window.tray_icon.contextMenu()
        assert menu is window._tray_menu and menu.parent() is window
        assert len([action for action in menu.actions() if not action.isSeparator()]) == 6
        if visible and not minimized:
            assert window.pos() == position, (name, window.pos(), position)
        results.append({'state': name, 'activation_policy': policy, 'window_visible': visible,
                        'minimized': minimized,
                        'tray_geometry': [rect.x(), rect.y(), rect.width(), rect.height()],
                        'tray_on_screen': any(screen.geometry().intersects(rect) for screen in app.screens())})

    # Same path used by --autostart with start_minimized, before the first show.
    window.minimize_to_tray()
    check('startup-shadow', 1, False)
    window._tray_menu.actions()[0].trigger()
    check('open-from-menu', 0, True)
    window.start_button.click()
    check('shadow-button', 1, False)
    window.on_tray_icon_activated(QSystemTrayIcon.Trigger)
    check('menu-click-keeps-shadow', 1, False)
    window.update_tray_menu()
    check('menu-rebuilt-in-shadow', 1, False)
    dialog = main.TranslationResultDialog(window, 'Привет', auto_copy=False, source_text='Hello')
    dialog.show()
    check('result-in-shadow', 1, False)
    assert dialog.isVisible()
    dialog.close()
    dialog.deleteLater()
    shadow_hotkeys = hotkey_dispatch_check()
    window.toggle_window_visibility()
    check('hotkey-restores', 0, True)
    window.toggle_window_visibility()
    check('hotkey-hides-to-shadow', 1, False)
    window.show_window_from_tray(force_show=True)
    window.close()
    check('close-to-shadow', 1, False)
    window.show_window_from_tray(force_show=True)
    window.minimize_to_taskbar()
    check('titlebar-minimize-in-dock', 0, True, True)
    window.toggle_window_visibility()
    check('restore-from-dock', 0, True)
    with mock.patch.object(window, 'tray_available', False):
        window.minimize_to_tray()
        check('no-tray-dock-fallback', 0, True, True)
    window.show_window_from_tray(force_show=True)
    check('final-restore', 0, True)
    assert providers == {key: window.config.get(key) for key in providers}
    return {'cases': len(results), 'states': results, 'shadow_hotkey_callbacks': shadow_hotkeys['callbacks'],
            'scope': 'own Cocoa NSApplication and QSystemTrayIcon; Qt actions, no physical menu-bar click'}


def dialog_placement_check(main, app, window, report_path, screenshots):
    """Exercise real secondary windows with a displaced/scaled native owner."""
    from PyQt5 import QtCore
    from PyQt5.QtTest import QTest
    import settings_window as settings
    from styled_dialogs import StyledMessageBox

    results = []
    for theme in ('dark', 'light'):
        expected_theme = 'Темная' if theme == 'dark' else 'Светлая'
        if window.current_theme != expected_theme:
            window.toggle_theme()
        for percent in (80, 100, 130):
            actual = window.set_ui_scale_percent(percent)
            bounds = window.screen().availableGeometry()
            window.move(bounds.left() + min(80, max(0, bounds.width() - window.width())),
                        bounds.top() + min(90, max(0, bounds.height() - window.height())))
            window.show_settings()
            owner = window.settings_window
            with mock.patch.object(QtCore.QTimer, 'singleShot'):
                packages = settings.OcrLanguageManagerDialog(owner)
            dialogs = [
                ('packages', packages), ('update', settings.UpdateProgressDialog(owner)),
                ('install', settings.TesseractInstallProgressDialog(owner)),
                ('argos-confirm', main.ArgosPackageInstallDialog(window, 'English → Русский')),
                ('argos-error', main.ArgosTranslationErrorDialog(window, 'English → Русский', 'Fixture error')),
                ('result', main.TranslationResultDialog(window, 'Привет', auto_copy=False, source_text='Hello')),
                ('document', main.DocumentTranslationDialog(window)), ('message', StyledMessageBox(owner)),
            ]
            dialogs[-1][1].setText('Проверка расположения окна')
            for name, dialog in dialogs:
                dialog.show()
                QTest.qWait(100)
                frame = dialog.frameGeometry()
                center = window.frameGeometry().center()
                x = max(bounds.left(), min(center.x() - (frame.width() - 1) // 2,
                                          bounds.right() - frame.width() + 1))
                y = max(bounds.top(), min(center.y() - (frame.height() - 1) // 2,
                                         bounds.bottom() - frame.height() + 1))
                assert frame.topLeft() == QtCore.QPoint(x, y), (name, frame, x, y)
                assert bounds.contains(frame), (name, frame, bounds)
                filename = f'{report_path.stem}-position-{theme}-{percent}-{name}.png'
                picture = dialog.grab()
                assert picture.save(str(report_path.with_name(filename)))
                screenshots.append({'file': filename, 'requested_percent': percent,
                                    'effective_percent': actual, 'width': picture.width(),
                                    'height': picture.height(), 'dpr': picture.devicePixelRatioF()})
                results.append({'window': name, 'theme': theme, 'scale': percent,
                                'geometry': [frame.x(), frame.y(), frame.width(), frame.height()]})
                dialog.close()
                dialog.deleteLater()
                app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    window.show_main_screen()
    return {'cases': len(results), 'checks': 'native owner center and available screen bounds',
            'results': results}


def popup_screenshots(app, window, report_path, screenshots):
    """Check the real NSWindow background as well as Qt's painted corners."""
    import ctypes
    import objc
    from PyQt5 import QtCore, QtWidgets
    from PyQt5.QtTest import QTest
    from styled_dialogs import StatusPopup

    result = {}
    for theme in ('dark', 'light'):
        expected = 'Темная' if theme == 'dark' else 'Светлая'
        if window.current_theme != expected:
            window.toggle_theme()
        window.activateWindow()
        QTest.qWait(100)
        for name in ('tooltip', 'status', 'menu'):
            # A menu or another tooltip can destroy the shared QTipLabel.
            # Inspect and capture each popup before opening the next one.
            if name == 'tooltip':
                button = window.help_button
                QtWidgets.QToolTip.showText(button.mapToGlobal(QtCore.QPoint(0, 25)),
                                           'Native tooltip / Подсказка', button)
                QTest.qWait(50)
                widget = next(w for w in app.topLevelWidgets()
                              if w.metaObject().className() == 'QTipLabel' and w.isVisible())
            elif name == 'status':
                widget = StatusPopup()
                widget.setText('Translation completed / Перевод завершён')
                widget.adjustSize()
                widget.show()
            else:
                widget = QtWidgets.QMenu(window)
                window._apply_main_context_menu_style(widget)
                widget.addAction('Translate / Перевести')
                widget.popup(window.mapToGlobal(QtCore.QPoint(40, 100)))
            QTest.qWait(30)
            try:
                native_view = objc.objc_object(c_void_p=ctypes.c_void_p(int(widget.winId())))
                native_window = native_view.window()
                try:
                    assert not native_window.isOpaque()
                    assert native_window.backgroundColor().alphaComponent() == 0.0
                finally:
                    del native_window, native_view
                picture = widget.grab()
                image = picture.toImage()
                assert image.pixelColor(0, 0).alpha() == 0
                assert widget.mask().isEmpty()
                background = image.pixelColor(image.width() // 2, round(4 * picture.devicePixelRatioF()))
                assert background.alpha() > 240
                filename = f'{report_path.stem}-{theme}-{name}.png'
                assert picture.save(str(report_path.with_name(filename)))
                screenshots.append({'file': filename, 'requested_percent': 100,
                                    'effective_percent': 100, 'width': picture.width(),
                                    'height': picture.height(), 'dpr': picture.devicePixelRatioF()})
                result[f'{theme}_{name}'] = 'transparent Cocoa background; painted surface'
            finally:
                if name == 'tooltip':
                    QtWidgets.QToolTip.hideText()
                    QTest.qWait(350)
                else:
                    widget.close()
                    widget.deleteLater()
                app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    return result


def dropdown_screenshots(main, app, window, report_path, screenshots):
    """Check first/repeated list geometry in the frozen Cocoa application."""
    from PyQt5 import QtCore, QtWidgets
    from PyQt5.QtTest import QTest

    checked = []
    def inspect(combo, name, requested, effective):
        previous = None
        for attempt in (1, 2):
            combo.showPopup()
            QTest.qWait(100)
            popup, view = combo.view().window(), combo.view()
            assert popup.isVisible(), name
            proxy = popup.graphicsProxyWidget()
            if proxy is not None:
                root = combo.window()
                geometry = proxy.mapRectToItem(root.graphicsProxyWidget(), proxy.boundingRect())
                bounds = QtCore.QRectF(root.rect())
                anchor = QtCore.QRectF(QtCore.QRect(combo.mapTo(root, QtCore.QPoint()), combo.size()))
            else:
                geometry = QtCore.QRectF(popup.geometry())
                bounds = QtCore.QRectF(combo._available_screen_rect())
                anchor = QtCore.QRectF(QtCore.QRect(combo.mapToGlobal(QtCore.QPoint()), combo.size()))
            assert bounds.contains(geometry), (name, geometry, bounds)
            assert not anchor.intersects(geometry), (name, anchor, geometry)
            if previous is not None:
                assert geometry == previous, (name, previous, geometry)
            previous = geometry
            if attempt == 1:
                picture = window.grab() if proxy is not None else popup.grab()
                filename = f'{report_path.stem}-combo-{name}.png'
                assert picture.save(str(report_path.with_name(filename)))
                screenshots.append({'file': filename, 'requested_percent': requested,
                                    'effective_percent': effective, 'width': picture.width(),
                                    'height': picture.height(), 'dpr': picture.devicePixelRatioF()})
            view.scrollToBottom()
            app.processEvents()
            last = combo.model().index(combo.count() - 1, combo.modelColumn(), combo.rootModelIndex())
            row = view.visualRect(last)
            visible = row.intersected(view.viewport().rect())
            assert not visible.isEmpty() and visible.height() == row.height(), (name, row, visible)
            combo.hidePopup()
            QTest.qWait(20)
        checked.append(name)

    window.set_interface_language('ru')
    for theme in ('dark', 'light'):
        expected = 'Темная' if theme == 'dark' else 'Светлая'
        if window.current_theme != expected:
            window.toggle_theme()
        for percent in (80, 100, 150):
            actual = window.set_ui_scale_percent(percent)
            prefix = f'{theme}-{percent}'
            window.show_main_screen()
            for key in ('source_lang', 'target_lang', 'hotkey_mode_combo',
                        'hotkey_source_combo', 'hotkey_target_combo'):
                inspect(getattr(window, key), prefix + '-main-' + key, percent, actual)
            window.show_settings()
            settings = window.settings_window
            settings._set_settings_page(0)
            for key in ('ocr_engine_combo', 'translator_combo', 'result_window_control'):
                inspect(getattr(settings, key), prefix + '-settings-' + key, percent, actual)
            settings._set_settings_page(2)
            for key in ('game_source_combo', 'game_target_combo'):
                inspect(getattr(settings, key), prefix + '-settings-' + key, percent, actual)
            window.show_main_screen()
            result = main.TranslationResultDialog(window, 'Привет!', auto_copy=False,
                         lang='ru', theme=window.current_theme, source_text='Hello!',
                         source_lang='en', target_lang='ru')
            document = main.DocumentTranslationDialog(window)
            for name, dialog, keys in (
                ('result', result, ('source_combo', 'target_combo')),
                ('document', document, ('source_combo', 'target_combo', 'provider_combo')),
            ):
                dialog.show()
                app.processEvents()
                for key in keys:
                    inspect(getattr(dialog, key), prefix + '-' + name + '-' + key, percent, actual)
                dialog.close()
                dialog.deleteLater()
                app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    return {'cases': len(checked), 'openings': len(checked) * 2,
            'checks': 'stable anchor, available bounds, last row reachable', 'names': checked}


def extended_screenshots(main, app, window, report_path, screenshots):
    """Opt-in native rendering matrix; no input synthesis or user data."""
    from PyQt5 import QtCore, QtWidgets
    from settings_window import OcrLanguageManagerDialog

    def capture(widget, name, requested):
        for _ in range(5):
            app.processEvents()
        picture = widget.grab()
        filename = f'{report_path.stem}-{name}.png'
        assert not picture.isNull() and picture.save(str(report_path.with_name(filename)))
        screenshots.append({'file': filename, 'requested_percent': requested,
                            'effective_percent': window._ui_scale_controller.effective_percent,
                            'width': picture.width(), 'height': picture.height(),
                            'dpr': picture.devicePixelRatioF()})

    for theme in ('dark', 'light'):
        expected = 'Темная' if theme == 'dark' else 'Светлая'
        if window.current_theme != expected:
            window.toggle_theme()
        for language in ('en', 'ru', 'de', 'es', 'fr', 'zh'):
            window.set_interface_language(language)
            for percent in (80, 100, 125, 150, 200):
                window.set_ui_scale_percent(percent)
                prefix = f'{theme}-{language}-{percent}'
                window.show_main_screen()
                capture(window, prefix + '-main', percent)
                window.show_settings()
                for page in range(3):
                    window.settings_window._set_settings_page(page)
                    capture(window, prefix + f'-settings{page}', percent)
            if language not in ('en', 'ru'):
                continue
            window.set_ui_scale_percent(100)
            prefix = f'{theme}-{language}'
            settings = window.settings_window
            # Render package pages without starting network catalogs or
            # optional-engine probes. Their actual runtimes are tested below
            # and by the separate native installation checks.
            with mock.patch.object(QtCore.QTimer, 'singleShot'):
                packages = OcrLanguageManagerDialog(settings)
            packages.show()
            for section, tabs in enumerate((packages.ocr_tabs, packages.translation_tabs)):
                packages.tabs.setCurrentIndex(section)
                for index in range(tabs.count()):
                    tabs.setCurrentIndex(index)
                    capture(packages, prefix + f'-packages{section}-{index}', 100)
            packages.close()
            packages.deleteLater()
            for name, action in (('hotkeys', settings.show_hotkeys_screen),
                                 ('copy-history', settings.show_copy_history_view),
                                 ('translation-history', settings.show_history_view)):
                action()
                capture(window, prefix + '-' + name, 100)
            window.show_main_screen()
            document = main.DocumentTranslationDialog(window)
            document.show()
            capture(document, prefix + '-documents', 100)
            document.close()
            document.deleteLater()
            result = main.TranslationResultDialog(window, 'Привет, мир!\nHello, world!',
                         auto_copy=False, lang=language, theme=window.current_theme,
                         source_text='Hello, world!', source_lang='en', target_lang='ru')
            result.show()
            capture(result, prefix + '-result', 100)
            drafts = result.source_edit.toPlainText(), result.text_edit.toPlainText()
            result.resize(420, 620)
            capture(result, prefix + '-result-narrow', 100)
            assert result._panel_orientation is False
            assert drafts == (result.source_edit.toPlainText(), result.text_edit.toPlainText())
            result.close()
            result.deleteLater()
            def close_help():
                dialog = next((w for w in app.topLevelWidgets()
                               if w.objectName() == 'helpDialogRoot' and w.isVisible()), None)
                assert dialog is not None and dialog.isVisible()
                capture(dialog, prefix + '-help', 100)
                dialog.accept()
                dialog.deleteLater()
            QtCore.QTimer.singleShot(100, close_help)
            window.show_help_dialog()
            window._guide_active = True
            window._guide_step_index = 0
            window._show_guide_step()
            capture(window, prefix + '-guide', 100)
            window.skip_first_run_guide()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def translation_draft_check(main, app, window, report_path, screenshots):
    """Exercise typing and async delivery inside the source and frozen GUI."""
    import time
    import translater
    from PyQt5.QtTest import QTest

    records = []
    for name, reply in (('success', 'Новый перевод'), ('empty', '  \n'),
                        ('error', RuntimeError('Selected provider unavailable'))):
        dialog = main.TranslationResultDialog(window, 'Previous result', auto_copy=False,
                    lang='ru', theme=window.current_theme, source_text='Previous source',
                    source_lang='en', target_lang='ru')
        dialog.show()
        app.processEvents()
        dialog.text_edit.selectAll()
        QTest.keyClicks(dialog.text_edit, 'My new draft')
        provider = mock.Mock(side_effect=reply) if isinstance(reply, Exception) else mock.Mock(return_value=reply)
        with mock.patch.object(translater, 'translate_text', provider), \
                mock.patch.object(main, 'save_translation_history'):
            dialog.translate_button.click()
            deadline = time.monotonic() + 5
            while dialog._retranslating and time.monotonic() < deadline:
                QTest.qWait(10)
            assert not dialog._retranslating
        assert provider.call_args.args == ('My new draft', 'en', 'ru')
        assert provider.call_args.kwargs['engine'] == window.config['translator_engine']
        assert dialog.source_edit.toPlainText() == 'My new draft'
        assert dialog.text_edit.toPlainText() == (reply if name == 'success' else 'My new draft')
        filename = f'{report_path.stem}-draft-{name}.png'
        picture = dialog.grab()
        assert picture.save(str(report_path.with_name(filename)))
        screenshots.append({'file': filename, 'width': picture.width(), 'height': picture.height(),
                            'dpr': picture.devicePixelRatioF()})
        if name == 'success':
            dialog.text_edit.undo()
            assert dialog.text_edit.toPlainText() == 'My new draft'
        records.append({'response': name, 'draft_preserved': True,
                        'selected_engine': provider.call_args.kwargs['engine']})
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
    return {'cases': records, 'scope': 'Native Qt typing and worker delivery; controlled provider replies'}


def main_direction_and_theme_check(main, app, window):
    """Exercise the actual scaled buttons, including Argos before model setup."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    previous = dict(window.config)
    results = {'direction_clicks': 0, 'theme_frames': 0}
    try:
        window.config.update(translator_engine='argos', main_translation_source_language='en',
                             main_translation_target_language='ru', hotkey_language_editor_mode='selection',
                             selection_translate_source_language='en', selection_translate_target_language='ru')
        window.show_main_screen()
        controller = window._ui_scale_controller
        def click(widget):
            QTest.mouseClick(controller.view.viewport(), Qt.LeftButton,
                             pos=controller.map_widget_to_view(widget))
            app.processEvents()
        for percent in (80, 100, 137, 200):
            window.set_ui_scale_percent(percent)
            app.processEvents()
            for expected in (('ru', 'en'), ('en', 'ru')):
                click(window.main_language_swap)
                assert window._configured_main_translation_pair() == expected
                click(window.hotkey_language_swap)
                assert window._configured_hotkey_translation_pair('selection') == expected
                assert window.config['translator_engine'] == 'argos'
                results['direction_clicks'] += 2
        for page in ('main', 'settings'):
            window.show_main_screen() if page == 'main' else window.show_settings()
            for _ in range(4):
                click(window.theme_button)
                expected = main.THEMES[window.current_theme]['background']
                for delay in (0, 40):
                    QTest.qWait(delay)
                    picture = window.grab().toImage()
                    for x in (1, picture.width() - 2):
                        assert picture.pixelColor(x, picture.height() // 2).name() == expected
                    assert controller.scene.backgroundBrush().color().name() == expected
                    results['theme_frames'] += 1
        return results
    finally:
        window.config.update(previous)
        window.current_theme = previous.get('theme', window.current_theme)
        window.apply_theme()
        window.show_main_screen()


def capture_picker_and_notice_check(main, app, window, report_path, screenshots):
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtTest import QTest
    from capture_widgets import CaptureLanguageCombo
    from languages import LANGUAGES, language_icon_path

    previous = dict(window.config)
    old_theme = window.current_theme
    owner = QtWidgets.QWidget()
    combo = CaptureLanguageCombo(owner)
    for language in LANGUAGES:
        combo.addItem(QtGui.QIcon(main.resource_path(language_icon_path(language.code))),
                      language.short_label, language.code)
    combo.setCurrentIndex(combo.findData('en'))
    owner.resize(150, 70)
    owner.move(280, 180)
    try:
        window.config['notifications'] = True
        window.minimize_to_tray()
        for theme, name in (('Светлая', 'light'), ('Темная', 'dark')):
            window.current_theme = theme
            window.apply_theme()
            window._copy_notification_signal.emit('ru')
            QTest.qWait(50)
            notice = window._copy_notice
            assert notice.isVisible() and not window.isVisible()
            assert notice.testAttribute(QtCore.Qt.WA_ShowWithoutActivating)
            assert notice.screen().availableGeometry().contains(notice.geometry())
            owner.show()
            combo.set_capture_theme(theme == 'Темная', 'ru')
            combo.showPopup()
            QTest.qWait(50)
            for kind, widget in (('copy-notice', notice), ('capture-picker', combo.view().window())):
                picture = widget.grab()
                filename = f'{report_path.stem}-{name}-{kind}.png'
                assert picture.save(str(report_path.with_name(filename)))
                screenshots.append({'file': filename, 'width': picture.width(), 'height': picture.height(),
                                    'dpr': picture.devicePixelRatioF()})
            combo.hidePopup()
            owner.hide()
            notice.hide()
        return {'themes': 2, 'notice_visible_in_shadow': True, 'system_tray_notification_used': False,
                'picker': 'full language names, selected checkmark, rounded themed surface'}
    finally:
        combo.hidePopup()
        owner.close()
        owner.deleteLater()
        window._copy_notice.hide()
        window.config.update(previous)
        window.current_theme = old_theme
        window.apply_theme()
        window.show_window_from_tray(force_show=True)


def compact_translation_views_check(main, app, window, report_path, screenshots):
    from PyQt5 import QtCore
    from PyQt5.QtTest import QTest

    previous_config = dict(window.config)
    previous_theme = window.current_theme
    previous_draft = getattr(window, '_main_input_draft', '')
    previous_result = getattr(window, '_main_result_snapshot', None)
    previous_visible = getattr(window, '_main_result_visible', False)
    source = 'A compact window keeps the original text available.'
    result = ('Компактное окно сохраняет исходный текст.\n' * 12) + 'Последняя строка'
    dialog = None
    records = []
    try:
        window.config.update(copy_translated_text=False, result_window_hidden_modes=())
        for theme, name in [('Светлая', 'light'), ('Темная', 'dark')]:
            window.current_theme = theme
            window.show_main_screen()
            window.apply_theme()
            window.main_input_tab.click()
            window.text_input.setPlainText(source)
            QTest.qWait(50)
            size = window.size()

            def capture(kind, widget):
                picture = widget.grab()
                filename = f'{report_path.stem}-{name}-{kind}.png'
                assert picture.save(str(report_path.with_name(filename)))
                screenshots.append({'file': filename, 'width': picture.width(), 'height': picture.height(),
                                    'dpr': picture.devicePixelRatioF()})

            capture('inline-input', window)
            with mock.patch.object(main, 'get_cached_config', return_value=window.config), \
                    mock.patch.object(main, 'save_translation_history'):
                window._present_main_translation_result(result, source, 'en', 'ru')
            QTest.qWait(50)
            assert window.size() == size
            assert window.main_result_view.isVisible() and not window.text_input.isVisible()
            assert window.main_result_view.toPlainText() == result
            assert window.main_result_view.verticalScrollBar().maximum() > 0
            capture('inline-result', window)
            dialog = main.show_translation_dialog(window, result, auto_copy=False, lang='ru', theme=theme,
                                                  source_text=source, source_lang='en', target_lang='ru')
            QTest.qWait(50)
            capture('workspace-expanded', dialog)
            dialog_size = dialog.size()
            dialog.source_toggle.click()
            QTest.qWait(50)
            assert dialog.size() == dialog_size and not dialog.source_panel.isVisible()
            assert dialog.result_panel.isVisible()
            assert dialog.source_edit.toPlainText() == source
            capture('workspace-collapsed', dialog)
            dialog.source_toggle.click()
            assert dialog.source_panel.isVisible()
            dialog.close()
            dialog = None
            window.main_input_tab.click()
            assert window.text_input.toPlainText() == source
            records.append({'theme': theme, 'main_size': [size.width(), size.height()],
                            'inline_scrollable': True, 'source_preserved': True, 'collapse_restores_input': True})
        return {'themes': records, 'provider_calls': False, 'scope': 'native presentation of a supplied result'}
    finally:
        if dialog is not None:
            dialog.close()
        window.config.update(previous_config)
        window.current_theme = previous_theme
        window._main_input_draft = previous_draft
        window._main_result_snapshot = previous_result
        window._main_result_visible = previous_visible
        window.show_main_screen()
        window.apply_theme()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def run(main, report_path):
    import macos_desktop
    import macos_ocr
    from macos_hotkeys import registry
    from PIL import Image, ImageDraw, ImageFont
    from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="cnt-macos-smoke-") as temporary:
        with (mock.patch.object(macos_desktop, "user_data_dir", return_value=temporary),
              mock.patch.object(main, "WelcomeDialog"),
              mock.patch.object(main, "HotkeyListenerThread"),
              mock.patch.object(main.DarkThemeApp, "_maybe_check_updates_on_launch"),
              mock.patch.object(main.DarkThemeApp, "_maybe_show_startup_news"),
              mock.patch.object(main.DarkThemeApp, "_maybe_start_first_run_guide")):
            main.invalidate_config_cache()
            app = main._ensure_startup_application()
            app._mac_reopen_handler = macos_desktop.install_dock_reopen_handler(app, lambda: None)
            window = main.DarkThemeApp()
            shadow_results = shadow_mode_check(main, app, window)
            window.show()
            for _ in range(5):
                app.processEvents()
            assert window.isVisible() and window.text_input.width() > 0
            initial_frame = window.frameGeometry()
            initial_bounds = window.screen().availableGeometry()
            assert initial_frame.center() == initial_bounds.center(), (initial_frame, initial_bounds)
            screenshots = []
            for theme in ('dark', 'light'):
                expected_theme = 'Темная' if theme == 'dark' else 'Светлая'
                if window.current_theme != expected_theme:
                    window.toggle_theme()
                for percent in (100, 150):
                    actual = window.set_ui_scale_percent(percent)
                    for page in ('main', 'settings'):
                        if page == 'main':
                            window.show_main_screen()
                        else:
                            window.show_settings()
                        for _ in range(5):
                            app.processEvents()
                        picture = window.grab()
                        assert not picture.isNull()
                        name = f'{report_path.stem}-{theme}-{page}-{percent}.png'
                        assert picture.save(str(report_path.with_name(name)))
                        screenshots.append({'file': name, 'requested_percent': percent,
                                            'effective_percent': actual, 'width': picture.width(),
                                            'height': picture.height(), 'dpr': picture.devicePixelRatioF()})
                        if page == 'settings':
                            assert window.settings_window.ocr_engine_combo.currentData() == "Apple Vision"
            # Exercise all four position engines' dispatch separately in unit
            # tests; this smoke check runs the actual native Vision framework.
            window.grab().save(str(report_path.with_suffix(".png")))
            if os.environ.get('CLICKNTRANSLATE_EXTENDED_SMOKE') == '1':
                extended_screenshots(main, app, window, report_path, screenshots)
            dropdown_results = dropdown_screenshots(main, app, window, report_path, screenshots)
            placement_results = dialog_placement_check(main, app, window, report_path, screenshots)
            popup_results = popup_screenshots(app, window, report_path, screenshots)
            draft_results = translation_draft_check(main, app, window, report_path, screenshots)
            direction_theme_results = main_direction_and_theme_check(main, app, window)
            capture_notice_results = capture_picker_and_notice_check(main, app, window, report_path, screenshots)
            compact_translation_results = compact_translation_views_check(main, app, window, report_path, screenshots)
            hotkey = registry().register("Ctrl+Alt+Shift+F19", lambda: None)
            try:
                duplicate = registry().register("Ctrl+Alt+Shift+F19", lambda: None)
            except RuntimeError as error:
                assert 'unavailable' in str(error)
            else:
                registry().unregister(duplicate)
                raise AssertionError('Carbon accepted a conflicting shortcut')
            registry().unregister(hotkey)
            hotkey = registry().register("Ctrl+Alt+Shift+F19", lambda: None)
            registry().unregister(hotkey)
            hotkey_delivery = hotkey_dispatch_check()
            image = Image.new("RGB", (900, 130), "white")
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 54)
            ImageDraw.Draw(image).text((30, 25), "CLICK TRANSLATE", font=font, fill="black")
            items = macos_ocr.recognize_image(image, "en")
            assert "TRANSLATE" in " ".join(item[1] for item in items).upper(), items
            report_path.write_text(json.dumps({
                "macos": platform.mac_ver()[0], "architecture": platform.machine(),
                "python": platform.python_version(), "qt": QT_VERSION_STR, "pyqt": PYQT_VERSION_STR,
                "screenshots": screenshots,
                "gui": "ok", "settings": "ok", "theme": "ok", "hotkey_registration": "ok",
                "hotkey_conflict_and_reregister": "ok",
                "permission_preflight": {kind: macos_desktop.permission_granted(kind)
                                         for kind in ('screen', 'accessibility')},
                "vision": "ok", "vision_languages": macos_ocr.supported_languages(),
                "native_popup_surfaces": popup_results,
                "dropdowns": dropdown_results,
                "hotkey_event_delivery": hotkey_delivery,
                "window_placement": placement_results,
                "shadow_mode": shadow_results,
                "translation_drafts": draft_results,
                "main_direction_and_theme": direction_theme_results,
                "capture_picker_and_notice": capture_notice_results,
                "compact_translation_views": compact_translation_results,
            }, indent=2), encoding="utf-8")
            window.force_quit = True
            window.close()
            window.deleteLater()
            app.processEvents()
            main.dispose_native_application(app)
    return 0
