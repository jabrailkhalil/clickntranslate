"""Export sharp static home shortcuts without loading animation atlases at runtime."""
from pathlib import Path
from PyQt5 import QtCore, QtGui


def export(root):
    for atlas in sorted((root/'src/icons/desktop-assistant').glob('*/pets-v2.png')):
        reader = QtGui.QImageReader(str(atlas))
        if reader.size() != QtCore.QSize(1536, 2288):
            raise ValueError(f'Unexpected sprite sheet: {atlas.name}')
        reader.setClipRect(QtCore.QRect(0, 0, 192, 208))
        image = reader.read()
        if image.size() != QtCore.QSize(192, 208) or not image.hasAlphaChannel():
            raise ValueError(f'Cannot extract resting pose: {atlas.parent.name}')
        if not image.save(str(atlas.with_name('preview.png')), 'PNG'):
            raise OSError(f'Cannot save resting pose: {atlas.parent.name}')
        print(atlas.parent.name, '192x208 static preview')


if __name__ == '__main__':
    export(Path(__file__).resolve().parents[1])
