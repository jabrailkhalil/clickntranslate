"""Create compact README GIFs and contact sheets from screen recordings.

The project already depends on OpenCV and Pillow, so this keeps the media
pipeline reproducible without requiring a separate ffmpeg installation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
from PIL import Image, ImageDraw


def _capture_metadata(path: Path) -> tuple[float, int, int, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()
    return fps, count, width, height


def _crop_frame(image: Image.Image, crop: tuple[int, int, int, int] | None) -> Image.Image:
    if crop is None:
        return image
    x, y, width, height = crop
    return image.crop((x, y, x + width, y + height))


def _read_frame(
    path: Path,
    frame_index: int,
    crop: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    capture = cv2.VideoCapture(str(path))
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise RuntimeError(f"Could not read frame {frame_index} from {path}")
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return _crop_frame(image, crop)


def create_contact_sheet(
    path: Path,
    output: Path,
    *,
    start_time: float = 0.0,
    end_time: float | None = None,
    crop: tuple[int, int, int, int] | None = None,
    sample_count: int = 12,
) -> None:
    fps, count, _, _ = _capture_metadata(path)
    first_index = max(0, min(count - 1, round(start_time * fps)))
    last_index = count - 1
    if end_time is not None:
        last_index = max(first_index, min(count - 1, round(end_time * fps)))
    indexes = [
        round(first_index + (last_index - first_index) * position / max(1, sample_count - 1))
        for position in range(sample_count)
    ]
    tiles: list[Image.Image] = []
    for index in indexes:
        frame = _read_frame(path, index, crop)
        frame.thumbnail((480, 270), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (480, 300), "#0d0f14")
        tile.paste(frame, ((480 - frame.width) // 2, 0))
        draw = ImageDraw.Draw(tile)
        draw.text((10, 277), f"{index / fps:0.1f}s", fill="#ffffff")
        tiles.append(tile)

    rows = (sample_count + 1) // 2
    sheet = Image.new("RGB", (960, rows * 300), "#080a0e")
    for position, tile in enumerate(tiles):
        sheet.paste(tile, ((position % 2) * 480, (position // 2) * 300))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=90)


def _resize_frame(
    frame,
    target_width: int,
    crop: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    rgb = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    rgb = _crop_frame(rgb, crop)
    if rgb.width <= target_width:
        return rgb
    target_height = max(1, round(rgb.height * target_width / rgb.width))
    return rgb.resize((target_width, target_height), Image.Resampling.LANCZOS)


def create_gif(
    path: Path,
    output: Path,
    *,
    target_width: int = 800,
    target_fps: float = 8.0,
    colors: int = 112,
    start_time: float = 0.0,
    end_time: float | None = None,
    crop: tuple[int, int, int, int] | None = None,
) -> None:
    source_fps, frame_count, _, _ = _capture_metadata(path)
    first_index = max(0, min(frame_count - 1, round(start_time * source_fps)))
    last_index = frame_count - 1
    if end_time is not None:
        last_index = max(first_index, min(frame_count - 1, round(end_time * source_fps)))
    step = max(1, round(source_fps / target_fps))
    duration_ms = max(20, round(1000 * step / source_fps))

    # Build one shared palette from evenly spaced thumbnails. A stable palette
    # avoids color flicker and makes the resulting GIF much smaller.
    samples: list[Image.Image] = []
    sample_count = min(24, max(1, last_index - first_index + 1))
    for position in range(sample_count):
        index = round(
            first_index
            + (last_index - first_index)
            * position
            / max(1, sample_count - 1)
        )
        sample = _read_frame(path, index, crop)
        sample.thumbnail((200, 113), Image.Resampling.LANCZOS)
        samples.append(sample)
    palette_source = Image.new("RGB", (200 * len(samples), 113), "black")
    for position, sample in enumerate(samples):
        palette_source.paste(sample, (position * 200, 0))
    palette = palette_source.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)

    capture = cv2.VideoCapture(str(path))
    capture.set(cv2.CAP_PROP_POS_FRAMES, first_index)
    frames: list[Image.Image] = []
    index = first_index
    while True:
        ok, frame = capture.read()
        if not ok or index > last_index:
            break
        if (index - first_index) % step == 0:
            resized = _resize_frame(frame, target_width, crop)
            frames.append(
                resized.quantize(
                    palette=palette,
                    dither=Image.Dither.FLOYDSTEINBERG,
                )
            )
        index += 1
    capture.release()
    if not frames:
        raise RuntimeError(f"No frames were decoded from {path}")

    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
        disposal=1,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--contact-sheets", action="store_true")
    parser.add_argument("--gifs", action="store_true")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float)
    parser.add_argument("--crop", help="x,y,width,height")
    parser.add_argument("--contact-count", type=int, default=12)
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--fps", type=float, default=8.0)
    args = parser.parse_args()
    if not args.contact_sheets and not args.gifs:
        parser.error("choose --contact-sheets and/or --gifs")

    crop = None
    if args.crop:
        values = tuple(int(value.strip()) for value in args.crop.split(","))
        if len(values) != 4:
            parser.error("--crop must be x,y,width,height")
        crop = values

    for position, video in enumerate(args.inputs, start=1):
        stem = f"demo-{position:02d}"
        if args.contact_sheets:
            create_contact_sheet(
                video,
                args.output_dir / f"{stem}-contact.jpg",
                start_time=args.start,
                end_time=args.end,
                crop=crop,
                sample_count=max(2, args.contact_count),
            )
        if args.gifs:
            create_gif(
                video,
                args.output_dir / f"{stem}.gif",
                target_width=args.width,
                target_fps=args.fps,
                start_time=args.start,
                end_time=args.end,
                crop=crop,
            )


if __name__ == "__main__":
    main()
