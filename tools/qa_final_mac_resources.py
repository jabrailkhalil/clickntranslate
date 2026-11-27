"""Check the installed fallback fonts and decode TIFFs with the candidate's Qt loader."""
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

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
for weight in ('Regular', 'Bold'):
    path = fonts / f'ClicknTranslateHan-{weight}.otf'
    data = path.read_bytes()
    assert data == (candidate / 'src/icons/fonts' / path.name).read_bytes()
    face = QtGui.QRawFont(str(path), 16, QtGui.QFont.PreferDefaultHinting)
    assert face.isValid() and face.familyName() == FAMILY and face.styleName() == weight
    assert all(face.supportsCharacter(c) for c in required)
    evidence['fonts'][weight] = {'covered_codepoints': len(required), 'sha256': hashlib.sha256(data).hexdigest()}
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
out = Path('build/macos/trace/final-resources.json')
out.parent.mkdir(exist_ok=True, parents=True)
out.write_text(json.dumps(evidence, indent=2))
print(json.dumps(evidence, indent=2))
