"""Paired capture/output selection and compact controls for live text windows."""

import logging

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import game_mode
import platform_support
from button_styles import button_qss
from number_controls import NumberStepper
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
        factor = float(self.property('ui_effective_scale') or 1.0)
        dark = self._config.get('theme', 'Темная') != 'Светлая'
        self.toolbar = QtWidgets.QFrame(self)
        self.toolbar.setObjectName('dynamicSelectionToolbar')
        self.toolbar.setCursor(QtCore.Qt.ArrowCursor)
        self.toolbar.setStyleSheet(f"""
            QFrame#dynamicSelectionToolbar {{ background:{'#121212' if dark else '#f0edf3'};
                border:1px solid {'#584963' if dark else '#bcaacb'}; border-radius:8px; }}
            QLabel, QCheckBox {{ background:transparent; border:0;
                color:{'#eee7f5' if dark else '#302639'}; font-size:{round(13*factor)}px; }}
            QComboBox {{ color:{'#eee7f5' if dark else '#302639'};
                background:{'#211d28' if dark else '#faf8fc'};
                border:1px solid {'#584963' if dark else '#bcaacb'}; border-radius:6px; padding:3px 8px; }}
            QComboBox QAbstractItemView {{ background:{'#211d28' if dark else '#faf8fc'};
                color:{'#eee7f5' if dark else '#302639'};
                selection-background-color:{'#3c3048' if dark else '#d9cbe5'}; }}
        """)
        layout = QtWidgets.QVBoxLayout(self.toolbar)
        layout.setContentsMargins(round(12*factor), round(10*factor), round(12*factor), round(10*factor))
        layout.setSpacing(round(8*factor))
        heading = QtWidgets.QHBoxLayout()
        self.step_label = QtWidgets.QLabel()
        self.step_label.setWordWrap(True)
        self.step_label.setStyleSheet(f'font-size:{round(15*factor)}px; font-weight:600;')
        heading.addWidget(self.step_label, 1)
        close = QtWidgets.QPushButton('×')
        close.setFixedSize(round(28*factor), round(28*factor))
        close.setAccessibleName(game_mode.game_text(self._language, 'close'))
        close.setStyleSheet(button_qss(dark, 'close', icon=True))
        close.clicked.connect(self.close)
        heading.addWidget(close)
        layout.addLayout(heading)
        self.selection_controls = QtWidgets.QGridLayout()
        self.selection_controls.setSpacing(round(6*factor))
        self._controls_wrapped = None
        for widget in (self.source_combo, self.swap_button, self.target_combo,
                       self.undo_button, self.start_button):
            widget.setParent(self.toolbar)
            widget.show()
        layout.addLayout(self.selection_controls)
        self._manual_output = bool(self._config.get('game_manual_output', False))
        self.template_combo = QtWidgets.QComboBox()
        self.template_combo.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.template_combo.setAccessibleName(text(self._language, 'choose_template'))
        self.template_combo.setMinimumHeight(round(28*factor))
        self.template_combo.activated.connect(self._load_template)
        layout.addWidget(self.template_combo)
        self.selection_note = QtWidgets.QLabel(text(self._language, 'selection_hint' if self._manual_output else 'simple_selection_hint'))
        self.selection_note.setWordWrap(True)
        self.selection_note.setStyleSheet(f'color:{"#b9b1c2" if dark else "#71647b"}; font-size:{round(12*factor)}px;')
        layout.addWidget(self.selection_note)
        from styled_dialogs import install_accent_controls
        install_accent_controls(self.toolbar, dark=dark)
        self._refresh_templates()
        self._layout_controls()
        self._update_selection_controls()
        self.toolbar.show()

    def _layout_controls(self):
        if not hasattr(self, 'toolbar'):
            return super()._layout_controls()
        monitor = self._screen.geometry().translated(-self.geometry().topLeft())
        factor = float(self.property('ui_effective_scale') or 1.0)
        self.toolbar.setFixedWidth(min(round(640*factor), monitor.width()-24))
        if hasattr(self, 'selection_controls'):
            controls = (self.source_combo, self.swap_button, self.target_combo,
                        self.undo_button, self.start_button)
            wrapped = sum(widget.width() for widget in controls)+round(48*factor) > self.toolbar.width()
            if wrapped != self._controls_wrapped:
                self._controls_wrapped = wrapped
                for widget in controls:
                    self.selection_controls.removeWidget(widget)
                for column in range(6):
                    self.selection_controls.setColumnStretch(column, 0)
                for index, widget in enumerate(controls):
                    row, column = ((1, index-3) if wrapped and index >= 3 else (0, index))
                    self.selection_controls.addWidget(widget, row, column)
                self.selection_controls.setColumnStretch(3 if wrapped else 5, 1)
        self.toolbar.adjustSize()
        self.toolbar.move(monitor.center().x()-self.toolbar.width()//2, monitor.top()+round(16*factor))
        self._caption_top = self.toolbar.geometry().bottom()+8

    def _complete(self):
        return bool(self._regions) and len(self._outputs) == len(self._regions) and all(rect is not None for rect in self._outputs)

    def _update_selection_controls(self):
        if not hasattr(self, 'start_button'):
            return
        complete = self._complete()
        self.start_button.setEnabled(complete and bool(self.source_combo.currentData() and self.target_combo.currentData()))
        self.start_button.setText(game_mode.game_text(self._language, 'start'))
        self.undo_button.setEnabled(bool(self._regions))
        if hasattr(self, 'step_label'):
            key = 'output' if self._outputs and self._outputs[-1] is None else ('simple_ready' if complete else 'source')
            self.step_label.setText(text(self._language, key))
            self._layout_controls()
        self.update()

    def _refresh_templates(self):
        try:
            values = self.store.load()
        except Exception:
            logging.getLogger('clickntranslate.game').exception('Unable to load dynamic templates')
            values = []
        with QtCore.QSignalBlocker(self.template_combo):
            self.template_combo.clear()
            self.template_combo.addItem(text(self._language, 'new_layout'), None)
            for value in values:
                self.template_combo.addItem(value['name'], value)
        self.template_combo.setVisible(bool(values))

    def _load_template(self, index):
        value = self.template_combo.itemData(index)
        if not value:
            self._manual_output = bool(self._config.get('game_manual_output', False))
            self._regions, self._outputs, self._styles = [], [], []
            self._selected_region = self._selected_hit = self._drag_hit = None
            self._start = self._end = None
            self.selection_note.setText(text(self._language, 'selection_hint' if self._manual_output else 'simple_selection_hint'))
            self._update_selection_controls()
            return
        source_index = self.source_combo.findData(value['source_language'])
        targets = self._translation_targets_for_source(value['source_language'], self._config)
        if source_index < 0 or value['target_language'] not in targets:
            self.selection_note.setText(text(self._language, 'unavailable'))
            with QtCore.QSignalBlocker(self.template_combo):
                self.template_combo.setCurrentIndex(0)
            self._layout_controls()
            return
        self.selection_note.setText(text(self._language, 'selection_hint' if self._manual_output else 'simple_selection_hint'))
        self.template_combo.setCurrentIndex(index)
        self.source_combo.setCurrentIndex(source_index)
        self._fill_targets(value['target_language'])
        origin = self.geometry().topLeft()
        self._regions = [decode_rect(pair['source'], self._screens).translated(-origin) for pair in value['pairs']]
        self._outputs = [decode_rect(pair['output'], self._screens).translated(-origin) for pair in value['pairs']]
        self._manual_output = any(source != output for source, output in zip(self._regions, self._outputs))
        self.selection_note.setText(text(self._language, 'selection_hint' if self._manual_output else 'simple_selection_hint'))
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
            if not self._manual_output and self._regions[index].contains(point):
                return index, 'source'
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
            if not self._manual_output:
                self._outputs[self._drag_hit[0]] = QtCore.QRect(rect)
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
                self._outputs.append(None if self._manual_output else QtCore.QRect(rect))
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
        if platform_support.IS_WINDOWS:
            target_window = game_mode._window_at_point(sources[0].center())
        game_mode._begin_game_session(sources, str(self.source_combo.currentData()), str(self.target_combo.currentData()),
                                      target_window, output_regions=outputs, output_styles=self._styles,
                                      template_name=self.template_combo.currentText() if self.template_combo.currentData() else '')

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(4, 7, 12, 112))
        areas = [(index, kind, rect) for index, source in enumerate(self._regions)
                 for kind, rect in (('source', source), ('output', self._outputs[index]))
                 if rect is not None and (kind == 'source' or rect != source)]
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

    def _update_bound_region(self):
        previous = QtCore.QRect(self.region)
        follows_source = self.output_rect == previous
        super()._update_bound_region()
        if follows_source and self.region != previous:
            self.output_rect = QtCore.QRect(self.region)
            self._place_near_region()

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
        return list(dict.fromkeys(widget for item in overlays for widget in (item, getattr(item, 'controls', None)) if widget is not None))

    def _grab_region(self):
        windows = self._capture_windows()
        if platform_support.IS_WINDOWS:
            if any(widget.isVisible() and not widget._capture_excluded for widget in windows):
                raise RuntimeError('Windows cannot exclude a translation window from capture')
            return super()._grab_region()
        # Mac's compositor excludes our windows from a grab automatically, and
        # X11 has no such exclusion at all: windowOpacity only works with a
        # compositor and does not remove the window from a root grab. A window
        # that overlaps the captured region is therefore hidden for the grab
        # and restored afterwards, while windows outside the region stay
        # untouched and keep the output visible without any flicker.
        region = self.region
        hidden = [widget for widget in windows
                  if widget.isVisible() and widget.geometry().intersects(region)]
        for widget in hidden:
            widget.hide()
        if hidden:
            # Let the window manager actually unmap the windows and repaint the
            # exposed region before the grab; XGetImage right after hide() can
            # still return the old backing store.
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            QTest.qWait(60)
        try:
            # Same capture as the base class, but without its windowOpacity
            # dance: visibility here is managed by hide()/show() above.
            from ocr import grab_screen_pixmap
            screen = QtWidgets.QApplication.screenAt(region.center()) or QtWidgets.QApplication.primaryScreen()
            geometry = screen.geometry()
            local = region.translated(-geometry.left(), -geometry.top())
            return grab_screen_pixmap(screen, local.x(), local.y(), local.width(), local.height())
        finally:
            for widget in hidden:
                if widget.isHidden():
                    widget.show()
                    widget.raise_()

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
            self.controls.set_error(error, self)
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
            self.controls.detach(self)


class OutputControls(QtWidgets.QFrame):
    """One session toolbar for all outputs, with inline optional settings."""
    def __init__(self, overlays, template_name=''):
        super().__init__(None, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.overlays = list(overlays)
        self.overlay = self.overlays[0]
        self.language = self.overlay.language
        self._gesture = None
        self._drag_offset = None
        self._closing = False
        self._errors = {}
        self._placed = False
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        configure_surface(self, windows=platform_support.IS_WINDOWS)
        if platform_support.IS_MAC:
            self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow, True)
        self.setObjectName('outputControls')
        dark = self.overlay.config.get('theme', 'Темная') != 'Светлая'
        self._dark = dark
        self.setStyleSheet(f"""
            QFrame#outputControls {{ background:{'#121212' if dark else '#f0edf3'};
                border:1px solid {'#584963' if dark else '#bcaacb'}; border-radius:8px; }}
            QLabel, QCheckBox {{ color:{'#eee7f5' if dark else '#302639'}; background:transparent; border:0; font-size:13px; }}
            QLineEdit, QSpinBox, QComboBox {{ background:{'#211d28' if dark else '#faf8fc'};
                color:{'#eee7f5' if dark else '#302639'}; border:1px solid {'#584963' if dark else '#bcaacb'};
                border-radius:5px; padding:3px 6px; font-size:13px; }}
            QComboBox QAbstractItemView {{ background:{'#211d28' if dark else '#faf8fc'};
                color:{'#eee7f5' if dark else '#302639'}; selection-background-color:{'#3c3048' if dark else '#d9cbe5'}; }}
        """)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        self.direction = QtWidgets.QLabel(f'{self.overlay.source_language.upper()} → {self.overlay.target_language.upper()}')
        self.direction.setStyleSheet('font-size:13px; font-weight:600;')
        self.direction.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        header.addWidget(self.direction, 1)
        self.gear = QtWidgets.QPushButton(text(self.language, 'parameters'))
        self.gear.setCheckable(True)
        self.pause_button = QtWidgets.QPushButton(game_mode.game_text(self.language, 'pause'))
        self.stop_button = QtWidgets.QPushButton(game_mode.game_text(self.language, 'stop'))
        for button in (self.gear, self.pause_button, self.stop_button):
            button.setFixedHeight(30)
            button.setStyleSheet(button_qss(dark, 'quiet' if button is self.gear else 'secondary', compact=True))
            header.addWidget(button)
        root.addLayout(header)
        self.panel = QtWidgets.QWidget()
        form = QtWidgets.QVBoxLayout(self.panel)
        form.setContentsMargins(0, 2, 0, 0)
        form.setSpacing(8)
        self.output_combo = QtWidgets.QComboBox()
        self.output_combo.setMinimumHeight(28)
        self.output_combo.setAccessibleName(text(self.language, 'output_choice'))
        form.addWidget(self.output_combo)
        fields = QtWidgets.QGridLayout()
        fields.setHorizontalSpacing(10)
        fields.setVerticalSpacing(6)
        self.font_size = NumberStepper(dark=dark)
        self.font_size.setRange(10, 48)
        self.opacity = NumberStepper(dark=dark)
        self.opacity.setRange(0, 100)
        self.opacity.setSuffix('%')
        for column, key, control in ((0, 'font', self.font_size), (1, 'opacity', self.opacity)):
            label = QtWidgets.QLabel(text(self.language, key))
            label.setBuddy(control)
            control.setAccessibleName(text(self.language, key))
            control.setKeyboardTracking(False)
            control.setFixedHeight(28)
            fields.addWidget(label, 0, column)
            fields.addWidget(control, 1, column)
            fields.setColumnStretch(column, 1)
        form.addLayout(fields)
        self.locked = QtWidgets.QCheckBox(text(self.language, 'locked'))
        gestures = QtWidgets.QHBoxLayout()
        gestures.setSpacing(6)
        gestures.addWidget(self.locked, 1)
        self.move_button = QtWidgets.QPushButton(text(self.language, 'move_short'))
        self.resize_button = QtWidgets.QPushButton(text(self.language, 'resize_short'))
        for button, key in ((self.move_button, 'move'), (self.resize_button, 'resize')):
            button.setToolTip(text(self.language, key))
            button.setFixedHeight(28)
            button.setStyleSheet(button_qss(dark, compact=True))
            button.installEventFilter(self)
            gestures.addWidget(button)
        form.addLayout(gestures)
        template_label = QtWidgets.QLabel(text(self.language, 'session_template'))
        template_label.setStyleSheet('font-size:12px;')
        form.addWidget(template_label)
        templates = QtWidgets.QHBoxLayout()
        templates.setSpacing(6)
        self.template_name = QtWidgets.QComboBox()
        self.template_name.setEditable(True)
        self.template_name.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.template_name.lineEdit().setMaxLength(80)
        self.template_name.lineEdit().setPlaceholderText(text(self.language, 'templates'))
        self.template_name.setMinimumWidth(0)
        self.template_name.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.template_name.setFixedHeight(30)
        templates.addWidget(self.template_name, 1)
        self.save_button = QtWidgets.QPushButton(text(self.language, 'save_short'))
        self.save_button.setStyleSheet(button_qss(dark, 'primary', compact=True))
        self.save_button.setFixedHeight(30)
        templates.addWidget(self.save_button)
        self.delete_button = QtWidgets.QToolButton()
        self.delete_button.setText('×')
        self.delete_button.setToolTip(text(self.language, 'delete'))
        self.delete_button.setAccessibleName(text(self.language, 'delete'))
        self.delete_button.setStyleSheet(button_qss(dark, 'quiet', 'QToolButton', icon=True))
        self.delete_button.setFixedSize(30, 30)
        templates.addWidget(self.delete_button)
        form.addLayout(templates)
        self.notice = QtWidgets.QLabel()
        self.notice.setWordWrap(True)
        self.notice.hide()
        form.addWidget(self.notice)
        root.addWidget(self.panel)
        self.panel.hide()
        self.error_label = QtWidgets.QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)
        self.gear.toggled.connect(self._toggle_panel)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.stop_button.clicked.connect(game_mode.stop_game_mode)
        self.output_combo.currentIndexChanged.connect(self._select_output)
        self.font_size.valueChanged.connect(lambda value: self.overlay.change_style(font_size=value))
        self.opacity.valueChanged.connect(lambda value: self.overlay.change_style(opacity=value))
        self.locked.toggled.connect(self._lock_changed)
        self.template_name.lineEdit().returnPressed.connect(self._save)
        self.template_name.editTextChanged.connect(self._update_template_actions)
        self.save_button.clicked.connect(self._save)
        self.delete_button.clicked.connect(self._delete_template)
        self._refresh_templates(template_name)
        self._refresh_outputs()
        from styled_dialogs import install_accent_controls
        install_accent_controls(self, dark=dark)
        from ui_scaling import desktop_control_scale
        from window_appearance import scale_native_controls
        screen = QtWidgets.QApplication.screenAt(self.overlay.output_rect.center()) or QtWidgets.QApplication.primaryScreen()
        available = screen.availableGeometry()
        self.ui_factor = min(desktop_control_scale(screen), available.width()/430, available.height()/360)
        scale_native_controls(self, self.ui_factor)
        for overlay in self.overlays:
            overlay.controls = self
        self._resize_panel()
        self._capture_excluded = False
        self.set_toolbar_visible(self.overlay.config.get('game_show_toolbar', True))

    def set_toolbar_visible(self, visible):
        self.setVisible(bool(visible))
        if visible:
            self._capture_excluded = game_mode._exclude_from_windows_capture(self)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor('#584963' if self._dark else '#bcaacb'), 1))
        painter.setBrush(QtGui.QColor('#121212' if self._dark else '#f0edf3'))
        radius = 8*self.ui_factor
        painter.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), radius, radius)

    def _toggle_panel(self, visible):
        self.panel.setVisible(visible)
        self._resize_panel()

    def _resize_panel(self):
        if not hasattr(self, 'ui_factor'):
            return
        self.ensurePolished()
        screen = self.screen() if self._placed else QtWidgets.QApplication.screenAt(self.overlay.output_rect.center())
        screen = screen or QtWidgets.QApplication.primaryScreen()
        self.setFixedWidth(min(round(430*self.ui_factor), screen.availableGeometry().width()))
        self.layout().activate()
        height = max(self.layout().totalHeightForWidth(self.width()), self.layout().minimumSize().height())
        self.setFixedHeight(height)
        set_surface_region(self, rounded_region(self.rect(), 8*self.ui_factor), windows=platform_support.IS_WINDOWS)
        self.place()

    def place(self):
        if not hasattr(self, 'ui_factor'):
            return
        screen = self.screen() if self._placed else QtWidgets.QApplication.screenAt(self.overlay.output_rect.center())
        screen = screen or QtWidgets.QApplication.primaryScreen()
        bounds = screen.availableGeometry()
        point = self.pos() if self._placed else QtCore.QPoint(bounds.center().x()-self.width()//2, bounds.top()+12)
        self.move(max(bounds.left(), min(point.x(), bounds.right()-self.width()+1)),
                  max(bounds.top(), min(point.y(), bounds.bottom()-self.height()+1)))
        self._placed = True

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and event.pos().y() < self.gear.geometry().bottom()+8:
            self._drag_offset = event.globalPos()-self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos()-self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        self.place()

    def _refresh_outputs(self):
        with QtCore.QSignalBlocker(self.output_combo):
            self.output_combo.clear()
            for index, overlay in enumerate(self.overlays):
                self.output_combo.addItem(text(self.language, 'area_number').format(number=index+1), overlay)
            self.output_combo.setCurrentIndex(self.overlays.index(self.overlay))
        self.output_combo.setVisible(len(self.overlays) > 1)
        self._select_output()

    def _select_output(self, *_):
        self.overlay = self.output_combo.currentData() or self.overlay
        self._cancel_gesture()
        for field, key in ((self.font_size, 'font_size'), (self.opacity, 'opacity')):
            with QtCore.QSignalBlocker(field):
                field.setValue(self.overlay.output_style[key])
        with QtCore.QSignalBlocker(self.locked):
            self.locked.setChecked(self.overlay.output_style['locked'])
        self.move_button.setEnabled(not self.locked.isChecked())
        self.resize_button.setEnabled(not self.locked.isChecked())

    def _toggle_pause(self):
        paused = not all(item.paused for item in self.overlays)
        for item in self.overlays:
            if item.paused != paused:
                item._toggle_pause()
        self.pause_button.setText(game_mode.game_text(self.language, 'resume' if paused else 'pause'))
        self._resize_panel()

    def _lock_changed(self, locked):
        self._cancel_gesture()
        self.overlay.change_style(locked=locked)
        self.move_button.setEnabled(not locked)
        self.resize_button.setEnabled(not locked)

    def _cancel_gesture(self):
        if self._gesture is not None:
            button = self._gesture[0]
            self._gesture = None
            button.setDown(False)
            if QtWidgets.QWidget.mouseGrabber() is button:
                button.releaseMouse()

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.Hide, QtCore.QEvent.UngrabMouse):
            self._cancel_gesture()
        if watched not in (self.move_button, self.resize_button) or self.overlay.output_style['locked']:
            return super().eventFilter(watched, event)
        if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
            self._gesture = (watched, event.globalPos(), QtCore.QRect(self.overlay.output_rect))
            watched.setDown(True)
            watched.grabMouse()
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
                self._cancel_gesture()
            return True
        return super().eventFilter(watched, event)

    def set_error(self, message, overlay=None):
        if self._closing:
            return
        overlay = overlay or self.overlay
        if message:
            self._errors[overlay] = message
        else:
            self._errors.pop(overlay, None)
        errors = [text(self.language, 'area_number').format(number=index+1)+': '+self._errors[item]
                  for index, item in enumerate(self.overlays) if item in self._errors]
        message = errors[0] if errors else ''
        # Provider diagnostics can be arbitrarily long. Keep the session bar
        # on-screen, with the complete message available on hover.
        compact = self.error_label.fontMetrics().elidedText(
            ' '.join(message.split()), QtCore.Qt.ElideRight,
            max(80, self.width() - round(20 * self.ui_factor)))
        if self.error_label.text() != compact or self.error_label.toolTip() != message:
            self.error_label.setText(compact)
            self.error_label.setToolTip(message)
            self.error_label.setVisible(bool(message))
            self._resize_panel()

    def _refresh_templates(self, selected=''):
        try:
            names = [item['name'] for item in TemplateStore().load()]
        except Exception:
            names = []
        with QtCore.QSignalBlocker(self.template_name):
            self.template_name.clear()
            self.template_name.addItems(names)
            self.template_name.setCurrentIndex(-1)
            self.template_name.setEditText(selected)
        self._template_names = names
        self._update_template_actions()

    def _update_template_actions(self, *_):
        name = self.template_name.currentText().strip()
        self.save_button.setEnabled(bool(name))
        self.delete_button.setEnabled(name in getattr(self, '_template_names', ()))

    def _save(self):
        name = self.template_name.currentText().strip()
        if not name:
            self.notice.setText(text(self.language, 'name_required'))
        else:
            try:
                TemplateStore().save(make_template(name, [item.region for item in self.overlays],
                    [item.output_rect for item in self.overlays], [item.output_style for item in self.overlays],
                    self.overlay.source_language, self.overlay.target_language))
                self.notice.setText(text(self.language, 'saved'))
                self._refresh_templates(name)
            except Exception:
                logging.getLogger('clickntranslate.game').exception('Unable to save output layout')
                self.notice.setText(text(self.language, 'save_error'))
        self.notice.show()
        self._resize_panel()

    def _delete_template(self):
        name = self.template_name.currentText().strip()
        if name not in self._template_names:
            return
        try:
            TemplateStore().delete(name)
            self._refresh_templates()
            self.notice.hide()
        except Exception:
            self.notice.setText(text(self.language, 'save_error'))
            self.notice.show()
        self._resize_panel()

    def detach(self, overlay):
        overlay.controls = None
        self._errors.pop(overlay, None)
        if overlay in self.overlays:
            self.overlays.remove(overlay)
        if not self.overlays:
            self._closing = True
            self.close()
        else:
            if self.overlay is overlay:
                self.overlay = self.overlays[0]
            self._refresh_outputs()
            self.set_error('', overlay)
            self._resize_panel()

    def closeEvent(self, event):
        self._cancel_gesture()
        if not self._closing:
            self._closing = True
            for overlay in self.overlays:
                overlay.controls = None
            game_mode.stop_game_mode()
        event.accept()
