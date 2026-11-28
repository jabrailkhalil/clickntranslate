"""Measure Arabic OCR on the same word pairs used in the Android acceptance suite."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unicodedata
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def normalized(text, *, marks=True):
    value = unicodedata.normalize('NFC', text)
    return ''.join(c for c in value if c.isalnum() or (marks and unicodedata.category(c).startswith('M')))


def compare(reference, text):
    return dict(text=text, exact_letters_and_marks=normalized(text) == normalized(reference),
                same_base_letters=normalized(text, marks=False) == normalized(reference, marks=False))


def fixtures(folder):
    with ZipFile(ROOT / 'tests/fixtures/arabic-diacritics.zip') as archive:
        rows = {}
        for line in archive.read('reference.tsv').decode('utf-8').splitlines():
            name, reference = line.split('\t', 1)
            path = folder / (name + '.png')
            path.write_bytes(archive.read(name + '.png'))
            rows[name] = (path, reference)
        return rows


def rapidocr(cards):
    from ocr_worker import run_request
    images = [dict(label=name, path=str(path)) for name, (path, _) in cards.items()]
    started = time.monotonic()
    result = run_request(dict(engine='rapidocr', action='recognize', language_code='ar', images=images))
    if result.get('error'):
        raise RuntimeError(result['error'])
    rows = {}
    for item in result['results']:
        if item.get('error'):
            raise RuntimeError(item['error'])
        name = item['label']
        rows[name] = dict(compare(cards[name][1], item['text']), elapsed_ms=item['elapsed_ms'])
    assert rows.keys() == cards.keys()
    return dict(cases=rows, elapsed_including_initialization=time.monotonic()-started)


def geometry_comparison(cards):
    """Separate detector crop errors from recognizer errors using the same pinned model."""
    from copy import copy
    from PIL import Image, ImageChops, ImageOps
    import pytesseract
    from ocr_worker import _parse_rapidocr_output, _rapidocr_class
    from ocr_text_layout import ocr_text_from_items
    from rapidocr_models import create_engine

    base = create_engine(_rapidocr_class(), 'ar')
    pieces = {}
    for name, (path, reference) in cards.items():
        with Image.open(path) as opened:
            original = opened.convert('RGB')
        gray = original.convert('L')
        background = gray.getpixel((0, 0))
        mask = ImageChops.difference(gray, Image.new('L', gray.size, background))
        left, top, right, bottom = mask.point(lambda pixel: 255 if pixel > 32 else 0).getbbox()
        positive = ImageOps.invert(original) if background < 128 else original
        trials = []
        for limit in (96, 128, 160, 192, 224, 320, 448):
            for treatment, image in (('original', original), ('dark-on-light', positive)):
                engine = copy(base)
                engine.text_det = copy(base._load_det_model())
                engine.text_det.limit_side_len = limit
                trials.append((f'det-{limit}-{treatment}',
                               lambda e=engine, im=image: [ocr_text_from_items(_parse_rapidocr_output(e(im)))]))
        for padding in (2, 6, 12):
            for treatment, image in (('original', original), ('dark-on-light', positive)):
                box = (max(0, left-padding), max(0, top-padding),
                       min(original.width, right+padding), min(original.height, bottom+padding))
                line = image.crop(box)
                trials.append((f'rec-{padding}-{treatment}',
                               lambda im=line: copy(base)(im, use_det=False).txts))
        for psm in (6, 7):
            trials.append((f'tesseract-psm-{psm}',
                           lambda mode=psm: [pytesseract.image_to_string(original, lang='ara', config=f'--psm {mode}')]))
        for setting, probe in trials:
            start = time.monotonic()
            value = ' '.join(probe() or ()).strip()
            pieces.setdefault(setting, {})[name] = dict(compare(reference, value), elapsed_ms=round((time.monotonic()-start)*1000, 1))
    return pieces


def platform_ocr(cards):
    from PIL import Image
    import ocr
    if sys.platform == 'win32':
        from languages import windows_ocr_tag
        from PyQt5.QtGui import QImage
        supported = ocr._get_available_windows_ocr_language_tags()
        if not any(tag.lower().split('-')[0] == 'ar' for tag in supported):
            return dict(engine='Windows OCR', available=False, languages=supported)
        assert ocr._get_windows_ocr_engine(windows_ocr_tag('ar')) is not None
        engine = 'Windows OCR'
    elif sys.platform == 'darwin':
        import macos_ocr
        if 'ar' not in macos_ocr.language_codes():
            return dict(engine='Apple Vision', available=False, languages=macos_ocr.supported_languages())
        engine = 'apple vision'
    else:
        engine = 'tesseract'
    rows = {}
    for name, (path, reference) in cards.items():
        start = time.monotonic()
        if sys.platform == 'win32':
            texts = []
            worker = ocr.FullScreenOCRWorker(QImage(str(path)), 'ar', engine='windows')
            worker.result_ready.connect(texts.extend)
            worker.run()
            if getattr(worker, 'error_message', ''):
                raise RuntimeError(worker.error_message)
        else:
            with Image.open(path) as image:
                texts = ocr._recognize_image_layout(image.convert('RGB'), engine, 'ar')
        value = ' '.join(item[4] for item in texts)
        rows[name] = dict(compare(reference, value), elapsed_ms=(time.monotonic()-start)*1000)
    return dict(engine=engine, available=True, cases=rows)


def main(path):
    if os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise SystemExit('Runs on a disposable hosted desktop.')
    path.parent.mkdir(parents=True, exist_ok=True)
    report = dict(source=os.environ['GITHUB_SHA'], platform=sys.platform, engines={})
    try:
        with tempfile.TemporaryDirectory(prefix='cnt-arabic-qa-') as temp:
            from unittest.mock import patch
            import portable_paths
            with patch.object(portable_paths, 'portable_base_dir', return_value=temp):
                cards = fixtures(Path(temp))
                report['expected'] = {key: ref for key, (_, ref) in cards.items()}
                report['engines']['rapidocr'] = rapidocr(cards)
                try:
                    report['engines']['platform'] = platform_ocr(cards)
                    if sys.platform.startswith('linux'):
                        report['geometry_comparison'] = geometry_comparison(cards)
                finally:
                    if 'ocr' in sys.modules:
                        sys.modules['ocr'].close_ocr_diagnostics_logging()
        for result in report['engines'].values():
            if rows := result.get('cases'):
                result['exact_count'] = sum(case['exact_letters_and_marks'] for case in rows.values())
                result['base_count'] = sum(case['same_base_letters'] for case in rows.values())
                assert any(case['text'] for case in rows.values())
    finally:
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    main(parser.parse_args().output)
