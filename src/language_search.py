"""Filter language popup rows in place, retaining the original item indexes."""
from PyQt5.QtCore import Qt, QEvent, QObject
from PyQt5.QtWidgets import QLineEdit, QApplication
from languages import LANGUAGES, LOCALIZED_LANGUAGE_NAMES, AUTO_LANGUAGE_NAMES

_NAMES = {l.code for l in LANGUAGES} | {l.short_label for l in LANGUAGES}
for _mapping in LOCALIZED_LANGUAGE_NAMES.values():
    _NAMES.update(_mapping.values())
_NAMES.update(AUTO_LANGUAGE_NAMES.values())
_SEARCH_TERMS = {}
for _language in LANGUAGES:
    _terms = [_language.code, _language.english_name, _language.russian_name]
    _terms += [_language.display_name(locale) for locale in LOCALIZED_LANGUAGE_NAMES]
    _joined = '\n'.join(_terms).casefold()
    for _term in _terms + [_language.short_label]:
        _SEARCH_TERMS[_term] = _joined


class _SearchKeys(QObject):
    def __init__(self, combo):
        super().__init__(combo)
        self.combo = combo

    def eventFilter(self, watched, event):
        if event.type() != QEvent.KeyPress:
            return False
        combo = self.combo
        if event.key() == Qt.Key_Escape:
            combo.hidePopup()
            return True
        rows = [r for r in range(combo.count()) if not combo.view().isRowHidden(r)]
        if not rows:
            return event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Down)
        if event.key() == Qt.Key_Down:
            combo.view().setCurrentIndex(combo.model().index(rows[0], combo.modelColumn()))
            combo.view().setFocus(Qt.TabFocusReason)
            return True
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            current = combo.view().currentIndex().row()
            combo.setCurrentIndex(current if current in rows else rows[0])
            combo.hidePopup()
            return True
        return False


def prepare_language_search(combo):
    # Engine/mode pickers retain their existing appearance and behaviour.
    if combo.count() < 12 or sum(combo.itemText(i) in _NAMES or str(combo.itemData(i)) in _NAMES
                                for i in range(combo.count())) < combo.count() * .8:
        return
    search = getattr(combo, '_language_search', None)
    if search is None:
        popup = combo.view().window()
        search = QLineEdit(popup)
        search.setObjectName('languageSearch')
        lang = getattr(combo, 'interface_language', 'en')
        owner = combo
        while owner is not None:
            config = getattr(owner, 'config', None)
            if not isinstance(config, dict):
                config = getattr(getattr(owner, 'parent', None), 'config', None)
            if isinstance(config, dict):
                lang = config.get('interface_language', lang)
                break
            owner = owner.parentWidget()
        search.setPlaceholderText({'ru': 'Найти язык…', 'es': 'Buscar idioma…', 'de': 'Sprache suchen…',
                                   'fr': 'Rechercher une langue…', 'zh': '搜索语言…'}.get(lang, 'Find a language…'))
        search.setAccessibleName(search.placeholderText())
        search.setClearButtonEnabled(True)
        popup.layout().insertWidget(0, search)
        combo._language_search = search
        combo._language_search_keys = _SearchKeys(combo)
        search.installEventFilter(combo._language_search_keys)

        def apply_filter(text):
            query = text.strip().casefold()
            for row in range(combo.count()):
                value = combo.itemData(row)
                terms = _SEARCH_TERMS.get(str(value), _SEARCH_TERMS.get(combo.itemText(row), combo.itemText(row).casefold()))
                combo.view().setRowHidden(row, bool(query and query not in terms))
            combo.view().doItemsLayout()
            combo._queue_popup_layout()
        search.textChanged.connect(apply_filter)
    combo.setMaxVisibleItems(8)
    search.setFont(combo.font())
    search.setFixedHeight(max(28, combo.fontMetrics().height() + 10))
    dark = getattr(combo, '_popup_background', '#20212a')
    from PyQt5.QtGui import QColor
    is_dark = QColor(dark).lightness() < 128
    search.setStyleSheet('QLineEdit { background:%s; color:%s; border:1px solid #786989; border-radius:4px; padding:3px 6px; }' %
                        ('#20212a' if is_dark else '#f1edf4', '#f4f6fb' if is_dark else '#202124'))
    search.clear()
    for row in range(combo.count()):
        combo.view().setRowHidden(row, False)
