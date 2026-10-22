"""Prepare verified macOS/Linux updates and hand off an atomic replacement.

The detached runner uses the system shell, never a Python/runtime inside the
bundle being replaced. Downloads and checksum verification happen in Settings.
"""
import os
from pathlib import Path, PurePosixPath
import platform
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile


def architecture(value=None):
    value = (value or platform.machine()).lower()
    if value in ('aarch64', 'arm64'):
        return 'arm64'
    if value in ('amd64', 'x86_64', 'x64'):
        return 'x86_64'
    return value


def update_target(system=None):
    """Return an owned portable install; distro/package-manager installs defer."""
    import platform_support
    system = system or sys.platform
    if not getattr(sys, 'frozen', False):
        return None
    if system == 'darwin':
        bundle = next((p for p in Path(sys.executable).parents if p.suffix == '.app'), None)
        if bundle and '/AppTranslocation/' not in str(bundle) and not str(bundle).startswith('/Volumes/'):
            return ('macos', bundle.resolve())
    elif system.startswith('linux'):
        image = platform_support.appimage_path()
        if image:
            return ('appimage', Path(image).resolve())
        binary = Path(sys.executable).resolve()
        # Only our self-contained tarball layout may be replaced. Never replace
        # /usr/bin or a directory owned by a distro package.
        if binary.name == 'clickntranslate' and (binary.parent / '_internal').is_dir():
            marker = binary.parent / '.cnt-portable-install'
            try:
                owned = marker.is_file() and marker.read_text(encoding='utf-8').strip() == platform_support.APP_ID
            except (OSError, UnicodeError):
                owned = False
            if owned and not any(binary.is_relative_to(root) for root in (Path('/usr'), Path('/bin'), Path('/sbin'))):
                return ('linux-dir', binary.parent)
    return None


def pick_asset(assets, kind, machine=None):
    arch = architecture(machine)
    arch_tokens = ('arm64', 'aarch64') if arch == 'arm64' else ('x86_64', 'amd64', 'x64')
    if arch not in ('arm64', 'x86_64'):
        return None
    extension = {'macos': '.zip', 'appimage': '.appimage', 'linux-dir': '.tar.gz'}[kind]
    platform_token = 'macos' if kind == 'macos' else 'linux'
    candidates = []
    for asset in assets:
        name = str(asset.get('name') or '').lower()
        compact = re.sub(r'[-_]', '', name)
        if ('clickntranslate' in compact and platform_token in name and name.endswith(extension)
                and any(re.search(r'(?:^|[-_])' + re.escape(token) + r'(?:[-_.]|$)', name) for token in arch_tokens)
                and not any(word in name for word in ('debug', 'source', 'bootstrap'))
                and (asset.get('browser_download_url') or asset.get('url'))):
            candidates.append(asset)
    return sorted(candidates, key=lambda item: item['name'])[0] if candidates else None


def _safe_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or '\x00' in name:
        raise ValueError('Unsafe update archive path')
    return path


def _validate_zip(archive):
    total = 0
    links = {}
    members = []
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            path = _safe_member(entry.filename)
            members.append(path)
            total += entry.file_size
            if total > 12 * 1024**3:
                raise ValueError('Update archive is too large')
            if stat.S_ISLNK(entry.external_attr >> 16):
                link = source.read(entry).decode('utf-8')
                # PyInstaller bundles contain relative framework symlinks.
                # Resolve lexically and allow only links within the archive.
                resolved = os.path.normpath(str(path.parent / link)).replace('\\', '/')
                resolved_path = _safe_member(resolved)
                if path.parts[0].endswith('.app') and resolved_path.parts[0] != path.parts[0]:
                    raise ValueError('Update symlink escapes the application bundle')
                if PurePosixPath(link).is_absolute():
                    raise ValueError('Unsafe update archive symlink')
                links[str(path)] = link
    # Validate the complete link graph too: B -> '.' followed by A -> B/../x
    # can escape a bundle even when both targets look safe in isolation.
    for member in members:
        pending = list(member.parts)
        resolved = []
        expansions = 0
        while pending:
            part = pending.pop(0)
            if part == '.':
                continue
            if part == '..':
                if not resolved:
                    raise ValueError('Update symlink escapes staging')
                resolved.pop()
                continue
            resolved.append(part)
            target = links.get('/'.join(resolved))
            if target is not None:
                expansions += 1
                if expansions > 40:
                    raise ValueError('Cyclic update symlink')
                resolved.pop()
                pending = list(PurePosixPath(target).parts) + pending
        if member.parts[0].endswith('.app') and (not resolved or resolved[0] != member.parts[0]):
            raise ValueError('Update symlink escapes the application bundle')


def _extract_linux(archive, destination):
    with tarfile.open(archive, 'r:gz') as source:
        total = 0
        for entry in source.getmembers():
            _safe_member(entry.name)
            total += entry.size
            if total > 12 * 1024**3 or entry.isdev() or entry.isfifo():
                raise ValueError('Unsafe update archive entry')
            if entry.issym() or entry.islnk():
                link = PurePosixPath(entry.linkname)
                resolved = os.path.normpath(str(PurePosixPath(entry.name).parent / link))
                _safe_member(resolved)
                if link.is_absolute():
                    raise ValueError('Unsafe update archive symlink')
        # The data filter additionally rejects extraction through symlinks and
        # strips ownership/setuid metadata. Requires Python >= 3.12 in builds.
        source.extractall(destination, filter='data')


def _command(args, env):
    return subprocess.run(args, env=env, capture_output=True, text=True, check=True, timeout=180)


def _mac_identity(bundle, env):
    result = _command(['/usr/bin/codesign', '-d', '--verbose=4', str(bundle)], env)
    return dict(re.findall(r'^(Identifier|TeamIdentifier)=(.+)$', result.stderr, re.M))


def prepare(package, version, target=None):
    """Stage next to the target so replacement is an atomic same-volume rename."""
    import platform_support
    target = target or update_target()
    if target is None:
        raise RuntimeError('Install this build into a writable application folder before updating.')
    kind, current = target
    current = Path(current).resolve(strict=True)
    if kind == 'linux-dir' and (current == Path(current.anchor) or current == Path.home()
            or current in (Path.home() / name for name in ('Desktop', 'Documents', 'Downloads', 'Applications'))):
        raise ValueError('Use a dedicated application folder for this portable installation')
    if not current.parent.is_dir() or not os.access(current.parent, os.W_OK):
        raise PermissionError('The application folder is not writable. Move the app to a folder you own.')
    if not re.fullmatch(r'\d+(?:\.\d+){1,3}', version):
        raise ValueError('Invalid update version')
    stage = Path(tempfile.mkdtemp(prefix='.cnt-stage-', dir=current.parent))
    env = platform_support.system_subprocess_env()
    try:
        package = Path(package)
        if kind == 'macos':
            _validate_zip(package)
            _command(['/usr/bin/ditto', '-x', '-k', str(package), str(stage)], env)
            bundles = list(stage.glob('*.app'))
            if len(bundles) != 1:
                raise ValueError('The update must contain exactly one application bundle')
            payload = bundles[0]
            with (payload / 'Contents/Info.plist').open('rb') as stream:
                info = plistlib.load(stream)
            with (current / 'Contents/Info.plist').open('rb') as stream:
                old_info = plistlib.load(stream)
            if (info.get('CFBundleIdentifier') != old_info.get('CFBundleIdentifier')
                    or info.get('CFBundleShortVersionString') != version):
                raise ValueError('The update bundle identity or version does not match')
            executable = info.get('CFBundleExecutable', '')
            if not executable or '/' in executable or executable in ('.', '..'):
                raise ValueError('Invalid application executable')
            relative_executable = 'Contents/MacOS/' + executable
            _command(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(payload)], env)
            old_identity, identity = _mac_identity(current, env), _mac_identity(payload, env)
            team = old_identity.get('TeamIdentifier')
            if team and team != 'not set' and identity.get('TeamIdentifier') != team:
                raise ValueError('The update is signed by a different developer')
        elif kind == 'linux-dir':
            _extract_linux(package, stage)
            payload = stage / 'clickntranslate'
            relative_executable = 'clickntranslate'
            if not (payload / '_internal').is_dir():
                raise ValueError('The update is missing its runtime')
            marker = payload / '.cnt-portable-install'
            if not marker.is_file() or marker.read_text(encoding='utf-8').strip() != platform_support.APP_ID:
                raise ValueError('The update is missing its portable installation identity')
            if {item.name for item in payload.iterdir()} - {'clickntranslate', '_internal', '.cnt-portable-install'}:
                raise ValueError('The update archive includes unexpected files outside the runtime')
            if any((payload / item).exists() for item in ('data', 'ocr', 'translators')):
                raise ValueError('The update archive includes user data')
        elif kind == 'appimage':
            with package.open('rb') as stream:
                header = stream.read(12)
            if header[:4] != b'\x7fELF' or header[8:11] != b'AI\x02':
                raise ValueError('The download is not a valid AppImage')
            payload = stage / current.name
            shutil.copyfile(package, payload)
            payload.chmod(current.stat().st_mode | stat.S_IXUSR)
            relative_executable = ''
        else:
            raise ValueError('Unsupported update format')
        launch = payload / relative_executable if relative_executable else payload
        if not launch.is_file() or (kind != 'appimage' and not os.access(launch, os.X_OK)):
            raise ValueError('The update is missing its application executable')
        return dict(kind=kind, target=str(current), payload=str(payload), stage=str(stage),
                    executable=relative_executable, version=version)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


# Every filesystem operand is a positional argument and is always quoted.
# Never rewrite a running executable in place (in particular a signed .app).
RUNNER = r'''#!/bin/sh
set -eu
target=$1
payload=$2
stage=$3
relative=$4
version=$5
parent_pid=$6
kind=$7
result=$8
ack="$stage/ready"
backup="$stage/previous"
new_pid=
swapped=0
restore() {
    trap - EXIT HUP INT TERM
    if [ -n "$new_pid" ]; then
        kill "$new_pid" 2>/dev/null || true
        # Do not remove a bundle while its process can still execute it.
        count=0
        while kill -0 "$new_pid" 2>/dev/null && [ "$count" -lt 10 ]; do sleep 1; count=$((count + 1)); done
        if kill -0 "$new_pid" 2>/dev/null; then kill -KILL "$new_pid" 2>/dev/null || true; fi
        wait "$new_pid" 2>/dev/null || true
    fi
    if [ -e "$backup" ]; then
        if [ "$kind" = linux-dir ]; then
            for folder in "$target" "$payload"; do
              for entry in "$folder"/* "$folder"/.[!.]* "$folder"/..?*; do
                if [ ! -e "$entry" ] && [ ! -L "$entry" ]; then continue; fi
                item=${entry##*/}
                case "$item" in clickntranslate|_internal|.cnt-portable-install) continue;; esac
                if [ ! -e "$backup/$item" ] && [ ! -L "$backup/$item" ]; then mv "$entry" "$backup/$item"; fi
              done
            done
        fi
        if [ "$swapped" = 1 ]; then mv "$target" "$stage/failed"; fi
        mv "$backup" "$target"
        printf '%s\n' 'Update failed; the previous version was restored.' > "$result"
        launch=$target
        if [ -n "$relative" ]; then launch="$target/$relative"; fi
        "$launch" --show-after-update >> "$stage/recovery.log" 2>&1 &
    else
        printf '%s\n' 'Update preparation failed; the current version was kept.' > "$result"
    fi
    exit 1
}
# A timeout waiting for the original app must leave it completely untouched.
count=0
while kill -0 "$parent_pid" 2>/dev/null; do
    count=$((count + 1))
    if [ "$count" -gt 45 ]; then printf '%s\n' 'The application did not close; update cancelled.' > "$result"; exit 1; fi
    sleep 1
done
trap restore EXIT HUP INT TERM
mv "$target" "$backup"
if [ "$kind" = linux-dir ]; then
    # Keep every non-program item, including user files outside the usual data
    # folders. A name collision aborts rather than replacing a personal file.
    for entry in "$backup"/* "$backup"/.[!.]* "$backup"/..?*; do
        if [ ! -e "$entry" ] && [ ! -L "$entry" ]; then continue; fi
        item=${entry##*/}
        case "$item" in clickntranslate|_internal|.cnt-portable-install) continue;; esac
        if [ -e "$payload/$item" ] || [ -L "$payload/$item" ]; then exit 1; fi
        mv "$entry" "$payload/$item"
    done
fi
mv "$payload" "$target"
swapped=1
launch=$target
if [ -n "$relative" ]; then launch="$target/$relative"; fi
"$launch" --show-after-update "--update-ack=$ack" >> "$stage/launch.log" 2>&1 &
new_pid=$!
count=0
while [ "$count" -lt 90 ]; do
    if [ -f "$ack" ] && [ "$(cat "$ack")" = "$version" ]; then
        # A short-lived first frame must not discard the recovery copy.
        stable=0
        while [ "$stable" -lt 5 ]; do
            sleep 1
            kill -0 "$new_pid" 2>/dev/null || exit 1
            stable=$((stable + 1))
        done
        trap - EXIT HUP INT TERM
        # The original target is a verified file/app root received from prepare;
        # backup/stage were created privately under that exact parent.
        rm -rf "$backup"
        rm -f "$result"
        rm -rf "$stage"
        exit 0
    fi
    kill -0 "$new_pid" 2>/dev/null || exit 1
    sleep 1
    count=$((count + 1))
done
exit 1
'''


def launch(plan, result_path):
    import platform_support
    stage = Path(plan['stage'])
    runner = stage / 'apply.sh'
    runner.write_text(RUNNER, encoding='utf-8', newline='\n')
    env = platform_support.system_subprocess_env()
    for key in tuple(env):
        if key.startswith('_PYI_') or key in ('APPDIR', 'APPIMAGE', 'LD_LIBRARY_PATH_ORIG'):
            env.pop(key, None)
    env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    env['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
    # A new AppImage must not inherit the old one's mount or runtime flags.
    args = ['/bin/sh', str(runner), plan['target'], plan['payload'], plan['stage'],
            plan['executable'], plan['version'], str(os.getpid()), plan['kind'], str(result_path)]
    with (stage / 'updater.log').open('ab') as log:
        subprocess.Popen(args, cwd=stage.parent, env=env, stdin=subprocess.DEVNULL,
                         stdout=log, stderr=log, close_fds=True, start_new_session=True)
