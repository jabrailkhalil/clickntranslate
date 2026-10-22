"""Asset routing, hostile archives and the actual detached update transaction."""
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from unittest import mock
import pytest
import posix_update as update


def asset(name):
    return dict(name=name, browser_download_url='https://example.test/' + name)


@pytest.mark.parametrize('kind,arch,expected', [
    ('macos', 'arm64', 'macos-arm64.zip'), ('macos', 'x86_64', 'macos-x86_64.zip'),
    ('appimage', 'AMD64', 'linux-x86_64.AppImage'),
    ('appimage', 'aarch64', 'linux-aarch64.AppImage'),
    ('linux-dir', 'x86_64', 'linux-x86_64.tar.gz'),
])
def test_asset_is_exact_for_platform_format_and_architecture(kind, arch, expected):
    assets = [asset('Click-n-Translate-9.0-' + suffix) for suffix in (
        'macos-arm64.zip', 'macos-x86_64.zip', 'linux-x86_64.AppImage',
        'linux-aarch64.AppImage', 'linux-x86_64.tar.gz', 'windows-x64.zip')]
    assert update.pick_asset(assets, kind, arch)['name'].endswith(expected)
    assert update.pick_asset(assets, kind, 'riscv64') is None


@pytest.mark.parametrize('name', ['../outside', '/tmp/outside', 'ok/../../outside'])
def test_mac_zip_rejects_paths_before_ditto_runs(tmp_path, name):
    archive = tmp_path / 'app.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr(name, 'unsafe')
    with pytest.raises(ValueError):
        update._validate_zip(archive)


def test_mac_zip_rejects_external_symlinks_but_accepts_internal_frameworks(tmp_path):
    for link, allowed in (('../../../../escape', False), ('Versions/Current/QtCore', True)):
        archive = tmp_path / 'app.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            entry = zipfile.ZipInfo('App.app/Contents/Frameworks/QtCore.framework/QtCore')
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            output.writestr(entry, link)
        if allowed:
            update._validate_zip(archive)
        else:
            with pytest.raises(ValueError):
                update._validate_zip(archive)


def test_tar_symlink_cannot_overwrite_a_file_outside_staging(tmp_path):
    archive = tmp_path / 'linux.tar.gz'
    with tarfile.open(archive, 'w:gz') as output:
        link = tarfile.TarInfo('clickntranslate/escape')
        link.type = tarfile.SYMTYPE
        link.linkname = '../../victim'
        output.addfile(link)
        entry = tarfile.TarInfo('clickntranslate/escape/file')
        entry.size = 3
        output.addfile(entry, io.BytesIO(b'bad'))
    with pytest.raises((ValueError, tarfile.FilterError)):
        update._extract_linux(archive, tmp_path / 'unpack')
    assert not (tmp_path / 'victim').exists()


def test_mac_symlink_chain_cannot_escape_bundle(tmp_path):
    archive = tmp_path / 'app.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        for name, target in (('App.app/B', '.'), ('App.app/A', 'B/../outside')):
            entry = zipfile.ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            output.writestr(entry, target)
    with pytest.raises(ValueError):
        update._validate_zip(archive)


def test_failed_preparation_leaves_installed_program_unchanged(tmp_path):
    image = tmp_path / 'app.AppImage'
    image.write_bytes(b'original')
    package = tmp_path / 'download.AppImage'
    package.write_bytes(b'not an AppImage')
    with pytest.raises(ValueError):
        update.prepare(package, '9.0.0', ('appimage', image))
    assert image.read_bytes() == b'original'
    assert not list(tmp_path.glob('.cnt-stage-*'))


def _shell():
    if sys.platform != 'win32':
        return '/bin/sh'
    git = shutil.which('git')
    if git:
        candidate = Path(git).parents[1] / 'usr/bin/sh.exe'
        if candidate.is_file():
            return str(candidate)
    pytest.skip('A POSIX shell is required for the real update transaction')


@pytest.mark.parametrize('confirm', [True, False, 'crash'])
def test_real_runner_updates_or_rolls_back_and_preserves_user_data(tmp_path, confirm):
    shell = _shell()
    # Use spaces and apostrophes to exercise the actual shell argument boundary.
    current = tmp_path / "my app's folder"
    stage = tmp_path / '.cnt-stage-test'
    payload = stage / 'payload'
    current.mkdir()
    (current / "personal notes.txt").write_text('personal file')
    (current / '.private').write_text('hidden file')
    payload.mkdir(parents=True)
    for item in ('data', 'ocr', 'translators'):
        (current / item).mkdir()
        (current / item / 'marker').write_text('keep me')
    old = current / 'clickntranslate'
    old.write_text('#!/bin/sh\nprintf restored > "$0.restored"\n', newline='\n')
    old.chmod(0o755)
    new = payload / 'clickntranslate'
    # The executable confirms GUI-ready through exactly the production argument.
    script = '#!/bin/sh\n'
    if confirm:
        script += 'for arg in "$@"; do case "$arg" in --update-ack=*) printf 9.0.0 > "${arg#*=}";; esac; done\n'
        script += 'sleep 1\nexit 1\n' if confirm == 'crash' else 'sleep 15\n'
    else:
        script += 'exit 1\n'
    new.write_text(script, newline='\n')
    new.chmod(0o755)
    runner = stage / 'apply.sh'
    runner.write_text(update.RUNNER, newline='\n')
    result = tmp_path / 'result.txt'
    args = [shell, str(runner), str(current), str(payload), str(stage), 'clickntranslate',
            '9.0.0', '2147483647', 'linux-dir', str(result)]
    # MSYS converts Windows absolute positional arguments for POSIX commands.
    if sys.platform == 'win32':
        args = [args[0], *[a.replace('\\', '/') for a in args[1:]]]
    env = os.environ.copy()
    if sys.platform == 'win32':
        # The bundled Git runtime has coreutils but no sleep. Supply a tiny
        # test-only sleep command; production runs system /bin utilities.
        utility = tmp_path / 'test-utils'
        utility.mkdir()
        (utility / 'sleep').write_text('#!/bin/sh\n"' + sys.executable.replace('\\', '/') +
            '" -c "import sys,time;time.sleep(float(sys.argv[1]))" "$1"\n', newline='\n')
        env['PATH'] = str(utility) + os.pathsep + str(Path(shell).parent) + os.pathsep + env['PATH']
    completed = subprocess.run(args, capture_output=True, text=True, timeout=30, env=env)
    assert completed.returncode == (0 if confirm is True else 1), completed.stderr
    for item in ('data', 'ocr', 'translators'):
        assert (current / item / 'marker').read_text() == 'keep me'
    assert (current / "personal notes.txt").read_text() == 'personal file'
    assert (current / '.private').read_text() == 'hidden file'
    if confirm is True:
        assert old.read_text() == script
        assert not result.exists()
        assert not stage.exists()
    else:
        assert 'restored' in result.read_text()
        assert 'printf restored' in old.read_text()


def test_no_replacement_for_source_or_distro_binary(tmp_path):
    with mock.patch.object(sys, 'frozen', False, create=True):
        assert update.update_target('darwin') is None
    with mock.patch.object(sys, 'frozen', True, create=True), \
         mock.patch.object(sys, 'executable', '/usr/bin/clickntranslate'), \
         mock.patch('platform_support.appimage_path', return_value=''):
        assert update.update_target('linux') is None
