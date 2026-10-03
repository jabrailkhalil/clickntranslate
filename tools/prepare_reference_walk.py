"""Pack separately drawn frames in the source GIF's order and timing.

Only crop, register and resize the generated artwork. No app build or tests.
The reference itself is kept outside application resources.
"""
from pathlib import Path
import json
from PIL import Image
from prepare_mascots import gutters

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'docs/mascots/sources-v8'
CHARACTERS = ('pancake', 'mochi', 'momo', 'orbit')
SIDE = 192


def pack(name):
    timeline = json.loads((SOURCES / 'timeline.json').read_text(encoding='utf-8'))
    row, column = divmod(CHARACTERS.index(name), 2)
    sprites = []
    for frame in timeline['frames']:
        atlas = Image.open(SOURCES / f'frame-{frame["index"]:02}.png').convert('RGBA')
        # Normalize the whole atlas once. Clear gutters may sit a few pixels
        # away from the nominal center when an extended hand is wide.
        atlas = atlas.resize((1280, 1280), Image.Resampling.LANCZOS)
        rows = gutters(atlas, 2, 1)
        strip = atlas.crop((0, rows[row], atlas.width, rows[row+1]))
        columns = gutters(strip, 2, 0)
        cell = strip.crop((columns[column], 0, columns[column+1], strip.height))
        bounds = cell.getchannel('A').point(lambda a: 255 if a > 128 else 0).getbbox()
        if bounds is None:
            raise ValueError(f'Empty frame {frame["index"]} for {name}')
        sprites.append(cell.crop(bounds))

    scale = min(166/max(im.width for im in sprites), 164/max(im.height for im in sprites))
    reference_boxes = [frame['bounds'] for frame in timeline['frames']]
    reference_scale = 166/(max(b[2] for b in reference_boxes)-min(b[0] for b in reference_boxes))
    reference_center = (reference_boxes[0][0]+reference_boxes[0][2])/2
    reference_floor = max(b[3] for b in reference_boxes)
    output = ROOT / 'src/icons/desktop-assistant' / name / 'walk-reference-frames'
    output.mkdir(parents=True, exist_ok=True)
    ready = []
    for index, (sprite, bounds) in enumerate(zip(sprites, reference_boxes)):
        sprite = sprite.resize((round(sprite.width*scale), round(sprite.height*scale)),
                               Image.Resampling.LANCZOS)
        center = SIDE/2 + ((bounds[0]+bounds[2])/2-reference_center)*reference_scale
        floor = 180 + (bounds[3]-reference_floor)*reference_scale
        canvas = Image.new('RGBA', (SIDE, SIDE))
        canvas.alpha_composite(sprite, (round(center-sprite.width/2), round(floor-sprite.height)))
        canvas.save(output / f'{index:02}.png')
        ready.append(canvas)

    durations = [frame['duration_ms'] for frame in timeline['frames']]
    palette_source = Image.new('RGB', (SIDE*len(ready), SIDE))
    for index, frame in enumerate(ready):
        palette_source.paste(frame.convert('RGB'), (index*SIDE, 0))
    palette = palette_source.quantize(colors=255)
    encoded = []
    for frame in ready:
        indexed = frame.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE)
        indexed.paste(255, mask=frame.getchannel('A').point(lambda a: 255 if a < 128 else 0))
        encoded.append(indexed)
    encoded[0].save(output.parent/'walk.gif', save_all=True, append_images=encoded[1:],
                    duration=durations, loop=0, disposal=2, transparency=255, optimize=False)
    print(f'{name}: {len(ready)} source-matched frames, {sum(durations)} ms cycle')


if __name__ == '__main__':
    import sys
    for character in sys.argv[1:] or CHARACTERS:
        pack(character)
