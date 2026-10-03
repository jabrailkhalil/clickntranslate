"""与 Kotlin PaddleOcrEngine 改动后 1:1 等价：BFS 联通域 + box score + 矩形 unclip。

用来在 PC 端再现并验证 Kotlin 端改动后的表现。不依赖 OpenCV/pyclipper。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
MODELS = HERE / "models"

DET_LIMIT_SIDE_LEN = 1600
DET_PROB_THRESH = 0.3
MIN_BOX_AREA = 16
DET_BOX_SCORE_THRESH = 0.6
DET_UNCLIP_RATIO = 1.6
REC_TARGET_H = 48
REC_MAX_W = 480
DET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
REC_MEAN = np.array([0.5, 0.5, 0.5], dtype=np.float32)
REC_STD = np.array([0.5, 0.5, 0.5], dtype=np.float32)


def load_keys() -> list[str]:
    raw = (MODELS / "keys.txt").read_bytes().decode("utf-8")
    return [ln.strip("\r\n \t") for ln in raw.splitlines() if ln.strip("\r\n \t")]


def resize_keep_aspect(img: np.ndarray, limit: int):
    h, w = img.shape[:2]
    ratio = limit / max(w, h)
    new_w = int(w * ratio)
    new_h = int(h * ratio)
    new_w = max(32, ((new_w + 31) // 32) * 32)
    new_h = max(32, ((new_h + 31) // 32) * 32)
    pil = Image.fromarray(img).resize((new_w, new_h), Image.BILINEAR)
    return np.array(pil), 1.0 / ratio


def to_nchw_bgr(img_rgb: np.ndarray, mean, std):
    arr = img_rgb.astype(np.float32) / 255.0
    bgr = arr[..., ::-1]
    bgr = (bgr - mean) / std
    return np.transpose(bgr, (2, 0, 1))[None, ...]


def extract_boxes(prob, scale):
    """与 Kotlin extractBoxesFromProbMap (改动后) 完全一致。"""
    h, w = prob.shape
    visited = np.zeros((h, w), dtype=bool)
    mask = prob >= DET_PROB_THRESH
    boxes = []
    for y0 in range(h):
        for x0 in range(w):
            if visited[y0, x0] or not mask[y0, x0]:
                continue
            min_x = max_x = x0
            min_y = max_y = y0
            stack = [(x0, y0)]
            visited[y0, x0] = True
            cnt = 0
            score_sum = 0.0
            while stack:
                cx, cy = stack.pop()
                cnt += 1
                score_sum += float(prob[cy, cx])
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
            avg = score_sum / cnt
            if avg < DET_BOX_SCORE_THRESH:
                continue
            bw = max_x - min_x + 1
            bh = max_y - min_y + 1
            perim = 2 * (bw + bh)
            dist = bw * bh * DET_UNCLIP_RATIO / perim
            pad = max(1, int(dist))
            l = max(0, min_x - pad) * scale
            t = max(0, min_y - pad) * scale
            r = min(w - 1, max_x + pad) * scale
            b = min(h - 1, max_y + pad) * scale
            l, t, r, b = int(l), int(t), int(r), int(b)
            if (r - l) > 6 and (b - t) > 6:
                boxes.append((l, t, r, b, avg))
    return boxes


def safe_crop(img, box):
    h, w = img.shape[:2]
    l, t, r, b = box[:4]
    l = max(0, min(l, w - 1))
    t = max(0, min(t, h - 1))
    r = max(l + 1, min(r, w))
    b = max(t + 1, min(b, h))
    return img[t:b, l:r]


def ctc_decode(logits, keys):
    best = logits.argmax(axis=1)
    sb = []
    prev = -1
    n = len(keys)
    for idx in best:
        idx = int(idx)
        if idx != 0 and idx != prev:
            ki = idx - 1
            if 0 <= ki < n:
                sb.append(keys[ki])
            elif ki == n:
                sb.append(" ")
        prev = idx
    return "".join(sb)


def recognize_box(crop, rec, keys):
    if crop.size == 0:
        return ""
    h, w = crop.shape[:2]
    ratio = REC_TARGET_H / h
    tw = max(8, min(REC_MAX_W, int(w * ratio)))
    pil = Image.fromarray(crop).resize((tw, REC_TARGET_H), Image.BILINEAR)
    tensor = to_nchw_bgr(np.array(pil), REC_MEAN, REC_STD)
    out = rec.run(None, {rec.get_inputs()[0].name: tensor})[0]
    return ctc_decode(out[0], keys)


def draw_boxes(img, boxes, texts):
    out = img.copy().convert("RGB")
    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
    except OSError:
        font = ImageFont.load_default()
    for i, ((l, t, r, b, s), txt) in enumerate(zip(boxes, texts)):
        d.rectangle((l, t, r, b), outline=(255, 64, 64), width=2)
        d.text((l + 2, max(0, t - 16)), f"{i}:{txt}", fill=(255, 255, 0), font=font)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    args = ap.parse_args()

    p = Path(args.image)
    img = np.array(Image.open(p).convert("RGB"))
    H, W = img.shape[:2]
    print(f"[input] {W}x{H}")

    det = ort.InferenceSession(str(MODELS / "det.onnx"), providers=["CPUExecutionProvider"])
    rec = ort.InferenceSession(str(MODELS / "rec.onnx"), providers=["CPUExecutionProvider"])
    keys = load_keys()

    resized, scale = resize_keep_aspect(img, DET_LIMIT_SIDE_LEN)
    print(f"[det] resized {resized.shape[1]}x{resized.shape[0]} scale_back={scale:.4f}")
    prob = det.run(None, {det.get_inputs()[0].name: to_nchw_bgr(resized, DET_MEAN, DET_STD)})[0][0, 0]
    print(f"[det] prob max={prob.max():.3f} >{DET_PROB_THRESH} ratio={(prob>=DET_PROB_THRESH).mean()*100:.2f}%")

    boxes = extract_boxes(prob, scale)
    boxes.sort(key=lambda b: (b[1], b[0]))
    print(f"[det] boxes={len(boxes)}")

    texts = []
    for i, box in enumerate(boxes):
        crop = safe_crop(img, box)
        t = recognize_box(crop, rec, keys).strip()
        texts.append(t)
        print(f"  [{i:>3}] ({box[0]},{box[1]},{box[2]},{box[3]}) {box[2]-box[0]}x{box[3]-box[1]} score={box[4]:.2f} → '{t}'")

    out_path = p.with_suffix(p.suffix + ".v3.png")
    draw_boxes(Image.fromarray(img), boxes, texts).save(out_path)
    print(f"[done] {out_path}")


if __name__ == "__main__":
    main()
