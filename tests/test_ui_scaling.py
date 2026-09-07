"""Exercise the actual scaled viewport, including icons, input and native boundaries."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QIconEngine, QMouseEvent, QPalette, QPixmap
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QGraphicsItem

import main
from qt_layout_test_support import ensure_layout_fonts
from ui_scaling import BASE_SCALE, MainWindowScaleController, configure_qt_platform, maximum_ui_scale, native_window_parent, normalize_ui_scale

REAL_SAVE_CONFIG = main.DarkThemeApp.save_config


class ScaleValueTest(unittest.TestCase):
    def test_font_backend_is_selected_before_startup_and_preserves_explicit_options(self):
        for platform, setting, expected in (
            ('win32', None, 'windows:fontengine=freetype'),
            ('win32', 'windows', 'windows:fontengine=freetype'),
            ('win32', 'windows:darkmode=2', 'windows:darkmode=2:fontengine=freetype'),
            ('win32', 'windows:fontengine=native', 'windows:fontengine=native'),
            ('win32', 'windows:fontengine=freetype', 'windows:fontengine=freetype'),
            ('win32', 'offscreen', 'offscreen'),
            ('linux', None, None),
        ):
            with self.subTest(platform=platform, setting=setting), \
                    mock.patch('ui_scaling.sys.platform', platform), \
                    mock.patch('ui_scaling.QApplication.instance', return_value=None), \
                    mock.patch.dict(os.environ, {}, clear=True):
                if setting is not None:
                    os.environ['QT_QPA_PLATFORM'] = setting
                configure_qt_platform()
                configure_qt_platform()
                self.assertEqual(os.environ.get('QT_QPA_PLATFORM'), expected)

    def test_invalid_and_out_of_range_values_have_safe_defaults(self):
        for value, expected in [(None, 100), (True, 100), ('bad', 100), (float('inf'), 100),
                                (-10, 80), (80, 80), (95, 95), (250, 200), ('150', 150), (123, 123)]:
            with self.subTest(value=value):
                self.assertEqual(normalize_ui_scale(value), expected)
        self.assertEqual(main.merge_config_defaults({})[0]['ui_scale_percent'], 100)
        self.assertEqual(main.merge_config_defaults({'ui_scale_percent': 'bad'})[0]['ui_scale_percent'], 100)

    def test_screen_limit_uses_both_dimensions_in_logical_pixels(self):
        self.assertEqual(maximum_ui_scale(QRect(0, 0, 1920, 1080)), 200)
        self.assertEqual(maximum_ui_scale(QRect(0, 0, 1280, 720)), 200 if sys.platform == "darwin" else 144)
        self.assertEqual(maximum_ui_scale(QRect(-1280, 0, 1280, 640)), 200 if sys.platform == "darwin" else 128)
        self.assertEqual(maximum_ui_scale(QRect(0, 0, 700, 400)), 125 if sys.platform == "darwin" else 80)


class UiScalingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        ensure_layout_fonts(cls.app)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='cnt-scale-tests-')
        self.addCleanup(self.temporary.cleanup)
        self.config_path = Path(self.temporary.name) / 'config.json'
        self.config_path.write_text(json.dumps(main.DEFAULT_CONFIG), encoding='utf-8')
        self.original_qt_scale = os.environ.get('QT_SCALE_FACTOR')
        for patch in (
            mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True),
            mock.patch.object(main, 'get_cached_config', return_value=dict(main.DEFAULT_CONFIG)),
            mock.patch.object(main.DarkThemeApp, 'save_config'),
            mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False),
            mock.patch.object(main, 'get_data_file', side_effect=lambda name: str(Path(self.temporary.name) / name)),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.window = main.DarkThemeApp()
        self.controller = self.window._ui_scale_controller
        self.available = mock.patch.object(MainWindowScaleController, 'available_geometry', return_value=QRect(0, 0, 2560, 1440)).start()
        self.addCleanup(mock.patch.stopall)
        self.window.show()
        self.settle()

    def tearDown(self):
        self.window._guide_step_timer.stop()
        self.window._guide_active = False
        self.window.force_quit = True
        self.window.close()
        self.window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def settle(self):
        for _ in range(5):
            self.app.processEvents()

    def click(self, widget, point=None):
        QTest.mouseClick(self.controller.view.viewport(), Qt.LeftButton,
                         pos=self.controller.map_widget_to_view(widget, point))
        self.settle()

    def test_every_scale_keeps_logical_geometry_and_enlarges_icons(self):
        self.window.show_main_screen()
        self.settle()
        widgets = [self.window.flag_button, self.window.settings_button, self.window.translate_button,
                   self.window.source_lang, self.window.text_input, self.window.main_hotkey_area,
                   self.window.hotkey_mode_combo, self.window.hotkey_source_combo,
                   self.window.hotkey_target_combo, self.window.hotkey_language_swap]
        original = [widget.geometry() for widget in widgets]
        icon = self.window.settings_button
        self.assertFalse(icon.icon().isNull())
        sizes = ((80, 448, 256), (100, 560, 320), (125, 700, 400),
                 (137, 767, 438), (150, 840, 480), (200, 1120, 640),
                 (125, 700, 400), (80, 448, 256)) if sys.platform == "darwin" else ((80, 700, 400), (100, 875, 500), (125, 1094, 625),
                                       (137, 1199, 685), (150, 1312, 750), (200, 1750, 1000),
                                       (125, 1094, 625), (80, 700, 400))
        for percent, width, height in sizes:
            with self.subTest(percent=percent):
                self.window.set_ui_scale_percent(percent)
                self.settle()
                self.assertEqual(self.window.width(), width)
                self.assertEqual(self.window.height(), height)
                self.assertEqual([widget.geometry() for widget in widgets], original)
                left = self.controller.map_widget_to_view(icon, QPoint())
                right = self.controller.map_widget_to_view(icon, QPoint(icon.width(), 0))
                self.assertAlmostEqual(right.x() - left.x(), icon.width() * percent / BASE_SCALE, delta=1)
                self.assertTrue(icon.isVisible())

    def test_clicks_and_multiline_typing_reach_the_scaled_controls(self):
        self.window.set_ui_scale_percent(175)
        self.click(self.window.settings_button)
        self.assertIsNotNone(self.window.settings_window)
        self.assertTrue(self.window.settings_window.ui_scale_control.isVisible())
        self.click(self.window.settings_button)
        self.click(self.window.text_input)
        viewport = self.controller.view.viewport()
        for index, text in enumerate(('one', 'two', 'three', 'four')):
            if index:
                QTest.keyClick(viewport, Qt.Key_Return, Qt.ShiftModifier)
            QTest.keyClicks(viewport, text)
        self.settle()
        self.assertEqual(self.window.text_input.toPlainText(), 'one\ntwo\nthree\nfour')
        self.assertTrue(self.window.document_expand_button.isVisible())
        with mock.patch.object(self.window, 'open_document_translation') as opened:
            self.click(self.window.document_expand_button)
            opened.assert_called_once_with(initial_text='one\ntwo\nthree\nfour')

    def test_scaled_text_uses_smooth_gray_edges_without_color_fringes(self):
        if self.window.current_theme != 'Темная':
            self.window.toggle_theme()
        title = self.window.title_bar
        bounds = title.fontMetrics().boundingRect(title.text())
        for percent in (80, 100, 137, 150, 200):
            with self.subTest(percent=percent):
                self.window.set_ui_scale_percent(percent)
                self.settle()
                picture = self.window.grab().toImage()
                ratio = picture.devicePixelRatio()
                top_left = self.controller.map_widget_to_view(title, QPoint(
                    (title.width() - bounds.width()) // 2, 4))
                bottom_right = self.controller.map_widget_to_view(title, QPoint(
                    (title.width() + bounds.width()) // 2, title.height() - 4))
                shades = set()
                for y in range(round(top_left.y() * ratio), round(bottom_right.y() * ratio)):
                    for x in range(round(top_left.x() * ratio), round(bottom_right.x() * ratio)):
                        color = picture.pixelColor(x, y)
                        self.assertLessEqual(max(color.red(), color.green(), color.blue()) -
                                             min(color.red(), color.green(), color.blue()), 1)
                        shades.add(color.red())
                self.assertGreater(len(shades), 10)
                self.assertGreater(max(shades) - min(shades), 100)

    def test_scaled_icons_request_source_pixels_for_the_actual_display_size(self):
        requests = []

        class RecordingIcon(QIconEngine):
            def clone(self):
                return RecordingIcon()

            def pixmap(self, size, mode, state):
                requests.append(size)
                pixmap = QPixmap(size)
                pixmap.fill(QColor('#ffffff'))
                return pixmap

        button = self.window.settings_button
        button.setIcon(QIcon(RecordingIcon()))
        for percent in (100, 137, 200):
            with self.subTest(percent=percent):
                self.window.set_ui_scale_percent(percent)
                self.settle()
                requests.clear()
                self.window.grab()
                self.assertTrue(requests)
                needed = button.iconSize().width() * percent / BASE_SCALE * button.devicePixelRatioF()
                self.assertGreaterEqual(max(size.width() for size in requests), needed)

    def test_arrow_clicks_and_keyboard_activation_apply_exact_five_percent_steps(self):
        self.window.show_settings()
        self.window.set_ui_scale_percent(125)
        self.settle()
        settings = self.window.settings_window
        self.click(settings.ui_scale_increase)
        self.assertEqual(self.window.config['ui_scale_percent'], 130)
        self.assertEqual(settings.ui_scale_value.text(), '130%')
        self.assertEqual(self.window.width(), round(700 * 130 / BASE_SCALE))
        QTest.keyClick(self.controller.view.viewport(), Qt.Key_Space)
        self.settle()
        self.assertEqual(self.window.config['ui_scale_percent'], 135)
        self.click(settings.ui_scale_decrease)
        self.assertEqual(self.window.config['ui_scale_percent'], 130)

    def test_scaled_popup_stays_inside_viewport_and_selection_works(self):
        self.window.set_ui_scale_percent(200)
        self.window.show_settings()
        self.settle()
        combo = self.window.settings_window.translator_combo
        self.click(combo)
        popup = combo.view().window()
        proxy = popup.graphicsProxyWidget()
        self.assertIsNotNone(proxy)
        self.assertTrue(self.controller.view.sceneRect().contains(proxy.sceneBoundingRect()))
        QTest.keyClick(self.controller.view.viewport(), Qt.Key_Escape)
        self.settle()
        self.assertFalse(popup.isVisible())

        self.window.show_main_screen()
        self.settle()
        combo = self.window.target_lang
        self.click(combo)
        popup = combo.view().window()
        proxy = popup.graphicsProxyWidget()
        self.assertTrue(self.controller.view.sceneRect().contains(proxy.sceneBoundingRect()))
        QTest.keyClick(self.controller.view.viewport(), Qt.Key_End)
        self.settle()
        last = combo.count() - 1
        row = combo.view().visualRect(combo.model().index(last, 0))
        self.assertTrue(combo.view().viewport().rect().contains(row.center()))
        point = combo.view().viewport().mapTo(popup, row.center())
        mapped = self.controller.view.mapFromScene(proxy.mapToScene(QPointF(point)))
        # Qt briefly suppresses release events after the click that opens a list.
        QTest.qWait(QApplication.doubleClickInterval() + 20)
        QTest.mouseClick(self.controller.view.viewport(), Qt.LeftButton, pos=mapped)
        self.settle()
        self.assertEqual(combo.currentIndex(), last)
        self.assertFalse(popup.isVisible())

    def test_first_popup_keeps_its_anchor_after_native_proxy_sync_and_zoom(self):
        self.window.show_main_screen()
        for percent in (80, 100, 137):
            self.window.set_ui_scale_percent(percent)
            self.settle()
            for combo in (self.window.source_lang, self.window.target_lang,
                          self.window.hotkey_source_combo):
                geometries = []
                for attempt in (1, 2):
                    self.click(combo)
                    # Cocoa's native-to-scene synchronization is posted after
                    # showPopup returns; processEvents alone missed the jump.
                    QTest.qWait(100)
                    popup = combo.view().window()
                    self.assertTrue(popup.isVisible())
                    proxy = popup.graphicsProxyWidget()
                    root = combo.window()
                    geometry = proxy.mapRectToItem(root.graphicsProxyWidget(), proxy.boundingRect())
                    field = QRect(combo.mapTo(root, QPoint()), combo.size())
                    self.assertTrue(root.rect().contains(geometry.toAlignedRect()))
                    self.assertFalse(geometry.intersects(QRectF(field)),
                                     (percent, attempt, geometry, field))
                    geometries.append(geometry)
                    QTest.keyClick(self.controller.view.viewport(), Qt.Key_Escape)
                    self.settle()
                self.assertEqual(geometries[0], geometries[1])

    def test_dynamic_language_catalog_is_ready_before_the_first_popup(self):
        self.window.show_settings()
        settings = self.window.settings_window
        settings._set_settings_page(2)
        with mock.patch('ocr.installed_ocr_language_codes', return_value={'en', 'ru', 'de'}):
            settings._refresh_game_language_controls()
            combo = settings.game_source_combo
            self.assertEqual(combo.count(), 1)
            combo.showPopup()
            self.assertEqual(combo.count(), 3)
            QTest.qWait(120)
            self.assertTrue(combo.view().window().isVisible())
            self.assertEqual(combo.currentData(), 'en')
            first = combo.view().window().size()
            combo.hidePopup()
            combo.showPopup()
            QTest.qWait(100)
            self.assertEqual(combo.view().window().size(), first)
            combo.hidePopup()

    def test_header_drag_and_document_shortcut_reach_the_native_window(self):
        self.window.set_ui_scale_percent(175)
        self.window.move(200, 200)
        self.settle()
        viewport = self.controller.view.viewport()
        position = self.window.pos()
        point = self.controller.map_widget_to_view(self.window.ui_root, QPoint(350, 20))
        global_point = viewport.mapToGlobal(point)
        QTest.mousePress(viewport, Qt.LeftButton, pos=point)
        destination = global_point + QPoint(40, 30)
        QApplication.sendEvent(viewport, QMouseEvent(QEvent.MouseMove,
                              viewport.mapFromGlobal(destination), destination,
                              Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        self.settle()
        QTest.mouseRelease(viewport, Qt.LeftButton, pos=viewport.mapFromGlobal(destination))
        self.assertEqual(self.window.pos(), position + QPoint(40, 30))
        self.assertFalse(self.window._is_dragging)
        self.click(self.window.text_input)
        with mock.patch.object(self.window, '_choose_document_from_main') as opened:
            QTest.keyClick(viewport, Qt.Key_O, Qt.ControlModifier)
            opened.assert_called_once_with()

    def test_scale_labels_fit_in_both_themes_and_every_interface_language(self):
        for theme in ('Темная', 'Светлая'):
            if self.window.current_theme != theme:
                self.window.toggle_theme()
            for language in ('en', 'ru', 'de', 'fr', 'es', 'zh'):
                with self.subTest(theme=theme, language=language):
                    self.window.current_interface_language = language
                    self.window.show_settings()
                    self.window.set_ui_scale_percent(150)
                    self.settle()
                    settings = self.window.settings_window
                    for label in (settings.ui_scale_label,):
                        self.assertGreaterEqual(label.width(), label.sizeHint().width(), label.text())
                        self.assertGreaterEqual(label.height(), label.sizeHint().height(), label.text())
                    editor = settings.ui_scale_value
                    self.assertGreaterEqual(editor.width(), editor.fontMetrics().horizontalAdvance(editor.text()) + 4)
                    self.assertGreaterEqual(editor.height(), editor.fontMetrics().height())
                    self.assertTrue(settings.ui_scale_control.isVisible())
                    self.assertEqual(settings.ui_scale_value.text(), '150%')
                    self.assertLess(settings.ui_scale_label.geometry().right(), settings.ui_scale_control.geometry().left())
                    for control in (settings.ocr_engine_combo, settings.translator_combo, settings.result_window_control):
                        self.assertEqual(settings.ui_scale_control.x(), control.x())
                        self.assertEqual(settings.ui_scale_control.size(), control.size())
                    self.assertEqual(settings.ui_scale_label.geometry().right(), settings.ocr_engine_label.geometry().right())

    def test_screen_changes_clamp_size_without_losing_the_preference(self):
        self.window.set_ui_scale_percent(200)
        self.available.return_value = QRect(-1024, 0, 1024, 512) if sys.platform == 'darwin' else QRect(-1280, 0, 1280, 640)
        self.controller.refresh()
        self.settle()
        self.assertEqual(self.controller.effective_percent, 160 if sys.platform == 'darwin' else 128)
        self.assertTrue(self.available.return_value.contains(self.window.geometry()))
        self.assertEqual(self.window.config['ui_scale_percent'], 200)
        self.available.return_value = QRect(0, 0, 2560, 1440)
        self.controller.refresh()
        self.assertEqual(self.controller.effective_percent, 200)

    def test_guide_uses_logical_canvas_and_other_windows_keep_native_geometry(self):
        self.window.set_ui_scale_percent(150)
        self.window._spotlight_guide_target(self.window.settings_button)
        self.window._ensure_guide_bubble()
        self.window._position_guide_bubble(self.window.settings_button)
        self.assertIs(self.window._guide_spotlight.parentWidget(), self.window.ui_root)
        self.assertEqual(self.window._guide_spotlight.size(), self.window.ui_root.size())
        self.assertIs(native_window_parent(self.window.text_input), self.window)
        dialog = main.QMessageBox(self.window.text_input)
        try:
            self.assertIs(dialog.parentWidget(), self.window)
            self.assertIsNone(dialog.graphicsProxyWidget())
            # Main-window scaling never installs a global Qt DPI override.
            self.assertEqual(os.environ.get('QT_SCALE_FACTOR'), self.original_qt_scale)
        finally:
            dialog.deleteLater()

    def test_hiding_and_restoring_preserve_scale_and_content(self):
        self.window.set_ui_scale_percent(150)
        self.window.text_input.setPlainText('keep this text')
        self.window.hide()
        self.settle()
        self.assertFalse(self.window.ui_root.isVisible())
        self.window.show()
        self.settle()
        self.assertTrue(self.window.text_input.isVisible())
        self.assertEqual(self.window.text_input.toPlainText(), 'keep this text')
        self.assertEqual(self.window.width(), round(700 * 150 / BASE_SCALE))

    def test_saved_scale_is_loaded_by_a_new_window(self):
        with mock.patch.object(self.window, 'save_config', side_effect=lambda: REAL_SAVE_CONFIG(self.window)):
            self.window.set_ui_scale_percent(137)
        self.assertEqual(json.loads(self.config_path.read_text(encoding='utf-8'))['ui_scale_percent'], 137)
        restarted = main.DarkThemeApp()
        try:
            self.assertEqual(restarted._ui_scale_controller.effective_percent, 137)
            self.assertEqual(restarted.width(), round(700 * 137 / BASE_SCALE))
            self.assertEqual(restarted.height(), round(400 * 137 / BASE_SCALE))
        finally:
            restarted.force_quit = True
            restarted.close()
            restarted.deleteLater()

    def test_icon_pixels_increase_with_the_window(self):
        self.window.current_interface_language = 'en'
        self.window.update_interface_language_button()
        counts = []
        icon = self.window.flag_button
        for percent in (100, 200):
            self.window.set_ui_scale_percent(percent)
            self.settle()
            screenshot = self.window.grab().toImage()
            dpr = screenshot.devicePixelRatio()
            first = self.controller.map_widget_to_view(icon, QPoint())
            last = self.controller.map_widget_to_view(icon, QPoint(icon.width(), icon.height()))
            count = 0
            for y in range(round(first.y() * dpr), round(last.y() * dpr)):
                for x in range(round(first.x() * dpr), round(last.x() * dpr)):
                    color = screenshot.pixelColor(x, y)
                    count += color.red() > 180 and color.green() < 140 and color.blue() < 140
            counts.append(count)
        self.assertGreater(counts[0], 20)
        self.assertGreater(counts[1], counts[0] * 3)

    def test_holding_an_arrow_keeps_the_ui_intact_until_release(self):
        self.window.show_settings()
        self.settle()
        settings = self.window.settings_window
        button = settings.ui_scale_increase
        viewport = self.controller.view.viewport()
        point = self.controller.map_widget_to_view(button)
        geometry = self.window.geometry()
        self.window.save_config.reset_mock()
        QTest.mouseMove(viewport, point)
        QTest.mousePress(viewport, Qt.LeftButton, pos=point)
        QTest.qWait(350)
        self.assertEqual(self.window.geometry(), geometry)
        self.assertEqual(self.controller.proxy.scale(), 100 / BASE_SCALE)
        self.assertEqual(self.controller.proxy.cacheMode(), QGraphicsItem.NoCache)
        self.window.save_config.assert_not_called()
        QTest.mouseRelease(viewport, Qt.LeftButton, pos=point)
        self.settle()
        self.assertEqual(self.window.width(), round(700 * 105 / BASE_SCALE))
        self.assertEqual(self.window.height(), round(400 * 105 / BASE_SCALE))
        self.assertEqual(self.controller.proxy.scale(), 105 / BASE_SCALE)
        self.window.save_config.assert_called_once_with()
        QTest.qWait(100)
        self.assertEqual(self.window.width(), round(700 * 105 / BASE_SCALE))

    def test_buttons_follow_the_screen_limit_and_allow_returning_to_smaller_sizes(self):
        self.window.show_settings()
        settings = self.window.settings_window
        self.settle()
        self.assertTrue(settings.ui_scale_decrease.isEnabled())
        for value in (95, 90, 85, 80):
            self.click(settings.ui_scale_decrease)
            self.assertEqual(settings.ui_scale_value.text(), f'{value}%')
        self.assertEqual((self.window.width(), self.window.height()), (round(700 * 80 / BASE_SCALE), round(400 * 80 / BASE_SCALE)))
        self.assertFalse(settings.ui_scale_decrease.isEnabled())
        self.assertTrue(settings.ui_scale_increase.isEnabled())
        self.window.set_ui_scale_percent(200)
        self.assertFalse(settings.ui_scale_increase.isEnabled())
        self.available.return_value = QRect(0, 0, 1280, 640)
        self.controller.refresh()
        self.assertEqual(settings.ui_scale_value.text(), '200%' if sys.platform == 'darwin' else '128%')
        self.assertFalse(settings.ui_scale_increase.isEnabled())
        self.click(settings.ui_scale_decrease)
        self.assertEqual(settings.ui_scale_value.text(), '195%' if sys.platform == 'darwin' else '123%')
        self.assertTrue(settings.ui_scale_increase.isEnabled())
        self.assertEqual(self.window.config['ui_scale_percent'], 195 if sys.platform == 'darwin' else 123)

    def test_repeated_clicks_keep_every_control_in_its_region(self):
        self.window.show_settings()
        self.settle()
        settings = self.window.settings_window
        originals = [widget.geometry() for widget in
                     (settings.ocr_engine_combo, settings.ui_scale_control, self.window.flag_button)]
        for direction, values in ((settings.ui_scale_increase, range(105, 151, 5)),
                                  (settings.ui_scale_decrease, range(145, 99, -5))):
            for percent in values:
                self.click(direction)
                self.assertEqual(self.window.width(), round(700 * percent / BASE_SCALE))
                self.assertEqual(settings.ui_scale_value.text(), f'{percent}%')
                self.assertEqual(self.controller.proxy.cacheMode(), QGraphicsItem.NoCache)
                self.assertEqual([widget.geometry() for widget in
                                 (settings.ocr_engine_combo, settings.ui_scale_control, self.window.flag_button)],
                                 originals)

    def test_repeated_clicks_at_one_desktop_point_keep_hitting_the_arrow(self):
        self.window.show_settings()
        self.window.set_ui_scale_percent(125)
        self.window.move(850, 500)
        self.settle()
        viewport = self.controller.view.viewport()
        for button, values in ((self.window.settings_window.ui_scale_increase, range(130, 181, 5)),
                               (self.window.settings_window.ui_scale_decrease, range(175, 119, -5))):
            fixed_point = viewport.mapToGlobal(self.controller.map_widget_to_view(button))
            for value in values:
                QTest.mouseClick(viewport, Qt.LeftButton, pos=viewport.mapFromGlobal(fixed_point))
                self.settle()
                self.assertEqual(self.window.config['ui_scale_percent'], value)
                self.assertTrue(button.rect().contains(button.mapFromGlobal(fixed_point)))

    def test_manual_percentage_is_applied_only_on_commit_and_escape_cancels(self):
        self.window.show_settings()
        self.settle()
        editor = self.window.settings_window.ui_scale_value
        viewport = self.controller.view.viewport()
        self.click(editor)
        QTest.keyClicks(viewport, '137')
        self.assertEqual(editor.text(), '137')
        self.assertEqual(self.window.width(), round(700 * 100 / BASE_SCALE))
        QTest.keyClick(viewport, Qt.Key_Return)
        self.settle()
        self.assertEqual(self.window.config['ui_scale_percent'], 137)
        self.assertEqual(self.window.width(), round(700 * 137 / BASE_SCALE))
        self.assertEqual(editor.text(), '137%')
        QTest.keyClick(viewport, Qt.Key_A, Qt.ControlModifier)
        QTest.keyClicks(viewport, '160')
        QTest.keyClick(viewport, Qt.Key_Escape)
        self.assertEqual(editor.text(), '137%')
        self.assertEqual(self.window.width(), round(700 * 137 / BASE_SCALE))
        QTest.keyClick(viewport, Qt.Key_Up)
        self.assertEqual(self.window.config['ui_scale_percent'], 142)

    def test_numeric_input_clamps_to_screen_and_handles_empty_input(self):
        self.window.show_settings()
        # Cocoa moves a visible window below the real menu bar. Keep this
        # artificial 640px work area on the actual available-screen origin.
        origin = self.app.primaryScreen().availableGeometry().topLeft()
        self.available.return_value = QRect(origin, QSize(1280, 640))
        self.controller.refresh()
        editor = self.window.settings_window.ui_scale_value
        viewport = self.controller.view.viewport()
        self.click(editor)
        for text, expected in (('999', 200 if sys.platform == 'darwin' else 128), ('', 200 if sys.platform == 'darwin' else 128), ('70', 80), ('90', 90), ('118%', 118)):
            QTest.keyClick(viewport, Qt.Key_A, Qt.ControlModifier)
            QTest.keyClick(viewport, Qt.Key_Backspace)
            QTest.keyClicks(viewport, text)
            QTest.keyClick(viewport, Qt.Key_Return)
            self.settle()
            self.assertEqual(editor.text(), f'{expected}%')
            self.assertEqual(self.window.config['ui_scale_percent'], expected)
            self.assertTrue(self.available.return_value.contains(self.window.geometry()),
                            (text, self.window.geometry(), self.available.return_value))

    def test_leaving_the_number_field_keeps_the_clicked_control_under_the_pointer(self):
        self.window.show_settings()
        self.window.move(850, 500)
        self.settle()
        settings = self.window.settings_window
        viewport = self.controller.view.viewport()
        self.click(settings.ui_scale_value)
        QTest.keyClicks(viewport, '130')
        self.click(settings.ui_scale_decrease)
        self.assertEqual(self.window.config['ui_scale_percent'], 125)
        self.click(settings.ui_scale_value)
        QTest.keyClicks(viewport, '130')
        self.click(settings.ui_scale_increase)
        self.assertEqual(self.window.config['ui_scale_percent'], 135)
        self.click(settings.ui_scale_value)
        QTest.keyClicks(viewport, '150')
        self.click(settings.translator_combo)
        self.assertEqual(self.window.config['ui_scale_percent'], 150)
        self.assertTrue(settings.translator_combo.view().window().isVisible())
        QTest.keyClick(viewport, Qt.Key_Escape)

    def test_window_edges_and_exposed_backing_follow_the_theme_during_scaling(self):
        self.window.show_settings()
        for theme in ('Светлая', 'Темная', 'Светлая', 'Темная'):
            if self.window.current_theme != theme:
                self.window.toggle_theme()
            expected = main.THEMES[theme]['background']
            for percent in (100, 137, 200):
                self.window.set_ui_scale_percent(percent)
                self.settle()
                self.assertEqual(self.controller.view.backgroundBrush().color().name(), expected)
                self.assertEqual(self.controller.view.viewport().palette().color(QPalette.Window).name(), expected)
                picture = self.window.grab().toImage()
                for x in (1, picture.width() - 2):
                    self.assertEqual(picture.pixelColor(x, picture.height() // 2).name(), expected)
            # Inspect the surface a resize exposes before the canvas is painted.
            self.window.ui_root.hide()
            self.settle()
            picture = self.window.grab().toImage()
            self.assertEqual(picture.pixelColor(picture.width() // 2, picture.height() // 2).name(), expected)
            self.window.ui_root.show()

    def test_shadow_button_repaints_on_first_theme_switch_and_after_settings(self):
        viewport = self.controller.view.viewport()
        for from_settings in (False, True):
            for theme in ('Светлая', 'Темная', 'Светлая'):
                if from_settings:
                    self.window.show_settings()
                if self.window.current_theme != theme:
                    self.window.toggle_theme()
                if from_settings:
                    self.window.show_main_screen()
                button = self.window.start_button
                for percent in (100, 137, 200):
                    self.window.set_ui_scale_percent(percent)
                    self.settle()
                    geometry = button.geometry()
                    for state in ('normal', 'hover', 'pressed', 'disabled'):
                        with self.subTest(theme=theme, percent=percent, state=state, from_settings=from_settings):
                            button.setEnabled(state != 'disabled')
                            button.setDown(state == 'pressed')
                            QTest.mouseMove(viewport, self.controller.map_widget_to_view(button)
                                            if state in ('hover', 'pressed') else QPoint(2, 2))
                            self.settle()
                            # Sample the painted button in the scaled main window,
                            # clear of its border and caption, rather than its QSS.
                            point = self.controller.map_widget_to_view(button, QPoint(10, button.height() // 2))
                            point = viewport.mapTo(self.window, point)
                            picture = self.window.grab().toImage()
                            ratio = picture.devicePixelRatio()
                            background = picture.pixelColor(round(point.x() * ratio), round(point.y() * ratio))
                            self.assertEqual(background.lightness() > 128, theme == 'Светлая', background.name())
                            self.assertEqual(button.geometry(), geometry)
                    button.setEnabled(True)
                    button.setDown(False)

    def test_rapid_theme_changes_and_navigation_paint_the_final_theme(self):
        viewport = self.controller.view.viewport()
        self.window.show_settings()
        cached_settings = self.window.settings_window
        for percent in (100, 137, 200):
            self.window.set_ui_scale_percent(percent)
            for switches in (3, 4):
                # No event processing between changes: a coalesced repaint
                # must use the final theme after returning from Settings.
                self.window.show_settings()
                self.assertIs(self.window.settings_window, cached_settings)
                for _ in range(switches):
                    self.window.toggle_theme()
                self.window.show_main_screen()
                self.settle()
                picture = self.window.grab().toImage()
                expected = main.THEMES[self.window.current_theme]['background']
                for x in (1, picture.width() - 2):
                    self.assertEqual(picture.pixelColor(x, picture.height() // 2).name(), expected)
                button = self.window.start_button
                point = self.controller.map_widget_to_view(button, QPoint(10, button.height() // 2))
                point = viewport.mapTo(self.window, point)
                ratio = picture.devicePixelRatio()
                color = picture.pixelColor(round(point.x() * ratio), round(point.y() * ratio))
                self.assertEqual(color.lightness() > 128, self.window.current_theme == 'Светлая')

    def test_theme_transaction_freezes_the_proxy_canvas_and_open_dialog(self):
        from PyQt5.QtWidgets import QDialog
        self.window.show_settings()
        dialog = QDialog(self.window)
        dialog.show()
        self.settle()
        settings = self.window.settings_window
        original = settings.apply_theme
        observed = []

        def apply_and_inspect():
            observed.append((self.window.updatesEnabled(), self.window.ui_root.updatesEnabled(),
                             dialog.updatesEnabled()))
            original()
        with mock.patch.object(settings, 'apply_theme', side_effect=apply_and_inspect):
            self.window.toggle_theme()
        self.assertEqual(observed, [(False, False, False)])
        self.assertTrue(self.window.updatesEnabled())
        self.assertTrue(self.window.ui_root.updatesEnabled())
        self.assertTrue(dialog.updatesEnabled())
        expected = main.THEMES[self.window.current_theme]['background']
        self.assertEqual(self.controller.scene.backgroundBrush().color().name(), expected)
        self.assertEqual(self.window.ui_root.palette().color(QPalette.Window).name(), expected)
        dialog.close()
        dialog.deleteLater()
