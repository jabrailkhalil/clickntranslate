"""Pinned PP-OCRv5 assets. Importing this module never imports a native engine.

Downloads happen only in the explicit installer/build preparation step. A newer
RapidOCR package must not silently select its new default model or fetch files
while the user is translating.
"""
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import sys

# renovate: datasource=pypi depName=rapidocr
RAPIDOCR_VERSION = '3.10.0'
MODEL_SOURCE_REVISION = 'v3.10.0'
BASE_URL = f'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/{MODEL_SOURCE_REVISION}/onnx/'
MODEL_ASSETS = {
    'det': ('PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx', 4819576, '4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae'),
    'cls': ('PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx', 585532, 'e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c'),
    'en': ('PP-OCRv5/rec/en_PP-OCRv5_rec_mobile.onnx', 7872351, 'c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8'),
    'cyrillic': ('PP-OCRv5/rec/cyrillic_PP-OCRv5_rec_mobile.onnx', 8074092, '90f761b4bfcce0c8c561c0cb5c887b0971d3ec01c32164bdf7374a35b0982711'),
    'arabic': ('PP-OCRv5/rec/arabic_PP-OCRv5_rec_mobile.onnx', 8023828, 'c1192e632d0baa9146ae5b756a0e635e3dc63c1733737ebfd1629e87144e9295'),
    'latin': ('PP-OCRv5/rec/latin_PP-OCRv5_rec_mobile.onnx', 7904513, 'b20bd37c168a570f583afbc8cd7925603890efbcdc000a59e22c269d160b5f5a'),
    'ch': ('PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx', 16631306, '5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5'),
}

# Conservative subset of the upstream script models. A language is exposed only
# when its recognizer and both shared models are present. Translation targets
# remain independent of OCR language support.
LANGUAGE_MODELS = dict.fromkeys(('ru', 'uk', 'be', 'bg', 'sr', 'mk'), 'cyrillic')
LANGUAGE_MODELS.update(dict.fromkeys(('ar', 'fa', 'ur', 'ps'), 'arabic'))
LANGUAGE_MODELS.update(dict.fromkeys(('de', 'es', 'fr', 'pt', 'it', 'tr', 'id', 'nl', 'pl', 'cs', 'sk', 'hr', 'sl', 'ro', 'hu', 'da', 'fi', 'sv', 'no', 'vi', 'ms'), 'latin'))
LANGUAGE_MODELS.update(en='en', zh='ch')


def model_roots(root_dir=''):
    roots = []
    override = os.environ.get('CLICKNTRANSLATE_RAPIDOCR_MODEL_DIR')
    if override:
        roots.append(Path(override))
    if root_dir:
        roots.append(Path(root_dir) / 'models' / 'ppocrv5')
    frozen = getattr(sys, '_MEIPASS', '')
    if frozen:
        roots.append(Path(frozen) / 'rapidocr_models')
    roots.append(Path(__file__).resolve().parents[1] / 'assets' / 'rapidocr_models')
    return roots


def asset_path(key, roots):
    filename = Path(MODEL_ASSETS[key][0]).name
    for root in roots:
        path = root / filename
        try:
            if path.stat().st_size == MODEL_ASSETS[key][1]:
                return path
        except OSError:
            pass
    return None


@lru_cache(maxsize=32)
def _verified(path, size, mtime_ns, expected):
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise RuntimeError(f'RapidOCR model checksum failed: {Path(path).name}')
    return path


def verify_model(path, key):
    stat = Path(path).stat()
    if stat.st_size != MODEL_ASSETS[key][1]:
        raise RuntimeError(f'Incomplete RapidOCR model: {Path(path).name}')
    return _verified(os.fspath(path), stat.st_size, stat.st_mtime_ns, MODEL_ASSETS[key][2])


def installed_languages(root_dir=''):
    roots = model_roots(root_dir)
    if not all(asset_path(key, roots) for key in ('det', 'cls')):
        return []
    available = {key for key in MODEL_ASSETS if asset_path(key, roots)}
    return [code for code, group in LANGUAGE_MODELS.items() if group in available]


def create_engine(rapid_cls, language_code='en', root_dir=''):
    code = str(language_code or 'en').lower().replace('_', '-').split('-')[0]
    if rapid_cls.__module__.startswith('rapidocr_onnxruntime'):
        if code not in ('en', 'zh'):
            raise RuntimeError('This legacy RapidOCR supports only English/Chinese. Update RapidOCR in Language packages.')
        return rapid_cls(text_score=.35, print_verbose=False)
    from rapidocr import EngineType, ModelType, OCRVersion
    group = LANGUAGE_MODELS.get(code)
    if group is None:
        raise RuntimeError(f'No installed RapidOCR recognizer for language: {code}')
    roots = model_roots(root_dir)
    paths = {}
    for key in ('det', 'cls', group):
        path = asset_path(key, roots)
        if path is None:
            raise RuntimeError(f'RapidOCR PP-OCRv5 model is missing: {key}. Install RapidOCR in Language packages.')
        paths[key] = verify_model(path, key)
    params = {'Global.text_score': .35, 'Global.log_level': 'error',
              # The shared Chinese 0/180 classifier can turn upright Arabic
              # words upside down. Screen captures are upright; leave Arabic
              # glyphs untouched instead of applying this unrelated classifier.
              'Global.use_cls': group != 'arabic'}
    for component, key, version, language in (
        ('Det', 'det', 'PP-OCRv5', 'ch'),
        ('Cls', 'cls', 'PP-OCRv4', 'ch'),
        ('Rec', group, 'PP-OCRv5', group),
    ):
        params.update({f'{component}.engine_type': EngineType.ONNXRUNTIME,
                       f'{component}.model_type': ModelType.MOBILE,
                       f'{component}.ocr_version': OCRVersion(version),
                       f'{component}.lang_type': language,
                       f'{component}.model_path': paths[key]})
    return rapid_cls(params=params)


def download_models(destination, download, check_cancel=lambda: None, progress=lambda *_: None):
    """Use the app's resumable downloader, then verify before installation."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for index, (key, (relative, _size, _sha)) in enumerate(MODEL_ASSETS.items()):
        check_cancel()
        path = destination / Path(relative).name
        download(BASE_URL + relative, os.fspath(path),
                 progress_callback=lambda done, total, i=index: progress(i, done, total))
        verify_model(path, key)
        check_cancel()


def bundled_model_data(project_root):
    """Fail a build before producing an app that silently fetches other models."""
    root = Path(project_root) / 'assets' / 'rapidocr_models'
    result = []
    for key, (relative, _size, _sha) in MODEL_ASSETS.items():
        path = root / Path(relative).name
        if not path.is_file():
            raise RuntimeError('Prepare PP-OCRv5 first: python tools/prepare_rapidocr_models.py')
        result.append((verify_model(path, key), 'rapidocr_models'))
    return result
