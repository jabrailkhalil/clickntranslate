"""Cancelled and oversized image requests stop before allocating the rest of the PNG."""
import base64
import io
from unittest import mock

import pytest
from PIL import Image

import api_providers as api
from translater import TranslationCancelledError


@pytest.mark.parametrize('recognize', [api.recognize, api.recognize_regions])
@pytest.mark.parametrize('cancel_after', [0, 3])
def test_cancelling_before_or_while_encoding_does_not_submit_the_image(monkeypatch, recognize, cancel_after):
    chunks = []

    def encode(_image, buffer, **_kwargs):
        for i in range(20):
            buffer.write(b'x' * 256)
            chunks.append(i)

    image = Image.new('RGB', (40, 30))
    monkeypatch.setattr(Image.Image, 'save', encode)
    monkeypatch.setattr(api, 'validate', lambda *_: {'model': 'test', 'vision': True, 'direct': True,
                                                    'url': 'https://mock.invalid'})
    monkeypatch.setattr(api, 'credential', lambda *_: 'unused')
    with mock.patch.object(api, '_session') as transport, pytest.raises(TranslationCancelledError):
        recognize('openai', image, 'ar', 'en', {}, lambda: len(chunks) >= cancel_after)
    assert len(chunks) == cancel_after
    transport.assert_not_called()


def test_png_output_stops_at_the_existing_upload_limit(monkeypatch):
    completed = []
    chunk = b'x' * (1024 * 1024)

    def encode(_image, buffer, **_kwargs):
        for i in range(12):
            buffer.write(chunk)
            completed.append(i)

    monkeypatch.setattr(Image.Image, 'save', encode)
    with pytest.raises(api.ProviderError, match='too large'):
        api._encode_image(Image.new('RGB', (40, 30)))
    assert len(completed) == 8


@pytest.mark.parametrize('mode', ['RGB', 'RGBA', 'L'])
def test_png_keeps_the_size_and_every_color_of_the_selected_image(mode):
    original = Image.new(mode, (5, 7), 0)
    original.putpixel((1, 2), {'RGB': (4, 27, 250), 'RGBA': (4, 27, 250, 38), 'L': 47}[mode])
    with Image.open(io.BytesIO(base64.b64decode(api._encode_image(original)))) as decoded:
        assert decoded.size == original.size and decoded.mode == 'RGB'
        assert decoded.tobytes() == original.convert('RGB').tobytes()


def test_import_cancelled_before_the_worker_runs_does_not_decode_the_photo():
    from image_input import recognize_image
    with mock.patch('image_input.load_image') as decode:
        assert recognize_image(b'fixture', {}, 'en', 'ru', lambda: True) == ('', None)
    decode.assert_not_called()
