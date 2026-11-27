"""Selected-model preparation and real child ownership, without user input."""
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest

import ocr
from ocr_lifecycle import IdleLifetime, IDLE_SECONDS
from ocr_readiness import ReadinessService
from native_worker_client import NativeWorkerClient, WorkerBusy
from test_demand_performance import child_adapter


def test_idle_deadline_pin_and_resume_with_five_full_minutes():
    now = [0.]
    lifetime = IdleLifetime(clock=lambda: now[0])
    assert IDLE_SECONDS == 300 and lifetime.remaining() == 300
    now[0] = 299
    assert lifetime.remaining() == 1
    lifetime.pin(True)
    now[0] = 3600
    assert lifetime.remaining() is None
    lifetime.pin(False)
    assert lifetime.remaining() == 300
    now[0] += 200
    lifetime.pin(False)  # Redundant UI updates cannot extend the deadline.
    assert lifetime.remaining() == 100
    lifetime.touch()
    assert lifetime.remaining() == 300
    now[0] += 301
    assert lifetime.remaining() == 0


def test_prepare_coalesces_changes_cancels_old_and_ignores_duplicate_selection():
    client = mock.Mock()
    entered, canceled = threading.Event(), threading.Event()
    calls = []
    def prepare(engine, language, cancel):
        calls.append((engine, language, threading.current_thread().name))
        if language == 'en':
            entered.set()
            assert canceled.wait(3)
            assert cancel()
            raise InterruptedError()
    service = ReadinessService(client, prepare)
    try:
        assert service.idle.is_set()
        client.refresh_policy.assert_not_called()
        service.select('RapidOCR', 'en')
        assert entered.wait(3)
        service.select('rapidocr', 'ru')
        service.select('rapidocr', 'ar')
        canceled.set()
        assert service.idle.wait(3)
        service.select('rapidocr', 'ar')
        assert [item[:2] for item in calls] == [('rapidocr', 'en'), ('rapidocr', 'ar')]
        assert all(item[2] == 'OCR-readiness' for item in calls)
        client.refresh_policy.assert_called_with('rapidocr')
    finally:
        canceled.set()
        service.shutdown()


def test_activity_changes_policy_without_loading_any_model_and_uninstall_retires():
    client = NativeWorkerClient()
    prepare = mock.Mock()
    service = ReadinessService(client, prepare)
    try:
        with mock.patch.object(client, 'retire_engine', wraps=client.retire_engine) as retire:
            service.activity('region-1', 'rapidocr')
            service.activity('region-2', 'rapidocr')
            assert service.idle.wait(3)
            assert client.is_pinned('rapidocr')
            service.activity('region-1')
            assert client.is_pinned('rapidocr')
            service.activity('region-2')
            assert not client.is_pinned('rapidocr')
            service.invalidate('rapidocr')
            assert service.idle.wait(3)
            retire.assert_called_once_with('rapidocr')
        prepare.assert_not_called()
        assert client._process is None
    finally:
        service.shutdown()


def test_shutdown_cancels_background_preparation():
    client = mock.Mock()
    entered = threading.Event()
    stopped = threading.Event()
    def prepare(engine, language, cancel):
        entered.set()
        while not cancel():
            time.sleep(.005)
        stopped.set()
    service = ReadinessService(client, prepare)
    service.select('rapidocr', 'ar')
    assert entered.wait(2)
    service.shutdown()
    assert stopped.is_set()
    client.shutdown.assert_called_once()
    service.select('rapidocr', 'ru')
    assert service.idle.is_set()


def test_owned_child_survives_idle_deadline_until_last_region_stops(child_adapter):
    command, path = child_adapter
    client = NativeWorkerClient()
    try:
        client.activity('first', 'rapidocr')
        client.activity('second', 'rapidocr')
        first = client.request(command, ('ar',), path, engine='rapidocr')
        process = client._process
        time.sleep(.55)  # Child fixture uses a .25-second deadline, not 300 s.
        assert process.poll() is None
        client.activity('first')
        client.refresh_policy('rapidocr')
        time.sleep(.35)
        assert process.poll() is None
        # Controls have no reply; subsequent replies must still match IDs.
        second = client.request(command, ('ar',), path, engine='rapidocr')
        assert first['pid'] == second['pid'] and second['count'] == 2
        client.activity('second')
        client.refresh_policy('rapidocr')
        process.wait(timeout=3)
        assert process.poll() is not None
    finally:
        client.close()


def test_preparation_deduplicates_and_real_recognition_reuses_same_child(child_adapter):
    command, path = child_adapter
    client = NativeWorkerClient()
    try:
        prepared = client.request(command, ('ar',), path, engine='rapidocr', prepare_only=True, background=True)
        process = client._process
        repeated = client.request(command, ('ar',), path, engine='rapidocr', prepare_only=True, background=True)
        assert repeated['prepared'] is True
        result = client.request(command, ('ar',), path, engine='rapidocr')
        assert result['pid'] == prepared['pid'] and result['count'] == 2
        assert client._process is process
        client.refresh_policy('openai')
        assert process.poll() is not None
    finally:
        client.close()


def test_background_preparation_does_not_queue_behind_foreground(child_adapter):
    command, path = child_adapter
    client = NativeWorkerClient()
    with client._lock:
        started = time.monotonic()
        with pytest.raises(WorkerBusy):
            client.request(command, ('ar',), path, prepare_only=True, background=True)
        assert time.monotonic() - started < .1
    client.close()


@pytest.mark.parametrize('background', [False, True])
def test_other_language_does_not_replace_a_pinned_game_model(child_adapter, background):
    command, path = child_adapter
    client = NativeWorkerClient()
    try:
        client.activity('game', 'rapidocr')
        client.request(command, ('ar',), path, engine='rapidocr')
        process = client._process
        with pytest.raises(WorkerBusy):
            client.request(command, ('ru',), path, engine='rapidocr', background=background,
                           fallback_for_other_model=True, prepare_only=background)
        assert client._process is process and process.poll() is None
    finally:
        client.close()


def test_memory_pressure_releases_even_a_pinned_child(child_adapter, tmp_path):
    command, path = child_adapter
    pressure = tmp_path / 'pressure'
    script = Path(command[1])
    contents = script.read_text(encoding='utf-8')
    contents = contents.replace('worker_lease.memory_pressure_high=lambda:False',
        f'worker_lease.memory_pressure_high=lambda:os.path.exists({str(pressure)!r})')
    contents = contents.replace('w.IDLE_SECONDS=.25',
        'w.IDLE_SECONDS=.25\nimport ocr_lifecycle\nocr_lifecycle.PRESSURE_INTERVAL=.05')
    script.write_text(contents, encoding='utf-8')
    client = NativeWorkerClient()
    try:
        client.activity('game', 'rapidocr')
        client.request(command, ('ar',), path, engine='rapidocr')
        process = client._process
        pressure.touch()
        process.wait(timeout=3)
        assert process.poll() is not None
    finally:
        client.close()


def test_uninstall_retires_a_model_even_with_an_active_workflow(child_adapter):
    command, path = child_adapter
    client = NativeWorkerClient()
    service = ReadinessService(client, mock.Mock())
    try:
        client.activity('game', 'rapidocr')
        client.request(command, ('ar',), path, engine='rapidocr')
        process = client._process
        service.invalidate('rapidocr')
        assert service.idle.wait(3)
        assert process.poll() is not None and client._process is None
    finally:
        service.shutdown()


@pytest.mark.parametrize('engine', ['Windows', 'Tesseract', 'EasyOCR', 'OpenAI API', ''])
def test_unsupported_preparation_never_imports_or_starts_native_runtime(engine):
    with mock.patch('component_runtime.managed_runtime') as runtime, \
         mock.patch.object(ocr, '_call_native_ocr_worker') as call:
        assert not ocr.prepare_selected_ocr(engine, 'ar')
    runtime.assert_not_called()
    call.assert_not_called()


def test_selected_installed_model_only_and_memory_pressure_blocks_preparation():
    with mock.patch('worker_lease.memory_pressure_high', return_value=False), \
         mock.patch('component_runtime.managed_runtime', return_value={'folder': 'installed'}), \
         mock.patch('rapidocr_models.installed_languages', return_value=['ar']), \
         mock.patch.object(ocr, '_call_native_ocr_worker', return_value={'prepared': True}) as call:
        assert not ocr.prepare_selected_ocr('RapidOCR', 'ru')
        call.assert_not_called()
        assert ocr.prepare_selected_ocr('RapidOCR', 'ar')
        assert call.call_args.args[0] == dict(action='prepare', engine='rapidocr', root_dir='installed',
                                             language_code='ar', allow_download=False)
        assert call.call_args.kwargs['resident_only']
    with mock.patch('worker_lease.memory_pressure_high', return_value=True), \
         mock.patch.object(ocr, '_call_native_ocr_worker') as call:
        assert not ocr.prepare_selected_ocr('RapidOCR', 'ar')
        call.assert_not_called()


def test_preparation_restores_persistent_rapidocr_detector_flag():
    import ocr_worker
    calls = []
    class Engine:
        use_det = True
        def __call__(self, image, use_det=None):
            if use_det is not None:
                self.use_det = use_det
            calls.append(self.use_det)
    engine = Engine()
    ocr_worker._exercise_rapidocr(engine, object())
    engine(object())
    assert calls == [False, True, True]
    with mock.patch.object(Engine, '__call__', side_effect=RuntimeError('unavailable')):
        with pytest.raises(RuntimeError):
            ocr_worker._exercise_rapidocr(engine, object())
    assert engine.use_det


def test_old_adapter_does_not_run_useless_one_shot_warmup(tmp_path):
    root = tmp_path / 'component'
    (root / 'runtime').mkdir(parents=True)
    (root / 'runtime/COMPONENT.json').write_text(json.dumps({'ocr_worker_protocol': 1}))
    runtime = dict(folder=root, command=['private-python', 'old-worker'], receipt={'generation': 'old'})
    with mock.patch('component_runtime.managed_runtime', return_value=runtime), \
         mock.patch('component_runtime.source_ocr_adapter_command', return_value=None), \
         mock.patch('component_store.ComponentStore') as store, \
         mock.patch('subprocess.run') as run:
        store.return_value.lease.return_value.__enter__.return_value = None
        result = ocr._call_native_ocr_worker({'action': 'prepare', 'engine': 'rapidocr'}, resident_only=True)
        assert not result['prepared']
        run.assert_not_called()


def test_layout_ui_construction_does_not_start_readiness():
    import ocr_readiness
    with mock.patch.object(ocr_readiness.SERVICE, 'select') as select:
        ocr_readiness.selected({'ocr_engine': 'RapidOCR', 'last_ocr_language': 'ar'})
        select.assert_not_called()


def test_main_hotkey_language_change_prepares_only_ocr_source():
    import main
    window = SimpleNamespace(config={'ocr_engine': 'RapidOCR', 'ocr_translate_source_language': 'en'},
        _available_hotkey_translation_pairs=lambda mode: {('ar', 'ru'), ('ar', 'en'), ('en', 'ru')},
        save_config=mock.Mock(), _refresh_selection_pair_hint=mock.Mock())
    with mock.patch('ocr_readiness.selected') as select:
        assert main.DarkThemeApp._set_hotkey_translation_pair(window, 'ocr', 'ar', 'ru')
        select.assert_called_once_with(window.config, language='ar')
        select.reset_mock()
        assert main.DarkThemeApp._set_hotkey_translation_pair(window, 'ocr', 'ar', 'en')
        select.assert_not_called()
        assert main.DarkThemeApp._set_hotkey_translation_pair(window, 'selection', 'en', 'ru')
        select.assert_not_called()


def test_tray_hide_keeps_model_but_actual_quit_shuts_it_down():
    import main
    window = SimpleNamespace(force_quit=False, has_tray=lambda: True,
                             minimize_to_tray=mock.Mock(), save_config=mock.Mock())
    event = mock.Mock()
    with mock.patch('ocr_readiness.SERVICE.shutdown') as shutdown, \
         mock.patch('mode_coordinator.stop_active_mode'):
        main.DarkThemeApp.closeEvent(window, event)
        shutdown.assert_not_called()
        window.minimize_to_tray.assert_called_once()
        event.ignore.assert_called_once()
        window.force_quit = True
        window._background_services = True
        main.DarkThemeApp.closeEvent(window, event)
        shutdown.assert_called_once()
        event.accept.assert_called_once()


@pytest.mark.parametrize('fullscreen', [False, True])
def test_dynamic_session_controls_hold_pause_resume_and_release(fullscreen):
    from test_game_mode import GameModeWidgetTest
    helper = GameModeWidgetTest()
    with mock.patch('ocr_readiness.begin_activity') as begin, \
         mock.patch('ocr_readiness.end_activity') as end:
        overlay = (helper._fullscreen_overlay(ocr_engine='RapidOCR') if fullscreen
                   else helper._overlay(ocr_engine='RapidOCR'))
        try:
            with mock.patch.object(overlay, '_scan_once'):
                if not fullscreen:
                    overlay._start_scanning()
                owner = ('game-fullscreen:' if fullscreen else 'game-region:') + str(id(overlay))
                begin.assert_called_with(owner, 'RapidOCR')
                overlay._toggle_pause()
                end.assert_called_with(owner)
                overlay._toggle_pause()
                begin.assert_called_with(owner, 'RapidOCR')
                if not fullscreen:
                    overlay._toggle_pause()
                    begin.reset_mock()
                    overlay._start_scanning()
                    begin.assert_not_called()
        finally:
            overlay.close()
            end.assert_called_with(owner)
