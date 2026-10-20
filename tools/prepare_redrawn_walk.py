"""Prepare fixed-cell references and pack directly drawn animation cels.

Artwork is drawn by imagegen. This tool only extracts, crops and uniformly
resizes complete cells; it never invents limb motion or resizes a single pose.
"""
from pathlib import Path
import argparse
import json

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/mascots/sources-v16'
CELL = 256
MASCOTS = ('pancake', 'mochi', 'bubu', 'momo', 'orbit')
SIDE = 192
SHEETS = {'pancake': 'pancake-sheet-yaw.png', 'bubu': 'bubu-sheet-spaced.png'}


def source_cel(name, index):
    sheet = Image.open(SOURCE / SHEETS.get(name, f'{name}-sheet.png')).convert('RGBA')
    column, row = index % 5, index // 5
    return sheet.crop((round(column*sheet.width/5), round(row*sheet.height/2),
                       round((column+1)*sheet.width/5), round((row+1)*sheet.height/2)))


def edit_references():
    for index, label in ((9, 'last-cel-targets'), (0, 'first-cel-arms')):
        atlas = Image.new('RGBA', (800, 800))
        for slot, name in enumerate(('pancake', 'mochi', 'momo', 'orbit')):
            cel = source_cel(name, index).resize((400, 400), Image.Resampling.LANCZOS)
            atlas.alpha_composite(cel, (slot % 2*400, slot // 2*400))
        atlas.save(SOURCE / f'{label}.png')
    atlas = Image.new('RGBA', (800, 400))
    for slot, (name, index) in enumerate((('orbit', 6), ('pancake', 7))):
        cel = source_cel(name, index).resize((400, 400), Image.Resampling.LANCZOS)
        atlas.alpha_composite(cel, (slot*400, 0))
    atlas.save(SOURCE / 'feet-correction-targets.png')


def apply_corrections():
    corrections = (
        ('last-cel-fixed.png', 2, 2, [('pancake', 9), ('mochi', 9), ('momo', 9), ('orbit', 9)]),
        ('feet-correction-fixed.png', 2, 1, [('orbit', 6), ('pancake', 7)]),
    )
    for filename, columns, rows, members in corrections:
        source = SOURCE / filename
        if not source.exists():
            continue
        image = Image.open(source).convert('RGBA')
        for slot, (name, index) in enumerate(members):
            if filename == 'last-cel-fixed.png' and name not in ('pancake', 'momo'):
                continue
            column, row = slot % columns, slot // columns
            cel = image.crop((round(column*image.width/columns), round(row*image.height/rows),
                              round((column+1)*image.width/columns), round((row+1)*image.height/rows)))
            cel = cel.resize(source_cel(name, index).size, Image.Resampling.LANCZOS)
            cel.save(SOURCE / f'{name}-cel-{index:02}-fixed.png')
    grounded = SOURCE / 'orbit-ground-fixed.png'
    if grounded.exists():
        cel = Image.open(grounded).convert('RGBA').resize(
            source_cel('orbit', 6).size, Image.Resampling.LANCZOS)
        cel.save(SOURCE / 'orbit-cel-06-fixed.png')


def reference():
    SOURCE.mkdir(parents=True, exist_ok=True)
    original = Image.open(ROOT / 'docs/mascots/reference/original.gif')
    atlas = Image.new('RGBA', (CELL*5, CELL*2))
    frames = []
    for index in range(original.n_frames):
        original.seek(index)
        # The same crop and scale in every cell retain the actual body bob,
        # foot spacing and sole height of the source animation.
        frame = original.convert('RGBA').crop((30, 43, 96, 109))
        frame = frame.resize((CELL, CELL), Image.Resampling.NEAREST)
        frame.save(SOURCE / f'reference-{index:02}.png')
        atlas.alpha_composite(frame, (index % 5 * CELL, index // 5 * CELL))
        frames.append({'index': index, 'duration_ms': original.info.get('duration', 110)})
    atlas.save(SOURCE / 'reference-atlas.png')
    (SOURCE / 'timing.json').write_text(json.dumps(frames, indent=2)+'\n', encoding='utf-8')
    print(SOURCE / 'reference-atlas.png')


def pack(name):
    filename = SHEETS.get(name, f'{name}-sheet.png')
    image = Image.open(SOURCE / filename).convert('RGBA')
    cells, bounds = [], []
    for index in range(10):
        column, row = index % 5, index // 5
        cell = image.crop((round(column*image.width/5), round(row*image.height/2),
                           round((column+1)*image.width/5), round((row+1)*image.height/2)))
        correction = SOURCE / f'{name}-cel-{index:02}-fixed.png'
        if correction.exists():
            cell = Image.open(correction).convert('RGBA')
        solid = cell.getchannel('A').point(lambda value: 255 if value >= 128 else 0).getbbox()
        if solid is None:
            raise ValueError(f'{name}: empty cel {index}')
        cells.append(cell)
        bounds.append(solid)

    # A single scale for the entire sequence. Register only whole cels by the
    # sole; never recenter a changing silhouette or stretch a single drawing.
    anchor_x = image.width/10
    reach = max(max(anchor_x-box[0], box[2]-anchor_x) for box in bounds)
    scale = min(88/reach, 166/max(box[3]-box[1] for box in bounds))
    timeline = json.loads((ROOT/'docs/mascots/sources-v8/timeline.json').read_text(encoding='utf-8'))
    reference_floor = max(item['bounds'][3] for item in timeline['frames'])
    output = ROOT / 'src/icons/desktop-assistant' / name / 'walk-redrawn-frames'
    output.mkdir(parents=True, exist_ok=True)
    frames, registration = [], []
    for index, (cell, box) in enumerate(zip(cells, bounds)):
        floor = 180. if name == 'bubu' else 180+(timeline['frames'][index]['bounds'][3]-reference_floor)*176/66
        dx, dy = SIDE/2-anchor_x*scale, floor-box[3]*scale
        # One resampling pass, identical scale, and fractional registration.
        frame = cell.transform((SIDE, SIDE), Image.Transform.AFFINE,
            (1/scale, 0, -dx/scale, 0, 1/scale, -dy/scale), Image.Resampling.BICUBIC)
        frame.save(output / f'{index:02}.png')
        frames.append(frame)
        registration.append({'frame': index, 'solid_bounds': box, 'scale': scale,
                             'offset': [dx, dy], 'floor': floor, 'duration_ms': 110,
                             'correction': f'{name}-cel-{index:02}-fixed.png'
                                 if (SOURCE / f'{name}-cel-{index:02}-fixed.png').exists() else None})

    (SOURCE / f'{name}-registration.json').write_text(
        json.dumps({'source': filename, 'frames': registration}, indent=2)+'\n', encoding='utf-8')
    # One shared palette avoids colour shimmer in external GIF previews. The
    # application reads the full-alpha PNG cels instead of this GIF.
    palette_source = Image.new('RGB', (SIDE*10, SIDE))
    for index, frame in enumerate(frames):
        palette_source.paste(frame.convert('RGB'), (index*SIDE, 0))
    palette = palette_source.quantize(colors=255)
    encoded = []
    for frame in frames:
        indexed = frame.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE)
        indexed.paste(255, mask=frame.getchannel('A').point(lambda value: 255 if value < 128 else 0))
        encoded.append(indexed)
    encoded[0].save(output.parent/'walk-redrawn.gif', save_all=True,
                    append_images=encoded[1:], duration=110, loop=0, disposal=2,
                    transparency=255, optimize=False)
    print(f'{name}: 10 full cels, shared scale {scale:.4f}, 110 ms each')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', action='store_true')
    parser.add_argument('--pack', nargs='+', choices=MASCOTS)
    parser.add_argument('--edit-references', action='store_true')
    parser.add_argument('--apply-corrections', action='store_true')
    args = parser.parse_args()
    if args.reference:
        reference()
    if args.edit_references:
        edit_references()
    if args.apply_corrections:
        apply_corrections()
    for name in args.pack or ():
        pack(name)
