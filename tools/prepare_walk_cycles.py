"""Pack ten original walk poses and two registered in-between poses.

This prepares art only. It neither packages the application nor runs its tests.
"""
from pathlib import Path
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from assistant_motion import WALK_FRAME_DURATIONS, WALK_FRAME_NAMES
CHARACTERS = ('pancake', 'mochi', 'momo', 'orbit')
SIDE = 192


def pack(name):
    atlas = Image.open(ROOT / 'docs/mascots/sources-v5' / f'{name}-walk.png').convert('RGBA')
    frames = []
    boxes = []
    for row in range(2):
        for column in range(5):
            frame = atlas.crop((round(column*atlas.width/5), round(row*atlas.height/2),
                                round((column+1)*atlas.width/5), round((row+1)*atlas.height/2)))
            bounds = frame.getchannel('A').point(lambda a: 255 if a > 128 else 0).getbbox()
            if bounds is None:
                raise ValueError(f'Empty pose in {name}')
            frames.append(frame)
            boxes.append(bounds)
    # One scale for the entire cycle, never fit each pose independently.
    # Keep horizontal registration from the original equal-cell atlas.
    left = min(b[0] for b in boxes)
    right = max(b[2] for b in boxes)
    height = max(b[3]-b[1] for b in boxes)
    scale = min(166/(right-left), 168/height)
    width = max(1, round((right-left)*scale))
    output = ROOT / 'src/icons/desktop-assistant' / name / 'walk-frames'
    output.mkdir(parents=True, exist_ok=True)
    ready = []
    for index, (frame, box) in enumerate(zip(frames, boxes)):
        pose = frame.crop((left, box[1], right, box[3]))
        pose = pose.resize((width, max(1, round(pose.height*scale))), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (SIDE, SIDE))
        canvas.alpha_composite(pose, ((SIDE-width)//2, 180-pose.height))
        canvas.save(output / f'{index:02}.png')
        ready.append(canvas)

    poses = {f'{index:02}': frame for index, frame in enumerate(ready)}
    additions = ROOT / 'docs/mascots/sources-v5-arms' / f'{name}-inbetweens.png'
    if additions.exists():
        sheet = Image.open(additions).convert('RGBA')
        for slot, (before, after) in enumerate(((4, 5), (8, 9))):
            cell = sheet.crop((round(slot*sheet.width/2), 0,
                               round((slot+1)*sheet.width/2), sheet.height))
            box = cell.getchannel('A').point(lambda a: 255 if a > 128 else 0).getbbox()
            if box is None:
                raise ValueError(f'Empty in-between in {name}')
            # Register each new full pose against its two unchanged neighbors.
            # Original v5 frames above retain their original packing exactly.
            adjacent = [ready[i].getchannel('A').point(lambda a: 255 if a > 128 else 0).getbbox()
                        for i in (before, after)]
            target_height = round(sum(b[3]-b[1] for b in adjacent)/2)
            center_x = sum((b[0]+b[2])/2 for b in adjacent)/2
            pose = cell.crop(box)
            pose = pose.resize((round(pose.width*target_height/pose.height), target_height),
                               Image.Resampling.LANCZOS)
            canvas = Image.new('RGBA', (SIDE, SIDE))
            canvas.alpha_composite(pose, (round(center_x-pose.width/2), 180-pose.height))
            key = f'{before:02}-{after:02}'
            canvas.save(output / f'{key}.png')
            poses[key] = canvas
    sequence = [poses.get(key, poses[key.split('-')[0]]) for key in WALK_FRAME_NAMES]
    palette_source = Image.new('RGB', (SIDE*len(sequence), SIDE))
    for index, frame in enumerate(sequence):
        palette_source.paste(frame.convert('RGB'), (index*SIDE, 0))
    palette = palette_source.quantize(colors=255)
    encoded = []
    for frame in sequence:
        indexed = frame.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE)
        indexed.paste(255, mask=frame.getchannel('A').point(lambda a: 255 if a < 128 else 0))
        encoded.append(indexed)
    encoded[0].save(output.parent/'walk.gif', save_all=True, append_images=encoded[1:],
                    duration=list(WALK_FRAME_DURATIONS), loop=0, disposal=2, transparency=255, optimize=False)
    print(f'{name}: {len(poses)} full poses, original scale {scale:.4f}, 1.1 s cycle')


if __name__ == '__main__':
    for name in (sys.argv[1:] or CHARACTERS):
        pack(name)
