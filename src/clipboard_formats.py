"""Keep the native representations of a clipboard item across a temporary text copy."""

from concurrent.futures import Future, TimeoutError

from PyQt5 import QtCore, QtGui, QtWidgets


MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024  # Same byte budget as a desktop image import.


def _check_types(kinds):
    for kind in kinds:
        name = str(kind).lower()
        if ('filegroupdescriptor' in name or 'filecontents' in name
                or ('file' in name and 'promise' in name)):
            raise ValueError('Virtual file contents must remain with their clipboard owner')


def _remaining_bytes(remaining, size):
    if size > remaining:
        raise ValueError('Clipboard representations exceed the in-memory budget')
    return remaining - size


def capture_cocoa_items(board):
    """Keep each pasteboard item and type separately, including an empty data payload."""
    source = [(item, list(item.types())) for item in board.pasteboardItems() or ()]
    _check_types(kind for _item, kinds in source for kind in kinds)
    if len(source) <= 1 and all(str(kind) in ('public.utf8-plain-text', 'NSStringPboardType')
                                for _item, kinds in source for kind in kinds):
        return None
    items = []
    remaining = MAX_SNAPSHOT_BYTES
    for item, kinds in source:
        representations = []
        for kind in kinds:
            value = item.dataForType_(kind)
            if value is None:
                raise ValueError('Pasteboard representation unavailable')
            remaining = _remaining_bytes(remaining, value.length())
            representations.append((str(kind), bytes(value)))
        items.append(representations)
    return items


def restore_cocoa_items(board, records, still_owned):
    from AppKit import NSPasteboardItem
    from Foundation import NSData

    items = []
    for record in records:
        item = NSPasteboardItem.alloc().init()
        for kind, value in record:
            data = NSData.dataWithBytes_length_(value, len(value))
            if not item.setData_forType_(data, kind):
                return False
        items.append(item)
    if not still_owned():
        return False
    board.clearContents()
    return not items or bool(board.writeObjects_(items))


class ClipboardFormats(QtCore.QObject):
    """Read delayed native formats and publish their copies on Qt's GUI thread."""

    _requested = QtCore.pyqtSignal(object)

    def __init__(self, app):
        super().__init__(app)
        self._requested.connect(self._execute, QtCore.Qt.QueuedConnection)
        self._cocoa = app.platformName() == 'cocoa'
        self._windows = app.platformName() == 'windows'

    @QtCore.pyqtSlot(object)
    def _execute(self, operation):
        operation()

    def _on_gui(self, operation):
        if QtCore.QThread.currentThread() == self.thread():
            return operation()
        pending = Future()

        def execute():
            if pending.set_running_or_notify_cancel():
                try:
                    pending.set_result(operation())
                except Exception as error:
                    pending.set_exception(error)

        self._requested.emit(execute)
        try:
            return pending.result(timeout=5)
        except TimeoutError:
            if pending.cancel():
                raise RuntimeError('The clipboard GUI request was not delivered') from None
            return pending.result()

    def capture(self):
        return self._on_gui(self._capture)

    def _capture(self):
        if self._cocoa:
            from AppKit import NSPasteboard
            return capture_cocoa_items(NSPasteboard.generalPasteboard())
        mime = QtWidgets.QApplication.clipboard().mimeData()
        kinds = mime.formats() if mime is not None else []
        if not any(kind != 'text/plain' for kind in kinds):
            return None
        _check_types(kinds)
        formats = []
        image = None
        remaining = MAX_SNAPSHOT_BYTES
        for kind in kinds:
            if kind == 'application/x-qt-image':
                value = mime.imageData()
                if isinstance(value, QtGui.QPixmap):
                    value = value.toImage()
                if not isinstance(value, QtGui.QImage) or value.isNull():
                    raise ValueError('Clipboard image unavailable')
                remaining = _remaining_bytes(remaining, value.sizeInBytes())
                image = QtGui.QImage(value)  # Implicitly shared until either image is written.
            else:
                value = mime.data(kind)
                if value.isNull():
                    raise ValueError('Clipboard representation unavailable')
                remaining = _remaining_bytes(remaining, value.size())
                # Qt 5 reads registered Windows formats through this wrapper, but
                # registers the name supplied to setData() verbatim when writing.
                prefix = 'application/x-qt-windows-mime;value="'
                if self._windows and kind.lower().startswith(prefix):
                    if not kind.endswith('"'):
                        raise ValueError('Indexed Windows clipboard formats must remain with their owner')
                    kind = kind[len(prefix):-1]
                formats.append((kind, bytes(value)))
        return formats, image

    def restore(self, snapshot, still_owned):
        return self._on_gui(lambda: self._restore(snapshot, still_owned))

    def _restore(self, snapshot, still_owned):
        if self._cocoa:
            from AppKit import NSPasteboard
            return restore_cocoa_items(NSPasteboard.generalPasteboard(), snapshot, still_owned)
        formats, image = snapshot
        mime = QtCore.QMimeData()
        for kind, value in formats:
            mime.setData(kind, value)
        if image is not None:
            mime.setImageData(image)
        if not still_owned():
            return False
        QtWidgets.QApplication.clipboard().setMimeData(mime)
        return True


def application_clipboard_formats():
    """Create once on the GUI thread, before the selection worker starts."""
    app = QtWidgets.QApplication.instance()
    if app is None or app.closingDown():
        return None
    service = getattr(app, '_selection_clipboard_formats', None)
    if service is None and QtCore.QThread.currentThread() == app.thread():
        service = app._selection_clipboard_formats = ClipboardFormats(app)
    return service
