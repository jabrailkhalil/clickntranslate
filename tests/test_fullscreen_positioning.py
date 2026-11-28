"""Fullscreen replacements keep OCR coordinates, including scaled captures."""
import os
import threading
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets, sip
import ocr
import translater
from qt_layout_test_support import ensure_layout_fonts
from PyQt5.QtTest import QTest


@pytest.fixture(scope='module', autouse=True)
def application():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ensure_layout_fonts(app)
    yield app


@pytest.fixture
def controlled_overlay(application, monkeypatch):
    from PyQt5 import QtGui
    pixels = QtGui.QPixmap(160, 90)
    pixels.fill(QtCore.Qt.white)
    monkeypatch.setattr(ocr, 'grab_screen_pixmap', lambda *_: pixels)
    monkeypatch.setattr(ocr, 'installed_ocr_language_codes', lambda **_: ['en', 'ru'])
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: dict(
        interface_language='en', translator_engine='Google',
        fullscreen_translate_from='en', fullscreen_translate_to='ru'))
    monkeypatch.setattr(ocr, '_write_ocr_config_updates', mock.Mock())
    monkeypatch.setattr(ocr, 'notify_current_activity', mock.Mock())
    monkeypatch.setattr(ocr, 'save_translation_history', mock.Mock())
    with mock.patch.object(QtCore.QTimer, 'singleShot'):
        overlay = ocr.FullScreenTranslateOverlay()
    yield overlay
    if not sip.isdeleted(overlay):
        overlay.close()
        application.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_switching_language_discards_old_fullscreen_results_before_debounce(controlled_overlay, monkeypatch):
    overlay = controlled_overlay
    start = mock.Mock()
    monkeypatch.setattr(overlay, '_start_ocr', start)
    overlay._restart_translation_from_controls()
    old_id = overlay._translation_run_id
    stale = [(QtCore.QRectF(10, 15, 80, 20), 'Source', 'Old translation')]
    overlay.target_lang_combo.setCurrentIndex(overlay.target_lang_combo.findData('es'))
    overlay.target_lang_combo.setCurrentIndex(overlay.target_lang_combo.findData('de'))
    assert overlay._rerun_timer.isActive() and start.call_count == 1
    overlay._translation_result_ready.emit(old_id, stale, '')
    assert not overlay.translated_blocks and overlay.loading
    ocr.save_translation_history.assert_not_called()

    overlay._rerun_timer.stop()
    overlay._rerun_timer.timeout.emit()
    assert start.call_count == 2
    assert start.call_args.args == (overlay._translation_run_id, 'en', 'de')


def test_failed_fullscreen_worker_admission_allows_next_language(controlled_overlay, monkeypatch):
    overlay = controlled_overlay

    class Worker(QtCore.QObject):
        result_ready = QtCore.pyqtSignal(object)
        finished = QtCore.pyqtSignal()

    failed, current = Worker(), Worker()
    failed.start = mock.Mock(side_effect=RuntimeError('worker unavailable'))
    failed.requestInterruption = mock.Mock()
    current.start = mock.Mock()
    current.requestInterruption = mock.Mock()
    monkeypatch.setattr(ocr, 'create_position_ocr_worker', mock.Mock(side_effect=[failed, current]))
    overlay._restart_translation_from_controls()
    assert not overlay.loading and overlay.error_message
    overlay.target_lang_combo.setCurrentIndex(overlay.target_lang_combo.findData('de'))
    overlay._rerun_timer.stop()
    overlay._rerun_timer.timeout.emit()
    current.start.assert_called_once_with()
    assert overlay._ocr_workers == {current}
    current.finished.emit()


def test_failed_windows_bitmap_conversion_completes_with_an_initialization_error(monkeypatch):
    from PyQt5 import QtGui
    image = QtGui.QImage(32, 16, QtGui.QImage.Format_RGB32)
    image.fill(QtCore.Qt.white)
    monkeypatch.setattr(ocr, '_position_ocr_bitmap', lambda *_: None)
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: {'interface_language': 'en'})
    worker = ocr.FullScreenOCRWorker(image, 'en', engine='windows')
    delivered = []
    worker.result_ready.connect(delivered.append)
    worker.run()
    assert delivered == [[]]
    assert worker.error_message == ocr.ocr_ui_text('en', 'ocr_init_failed')


def test_unchanged_fullscreen_repaints_reuse_the_layout_and_identical_pixels(controlled_overlay, monkeypatch):
    from PyQt5 import QtGui
    overlay = controlled_overlay
    overlay.tgt_lang = 'ar'
    overlay.resize(640, 360)
    blocks = [(QtCore.QRectF(18, 36 + row * 26, 92, 18), 'Source', 'بغداد ' + str(row)) for row in range(6)]
    overlay._apply_translation_result(overlay._translation_run_id, blocks, '')
    layout = mock.Mock(wraps=overlay._translation_block_layout)
    monkeypatch.setattr(overlay, '_translation_block_layout', layout)

    def render():
        image = QtGui.QImage(overlay.size(), QtGui.QImage.Format_ARGB32_Premultiplied)
        image.fill(QtCore.Qt.transparent)
        overlay.render(image, flags=QtWidgets.QWidget.DrawWindowBackground)
        return image

    first = render()
    assert layout.call_count == len(blocks)
    assert render() == first
    assert layout.call_count == len(blocks)
    overlay.resize(550, 340)
    render()
    assert layout.call_count == 2 * len(blocks)
    changed = [(rect, original, 'A new translation') for rect, original, _text in blocks]
    before = render()
    overlay._apply_translation_result(overlay._translation_run_id, changed, '')
    assert render() != before
    assert layout.call_count == 3 * len(blocks)
    old_dpi = overlay.logicalDpiX()
    monkeypatch.setattr(overlay, 'logicalDpiX', lambda: old_dpi + 24)
    render()
    assert layout.call_count == 4 * len(blocks)


def test_indexed_layout_matches_the_full_obstacle_scan_across_fractional_rows(controlled_overlay):
    overlay = controlled_overlay
    overlay.resize(770, 500)
    rects = [QtCore.QRectF(18 + col * 144.25, 26.25 + row * 29.8, 81.5, 15.3)
             for row in range(14) for col in range(5)]
    rects.extend([QtCore.QRectF(421.5, 25.5, 30.2, 145.5), QtCore.QRectF(-22, 30.1, 92, 16),
                  QtCore.QRectF(600, 169, 50, 220), QtCore.QRectF(901, -220, 45, 31),
                  QtCore.QRectF(9, 31.9, 75, 13.2), QtCore.QRectF(10, 32, 0, 15)])
    blocks = [(rect, 'Source', ('ترجمة عربية طويلة', 'A longer translation')[i % 2]) for i, rect in enumerate(rects)]
    occupied, expected = [], []
    for i, (rect, source, text) in enumerate(blocks):
        layout = overlay._translation_block_layout(rect, source, text, occupied=occupied,
                                                   obstacles=rects[:i] + rects[i + 1:])
        occupied.append(layout[0])
        expected.append((rect, source, text, layout))

    counts = []

    def layout_with_neighbours(rect, source, text, *, obstacles):
        counts.append(len(obstacles))
        return overlay._translation_block_layout(rect, source, text, obstacles=obstacles)

    assert ocr._layout_screen_translation_blocks(blocks, overlay.height(), layout_with_neighbours) == expected
    assert sum(counts) < len(blocks) * (len(blocks) - 1) // 2


def test_fullscreen_provider_finishing_after_close_exits_without_touching_the_deleted_overlay(
        application, controlled_overlay, monkeypatch):
    overlay = controlled_overlay
    entered, release = threading.Event(), threading.Event()
    errors = []

    def translate(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return 'Late answer'

    def run():
        try:
            overlay._translate_all(overlay._translation_run_id, [(0, 0, 40, 20, 'Source')], 'en', 'ru')
        except Exception as exc:
            errors.append(exc)

    monkeypatch.setattr(translater, 'translate_text', translate)
    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert entered.wait(3)
        overlay.close()
        application.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        assert sip.isdeleted(overlay)
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive() and not errors


def test_right_click_closes_fullscreen_translation_and_releases_mode(application, monkeypatch):
    import mode_coordinator
    from PyQt5 import QtGui
    screenshot = QtGui.QPixmap(800, 600)
    screenshot.fill(QtCore.Qt.black)
    monkeypatch.setattr(ocr, 'grab_screen_pixmap', lambda *_args: screenshot)
    release = mock.Mock()
    monkeypatch.setattr(mode_coordinator, 'release_mode', release)
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: {
        'interface_language': 'ru', 'translator_engine': 'Google',
        'fullscreen_translate_from': 'en', 'fullscreen_translate_to': 'ru'})
    monkeypatch.setattr(ocr, 'installed_ocr_language_codes', lambda **kw: ['en', 'ru'])
    monkeypatch.setattr(ocr.FullScreenTranslateOverlay, '_restart_translation_from_controls', lambda self: None)
    overlay = ocr.FullScreenTranslateOverlay()
    overlay.show()
    application.processEvents()
    QTest.mouseClick(overlay, QtCore.Qt.RightButton, pos=overlay.rect().center())
    assert not overlay.isVisible()
    release.assert_called_once_with('fullscreen')
    assert ocr._fullscreen_overlay_ref is None


@pytest.mark.parametrize('scale_x,scale_y', [(1, 1), (1.25, 1.25), (1.5, 1.5), (2, 2), (2, 1.5)])
def test_translations_keep_separate_screen_positions(scale_x, scale_y, monkeypatch):
    signal = mock.Mock()
    overlay = SimpleNamespace(_ocr_scale_x=scale_x, _ocr_scale_y=scale_y,
                              _translation_run_id=3, _translation_result_ready=signal)
    lines = [(40, 80, 120, 24, 'One'), (430, 80, 120, 24, 'Two'), (430, 380, 120, 24, 'Three')]
    pixels = [(x * scale_x, y * scale_y, w * scale_x, h * scale_y, text) for x, y, w, h, text in lines]
    translate = mock.Mock(side_effect=lambda text, *a, **kw: text.replace('One', 'Один').replace('Two', 'Два').replace('Three', 'Три'))
    monkeypatch.setattr(translater, 'translate_text', translate)
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: {'translator_engine': 'Lingva'})
    ocr.FullScreenTranslateOverlay._translate_all(overlay, 3, pixels, 'en', 'ru')
    run_id, blocks, error = signal.emit.call_args.args
    assert run_id == 3 and not error
    assert [value[2] for value in blocks] == ['Один', 'Два', 'Три']
    assert [value[0].getRect() for value in blocks] == [tuple(row[:4]) for row in lines]
    assert translate.call_args.kwargs['engine'] == 'Lingva'
    assert not translate.call_args.kwargs['cancel_callback']()
    overlay._translation_run_id += 1
    assert translate.call_args.kwargs['cancel_callback']()


@pytest.mark.parametrize('rect', [(-300, 60, 100, 20), (850, 60, 100, 20),
                                 (100, 550, 100, 20), (100, -60, 100, 20),
                                 (float('nan'), 60, 100, 20), (20, 60, 0, 20)])
def test_invalid_ocr_boxes_never_become_text_at_top_left(rect):
    overlay = SimpleNamespace(width=lambda: 800, height=lambda: 500)
    layout = ocr.FullScreenTranslateOverlay._translation_block_layout(
        overlay, QtCore.QRectF(*rect), 'Original', 'Translation')
    assert layout[0].isEmpty()
    painter = mock.Mock()
    ocr.FullScreenTranslateOverlay._paint_block(overlay, painter, QtCore.QRectF(*rect),
                                               'Original', 'Translation', layout=layout)
    painter.drawText.assert_not_called()
    painter.drawRect.assert_not_called()


def test_malformed_ocr_coordinates_are_excluded_before_translation():
    assert ocr._group_screen_ocr_lines([
        (float('nan'), 20, 20, 20, 'invalid'),
        (20, float('inf'), 20, 20, 'invalid'),
        (20, 40, -10, 20, 'invalid'),
        (200, 80, 120, 24, 'Visible'),
    ]) == [(200, 80, 120, 24, 'Visible')]


@pytest.mark.parametrize('angle,expected', [(0, (80, 40, 30, 10)),
                                          (None, (80, 40, 30, 10)),
                                          (90, (100, 30, 10, 30)),
                                          (-90, (90, 40, 10, 30))])
def test_windows_deskewed_boxes_return_to_original_image(angle, expected):
    word = SimpleNamespace(text='Word', bounding_rect=SimpleNamespace(x=80, y=40, width=30, height=10))
    result = SimpleNamespace(text_angle=angle, lines=[SimpleNamespace(words=[word])])
    lines = ocr._windows_ocr_lines_in_image(result, 200, 100)
    assert lines[0][:4] == pytest.approx(expected)
    assert lines[0][4] == 'Word'
