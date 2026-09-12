"""Paired capture/output selection and compact controls for live text windows."""

import logging

from PyQt5 import QtCore, QtGui, QtWidgets

import game_mode
import platform_support
from button_styles import button_qss
from dynamic_templates import TemplateStore, decode_rect, encode_rect, output_style, text
from windows_overlay import configure_surface, rounded_region, set_surface_region


def make_template(name, sources, outputs, styles, source_language, target_language):
    screens = QtWidgets.QApplication.screens()
    return {'name': name, 'source_language': source_language, 'target_language': target_language,
            'pairs': [{'source': encode_rect(source, screens), 'output': encode_rect(output, screens), 'style': style}
                      for source, output, style in zip(sources, outputs, styles)]}


class PairedRegionSelector(game_mode.GameRegionSelector):
    def __init__(self, target_window=0, *, store=None):
        self._outputs = []
        self._styles = []
        self._drag_hit = None
        self._selected_hit = None
        self.store = store or TemplateStore()
        super().__init__(target_window)
        self._screens = QtWidgets.QApplication.screens()
        bounds = QtCore.QRect()
        for screen in self._screens:
            bounds = bounds.united(screen.geometry())
        self.setGeometry(bounds)
        self.template_combo = QtWidgets.QComboBox(self)
        self.template_combo.setEditable(True)
        self.template_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.template_combo.lineEdit().setPlaceholderText(text(self._language, 'templates'))
        self.template_combo.setFixedSize(248, 32)
        self.template_combo.setStyleSheet('QComboBox { color:#f5f0fa; background:#211d29; border:1px solid #746087; border-radius:6px; padding:4px; }')
        self.save_template_button = QtWidgets.QPushButton('+', self)
        self.delete_template_button = QtWidgets.QPushButton('×', self)
        for button, key in ((self.save_template_button, 'save'), (self.delete_template_button, 'delete')):
            button.setFixedSize(32, 32)
            button.setToolTip(text(self._language, key))
            button.setStyleSheet(button_qss(True, compact=True))
        self.save_template_button.clicked.connect(self._save_template)
        self.delete_template_button.clicked.connect(self._delete_template)
        self.template_combo.activated.connect(self._load_template)
        self._refresh_templates()
        self._layout_controls()
        self._update_selection_controls()
        for widget in (self.template_combo, self.save_template_button, self.delete_template_button):
            widget.show()

    def _layout_controls(self):
        if not hasattr(self, 'start_button'):
            return
        # Put the controls on the monitor under the pointer, not in a gap
        # between monitors or on another display's title bar.
        monitor = self._screen.geometry().translated(-self.geometry().topLeft())
        languages = [self.source_combo, self.swap_button, self.target_combo]
        actions = [self.undo_button, self.start_button]
        controls = languages + actions
        rows = [controls] if sum(widget.width() for widget in controls)+32 <= monitor.width()-24 else [languages, actions]
        y = monitor.top()+20
        for row in rows:
            height = max(widget.height() for widget in row)
            x = monitor.center().x()-(sum(widget.width() for widget in row)+8*(len(row)-1))//2
            for widget in row:
                widget.move(x, y)
                x += widget.width()+8
            y += height+8
        self._caption_top = y
        if not hasattr(self, 'template_combo'):
            return
        x = monitor.center().x() - 164
        for widget in (self.template_combo, self.save_template_button, self.delete_template_button):
            widget.move(x, y)
            x += widget.width()+8
        self._caption_top = y+40

    def _complete(self):
        return bool(self._regions) and len(self._outputs) == len(self._regions) and all(rect is not None for rect in self._outputs)

    def _update_selection_controls(self):
        if not hasattr(self, 'start_button'):
            return
        complete = self._complete()
        self.start_button.setEnabled(complete and bool(self.source_combo.currentData() and self.target_combo.currentData()))
        self.start_button.setText(game_mode.game_text(self._language, 'start'))
        self.undo_button.setEnabled(bool(self._regions))
        if hasattr(self, 'save_template_button'):
            self.save_template_button.setEnabled(complete)
        self.update()

    def _refresh_templates(self, selected=''):
        try:
            values = self.store.load()
        except Exception:
            logging.getLogger('clickntranslate.game').exception('Unable to load dynamic templates')
            values = []
            self.template_combo.setToolTip(text(self._language, 'save_error'))
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        for value in values:
            self.template_combo.addItem(value['name'], value)
        self.template_combo.setCurrentIndex(-1)
        self.template_combo.setEditText(selected)
        self.template_combo.blockSignals(False)

    def _save_template(self):
        if not self._complete():
            return
        name = self.template_combo.currentText().strip()
        if not name:
            self.template_combo.lineEdit().setFocus()
            self.template_combo.setToolTip(text(self._language, 'name_required'))
            return
        origin = self.geometry().topLeft()
        value = make_template(name, [rect.translated(origin) for rect in self._regions],
                              [rect.translated(origin) for rect in self._outputs], self._styles,
                              str(self.source_combo.currentData()), str(self.target_combo.currentData()))
        try:
            self.store.save(value)
            self._refresh_templates(name)
            self.save_template_button.setToolTip(text(self._language, 'saved'))
        except Exception:
            logging.getLogger('clickntranslate.game').exception('Unable to save dynamic template')
            self.template_combo.setToolTip(text(self._language, 'save_error'))

    def _delete_template(self):
        name = self.template_combo.currentText().strip()
        try:
            self.store.delete(name)
            self._refresh_templates()
        except Exception:
            self.template_combo.setToolTip(text(self._language, 'save_error'))

    def _load_template(self, index):
        value = self.template_combo.itemData(index)
        if not value:
            return
        source_index = self.source_combo.findData(value['source_language'])
        targets = self._translation_targets_for_source(value['source_language'], self._config)
        if source_index < 0 or value['target_language'] not in targets:
            self.template_combo.setToolTip(text(self._language, 'unavailable'))
            return
        self.template_combo.setCurrentIndex(index)
        self.source_combo.setCurrentIndex(source_index)
        self._fill_targets(value['target_language'])
        origin = self.geometry().topLeft()
        self._regions = [decode_rect(pair['source'], self._screens).translated(-origin) for pair in value['pairs']]
        self._outputs = [decode_rect(pair['output'], self._screens).translated(-origin) for pair in value['pairs']]
        self._styles = [output_style(pair['style']) for pair in value['pairs']]
        self._selected_region = self._selected_hit = self._drag_hit = None
        self._start = self._end = None
        self._update_selection_controls()

    def _remove_region(self, index):
        if index is not None and 0 <= index < len(self._regions):
            for values in (self._regions, self._outputs, self._styles):
                values.pop(index)
        self._selected_region = self._selected_hit = self._drag_hit = None
        self._update_selection_controls()

    def _undo_last_region(self):
        if self._regions:
            self._remove_region(len(self._regions)-1)

    def _hit(self, point):
        for index in reversed(range(len(self._regions))):
            for kind, rect in (('output', self._outputs[index]), ('source', self._regions[index])):
                if rect is not None and rect.contains(point):
                    return index, kind
        return None

    def _rect_for_hit(self, hit):
        return (self._outputs if hit[1] == 'output' else self._regions)[hit[0]]

    def _screen_local_bounds(self, point):
        global_point = point+self.geometry().topLeft()
        screen = QtWidgets.QApplication.screenAt(global_point) or self._screen
        return screen.geometry().translated(-self.geometry().topLeft())

    def mousePressEvent(self, event):
        hit = self._hit(event.pos())
        if event.button() == QtCore.Qt.RightButton:
            self._remove_region(hit[0]) if hit else self._undo_last_region()
            return
        if event.button() != QtCore.Qt.LeftButton:
            return
        self.setFocus(QtCore.Qt.MouseFocusReason)
        self._selected_hit = hit
        self._selected_region = hit[0] if hit else None
        if hit and self._remove_button_rect(self._rect_for_hit(hit)).contains(event.pos()):
            self._remove_region(hit[0])
            return
        pending_output = bool(self._outputs) and self._outputs[-1] is None
        if hit and not pending_output and not event.modifiers() & QtCore.Qt.ShiftModifier:
            self._drag_hit = hit
            self._move_offset = event.pos()-self._rect_for_hit(hit).topLeft()
        else:
            self._start = self._end = event.pos()
        self.update()

    def mouseMoveEvent(self, event):
        if self._drag_hit:
            rect = self._rect_for_hit(self._drag_hit)
            bounds = self._screen_local_bounds(event.pos())
            rect.setSize(QtCore.QSize(min(rect.width(), bounds.width()), min(rect.height(), bounds.height())))
            point = event.pos()-self._move_offset
            rect.moveTopLeft(QtCore.QPoint(max(bounds.left(), min(point.x(), bounds.right()-rect.width()+1)),
                                           max(bounds.top(), min(point.y(), bounds.bottom()-rect.height()+1))))
        elif self._start is not None:
            self._end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        if self._drag_hit:
            self.mouseMoveEvent(event)
            self._drag_hit = None
            return
        if self._start is None:
            return
        rect = QtCore.QRect(self._start, event.pos()).normalized().intersected(self._screen_local_bounds(self._start))
        self._start = self._end = None
        if rect.width() >= 60 and rect.height() >= 24:
            if self._outputs and self._outputs[-1] is None:
                self._outputs[-1] = rect
            elif len(self._regions) < 16:
                self._regions.append(rect)
                self._outputs.append(None)
                self._styles.append(output_style(opacity=int(self._config.get('game_overlay_opacity', 88))))
        self._update_selection_controls()

    def _start_selected_regions(self):
        if not self._complete() or not self.start_button.isEnabled():
            return
        origin = self.geometry().topLeft()
        sources = [rect.translated(origin) for rect in self._regions]
        outputs = [rect.translated(origin) for rect in self._outputs]
        target_window = self._target_window
        if platform_support.IS_MAC:
            try:
                from macos_desktop import window_number_at_point
                center = sources[0].center()
                target_window = window_number_at_point(center.x(), center.y()) or target_window
            except Exception:
                logging.getLogger('clickntranslate.game').exception('Unable to bind selected source window')
        self._persist_pair()
        self._starting_session = True
        self.close()
        game_mode._begin_game_session(sources, str(self.source_combo.currentData()), str(self.target_combo.currentData()),
                                      target_window, output_regions=outputs, output_styles=self._styles)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(4, 7, 12, 112))
        areas = [(index, kind, rect) for index, source in enumerate(self._regions)
                 for kind, rect in (('source', source), ('output', self._outputs[index])) if rect is not None]
        if self._start is not None and self._end is not None:
            kind = 'output' if self._outputs and self._outputs[-1] is None else 'source'
            areas.append((-1, kind, QtCore.QRect(self._start, self._end).normalized()))
        painter.setFont(QtGui.QFont('Segoe UI', 9))
        for index, kind, rect in areas:
            color = QtGui.QColor('#b596dd' if kind == 'source' else '#79c9ae')
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_Clear)
            painter.fillRect(rect, QtCore.Qt.transparent)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            faint = QtGui.QColor(color)
            faint.setAlpha(15)
            painter.fillRect(rect, faint)
            painter.setPen(QtGui.QPen(color, 2))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(rect)
            if index >= 0:
                label = f'{index+1} · {text(self._language, "read" if kind == "source" else "write")}'
                badge = QtCore.QRect(rect.x()+4, rect.y()+4, min(rect.width()-36, painter.fontMetrics().horizontalAdvance(label)+12), 20)
                painter.fillRect(badge, QtGui.QColor('#211d29'))
                painter.drawText(badge, QtCore.Qt.AlignCenter, label)
                painter.drawText(self._remove_button_rect(rect), QtCore.Qt.AlignCenter, '×')
        key = 'output' if self._outputs and self._outputs[-1] is None else ('ready' if self._regions else 'source')
        monitor = self._screen.geometry().translated(-self.geometry().topLeft())
        painter.setPen(QtGui.QColor('#e7e1ed'))
        painter.drawText(QtCore.QRect(monitor.x()+12, self._caption_top, monitor.width()-24, 30), QtCore.Qt.AlignHCenter, text(self._language, key))
        painter.end()


class PairedTranslationOverlay(game_mode.GameTranslationOverlay):
    """OCR reads region; this window paints only the translated text elsewhere."""

    def __init__(self, region, source_language, target_language, target_window=0, *, output_region, style=None, start_delay_ms=0):
        self.output_rect = QtCore.QRect(output_region)
        self.output_style = output_style(style)
        self._output_frame = QtGui.QImage()
        self._output_ready = False
        self.controls = None
        super().__init__(region, source_language, target_language, target_window, start_delay_ms=start_delay_ms)
        self.translation_label.clear()
        self.translation_label.setTextFormat(QtCore.Qt.PlainText)
        self.translation_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.layout().setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.translation_label.setMinimumSize(0, 0)
        self.translation_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.original_label.hide()
        self._startup_frame_visible = False
        self._output_ready = True
        self.controls = OutputControls(self)
        self._update_capture_shape()

    def _apply_style(self):
        dark = self.config.get('theme', 'Темная') != 'Светлая'
        alpha = round(255*self.output_style['opacity']/100)
        background = f'rgba(18,16,22,{alpha})' if dark else f'rgba(245,243,247,{alpha})'
        color = '#fbf9fd' if dark else '#251f2b'
        self.setStyleSheet(f'QFrame#gameTranslationCard {{ background:{background}; border:0; border-radius:4px; }}'
                          f'QLabel {{ background:transparent; border:0; color:{color}; }}'
                          f'QLabel#gameTranslation {{ font:{self.output_style["font_size"]}px "Segoe UI"; }}')
        if self.card.layout():
            self.card.layout().setContentsMargins(6, 4, 6, 4)
            self.card.layout().setSpacing(0)

    def _place_near_region(self):
        self.setGeometry(self.output_rect)
        self._update_capture_shape()
        if self.controls:
            self.controls.place()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._output_ready:
            self.output_rect = self.geometry()
            if self.controls:
                self.controls.place()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._output_ready:
            self.output_rect = self.geometry()
            self._output_frame = QtGui.QImage()
            self._update_capture_shape()
            if self.controls:
                self.controls.place()

    def set_output_geometry(self, rect):
        screen = QtWidgets.QApplication.screenAt(rect.center()) or QtWidgets.QApplication.primaryScreen()
        bounds = screen.geometry()
        rect = QtCore.QRect(rect)
        rect.setSize(QtCore.QSize(min(bounds.width(), max(60, rect.width())), min(bounds.height(), max(24, rect.height()))))
        rect.moveTopLeft(QtCore.QPoint(max(bounds.left(), min(rect.x(), bounds.right()-rect.width()+1)),
                                       max(bounds.top(), min(rect.y(), bounds.bottom()-rect.height()+1))))
        self.output_rect = rect
        self._place_near_region()

    def _capture_windows(self):
        overlays = [item for item in game_mode._game_overlay_refs if not item._closed]
        if self not in overlays:
            overlays.append(self)
        return [widget for item in overlays for widget in (item, getattr(item, 'controls', None)) if widget is not None]

    def _grab_region(self):
        windows = self._capture_windows()
        if platform_support.IS_WINDOWS:
            if any(not widget._capture_excluded for widget in windows):
                raise RuntimeError('Windows cannot exclude a translation window from capture')
            return super()._grab_region()
        # Mac's compositor already excludes all process windows. On X11 the
        # output of another pair and its controls must also stay out of OCR.
        hidden = [(widget, widget.windowOpacity()) for widget in windows]
        for widget, _ in hidden:
            widget.setWindowOpacity(0)
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        try:
            return super()._grab_region()
        finally:
            for widget, opacity in hidden:
                widget.setWindowOpacity(opacity)

    def _process_frame(self, image):
        if platform_support.IS_WINDOWS:
            from ocr import grab_screen_pixmap
            screen = QtWidgets.QApplication.screenAt(self.output_rect.center()) or QtWidgets.QApplication.primaryScreen()
            local = self.output_rect.translated(-screen.geometry().topLeft())
            self._output_frame = grab_screen_pixmap(screen, *local.getRect()).toImage()
        super()._process_frame(image)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        if platform_support.IS_WINDOWS:
            if not self._output_frame.isNull():
                painter.drawImage(self.rect(), self._output_frame)
            else:
                painter.fillRect(self.rect(), QtGui.QColor('#121016' if self.config.get('theme') != 'Светлая' else '#f5f3f7'))
        if not self.output_style['locked']:
            painter.setPen(QtGui.QPen(QtGui.QColor('#79c9ae'), 1, QtCore.Qt.DashLine))
            painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()

    def _update_capture_shape(self):
        if not hasattr(self, 'card'):
            return
        region = rounded_region(self.rect(), 4) if not self.card.isHidden() else QtGui.QRegion()
        if not self.output_style['locked']:
            region |= QtGui.QRegion(self.rect()) - QtGui.QRegion(self.rect().adjusted(1, 1, -1, -1))
        set_surface_region(self, region, windows=platform_support.IS_WINDOWS)

    def _set_status(self, key, active=True):
        self._diagnostic_status = key
        self._startup_frame_visible = False
        self.status_label.hide()
        self.original_label.hide()
        if self.controls:
            error = game_mode.game_text(self.language, key) if key in {'capture_error', 'ocr_error', 'translation_error'} else ''
            self.controls.set_error(error)
        self._update_capture_shape()

    def _target_is_active(self):
        if self.controls and self.controls.isActiveWindow():
            return True
        return super()._target_is_active()

    def change_style(self, **values):
        self.output_style = output_style({**self.output_style, **values})
        self._apply_style()
        self._update_capture_shape()
        self.update()

    def closeEvent(self, event):
        super().closeEvent(event)
        if self.controls:
            self.controls.close()


class OutputControls(QtWidgets.QFrame):
    def __init__(self, overlay):
        super().__init__(None, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.overlay = overlay
        self._gesture = None
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        configure_surface(self, windows=platform_support.IS_WINDOWS)
        if platform_support.IS_MAC:
            self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow, True)
        self.setObjectName('outputControls')
        dark = overlay.config.get('theme', 'Темная') != 'Светлая'
        self.setStyleSheet(f'QFrame#outputControls {{ background:{"#211d29" if dark else "#f5f1f8"}; border:1px solid #746087; border-radius:6px; }}'
                          f'QLabel, QCheckBox {{ color:{"#f5f0fa" if dark else "#302837"}; background:transparent; border:0; font:12px "Segoe UI"; }}'
                          f'QLineEdit, QSpinBox {{ background:{"#302a3c" if dark else "#fff"}; color:{"#f5f0fa" if dark else "#302837"}; padding:4px; border:1px solid #746087; border-radius:4px; font:12px "Segoe UI"; }}')
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(3, 3, 3, 3)
        root.setSpacing(4)
        self.gear = QtWidgets.QToolButton()
        self.gear.setText('...')
        self.gear.setToolTip(text(overlay.language, 'settings'))
        self.gear.setFixedSize(24, 22)
        self.gear.setStyleSheet(button_qss(dark, 'quiet', selector='QToolButton', icon=True))
        root.addWidget(self.gear, 0, QtCore.Qt.AlignRight)
        self.panel = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(self.panel)
        form.setContentsMargins(7, 3, 7, 6)
        form.setSpacing(7)
        self.font_size = QtWidgets.QSpinBox()
        self.font_size.setRange(10, 48)
        self.font_size.setValue(overlay.output_style['font_size'])
        form.addRow(text(overlay.language, 'font'), self.font_size)
        self.opacity = QtWidgets.QSpinBox()
        self.opacity.setRange(0, 100)
        self.opacity.setSuffix('%')
        self.opacity.setValue(overlay.output_style['opacity'])
        form.addRow(text(overlay.language, 'opacity'), self.opacity)
        self.locked = QtWidgets.QCheckBox(text(overlay.language, 'locked'))
        self.locked.setChecked(overlay.output_style['locked'])
        self.move_button = QtWidgets.QToolButton()
        self.resize_button = QtWidgets.QToolButton()
        gesture_row = QtWidgets.QHBoxLayout()
        gesture_row.addWidget(self.locked)
        for button, label, key in ((self.move_button, '↔', 'move'), (self.resize_button, '↘', 'resize')):
            button.setText(label)
            button.setToolTip(text(overlay.language, key))
            button.setFixedSize(28, 26)
            button.setEnabled(not self.locked.isChecked())
            button.installEventFilter(self)
            gesture_row.addWidget(button)
        form.addRow(gesture_row)
        self.template_name = QtWidgets.QLineEdit()
        self.template_name.setMaxLength(80)
        self.template_name.setPlaceholderText(text(overlay.language, 'templates'))
        form.addRow(self.template_name)
        self.save_button = QtWidgets.QPushButton(text(overlay.language, 'save'))
        form.addRow(self.save_button)
        self.notice = QtWidgets.QLabel()
        self.notice.setWordWrap(True)
        self.notice.hide()
        form.addRow(self.notice)
        self.error_label = QtWidgets.QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        form.addRow(self.error_label)
        self.stop_button = QtWidgets.QPushButton(game_mode.game_text(overlay.language, 'stop'))
        form.addRow(self.stop_button)
        for button in (self.save_button, self.stop_button, self.move_button, self.resize_button):
            selector = 'QToolButton' if isinstance(button, QtWidgets.QToolButton) else 'QPushButton'
            button.setStyleSheet(button_qss(dark, compact=True, selector=selector, icon=isinstance(button, QtWidgets.QToolButton)))
        self.save_button.setFixedHeight(28)
        self.stop_button.setFixedHeight(26)
        root.addWidget(self.panel)
        self.panel.hide()
        self.gear.clicked.connect(self._toggle_panel)
        self.font_size.valueChanged.connect(lambda value: overlay.change_style(font_size=value))
        self.opacity.valueChanged.connect(lambda value: overlay.change_style(opacity=value))
        self.locked.toggled.connect(self._lock_changed)
        self.save_button.clicked.connect(self._save)
        self.stop_button.clicked.connect(game_mode.stop_game_mode)
        self.template_name.returnPressed.connect(self._save)
        self._resize_panel()
        self.show()
        self._capture_excluded = game_mode._exclude_from_windows_capture(self)

    def _toggle_panel(self):
        self.panel.setVisible(self.panel.isHidden())
        self._resize_panel()

    def _resize_panel(self):
        self.setFixedWidth(286 if not self.panel.isHidden() else 30)
        self.setFixedHeight(self.sizeHint().height())
        set_surface_region(self, rounded_region(self.rect(), 6), windows=platform_support.IS_WINDOWS)
        self.place()

    def place(self):
        rect = self.overlay.output_rect
        screen = QtWidgets.QApplication.screenAt(rect.center()) or QtWidgets.QApplication.primaryScreen()
        bounds = screen.availableGeometry()
        x = max(bounds.left(), min(rect.right()-self.width()+1, bounds.right()-self.width()+1))
        y = rect.top()-self.height()-3
        if y < bounds.top():
            y = max(bounds.top(), min(rect.bottom()+3, bounds.bottom()-self.height()+1))
        self.move(x, y)

    def _lock_changed(self, locked):
        self._gesture = None
        self.overlay.change_style(locked=locked)
        self.move_button.setEnabled(not locked)
        self.resize_button.setEnabled(not locked)

    def eventFilter(self, watched, event):
        if watched not in (self.move_button, self.resize_button) or self.overlay.output_style['locked']:
            return super().eventFilter(watched, event)
        if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
            self._gesture = (watched, event.globalPos(), QtCore.QRect(self.overlay.output_rect))
            return True
        if self._gesture and event.type() in (QtCore.QEvent.MouseMove, QtCore.QEvent.MouseButtonRelease):
            button, origin, rect = self._gesture
            delta = event.globalPos()-origin
            rect = QtCore.QRect(rect)
            if button is self.move_button:
                rect.translate(delta)
            else:
                rect.setSize(rect.size()+QtCore.QSize(delta.x(), delta.y()))
            self.overlay.set_output_geometry(rect)
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                self._gesture = None
            return True
        return super().eventFilter(watched, event)

    def set_error(self, message):
        if self.error_label.text() == message:
            return
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))
        self.gear.setToolTip(message or text(self.overlay.language, 'settings'))
        self._resize_panel()

    def _save(self):
        name = self.template_name.text().strip()
        if not name:
            self.notice.setText(text(self.overlay.language, 'name_required'))
        else:
            overlays = [item for item in game_mode._game_overlay_refs if isinstance(item, PairedTranslationOverlay) and not item._closed] or [self.overlay]
            try:
                TemplateStore().save(make_template(name, [item.region for item in overlays], [item.output_rect for item in overlays],
                    [item.output_style for item in overlays], self.overlay.source_language, self.overlay.target_language))
                self.notice.setText(text(self.overlay.language, 'saved'))
            except Exception:
                logging.getLogger('clickntranslate.game').exception('Unable to save output layout')
                self.notice.setText(text(self.overlay.language, 'save_error'))
        self.notice.show()
        self._resize_panel()

    def closeEvent(self, event):
        if not self.overlay._closed:
            self.overlay.close()
        event.accept()
