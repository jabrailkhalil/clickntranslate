"""Optional last-area geometry, independent of OCR languages and UI scale."""
from PyQt5 import QtCore, QtWidgets

LANGUAGES = ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id')
TEXT = {
    'capture_error': ('The selected area cannot be captured', 'Не удалось захватить выбранную область', 'No se puede capturar el área seleccionada', 'Der ausgewählte Bereich kann nicht erfasst werden', 'Impossible de capturer la zone sélectionnée', '无法捕获所选区域', 'A área selecionada não pode ser capturada', "L’area selezionata non può essere catturata", 'تعذر التقاط المنطقة المحددة', 'Seçili alan yakalanamıyor', 'चुना क्षेत्र कैप्चर नहीं हो सकता', 'Area pilihan tidak dapat ditangkap'),
    'remember': ('Remember area', 'Запоминать область', 'Recordar zona', 'Bereich merken', 'Mémoriser la zone', '记住区域', 'Lembrar área', 'Ricorda area', 'تذكر المنطقة', 'Alanı hatırla', 'क्षेत्र याद रखें', 'Ingat area'),
    'translation_setting': ('Remember translation area', 'Запоминать область перевода', 'Recordar la zona de traducción', 'Übersetzungsbereich merken', 'Mémoriser la zone de traduction', '记住翻译区域', 'Lembrar área de tradução', 'Ricorda l’area di traduzione', 'تذكر منطقة الترجمة', 'Çeviri alanını hatırla', 'अनुवाद क्षेत्र याद रखें', 'Ingat area terjemahan'),
    'translation_setting_hint': (
        'Shows the previous frame the next time you translate a screen area. Enter or Repeat captures fresh text. The checkbox in the capture panel changes this same setting. Turning it off clears the saved area. Recognition without translation is configured separately.',
        'При следующем вызове перевода области покажет последнюю рамку. Enter или «Повторить» захватывает новый текст. Галочка в панели захвата меняет эту же настройку. При отключении сохранённая область удаляется. Распознавание без перевода настраивается отдельно.',
        'Muestra el marco anterior al volver a traducir una zona de pantalla. Intro o Repetir captura texto nuevo. La casilla del panel de captura cambia este mismo ajuste. Al desactivarla se borra la zona guardada. El reconocimiento sin traducción se configura por separado.',
        'Zeigt beim nächsten Übersetzen eines Bildschirmbereichs den bisherigen Rahmen. Eingabe oder Wiederholen erfasst neuen Text. Das Häkchen im Aufnahmebereich ändert dieselbe Einstellung. Beim Ausschalten wird der gespeicherte Bereich gelöscht. Erkennung ohne Übersetzung wird getrennt eingestellt.',
        'Affiche le dernier cadre lors de la prochaine traduction d’une zone de l’écran. Entrée ou Répéter capture le nouveau texte. La case du panneau de capture modifie ce même réglage. La désactiver efface la zone mémorisée. La reconnaissance sans traduction se règle séparément.',
        '下次翻译屏幕区域时显示上次的选框。按 Enter 或点击“重复”捕获新文字。捕获面板中的复选框控制同一设置。关闭后会清除保存的区域。不含翻译的文字识别需单独设置。',
        'Mostra a última moldura ao traduzir uma área da tela novamente. Enter ou Repetir captura texto novo. A caixa no painel de captura altera esta mesma configuração. Desativá-la apaga a área salva. O reconhecimento sem tradução é configurado separadamente.',
        'Mostra l’ultimo riquadro alla successiva traduzione di un’area dello schermo. Invio o Ripeti acquisisce nuovo testo. La casella nel pannello di acquisizione modifica questa stessa impostazione. Disattivarla elimina l’area salvata. Il riconoscimento senza traduzione si configura separatamente.',
        'يعرض آخر إطار عند ترجمة منطقة من الشاشة مجددًا. يلتقط Enter أو تكرار نصًا جديدًا. يغيّر مربع الاختيار في لوحة الالتقاط الإعداد نفسه. يؤدي إلغاء التحديد إلى مسح المنطقة المحفوظة. يُضبط التعرف على النص دون ترجمة بشكل منفصل.',
        'Ekran alanını yeniden çevirirken önceki çerçeveyi gösterir. Enter veya Tekrarla yeni metni yakalar. Yakalama panelindeki onay kutusu aynı ayarı değiştirir. Kapatılması kayıtlı alanı siler. Çevirisiz metin tanıma ayrı ayarlanır.',
        'अगली बार स्क्रीन क्षेत्र का अनुवाद करते समय पिछला फ़्रेम दिखाता है। Enter या दोहराएँ नया टेक्स्ट लेता है। कैप्चर पैनल की टिक इसी सेटिंग को बदलती है। बंद करने पर सहेजा क्षेत्र मिट जाता है। बिना अनुवाद के टेक्स्ट की पहचान अलग से सेट होती है।',
        'Tampilkan bingkai terakhir saat menerjemahkan area layar lagi. Enter atau Ulangi menangkap teks baru. Kotak centang di panel tangkapan mengubah pengaturan yang sama. Menonaktifkannya menghapus area tersimpan. Pengenalan tanpa terjemahan diatur terpisah.'),
    'repeat': ('Repeat', 'Повторить', 'Repetir', 'Wiederholen', 'Répéter', '重复', 'Repetir', 'Ripeti', 'تكرار', 'Tekrarla', 'दोहराएँ', 'Ulangi'),
    'hint': ('Show the previous area next time in this mode. Click Repeat or press Enter to capture fresh text, or draw a new area.', 'При следующем запуске этого режима покажет прежнюю рамку. Кнопка «Повторить» или Enter захватит новый текст; мышью можно выделить другую область.', 'Muestra la zona anterior al volver a este modo. Pulsa Repetir o Enter para capturar texto nuevo, o dibuja otra zona.', 'Zeigt beim nächsten Aufruf dieses Modus den bisherigen Bereich. Wiederholen oder Enter erfasst neuen Text; mit der Maus einen anderen Bereich wählen.', 'Affiche la zone précédente au prochain lancement de ce mode. Répéter ou Entrée capture le nouveau texte ; vous pouvez aussi tracer une autre zone.', '下次启动此模式时显示上次区域。点击“重复”或按 Enter 捕获新文字，也可以重新选择区域。', 'Mostra a área anterior ao abrir este modo novamente. Clique em Repetir ou pressione Enter para capturar texto novo, ou selecione outra área.', 'Mostra l’area precedente al prossimo avvio di questa modalità. Premi Ripeti o Invio per acquisire nuovo testo, oppure seleziona un’altra area.', 'يعرض المنطقة السابقة عند تشغيل هذا الوضع مجددًا. انقر على تكرار أو اضغط Enter لالتقاط نص جديد، أو حدد منطقة أخرى.', 'Bu mod tekrar açıldığında önceki alanı gösterir. Yeni metni almak için Tekrarla veya Enter kullanın ya da yeni bir alan çizin.', 'अगली बार इस मोड में पिछला क्षेत्र दिखाएगा। नया टेक्स्ट लेने के लिए दोहराएँ या Enter दबाएँ, या दूसरा क्षेत्र चुनें।', 'Tampilkan area sebelumnya saat mode ini dibuka lagi. Klik Ulangi atau tekan Enter untuk mengambil teks baru, atau pilih area lain.'),
    'ready': ('Previous area · Enter or Repeat · Draw a new area to replace it', 'Прежняя область · Enter или «Повторить» · Мышью — новая область', 'Zona anterior · Enter o Repetir · Dibuja otra para cambiarla', 'Bisheriger Bereich · Enter oder Wiederholen · Mit der Maus neu wählen', 'Zone précédente · Entrée ou Répéter · Tracez une autre zone pour la remplacer', '上次区域 · Enter 或“重复” · 重新框选可替换区域', 'Área anterior · Enter ou Repetir · Selecione outra para substituí-la', 'Area precedente · Invio o Ripeti · Seleziona una nuova area per sostituirla', 'المنطقة السابقة · Enter أو تكرار · حدد منطقة جديدة لاستبدالها', 'Önceki alan · Enter veya Tekrarla · Değiştirmek için yeni alan çizin', 'पिछला क्षेत्र · Enter या दोहराएँ · बदलने के लिए नया क्षेत्र चुनें', 'Area sebelumnya · Enter atau Ulangi · Pilih area baru untuk menggantinya'),
    'unavailable': ('The saved area is unavailable on this screen. Select a new area.', 'Сохранённая область недоступна на этом экране. Выделите новую.', 'La zona guardada no está disponible en esta pantalla. Selecciona otra.', 'Der gespeicherte Bereich ist auf diesem Bildschirm nicht verfügbar. Bitte neu auswählen.', 'La zone mémorisée est indisponible sur cet écran. Sélectionnez une autre zone.', '此屏幕上无法恢复保存的区域，请重新选择。', 'A área salva não está disponível nesta tela. Selecione outra.', 'L’area salvata non è disponibile su questo schermo. Selezionane un’altra.', 'المنطقة المحفوظة غير متاحة على هذه الشاشة. حدد منطقة جديدة.', 'Kayıtlı alan bu ekranda kullanılamıyor. Yeni bir alan seçin.', 'सहेजा क्षेत्र इस स्क्रीन पर उपलब्ध नहीं है। नया क्षेत्र चुनें।', 'Area tersimpan tidak tersedia di layar ini. Pilih area baru.'),
    'save_error': ('Could not save the area preference.', 'Не удалось сохранить настройку области.', 'No se pudo guardar la preferencia de zona.', 'Die Bereichseinstellung konnte nicht gespeichert werden.', 'Impossible d’enregistrer le réglage de la zone.', '无法保存区域设置。', 'Não foi possível salvar a preferência da área.', 'Impossibile salvare l’impostazione dell’area.', 'تعذر حفظ إعداد المنطقة.', 'Alan tercihi kaydedilemedi.', 'क्षेत्र की सेटिंग सहेज नहीं सके।', 'Preferensi area tidak dapat disimpan.'),
    'dynamic_remember': ('Remember selected template', 'Запоминать выбранный шаблон', 'Recordar plantilla elegida', 'Gewählte Vorlage merken', 'Mémoriser le modèle choisi', '记住选中的模板', 'Lembrar modelo selecionado', 'Ricorda il modello selezionato', 'تذكر القالب المحدد', 'Seçili şablonu hatırla', 'चुना टेम्पलेट याद रखें', 'Ingat templat terpilih'),
    'template_label': ('Template:', 'Шаблон:', 'Plantilla:', 'Vorlage:', 'Modèle :', '模板：', 'Modelo:', 'Modello:', 'القالب:', 'Şablon:', 'टेम्पलेट:', 'Templat:'),
    'dynamic_hint': ('Reopen the selected template for review before starting. Choosing a template loads its languages; changing languages afterwards keeps its areas. Use Create template to save new areas.', 'Перед запуском откроет выбранный шаблон для проверки. Выбор шаблона подставляет его языки; их последующее изменение сохраняет области. Новые области можно сохранить через «Создать шаблон».', 'Abre la plantilla elegida para revisarla antes de empezar. Elegirla carga sus idiomas; cambiarlos después conserva las zonas. Usa Crear plantilla para guardar zonas nuevas.', 'Öffnet die gewählte Vorlage vor dem Start zur Prüfung. Die Auswahl lädt ihre Sprachen; spätere Sprachänderungen behalten die Bereiche. Neue Bereiche über Vorlage erstellen speichern.', 'Rouvre le modèle choisi pour vérification avant de démarrer. Sa sélection charge ses langues ; les modifier ensuite conserve les zones. Utilisez Créer un modèle pour enregistrer de nouvelles zones.', '开始前会打开所选模板供检查。选择模板会载入其语言，之后更改语言仍会保留区域。使用“创建模板”保存新区域。', 'Reabre o modelo selecionado para conferir antes de iniciar. Selecioná-lo carrega seus idiomas; alterá-los depois mantém as áreas. Use Criar modelo para salvar novas áreas.', 'Riapre il modello scelto per controllarlo prima di avviare. Sceglierlo carica le sue lingue; cambiarle dopo mantiene le aree. Usa Crea modello per salvare nuove aree.', 'يفتح القالب المحدد للمراجعة قبل البدء. يحمّل اختيار القالب لغاته؛ ويُبقي تغيير اللغات لاحقًا على مناطقه. استخدم «إنشاء قالب» لحفظ مناطق جديدة.', 'Seçili şablonu başlamadan önce gözden geçirmek için açar. Şablon seçimi dillerini yükler; daha sonra dilleri değiştirmek alanları korur. Yeni alanlar için Şablon oluştur seçeneğini kullanın.', 'शुरू करने से पहले चुना टेम्पलेट जाँचने के लिए खोलता है। टेम्पलेट चुनने पर उसकी भाषाएँ लोड होती हैं; बाद में भाषाएँ बदलने पर क्षेत्र बने रहते हैं। नए क्षेत्र सहेजने के लिए टेम्पलेट बनाएँ चुनें।', 'Buka templat terpilih untuk diperiksa sebelum memulai. Memilih templat memuat bahasanya; mengganti bahasa setelahnya tetap mempertahankan area. Gunakan Buat templat untuk menyimpan area baru.'),
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
