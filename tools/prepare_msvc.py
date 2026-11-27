"""Extract pinned Microsoft runtime files without executing its installer."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from component_store import file_digest
from component_catalog import safe_relative


def prepare(output, runtime, recipe):
    import requests
    source = output / 'msvc-source.exe'
    if not source.exists():
        with requests.get(recipe['url'], stream=True, timeout=120) as response:
            response.raise_for_status()
            with source.open('wb') as target:
                for block in response.iter_content(1024 * 1024):
                    if target.tell() + len(block) > recipe['size']:
                        raise RuntimeError('Microsoft runtime source exceeds pinned size')
                    target.write(block)
    if source.stat().st_size != recipe['size'] or file_digest(source) != recipe['sha256']:
        raise RuntimeError('Microsoft runtime source checksum mismatch')
    # Burn's attached CAB is a fixed slice of these exact, already verified
    # bytes. expand.exe reads CAB data only; it never runs EXE/MSI installers.
    data = source.read_bytes()
    offset, size = recipe['container_offset'], recipe['container_size']
    if offset < 0 or size < 36 or offset + size > len(data) or data[offset:offset+4] != b'MSCF':
        raise RuntimeError('Invalid Microsoft CAB description')
    container = output / 'msvc-attached.cab'
    container.write_bytes(data[offset:offset+size])
    expand = Path(os.environ['SystemRoot']) / 'System32/expand.exe'
    cabinets, files = output / 'msvc-cabinets', output / 'msvc-files'
    cabinets.mkdir()
    files.mkdir()
    subprocess.run([str(expand), '-F:' + safe_relative(recipe['cabinet']), str(container),
                    str(cabinets)], check=True, stdout=subprocess.DEVNULL)
    cabinet = cabinets / recipe['cabinet']
    if file_digest(cabinet) != recipe['cabinet_sha256']:
        raise RuntimeError('Microsoft inner CAB checksum mismatch')
    subprocess.run([str(expand), '-F:*', str(cabinet), str(files)],
                   check=True, stdout=subprocess.DEVNULL)
    for name, digest in recipe['files'].items():
        safe_relative(name)
        source_file = files / (name + '_amd64')
        if file_digest(source_file) != digest:
            raise RuntimeError('Microsoft DLL checksum mismatch: ' + name)
        shutil.copy2(source_file, runtime / name)
    (runtime / 'MICROSOFT-RUNTIME.json').write_text(json.dumps(recipe, indent=2), encoding='utf-8')
