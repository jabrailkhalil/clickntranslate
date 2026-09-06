"""Scale the fixed main UI as one scene, independently of desktop/OCR DPI."""

import os
import math
import sys
import weakref

from PyQt5.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, QSize, QRegularExpression, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QRegularExpressionValidator
from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QLineEdit, QMainWindow, QPushButton,
    QStyle, QStyleOptionButton, QStyleOptionToolButton, QStylePainter, QToolButton, QWidget,
)


BASE_WIDTH, BASE_HEIGHT = 700, 400
# The original 700x400 canvas is now 80%; the default 100% is 875x500.
BASE_SCALE = 80
MIN_SCALE, DEFAULT_SCALE, MAX_SCALE, SCALE_STEP = 80, 100, 200, 5


def configure_qt_platform():
    """Select scalable font rasterization before Qt initializes Windows."""
    if sys.platform != 'win32' or QApplication.instance() is not None:
        return
    platform = os.environ.get('QT_QPA_PLATFORM', 'windows')
    name, _, options = platform.partition(':')
    if name == 'windows' and not any(option.startswith('fontengine=') for option in options.split(':')):
        os.environ['QT_QPA_PLATFORM'] = platform.rstrip(':') + ':fontengine=freetype'


def configure_interface_font():
    """Use grayscale glyph edges that remain clean under the scene transform."""
    app = QApplication.instance()
    font = QFont(app.font())
    if sys.platform == 'win32':
        if font.family() in ('MS Shell Dlg', 'MS Shell Dlg 2', 'MS Sans Serif'):
            font.setFamily('Segoe UI')
        # FreeType rasterizes the outlines at the final scale; vertical hinting
        # keeps stems crisp without forcing glyph widths onto the base grid.
        font.setHintingPreference(QFont.PreferVerticalHinting)
    font.setStyleStrategy(QFont.PreferAntialias | QFont.NoSubpixelAntialias)
    if font != app.font():
        # Set the base before stylesheets resolve their fonts. Changing only
        # the canvas font later does not reach stylesheet-rendered controls.
        app.setFont(font)


def normalize_ui_scale(value):
    if isinstance(value, bool):
        return DEFAULT_SCALE
    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_SCALE
    return max(MIN_SCALE, min(MAX_SCALE, value))


def maximum_ui_scale(available):
    percent = min(available.width() * BASE_SCALE // BASE_WIDTH, available.height() * BASE_SCALE // BASE_HEIGHT)
    return max(MIN_SCALE, min(MAX_SCALE, percent))


def native_window_parent(widget):
    """Keep dialogs/native menus outside the embedded, clipped main canvas."""
    if isinstance(widget, QWidget):
        reference = getattr(widget.window(), '_ui_native_owner', None)
        if reference is not None and reference() is not None:
            return reference()
    return widget


def paint_scaled_icon(painter, button, option):
    """Request source pixels for the final size, not a stretched 24px preview."""
    controller = getattr(native_window_parent(button), '_ui_scale_controller', None)
    scale = controller.effective_percent / BASE_SCALE if controller is not None else 1.0
    density = scale * button.devicePixelRatioF()
    size = button.iconSize()
    requested = QSize(math.ceil(size.width() * density), math.ceil(size.height() * density))
    mode = QIcon.Disabled if not button.isEnabled() else (
        QIcon.Active if option.state & QStyle.State_MouseOver else QIcon.Normal)
    state = QIcon.On if button.isChecked() else QIcon.Off
    pixmap = button.icon().pixmap(requested, mode, state)
    if pixmap.isNull():
        return
    pixmap.setDevicePixelRatio(1)
    fit = min(size.width() / pixmap.width(), size.height() / pixmap.height())
    width, height = pixmap.width() * fit, pixmap.height() * fit
    target = QRectF((button.width() - width) / 2, (button.height() - height) / 2, width, height)
    painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))


class ScaledIconButton(QPushButton):
    def paintEvent(self, event):
        if self.icon().isNull() or self.text():
            return super().paintEvent(event)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.icon = QIcon()
        painter = QStylePainter(self)
        painter.drawControl(QStyle.CE_PushButton, option)
        paint_scaled_icon(painter, self, option)


class ScaledIconToolButton(QToolButton):
    def paintEvent(self, event):
        if self.icon().isNull() or self.text():
            return super().paintEvent(event)
        option = QStyleOptionToolButton()
        self.initStyleOption(option)
        option.icon = QIcon()
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.CC_ToolButton, option)
        paint_scaled_icon(painter, self, option)


class ScalePercentEdit(QLineEdit):
    step_requested = pyqtSignal(int)
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMaxLength(4)
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r'[0-9]{0,3}%?'), self))

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._select_after_click = True
        self.selectAll()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if getattr(self, '_select_after_click', False):
            self.selectAll()
            self._select_after_click = False

    def keyPressEvent(self, event):
        self._select_after_click = False
        if event.key() == Qt.Key_Escape:
            self.cancel_requested.emit()
            self.selectAll()
            event.accept()
        elif event.key() in (Qt.Key_Up, Qt.Key_Down):
            self.step_requested.emit(1 if event.key() == Qt.Key_Up else -1)
            self.selectAll()
            event.accept()
        else:
            super().keyPressEvent(event)


class _ScaleView(QGraphicsView):
    before_mouse_release = pyqtSignal()
    mouse_global_position = None
    mouse_event_type = None

    def viewportEvent(self, event):
        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease):
            # Preserve desktop coordinates through proxy rounding and focus changes.
            self.mouse_global_position = event.globalPos()
            self.mouse_event_type = event.type()
            try:
                if event.type() == QEvent.MouseButtonRelease:
                    self.before_mouse_release.emit()
                return super().viewportEvent(event)
            finally:
                self.mouse_global_position = None
                self.mouse_event_type = None
        return super().viewportEvent(event)


class _InterfaceCanvas(QMainWindow):
    def __init__(self, owner):
        super().__init__()
        self._ui_native_owner = weakref.ref(owner)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setFixedSize(BASE_WIDTH, BASE_HEIGHT)
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):
        self._ui_native_owner().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._ui_native_owner().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._ui_native_owner().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        self._ui_native_owner().dragEnterEvent(event)

    def dropEvent(self, event):
        self._ui_native_owner().dropEvent(event)

    def keyPressEvent(self, event):
        self._ui_native_owner().keyPressEvent(event)


class MainWindowScaleController(QObject):
    changed = pyqtSignal(int, int)  # effective percentage, screen maximum

    def __init__(self, owner):
        super().__init__(owner)
        configure_interface_font()
        self.owner = owner
        self.requested_percent = MIN_SCALE
        self.effective_percent = MIN_SCALE
        self.maximum_percent = MAX_SCALE
        self._screen = None
        self.canvas = _InterfaceCanvas(owner)
        self.view = _ScaleView(owner)
        self.view.setObjectName('mainUiScaleView')
        self.view.viewport().setObjectName('mainUiViewport')
        self.view.setFrameShape(QGraphicsView.NoFrame)
        self.view.setStyleSheet('QGraphicsView#mainUiScaleView { border:0; padding:0; margin:0; }')
        self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.scene = QGraphicsScene(self.view)
        self.view.setScene(self.scene)
        self.proxy = self.scene.addWidget(self.canvas)
        self.proxy.setPos(0, 0)
        self.canvas.hide()
        self.view.setSceneRect(0, 0, BASE_WIDTH, BASE_HEIGHT)
        self.owner.setCentralWidget(self.view)
        handle = owner.windowHandle()
        if handle is not None:
            handle.screenChanged.connect(self._screen_changed)
            self._screen_changed(handle.screen())

    def available_geometry(self):
        handle = self.owner.windowHandle()
        screen = handle.screen() if handle is not None else None
        screen = screen or QApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else QRect(0, 0, 1920, 1080)

    def _screen_changed(self, screen):
        if self._screen is not None:
            try:
                self._screen.availableGeometryChanged.disconnect(self._screen_geometry_changed)
            except (TypeError, RuntimeError):
                pass
        self._screen = screen
        if screen is not None:
            screen.availableGeometryChanged.connect(self._screen_geometry_changed)
        # Qt finishes changing screens before its new logical coordinates are used.
        QTimer.singleShot(0, self.refresh)

    def _screen_geometry_changed(self, _geometry):
        self.refresh()

    def refresh(self):
        self.set_percent(self.requested_percent)

    def set_percent(self, value, anchor_widget=None):
        self.requested_percent = normalize_ui_scale(value)
        available = self.available_geometry()
        self.maximum_percent = maximum_ui_scale(available)
        actual = min(self.requested_percent, self.maximum_percent)
        factor = actual / BASE_SCALE
        width, height = round(BASE_WIDTH * factor), round(BASE_HEIGHT * factor)
        position = self.owner.pos()
        if anchor_widget is not None:
            anchor_global = self.view.mouse_global_position
            if anchor_global is None or not self.view.viewport().rect().contains(self.view.viewport().mapFromGlobal(anchor_global)):
                anchor_global = self.view.viewport().mapToGlobal(self.map_widget_to_view(anchor_widget))
            point = self.proxy.mapFromScene(self.view.mapToScene(self.view.viewport().mapFromGlobal(anchor_global)))
            viewport_offset = self.view.viewport().mapTo(self.owner, QPoint())
            position = (QPointF(anchor_global) - point * factor - QPointF(viewport_offset)).toPoint()
        position.setX(max(available.left(), min(position.x(), available.right() - width + 1)))
        position.setY(max(available.top(), min(position.y(), available.bottom() - height + 1)))
        # Apply each click as a complete size change. Proxy image caches can
        # expose a stretched dirty region while the native window is resizing.
        updates_enabled = self.owner.updatesEnabled()
        self.owner.setUpdatesEnabled(False)
        try:
            self.effective_percent = actual
            self.proxy.setScale(factor)
            self.view.setSceneRect(QRectF(0, 0, width, height))
            self.owner.setFixedSize(width, height)
            self.owner.layout().activate()
            self.owner.move(position)
        finally:
            self.owner.setUpdatesEnabled(updates_enabled)
        self.changed.emit(actual, self.maximum_percent)
        return actual

    def apply_theme(self, stylesheet, background):
        self.canvas.setStyleSheet(stylesheet)
        # The exposed backing surface must use the theme too, including the
        # newly exposed strips before Qt paints the resized canvas over them.
        color = QColor(background)
        # A palette alone is reset by Qt's stylesheet unpolish/polish cycle.
        self.view.setStyleSheet(f'''
            QGraphicsView#mainUiScaleView {{
                border: 0; padding: 0; margin: 0; background-color: {color.name()};
            }}
            QWidget#mainUiViewport {{ background-color: {color.name()}; }}
        ''')
        for widget in (self.owner, self.view, self.view.viewport()):
            palette = widget.palette()
            palette.setColor(QPalette.Window, color)
            if widget is not self.owner:
                palette.setColor(QPalette.Base, color)
            widget.setPalette(palette)
        self.view.viewport().setAutoFillBackground(True)
        self.view.setBackgroundBrush(color)

    def map_widget_to_view(self, widget, point=None):
        point = point if point is not None else widget.rect().center()
        local = widget.mapTo(self.canvas, point)
        return self.view.mapFromScene(self.proxy.mapToScene(QPointF(local)))


def position_embedded_combo_popup(combo, popup, gap):
    """Popup coordinates belong to the scene, not to the native desktop."""
    root = combo.window()
    reference = getattr(root, '_ui_native_owner', None)
    proxy = popup.graphicsProxyWidget()
    if reference is None or proxy is None:
        return False
    top_left = combo.mapTo(root, QPoint())
    below = top_left.y() + combo.height() + gap
    below_space = max(0, root.height() - below - 4)
    above_space = max(0, top_left.y() - gap - 4)
    open_below = popup.height() <= below_space or below_space >= above_space
    space = below_space if open_below else above_space
    height = min(popup.height(), space)
    width = min(popup.width(), root.width() - 8)
    popup.resize(width, max(1, height))
    if popup.layout() is not None:
        popup.layout().activate()
    x = max(4, min(top_left.x(), root.width() - width - 4))
    y = below if open_below else top_left.y() - gap - popup.height()
    scene_position = root.graphicsProxyWidget().mapToScene(QPointF(x, y))
    parent = proxy.parentItem()
    proxy.setPos(parent.mapFromScene(scene_position) if parent is not None else scene_position)
    return True
