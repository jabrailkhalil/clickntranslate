"""Category navigation inside the shared provider popup; provider IDs stay intact."""
from PyQt5 import QtCore, QtGui, QtWidgets

CATEGORY_ROLE = QtCore.Qt.UserRole + 104


def configure_categories(combo, labels, groups):
    combo._provider_categories = [(key, labels.get(key, 'API')) for key in groups]
    categories = iter(groups)
    category = None
    for row in range(combo.count()):
        if combo.itemData(row, QtCore.Qt.UserRole + 100):
            category = next(categories, None)
        combo.setItemData(row, category, CATEGORY_ROLE)


class ProviderCategoryBar(QtWidgets.QTabBar):
    def __init__(self, combo):
        super().__init__(combo.view().window())
        self.combo = combo
        self.setObjectName('providerCategoryBar')
        self.setDrawBase(False)
        self.setExpanding(True)
        self.setUsesScrollButtons(False)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.currentChanged.connect(self.filter_rows)
        combo.view().installEventFilter(self)

    def filter_rows(self, index):
        category = self.tabData(index)
        combo = self.combo
        rows = []
        for row in range(combo.count()):
            visible = (not combo.itemData(row, combo.GROUP_HEADER_ROLE)
                       and combo.itemData(row, CATEGORY_ROLE) == category)
            combo.view().setRowHidden(row, not visible)
            if visible:
                rows.append(row)
        if rows:
            row = combo.currentIndex() if combo.currentIndex() in rows else rows[0]
            combo.view().setCurrentIndex(combo.model().index(row, combo.modelColumn()))
        combo.view().doItemsLayout()
        combo._queue_popup_layout()

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.KeyPress and event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right):
            step = -1 if event.key() == QtCore.Qt.Key_Left else 1
            if self.layoutDirection() == QtCore.Qt.RightToLeft:
                step *= -1
            self.setCurrentIndex((self.currentIndex() + step) % self.count())
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Down, QtCore.Qt.Key_Tab):
            self.combo.view().setFocus(QtCore.Qt.TabFocusReason)
            event.accept()
        elif event.key() == QtCore.Qt.Key_Escape:
            self.combo.hidePopup()
        else:
            super().keyPressEvent(event)


def prepare_categories(combo):
    categories = getattr(combo, '_provider_categories', ())
    if not categories:
        return
    bar = getattr(combo, '_provider_category_bar', None)
    if bar is None:
        bar = combo._provider_category_bar = ProviderCategoryBar(combo)
        combo.view().window().layout().insertWidget(0, bar)
    colors = combo.popup_colors()
    from combo_popup import popup_scale
    scale = popup_scale(combo)
    from combo_popup import popup_font
    bar.setFont(popup_font(combo))
    bar.setLayoutDirection(combo.layoutDirection())
    bar.setStyleSheet(f'''
        QTabBar {{ background:transparent; border:0; }}
        QTabBar::tab {{ background:transparent; color:{colors['muted']};
            border:0; border-bottom:2px solid transparent;
            padding:{round(7*scale)}px {round(12*scale)}px; margin:0; }}
        QTabBar::tab:selected {{ color:{colors['accent']}; border-bottom:2px solid {colors['accent']}; }}
        QTabBar::tab:hover:!selected {{ color:{colors['text']}; background:{colors['hover']}; }}
    ''')
    blocker = QtCore.QSignalBlocker(bar)
    while bar.count():
        bar.removeTab(0)
    for key, label in categories:
        index = bar.addTab(label)
        bar.setTabData(index, key)
        bar.setTabToolTip(index, label)
    category = combo.itemData(combo.currentIndex(), CATEGORY_ROLE)
    index = next((i for i, (key, _) in enumerate(categories) if key == category), 0)
    bar.setCurrentIndex(index)
    del blocker
    bar.filter_rows(index)
    bar.show()
