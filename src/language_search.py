"""Filter language popup rows in place, retaining the original item indexes."""
from PyQt5.QtCore import Qt, QEvent, QObject
from PyQt5.QtWidgets import QLineEdit, QLabel, QApplication
from PyQt5.QtGui import QFont
from languages import LANGUAGES, LOCALIZED_LANGUAGE_NAMES, AUTO_LANGUAGE_NAMES

_NAMES = {l.code for l in LANGUAGES} | {l.short_label for l in LANGUAGES}
for _mapping in LOCALIZED_LANGUAGE_NAMES.values():
    _NAMES.update(_mapping.values())
_NAMES.update(AUTO_LANGUAGE_NAMES.values())
SEARCH_TEXT = {
    'en': ('Find a language…', 'No languages found'),
    'ru': ('Найти язык…', 'Языки не найдены'),
    'es': ('Buscar idioma…', 'No se encontraron idiomas'),
    'de': ('Sprache suchen…', 'Keine Sprachen gefunden'),
    'fr': ('Rechercher une langue…', 'Aucune langue trouvée'),
    'zh': ('搜索语言…', '未找到语言'),
    'pt': ('Encontre um idioma…', 'Nenhum idioma encontrado'),
    'it': ('Trova una lingua…', 'Nessuna lingua trovata'),
    'ar': ('ابحث عن لغة…', 'لم يتم العثور على لغات'),
    'tr': ('Dil bul…', 'Dil bulunamadı'),
    'hi': ('भाषा खोजें…', 'कोई भाषा नहीं मिली'),
    'id': ('Cari bahasa…', 'Bahasa tidak ditemukan'),
}
_SEARCH_TERMS = {}
_OPTION_CODES = {}
for _language in LANGUAGES:
    _terms = [_language.code, _language.english_name, _language.russian_name]
    _terms += [_language.display_name(locale) for locale in LOCALIZED_LANGUAGE_NAMES]
    _joined = '\n'.join(_terms).casefold()
    for _term in _terms + [_language.short_label]:
        _SEARCH_TERMS[_term] = _joined
        _OPTION_CODES[_term.strip().casefold()] = _language.code


def language_code_for_option_text(label):
    return _OPTION_CODES.get(str(label).strip().casefold())


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
    # Short menus do not need an input. A language provider can change while
    # the same control survives, so remove the previous search chrome as well.
    if combo.count() < 12 or sum(combo.itemText(i) in _NAMES or str(combo.itemData(i)) in _NAMES
                                for i in range(combo.count())) < combo.count() * .8:
        if getattr(combo, '_language_search', None) is not None:
            combo._language_search.clear()
            combo._language_search.hide()
            combo._language_empty.hide()
        return
    search = getattr(combo, '_language_search', None)
    if search is None:
        popup = combo.view().window()
        search = QLineEdit(popup)
        search.setObjectName('languageSearch')
        search.setClearButtonEnabled(True)
        popup.layout().insertWidget(0, search)
        combo._language_search = search
        combo._language_empty = QLabel(popup)
        combo._language_empty.setObjectName('languageSearchEmpty')
        combo._language_empty.setAlignment(Qt.AlignCenter)
        popup.layout().insertWidget(1, combo._language_empty)
        combo._language_empty.hide()
        combo._language_search_keys = _SearchKeys(combo)
        search.installEventFilter(combo._language_search_keys)

        def apply_filter(text):
            query = text.strip().casefold()
            matches = 0
            for row in range(combo.count()):
                value = combo.itemData(row)
                terms = _SEARCH_TERMS.get(str(value), _SEARCH_TERMS.get(combo.itemText(row), combo.itemText(row).casefold()))
                hidden = bool(query and query not in terms)
                combo.view().setRowHidden(row, hidden)
                matches += not hidden
            combo._language_empty.setVisible(not matches)
            combo.view().doItemsLayout()
            combo._queue_popup_layout()
        search.textChanged.connect(apply_filter)
    combo.setMaxVisibleItems(8)
    from combo_popup import popup_scale
    from dialog_text import dialog_language
    factor = popup_scale(combo)
    colors = combo.popup_colors()
    labels = SEARCH_TEXT.get(dialog_language(combo), SEARCH_TEXT['en'])
    search.setPlaceholderText(labels[0])
    search.setAccessibleName(labels[0])
    combo._language_empty.setText(labels[1])
    font = QFont(combo.font())
    font.setWeight(QFont.Normal)
    search.setFont(font)
    combo._language_empty.setFont(font)
    combo._language_empty.setFixedHeight(max(round(34*factor), combo._language_empty.fontMetrics().height()+round(12*factor)))
    search.setFixedHeight(max(round(32*factor), search.fontMetrics().height()+round(12*factor)))
    search.setStyleSheet(f'''QLineEdit {{ background:{colors['surface']}; color:{colors['text']};
        border:1px solid {colors['border']}; border-radius:{round(5*factor)}px;
        padding:0 {round(9*factor)}px; font-weight:400; }}
        QLineEdit:focus {{ border-color:{colors['accent']}; }}''')
    combo._language_empty.setStyleSheet(f"color:{colors['muted']}; background:transparent; border:0; padding:4px;")
    search.show()
    search.clear()
    combo._language_empty.hide()
    for row in range(combo.count()):
        combo.view().setRowHidden(row, False)
