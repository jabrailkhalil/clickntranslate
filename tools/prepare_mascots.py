"""Extract generated emotion/limb layers and export a rig animation sample.

Run with Python + Pillow + PyQt5. Sources and prompts live in docs/mascots. This only
packs/resizes the generated artwork; it does not draw or retouch characters.
"""
from pathlib import Path
import os
import sys

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MASCOTS = ('pancake', 'mochi', 'bubu', 'momo', 'orbit')
NAMES = ('neutral', 'happy', 'curious', 'thinking', 'surprised', 'sad', 'sleepy', 'blink',
         'sleep', 'proud', 'work-a', 'work-b', 'foot-left', 'foot-right', 'arm-left', 'arm-right')
SIDE = 192


def gutters(image, count, axis):
    """Find the clear gutter nearest each nominal grid boundary."""
    alpha = image.getchannel('A')
    extent = image.size[axis]
    cuts = [0]
    for index in range(1, count):
        expected = round(extent * index / count)
        radius = round(extent / count * .25)
        scores = []
        for position in range(expected - radius, expected + radius + 1):
            box = ((position, 0, position + 1, image.height) if axis == 0 else
                   (0, position, image.width, position + 1))
            # Tiny antialiasing specks should not override the visible contour.
            score = sum(value for value in alpha.crop(box).getdata() if value > 32)
            scores.append((score, abs(position - expected), position))
        cuts.append(min(scores)[2])
    return cuts + [extent]


def cells(sheet):
    rows = gutters(sheet, 4, 1)
    result = []
    for top, bottom in zip(rows, rows[1:]):
        row = sheet.crop((0, top, sheet.width, bottom))
        columns = gutters(row, 4, 0)
        for left, right in zip(columns, columns[1:]):
            cell = row.crop((left, 0, right, row.height))
            bounds = cell.getchannel('A').point(lambda value: 255 if value > 128 else 0).getbbox()
            if bounds is None:
                raise ValueError('Empty sprite cell')
            result.append(cell.crop(bounds))
    return result


def pack(mascot):
    source = ROOT / 'docs/mascots/sources-v2' / f'{mascot}.png'
    sheet = Image.open(source).convert('RGBA')
    if sheet.getchannel('A').getextrema() != (0, 255):
        raise ValueError(f'{source}: expected a transparent atlas')
    sprites = cells(sheet)
    if mascot == 'mochi':
        paws = Image.open(ROOT / 'docs/mascots/sources-v3/mochi-paws.png').convert('RGBA')
        columns = gutters(paws, 2, 0)
        for slot, (left, right) in enumerate(zip(columns, columns[1:])):
            paw = paws.crop((left, 0, right, paws.height))
            bounds = paw.getchannel('A').point(lambda a: 255 if a > 128 else 0).getbbox()
            sprites[12+slot] = paw.crop(bounds)
    output = ROOT / 'src/icons/desktop-assistant' / mascot
    layers = output / 'rig'
    layers.mkdir(parents=True, exist_ok=True)
    for name, sprite in zip(NAMES, sprites):
        sprite.thumbnail((256, 256), Image.Resampling.LANCZOS)
        sprite.save(layers / f'{name}.png')
    print(f'{mascot}: 8 expressions, 4 special poses, 4 rig parts')


def sample_walk(mascot):
    # The current sequence was drawn one source GIF frame at a time.
    if mascot != 'bubu' and (ROOT / 'docs/mascots/sources-v8/frame-09.png').exists():
        from prepare_reference_walk import pack as pack_walk
        pack_walk(mascot)
        return
    if (ROOT / 'docs/mascots/sources-v5' / f'{mascot}-walk.png').exists():
        from prepare_walk_cycles import pack as pack_walk
        pack_walk(mascot)
        return
    from PyQt5 import QtCore, QtGui
    from assistant_motion import paint_pet
    frames = []
    count = 20
    for index in range(count):
        canvas = QtGui.QImage(SIDE, SIDE, QtGui.QImage.Format_RGBA8888)
        canvas.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(canvas)
        paint_pet(painter, QtCore.QRectF(0, 0, SIDE, SIDE), mascot, phase=index/count,
                  crawl_phase=index/count, action='walk')
        painter.end()
        pointer = canvas.bits()
        pointer.setsize(canvas.byteCount())
        frames.append(Image.frombytes('RGBA', (SIDE, SIDE), bytes(pointer)))
    output = ROOT / 'src/icons/desktop-assistant' / mascot
    # One palette prevents color flicker. Index 255 is reserved for transparency;
    # disposal=2 clears each frame so feet cannot leave a trail.
    palette_source = Image.new('RGB', (SIDE * len(frames), SIDE))
    for index, frame in enumerate(frames):
        palette_source.paste(frame.convert('RGB'), (index * SIDE, 0))
    palette = palette_source.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    encoded = []
    for frame in frames:
        quantized = frame.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE)
        quantized.paste(255, mask=frame.getchannel('A').point(lambda a: 255 if a < 128 else 0))
        encoded.append(quantized)
    encoded[0].save(output / 'walk.gif', save_all=True, append_images=encoded[1:],
                    duration=50, loop=0, disposal=2, transparency=255, optimize=False)
    with Image.open(output / 'walk.gif') as walk:
        if walk.n_frames < 16:
            raise ValueError(f'{mascot}: insufficient distinct sample frames')


if __name__ == '__main__':
    for name in MASCOTS:
        pack(name)
    sys.path.insert(0, str(ROOT / 'src'))
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    for name in MASCOTS:
        sample_walk(name)
