# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules


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
    upx=True,
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
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    worker_exe,
    ocr_worker_exe,
    a.binaries,
    a.datas,
    worker_a.binaries,
    worker_a.datas,
    ocr_worker_a.binaries,
    ocr_worker_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ClicknTranslate',
)
