"""Archive the rejected generated Orbit study against the shell geometry.

This is resource preparation, not an animation generator: every cel receives
the same scale and one translation. Arms, feet and face pixels are untouched.
"""
from pathlib import Path
import argparse
import json
import statistics

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/mascots/sources-v17'
OUTPUT = SOURCE / 'generated-study'
SOURCE_CROP = (30, 43, 96, 109)
SOURCE_SIDE = 66
RAW_TO_SOURCE = .060
SIDE = 192
# The antenna extends above the original character's crop at the high poses.
# One fixed viewport preserves that headroom and identical scale in every cel.
VIEWPORT = (-3., -6., 69., 66.)
DISPLAY_SCALE = SIDE / (VIEWPORT[2] - VIEWPORT[0])
CAP_WIDTH = 30.
CAP_HEIGHT = 4.
CROWN_OFFSETS = (-12., 7., 12.)


def body_pixel(pixel, original=False):
    r, g, b, a = pixel
    if original:
        return a > 200 and r > 150 and b > g and r > b
    return a > 200 and r > 150 and g > 110 and r >= g and g > b + 8


def shell_geometry(image, pixel_scale, original=False):
    """Measure the wide upper shell, above the moving arm and below antenna."""
    pixels = image.load()
    rows = []
    for y in range(image.height):
        xs = [x for x in range(image.width) if body_pixel(pixels[x, y], original)]
        if xs:
            rows.append((y, min(xs), max(xs) + 1, len(xs)))
    minimum_width = CAP_WIDTH / pixel_scale
    wide = [row for row in rows
            if row[2] - row[1] >= minimum_width
            and row[3] >= .6 * (row[2] - row[1])]
    if not wide:
        raise ValueError('No broad upper-shell cap found')
    first_y = wide[0][0]
    cap = [row for row in wide if row[0] < first_y + CAP_HEIGHT / pixel_scale]
    center_x = statistics.mean((row[1] + row[2]) / 2 for row in cap)
    anchors = []
    # Sampling opposite sides of the crown avoids the antenna near x=-7.
    for offset in CROWN_OFFSETS:
        x = round(center_x + offset / pixel_scale)
        low = max(0, round(first_y - 7 / pixel_scale))
        high = min(image.height, round(first_y + 5 / pixel_scale))
        ys = [y for y in range(low, high) if body_pixel(pixels[x, y], original)]
        if not ys:
            raise ValueError(f'No shell crown at column {x}')
        anchors.append({'offset_source_px': offset, 'point': [x, min(ys)]})
    return {
        'upper_cap_center_x': center_x,
        'upper_cap_first_y': first_y,
        'upper_cap_rows': [[y, left, right] for y, left, right, count in cap],
        'crown_anchors': anchors,
    }


def render(image, raw_scale=1., translation=(0., 0.)):
    scale = raw_scale * DISPLAY_SCALE
    ox = (translation[0] - VIEWPORT[0]) * DISPLAY_SCALE
    oy = (translation[1] - VIEWPORT[1]) * DISPLAY_SCALE
    return image.transform((SIDE, SIDE), Image.Transform.AFFINE,
                           (1 / scale, 0, -ox / scale,
                            0, 1 / scale, -oy / scale),
                           resample=Image.Resampling.BICUBIC)


def transparent_gif(frames, target, durations):
    colors = Image.new('RGB', (SIDE * len(frames), SIDE), '#ffffff')
    for index, frame in enumerate(frames):
        colors.paste(frame, (index * SIDE, 0), frame.getchannel('A'))
    palette = colors.quantize(colors=255)
    sequence = []
    for frame in frames:
        item = frame.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE)
        item.paste(255, mask=frame.getchannel('A').point(lambda a: 255 if a < 128 else 0))
        sequence.append(item)
    sequence[0].save(target, save_all=True, append_images=sequence[1:],
                     duration=durations, loop=0, transparency=255, disposal=2)


def pack(label=''):
    paths = []
    for index in range(10):
        fixed = SOURCE / f'orbit-{index:02}-fixed.png'
        paths.append(fixed if fixed.exists() else SOURCE / f'orbit-{index:02}.png')
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise SystemExit('Wait for all ten drawings before packing:\n' + '\n'.join(missing))

    original = Image.open(ROOT / 'docs/mascots/reference/original.gif')
    records, frames, references, durations = [], [], [], []
    for index, path in enumerate(paths):
        image = Image.open(path).convert('RGBA')
        if image.size != (1254, 1254):
            raise ValueError(f'{path.name}: expected shared 1254x1254 source canvas, got {image.size}')
        original.seek(index)
        reference = original.convert('RGBA').crop(SOURCE_CROP)
        source_shell = shell_geometry(reference, 1., original=True)
        drawn_shell = shell_geometry(image, RAW_TO_SOURCE)
        tx = source_shell['upper_cap_center_x'] - RAW_TO_SOURCE * drawn_shell['upper_cap_center_x']
        y_offsets = [ref['point'][1] - RAW_TO_SOURCE * cel['point'][1]
                     for ref, cel in zip(source_shell['crown_anchors'], drawn_shell['crown_anchors'])]
        ty = statistics.mean(y_offsets)
        frame = render(image, RAW_TO_SOURCE, (tx, ty))
        duration = original.info.get('duration', 110)
        solid = image.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()
        source_bounds = [solid[0] * RAW_TO_SOURCE + tx, solid[1] * RAW_TO_SOURCE + ty,
                         solid[2] * RAW_TO_SOURCE + tx, solid[3] * RAW_TO_SOURCE + ty]
        if (source_bounds[0] < VIEWPORT[0] or source_bounds[1] < VIEWPORT[1]
                or source_bounds[2] > VIEWPORT[2] or source_bounds[3] > VIEWPORT[3]):
            raise ValueError(f'{path.name}: solid artwork extends outside fixed viewport: {source_bounds}')
        records.append({'index': index, 'source': path.name, 'source_size': list(image.size),
                        'duration_ms': duration, 'translation_source_px': [tx, ty],
                        'source_shell': source_shell, 'drawn_shell': drawn_shell,
                        'crown_y_offsets_source_px': y_offsets,
                        'solid_bounds_source_px': source_bounds})
        frames.append(frame)
        references.append(render(reference))
        durations.append(duration)

    destination = OUTPUT / 'walk-matched-frames'
    destination.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        frame.save(destination / f'{index:02}.png')
    transparent_gif(frames, OUTPUT / 'walk-matched.gif', durations)
    metadata = {
        'method': 'Shared uniform scale and whole-cel translation; no separate limb transforms. '
                  'Horizontal translation matches upper-shell cap centers. Vertical translation '
                  'is the mean of three upper-shell curve anchor offsets. Antenna, soles and '
                  'the moving hands are not registration anchors.',
        'source_crop': list(SOURCE_CROP), 'source_coordinate_size': [SOURCE_SIDE, SOURCE_SIDE],
        'raw_to_source_scale': RAW_TO_SOURCE, 'viewport_source_px': list(VIEWPORT),
        'output_size': [SIDE, SIDE], 'source_to_output_scale': DISPLAY_SCALE,
        'raw_to_output_scale': RAW_TO_SOURCE * DISPLAY_SCALE,
        'cap_width_source_px': CAP_WIDTH, 'cap_height_source_px': CAP_HEIGHT,
        'crown_offsets_source_px': list(CROWN_OFFSETS), 'frames': records,
    }
    (SOURCE / 'registration.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    contact = Image.new('RGB', (SIDE * 10, (SIDE + 28) * 2), '#252532')
    draw = ImageDraw.Draw(contact)
    for row, sequence in enumerate((references, frames)):
        for index, frame in enumerate(sequence):
            left, top = index * SIDE, row * (SIDE + 28)
            contact.paste(frame, (left, top), frame.getchannel('A'))
            draw.text((left + 8, top + SIDE + 3), f'{"Source" if row == 0 else "Orbit"} {index:02} / {durations[index]}ms', fill='#e2d9ed')
    suffix = f'-{label}' if label else ''
    contact_path = SOURCE / f'registration-contact{suffix}.png'
    contact.save(contact_path)
    print(contact_path)
    print(OUTPUT / 'walk-matched.gif')
    for record in records:
        print(f'{record["index"]:02} {record["source"]}: translation={record["translation_source_px"]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', default='', help='Optional suffix for the review contact sheet')
    pack(parser.parse_args().label)
