"""Optional last-area geometry, independent of OCR languages and UI scale."""
from PyQt5 import QtCore, QtWidgets

LANGUAGES = ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id')
TEXT = {
    'capture_error': ('The selected area cannot be captured', 'Не удалось захватить выбранную область', 'No se puede capturar el área seleccionada', 'Der ausgewählte Bereich kann nicht erfasst werden', 'Impossible de capturer la zone sélectionnée', '无法捕获所选区域', 'A área selecionada não pode ser capturada', "L’area selezionata non può essere catturata", 'تعذر التقاط المنطقة المحددة', 'Seçili alan yakalanamıyor', 'चुना क्षेत्र कैप्चर नहीं हो सकता', 'Area pilihan tidak dapat ditangkap'),
    'remember': ('Remember area', 'Запоминать область', 'Recordar zona', 'Bereich merken', 'Mémoriser la zone', '记住区域', 'Lembrar área', 'Ricorda area', 'تذكر المنطقة', 'Alanı hatırla', 'क्षेत्र याद रखें', 'Ingat area'),
    'repeat': ('Repeat', 'Повторить', 'Repetir', 'Wiederholen', 'Répéter', '重复', 'Repetir', 'Ripeti', 'تكرار', 'Tekrarla', 'दोहराएँ', 'Ulangi'),
    'hint': ('Show the previous area next time in this mode. Click Repeat or press Enter to capture fresh text, or draw a new area.', 'При следующем запуске этого режима покажет прежнюю рамку. Кнопка «Повторить» или Enter захватит новый текст; мышью можно выделить другую область.', 'Muestra la zona anterior al volver a este modo. Pulsa Repetir o Enter para capturar texto nuevo, o dibuja otra zona.', 'Zeigt beim nächsten Aufruf dieses Modus den bisherigen Bereich. Wiederholen oder Enter erfasst neuen Text; mit der Maus einen anderen Bereich wählen.', 'Affiche la zone précédente au prochain lancement de ce mode. Répéter ou Entrée capture le nouveau texte ; vous pouvez aussi tracer une autre zone.', '下次启动此模式时显示上次区域。点击“重复”或按 Enter 捕获新文字，也可以重新选择区域。', 'Mostra a área anterior ao abrir este modo novamente. Clique em Repetir ou pressione Enter para capturar texto novo, ou selecione outra área.', 'Mostra l’area precedente al prossimo avvio di questa modalità. Premi Ripeti o Invio per acquisire nuovo testo, oppure seleziona un’altra area.', 'يعرض المنطقة السابقة عند تشغيل هذا الوضع مجددًا. انقر على تكرار أو اضغط Enter لالتقاط نص جديد، أو حدد منطقة أخرى.', 'Bu mod tekrar açıldığında önceki alanı gösterir. Yeni metni almak için Tekrarla veya Enter kullanın ya da yeni bir alan çizin.', 'अगली बार इस मोड में पिछला क्षेत्र दिखाएगा। नया टेक्स्ट लेने के लिए दोहराएँ या Enter दबाएँ, या दूसरा क्षेत्र चुनें।', 'Tampilkan area sebelumnya saat mode ini dibuka lagi. Klik Ulangi atau tekan Enter untuk mengambil teks baru, atau pilih area lain.'),
    'ready': ('Previous area · Enter or Repeat · Draw a new area to replace it', 'Прежняя область · Enter или «Повторить» · Мышью — новая область', 'Zona anterior · Enter o Repetir · Dibuja otra para cambiarla', 'Bisheriger Bereich · Enter oder Wiederholen · Mit der Maus neu wählen', 'Zone précédente · Entrée ou Répéter · Tracez une autre zone pour la remplacer', '上次区域 · Enter 或“重复” · 重新框选可替换区域', 'Área anterior · Enter ou Repetir · Selecione outra para substituí-la', 'Area precedente · Invio o Ripeti · Seleziona una nuova area per sostituirla', 'المنطقة السابقة · Enter أو تكرار · حدد منطقة جديدة لاستبدالها', 'Önceki alan · Enter veya Tekrarla · Değiştirmek için yeni alan çizin', 'पिछला क्षेत्र · Enter या दोहराएँ · बदलने के लिए नया क्षेत्र चुनें', 'Area sebelumnya · Enter atau Ulangi · Pilih area baru untuk menggantinya'),
    'unavailable': ('The saved area is unavailable on this screen. Select a new area.', 'Сохранённая область недоступна на этом экране. Выделите новую.', 'La zona guardada no está disponible en esta pantalla. Selecciona otra.', 'Der gespeicherte Bereich ist auf diesem Bildschirm nicht verfügbar. Bitte neu auswählen.', 'La zone mémorisée est indisponible sur cet écran. Sélectionnez une autre zone.', '此屏幕上无法恢复保存的区域，请重新选择。', 'A área salva não está disponível nesta tela. Selecione outra.', 'L’area salvata non è disponibile su questo schermo. Selezionane un’altra.', 'المنطقة المحفوظة غير متاحة على هذه الشاشة. حدد منطقة جديدة.', 'Kayıtlı alan bu ekranda kullanılamıyor. Yeni bir alan seçin.', 'सहेजा क्षेत्र इस स्क्रीन पर उपलब्ध नहीं है। नया क्षेत्र चुनें।', 'Area tersimpan tidak tersedia di layar ini. Pilih area baru.'),
    'save_error': ('Could not save the area preference.', 'Не удалось сохранить настройку области.', 'No se pudo guardar la preferencia de zona.', 'Die Bereichseinstellung konnte nicht gespeichert werden.', 'Impossible d’enregistrer le réglage de la zone.', '无法保存区域设置。', 'Não foi possível salvar a preferência da área.', 'Impossibile salvare l’impostazione dell’area.', 'تعذر حفظ إعداد المنطقة.', 'Alan tercihi kaydedilemedi.', 'क्षेत्र की सेटिंग सहेज नहीं सके।', 'Preferensi area tidak dapat disimpan.'),
    'dynamic_remember': ('Remember selected template', 'Запоминать выбранный шаблон', 'Recordar plantilla elegida', 'Gewählte Vorlage merken', 'Mémoriser le modèle choisi', '记住选中的模板', 'Lembrar modelo selecionado', 'Ricorda il modello selezionato', 'تذكر القالب المحدد', 'Seçili şablonu hatırla', 'चुना टेम्पलेट याद रखें', 'Ingat templat terpilih'),
    'template_label': ('Template:', 'Шаблон:', 'Plantilla:', 'Vorlage:', 'Modèle :', '模板：', 'Modelo:', 'Modello:', 'القالب:', 'Şablon:', 'टेम्पलेट:', 'Templat:'),
    'dynamic_hint': ('Reopen the template used to start the last session. Check its areas and click Start. Choosing New template starts with empty areas.', 'При следующем включении откроет шаблон, с которым запустили прошлый сеанс. Проверьте области и нажмите «Запустить». «Новый шаблон» начнёт выбор с пустых областей.', 'Abre la plantilla usada al iniciar la última sesión. Revisa las zonas y pulsa Iniciar. Nueva plantilla empieza con zonas vacías.', 'Öffnet die Vorlage der zuletzt gestarteten Sitzung. Bereiche prüfen und Start drücken. Neue Vorlage beginnt ohne Bereiche.', 'Rouvre le modèle de la dernière session démarrée. Vérifiez les zones puis cliquez sur Démarrer. Nouveau modèle commence sans zones.', '重新打开上次启动会话时使用的模板。检查区域后点击开始。“新模板”从空白区域开始。', 'Reabre o modelo usado na última sessão iniciada. Confira as áreas e clique em Iniciar. Novo modelo começa sem áreas.', 'Riapre il modello dell’ultima sessione avviata. Controlla le aree e premi Avvia. Nuovo modello parte senza aree.', 'يعيد فتح قالب آخر جلسة بدأت. تحقق من المناطق وانقر على ابدأ. اختر «قالب جديد» للبدء بمناطق فارغة.', 'Son başlatılan oturumun şablonunu açar. Alanları kontrol edip Başlat’a basın. Yeni şablon boş alanlarla başlar.', 'पिछले शुरू किए सत्र का टेम्पलेट खोलेगा। क्षेत्र जाँचकर शुरू करें दबाएँ। नया टेम्पलेट खाली क्षेत्रों से शुरू होता है।', 'Buka kembali templat sesi terakhir yang dimulai. Periksa area lalu klik Mulai. Templat baru dimulai tanpa area.'),
    'dynamic_missing': ('The saved template or one of its screens is unavailable. Choose another template or draw new areas.', 'Сохранённый шаблон или один из его экранов недоступен. Выберите другой шаблон или выделите новые области.', 'La plantilla guardada o una de sus pantallas no está disponible. Elige otra plantilla o nuevas zonas.', 'Die gespeicherte Vorlage oder ein Bildschirm ist nicht verfügbar. Andere Vorlage oder neue Bereiche wählen.', 'Le modèle mémorisé ou un de ses écrans est indisponible. Choisissez un autre modèle ou de nouvelles zones.', '保存的模板或其中一个屏幕不可用，请选择其他模板或重新选择区域。', 'O modelo salvo ou uma de suas telas não está disponível. Escolha outro modelo ou novas áreas.', 'Il modello salvato o uno dei suoi schermi non è disponibile. Scegli un altro modello o nuove aree.', 'القالب المحفوظ أو إحدى شاشاته غير متاحة. اختر قالبًا آخر أو حدد مناطق جديدة.', 'Kayıtlı şablon veya ekranlarından biri kullanılamıyor. Başka şablon ya da yeni alanlar seçin.', 'सहेजा टेम्पलेट या उसकी कोई स्क्रीन उपलब्ध नहीं है। दूसरा टेम्पलेट या नए क्षेत्र चुनें।', 'Templat tersimpan atau salah satu layarnya tidak tersedia. Pilih templat lain atau area baru.'),
}


def text(locale, key):
    from text_direction import ui_directional_text
    return ui_directional_text(TEXT[key][LANGUAGES.index(locale) if locale in LANGUAGES else 0], locale)


def memory_keys(mode):
    prefix = 'translate' if mode == 'translate' else 'copy'
    return f'remember_{prefix}_area', f'last_{prefix}_area'


def screen_identity(screen):
    identity = {'name': screen.name(), 'size': [screen.geometry().width(), screen.geometry().height()]}
    for key in ('serialNumber', 'manufacturer', 'model'):
        value = getattr(screen, key, lambda: '')()
        if value:
            identity[key] = str(value)
    identity['dpi'] = round(float(getattr(screen, 'logicalDotsPerInch', lambda: 96.)()), 2)
    return identity


def encode_area(rect, screen):
    rect = QtCore.QRect(rect).normalized()
    if screen is None or not screen.geometry().contains(rect) or rect.width() < 8 or rect.height() < 8 or rect.width()*rect.height() < 180:
        return None
    local = rect.translated(-screen.geometry().topLeft())
    return {'version': 1, 'screen': screen_identity(screen), 'rect': list(local.getRect())}


def validated_area(value):
    """Validate portable settings without accessing any attached screen."""
    import math
    if not isinstance(value, dict) or value.get('version') != 1:
        return None
    identity, rect = value.get('screen'), value.get('rect')
    if not isinstance(identity, dict) or not isinstance(identity.get('name'), str):
        return None
    if len(identity['name']) > 2000:
        return None
    size, dpi = identity.get('size'), identity.get('dpi')
    if (not isinstance(size, list) or len(size) != 2
            or not all(type(n) is int and 0 < n < 100000 for n in size)
            or not isinstance(dpi, (int, float)) or isinstance(dpi, bool)
            or not math.isfinite(dpi) or not 0 < dpi < 10000):
        return None
    if (not isinstance(rect, list) or len(rect) != 4
            or not all(type(n) is int and 0 <= n < 100000 for n in rect)):
        return None
    x, y, width, height = rect
    if width < 8 or height < 8 or width*height < 180 or x+width > size[0] or y+height > size[1]:
        return None
    clean = {'name': identity['name'], 'size': list(size), 'dpi': dpi}
    for key in ('serialNumber', 'manufacturer', 'model'):
        if key in identity:
            if not isinstance(identity[key], str) or len(identity[key]) > 2000:
                return None
            clean[key] = identity[key]
    return {'version': 1, 'screen': clean, 'rect': list(rect)}


def resolve_area(value, screen):
    value = validated_area(value)
    if screen is None or value is None:
        return None
    stored, current = value['screen'], screen_identity(screen)
    if any(stored.get(key) != current.get(key) for key in current):
        return None
    local = QtCore.QRect(*value['rect'])
    global_rect = local.translated(screen.geometry().topLeft())
    return global_rect if encode_area(global_rect, screen) is not None else None


class CaptureMemoryPanel(QtWidgets.QFrame):
    # Blank toolbar space must not start an underlying screen selection.
    def mousePressEvent(self, event):
        event.accept()

    mouseMoveEvent = mousePressEvent
    mouseReleaseEvent = mousePressEvent


def show_save_warning(locale):
    """Show a quiet error after capture closes, never inside the captured image."""
    from PyQt5 import sip
    from styled_dialogs import StatusPopup, position_popup_near_cursor
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    previous = getattr(app, '_capture_memory_warning', None)
    if previous is not None and not sip.isdeleted(previous):
        previous.hide()
        previous.deleteLater()
    popup = StatusPopup()
    app._capture_memory_warning = popup
    popup.setWordWrap(True)
    popup.setMaximumWidth(340)
    popup.setText(text(locale, 'save_error'))
    popup.adjustSize()
    position_popup_near_cursor(popup)
    popup.show()
    QtCore.QTimer.singleShot(4000, popup.deleteLater)
