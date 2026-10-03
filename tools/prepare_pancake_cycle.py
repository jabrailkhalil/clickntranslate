"""Crop the generated v9 or v14 parts; preserve their artwork and alpha."""
from pathlib import Path
from PIL import Image
from prepare_mascots import gutters

ROOT = Path(__file__).resolve().parents[1]


def pack(volume=False):
    source = 'sources-v14/pancake-limbs.png' if volume else 'sources-v9/pancake-layers.png'
    image = Image.open(ROOT/'docs/mascots'/source).convert('RGBA')
    output = ROOT/'src/icons/desktop-assistant/pancake'/('volume-layers' if volume else 'cycle-layers')
    output.mkdir(parents=True, exist_ok=True)
    rows = gutters(image, 2, 1)
    names = ('foot-near', 'foot-far', 'arm-near', 'arm-far') if volume else ('body', 'face', 'arm-near', 'arm-far')
    for row in range(2):
        strip = image.crop((0, rows[row], image.width, rows[row+1]))
        columns = gutters(strip, 2, 0)
        for column in range(2):
            cell = strip.crop((columns[column], 0, columns[column+1], strip.height))
            bounds = cell.getchannel('A').point(lambda a: 255 if a > 128 else 0).getbbox()
            cell = cell.crop(bounds)
            cell.thumbnail((320, 320) if volume else (512, 512), Image.Resampling.LANCZOS)
            cell.save(output/f'{names[row*2+column]}.png')
    print(output)


if __name__ == '__main__':
    import sys
    pack('--volume' in sys.argv)
