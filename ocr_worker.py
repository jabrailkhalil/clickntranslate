"""Non-Qt companion process for optional native OCR engines on Windows."""

import contextlib
import importlib
import json
import os
import sys
import time
import traceback

from PIL import Image


_DLL_HANDLES = []


def _candidate_paths(root_dir):
    candidates = [
        root_dir,
        os.path.join(root_dir, "site-packages"),
        os.path.join(root_dir, "Lib", "site-packages"),
        os.path.join(root_dir, "lib", "site-packages"),
    ]
    try:
        for name in os.listdir(root_dir):
            lower = name.lower()
            if lower.startswith("python") or lower in {"venv", ".venv"}:
                candidates.extend(
                    [
                        os.path.join(root_dir, name, "Lib", "site-packages"),
                        os.path.join(root_dir, name, "lib", "site-packages"),
                    ]
                )
    except OSError:
        pass

    unique = []
    seen = set()
    for path in candidates:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen or not os.path.isdir(path):
            continue
        seen.add(normalized)
        unique.append(os.path.abspath(path))
    return unique


def _configure_runtime(root_dir):
    package_paths = _candidate_paths(root_dir)
    for path in reversed(package_paths):
        if path not in sys.path:
            sys.path.insert(0, path)

    dll_paths = []
    for path in package_paths:
        dll_paths.extend(
            [
                path,
                os.path.join(path, "onnxruntime", "capi"),
                os.path.join(path, "cv2"),
                os.path.join(path, "torch", "lib"),
            ]
        )
    dll_paths = [path for path in dll_paths if os.path.isdir(path)]
    if dll_paths:
        os.environ["PATH"] = os.pathsep.join(dll_paths + [os.environ.get("PATH", "")])
    if hasattr(os, "add_dll_directory"):
        for path in dll_paths:
            try:
                _DLL_HANDLES.append(os.add_dll_directory(path))
            except OSError:
                pass


def _rapidocr_class():
    errors = []
    try:
        return importlib.import_module("rapidocr").RapidOCR
    except Exception as exc:
        errors.append(f"rapidocr: {exc}")
    try:
        return importlib.import_module("rapidocr_onnxruntime").RapidOCR
    except Exception as exc:
        errors.append(f"rapidocr_onnxruntime: {exc}")
    raise RuntimeError("; ".join(errors))


def _rapidocr_engine():
    rapid_cls = _rapidocr_class()
    last_type_error = None
    for kwargs in (
        {"text_score": 0.35, "print_verbose": False},
        {"print_verbose": False},
        {},
    ):
        try:
            return rapid_cls(**kwargs)
        except TypeError as exc:
            last_type_error = exc
    raise RuntimeError(f"RapidOCR constructor is unsupported: {last_type_error}")


def _box_origin(box):
    try:
        return min(float(point[1]) for point in box), min(float(point[0]) for point in box)
    except Exception:
        return 0.0, 0.0


def _parse_rapidocr_output(output):
    result = output[0] if isinstance(output, tuple) and output else output
    if result is None:
        return []
    items = []
    if hasattr(result, "txts"):
        texts = list(getattr(result, "txts", None) or [])
        scores = list(getattr(result, "scores", None) or [])
        boxes = list(getattr(result, "boxes", None) or [])
        for index, text in enumerate(texts):
            items.append(
                (
                    boxes[index] if index < len(boxes) else None,
                    str(text or ""),
                    float(scores[index] if index < len(scores) else 0.0),
                )
            )
    elif isinstance(result, (list, tuple)):
        for row in result:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            try:
                score = float(row[2] if len(row) >= 3 else 0.0)
            except Exception:
                score = 0.0
            items.append((row[0], str(row[1] or ""), score))
    items = [(box, text.strip(), score) for box, text, score in items if text.strip()]
    items.sort(key=lambda item: _box_origin(item[0]))
    return items


def _parse_easyocr_output(output):
    items = []
    for row in output or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        try:
            score = float(row[2] if len(row) >= 3 else 0.0)
        except Exception:
            score = 0.0
        items.append((row[0], str(row[1] or "").strip(), score))
    items = [item for item in items if item[1]]
    items.sort(key=lambda item: _box_origin(item[0]))
    return items


def _result_for_items(label, items, elapsed_ms):
    confidences = [item[2] for item in items if item[2] > 0]
    return {
        "label": label,
        "text": "\n".join(item[1] for item in items).strip(),
        "confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        "boxes_count": len(items),
        "elapsed_ms": elapsed_ms,
        "error": "",
    }


def _recognize_rapidocr(request):
    engine = _rapidocr_engine()
    results = []
    for image_request in request.get("images") or []:
        label = str(image_request.get("label") or "image")
        try:
            with Image.open(image_request["path"]) as opened:
                image = opened.convert("RGB").copy()
            started = time.perf_counter()
            items = _parse_rapidocr_output(engine(image))
            results.append(_result_for_items(label, items, (time.perf_counter() - started) * 1000.0))
        except Exception as exc:
            results.append({"label": label, "text": "", "error": f"{type(exc).__name__}: {exc}"})
    return results


def _recognize_easyocr(request):
    easyocr = importlib.import_module("easyocr")
    root_dir = request.get("root_dir") or ""
    model_dir = os.path.join(root_dir, "models")
    user_network_dir = os.path.join(root_dir, "user_network")
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(user_network_dir, exist_ok=True)
    reader = easyocr.Reader(
        list(request.get("language_codes") or ["en"]),
        gpu=False,
        model_storage_directory=model_dir,
        user_network_directory=user_network_dir,
        # Missing flags are intentionally safe: models may be downloaded only
        # by the explicit Language packages installation flow.
        download_enabled=bool(request.get("allow_download", False)),
        verbose=False,
    )
    numpy = importlib.import_module("numpy")
    results = []
    for image_request in request.get("images") or []:
        label = str(image_request.get("label") or "image")
        try:
            with Image.open(image_request["path"]) as opened:
                image = opened.convert("RGB").copy()
            started = time.perf_counter()
            output = reader.readtext(numpy.array(image), detail=1, paragraph=False)
            results.append(
                _result_for_items(label, _parse_easyocr_output(output), (time.perf_counter() - started) * 1000.0)
            )
        except Exception as exc:
            results.append({"label": label, "text": "", "error": f"{type(exc).__name__}: {exc}"})
    return results


def run_request(request):
    engine = str(request.get("engine") or "").lower()
    _configure_runtime(str(request.get("root_dir") or ""))
    action = request.get("action") or "recognize"
    if action == "import":
        if engine == "rapidocr":
            _rapidocr_class()
        elif engine == "easyocr":
            importlib.import_module("easyocr")
        else:
            raise ValueError(f"Unknown OCR engine: {engine}")
        return {"available": True, "error": ""}
    if engine == "rapidocr":
        return {"results": _recognize_rapidocr(request), "error": ""}
    if engine == "easyocr":
        return {"results": _recognize_easyocr(request), "error": ""}
    raise ValueError(f"Unknown OCR engine: {engine}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(json.dumps({"error": "OCR worker request file is required."}))
        return 2
    try:
        with open(argv[0], "r", encoding="utf-8") as request_file:
            request = json.load(request_file)
        with contextlib.redirect_stdout(sys.stderr):
            payload = run_request(request)
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                },
                ensure_ascii=False,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
