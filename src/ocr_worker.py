"""Non-Qt companion process for optional native OCR engines."""

import contextlib
import importlib
import json
import os
import sys
import time
import traceback
import tempfile
import gc
import queue
import threading
from pathlib import Path

from runtime_bootstrap import activate

_PRIVATE_DLL_RUNTIME = activate()

from PIL import Image, ImageDraw
from ocr_text_layout import order_ocr_items, ocr_text_from_items


_DLL_HANDLES = []
_EASYOCR_CPU_CONFIGURED = False
_SERVING = False
_RESIDENT_ENGINE = None
_RESIDENT_KEY = None
_CONFIGURED_ROOT = None
WORKER_PROTOCOL = 2
IDLE_SECONDS = 300


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
    global _CONFIGURED_ROOT
    if _CONFIGURED_ROOT == root_dir:
        return
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
    _CONFIGURED_ROOT = root_dir


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


def _rapidocr_engine(request=None):
    global _RESIDENT_ENGINE, _RESIDENT_KEY
    from rapidocr_models import create_engine
    request = request or {}
    key = (request.get('root_dir') or '', request.get('language_code') or 'en')
    if _SERVING and _RESIDENT_KEY == key and _RESIDENT_ENGINE is not None:
        return _RESIDENT_ENGINE
    if _SERVING:
        _RESIDENT_ENGINE = None
        gc.collect()
    engine = create_engine(_rapidocr_class(), key[1], key[0])
    if _SERVING:
        _RESIDENT_KEY, _RESIDENT_ENGINE = key, engine
    return engine


def _parse_rapidocr_output(output):
    result = output[0] if isinstance(output, tuple) and output else output
    if result is None:
        return []
    items = []
    if hasattr(result, "txts"):
        texts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        boxes = getattr(result, "boxes", None)
        texts = list(texts) if texts is not None else []
        scores = list(scores) if scores is not None else []
        boxes = list(boxes) if boxes is not None else []
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
    return order_ocr_items(items)


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
    return order_ocr_items(items)


def _result_for_items(label, items, elapsed_ms):
    confidences = [item[2] for item in items if item[2] > 0]
    return {
        "label": label,
        "text": ocr_text_from_items(items),
        "confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        "boxes_count": len(items),
        "items": [([[float(x), float(y)] for x, y in box], text, float(score))
                  for box, text, score in items],
        "elapsed_ms": elapsed_ms,
        "error": "",
    }


def _exercise_rapidocr(engine, probe):
    # RapidOCR 3 persists per-call options on the engine. Warming the
    # recognizer alone must not leave detection disabled for real screenshots.
    original = getattr(engine, 'use_det', True)
    try:
        engine(probe, use_det=False)
    finally:
        if hasattr(engine, 'use_det'):
            engine.use_det = original
    engine(probe, use_det=original)


def _recognize_rapidocr(request):
    engine = _rapidocr_engine(request)
    results = []
    images = request.get('images') or []
    if not images:
        # Availability probes must also exercise lazily loaded native models.
        probe = Image.new('RGB', (96, 40), 'white')
        _exercise_rapidocr(engine, probe)
    for image_request in images:
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
    with _easyocr_reader(request) as reader:
        return _read_easyocr_images(reader, request.get('images') or [])


@contextlib.contextmanager
def _easyocr_reader(request, *, codes=None, recognizer=True):
    root_dir = request.get("root_dir") or ""
    model_dir = os.path.join(root_dir, "models")
    marker = Path(root_dir) / 'runtime/COMPONENT.json'
    managed = marker.is_file() and json.loads(marker.read_bytes()).get('component') == 'ocr.easyocr'
    if managed:
        _configure_easyocr_cpu()
        receipt_path = Path(root_dir)/'receipt.json'
        if receipt_path.is_file():
            aliases = json.loads(receipt_path.read_bytes()).get('sdk_codes',{})
            codes = [aliases.get(code,code) for code in (codes or request.get('language_codes') or ['en'])]
    easyocr = importlib.import_module('easyocr')
    if managed and getattr(easyocr,'__version__','') == '1.7.2':
        from easyocr_models import TAMIL_ALPHABET_FIX
        config = importlib.import_module('easyocr.config')
        tamil = config.recognition_models['gen1']['tamil_g1']
        if tamil['md5sum'] != TAMIL_ALPHABET_FIX['model_md5']:
            raise RuntimeError('Tamil model changed; review its alphabet before approval')
        tamil['characters'] = TAMIL_ALPHABET_FIX['characters']
    with tempfile.TemporaryDirectory(prefix='clickntranslate_easyocr_', dir=request.get('work_dir')) as work:
        if managed:
            user_network_dir = str(Path(work)/'user_network')
            os.environ['TORCH_HOME'] = str(Path(work)/'torch')
        else:
            user_network_dir = os.path.join(root_dir, 'user_network')
        os.makedirs(model_dir, exist_ok=True)
        os.makedirs(user_network_dir, exist_ok=True)
        reader = easyocr.Reader(list(codes or request.get('language_codes') or ['en']),
            gpu=False, model_storage_directory=model_dir, user_network_directory=user_network_dir,
            download_enabled=False if managed else bool(request.get('allow_download', False)),
            recognizer=recognizer, verbose=False)
        try:
            yield reader
        finally:
            del reader
            gc.collect()


def _configure_easyocr_cpu():
    global _EASYOCR_CPU_CONFIGURED
    torch = importlib.import_module('torch')
    if not _EASYOCR_CPU_CONFIGURED:
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        torch.set_num_interop_threads(1)
        _EASYOCR_CPU_CONFIGURED = True
    return torch


def _read_easyocr_images(reader, images):
    numpy = importlib.import_module("numpy")
    results = []
    for image_request in images:
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


def _validate_easyocr(request):
    from easyocr_models import PROBE_CODES, MODEL_FILES
    torch = _configure_easyocr_cpu()
    torchvision = importlib.import_module('torchvision')
    if torch.version.cuda is not None or (sys.platform != 'darwin' and '+cpu' not in torch.__version__):
        raise RuntimeError('Managed EasyOCR requires the declared CPU-only Torch runtime')
    # Loading torchvision alone does not verify its compiled operator ABI.
    torchvision.ops.nms(torch.tensor([[0.,0.,10.,10.]]), torch.tensor([1.]), .5)
    groups = request.get('groups', [])
    root = Path(request['root_dir'])/'models'
    expected = {'craft_mlt_25k.pth', *(MODEL_FILES[group] for group in groups)}
    if {p.name for p in root.glob('*.pth')} != expected:
        raise RuntimeError('EasyOCR models differ from the selected plan')
    with tempfile.TemporaryDirectory(prefix='clickntranslate_easyocr_probe_', dir=request.get('work_dir')) as work:
        path = Path(work)/'probe.png'
        probe = Image.new('RGB',(500,100),'white')
        ImageDraw.Draw(probe).text((20,20),'TEST 123',fill='black',font_size=40)
        probe.save(path)
        for group in groups:
            codes = [PROBE_CODES[group]]
            if codes != ['en']:
                codes.append('en')
            try:
                with _easyocr_reader(request,codes=codes) as reader:
                    result = _read_easyocr_images(reader,[{'path':str(path),'label':group}])[0]
                    if result.get('error') or not result.get('text'):
                        raise RuntimeError('empty or invalid OCR result')
            except Exception as error:
                raise RuntimeError(f'EasyOCR {group}: {error}') from error
        if not groups:
            with _easyocr_reader(request,codes=['en'],recognizer=False) as reader:
                reader.detect(importlib.import_module('numpy').array(probe))
    return {'validated':groups, 'torch':torch.__version__, 'cuda':torch.version.cuda,
            'dll_runtime':_PRIVATE_DLL_RUNTIME, 'error':''}


def run_request(request):
    engine = str(request.get("engine") or "").lower()
    _configure_runtime(str(request.get("root_dir") or ""))
    action = request.get("action") or "recognize"
    if action == 'prepare':
        if engine != 'rapidocr':
            return {'prepared': False, 'available': False, 'error': ''}
        # Initialize only this selected model on a tiny private test image.
        # No screen/clipboard access, downloads, or other language models.
        _recognize_rapidocr(dict(request, images=[]))
        return {'prepared': True, 'available': True, 'error': ''}
    if action == "import":
        if engine == "rapidocr":
            _rapidocr_class()
        elif engine == "easyocr":
            importlib.import_module("easyocr")
        else:
            raise ValueError(f"Unknown OCR engine: {engine}")
        return {"available": True, "error": ""}
    if action == 'validate' and engine == 'rapidocr':
        # Exercise detector, orientation and every recognizer before committing
        # an installation. RapidOCR 3 initializes models lazily, so importing or
        # constructing the engine alone cannot verify its native dependencies.
        probe = Image.new('RGB', (240, 64), 'white')
        ImageDraw.Draw(probe).text((12, 12), 'OCR 123', fill='black', font_size=28)
        for code in ('en', 'ru', 'ar', 'zh', 'es'):
            instance = _rapidocr_engine(dict(request, language_code=code))
            _exercise_rapidocr(instance, probe)
        return {'available': True, 'error': '', 'dll_runtime': _PRIVATE_DLL_RUNTIME}
    if action == 'validate' and engine == 'easyocr':
        return _validate_easyocr(request)
    if engine == "rapidocr":
        return {"results": _recognize_rapidocr(request), "error": ""}
    if engine == "easyocr":
        return {"results": _recognize_easyocr(request), "error": ""}
    raise ValueError(f"Unknown OCR engine: {engine}")


def serve():
    """No preload: receive the first real request before constructing a model.

    EOF from the owning parent is observed even during native inference. This
    avoids orphaned model processes and lets the OS release the child's lease.
    There is no timer/polling loop when the application has never used OCR.
    """
    global _SERVING
    from worker_lease import shared_lease, resident_bytes, memory_pressure_high
    from ocr_lifecycle import IdleLifetime, PRESSURE_INTERVAL
    lifetime = IdleLifetime(IDLE_SECONDS)
    incoming = queue.Queue(maxsize=2)
    output = sys.stdout
    _SERVING = True

    def read_message():
        line = sys.stdin.buffer.readline(16385)
        if not line:
            os._exit(0)
        if len(line) > 16384 or not line.endswith(b'\n'):
            os._exit(2)
        return json.loads(line)

    def receive():
        while True:
            try:
                message = read_message()
                if message.get('control') == 'retention':
                    lifetime.pin(message.get('pinned', False))
                    # One coalesced wakeup interrupts a previously pinned wait.
                    if incoming.empty():
                        incoming.put_nowait({'control': 'wake'})
                else:
                    incoming.put_nowait(message)
            except (ValueError, queue.Full):
                os._exit(2)

    def send(payload):
        output.write(json.dumps(payload, ensure_ascii=False) + '\n')
        output.flush()

    with shared_lease(os.environ.get('CLICKNTRANSLATE_OCR_LEASE', '')):
        # Some Windows NumPy/OpenBLAS builds deadlock in DLL initialization
        # while another thread is blocked reading CRT stdin. Initialize on
        # the first actual request before starting that reader, never ahead
        # of user demand. The owner's Windows Job covers parent death here.
        try:
            reader_started = False
            if os.name != 'nt':
                threading.Thread(target=receive, name='OCR-owner', daemon=True).start()
                reader_started = True
            send({'protocol': WORKER_PROTOCOL})
            while True:
                try:
                    remaining = lifetime.remaining()
                    timeout = PRESSURE_INTERVAL if remaining is None else min(remaining, PRESSURE_INTERVAL)
                    message = incoming.get(timeout=timeout) if reader_started else read_message()
                except queue.Empty:
                    if lifetime.remaining() == 0 or memory_pressure_high():
                        return 0
                    continue
                if message.get('control') == 'wake':
                    continue
                lifetime.pin(message.get('pinned', False))
                try:
                    path = Path(message['path'])
                    if path.stat().st_size > 2 * 1024 * 1024:
                        raise ValueError('OCR request exceeds the protocol limit')
                    request = json.loads(path.read_text(encoding='utf-8'))
                    if request.get('action') not in ('recognize', 'prepare') or request.get('allow_download'):
                        raise ValueError('Resident OCR accepts only explicit local requests')
                    with contextlib.redirect_stdout(sys.stderr):
                        payload = run_request(request)
                    memory = resident_bytes()
                    retain = (request.get('engine') == 'rapidocr' and memory is not None
                              and memory <= 384 * 1024 * 1024 and not memory_pressure_high())
                    lifetime.touch()
                except Exception as error:
                    payload, retain, memory = {'error': f'{type(error).__name__}: {error}'}, False, None
                send({'id': message['id'], 'result': payload, 'retain': retain, 'resident_bytes': memory})
                if not retain:
                    return 0
                if not reader_started:
                    threading.Thread(target=receive, name='OCR-owner', daemon=True).start()
                    reader_started = True
        finally:
            # This read-only child has no user state to flush; every reply was
            # already flushed. Keep the OS lease handle until *all* native
            # threads have stopped, rather than releasing it before Python's
            # slow model destructors. OS process exit releases the lease.
            os._exit(0)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if argv == ['--serve']:
        return serve()
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
