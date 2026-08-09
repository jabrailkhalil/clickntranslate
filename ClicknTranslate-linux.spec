# -*- mode: python ; coding: utf-8 -*-
"""Linux build.

Mirrors ClicknTranslate.spec (one Qt GUI plus two non-Qt helper executables) with
the Windows-only pieces removed:

* no WinRT — Windows OCR does not exist here, Tesseract is the default engine,
* no Visual C++ runtime pinning,
* no icon/manifest arguments, which are PE concepts,
* helper executables have no .exe suffix.

The GUI archive still excludes ctranslate2 and the neural OCR runtimes: they load
native libraries that must not be initialized inside the Qt process.
"""

import os as _os
import sys as _sys

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules


if _sys.platform != 'linux':
    raise SystemExit('ClicknTranslate-linux.spec builds the Linux package; use ClicknTranslate.spec on Windows.')


def _xcb_platform_libraries():
    """The libraries Qt's xcb plugin links, resolved from the build machine.

    PyInstaller follows the dependencies of the executable, not of a plugin it
    merely copies, so `libqxcb.so` shipped with six unresolved sonames and the
    app died on start with "Could not load the Qt platform plugin xcb" on any
    machine that did not happen to have them. An AppImage is supposed to carry
    its own dependencies, so they are bundled rather than documented.
    """
    import subprocess

    required = (
        'libxcb-icccm.so.4',
        'libxcb-image.so.0',
        'libxcb-keysyms.so.1',
        'libxcb-render-util.so.0',
        'libxcb-shape.so.0',
        'libxcb-xinerama.so.0',
        'libxcb-util.so.1',
        'libxkbcommon-x11.so.0',
    )
    try:
        cache = subprocess.run(
            ['ldconfig', '-p'], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'Could not read the shared library cache: {error}')

    found = {}
    for line in cache.splitlines():
        entry = line.strip()
        if '=>' not in entry:
            continue
        soname, _, path = entry.partition('=>')
        soname = soname.split()[0].strip()
        path = path.strip()
        if soname in required and soname not in found and _os.path.exists(path):
            found[soname] = path

    missing = [name for name in required if name not in found]
    if missing:
        # Failing the build is the point: shipping without these produces an
        # AppImage that cannot open a window, and nothing else reports it.
        packages = 'libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 ' \
                   'libxcb-shape0 libxcb-xinerama0 libxcb-util1 libxkbcommon-x11-0'
        raise SystemExit(
            'The Qt xcb platform plugin needs libraries that are not installed on this '
            'build machine:\n  ' + '\n  '.join(missing) +
            f'\n\nInstall them and build again:\n  sudo apt-get install -y {packages}\n'
            '(tools/setup_linux_env.sh does this for you.)'
        )
    return [(path, '.') for path in found.values()]


gui_datas = [('icons', 'icons')]
gui_binaries = _xcb_platform_libraries()
gui_hiddenimports = ['pypdf']

for package_name in (
    'pyperclip',
    'PyQt5',
    'PIL',
    'requests',
    'pytesseract',
    'psutil',
    'numpy',
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    gui_datas += package_datas
    gui_binaries += package_binaries
    gui_hiddenimports += package_hiddenimports

argos_hiddenimports = [
    'argostranslate.package',
    'argostranslate.translate',
    'filelock',
]

# stanza pulls torch and minisbd pulls onnxruntime, both only for sentence
# splitting, which translater.py does itself.
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


# RapidOCR is bundled into the isolated worker when it is available in the build
# environment. Unlike the Windows build this is optional: distributions vary in
# what onnxruntime wheels they can install, and the app falls back to Tesseract.
try:
    ocr_worker_datas = collect_data_files(
        'rapidocr_onnxruntime',
        includes=['**/*.onnx', '**/*.yaml', '**/*.yml', '**/*.json', '**/*.txt'],
    )
    ocr_worker_hiddenimports = collect_submodules('rapidocr_onnxruntime') + [
        'rapidocr_onnxruntime',
        'onnxruntime',
        'cv2',
        'pyclipper',
        'shapely',
        'yaml',
        'tqdm',
        'six',
    ]
    _bundled_rapidocr = True
except Exception as _exc:  # pragma: no cover - depends on the build environment
    print(f'RapidOCR is not available in this build environment ({_exc}); '
          'the OCR worker will only serve engines installed at runtime.')
    ocr_worker_datas = []
    ocr_worker_hiddenimports = []
    _bundled_rapidocr = False

ocr_worker_binaries = []
ocr_worker_hiddenimports += _stdlib_hiddenimports()
ocr_worker_hiddenimports += [
    'PIL',
    'numpy',
    'importlib.metadata',
    'concurrent.futures',
]


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
        # Argos runs in its own non-Qt executable.
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
        'PyQt5',
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
        'PyQt5',
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
    ] + ([] if _bundled_rapidocr else ['rapidocr_onnxruntime', 'onnxruntime', 'cv2']),
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)
worker_pyz = PYZ(worker_a.pure)
ocr_worker_pyz = PYZ(ocr_worker_a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='clickntranslate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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

# The workers live in _internal next to the GUI, exactly as on Windows, so
# translater._argos_worker_path and ocr._native_ocr_worker_path find them.
worker_collection = [
    ('_internal/ArgosWorker', worker_exe.name, 'EXECUTABLE'),
    *worker_exe.dependencies,
]

ocr_worker_collection = [
    ('_internal/OcrWorker', ocr_worker_exe.name, 'EXECUTABLE'),
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
    name='clickntranslate',
)


# The archive is appended to each executable after it is written, and a Windows
# build once produced a GUI executable whose embedded PYZ began with a mebibyte
# of zeros while every artifact on disk was intact — PyInstaller still exited 0
# and the app died at startup. Read the output back rather than trusting the
# exit code. See the same check in ClicknTranslate.spec.
def _verify_frozen_executables(dist_root):
    from PyInstaller.archive.readers import CArchiveReader

    executables = [
        _os.path.join(dist_root, 'clickntranslate'),
        _os.path.join(dist_root, '_internal', 'ArgosWorker'),
        _os.path.join(dist_root, '_internal', 'OcrWorker'),
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
            if not payload.startswith(b'PYZ\0'):
                zeros = len(payload) - len(payload.lstrip(b'\0'))
                problems.append(
                    f'{_os.path.basename(path)}: {entry} is corrupt — '
                    f'{zeros:,} leading zero bytes of {len(payload):,}'
                )

    if problems:
        raise SystemExit(
            'Build produced unusable executables:\n  ' + '\n  '.join(problems)
            + '\n\nClose any running instance and rebuild with --clean.'
        )
    print(f'Verified embedded archives in {len(executables)} executables.')


_verify_frozen_executables(_os.path.join(DISTPATH, 'clickntranslate'))
