"""Button appearance shared by the main app, dialogs and capture processes.

Layouts own sizes. Compact actions keep the same typography, corners and
states, but omit vertical padding to fit existing fixed-height rows.
"""

BUTTON_RADIUS = 7
BUTTON_FONT_SIZE = 13


def _install_keyboard_focus_tracking():
    """Keep keyboard focus visible without leaving a ring after a mouse click."""
    from PyQt5.QtCore import QEvent, QObject, Qt
    from PyQt5.QtWidgets import QApplication, QComboBox, QPushButton, QToolButton

    app = QApplication.instance()
    if app is None or hasattr(app, "_button_focus_filter"):
        return

    class ButtonFocusFilter(QObject):
        def eventFilter(self, widget, event):
            kind = event.type()
            if kind not in (QEvent.FocusIn, QEvent.FocusOut, QEvent.MouseButtonPress):
                return False
            if not isinstance(widget, (QPushButton, QToolButton, QComboBox)):
                return False
            keyboard = kind == QEvent.FocusIn and event.reason() in (
                Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason,
            )
            if bool(widget.property("keyboardFocus")) != keyboard:
                widget.setProperty("keyboardFocus", keyboard)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
            return False

    app._button_focus_filter = ButtonFocusFilter(app)
    app.installEventFilter(app._button_focus_filter)


def button_palette(dark):
    return {
        "surface": "#211d28" if dark else "#f2edf6",
        "hover": "#302737" if dark else "#e7ddee",
        "pressed": "#3c3048" if dark else "#d9cbe5",
        "text": "#eee7f5" if dark else "#302639",
        "border": "#584963" if dark else "#bcaacb",
        "accent": "#7a5fa1" if dark else "#755397",
        "accent_hover": "#8b70b2" if dark else "#8563a7",
        "accent_pressed": "#654a87" if dark else "#624280",
        "focus": "#c5ace3" if dark else "#79569b",
        "danger": "#e39ba4" if dark else "#9d3548",
        "danger_hover": "#613440" if dark else "#f2dce1",
        "danger_pressed": "#774250" if dark else "#e8c5ce",
        "disabled": "#7d7487" if dark else "#958b9f",
        "disabled_surface": "#242129" if dark else "#eae4ef",
        "disabled_border": "#3c3544" if dark else "#d5cadf",
    }


def button_qss(dark, role="secondary", selector="QPushButton", *, compact=False,
               icon=False, radius=BUTTON_RADIUS):
    _install_keyboard_focus_tracking()
    colors = button_palette(dark)
    background, hover, pressed = colors["surface"], colors["hover"], colors["pressed"]
    ink, border = colors["text"], colors["border"]
    if role == "primary":
        background, hover, pressed = colors["accent"], colors["accent_hover"], colors["accent_pressed"]
        ink = "#ffffff"
        border = colors["accent"]
    elif role == "danger":
        ink = colors["danger"]
        hover, pressed = colors["danger_hover"], colors["danger_pressed"]
    elif role in ("quiet", "close"):
        background, border = "transparent", "transparent"
        if role == "close":
            hover, pressed = colors["danger_hover"], colors["danger_pressed"]
    elif role != "secondary":
        raise ValueError(f"Unknown button role: {role}")
    padding = "0" if icon else "0 12px" if compact else "6px 12px"
    size, weight = (20, 400) if icon else (BUTTON_FONT_SIZE, 600)
    selectors = [part.strip() for part in selector.split(",")]

    def state(value):
        return ", ".join(part + value for part in selectors)

    return f"""
        {selector} {{ background:{background}; color:{ink};
            border:1px solid {border}; border-radius:{radius}px;
            padding:{padding}; font-size:{size}px; font-weight:{weight}; }}
        {state(':hover')} {{ background:{hover}; }}
        {state(':pressed')} {{ background:{pressed}; }}
        {state('[keyboardFocus="true"]:focus')} {{ border-color:{colors['focus']}; }}
        {state(':checked')} {{ background:{colors['pressed']}; border-color:{colors['focus']}; }}
        {state(':disabled')} {{ background:{colors['disabled_surface']};
            color:{colors['disabled']}; border-color:{colors['disabled_border']}; }}
    """


def standard_buttons(dark, *, compact=False):
    """Known action roles, using the stable object names in our windows."""
    rules = [button_qss(dark, compact=compact)]
    roles = {
        "primary": ("argosInstallButton", "translationResultCopy", "docPrimaryButton",
                    "welcomeStart", "hotkeyLanguageDone", "guidePrimary",
                    "languagePackageAction", "saveReturnButton"),
        "danger": ("docDangerButton", "secondaryClearButton", "historyDeleteButton",
                   "languagePackageEngineRemove"),
        "quiet": ("welcomeSkip", "guideSkip"),
    }
    for role, names in roles.items():
        rules.append(button_qss(dark, role, ", ".join(f"QPushButton#{name}" for name in names), compact=compact))
    for role in ("primary", "secondary", "danger"):
        rules.append(button_qss(dark, role, f'QPushButton[buttonRole="{role}"]', compact=compact))
    for widget_type, names, role in (
        ("QPushButton", ("welcomeClose", "guideClose"), "close"),
        ("QPushButton", ("welcomeLang",), "quiet"),
        ("QToolButton", ("translationResultTitleClose", "docWindowClose", "helpTitleClose",
                         "hotkeyLanguageClose", "languageManagerTitleClose", "styledMessageClose"), "close"),
        ("QToolButton", ("translationResultSwap", "docLanguageSwap", "hotkeyLanguageSwap",
                         "gameLanguageSwap", "hotkeyLanguageBarSwap"), "secondary"),
        ("QToolButton", ("docWindowButton",), "quiet"),
    ):
        rules.append(button_qss(dark, role, ", ".join(f"{widget_type}#{name}" for name in names), icon=True))
    return "\n".join(rules)
