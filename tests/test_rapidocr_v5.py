import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

import ocr
import ocr_worker
import rapidocr_models as models
from ocr_text_layout import ocr_text_from_items, windows_line_text


def test_installer_and_platform_requirements_agree_on_the_backend_version():
    from settings_window import RAPIDOCR_PIP_PACKAGES
    expected=f'rapidocr[rtl]=={models.RAPIDOCR_VERSION}'
    root=Path(__file__).resolve().parents[1]
    assert expected in RAPIDOCR_PIP_PACKAGES
    for name in ('requirements.txt','requirements-linux.txt','requirements-macos.txt'):
        assert expected in (root/name).read_text(encoding='utf8').splitlines()


def test_modern_numpy_output_survives_worker_protocol_and_retains_arabic_order():
    # Deliberately supply visual left-to-right boxes from an Arabic recognizer.
    result = SimpleNamespace(
        boxes=np.array([[[0, 0], [30, 0], [30, 20], [0, 20]],
                        [[45, 0], [75, 0], [75, 20], [45, 20]]]),
        txts=('بالعالم', 'مرحبا'), scores=np.array([.98, .99]))
    items = ocr_worker._parse_rapidocr_output(result)
    payload = ocr_worker._result_for_items('ar', items, 10)
    round_trip = json.loads(json.dumps(payload))
    assert round_trip['text'] == 'مرحبا بالعالم'
    assert ocr_text_from_items(round_trip['items'], join_paragraphs=True) == 'مرحبا بالعالم'


def test_empty_modern_result_is_not_an_error():
    assert ocr_worker._parse_rapidocr_output(SimpleNamespace(boxes=None, txts=None, scores=None)) == []


def test_availability_probe_exercises_lazy_recognizer_and_detector():
    instance = mock.Mock()
    with mock.patch.object(ocr_worker, '_rapidocr_engine', return_value=instance):
        assert ocr_worker._recognize_rapidocr({'images': []}) == []
    assert instance.call_count == 2
    assert instance.call_args_list[0].kwargs == {'use_det': False}
    assert instance.call_args_list[1].kwargs == {}


def test_winrt_arabic_words_are_joined_by_geometry_without_reversing_characters():
    line = SimpleNamespace(words=[SimpleNamespace(text='بالعالم', bounding_rect=SimpleNamespace(x=0)),
                                  SimpleNamespace(text='مرحبا', bounding_rect=SimpleNamespace(x=90))])
    assert windows_line_text(line) == 'مرحبا بالعالم'
    line.words.reverse()
    assert windows_line_text(line) == 'مرحبا بالعالم'


@pytest.mark.parametrize('paragraphs', (False, True))
def test_latin_phrase_and_number_keep_their_internal_order_in_arabic_line(paragraphs):
    texts = ['OpenAI', 'API', '2026', 'أستخدم', 'بالتأكيد', 'أنا']
    items = [([[i*80, 0], [i*80+70, 0], [i*80+70, 20], [i*80, 20]], text, .99)
             for i, text in enumerate(texts)]
    assert ocr_text_from_items(items, join_paragraphs=paragraphs) == 'أنا بالتأكيد أستخدم OpenAI API 2026'


def test_rapid_source_language_reaches_native_worker():
    with mock.patch.object(ocr, '_call_native_ocr_worker', return_value={'results': []}) as worker:
        ocr._recognize_with_native_ocr_worker('rapidocr', [], 'test', 'session', language_code='ar')
    assert worker.call_args.args[0]['language_code'] == 'ar'
    assert worker.call_args.args[0]['allow_download'] is False


def test_fullscreen_source_language_reaches_native_worker():
    from PIL import Image
    with mock.patch.object(ocr, '_call_native_ocr_worker', return_value={'results': []}) as worker:
        ocr._recognize_image_layout(Image.new('RGB', (20, 20)), 'rapidocr', 'ru')
    assert worker.call_args.args[0]['language_code'] == 'ru'


def test_each_language_requires_its_installed_recognizer_and_shared_models(tmp_path):
    def place(key):
        relative, size, _sha = models.MODEL_ASSETS[key]
        with (tmp_path / Path(relative).name).open('wb') as output:
            output.truncate(size)
    with mock.patch.object(models, 'model_roots', return_value=[tmp_path]):
        place('en')
        assert models.installed_languages() == []
        place('det')
        place('cls')
        assert models.installed_languages() == ['en']
        place('arabic')
        assert 'ar' in models.installed_languages()
        assert 'ru' not in models.installed_languages()
        assert 'hi' not in models.installed_languages()


def test_corrupt_model_is_rejected_before_engine_creation(tmp_path):
    bad = tmp_path / 'en.onnx'
    bad.write_bytes(b'bad')
    assets = {'en': ('en.onnx', 3, hashlib.sha256(b'new').hexdigest())}
    with mock.patch.object(models, 'MODEL_ASSETS', assets):
        with pytest.raises(RuntimeError, match='checksum'):
            models.verify_model(bad, 'en')


def test_download_cancellation_stops_before_next_model(tmp_path):
    data = b'model'
    digest = hashlib.sha256(data).hexdigest()
    calls = []
    def download(url, target, **_kwargs):
        calls.append(url)
        Path(target).write_bytes(data)
    def cancelled():
        if calls:
            raise RuntimeError('cancelled')
    with mock.patch.object(models, 'MODEL_ASSETS', {'en': ('en.onnx', len(data), digest),
                                                   'arabic': ('ar.onnx', len(data), digest)}):
        with pytest.raises(RuntimeError, match='cancelled'):
            models.download_models(tmp_path, download, check_cancel=cancelled)
    assert len(calls) == 1


def test_legacy_backend_does_not_claim_to_recognize_arabic():
    class Legacy:
        __module__ = 'rapidocr_onnxruntime.main'
        def __init__(self, **kwargs):
            self.kwargs = kwargs
    assert models.create_engine(Legacy, 'en').kwargs['text_score'] == .35
    with pytest.raises(RuntimeError, match='legacy'):
        models.create_engine(Legacy, 'ar')


@pytest.mark.parametrize('code,group,use_cls', [('ru', 'cyrillic', True), ('ar', 'arabic', False)])
def test_modern_profile_pins_v5_and_local_paths_instead_of_upstream_defaults(tmp_path, code, group, use_cls):
    from enum import Enum
    class EngineType(Enum):
        ONNXRUNTIME = 'onnxruntime'
    class ModelType(Enum):
        MOBILE = 'mobile'
    class OCRVersion(Enum):
        V4 = 'PP-OCRv4'
        V5 = 'PP-OCRv5'
    seen = {}
    class Modern:
        __module__ = 'rapidocr.main'
        def __init__(self, params):
            seen.update(params)
    fake_module = SimpleNamespace(EngineType=EngineType, ModelType=ModelType, OCRVersion=OCRVersion)
    with mock.patch.dict('sys.modules', rapidocr=fake_module), \
         mock.patch.object(models, 'asset_path', side_effect=lambda key, _roots: tmp_path / key), \
         mock.patch.object(models, 'verify_model', side_effect=lambda path, _key: str(path)):
        models.create_engine(Modern, code)
    assert seen['Rec.lang_type'] == group
    assert seen['Global.use_cls'] is use_cls
    assert seen['Rec.ocr_version'].value == 'PP-OCRv5'
    assert seen['Det.ocr_version'].value == 'PP-OCRv5'
    assert seen['Cls.ocr_version'].value == 'PP-OCRv4'
    assert seen['Rec.model_path'] == str(tmp_path / group)


def test_pinned_model_data_is_required_before_packaging(tmp_path):
    with pytest.raises(RuntimeError, match='prepare_rapidocr_models'):
        models.bundled_model_data(tmp_path)
