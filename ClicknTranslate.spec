# -*- mode: python ; coding: utf-8 -*-
import re as _re
import sys as _sys

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules


# The optional OCR engines are pip-installed at runtime into a private folder and
# then imported by the frozen OcrWorker, so their wheels must match this build's
# Python ABI.  settings_window pins that dependency set (and ships a matching
# embedded interpreter as a fallback), which means the build interpreter has to
# be the same series as EASYOCR_PYTHON_VERSION.
#
# Building 1.5.4 on 3.11 instead of 3.12 shipped an app that asked pip for
# packages requiring >= 3.12, so EasyOCR and RapidOCR installs failed outright
# with "Could not find a version that satisfies the requirement scipy==1.18.0".
# Fail the build instead of shipping that again.
_settings_source = open('settings_window.py', encoding='utf-8').read()
_engine_python = _re.search(
    r'EASYOCR_PYTHON_VERSION\s*=\s*"(\d+)\.(\d+)\.\d+"', _settings_source
)
if _engine_python:
    _required = (int(_engine_python.group(1)), int(_engine_python.group(2)))
    if _sys.version_info[:2] != _required:
        raise SystemExit(
            'Build Python %d.%d does not match EASYOCR_PYTHON_VERSION %d.%d. '
            'The runtime OCR engine wheels would not be importable by the frozen '
            'workers. Build with Python %d.%d.'
            % (_sys.version_info[0], _sys.version_info[1], _required[0], _required[1],
               _required[0], _required[1])
        )


gui_datas = [('icons', 'icons')]
gui_binaries = []
gui_hiddenimports = [
    'winrt.windows.media.ocr',
    'winrt.windows.globalization',
    'winrt.windows.graphics.imaging',
    'winrt.windows.graphics.directx',
    'winrt.windows.graphics.directx.direct3d11',
    'winrt.windows.storage.streams',
    'winrt.windows.storage',
    'winrt.windows.foundation',
    'winrt.windows.foundation.collections',
    'winrt.windows.system',
    'winrt._winrt',
    'pypdf',
]

# Preserve the upstream OCR/GUI package collection while keeping Argos and the
# native neural OCR runtimes out of the Qt process.
for package_name in (
    'pyperclip',
    'PyQt5',
    'PIL',
    'requests',
    'pytesseract',
    'psutil',
    'numpy',
    'winrt',
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    gui_datas += package_datas
    gui_binaries += package_binaries
    gui_hiddenimports += package_hiddenimports
gui_hiddenimports += collect_submodules('winrt')

argos_hiddenimports = [
    'argostranslate.package',
    'argostranslate.translate',
    'filelock',
]

native_sbd_excludes = [
    'torch',
    'stanza',
    'minisbd',
    'onnxruntime',
    'spacy',
    'thinc',
]

optional_ocr_excludes = [
    'easyocr',
    'rapidocr',
    'rapidocr_onnxruntime',
    'torchvision',
    'skimage',
]

common_excludes = [
    'tensorflow',
    'keras',
    'scipy',
    'matplotlib',
    'pandas',
    'sklearn',
    'cv2',
    'tkinter',
    '_tkinter',
    'pytest',
    'IPython',
    'jupyter',
]

def _stdlib_hiddenimports():
    """The whole standard library, for the OCR worker only.

    EasyOCR and torch are installed at runtime, so PyInstaller never sees them
    and bundles only what our own code imports. torch then reaches for whatever
    it likes — `pickletools` from its serializer, `timeit` from its profiler —
    and each missing name is a fresh "installed but could not be imported"
    failure after a 1.3 GB download. Naming them one per rebuild does not
    converge; carrying the stdlib does, for a few megabytes in a worker that
    already ships an ONNX runtime.
    """
    import sys as _stdlib_sys

    names = sorted(getattr(_stdlib_sys, 'stdlib_module_names', ()))
    # Skipped on purpose: GUI toolkits the worker must never load (and which the
    # excludes below would fight over), plus the test and packaging trees.
    unwanted = {
        'antigravity', 'this', 'idlelib', 'tkinter', 'turtle', 'turtledemo',
        'lib2to3', 'test', 'ensurepip', 'venv', 'distutils', 'pydoc_data',
    }
    wanted = [name for name in names if not name.startswith('_') and name not in unwanted]

    # Top-level names are not enough: torch imports `unittest.mock`, and a
    # package's submodules are separate modules to PyInstaller. Walk each one.
    collected = set(wanted)
    for name in wanted:
        try:
            collected.update(collect_submodules(name))
        except Exception:
            # A package that cannot even be imported on this machine (curses
            # without a terminal, dbm without a backend) has nothing to give.
            continue
    return sorted(collected)


# RapidOCR is bundled only into the isolated worker. This makes it available on
# first launch without requiring a matching system Python, while keeping the Qt
# GUI startup path free of ONNX/OpenCV imports. EasyOCR remains an optional
# runtime because its torch payload is substantially larger.
ocr_worker_datas = collect_data_files(
    'rapidocr_onnxruntime',
    includes=['**/*.onnx', '**/*.yaml', '**/*.yml', '**/*.json', '**/*.txt'],
)
ocr_worker_binaries = []
ocr_worker_hiddenimports = [
    'timeit',
    'pickletools',
    'uuid',
    'unittest.mock',
    'concurrent.futures',
    'multiprocessing.shared_memory',
    'multiprocessing.resource_tracker',
    'html.parser',
    'http.client',
    'email.message',
    'email.parser',
    'importlib.metadata',
    'pydoc',
    'doctest',
    'sqlite3',
    'modulefinder',
    'cProfile',
    'profile',
    'pstats',
    'configparser',
]
ocr_worker_hiddenimports += collect_submodules('rapidocr_onnxruntime')
ocr_worker_hiddenimports += [
    'PIL',
    'numpy',
    'rapidocr_onnxruntime',
    'onnxruntime',
    'cv2',
    'pyclipper',
    'shapely',
    'yaml',
    'tqdm',
    'six',
]
ocr_worker_hiddenimports += collect_submodules('ctypes')
ocr_worker_hiddenimports += _stdlib_hiddenimports()


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=gui_binaries,
    datas=gui_datas,
    hiddenimports=gui_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Argos runs in its own non-Qt executable; keep its Python runtime out
        # of the GUI archive so CTranslate2 cannot initialize inside Qt.
        'argostranslate',
        'ctranslate2',
        'sentencepiece',
        'sacremoses',
        'filelock',
        *native_sbd_excludes,
        *optional_ocr_excludes,
        *common_excludes,
    ],
    noarchive=False,
    optimize=0,
)

worker_a = Analysis(
    ['argos_worker.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=argos_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # This process deliberately has no Qt/WinRT runtime hooks.
        'PyQt5',
        'winrt',
        *native_sbd_excludes,
        *optional_ocr_excludes,
        *common_excludes,
    ],
    noarchive=False,
    optimize=0,
)

ocr_worker_a = Analysis(
    ['ocr_worker.py'],
    pathex=[],
    binaries=ocr_worker_binaries,
    datas=ocr_worker_datas,
    hiddenimports=ocr_worker_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # EasyOCR is loaded from the portable engine directory. RapidOCR and
        # its native dependencies are collected above for this worker only.
        'PyQt5',
        'winrt',
        'argostranslate',
        'ctranslate2',
        'sentencepiece',
        'sacremoses',
        'filelock',
        'torch',
        'stanza',
        'minisbd',
        'spacy',
        'thinc',
        'easyocr',
        'torchvision',
        'skimage',
        'tensorflow',
        'keras',
        'scipy',
        'matplotlib',
        'pandas',
        'sklearn',
        'tkinter',
        '_tkinter',
        'pytest',
        'IPython',
        'jupyter',
    ],
    noarchive=False,
    optimize=0,
)

import os as _os


# PyInstaller resolves DLL dependencies with the Windows search order, which
# includes PATH.  Any tool on the build machine's PATH that ships its own Visual
# C++ runtime therefore wins over the system one.  On one build machine an old
# AdoptOpenJDK on PATH supplied MSVCP140.dll 14.27 while MSVCP140_1.dll, which it
# does not ship, still came from System32 at 14.51.  MSVCP140_1.dll is an
# extension of MSVCP140.dll and the two must come from the same redistributable,
# so the mismatch made ArgosWorker.exe die instantly with an access violation
# (0xC0000005) inside MSVCP140.dll before Python could report anything.
#
# Pin the whole runtime to the System32 copies so the bundle is always a single
# consistent set, whatever happens to be on PATH.
_VCRUNTIME_DLLS = {
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'vcruntime140.dll',
    'vcruntime140_1.dll',
    'concrt140.dll',
}
_SYSTEM32 = _os.path.join(_os.environ.get('SystemRoot', r'C:\Windows'), 'System32')


def _pin_system_vcruntime(binaries):
    pinned = []
    for entry in binaries:
        destination, source = entry[0], entry[1]
        base = _os.path.basename(destination)
        if base.lower() in _VCRUNTIME_DLLS:
            system_copy = _os.path.join(_SYSTEM32, base)
            if _os.path.isfile(system_copy):
                entry = (destination, system_copy) + tuple(entry[2:])
        pinned.append(entry)
    return pinned


def _assert_consistent_vcruntime(*binary_lists):
    """Fail the build rather than ship a runtime mix that crashes at startup."""
    try:
        from PyInstaller.utils.win32.versioninfo import read_version_info_from_executable
    except Exception:
        return
    versions = {}
    for binaries in binary_lists:
        for entry in binaries:
            base = _os.path.basename(entry[0])
            if base.lower() not in _VCRUNTIME_DLLS:
                continue
            try:
                info = read_version_info_from_executable(entry[1])
                fixed = getattr(info, 'ffi', None)
                version = (fixed.fileVersionMS, fixed.fileVersionLS) if fixed else None
            except Exception:
                continue
            if version is not None:
                versions.setdefault(version, set()).add(base)
    if len(versions) > 1:
        raise SystemExit(
            'Inconsistent Visual C++ runtime DLLs collected: %s. '
            'They must all come from the same redistributable.' % versions
        )


a.binaries = _pin_system_vcruntime(a.binaries)
worker_a.binaries = _pin_system_vcruntime(worker_a.binaries)
ocr_worker_a.binaries = _pin_system_vcruntime(ocr_worker_a.binaries)
_assert_consistent_vcruntime(a.binaries, worker_a.binaries, ocr_worker_a.binaries)

pyz = PYZ(a.pure)
worker_pyz = PYZ(worker_a.pure)
ocr_worker_pyz = PYZ(ocr_worker_a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ClicknTranslate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # Avoid executable packers in public builds. Packed unsigned PyInstaller
    # stubs receive substantially more heuristic antivirus detections.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icons\\icon.ico'],
    manifest='installer\\windows\\ClicknTranslate.exe.manifest',
)

worker_exe = EXE(
    worker_pyz,
    worker_a.scripts,
    [],
    exclude_binaries=True,
    name='ArgosWorker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='.',
)

ocr_worker_exe = EXE(
    ocr_worker_pyz,
    ocr_worker_a.scripts,
    [],
    exclude_binaries=True,
    name='OcrWorker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='.',
)

worker_collection = [
    ('_internal/ArgosWorker.exe', worker_exe.name, 'EXECUTABLE'),
    *worker_exe.dependencies,
]

ocr_worker_collection = [
    ('_internal/OcrWorker.exe', ocr_worker_exe.name, 'EXECUTABLE'),
    *ocr_worker_exe.dependencies,
]

coll = COLLECT(
    exe,
    worker_collection,
    ocr_worker_collection,
    a.binaries,
    a.datas,
    worker_a.binaries,
    worker_a.datas,
    ocr_worker_a.binaries,
    ocr_worker_a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ClicknTranslate',
)


# One build produced a GUI executable whose embedded PYZ had its first mebibyte
# overwritten with zeros. Every standalone artifact on disk was intact — the
# PYZ file, the PKG archive — so the damage happened while the archive was
# being appended to the executable, and PyInstaller still exited 0. The app
# then died at startup with "Failed to setup PYZ archive reader!".
#
# A packaging failure that survives a green build must not reach a user, so the
# build now reads its own output back and refuses to finish if an executable
# cannot serve its archive.
def _verify_frozen_executables(dist_root):
    from PyInstaller.archive.readers import CArchiveReader

    executables = [
        _os.path.join(dist_root, 'ClicknTranslate.exe'),
        _os.path.join(dist_root, '_internal', 'ArgosWorker.exe'),
        _os.path.join(dist_root, '_internal', 'OcrWorker.exe'),
    ]

    problems = []
    for path in executables:
        if not _os.path.isfile(path):
            problems.append(f'{_os.path.basename(path)}: missing from the build')
            continue
        try:
            reader = CArchiveReader(path)
        except Exception as exc:
            problems.append(f'{_os.path.basename(path)}: unreadable archive ({exc})')
            continue

        entries = [name for name in reader.toc if name.endswith('.pyz')]
        if not entries:
            problems.append(f'{_os.path.basename(path)}: no PYZ archive embedded')
            continue

        for entry in entries:
            try:
                payload = reader.extract(entry)
                payload = payload[1] if isinstance(payload, tuple) else payload
            except Exception as exc:
                problems.append(f'{_os.path.basename(path)}: cannot extract {entry} ({exc})')
                continue
            # The reader validates the magic itself, but check explicitly so a
            # zero-filled payload is named for what it is.
            if not payload.startswith(b'PYZ\0'):
                zeros = len(payload) - len(payload.lstrip(b'\0'))
                problems.append(
                    f'{_os.path.basename(path)}: {entry} is corrupt — '
                    f'{zeros:,} leading zero bytes of {len(payload):,}'
                )

    if problems:
        raise SystemExit(
            'Build produced unusable executables:\n  ' + '\n  '.join(problems)
            + '\n\nThe archive is appended to the executable after it is written, so this is '
              'usually another process touching the file: a running copy of the app, an '
              'interrupted previous build, or an on-access virus scanner. Close any running '
              'instance and rebuild with --clean.'
        )
    print(f'Verified embedded archives in {len(executables)} executables.')


_verify_frozen_executables(_os.path.join(DISTPATH, 'ClicknTranslate'))
