"""Release metadata cannot turn a prerelease/build or x86 asset into an upgrade."""
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

import settings_window as settings


@pytest.mark.parametrize('current,latest,expected', [
    ('1.8.2', '1.8.2-rc.1', 'up_to_date'),
    ('1.8.2', '1.8.2-beta.8', 'up_to_date'),
    ('1.8.2', '1.8.2+build.100', 'up_to_date'),
    ('1.8.2', 'v1.8.2+artifact.20261106', 'up_to_date'),
    ('1.8.2', '1.8.2.0', 'up_to_date'),
    ('1.8.2', 'v1.8.3', 'ready'),
    ('1.8.2-rc.1', '1.8.2', 'ready'),
])
def test_release_check_orders_release_versions_without_suffix_digits(current, latest, expected):
    artifact = {'name': 'ClicknTranslate-windows-x64.zip',
                'browser_download_url': 'https://example.invalid/not-downloaded.zip'}
    owner = SimpleNamespace(
        parent=SimpleNamespace(current_interface_language='en'),
        _update_cancel_requested=threading.Event(),
        _pick_update_asset=mock.Mock(return_value=artifact),
        _pick_checksum_url=mock.Mock(return_value='https://example.invalid/not-downloaded.sha256'),
        _post_update_check_result=mock.Mock())
    response = mock.Mock()
    response.json.return_value = {'tag_name': latest, 'assets': [artifact]}
    with (mock.patch.object(settings, 'APP_VERSION', current),
          mock.patch.object(settings.requests, 'get', return_value=response)):
        settings.SettingsWindow._check_latest_release_worker(owner)
    owner._post_update_check_result.assert_called_once()
    assert owner._post_update_check_result.call_args.args[0]['status'] == expected
    if expected == 'up_to_date':
        owner._pick_update_asset.assert_not_called()
    else:
        owner._pick_update_asset.assert_called_once_with([artifact])


@pytest.mark.parametrize('installed', [False, True], ids=['portable', 'installed'])
@pytest.mark.parametrize('architecture', ['x86', 'ia32'])
@pytest.mark.parametrize('fallback', [False, True], ids=['wrong-only', 'with-x64-portable'])
def test_windows_x64_update_selection_rejects_explicit_32bit_assets(installed, architecture, fallback):
    name = (f'ClicknTranslate-1.9.0-windows-{architecture}-setup.exe' if installed else
            f'ClicknTranslate-1.9.0-windows-{architecture}.zip')
    wrong = {'name': name, 'browser_download_url': 'https://example.invalid/wrong'}
    compatible = {'name': 'Click-n-Translate-1.9.0-windows-portable-x64.zip',
                  'browser_download_url': 'https://example.invalid/compatible'}
    assets = [wrong, compatible] if fallback else [wrong]
    with (mock.patch.object(settings.platform_support, 'IS_WINDOWS', True),
          mock.patch.object(settings, '_is_inno_installed_copy', return_value=installed)):
        selected = settings.SettingsWindow._pick_update_asset(None, assets)
    assert selected is (compatible if fallback else None)


@pytest.mark.parametrize('installed', [False, True], ids=['portable', 'installed'])
@pytest.mark.parametrize('architecture', ['x86_64', 'x86-64'])
def test_windows_x64_update_selection_still_accepts_explicit_x86_64_assets(installed, architecture):
    suffix = '-installer.exe' if installed else '.zip'
    artifact = {'name': 'ClicknTranslate-1.9.0-windows-' + architecture + suffix,
                'browser_download_url': 'https://example.invalid/not-downloaded'}
    with (mock.patch.object(settings.platform_support, 'IS_WINDOWS', True),
          mock.patch.object(settings, '_is_inno_installed_copy', return_value=installed)):
        assert settings.SettingsWindow._pick_update_asset(None, [artifact]) is artifact


@pytest.mark.parametrize('installed', [False, True], ids=['portable', 'installed'])
@pytest.mark.parametrize('architecture_label', [' x86', ' (ia32)'], ids=['space', 'parentheses'])
def test_windows_32bit_architecture_tokens_are_rejected_with_filename_punctuation(installed, architecture_label):
    suffix = '-setup.exe' if installed else '.zip'
    artifact = {'name': 'ClicknTranslate-1.9.0' + architecture_label + suffix,
                'browser_download_url': 'https://example.invalid/not-downloaded'}
    with (mock.patch.object(settings.platform_support, 'IS_WINDOWS', True),
          mock.patch.object(settings, '_is_inno_installed_copy', return_value=installed)):
        assert settings.SettingsWindow._pick_update_asset(None, [artifact]) is None


@pytest.mark.parametrize('latest,current', [
    ('invalid.9', '1.8.2'),
    ('1.8.3+bad!build', '1.8.2'),
    ('1.8.3', None),
    ('1.8.3', 'invalid.1'),
])
def test_invalid_release_versions_cannot_be_accepted_as_an_upgrade(latest, current):
    assert settings._is_newer_version(latest, current) is False
