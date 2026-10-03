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
    output = ROOT / 'docs/mascots'
    motions = [PetMotion(m) for m in MASCOTS]
    positions = [150.] * 5
    frames = []
    # Movement, personal activities, celebration and a stationary pause.
    for index in range(200):
        image = canvas(760, 640)
        painter = QtGui.QPainter(image)
        caption(painter, 24, 28, '1.8.2 • прогулка и ползание → занятие → готово')
        for row, (mascot, motion) in enumerate(zip(MASCOTS, motions)):
            if index == 100:
                motion.set_activity('busy')
            if index == 160:
                motion.set_activity('success')
            delta = motion.advance(.04, 48, 104)
            positions[row] += delta
            motion.moved(delta, 104)
            y = 46 + row * 116
            caption(painter, 24, y+60, ('Блинчик', 'Моти', 'Бубу', 'Момо', 'Орбит')[row])
            painter.setPen(QtGui.QColor('#3c3e51'))
            painter.drawLine(142, y+98, 724, y+98)
            paint_pet(painter, QtCore.QRectF(positions[row], y, 104, 104), mascot,
                      phase=motion.phase, time=motion.time, action=motion.action(),
                      crawl_phase=motion.crawl_phase)
        painter.end()
        frames.append(pil(image).convert('RGB'))
        if index in (0, 4, 8, 12, 16, 120, 174):
            image.save(str(output / f'motion-frame-{index:03}.png'))
    # Fixed palette across all frames prevents background and outline flicker.
    palette_sheet = Image.new('RGB', (760*4, 640))
    for slot, index in enumerate((0, 80, 130, 180)):
        palette_sheet.paste(frames[index], (slot*760, 0))
    palette = palette_sheet.quantize(colors=256)
    encoded = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    encoded[0].save(output / 'motion-v2.gif', save_all=True, append_images=encoded[1:],
                    duration=40, loop=0, optimize=False)
    poses = [p for p in APPEARANCES if p not in ('walking', 'custom')]
    sheet = canvas(1100, 590)
    painter = QtGui.QPainter(sheet)
    labels = ('Спокойный', 'Радость', 'Интерес', 'Думает', 'Удивление', 'Грусть',
              'Сонный', 'Спит', 'Гордится', 'Празднует', 'Занят')
    for col, label in enumerate(labels):
        caption(painter, col*100+4, 23, label)
    for row, mascot in enumerate(MASCOTS):
        for col, pose in enumerate(poses):
            painter.drawPixmap(QtCore.QRect(col*100+2, 30+row*110, 96, 96), companion_art(pose, mascot=mascot))
    painter.end()
    sheet.save(str(output / 'emotions-v2.png'))
    print(f'Motion and 55 static choices rendered in {output}')


if __name__ == '__main__':
    run()
