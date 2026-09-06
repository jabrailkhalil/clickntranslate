"""Use real font metrics with Qt's Windows offscreen platform plugin."""

import os
import sys
from pathlib import Path

from PyQt5.QtGui import QFont, QFontDatabase


def ensure_layout_fonts(app):
    if sys.platform != "win32" or QFontDatabase().families():
        return
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    # Keep these registered for the QApplication's lifetime. Removing a font
    # while cached widgets still reference it changes subsequent size hints.
    # Include the bold CJK face too. Synthetic bold with the offscreen plugin
    # can corrupt fallback-font baselines after rendering Chinese text.
    for name in ("segoeui.ttf", "segoeuib.ttf", "arial.ttf", "arialbd.ttf", "msyh.ttc", "msyhbd.ttc"):
        QFontDatabase.addApplicationFont(str(fonts / name))
    app.setFont(QFont("Segoe UI", 10))
