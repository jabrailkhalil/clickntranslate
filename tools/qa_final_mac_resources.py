"""Check the installed fallback fonts and decode TIFFs with the candidate's Qt loader."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

from PIL import Image
from PyQt5 import QtGui, QtWidgets

candidate = Path('release-source').resolve()
sys.path[:0] = [str(candidate / 'src'), str(candidate)]
from image_input import load_image
from tools.build_chinese_ui_font import FAMILY, interface_codepoints

app = QtWidgets.QApplication([])
root = Path('/Applications/ClicknTranslate.app/Contents')
fonts = root / 'Resources/icons/fonts'
assert (fonts / 'NOTO-CJK-LICENSE.txt').read_bytes() == (
    candidate / 'src/icons/fonts/NOTO-CJK-LICENSE.txt').read_bytes()
required = interface_codepoints()
evidence = {'source_sha': os.environ['EXPECTED_SHA'], 'architecture': platform.machine(),
            'qt': app.platformName(), 'fonts': {}, 'tiff': {}}
assert app.platformName() == 'cocoa'
trace = Path('build/macos/trace').resolve()
trace.mkdir(parents=True, exist_ok=True)
sheet = QtGui.QImage(560, 145, QtGui.QImage.Format_ARGB32)
sheet.fill(QtGui.QColor('#f7f8fa'))
painter = QtGui.QPainter(sheet)
painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
painter.setPen(QtGui.QColor('#192132'))
for weight in ('Regular', 'Bold'):
    path = fonts / f'ClicknTranslateHan-{weight}.otf'
    data = path.read_bytes()
    assert data == (candidate / 'src/icons/fonts' / path.name).read_bytes()
    face = QtGui.QRawFont(str(path), 16, QtGui.QFont.PreferDefaultHinting)
    assert face.isValid() and face.familyName() == FAMILY and face.styleName() == weight
    assert all(face.supportsCharacter(c) for c in required)
    evidence['fonts'][weight] = {'covered_codepoints': len(required), 'sha256': hashlib.sha256(data).hexdigest()}
    assert QtGui.QFontDatabase.addApplicationFont(str(path)) >= 0
    font = QtGui.QFont(FAMILY, 24, QtGui.QFont.Bold if weight == 'Bold' else QtGui.QFont.Normal)
    font.setStyleStrategy(QtGui.QFont.NoFontMerging)
    painter.setFont(font)
    for x, label in ((22, '中文翻译'), (190, '设置'), (295, '在线'), (400, '离线')):
        painter.drawText(x, 51 if weight == 'Regular' else 110, label)
painter.end()
assert sheet.save(str(trace / 'final-chinese-fonts.png'))
tiff = root / 'Frameworks/PyQt5/Qt5/plugins/imageformats/libqtiff.dylib'
assert tiff.is_file()
with tempfile.TemporaryDirectory() as directory:
    for compression in ('raw', 'tiff_lzw', 'tiff_adobe_deflate'):
        path = Path(directory) / (compression + '.tiff')
        im = Image.new('RGB', (97, 65), (21, 156, 90))
        im.save(path, compression=compression)
        for repetition in range(12):
            decoded = load_image(path)
            assert (decoded.width(), decoded.height()) == (97, 65)
            assert decoded.pixelColor(11, 9).getRgb()[:3] == (21, 156, 90)
        evidence['tiff'][compression] = 12
out = trace / 'final-resources.json'
out.write_text(json.dumps(evidence, indent=2))
with tempfile.TemporaryDirectory(prefix='cnt-invalid-theme-') as directory:
    profile = Path(directory)
    runtime = profile / 'runtime'
    runtime.mkdir(mode=0o700)
    data = profile / 'Library/Application Support/ClicknTranslate/data'
    data.mkdir(parents=True)
    preferences = {'theme': 'invalid-theme-macos-qa', 'interface_language': 'en',
                   'show_update_info': False, 'update_check_on_launch': False,
                   'first_run_guide_completed': True, 'first_run_guide_pending': False}
    (data / 'config.json').write_text(json.dumps(preferences))
    env = dict(os.environ, HOME=str(profile), XDG_RUNTIME_DIR=str(runtime))
    ack = profile / 'gui-ready'
    program = root / 'MacOS/ClicknTranslate'
    with (profile / 'startup.log').open('w') as log:
        started = time.monotonic()
        child = subprocess.Popen([str(program), '--show-after-update', f'--update-ack={ack}'],
                                 stdout=log, stderr=log, env=env)
        try:
            while time.monotonic() - started < 75 and not ack.exists() and child.poll() is None:
                time.sleep(.15)
            if not ack.exists():
                log.flush()
                raise AssertionError(f'Invalid-theme profile failed to start: {child.poll()}, '
                                     f'{(profile / "startup.log").read_text()[-1500:]}')
            assert ack.read_text() == '1.8.3'
            evidence['invalid_theme_gui'] = {'version': ack.read_text(), 'input': preferences['theme'],
                                             'seconds_to_gui': round(time.monotonic() - started, 2)}
            import Quartz
            windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, 0)
            candidates = [window for window in windows if int(window.get(Quartz.kCGWindowOwnerPID, -1)) == child.pid
                          and float(window.get(Quartz.kCGWindowBounds, {}).get('Width', 0)) > 240]
            if candidates:
                window = max(candidates, key=lambda item: float(item[Quartz.kCGWindowBounds]['Width']))
                snap = subprocess.run(['/usr/sbin/screencapture', '-x', '-o', '-l',
                                       str(window[Quartz.kCGWindowNumber]), str(trace / 'invalid-theme-main.png')],
                                      capture_output=True, timeout=15)
                evidence['invalid_theme_gui']['captured'] = snap.returncode == 0
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
out.write_text(json.dumps(evidence, indent=2))
print(json.dumps(evidence, indent=2))
