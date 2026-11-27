"""Materialize history cards in small batches while retaining every record."""
from PyQt5 import QtCore, QtWidgets, sip


class HistoryCardPager(QtCore.QObject):
    BATCH_SIZE = 25

    def __init__(self, scroll, layout, records, create_card, is_current, batch_added):
        super().__init__(scroll)
        self.scroll, self.layout = scroll, layout
        self.records = list(records)
        self.cards = []
        self._next = len(self.records) - 1
        self._create_card = create_card
        self._is_current = is_current
        self._batch_added = batch_added
        self._stopped = False
        self._restore_to = None
        self._last_button = None
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._maybe_append)
        self.scroll.verticalScrollBar().valueChanged.connect(self.schedule)
        self.scroll.verticalScrollBar().rangeChanged.connect(self.schedule)
        self.scroll.viewport().installEventFilter(self)
        # Run before the shared keyboard navigator takes its tab-stop snapshot.
        # This is an in-process Qt filter, not a system keyboard listener.
        QtWidgets.QApplication.instance().installEventFilter(self)

    def current(self):
        return (not self._stopped and not sip.isdeleted(self.scroll)
                and not sip.isdeleted(self.layout) and self._is_current())

    def stop(self):
        self._stopped = True
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        if not sip.isdeleted(self.timer):
            self.timer.stop()

    def schedule(self, *args):
        if self.current() and (self._next >= 0 or self._restore_to is not None) and not self.timer.isActive():
            self.timer.start(0)

    def restore_position(self, position):
        self._restore_to = max(0, int(position))
        self.schedule()

    def append_batch(self):
        if not self.current() or self._next < 0:
            return
        # Keep the single expanding spacer below the materialized cards.
        if self.layout.count() and self.layout.itemAt(self.layout.count()-1).spacerItem():
            self.layout.takeAt(self.layout.count()-1)
        stop = max(-1, self._next-self.BATCH_SIZE)
        while self._next > stop:
            index = self._next
            card = self._create_card(self.records[index], index)
            self.cards.append(card)
            card.show()
            self._next -= 1
        self.layout.addStretch(1)
        self.layout.activate()
        content = self.scroll.widget()
        content.resize(content.width(), max(content.height(), self.layout.minimumSize().height()))
        self.layout.activate()
        buttons = [button for card in self.cards for button in card.findChildren(QtWidgets.QAbstractButton)]
        self._last_button = buttons[-1] if buttons else None
        if self._last_button is not None:
            self._last_button.installEventFilter(self)
        self._batch_added(self)
        self.schedule()

    def _maybe_append(self):
        if not self.current() or not self.scroll.isVisible():
            return
        bar = self.scroll.verticalScrollBar()
        if self._restore_to is not None:
            if bar.maximum() >= self._restore_to or self._next < 0:
                position, self._restore_to = self._restore_to, None
                bar.setValue(position)
            else:
                self.append_batch()
            return
        if self._next < 0:
            return
        if bar.maximum() == 0 and self.layout.minimumSize().height() > self.scroll.viewport().height():
            # LayoutRequest has not published the new scroll range yet.
            return
        if bar.maximum()-bar.value() <= max(60, self.scroll.viewport().height()//2):
            self.append_batch()

    def eventFilter(self, watched, event):
        if self._stopped or sip.isdeleted(self.scroll):
            return False
        if watched is self.scroll.viewport() and event.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show):
            self.schedule()
        elif (watched is self._last_button and event.type() == QtCore.QEvent.KeyPress
              and event.key() == QtCore.Qt.Key_Tab and not event.modifiers() & QtCore.Qt.ShiftModifier):
            # Add the next controls before Qt computes its next focus target.
            self.append_batch()
        return False
