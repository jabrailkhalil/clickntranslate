"""Tiny owned images through actual file loading and fake OCR boundaries."""
import threading
import io
import struct
import zlib
from types import SimpleNamespace

import pytest
from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets

import api_providers as api
import image_input as images


@pytest.fixture(scope='module', autouse=True)
def qt_app():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app.platformName().split(':')[0] == 'offscreen'
    yield app


def supported(format):
    choices = {bytes(item).decode().lower() for item in QtGui.QImageReader.supportedImageFormats()}
    if not ({format.lower(), 'tif' if format == 'TIFF' else format.lower()} & choices):
        pytest.skip('Qt codec unavailable: ' + format)


def corners():
    image = Image.new('RGB', (40, 20))
    for y in range(20):
        for x in range(40):
            image.putpixel((x, y), [(240, 20, 20), (20, 220, 20), (20, 20, 240), (220, 220, 20)][(y >= 10) * 2 + (x >= 20)])
    return image


TRANSPOSE = {2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
             4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
             6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE, 8: Image.Transpose.ROTATE_90}


def assert_corners(actual, expected, tolerance=0):
    assert (actual.width(), actual.height()) == expected.size
    w, h = expected.size
    for x, y in [(w // 4, h // 4), (3 * w // 4, h // 4), (w // 4, 3 * h // 4), (3 * w // 4, 3 * h // 4)]:
        got = actual.pixelColor(x, y).getRgb()[:3]
        wanted = expected.getpixel((x, y))
        assert all(abs(a - b) <= tolerance for a, b in zip(got, wanted)), (got, wanted)


@pytest.mark.parametrize('format,extension', [('JPEG', 'jpg'), ('PNG', 'png'), ('TIFF', 'tiff')])
@pytest.mark.parametrize('orientation', range(1, 9))
def test_all_exif_rotations_and_reflections_match_owned_pixels(tmp_path, format, extension, orientation):
    supported(format)
    original = corners()
    exif = original.getexif()
    exif[274] = orientation
    path = tmp_path / ('oriented.' + extension)
    original.save(path, format=format, exif=exif)
    expected = original.transpose(TRANSPOSE[orientation]) if orientation in TRANSPOSE else original
    assert_corners(images.load_image(path), expected, tolerance=35 if format == 'JPEG' else 0)


def glyph(path, mode, foreground):
    if mode == 'RGBA':
        image = Image.new('RGBA', (12, 8), (foreground,) * 3 + (0,))
        for y in range(2, 6):
            for x in range(4, 8):
                image.putpixel((x, y), (foreground,) * 3 + (255,))
    else:
        image = Image.new('P', (12, 8), 0)
        image.putpalette([foreground, foreground, foreground] * 2 + [0] * 762)
        for y in range(2, 6):
            for x in range(4, 8):
                image.putpixel((x, y), 1)
        image.info['transparency'] = 0
    image.save(path, format='PNG')


@pytest.mark.parametrize('mode', ['RGBA', 'P'])
@pytest.mark.parametrize('foreground', [0, 255], ids=['black-text', 'white-text'])
@pytest.mark.parametrize('engine', ['OpenAI API', 'Tesseract'])
@pytest.mark.parametrize('kind', ['file', 'qimage'])
def test_transparency_keeps_glyph_contrast_in_actual_selected_ocr_payload(tmp_path, monkeypatch, mode, foreground, engine, kind):
    path = tmp_path / 'alpha-glyph.png'
    glyph(path, mode, foreground)
    payload = path if kind == 'file' else QtGui.QImage(str(path))
    seen = []
    if engine == 'OpenAI API':
        def recognize(provider, image, source, target, config, cancel):
            assert provider == 'openai' and source == 'en' and target == 'ar'
            seen.append(image)
            return SimpleNamespace(source='Glyph', translation=None)
        monkeypatch.setattr(api, 'recognize', recognize)
    else:
        import ocr
        def recognize(image, engine, language, **_kwargs):
            assert engine == 'tesseract' and language == 'en'
            seen.append(image)
            return [(0, 0, image.width, image.height, 'Glyph')]
        monkeypatch.setattr(ocr, '_recognize_image_layout', recognize)
    assert images.recognize_image(payload, {'ocr_engine': engine}, 'en', 'ar', lambda: False) == ('Glyph', None)
    assert len(seen) == 1 and seen[0].size == (12, 8)
    assert any(low != high for low, high in seen[0].convert('RGB').getextrema()), 'Alpha-defined glyph became a solid-color OCR payload'


@pytest.mark.parametrize('mode', ['1', 'P'])
def test_opaque_mono_and_palette_pixels_stay_distinct(tmp_path, mode):
    source = Image.new(mode, (12, 8), 0)
    if mode == 'P':
        source.putpalette([0, 0, 0, 255, 255, 255] + [0] * 762)
    source.putpixel((5, 4), 1 if mode == 'P' else 255)
    path = tmp_path / 'opaque.png'
    source.save(path)
    result = images.load_image(path)
    assert result.pixelColor(0, 0).red() == 0
    assert result.pixelColor(5, 4).red() == 255


@pytest.mark.parametrize('format,extension', [('GIF', 'gif'), ('TIFF', 'tiff')])
def test_multiframe_import_uses_the_first_frame(tmp_path, format, extension):
    supported(format)
    first = Image.new('RGB', (12, 8), (240, 10, 10))
    second = Image.new('RGB', (12, 8), (10, 10, 240))
    path = tmp_path / ('frames.' + extension)
    first.save(path, format=format, save_all=True, append_images=[second], duration=100, loop=0)
    loaded = images.load_image(path)
    assert loaded.pixelColor(5, 4).getRgb()[:3] == (240, 10, 10)


@pytest.mark.parametrize('operation', ['paste', 'drop'])
def test_file_mime_routes_the_same_oriented_owned_pixels(tmp_path, operation):
    source = corners()
    exif = source.getexif()
    exif[274] = 6
    path = tmp_path / 'mime.jpg'
    source.save(path, exif=exif)
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(str(path))])
    editor = images.ImageInputTextEdit()
    payloads = []
    editor.image_requested.connect(payloads.append)
    try:
        if operation == 'paste':
            editor.insertFromMimeData(mime)
        else:
            event = QtGui.QDropEvent(QtCore.QPointF(2, 2), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
            editor.dropEvent(event)
            assert event.isAccepted()
        assert len(payloads) == 1
        assert_corners(images.load_image(payloads[0]), source.transpose(TRANSPOSE[6]), tolerance=35)
    finally:
        editor.deleteLater()


@pytest.mark.parametrize('cancel', [False, True], ids=['config-snapshot', 'cancel-while-loading'])
def test_loading_boundary_keeps_selected_provider_pixels_and_cancel_identity(tmp_path, monkeypatch, qt_app, cancel):
    source = corners()
    path = tmp_path / 'loading.png'
    source.save(path)
    entered, release, stopped = threading.Event(), threading.Event(), threading.Event()
    load, recognize = images.load_image, images.recognize_image
    seen, ready, failed = [], [], []
    def held_load(payload):
        result = load(payload)
        entered.set()
        assert release.wait(3)
        return result
    def tracking(*args):
        try:
            return recognize(*args)
        finally:
            stopped.set()
    def provider(name, image, src, tgt, config, cancelled):
        seen.append((name, image.copy(), src, tgt, config))
        return SimpleNamespace(source='Owned image', translation=None)
    monkeypatch.setattr(images, 'load_image', held_load)
    monkeypatch.setattr(images, 'recognize_image', tracking)
    monkeypatch.setattr(api, 'recognize', provider)
    owner = QtCore.QObject()
    controller = images.ImageImportController(owner)
    controller.ready.connect(lambda *args: ready.append(args))
    controller.failed.connect(failed.append)
    config = {'ocr_engine': 'OpenAI API', 'api_providers': {'openai': {'model': 'old-model'}}}
    try:
        assert controller.start(path, config, 'en', 'ar')
        assert entered.wait(2)
        config['ocr_engine'] = 'Gemini API'
        config['api_providers']['openai']['model'] = 'new-model'
        Image.new('RGB', source.size, 'black').save(path)
        if cancel:
            controller.cancel()
        release.set()
        assert stopped.wait(3)
        qt_app.processEvents()
        assert not failed
        if cancel:
            assert not seen and not ready and not controller.busy
        else:
            assert ready == [('Owned image', None)] and not controller.busy
            assert len(seen) == 1 and seen[0][0] == 'openai' and seen[0][2:4] == ('en', 'ar')
            assert seen[0][4]['api_providers']['openai']['model'] == 'old-model'
            assert seen[0][1].getpixel((10, 5)) == source.getpixel((10, 5))
    finally:
        release.set()
        controller.cancel()
        owner.deleteLater()


@pytest.mark.parametrize('ratio', [1.0, 1.25, 2.0])
@pytest.mark.parametrize('foreground', [0, 255], ids=['black-glyph', 'white-glyph'])
@pytest.mark.parametrize('format', [QtGui.QImage.Format_RGBA8888, QtGui.QImage.Format_ARGB32_Premultiplied],
                         ids=['straight-rgba', 'premultiplied-argb'])
def test_alpha_normalization_preserves_raw_pixels_dimensions_and_dpr(ratio, foreground, format):
    source = QtGui.QImage(12, 8, format)
    source.fill(QtGui.QColor(foreground, foreground, foreground, 0))
    for y in range(2, 6):
        for x in range(4, 8):
            source.setPixelColor(x, y, QtGui.QColor(foreground, foreground, foreground, 255))
    source.setDevicePixelRatio(ratio)
    before = [source.pixelColor(x, y).getRgb() for y in range(8) for x in range(12)]
    result = images.load_image(source)
    assert (result.width(), result.height()) == (12, 8)
    assert result.devicePixelRatio() == ratio
    assert result.pixelColor(0, 0).getRgb() == (255 - foreground,) * 3 + (255,)
    for y in range(8):
        for x in range(12):
            expected = foreground if 4 <= x < 8 and 2 <= y < 6 else 255 - foreground
            assert result.pixelColor(x, y).getRgb() == (expected,) * 3 + (255,)
    assert before == [source.pixelColor(x, y).getRgb() for y in range(8) for x in range(12)]


@pytest.mark.parametrize('foreground', [0, 255], ids=['dark', 'light'])
def test_semtransparent_glyph_is_composited_with_its_original_opacity(foreground):
    source = QtGui.QImage(12, 8, QtGui.QImage.Format_RGBA8888)
    source.fill(QtCore.Qt.transparent)
    source.setPixelColor(5, 4, QtGui.QColor(foreground, foreground, foreground, 128))
    result = images.load_image(source)
    assert result.pixelColor(0, 0).getRgb() == (255 - foreground,) * 3 + (255,)
    expected = 127 if foreground == 0 else 128
    assert abs(result.pixelColor(5, 4).red() - expected) <= 1
    assert result.pixelColor(5, 4).alpha() == 255


def test_faint_background_rgb_does_not_outvote_opaque_dark_foreground():
    source = QtGui.QImage(12, 8, QtGui.QImage.Format_RGBA8888)
    source.fill(QtGui.QColor(255, 255, 255, 1))
    for y in range(2, 6):
        for x in range(4, 8):
            source.setPixelColor(x, y, QtGui.QColor(0, 0, 0, 255))
    result = images.load_image(source)
    assert result.pixelColor(0, 0).getRgb() == (255, 255, 255, 255)
    assert result.pixelColor(5, 4).getRgb() == (0, 0, 0, 255)


def test_fully_transparent_pixels_become_blank_without_resurrecting_hidden_rgb():
    source = QtGui.QImage(12, 8, QtGui.QImage.Format_RGBA8888)
    source.fill(QtCore.Qt.transparent)
    source.setPixelColor(5, 4, QtGui.QColor(255, 0, 0, 0))
    result = images.load_image(source)
    assert all(result.pixelColor(x, y).getRgb() == (255, 255, 255, 255) for y in range(8) for x in range(12))
    assert source.pixelColor(5, 4).getRgb() == (255, 0, 0, 0)


@pytest.mark.parametrize('format', [QtGui.QImage.Format_RGB32, QtGui.QImage.Format_RGBA8888], ids=['rgb', 'opaque-rgba'])
def test_opaque_image_keeps_every_color_and_its_dpr(format):
    source = QtGui.QImage(12, 8, format)
    source.fill(QtGui.QColor(245, 230, 180))
    source.setPixelColor(5, 4, QtGui.QColor(10, 20, 30))
    source.setDevicePixelRatio(1.25)
    result = images.load_image(source)
    assert result.devicePixelRatio() == 1.25
    assert source.size() == result.size()
    assert all(result.pixelColor(x, y) == source.pixelColor(x, y) for y in range(8) for x in range(12))


def png_with_late_exif(path, exif):
    source = corners()
    stream = io.BytesIO()
    source.save(stream, format='PNG')
    raw = stream.getvalue()
    position = 8
    while raw[position + 4:position + 8] != b'IEND':
        position += 12 + int.from_bytes(raw[position:position + 4], 'big')
    kind = b'eXIf'
    chunk = struct.pack('>I', len(exif)) + kind + exif + struct.pack('>I', zlib.crc32(kind + exif))
    path.write_bytes(raw[:position] + chunk + raw[position:])
    return source


@pytest.mark.parametrize('orientation', range(1, 9))
def test_png_exif_after_idat_is_honored_without_a_second_pillow_decode(tmp_path, monkeypatch, orientation):
    exif = Image.Exif()
    exif[274] = orientation
    path = tmp_path / 'late-exif.png'
    source = png_with_late_exif(path, exif.tobytes()[6:])
    monkeypatch.setattr(Image, 'open', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('second image decode')))
    expected = source.transpose(TRANSPOSE[orientation]) if orientation in TRANSPOSE else source
    assert_corners(images.load_image(path), expected)


@pytest.mark.parametrize('metadata', [b'', b'II*\x00\xff\xff\xff\x7f'], ids=['empty', 'invalid-ifd-offset'])
def test_optional_corrupt_png_exif_never_rejects_readable_pixels(tmp_path, metadata):
    path = tmp_path / 'optional-bad-exif.png'
    source = png_with_late_exif(path, metadata)
    assert_corners(images.load_image(path), source)


@pytest.mark.parametrize('metadata', [b'broken', b'Exif\x00\x00bad'], ids=['not-tiff', 'bad-prefixed-tiff'])
def test_qt_rejected_corrupt_png_remains_invalid(tmp_path, metadata):
    path = tmp_path / 'qt-rejected-exif.png'
    png_with_late_exif(path, metadata)
    with pytest.raises(ValueError, match='invalid'):
        images.load_image(path)


@pytest.mark.parametrize('error', [OSError, ValueError, OverflowError, RuntimeError])
def test_optional_exif_metadata_failure_keeps_otherwise_readable_png(tmp_path, monkeypatch, error):
    exif = Image.Exif()
    exif[274] = 6
    path = tmp_path / 'readable-metadata-fault.png'
    source = png_with_late_exif(path, exif.tobytes()[6:])
    def fail(*_args):
        raise error('synthetic optional metadata failure')
    monkeypatch.setattr(Image.Exif, 'load', fail)
    assert_corners(images.load_image(path), source)
