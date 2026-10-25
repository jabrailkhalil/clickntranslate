"""Provider contracts, secrets, and single-request OCR paths without paid calls."""
import json
from unittest import mock
import pytest
from PIL import Image
import api_providers as api
import provider_secrets as secrets


@pytest.fixture
def config():
    with mock.patch.object(api, 'credential', return_value='test-secret'):
        yield {'api_providers': {p.key: {'url': p.url or 'https://custom.test/v1',
                    'model': 'test-model', 'vision': True, 'direct': True} for p in api.PROVIDERS}}


@pytest.mark.parametrize('provider,body,path', [
    ('openai', {'status':'completed', 'output':[{'type':'message', 'content':[{'type':'output_text','text':'Привет'}]}]}, '/responses'),
    ('openai-compatible', {'choices':[{'message':{'content':'Привет'},'finish_reason':'stop'}]}, '/chat/completions'),
    ('gemini', {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'Привет'}]}}]}, ':generateContent'),
    ('anthropic', {'stop_reason':'end_turn','content':[{'type':'text','text':'Привет'}]}, '/messages'),
    ('deepl', {'translations':[{'text':'Привет'}]}, '/translate'),
])
def test_text_translation_dispatches_only_to_selected_protocol(config, provider, body, path):
    with mock.patch.object(api, '_post', return_value=body) as post:
        assert api.translate(provider, 'Hello', 'en', 'ru', config) == 'Привет'
        post.assert_called_once()
        url, headers, payload, cancel = post.call_args.args
        assert url.endswith(path)
        assert 'test-secret' not in json.dumps(payload)
        if provider == 'openai':
            assert payload['store'] is False
        if provider == 'gemini':
            assert headers['x-goog-api-key'] == 'test-secret'
            assert 'test-secret' not in url


def test_image_request_returns_source_and_translation_once(config):
    with mock.patch.object(api, '_text_response', return_value='{"source":"Hello","translation":"Привет"}') as call:
        result = api.recognize('openai', Image.new('RGB',(60,30)), 'en', 'ru', config)
    assert result == api.VisionResult('Hello','Привет')
    call.assert_called_once()
    assert call.call_args.args[5].startswith('iVBOR')


def test_copy_only_does_not_request_translation(config):
    config['ocr_join_paragraphs'] = True
    with mock.patch.object(api, '_text_response', return_value='{"source":"Hello","translation":null}') as call:
        result = api.recognize('openai', Image.new('RGB',(60,30)), 'en', None, config)
    assert result.translation is None
    assert 'do not translate' in call.call_args.args[3]
    assert 'Join visual line wraps' not in call.call_args.args[3]


def test_paragraph_option_is_part_of_the_same_vision_request(config):
    config['ocr_join_paragraphs'] = True
    with mock.patch.object(api, '_text_response', return_value='{"source":"Hello there","translation":"مرحبا"}') as call:
        api.recognize('openai', Image.new('RGB', (60, 30)), 'en', 'ar', config)
    call.assert_called_once()
    assert 'Join visual line wraps' in call.call_args.args[3]


def test_positioned_one_request_result_preserves_mapping(config):
    raw = json.dumps({'regions':[{'source':'Hello','box':[100,100,900,300],'translation':'Привет'}]})
    with mock.patch.object(api, '_text_response', return_value=raw):
        result = api.recognize_regions('openai', Image.new('RGB',(200,100)), 'en','ru',config)
    assert result == [(20,10,160,20,'Hello')]
    assert result.translations == ['Привет']


@pytest.mark.parametrize('box', [[0,0,1001,30],[10,10,5,30],[0,0,float('nan'),10],[True,0,10,10]])
def test_invalid_model_boxes_are_rejected(config, box):
    with mock.patch.object(api, '_text_response', return_value=json.dumps({'regions':[{'source':'Hi','box':box,'translation':'Привет'}]})):
        with pytest.raises(api.ProviderError):
            api.recognize_regions('openai', Image.new('RGB',(20,20)), 'en','ru',config)


@pytest.mark.parametrize('url', ['http://remote.test/v1','https://user:pass@example.test/v1','https://test/v1?key=secret','file:///tmp/key'])
def test_credentials_cannot_be_sent_to_insecure_or_embedded_auth_urls(url):
    with pytest.raises(api.ProviderError): api.validate_url(url)


def test_local_compatible_server_does_not_require_a_key(config):
    config['api_providers']['openai-compatible']['url'] = 'http://localhost:11434/v1'
    with mock.patch.object(api,'credential',return_value=''):
        assert api.validate('openai-compatible',config)['url'].startswith('http://localhost')


def test_native_vault_failure_never_writes_plaintext(tmp_path):
    with mock.patch.object(secrets,'_vault',side_effect=RuntimeError('locked')):
        assert secrets.set_key('test','https://vault.test','test-secret') is False
        assert secrets.get_key('test','https://vault.test') == 'test-secret'
        assert not list(tmp_path.iterdir())
        secrets.set_key('test','https://vault.test','')


def test_connection_identity_changes_with_model_or_server(config):
    before=api.cache_identity('openai-compatible',config)
    config['api_providers']['openai-compatible']['model']='other-model'
    assert before != api.cache_identity('openai-compatible',config)
    config['api_providers']['openai-compatible']['url']='https://other.test/v1'
    assert before != api.cache_identity('openai-compatible',config)


def test_exports_and_imports_drop_secret_fields(config):
    from settings_window import settings_export_payload,validated_import_settings
    import main
    config['api_providers']['openai']['api_key']='do-not-export'
    payload=settings_export_payload(config)
    assert 'do-not-export' not in json.dumps(payload)
    accepted=validated_import_settings(payload,main.DEFAULT_CONFIG)
    assert accepted['api_providers']['openai']['model']=='test-model'


def test_http_failures_are_redacted_and_not_retried():
    response=mock.MagicMock(status_code=401)
    response.__enter__.return_value=response
    response.text='sensitive echoed key and user text'
    with mock.patch.object(api,'_session') as session:
        session.return_value.post.return_value=response
        with pytest.raises(api.ProviderError,match='HTTP 401') as error:
            api._post('https://example.test',{'Authorization':'secret'},{'text':'private'})
        assert 'sensitive' not in str(error.value)
        session.return_value.post.assert_called_once()
        assert session.return_value.post.call_args.kwargs['allow_redirects'] is False


@pytest.mark.parametrize('direct', [True, False])
def test_area_worker_skips_the_second_translator_only_for_direct_mode(config, direct):
    from api_ocr import ApiOCRWorker
    result = api.VisionResult('Hello', 'Привет' if direct else None)
    worker = ApiOCRWorker('openai', Image.new('RGB',(40,20)), 'en','ru',config)
    delivered=[]
    worker.result_ready.connect(delivered.append)
    with mock.patch.object(api,'recognize',return_value=result), mock.patch('translater.translate_text',return_value='Привет') as translate:
        worker.run()
    assert delivered == [api.VisionResult('Hello','Привет')]
    assert translate.call_count == (0 if direct else 1)


@pytest.mark.parametrize('enabled', [False, True])
def test_api_ocr_fallback_joins_wrapped_lines_before_the_text_translator(config, enabled):
    from api_ocr import ApiOCRWorker
    from test_ocr_paragraphs import REPORTED_LINES
    source = '\n'.join(REPORTED_LINES) + '\n\n1. First item\ncontinues\n2. Second item'
    expected = (' '.join(REPORTED_LINES) + '\n\n1. First item continues\n\n2. Second item'
                if enabled else source)
    config['api_providers']['openai']['direct'] = False
    config['ocr_join_paragraphs'] = enabled
    config['translator_engine'] = 'Google'
    worker = ApiOCRWorker('openai', Image.new('RGB', (40, 20)), 'en', 'ar', config)
    delivered = []
    worker.result_ready.connect(delivered.append)
    response = json.dumps({'source': source, 'translation': None})
    with (mock.patch.object(api, '_text_response', return_value=response),
          mock.patch('translater.translate_text', return_value='ترجمة') as translate):
        worker.run()
    assert translate.call_args.args == (expected, 'en', 'ar')
    assert delivered == [api.VisionResult(expected, 'ترجمة')]


def test_api_copy_keeps_recognized_lines_with_paragraph_option_enabled(config):
    source = 'First line\nsecond line\n\nAnother paragraph'
    config['api_providers']['openai']['direct'] = False
    config['ocr_join_paragraphs'] = True
    with mock.patch.object(api, '_text_response', return_value=json.dumps({
            'source': source, 'translation': None})):
        result = api.recognize('openai', Image.new('RGB', (40, 20)), 'en', None, config)
    assert result == api.VisionResult(source, None)


def test_fullscreen_direct_result_does_not_run_text_translation(config):
    from PyQt5.QtCore import QObject,pyqtSignal
    from ocr import FullScreenTranslateOverlay
    class Owner(QObject):
        _translation_result_ready=pyqtSignal(int,object,str)
        _ocr_scale_x=_ocr_scale_y=1
    owner=Owner()
    delivered=[]
    owner._translation_result_ready.connect(lambda *args:delivered.append(args))
    lines=api.VisionLayout([(0,0,40,20,'Hello')])
    lines.translations=['Привет']
    with mock.patch('translater.translate_text') as translate:
        FullScreenTranslateOverlay._translate_all(owner,1,lines,'en','ru')
    translate.assert_not_called()
    assert delivered[0][1][0][1:] == ('Hello','Привет')


@pytest.mark.parametrize('body',[{'choices':['invalid']},{'choices':{}},{'choices':None}])
def test_malformed_api_envelopes_are_reported_without_raw_payload(config, body):
    with mock.patch.object(api,'_post',return_value=body):
        with pytest.raises(api.ProviderError):
            api.translate('openai-compatible','Hello','en','ru',config)


def test_native_smoke_round_trip_removes_only_its_disposable_vault_item():
    import macos_smoke
    values={}
    class Vault:
        def set_password(self,service,name,value): values[service,name]=value
        def get_password(self,service,name): return values.get((service,name),'')
        def delete_password(self,service,name): values.pop((service,name),None)
    previous=secrets._SERVICE
    with mock.patch.object(secrets,'_vault',return_value=Vault()):
        result=macos_smoke.api_keychain_check()
    assert result == dict(storage='keychain',persisted=True,read_back=True,removed=True)
    assert not values
    assert secrets._SERVICE == previous
