"""
改进版 OCR 后处理 + 检测，对照 Kotlin 端的简化版找差距。

相对 run_debug.py 的差异（每一条都应当移植回 PaddleOcrEngine.kt）：
  1. DET 输入边长改为 limit_side = 1600（不是 960），高分辨率截图小字不再被磨平
  2. DET 后处理用 cv2.findContours + minAreaRect + pyclipper 的 unclip（PaddleOCR 官方做法）
  3. DET_BIN_THRESH=0.3（v5 推荐）+ box_score_thresh=0.6（用 prob map 复核框平均得分）
  4. min_box_size=3px（图像空间），不是面积 64
  5. 识别裁剪前给 box 加 1.5px 各方向 margin（避免笔画贴边被切）
  6. 裁出图按 box 旋转角度做透视矫正，倾斜文字也能识别
  7. CRNN 用 box 的真实 aspect ratio 决定 W，但限制 8 <= W <= 480（之前是 320）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
import pyclipper
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon

HERE = Path(__file__).parent
MODELS = HERE / "models"

DET_LIMIT_SIDE_LEN = 1600
DET_BIN_THRESH = 0.3
DET_BOX_SCORE_THRESH = 0.6
DET_UNCLIP_RATIO = 1.6
DET_MIN_SIZE = 3
REC_TARGET_H = 48
REC_MAX_W = 480
DET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
REC_MEAN = np.array([0.5, 0.5, 0.5], dtype=np.float32)
REC_STD = np.array([0.5, 0.5, 0.5], dtype=np.float32)


def load_keys() -> list[str]:
    raw = (MODELS / "keys.txt").read_bytes().decode("utf-8")
    return [ln.strip("\r\n \t") for ln in raw.splitlines() if ln.strip("\r\n \t")]


def resize_keep_aspect(img: np.ndarray, limit: int) -> tuple[np.ndarray, float, float]:
    h, w = img.shape[:2]
    ratio = limit / max(w, h)
    new_w = int(w * ratio)
    new_h = int(h * ratio)
    new_w = max(32, ((new_w + 31) // 32) * 32)
    new_h = max(32, ((new_h + 31) // 32) * 32)
    out = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    return out, w / new_w, h / new_h


def to_nchw_bgr(img_rgb: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    arr = img_rgb.astype(np.float32) / 255.0
    bgr = arr[..., ::-1]
    bgr = (bgr - mean) / std
    return np.transpose(bgr, (2, 0, 1))[None, ...]


def box_score(prob_map: np.ndarray, box: np.ndarray) -> float:
    """box 是 4 个点的 quad（图像坐标系）。返回 prob_map 在该 quad 内的均值。"""
    h, w = prob_map.shape
    xs = box[:, 0]
    ys = box[:, 1]
    xmin = int(max(0, np.floor(xs.min())))
    xmax = int(min(w - 1, np.ceil(xs.max())))
    ymin = int(max(0, np.floor(ys.min())))
    ymax = int(min(h - 1, np.ceil(ys.max())))
    if xmax <= xmin or ymax <= ymin:
        return 0.0
    mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
    shifted = box.copy()
    shifted[:, 0] -= xmin
    shifted[:, 1] -= ymin
    cv2.fillPoly(mask, [shifted.astype(np.int32)], 1)
    region = prob_map[ymin:ymax + 1, xmin:xmax + 1]
    return float(cv2.mean(region, mask=mask)[0])


def unclip(box: np.ndarray, unclip_ratio: float) -> np.ndarray:
    poly = Polygon(box)
    distance = poly.area * unclip_ratio / max(poly.length, 1e-6)
    pco = pyclipper.PyclipperOffset()
    pco.AddPath([tuple(p) for p in box], pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    expanded = pco.Execute(distance)
    if not expanded:
        return box
    return np.array(expanded[0])


def get_mini_box(contour: np.ndarray) -> tuple[np.ndarray, float]:
    rect = cv2.minAreaRect(contour)
    points = sorted(cv2.boxPoints(rect), key=lambda p: p[0])
    # 按 left-top, right-top, right-bottom, left-bottom 排
    if points[1][1] > points[0][1]:
        i1, i4 = 0, 1
    else:
        i1, i4 = 1, 0
    if points[3][1] > points[2][1]:
        i2, i3 = 2, 3
    else:
        i2, i3 = 3, 2
    box = np.array([points[i1], points[i2], points[i3], points[i4]], dtype=np.float32)
    side = min(rect[1])
    return box, side


def extract_boxes(prob_map: np.ndarray, sx: float, sy: float,
                  bin_thresh: float, score_thresh: float, unclip_ratio: float) -> list[np.ndarray]:
    """PaddleOCR 官方 DB 后处理：bin → contour → minAreaRect → score 复核 → unclip。"""
    bin_map = (prob_map >= bin_thresh).astype(np.uint8) * 255
    contours, _ = cv2.findContours(bin_map, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[np.ndarray] = []
    for c in contours:
        if c.shape[0] < 4:
            continue
        box, side = get_mini_box(c.reshape(-1, 2))
        if side < DET_MIN_SIZE:
            continue
        score = box_score(prob_map, box.astype(np.int32))
        if score < score_thresh:
            continue
        expanded = unclip(box, unclip_ratio).reshape(-1, 2)
        if expanded.shape[0] < 4:
            continue
        box2, side2 = get_mini_box(expanded)
        if side2 < DET_MIN_SIZE + 2:
            continue
        box2[:, 0] *= sx
        box2[:, 1] *= sy
        boxes.append(box2)
    return boxes


def warp_crop(img: np.ndarray, box: np.ndarray) -> np.ndarray:
    """按 quad 4 点做透视矫正，水平摆放裁出矩形。"""
    box = box.astype(np.float32)
    w1 = np.linalg.norm(box[0] - box[1])
    w2 = np.linalg.norm(box[2] - box[3])
    h1 = np.linalg.norm(box[0] - box[3])
    h2 = np.linalg.norm(box[1] - box[2])
    crop_w = int(max(w1, w2))
    crop_h = int(max(h1, h2))
    if crop_w < 2 or crop_h < 2:
        return np.zeros((0, 0, 3), dtype=np.uint8)
    dst = np.array([[0, 0], [crop_w, 0], [crop_w, crop_h], [0, crop_h]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(box, dst)
    out = cv2.warpPerspective(img, M, (crop_w, crop_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    # 竖排（高 > 宽 1.5x）转 90 度
    if crop_h * 1.0 / max(crop_w, 1) >= 1.5:
        out = cv2.rotate(out, cv2.ROTATE_90_CLOCKWISE)
    return out


def ctc_decode(logits: np.ndarray, keys: list[str]) -> str:
    best = logits.argmax(axis=1)
    sb: list[str] = []
    prev = -1
    n_keys = len(keys)
    for idx in best:
        idx = int(idx)
        if idx != 0 and idx != prev:
            kidx = idx - 1
            if 0 <= kidx < n_keys:
                sb.append(keys[kidx])
            elif kidx == n_keys:
                sb.append(" ")
        prev = idx
    return "".join(sb)


def recognize_crop(crop_rgb: np.ndarray, rec: ort.InferenceSession, keys: list[str]) -> str:
    if crop_rgb.size == 0:
        return ""
    h, w = crop_rgb.shape[:2]
    ratio = REC_TARGET_H / h
    target_w = max(8, min(REC_MAX_W, int(w * ratio)))
    resized = cv2.resize(crop_rgb, (target_w, REC_TARGET_H), interpolation=cv2.INTER_LINEAR)
    tensor = to_nchw_bgr(resized, REC_MEAN, REC_STD)
    out = rec.run(None, {rec.get_inputs()[0].name: tensor})[0]
    return ctc_decode(out[0], keys)


def draw_boxes(img: Image.Image, boxes: list[np.ndarray], texts: list[str]) -> Image.Image:
    out = img.copy().convert("RGB")
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
    except OSError:
        font = ImageFont.load_default()
    for i, (box, text) in enumerate(zip(boxes, texts)):
        pts = [(float(p[0]), float(p[1])) for p in box]
        draw.polygon(pts, outline=(255, 64, 64), width=2)
        label = f"{i}:{text}"
        x = float(min(p[0] for p in pts))
        y = float(min(p[1] for p in pts))
        draw.text((x + 2, max(0, y - 16)), label, fill=(255, 255, 0), font=font)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--crops", action="store_true")
    ap.add_argument("--limit", type=int, default=DET_LIMIT_SIDE_LEN)
    ap.add_argument("--bin-thresh", type=float, default=DET_BIN_THRESH)
    ap.add_argument("--score-thresh", type=float, default=DET_BOX_SCORE_THRESH)
    ap.add_argument("--unclip", type=float, default=DET_UNCLIP_RATIO)
    args = ap.parse_args()

    img_path = Path(args.image)
    img_rgb = cv2.cvtColor(cv2.imread(str(img_path)), cv2.COLOR_BGR2RGB)
    H, W = img_rgb.shape[:2]
    print(f"[input] {W}x{H}  limit={args.limit} bin={args.bin_thresh} "
          f"score={args.score_thresh} unclip={args.unclip}")

    det = ort.InferenceSession(str(MODELS / "det.onnx"), providers=["CPUExecutionProvider"])
    rec = ort.InferenceSession(str(MODELS / "rec.onnx"), providers=["CPUExecutionProvider"])
    keys = load_keys()

    resized, sx, sy = resize_keep_aspect(img_rgb, args.limit)
    rH, rW = resized.shape[:2]
    print(f"[det] resized to {rW}x{rH} (sx={sx:.3f} sy={sy:.3f})")

    det_in = to_nchw_bgr(resized, DET_MEAN, DET_STD)
    prob = det.run(None, {det.get_inputs()[0].name: det_in})[0][0, 0]
    print(f"[det] prob max={prob.max():.3f} mean={prob.mean():.3f} "
          f">{args.bin_thresh} ratio={(prob>=args.bin_thresh).mean()*100:.2f}%")

    boxes = extract_boxes(prob, sx, sy, args.bin_thresh, args.score_thresh, args.unclip)
    # 按 y 中心从上到下，x 中心从左到右排序
    boxes.sort(key=lambda b: (b[:, 1].mean(), b[:, 0].mean()))
    print(f"[det] boxes={len(boxes)}")

    texts: list[str] = []
    crops_dir = img_path.parent / f"{img_path.stem}.v2.crops"
    if args.crops:
        crops_dir.mkdir(exist_ok=True)
    for i, box in enumerate(boxes):
        crop = warp_crop(img_rgb, box)
        text = recognize_crop(crop, rec, keys).strip()
        texts.append(text)
        cx = int(box[:, 0].mean()); cy = int(box[:, 1].mean())
        print(f"  [{i:>3}] center=({cx},{cy}) crop={crop.shape[1]}x{crop.shape[0]} → '{text}'")
        if args.crops:
            cv2.imwrite(str(crops_dir / f"{i:03d}.png"), cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))

    out_path = img_path.with_suffix(img_path.suffix + ".v2.png")
    out_img = draw_boxes(Image.fromarray(img_rgb), boxes, texts)
    out_img.save(out_path)
    print(f"[done] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
