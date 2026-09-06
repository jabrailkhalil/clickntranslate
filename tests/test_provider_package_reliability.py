"""Failure-path checks use temporary packages and never alter installed engines."""
import io
import os
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
import requests
import cache_manager
import package_installation
import settings_window as sw
import translater


@pytest.mark.parametrize('provider,chunk_function,limit', [
    ('google_translate', '_google_translate_chunk', 1500),
    ('mymemory_translate', '_mymemory_translate_chunk', 500),
    ('lingva_translate', '_lingva_translate_chunk', 1500),
    ('libretranslate', '_libretranslate_chunk', 1500),
    ('hymt_translate', '_hymt_translate_chunk', 1000),
])
@pytest.mark.parametrize('text', [
    '  Привет, мир!\r\n\r\n' * 200 + 'Конец.  ',
    '你好世界🙂' * 600,
    'word ' * 1300,
    'x' * 5001,
    ' \n\t ' * 600,
])
def test_long_translation_preserves_boundaries_and_limits_requests(provider, chunk_function, limit, text):
    def identity(chunk, *_args, **_kwargs):
        assert chunk.strip()
        assert len(chunk.encode('utf-8')) <= limit
        return chunk
    with mock.patch.object(translater, chunk_function, side_effect=identity):
        assert getattr(translater, provider)(text, 'en', 'ru') == text


@pytest.mark.parametrize('provider', ['google_translate', 'mymemory_translate', 'lingva_translate', 'libretranslate'])
def test_empty_translation_never_contacts_provider(provider):
    with mock.patch.object(translater, '_get_http_session') as session:
        for text in ('', ' \n\t '):
            assert getattr(translater, provider)(text, 'en', 'ru') == text
        session.assert_not_called()


@pytest.mark.parametrize('provider,method,field', [('lingva_translate', 'get', 'translation')])
@pytest.mark.parametrize('invalid', [None, '', '  ', 42])
def test_invalid_success_response_tries_next_instance(provider, method, field, invalid):
    responses = [mock.Mock(status_code=200), mock.Mock(status_code=200)]
    responses[0].json.return_value = {field: invalid}
    responses[1].json.return_value = {field: 'Привет'}
    request = mock.Mock(side_effect=responses)
    with mock.patch.object(translater, '_get_http_session', return_value=SimpleNamespace(**{method: request})):
        assert getattr(translater, provider)('Hello', 'en', 'ru') == 'Привет'
    assert request.call_count == 2


@pytest.mark.parametrize('invalid', [None, '', '  ', 42])
def test_libretranslate_invalid_response_is_reported(invalid):
    response = mock.Mock(status_code=200)
    response.json.return_value = {'translatedText':invalid}
    with mock.patch.object(translater, '_get_http_session', return_value=SimpleNamespace(post=lambda *args,**kwargs:response)):
        with pytest.raises(Exception, match='empty or invalid translation'):
            translater.libretranslate('Hello','en','ru')


@pytest.mark.parametrize('custom_url', ['', 'https://translator.example.test'])
def test_libretranslate_key_is_sent_only_to_selected_server(custom_url):
    response = mock.Mock(status_code=403)
    response.json.return_value = {'error':'API key rejected'}
    post = mock.Mock(return_value=response)
    with mock.patch.dict(os.environ, {'CLICKNTRANSLATE_LIBRETRANSLATE_API_KEY':'test-only-key','CLICKNTRANSLATE_LIBRETRANSLATE_URL':custom_url}), \
         mock.patch.object(translater, '_get_http_session', return_value=SimpleNamespace(post=post)):
        with pytest.raises(Exception, match='API key rejected'):
            translater.libretranslate('Hello','en','ru')
    post.assert_called_once()
    assert post.call_args.args[0] == (custom_url or 'https://libretranslate.com') + '/translate'
    assert post.call_args.kwargs['json']['api_key'] == 'test-only-key'


def test_provider_failure_never_caches_a_substitute_translation():
    with mock.patch.object(translater, 'get_cached_translator_config', return_value={}), \
         mock.patch.object(cache_manager, 'get_cached_translation', return_value=None), \
         mock.patch.object(cache_manager, 'save_cached_translation') as save, \
         mock.patch.object(translater, 'google_translate', side_effect=RuntimeError('offline')), \
         mock.patch.object(translater, '_try_argos_translate', return_value='Привет'):
        with pytest.raises(RuntimeError, match='offline'):
            translater.translate_text('Hello', 'en', 'ru', engine='google')
    save.assert_not_called()


class DownloadResponse:
    def __init__(self, status=200, headers=None, chunks=()):
        self.status_code = status
        self.headers = headers or {}
        self.chunks = chunks

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, **_kwargs):
        for chunk in self.chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass


def download(destination, responses, **kwargs):
    with mock.patch.object(sw.requests, 'get', side_effect=responses) as get, \
         mock.patch.object(sw.time, 'sleep'):
        sw.SettingsWindow._download_file(SimpleNamespace(), 'https://packages.test/model', str(destination), **kwargs)
    return get


def test_interrupted_download_resumes_exact_bytes_with_validator(tmp_path):
    target = tmp_path / 'model'
    target.write_bytes(b'old model')
    get = download(target, [
        DownloadResponse(headers={'Content-Length': '6', 'ETag': '"v1"'}, chunks=[b'abc', requests.ConnectionError('reset')]),
        DownloadResponse(206, {'Content-Range': 'bytes 3-5/6', 'Content-Length': '3'}, [b'def']),
    ], max_attempts=2)
    assert target.read_bytes() == b'abcdef'
    assert get.call_args_list[1].kwargs['headers']['Range'] == 'bytes=3-'
    assert get.call_args_list[1].kwargs['headers']['If-Range'] == '"v1"'
    assert get.call_args.kwargs['headers']['Accept-Encoding'] == 'identity'
    assert not target.with_suffix('.part').exists()


@pytest.mark.parametrize('response', [
    DownloadResponse(206, {'Content-Range': 'bytes 0-2/6'}, [b'abc']),
    DownloadResponse(206, {'Content-Range': 'invalid'}, [b'abc']),
    DownloadResponse(416),
    DownloadResponse(200, {'Content-Encoding': 'gzip'}, [b'bad']),
])
def test_bad_range_or_encoding_restarts_without_corrupting_file(tmp_path, response):
    target = tmp_path / 'model'
    target.write_bytes(b'old')
    (tmp_path / 'model.part').write_bytes(b'abc')
    get = download(target, [response, DownloadResponse(headers={'Content-Length':'6'}, chunks=[b'abcdef'])], max_attempts=2)
    assert target.read_bytes() == b'abcdef'
    assert 'Range' not in get.call_args_list[1].kwargs['headers']


def test_server_ignoring_range_replaces_partial_instead_of_appending(tmp_path):
    target = tmp_path / 'model'
    (tmp_path / 'model.part').write_bytes(b'old prefix')
    download(target, [DownloadResponse(headers={'Content-Length':'3'}, chunks=[b'new'])])
    assert target.read_bytes() == b'new'


def test_failed_download_preserves_existing_destination(tmp_path):
    target = tmp_path / 'model'
    target.write_bytes(b'working')
    with pytest.raises(RuntimeError):
        download(target, [DownloadResponse(headers={'Content-Length':'6'}, chunks=[b'abc'])], max_attempts=1)
    assert target.read_bytes() == b'working'


def test_cancel_removes_partial_and_preserves_old_model(tmp_path):
    target = tmp_path / 'model'
    target.write_bytes(b'working')
    (tmp_path / 'model.part').write_bytes(b'partial')
    with pytest.raises(sw.UpdateCancelledError):
        download(target, [], cancel_callback=lambda: True)
    assert target.read_bytes() == b'working'
    assert not (tmp_path / 'model.part').exists()


def make_package(path, content=b'new'):
    path.mkdir()
    (path / 'engine').write_bytes(content)
    return path


@pytest.mark.parametrize('has_previous', [False, True])
def test_invalid_engine_rolls_back_entire_install(tmp_path, has_previous):
    source = make_package(tmp_path / 'source')
    destination = tmp_path / 'installed'
    if has_previous:
        make_package(destination, b'working')
    with pytest.raises(RuntimeError, match='broken runtime'):
        package_installation.install_directory(source, destination, mock.Mock(side_effect=RuntimeError('broken runtime')))
    assert destination.exists() == has_previous
    if has_previous:
        assert (destination / 'engine').read_bytes() == b'working'
    assert not list(tmp_path.glob('.installed-install-*'))


@pytest.mark.parametrize('folder', ['models', 'tessdata', 'user_network'])
def test_engine_update_preserves_downloaded_language_models(tmp_path, folder):
    source = make_package(tmp_path / 'source')
    destination = make_package(tmp_path / 'installed', b'old')
    (destination / folder).mkdir()
    (destination / folder / 'extra-language').write_bytes(b'keep me')
    (destination / folder / 'bundled').write_bytes(b'old bundled model')
    (source / folder).mkdir()
    (source / folder / 'bundled').write_bytes(b'new bundled model')
    package_installation.install_directory(source, destination, lambda path: None, preserve=(folder,))
    assert (destination / 'engine').read_bytes() == b'new'
    assert (destination / folder / 'extra-language').read_bytes() == b'keep me'
    assert (destination / folder / 'bundled').read_bytes() == b'new bundled model'


def test_copy_failure_leaves_previous_engine_untouched(tmp_path):
    source = make_package(tmp_path / 'source')
    destination = make_package(tmp_path / 'installed', b'working')
    with mock.patch.object(package_installation.shutil, 'move', side_effect=OSError('disk full')):
        with pytest.raises(OSError, match='disk full'):
            package_installation.install_directory(source, destination, lambda path: None)
    assert (destination / 'engine').read_bytes() == b'working'


def test_cancellation_during_validation_restores_previous_engine(tmp_path):
    source = make_package(tmp_path / 'source')
    destination = make_package(tmp_path / 'installed', b'working')
    with pytest.raises(sw.UpdateCancelledError):
        package_installation.install_directory(
            source, destination, lambda path: None,
            check_cancel=mock.Mock(side_effect=[None, None, sw.UpdateCancelledError('canceled')]),
        )
    assert (destination / 'engine').read_bytes() == b'working'


@pytest.mark.parametrize('version,locked', [((3,10),False),((3,12),True),((3,13),True),((3,14),False)])
def test_easyocr_dependency_lock_matches_only_verified_python_versions(version, locked):
    dummy = SimpleNamespace(_pip_target_python_version=lambda command: version)
    requirements = sw.SettingsWindow._easyocr_requirements(dummy, ['python'])
    assert requirements == (sw.EASYOCR_PIP_PACKAGES if locked else sw.EASYOCR_PIP_PACKAGES_ANY_PYTHON)


def test_failed_rollback_keeps_recovery_files_and_reports_location(tmp_path):
    source = make_package(tmp_path / 'source')
    destination = make_package(tmp_path / 'installed', b'working')
    with mock.patch.object(package_installation.shutil, 'rmtree', side_effect=PermissionError('in use')):
        with pytest.raises(RuntimeError, match='Recovery files were preserved'):
            package_installation.install_directory(source, destination, mock.Mock(side_effect=RuntimeError('bad engine')))
    backup, = tmp_path.glob('.installed-install-*/backup/engine')
    assert backup.read_bytes() == b'working'


def test_argos_detects_corrupt_cached_zip_before_installing(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('model/model.bin', b'valid model payload')
    archive_path = tmp_path / 'cached.argosmodel'
    archive_path.write_bytes(buffer.getvalue().replace(b'valid model payload', b'wrong model payload'))
    assert zipfile.is_zipfile(archive_path)
    assert not translater._argos_archive_valid(archive_path)


@pytest.mark.parametrize('operation', ['install', 'uninstall'])
def test_partial_argos_batch_invalidates_runtime_cache(operation):
    packages = [SimpleNamespace(from_code='en', to_code=code) for code in ('de', 'ru')]
    api = SimpleNamespace(
        update_package_index=mock.Mock(), get_available_packages=lambda: packages,
        get_installed_packages=lambda: packages,
        install_from_path=mock.Mock(side_effect=[None, OSError('disk full')]),
        uninstall=mock.Mock(side_effect=[None, OSError('file busy')]),
    )
    with mock.patch.object(translater, '_ensure_argos_available', return_value=True), \
         mock.patch.object(translater, 'arg_pkg', api), \
         mock.patch.object(translater, '_installed_pairs', return_value=set()), \
         mock.patch.object(translater, '_download_argos_package', return_value='download'), \
         mock.patch.object(translater, '_invalidate_argos_cache') as invalidate:
        with pytest.raises(OSError):
            getattr(translater, f'_{operation}_argos_packages_local')([('en','de'),('en','ru')])
    assert invalidate.call_count == 2


def test_argos_removal_deletes_all_versions_of_requested_direction():
    packages = [SimpleNamespace(from_code='en',to_code='ru',package_version=version) for version in ('1.8','1.9')]
    unrelated = SimpleNamespace(from_code='en',to_code='de',package_version='1.9')
    api = SimpleNamespace(get_installed_packages=lambda:[*packages,unrelated], uninstall=mock.Mock())
    with mock.patch.object(translater,'_ensure_argos_available',return_value=True), \
         mock.patch.object(translater,'arg_pkg',api), \
         mock.patch.object(translater,'_invalidate_argos_cache'):
        assert translater._uninstall_argos_packages_local([('en','ru')]) == [('en','ru')]
    assert [call.args[0] for call in api.uninstall.call_args_list] == packages


def test_linux_tesseract_download_remove_and_system_package_visibility(tmp_path):
    import ocr
    binary = tmp_path / 'usr' / 'bin' / 'tesseract'
    binary.parent.mkdir(parents=True)
    binary.touch()
    system = tmp_path / 'system-tessdata'
    system.mkdir()
    (system / 'eng.traineddata').write_bytes(b'system model')
    app_root = tmp_path / 'app-data'
    owner = SimpleNamespace(_find_available_tesseract_exe=lambda: str(binary))
    dialog = SimpleNamespace(owner=owner, _cancel_requested=SimpleNamespace(is_set=lambda:False),
                             _finish_language_task=mock.Mock(), _emit_language_progress=mock.Mock())
    dialog._tesseract_data_dirs = lambda: sw.OcrLanguageManagerDialog._tesseract_data_dirs(dialog)
    dialog._tesseract_language_installed = lambda code, dirs: sw.OcrLanguageManagerDialog._tesseract_language_installed(dialog, code, dirs)
    with mock.patch.object(ocr.platform_support, 'IS_LINUX', True), \
         mock.patch.object(ocr, '_system_tessdata_dirs', return_value=[str(system)]), \
         mock.patch.object(ocr, 'get_portable_dir', return_value=str(app_root)), \
         mock.patch.object(ocr, 'get_cached_ocr_config', return_value={}), \
         mock.patch.object(requests, 'get', return_value=DownloadResponse(headers={'Content-Length':'4'},chunks=[b'data'])), \
         mock.patch.dict(os.environ):
        prepared = ocr._prepare_tesseract_data(str(binary), 'deu', raise_on_error=True)
        managed = app_root / 'ocr' / 'tessdata'
        assert prepared == [str(managed / 'deu.traineddata')]
        assert set(dialog._tesseract_data_dirs()[1]) == {str(managed), str(system)}
        assert ocr._configure_installed_tesseract_data(str(binary), 'deu') == str(managed)
        assert ocr._configure_installed_tesseract_data(str(binary), 'eng') == str(system)
        sw.OcrLanguageManagerDialog._remove_tesseract_worker(dialog, ['de'])
        dialog._finish_language_task.assert_called_with('Tesseract')
        assert not (managed / 'deu.traineddata').exists()
        sw.OcrLanguageManagerDialog._remove_tesseract_worker(dialog, ['en'])
        assert 'system Tesseract' in dialog._finish_language_task.call_args.args[1]
    assert (system / 'eng.traineddata').read_bytes() == b'system model'


def test_easyocr_removal_lists_other_affected_languages():
    dialog = SimpleNamespace(_easyocr_language_installed=lambda code: code in ('ru','uk','en'))
    dialog._easyocr_model_groups_for_language = lambda code: sw.OcrLanguageManagerDialog._easyocr_model_groups_for_language(dialog,code)
    affected = sw.OcrLanguageManagerDialog._easyocr_removal_languages(dialog,['ru'])
    assert set(affected) == {'ru','uk'}


def test_canceled_easyocr_removal_invalidates_loaded_readers():
    reset = mock.Mock()
    dialog = SimpleNamespace(
        owner=SimpleNamespace(_reset_easyocr_runtime_cache=reset),
        _cancel_requested=SimpleNamespace(is_set=lambda:True),
        _easyocr_model_groups_for_language=lambda code:['cyrillic_g2'],
        _easyocr_model_dir=lambda:'.', _finish_language_task=mock.Mock(),
    )
    sw.OcrLanguageManagerDialog._remove_easyocr_worker(dialog,['ru'])
    reset.assert_called_once_with(clear_modules=True)
