"""Keyboard access for native dialogs and the scaled main-window canvas."""
import weakref
import sys

from PyQt5 import QtCore, QtGui, QtWidgets, sip


LANGUAGES = ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id')
TEXT = {
    'title': ('Keyboard controls', 'Управление с клавиатуры', 'Control con teclado', 'Tastatursteuerung', 'Commandes au clavier', '键盘操作', 'Controles do teclado', 'Comandi da tastiera', 'التحكم بلوحة المفاتيح', 'Klavye denetimleri', 'कीबोर्ड नियंत्रण', 'Kontrol papan ketik'),
    'controls': ('Arrows — move between controls\nTab / Shift+Tab — next / previous control\nEnter / Space — activate a button or checkbox\nEnter / Alt+Down — open a list; arrows — choose\nEscape — close the list or dialog; go back in settings', 'Стрелки — переход между элементами\nTab / Shift+Tab — следующий / предыдущий элемент\nEnter / Пробел — нажать кнопку или галочку\nEnter / Alt+↓ — открыть список; стрелки — выбрать\nEscape — закрыть список или диалог; вернуться из настроек', 'Flechas — moverse entre controles\nTab / Mayús+Tab — control siguiente / anterior\nIntro / Espacio — activar un botón o casilla\nIntro / Alt+↓ — abrir una lista; flechas — elegir\nEsc — cerrar la lista o diálogo; volver desde ajustes', 'Pfeile — zwischen Elementen wechseln\nTab / Umschalt+Tab — nächstes / voriges Element\nEingabe / Leertaste — Schaltfläche oder Kästchen betätigen\nEingabe / Alt+↓ — Liste öffnen; Pfeile — auswählen\nEscape — Liste oder Dialog schließen; in Einstellungen zurück', 'Flèches — passer entre les commandes\nTab / Maj+Tab — commande suivante / précédente\nEntrée / Espace — activer un bouton ou une case\nEntrée / Alt+↓ — ouvrir une liste ; flèches — choisir\nÉchap — fermer la liste ou le dialogue ; revenir des réglages', '方向键 — 在控件间移动\nTab / Shift+Tab — 下一个／上一个控件\nEnter / 空格 — 激活按钮或复选框\nEnter / Alt+↓ — 打开列表；方向键 — 选择\nEsc — 关闭列表或对话框；从设置返回', 'Setas — mover entre controles\nTab / Shift+Tab — controle seguinte / anterior\nEnter / Espaço — acionar botão ou caixa\nEnter / Alt+↓ — abrir lista; setas — escolher\nEsc — fechar lista ou diálogo; voltar das configurações', 'Frecce — spostarsi tra i controlli\nTab / Maiusc+Tab — controllo successivo / precedente\nInvio / Spazio — attivare un pulsante o una casella\nInvio / Alt+↓ — aprire elenco; frecce — scegliere\nEsc — chiudere elenco o finestra; tornare dalle impostazioni', 'الأسهم — الانتقال بين عناصر التحكم\nTab / Shift+Tab — العنصر التالي / السابق\nEnter / مسافة — تفعيل زر أو مربع اختيار\nEnter / Alt+↓ — فتح قائمة؛ الأسهم — اختيار\nEscape — إغلاق القائمة أو النافذة؛ الرجوع من الإعدادات', 'Oklar — denetimler arasında geçiş\nTab / Shift+Tab — sonraki / önceki denetim\nEnter / Boşluk — düğmeyi veya kutuyu etkinleştir\nEnter / Alt+↓ — listeyi aç; oklar — seç\nEsc — listeyi veya pencereyi kapat; ayarlardan geri dön', 'तीर — नियंत्रणों के बीच जाएँ\nTab / Shift+Tab — अगला / पिछला नियंत्रण\nEnter / स्पेस — बटन या चेकबॉक्स चलाएँ\nEnter / Alt+↓ — सूची खोलें; तीर — चुनें\nEscape — सूची या संवाद बंद करें; सेटिंग्स से लौटें', 'Panah — berpindah antar kontrol\nTab / Shift+Tab — kontrol berikutnya / sebelumnya\nEnter / Spasi — aktifkan tombol atau kotak centang\nEnter / Alt+↓ — buka daftar; panah — pilih\nEscape — tutup daftar atau dialog; kembali dari pengaturan'),
    'app': ('Ctrl+, — settings\nCtrl+Tab / Ctrl+Shift+Tab — next / previous settings tab\nAlt+Left — back\nCtrl+O — attach a file\nCtrl+Enter — translate from the text editor\nF1 — keyboard help', 'Ctrl+, — настройки\nCtrl+Tab / Ctrl+Shift+Tab — следующая / предыдущая вкладка настроек\nAlt+← — назад\nCtrl+O — прикрепить файл\nCtrl+Enter — перевести текст из редактора\nF1 — помощь по клавиатуре', 'Ctrl+, — ajustes\nCtrl+Tab / Ctrl+Mayús+Tab — pestaña siguiente / anterior\nAlt+← — volver\nCtrl+O — adjuntar archivo\nCtrl+Intro — traducir desde el editor\nF1 — ayuda del teclado', 'Strg+, — Einstellungen\nStrg+Tab / Strg+Umschalt+Tab — nächster / voriger Einstellungsreiter\nAlt+← — zurück\nStrg+O — Datei anhängen\nStrg+Eingabe — Text im Editor übersetzen\nF1 — Tastaturhilfe', 'Ctrl+, — réglages\nCtrl+Tab / Ctrl+Maj+Tab — onglet suivant / précédent\nAlt+← — retour\nCtrl+O — joindre un fichier\nCtrl+Entrée — traduire depuis l’éditeur\nF1 — aide du clavier', 'Ctrl+, — 设置\nCtrl+Tab / Ctrl+Shift+Tab — 下一个／上一个设置标签\nAlt+← — 返回\nCtrl+O — 附加文件\nCtrl+Enter — 翻译编辑器中的文本\nF1 — 键盘帮助', 'Ctrl+, — configurações\nCtrl+Tab / Ctrl+Shift+Tab — aba seguinte / anterior\nAlt+← — voltar\nCtrl+O — anexar arquivo\nCtrl+Enter — traduzir no editor\nF1 — ajuda do teclado', 'Ctrl+, — impostazioni\nCtrl+Tab / Ctrl+Maiusc+Tab — scheda successiva / precedente\nAlt+← — indietro\nCtrl+O — allegare un file\nCtrl+Invio — tradurre dall’editor\nF1 — guida della tastiera', 'Ctrl+, — الإعدادات\nCtrl+Tab / Ctrl+Shift+Tab — تبويب الإعدادات التالي / السابق\nAlt+← — رجوع\nCtrl+O — إرفاق ملف\nCtrl+Enter — ترجمة النص من المحرر\nF1 — مساعدة لوحة المفاتيح', 'Ctrl+, — ayarlar\nCtrl+Tab / Ctrl+Shift+Tab — sonraki / önceki ayar sekmesi\nAlt+← — geri\nCtrl+O — dosya ekle\nCtrl+Enter — düzenleyicideki metni çevir\nF1 — klavye yardımı', 'Ctrl+, — सेटिंग्स\nCtrl+Tab / Ctrl+Shift+Tab — अगला / पिछला सेटिंग्स टैब\nAlt+← — वापस\nCtrl+O — फ़ाइल संलग्न करें\nCtrl+Enter — संपादक से अनुवाद करें\nF1 — कीबोर्ड सहायता', 'Ctrl+, — pengaturan\nCtrl+Tab / Ctrl+Shift+Tab — tab pengaturan berikutnya / sebelumnya\nAlt+← — kembali\nCtrl+O — lampirkan berkas\nCtrl+Enter — terjemahkan dari editor\nF1 — bantuan papan ketik'),
    'area': ('F6 — switch between the area and its controls\nArrows — create or move the area; Shift+arrows — resize\nCtrl+arrows — move faster\nEnter — confirm; Escape — cancel', 'F6 — переключиться между областью и кнопками\nСтрелки — создать или двигать область; Shift+стрелки — размер\nCtrl+стрелки — двигать быстрее\nEnter — подтвердить; Escape — отменить', 'F6 — alternar entre zona y controles\nFlechas — crear o mover zona; Mayús+flechas — tamaño\nCtrl+flechas — mover más rápido\nIntro — confirmar; Esc — cancelar', 'F6 — zwischen Bereich und Bedienelementen wechseln\nPfeile — Bereich erstellen oder bewegen; Umschalt+Pfeile — Größe\nStrg+Pfeile — schneller bewegen\nEingabe — bestätigen; Escape — abbrechen', 'F6 — passer de la zone aux commandes\nFlèches — créer ou déplacer ; Maj+flèches — redimensionner\nCtrl+flèches — déplacer plus vite\nEntrée — confirmer ; Échap — annuler', 'F6 — 在区域与控件间切换\n方向键 — 创建或移动区域；Shift+方向键 — 调整大小\nCtrl+方向键 — 加速移动\nEnter — 确认；Esc — 取消', 'F6 — alternar entre área e controles\nSetas — criar ou mover área; Shift+setas — tamanho\nCtrl+setas — mover mais rápido\nEnter — confirmar; Esc — cancelar', 'F6 — passare dall’area ai controlli\nFrecce — creare o spostare l’area; Maiusc+frecce — dimensioni\nCtrl+frecce — spostare più velocemente\nInvio — confermare; Esc — annullare', 'F6 — التبديل بين المنطقة وعناصر التحكم\nالأسهم — إنشاء المنطقة أو نقلها؛ Shift+الأسهم — تغيير الحجم\nCtrl+الأسهم — نقل أسرع\nEnter — تأكيد؛ Escape — إلغاء', 'F6 — alan ve denetimler arasında geçiş\nOklar — alan oluştur veya taşı; Shift+oklar — boyutlandır\nCtrl+oklar — daha hızlı taşı\nEnter — onayla; Esc — iptal', 'F6 — क्षेत्र और नियंत्रणों के बीच बदलें\nतीर — क्षेत्र बनाएँ या खिसकाएँ; Shift+तीर — आकार बदलें\nCtrl+तीर — तेज़ खिसकाएँ\nEnter — पुष्टि; Escape — रद्द', 'F6 — beralih antara area dan kontrol\nPanah — buat atau pindahkan area; Shift+panah — ubah ukuran\nCtrl+panah — pindahkan lebih cepat\nEnter — konfirmasi; Escape — batal'),
    'pairs': ('Insert / N — add an area; Space — switch source / output\nPageUp / PageDown — previous / next area\nDelete — remove the selected area', 'Insert / N — добавить область; Пробел — источник / результат\nPageUp / PageDown — предыдущая / следующая область\nDelete — удалить выбранную область', 'Insert / N — añadir zona; Espacio — origen / resultado\nRePág / AvPág — zona anterior / siguiente\nSupr — eliminar zona seleccionada', 'Insert / N — Bereich hinzufügen; Leertaste — Quelle / Ausgabe\nBild↑ / Bild↓ — voriger / nächster Bereich\nEntf — ausgewählten Bereich entfernen', 'Insert / N — ajouter une zone ; Espace — source / résultat\nPage↑ / Page↓ — zone précédente / suivante\nSuppr — supprimer la zone sélectionnée', 'Insert / N — 添加区域；空格 — 切换源区域／结果区域\nPageUp / PageDown — 上一个／下一个区域\nDelete — 删除所选区域', 'Insert / N — adicionar área; Espaço — origem / resultado\nPageUp / PageDown — área anterior / seguinte\nDelete — remover área selecionada', 'Insert / N — aggiungere area; Spazio — origine / risultato\nPagSu / PagGiù — area precedente / successiva\nCanc — eliminare l’area selezionata', 'Insert / N — إضافة منطقة؛ مسافة — المصدر / النتيجة\nPageUp / PageDown — المنطقة السابقة / التالية\nDelete — حذف المنطقة المحددة', 'Insert / N — alan ekle; Boşluk — kaynak / sonuç\nPageUp / PageDown — önceki / sonraki alan\nDelete — seçili alanı sil', 'Insert / N — क्षेत्र जोड़ें; स्पेस — स्रोत / परिणाम\nPageUp / PageDown — पिछला / अगला क्षेत्र\nDelete — चयनित क्षेत्र हटाएँ', 'Insert / N — tambah area; Spasi — sumber / hasil\nPageUp / PageDown — area sebelumnya / berikutnya\nDelete — hapus area terpilih'),
}


def text(locale, key):
    from text_direction import ui_directional_text
    return ui_directional_text(TEXT[key][LANGUAGES.index(locale) if locale in LANGUAGES else 0], locale)


def _root(widget):
    window = widget.window()
    if hasattr(window, 'ui_root'):
        return window.ui_root
    return window


def _owner(root):
    reference = getattr(root, '_ui_native_owner', None)
    return reference() if reference is not None else None


def _inside(widget, property_name):
    while widget is not None:
        if widget.property(property_name):
            return widget
        widget = widget.parentWidget()
    return None


def matches_control_shortcut(event, key):
    """Keep the two advertised app commands usable on non-Latin Windows layouts."""
    if event.modifiers() != QtCore.Qt.ControlModifier:
        return False
    if event.key() == key:
        return True
    if sys.platform == 'win32':
        # Qt reports Cyrillic/Arabic characters in key(), whereas these Windows
        # virtual keys remain stable. Do not interpret native codes on macOS/X11.
        virtual_key = {QtCore.Qt.Key_Comma: 0xBC, QtCore.Qt.Key_O: 0x4F}.get(key)
        return virtual_key is not None and event.nativeVirtualKey() == virtual_key
    return False


def _has_embedded_popup(root):
    # A QGraphicsProxyWidget popup is not QApplication.activePopupWidget().
    # The native view still receives its keys, so inspect its small proxy tree
    # instead of redirecting those keys to a control behind the open list.
    proxy = root.graphicsProxyWidget()
    pending = list(proxy.childItems()) if proxy is not None else []
    while pending:
        item = pending.pop()
        if not item.isVisible():
            continue
        if isinstance(item, QtWidgets.QGraphicsProxyWidget):
            popup = item.widget()
            if popup is not None and popup.windowType() == QtCore.Qt.Popup:
                return True
        pending.extend(item.childItems())
    return False


_CONTROLS = (QtWidgets.QAbstractButton, QtWidgets.QComboBox, QtWidgets.QLineEdit,
             QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit, QtWidgets.QAbstractSpinBox,
             QtWidgets.QAbstractSlider, QtWidgets.QAbstractItemView, QtWidgets.QTabBar,
             QtWidgets.QKeySequenceEdit, QtWidgets.QScrollArea, QtWidgets.QTextBrowser, QtWidgets.QLabel)


def tab_stops(root):
    """Collect only visible controls, in reading order, at the time of Tab."""
    rows = []
    for widget in root.findChildren(QtWidgets.QWidget):
        if (not isinstance(widget, _CONTROLS) or not widget.focusPolicy() & QtCore.Qt.TabFocus
                or not widget.isVisibleTo(root) or not widget.isEnabled() or widget.window() is not root):
            continue
        if isinstance(widget, QtWidgets.QAbstractButton) and _inside(widget, 'keyboardTabs') is not None and not widget.isChecked():
            continue
        if isinstance(widget, QtWidgets.QRadioButton):
            group = widget.group()
            siblings = group.buttons() if group is not None else [child for child in widget.parentWidget().children()
                        if isinstance(child, QtWidgets.QRadioButton)]
            if (group is not None and group.exclusive()) or widget.autoExclusive():
                eligible = [button for button in siblings if button.isVisibleTo(root) and button.isEnabled()]
                selected = next((button for button in eligible if button.isChecked()), eligible[0] if eligible else None)
                if widget is not selected:
                    continue
        parent = widget.parentWidget()
        internal = False
        while parent is not None and parent is not root:
            if isinstance(parent, (QtWidgets.QComboBox, QtWidgets.QAbstractSpinBox, QtWidgets.QAbstractItemView,
                                   QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit, QtWidgets.QKeySequenceEdit)):
                internal = True
                break
            parent = parent.parentWidget()
        if not internal:
            point = widget.mapTo(root, QtCore.QPoint())
            rows.append((widget, point))
    # Group by proximity instead of rounding into buckets: controls centered
    # on opposite sides of a bucket boundary still belong to the same row.
    rows.sort(key=lambda item: item[1].y()+item[0].height()/2)
    groups = []
    for item in rows:
        center = item[1].y()+item[0].height()/2
        if not groups or center-groups[-1][0] > 12:
            groups.append((center, []))
        groups[-1][1].append(item)
    result = []
    for _center, items in groups:
        rtl = root.layoutDirection() == QtCore.Qt.RightToLeft and not root.property('keyboardCanvas')
        items.sort(key=lambda item: -item[1].x() if rtl else item[1].x())
        result.extend(widget for widget, _point in items)
    return result


def focus_control(widget, backwards=False):
    navigation = getattr(QtWidgets.QApplication.instance(), '_keyboard_navigation', None)
    if navigation is not None:
        # This helper deliberately requests keyboard navigation. Qt also uses
        # TabFocusReason for automatic focus transfers after a mouse action,
        # so the reason on a later FocusIn event cannot establish the mode.
        navigation.keyboard = True
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QtWidgets.QScrollArea):
            parent.ensureWidgetVisible(widget, 8, 8)
        parent = parent.parentWidget()
    widget.setFocus(QtCore.Qt.BacktabFocusReason if backwards else QtCore.Qt.TabFocusReason)
    if navigation is not None:
        # A one-control dialog can wrap Tab back to the already focused
        # widget, producing no FocusIn event to paint the keyboard cue.
        navigation._show_ring(widget)


def _scroll_area(widget):
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QtWidgets.QScrollArea):
            return parent
        parent = parent.parentWidget()
    return None


def spatial_target(root, current, key):
    """Find the closest control in the requested visual direction."""
    controls = tab_stops(root)
    if current not in controls:
        return controls[0] if controls else None
    origin = QtCore.QRect(current.mapTo(root, QtCore.QPoint()), current.size())
    center = QtCore.QPointF(origin.center())
    horizontal = key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right)
    sign = -1 if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Up) else 1
    current_scroll = _scroll_area(current)
    candidates = []
    for widget in controls:
        if widget is current or widget.isAncestorOf(current) or isinstance(widget, QtWidgets.QScrollArea):
            continue
        rect = QtCore.QRect(widget.mapTo(root, QtCore.QPoint()), widget.size())
        scroll = _scroll_area(widget)
        if scroll is not None and scroll is not current_scroll:
            viewport = scroll.viewport()
            visible = QtCore.QRect(viewport.mapTo(root, QtCore.QPoint()), viewport.size())
            if not visible.intersects(rect):
                continue
        dx, dy = rect.center().x()-center.x(), rect.center().y()-center.y()
        primary = (dx if horizontal else dy)*sign
        if primary <= 1:
            continue
        cross = abs(dy if horizontal else dx)
        cross_size = (rect.height()+origin.height() if horizontal else rect.width()+origin.width())/2
        primary_size = (rect.width()+origin.width() if horizontal else rect.height()+origin.height())/2
        cross_gap, gap = max(0, cross-cross_size), max(0, primary-primary_size)
        candidates.append(((cross_gap > 0, gap+cross_gap*3, cross, primary), widget))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _uses_arrow_navigation(widget):
    if _inside(widget, 'numberStepper') is not None or widget.property('keyboardArrowControl'):
        return False
    if isinstance(widget, QtWidgets.QRadioButton):
        return False  # Native arrows select within the radio group.
    return (isinstance(widget, (QtWidgets.QAbstractButton, QtWidgets.QLabel))
            or isinstance(widget, QtWidgets.QComboBox) and not widget.isEditable())


def edit_area(rect, bounds, key, modifiers=QtCore.Qt.NoModifier, minimum=(8, 8)):
    """Move/resize in logical screen coordinates; no pointer warping."""
    if rect is None:
        size = QtCore.QSize(min(bounds.width(), max(minimum[0], min(320, bounds.width()//2))),
                            min(bounds.height(), max(minimum[1], min(120, bounds.height()//3))))
        rect = QtCore.QRect(QtCore.QPoint(), size)
        rect.moveCenter(bounds.center())
    else:
        rect = QtCore.QRect(rect)
    step = 10 if modifiers & QtCore.Qt.ControlModifier else 1
    dx = -step if key == QtCore.Qt.Key_Left else step if key == QtCore.Qt.Key_Right else 0
    dy = -step if key == QtCore.Qt.Key_Up else step if key == QtCore.Qt.Key_Down else 0
    if modifiers & QtCore.Qt.ShiftModifier:
        rect.setWidth(max(minimum[0], min(bounds.right()-rect.x()+1, rect.width()+dx)))
        rect.setHeight(max(minimum[1], min(bounds.bottom()-rect.y()+1, rect.height()+dy)))
    else:
        rect.translate(dx, dy)
        rect.moveLeft(max(bounds.left(), min(rect.x(), bounds.right()-rect.width()+1)))
        rect.moveTop(max(bounds.top(), min(rect.y(), bounds.bottom()-rect.height()+1)))
    return rect


class _FocusRing(QtWidgets.QWidget):
    def __init__(self, root):
        super().__init__(root)
        self.setObjectName('keyboardFocusRing')
        self.setProperty('_cntTransientChrome', True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.hide()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        dark = QtWidgets.QApplication.instance().property('ui_theme') != 'Светлая'
        painter.setPen(QtGui.QPen(QtGui.QColor('#c5ace3' if dark else '#79569b'), 1.5))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1), 5, 5)


class KeyboardNavigation(QtCore.QObject):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.keyboard = False
        self._focused = lambda: None
        self._ring = lambda: None
        self._help_dialog = None
        self._help_pending = False

    def _hide_ring(self):
        ring = self._ring()
        if ring is not None and not sip.isdeleted(ring):
            ring.hide()

    @staticmethod
    def _focus_style(widget, enabled):
        if (isinstance(widget, (QtWidgets.QPushButton, QtWidgets.QToolButton, QtWidgets.QComboBox))
                and not sip.isdeleted(widget) and bool(widget.property('keyboardFocus')) != enabled):
            widget.setProperty('keyboardFocus', enabled)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def _show_ring(self, widget):
        self._hide_ring()
        if not isinstance(widget, _CONTROLS) or not widget.isVisible():
            return
        root = _root(widget)
        if widget.window() is not root or isinstance(root, QtWidgets.QMenu):
            return
        self._focus_style(widget, True)
        ring = getattr(root, '_keyboard_focus_ring', None)
        if ring is None or sip.isdeleted(ring):
            ring = root._keyboard_focus_ring = _FocusRing(root)
        geometry = QtCore.QRect(widget.mapTo(root, QtCore.QPoint()), widget.size())
        if isinstance(widget, (QtWidgets.QCheckBox, QtWidgets.QRadioButton, QtWidgets.QLabel)):
            geometry.adjust(-2, -2, 2, 2)
        ring.setGeometry(geometry.intersected(root.rect()))
        ring.show()
        ring.raise_()
        self._focused, self._ring = weakref.ref(widget), weakref.ref(ring)

    def note_key_input(self, widget, event):
        """Only focus-navigation keys enable the keyboard focus decoration."""
        key, modifiers = event.key(), event.modifiers()
        if key in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab, QtCore.Qt.Key_F1,
                   QtCore.Qt.Key_F6) or matches_control_shortcut(event, QtCore.Qt.Key_Comma):
            self.keyboard = True
        elif modifiers & QtCore.Qt.AltModifier and key == QtCore.Qt.Key_Left:
            self.keyboard = True
        else:
            target = widget
            editing = False
            while target is not None:
                if isinstance(target, (QtWidgets.QLineEdit, QtWidgets.QTextEdit,
                        QtWidgets.QPlainTextEdit, QtWidgets.QAbstractSpinBox,
                        QtWidgets.QKeySequenceEdit)):
                    editing = True
                    break
                target = target.parentWidget()
            if not editing and key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right,
                    QtCore.Qt.Key_Up, QtCore.Qt.Key_Down, QtCore.Qt.Key_Home,
                    QtCore.Qt.Key_End, QtCore.Qt.Key_PageUp, QtCore.Qt.Key_PageDown,
                    QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Space):
                self.keyboard = True
        return self.keyboard

    def _back(self, owner):
        settings = getattr(owner, 'settings_window', None)
        if settings is None:
            return False
        if getattr(settings, '_secondary_view_kind', None):
            settings._return_from_secondary_view()
        else:
            owner.show_main_screen()
        focus_control(owner.settings_button)
        return True

    def _settings_tab(self, owner, direction):
        settings = getattr(owner, 'settings_window', None)
        if settings is None or getattr(settings, '_secondary_view_kind', None):
            return False
        from settings_sections import VISUAL_PAGE_ORDER
        order = VISUAL_PAGE_ORDER
        current = getattr(settings, '_settings_page_index', 0)
        # The inline updater adds a status page outside the settings tabs.
        # Its progress/result must not be interpreted as an index in this order.
        if current not in order or getattr(settings, '_update_in_progress', False):
            return False
        index = order[(order.index(current)+direction) % len(order)]
        settings._set_settings_page(index)
        focus_control(settings.settings_page_tabs[index])
        return True

    def _help(self, root):
        if self._help_dialog is not None and not sip.isdeleted(self._help_dialog) and self._help_dialog.isVisible():
            self._help_dialog.raise_()
            self._help_dialog.activateWindow()
            return
        if self._help_pending:
            return
        self._help_pending = True
        root_ref = weakref.ref(root)
        focused = root.focusWidget()
        focus_ref = weakref.ref(focused) if focused is not None else lambda: None
        # Leave the native/graphics-proxy key dispatch before showing a window.
        QtCore.QTimer.singleShot(0, lambda: self._open_help(root_ref, focus_ref))

    def _open_help(self, root_ref, focus_ref):
        self._help_pending = False
        root = root_ref()
        if root is None or sip.isdeleted(root) or not root.isVisible():
            return
        owner = _owner(root)
        config = getattr(owner or root, 'config', getattr(root, '_config', {}))
        if not isinstance(config, dict):
            config = {}
        locale = config.get('interface_language')
        if not locale:
            for attribute in ['lang', '_language', '_memory_locale', 'language', '_lang', '_dialog_language_code']:
                value = getattr(root, attribute, None)
                if isinstance(value, str) and value:
                    locale = value
                    break
        locale = locale or 'en'
        message = text(locale, 'controls')
        if owner is not None:
            message += '\n\n'+text(locale, 'app')
        if root.property('keyboardCanvas'):
            message += '\n\n'+text(locale, 'area')
        if root.property('keyboardPairedAreas'):
            message += '\n\n'+text(locale, 'pairs')
        from styled_dialogs import StyledMessageBox
        box = StyledMessageBox(owner or root)
        self._help_dialog = box
        box.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        box.setWindowTitle(text(locale, 'title'))
        box.setText(message)
        box.setStandardButtons(StyledMessageBox.Ok)
        def finished(_result):
            if self._help_dialog is box:
                self._help_dialog = None
            previous = focus_ref()
            if previous is not None and not sip.isdeleted(previous) and previous.isVisible() and previous.isEnabled():
                if self.keyboard:
                    focus_control(previous)
                else:
                    previous.setFocus(QtCore.Qt.OtherFocusReason)
        box.finished.connect(finished)
        box.open()

    def eventFilter(self, widget, event):
        kind = event.type()
        if not isinstance(widget, QtWidgets.QWidget):
            return False
        if kind == QtCore.QEvent.Polish:
            if isinstance(widget, QtWidgets.QAbstractButton) and widget.focusPolicy() == QtCore.Qt.NoFocus:
                widget.setFocusPolicy(QtCore.Qt.TabFocus)
            elif isinstance(widget, (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
                widget.setTabChangesFocus(True)
            elif isinstance(widget, QtWidgets.QScrollArea):
                widget.setFocusPolicy(QtCore.Qt.StrongFocus)
            elif isinstance(widget, QtWidgets.QLabel) and 'href=' in widget.text():
                widget.setTextInteractionFlags(widget.textInteractionFlags() | QtCore.Qt.LinksAccessibleByKeyboard)
                widget.setFocusPolicy(QtCore.Qt.TabFocus)
            return False
        if kind in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.Wheel):
            self.keyboard = False
            self._hide_ring()
            self._focus_style(self._focused(), False)
            return False
        if kind in (QtCore.QEvent.WindowDeactivate, QtCore.QEvent.ApplicationDeactivate):
            self._hide_ring()
            return False
        if kind == QtCore.QEvent.FocusOut:
            self._focus_style(widget, False)
            if self._focused() is widget:
                self._hide_ring()
            return False
        if kind == QtCore.QEvent.FocusIn:
            if event.reason() == QtCore.Qt.MouseFocusReason:
                self.keyboard = False
                self._hide_ring()
                self._focus_style(self._focused(), False)
                self._focus_style(widget, False)
            if self.keyboard:
                self._show_ring(widget)
            return False
        if kind in (QtCore.QEvent.Hide, QtCore.QEvent.EnabledChange):
            if self._focused() is widget:
                self._hide_ring()
            return False
        if kind in (QtCore.QEvent.Move, QtCore.QEvent.Resize):
            if self.keyboard and self._focused() is widget:
                self._show_ring(widget)
            return False
        if kind != QtCore.QEvent.KeyPress:
            return False
        root = _root(widget)
        # Native menu/search popups and the paged UI-language selector manage
        # their own keys. A key must never act on the window behind a popup.
        if root.windowType() == QtCore.Qt.Popup:
            # A proxy can forward the closing Enter again after Qt hides its
            # popup. Consume that stale delivery before it reopens the combo.
            return not root.isVisible()
        if (self.app.activePopupWidget() is not None or isinstance(root, QtWidgets.QMenu)
                or _has_embedded_popup(root)):
            return False
        if _inside(widget, 'keyboardOwnNavigation') is not None:
            return False
        parent = widget
        while parent is not None:
            if isinstance(parent, QtWidgets.QKeySequenceEdit) and not (
                    event.key() in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab)
                    and event.modifiers() in (QtCore.Qt.NoModifier, QtCore.Qt.ShiftModifier)):
                return False
            parent = parent.parentWidget()
        focus = widget if isinstance(widget, _CONTROLS) else root.focusWidget() or widget
        if _inside(focus, 'keyboardOwnNavigation') is not None:
            return False
        key, modifiers = event.key(), event.modifiers()
        ctrl, shift, alt = bool(modifiers & QtCore.Qt.ControlModifier), bool(modifiers & QtCore.Qt.ShiftModifier), bool(modifiers & QtCore.Qt.AltModifier)
        owner = _owner(root)
        self.note_key_input(focus, event)
        if key == QtCore.Qt.Key_F1 and not modifiers:
            if not event.isAutoRepeat():
                self._help(root)
            return True
        if owner is not None:
            if matches_control_shortcut(event, QtCore.Qt.Key_Comma):
                owner.show_settings()
                focus_control(owner.settings_window.settings_page_tabs[0])
                return True
            if ctrl and key in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab):
                return self._settings_tab(owner, -1 if shift or key == QtCore.Qt.Key_Backtab else 1)
            editing = isinstance(focus, (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox, QtWidgets.QKeySequenceEdit))
            if (key == QtCore.Qt.Key_Escape and not modifiers and not editing) or (alt and key == QtCore.Qt.Key_Left):
                if self._back(owner):
                    return True
        if key == QtCore.Qt.Key_F6 and root.property('keyboardCanvas'):
            controls = tab_stops(root)
            if focus is root and controls:
                source = getattr(root, 'lang_combo', None)
                if (isinstance(source, QtWidgets.QWidget) and not sip.isdeleted(source)
                        and source.isVisibleTo(root) and source.isEnabled()):
                    focus_control(source)
                else:
                    focus_control(controls[0])
            else:
                root.setFocus(QtCore.Qt.TabFocusReason)
                self._hide_ring()
            return True
        if key in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab) and not ctrl and not alt:
            if isinstance(focus, (QtWidgets.QTextBrowser, QtWidgets.QLabel)):
                return False  # Its native Tab traversal also visits HTML links.
            controls = tab_stops(root)
            if controls:
                parent = focus.parentWidget()
                while focus not in controls and parent is not None:
                    if parent in controls:
                        focus = parent
                        break
                    parent = parent.parentWidget()
                backward = shift or key == QtCore.Qt.Key_Backtab
                index = controls.index(focus) if focus in controls else (0 if backward else -1)
                focus_control(controls[(index+(-1 if backward else 1)) % len(controls)], backward)
                return True
        if modifiers == QtCore.Qt.NoModifier:
            group = _inside(focus, 'keyboardTabs')
            if group is not None and key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Home, QtCore.Qt.Key_End):
                buttons = [button for button in group.findChildren(QtWidgets.QAbstractButton)
                           if button.isVisibleTo(root) and button.isEnabled()]
                buttons.sort(key=lambda button: button.mapTo(root, QtCore.QPoint()).x())
                if buttons:
                    index = buttons.index(focus) if focus in buttons else 0
                    target = (0 if key == QtCore.Qt.Key_Home else len(buttons)-1 if key == QtCore.Qt.Key_End
                              else (index+(-1 if key == QtCore.Qt.Key_Left else 1)) % len(buttons))
                    buttons[target].click()
                    focus_control(buttons[target])
                    return True
            navigate = (_uses_arrow_navigation(focus) or isinstance(focus, QtWidgets.QTabBar)
                        and key in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down))
            if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down) and navigate:
                target = spatial_target(root, focus, key)
                if target is not None:
                    focus_control(target)
                self._show_ring(target or focus)
                return True
            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and isinstance(focus, QtWidgets.QAbstractButton):
                if not event.isAutoRepeat() and focus.isEnabled():
                    focus.click()
                return True
            if isinstance(focus, QtWidgets.QComboBox) and not focus.isEditable() and key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Space):
                focus.showPopup()
                return True
            if key == QtCore.Qt.Key_Space and isinstance(focus, QtWidgets.QTableWidget):
                row = focus.currentRow()
                for column in range(focus.columnCount()):
                    item = focus.item(row, column)
                    if item is not None and item.flags() & QtCore.Qt.ItemIsUserCheckable and item.flags() & QtCore.Qt.ItemIsEnabled:
                        item.setCheckState(QtCore.Qt.Unchecked if item.checkState() == QtCore.Qt.Checked else QtCore.Qt.Checked)
                        return True
                    cell = focus.cellWidget(row, column)
                    checkbox = cell if isinstance(cell, QtWidgets.QCheckBox) else cell.findChild(QtWidgets.QCheckBox) if cell is not None else None
                    if checkbox is not None and checkbox.isEnabled():
                        checkbox.click()
                        return True
        if self.keyboard:
            self._show_ring(focus)
        return False


def install_keyboard_navigation(app=None):
    app = app or QtWidgets.QApplication.instance()
    if app is not None and not hasattr(app, '_keyboard_navigation'):
        app._keyboard_navigation = KeyboardNavigation(app)
        app.installEventFilter(app._keyboard_navigation)
