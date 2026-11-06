"""Memory MIME and isolated OCR admission ordering, without desktop I/O."""
from threading import Thread
from types import SimpleNamespace

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

import image_input as images


def picture():
    image = QtGui.QImage(20, 10, QtGui.QImage.Format_RGB32)
    image.fill(QtCore.Qt.white)
    return image


def mime_payload(tmp_path, kind):
    mime = QtCore.QMimeData()
    if kind in ('image', 'mixed'):
        mime.setImageData(picture())
    if kind in ('file', 'mixed'):
        mime.setUrls([QtCore.QUrl.fromLocalFile(str(tmp_path / 'document.txt'))])
    mime.setText('Do not replace the draft')
    return mime


@pytest.mark.parametrize('kind', ['image', 'file', 'mixed'])
@pytest.mark.parametrize('operation', ['drag', 'drop'])
def test_read_only_editor_cannot_admit_an_attachment_drop(tmp_path, kind, operation):
    editor = images.ImageInputTextEdit()
    image_requests, file_requests = [], []
    editor.image_requested.connect(image_requests.append)
    editor.file_requested.connect(file_requests.append)
    editor.setPlainText('Preserved draft')
    editor.setReadOnly(True)
    mime = mime_payload(tmp_path, kind)
    if operation == 'drag':
        event = QtGui.QDragEnterEvent(QtCore.QPoint(3, 3), QtCore.Qt.CopyAction, mime,
                                      QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        editor.dragEnterEvent(event)
    else:
        event = QtGui.QDropEvent(QtCore.QPointF(3, 3), QtCore.Qt.CopyAction, mime,
                                QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        editor.dropEvent(event)
    try:
        assert image_requests == [] and file_requests == []
        assert not event.isAccepted()
        assert editor.toPlainText() == 'Preserved draft'
    finally:
        editor.deleteLater()


@pytest.mark.parametrize('pixmap', [False, True])
def test_clipboard_pixel_limit_is_checked_before_copying_or_converting_pixels(monkeypatch, pixmap):
    mime = QtCore.QMimeData()
    mime.setImageData(QtGui.QPixmap.fromImage(picture()) if pixmap else picture())
    copies, conversions = [], []
    copy = QtGui.QImage.copy
    convert = QtGui.QPixmap.toImage
    monkeypatch.setattr(images, 'MAX_PIXELS', 100)

    def copied(image, *args):
        copies.append(image.size())
        return copy(image, *args)

    def converted(image, *args):
        conversions.append(image.size())
        return convert(image, *args)

    monkeypatch.setattr(QtGui.QImage, 'copy', copied)
    monkeypatch.setattr(QtGui.QPixmap, 'toImage', converted)
    payload = images.image_from_mime(mime)
    with pytest.raises(ValueError, match='large'):
        images.load_image(payload)
    assert copies == [] and conversions == []


def test_valid_mixed_mime_keeps_image_priority_and_an_owned_pixel_snapshot(tmp_path):
    mime = mime_payload(tmp_path, 'mixed')
    payload = images.image_from_mime(mime)
    assert isinstance(payload, QtGui.QImage)
    source = mime.imageData()
    source.fill(QtCore.Qt.red)
    assert payload.pixelColor(1, 1) == QtGui.QColor('white')
    assert mime.text() == 'Do not replace the draft'


@pytest.mark.parametrize('pixmap', [False, True])
@pytest.mark.parametrize('operation', ['paste', 'drop'])
def test_oversized_mime_uses_the_existing_large_error_then_accepts_a_small_retry(monkeypatch, pixmap, operation):
    editor = images.ImageInputTextEdit()
    owner = QtCore.QObject()
    controller = images.ImageImportController(owner)
    jobs, failed, ready, busy = [], [], [], []
    controller.failed.connect(failed.append)
    controller.ready.connect(lambda *args: ready.append(args))
    controller.busy_changed.connect(busy.append)
    editor.image_requested.connect(lambda payload: controller.start(payload, {}, 'en', 'ru'))
    monkeypatch.setattr(images, 'MAX_PIXELS', 100)
    monkeypatch.setattr(images.threading, 'Thread',
                        lambda *, target, **_kwargs: SimpleNamespace(start=lambda: jobs.append(target)))

    def recognize(payload, *_args):
        images.load_image(payload)
        return 'Small image text', None

    monkeypatch.setattr(images, 'recognize_image', recognize)
    mime = QtCore.QMimeData()
    mime.setImageData(QtGui.QPixmap.fromImage(picture()) if pixmap else picture())
    try:
        if operation == 'paste':
            editor.insertFromMimeData(mime)
        else:
            event = QtGui.QDropEvent(QtCore.QPointF(3, 3), QtCore.Qt.CopyAction, mime,
                                    QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
            editor.dropEvent(event)
            assert event.isAccepted()
        assert controller.busy and len(jobs) == 1
        jobs[-1]()
        assert failed == ['large'] and not ready and not controller.busy
        small = QtGui.QImage(5, 5, QtGui.QImage.Format_RGB32)
        small.fill(QtCore.Qt.white)
        mime.setImageData(small)
        editor.insertFromMimeData(mime)
        jobs[-1]()
        assert ready == [('Small image text', None)] and not controller.busy
        assert failed == ['large']
        assert busy == [True, False, True, False]
    finally:
        controller.cancel()
        owner.deleteLater()
        editor.deleteLater()


def test_old_queued_ocr_does_not_complete_a_newer_failed_admission_or_its_retry(monkeypatch):
    owner = QtCore.QObject()
    controller = images.ImageImportController(owner)
    jobs, ready, failed, busy = [], [], [], []
    controller.ready.connect(lambda *args: ready.append(args))
    controller.failed.connect(failed.append)
    controller.busy_changed.connect(busy.append)
    monkeypatch.setattr(images, 'recognize_image', lambda payload, *_args: (payload, None))
    monkeypatch.setattr(images.threading, 'Thread',
                        lambda *, target, **_kwargs: SimpleNamespace(start=lambda: jobs.append(target)))
    try:
        assert controller.start('Old image text', {}, 'en', 'ru')
        worker = Thread(target=jobs[0])
        worker.start()
        worker.join(3)
        assert not worker.is_alive() and not ready
        controller.cancel()
        with monkeypatch.context() as fault:
            fault.setattr(images.threading, 'Thread', lambda **_kwargs: (_ for _ in ()).throw(RuntimeError('synthetic admission refusal')))
            assert not controller.start('Refused image', {}, 'en', 'ru')
        assert not controller.busy and len(failed) == 1
        assert controller.start('Current retry text', {}, 'en', 'ar')
        QtWidgets.QApplication.processEvents()
        assert controller.busy and ready == [] and len(failed) == 1
        jobs[-1]()
        assert ready == [('Current retry text', None)]
        assert not controller.busy
        assert busy == [True, False, True, False, True, False]
    finally:
        controller.cancel()
        owner.deleteLater()


@pytest.mark.parametrize('missing', [False, True])
def test_file_failure_restores_admission_and_the_following_image_uses_its_own_pair(tmp_path, monkeypatch, missing):
    owner = QtCore.QObject()
    controller = images.ImageImportController(owner)
    jobs, ready, failed, calls = [], [], [], []
    path = tmp_path / 'broken.png'
    if not missing:
        path.write_bytes(b'not image data')

    def recognize(payload, config, source, target, _cancel):
        calls.append((source, target))
        if payload == path:
            images.load_image(payload)
        return 'Recovered image text', None

    controller.ready.connect(lambda *args: ready.append(args))
    controller.failed.connect(failed.append)
    monkeypatch.setattr(images, 'recognize_image', recognize)
    monkeypatch.setattr(images.threading, 'Thread',
                        lambda *, target, **_kwargs: SimpleNamespace(start=lambda: jobs.append(target)))
    try:
        assert controller.start(path, {}, 'en', 'ru')
        jobs[-1]()
        assert failed == ['invalid'] and not controller.busy
        assert controller.start(picture(), {}, 'ar', 'en')
        jobs[-1]()
        assert ready == [('Recovered image text', None)]
        assert calls == [('en', 'ru'), ('ar', 'en')]
        assert not controller.busy
    finally:
        controller.cancel()
        owner.deleteLater()
