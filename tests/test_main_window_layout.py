"""The main window has to say where to start.

It used to open with three stacked rows of language pickers — the hotkey pair
first, then the text pair — a 56px text box, an outlined Translate button and a
solid accent "Shadow mode" bar underneath it. Measured: 126px of language
pickers against 56px for the thing the window is for, and the only filled button
sent the window away.

The order now follows the task: pick a direction, type, translate. Everything
below the divider is settings and reference.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5 import QtCore  # noqa: E402
from PyQt5.QtCore import QEvent, Qt  # noqa: E402
from PyQt5.QtGui import QImage, QMouseEvent, QTextCursor  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication, QFrame, QWidget  # noqa: E402

import main  # noqa: E402
import layout_editor  # noqa: E402
from qt_layout_test_support import ensure_layout_fonts

LANGUAGES = ("en", "ru", "es", "de", "fr", "zh")


class MainScreenSourceTest(unittest.TestCase):
    """Assertions about how the screen is built, without building the app."""

    @staticmethod
    def _source():
        import inspect

        return inspect.getsource(main.DarkThemeApp.show_main_screen)

    def test_the_blocks_are_added_in_task_order(self):
        source = self._source()
        order = [
            "text_section_layout.addLayout(language_picker_layout)",
            "text_section_layout.addWidget(self.main_composer, 1)",
            "self.main_layout.addWidget(self.main_text_section, 1)",
            "shortcut_section_layout.addWidget(self.hotkey_language_bar)",
            "self.main_layout.addWidget(self.main_shortcut_section)",
            "self.main_layout.addWidget(self.main_footer)",
        ]
        positions = []
        for marker in order:
            self.assertIn(marker, source, marker)
            positions.append(source.index(marker))
        self.assertEqual(positions, sorted(positions), "the blocks are out of order")

    def test_the_direction_pair_is_one_row(self):
        source = self._source()
        self.assertIn("language_picker_layout = QHBoxLayout()", source)
        # Two stacked full-width combos read as two unrelated settings.
        self.assertNotIn("language_picker_layout = QVBoxLayout()", source)

    def test_translate_is_inside_the_chat_composer(self):
        source = self._source()
        translate = source[source.index("mainTranslateButton"):source.index("shortcut_section_layout.addWidget(self.hotkey_language_bar)")]
        shadow = source[source.index("mainShadowButton"):]

        self.assertIn("composer_actions_layout.addWidget", translate)
        self.assertIn("Qt.AlignHCenter | Qt.AlignBottom", translate)
        self.assertIn("self.text_input.setViewportMargins(0, 0, 0, 0)", source)
        self.assertIn("self.text_input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)", source)
        self.assertIn("text_section_layout.addWidget(self.main_composer, 1)", translate)
        self.assertNotIn("self.main_layout.addWidget(self.translate_button)", translate)
        self.assertIn("self.translate_button = ScaledIconButton()", source)
        self.assertIn("self.translate_button.setFixedSize(32, 32)", translate)
        self.assertIn("self.document_expand_button.hide()", source)
        self.assertIn("_apply_main_translate_button_theme", translate)
        self.assertNotIn("background-color: #C5B3E9", shadow)

    def test_main_reference_text_keeps_a_readable_size(self):
        # The helper lives outside show_main_screen, so inspect it directly.
        import inspect

        helper = inspect.getsource(main.DarkThemeApp._create_main_hotkey_pair)
        theme = inspect.getsource(main.DarkThemeApp._apply_main_combo_theme)
        self.assertIn('font-size: 14px', helper)
        self.assertIn('font-size: 13px', helper)
        self.assertIn('font-size: 12px', helper)
        self.assertIn('font_size = 13', theme)

    def test_the_text_box_has_room_to_be_the_focus(self):
        source = self._source()
        # Reserve a real gap below the language pickers within the fixed
        # 700x400 viewport, while retaining three readable lines of text.
        self.assertIn("self.main_composer.setMinimumHeight(74)", source)
        self.assertIn("self.text_input.setMinimumHeight(66)", source)


class HotkeyBarTextTest(unittest.TestCase):
    def test_every_language_has_a_short_caption_and_keeps_the_full_sentence(self):
        for language in LANGUAGES:
            caption = main.hotkey_language_text(language, "bar_caption")
            hint = main.hotkey_language_text(language, "bar_hint")
            self.assertTrue(caption, language)
            self.assertLessEqual(len(caption), 14, (language, caption))
            # The sentence is not lost: it became the bar's tooltip.
            self.assertGreater(len(hint), len(caption), language)

    def test_every_shortcut_has_localized_hover_help(self):
        for language in LANGUAGES:
            for action in ("copy", "ocr", "fullscreen", "game", "selection", "replace", "toggle"):
                self.assertTrue(main.main_hotkey_tooltip(language, action), (language, action))


class MainWindowGeometryTest(unittest.TestCase):
    """Built for real, because heights are the whole point.

    Stop the app before running this: a live instance owns the single-instance
    handshake, and a second window built here waits on it forever.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        ensure_layout_fonts(cls.app)
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        # The window opens its welcome dialog on a fresh config, and a modal
        # dialog in a test run waits for a click that never comes.
        welcome = mock.patch.object(main, "WelcomeDialog")
        welcome.start()
        self.addCleanup(welcome.stop)
        update_check = mock.patch.object(
            main.DarkThemeApp, "_maybe_check_updates_on_launch"
        )
        update_check.start()
        self.addCleanup(update_check.stop)
        startup_news = mock.patch.object(
            main.DarkThemeApp, "_maybe_show_startup_news"
        )
        startup_news.start()
        self.addCleanup(startup_news.stop)
        guide = mock.patch.object(main.DarkThemeApp, "_maybe_start_first_run_guide")
        guide.start()
        self.addCleanup(guide.stop)
        hotkey_listener = mock.patch.object(main, "HotkeyListenerThread")
        hotkey_listener.start()
        self.addCleanup(hotkey_listener.stop)

        try:
            self.window = main.DarkThemeApp()
        except Exception as error:                      # pragma: no cover
            self.skipTest(f"the main window cannot be built here: {error}")
        self.window.show()
        for _ in range(6):
            self.app.processEvents()

    def tearDown(self):
        # closeEvent normally minimizes a live application to the tray. Tests
        # need a real shutdown so the next window does not inherit Qt objects
        # and background workers from the previous case.
        self.window.force_quit = True
        self.window.close()
        self.window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def _blocks(self):
        layout = self.window.main_layout
        return [layout.itemAt(index) for index in range(layout.count())]

    def test_inline_result_preserves_input_and_fixed_window_across_pages(self):
        window = self.window
        source = 'A draft that stays available.'
        result = ('Длинный перевод со всеми строками.\n' * 50) + 'LAST LINE'
        window.text_input.setPlainText(source)
        initial_size = window.size()
        with mock.patch.object(main, 'get_cached_config', return_value=dict(
                window.config, result_window_hidden_modes=(), copy_translated_text=True)), \
                mock.patch.object(main, 'save_translation_history') as history, \
                mock.patch.object(main, 'save_copy_history'), \
                mock.patch.object(main.platform_support, 'copy_text') as copy, \
                mock.patch.object(main, 'show_translation_dialog') as dialog:
            window._present_main_translation_result(result, source, 'en', 'ru')
            self.app.processEvents()
            self.assertTrue(window.main_result_view.isVisible())
            self.assertTrue(window.text_input.isVisible())
            self.assertEqual(window.size(), initial_size)
            self.assertEqual(window.main_result_view.toPlainText(), result)
            self.assertGreater(window.main_result_view.verticalScrollBar().maximum(), 0)
            copy.assert_called_once_with(result)
            history.assert_called_once_with(source, result, 'ru')
            dialog.assert_not_called()
            self.assertTrue(window.text_input.isVisible())
            self.assertEqual(window.text_input.toPlainText(), source)
            window.text_input.insertPlainText(' New edit.')
            edited_source = window.text_input.toPlainText()
            self.assertEqual(window.main_result_caption.text(),
                             main.TRANSLATION_RESULT_DIALOG_TEXT[window.current_interface_language]['previous_result'])
            for theme in ('Светлая', 'Темная'):
                window.current_theme = theme
                window.apply_theme()
                self.app.processEvents()
                self.assertEqual(window.size(), initial_size)
                self.assertEqual(window.main_result_view.toPlainText(), result)
            window.show_main_screen()
            self.app.processEvents()
            self.assertTrue(window.main_result_view.isVisible())
            self.assertEqual(window.text_input.toPlainText(), edited_source)
            window.main_result_expand_button.click()
            self.assertEqual(dialog.call_args.kwargs['source_text'], source)
            self.assertEqual(dialog.call_args.kwargs['translated_text'], result)
            self.assertFalse(dialog.call_args.kwargs['auto_copy'])
            copy.assert_called_once()  # Expanding does not copy the result twice.

    def test_failed_main_translation_keeps_draft_and_previous_result(self):
        window = self.window
        window._show_inline_main_result('Previous result', 'Previous input', 'en', 'ru')
        window.text_input.setPlainText('A new draft')
        with mock.patch.object(main, 'get_cached_config', return_value=dict(window.config, translator_engine='Lingva')), \
                mock.patch.object(main.translater, 'translate_text', side_effect=RuntimeError('Provider unavailable')), \
                mock.patch.object(main.QMessageBox, 'warning') as warning:
            window.translate_input_text()
        self.assertIn('Provider unavailable', warning.call_args.args[-1])
        self.assertEqual(window.text_input.toPlainText(), 'A new draft')
        self.assertEqual(window.main_result_view.toPlainText(), 'Previous result')
        self.assertTrue(window.text_input.isVisible())
        with mock.patch.object(main, 'get_cached_config', return_value=dict(window.config, translator_engine='Lingva')), \
                mock.patch.object(main.translater, 'translate_text', return_value=''), \
                mock.patch.object(main, 'save_translation_history') as history, \
                mock.patch.object(main.QMessageBox, 'warning') as warning:
            window.translate_input_text()
        warning.assert_called_once()
        history.assert_not_called()
        self.assertEqual(window.text_input.toPlainText(), 'A new draft')
        self.assertEqual(window.main_result_view.toPlainText(), 'Previous result')

    def test_the_chat_composer_stays_compact(self):
        # A Telegram-style composer is deliberately shorter than the settings
        # panel below it, while still fitting two placeholder/text lines.
        self.assertGreaterEqual(self.window.text_input.height(), 66)
        self.assertGreaterEqual(self.window.main_composer.height(), 74)
        self.assertLess(self.window.main_composer.height(), self.window.main_shortcut_section.height())

    def test_visual_constructor_edits_real_widgets_and_keeps_a_separate_draft(self):
        with tempfile.TemporaryDirectory() as temporary:
            draft_path = Path(temporary) / "layout.json"
            panel = layout_editor.LayoutEditorPanel(self.window, draft_path)
            panel.show()
            for _ in range(4):
                self.app.processEvents()
            try:
                # Rapid page changes used to leave several zero-delay overlay
                # rebuilds queued. They reparented the same Qt controls more
                # than once and could crash Windows with an access violation.
                for _ in range(3):
                    for screen in ("settings0", "settings1", "settings2", "main"):
                        panel.show_screen(screen)
                for _ in range(8):
                    self.app.processEvents()
                self.assertEqual(panel.screen, "main")
                self.assertTrue(all(
                    button.isEnabled() for button in panel.screen_buttons.values()
                ))
                self.assertTrue(panel.overlay._detached_buttons)
                for control, info in panel.overlay._detached_buttons.items():
                    if info["key"] not in panel.values["widgets"]["main"]:
                        self.assertEqual(
                            control.pos(), info["absolute"].topLeft(), info["key"]
                        )
                theme_default_position = panel.overlay._detached_buttons[
                    self.window.theme_button
                ]["absolute"].topLeft()
                detached_keys = {
                    info["key"] for info in panel.overlay._detached_buttons.values()
                }
                self.assertIn("main_input_caption", detached_keys)
                self.assertIn("main_result_caption", detached_keys)
                self.assertIn("mainShortcutSectionTitle", detached_keys)
                self.assertIn("mainOcrSummary", detached_keys)
                source_info = panel.overlay._detached_buttons[self.window.source_lang]
                translate_info = panel.overlay._detached_buttons[self.window.translate_button]
                source_target = panel.target_by_id(f"button:{source_info['key']}")
                translate_target = panel.target_by_id(f"button:{translate_info['key']}")
                marquee = source_target["rect"].united(translate_target["rect"])
                panel.area_select_button.setChecked(True)
                panel.overlay.mousePressEvent(QMouseEvent(
                    QEvent.MouseButtonPress,
                    QtCore.QPointF(marquee.topLeft()),
                    Qt.LeftButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                ))
                panel.overlay.mouseMoveEvent(QMouseEvent(
                    QEvent.MouseMove,
                    QtCore.QPointF(marquee.bottomRight()),
                    Qt.NoButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                ))
                panel.overlay.mouseReleaseEvent(QMouseEvent(
                    QEvent.MouseButtonRelease,
                    QtCore.QPointF(marquee.bottomRight()),
                    Qt.LeftButton,
                    Qt.NoButton,
                    Qt.NoModifier,
                ))
                self.assertTrue({
                    f"button:{source_info['key']}",
                    f"button:{translate_info['key']}",
                }.issubset(panel.overlay._selected_ids))
                self.assertFalse(panel.area_selection_mode)
                title_info = panel.overlay._detached_buttons[self.window.title_bar]
                panel.select_target(f"button:{title_info['key']}")
                panel.text_edit.setText("Click'n'Translate — макет")
                panel.apply_selected_text()
                self.assertEqual(
                    self.window.title_bar.text(), "Click'n'Translate — макет"
                )
                self.assertEqual(
                    panel.values["widgets"]["main"][title_info["key"]]["text"],
                    "Click'n'Translate — макет",
                )
                self.window.activateWindow()
                QTest.keyClick(self.window, Qt.Key_Z, Qt.ControlModifier)
                for _ in range(3):
                    self.app.processEvents()
                self.assertEqual(
                    self.window.title_bar.text(),
                    main.INTERFACE_TEXT[self.window.current_interface_language]["title"],
                )
                # The properties editor has its own native text-undo behavior.
                # Ctrl+Z must still undo the layout command, not only edit the
                # QLineEdit, because that is where a designer usually has focus.
                title_info = panel.overlay._detached_buttons[self.window.title_bar]
                panel.select_target(f"button:{title_info['key']}")
                panel.text_edit.setText("Click'n'Translate — второй макет")
                panel.apply_selected_text()
                panel.text_edit.setFocus()
                QTest.keyClick(panel.text_edit, Qt.Key_Z, Qt.ControlModifier)
                for _ in range(3):
                    self.app.processEvents()
                self.assertEqual(
                    self.window.title_bar.text(),
                    main.INTERFACE_TEXT[self.window.current_interface_language]["title"],
                )
                translate_button = self.window.translate_button
                button_info = panel.overlay._detached_buttons[translate_button]
                button_origin = translate_button.pos()
                local_start = translate_button.rect().center()
                local_finish = local_start + QtCore.QPoint(24, 11)
                panel.overlay.eventFilter(translate_button, QMouseEvent(
                    QEvent.MouseButtonPress,
                    QtCore.QPointF(local_start),
                    Qt.LeftButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                ))
                panel.overlay.eventFilter(translate_button, QMouseEvent(
                    QEvent.MouseMove,
                    QtCore.QPointF(local_finish),
                    Qt.NoButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                ))
                panel.overlay.eventFilter(translate_button, QMouseEvent(
                    QEvent.MouseButtonRelease,
                    QtCore.QPointF(local_finish),
                    Qt.LeftButton,
                    Qt.NoButton,
                    Qt.NoModifier,
                ))
                expected_x, expected_y = panel.overlay._snap_position(
                    button_origin.x() + 24,
                    button_origin.y() + 11,
                    translate_button.width(),
                    translate_button.height(),
                )
                expected_button_position = QtCore.QPoint(expected_x, expected_y)
                self.assertEqual(translate_button.pos(), expected_button_position)
                self.assertEqual(
                    panel.values["widgets"]["main"][button_info["key"]],
                    {"x": translate_button.x(), "y": translate_button.y()},
                )

                source_combo = self.window.source_lang
                source_info = panel.overlay._detached_buttons[source_combo]
                translate_origin = QtCore.QPoint(translate_button.pos())
                source_origin = QtCore.QPoint(source_combo.pos())
                panel.select_targets([
                    f"button:{button_info['key']}",
                    f"button:{source_info['key']}",
                ])
                panel.nudge_selected(0, 1)
                self.assertEqual(
                    translate_button.y() - translate_origin.y(),
                    panel.overlay._grid_size(),
                )
                self.assertEqual(
                    source_combo.y() - source_origin.y(),
                    panel.overlay._grid_size(),
                )
                panel.undo_layout()
                for _ in range(4):
                    self.app.processEvents()
                translate_button = self.window.translate_button
                self.assertEqual(translate_button.pos(), translate_origin)
                self.assertEqual(self.window.source_lang.pos(), source_origin)

                engine = next(
                    target
                    for target in panel.overlay.targets()
                    if target["id"] == "engine"
                )
                original_width = panel.values["main"]["engine_status_width"]
                # Status labels are stacked now; use the empty trailing gutter.
                start = QtCore.QPoint(engine["rect"].right() - 2, engine["rect"].center().y())
                finish = start + QtCore.QPoint(16, 0)
                panel.overlay.mousePressEvent(QMouseEvent(
                    QEvent.MouseButtonPress,
                    QtCore.QPointF(start),
                    Qt.LeftButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                ))
                panel.overlay.mouseMoveEvent(QMouseEvent(
                    QEvent.MouseMove,
                    QtCore.QPointF(finish),
                    Qt.NoButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                ))
                panel.overlay.mouseReleaseEvent(
                    QMouseEvent(
                        QEvent.MouseButtonRelease,
                        QtCore.QPointF(finish),
                        Qt.LeftButton,
                        Qt.NoButton,
                        Qt.NoModifier,
                    )
                )
                self.app.processEvents()
                self.assertEqual(
                    panel.values["main"]["engine_status_width"],
                    original_width - 16,
                )
                self.assertTrue(draft_path.is_file())

                copy_target = next(
                    target
                    for target in panel.overlay.targets()
                    if target["id"] == "hotkey:copy"
                )
                copy_widget = copy_target["resize_widget"]
                original_copy_size = QtCore.QSize(copy_widget.size())
                resize_start = copy_target["rect"].topRight() + QtCore.QPoint(-2, 2)
                resize_finish = resize_start + QtCore.QPoint(16, 8)
                panel.overlay.mousePressEvent(QMouseEvent(
                    QEvent.MouseButtonPress,
                    QtCore.QPointF(resize_start),
                    Qt.LeftButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                ))
                panel.overlay.mouseMoveEvent(QMouseEvent(
                    QEvent.MouseMove,
                    QtCore.QPointF(resize_finish),
                    Qt.NoButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                ))
                panel.overlay.mouseReleaseEvent(QMouseEvent(
                    QEvent.MouseButtonRelease,
                    QtCore.QPointF(resize_finish),
                    Qt.LeftButton,
                    Qt.NoButton,
                    Qt.NoModifier,
                ))
                copy_size_draft = panel.values["widgets"]["main"]["hotkey_card_copy"]
                self.assertGreater(copy_widget.width(), original_copy_size.width())
                self.assertEqual(copy_size_draft["w"], copy_widget.width())
                self.assertEqual(copy_size_draft["h"], copy_widget.height())

                copy_target = next(
                    target
                    for target in panel.overlay.targets()
                    if target["id"] == "hotkey:copy"
                )
                copy_start = QtCore.QPoint(
                    copy_target["rect"].center().x(),
                    copy_target["rect"].top() + 4,
                )
                empty_slot = panel.overlay._main_slots()[7].center()
                panel.overlay.mousePressEvent(QMouseEvent(
                    QEvent.MouseButtonPress,
                    QtCore.QPointF(copy_start),
                    Qt.LeftButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                ))
                panel.overlay.mouseMoveEvent(QMouseEvent(
                    QEvent.MouseMove,
                    QtCore.QPointF(empty_slot),
                    Qt.NoButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                ))
                panel.overlay.mouseReleaseEvent(QMouseEvent(
                    QEvent.MouseButtonRelease,
                    QtCore.QPointF(empty_slot),
                    Qt.LeftButton,
                    Qt.NoButton,
                    Qt.NoModifier,
                ))
                for _ in range(3):
                    self.app.processEvents()
                self.assertEqual(
                    panel.values["main"]["hotkey_order"][7], "copy"
                )

                panel.show_screen("settings1")
                for _ in range(3):
                    self.app.processEvents()
                detached_keys = {
                    info["key"]
                    for info in panel.overlay._detached_buttons.values()
                }
                self.assertTrue({
                    "export_settings_btn",
                    "import_settings_btn",
                    "create_bug_report_btn",
                    "update_check_on_launch_checkbox",
                }.issubset(detached_keys))
                self.assertNotIn("autostart_checkbox", detached_keys)
                self.assertNotIn("ocr_engine_combo", detached_keys)
                self.assertTrue(
                    any(
                        target["id"] == "settings-actions"
                        for target in panel.overlay.targets()
                    )
                )
                panel.show_screen("settings2")
                for _ in range(3):
                    self.app.processEvents()
                detached_keys = {
                    info["key"]
                    for info in panel.overlay._detached_buttons.values()
                }
                self.assertTrue({
                    "game_source_combo",
                    "game_target_combo",
                    "game_scan_interval_slider",
                    "game_overlay_opacity_slider",
                }.issubset(detached_keys))
                self.assertNotIn("autostart_checkbox", detached_keys)
                self.assertNotIn("export_settings_btn", detached_keys)
                panel.show_screen("main")
                for _ in range(3):
                    self.app.processEvents()
                restored_translate = self.window.translate_button
                saved_translate = panel.values["widgets"]["main"][
                    "translate_button"
                ]
                self.assertEqual(
                    restored_translate.pos(),
                    QtCore.QPoint(saved_translate["x"], saved_translate["y"]),
                )
                self.assertEqual(
                    self.window.theme_button.pos(), theme_default_position
                )
                self.assertEqual(
                    self.window.main_hotkey_references["copy"].size(),
                    QtCore.QSize(copy_size_draft["w"], copy_size_draft["h"]),
                )
                panel.language_combo.setCurrentIndex(
                    panel.language_combo.findData("de")
                )
                panel.theme_combo.setCurrentIndex(
                    panel.theme_combo.findData("Светлая")
                )
                for _ in range(4):
                    self.app.processEvents()
                self.assertEqual(
                    self.window.translate_button.pos(),
                    QtCore.QPoint(saved_translate["x"], saved_translate["y"]),
                )
                self.assertEqual(
                    self.window.main_hotkey_references["copy"].size(),
                    QtCore.QSize(copy_size_draft["w"], copy_size_draft["h"]),
                )
            finally:
                panel.overlay.hide()
                panel.hide()
                panel.deleteLater()
                self.window.show_main_screen()
                self.app.processEvents()

    def test_send_action_sits_below_and_to_the_right_of_the_text_view(self):
        button = self.window.translate_button
        text = self.window.text_input
        button_top_left = button.mapTo(self.window.ui_root, button.rect().topLeft())
        text_top_left = text.mapTo(self.window.ui_root, text.rect().topLeft())
        button_left = button_top_left.x()
        button_bottom = button_top_left.y() + button.height() - 1
        text_right = text_top_left.x() + text.width() - 1
        text_bottom = text_top_left.y() + text.height() - 1

        self.assertGreaterEqual(button_left, text_right)
        self.assertLessEqual(abs(button_bottom - text_bottom), 2)

    def test_long_input_offers_document_mode_without_a_scrollbar(self):
        editor = self.window.text_input
        expand = self.window.document_expand_button

        self.assertEqual(editor.verticalScrollBarPolicy(), Qt.ScrollBarAsNeeded)
        editor.setPlainText("one\ntwo")
        for _ in range(3):
            self.app.processEvents()
        self.assertFalse(expand.isVisible())

        editor.setPlainText("one\ntwo\nthree")
        for _ in range(3):
            self.app.processEvents()
        self.assertTrue(expand.isVisible())

    def test_document_workspace_reopens_and_receives_composer_text(self):
        text = "one\ntwo\nthree\nfour"
        self.window.text_input.setPlainText(text)
        for _ in range(3):
            self.app.processEvents()

        QTest.mouseClick(self.window.document_expand_button, Qt.LeftButton)
        self.app.processEvents()
        dialog = self.window.document_dialog
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.original_view.toPlainText(), text)

        dialog.close()
        self.app.processEvents()
        self.assertFalse(dialog.isVisible())
        reopened = self.window.open_document_translation()
        self.app.processEvents()
        self.assertIs(reopened, dialog)
        self.assertTrue(reopened.isVisible())

    def test_cached_document_workspace_uses_the_current_light_theme_when_reopened(self):
        dialog = self.window.open_document_translation()
        self.app.processEvents()
        dialog.close()
        self.app.processEvents()

        self.window.current_theme = "Светлая"
        reopened = self.window.open_document_translation()
        self.app.processEvents()

        self.assertIs(reopened, dialog)
        self.assertEqual(reopened.theme_name, "Светлая")
        # Verify the painted surfaces instead of pinning a particular shade.
        for surface in (reopened.window_frame, reopened.original_view.viewport(),
                        reopened.translated_view.viewport()):
            image = surface.grab().toImage()
            pixel = image.pixelColor(image.width() // 2, image.height() - round(12 * image.devicePixelRatio()))
            self.assertGreater(pixel.lightness(), 200)

    def test_the_two_language_pickers_sit_on_one_line(self):
        source = self.window.source_lang
        target = self.window.target_lang

        self.assertEqual(source.y(), target.y())
        self.assertLess(source.x(), target.x())

    def test_document_workspace_has_a_persistent_title_bar_entry(self):
        button = self.window.document_button
        self.assertFalse(button.icon().isNull())
        self.assertEqual(
            button.accessibleName(),
            main.doc_text(self.window.current_interface_language, "title"),
        )
        self.assertLess(button.x(), self.window.help_button.x())
        self.assertLess(self.window.help_button.x(), self.window.settings_button.x())

    def test_document_icon_uses_black_and_white_contours(self):
        def visible_rgb(icon):
            image = icon.pixmap(64, 64).toImage().convertToFormat(
                QImage.Format_ARGB32
            )
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    if color.alpha() >= 240:
                        return color.red(), color.green(), color.blue()
            self.fail("Document icon produced no opaque pixels")

        self.assertEqual(visible_rgb(main.document_translation_icon("Светлая")), (0, 0, 0))
        self.assertEqual(visible_rgb(main.document_translation_icon("Темная")), (255, 255, 255))

    def test_the_hotkey_bar_comes_after_the_translate_button(self):
        self.assertGreater(
            self.window.hotkey_language_bar.mapTo(self.window.ui_root, QtCore.QPoint()).y(),
            self.window.translate_button.mapTo(self.window.ui_root, QtCore.QPoint()).y()
        )

    def test_settings_widget_is_reused_instead_of_rebuilt(self):
        self.window.show_settings()
        self.app.processEvents()
        first = self.window.settings_window

        self.window.show_main_screen()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.window.show_settings()
        self.app.processEvents()

        self.assertIs(self.window.settings_window, first)

    def test_return_from_settings_does_not_repolish_the_hidden_settings_tree(self):
        self.window.show_settings()
        self.app.processEvents()

        with mock.patch.object(self.window, "apply_theme", wraps=self.window.apply_theme) as apply:
            self.window.show_main_screen()

        apply.assert_not_called()

    def test_home_icon_contrasts_with_both_title_bar_themes(self):
        def first_opaque_rgb():
            image = self.window.settings_button.icon().pixmap(64, 64).toImage().convertToFormat(
                QImage.Format_ARGB32
            )
            values = []
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    if color.alpha() >= 220:
                        values.append((color.red() + color.green() + color.blue()) / 3)
            self.assertTrue(values)
            return sum(values) / len(values)

        original_theme = self.window.current_theme
        try:
            self.window.current_theme = "Темная"
            self.window.set_settings_button_to_home()
            self.assertGreater(first_opaque_rgb(), 200)
            self.window.current_theme = "Светлая"
            self.window.set_settings_button_to_home()
            self.assertLess(first_opaque_rgb(), 55)
        finally:
            self.window.current_theme = original_theme
            self.window.set_settings_button_to_settings()

    def test_text_and_shortcuts_occupy_separate_labeled_regions(self):
        text = self.window.main_text_section
        shortcuts = self.window.main_shortcut_section
        footer = self.window.main_footer
        rect = lambda widget: QtCore.QRect(widget.mapTo(self.window.ui_root, QtCore.QPoint()), widget.size())
        self.assertGreaterEqual(rect(shortcuts).top() - rect(text).bottom(), 8)
        self.assertGreaterEqual(rect(footer).top() - rect(shortcuts).bottom(), 8)
        self.assertTrue(text.isAncestorOf(self.window.source_lang))
        self.assertTrue(text.isAncestorOf(self.window.text_input))
        self.assertTrue(shortcuts.isAncestorOf(self.window.hotkey_mode_combo))
        self.assertTrue(shortcuts.isAncestorOf(self.window.main_hotkey_area))
        self.assertTrue(footer.isAncestorOf(self.window.start_button))
        self.assertEqual(self.window.ui_root.size(), QtCore.QSize(700, 400))

    def test_the_mode_picker_is_sized_by_qt_not_by_a_guess(self):
        """Full mode names get their measured width on the current platform."""
        import inspect

        source = inspect.getsource(main.DarkThemeApp._fit_hotkey_mode_combo)

        self.assertIn("AdjustToContents", source)
        self.assertIn("sizeHint().width()", source)
        self.assertGreaterEqual(self.window.hotkey_mode_combo.width(), 160)
        self.assertEqual(self.window.hotkey_mode_combo.width(), max(160, self.window.hotkey_mode_combo.sizeHint().width()))
        for index in range(self.window.hotkey_mode_combo.count()):
            self.assertTrue(
                self.window.hotkey_mode_combo.itemData(index, Qt.ToolTipRole),
                index,
            )

    def test_the_shortcut_legend_keeps_seven_actions_in_two_columns(self):
        """Every action is visible in four aligned rows, without card frames."""
        chips = self.window.ui_root.findChildren(QWidget, "mainHotkeyPair")
        # All seven registered actions are listed, including Gaming.
        self.assertEqual(len(chips), 7)
        self.assertTrue(all(chip.toolTip() for chip in chips))
        self.assertIn(self.window.replace_hotkey_reference, chips)
        self.assertEqual(
            set(self.window.main_hotkey_references),
            {"copy", "ocr", "fullscreen", "game", "selection", "replace", "toggle"},
        )
        self.assertEqual(set(self.window.main_hotkey_references.values()), set(chips))
        rows = {chip.mapTo(self.window.ui_root, chip.rect().topLeft()).y() for chip in chips}
        self.assertEqual(len(rows), 4)
        refs = self.window.main_hotkey_references
        absolute_y = lambda key: refs[key].mapTo(
            self.window.ui_root, refs[key].rect().topLeft()
        ).y()
        self.assertEqual(absolute_y("copy"), absolute_y("ocr"))
        self.assertEqual(absolute_y("toggle"), absolute_y("fullscreen"))
        self.assertEqual(absolute_y("game"), absolute_y("selection"))
        game = self.window.main_hotkey_references["game"]
        self.assertLess(absolute_y("copy"), absolute_y("game"))
        self.assertLess(absolute_y("game"), absolute_y("replace"))
        self.assertLessEqual(
            absolute_y("game") + game.height(), self.window.start_button.mapTo(self.window.ui_root, QtCore.QPoint()).y()
        )

    def test_dynamic_reference_keeps_the_same_readable_style_in_every_language(self):
        for language in LANGUAGES:
            pair = self.window._create_main_hotkey_pair(
                main.main_hotkey_compact_caption(language, "game"),
                main.DEFAULT_GAME_HOTKEY,
                compact=True,
            )
            try:
                for label in (pair.caption_label, pair.value_label):
                    self.assertGreaterEqual(label.height(), label.sizeHint().height(), language)
                    self.assertLessEqual(label.height(), pair.height(), language)
                self.assertIn("font-size: 13px", pair.caption_label.styleSheet())
                self.assertIn("font-size: 12px", pair.value_label.styleSheet())
            finally:
                pair.deleteLater()

    def test_every_language_keeps_the_shortcut_columns_and_status_inside_the_window(self):
        original_language = self.window.current_interface_language
        try:
            # Rebuilding the real screen emits language-combo persistence
            # signals. Suppress disk writes: this geometry sweep must never
            # change the developer's own interface language.
            with mock.patch.object(self.window, "save_config"):
                for language in LANGUAGES:
                    self.window.current_interface_language = language
                    self.window.show_main_screen()
                    for _ in range(3):
                        self.app.processEvents()

                    refs = self.window.main_hotkey_references
                    absolute = {
                        key: widget.mapTo(self.window.ui_root, widget.rect().topLeft())
                        for key, widget in refs.items()
                    }
                    for left_key, right_key in (
                        ("ocr", "copy"),
                        ("fullscreen", "toggle"),
                        ("selection", "game"),
                    ):
                        self.assertEqual(
                            absolute[left_key].y(), absolute[right_key].y(), language
                        )
                        self.assertLess(
                            absolute[left_key].x() + refs[left_key].width(),
                            absolute[right_key].x(),
                            language,
                        )
                    for column in (("ocr", "fullscreen", "selection", "replace"), ("copy", "toggle", "game")):
                        key_edges = {
                            refs[key].value_label.mapTo(self.window.ui_root, refs[key].value_label.rect().topRight()).x()
                            for key in column
                        }
                        self.assertEqual(len(key_edges), 1, language)
                    self.assertTrue(all(widget.x() >= 0 for widget in refs.values()), language)
                    self.assertTrue(
                        all(
                            absolute[key].x() + widget.width()
                            <= self.window.central_widget.width()
                            for key, widget in refs.items()
                        ),
                        language,
                    )
                    engine = self.window.main_engine_status_panel
                    engine_position = engine.mapTo(
                        self.window.ui_root, engine.rect().topLeft()
                    )
                    shortcuts_bottom = max(absolute[key].y() + widget.height() for key, widget in refs.items())
                    self.assertLessEqual(
                        shortcuts_bottom,
                        engine_position.y(),
                        language,
                    )
                    self.assertTrue(self.window.main_footer.isAncestorOf(engine))
                    self.assertLessEqual(engine_position.y() + engine.height(), self.window.ui_root.height() - 14)
                    for key, pair in refs.items():
                        for label in (pair.caption_label, pair.value_label):
                            if label.wordWrap():
                                self.assertLessEqual(label.heightForWidth(label.width()), label.height(), (language, key, label.text()))
                            else:
                                self.assertLessEqual(
                                    label.fontMetrics().horizontalAdvance(label.text()),
                                    label.contentsRect().width(),
                                    (language, key, label.text()),
                                )
                    self.assertLessEqual(
                        absolute["game"].y() + refs["game"].height(),
                        self.window.start_button.mapTo(self.window.ui_root, QtCore.QPoint()).y(),
                        language,
                    )
        finally:
            with mock.patch.object(self.window, "save_config"):
                self.window.current_interface_language = original_language
                self.window.show_main_screen()
                self.app.processEvents()

    def test_clicking_hotkey_badge_offers_its_exact_setting(self):
        game = self.window.main_hotkey_references["game"]
        with mock.patch.object(self.window, "_offer_hotkey_settings") as offer:
            QTest.mouseClick(game.value_label, Qt.LeftButton)

        offer.assert_called_once_with(
            "game_translate_hotkey",
            main.ui_text(self.window.current_interface_language, "hotkey_gaming"),
        )

    def test_caption_shortcut_and_empty_space_are_one_click_target(self):
        bindings = {
            "copy": "copy_hotkey", "ocr": "translate_hotkey",
            "fullscreen": "fullscreen_translate_hotkey", "selection": "translate_selection_hotkey",
            "replace": "translate_replace_selection_hotkey", "toggle": "toggle_window_hotkey",
            "game": "game_translate_hotkey",
        }
        for action, row in self.window.main_hotkey_references.items():
            points = (
                row.caption_label.geometry().center(),
                row.value_label.geometry().center(),
                QtCore.QPoint((row.caption_label.geometry().right() + row.value_label.x()) // 2, row.height() // 2),
            )
            for point in points:
                with self.subTest(action=action, point=point), mock.patch.object(self.window, "_offer_hotkey_settings") as offer:
                    hit = self.window.ui_root.childAt(row.mapTo(self.window.ui_root, point))
                    self.assertIs(hit, row)
                    QTest.mouseClick(row, Qt.LeftButton, pos=point)
                    offer.assert_called_once()
                    self.assertEqual(offer.call_args.args[0], bindings[action])

    def test_shortcut_row_can_be_activated_from_the_keyboard(self):
        row = self.window.main_hotkey_references["copy"]
        self.assertEqual(row.focusPolicy(), Qt.StrongFocus)
        self.assertEqual(row.caption_label.focusPolicy(), Qt.NoFocus)
        self.assertEqual(row.value_label.focusPolicy(), Qt.NoFocus)
        for key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            with self.subTest(key=key), mock.patch.object(self.window, "_offer_hotkey_settings") as offer:
                QTest.keyClick(row, key)
                offer.assert_called_once()
                self.assertEqual(offer.call_args.args[0], "copy_hotkey")

    def test_shortcut_row_does_not_activate_on_right_click_or_cancelled_press(self):
        row = self.window.main_hotkey_references["copy"]
        with (
            mock.patch.object(self.window, "_offer_hotkey_settings") as offer,
            mock.patch.object(self.window, "show_main_context_menu") as context_menu,
        ):
            QTest.mouseClick(row, Qt.RightButton)
            QTest.mouseRelease(row, Qt.LeftButton)
            QTest.mousePress(row, Qt.LeftButton)
            QTest.mouseRelease(row, Qt.LeftButton, pos=QtCore.QPoint(row.width() + 5, row.height() // 2))
        offer.assert_not_called()
        context_menu.assert_called_once()

    def test_declining_hotkey_prompt_does_not_open_settings(self):
        with (
            mock.patch.object(self.window, "_confirm_open_hotkey_settings", return_value=False),
            mock.patch.object(self.window, "_open_hotkey_setting") as open_setting,
        ):
            accepted = self.window._offer_hotkey_settings("copy_hotkey", "Copy")

        self.assertFalse(accepted)
        open_setting.assert_not_called()

    def test_gaming_is_not_a_title_bar_button(self):
        self.assertFalse(hasattr(self.window, "game_button"))

    def test_next_button_cannot_skip_multiple_cards_during_transition(self):
        self.window._guide_active = True
        self.window._guide_step_index = main.GUIDE_TOUR_ORDER.index("shortcut_overview")
        self.window._show_guide_step()
        start = self.window._guide_step_index

        self.window.skip_current_guide_step()
        self.window.skip_current_guide_step()

        self.assertEqual(self.window._guide_step_index, start + 1)
        self.assertFalse(self.window._guide_skip_btn.isEnabled())
        self.window._guide_active = False
        self.window._guide_step_timer.stop()
        self.window._clear_guide_spotlight()
        self.window._guide_bubble.hide()

    def test_clicking_a_highlighted_control_also_locks_next_until_new_card(self):
        self.window._guide_active = True
        self.window._guide_step_index = main.GUIDE_TOUR_ORDER.index("shortcut_overview")
        self.window._show_guide_step()
        start = self.window._guide_step_index
        action = self.window._guide_current_action()

        self.window._complete_guide_step(action)
        self.window.skip_current_guide_step()

        self.assertEqual(self.window._guide_step_index, start + 1)
        self.assertFalse(self.window._guide_skip_btn.isEnabled())
        self.window._guide_active = False
        self.window._guide_step_timer.stop()
        self.window._clear_guide_spotlight()
        self.window._guide_bubble.hide()

    def test_every_tour_target_exists_in_the_view_where_it_is_explained(self):
        actions = [
            action
            for action, _title, _body in main.guide_text(
                self.window.current_interface_language
            )["steps"]
        ]
        for action in actions:
            self.window._prepare_guide_settings_page(action)
            self.app.processEvents()
            target = self.window._guide_target_widget(action)
            self.assertIsNotNone(target, action)
            self.assertTrue(target.isVisible(), action)

        target = self.window._guide_target_widget("back_home")
        self.assertIsNotNone(target)
        self.assertTrue(target.isVisible())


class DirectionSummaryTest(unittest.TestCase):
    """The window shows two direction rows; this line says which is which.

    The pair at the top belongs to the typed text, the pair in the shortcut bar
    belongs to whichever shortcut mode is being edited, and each of the four
    modes keeps its own. Nothing on screen said so — a window reading
    "Russian to English" at the top and "English to Russian" below looks broken.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        welcome = mock.patch.object(main, "WelcomeDialog")
        welcome.start()
        self.addCleanup(welcome.stop)
        update_check = mock.patch.object(
            main.DarkThemeApp, "_maybe_check_updates_on_launch"
        )
        update_check.start()
        self.addCleanup(update_check.stop)
        startup_news = mock.patch.object(
            main.DarkThemeApp, "_maybe_show_startup_news"
        )
        startup_news.start()
        self.addCleanup(startup_news.stop)
        guide = mock.patch.object(main.DarkThemeApp, "_maybe_start_first_run_guide")
        guide.start()
        self.addCleanup(guide.stop)
        hotkey_listener = mock.patch.object(main, "HotkeyListenerThread")
        hotkey_listener.start()
        self.addCleanup(hotkey_listener.stop)
        try:
            self.window = main.DarkThemeApp()
        except Exception as error:                      # pragma: no cover
            self.skipTest(f"the main window cannot be built here: {error}")
        # In-memory only: these tests never save, so the user's config is safe.
        self.window.config["main_translation_source_language"] = "ru"
        self.window.config["main_translation_target_language"] = "en"

    def tearDown(self):
        self.window.force_quit = True
        self.window.close()
        self.window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def _set_every_mode(self, source, target):
        for mode in main.HOTKEY_LANGUAGE_MODES:
            source_key, target_key = main.HOTKEY_LANGUAGE_CONFIG_KEYS[mode]
            self.window.config[source_key] = source
            self.window.config[target_key] = target

    def test_mode_languages_use_one_row_with_the_details_in_hover_help(self):
        self.assertTrue(self.window.direction_summary.isHidden())
        self.assertEqual(self.window.hotkey_language_bar.height(), 30)
        self.assertTrue(self.window.hotkey_language_bar.toolTip())

    def test_one_direction_everywhere_is_said_once(self):
        self._set_every_mode("ru", "en")

        text = self.window._direction_summary_text()

        language = self.window.current_interface_language
        self.assertIn(main.language_display_name("ru", language), text)
        self.assertIn(main.language_display_name("en", language), text)
        # Four modes agreeing must not print four identical pairs.
        self.assertEqual(text.count("→"), 2)
        self.assertNotIn("(", text)

    def test_a_mode_that_differs_is_named(self):
        self._set_every_mode("ru", "en")
        source_key, target_key = main.HOTKEY_LANGUAGE_CONFIG_KEYS["fullscreen"]
        self.window.config[source_key] = "en"
        self.window.config[target_key] = "ru"

        text = self.window._direction_summary_text()

        fullscreen = main.ui_text(self.window.current_interface_language, "hotkey_fullscreen")
        self.assertIn(fullscreen, text)
        self.assertEqual(text.count("→"), 3)

    def test_it_names_the_typed_pair_and_the_shortcut_pair_apart(self):
        self._set_every_mode("en", "ru")

        text = self.window._direction_summary_text()
        language = self.window.current_interface_language

        self.assertIn(main.ui_text(language, "direction_typed"), text)
        self.assertIn(main.ui_text(language, "direction_shortcuts"), text)

    def test_the_short_form_keeps_the_modes_and_drops_the_spelling(self):
        """Which mode does what is the point of the line; "English" is not."""
        self._set_every_mode("ru", "en")
        source_key, target_key = main.HOTKEY_LANGUAGE_CONFIG_KEYS["selection"]
        self.window.config[source_key] = "en"
        self.window.config[target_key] = "ru"

        short = self.window._direction_summary_text(names=False)

        self.assertIn("RU", short)
        self.assertIn("EN", short)
        self.assertIn(
            main.ui_text(self.window.current_interface_language, "hotkey_selection"),
            short,
        )

    def test_reading_it_asks_no_engine_anything(self):
        """It redraws whenever a combo changes; inspecting installed OCR
        languages on every keystroke is not acceptable there."""
        with mock.patch.object(
            main.DarkThemeApp,
            "_available_hotkey_translation_pairs",
            side_effect=AssertionError("the summary must not probe the engines"),
        ):
            self.window._direction_summary_text()

    def test_main_and_hotkey_arrows_swap_their_own_language_pairs(self):
        for button in (
            self.window.main_language_swap,
            self.window.hotkey_language_swap,
        ):
            self.assertIsInstance(button, main.LanguageSwapButton)
            self.assertEqual(button.text(), "")

        self.window.config["translator_engine"] = "Google"
        self.window.config["main_translation_source_language"] = "en"
        self.window.config["main_translation_target_language"] = "ru"
        self.window._restore_main_translation_languages()

        self.window.main_language_swap.click()

        self.assertEqual(
            self.window._configured_main_translation_pair(),
            ("ru", "en"),
        )

        source_key, target_key = main.HOTKEY_LANGUAGE_CONFIG_KEYS["selection"]
        self.window.config["hotkey_language_editor_mode"] = "selection"
        self.window.config[source_key] = "en"
        self.window.config[target_key] = "ru"
        self.window._refresh_hotkey_language_controls()

        self.window.hotkey_language_swap.click()

        self.assertEqual(
            self.window._configured_hotkey_translation_pair("selection"),
            ("ru", "en"),
        )

    def test_the_label_carries_the_tooltip_style(self):
        """A widget with its own stylesheet resolves its tooltip against that
        sheet, so the app-wide purple QToolTip rule never reaches it."""
        self.assertIn("QToolTip", self.window.direction_summary.styleSheet())
        self.assertTrue(self.window.direction_summary.toolTip())

    def test_every_language_has_the_words(self):
        for language in LANGUAGES:
            for key in ("direction_typed", "direction_shortcuts", "direction_hint"):
                value = main.ui_text(language, key)
                self.assertTrue(value and value != key, (language, key))
            # The two labels share a line with two language pairs.
            self.assertLessEqual(
                len(main.ui_text(language, "direction_typed")), 16, language
            )
            self.assertLessEqual(
                len(main.ui_text(language, "direction_shortcuts")), 16, language
            )
            # The tooltip is where the explanation lives, so it is a sentence.
            self.assertGreater(len(main.ui_text(language, "direction_hint")), 40, language)


class TranslateOnEnterTest(unittest.TestCase):
    """Enter translates; Shift+Enter is how you get a new line.

    The box used to swallow Enter, so after typing you had to leave the
    keyboard and find the button.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.box = main.TranslateOnEnterTextEdit()
        self.asked = []
        self.box.translation_requested.connect(lambda: self.asked.append(True))

    def _press(self, key, modifiers=Qt.NoModifier):
        QTest.keyClick(self.box, key, modifiers)

    def test_enter_asks_for_a_translation_and_types_nothing(self):
        self.box.setPlainText("hola")
        self._press(Qt.Key_Return)

        self.assertEqual(len(self.asked), 1)
        self.assertEqual(self.box.toPlainText(), "hola")

    def test_shift_enter_makes_a_new_line_and_translates_nothing(self):
        self.box.setPlainText("hola")
        self.box.moveCursor(QTextCursor.End)
        self._press(Qt.Key_Return, Qt.ShiftModifier)

        self.assertEqual(self.asked, [])
        self.assertEqual(self.box.toPlainText().splitlines(), ["hola"])
        self.assertTrue(self.box.toPlainText().endswith("\n"))

    def test_the_keypad_enter_behaves_like_the_main_one(self):
        self._press(Qt.Key_Enter)

        self.assertEqual(len(self.asked), 1)

    def test_ctrl_enter_still_translates(self):
        """It was the only keyboard way to do it before; it still works."""
        self._press(Qt.Key_Return, Qt.ControlModifier)

        self.assertEqual(len(self.asked), 1)

    def test_ordinary_typing_is_untouched(self):
        QTest.keyClicks(self.box, "hola")

        self.assertEqual(self.asked, [])
        self.assertEqual(self.box.toPlainText(), "hola")

    def test_the_main_window_uses_this_box(self):
        import inspect

        source = inspect.getsource(main.DarkThemeApp.show_main_screen)
        self.assertIn("self.text_input = TranslateOnEnterTextEdit()", source)
        self.assertIn(
            "self.text_input.translation_requested.connect(self.translate_input_text)",
            source,
        )


class EngineDividerSpacingTest(unittest.TestCase):
    """Passive engine information occupies one footer below the references."""

    @staticmethod
    def _source():
        import inspect

        return inspect.getsource(main.DarkThemeApp.show_main_screen)

    def test_engine_status_and_shadow_action_share_the_footer(self):
        import inspect
        import re

        source = self._source()
        spacing = re.search(
            r"MAIN_HOTKEY_HORIZONTAL_SPACING\s*=\s*(\d+)",
            inspect.getsource(main),
        )
        self.assertIsNotNone(spacing)
        self.assertEqual(int(spacing.group(1)), 28)
        self.assertIn("hotkey_grid.setHorizontalSpacing(hotkey_spacing)", source)
        self.assertIn("engine_status_panel", source)
        self.assertIn("MAIN_HOTKEY_DEFAULT_ORDER", source)
        self.assertIn("engine_status_panel.setMaximumWidth(engine_status_width)", source)
        self.assertIn("hotkey_grid.setColumnStretch(column, 1)", source)
        self.assertIn("footer_layout.addWidget(engine_status_panel, 0, 0)", source)
        self.assertIn("footer_layout.addWidget(self.start_button, 0, 1)", source)
        self.assertIn("footer_layout.addWidget(ocr_summary, 0, 2)", source)
        self.assertNotIn("mainEngineStatusSeparator", source)
        self.assertNotIn("engine_status_layout.addWidget(game_reference)", source)
        self.assertIn("compact=True", source)

    def test_no_column_is_pinned_to_a_width_measured_in_one_language(self):
        self.assertNotIn("setColumnMinimumWidth", self._source())


class WindowEdgeTest(unittest.TestCase):
    """Content that touches the frame reads as a rendering fault.

    It sat 5px from every edge, and 5px under a 40px title bar.
    """

    TITLE_BAR_HEIGHT = 40

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_margins_leave_the_frame_alone(self):
        import inspect
        import re

        source = inspect.getsource(main.DarkThemeApp.__init__)
        found = re.search(
            r"self\.main_layout\.setContentsMargins\((\d+), (\d+), (\d+), (\d+)\)",
            source,
        )
        self.assertIsNotNone(found)
        left, top, right, bottom = (int(value) for value in found.groups())

        self.assertEqual(left, right)
        for name, value in (("left", left), ("right", right), ("bottom", bottom)):
            self.assertGreaterEqual(value, 12, name)
        # And the first row is not pressed against the title.
        self.assertGreaterEqual(top - self.TITLE_BAR_HEIGHT, 8)


class HotkeyLegendCoverageTest(unittest.TestCase):
    """Every hotkey the app registers has to be visible on the main screen.

    All seven shortcuts, including Gaming, live in the main-screen legend.
    """

    #: Every hotkey setting the app reads when it registers them.
    REGISTERED = (
        "copy_hotkey",
        "translate_hotkey",
        "fullscreen_translate_hotkey",
        "translate_selection_hotkey",
        "translate_replace_selection_hotkey",
        "game_translate_hotkey",
        "toggle_window_hotkey",
    )

    def test_the_registration_list_is_what_this_test_thinks_it_is(self):
        """If another hotkey is added, this fails before its visible entry does."""
        import inspect
        import re

        # The hotkeys are registered inline in the constructor.
        source = inspect.getsource(main.DarkThemeApp.__init__)
        found = set(re.findall(r'self\.config\.get\("([a-z_]+_hotkey)"', source))

        self.assertEqual(found, set(self.REGISTERED))

    def test_the_main_screen_shows_every_registered_hotkey(self):
        import inspect
        import re

        source = "\n".join((
            inspect.getsource(main.DarkThemeApp.show_main_screen),
            inspect.getsource(main.DarkThemeApp.init_ui),
        ))
        shown = set(re.findall(r"self\.config\.get\(['\"]([a-z_]+_hotkey)['\"]", source))

        missing = sorted(set(self.REGISTERED) - shown)
        self.assertEqual(missing, [], f"registered but not shown: {missing}")

    def test_every_language_has_a_caption_for_each_one(self):
        captions = (
            "hotkey_copy",
            "hotkey_ocr_translate",
            "hotkey_fullscreen",
            "hotkey_selection",
            "hotkey_replace",
            "game_translate",
            "hotkey_toggle",
        )
        self.assertEqual(len(captions), len(self.REGISTERED))
        for language in LANGUAGES:
            for key in captions:
                caption = main.ui_text(language, key)
                self.assertTrue(caption and caption != key, (language, key))
                # Chips are short; the dedicated game title can be a little wider.
                self.assertLessEqual(len(caption), 22, (language, key, caption))


if __name__ == "__main__":
    unittest.main()
