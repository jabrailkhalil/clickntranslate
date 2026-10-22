"""Cloud recognition runs off the GUI thread; stale sessions are ignored by OCR."""
from PyQt5.QtCore import QThread, pyqtSignal


class ApiOCRWorker(QThread):
    result_ready = pyqtSignal(object)
    failed = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, provider, image, source, target, config):
        super().__init__()
        import copy
        self.provider, self.image = provider, image.copy()
        self.source, self.target = source, target
        self.config = copy.deepcopy(config)

    def cancel(self):
        self.requestInterruption()

    def run(self):
        from api_providers import recognize, VisionResult, display_error
        from translater import translate_text, TranslationCancelledError
        try:
            result = recognize(self.provider, self.image, self.source, self.target,
                               self.config, self.isInterruptionRequested)
            if self.target and result.source.strip() and result.translation is None:
                result = VisionResult(result.source, translate_text(result.source, self.source, self.target,
                    engine=self.config.get('translator_engine', 'google'), cancel_callback=self.isInterruptionRequested))
            if not self.isInterruptionRequested():
                self.result_ready.emit(result)
        except TranslationCancelledError:
            pass
        except Exception as error:
            if not self.isInterruptionRequested():
                self.failed.emit(display_error(error, self.config.get('interface_language', 'en')))
