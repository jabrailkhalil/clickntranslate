"""Install native Tesseract in application data without a system package manager."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import time
import uuid

import platform_support


MICROMAMBA_VERSION = '2.9.0-0'
MICROMAMBA_SHA256 = {
    'osx-arm64': 'ec2a072f028e1a7cf20f3e2e74d5a8127cf5a5f27636375b5359811565f4e5be',
    'osx-64': '1e71054bb3ac9a076e21f7ec48acfef536f9b3f1408f371a942784bf5ef83d8a',
}


def managed_command(root):
    root = Path(root)
    try:
        runtime = json.loads((root / 'installation.json').read_text())['runtime']
        if not re.fullmatch(r'runtime-[0-9a-f]{32}', runtime):
            return ''
        command = root / runtime / 'bin/tesseract'
        if (command.resolve().is_relative_to(root.resolve())
                and command.is_file() and os.access(command, os.X_OK)):
            return str(command)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return ''


def _run_install(command, env, log_path, check_cancel, *, engine_name='Tesseract'):
    # A file avoids pipe backpressure while keeping cancellation responsive.
    with open(log_path, 'wb') as output:
        process = subprocess.Popen(command, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 1200
            while process.poll() is None:
                check_cancel()
                if time.monotonic() > deadline:
                    raise RuntimeError(f'{engine_name} installation timed out. Please retry.')
                time.sleep(0.15)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
    check_cancel()
    if process.returncode:
        detail = Path(log_path).read_text(errors='replace')[-3000:]
        raise RuntimeError(f'{engine_name} installation failed ({process.returncode}):\n{detail}')


def install(root, download, check_cancel, progress):
    """Publish a validated prefix atomically; retain the previous installation."""
    if not platform_support.IS_MAC:
        raise RuntimeError('This installer requires macOS.')
    architecture = {'arm64': 'osx-arm64', 'x86_64': 'osx-64'}.get(platform.machine().lower())
    if not architecture:
        raise RuntimeError('Unsupported Mac architecture for Tesseract.')
    root = Path(root).resolve()
    check_cancel()
    root.mkdir(parents=True, exist_ok=True)
    runtime = root / ('runtime-' + uuid.uuid4().hex)
    committed = False
    manifest_stage = root / ('.installation-' + uuid.uuid4().hex)
    try:
        with tempfile.TemporaryDirectory(prefix='clickntranslate-tesseract-') as temporary:
            stage = Path(temporary)
            manager = stage / 'micromamba'
            url = (f'https://github.com/mamba-org/micromamba-releases/releases/download/'
                   f'{MICROMAMBA_VERSION}/micromamba-{architecture}')
            progress('download', 1)
            download(url, str(manager), progress_callback=lambda done, total:
                     progress('download', 1 + int(14 * done / total) if total else 2))
            check_cancel()
            if hashlib.sha256(manager.read_bytes()).hexdigest() != MICROMAMBA_SHA256[architecture]:
                raise RuntimeError('Tesseract installer SHA-256 verification failed.')
            manager.chmod(0o700)
            env = platform_support.system_subprocess_env()
            for key in list(env):
                if key.startswith(('CONDA_', 'MAMBA_')) or key == 'TESSDATA_PREFIX':
                    env.pop(key)
            env.update({'MAMBA_ROOT_PREFIX': str(stage / 'mamba'), 'MAMBA_NO_BANNER': '1'})
            progress('install', 20)
            # Conda prefixes can contain absolute paths: create at the permanent
            # location, then publish only the small manifest after validation.
            _run_install([
                str(manager), '--no-rc', 'create', '--yes', '--prefix', str(runtime),
                '--root-prefix', str(stage / 'mamba'), '--platform', architecture,
                '--override-channels', '--channel', 'https://conda.anaconda.org/conda-forge',
                'tesseract=5.5.3',
            ], env, stage / 'install.log', check_cancel)
            progress('verify', 95)
            executable = runtime / 'bin/tesseract'
            result = subprocess.run([str(executable), '--version'], env=env,
                                    capture_output=True, text=True, timeout=20)
            if result.returncode or 'tesseract 5.' not in result.stdout.lower():
                raise RuntimeError('Installed Tesseract could not start:\n' + result.stderr[-2000:])
            check_cancel()
            manifest_stage.write_text(json.dumps({'runtime': runtime.name, 'architecture': architecture,
                                                   'version': '5.5.3'}) + '\n')
            os.replace(manifest_stage, root / 'installation.json')
            committed = True
            progress('done', 100)
            return str(executable)
    finally:
        manifest_stage.unlink(missing_ok=True)
        if not committed and runtime.exists():
            shutil.rmtree(runtime)
