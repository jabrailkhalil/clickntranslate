"""Export the native ten-cel Orbit renderer for visual review and app GIFs."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, str(ROOT / 'src'))
from PyQt5 import QtWidgets
from PIL import Image
from assistant_traced_walk import orbit_frame, geometry


def export():
    app = QtWidgets.QApplication(sys.argv)
    output = ROOT / 'src/icons/desktop-assistant/orbit/walk-traced-frames'
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    for index in range(10):
        target = output / f'{index:02}.png'
        orbit_frame(index).save(str(target))
        frames.append(Image.open(target).convert('RGBA'))
    palette_source = Image.new('RGB', (1920, 192), '#ffffff')
    for index, frame in enumerate(frames):
        palette_source.paste(frame, (index*192, 0), frame.getchannel('A'))
    palette = palette_source.quantize(colors=255)
    encoded = []
    for frame in frames:
        item = frame.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE)
        item.paste(255, mask=frame.getchannel('A').point(lambda a: 255 if a < 128 else 0))
        encoded.append(item)
    target = output.parent / 'walk-traced.gif'
    encoded[0].save(target, save_all=True, append_images=encoded[1:],
                    duration=[cel['duration_ms'] for cel in geometry()['frames']],
                    loop=0, disposal=2, transparency=255, optimize=False)
    print(target)
    return app


if __name__ == '__main__':
    export()
