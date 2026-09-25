"""One slim scrollbar style for every window and popup in the application."""

from PyQt5 import QtCore, QtWidgets


SCROLLBAR_WIDTH = 6


def scrollbar_stylesheet():
    # Keep this application rule independent of the theme and UI text scale.
    # Replacing QApplication's stylesheet on a theme change repolishes every
    # rich-text document; only the scrollbar theme properties need to change instead.
    return '''
        /* clickntranslate-scrollbars */
        QScrollBar:vertical {
            background: transparent; border: none; width: 6px; margin: 2px 0;
        }
        QScrollBar:horizontal {
            background: transparent; border: none; height: 6px; margin: 0 2px;
        }
        QScrollBar::handle {
            background: #b7a5ca; border: none; border-radius: 3px;
        }
        QScrollBar::handle:vertical { min-height: 24px; }
        QScrollBar::handle:horizontal { min-width: 24px; }
        QScrollBar::handle:hover, QScrollBar::handle:pressed {
            background: #7a5fa1;
        }
        QScrollBar[_cntScrollDark="true"]::handle { background: #66527e; }
        QScrollBar[_cntScrollDark="true"]::handle:hover,
        QScrollBar[_cntScrollDark="true"]::handle:pressed { background: #aa91c9; }
        QScrollBar::add-line, QScrollBar::sub-line {
            width: 0; height: 0; border: none; background: transparent;
        }
        QScrollBar::add-page, QScrollBar::sub-page {
            background: transparent;
        }
        QScrollBar::up-arrow, QScrollBar::down-arrow,
        QScrollBar::left-arrow, QScrollBar::right-arrow {
            width: 0; height: 0; background: transparent; border: none;
        }
        QAbstractScrollArea::corner { background: transparent; border: none; }
        /* end-clickntranslate-scrollbars */
    '''


class _ScrollbarTheme(QtCore.QObject):
    def __init__(self, app, is_dark):
        super().__init__(app)
        self.app = app
        self.is_dark = is_dark
        self._applying = False

    def apply(self, bar, *, polishing=False):
        if self._applying:
            return
        self._applying = True
        try:
            dark = bool(self.is_dark(bar))
            if bar.property('_cntScrollDark') != dark:
                bar.setProperty('_cntScrollDark', dark)
                if not polishing:
                    bar.style().unpolish(bar)
                    bar.style().polish(bar)
                    bar.update()
        finally:
            self._applying = False

    def refresh(self):
        for widget in self.app.allWidgets():
            if isinstance(widget, QtWidgets.QScrollBar):
                self.apply(widget)

    def eventFilter(self, watched, event):
        kind = event.type()
        if isinstance(watched, QtWidgets.QScrollBar) and kind in (
            QtCore.QEvent.Polish, QtCore.QEvent.Show, QtCore.QEvent.StyleChange,
            QtCore.QEvent.ParentChange,
        ):
            self.apply(watched, polishing=kind == QtCore.QEvent.Polish)
        elif (watched is self.app and kind == QtCore.QEvent.DynamicPropertyChange
              and event.propertyName() == b'ui_theme'):
            self.refresh()
        return False


def install_scrollbar_theme(app, is_dark):
    """Cover existing scrollbars and those created later, including popups."""
    if not hasattr(app, '_thin_scrollbar_theme'):
        app._thin_scrollbar_theme = _ScrollbarTheme(app, is_dark)
        app.installEventFilter(app._thin_scrollbar_theme)
    app._thin_scrollbar_theme.refresh()
