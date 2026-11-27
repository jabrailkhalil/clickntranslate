"""The restrained colours of the original application settings screen."""


def classic_palette(dark):
    return {
        'background': '#111111' if dark else '#f0ecf3',
        'surface': '#111111' if dark else '#f0ecf3',
        'card': '#17181d' if dark else '#e9e4ed',
        'field': '#17181d' if dark else '#e9e4ed',
        'field_alt': '#17181d' if dark else '#e9e4ed',
        'text': '#f4f6fb' if dark else '#202124',
        'muted': '#9b92a6' if dark else '#766d80',
        'border': '#3d3948' if dark else '#d7cde7',
        'soft_border': '#3d3948' if dark else '#d7cde7',
        'header': '#1e1e1e' if dark else '#ddd7e2',
        'header_border': '#3b3542' if dark else '#c5bacf',
        'accent': '#7a5fa1',
        'accent_hover': '#8b70b2' if dark else '#8563a7',
        'accent_text': '#c5b3e9' if dark else '#765099',
        'selected': '#302737' if dark else '#e7ddee',
        'hover': '#221f2c' if dark else '#ded7e5',
        'danger': '#e39ba4' if dark else '#9d3548',
        'danger_hover': '#613440' if dark else '#f2dce1',
        'scroll': '#6f5a8c' if dark else '#9b84b8',
    }


def classic_feedback_style(dark):
    """Offline-model confirmations and errors use the ordinary form style."""
    c = classic_palette(dark)
    return f"""
        QDialog {{ background: {c['background']}; color:{c['text']}; }}
        QLabel {{ background:transparent; color:{c['text']}; font-size:14px; font-weight:400; }}
        QLabel#argosDialogTitle, QLabel#argosErrorTitle {{ font-size:16px; font-weight:600; }}
        QLabel#argosDialogEyebrow, QLabel#argosErrorEyebrow,
        QLabel#argosRouteCaption, QLabel#argosErrorDetailsCaption,
        QLabel#argosDialogDetail {{ color:{c['muted']}; font-size:12px; }}
        QLabel#argosDialogIcon {{ color:{c['accent_text']}; font-size:20px; font-weight:600; }}
        QLabel#argosErrorIcon {{ color:{c['danger']}; font-size:20px; font-weight:600; }}
        QFrame#argosRouteCard {{ background:transparent; border:0; }}
        QLabel#argosRouteLabel, QLabel#argosErrorRoute {{ color:{c['text']}; font-size:14px; font-weight:600; border:0; }}
        QTextEdit#argosErrorDetails {{ background:{c['field']}; color:{c['text']}; border:1px solid {c['border']}; border-radius:7px; padding:5px 7px; font-size:13px; selection-background-color:{c['accent']}; }}
    """
