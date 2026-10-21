"""Readable package tables with rectangular frames and themed row selection."""
from PyQt5 import QtCore, QtWidgets


class _PackageDelegate(QtWidgets.QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # The entire selected row already identifies keyboard focus. A native
        # dotted rectangle around one cell conflicts with that row selection.
        option.state &= ~QtWidgets.QStyle.State_HasFocus


class PackageTable(QtWidgets.QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_PackageDelegate(self))
        self.setWordWrap(False)
        self.setTextElideMode(QtCore.Qt.ElideRight)
        self._fit_timer = QtCore.QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self.fit_columns)
        self.verticalScrollBar().rangeChanged.connect(self._schedule_fit)
        # Qt normally gives the bar the full table height, including the
        # stationary header. Reserve that header height in its own layout so
        # the draggable track belongs only to the rows, at every UI scale.
        self._scroll_header_gap = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.verticalScrollBar().parentWidget().layout().insertSpacerItem(0, self._scroll_header_gap)
        self.horizontalHeader().geometriesChanged.connect(self._schedule_fit)

    def _schedule_fit(self, *_):
        self._fit_timer.start(0)

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_fit()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.FontChange, QtCore.QEvent.StyleChange):
            if event.type() == QtCore.QEvent.FontChange:
                self.setMaximumHeight(16777215)
            if hasattr(self, '_fit_timer'):
                self._schedule_fit()

    def fit_columns(self):
        if not self.isVisible():
            return
        header = self.horizontalHeader()
        gap = header.height() if header.isVisible() else 0
        if self._scroll_header_gap.sizeHint().height() != gap:
            self._scroll_header_gap.changeSize(
                0, gap, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
            self.verticalScrollBar().parentWidget().layout().invalidate()
        if self.columnCount() != 4:
            return
        metrics = self.fontMetrics()
        padding = max(12, metrics.height())
        header.setMinimumSectionSize(max(24, metrics.height()))
        checkbox = 0 if self.isColumnHidden(0) else max(34, metrics.height()+14)
        if checkbox:
            self.setColumnWidth(0, checkbox)
        available = max(60, self.viewport().width()-checkbox)
        for column, fraction in ((2, .31), (3, .40)):
            title = self.horizontalHeaderItem(column)
            needed = header.fontMetrics().horizontalAdvance(title.text())+padding if title else 0
            for row in range(self.rowCount()):
                item = self.item(row, column)
                if item is not None:
                    needed = max(needed, metrics.horizontalAdvance(item.text())+padding)
                    item.setToolTip(item.text())
            # Reserve a readable name column, and elide genuinely long values
            # instead of painting them underneath the right frame/scrollbar.
            self.setColumnWidth(column, max(header.minimumSectionSize(), min(needed, int(available*fraction))))
        self.resizeRowsToContents()
        if self.rowCount():
            height = max(self.rowHeight(row) for row in range(self.rowCount()))
            for row in range(self.rowCount()):
                self.setRowHeight(row, height)

