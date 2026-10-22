"""Export actual production motion and emotions for visual review (no art generation)."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets
from assistant_art import MASCOTS, APPEARANCES, companion_art
from assistant_motion import PetMotion, paint_pet
from assistant_text import assistant_text


def pil(canvas):
    pointer = canvas.bits()
    pointer.setsize(canvas.byteCount())
    return Image.frombytes('RGBA', (canvas.width(), canvas.height()), bytes(pointer))


def canvas(width, height):
    result = QtGui.QImage(width, height, QtGui.QImage.Format_RGBA8888)
    result.fill(QtGui.QColor('#22232e'))
    return result


def caption(painter, x, y, text):
    painter.setPen(QtGui.QColor('#eee8fa'))
    font = painter.font()
    font.setPixelSize(16)
    painter.setFont(font)
    painter.drawText(x, y, text)


def run():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    sys.path.insert(0, str(ROOT / 'tests'))
    from qt_layout_test_support import ensure_layout_fonts
    ensure_layout_fonts(app)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / '.tmp/pets-v18'
    output.mkdir(parents=True, exist_ok=True)
    states = ('idle', 'waving', 'jumping', 'running', 'waiting', 'review', 'failed')
    frames = []
    # All six characters stay at the same origin through every native state.
    for index in range(182):
        state = states[index // 26]
        seconds = index % 26 * .05
        image = canvas(680, 760)
        painter = QtGui.QPainter(image)
        caption(painter, 24, 28, 'Pets v2 • ' + assistant_text('ru', 'reaction_' + state))
        for row, mascot in enumerate(MASCOTS):
            y = 46 + row * 116
            caption(painter, 24, y+60, assistant_text('ru', mascot))
            paint_pet(painter, QtCore.QRectF(290, y, 104, 104), mascot,
                      time=seconds, action=state, state_time=seconds)
        painter.end()
        frames.append(pil(image).convert('RGB'))
    # Fixed palette across all frames prevents background and outline flicker.
    palette_sheet = Image.new('RGB', (680*4, 760))
    for slot, index in enumerate((0, 40, 90, 150)):
        palette_sheet.paste(frames[index], (slot*680, 0))
    palette = palette_sheet.quantize(colors=256)
    encoded = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    encoded[0].save(output / 'stationary-v2.gif', save_all=True, append_images=encoded[1:],
                    duration=50, loop=0, optimize=False)
    poses = [p for p in APPEARANCES if p not in ('animated', 'custom')]
    sheet = canvas(1140, 740)
    painter = QtGui.QPainter(sheet)
    for col, pose in enumerate(poses):
        painter.setPen(QtGui.QColor('#eee8fa'))
        font = painter.font()
        font.setPixelSize(16)
        painter.setFont(font)
        painter.drawText(QtCore.QRect(84+col*150, 2, 148, 38),
                         QtCore.Qt.AlignCenter | QtCore.Qt.TextWordWrap,
                         assistant_text('ru', pose))
    for row, mascot in enumerate(MASCOTS):
        caption(painter, 8, 90+row*110, assistant_text('ru', mascot))
        for col, pose in enumerate(poses):
            painter.drawPixmap(QtCore.QRect(98+col*150, 40+row*110, 96, 96), companion_art(pose, mascot=mascot))
    painter.end()
    sheet.save(str(output / 'native-emotions-v2.png'))
    print(f'Seven stationary native states, six characters: {output}')


if __name__ == '__main__':
    run()
