"""Developer-only visual layout editor for Click'n'Translate.

Run it through ``python main.py --layout-editor``.  The editor overlays the
real application widgets, so language and theme changes exercise exactly the
same fixed-size UI that ships to users.  It writes only ``ui_layout_draft.json``
next to this module; normal application launches deliberately ignore the file.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from button_styles import standard_buttons

from PyQt5 import QtCore, QtGui, QtWidgets, sip


HOTKEY_KEYS = (
    "ocr",
    "copy",
    "fullscreen",
    "toggle",
    "selection",
    "game",
    "replace",
)
DEFAULT_LAYOUT = {
    "main": {
        "hotkey_order": [*HOTKEY_KEYS, None],
        "hotkey_horizontal_spacing": 28,
        "engine_status_width": 672,
    },
    "settings": {
        "actions_footer_gap": 12,
    },
    # Free-form button positions are grouped per preview screen.  They are
    # design coordinates only; ordinary application launches never load them.
    "widgets": {
        "main": {},
        "settings0": {},
        "settings1": {},
        "settings2": {},
    },
    "editor": {
        "snap_enabled": True,
        "grid_size": 8,
    },
}
DEFAULT_DRAFT_PATH = Path(__file__).with_name("ui_layout_draft.json")


def normalized_layout(values=None):
    """Return a complete, bounded draft without trusting hand-edited JSON."""
    result = copy.deepcopy(DEFAULT_LAYOUT)
    values = values if isinstance(values, dict) else {}
    main_values = values.get("main") if isinstance(values.get("main"), dict) else {}
    settings_values = (
        values.get("settings") if isinstance(values.get("settings"), dict) else {}
    )

    requested = main_values.get("hotkey_order")
    requested = list(requested) if isinstance(requested, (list, tuple)) else []
    order = []
    used = set()
    for key in requested[:8]:
        if key is None:
            order.append(None)
        elif key in HOTKEY_KEYS and key not in used:
            order.append(key)
            used.add(key)
        else:
            order.append(None)
    for key in HOTKEY_KEYS:
        if key in used:
            continue
        try:
            empty = order.index(None)
        except ValueError:
            order.append(key)
        else:
            order[empty] = key
        used.add(key)
    result["main"]["hotkey_order"] = (order + [None] * 8)[:8]

    def bounded(section, key, low, high):
        try:
            value = int(section.get(key, result["main"].get(key, 0)))
        except (TypeError, ValueError):
            value = result["main"].get(key, low)
        return max(low, min(high, value))

    result["main"]["hotkey_horizontal_spacing"] = bounded(
        main_values, "hotkey_horizontal_spacing", 0, 40
    )
    result["main"]["engine_status_width"] = bounded(
        main_values, "engine_status_width", 480, 672
    )
    try:
        gap = int(settings_values.get("actions_footer_gap", 12))
    except (TypeError, ValueError):
        gap = 12
    result["settings"]["actions_footer_gap"] = max(4, min(64, gap))
    widget_values = values.get("widgets")
    widget_values = widget_values if isinstance(widget_values, dict) else {}
    for screen in result["widgets"]:
        screen_values = widget_values.get(screen)
        if not isinstance(screen_values, dict):
            continue
        for key, position in screen_values.items():
            if not isinstance(key, str) or not isinstance(position, dict):
                continue
            try:
                x = int(position.get("x"))
                y = int(position.get("y"))
            except (TypeError, ValueError):
                continue
            # The fixed preview is 700x400.  Keep a generous valid range here;
            # the live overlay clamps against the real button dimensions.
            clean_position = {
                "x": max(0, min(699, x)),
                "y": max(0, min(399, y)),
            }
            for dimension, low, high in (("w", 1, 700), ("h", 1, 400)):
                if dimension not in position:
                    continue
                try:
                    clean_position[dimension] = max(
                        low, min(high, int(position[dimension]))
                    )
                except (TypeError, ValueError):
                    pass
            if isinstance(position.get("text"), str):
                clean_position["text"] = position["text"][:500]
            result["widgets"][screen][key] = clean_position
    editor_values = values.get("editor")
    editor_values = editor_values if isinstance(editor_values, dict) else {}
    result["editor"]["snap_enabled"] = bool(
        editor_values.get("snap_enabled", True)
    )
    try:
        grid_size = int(editor_values.get("grid_size", 8))
    except (TypeError, ValueError):
        grid_size = 8
    result["editor"]["grid_size"] = max(2, min(32, grid_size))
    return result


def load_layout_draft(path=DEFAULT_DRAFT_PATH):
    path = Path(path)
    try:
        return normalized_layout(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return normalized_layout()


def save_layout_draft(values, path=DEFAULT_DRAFT_PATH):
    path = Path(path)
    clean = normalized_layout(values)
    path.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return clean


class LayoutEditorOverlay(QtWidgets.QWidget):
    """Transparent hit surface that edits real layout constraints."""

    accent = QtGui.QColor("#b88cff")
    accent_fill = QtGui.QColor(184, 140, 255, 34)
    slot_ink = QtGui.QColor(100, 125, 156, 150)

    def __init__(self, editor):
        super().__init__(editor.preview.central_widget)
        self.editor = editor
        self.setObjectName("layoutEditorOverlay")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self._active = None
        self._press_pos = QtCore.QPoint()
        self._origin_value = 0
        self._ghost_offset = QtCore.QPoint()
        self._detached_buttons = {}
        self._button_drag_origin = QtCore.QPoint()
        self._button_resize_origin = QtCore.QSize()
        self._resize_target = None
        self._selected_id = None
        self._selected_ids = set()
        self._marquee_rect = QtCore.QRect()
        self._group_drag_origins = {}
        self.sync_geometry()
        self.show()
        self.raise_()

    @staticmethod
    def _is_decorative_element(widget):
        """Leaf frames used as separators, rules and visual accents."""
        if widget is None or sip.isdeleted(widget):
            return False
        try:
            name = widget.objectName().lower()
            named_rule = any(
                token in name for token in ("separator", "divider", "line", "rule")
            )
            plain_frame = type(widget) is QtWidgets.QFrame
            if not (named_rule or plain_frame):
                return False
            return not any(
                child.isVisible()
                for child in widget.findChildren(
                    QtWidgets.QWidget, options=QtCore.Qt.FindDirectChildrenOnly
                )
            )
        except RuntimeError:
            return False

    @staticmethod
    def _is_movable_control(widget):
        if widget is None or sip.isdeleted(widget):
            return False
        try:
            # Shortcut rows have their own drag/swap targets. Their labels
            # remain independently editable, but the button container must
            # stay in its grid instead of being detached a second time.
            if widget.objectName() == "mainHotkeyPair":
                return False
            return (
                isinstance(
                    widget,
                    (
                        QtWidgets.QAbstractButton,
                        QtWidgets.QComboBox,
                        QtWidgets.QLabel,
                        QtWidgets.QSlider,
                    ),
                )
                or LayoutEditorOverlay._is_decorative_element(widget)
            )
        except RuntimeError:
            return False

    @staticmethod
    def _control_label(widget):
        text_method = getattr(widget, "text", None)
        if callable(text_method):
            try:
                value = str(text_method() or "").replace("&", "")
                if value:
                    return value
            except TypeError:
                pass
        current_text = getattr(widget, "currentText", None)
        if callable(current_text):
            value = str(current_text() or "")
            if value:
                return value
        return widget.objectName() or widget.metaObject().className()

    @staticmethod
    def _editable_text(widget):
        getter = getattr(widget, "text", None)
        setter = getattr(widget, "setText", None)
        if not callable(getter) or not callable(setter):
            return None
        try:
            return str(getter())
        except TypeError:
            return None

    def _button_attribute_names(self):
        """Map live movable controls to stable Python attribute names."""
        owners = [self.editor.preview]
        settings = getattr(self.editor.preview, "settings_window", None)
        if settings is not None and not sip.isdeleted(settings):
            owners.append(settings)
        names = {}
        for owner in owners:
            for name, value in vars(owner).items():
                if isinstance(value, QtWidgets.QWidget) and self._is_movable_control(value):
                    names.setdefault(value, name)
                elif isinstance(value, (list, tuple)):
                    for index, item in enumerate(value):
                        if isinstance(item, QtWidgets.QWidget) and self._is_movable_control(item):
                            names.setdefault(item, f"{name}_{index}")
                elif isinstance(value, dict):
                    for item_key, item in value.items():
                        if isinstance(item, QtWidgets.QWidget) and self._is_movable_control(item):
                            names.setdefault(item, f"{name}_{item_key}")
        for key, pair in (
            getattr(self.editor.preview, "main_hotkey_references", {}) or {}
        ).items():
            names.setdefault(pair.value_label, f"hotkey_value_{key}")
        return names

    def _grid_size(self):
        return int(self.editor.values.get("editor", {}).get("grid_size", 8))

    @staticmethod
    def _is_descendant_of(widget, ancestor):
        if widget is None or ancestor is None:
            return False
        try:
            current = widget
            while current is not None:
                if current is ancestor:
                    return True
                current = current.parentWidget()
        except RuntimeError:
            return False
        return False

    def _belongs_to_active_screen(self, widget):
        """Do not pull covered Settings controls above the active page.

        Settings keeps its general form alive underneath pages two and three.
        QWidget.isVisible() therefore remains true for those covered controls.
        Reparenting them to the editor overlay used to lift the hidden form on
        top of the active page, making page two appear absent and scrambled.
        """
        if self.editor.screen == "main":
            return True
        settings = getattr(self.editor.preview, "settings_window", None)
        if settings is None or sip.isdeleted(settings):
            return False
        if not self._is_descendant_of(widget, settings):
            # Persistent application chrome (flag, theme, FAQ, close, back).
            return True
        updates = getattr(settings, "settings_updates_page", None)
        game = getattr(settings, "settings_game_page", None)
        footer = getattr(settings, "settings_page_footer", None)
        if self.editor.screen == "settings0":
            return not (
                self._is_descendant_of(widget, updates)
                or self._is_descendant_of(widget, game)
            )
        active_page = updates if self.editor.screen == "settings1" else game
        return self._is_descendant_of(widget, active_page) or self._is_descendant_of(
            widget, footer
        )

    def _snap(self, value):
        if not self.editor.values.get("editor", {}).get("snap_enabled", True):
            return int(value)
        step = self._grid_size()
        return int(round(float(value) / step) * step)

    def _snap_position(self, x, y, width, height):
        return (
            max(0, min(self.width() - width, self._snap(x))),
            max(0, min(self.height() - height, self._snap(y))),
        )

    def _snap_size(self, width, height, minimum=(18, 16)):
        return (
            max(minimum[0], min(self.width(), self._snap(width))),
            max(minimum[1], min(self.height(), self._snap(height))),
        )

    def attach_buttons(self):
        """Put every visible button on the free-moving design layer.

        A same-size placeholder remains in the production layout.  The page
        therefore keeps its real spacing while the actual styled widget can be
        moved anywhere inside the fixed preview.
        """
        self.restore_buttons()
        preview = self.editor.preview
        attribute_names = self._button_attribute_names()
        candidates = [
            widget
            for widget in getattr(preview, 'ui_root', preview).findChildren(QtWidgets.QWidget)
            if self._is_movable_control(widget)
            and widget is not self
            and widget.isVisible()
            and not sip.isdeleted(widget)
            and self._belongs_to_active_screen(widget)
        ]
        used_keys = set()
        for index, button in enumerate(candidates):
            parent = button.parentWidget()
            if parent is None or parent is self or sip.isdeleted(parent):
                continue
            # QMainWindow owns a private QMainWindowLayout.  It is not a
            # regular content layout and calling replaceWidget() on it emits
            # warnings (and can disturb custom title-bar controls).  Direct
            # window children are restored by their exact geometry instead.
            parent_layout = None if parent is getattr(preview, 'ui_root', preview) else parent.layout()
            original_rect = self._widget_rect(button)
            if not original_rect.isValid():
                continue
            base_key = (
                attribute_names.get(button)
                or button.objectName()
                or f"{button.metaObject().className()}_{index}"
            )
            key = str(base_key)
            suffix = 2
            while key in used_keys:
                key = f"{base_key}_{suffix}"
                suffix += 1
            used_keys.add(key)

            original_geometry = QtCore.QRect(button.geometry())
            placeholder = None
            if parent_layout is not None:
                placeholder = QtWidgets.QWidget(parent)
                placeholder.setObjectName("layoutEditorPlaceholder")
                placeholder.setFixedSize(button.size())
                placeholder.setSizePolicy(button.sizePolicy())
                old_item = parent_layout.replaceWidget(
                    button,
                    placeholder,
                    QtCore.Qt.FindChildrenRecursively,
                )
                if old_item is None:
                    placeholder.deleteLater()
                    placeholder = None
                else:
                    del old_item
            was_visible = button.isVisible()
            original_cursor = button.cursor()
            original_size = button.size()
            original_minimum = button.minimumSize()
            original_maximum = button.maximumSize()
            original_text = self._editable_text(button)
            button.setParent(self)
            button.setCursor(QtCore.Qt.SizeAllCursor)
            button.installEventFilter(self)
            position = (
                self.editor.values.get("widgets", {})
                .get(self.editor.screen, {})
                .get(key, {})
            )
            if "text" in position and original_text is not None:
                button.setText(str(position["text"]))
            x = int(position.get("x", original_rect.x()))
            y = int(position.get("y", original_rect.y()))
            if "w" in position or "h" in position:
                minimum = (1, 1) if self._is_decorative_element(button) else (18, 16)
                width, height = self._snap_size(
                    int(position.get("w", button.width())),
                    int(position.get("h", button.height())),
                    minimum=minimum,
                )
                button.setFixedSize(width, height)
            if position:
                x, y = self._snap_position(x, y, button.width(), button.height())
            else:
                x = max(0, min(self.width() - button.width(), x))
                y = max(0, min(self.height() - button.height(), y))
            button.move(x, y)
            button.setVisible(was_visible)
            button.raise_()
            self._detached_buttons[button] = {
                "key": key,
                "parent": parent,
                "layout": parent_layout,
                "placeholder": placeholder,
                "visible": was_visible,
                "cursor": original_cursor,
                "size": original_size,
                "minimum": original_minimum,
                "maximum": original_maximum,
                "geometry": original_geometry,
                "absolute": original_rect,
                "text": original_text,
            }
        self.raise_detached_buttons()
        self.update()

    def raise_detached_buttons(self):
        self.raise_()
        for button in tuple(self._detached_buttons):
            if not sip.isdeleted(button):
                button.raise_()

    def restore_buttons(self):
        """Return design-layer buttons to their original production layouts."""
        for button, info in list(self._detached_buttons.items()):
            placeholder = info["placeholder"]
            parent = info["parent"]
            layout = info["layout"]
            try:
                button.removeEventFilter(self)
                button.hide()
                button.setParent(parent)
                if layout is not None and placeholder is not None:
                    old_item = layout.replaceWidget(
                        placeholder,
                        button,
                        QtCore.Qt.FindChildrenRecursively,
                    )
                    if old_item is not None:
                        del old_item
                button.setCursor(info["cursor"])
                button.setMinimumSize(info["minimum"])
                button.setMaximumSize(info["maximum"])
                button.resize(info["size"])
                if info["text"] is not None:
                    button.setText(info["text"])
                button.setVisible(bool(info["visible"]))
                if placeholder is not None:
                    placeholder.setParent(None)
                    placeholder.deleteLater()
                if layout is not None and placeholder is not None:
                    layout.invalidate()
                    layout.activate()
                else:
                    button.setGeometry(info["geometry"])
            except RuntimeError:
                pass
        self._detached_buttons.clear()
        self._active = None

    def eventFilter(self, watched, event):
        info = self._detached_buttons.get(watched)
        if info is None:
            return super().eventFilter(watched, event)
        event_type = event.type()
        if event_type == QtCore.QEvent.MouseMove and self._active is None:
            resize_corner = (
                watched.width() - event.pos().x() <= 12
                and watched.height() - event.pos().y() <= 12
            )
            watched.setCursor(
                QtCore.Qt.SizeFDiagCursor
                if resize_corner
                else QtCore.Qt.SizeAllCursor
            )
            return True
        if event_type == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
            target_id = f"button:{info['key']}"
            resize_corner = (
                watched.width() - event.pos().x() <= 12
                and watched.height() - event.pos().y() <= 12
            )
            keep_group = target_id in self._selected_ids and len(self._selected_ids) > 1
            self.editor.select_target(target_id, preserve_group=keep_group)
            self.editor.begin_change()
            self._group_drag_origins = {}
            if keep_group and not resize_corner:
                self._group_drag_origins = {
                    control: QtCore.QPoint(control.pos())
                    for control, control_info in self._detached_buttons.items()
                    if f"button:{control_info['key']}" in self._selected_ids
                    and not sip.isdeleted(control)
                }
            self._active = (
                f"button-resize:{info['key']}"
                if resize_corner
                else f"button:{info['key']}"
            )
            self._press_pos = watched.pos() + event.pos()
            self._button_drag_origin = watched.pos()
            self._button_resize_origin = watched.size()
            watched.setCursor(
                QtCore.Qt.SizeFDiagCursor
                if resize_corner
                else QtCore.Qt.ClosedHandCursor
            )
            return True
        if event_type == QtCore.QEvent.MouseMove and self._active == f"button-resize:{info['key']}":
            local_press = self._press_pos - self._button_drag_origin
            delta = event.pos() - local_press
            minimum = (1, 1) if self._is_decorative_element(watched) else (18, 16)
            width, height = self._snap_size(
                self._button_resize_origin.width() + delta.x(),
                self._button_resize_origin.height() + delta.y(),
                minimum=minimum,
            )
            width = min(width, self.width() - watched.x())
            height = min(height, self.height() - watched.y())
            watched.setFixedSize(width, height)
            watched.raise_()
            self.update()
            self.editor.update_selected_properties()
            return True
        if event_type == QtCore.QEvent.MouseMove and self._active == f"button:{info['key']}":
            current = watched.pos() + event.pos()
            delta = current - self._press_pos
            x, y = self._snap_position(
                self._button_drag_origin.x() + delta.x(),
                self._button_drag_origin.y() + delta.y(),
                watched.width(),
                watched.height(),
            )
            effective_delta = QtCore.QPoint(
                x - self._button_drag_origin.x(),
                y - self._button_drag_origin.y(),
            )
            if self._group_drag_origins:
                min_dx = max(-origin.x() for origin in self._group_drag_origins.values())
                min_dy = max(-origin.y() for origin in self._group_drag_origins.values())
                max_dx = min(
                    self.width() - control.width() - origin.x()
                    for control, origin in self._group_drag_origins.items()
                )
                max_dy = min(
                    self.height() - control.height() - origin.y()
                    for control, origin in self._group_drag_origins.items()
                )
                effective_delta.setX(max(min_dx, min(max_dx, effective_delta.x())))
                effective_delta.setY(max(min_dy, min(max_dy, effective_delta.y())))
                for control, origin in self._group_drag_origins.items():
                    control.move(origin + effective_delta)
                    control.raise_()
            else:
                watched.move(x, y)
                watched.raise_()
            self.update()
            self.editor.update_selected_properties()
            return True
        if event_type == QtCore.QEvent.MouseButtonRelease and self._active == f"button-resize:{info['key']}":
            positions = self.editor.values.setdefault("widgets", {}).setdefault(
                self.editor.screen, {}
            )
            previous = positions.get(info["key"], {})
            positions[info["key"]] = {
                "x": watched.x(),
                "y": watched.y(),
                "w": watched.width(),
                "h": watched.height(),
                **({"text": previous["text"]} if "text" in previous else {}),
            }
            watched.setCursor(QtCore.Qt.SizeAllCursor)
            self._active = None
            self.editor.persist(
                f"Размер «{self._control_label(watched)}» сохранён"
            )
            self.editor.update_selected_properties()
            self.update()
            return True
        if event_type == QtCore.QEvent.MouseButtonRelease and self._active == f"button:{info['key']}":
            positions = self.editor.values.setdefault("widgets", {}).setdefault(
                self.editor.screen, {}
            )
            moved_controls = self._group_drag_origins or {watched: watched.pos()}
            for control in moved_controls:
                control_info = self._detached_buttons[control]
                previous = positions.get(control_info["key"], {})
                positions[control_info["key"]] = {
                    "x": control.x(),
                    "y": control.y(),
                    **({key: previous[key] for key in ("w", "h", "text") if key in previous}),
                }
            watched.setCursor(QtCore.Qt.SizeAllCursor)
            self._active = None
            self._group_drag_origins = {}
            self.editor.persist(
                "Группа элементов сохранена"
                if len(moved_controls) > 1
                else f"Элемент «{self._control_label(watched)}» сохранён"
            )
            self.editor.update_selected_properties()
            self.update()
            return True
        # Suppress clicks, keyboard activation and context menus in the
        # constructor: editing layout must never trigger Reset, Update, etc.
        if event_type in {
            QtCore.QEvent.MouseButtonDblClick,
            QtCore.QEvent.ContextMenu,
            QtCore.QEvent.Wheel,
            QtCore.QEvent.KeyPress,
            QtCore.QEvent.KeyRelease,
        }:
            return True
        return False

    def sync_geometry(self):
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self.raise_()
        self.update()

    def _widget_rect(self, widget):
        if widget is None or sip.isdeleted(widget):
            return QtCore.QRect()
        try:
            if not widget.isVisible():
                return QtCore.QRect()
            # QWidget.mapTo() can enter native coordinate conversion while a
            # previous page is pending deleteLater(); on PyQt5/Windows that
            # occasionally dereferences the old native handle.  These widgets
            # all live below the central widget, so summing ordinary child
            # geometries is both sufficient and safe during page rebuilds.
            root = self.parentWidget()
            preview = getattr(self.editor.preview, 'ui_root', self.editor.preview)
            current = widget
            top_left = QtCore.QPoint()
            while (
                current is not None
                and current is not root
                and current is not preview
            ):
                if sip.isdeleted(current):
                    return QtCore.QRect()
                top_left += current.geometry().topLeft()
                current = current.parentWidget()
            if current is not root:
                if current is not preview:
                    return QtCore.QRect()
                # Title-bar controls are direct descendants of QMainWindow,
                # not its central widget. Convert their window-relative point
                # into the overlay's central-widget coordinates.
                top_left -= root.geometry().topLeft()
            return QtCore.QRect(top_left, widget.size())
        except RuntimeError:
            return QtCore.QRect()

    def _main_slots(self):
        preview = self.editor.preview
        area = getattr(preview, "main_hotkey_area", None)
        grid = getattr(preview, "main_hotkey_grid", None)
        if area is None or grid is None:
            return []
        area_rect = self._widget_rect(area)
        if not area_rect.isValid():
            return []
        slots = []
        for slot in range(8):
            row, column = divmod(slot, 2)
            rect = grid.cellRect(row, column).translated(area_rect.topLeft())
            slots.append(rect)
        return slots

    def _resizable_widgets(self):
        """Stable cards whose real size can be tuned from the overlay."""
        preview = self.editor.preview
        if self.editor.screen != "main":
            return []
        widgets = [
            ("main_composer", getattr(preview, "main_composer", None), "поле сообщения"),
            ("hotkey_language_bar", getattr(preview, "hotkey_language_bar", None), "языки режимов"),
            ("main_hotkey_area", getattr(preview, "main_hotkey_area", None), "список горячих клавиш"),
        ]
        for key, widget in (getattr(preview, "main_hotkey_references", {}) or {}).items():
            widgets.append((f"hotkey_card_{key}", widget, f"строка {key}"))
        return [item for item in widgets if item[1] is not None and not sip.isdeleted(item[1])]

    def apply_resizable_drafts(self):
        screen_values = self.editor.values.get("widgets", {}).get(
            self.editor.screen, {}
        )
        for key, widget, _label in self._resizable_widgets():
            if not hasattr(widget, "_layout_editor_original_constraints"):
                widget._layout_editor_original_constraints = (
                    QtCore.QSize(widget.size()),
                    QtCore.QSize(widget.minimumSize()),
                    QtCore.QSize(widget.maximumSize()),
                )
            position = screen_values.get(key, {})
            if "w" in position or "h" in position:
                width, height = self._snap_size(
                    int(position.get("w", widget.width())),
                    int(position.get("h", widget.height())),
                )
                widget.setFixedSize(width, height)
            else:
                original, minimum, maximum = widget._layout_editor_original_constraints
                widget.setMinimumSize(minimum)
                widget.setMaximumSize(maximum)
                widget.resize(original)
            parent = widget.parentWidget()
            if parent is not None and parent.layout() is not None:
                parent.layout().invalidate()
                parent.layout().activate()

    def targets(self):
        preview = self.editor.preview
        targets = []
        for button, info in self._detached_buttons.items():
            if sip.isdeleted(button) or not button.isVisible():
                continue
            targets.append({
                "id": f"button:{info['key']}",
                "label": self._control_label(button) or info["key"],
                "rect": QtCore.QRect(button.pos(), button.size()),
                "button": True,
                "control_widget": button,
                "draft_key": info["key"],
            })
        if self.editor.screen == "main":
            refs = getattr(preview, "main_hotkey_references", {}) or {}
            for key, widget in refs.items():
                rect = self._widget_rect(widget)
                if rect.isValid():
                    targets.append(
                        {
                            "id": f"hotkey:{key}",
                            "label": key,
                            "rect": rect,
                            "resizable": True,
                            "resize_widget": widget,
                            "draft_key": f"hotkey_card_{key}",
                            "handle_corner": "top-right",
                        }
                    )
            panel = getattr(preview, "main_engine_status_panel", None)
            rect = self._widget_rect(panel)
            if rect.isValid():
                targets.append(
                    {"id": "engine", "label": "OCR / translator", "rect": rect}
                )
            for key, widget, label in self._resizable_widgets():
                if key.startswith("hotkey_card_"):
                    continue
                rect = self._widget_rect(widget)
                if rect.isValid():
                    targets.append({
                        "id": f"resize:{key}",
                        "label": label,
                        "rect": rect,
                        "resizable": True,
                        "resize_widget": widget,
                        "draft_key": key,
                    })
        else:
            settings = getattr(preview, "settings_window", None)
            if settings is not None:
                panel = (
                    getattr(settings, "settings_action_panel", None)
                    if self.editor.screen == "settings0"
                    else getattr(settings, "settings_transfer_panel", None)
                    if self.editor.screen == "settings1"
                    else None
                )
                rect = self._widget_rect(panel)
                if rect.isValid():
                    targets.append(
                        {
                            "id": "settings-actions",
                            "label": "нижние кнопки",
                            "rect": rect,
                        }
                    )
        return targets

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        if self.editor.values.get("editor", {}).get("snap_enabled", True):
            step = self._grid_size()
            grid_color = QtGui.QColor(184, 140, 255, 42)
            painter.setPen(QtGui.QPen(grid_color, 1, QtCore.Qt.DotLine))
            for x in range(0, self.width(), step):
                painter.drawLine(x, 0, x, self.height())
            for y in range(0, self.height(), step):
                painter.drawLine(0, y, self.width(), y)
        if self.editor.screen == "main":
            slot_pen = QtGui.QPen(self.slot_ink, 1, QtCore.Qt.DotLine)
            painter.setPen(slot_pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            for rect in self._main_slots():
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 5, 5)

        quiet_accent = QtGui.QColor(self.accent)
        quiet_accent.setAlpha(105)
        pen = QtGui.QPen(quiet_accent, 1, QtCore.Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        for target in self.targets():
            rect = QtCore.QRect(target["rect"])
            if self._active == target["id"] and target["id"].startswith("hotkey:"):
                rect.translate(self._ghost_offset)
            selected = target["id"] in self._selected_ids
            painter.save()
            if selected:
                painter.setPen(QtGui.QPen(QtGui.QColor("#f0c4ff"), 3))
                painter.setBrush(QtGui.QColor(184, 140, 255, 56))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)
            if target.get("button") or target.get("resizable"):
                handle_y = (
                    rect.top()
                    if target.get("handle_corner") == "top-right"
                    else rect.bottom() - 11
                )
                handle = QtCore.QRect(rect.right() - 11, handle_y, 11, 11)
                painter.fillRect(handle, self.accent)
            if not target.get("button"):
                label_rect = QtCore.QRect(rect.left() + 3, rect.top() - 15, 150, 15)
                painter.drawText(label_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, target["label"])
            painter.restore()
        if not self._marquee_rect.isNull():
            painter.setPen(QtGui.QPen(QtGui.QColor("#e1b6ff"), 2, QtCore.Qt.DashLine))
            painter.setBrush(QtGui.QColor(184, 140, 255, 38))
            painter.drawRect(self._marquee_rect)

    def _target_at(self, pos):
        candidates = [
            target
            for target in self.targets()
            if target["rect"].adjusted(-3, -3, 3, 3).contains(pos)
        ]
        if not candidates:
            return None
        resize_handles = [
            target for target in candidates if self._in_resize_handle(target, pos)
        ]
        if resize_handles:
            return min(
                resize_handles,
                key=lambda target: target["rect"].width() * target["rect"].height(),
            )
        hotkey_cards = [
            target for target in candidates if target["id"].startswith("hotkey:")
        ]
        if hotkey_cards:
            return hotkey_cards[0]
        # Nested cards overlap by design.  The smallest visible element is the
        # one the pointer actually communicates (hotkey before its whole area,
        # engine summary before the grid card, and so on).
        return min(
            candidates,
            key=lambda target: target["rect"].width() * target["rect"].height(),
        )

    @staticmethod
    def _in_resize_handle(target, pos):
        if not target.get("resizable"):
            return False
        rect = target["rect"]
        near_right = rect.right() - pos.x() <= 14
        if target.get("handle_corner") == "top-right":
            return near_right and pos.y() - rect.top() <= 14
        return near_right and rect.bottom() - pos.y() <= 14

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        if self.editor.area_selection_mode:
            self._active = "marquee"
            self._press_pos = event.pos()
            self._marquee_rect = QtCore.QRect(event.pos(), event.pos())
            self.setCursor(QtCore.Qt.CrossCursor)
            self.update()
            event.accept()
            return
        target = self._target_at(event.pos())
        if target is None:
            return
        self.editor.select_target(target["id"])
        self.editor.begin_change()
        resize_corner = self._in_resize_handle(target, event.pos())
        if resize_corner:
            self._resize_target = target
            self._active = f"target-resize:{target['draft_key']}"
            self._press_pos = event.pos()
            self._button_resize_origin = target["resize_widget"].size()
            self.setCursor(QtCore.Qt.SizeFDiagCursor)
            event.accept()
            return
        self._active = target["id"]
        self._press_pos = event.pos()
        self._ghost_offset = QtCore.QPoint()
        if self._active == "engine":
            self._origin_value = int(
                self.editor.values["main"]["engine_status_width"]
            )
            self.setCursor(QtCore.Qt.SizeHorCursor)
        elif self._active == "settings-actions":
            self._origin_value = int(
                self.editor.values["settings"]["actions_footer_gap"]
            )
            self.setCursor(QtCore.Qt.SizeVerCursor)
        else:
            self.setCursor(QtCore.Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._active == "marquee":
            self._marquee_rect = QtCore.QRect(
                self._press_pos, event.pos()
            ).normalized()
            self.update()
            event.accept()
            return
        if self._active is None:
            target = self._target_at(event.pos())
            if target is None:
                self.unsetCursor()
            elif self._in_resize_handle(target, event.pos()):
                self.setCursor(QtCore.Qt.SizeFDiagCursor)
            elif target["id"] == "engine":
                self.setCursor(QtCore.Qt.SizeHorCursor)
            elif target["id"] == "settings-actions":
                self.setCursor(QtCore.Qt.SizeVerCursor)
            else:
                self.setCursor(QtCore.Qt.OpenHandCursor)
            return

        delta = event.pos() - self._press_pos
        if self._active.startswith("target-resize:") and self._resize_target:
            widget = self._resize_target["resize_widget"]
            width, height = self._snap_size(
                self._button_resize_origin.width() + delta.x(),
                self._button_resize_origin.height() + delta.y(),
                minimum=(36, 24),
            )
            widget.setFixedSize(width, height)
            parent = widget.parentWidget()
            if parent is not None and parent.layout() is not None:
                parent.layout().invalidate()
                parent.layout().activate()
            self.editor.update_selected_properties()
        elif self._active == "engine":
            width = max(480, min(672, self._snap(self._origin_value - delta.x())))
            self.editor.values["main"]["engine_status_width"] = width
            panel = getattr(self.editor.preview, "main_engine_status_panel", None)
            if panel is not None:
                panel.setMaximumWidth(width)
                panel.parentWidget().layout().activate()
            self.editor.show_values()
        elif self._active == "settings-actions":
            gap = max(4, min(64, self._snap(self._origin_value - delta.y())))
            self.editor.values["settings"]["actions_footer_gap"] = gap
            settings = getattr(self.editor.preview, "settings_window", None)
            if settings is not None:
                settings._position_settings_updates_page()
            self.editor.show_values()
        else:
            self._ghost_offset = delta
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        active = self._active
        if event.button() != QtCore.Qt.LeftButton or active is None:
            return
        if active == "marquee":
            selection = [
                target["id"]
                for target in self.targets()
                if target.get("button")
                and self._marquee_rect.intersects(target["rect"])
            ]
            self._active = None
            self._marquee_rect = QtCore.QRect()
            self.unsetCursor()
            self.editor.select_targets(selection)
            self.editor.finish_area_selection()
            self.update()
            event.accept()
            return
        if active.startswith("target-resize:") and self._resize_target:
            target = self._resize_target
            widget = target["resize_widget"]
            rect = self._widget_rect(widget)
            positions = self.editor.values.setdefault("widgets", {}).setdefault(
                self.editor.screen, {}
            )
            previous = positions.get(target["draft_key"], {})
            positions[target["draft_key"]] = {
                "x": int(previous.get("x", rect.x())),
                "y": int(previous.get("y", rect.y())),
                "w": widget.width(),
                "h": widget.height(),
            }
            self.editor.persist(f"Размер «{target['label']}» сохранён")
            self.editor.update_selected_properties()
        elif active.startswith("hotkey:"):
            key = active.split(":", 1)[1]
            slots = self._main_slots()
            if slots:
                destination = min(
                    range(len(slots)),
                    key=lambda index: (
                        slots[index].center().x() - event.pos().x()
                    ) ** 2
                    + (
                        slots[index].center().y() - event.pos().y()
                    ) ** 2,
                )
                order = list(self.editor.values["main"]["hotkey_order"])
                try:
                    source = order.index(key)
                except ValueError:
                    source = -1
                if source >= 0 and source != destination:
                    order[source], order[destination] = order[destination], order[source]
                    self.editor.values["main"]["hotkey_order"] = order
                    self.editor.persist("Порядок горячих клавиш сохранён")
                    self.editor.rebuild_preview()
        else:
            self.editor.persist("Положение сохранено в черновик")
        self._active = None
        self._resize_target = None
        self._ghost_offset = QtCore.QPoint()
        self.unsetCursor()
        self.update()
        event.accept()


class LayoutEditorPanel(QtWidgets.QWidget):
    """Friendly external control panel for the live fixed-window preview."""

    def __init__(self, preview, draft_path=DEFAULT_DRAFT_PATH):
        super().__init__(None, QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        self.preview = preview
        self.draft_path = Path(draft_path)
        self.values = load_layout_draft(self.draft_path)
        self.preview._layout_editor_values = self.values
        self.screen = "main"
        self._updating_properties = False
        self._undo_stack = []
        self.area_selection_mode = False
        self._refresh_generation = 0
        self._closing = False
        self.setWindowTitle("Click'n'Translate — UI constructor")
        self.setFixedWidth(460)
        self._build_ui()
        # Ctrl+Z must belong to the constructor even while keyboard focus is
        # inside a detached preview control or the editable text field.  A
        # QShortcut alone loses to some widgets' built-in undo handling on
        # Windows, so observe application key events as a reliable fallback.
        application = QtWidgets.QApplication.instance()
        if application is not None:
            application.installEventFilter(self)
        self.overlay = LayoutEditorOverlay(self)
        self.rebuild_preview()
        self._place_next_to_preview()

    def _build_ui(self):
        self.setStyleSheet(
            "QWidget { background:#17141c; color:#f7f3fb; font:14px 'Segoe UI'; }"
            "QComboBox, QSpinBox, QLineEdit { min-height:30px; border:1px solid #68547d;"
            " border-radius:7px; padding:2px 8px; background:#241e2d; }"
            "QPushButton { min-height:30px; }"
            "QLabel#editorTitle { font-size:18px; font-weight:700; color:#caa7f3; }"
            "QLabel#editorStatus { color:#ab98bd; font-size:12px; }"
            "QGroupBox { border:1px solid #4e405e; border-radius:9px; margin-top:10px;"
            " padding:10px 8px 8px 8px; font-weight:600; color:#caa7f3; }"
            "QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; }"
            + standard_buttons(True, compact=True)
        )
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Конструктор интерфейса")
        title.setObjectName("editorTitle")
        self.undo_button = QtWidgets.QPushButton("↶ Назад")
        self.undo_button.setEnabled(False)
        self.undo_button.setToolTip("Отменить последнее изменение (Ctrl+Z)")
        self.undo_button.clicked.connect(self.undo_layout)
        title_row.addWidget(title, 1)
        title_row.addWidget(self.undo_button)
        root.addLayout(title_row)
        self.undo_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence.Undo, self)
        # The user edits the preview, not the toolbox, so the toolbox almost
        # never owns keyboard focus. WindowShortcut made Ctrl+Z appear broken
        # whenever a preview control was selected. This constructor exists
        # only in developer mode, making an application-wide shortcut safe.
        self.undo_shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        self.undo_shortcut.activated.connect(self.undo_layout)
        help_text = QtWidgets.QLabel(
            "Выберите элемент в окне или в списке. Перетаскивайте его мышью, "
            "тяните за фиолетовый угол для размера либо используйте точные поля ниже."
        )
        help_text.setWordWrap(True)
        root.addWidget(help_text)

        screen_row = QtWidgets.QGridLayout()
        self.screen_buttons = {}
        for index, (key, text) in enumerate((
            ("main", "Главная"),
            ("settings0", "Настр. 1"),
            ("settings1", "Настр. 2"),
            ("settings2", "Настр. 3"),
        )):
            button = QtWidgets.QPushButton(text)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, value=key: self.show_screen(value))
            screen_row.addWidget(button, 0, index)
            self.screen_buttons[key] = button
        root.addLayout(screen_row)

        selection_row = QtWidgets.QHBoxLayout()
        self.area_select_button = QtWidgets.QPushButton("▧ Выделить область")
        self.area_select_button.setCheckable(True)
        self.area_select_button.setToolTip(
            "Обведите рамкой несколько элементов, затем перетащите любой из них"
        )
        self.area_select_button.toggled.connect(self.toggle_area_selection)
        selection_row.addWidget(self.area_select_button)
        selection_help = QtWidgets.QLabel("После выделения тяните любой элемент группы")
        selection_help.setObjectName("editorStatus")
        selection_row.addWidget(selection_help, 1)
        root.addLayout(selection_row)

        options = QtWidgets.QHBoxLayout()
        self.language_combo = QtWidgets.QComboBox()
        for code, name in (
            ("en", "English"),
            ("ru", "Русский"),
            ("es", "Español"),
            ("de", "Deutsch"),
            ("fr", "Français"),
            ("zh", "中文"),
        ):
            self.language_combo.addItem(name, code)
        index = self.language_combo.findData(self.preview.current_interface_language)
        self.language_combo.setCurrentIndex(max(0, index))
        self.language_combo.currentIndexChanged.connect(self.change_language)
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItem("Тёмная", "Темная")
        self.theme_combo.addItem("Светлая", "Светлая")
        theme_index = self.theme_combo.findData(self.preview.current_theme)
        self.theme_combo.setCurrentIndex(max(0, theme_index))
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        options.addWidget(self.language_combo, 1)
        options.addWidget(self.theme_combo, 1)
        root.addLayout(options)

        grid_row = QtWidgets.QHBoxLayout()
        self.snap_checkbox = QtWidgets.QCheckBox("Привязка к сетке")
        self.snap_checkbox.setChecked(
            bool(self.values.get("editor", {}).get("snap_enabled", True))
        )
        self.snap_checkbox.toggled.connect(self.change_snap)
        self.grid_spin = QtWidgets.QSpinBox()
        self.grid_spin.setRange(2, 32)
        self.grid_spin.setSuffix(" px")
        self.grid_spin.setValue(
            int(self.values.get("editor", {}).get("grid_size", 8))
        )
        self.grid_spin.valueChanged.connect(self.change_grid_size)
        grid_row.addWidget(self.snap_checkbox, 1)
        grid_row.addWidget(QtWidgets.QLabel("Шаг:"))
        grid_row.addWidget(self.grid_spin)
        root.addLayout(grid_row)

        self.properties_box = QtWidgets.QGroupBox("Выбранный элемент")
        properties = QtWidgets.QGridLayout(self.properties_box)
        properties.setHorizontalSpacing(7)
        properties.setVerticalSpacing(6)
        self.element_combo = QtWidgets.QComboBox()
        self.element_combo.setEditable(True)
        self.element_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.element_combo.completer().setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.element_combo.currentIndexChanged.connect(self.select_combo_target)
        properties.addWidget(self.element_combo, 0, 0, 1, 4)

        self.text_edit = QtWidgets.QLineEdit()
        self.text_edit.setPlaceholderText("У этого элемента нет редактируемого текста")
        self.text_edit.returnPressed.connect(self.apply_selected_text)
        self.apply_text_button = QtWidgets.QPushButton("Применить текст")
        self.apply_text_button.clicked.connect(self.apply_selected_text)
        properties.addWidget(QtWidgets.QLabel("Текст:"), 1, 0)
        properties.addWidget(self.text_edit, 1, 1, 1, 2)
        properties.addWidget(self.apply_text_button, 1, 3)

        self.geometry_spins = {}
        for column, (key, caption, maximum) in enumerate((
            ("x", "X", 699),
            ("y", "Y", 399),
            ("w", "Ширина", 700),
            ("h", "Высота", 400),
        )):
            label = QtWidgets.QLabel(caption)
            label.setAlignment(QtCore.Qt.AlignCenter)
            spin = QtWidgets.QSpinBox()
            spin.setRange(0 if key in {"x", "y"} else 1, maximum)
            spin.setAlignment(QtCore.Qt.AlignCenter)
            spin.editingFinished.connect(self.apply_selected_geometry)
            properties.addWidget(label, 2, column)
            properties.addWidget(spin, 3, column)
            self.geometry_spins[key] = spin

        nudge_row = QtWidgets.QHBoxLayout()
        self.nudge_buttons = []
        for text, dx, dy, tip in (
            ("←", -1, 0, "Сдвинуть влево"),
            ("↑", 0, -1, "Сдвинуть вверх"),
            ("↓", 0, 1, "Сдвинуть вниз"),
            ("→", 1, 0, "Сдвинуть вправо"),
        ):
            button = QtWidgets.QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(
                lambda _checked=False, x=dx, y=dy: self.nudge_selected(x, y)
            )
            nudge_row.addWidget(button)
            self.nudge_buttons.append(button)
        self.align_grid_button = QtWidgets.QPushButton("По сетке")
        self.align_grid_button.setToolTip(
            "Выровнять координаты и размер выбранного элемента по сетке"
        )
        self.align_grid_button.clicked.connect(self.align_selected_to_grid)
        nudge_row.addWidget(self.align_grid_button, 2)
        self.reset_element_button = QtWidgets.QPushButton("Вернуть элемент")
        self.reset_element_button.clicked.connect(self.reset_selected_element)
        nudge_row.addWidget(self.reset_element_button, 2)
        properties.addLayout(nudge_row, 4, 0, 1, 4)
        self.element_hint = QtWidgets.QLabel(
            "Стрелки двигают на шаг сетки. Карточки меняют размер, а карточки "
            "горячих клавиш ещё и переставляются перетаскиванием."
        )
        self.element_hint.setWordWrap(True)
        self.element_hint.setObjectName("editorStatus")
        properties.addWidget(self.element_hint, 5, 0, 1, 4)
        root.addWidget(self.properties_box)

        self.values_label = QtWidgets.QLabel()
        self.values_label.setWordWrap(True)
        root.addWidget(self.values_label)

        actions = QtWidgets.QHBoxLayout()
        save_button = QtWidgets.QPushButton("Сохранить")
        save_button.clicked.connect(lambda: self.persist("Черновик сохранён"))
        reset_button = QtWidgets.QPushButton("Сбросить")
        reset_button.clicked.connect(self.reset_layout)
        close_button = QtWidgets.QPushButton("Закрыть")
        close_button.clicked.connect(self.close)
        actions.addWidget(save_button)
        actions.addWidget(reset_button)
        actions.addWidget(close_button)
        root.addLayout(actions)
        self.status_label = QtWidgets.QLabel()
        self.status_label.setObjectName("editorStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.show_values()

    def eventFilter(self, watched, event):
        if (
            not self._closing
            and event.type() == QtCore.QEvent.KeyPress
            and event.key() == QtCore.Qt.Key_Z
        ):
            modifiers = event.modifiers()
            if (
                modifiers & QtCore.Qt.ControlModifier
                and not modifiers
                & (QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier)
            ):
                self.undo_layout()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def editable_targets(self):
        overlay = getattr(self, "overlay", None)
        if overlay is None:
            return []
        return [
            target
            for target in overlay.targets()
            if target.get("button") or target.get("resizable")
        ]

    def begin_change(self):
        snapshot = copy.deepcopy(self.values)
        if not self._undo_stack or self._undo_stack[-1] != snapshot:
            self._undo_stack.append(snapshot)
            del self._undo_stack[:-50]
        self.undo_button.setEnabled(bool(self._undo_stack))

    def undo_layout(self):
        if not self._undo_stack:
            return
        selected_ids = set(getattr(self.overlay, "_selected_ids", set()))
        self.values = self._undo_stack.pop()
        self.preview._layout_editor_values = self.values
        self.undo_button.setEnabled(bool(self._undo_stack))
        self.persist("Последнее изменение отменено")
        self.rebuild_preview()
        self.overlay._selected_ids = selected_ids
        self.overlay._selected_id = next(iter(selected_ids), None)
        QtCore.QTimer.singleShot(0, self.refresh_element_list)

    def toggle_area_selection(self, enabled):
        self.area_selection_mode = bool(enabled)
        if enabled:
            self.status_label.setText(
                "Проведите рамку вокруг нужных кнопок и надписей"
            )
            self.overlay.raise_()
            self.overlay.setCursor(QtCore.Qt.CrossCursor)
        else:
            self.overlay.raise_detached_buttons()
            self.overlay.unsetCursor()

    def finish_area_selection(self):
        blocker = QtCore.QSignalBlocker(self.area_select_button)
        self.area_select_button.setChecked(False)
        del blocker
        self.area_selection_mode = False
        self.overlay.raise_detached_buttons()
        self.overlay.unsetCursor()

    def target_by_id(self, target_id):
        return next(
            (target for target in self.editable_targets() if target["id"] == target_id),
            None,
        )

    def refresh_element_list(self):
        current = getattr(self.overlay, "_selected_id", None)
        targets = self.editable_targets()
        valid_ids = {target["id"] for target in targets}
        self.overlay._selected_ids.intersection_update(valid_ids)
        if current not in valid_ids:
            current = next(iter(self.overlay._selected_ids), None)
        blocker = QtCore.QSignalBlocker(self.element_combo)
        self.element_combo.clear()
        for target in targets:
            widget = target.get("control_widget")
            if widget is not None and self.overlay._is_decorative_element(widget):
                kind = "линия / блок"
            elif isinstance(widget, QtWidgets.QLabel):
                kind = "надпись"
            elif isinstance(widget, QtWidgets.QAbstractButton):
                kind = "кнопка"
            else:
                kind = "элемент" if target.get("button") else "карточка"
            self.element_combo.addItem(f"{target['label']}  ·  {kind}", target["id"])
        del blocker
        index = self.element_combo.findData(current)
        if index < 0 and targets:
            index = 0
            current = targets[0]["id"]
        if index >= 0:
            blocker = QtCore.QSignalBlocker(self.element_combo)
            self.element_combo.setCurrentIndex(index)
            del blocker
            if len(self.overlay._selected_ids) > 1:
                self.overlay._selected_id = current
                self.update_selected_properties()
                self.overlay.update()
            else:
                self.select_target(current)
        else:
            self.update_selected_properties()

    def select_combo_target(self, index):
        if index >= 0:
            self.select_target(self.element_combo.itemData(index))

    def select_target(self, target_id, preserve_group=False):
        if not target_id:
            return
        self.overlay._selected_id = str(target_id)
        if not preserve_group:
            self.overlay._selected_ids = {str(target_id)}
        else:
            self.overlay._selected_ids.add(str(target_id))
        index = self.element_combo.findData(target_id)
        if index >= 0 and index != self.element_combo.currentIndex():
            blocker = QtCore.QSignalBlocker(self.element_combo)
            self.element_combo.setCurrentIndex(index)
            del blocker
        self.update_selected_properties()
        self.overlay.update()

    def select_targets(self, target_ids):
        valid = {target["id"] for target in self.editable_targets()}
        ordered = [target_id for target_id in target_ids if target_id in valid]
        self.overlay._selected_ids = set(ordered)
        self.overlay._selected_id = ordered[0] if ordered else None
        if ordered:
            index = self.element_combo.findData(ordered[0])
            if index >= 0:
                blocker = QtCore.QSignalBlocker(self.element_combo)
                self.element_combo.setCurrentIndex(index)
                del blocker
        self.update_selected_properties()
        self.overlay.update()
        self.status_label.setText(
            f"Выбрано элементов: {len(ordered)}"
            if ordered
            else "В этой области нет перемещаемых элементов"
        )

    def update_selected_properties(self):
        if not hasattr(self, "geometry_spins"):
            return
        target = self.target_by_id(getattr(self.overlay, "_selected_id", None))
        self._updating_properties = True
        try:
            selection_count = len(getattr(self.overlay, "_selected_ids", set()))
            multiple = selection_count > 1
            self.properties_box.setTitle(
                f"Выбрано элементов: {selection_count}"
                if multiple
                else "Выбранный элемент"
            )
            enabled = target is not None
            movable = bool(target and target.get("button") and not multiple)
            resizable = bool(
                target
                and (target.get("button") or target.get("resizable"))
                and not multiple
            )
            rect = target["rect"] if target else QtCore.QRect()
            for key, spin in self.geometry_spins.items():
                blocker = QtCore.QSignalBlocker(spin)
                spin.setValue({"x": rect.x(), "y": rect.y(), "w": rect.width(), "h": rect.height()}[key])
                spin.setEnabled(movable if key in {"x", "y"} else resizable)
                del blocker
            for button in self.nudge_buttons:
                button.setEnabled(bool(enabled and target.get("button")))
            self.align_grid_button.setEnabled(enabled)
            self.reset_element_button.setEnabled(enabled)
            widget = target.get("control_widget") if target else None
            text_value = (
                self.overlay._editable_text(widget)
                if widget is not None and not multiple
                else None
            )
            blocker = QtCore.QSignalBlocker(self.text_edit)
            self.text_edit.setText(text_value or "")
            self.text_edit.setEnabled(text_value is not None)
            self.apply_text_button.setEnabled(text_value is not None)
            del blocker
        finally:
            self._updating_properties = False

    def apply_selected_text(self):
        target = self.target_by_id(getattr(self.overlay, "_selected_id", None))
        if target is None or not target.get("button"):
            return
        widget = target.get("control_widget")
        if widget is None or self.overlay._editable_text(widget) is None:
            return
        self.begin_change()
        text_value = self.text_edit.text()
        widget.setText(text_value)
        positions = self.values.setdefault("widgets", {}).setdefault(self.screen, {})
        previous = positions.get(target["draft_key"], {})
        positions[target["draft_key"]] = {
            "x": widget.x(),
            "y": widget.y(),
            **({key: previous[key] for key in ("w", "h") if key in previous}),
            "text": text_value,
        }
        index = self.element_combo.findData(target["id"])
        if index >= 0:
            kind = "надпись" if isinstance(widget, QtWidgets.QLabel) else "кнопка"
            self.element_combo.setItemText(index, f"{text_value or target['draft_key']}  ·  {kind}")
        self.persist(f"Текст «{target['label']}» изменён")
        self.overlay.update()

    def apply_selected_geometry(self):
        if self._updating_properties:
            return
        target = self.target_by_id(getattr(self.overlay, "_selected_id", None))
        if target is None:
            return
        widget = target.get("control_widget") or target.get("resize_widget")
        if widget is None or sip.isdeleted(widget):
            return
        self.begin_change()
        width = min(self.overlay.width(), self.geometry_spins["w"].value())
        height = min(self.overlay.height(), self.geometry_spins["h"].value())
        widget.setFixedSize(width, height)
        if target.get("button"):
            x = max(0, min(self.overlay.width() - width, self.geometry_spins["x"].value()))
            y = max(0, min(self.overlay.height() - height, self.geometry_spins["y"].value()))
            widget.move(x, y)
        rect = self.overlay._widget_rect(widget)
        positions = self.values.setdefault("widgets", {}).setdefault(self.screen, {})
        previous = positions.get(target["draft_key"], {})
        positions[target["draft_key"]] = {
            "x": rect.x(), "y": rect.y(), "w": width, "h": height,
            **({"text": previous["text"]} if "text" in previous else {}),
        }
        parent = widget.parentWidget()
        if not target.get("button") and parent is not None and parent.layout() is not None:
            parent.layout().invalidate()
            parent.layout().activate()
        self.persist(f"Размер и положение «{target['label']}» сохранены")
        self.overlay.update()
        self.update_selected_properties()

    def nudge_selected(self, dx, dy):
        selected_ids = set(getattr(self.overlay, "_selected_ids", set()))
        targets = [
            target
            for target in self.editable_targets()
            if target["id"] in selected_ids and target.get("button")
        ]
        if not targets:
            return
        self.begin_change()
        step = self.overlay._grid_size() if self.values["editor"].get("snap_enabled") else 1
        desired_dx = dx * step
        desired_dy = dy * step
        widgets = [target["control_widget"] for target in targets]
        desired_dx = max(
            max(-widget.x() for widget in widgets),
            min(
                min(self.overlay.width() - widget.width() - widget.x() for widget in widgets),
                desired_dx,
            ),
        )
        desired_dy = max(
            max(-widget.y() for widget in widgets),
            min(
                min(self.overlay.height() - widget.height() - widget.y() for widget in widgets),
                desired_dy,
            ),
        )
        positions = self.values.setdefault("widgets", {}).setdefault(self.screen, {})
        for target in targets:
            widget = target["control_widget"]
            widget.move(widget.x() + desired_dx, widget.y() + desired_dy)
            previous = positions.get(target["draft_key"], {})
            positions[target["draft_key"]] = {
                "x": widget.x(),
                "y": widget.y(),
                **({key: previous[key] for key in ("w", "h", "text") if key in previous}),
            }
        self.persist(
            f"Группа из {len(targets)} элементов сдвинута"
            if len(targets) > 1
            else f"«{targets[0]['label']}» сдвинут"
        )
        self.overlay.update()
        self.update_selected_properties()

    def align_selected_to_grid(self):
        selected_ids = set(getattr(self.overlay, "_selected_ids", set()))
        targets = [
            target
            for target in self.editable_targets()
            if target["id"] in selected_ids
        ]
        if not targets:
            return
        self.begin_change()
        positions = self.values.setdefault("widgets", {}).setdefault(self.screen, {})
        for target in targets:
            widget = target.get("control_widget") or target.get("resize_widget")
            if widget is None or sip.isdeleted(widget):
                continue
            minimum = (
                (1, 1)
                if self.overlay._is_decorative_element(widget)
                else (18, 16)
            )
            width, height = self.overlay._snap_size(
                widget.width(), widget.height(), minimum=minimum
            )
            widget.setFixedSize(width, height)
            if target.get("button"):
                x, y = self.overlay._snap_position(widget.x(), widget.y(), width, height)
                widget.move(x, y)
            rect = self.overlay._widget_rect(widget)
            previous = positions.get(target["draft_key"], {})
            positions[target["draft_key"]] = {
                "x": rect.x(), "y": rect.y(), "w": width, "h": height,
                **({"text": previous["text"]} if "text" in previous else {}),
            }
            parent = widget.parentWidget()
            if not target.get("button") and parent is not None and parent.layout() is not None:
                parent.layout().invalidate()
                parent.layout().activate()
        self.persist(f"По сетке выровнено: {len(targets)}")
        self.overlay.update()
        self.update_selected_properties()

    def reset_selected_element(self):
        selected_ids = set(getattr(self.overlay, "_selected_ids", set()))
        targets = [
            target for target in self.editable_targets() if target["id"] in selected_ids
        ]
        if not targets:
            return
        self.begin_change()
        positions = self.values.setdefault("widgets", {}).setdefault(self.screen, {})
        for target in targets:
            positions.pop(target["draft_key"], None)
        self.persist(f"Возвращено элементов: {len(targets)}")
        self.rebuild_preview()
        self.overlay._selected_ids = selected_ids
        self.overlay._selected_id = next(iter(selected_ids), None)
        QtCore.QTimer.singleShot(0, self.refresh_element_list)

    def _place_next_to_preview(self):
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        preview_frame = self.preview.frameGeometry()
        # Python's host executable can be DPI-virtualized on Windows whereas
        # the packaged application is manifest-aware.  Putting the toolbox to
        # the right looked safe in Qt logical coordinates but could leave half
        # of it beyond the physical screen.  The left side is deterministic
        # and keeps both fixed windows fully visible at 125–175% scaling.
        x = max(screen.left(), preview_frame.left() - self.width() - 16)
        y = max(screen.top(), min(preview_frame.top(), screen.bottom() - self.height()))
        self.move(x, y)

    def show_values(self):
        main = self.values["main"]
        settings = self.values["settings"]
        positioned = len(
            self.values.get("widgets", {}).get(self.screen, {})
        )
        snap = "вкл" if self.values.get("editor", {}).get("snap_enabled", True) else "выкл"
        self.values_label.setText(
            f"OCR/переводчик: {main['engine_status_width']} px   ·   "
            f"сетка: {snap}/{self.values.get('editor', {}).get('grid_size', 8)} px\n"
            f"Вкладки → содержимое: {settings['actions_footer_gap']} px   ·   "
            f"перемещено: {positioned}"
        )

    def persist(self, message="Черновик сохранён"):
        try:
            self.values = save_layout_draft(self.values, self.draft_path)
            self.preview._layout_editor_values = self.values
            self.status_label.setText(f"{message}: {self.draft_path.name}")
        except OSError as exc:
            self.status_label.setText(f"Не удалось сохранить: {exc}")
        self.show_values()

    def reset_layout(self):
        self.begin_change()
        self.values = normalized_layout()
        self.preview._layout_editor_values = self.values
        blocker = QtCore.QSignalBlocker(self.snap_checkbox)
        self.snap_checkbox.setChecked(self.values["editor"]["snap_enabled"])
        del blocker
        blocker = QtCore.QSignalBlocker(self.grid_spin)
        self.grid_spin.setValue(self.values["editor"]["grid_size"])
        del blocker
        self.persist("Возвращены исходные значения")
        self.rebuild_preview()

    def show_screen(self, screen):
        self.screen = screen
        self.rebuild_preview()

    def rebuild_preview(self):
        self._refresh_generation += 1
        generation = self._refresh_generation
        overlay = getattr(self, "overlay", None)
        if overlay is not None:
            overlay.restore_buttons()
            overlay.hide()
        for button in self.screen_buttons.values():
            button.setEnabled(False)
        self.preview._layout_editor_values = self.values
        if self.screen == "main":
            self.preview.show_main_screen()
        else:
            self.preview.show_settings()
            settings = self.preview.settings_window
            settings._set_settings_page(int(self.screen[-1]))
        for key, button in self.screen_buttons.items():
            button.setChecked(key == self.screen)
        self.preview.showNormal()
        self.preview.raise_()
        self.preview.activateWindow()
        # Several page/language/theme buttons can otherwise queue multiple
        # zero-delay rebuilds. The first callback would detach the new page,
        # the second would immediately restore and detach it again while Qt is
        # still deleting placeholders from the first pass. On Windows that is
        # a native access violation, not a catchable Python exception. Only
        # the newest generation is allowed to touch the widget tree.
        QtCore.QTimer.singleShot(
            0,
            lambda current=generation: self._refresh_overlay(current),
        )
        self.show_values()

    def _refresh_overlay(self, generation=None):
        if self._closing:
            return
        if generation is not None and generation != self._refresh_generation:
            return
        try:
            self.overlay.setParent(self.preview.central_widget)
            self.overlay.sync_geometry()
            self.overlay.apply_resizable_drafts()
            self.overlay.show()
            self.overlay.raise_()
            self.overlay.attach_buttons()
            self.refresh_element_list()
        except RuntimeError as error:
            # A stale wrapper must never take down the native Qt process. A
            # fresh generation can be requested safely by the next click.
            self.overlay.restore_buttons()
            self.overlay.hide()
            self.status_label.setText(f"Страница ещё перестраивается: {error}")
        finally:
            if generation is None or generation == self._refresh_generation:
                for button in self.screen_buttons.values():
                    button.setEnabled(True)

    def change_language(self, _index):
        code = self.language_combo.currentData()
        if not code:
            return
        self.preview.current_interface_language = str(code)
        self.rebuild_preview()

    def change_theme(self, _index):
        theme = self.theme_combo.currentData()
        if not theme:
            return
        self.preview.current_theme = str(theme)
        self.preview.apply_theme()
        settings = getattr(self.preview, "settings_window", None)
        if settings is not None:
            settings.apply_theme()
        self.rebuild_preview()

    def change_snap(self, enabled):
        self.begin_change()
        self.values.setdefault("editor", {})["snap_enabled"] = bool(enabled)
        self.persist("Привязка к сетке изменена")
        self.overlay.update()

    def change_grid_size(self, value):
        self.begin_change()
        self.values.setdefault("editor", {})["grid_size"] = int(value)
        self.persist("Шаг сетки изменён")
        self.overlay.update()

    def closeEvent(self, event):
        self._closing = True
        self._refresh_generation += 1
        application = QtWidgets.QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        self.overlay.restore_buttons()
        self.preview.force_quit = True
        self.preview.close()
        QtWidgets.QApplication.instance().quit()
        super().closeEvent(event)


def start_layout_editor(preview):
    """Attach the visual editor and keep a strong reference on the preview."""
    panel = LayoutEditorPanel(preview)
    preview._layout_editor_panel = panel
    panel.show()
    panel.raise_()
    panel.activateWindow()
    return panel
