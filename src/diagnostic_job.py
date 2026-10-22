"""Build diagnostic ZIPs off the Qt thread and deliver one completion signal."""
from PyQt5.QtCore import QObject, pyqtSignal
import threading


class DiagnosticJob(QObject):
    finished = pyqtSignal(object, str)

    def __init__(self, parent, **options):
        super().__init__(parent)
        self.options = options
        self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._run, name='ClicknTranslate diagnostics', daemon=True).start()

    def _run(self):
        from diagnostics import create_bug_report, _redact
        path, error = None, ''
        try:
            path = create_bug_report(**self.options)
        except Exception as failure:
            error = _redact(failure)
        self.running = False
        try:
            self.finished.emit(path, error)
        except RuntimeError:
            pass  # Application was closed while the local ZIP was being made.
