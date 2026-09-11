from pathlib import Path

import pytest
from release_manifest import MANIFEST, REQUIRED, verify_manifest, write_manifest
from update_handshake import acknowledge_ready


@pytest.fixture
def package(tmp_path):
    for relative in REQUIRED | {'app/_internal/qt/plugins/platforms/qwindows.dll', 'app/_internal/icons/icon.png'}:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'new program payload')
    for relative in ['data/config.json', 'ocr/model.bin', 'translators/model.bin', 'unins000.dat']:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'user data')
    write_manifest(tmp_path, '1.7.1')
    return tmp_path


def test_manifest_covers_all_modules_and_excludes_user_data(package):
    assert verify_manifest(package, '1.7.1') == 8
    (package / 'data/config.json').write_bytes(b'edited settings')
    assert verify_manifest(package, '1.7.1') == 8


@pytest.mark.parametrize('relative', sorted(REQUIRED | {'app/_internal/qt/plugins/platforms/qwindows.dll', 'app/_internal/icons/icon.png'}))
@pytest.mark.parametrize('damage', ['missing', 'changed'])
def test_each_missing_or_stale_module_fails_verification(package, relative, damage):
    path = package / relative
    if damage == 'missing':
        path.unlink()
    else:
        path.write_bytes(b'old version')
    with pytest.raises(ValueError, match='Missing or damaged'):
        verify_manifest(package, '1.7.1')


def test_unlisted_old_module_is_not_accepted(package):
    (package / 'app/legacy_ocr.py').write_bytes(b'old module')
    with pytest.raises(ValueError, match='Unexpected program files'):
        verify_manifest(package, '1.7.1')


def test_legacy_updater_cannot_get_ack_for_incomplete_package(package, tmp_path):
    (package / 'app/_internal/base_library.zip').unlink()
    ack = tmp_path / 'data/ready.txt'
    assert not acknowledge_ready([f'--update-ack={ack}'], '1.7.1', package)
    assert not ack.exists()


def test_mismatched_manifest_version_is_rejected(package):
    with pytest.raises(ValueError, match='version'):
        verify_manifest(package, '1.7.2')


@pytest.mark.parametrize('relative', ['../outside', '/absolute', 'C:/outside', 'data/config.json', 'app/../other'])
def test_manifest_cannot_address_nonprogram_paths(package, relative):
    with (package / MANIFEST).open('a', encoding='utf-8') as output:
        output.write('0' * 64 + ' *' + relative + '\n')
    with pytest.raises(ValueError, match='Invalid program manifest path'):
        verify_manifest(package, '1.7.1')
