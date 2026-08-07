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


gui_datas = [('icons', 'icons')]
gui_binaries = []
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
