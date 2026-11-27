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
    ('1.8.3', 'v1.8.2', 'up_to_date'),
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


def _release_item(name):
    return {'name': name, 'browser_download_url': 'https://example.invalid/' + name}


@pytest.mark.parametrize('name', [
    'ClicknTranslate-9.0.0-android-x86_64.zip',
    'ClicknTranslate-9.0.0-windows-x64-debug-symbols.zip',
    'ClicknTranslate-9.0.0-rapidocr-windows-x64-installer.exe',
])
def test_non_app_downloads_never_offer_a_windows_update(monkeypatch, name):
    monkeypatch.setattr(settings.platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(settings, '_is_inno_installed_copy', lambda: True)
    selected = settings.SettingsWindow._pick_update_asset(None, [_release_item(name)])
    assert selected is None


@pytest.mark.parametrize('asset_names,expected', [
    (['ClicknTranslate-9.0.0-arm64.apk'], False),
    (['ClicknTranslate-9.0.0-win64.zip'], False),
    (['ClicknTranslate-9.0.0-win64.zip', 'ClicknTranslate-9.0.0-win64.zip.sha256'], True),
])
def test_startup_and_manual_check_offer_the_same_installable_download(monkeypatch, asset_names, expected):
    from main import DarkThemeApp

    monkeypatch.setattr(settings.platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(settings, '_is_inno_installed_copy', lambda: False)
    reply = mock.Mock()
    reply.json.return_value = {'tag_name': 'v9.0.0', 'assets': [_release_item(name) for name in asset_names]}
    request = mock.Mock(return_value=reply)
    # A custom single-release feed is authoritative and has no history endpoint.
    monkeypatch.setenv(settings.UPDATE_API_ENV, 'https://example.invalid/qa/release')
    monkeypatch.setattr(settings.requests, 'get', request)
    launch = SimpleNamespace(_launch_update_signal=mock.Mock())
    DarkThemeApp._launch_update_worker(launch)
    assert launch._launch_update_signal.emit.called is expected

    owner = SimpleNamespace(parent=SimpleNamespace(current_interface_language='en'),
                            _update_cancel_requested=threading.Event(), _post_update_check_result=mock.Mock())
    for name in ('_pick_update_asset', '_pick_checksum_url'):
        setattr(owner, name, getattr(settings.SettingsWindow, name).__get__(owner))
    settings.SettingsWindow._check_latest_release_worker(owner)
    assert owner._post_update_check_result.call_args.args[0]['status'] == ('ready' if expected else 'no_asset')
    assert request.call_count == 2
    assert all(call.args[0] == settings._update_feed_api_url() for call in request.call_args_list)


@pytest.mark.parametrize('paginate', [False, True])
def test_desktop_can_find_a_stable_upgrade_behind_a_mobile_only_release(monkeypatch, paginate):
    from main import DarkThemeApp

    def release(version, suffix, **extra):
        name = f'ClicknTranslate-{version}-{suffix}'
        return dict(tag_name='v' + version, assets=[_release_item(name), _release_item(name + '.sha256')], **extra)

    latest = release('9.3.0', 'arm64.apk')
    page = [latest, release('9.2.5', 'win64.zip', prerelease=True),
            release('9.2.4', 'win64.zip', draft=True), release('9.0.0', 'win64.zip'),
            release('9.2.0', 'win64.zip'), release('8.1.0', 'win64.zip'),
            release('10.0.0', 'win64.zip')]
    def fetch(url, **_kwargs):
        assert url.startswith(settings.GITHUB_LATEST_RELEASE_API.rsplit('/', 1)[0])
        result = mock.Mock(links={})
        if url == settings.GITHUB_LATEST_RELEASE_API:
            result.json.return_value = latest
        elif paginate and url.endswith('page=1'):
            result.json.return_value = page[:4]
            result.links = {'next': {'rel': 'next'}}
        else:
            result.json.return_value = page[4:] if paginate else page
        return result

    monkeypatch.delenv(settings.UPDATE_API_ENV, raising=False)
    monkeypatch.setattr(settings.platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(settings, '_is_inno_installed_copy', lambda: False)
    monkeypatch.setattr(settings.requests, 'get', fetch)
    launch = SimpleNamespace(_launch_update_signal=mock.Mock())
    DarkThemeApp._launch_update_worker(launch)
    launch._launch_update_signal.emit.assert_called_once_with('9.2.0')
    owner = SimpleNamespace(parent=SimpleNamespace(current_interface_language='en'),
                            _update_cancel_requested=threading.Event(), _post_update_check_result=mock.Mock(),
                            _pick_update_asset=settings._desktop_update_asset, _pick_checksum_url=settings._desktop_checksum_url)
    settings.SettingsWindow._check_latest_release_worker(owner)
    offer = owner._post_update_check_result.call_args.args[0]
    assert (offer['status'], offer['latest_version'], offer['asset_name']) == ('ready', '9.2.0', 'ClicknTranslate-9.2.0-win64.zip')


def test_checksum_picker_prefers_an_exact_file_over_similarly_named_reports():
    name = 'ClicknTranslate-9.0.0-win64.zip'
    assets = [_release_item('audit.ClicknTranslate-9.0.0-win64.report.sha256'),
              _release_item('ClicknTranslate-9.0.0-win64.sha256'),
              _release_item(name + '.sha256')]
    assert settings.SettingsWindow._pick_checksum_url(None, assets, name) == assets[2]['browser_download_url']


@pytest.mark.parametrize('name', ['ClicknTranslate.zip', 'ClicknTranslate-Windows.zip',
                                  'ClicknTranslate-v1.5.0-win64.zip', 'ClicknTranslate-Setup-v1.5.0-win64.exe',
                                  'Click-n-Translate-1.8.2-windows-x64-installer.exe'])
def test_historical_windows_distributions_are_still_recognised(monkeypatch, name):
    monkeypatch.setattr(settings.platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(settings, '_is_inno_installed_copy', lambda: True)
    item = _release_item(name)
    assert settings.SettingsWindow._pick_update_asset(None, [item]) is item


@pytest.mark.parametrize('missing', ['checksum', 'partial_upload', 'empty'])
def test_installed_copy_can_fall_back_to_complete_portable_package(monkeypatch, missing):
    monkeypatch.setattr(settings.platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(settings, '_is_inno_installed_copy', lambda: True)
    setup = _release_item('Click-n-Translate-9.0.0-windows-x64-installer.exe')
    portable = _release_item('Click-n-Translate-9.0.0-windows-portable-x64.zip')
    manifest = _release_item(portable['name'] + '.sha256')
    assets = [setup, portable, manifest]
    if missing != 'checksum':
        checksum = _release_item(setup['name'] + '.sha256')
        checksum.update({'state': 'starter'} if missing == 'partial_upload' else {'size': 0})
        assets.append(checksum)
    offer = settings._desktop_release_offer({'tag_name': 'v9.0.0', 'assets': assets}, '1.8.3')
    assert offer['asset_url'] == portable['browser_download_url']
    assert offer['checksum_url'] == manifest['browser_download_url']


@pytest.mark.parametrize('name', [
    'Click-n-Translate-8.0.0-windows-portable-x64.zip',
    'Click-n-Translate-8.0.0-windows-x64-installer.exe',
])
def test_an_attachment_from_an_older_version_is_not_offered(monkeypatch, name):
    monkeypatch.setattr(settings.platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(settings, '_is_inno_installed_copy', lambda: True)
    assets = [_release_item(name), _release_item(name + '.sha256')]
    assert settings._desktop_release_offer({'tag_name': 'v9.0.0', 'assets': assets}, '1.8.3')['status'] == 'no_asset'
