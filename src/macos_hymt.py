"""Verified native llama.cpp packages for the in-app Hy-MT installer."""
import os
import platform
import subprocess
import tarfile

import platform_support


RUNTIME_SHA256 = {
    'arm64': '7c48ae58b9b63853cff08b8c64d54a226e49481b1f0e6b6869b3ba447731063d',
    'x86_64': '9cce93d4640a0cad7541af89ecd8c510f4df4c5fb2d1b96e862510ec0f214ce6',
}


def runtime_plan():
    version = platform.mac_ver()[0]
    if version and int(version.split('.')[0]) < 14:
        raise RuntimeError('Hy-MT requires macOS 14 or newer. Update macOS before installing Hy-MT.')
    machine = platform.machine().lower()
    if machine not in RUNTIME_SHA256:
        raise RuntimeError(f'Unsupported Mac architecture for Hy-MT: {machine}')
    arch = 'arm64' if machine == 'arm64' else 'x64'
    name = f'llama-b9048-bin-macos-{arch}.tar.gz'
    return {'name': name, 'sha256': RUNTIME_SHA256[machine],
            'url': f'https://github.com/ggml-org/llama.cpp/releases/download/b9048/{name}'}


def extract_runtime(archive_path, destination):
    # data permits internal dylib symlinks and executable mode bits, but rejects
    # path traversal, device nodes and links escaping the destination directory.
    with tarfile.open(archive_path, 'r:gz') as archive:
        archive.extractall(destination, filter='data')


def validate_runner(runner):
    if not runner or not os.access(runner, os.X_OK):
        raise RuntimeError('The installed Hy-MT runner is not executable.')
    result = subprocess.run([runner, '--version'], cwd=os.path.dirname(runner),
                            env=platform_support.system_subprocess_env(),
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Hy-MT could not start:\n' + (result.stderr or result.stdout)[-2000:])
