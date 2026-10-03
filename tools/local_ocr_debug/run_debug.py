"""本地复现 PaddleOcrEngine.kt 的检测+识别流水线，方便对截图调参。

用法：
    python run_debug.py <image>              # 跑当前 Kotlin 等价算法
    python run_debug.py <image> --variant v2 # 跑改进版（DBNet 收缩/box_thresh/padding）

输出：
    <image>.boxes.png  — 画了所有检测框 + 序号的可视化
    <image>.crops/     — 每个 box 裁出的小图（便于人工肉眼对一下识别错的是什么）
    控制台 stdout      — 每个 box 的识别文本、面积、置信
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
MODELS = HERE / "models"

# ---- 与 Kotlin 端保持一致的常量 ----
DET_LIMIT_SIDE_LEN = 960
DET_PROB_THRESH = 0.5
MIN_BOX_AREA = 64
REC_TARGET_H = 48
REC_MAX_W = 320
DET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
REC_MEAN = np.array([0.5, 0.5, 0.5], dtype=np.float32)
REC_STD = np.array([0.5, 0.5, 0.5], dtype=np.float32)


def load_keys() -> list[str]:
    raw = (MODELS / "keys.txt").read_bytes().decode("utf-8")
    return [ln.strip("\r\n \t") for ln in raw.splitlines() if ln.strip("\r\n \t")]


def resize_keep_aspect(img: np.ndarray, limit: int) -> tuple[np.ndarray, float]:
    """与 Kotlin resizeKeepingAspect 等价：最长边=limit，宽高都 round 到 32 倍数。"""
    h, w = img.shape[:2]
    ratio = limit / max(w, h)
    new_w = int(w * ratio)
    new_h = int(h * ratio)
    new_w = max(32, ((new_w + 31) // 32) * 32)
    new_h = max(32, ((new_h + 31) // 32) * 32)
    pil = Image.fromarray(img).resize((new_w, new_h), Image.BILINEAR)
    return np.array(pil), 1.0 / ratio


def to_nchw_bgr(img_rgb: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """复刻 bitmapToNCHW: RGB→BGR + (x/255 - mean)/std。"""
    arr = img_rgb.astype(np.float32) / 255.0
    bgr = arr[..., ::-1]  # RGB→BGR
    bgr = (bgr - mean) / std
    return np.transpose(bgr, (2, 0, 1))[None, ...]


def extract_boxes_kotlin(prob_map: np.ndarray, scale: float) -> list[tuple[int, int, int, int]]:
    """逐像素 BFS 联通域 → 外接矩形。和 Kotlin 实现 1:1 对齐。"""
    h, w = prob_map.shape
    visited = np.zeros((h, w), dtype=bool)
    boxes: list[tuple[int, int, int, int]] = []
    mask = prob_map >= DET_PROB_THRESH
    for y0 in range(h):
        for x0 in range(w):
            if visited[y0, x0] or not mask[y0, x0]:
                continue
            min_x = max_x = x0
            min_y = max_y = y0
            stack = [(x0, y0)]
            visited[y0, x0] = True
            cnt = 0
            while stack:
                cx, cy = stack.pop()
                cnt += 1
                if cx < min_x: min_x = cx
                if cx > max_x: max_x = cx
                if cy < min_y: min_y = cy
                if cy > max_y: max_y = cy
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx] and mask[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((nx, ny))
            if cnt < MIN_BOX_AREA:
                continue
            pad = 2
            l = max(0, min_x - pad) * scale
            t = max(0, min_y - pad) * scale
            r = min(w - 1, max_x + pad) * scale
            b = min(h - 1, max_y + pad) * scale
            l, t, r, b = int(l), int(t), int(r), int(b)
            if (r - l) > 6 and (b - t) > 6:
                boxes.append((l, t, r, b))
    return boxes


def ctc_decode(logits: np.ndarray, keys: list[str]) -> str:
    """[T, C] → 文本。空白 idx=0，键表从 idx=1 起。"""
    best = logits.argmax(axis=1)
    sb: list[str] = []
    prev = -1
    n_keys = len(keys)
    out_of_range = 0
    for idx in best:
        idx = int(idx)
        if idx != 0 and idx != prev:
            kidx = idx - 1
            if 0 <= kidx < n_keys:
                sb.append(keys[kidx])
            elif kidx == n_keys:
                sb.append(" ")
            else:
                out_of_range += 1
        prev = idx
    return "".join(sb)


def recognize_box(crop_rgb: np.ndarray, rec: ort.InferenceSession, keys: list[str]) -> str:
    if crop_rgb.size == 0:
        return ""
    h, w = crop_rgb.shape[:2]
    ratio = REC_TARGET_H / h
    target_w = max(8, min(REC_MAX_W, int(w * ratio)))
    pil = Image.fromarray(crop_rgb).resize((target_w, REC_TARGET_H), Image.BILINEAR)
    tensor = to_nchw_bgr(np.array(pil), REC_MEAN, REC_STD)
    out = rec.run(None, {rec.get_inputs()[0].name: tensor})[0]
    # out shape: [1, T, C]
    return ctc_decode(out[0], keys)


def safe_crop(img: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    h, w = img.shape[:2]
    l, t, r, b = box
    l = max(0, min(l, w - 1))
    t = max(0, min(t, h - 1))
    r = max(l + 1, min(r, w))
    b = max(t + 1, min(b, h))
    return img[t:b, l:r]


def draw_boxes(img: Image.Image, boxes: list[tuple[int, int, int, int]], texts: list[str]) -> Image.Image:
    out = img.copy().convert("RGB")
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
    except OSError:
        font = ImageFont.load_default()
    for i, (box, text) in enumerate(zip(boxes, texts)):
        draw.rectangle(box, outline=(255, 64, 64), width=2)
        label = f"{i}:{text}"
        draw.text((box[0] + 2, max(0, box[1] - 16)), label, fill=(255, 255, 0), font=font)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--crops", action="store_true", help="把每个 box 的裁剪图保存到 .crops/")
    args = ap.parse_args()

    img_path = Path(args.image)
    if not img_path.exists():
        print(f"image not found: {img_path}", file=sys.stderr)
        return 2

    print(f"[load] det={MODELS/'det.onnx'}")
    det = ort.InferenceSession(str(MODELS / "det.onnx"), providers=["CPUExecutionProvider"])
    print(f"[load] rec={MODELS/'rec.onnx'}")
    rec = ort.InferenceSession(str(MODELS / "rec.onnx"), providers=["CPUExecutionProvider"])
    keys = load_keys()
    print(f"[load] keys={len(keys)}")

    img_pil = Image.open(img_path).convert("RGB")
    img = np.array(img_pil)
    H, W = img.shape[:2]
    print(f"[input] {W}x{H}")

    resized, scale = resize_keep_aspect(img, DET_LIMIT_SIDE_LEN)
    rH, rW = resized.shape[:2]
    print(f"[det] resized to {rW}x{rH}, scale_back={scale:.4f}")

    det_in = to_nchw_bgr(resized, DET_MEAN, DET_STD)
    det_out = det.run(None, {det.get_inputs()[0].name: det_in})[0]
    prob = det_out[0, 0]
    print(f"[det] prob_map={prob.shape} max={prob.max():.3f} mean={prob.mean():.3f} "
          f">thresh ratio={(prob>=DET_PROB_THRESH).mean()*100:.2f}%")

    boxes = extract_boxes_kotlin(prob, scale)
    boxes.sort(key=lambda b: (b[1], b[0]))
    print(f"[det] boxes={len(boxes)}")

    texts: list[str] = []
    crops_dir = img_path.parent / f"{img_path.stem}.crops"
    if args.crops:
        crops_dir.mkdir(exist_ok=True)
    for i, box in enumerate(boxes):
        crop = safe_crop(img, box)
        text = recognize_box(crop, rec, keys).strip()
        texts.append(text)
        bw = box[2] - box[0]
        bh = box[3] - box[1]
        print(f"  [{i:>3}] box=({box[0]},{box[1]},{box[2]},{box[3]}) "
              f"{bw}x{bh} → '{text}'")
        if args.crops:
            Image.fromarray(crop).save(crops_dir / f"{i:03d}.png")

    out_img = draw_boxes(img_pil, boxes, texts)
    out_path = img_path.with_suffix(img_path.suffix + ".boxes.png")
    out_img.save(out_path)
    print(f"[done] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
