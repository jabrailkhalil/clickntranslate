# -*- mode: python ; coding: utf-8 -*-
"""Native Mac bundle: Qt GUI and two isolated non-Qt inference helpers."""
import os
import platform
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

if sys.platform != 'darwin':
    raise SystemExit('Build this spec on macOS; cross-compilation is not supported.')

from app_version import APP_VERSION
from platform_support import APP_ID

architecture = platform.machine()
identity = os.environ.get('MACOS_CODESIGN_IDENTITY') or None
entitlements = 'packaging/macos/entitlements.plist' if identity else None
common_excludes = ['tkinter', 'pytest', 'IPython', 'jupyter', 'tensorflow', 'keras',
                   'matplotlib', 'pandas', 'sklearn', 'stanza', 'minisbd', 'spacy', 'thinc']
optional = ['easyocr', 'torch', 'torchvision', 'skimage']
native_bridges = ['Vision', 'Quartz', 'AppKit', 'Foundation', 'CoreFoundation', 'ApplicationServices', 'objc']
gui_hidden = ['pypdf']
for module in native_bridges:
    gui_hidden += collect_submodules(module)

gui = Analysis(['main.py'], pathex=[SPECPATH],
               datas=[('icons', 'icons')], binaries=[], hiddenimports=gui_hidden,
               excludes=[*common_excludes, *optional, 'argostranslate', 'ctranslate2',
                         'sentencepiece', 'onnxruntime', 'rapidocr_onnxruntime', 'cv2'],
               noarchive=False)
argos = Analysis(['argos_worker.py'], pathex=[SPECPATH], datas=[], binaries=[],
                 hiddenimports=['argostranslate.package', 'argostranslate.translate', 'filelock', 'sacremoses'],
                 excludes=[*common_excludes, *optional, *native_bridges, 'PyQt5',
                           'onnxruntime', 'rapidocr_onnxruntime', 'cv2'], noarchive=False)

# Optional OCR packages load at runtime; include stdlib submodules used by their
# wheels so an install doesn't fail later on e.g. unittest.mock or pickletools.
stdlib = set()
for module in sorted(sys.stdlib_module_names):
    if module.startswith('_') or module in {'antigravity', 'this', 'idlelib', 'tkinter',
                                           'turtle', 'turtledemo', 'test', 'ensurepip'}:
        continue
    stdlib.add(module)
    stdlib.update(collect_submodules(module, on_error='ignore'))
ocr_hidden = list(stdlib) + collect_submodules('rapidocr_onnxruntime') + collect_submodules('PIL') + [
    'onnxruntime', 'cv2', 'pyclipper', 'shapely', 'yaml', 'tqdm', 'six', 'numpy', 'PIL']
ocr = Analysis(['ocr_worker.py'], pathex=[SPECPATH], binaries=[],
               datas=collect_data_files('rapidocr_onnxruntime'), hiddenimports=ocr_hidden,
               excludes=[*common_excludes, *optional, *native_bridges, 'PyQt5',
                         'argostranslate', 'ctranslate2', 'sentencepiece'], noarchive=False)


def executable(analysis, name, console):
    return EXE(PYZ(analysis.pure), analysis.scripts, [], exclude_binaries=True,
               name=name, console=console, upx=False, strip=False,
               argv_emulation=False, target_arch=architecture,
               codesign_identity=identity, entitlements_file=entitlements)


gui_exe = executable(gui, 'ClicknTranslate', False)
argos_exe = executable(argos, 'ArgosWorker', True)
ocr_exe = executable(ocr, 'OcrWorker', True)
collection = COLLECT(gui_exe, argos_exe, ocr_exe,
                     gui.binaries, gui.datas, argos.binaries, argos.datas, ocr.binaries, ocr.datas,
                     name='ClicknTranslate-macos', upx=False, strip=False)
# BUNDLE relocates code to MacOS/Frameworks and resources to Resources, creating
# the necessary links. Do not move helpers after signing or mutate the bundle.
app = BUNDLE(collection, name='ClicknTranslate.app', icon='build/macos/icon.icns',
             bundle_identifier=APP_ID, codesign_identity=identity, entitlements_file=entitlements,
             info_plist={
                 # COLLECT sorts its executables and does not retain the GUI
                 # console flag. BUNDLE otherwise picks ArgosWorker and marks
                 # the whole application as background-only.
                 'CFBundleExecutable': 'ClicknTranslate',
                 'LSBackgroundOnly': False,
                 'CFBundleDisplayName': "Click’n’Translate",
                 'CFBundleShortVersionString': APP_VERSION,
                 'CFBundleVersion': APP_VERSION,
                 # ONNX Runtime's wheels are tagged macosx_13_0 but their
                 # Mach-O libraries actually require 13.4.
                 'LSMinimumSystemVersion': '13.4',
                 'NSHighResolutionCapable': True,
                 'NSSupportsAutomaticGraphicsSwitching': True,
                 'NSPrincipalClass': 'NSApplication',
                 'NSHumanReadableCopyright': 'Click’n’Translate contributors',
             })

# Verify all three appended Python archives, including the final bundle paths.
from PyInstaller.archive.readers import CArchiveReader
for name in ('ClicknTranslate', 'ArgosWorker', 'OcrWorker'):
    reader = CArchiveReader(os.path.join(DISTPATH, 'ClicknTranslate.app', 'Contents', 'MacOS', name))
    archives = [name for name in reader.toc if name.endswith('.pyz')]
    if not archives or any(not reader.extract(name).startswith(b'PYZ\0') for name in archives):
        raise SystemExit('Corrupt embedded Python archive in ' + name)
