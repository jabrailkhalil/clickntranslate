"""Saved source/output layouts, independent of a running translation session."""

import json
import math
from pathlib import Path

from PyQt5 import QtCore


_COPY = {
    'parameters': ('Options', 'Параметры', 'Opciones', 'Optionen', 'Options', '选项', 'Opções', 'Opzioni', 'الخيارات', 'Seçenekler', 'विकल्प', 'Opsi'),
    'choose_template': ('Saved layout', 'Сохранённое расположение', 'Diseño guardado', 'Gespeicherte Anordnung', 'Disposition enregistrée', '已保存布局', 'Layout salvo', 'Disposizione salvata', 'تخطيط محفوظ', 'Kayıtlı düzen', 'सहेजा लेआउट', 'Tata letak tersimpan'),
    'new_layout': ('New layout', 'Новое расположение', 'Nuevo diseño', 'Neue Anordnung', 'Nouvelle disposition', '新布局', 'Novo layout', 'Nuova disposizione', 'تخطيط جديد', 'Yeni düzen', 'नया लेआउट', 'Tata letak baru'),
    'manual_output': ("Don't overlay on text", 'Не накладывать на текст', 'No superponer sobre el texto', 'Nicht auf den Text legen', 'Ne pas superposer sur le texte', '不覆盖在原文上', 'Não se sobreponha ao texto', 'Non sovrapporre al testo', 'عدم تغطية النص الأصلي', 'Metnin üstüne bindirme', 'टेक्स्ट को न ढकें', 'Jangan timpa teks'),
    'show_toolbar': ('Show Pause / Stop toolbar', 'Показывать панель паузы и остановки', 'Mostrar la barra Pausa / Detener', 'Pause-/Stopp-Leiste anzeigen', 'Afficher la barre Pause / Arrêter', '显示暂停／停止工具栏', 'Mostrar barra de ferramentas Pausar/Parar', 'Mostra la barra degli strumenti Pausa/Interrompi', 'إظهار شريط الإيقاف المؤقت والإيقاف', 'Duraklat / Durdur çubuğunu göster', 'रोकें / समाप्त करें पट्टी दिखाएँ', 'Tampilkan bilah Jeda / Hentikan'),
    'toolbar_hint': ('When hidden, press {hotkey} to stop translation.', 'Если панель скрыта, нажмите {hotkey}, чтобы остановить перевод.', 'Si está oculta, pulsa {hotkey} para detener la traducción.', 'Bei ausgeblendeter Leiste beendet {hotkey} die Übersetzung.', 'Si la barre est masquée, appuyez sur {hotkey} pour arrêter la traduction.', '工具栏隐藏时，按 {hotkey} 停止翻译。', 'Quando oculto, pressione {hotkey} para interromper a tradução.', 'Quando è nascosto, premi {hotkey} per interrompere la traduzione.', 'عند إخفاء الشريط، اضغط {hotkey} لإيقاف الترجمة.', 'Gizliyken çeviriyi durdurmak için {hotkey} tuşuna basın.', 'छिपा हो तो अनुवाद रोकने के लिए {hotkey} दबाएँ।', 'Saat tersembunyi, tekan {hotkey} untuk menghentikan terjemahan.'),
    'simple_ready': ('Ready — start translation', 'Готово — можно запускать перевод', 'Listo para traducir', 'Bereit zum Übersetzen', 'Prêt à traduire', '已就绪，可以开始翻译', 'Pronto – inicie a tradução', 'Pronto: avvia la traduzione', 'جاهز لبدء الترجمة', 'Hazır — çeviriyi başlat', 'तैयार — अनुवाद शुरू करें', 'Siap — mulai terjemahan'),
    'simple_selection_hint': ('Draw around the text. Translation overlays the selected text. Esc cancels.', 'Обведите текст. Перевод появится поверх исходного текста. Esc — отмена.', 'Rodea el texto. La traducción cubrirá el texto seleccionado. Esc cancela.', 'Text umrahmen. Die Übersetzung überlagert den ausgewählten Text. Esc bricht ab.', 'Encadrez le texte. La traduction recouvrira le texte sélectionné. Échap annule.', '框选原文，译文会覆盖所选原文。Esc 取消。', 'Desenhe ao redor do texto. A tradução sobrepõe o texto selecionado. Esc cancela.', 'Disegna attorno al testo. La traduzione si sovrappone al testo selezionato. Esc annulla.', 'أحط النص بمنطقة تحديد. تظهر الترجمة فوق النص المحدد. يُلغي Esc التحديد.', 'Metnin etrafını çizin. Çeviri seçilen metnin üzerine gelir. Esc iptal eder.', 'टेक्स्ट के आसपास चुनें। अनुवाद चुने टेक्स्ट को ढकेगा। Esc रद्द करता है।', 'Gambar di sekeliling teks. Terjemahan menimpa teks pilihan. Esc membatalkan.'),
    'output_choice': ('Translation area', 'Область перевода', 'Zona de traducción', 'Übersetzungsbereich', 'Zone de traduction', '译文区域', 'Área de tradução', 'Zona di traduzione', 'منطقة الترجمة', 'Çeviri alanı', 'अनुवाद क्षेत्र', 'Area terjemahan'),
    'area_number': ('Area {number}', 'Область {number}', 'Zona {number}', 'Bereich {number}', 'Zone {number}', '区域 {number}', 'Área {number}', 'Zona {number}', 'المنطقة {number}', 'Alan {number}', 'क्षेत्र {number}', 'Area {number}'),
    'move_short': ('Move', 'Переместить', 'Mover', 'Verschieben', 'Déplacer', '移动', 'Mover', 'Sposta', 'تحريك', 'Taşı', 'खिसकाएँ', 'Pindah'),
    'resize_short': ('Resize', 'Размер', 'Tamaño', 'Größe', 'Taille', '调整大小', 'Redimensionar', 'Ridimensiona', 'تغيير الحجم', 'Boyutlandır', 'आकार बदलें', 'Ubah ukuran'),
    'session_template': ('Save all areas as one layout', 'Сохранить все области одним шаблоном', 'Guardar todas las zonas como diseño', 'Alle Bereiche als Vorlage speichern', 'Enregistrer toutes les zones ensemble', '将所有区域保存为一个布局', 'Salve todas as áreas como um layout', 'Salva tutte le aree come un unico layout', 'حفظ جميع المناطق في تخطيط واحد', 'Tüm alanları tek düzen olarak kaydet', 'सभी क्षेत्र एक लेआउट में सहेजें', 'Simpan semua area sebagai satu tata letak'),
    'save_short': ('Save', 'Сохранить', 'Guardar', 'Speichern', 'Enregistrer', '保存', 'Salvar', 'Salva', 'حفظ', 'Kaydet', 'सहेजें', 'Simpan'),
    'help': ('How it works', 'Как пользоваться', 'Cómo funciona', 'So funktioniert es', 'Mode d’emploi', '使用方法', 'Como funciona', 'Come funziona', 'طريقة العمل', 'Nasıl çalışır', 'यह कैसे काम करता है', 'Cara kerja'),
    'shortcuts': ('Change shortcut', 'Изменить горячую клавишу', 'Cambiar atajo', 'Tastenkürzel ändern', 'Modifier le raccourci', '修改快捷键', 'Alterar atalho', 'Cambia scorciatoia', 'تغيير الاختصار', 'Kısayolu değiştir', 'शॉर्टकट बदलें', 'Ubah pintasan'),
    'instructions': (
        '1. Choose the languages and draw around the text.\n2. Click Start; translation overlays the selected text and updates automatically.\n3. Open Options on the session toolbar to adjust the selected output or save all areas as one template.\n\nTo place translation elsewhere, enable Don\'t overlay on text in Settings → Dynamic before drawing. A saved layout can be selected before starting.\n\nEsc cancels selection. Stop or {hotkey} ends the session.',
        '1. Выберите языки и обведите текст на экране.\n2. Нажмите «Запустить»: перевод появится поверх исходного текста и будет обновляться сам.\n3. В «Параметрах» общей панели можно настроить вывод и сохранить все области одним шаблоном.\n\nЧтобы указать другое место вывода, заранее включите «Не накладывать на текст» в настройках динамического перевода. Сохранённый шаблон выбирается перед запуском.\n\nEsc отменяет выделение. «Остановить» или {hotkey} завершает сеанс.',
        '1. Elige los idiomas y rodea el texto.\n2. Inicia: la traducción cubre el texto seleccionado y se actualiza sola.\n3. Opciones permite ajustar la salida y guardar todas las zonas como plantilla.\n\nActiva No superponer sobre el texto en Ajustes → Dinámico para colocarla en otro lugar. Puedes elegir un diseño guardado antes de iniciar.\n\nEsc cancela. Detener o {hotkey} finaliza la sesión.',
        '1. Sprachen wählen und den Text umrahmen.\n2. Start drücken: Die Übersetzung überlagert den ausgewählten Text und aktualisiert sich automatisch.\n3. Unter Optionen die Ausgabe anpassen und alle Bereiche als Vorlage speichern.\n\nFür eine andere Position vorher Nicht auf den Text legen unter Einstellungen → Dynamisch aktivieren. Gespeicherte Anordnungen vor dem Start auswählen.\n\nEsc bricht ab. Stopp oder {hotkey} beendet die Sitzung.',
        '1. Choisissez les langues et encadrez le texte.\n2. Démarrez : la traduction recouvre le texte sélectionné et se met à jour automatiquement.\n3. Options permet de régler la sortie et de sauvegarder toutes les zones ensemble.\n\nActivez Ne pas superposer sur le texte dans Réglages → Dynamique pour la placer ailleurs. Vous pouvez choisir une disposition enregistrée avant de démarrer.\n\nÉchap annule. Arrêter ou {hotkey} termine la session.',
        '1. 选择语言并框选原文。\n2. 点击开始，译文会覆盖所选原文并自动更新。\n3. 在公共工具栏的选项中调整译文区域，或将全部区域保存为一个布局。\n\n需要自定义位置时，请先在设置 → 动态翻译中勾选不覆盖在原文上。开始前可以选择已保存的布局。\n\nEsc 取消选择。停止按钮或 {hotkey} 结束会话。',
     '1. Escolha os idiomas e desenhe ao redor do texto.\n2. Clique em Iniciar; a tradução sobrepõe o texto selecionado e é atualizada automaticamente.\n3. Abra Opções na barra de ferramentas da sessão para ajustar a saída selecionada ou salvar todas as áreas como um modelo.\n\nPara colocar a tradução em outro lugar, ative Não sobrepor texto em Configurações → Dinâmico antes de desenhar. Um layout salvo pode ser selecionado antes de iniciar.\n\nEsc cancela a seleção. Parar ou {hotkey} encerra a sessão.', "1. Scegli le lingue e disegna attorno al testo.\n2. Fare clic su Avvia; la traduzione si sovrappone al testo selezionato e si aggiorna automaticamente.\n3. Aprire Opzioni sulla barra degli strumenti della sessione per regolare l'output selezionato o salvare tutte le aree come un unico modello.\n\nPer posizionare la traduzione altrove, abilita Non sovrapporre al testo in Impostazioni → Dinamico prima di disegnare. È possibile selezionare un layout salvato prima di iniziare.\n\nEsc annulla la selezione. Stop oppure {hotkey} termina la sessione.", '1. اختر اللغتين وحدد منطقة النص.\n2. اضغط «ابدأ»؛ تظهر الترجمة فوق النص المحدد وتُحدَّث تلقائيًا.\n3. افتح «الخيارات» من شريط الجلسة لضبط النتيجة المختارة أو حفظ جميع المناطق في قالب واحد.\n\nلعرض الترجمة في مكان آخر، فعّل «عدم تغطية النص الأصلي» في الإعدادات ← الترجمة المستمرة قبل التحديد. يمكنك اختيار تخطيط محفوظ قبل البدء.\n\nيلغي Esc التحديد. ينهي «إيقاف» أو {hotkey} الجلسة.', "1. Dilleri seçip metnin etrafını çizin.\n2. Başlat'a tıklayın; çeviri metnin üstünde otomatik güncellenir.\n3. Seçili çıktıyı ayarlamak veya tüm alanları şablon olarak kaydetmek için oturum çubuğundaki Seçenekler'i açın.\n\nÇeviriyi ayrı yere koymak için çizmeden önce Ayarlar → Dinamik bölümünde Metnin üstüne bindirme'yi açın. Başlamadan kayıtlı düzen seçebilirsiniz.\n\nEsc seçimi iptal eder. Durdur veya {hotkey} oturumu bitirir.", '1. भाषाएँ चुनें और टेक्स्ट के आसपास क्षेत्र बनाएँ।\n2. शुरू करें दबाएँ; अनुवाद चुने टेक्स्ट पर अपने आप अपडेट होगा।\n3. परिणाम बदलने या सभी क्षेत्र एक टेम्पलेट में सहेजने के लिए सत्र पट्टी में विकल्प खोलें।\n\nअनुवाद दूसरी जगह रखने के लिए क्षेत्र बनाने से पहले सेटिंग्स → गतिशील में टेक्स्ट को न ढकें चालू करें। शुरू करने से पहले सहेजा लेआउट चुन सकते हैं।\n\nEsc चयन रद्द करता है। रोकें या {hotkey} सत्र समाप्त करता है।', '1. Pilih bahasa dan gambar area teks.\n2. Klik Mulai; terjemahan menimpa teks dan diperbarui otomatis.\n3. Buka Opsi di bilah sesi untuk mengatur keluaran atau menyimpan semua area sebagai satu templat.\n\nUntuk menaruh terjemahan di tempat lain, aktifkan Jangan timpa teks di Pengaturan → Dinamis sebelum menggambar. Tata letak tersimpan dapat dipilih sebelum mulai.\n\nEsc membatalkan pilihan. Hentikan atau {hotkey} mengakhiri sesi.'),
    'selection_hint': ('Drag with the left mouse button · Esc cancels', 'Зажмите левую кнопку и протяните рамку · Esc — отмена', 'Arrastra con el botón izquierdo · Esc cancela', 'Mit linker Maustaste ziehen · Esc bricht ab', 'Tracez avec le bouton gauche · Échap annule', '按住左键拖动框选 · Esc 取消', 'Arraste com o botão esquerdo do mouse · Esc cancela', 'Trascinare con il tasto sinistro del mouse · Esc annulla', 'اسحب بزر الفأرة الأيسر · يلغي Esc التحديد', 'Sol fare tuşuyla sürükleyin · Esc iptal eder', 'बायाँ माउस बटन दबाकर खींचें · Esc रद्द करता है', 'Seret dengan tombol kiri tetikus · Esc membatalkan'),
    'source': ('1 · Select text to read', '1 · Выделите исходный текст', '1 · Selecciona el texto original', '1 · Quelltext auswählen', '1 · Sélectionnez le texte source', '1 · 选择原文区域', '1 · Selecione o texto para ler', '1 · Selezionare il testo da leggere', '1 · حدد النص المطلوب قراءته', '1 · Okunacak metni seçin', '1 · पढ़ने का टेक्स्ट चुनें', '1 · Pilih teks untuk dibaca'),
    'output': ('2 · Select where to show translation', '2 · Выделите место для перевода', '2 · Selecciona dónde mostrar la traducción', '2 · Bereich für die Übersetzung wählen', '2 · Choisissez où afficher la traduction', '2 · 选择译文显示区域', '2 · Selecione onde mostrar a tradução', '2 · Seleziona dove mostrare la traduzione', '2 · حدد مكان عرض الترجمة', '2 · Çevirinin yerini seçin', '2 · अनुवाद दिखाने की जगह चुनें', '2 · Pilih lokasi terjemahan'),
    'ready': ('Add another pair or press Start', 'Можно добавить пару или нажать «Запустить»', 'Añade otra pareja o pulsa Iniciar', 'Weiteres Paar wählen oder Start drücken', 'Ajoutez une paire ou démarrez', '添加另一组区域或点击开始', 'Adicione outro par ou pressione Iniciar', "Aggiungi un'altra coppia o premi Avvia", 'أضف اتجاهًا آخر أو اضغط «ابدأ»', "Başka çift ekleyin veya Başlat'a basın", 'दूसरी जोड़ी जोड़ें या शुरू करें दबाएँ', 'Tambahkan pasangan lain atau tekan Mulai'),
    'read': ('Read', 'Читать', 'Leer', 'Lesen', 'Lire', '原文', 'Leia', 'Leggi', 'قراءة', 'Oku', 'पढ़ें', 'Baca'),
    'write': ('Translation', 'Перевод', 'Traducción', 'Übersetzung', 'Traduction', '译文', 'Tradução', 'Traduzione', 'الترجمة', 'Çeviri', 'अनुवाद', 'Terjemahan'),
    'templates': ('Template name', 'Имя шаблона', 'Nombre de plantilla', 'Vorlagenname', 'Nom du modèle', '模板名称', 'Nome do modelo', 'Nome del modello', 'اسم القالب', 'Şablon adı', 'टेम्पलेट का नाम', 'Nama templat'),
    'save': ('Save template', 'Сохранить шаблон', 'Guardar plantilla', 'Vorlage speichern', 'Enregistrer le modèle', '保存模板', 'Salvar modelo', 'Salva modello', 'حفظ القالب', 'Şablonu kaydet', 'टेम्पलेट सहेजें', 'Simpan templat'),
    'delete': ('Delete template', 'Удалить шаблон', 'Eliminar plantilla', 'Vorlage löschen', 'Supprimer le modèle', '删除模板', 'Excluir modelo', 'Elimina modello', 'حذف القالب', 'Şablonu sil', 'टेम्पलेट हटाएँ', 'Hapus templat'),
    'saved': ('Saved', 'Сохранено', 'Guardado', 'Gespeichert', 'Enregistré', '已保存', 'Salvo', 'Salvato', 'تم الحفظ', 'Kaydedildi', 'सहेजा गया', 'Disimpan'),
    'name_required': ('Enter a template name', 'Введите имя шаблона', 'Escribe un nombre', 'Vorlagennamen eingeben', 'Saisissez un nom', '请输入模板名称', 'Insira um nome de modelo', 'Inserisci un nome per il modello', 'أدخل اسمًا للقالب', 'Şablon adı girin', 'टेम्पलेट का नाम लिखें', 'Masukkan nama templat'),
    'settings': ('Window settings', 'Настройки окна', 'Ajustes de ventana', 'Fenstereinstellungen', 'Réglages de fenêtre', '窗口设置', 'Configurações da janela', 'Impostazioni della finestra', 'إعدادات النافذة', 'Pencere ayarları', 'विंडो सेटिंग्स', 'Pengaturan jendela'),
    'font': ('Text size', 'Размер текста', 'Tamaño de texto', 'Schriftgröße', 'Taille du texte', '文字大小', 'Tamanho do texto', 'Dimensione del testo', 'حجم النص', 'Metin boyutu', 'टेक्स्ट का आकार', 'Ukuran teks'),
    'opacity': ('Background opacity', 'Непрозрачность фона', 'Opacidad del fondo', 'Hintergrunddeckkraft', 'Opacité du fond', '背景不透明度', 'Opacidade de fundo', 'Opacità dello sfondo', 'عتامة الخلفية', 'Arka plan opaklığı', 'पृष्ठभूमि की अपारदर्शिता', 'Opasitas latar'),
    'locked': ('Lock position', 'Закрепить', 'Fijar posición', 'Position sperren', 'Verrouiller', '固定位置', 'Fixar posição', 'Blocca posizione', 'قفل الموضع', 'Konumu kilitle', 'जगह लॉक करें', 'Kunci posisi'),
    'move': ('Drag to move the output', 'Перетащите, чтобы переместить вывод', 'Arrastra para mover la salida', 'Ziehen zum Verschieben', 'Glissez pour déplacer la sortie', '拖动以移动译文区域', 'Arraste para mover a saída', "Trascina per spostare l'output", 'اسحب لتحريك منطقة النتيجة', 'Çıktıyı taşımak için sürükleyin', 'परिणाम खिसकाने के लिए खींचें', 'Seret untuk memindahkan keluaran'),
    'resize': ('Drag to resize the output', 'Перетащите, чтобы изменить размер', 'Arrastra para cambiar el tamaño', 'Ziehen zum Ändern der Größe', 'Glissez pour redimensionner', '拖动以调整大小', 'Arraste para redimensionar a saída', "Trascina per ridimensionare l'output", 'اسحب لتغيير حجم منطقة النتيجة', 'Çıktıyı boyutlandırmak için sürükleyin', 'परिणाम का आकार बदलने के लिए खींचें', 'Seret untuk mengubah ukuran keluaran'),
    'unavailable': ('Template languages are unavailable', 'Языки шаблона недоступны', 'Idiomas de plantilla no disponibles', 'Vorlagensprachen nicht verfügbar', 'Langues du modèle indisponibles', '模板语言不可用', 'Idiomas de modelo não estão disponíveis', 'Le lingue dei modelli non sono disponibili', 'لغات القالب غير متاحة', 'Şablon dilleri kullanılamıyor', 'टेम्पलेट की भाषाएँ उपलब्ध नहीं हैं', 'Bahasa templat tidak tersedia'),
    'save_error': ('Template could not be saved', 'Не удалось сохранить шаблон', 'No se pudo guardar', 'Speichern fehlgeschlagen', 'Enregistrement impossible', '无法保存模板', 'Não foi possível salvar o modelo', 'Impossibile salvare il modello', 'تعذّر حفظ القالب', 'Şablon kaydedilemedi', 'टेम्पलेट सहेज नहीं सके', 'Templat tidak dapat disimpan'),
}


def text(language, key):
    languages = ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id')
    return _COPY[key][languages.index(language) if language in languages else 0]


def output_style(value=None, *, opacity=88):
    value = value if isinstance(value, dict) else {}
    def number(key, default, low, high):
        try:
            return max(low, min(high, int(value.get(key, default))))
        except (ValueError, TypeError, OverflowError):
            return default
    return {'font_size': number('font_size', 18, 10, 48),
            'opacity': number('opacity', opacity, 0, 100),
            'locked': value.get('locked', True) is not False}


def encode_rect(rect, screens):
    screen = next((screen for screen in screens if screen.geometry().contains(rect.center())), screens[0])
    bounds = screen.geometry()
    rect = rect.intersected(bounds)
    if rect.isEmpty():
        raise ValueError('Region is outside its screen')
    return {'screen': screen.name(), 'rect': [(rect.x()-bounds.x())/bounds.width(),
            (rect.y()-bounds.y())/bounds.height(), rect.width()/bounds.width(), rect.height()/bounds.height()]}


def decode_rect(value, screens):
    screen = next((screen for screen in screens if screen.name() == value['screen']), screens[0])
    bounds = screen.geometry()
    x, y, width, height = value['rect']
    width, height = min(bounds.width(), max(60, round(width*bounds.width()))), min(bounds.height(), max(24, round(height*bounds.height())))
    x = min(max(0, round(x*bounds.width())), bounds.width()-width)
    y = min(max(0, round(y*bounds.height())), bounds.height()-height)
    return QtCore.QRect(bounds.x()+x, bounds.y()+y, width, height)


def validate_template(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid template')
    name = str(value.get('name', '')).strip()[:80]
    source, target = value.get('source_language'), value.get('target_language')
    pairs = value.get('pairs')
    if not name or not all(isinstance(code, str) and 1 <= len(code) <= 20 for code in (source, target)):
        raise ValueError('Invalid template name or languages')
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 16:
        raise ValueError('Invalid template regions')
    clean = []
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError('Invalid template pair')
        item = {}
        for key in ('source', 'output'):
            area = pair.get(key, {})
            if not isinstance(area, dict):
                raise ValueError('Invalid template region')
            rect = area.get('rect')
            if (not isinstance(rect, list) or len(rect) != 4
                    or not all(isinstance(n, (int, float)) and not isinstance(n, bool) and 0 <= n <= 1 and math.isfinite(n) for n in rect)
                    or rect[2] <= 0 or rect[3] <= 0 or rect[0]+rect[2] > 1.000001 or rect[1]+rect[3] > 1.000001):
                raise ValueError('Invalid template coordinates')
            item[key] = {'screen': str(area.get('screen', ''))[:200], 'rect': list(rect)}
        item['style'] = output_style(pair.get('style'))
        clean.append(item)
    return {'name': name, 'source_language': source, 'target_language': target, 'pairs': clean}


class TemplateStore:
    def __init__(self, path=None):
        if path is None:
            from ocr import get_data_file
            path = get_data_file('dynamic_templates.json')
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('templates'), list):
            raise ValueError('Unsupported templates file')
        return [validate_template(value) for value in data['templates'][:100]]

    def _write(self, values):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        output = QtCore.QSaveFile(str(self.path))
        if not output.open(QtCore.QIODevice.WriteOnly):
            raise OSError(output.errorString())
        data = json.dumps({'version': 1, 'templates': values}, ensure_ascii=False, indent=2).encode('utf-8')
        if output.write(data) != len(data) or not output.commit():
            raise OSError(output.errorString())

    def save(self, value):
        value = validate_template(value)
        values = [item for item in self.load() if item['name'].casefold() != value['name'].casefold()]
        if len(values) >= 100:
            raise ValueError('Too many templates')
        self._write(values + [value])
        return value

    def delete(self, name):
        self._write([item for item in self.load() if item['name'] != name])
