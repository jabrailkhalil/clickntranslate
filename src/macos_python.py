"""Temporary native Python/pip for optional OCR packages, without Homebrew."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import platform_support
from macos_tesseract import MICROMAMBA_VERSION, MICROMAMBA_SHA256, _run_install


def prepare_pip_command(temp_dir, engine_name, download, check_cancel, progress=None):
    """The caller owns temp_dir and removes it after pip has finished."""
    if not platform_support.IS_MAC:
        raise RuntimeError('The private Mac Python bootstrap requires macOS.')
    machine = platform.machine().lower()
    architecture = {'arm64': 'osx-arm64', 'x86_64': 'osx-64'}.get(machine)
    if not architecture:
        raise RuntimeError(f'Unsupported Mac architecture for {engine_name}: {machine}')
    required = f'{sys.version_info.major}.{sys.version_info.minor}'
    check_cancel()
    stage = Path(temp_dir) / 'python-bootstrap'
    stage.mkdir(parents=True, exist_ok=False)
    manager = stage / 'micromamba'
    url = (f'https://github.com/mamba-org/micromamba-releases/releases/download/'
           f'{MICROMAMBA_VERSION}/micromamba-{architecture}')
    def report(done, total):
        if progress:
            progress(1 + int(8 * done / total) if total else 1, bool(total))
    download(url, str(manager), progress_callback=report)
    check_cancel()
    if hashlib.sha256(manager.read_bytes()).hexdigest() != MICROMAMBA_SHA256[architecture]:
        raise RuntimeError('Mac Python installer SHA-256 verification failed.')
    manager.chmod(0o700)
    env = platform_support.system_subprocess_env()
    for key in list(env):
        if key.startswith(('CONDA_', 'MAMBA_')) or key in ('PYTHONHOME', 'PYTHONPATH'):
            env.pop(key)
    env.update({'MAMBA_ROOT_PREFIX': str(stage / 'mamba'), 'MAMBA_NO_BANNER': '1'})
    runtime = stage / 'runtime'
    if progress:
        progress(10, False)
    _run_install([
        str(manager), '--no-rc', 'create', '--yes', '--prefix', str(runtime),
        '--root-prefix', str(stage / 'mamba'), '--platform', architecture,
        '--override-channels', '--channel', 'https://conda.anaconda.org/conda-forge',
        f'python={required}', 'pip',
    ], env, stage / 'install.log', check_cancel, engine_name=engine_name)
    executable = runtime / 'bin/python'
    code = ('import json,platform,sys,pip; '
            'print(json.dumps({"version":"%d.%d" % sys.version_info[:2],'
            '"architecture":platform.machine()}))')
    result = subprocess.run([str(executable), '-I', '-c', code], env=env,
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(f'Private Python could not load pip:\n{result.stderr[-2000:]}')
    info = json.loads(result.stdout)
    if info != {'version': required, 'architecture': machine}:
        raise RuntimeError(f'Private Python does not match this app: {info}')
    check_cancel()
    if progress:
        progress(12, True)
    return [str(executable), '-I', '-m', 'pip']
