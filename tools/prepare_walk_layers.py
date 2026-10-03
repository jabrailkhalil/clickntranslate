"""Crop the generated 2 x 3 animation sheet into transparent runtime layers."""
from pathlib import Path
import sys
from PIL import Image
from prepare_mascots import gutters

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('body', 'blink', 'arm-near', 'arm-far', 'foot-near', 'foot-far')


def pack(mascot):
    sheet = Image.open(ROOT/'docs/mascots/sources-v7'/f'{mascot}-layers.png').convert('RGBA')
    rows = gutters(sheet, 3, 1)
    output = ROOT/'src/icons/desktop-assistant'/mascot/'walk-layers'
    output.mkdir(parents=True, exist_ok=True)
    index = 0
    for top, bottom in zip(rows, rows[1:]):
        row = sheet.crop((0, top, sheet.width, bottom))
        columns = gutters(row, 2, 0)
        for left, right in zip(columns, columns[1:]):
            cell = row.crop((left, 0, right, row.height))
            bounds = cell.getchannel('A').point(lambda a: 255 if a > 128 else 0).getbbox()
            if bounds is None:
                raise ValueError(f'Empty layer: {mascot}/{NAMES[index]}')
            cell = cell.crop(bounds)
            cell.thumbnail((256, 256), Image.Resampling.LANCZOS)
            cell.save(output/f'{NAMES[index]}.png')
            index += 1
    print(f'{mascot}: six transparent walk layers')


if __name__ == '__main__':
    for mascot in (sys.argv[1:] or ('pancake', 'mochi', 'momo', 'orbit')):
        pack(mascot)
