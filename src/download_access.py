"""Nonblocking, bounded checks for the actual component-download path."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from urllib.parse import urlparse

from PyQt5 import QtCore, QtWidgets
from engine_center import text


def sources(catalog=None):
    from component_catalog import CATALOG_URL
    urls = [('catalog', CATALOG_URL + 'timestamp.json'),
            ('api', 'https://api.github.com/repos/jabrailkhalil/clickntranslate-components')]
    # Use a real small release file, so redirects to GitHub's asset CDN are
    # checked as well. An HTTP HEAD never downloads the package payload.
    artifacts = (catalog or {}).get('artifacts', {})
    candidates = [(item.get('size', float('inf')), url) for item in artifacts.values()
                  for url in item.get('urls', ())
                  if url.startswith('https://github.com/jabrailkhalil/clickntranslate-components/releases/download/')]
    if candidates:
        urls.append(('files', min(candidates)[1]))
    else:
        urls.append(('files', None))
    return urls


def probe(url, *, head=None, clock=time.monotonic):
    import requests
    if url is None:
        return {'status': 'unchecked', 'code': None, 'ms': 0, 'host': ''}
    start = clock()
    try:
        with (head or requests.head)(url, timeout=(3, 5), allow_redirects=True,
                                     headers={'User-Agent': 'ClicknTranslate download check'}) as response:
            code = int(response.status_code)
            status = 'ok' if 200 <= code < 400 else 'restricted' if code in (401, 403, 429) else 'failed'
            if code == 405:
                status = 'unchecked'  # A rejected HEAD is not proof that GET/downloads fail.
            host = urlparse(response.url).hostname or ''
            source = urlparse(url).hostname
            allowed = ({'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}
                       if source == 'github.com' else {source})
            if status == 'ok' and host not in allowed:
                status = 'restricted'
            return {'status': status, 'code': code, 'ms': round((clock()-start)*1000),
                    'host': host}
    except requests.RequestException:
        return {'status': 'failed', 'code': None, 'ms': round((clock()-start)*1000), 'host': ''}


class DownloadAccessPage(QtWidgets.QWidget):
    completed = QtCore.pyqtSignal(object)

    def __init__(self, lang, parent=None):
        super().__init__(parent)
        self.lang, self._busy = lang, False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)
        title = QtWidgets.QLabel(text(lang, 'network_title'), self)
        title.setStyleSheet('font-size:16px; font-weight:600;')
        layout.addWidget(title)
        self.description = QtWidgets.QLabel(text(lang, 'network_intro'), self)
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.rows = {}
        for key, _url in sources():
            row = QtWidgets.QFrame(self)
            row.setObjectName('downloadAccessRow')
            form = QtWidgets.QVBoxLayout(row)
            form.setContentsMargins(10, 8, 10, 8)
            caption = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(text(lang, key), row)
            result = QtWidgets.QLabel(text(lang, 'unchecked'), row)
            result.setTextFormat(QtCore.Qt.PlainText)
            caption.addWidget(label)
            caption.addStretch()
            caption.addWidget(result)
            form.addLayout(caption)
            address = QtWidgets.QLabel('', row)
            address.setTextFormat(QtCore.Qt.PlainText)
            address.setWordWrap(True)
            address.setStyleSheet('font-size:11px;')
            address.setLayoutDirection(QtCore.Qt.LeftToRight)
            form.addWidget(address)
            layout.addWidget(row)
            self.rows[key] = (result, address)
        layout.addStretch()
        self.check = QtWidgets.QPushButton(text(lang, 'again'), self)
        self.check.setFixedHeight(30)
        self.check.clicked.connect(lambda: self.start(self._catalog))
        layout.addWidget(self.check)
        self._catalog = None
        self.completed.connect(self._finish)

    def start(self, catalog=None):
        if self._busy:
            return
        self._catalog, self._busy = catalog, True
        self.check.setEnabled(False)
        checks = sources(catalog)
        for key, url in checks:
            self.rows[key][0].setText(text(self.lang, 'checking' if url else 'unchecked'))
            self.rows[key][1].setText(urlparse(url).hostname if url else '')
            self.rows[key][1].setToolTip(url or '')

        def unavailable():
            return {key: {'status': 'failed' if url else 'unchecked',
                          'code': None, 'ms': 0, 'host': ''} for key, url in checks}

        completion_lock = threading.Lock()
        completed = False
        def complete(results):
            nonlocal completed
            with completion_lock:
                if completed:
                    return
                completed = True
            try:
                self.completed.emit(results)
            except RuntimeError:
                pass  # Closing the center never leaves a callback to a deleted widget.

        def worker():
            results = unavailable()
            try:
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {}
                    for key, url in checks:
                        try:
                            futures[key] = executor.submit(probe, url)
                        except Exception:
                            pass  # Other sources may still be checkable.
                    for key, future in futures.items():
                        try:
                            results[key] = future.result()
                        except Exception:
                            pass
            except Exception:
                pass  # A failed pool must also release the check button.
            complete(results)
        try:
            threading.Thread(target=worker, name='DownloadAccessCheck', daemon=True).start()
        except Exception:
            complete(unavailable())

    @QtCore.pyqtSlot(object)
    def _finish(self, results):
        self._busy = False
        self.check.setEnabled(True)
        for key, result in results.items():
            label, address = self.rows[key]
            caption = text(self.lang, result['status'])
            if result['code'] is not None and result['status'] != 'ok':
                caption += ' · HTTP ' + str(result['code'])
            label.setText(caption if result['status'] == 'unchecked' else
                          caption + f" · {result['ms']} " + text(self.lang, 'ms'))
            if result['host']:
                address.setText(result['host'])
        self.description.setText(text(self.lang, 'network_intro'))
