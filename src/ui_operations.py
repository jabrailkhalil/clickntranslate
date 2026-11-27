"""Lazy file work and short GUI stages, with one delayed in-window indicator."""
import logging
import threading
import time
from contextlib import contextmanager
from PyQt5 import QtCore, QtGui, QtWidgets, sip

from classic_style import classic_palette


# One label per action, shared by the title-bar indicator and accessibility.
TEXT = {
    'en': ('Applying theme…', 'Reading settings…', 'Exporting settings…', 'Applying settings…'),
    'ru': ('Применяю тему…', 'Читаю настройки…', 'Экспортирую настройки…', 'Применяю настройки…'),
    'es': ('Aplicando tema…', 'Leyendo ajustes…', 'Exportando ajustes…', 'Aplicando ajustes…'),
    'de': ('Design anwenden…', 'Einstellungen lesen…', 'Einstellungen exportieren…', 'Einstellungen anwenden…'),
    'fr': ('Application du thème…', 'Lecture des réglages…', 'Export des réglages…', 'Application des réglages…'),
    'zh': ('正在应用主题…', '正在读取设置…', '正在导出设置…', '正在应用设置…'),
    'pt': ('Aplicando tema…', 'Lendo configurações…', 'Exportando configurações…', 'Aplicando configurações…'),
    'it': ('Applicazione del tema…', 'Lettura delle impostazioni…', 'Esportazione delle impostazioni…', 'Applicazione delle impostazioni…'),
    'ar': ('جارٍ تطبيق المظهر…', 'جارٍ قراءة الإعدادات…', 'جارٍ تصدير الإعدادات…', 'جارٍ تطبيق الإعدادات…'),
    'tr': ('Tema uygulanıyor…', 'Ayarlar okunuyor…', 'Ayarlar dışa aktarılıyor…', 'Ayarlar uygulanıyor…'),
    'hi': ('थीम लागू हो रही है…', 'सेटिंग पढ़ी जा रही हैं…', 'सेटिंग निर्यात हो रही हैं…', 'सेटिंग लागू हो रही हैं…'),
    'id': ('Menerapkan tema…', 'Membaca pengaturan…', 'Mengekspor pengaturan…', 'Menerapkan pengaturan…'),
}
PHASES = {'theme': 0, 'import': 1, 'export': 2, 'settings': 3}

FAILURE_TEXT = {
    'en': 'Could not complete this action.', 'ru': 'Не удалось выполнить действие.',
    'es': 'No se pudo completar esta acción.', 'de': 'Diese Aktion konnte nicht abgeschlossen werden.',
    'fr': 'Impossible de terminer cette action.', 'zh': '无法完成此操作。',
    'pt': 'Não foi possível concluir esta ação.', 'it': 'Impossibile completare questa azione.',
    'ar': 'تعذّر إكمال هذا الإجراء.', 'tr': 'Bu işlem tamamlanamadı.',
    'hi': 'यह कार्रवाई पूरी नहीं हो सकी।', 'id': 'Tindakan ini tidak dapat diselesaikan.',
}


def show_operation_error(owner, error):
    from styled_dialogs import StyledMessageBox
    locale = getattr(owner, 'current_interface_language', 'en')
    label = FAILURE_TEXT.get(locale, FAILURE_TEXT['en'])
    StyledMessageBox.warning(owner, "Click'n'Translate", label+'\n\n'+str(error))


@contextmanager
def hold_content_paint(owner, content=None):
    """Retain the last complete content frame while the title stays live."""
    root = getattr(owner, 'ui_root', owner)
    controller = getattr(owner, '_ui_scale_controller', None)
    widgets = list(dict.fromkeys((getattr(owner, 'central_widget', None), content,
        root if root is not owner else None, getattr(controller, 'view', None),
        *(widget for widget in QtWidgets.QApplication.topLevelWidgets() if widget not in (owner, root)))))
    frozen = [(widget, widget.updatesEnabled()) for widget in widgets
              if widget is not None and not sip.isdeleted(widget) and widget.isVisible()]
    try:
        for widget, _enabled in frozen:
            widget.setUpdatesEnabled(False)
        yield
    finally:
        for widget, enabled in reversed(frozen):
            if not sip.isdeleted(widget):
                widget.setUpdatesEnabled(enabled)


class OperationIndicator(QtWidgets.QWidget):
    def __init__(self, owner):
        self.owner = owner
        # The native child is outside the GraphicsProxy canvas. The entire
        # canvas can retain its cached frame while this small widget animates.
        super().__init__(owner)
        self.setObjectName('operationIndicator')
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.phase = 'settings'
        self.display_theme = None
        self._factor = 1.
        self._animation = QtCore.QTimer(self)
        self._animation.setInterval(50)
        self._animation.timeout.connect(self.update)
        self.hide()

    def label(self):
        locale = getattr(self.owner, 'current_interface_language', 'en')
        return TEXT.get(locale, TEXT['en'])[PHASES[self.phase]]

    def position(self):
        root = getattr(self.owner, 'ui_root', self.owner)
        left, right = 8, root.width()-8
        for name in ('flag_button', 'theme_button', 'document_button', 'help_button',
                     'settings_button', 'minimize_button', 'close_button'):
            button = getattr(self.owner, name, None)
            if button is not None and not sip.isdeleted(button):
                if button.geometry().center().x() < root.width()/2:
                    left = max(left, button.geometry().right()+8)
                else:
                    right = min(right, button.geometry().left()-8)
        width = min(320, max(1, right-left))
        x = left+(right-left-width)//2
        if root is self.owner:
            self._factor = 1.
            self.setGeometry(x, 7, width, 26)
        else:
            from ui_scaling import widget_global_rect
            area = widget_global_rect(root)
            self._factor = area.width()/max(1, root.width())
            origin = self.owner.mapFromGlobal(area.topLeft())
            self.setGeometry(origin.x()+round(x*self._factor), origin.y()+round(7*self._factor),
                             max(1, round(width*self._factor)), max(1, round(26*self._factor)))

    def showEvent(self, event):
        self.position()
        self.setAccessibleName(self.label())
        self._animation.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._animation.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        colors = classic_palette((self.display_theme or getattr(self.owner, 'current_theme', 'Темная')) != 'Светлая')
        painter = QtGui.QPainter(self)
        painter.scale(self._factor, self._factor)
        width, height = self.width()/self._factor, self.height()/self._factor
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(colors['border']), 1))
        painter.setBrush(QtGui.QColor(colors['field']))
        painter.drawRoundedRect(QtCore.QRectF(0, 0, width, height).adjusted(.5, .5, -.5, -.5), 6, 6)
        rtl = self.owner.layoutDirection() == QtCore.Qt.RightToLeft
        ring = QtCore.QRectF(width-24 if rtl else 10, 7, 12, 12)
        painter.setPen(QtGui.QPen(QtGui.QColor(colors['accent_text']), 1.8,
                                 QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.drawArc(ring, -int(time.monotonic()*270)%360*16, 255*16)
        font = QtGui.QFont(self.font())
        font.setPixelSize(12)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(colors['text']))
        text_rect = QtCore.QRectF(8 if rtl else 30, 0, max(0, width-38), height)
        label = QtGui.QFontMetrics(font).elidedText(self.label(), QtCore.Qt.ElideRight, int(text_rect.width()))
        painter.drawText(text_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignAbsolute
                         | (QtCore.Qt.AlignRight if rtl else QtCore.Qt.AlignLeft), label)


class UiOperation(QtCore.QObject):
    worker_result = QtCore.pyqtSignal(int, object, bool)
    DELAY_MS = 600
    INPUT_EVENTS = {QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease,
        QtCore.QEvent.MouseButtonDblClick, QtCore.QEvent.Wheel, QtCore.QEvent.KeyPress,
        QtCore.QEvent.KeyRelease, QtCore.QEvent.Shortcut, QtCore.QEvent.ShortcutOverride,
        QtCore.QEvent.ContextMenu, QtCore.QEvent.TouchBegin, QtCore.QEvent.TouchUpdate,
        QtCore.QEvent.TouchEnd}

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.active = False
        self._finishing = False
        self._revision = 0
        self._steps = None
        self._indicator = None
        self._delay = QtCore.QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.timeout.connect(self._show_indicator)
        self._next = QtCore.QTimer(self)
        self._next.setSingleShot(True)
        self._next.timeout.connect(self._advance)
        self.worker_result.connect(self._receive, QtCore.Qt.QueuedConnection)
        owner.destroyed.connect(self.cancel)

    def start(self, phase, *, work=None, steps=None, done=None, failed=None):
        if self.active or self._finishing or sip.isdeleted(self.owner):
            return False
        if phase not in PHASES:
            raise ValueError('Unknown UI operation phase: '+str(phase))
        self.active = True
        self._started = time.perf_counter()
        self._initial_phase = phase
        self._display_theme = getattr(self.owner, 'current_theme', 'Темная')
        self._revision += 1
        token = self._revision
        self.phase = phase
        self._factory, self._done, self._failed = steps, done, failed
        self._result = None
        self._root = getattr(self.owner, 'ui_root', self.owner)
        self._had_cursor = self._root.testAttribute(QtCore.Qt.WA_SetCursor)
        self._cursor = self._root.cursor()
        self._root.setCursor(QtCore.Qt.WaitCursor)
        # Gate input without disabling/repolishing hundreds of controls or
        # turning the saved frame gray during a theme/settings transaction.
        QtWidgets.QApplication.instance().installEventFilter(self)
        self._delay.start(self.DELAY_MS)
        if work is None:
            self._next.start(0)
        else:
            def execute():
                try:
                    value, success = work(), True
                except Exception as error:
                    value, success = error, False
                try:
                    self.worker_result.emit(token, value, success)
                except RuntimeError:
                    pass  # The owner was destroyed; the file worker owns no widgets.
            try:
                threading.Thread(target=execute, name='Settings-file', daemon=True).start()
            except Exception as error:
                self._finish(error=error)
        return True

    def eventFilter(self, watched, event):
        if self.active and event.type() in self.INPUT_EVENTS:
            modal = QtWidgets.QApplication.activeModalWidget()
            target = watched
            while target is not None and modal is not None:
                if target is modal:
                    return False  # A permission/error prompt must remain dismissible.
                target = target.parent()
            target = watched
            while target is not None:
                if target is self.owner or target is self._root:
                    event.accept()
                    return True
                target = target.parent()
        return False

    @QtCore.pyqtSlot(int, object, bool)
    def _receive(self, token, value, success):
        if not self.active or token != self._revision:
            return
        if not success:
            self._finish(error=value)
            return
        self._result = value
        self._next.start(0)

    def _advance(self):
        if not self.active:
            return
        try:
            if self._steps is None:
                if self._factory is None:
                    self._finish(result=self._result)
                    return
                self._steps = iter(self._factory(self._result))
            phase = next(self._steps)
            if phase in PHASES:
                self.phase = phase
                if self._indicator is not None:
                    self._indicator.phase = phase
                    self._indicator.position()
                    self._indicator.setAccessibleName(self._indicator.label())
                    self._indicator.update()
            self._next.start(0)
        except StopIteration as complete:
            self._finish(result=complete.value)
        except Exception as error:
            self._finish(error=error)

    def _show_indicator(self):
        if not self.active or sip.isdeleted(self.owner):
            return
        if self._indicator is None:
            self._indicator = OperationIndicator(self.owner)
        self._indicator.phase = self.phase
        self._indicator.display_theme = self._display_theme
        self._indicator.position()
        self._indicator.show()
        self._indicator.raise_()

    def _cleanup(self):
        self._finishing = True
        self._delay.stop()
        self._next.stop()
        self.active = False
        application = QtWidgets.QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        self._revision += 1
        steps, self._steps = self._steps, None
        self._result = None  # Do not retain the imported JSON or a completed file-job buffer while idle.
        try:
            if steps is not None and hasattr(steps, 'close'):
                steps.close()
        except Exception:
            logging.exception('Could not close a cancelled settings stage')
        finally:
            try:
                if self._indicator is not None and not sip.isdeleted(self._indicator):
                    self._indicator.hide()
                root = getattr(self, '_root', None)
                if root is not None and not sip.isdeleted(root):
                    if self._had_cursor:
                        root.setCursor(self._cursor)
                    else:
                        root.unsetCursor()
                        root.setAttribute(QtCore.Qt.WA_SetCursor, False)
            finally:
                self._finishing = False

    def _finish(self, result=None, error=None):
        from runtime_metrics import record
        name = 'ui.theme' if self._initial_phase == 'theme' else 'ui.settings.'+self._initial_phase
        record(name, (time.perf_counter()-self._started)*1000, error is not None)
        done, failed = self._done, self._failed
        self._factory = self._done = self._failed = None
        self._cleanup()
        if sip.isdeleted(self.owner):
            return
        callback, value = (failed, error) if error is not None else (done, result)
        if callback is not None:
            try:
                callback(value)
            except Exception:
                logging.exception('Could not display the settings operation result')
        elif error is not None:
            logging.error('Settings operation failed: %s', error)

    def cancel(self, *_args):
        if self.active:
            self._factory = self._done = self._failed = None
            self._cleanup()


def operation_for(owner):
    operation = getattr(owner, '_ui_operation', None)
    if operation is None or sip.isdeleted(operation):
        operation = owner._ui_operation = UiOperation(owner)
    return operation


def consume_steps(steps):
    """Keep the direct Python API synchronous; UI actions use queued stages."""
    while True:
        try:
            next(steps)
        except StopIteration as complete:
            return complete.value
