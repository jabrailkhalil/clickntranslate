"""Portable regression checks for macOS integration; native checks run in CI."""

import ctypes
import os
from pathlib import Path
import plistlib
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import macos_desktop as desktop
import macos_hotkeys as hotkeys
import macos_ocr as vision
import platform_support
import portable_paths


@pytest.fixture
def mac(monkeypatch, tmp_path):
    monkeypatch.setattr(platform_support, "IS_MAC", True)
    monkeypatch.setattr(platform_support, "IS_WINDOWS", False)
    monkeypatch.setattr(platform_support, "IS_LINUX", False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(desktop, 'user_data_dir', lambda: str(tmp_path / 'Library/Application Support/ClicknTranslate'))
    return tmp_path


@pytest.fixture
def app():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_data_is_outside_the_signed_app_even_for_workers(mac, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/Applications/ClicknTranslate.app/Contents/MacOS/OcrWorker")
    assert portable_paths.portable_base_dir() == str(mac / "Library/Application Support/ClicknTranslate")
    assert platform_support.default_ocr_engine() == "Apple Vision"
    assert "windows" not in platform_support.available_ocr_engines()
    assert not platform_support.supports_in_app_update()


def test_autostart_round_trip_preserves_paths_and_other_agents(mac, monkeypatch):
    bundle = mac / 'My Apps & Tools' / 'ClicknTranslate.app'
    (bundle / 'Contents/MacOS').mkdir(parents=True)
    (bundle / 'Contents/Info.plist').write_bytes(plistlib.dumps({}))
    monkeypatch.setattr(sys, 'executable', str(bundle / 'Contents/MacOS/ClicknTranslate'))
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    assert desktop.set_autostart(True)
    path = desktop.autostart_path()
    entry = plistlib.loads(path.read_bytes())
    assert entry['ProgramArguments'] == ['/usr/bin/open', '-a', str(bundle), '--args', '--autostart']
    assert 'KeepAlive' not in entry
    sibling = path.with_name('unrelated.plist')
    sibling.write_bytes(b'untouched')
    assert desktop.set_autostart(False) is False
    assert not path.exists() and sibling.read_bytes() == b'untouched'


def test_stale_and_corrupt_autostart_are_not_reported_enabled(mac, monkeypatch):
    monkeypatch.setattr(desktop, 'launch_arguments', lambda: ['/current/app'])
    desktop.set_autostart(True)
    monkeypatch.setattr(desktop, 'launch_arguments', lambda: ['/moved/app'])
    assert not desktop.autostart_enabled()
    desktop.autostart_path().write_bytes(b'not a plist')
    assert not desktop.autostart_enabled()


def test_source_autostart_keeps_resource_working_directory(mac, monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    assert desktop.set_autostart(True)
    entry = plistlib.loads(desktop.autostart_path().read_bytes())
    assert entry['WorkingDirectory'] == str(Path(desktop.__file__).resolve().parent)
    assert entry['ProgramArguments'][1] == str(Path(desktop.__file__).with_name('main.py').resolve())


@pytest.mark.parametrize('engine', ['Apple Vision', 'Tesseract', 'RapidOCR', 'EasyOCR'])
def test_imported_settings_preserve_every_available_selected_engine(mac, engine):
    import main
    merged, migrated = main.merge_config_defaults({'ocr_engine': engine})
    assert merged['ocr_engine'] == engine
    assert 'ocr_engine' not in migrated


def test_imported_windows_engine_is_migrated_before_showing_mac_picker(mac):
    import main
    merged, migrated = main.merge_config_defaults({'ocr_engine': 'Windows'})
    assert merged['ocr_engine'] == 'Apple Vision'
    assert 'ocr_engine' in migrated


@pytest.mark.parametrize('target_unchanged', [False, True])
def test_native_paste_rechecks_focus_after_releasing_modifiers(mac, monkeypatch, target_unchanged):
    events = []
    flags = iter([256, 0])
    quartz = SimpleNamespace(
        kCGEventFlagMaskControl=1, kCGEventFlagMaskAlternate=2,
        kCGEventFlagMaskShift=4, kCGEventFlagMaskCommand=256,
        kCGEventSourceStateCombinedSessionState=0, kCGHIDEventTap=0,
        CGEventSourceFlagsState=lambda _: next(flags),
        CGEventCreateKeyboardEvent=lambda _, key, pressed: (key, pressed),
        CGEventSetFlags=mock.Mock(), CGEventPost=lambda _, event: events.append(event))
    monkeypatch.setitem(sys.modules, 'Quartz', quartz)
    monkeypatch.setattr(desktop, 'permission_granted', lambda _: True)
    sleep = mock.Mock()
    monkeypatch.setattr(desktop.time, 'sleep', sleep)
    def validate():
        sleep.assert_called_once_with(.02)
        return target_unchanged
    assert desktop.send_edit_shortcut('v', validate_target=validate) == target_unchanged
    assert events == ([(9, True), (9, False)] if target_unchanged else [])


def test_optional_ocr_install_skips_rosetta_python_for_native_worker(mac, monkeypatch):
    import settings_window as settings
    owner = settings.SettingsWindow.__new__(settings.SettingsWindow)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(settings.shutil, 'which', lambda _: None)
    monkeypatch.setattr(settings.platform, 'machine', lambda: 'arm64')
    monkeypatch.setattr(platform_support, 'system_command', lambda name: '/tools/' + name)
    monkeypatch.setattr(owner, '_python_command_version', lambda _: f'{sys.version_info.major}.{sys.version_info.minor}')
    monkeypatch.setattr(owner, '_python_command_has_pip', lambda _: True)
    monkeypatch.setattr(owner, '_python_command_output',
                        lambda command, *args, **kw: (0, 'arm64' if command == ['/tools/python3'] else 'x86_64'))
    assert owner._find_rapidocr_install_python_command() == ['/tools/python3']


def test_finder_can_find_homebrew_tesseract(mac, monkeypatch):
    monkeypatch.setattr(platform_support.shutil, 'which', lambda _: None)
    monkeypatch.setattr(os.path, 'isfile', lambda path: path.replace('\\', '/') == '/opt/homebrew/bin/tesseract')
    monkeypatch.setattr(os, 'access', lambda *_: True)
    assert platform_support.system_tesseract_command().replace('\\', '/') == '/opt/homebrew/bin/tesseract'
    assert platform_support.tesseract_install_hint().startswith('brew install')


@pytest.mark.parametrize('shortcut, expected', [
    ('Ctrl+Alt+T', (256 | 2048, 17)), ('Ctrl+Shift+Space', (256 | 512, 49)),
    ('Meta+Q', (4096, 12)), ('Ctrl+Я', (256, 6)), ('Cmd+F19', (256, 80)),
])
def test_shortcut_matches_qt_portable_modifiers(shortcut, expected):
    assert hotkeys.parse_hotkey(shortcut) == expected


@pytest.mark.parametrize('shortcut', ['', 'Ctrl+', 'Ctrl+Q+W', 'Q', 'Ctrl+Unknown', 'Ctrl+F99'])
def test_invalid_shortcuts_are_rejected(shortcut):
    with pytest.raises(ValueError):
        hotkeys.parse_hotkey(shortcut)


def test_carbon_callback_ignores_repeat_and_foreign_events():
    registry = hotkeys.HotkeyRegistry.__new__(hotkeys.HotkeyRegistry)
    registry.signature = hotkeys._fourcc('CnTr')
    callback = mock.Mock()
    registry.callbacks, registry.pressed = {1: callback}, set()
    identity = hotkeys._HotkeyID(registry.signature, 1)
    # Literal values from Apple's SDK, not the implementation's constants.
    kind = [6]

    def parameter(*args):
        ctypes.memmove(args[-1], ctypes.byref(identity), ctypes.sizeof(identity))
        return 0

    registry.library = SimpleNamespace(GetEventParameter=parameter, GetEventKind=lambda _: kind[0])
    registry._handle_event(None, None, None)
    callback.assert_not_called()  # releasing cannot execute an action
    kind[0] = 5
    registry._handle_event(None, None, None)
    registry._handle_event(None, None, None)
    callback.assert_called_once()
    kind[0] = 6
    registry._handle_event(None, None, None)
    kind[0] = 5
    registry._handle_event(None, None, None)
    assert callback.call_count == 2
    kind[0] = 7
    assert registry._handle_event(None, None, None) == -9874
    assert callback.call_count == 2
    identity.signature = 0
    assert registry._handle_event(None, None, None) == -9874
    assert callback.call_count == 2


@pytest.mark.skipif(sys.platform != 'darwin', reason='requires native Carbon')
def test_native_carbon_delivers_press_release_and_reregister(app):
    if app.platformName() != 'cocoa':
        pytest.skip('requires the Cocoa event target')
    from macos_smoke import hotkey_dispatch_check
    assert hotkey_dispatch_check()['callbacks'] == 10


@pytest.mark.skipif(sys.platform != 'darwin', reason='requires native Carbon')
def test_native_hotkey_conflict_with_another_process_is_reported(app):
    if app.platformName() != 'cocoa':
        pytest.skip('requires the Cocoa event target')
    import selectors
    import subprocess
    script = '''
import sys
from PyQt5.QtWidgets import QApplication
from macos_hotkeys import registry
app = QApplication([])
identifier = registry().register('Ctrl+Alt+Shift+F17', lambda: None)
print('ready', flush=True)
sys.stdin.readline()
registry().unregister(identifier)
'''
    process = subprocess.Popen([sys.executable, '-c', script], text=True,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=str(Path(__file__).resolve().parents[1]))
    try:
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            assert ready.select(timeout=15), 'Carbon fixture did not start'
        assert process.stdout.readline().strip() == 'ready'
        with pytest.raises(RuntimeError, match='unavailable'):
            hotkeys.registry().register('Ctrl+Alt+Shift+F17', lambda: None)
    finally:
        try:
            process.communicate('\n', timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
    assert process.returncode == 0
    identifier = hotkeys.registry().register('Ctrl+Alt+Shift+F17', lambda: None)
    hotkeys.registry().unregister(identifier)


def test_vision_coordinates_keep_pixel_detail_and_flip_origin():
    rect = SimpleNamespace(origin=SimpleNamespace(x=.1, y=.6), size=SimpleNamespace(width=.3, height=.2))
    box = vision.pixel_box(rect, 2000, 1000)
    assert box[0] == pytest.approx([200, 200])
    assert box[2] == pytest.approx([800, 400])


def test_vision_does_not_silently_change_an_unsupported_language():
    assert vision.recognition_languages('ru', ['en-US', 'ru-RU']) == ['ru-RU', 'en-US']
    assert vision.recognition_languages('auto', ['en-US']) == []
    with pytest.raises(ValueError, match='does not support'):
        vision.recognition_languages('ru', ['en-US'])


def test_retina_frozen_region_preserves_resolution_and_position(app):
    from PyQt5 import QtCore, QtGui
    import ocr
    image = QtGui.QImage(400, 200, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor('white'))
    painter = QtGui.QPainter(image)
    painter.fillRect(100, 40, 80, 60, QtGui.QColor('red'))
    painter.end()
    pixmap = QtGui.QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(2)
    cropped = ocr.crop_frozen_pixmap(pixmap, QtCore.QRect(50, 20, 40, 30))
    assert (cropped.width(), cropped.height(), cropped.devicePixelRatioF()) == (80, 60, 2)
    assert cropped.toImage().pixelColor(0, 0) == QtGui.QColor('red')
    assert cropped.toImage().pixelColor(79, 59) == QtGui.QColor('red')


def test_denied_screen_permission_does_not_capture_or_prompt(mac, app, monkeypatch):
    import ocr
    monkeypatch.setattr(desktop, 'permission_granted', lambda _: False)
    screen = mock.Mock()
    assert ocr.grab_screen_pixmap(screen).isNull()
    screen.grabWindow.assert_not_called()


@pytest.mark.parametrize('engine', ['apple vision', 'tesseract', 'rapidocr', 'easyocr'])
def test_fullscreen_worker_uses_exactly_the_selected_engine(app, monkeypatch, engine):
    import ocr
    recognize = mock.Mock(return_value=[(10, 20, 30, 40, 'Text')])
    monkeypatch.setattr(ocr, '_recognize_image_layout', recognize)
    captured = []
    image = object()
    worker = ocr.FullScreenOCRWorker(image, 'ru', engine=engine)
    worker.result_ready.connect(captured.append)
    worker.run()
    recognize.assert_called_once_with(image, engine, 'ru')
    assert captured == [[(10, 20, 30, 40, 'Text')]]


def test_macos_never_downloads_windows_installers(mac):
    import settings_window as settings
    owner = settings.SettingsWindow.__new__(settings.SettingsWindow)
    with pytest.raises(RuntimeError, match='Windows-only'):
        owner._portable_pip_bootstrap_plan()
    with pytest.raises(RuntimeError, match='Windows-only'):
        owner._get_tesseract_bundle_url()


def test_macos_engine_picker_has_vision_and_no_windows(mac, app):
    from PyQt5.QtWidgets import QComboBox
    import settings_window as settings
    combo = QComboBox()
    settings._populate_grouped_ocr_combo(combo, 'ru', installed_engines={'Apple Vision'})
    engines = [combo.itemData(i) for i in range(combo.count()) if combo.itemData(i)]
    assert engines == ['Apple Vision', 'Tesseract', 'RapidOCR', 'EasyOCR']


def test_macos_permission_copy_is_localized():
    from macos_text import TEXT
    assert set(TEXT) == {'en', 'ru', 'de', 'es', 'fr', 'zh'}
    assert all(set(values) == set(TEXT['en']) and all(values.values()) for values in TEXT.values())


def test_dynamic_capture_tracks_macos_window_bounds_and_visibility(mac, monkeypatch):
    import game_mode
    monkeypatch.setattr(desktop, 'foreground_window_number', lambda: 73)
    monkeypatch.setattr(desktop, 'window_info', lambda number: {
        'kCGWindowOwnerPID': os.getpid(), 'kCGWindowIsOnscreen': True,
        'kCGWindowBounds': {'X': -200, 'Y': 40, 'Width': 900, 'Height': 600}})
    assert game_mode._foreground_window() == 73
    assert game_mode._window_rect(73).getRect() == (-200, 40, 900, 600)
    assert game_mode._window_belongs_to_this_process(73)
    assert not game_mode._window_is_minimized(73)


@pytest.mark.parametrize('engine', ['Apple Vision', 'Tesseract', 'RapidOCR', 'EasyOCR'])
def test_position_factory_keeps_selected_engine_and_retina_pixels(mac, app, monkeypatch, engine):
    import ocr
    from PyQt5.QtGui import QImage
    image = QImage(400, 200, QImage.Format_RGB32)
    image.fill(0xffffffff)
    image.setDevicePixelRatio(2)
    constructor = mock.Mock()
    monkeypatch.setattr(ocr, 'FullScreenOCRWorker', constructor)
    ocr.create_position_ocr_worker(image, 'en', engine)
    assert constructor.call_args.kwargs['engine'] == engine.lower()
    assert constructor.call_args.args[0].size == (400, 200)


def test_dynamic_position_mode_passes_its_selected_engine(app, monkeypatch):
    import game_mode
    import ocr
    factory = mock.Mock(return_value=None)
    monkeypatch.setattr(ocr, 'create_position_ocr_worker', factory)
    owner = SimpleNamespace(source_language='en', config={'ocr_engine': 'RapidOCR'}, _set_status=mock.Mock())
    image = object()
    game_mode.GameFullscreenOverlay._start_position_ocr(owner, image)
    factory.assert_called_once_with(image, 'en', 'RapidOCR')


@pytest.mark.skipif(sys.platform != 'darwin', reason='requires the real macOS frameworks')
def test_native_vision_language_catalog_is_available():
    assert 'en' in vision.language_codes()


def test_source_macos_ocr_is_also_isolated(mac, monkeypatch):
    import ocr
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.delenv('CLICKNTRANSLATE_USE_OCR_WORKER', raising=False)
    assert ocr._native_ocr_worker_enabled()
    assert ocr._native_ocr_worker_command() == [sys.executable, str(Path(ocr.__file__).with_name('ocr_worker.py'))]


def test_mac_picker_sees_rapidocr_in_the_bundled_helper(mac, monkeypatch):
    import ocr
    import settings_window as settings
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(ocr, '_native_ocr_worker_path', lambda: '/App/Contents/MacOS/OcrWorker')
    owner = SimpleNamespace(_local_rapidocr_installed=lambda: False,
                            _module_available_without_import=mock.Mock(return_value=False))
    assert settings.SettingsWindow._rapidocr_runtime_installed(owner)
    owner._module_available_without_import.assert_not_called()


def test_mac_argos_defaults_to_application_support_and_respects_overrides(mac, monkeypatch):
    import translater
    for name in ('XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME'):
        monkeypatch.delenv(name, raising=False)
    translater._prepare_argos_environment()
    expected = mac / 'Library/Application Support/ClicknTranslate/argos'
    assert Path(os.environ['XDG_DATA_HOME']) == expected / 'data'
    assert Path(os.environ['XDG_CACHE_HOME']) == expected / 'cache'
    assert Path(os.environ['XDG_CONFIG_HOME']) == expected / 'config'
    monkeypatch.setenv('XDG_DATA_HOME', str(mac / 'custom'))
    translater._prepare_argos_environment()
    assert Path(os.environ['XDG_DATA_HOME']) == mac / 'custom'
