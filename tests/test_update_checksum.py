"""A broken or unrelated checksum must never allow launching an updater."""
import os
import threading
import types
from unittest import mock
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
import settings_window as sw


@pytest.mark.parametrize('content,valid', [
    ('a' * 64, True),
    ('\ufeff' + 'a' * 64 + ' *app.zip\n', True),
    ('a' * 64 + '  app.zip\n', True),
    ('SHA256 (app.zip) = ' + 'a' * 64, True),
    ('a' * 64 + ' *app.zip.exe', False),
    ('a' * 64 + ' *another.zip', False),
    ('hash: ' + 'a' * 64, False),
    (('a' * 64 + ' *app.zip\n') * 2, False),
    ('a' * 64 + '\n' + 'b' * 64, False),
    ('not a checksum', False),
    ('', False),
])
def test_checksum_matches_exactly_one_file(tmp_path, content, valid):
    checksum = tmp_path / 'checksum.txt'
    checksum.write_text(content, encoding='utf-8')
    assert sw.SettingsWindow._read_checksum(None, checksum, 'app.zip') == ('a' * 64 if valid else '')


@pytest.mark.parametrize('checksum_url,content', [('', ''), ('https://example.invalid/hash', 'broken')])
def test_unverified_package_never_reaches_apply_helper(tmp_path, checksum_url, content):
    dummy = types.SimpleNamespace(parent=None, _update_cancel_requested=threading.Event(),
        _check_update_cancel_requested=mock.Mock(), _cleanup_update_temp_dir=mock.Mock(),
        _launch_apply_updater=mock.Mock(return_value=(True, None)))
    dummy._read_checksum = types.MethodType(sw.SettingsWindow._read_checksum, dummy)
    def download(url, path, **kwargs):
        if url == checksum_url:
            from pathlib import Path
            Path(path).write_text(content, encoding='utf-8')
        else:
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('test', 'payload')
    dummy._download_file = mock.Mock(side_effect=download)
    with mock.patch.object(sw.tempfile, 'mkdtemp', return_value=str(tmp_path)), \
         mock.patch.object(sw.QMetaObject, 'invokeMethod') as posted:
        sw.SettingsWindow._download_and_prepare_update(dummy, 'https://example.invalid/app.zip', 'app.zip', '2.0.0', checksum_url)
    dummy._launch_apply_updater.assert_not_called()
    assert '_on_update_failed' in [call.args[1] for call in posted.call_args_list]
    if not checksum_url:
        dummy._download_file.assert_not_called()


@pytest.mark.parametrize('name', [
    'Click-n-Translate-1.8.0-macos-arm64.zip',
    'ClicknTranslate-1.8.0-macos-x86_64.zip',
    'ClicknTranslate-linux-x86_64.zip',
    'Click-n-Translate-1.8.0-verification.zip',
    'ClicknTranslate-1.8.0-source.zip',
    'unrelated-windows-x64.zip',
    'ClicknTranslate-windows-arm64.zip',
])
def test_windows_never_uses_another_platform_or_service_archive(name):
    with mock.patch.object(sw, '_is_inno_installed_copy', return_value=False):
        assert sw.SettingsWindow._pick_update_asset(None, [
            {'name': name, 'browser_download_url': 'https://example.invalid/file'},
        ]) is None
