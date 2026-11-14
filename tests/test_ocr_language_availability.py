"""Selected OCR engines must expose usable languages and honor vision routing."""
import os
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5 import QtCore, QtGui, QtWidgets
import main
import ocr
import game_mode
from api_providers import VisionLayout, VisionResult
from settings_window import SettingsWindow


def application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class DynamicHarness:
    _populate_game_language_controls = SettingsWindow._populate_game_language_controls
    _populate_game_targets = SettingsWindow._populate_game_targets
    _update_game_swap_enabled = SettingsWindow._update_game_swap_enabled
    _save_game_language_pair = SettingsWindow._save_game_language_pair

    def __init__(self, **config):
        self.app = application()
        self.parent = SimpleNamespace(config=dict(game_translate_source_language='en',
            game_translate_target_language='ru', translator_engine='Google', **config),
            current_interface_language='en', save_config=mock.Mock())
        self.game_source_combo = QtWidgets.QComboBox()
        self.game_target_combo = QtWidgets.QComboBox()
        self.game_swap_button = QtWidgets.QPushButton()
        self.game_launch_button = QtWidgets.QPushButton()


def test_missing_ocr_languages_do_not_offer_translation_targets_or_change_saved_pair():
    harness = DynamicHarness()
    with mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=[]):
        harness._populate_game_language_controls()
    assert harness.game_source_combo.currentData() is None
    assert harness.game_target_combo.currentData() is None
    assert 'installed' in harness.game_source_combo.currentText()
    assert not harness.game_source_combo.isEnabled()
    assert not harness.game_target_combo.isEnabled()
    assert not harness.game_swap_button.isEnabled()
    assert not harness.game_launch_button.isEnabled()
    assert 'Language packages' in harness.game_launch_button.toolTip()
    harness._save_game_language_pair()
    harness.parent.save_config.assert_not_called()
    assert harness.parent.config['game_translate_source_language'] == 'en'
    assert harness.parent.config['game_translate_target_language'] == 'ru'


def test_ocr_probe_failure_does_not_advertise_the_whole_language_catalog():
    harness = DynamicHarness()
    with mock.patch.object(ocr, 'installed_ocr_language_codes', side_effect=RuntimeError('probe')):
        harness._populate_game_language_controls()
    assert harness.game_source_combo.currentData() is None
    assert not harness.game_launch_button.isEnabled()


def test_missing_argos_direction_is_described_as_translation_not_missing_ocr():
    harness = DynamicHarness()
    harness.parent.config['translator_engine'] = 'argos'
    with mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=['en']), \
            mock.patch.object(ocr, '_installed_argos_translation_pairs', return_value=set()):
        harness._populate_game_language_controls()
    assert 'translation pairs' in harness.game_source_combo.currentText()
    assert harness.game_source_combo.currentData() is None
    assert not harness.game_launch_button.isEnabled()


def test_translation_probe_failure_is_disabled_and_can_recover():
    harness = DynamicHarness()
    with mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=['en', 'zh']), \
            mock.patch.object(ocr, '_translation_targets_for_source', side_effect=RuntimeError('probe')):
        harness._populate_game_language_controls()
    assert harness.game_source_combo.currentData() == 'en'
    assert harness.game_target_combo.currentData() is None
    assert not harness.game_launch_button.isEnabled()
    with mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=['en', 'zh']):
        harness._populate_game_language_controls()
    assert harness.game_source_combo.isEnabled()
    assert harness.game_target_combo.isEnabled()
    assert harness.game_launch_button.isEnabled()
    assert harness.game_target_combo.currentData() == 'ru'
    assert harness.game_source_combo.findData('ru') == -1
    assert not harness.game_swap_button.isEnabled()


def test_main_ocr_hotkey_pairs_fail_closed_without_hiding_text_only_modes():
    pairs = {('en', 'ru'), ('ru', 'en')}
    harness = SimpleNamespace(config={'ocr_engine': 'EasyOCR'},
                              _available_main_translation_pairs=lambda: pairs)
    with mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=[]):
        for mode in ('ocr', 'fullscreen', 'game'):
            assert main.DarkThemeApp._available_hotkey_translation_pairs(harness, mode) == set()
        assert main.DarkThemeApp._available_hotkey_translation_pairs(harness, 'selection') == pairs
    with mock.patch.object(ocr, 'installed_ocr_language_codes', side_effect=RuntimeError('probe')):
        assert main.DarkThemeApp._available_hotkey_translation_pairs(harness, 'ocr') == set()


def direct_config(direct=True):
    return {'ocr_engine': 'OpenAI API', 'translator_engine': 'argos', 'ocr_translate_target_language': 'ar',
            'api_providers': {'openai': {'vision': True, 'direct': direct}}}


def test_direct_image_translation_ignores_unrelated_missing_argos_packages():
    config = direct_config()
    harness = SimpleNamespace(config=config, _available_main_translation_pairs=lambda: set())
    with mock.patch.object(ocr, '_installed_argos_translation_pairs', return_value=set()), \
            mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=['en', 'ar']):
        assert 'ar' in ocr._translation_targets_for_source('en', config)
        assert ('en', 'ar') in ocr._ocr_translate_options_from_config(config)
        assert ('en', 'ar') in main.DarkThemeApp._available_hotkey_translation_pairs(harness, 'game')
        assert main.DarkThemeApp._available_hotkey_translation_pairs(harness, 'selection') == set()
    with mock.patch.object(ocr, '_installed_argos_translation_pairs', return_value=set()):
        assert ocr._translation_targets_for_source('en', direct_config(False)) == []


class FakeApiWorker(QtCore.QObject):
    result_ready = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, provider, image, source, target, config):
        super().__init__()
        self.provider, self.image, self.source, self.target, self.config = provider, image, source, target, config
        self.start = mock.Mock()

    def cancel(self):
        pass


def region_overlay(direct=True):
    application()
    config = dict(direct_config(direct), theme='Темная', interface_language='en', history=False)
    with mock.patch.object(ocr, 'get_cached_ocr_config', return_value=config), \
            mock.patch.object(game_mode, '_exclude_from_windows_capture', return_value=True):
        overlay = game_mode.GameTranslationOverlay(QtCore.QRect(100, 100, 400, 100), 'en', 'ar')
    overlay._timer.stop()
    return overlay


def test_dynamic_region_uses_vision_worker_with_original_image_and_direct_result():
    import api_ocr
    overlay = region_overlay()
    image = QtGui.QImage(120, 40, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor('red'))
    try:
        with mock.patch.object(api_ocr, 'ApiOCRWorker', FakeApiWorker), \
                mock.patch.object(game_mode, '_prepare_game_ocr_variants') as preprocess, \
                mock.patch.object(overlay, '_start_translation') as separate_translation:
            overlay._start_ocr(image)
            worker = next(iter(overlay._workers))
            assert worker.provider == 'openai'
            assert worker.source == 'en' and worker.target == 'ar'
            assert worker.image.size == (120, 40)
            assert worker.image.getpixel((1, 1)) == (255, 0, 0)
            preprocess.assert_not_called()
            worker.start.assert_called_once()
            worker.result_ready.emit(VisionResult('Hello world', 'مرحبا بالعالم'))
            worker.finished.emit()
            assert overlay.translation_label.text() == 'مرحبا بالعالم'
            assert not overlay._ocr_busy
            separate_translation.assert_not_called()
    finally:
        overlay.close()


def test_dynamic_ocr_only_api_uses_selected_text_translator_and_shows_failure_detail():
    import api_ocr
    overlay = region_overlay(False)
    image = QtGui.QImage(120, 40, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor('white'))
    try:
        with mock.patch.object(api_ocr, 'ApiOCRWorker', FakeApiWorker), \
                mock.patch.object(overlay, '_start_translation') as translate:
            overlay._start_ocr(image)
            worker = next(iter(overlay._workers))
            assert worker.target is None
            worker.result_ready.emit(VisionResult('Hello world', None))
            translate.assert_called_once_with('Hello world')
            worker.failed.emit('Connection failed')
            assert overlay.status_label.toolTip() == 'Connection failed'
            worker.finished.emit()
    finally:
        overlay.close()


def test_closed_dynamic_session_ignores_late_api_response():
    overlay = region_overlay()
    try:
        overlay._closed = True
        with mock.patch.object(overlay, '_apply_translation') as display:
            overlay._on_api_ocr_result(VisionResult('Hello', 'مرحبا'))
            display.assert_not_called()
    finally:
        overlay.close()


def test_single_shot_fullscreen_keeps_direct_translations_when_dispatching_worker():
    lines = VisionLayout([(10, 10, 100, 25, 'Hello')])
    lines.translations = ['مرحبا']
    harness = SimpleNamespace(_translation_run_id=1, _translate_all=mock.Mock(), _fail_translation=mock.Mock())
    with mock.patch('threading.Thread') as thread:
        ocr.FullScreenTranslateOverlay._on_ocr_complete(harness, lines, 1, 'en', 'ar')
    dispatched = thread.call_args.kwargs['args'][1]
    assert isinstance(dispatched, VisionLayout)
    assert dispatched is not lines
    assert dispatched.translations == ['مرحبا']
    harness._fail_translation.assert_not_called()


def test_dynamic_fullscreen_requests_and_uses_direct_positioned_translations():
    application()
    config = dict(direct_config(), theme='Темная', interface_language='en', history=True)
    with mock.patch.object(ocr, 'get_cached_ocr_config', return_value=config), \
            mock.patch.object(game_mode, '_exclude_from_windows_capture', return_value=True):
        overlay = game_mode.GameFullscreenOverlay('en', 'ar')
    overlay._timer.stop()
    overlay._settle_timer.stop()
    image = QtGui.QImage(120, 40, QtGui.QImage.Format_RGB32)
    lines = VisionLayout([(10, 10, 100, 25, 'Hello')])
    lines.translations = ['مرحبا']
    try:
        worker = FakeApiWorker('openai', None, 'en', 'ar', config)
        with mock.patch.object(ocr, 'create_position_ocr_worker', return_value=worker), \
                mock.patch.object(overlay, '_start_block_translation') as translate, \
                mock.patch.object(ocr, 'save_translation_history') as history:
            overlay._start_position_ocr(image)
            assert worker.translation_target_code == 'ar'
            worker.result_ready.emit(lines)
            worker.finished.emit()
            assert overlay._blocks == [(10, 10, 100, 25, 'Hello', 'مرحبا')]
            assert overlay._has_shown_translation
            translate.assert_not_called()
            history.assert_called_once_with('Hello', 'مرحبا', 'ar')
            overlay._on_position_ocr_result(lines)
            history.assert_called_once()
    finally:
        overlay.close()
