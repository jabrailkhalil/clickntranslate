"""Regression contracts for UI latency, settings transfer and diagnostics."""
import json
import threading
from pathlib import Path
from unittest import mock
import pytest
from PyQt5 import QtCore
from PyQt5.QtTest import QTest
from test_desktop_ux import app, window
import main
import diagnostics
import provider_secrets
from settings_window import settings_export_payload, validated_import_settings

_SAVE_CONFIG = main.DarkThemeApp.save_config


def test_runtime_timings_are_bounded_and_do_not_capture_arguments(monkeypatch):
    import runtime_metrics
    monkeypatch.setattr(runtime_metrics,'_SAMPLES',{})
    readings=iter([0, .01, 1, 1.03])
    monkeypatch.setattr(runtime_metrics,'time',mock.Mock(perf_counter=lambda:next(readings)))
    @runtime_metrics.measure('qa.action')
    def action(private_text):
        return private_text
    action('private-argument');action('another-private-argument')
    report=runtime_metrics.snapshot()['qa.action']
    assert report['median_ms'] == 20 and report['count'] == 2
    assert report['max_ms'] == 30 and 'private' not in json.dumps(runtime_metrics.snapshot())
    monkeypatch.setattr(runtime_metrics.time,'perf_counter',lambda:2.)
    for _ in range(80):action('private')
    assert runtime_metrics.snapshot()['qa.action']['sample_count'] == 64
    assert runtime_metrics.snapshot()['qa.action']['count'] == 82


def test_unrelated_settings_do_not_rebuild_home_or_lose_draft(window, app):
    editor=window.text_input
    editor.setPlainText('An unfinished message')
    window.show_settings()
    window.config.update(history=True, autostart=True, update_check_on_launch=False, ui_scale_percent=120)
    window.show_main_screen();app.processEvents()
    assert window.text_input is editor
    assert editor.toPlainText() == 'An unfinished message'


def test_theme_updates_cached_home_once_without_rebuilding(window, app):
    editor=window.text_input
    window.show_settings()
    with mock.patch.object(window,'_apply_main_combo_theme',wraps=window._apply_main_combo_theme) as style:
        window.toggle_theme()
        assert style.call_count == 0
        window.show_main_screen();app.processEvents()
        assert style.call_count == 1
        assert window.text_input is editor
        assert window._main_controls_theme == window.current_theme
        window.show_settings();window.show_main_screen()
        assert style.call_count == 1


def test_missing_credentials_are_cached_briefly_but_saving_is_immediate(monkeypatch):
    key=provider_secrets.account('qa-missing','https://example.test')
    provider_secrets._SESSION.pop(key,None);provider_secrets._MISSING.pop(key,None)
    vault=mock.Mock();vault.get_password.return_value=''
    clock=[100.]
    monkeypatch.setattr(provider_secrets.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(provider_secrets,'_vault',lambda:vault)
    try:
        assert provider_secrets.get_key('qa-missing','https://example.test') == ''
        assert provider_secrets.get_key('qa-missing','https://example.test') == ''
        assert vault.get_password.call_count == 1
        clock[0]+=16
        provider_secrets.get_key('qa-missing','https://example.test')
        assert vault.get_password.call_count == 2
        assert provider_secrets.set_key('qa-missing','https://example.test','qa-only-token')
        assert provider_secrets.get_key('qa-missing','https://example.test') == 'qa-only-token'
    finally:
        provider_secrets._SESSION.pop(key,None);provider_secrets._MISSING.pop(key,None)


def test_export_removes_legacy_credentials_at_every_depth_and_position_round_trips():
    config=dict(main.DEFAULT_CONFIG, desktop_assistant_position=dict(screen='qa-screen',x=.25,y=.75),
        legacy_api_key='do-not-export', extension=dict(password='do-not-export',label='keep'),
        service_profiles=[dict(access_token='do-not-export')])
    exported=settings_export_payload(config)
    assert 'do-not-export' not in json.dumps(exported)
    assert exported['settings']['extension']['label'] == 'keep'
    restored=validated_import_settings(exported,main.DEFAULT_CONFIG)
    assert restored['desktop_assistant_position'] == config['desktop_assistant_position']


def test_import_does_not_overwrite_new_language_pair_with_cached_controls(window, app, tmp_path):
    config=dict(main.DEFAULT_CONFIG, main_translation_source_language='ja',main_translation_target_language='de',
        desktop_assistant_position=dict(screen='qa',x=.3,y=.6), replace_selection_select_all=True)
    imported=tmp_path/'settings.json'
    imported.write_text(json.dumps(settings_export_payload(config)),encoding='utf-8')
    window.show_settings();settings=window.settings_window
    with (mock.patch('settings_window.QtWidgets.QFileDialog.getOpenFileName',return_value=(str(imported),'')),
          mock.patch('settings_window.QMessageBox.information'),
          mock.patch('settings_window.QMessageBox.warning') as warning,
          mock.patch.object(window,'set_autostart',return_value=False),
          mock.patch.object(window,'restart_all_hotkey_listeners'),
          mock.patch.object(window,'_sync_selection_quick_translate') as sync,
          mock.patch('main.get_cached_config',side_effect=lambda:window.config),
          mock.patch.object(window,'save_config',side_effect=lambda **kwargs:_SAVE_CONFIG(window,**kwargs))):
        settings.import_settings();app.processEvents()
        warning.assert_not_called()
        assert window.config['main_translation_source_language'] == 'ja'
        assert window.config['main_translation_target_language'] == 'de'
        assert window.config['desktop_assistant_position']['x'] == .3
        assert window.config['replace_selection_select_all'] is True
        sync.assert_called_once()


def test_export_writes_real_json_and_failed_replace_preserves_existing_files(window, tmp_path):
    window.show_settings();settings=window.settings_window
    target=tmp_path/'settings.json'
    unrelated=tmp_path/'settings.json.tmp'
    unrelated.write_text('unrelated',encoding='utf-8')
    window.config['replace_selection_select_all']=True
    with (mock.patch('settings_window.QtWidgets.QFileDialog.getSaveFileName',return_value=(str(target),'')),
          mock.patch('settings_window.QMessageBox.information'),
          mock.patch('settings_window.QMessageBox.warning') as warning):
        assert settings.export_settings() == target
        saved=target.read_bytes()
        assert json.loads(saved)['settings']['replace_selection_select_all'] is True
        with mock.patch('settings_window.os.replace',side_effect=OSError('qa write failure')):
            assert settings.export_settings() is None
        warning.assert_called_once()
    assert target.read_bytes() == saved
    assert unrelated.read_text(encoding='utf-8') == 'unrelated'
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ['settings.json','settings.json.tmp']


def test_oversized_import_is_rejected_without_changing_preferences(window, tmp_path):
    window.show_settings();settings=window.settings_window
    target=tmp_path/'oversized.json'
    target.write_bytes(b' '*(1024*1024+1))
    previous=dict(window.config)
    with (mock.patch('settings_window.QtWidgets.QFileDialog.getOpenFileName',return_value=(str(target),'')),
          mock.patch('settings_window.QMessageBox.warning') as warning):
        assert settings.import_settings() is None
        warning.assert_called_once()
    assert window.config == previous


def test_bug_report_uses_actual_data_directory_and_adds_private_safe_runtime(tmp_path, monkeypatch):
    code=tmp_path/'code';code.mkdir()
    data=tmp_path/'profile/data';data.mkdir(parents=True)
    (data/'config.json').write_text(json.dumps(dict(ui_scale_percent=120,ocr_engine='Windows',api_key='private-key')))
    monkeypatch.setattr(diagnostics,'_portable_root',lambda:code)
    report=diagnostics.create_bug_report(tmp_path/'reports',data_dir=data,runtime=dict(qt='test',timings={'ui.theme':{'max_ms':125}}))
    import zipfile
    with zipfile.ZipFile(report) as z:
        config=json.loads(z.read('safe-config.json'));runtime=json.loads(z.read('runtime.json'))
        assert config['ui_scale_percent'] == 120
        assert runtime['timings']['ui.theme']['max_ms'] == 125
        assert 'private-key' not in ''.join(z.read(n).decode('utf-8') for n in z.namelist())


@pytest.mark.parametrize('line', [
    'x-api-key: hidden-credential', 'x-goog-api-key: hidden-credential',
    '{"api_key": "hidden-credential"}', 'https://host.test/?key=hidden-credential&mode=ok',
    'Authorization: Bearer hidden-credential',
])
def test_diagnostic_redaction_covers_api_headers_json_and_urls(line):
    assert 'hidden-credential' not in diagnostics._redact(line)


def test_diagnostic_job_does_not_block_qt_event_delivery(window, app, tmp_path):
    from diagnostic_job import DiagnosticJob
    entered,released=threading.Event(),threading.Event()
    path=tmp_path/'qa.zip'
    def slow_report(**kwargs):
        entered.set();released.wait(3);return path
    completed=[];ticks=[]
    with mock.patch('diagnostics.create_bug_report',side_effect=slow_report):
        job=DiagnosticJob(window,output_dir=tmp_path)
        job.finished.connect(lambda report,error:completed.append((report,error)))
        try:
            job.start();assert entered.wait(1)
            QtCore.QTimer.singleShot(0,lambda:ticks.append(True))
            app.processEvents()
            assert ticks == [True] and job.running and not completed
        finally:
            released.set()
            for _ in range(100):
                app.processEvents()
                if completed:break
                QTest.qWait(10)
        assert completed == [(path,'')]


def test_report_action_waits_for_delivery_then_releases_completed_job(window, app, tmp_path):
    from diagnostic_job import DiagnosticJob
    from PyQt5 import sip
    window.show_settings();settings=window.settings_window
    with mock.patch.object(DiagnosticJob,'start') as start:
        job=window._create_bug_report(settings)
        # A worker may have finished while its Qt completion is still queued.
        job.running=False
        assert window._create_bug_report(settings) is job
        start.assert_called_once()
        assert not settings.create_bug_report_btn.isEnabled()
    with mock.patch('main.QMessageBox.warning') as warning:
        window._finish_bug_report(None,'qa report failure')
        warning.assert_called_once()
    assert settings.create_bug_report_btn.isEnabled()
    assert window._diagnostic_job is None and window._diagnostic_parent is None
    app.sendPostedEvents(None,QtCore.QEvent.DeferredDelete)
    assert sip.isdeleted(job)


def test_real_local_http_transport_does_not_reuse_credentials_or_follow_redirects(monkeypatch):
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    import api_providers
    import requests
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload=self.rfile.read(int(self.headers.get('Content-Length','0')))
            calls.append((self.path,dict(self.headers),payload))
            if self.path=='/redirect':
                self.send_response(302);self.send_header('Location','/unexpected');self.end_headers()
            else:
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(b'{"ok":true}')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    session=requests.Session();session.trust_env=False
    monkeypatch.setattr(api_providers,'_session',lambda:session)
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        assert api_providers._post(base+'/one',{'Authorization':'Bearer qa-one'},{'text':'example'}) == {'ok':True}
        assert api_providers._post(base+'/two',{'x-api-key':'qa-two'},{'text':'example'}) == {'ok':True}
        assert calls[0][1]['Authorization']=='Bearer qa-one'
        assert 'Authorization' not in calls[1][1]
        assert calls[1][1]['x-api-key']=='qa-two'
        assert b'qa-one' not in calls[1][2] and b'qa-two' not in calls[1][2]
        with pytest.raises(api_providers.ProviderError):
            api_providers._post(base+'/redirect',{'Authorization':'Bearer qa-one'},{})
        assert [c[0] for c in calls] == ['/one','/two','/redirect']
    finally:
        session.close();server.shutdown();server.server_close();worker.join(2)
