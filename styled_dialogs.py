"""Shared, consistently styled dialogs used by every application process."""

from __future__ import annotations

import ctypes
import logging
import os
import re
import sys
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets


# One definition for every tooltip in the application.  It used to be pasted
# into four separate stylesheets, so any widget outside those four got the
# system default instead and the popups did not match each other.
TOOLTIP_QSS = """
    QToolTip {
        background-color: #17131f;
        color: #f7f3ff;
        border: 1px solid #7a5fa1;
        border-radius: 8px;
        padding: 7px 11px;
        font-family: 'Segoe UI';
        font-size: 13px;
        opacity: 245;
    }
"""

# Qt only word-wraps a tooltip when the text looks like rich text
# (QTipLabel does `setWordWrap(Qt::mightBeRichText(text))`).  A long plain
# string is therefore laid out on one endless line and runs off the screen,
# which is why the engine-picker hint was clipped.  Anything longer than this
# gets wrapped to a fixed width; short labels stay snug so "Close" does not
# become a 320px box.
TOOLTIP_WRAP_THRESHOLD = 44
TOOLTIP_WRAP_WIDTH = 320


def tooltip_text(text, width: int = TOOLTIP_WRAP_WIDTH) -> str:
    """Return tooltip markup that wraps consistently at a readable width."""
    value = str(text or "")
    if not value:
        return ""
    if len(value) <= TOOLTIP_WRAP_THRESHOLD and "\n" not in value:
        return value
    import html as _html

    escaped = _html.escape(value).replace("\n", "<br>")
    return f'<qt><div style="width:{int(width)}px">{escaped}</div></qt>'


class _RoundedTooltipFilter(QtCore.QObject):
    """Makes the rounded corners in TOOLTIP_QSS actually round.

    `border-radius` only rounds what Qt paints. The tooltip is a window of its
    own with square edges, so each corner kept a square of the window's own
    background — the sharp black corners you see against the rounded purple
    frame. A translucent background lets the corners show what is behind them.
    """

    def eventFilter(self, watched, event):
        rounded_popup = _is_rounded_popup(watched)
        if event.type() == QtCore.QEvent.Polish and rounded_popup:
            watched.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
            watched.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
            watched.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        if rounded_popup and event.type() in (
            QtCore.QEvent.Polish,
            QtCore.QEvent.Show,
            QtCore.QEvent.Resize,
        ):
            # Qt's stylesheet rounds only the paint; on Windows the native
            # tooltip/popup window itself remains rectangular.  A real window
            # mask removes those four square hover corners.  Apply once now
            # and once after Qt has finished laying out a newly shown tip.
            _apply_rounded_popup_mask(watched)
            QtCore.QTimer.singleShot(
                0, lambda widget=watched: _apply_rounded_popup_mask(widget)
            )
        return False


def _is_tooltip(widget) -> bool:
    try:
        return widget.metaObject().className() == "QTipLabel"
    except Exception:
        return False


def _is_rounded_popup(widget) -> bool:
    try:
        return _is_tooltip(widget) or bool(
            widget.property("clickntranslateRoundedPopup")
        )
    except (AttributeError, RuntimeError):
        return False


def _apply_rounded_popup_mask(widget, radius: float = 8.0) -> None:
    """Clip a tooltip-sized top-level window to true rounded corners."""
    try:
        rect = widget.rect()
        if rect.width() < 2 or rect.height() < 2:
            return
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(rect), radius, radius)
        polygon = path.toFillPolygon().toPolygon()
        widget.setMask(QtGui.QRegion(polygon))
    except (AttributeError, RuntimeError):
        # The shared QTipLabel can be destroyed before the queued pass runs.
        return


_TOOLTIP_FILTER = None


def install_tooltip_style(app=None) -> None:
    """Apply the shared tooltip look to every window, including unstyled ones."""
    global _TOOLTIP_FILTER

    app = app or QtWidgets.QApplication.instance()
    if app is None:
        return
    if _TOOLTIP_FILTER is None:
        _TOOLTIP_FILTER = _RoundedTooltipFilter(app)
        app.installEventFilter(_TOOLTIP_FILTER)
    existing = app.styleSheet() or ""
    if "QToolTip" in existing:
        return
    app.setStyleSheet(existing + TOOLTIP_QSS)


def install_qt_exception_guard() -> None:
    """Log uncaught Qt callback errors instead of letting PyQt abort the GUI."""
    if getattr(sys.excepthook, "_clickntranslate_qt_guard", False):
        return

    previous_hook = sys.excepthook

    def _guard(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            previous_hook(exc_type, exc_value, exc_traceback)
            return
        try:
            logging.getLogger("clickntranslate.qt").critical(
                "Unhandled exception in Qt callback",
                exc_info=(exc_type, exc_value, exc_traceback),
            )
        except Exception:
            try:
                previous_hook(exc_type, exc_value, exc_traceback)
            except Exception:
                pass

    _guard._clickntranslate_qt_guard = True
    sys.excepthook = _guard


def _resource_path(relative_path: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / relative_path)


def _theme_value(widget) -> str:
    """Find the nearest explicit application theme without importing app modules."""
    seen = set()
    current = widget
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        try:
            for attr in ("current_theme", "theme"):
                value = getattr(current, attr, None)
                if isinstance(value, str) and value:
                    return value.lower()

            owner = getattr(current, "owner", None)
            if owner is not None:
                current = owner
                continue

            # SettingsWindow intentionally stores its QWidget parent in a
            # ``parent`` instance attribute, shadowing QObject.parent().  Both
            # forms are valid in this project, so never assume it is callable.
            parent_ref = getattr(current, "parent", None)
            current = parent_ref() if callable(parent_ref) else parent_ref
        except (RuntimeError, TypeError):
            # Theme detection must never escape into a Qt signal handler: an
            # unhandled Python exception there aborts a windowed PyQt process.
            return ""
    return ""


def _uses_dark_theme(widget=None) -> bool:
    value = _theme_value(widget)
    if not value:
        app = QtWidgets.QApplication.instance()
        value = _theme_value(app.activeWindow()) if app is not None else ""
    if any(marker in value for marker in ("свет", "light")):
        return False
    if any(marker in value for marker in ("тем", "dark")):
        return True
    # The application's default and release screenshots use the dark theme.
    return True


#: The accent used by every purple control in the application.
ACCENT = "#7a5fa1"
ACCENT_LIGHT = "#c5b3e9"
ACCENT_HOVER = "#a985d2"


class AccentControlStyle(QtWidgets.QProxyStyle):
    """Paints check boxes in the application's palette.

    Qt draws the platform's own indicator, which on Windows is a bright white
    square — the lightest thing on a dark purple window, and the first thing the
    eye lands on. A stylesheet cannot fix it: styling ``QCheckBox::indicator``
    with colours replaces the native rendering entirely, and the check mark
    disappears with it unless an image file is supplied. Painting the indicator
    here keeps the mark, needs no image assets, and applies to every check box
    under the widget the style is installed on.
    """

    def __init__(self, dark: bool = True):
        # Never pass QApplication.style() here: QProxyStyle takes ownership of
        # the style it is given and would delete the application's own, which
        # crashes the process the next time anything paints. With no argument
        # the proxy defers to the application style without owning it.
        super().__init__()
        self.dark = bool(dark)

    def _draw_chevron(self, option, painter):
        """The drop-down marker for combo boxes.

        A stylesheet that touches ``QComboBox::drop-down`` suppresses the
        platform arrow, and QSS cannot draw a triangle from borders the way CSS
        does — it fills the box instead. So the chevron is painted here.
        """
        rect = QtCore.QRectF(option.rect)
        size = min(rect.width(), rect.height()) * 0.5
        center = rect.center()
        half = size / 2.0
        enabled = bool(option.state & QtWidgets.QStyle.State_Enabled)

        color = QtGui.QColor(ACCENT_LIGHT if self.dark else "#6c5b8c")
        if not enabled:
            color.setAlpha(110)

        pen = QtGui.QPen(color, max(1.6, size * 0.22))
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)

        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        path = QtGui.QPainterPath()
        path.moveTo(center.x() - half, center.y() - half * 0.45)
        path.lineTo(center.x(), center.y() + half * 0.55)
        path.lineTo(center.x() + half, center.y() - half * 0.45)
        painter.drawPath(path)
        painter.restore()

    def _colors(self, option):
        state = option.state
        enabled = bool(state & QtWidgets.QStyle.State_Enabled)
        hovered = bool(state & QtWidgets.QStyle.State_MouseOver)
        checked = bool(state & QtWidgets.QStyle.State_On)
        partially = bool(state & QtWidgets.QStyle.State_NoChange)

        if self.dark:
            empty, border = QtGui.QColor("#17181d"), QtGui.QColor("#4b415d")
        else:
            empty, border = QtGui.QColor("#ffffff"), QtGui.QColor("#c9bdd8")

        if checked or partially:
            fill = QtGui.QColor(ACCENT)
            border = QtGui.QColor(ACCENT_HOVER)
        else:
            fill = empty
            if hovered:
                border = QtGui.QColor(ACCENT_HOVER)

        if not enabled:
            fill.setAlpha(110)
            border.setAlpha(110)
        return fill, border, checked, partially

    #: Check boxes in a list row are a different primitive from a stand-alone
    #: check box, and a checkable drop-down uses the list one.
    _CHECK_ELEMENTS = tuple(
        element for element in (
            getattr(QtWidgets.QStyle, "PE_IndicatorCheckBox", None),
            getattr(QtWidgets.QStyle, "PE_IndicatorViewItemCheck", None),
            getattr(QtWidgets.QStyle, "PE_IndicatorItemViewItemCheck", None),
        )
        if element is not None
    )

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QtWidgets.QStyle.PE_IndicatorArrowDown:
            self._draw_chevron(option, painter)
            return
        if element not in self._CHECK_ELEMENTS:
            super().drawPrimitive(element, option, painter, widget)
            return

        fill, border, checked, partially = self._colors(option)
        rect = QtCore.QRectF(option.rect).adjusted(1.5, 1.5, -1.5, -1.5)
        radius = max(3.0, rect.height() * 0.22)

        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(border, 1.6))
        painter.setBrush(QtGui.QBrush(fill))
        painter.drawRoundedRect(rect, radius, radius)

        if checked:
            mark = QtGui.QPainterPath()
            # Proportional so the mark stays centred at any DPI.
            mark.moveTo(rect.left() + rect.width() * 0.24, rect.top() + rect.height() * 0.52)
            mark.lineTo(rect.left() + rect.width() * 0.43, rect.top() + rect.height() * 0.72)
            mark.lineTo(rect.left() + rect.width() * 0.78, rect.top() + rect.height() * 0.29)
            pen = QtGui.QPen(QtGui.QColor("#ffffff"), max(1.8, rect.height() * 0.14))
            pen.setCapStyle(QtCore.Qt.RoundCap)
            pen.setJoinStyle(QtCore.Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawPath(mark)
        elif partially:
            painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), max(1.8, rect.height() * 0.14)))
            painter.drawLine(
                QtCore.QPointF(rect.left() + rect.width() * 0.26, rect.center().y()),
                QtCore.QPointF(rect.right() - rect.width() * 0.26, rect.center().y()),
            )
        painter.restore()


def accent_check_pixmap(checked: bool, dark: bool = True, size: int = 18) -> QtGui.QPixmap:
    """A check box indicator as a pixmap, for rows in a drop-down list.

    A stylesheet on a combo box makes Qt paint the popup itself, so a proxy
    style never gets to draw the row indicators. Handing the row an icon keeps
    the same look under our own control.
    """
    ratio = QtWidgets.QApplication.instance().devicePixelRatio() if QtWidgets.QApplication.instance() else 1.0
    ratio = max(1.0, float(ratio))
    pixmap = QtGui.QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(QtCore.Qt.transparent)

    option = QtWidgets.QStyleOptionButton()
    option.rect = QtCore.QRect(0, 0, size, size)
    option.state = QtWidgets.QStyle.State_Enabled
    option.state |= QtWidgets.QStyle.State_On if checked else QtWidgets.QStyle.State_Off

    painter = QtGui.QPainter(pixmap)
    try:
        AccentControlStyle(dark).drawPrimitive(
            QtWidgets.QStyle.PE_IndicatorCheckBox, option, painter, None
        )
    finally:
        painter.end()
    return pixmap


def install_accent_controls(widget, dark: bool = True) -> None:
    """Use the accent-painted controls for `widget` and everything inside it."""
    if widget is None:
        return
    try:
        style = AccentControlStyle(dark)
        # setStyle() does not take ownership, so the proxy has to be kept alive
        # by something: parent it to the widget and hold a reference as well.
        style.setParent(widget)
        widget._accent_control_style = style
        widget.setStyle(style)
        for child in widget.findChildren(QtWidgets.QCheckBox):
            child.setStyle(style)
        # Drop-down popups are separate top-level widgets, so the check boxes on
        # checkable rows would otherwise keep the platform's white squares.
        for view in widget.findChildren(QtWidgets.QAbstractItemView):
            view.setStyle(style)
    except Exception:
        # Styling must never break a window that is otherwise fine.
        logging.getLogger("clickntranslate.style").debug("accent controls unavailable", exc_info=True)


def apply_dark_native_frame(widget, enabled: bool = True) -> None:
    """Ask Windows to render a native Qt dialog frame with a dark title bar."""
    if os.name != "nt" or widget is None:
        return
    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(1 if enabled else 0)
        dwmapi = ctypes.windll.dwmapi
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE variants
            try:
                if dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
                ) == 0:
                    break
            except Exception:
                continue
        if enabled:
            # Caption, caption text and border colors on current Windows builds.
            for attribute, color in ((35, 0x00151515), (36, 0x00FFFFFF), (34, 0x002C2C2C)):
                try:
                    color_value = ctypes.c_uint(color)
                    dwmapi.DwmSetWindowAttribute(
                        hwnd,
                        attribute,
                        ctypes.byref(color_value),
                        ctypes.sizeof(color_value),
                    )
                except Exception:
                    continue
    except Exception:
        pass


class NativeDialogFrameFilter(QtCore.QObject):
    """Keeps the title bars of remaining native Qt dialogs consistently dark."""

    def eventFilter(self, watched, event):
        if (
            event.type() == QtCore.QEvent.Show
            and isinstance(watched, QtWidgets.QDialog)
            and not (watched.windowFlags() & QtCore.Qt.FramelessWindowHint)
        ):
            QtCore.QTimer.singleShot(0, lambda dialog=watched: apply_dark_native_frame(dialog, True))
        return super().eventFilter(watched, event)


class _TitleBar(QtWidgets.QFrame):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self._drag_offset = None
        self.setObjectName("styledMessageTitleBar")
        self.setFixedHeight(42)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 6, 0)
        layout.setSpacing(9)

        self.icon_label = QtWidgets.QLabel(self)
        self.icon_label.setObjectName("styledMessageAppIcon")
        self.icon_label.setFixedSize(20, 20)
        icon = QtGui.QIcon(_resource_path("icons/icon.ico"))
        if not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(18, 18))
        layout.addWidget(self.icon_label)

        self.title_label = QtWidgets.QLabel(self)
        self.title_label.setObjectName("styledMessageTitle")
        layout.addWidget(self.title_label, 1)

        self.close_button = QtWidgets.QToolButton(self)
        self.close_button.setObjectName("styledMessageClose")
        self.close_button.setText("×")
        self.close_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_button.setFixedSize(34, 32)
        self.close_button.setToolTip("Close")
        self.close_button.clicked.connect(dialog.reject)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.dialog.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.dialog.move(event.globalPos() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class StyledMessageBox(QtWidgets.QMessageBox):
    """Drop-in QMessageBox with the same chrome as Click'n'Translate windows."""

    _TITLE_HEIGHT = 42

    def __init__(self, parent=None):
        self._styled_ready = False
        self._external_stylesheet = ""
        super().__init__(parent)
        self._styled_ready = True
        self._dark = _uses_dark_theme(parent)
        self._message_icon = self.NoIcon
        self._positioned = False

        self.setWindowFlags(
            (self.windowFlags() | QtCore.Qt.Dialog)
            & ~QtCore.Qt.WindowContextHelpButtonHint
            | QtCore.Qt.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        self.setObjectName("styledMessageBox")
        self.setMinimumWidth(500)
        self.setMaximumWidth(650)

        layout = self.layout()
        if layout is not None:
            margins = layout.contentsMargins()
            layout.setContentsMargins(
                max(20, margins.left()),
                self._TITLE_HEIGHT + 18,
                max(20, margins.right()),
                max(16, margins.bottom()),
            )

        self.title_bar = _TitleBar(self)
        self.title_bar.raise_()
        self._apply_style()

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        bar = getattr(self, "title_bar", None)
        if bar is not None:
            bar.title_label.setText(str(title))

    def setWindowIcon(self, icon):
        super().setWindowIcon(icon)
        bar = getattr(self, "title_bar", None)
        if bar is not None and isinstance(icon, QtGui.QIcon) and not icon.isNull():
            bar.icon_label.setPixmap(icon.pixmap(18, 18))

    def setIcon(self, icon):
        self._message_icon = icon
        super().setIcon(icon)
        if getattr(self, "_styled_ready", False):
            QtCore.QTimer.singleShot(0, self._refresh_status_icon)

    def setIconPixmap(self, pixmap):
        self._message_icon = None
        super().setIconPixmap(pixmap)

    def setStyleSheet(self, style):
        if not getattr(self, "_styled_ready", False):
            super().setStyleSheet(style)
            return
        self._external_stylesheet = str(style or "")
        white_box = re.search(
            r"QMessageBox\s*\{[^}]*background(?:-color)?\s*:\s*(?:#fff(?:fff)?|white)",
            self._external_stylesheet,
            re.IGNORECASE | re.DOTALL,
        )
        dark_box = re.search(
            r"QMessageBox\s*\{[^}]*background(?:-color)?\s*:\s*(?:#(?:0[0-9a-f]{5}|1[0-9a-f]{5}|2[0-9a-f]{5})|black)",
            self._external_stylesheet,
            re.IGNORECASE | re.DOTALL,
        )
        if white_box:
            self._dark = False
        elif dark_box:
            self._dark = True
        self._apply_style()

    def _apply_style(self):
        dark = getattr(self, "_dark", True)
        background = "#101114" if dark else "#f8f8fb"
        panel = "#17181d" if dark else "#ffffff"
        text = "#f5f5f7" if dark else "#17171a"
        muted = "#b8b8c2" if dark else "#55545e"
        border = "#33313c" if dark else "#d7d3df"
        button = "#211f28" if dark else "#ffffff"
        button_hover = "#322d3d" if dark else "#eee9f5"
        qss = f"""
            QWidget#styledMessageBox {{
                background: {background};
                color: {text};
                border: 1px solid {border};
            }}
            QFrame#styledMessageTitleBar {{
                background: #151515;
                border: none;
                border-bottom: 1px solid #29292d;
            }}
            QLabel#styledMessageTitle {{
                color: #f7f7f7;
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#styledMessageAppIcon {{
                background: transparent;
                border: none;
            }}
            QToolButton#styledMessageClose {{
                color: #eeeeee;
                background: transparent;
                border: none;
                border-radius: 4px;
                font-size: 22px;
                font-weight: 300;
            }}
            QToolButton#styledMessageClose:hover {{
                color: #ffffff;
                background: #c42b1c;
            }}
            QWidget#styledMessageBox QLabel {{
                color: {text};
                background: transparent;
                border: none;
                font-size: 13px;
            }}
            QWidget#styledMessageBox QLabel#qt_msgbox_informativelabel {{
                color: {muted};
                font-size: 12px;
            }}
            QWidget#styledMessageBox QPushButton {{
                min-width: 92px;
                min-height: 34px;
                padding: 0 14px;
                color: {text};
                background: {button};
                border: 1px solid #8060a8;
                border-radius: 5px;
                font-size: 13px;
                font-weight: 500;
            }}
            QWidget#styledMessageBox QPushButton:hover {{
                background: {button_hover};
                border-color: #a985d2;
            }}
            QWidget#styledMessageBox QPushButton:pressed {{
                background: #735397;
                color: #ffffff;
            }}
            QWidget#styledMessageBox QPushButton:default {{
                background: #7959a0;
                color: #ffffff;
                border-color: #a985d2;
            }}
        """
        super().setStyleSheet((self._external_stylesheet + "\n" + qss).strip())

    def _status_color_and_glyph(self):
        icon = self._message_icon
        if icon == self.Question:
            return "#2788d7", "?"
        if icon == self.Warning:
            return "#e7a619", "!"
        if icon == self.Critical:
            return "#d94a4a", "×"
        if icon == self.Information:
            return "#7959a0", "i"
        return None, ""

    def _status_pixmap(self, size=42):
        color, glyph = self._status_color_and_glyph()
        if color is None:
            return QtGui.QPixmap()
        ratio = max(1.0, float(self.devicePixelRatioF()))
        px = int(size * ratio)
        pixmap = QtGui.QPixmap(px, px)
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(color))
        painter.drawEllipse(QtCore.QRectF(2, 2, size - 4, size - 4))
        font = QtGui.QFont("Segoe UI", 21)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#ffffff"))
        painter.drawText(QtCore.QRectF(0, 0, size, size), QtCore.Qt.AlignCenter, glyph)
        painter.end()
        return pixmap

    def _refresh_status_icon(self):
        label = self.findChild(QtWidgets.QLabel, "qt_msgboxex_icon_label")
        if label is None:
            return
        pixmap = self._status_pixmap()
        if pixmap.isNull():
            label.hide()
            return
        label.setFixedSize(48, 48)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setPixmap(pixmap)
        label.show()

    def _prepare_contents(self):
        layout = self.layout()
        if layout is not None:
            layout.setContentsMargins(20, self._TITLE_HEIGHT + 18, 20, 16)
        for label in self.findChildren(QtWidgets.QLabel):
            if label.objectName() in {
                "styledMessageTitle",
                "styledMessageAppIcon",
                "qt_msgboxex_icon_label",
            }:
                continue
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setMaximumWidth(505)
        self._refresh_status_icon()
        if layout is not None:
            layout.invalidate()
            layout.activate()
        self.adjustSize()
        if self.width() < self.minimumWidth():
            self.resize(self.minimumWidth(), self.height())
        bar = getattr(self, "title_bar", None)
        if bar is not None:
            bar.title_label.setText(self.windowTitle())
            bar.setGeometry(0, 0, self.width(), self._TITLE_HEIGHT)
            bar.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        bar = getattr(self, "title_bar", None)
        if bar is not None:
            bar.setGeometry(0, 0, self.width(), self._TITLE_HEIGHT)
            bar.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._finish_show)

    def _finish_show(self):
        self._prepare_contents()
        if not self._positioned:
            self._positioned = True
            self._center_on_owner()

    def _center_on_owner(self):
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            available = QtWidgets.QApplication.desktop().availableGeometry(parent)
            # SettingsWindow is embedded inside the frameless main window, so
            # its frameGeometry is parent-relative. Convert its visible center
            # to desktop coordinates before positioning this top-level dialog.
            center = parent.mapToGlobal(parent.rect().center())
        else:
            app = QtWidgets.QApplication.instance()
            active = app.activeWindow() if app is not None else None
            if active is not None and active is not self and active.isVisible():
                available = QtWidgets.QApplication.desktop().availableGeometry(active)
                center = active.mapToGlobal(active.rect().center())
            else:
                available = QtWidgets.QApplication.desktop().availableGeometry(self)
                center = available.center()
        frame = self.frameGeometry()
        frame.moveCenter(center)
        x = max(available.left(), min(frame.left(), available.right() - frame.width() + 1))
        y = max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1))
        self.move(x, y)

    @classmethod
    def _run_standard(cls, parent, title, text, icon, buttons, default_button):
        box = cls(parent)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(icon)
        box.setStandardButtons(buttons)
        if default_button not in (cls.NoButton, None):
            try:
                box.setDefaultButton(default_button)
            except TypeError:
                pass
        return box.exec_()

    @classmethod
    def information(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(
            parent,
            title,
            text,
            cls.Information,
            cls.Ok if buttons is None else buttons,
            cls.NoButton if defaultButton is None else defaultButton,
        )

    @classmethod
    def warning(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(
            parent,
            title,
            text,
            cls.Warning,
            cls.Ok if buttons is None else buttons,
            cls.NoButton if defaultButton is None else defaultButton,
        )

    @classmethod
    def critical(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(
            parent,
            title,
            text,
            cls.Critical,
            cls.Ok if buttons is None else buttons,
            cls.NoButton if defaultButton is None else defaultButton,
        )

    @classmethod
    def question(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(
            parent,
            title,
            text,
            cls.Question,
            (cls.Yes | cls.No) if buttons is None else buttons,
            cls.NoButton if defaultButton is None else defaultButton,
        )


class SilentStyledMessageBox(QtWidgets.QDialog):
    """A QMessageBox-compatible dialog that never asks Windows to play a sound."""

    NoIcon = QtWidgets.QMessageBox.NoIcon
    Information = QtWidgets.QMessageBox.Information
    Warning = QtWidgets.QMessageBox.Warning
    Critical = QtWidgets.QMessageBox.Critical
    Question = QtWidgets.QMessageBox.Question

    NoButton = QtWidgets.QMessageBox.NoButton
    Ok = QtWidgets.QMessageBox.Ok
    Save = QtWidgets.QMessageBox.Save
    SaveAll = QtWidgets.QMessageBox.SaveAll
    Open = QtWidgets.QMessageBox.Open
    Yes = QtWidgets.QMessageBox.Yes
    YesToAll = QtWidgets.QMessageBox.YesToAll
    No = QtWidgets.QMessageBox.No
    NoToAll = QtWidgets.QMessageBox.NoToAll
    Abort = QtWidgets.QMessageBox.Abort
    Retry = QtWidgets.QMessageBox.Retry
    Ignore = QtWidgets.QMessageBox.Ignore
    Close = QtWidgets.QMessageBox.Close
    Cancel = QtWidgets.QMessageBox.Cancel
    Discard = QtWidgets.QMessageBox.Discard
    Help = QtWidgets.QMessageBox.Help
    Apply = QtWidgets.QMessageBox.Apply
    Reset = QtWidgets.QMessageBox.Reset
    RestoreDefaults = QtWidgets.QMessageBox.RestoreDefaults

    InvalidRole = QtWidgets.QMessageBox.InvalidRole
    AcceptRole = QtWidgets.QMessageBox.AcceptRole
    RejectRole = QtWidgets.QMessageBox.RejectRole
    DestructiveRole = QtWidgets.QMessageBox.DestructiveRole
    ActionRole = QtWidgets.QMessageBox.ActionRole
    HelpRole = QtWidgets.QMessageBox.HelpRole
    YesRole = QtWidgets.QMessageBox.YesRole
    NoRole = QtWidgets.QMessageBox.NoRole
    ApplyRole = QtWidgets.QMessageBox.ApplyRole
    ResetRole = QtWidgets.QMessageBox.ResetRole

    _STANDARD_BUTTONS = (
        (Ok, "OK", AcceptRole),
        (Save, "Save", AcceptRole),
        (SaveAll, "Save all", AcceptRole),
        (Open, "Open", AcceptRole),
        (Yes, "Yes", YesRole),
        (YesToAll, "Yes to all", YesRole),
        (No, "No", NoRole),
        (NoToAll, "No to all", NoRole),
        (Abort, "Abort", RejectRole),
        (Retry, "Retry", AcceptRole),
        (Ignore, "Ignore", AcceptRole),
        (Close, "Close", RejectRole),
        (Cancel, "Cancel", RejectRole),
        (Discard, "Discard", DestructiveRole),
        (Help, "Help", HelpRole),
        (Apply, "Apply", ApplyRole),
        (Reset, "Reset", ResetRole),
        (RestoreDefaults, "Restore defaults", ResetRole),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dark = _uses_dark_theme(parent)
        self._external_stylesheet = ""
        self._message_icon = self.NoIcon
        self._clicked_button = None
        self._button_roles = {}
        self._button_standards = {}
        self._standard_buttons = self.NoButton
        self._text_format = QtCore.Qt.AutoText
        self._positioned = False

        self.setWindowFlags(
            QtCore.Qt.Dialog
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowSystemMenuHint
        )
        self.setModal(True)
        self.setObjectName("styledMessageBox")
        self.setMinimumWidth(500)
        self.setMaximumWidth(650)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        self.title_bar = _TitleBar(self)
        outer.addWidget(self.title_bar)

        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(20, 18, 20, 16)
        body.setSpacing(12)
        outer.addLayout(body)

        message_row = QtWidgets.QHBoxLayout()
        message_row.setSpacing(14)
        self.status_label = QtWidgets.QLabel(self)
        self.status_label.setObjectName("styledMessageStatus")
        self.status_label.setFixedSize(48, 48)
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.hide()
        message_row.addWidget(self.status_label, 0, QtCore.Qt.AlignTop)

        text_column = QtWidgets.QVBoxLayout()
        text_column.setSpacing(8)
        self.message_label = QtWidgets.QLabel(self)
        self.message_label.setObjectName("styledMessageText")
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.message_label.setMaximumWidth(505)
        text_column.addWidget(self.message_label)
        self.informative_label = QtWidgets.QLabel(self)
        self.informative_label.setObjectName("styledMessageInformation")
        self.informative_label.setWordWrap(True)
        self.informative_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.informative_label.setMaximumWidth(505)
        self.informative_label.hide()
        text_column.addWidget(self.informative_label)
        message_row.addLayout(text_column, 1)
        body.addLayout(message_row)

        self.details_edit = QtWidgets.QPlainTextEdit(self)
        self.details_edit.setObjectName("styledMessageDetails")
        self.details_edit.setReadOnly(True)
        self.details_edit.setMaximumHeight(145)
        self.details_edit.hide()
        body.addWidget(self.details_edit)

        self.button_row = QtWidgets.QHBoxLayout()
        self.button_row.setSpacing(8)
        self.button_row.addStretch(1)
        body.addLayout(self.button_row)
        self._apply_style()

    def setWindowTitle(self, title):
        super().setWindowTitle(str(title))
        self.title_bar.title_label.setText(str(title))

    def setWindowIcon(self, icon):
        super().setWindowIcon(icon)
        if isinstance(icon, QtGui.QIcon) and not icon.isNull():
            self.title_bar.icon_label.setPixmap(icon.pixmap(18, 18))

    def setText(self, text):
        self.message_label.setTextFormat(self._text_format)
        self.message_label.setText(str(text or ""))

    def text(self):
        return self.message_label.text()

    def setTextFormat(self, text_format):
        self._text_format = text_format
        self.message_label.setTextFormat(text_format)

    def setInformativeText(self, text):
        value = str(text or "")
        self.informative_label.setText(value)
        self.informative_label.setVisible(bool(value))

    def informativeText(self):
        return self.informative_label.text()

    def setDetailedText(self, text):
        value = str(text or "")
        self.details_edit.setPlainText(value)
        self.details_edit.setVisible(bool(value))

    def detailedText(self):
        return self.details_edit.toPlainText()

    def setIcon(self, icon):
        self._message_icon = icon
        self._refresh_status_icon()

    def icon(self):
        return self._message_icon

    def setIconPixmap(self, pixmap):
        self._message_icon = None
        self.status_label.setPixmap(pixmap)
        self.status_label.setVisible(not pixmap.isNull())

    def _status_color_and_glyph(self):
        if self._message_icon == self.Question:
            return "#2788d7", "?"
        if self._message_icon == self.Warning:
            return "#e7a619", "!"
        if self._message_icon == self.Critical:
            return "#d94a4a", "×"
        if self._message_icon == self.Information:
            return "#7959a0", "i"
        return None, ""

    def _status_pixmap(self, size=42):
        color, glyph = self._status_color_and_glyph()
        if color is None:
            return QtGui.QPixmap()
        ratio = max(1.0, float(self.devicePixelRatioF()))
        pixmap = QtGui.QPixmap(int(size * ratio), int(size * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(color))
        painter.drawEllipse(QtCore.QRectF(2, 2, size - 4, size - 4))
        font = QtGui.QFont("Segoe UI", 21, QtGui.QFont.Bold)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#ffffff"))
        painter.drawText(QtCore.QRectF(0, 0, size, size), QtCore.Qt.AlignCenter, glyph)
        painter.end()
        return pixmap

    def _refresh_status_icon(self):
        pixmap = self._status_pixmap()
        self.status_label.setPixmap(pixmap)
        self.status_label.setVisible(not pixmap.isNull())

    def _clear_buttons(self):
        for button in list(self._button_roles):
            self.button_row.removeWidget(button)
            button.deleteLater()
        self._button_roles.clear()
        self._button_standards.clear()
        self._clicked_button = None

    def addButton(self, button_or_text, role=None):
        if isinstance(button_or_text, QtWidgets.QAbstractButton):
            button = button_or_text
            actual_role = self.ActionRole if role is None else role
        elif role is None and isinstance(button_or_text, int):
            standard = button_or_text
            label, actual_role = self._standard_button_details(standard)
            button = QtWidgets.QPushButton(label, self)
            self._button_standards[button] = standard
        else:
            button = QtWidgets.QPushButton(str(button_or_text), self)
            actual_role = self.ActionRole if role is None else role
        self._button_roles[button] = actual_role
        button.clicked.connect(lambda _checked=False, current=button: self._button_clicked(current))
        self.button_row.addWidget(button)
        return button

    def _standard_button_details(self, standard):
        for value, label, role in self._STANDARD_BUTTONS:
            if value == standard:
                return label, role
        return "OK", self.AcceptRole

    def setStandardButtons(self, buttons):
        self._clear_buttons()
        self._standard_buttons = buttons
        for standard, _label, _role in self._STANDARD_BUTTONS:
            if buttons & standard:
                self.addButton(standard)

    def standardButtons(self):
        return self._standard_buttons

    def setDefaultButton(self, button):
        if isinstance(button, int):
            button = self.button(button)
        if isinstance(button, QtWidgets.QPushButton):
            button.setDefault(True)
            button.setFocus(QtCore.Qt.OtherFocusReason)

    def setEscapeButton(self, button):
        self._escape_button = self.button(button) if isinstance(button, int) else button

    def button(self, standard):
        for button, value in self._button_standards.items():
            if value == standard:
                return button
        return None

    def clickedButton(self):
        return self._clicked_button

    def buttonRole(self, button):
        return self._button_roles.get(button, self.InvalidRole)

    def standardButton(self, button):
        return self._button_standards.get(button, self.NoButton)

    def _button_clicked(self, button):
        self._clicked_button = button
        standard = self._button_standards.get(button, self.NoButton)
        role = self._button_roles.get(button, self.InvalidRole)
        result = standard if standard != self.NoButton else QtWidgets.QDialog.Accepted
        if role in (self.RejectRole, self.NoRole):
            result = standard if standard != self.NoButton else QtWidgets.QDialog.Rejected
        self.done(result)

    def setStyleSheet(self, style):
        self._external_stylesheet = str(style or "")
        if re.search(r"QMessageBox\s*\{[^}]*background(?:-color)?\s*:\s*(?:#fff(?:fff)?|white)", self._external_stylesheet, re.I | re.S):
            self._dark = False
        elif re.search(r"QMessageBox\s*\{[^}]*background(?:-color)?\s*:\s*(?:#(?:0[0-9a-f]{5}|1[0-9a-f]{5}|2[0-9a-f]{5})|black)", self._external_stylesheet, re.I | re.S):
            self._dark = True
        self._apply_style()

    def _apply_style(self):
        dark = self._dark
        background = "#101114" if dark else "#f8f8fb"
        panel = "#17181d" if dark else "#ffffff"
        text = "#f5f5f7" if dark else "#17171a"
        muted = "#b8b8c2" if dark else "#55545e"
        border = "#33313c" if dark else "#d7d3df"
        button = "#211f28" if dark else "#ffffff"
        button_hover = "#322d3d" if dark else "#eee9f5"
        qss = f"""
            QDialog#styledMessageBox {{ background: {background}; color: {text}; border: 1px solid {border}; }}
            QFrame#styledMessageTitleBar {{ background: #151515; border: none; border-bottom: 1px solid #29292d; }}
            QLabel#styledMessageTitle {{ color: #f7f7f7; background: transparent; border: none; font-size: 13px; font-weight: 600; }}
            QLabel#styledMessageAppIcon {{ background: transparent; border: none; }}
            QToolButton#styledMessageClose {{ color: #eeeeee; background: transparent; border: none; border-radius: 4px; font-size: 22px; }}
            QToolButton#styledMessageClose:hover {{ color: #ffffff; background: #c42b1c; }}
            QLabel#styledMessageText {{ color: {text}; font-size: 13px; background: transparent; }}
            QLabel#styledMessageInformation {{ color: {muted}; font-size: 12px; background: transparent; }}
            QPlainTextEdit#styledMessageDetails {{ color: {muted}; background: {panel}; border: 1px solid {border}; border-radius: 5px; padding: 7px; }}
            QDialog#styledMessageBox QPushButton {{ min-width: 92px; min-height: 34px; padding: 0 14px; color: {text}; background: {button}; border: 1px solid #8060a8; border-radius: 5px; font-size: 13px; font-weight: 500; }}
            QDialog#styledMessageBox QPushButton:hover {{ background: {button_hover}; border-color: #a985d2; }}
            QDialog#styledMessageBox QPushButton:pressed {{ background: #735397; color: #ffffff; }}
            QDialog#styledMessageBox QPushButton:default {{ background: #7959a0; color: #ffffff; border-color: #a985d2; }}
        """
        super().setStyleSheet((self._external_stylesheet + "\n" + qss).strip())

    def _center_on_owner(self):
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            available = QtWidgets.QApplication.desktop().availableGeometry(parent)
            center = parent.mapToGlobal(parent.rect().center())
        else:
            app = QtWidgets.QApplication.instance()
            active = app.activeWindow() if app is not None else None
            if active is not None and active is not self and active.isVisible():
                available = QtWidgets.QApplication.desktop().availableGeometry(active)
                center = active.mapToGlobal(active.rect().center())
            else:
                available = QtWidgets.QApplication.desktop().availableGeometry(self)
                center = available.center()
        frame = self.frameGeometry()
        frame.moveCenter(center)
        x = max(available.left(), min(frame.left(), available.right() - frame.width() + 1))
        y = max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1))
        self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        self.adjustSize()
        if self.width() < self.minimumWidth():
            self.resize(self.minimumWidth(), self.height())
        if not self._positioned:
            self._positioned = True
            QtCore.QTimer.singleShot(0, self._center_on_owner)

    @classmethod
    def _run_standard(cls, parent, title, text, icon, buttons, default_button):
        box = cls(parent)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(icon)
        box.setStandardButtons(buttons)
        if default_button not in (cls.NoButton, None):
            box.setDefaultButton(default_button)
        return box.exec_()

    @classmethod
    def information(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(parent, title, text, cls.Information, cls.Ok if buttons is None else buttons, cls.NoButton if defaultButton is None else defaultButton)

    @classmethod
    def warning(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(parent, title, text, cls.Warning, cls.Ok if buttons is None else buttons, cls.NoButton if defaultButton is None else defaultButton)

    @classmethod
    def critical(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(parent, title, text, cls.Critical, cls.Ok if buttons is None else buttons, cls.NoButton if defaultButton is None else defaultButton)

    @classmethod
    def question(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._run_standard(parent, title, text, cls.Question, (cls.Yes | cls.No) if buttons is None else buttons, cls.NoButton if defaultButton is None else defaultButton)


# All application modules import this public name.  Keeping the legacy class
# above makes old pickles/tests harmless while the actual UI uses only QDialog,
# never QMessageBox (which can trigger the Windows notification sound).
StyledMessageBox = SilentStyledMessageBox
