"""Filter language popup rows in place, retaining the original item indexes."""
import unicodedata

from PyQt5.QtCore import Qt, QEvent, QObject, QSize
from PyQt5.QtWidgets import QLineEdit, QLabel
from PyQt5.QtGui import QFont, QFontInfo
from languages import LANGUAGES, LOCALIZED_LANGUAGE_NAMES, AUTO_LANGUAGE_NAMES

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


def language_search_key(value):
    return ''.join(char for char in unicodedata.normalize('NFKD', str(value).casefold())
                   if not unicodedata.combining(char)).strip()


_SEARCH_TERMS = {}
_OPTION_CODES = {}


def _index_language(code, aliases):
    _SEARCH_TERMS[code] = language_search_key('\n'.join(aliases))
    for alias in aliases:
        _OPTION_CODES[alias.strip().casefold()] = code


_index_language('auto', ['auto', *AUTO_LANGUAGE_NAMES.values()])
for _language in LANGUAGES:
    _terms = [_language.code, _language.short_label, _language.english_name, _language.russian_name]
    _terms += [_language.display_name(locale) for locale in LOCALIZED_LANGUAGE_NAMES]
    _index_language(_language.code, _terms)


def language_code_for_option_text(label):
    return _OPTION_CODES.get(str(label).strip().casefold())


def _row_code(combo, row):
    return (language_code_for_option_text(combo.itemData(row))
            or language_code_for_option_text(combo.itemText(row)))


def stable_search_popup_size(combo, desired):
    """Keep row/flag columns stable, while height follows the search results.

    DropDownCombo keeps the search box at its opening position as rows disappear.
    """
    search = getattr(combo, '_language_search', None)
    if search is None or search.isHidden():
        return desired
    previous = getattr(combo, '_language_popup_size', None)
    # An unfiltered menu tracks the field as its layout settles after Show.
    # A query can hide the widest label, so retain the width while filtering.
    width = desired.width()
    if search.text() and previous is not None:
        width = max(width, previous.width())
    size = QSize(width, desired.height())
    combo._language_popup_size = QSize(size)
    return size


class _SearchKeys(QObject):
    def __init__(self, combo):
        super().__init__(combo)
        self.combo = combo

    def filter_rows(self, text, *, reset_scroll=True):
        combo = self.combo
        query = language_search_key(text)
        # Exact ISO input is unambiguous. In particular, "ar" is also a
        # substring of localized names for Chinese and several other languages.
        exact = query in _SEARCH_TERMS
        matches = 0
        view = combo.view()
        for row in range(combo.count()):
            hidden = False
            if query:
                code = _row_code(combo, row)
                terms = _SEARCH_TERMS[code] if code is not None else language_search_key(combo.itemText(row))
                hidden = code != query if exact else query not in terms
            if view.isRowHidden(row) != hidden:
                view.setRowHidden(row, hidden)
            matches += not hidden
        combo._language_empty.setVisible(not matches)
        view.doItemsLayout()
        if reset_scroll:
            view.verticalScrollBar().setValue(0)
        combo._queue_popup_layout()

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


def prepare_language_search(combo, *, model_changed=False):
    # Short menus do not need an input. A language provider can change while
    # the same control survives, so remove the previous search chrome as well.
    search = getattr(combo, '_language_search', None)
    searching = model_changed and search is not None and not search.isHidden() and bool(search.text().strip())
    count = combo.count()
    if ((count < 12 and not searching)
            or sum(_row_code(combo, i) is not None for i in range(count)) < count * .8):
        if search is not None and not search.isHidden():
            search.clear()
            search.hide()
            combo._language_empty.hide()
            combo.itemDelegate().invalidate_metrics()
        return
    if model_changed and search is not None and not search.isHidden():
        combo._language_search_keys.filter_rows(search.text(), reset_scroll=False)
        return
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
        search.textChanged.connect(combo._language_search_keys.filter_rows)
    combo.setMaxVisibleItems(8)
    from combo_popup import popup_scale
    from dialog_text import dialog_language
    factor = popup_scale(combo)
    colors = combo.popup_colors()
    labels = SEARCH_TEXT.get(dialog_language(combo), SEARCH_TEXT['en'])
    search.setPlaceholderText(labels[0])
    search.setAccessibleName(labels[0])
    combo._language_empty.setText(labels[1])
    from combo_popup import popup_font
    font = popup_font(combo)
    font.setWeight(QFont.Normal)
    font_pixels = font.pixelSize() if font.pixelSize() > 0 else QFontInfo(font).pixelSize()
    search.setFont(font)
    combo._language_empty.setFont(font)
    search.setStyleSheet(f'''QLineEdit {{ background:{colors['surface']}; color:{colors['text']};
        border:1px solid {colors['border']}; border-radius:{round(5*factor)}px;
        padding:0 {round(9*factor)}px; font-size:{font_pixels}px; font-weight:400; }}
        QLineEdit:focus {{ border-color:{colors['accent']}; }}''')
    combo._language_empty.setStyleSheet(f"color:{colors['muted']}; background:transparent; border:0; padding:4px; font-size:{font_pixels}px;")
    # Replace a former host's explicit CSS font before measuring the new one.
    # QWidget.setFont alone cannot override an existing stylesheet font size.
    search.ensurePolished()
    combo._language_empty.ensurePolished()
    combo._language_empty.setFixedHeight(max(round(34*factor), combo._language_empty.fontMetrics().height()+round(12*factor)))
    search.setFixedHeight(max(round(32*factor), search.fontMetrics().height()+round(12*factor)))
    search.show()
    combo.itemDelegate().invalidate_metrics()
    if search.text():
        search.clear()
    else:
        combo._language_search_keys.filter_rows('')
