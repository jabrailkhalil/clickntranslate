"""Settings guide copy and routes follow the visible settings categories."""
COPY = {
 'ru': (
    'Настройки перевода и результата',
    'Основные настройки: запуск, история, подсказки, проверка обновлений, показ окна, масштаб и размер текста результата с примером.',
    'Перевод и OCR: движки, захват, копирование и замена текста. «Объединять строки в абзацы» убирает переносы внутри связного текста перед переводом.',
    'Языковые пакеты → API',
    'Во вкладке API окна «Языковые пакеты» выберите сервис, введите ключ и ID модели. «Сохранить и выбрать» подключает его к переводу; режим распознавания также выбирает этот сервис для OCR. API необязателен.',
    'Текст результата',
    'В основных настройках стрелки «Текст результата» меняют шрифт перевода. Пример ниже обновляется сразу. «Масштаб» отдельно меняет весь интерфейс.',
    'Закрытие результата',
    '«Закрывать результат кликом снаружи» находится в «Перевод и OCR». Включите, если хотите убирать окно перевода при переходе в другое приложение. По умолчанию выключено.',
    'Запуск перевода выделения',
    'Главное окно → режим «Выделение» → настройки языков, либо «Настроить горячие клавиши» → «Режим выделения». В поле «После выделения» выберите горячую клавишу, кнопку рядом с текстом или немедленный перевод. Это способы запуска одного режима, с теми же языками и переводчиком.',
    'Один запрос распознаёт и переводит изображение выбранной моделью. Для обычного текста используется тот же сервис, если нажать «Сохранить и выбрать». Ключи остаются в системном хранилище и не попадают в экспорт. Облачный сервис может брать плату за запросы.',
 ),
 'en': (
    'Translation and result settings',
    'General: startup, history, tooltips, update checks, result window, interface scale and result text size with a preview.',
    'Translation and OCR: engines, capture, copying and replacing text. Join OCR lines into paragraphs removes visual line wraps from connected text before translating.',
    'Language packages → API',
    'In the API tab of Language packages, choose a service and enter its key and model ID. Save and select uses it for translation; a recognition mode also selects it for OCR. API services are optional.',
    'Result text',
    'In General, Result text arrows change the translation font and the preview updates immediately. Scale changes the entire interface separately.',
    'Closing results',
    'Close result on outside click is in Translation and OCR. Enable it to dismiss the translation window when using another app. Off by default.',
    'Starting selection translation',
    'Main window → Selection → language settings, or Configure hotkeys → Selection mode. After selecting chooses a hotkey, a button beside the text, or immediate translation. These are triggers for the same mode, languages and translator.',
    'One request recognizes and translates an image using the chosen model. Save and select also uses this service for plain text. Keys stay in the system vault and are not exported. The cloud service may charge for requests.',
 ),
 'es': (
    'Ajustes de traducción y resultado',
    'General: inicio, historiales, ayudas, actualizaciones, ventana de resultado, escala y tamaño del texto con vista previa.',
    'Traducción y OCR: motores, captura, copia y reemplazo. Unir líneas OCR en párrafos elimina los saltos de línea dentro de un texto continuo antes de traducir.',
    'Paquetes de idioma → API',
    'En la pestaña API de Paquetes de idioma, elige un servicio, su clave y el ID del modelo. Guardar y elegir lo usa para traducir; un modo de reconocimiento también lo selecciona para OCR. La API es opcional.',
    'Texto del resultado',
    'En General, las flechas del tamaño del resultado cambian la fuente y actualizan la vista previa. La escala cambia toda la interfaz por separado.',
    'Cerrar resultados',
    'Cerrar resultado al pulsar fuera está en Traducción y OCR. Oculta el resultado al usar otra app. Desactivado de forma predeterminada.',
    'Iniciar la traducción de selección',
    'Ventana principal → Selección → idiomas, o Configurar atajos → Modo Selección. Tras seleccionar permite usar el atajo, mostrar un botón junto al texto o traducir al instante. Usan el mismo modo, idiomas y traductor.',
    'Una petición reconoce y traduce una imagen con el modelo elegido. Guardar y elegir usa el mismo servicio para texto. Las claves quedan en la bóveda del sistema y no se exportan. El servicio puede cobrar por las peticiones.',
 ),
 'de': (
    'Übersetzung und Ergebnis einstellen',
    'Allgemein: Start, Verlauf, Hinweise, Updates, Ergebnisfenster, Skalierung und Textgröße mit Vorschau.',
    'Übersetzung und OCR: Dienste, Aufnahme, Kopieren und Ersetzen. OCR-Zeilen zu Absätzen verbinden entfernt visuelle Zeilenumbrüche vor der Übersetzung.',
    'Sprachpakete → API',
    'Im API-Tab der Sprachpakete Dienst, Schlüssel und Modell-ID eingeben. Speichern und wählen verwendet den Dienst zur Übersetzung; ein Erkennungsmodus wählt ihn auch für OCR. API-Dienste sind optional.',
    'Ergebnistext',
    'Unter Allgemein ändern die Pfeile beim Ergebnistext die Übersetzungsschrift mit direkter Vorschau. Skalierung ändert separat die gesamte Oberfläche.',
    'Ergebnisse schließen',
    'Ergebnis bei Außenklick schließen befindet sich unter Übersetzung und OCR. Schließt das Ergebnis beim Wechsel zu einer anderen App. Standardmäßig aus.',
    'Auswahlübersetzung starten',
    'Hauptfenster → Auswahl → Spracheinstellungen oder Tastenkürzel → Auswahlmodus. Nach der Auswahl: Tastenkürzel, Schaltfläche neben dem Text oder sofort übersetzen. Derselbe Modus, dieselben Sprachen und derselbe Übersetzer.',
    'Eine Anfrage erkennt und übersetzt ein Bild mit dem gewählten Modell. Speichern und wählen nutzt den Dienst auch für Text. Schlüssel bleiben im Systemtresor und werden nicht exportiert. Der Dienst kann Anfragen berechnen.',
 ),
 'fr': (
    'Réglages de traduction et de résultat',
    'Général : démarrage, historiques, aides, mises à jour, fenêtre de résultat, échelle et taille du texte avec aperçu.',
    'Traduction et OCR : moteurs, capture, copie et remplacement. Réunir les lignes OCR en paragraphes supprime les retours à la ligne visuels avant la traduction.',
    'Modules de langue → API',
    'Dans l’onglet API des modules de langue, choisissez un service, sa clé et son identifiant de modèle. Enregistrer et choisir l’utilise pour traduire ; un mode de reconnaissance le choisit aussi pour l’OCR. L’API est facultative.',
    'Texte du résultat',
    'Dans Général, les flèches du texte du résultat changent la police avec aperçu immédiat. L’échelle modifie toute l’interface séparément.',
    'Fermer les résultats',
    'Fermer le résultat au clic extérieur se trouve dans Traduction et OCR. Ferme le résultat lorsque vous utilisez une autre app. Désactivé par défaut.',
    'Démarrer la traduction de sélection',
    'Fenêtre principale → Sélection → langues, ou Configurer les raccourcis → Mode Sélection. Après sélection : raccourci, bouton près du texte ou traduction immédiate. Même mode, mêmes langues et même traducteur.',
    'Une requête reconnaît et traduit une image avec le modèle choisi. Enregistrer et choisir utilise aussi ce service pour le texte. Les clés restent dans le coffre système et ne sont pas exportées. Le service peut facturer les requêtes.',
 ),
 'zh': (
    '翻译与结果设置',
    '常规设置：启动、历史、提示、更新、结果窗口、界面缩放和带预览的结果文字大小。',
    '翻译与 OCR：引擎、捕获、复制和替换文字。“将 OCR 行合并为段落”可在翻译前去除段落内的视觉换行。',
    '语言包 → API',
    '在语言包窗口的 API 标签页中选择服务，输入密钥和模型 ID。“保存并选用”将其用于翻译；识别模式也将其用于 OCR。API 为可选功能。',
    '结果文字',
    '常规设置中的结果文字箭头调整译文字体，预览立即更新。缩放单独调整整个界面。',
    '关闭结果',
    '在翻译与 OCR 中启用“点击外部关闭结果”，切换到其他应用时关闭翻译窗口。默认关闭。',
    '启动选中文字翻译',
    '主窗口 → 选中文字 → 语言设置，或设置快捷键 → 选中文字模式。选择文字后可使用快捷键、显示文字旁的按钮或立即翻译。它们使用相同模式、语言和翻译服务。',
    '一次请求使用所选模型识别并翻译图像。“保存并选用”也将此服务用于普通文字。密钥保留在系统密钥库中，不会导出。云服务可能收费。',
 ),

    'pt': ('Configurações de tradução e resultados',
     'Geral: inicialização, histórico, dicas de ferramentas, verificações de atualização, janela de '
     'resultados, escala de interface e tamanho do texto do resultado com visualização.',
     'Tradução e OCR: motores, captura, cópia e substituição. Unir linhas OCR em parágrafos remove '
     'as quebras visuais dentro do texto antes de traduzir.',
     'Pacotes de idiomas → API',
     'Na aba API de Pacotes de idiomas, escolha um serviço e informe a chave e o ID do modelo. Salvar '
     'e selecionar ativa o serviço para tradução; os modos de reconhecimento também o ativam para OCR. '
     'O uso de API é opcional.',
     'Texto do resultado',
     'Em Configurações gerais, as setas de Texto do resultado alteram o tamanho da tradução e '
     'atualizam o exemplo imediatamente. Escala ajusta toda a interface separadamente.',
     'Fechamento do resultado',
     'Fechar resultado ao clicar fora fica em Tradução e OCR. Ative para fechar a janela de tradução '
     'ao clicar em outro aplicativo. Vem desativado.',
     'Iniciando tradução de seleção',
     'Janela principal → Seleção → idiomas, ou Configurar atalhos → Modo de seleção. Em Após '
     'selecionar, escolha o atalho, um botão ao lado do texto ou tradução imediata. As três opções '
     'usam o mesmo modo, par de idiomas e tradutor.',
     'Uma solicitação reconhece e traduz uma imagem usando o modelo escolhido. Salvar e selecionar '
     'também usa este serviço para texto simples. As chaves permanecem no cofre do sistema e não são '
     'exportadas. O serviço de nuvem pode cobrar pelas solicitações.'),
    'it': ('Impostazioni di traduzione e risultati',
     'Generale: avvio, cronologia, descrizioni comandi, controlli degli aggiornamenti, finestra dei '
     "risultati, scala dell'interfaccia e dimensione del testo dei risultati con un'anteprima.",
     'Traduzione e OCR: motori, acquisizione, copia e sostituzione. Unisci le righe OCR in paragrafi '
     'rimuove gli a capo visivi nel testo prima della traduzione.',
     'Pacchetti lingua → API',
     'Nella scheda API di Pacchetti lingua, scegli un servizio e inserisci la chiave e l’ID del '
     'modello. Salva e seleziona lo attiva per la traduzione; le modalità di riconoscimento lo '
     'attivano anche per l’OCR. L’API è facoltativa.',
     'Testo del risultato',
     'In Impostazioni generali, le frecce di Testo del risultato cambiano la dimensione della '
     'traduzione e aggiornano subito l’esempio. Scala regola separatamente l’intera interfaccia.',
     'Chiusura del risultato',
     'Chiudi risultato con clic esterno si trova in Traduzione e OCR. Attivalo per chiudere la '
     'finestra della traduzione quando fai clic in un’altra app. È disattivato per impostazione '
     'predefinita.',
     'Avvio della traduzione della selezione',
     'Finestra principale → Selezione → lingue, oppure Configura scorciatoie → Modalità di selezione. '
     'In Dopo la selezione, scegli la scorciatoia, un pulsante accanto al testo o la traduzione '
     'immediata. Le tre opzioni usano la stessa modalità, coppia di lingue e servizio.',
     "Una richiesta riconosce e traduce un'immagine utilizzando il modello scelto. Salva e seleziona "
     'utilizza questo servizio anche per il testo semplice. Le chiavi rimangono nel vault di sistema e '
     'non vengono esportate. Il servizio cloud potrebbe addebitare costi per le richieste.'),

 'ar': ('إعدادات الترجمة والنتيجة',
  'الإعدادات العامة: بدء التشغيل والسجل والتلميحات والتحقق من التحديثات ونافذة النتيجة وحجم الواجهة '
  'وحجم نص الترجمة مع معاينة.',
  'الترجمة والتعرف على النص: المحركات والالتقاط ونسخ النص واستبداله. يزيل دمج أسطر OCR في فقرات '
  'التفاف الأسطر المرئي في النص المتصل قبل ترجمته.',
  'حزم اللغات ← API',
  'في علامة API ضمن حزم اللغات، اختر خدمة وأدخل مفتاحها ومعرّف النموذج. يختار «حفظ واختيار» الخدمة '
  'للترجمة؛ ويختارها وضع التعرف أيضًا لمحرك OCR. خدمات API اختيارية.',
  'نص النتيجة',
  'في الإعدادات العامة، تغيّر أسهم نص النتيجة حجم خط الترجمة وتحدّث المعاينة فورًا. يغيّر مقياس '
  'الواجهة حجم الواجهة كلها بشكل مستقل.',
  'إغلاق النتائج',
  'خيار إغلاق النتيجة بالنقر خارجها موجود في الترجمة والتعرف على النص. فعّله لإغلاق نافذة الترجمة '
  'عند استخدام تطبيق آخر. معطّل افتراضيًا.',
  'بدء ترجمة النص المحدد',
  'النافذة الرئيسية ← التحديد ← إعدادات اللغات، أو ضبط الاختصارات ← وضع التحديد. يختار إعداد «بعد '
  'التحديد» الاختصار أو زرًا بجوار النص أو الترجمة الفورية. هذه طرق تشغيل للوضع نفسه وبنفس اللغات '
  'والمترجم.',
  'يتعرف طلب واحد على نص الصورة ويترجمه باستخدام النموذج المختار. يستخدم «حفظ واختيار» الخدمة نفسها '
  'للنص العادي أيضًا. تبقى المفاتيح في مخزن النظام ولا تُصدَّر. قد تفرض الخدمة السحابية رسومًا على '
  'الطلبات.'),

 'tr': ('Çeviri ve sonuç ayarları',
  'Genel: başlangıç, geçmiş, ipuçları, güncelleme denetimi, sonuç penceresi, arayüz ölçeği ve '
  'önizlemeli sonuç metin boyutu.',
  'Çeviri ve OCR: motorlar, yakalama, metni kopyalama ve değiştirme. OCR satırlarını paragraflarda '
  'birleştir, çeviriden önce bağlantılı metindeki görsel satır sonlarını kaldırır.',
  'Dil paketleri → API',
  'Dil paketleri içindeki API sekmesinde hizmet seçip anahtar ve model kimliğini girin. Kaydet ve '
  'seç çeviri için kullanır; tanıma modu OCR için de seçer. API hizmetleri isteğe bağlıdır.',
  'Sonuç metni',
  'Genel bölümündeki Sonuç metni okları çeviri yazı tipini değiştirir; önizleme hemen güncellenir. '
  'Ölçek tüm arayüzü ayrı değiştirir.',
  'Sonuçları kapatma',
  'Dışarı tıklanınca sonucu kapat, Çeviri ve OCR bölümündedir. Başka uygulama kullanırken çeviri '
  'penceresini kapatmak için açın. Varsayılan olarak kapalıdır.',
  'Seçim çevirisini başlatma',
  'Ana pencere → Seçim → dil ayarları veya Kısayolları ayarla → Seçim modu. Seçimden sonra, '
  'kısayol, metnin yanındaki düğme veya anında çeviri seçilir. Hepsi aynı modu, dilleri ve '
  'çevirmeni kullanır.',
  'Tek istek seçili modelle görüntüyü tanır ve çevirir. Kaydet ve seç düz metin için de bu hizmeti '
  'kullanır. Anahtarlar sistem kasasında kalır, dışa aktarılmaz. Bulut hizmeti ücret alabilir.'),
 'hi': ('अनुवाद और परिणाम सेटिंग्स',
  'सामान्य: स्टार्टअप, इतिहास, संकेत, अपडेट जाँच, परिणाम विंडो, इंटरफ़ेस स्केल और उदाहरण सहित '
  'परिणाम टेक्स्ट आकार।',
  'अनुवाद और OCR: इंजन, कैप्चर, टेक्स्ट कॉपी और बदलना। OCR पंक्तियाँ अनुच्छेद में जोड़ें अनुवाद से '
  'पहले जुड़े टेक्स्ट के दृश्य पंक्ति-विराम हटाता है।',
  'भाषा पैकेज → API',
  'भाषा पैकेज के API टैब में सेवा चुनकर कुंजी और मॉडल ID डालें। सहेजें और चुनें से अनुवाद में उपयोग '
  'होगा; पहचान मोड उसे OCR में भी चुनता है। API सेवाएँ वैकल्पिक हैं।',
  'परिणाम टेक्स्ट',
  'सामान्य में परिणाम टेक्स्ट के तीर अनुवाद फ़ॉन्ट बदलते हैं और उदाहरण तुरंत बदलता है। स्केल पूरे '
  'इंटरफ़ेस को अलग बदलता है।',
  'परिणाम बंद करना',
  'बाहर क्लिक पर परिणाम बंद करें अनुवाद और OCR में है। दूसरे ऐप पर क्लिक से अनुवाद विंडो बंद करने '
  'के लिए चालू करें। डिफ़ॉल्ट में बंद है।',
  'चयन अनुवाद शुरू करना',
  'मुख्य विंडो → चयन → भाषा सेटिंग्स, या शॉर्टकट सेट करें → चयन मोड। चयन के बाद में शॉर्टकट, पास का '
  'बटन या तुरंत अनुवाद चुनें। ये उसी मोड, भाषाओं और अनुवादक को शुरू करने के तरीके हैं।',
  'एक अनुरोध चुने मॉडल से इमेज पहचानता और अनुवाद करता है। सहेजें और चुनें इसी सेवा को साधारण '
  'टेक्स्ट के लिए भी लगाता है। कुंजियाँ सिस्टम भंडार में हैं, निर्यात नहीं होतीं। क्लाउड सेवा शुल्क '
  'ले सकती है।'),
 'id': ('Pengaturan terjemahan dan hasil',
  'Umum: mulai, riwayat, petunjuk, pemeriksaan pembaruan, jendela hasil, skala antarmuka, dan '
  'ukuran teks hasil dengan pratinjau.',
  'Terjemahan dan OCR: mesin, tangkapan, penyalinan dan penggantian teks. Gabung baris OCR menjadi '
  'paragraf menghapus pembungkusan baris sebelum menerjemahkan.',
  'Paket bahasa → API',
  'Di tab API pada Paket bahasa, pilih layanan dan masukkan kunci serta ID model. Simpan dan pilih '
  'memakainya untuk terjemahan; mode pengenalan juga memilihnya untuk OCR. Layanan API opsional.',
  'Teks hasil',
  'Di Umum, panah Teks hasil mengubah font terjemahan dan pratinjau langsung diperbarui. Skala '
  'mengubah seluruh antarmuka secara terpisah.',
  'Menutup hasil',
  'Tutup hasil saat klik di luar ada di Terjemahan dan OCR. Aktifkan untuk menutup jendela saat '
  'memakai aplikasi lain. Bawaan nonaktif.',
  'Memulai terjemahan pilihan',
  'Jendela utama → Pilihan → pengaturan bahasa, atau Atur pintasan → Mode pilihan. Setelah memilih '
  'menentukan pintasan, tombol dekat teks, atau terjemahan langsung. Semuanya memicu mode, bahasa, '
  'dan penerjemah yang sama.',
  'Satu permintaan mengenali dan menerjemahkan gambar dengan model pilihan. Simpan dan pilih juga '
  'memakai layanan ini untuk teks biasa. Kunci tetap di brankas sistem dan tidak diekspor. Layanan '
  'cloud dapat mengenakan biaya.'),
}


LAYOUT_COPY = {
 'ru': (
    'Приложение: запуск, истории, подсказки, проверка обновлений, язык интерфейса, масштаб и размер текста результата. Обслуживание и резервные копии — в «Данные и обновления».',
    'Перевод: переводчик, окно результата, копирование и замена текста. OCR: распознавание, объединение строк в абзацы и захват экрана. Кнопки офлайн-пакетов и API находятся внизу соответствующего раздела.',
    'На вкладке «Приложение» стрелки «Текст результата» меняют шрифт перевода. Пример ниже обновляется сразу. «Масштаб» отдельно меняет весь интерфейс.',
    '«Закрывать результат кликом снаружи» находится во вкладке «Перевод». Включите, чтобы убирать окно результата при переходе в другое приложение. По умолчанию выключено.',
    'Приложение → Данные и обновления: проверка обновлений, очистка кэша, сброс, экспорт и импорт настроек, отчёт об ошибке. «Назад» возвращает к настройкам приложения.',
 ),
 'en': (
    'Application: startup, histories, tooltips, update checks, interface language, scale and result text size. Maintenance and backups are in Data and updates.',
    'Translation: translator, result window, copying and replacing text. OCR: recognition, joining lines into paragraphs and screen capture. Offline packages and API buttons are at the bottom of the relevant section.',
    'In Application, Result text arrows change the translation font and update the preview immediately. Scale changes the entire interface separately.',
    'Close result on outside click is in Translation. Enable it to dismiss the result window when using another app. Off by default.',
    'Application → Data and updates: check updates, clear cache, reset, export or import settings, and create a bug report. Back returns to application settings.',
 ),
 'es': (
    'Aplicación: inicio, historiales, ayudas, actualizaciones, idioma de interfaz, escala y tamaño del resultado. Mantenimiento y copias de seguridad están en Datos y actualizaciones.',
    'Traducción: traductor, ventana de resultado, copia y reemplazo. OCR: reconocimiento, unión de líneas en párrafos y captura. Los botones de paquetes sin conexión y API están al pie del apartado correspondiente.',
    'En Aplicación, las flechas de Texto del resultado cambian la fuente y actualizan la vista previa. Escala cambia toda la interfaz por separado.',
    'Cerrar resultado al pulsar fuera está en Traducción. Actívalo para cerrar el resultado al usar otra aplicación. Desactivado de forma predeterminada.',
    'Aplicación → Datos y actualizaciones: buscar versiones, borrar caché, restablecer, exportar o importar ajustes y crear un informe de error. Atrás vuelve a los ajustes de la aplicación.',
 ),
 'de': (
    'Anwendung: Start, Verläufe, Hinweise, Updateprüfung, Oberflächensprache, Skalierung und Ergebnistextgröße. Wartung und Sicherungen finden Sie unter Daten und Updates.',
    'Übersetzung: Übersetzer, Ergebnisfenster, Kopieren und Ersetzen. OCR: Erkennung, Zeilen zu Absätzen verbinden und Bildschirmaufnahme. Offline-Pakete und API öffnen Sie unten im jeweiligen Bereich.',
    'Unter Anwendung ändern die Pfeile bei Ergebnistext die Übersetzungsschrift und sofort die Vorschau. Skalierung passt die gesamte Oberfläche separat an.',
    'Ergebnis bei Außenklick schließen finden Sie unter Übersetzung. Aktivieren, um das Ergebnisfenster beim Wechsel zu einer anderen App zu schließen. Standardmäßig aus.',
    'Anwendung → Daten und Updates: Updates suchen, Cache leeren, Einstellungen zurücksetzen, exportieren oder importieren und Fehlerberichte erstellen. Zurück führt zu den Anwendungseinstellungen.',
 ),
 'fr': (
    'Application : démarrage, historiques, aides, mises à jour, langue, échelle et taille du résultat. Entretien et sauvegardes se trouvent dans Données et mises à jour.',
    'Traduction : moteur, fenêtre de résultat, copie et remplacement. OCR : reconnaissance, regroupement en paragraphes et capture. Les boutons des modules hors ligne et de l’API sont au bas de la rubrique correspondante.',
    'Dans Application, les flèches de Texte du résultat changent la police et actualisent immédiatement l’exemple. Échelle règle séparément toute l’interface.',
    'Fermer le résultat au clic extérieur se trouve dans Traduction. Activez cette option pour fermer le résultat en passant à une autre application. Désactivée par défaut.',
    'Application → Données et mises à jour : rechercher une version, vider le cache, réinitialiser, exporter ou importer les réglages et créer un rapport. Retour ramène aux réglages de l’application.',
 ),
 'zh': (
    '程序：启动、历史记录、提示、更新检查、界面语言、缩放和译文大小。维护及备份位于“数据与更新”。',
    '翻译：翻译引擎、结果窗口、复制与替换。OCR：文字识别、将行合并为段落及屏幕截取。离线包和 API 按钮位于对应页面底部。',
    '在“程序”中，“结果文字”两侧箭头调整译文字体，并立即更新示例。“缩放”单独调整整个界面。',
    '“点击外部关闭结果”位于“翻译”。启用后，使用其他程序时可关闭结果窗口。默认关闭。',
    '程序 → 数据与更新：检查更新、清除缓存、重置、导出或导入设置，以及生成问题报告。“返回”回到程序设置。',
 ),
 'pt': (
    'Aplicativo: inicialização, históricos, dicas, atualizações, idioma, escala e tamanho do resultado. A manutenção e os backups ficam em Dados e atualizações.',
    'Tradução: tradutor, janela de resultado, cópia e substituição. OCR: reconhecimento, união de linhas em parágrafos e captura. Os botões de pacotes offline e API ficam na parte inferior da seção correspondente.',
    'Em Aplicativo, as setas de Texto do resultado alteram a fonte e atualizam o exemplo imediatamente. Escala ajusta toda a interface separadamente.',
    'Fechar resultado ao clicar fora fica em Tradução. Ative para fechar o resultado ao usar outro aplicativo. Desativado por padrão.',
    'Aplicativo → Dados e atualizações: buscar atualizações, limpar cache, redefinir, exportar ou importar configurações e criar um relatório. Voltar retorna às configurações do aplicativo.',
 ),
 'it': (
    'Applicazione: avvio, cronologie, suggerimenti, aggiornamenti, lingua, scala e dimensione del risultato. Manutenzione e backup sono in Dati e aggiornamenti.',
    'Traduzione: traduttore, finestra del risultato, copia e sostituzione. OCR: riconoscimento, unione delle righe in paragrafi e acquisizione. I pulsanti per pacchetti offline e API sono in fondo alla sezione corrispondente.',
    'In Applicazione, le frecce di Testo del risultato cambiano il carattere e aggiornano subito l’esempio. Scala regola separatamente tutta l’interfaccia.',
    'Chiudi risultato con clic esterno si trova in Traduzione. Attivalo per chiudere il risultato quando usi un’altra applicazione. Disattivato per impostazione predefinita.',
    'Applicazione → Dati e aggiornamenti: cerca aggiornamenti, svuota la cache, ripristina, esporta o importa impostazioni e crea un rapporto. Indietro torna alle impostazioni dell’applicazione.',
 ),
 'ar': (
    'التطبيق: بدء التشغيل والسجلات والتلميحات والتحديثات ولغة الواجهة ومقياسها وحجم نص النتيجة. الصيانة والنسخ الاحتياطية ضمن البيانات والتحديثات.',
    'الترجمة: المترجم ونافذة النتيجة ونسخ النص واستبداله. OCR: التعرف على النص ودمج الأسطر في فقرات والتقاط الشاشة. توجد أزرار الحزم دون اتصال وAPI أسفل القسم المناسب.',
    'في التطبيق، تغيّر أسهم نص النتيجة خط الترجمة وتحدّث المعاينة فورًا. يغيّر المقياس حجم الواجهة كلها بشكل مستقل.',
    'خيار إغلاق النتيجة بالنقر خارجها موجود في الترجمة. فعّله لإغلاق النتيجة عند استخدام تطبيق آخر. معطّل افتراضيًا.',
    'التطبيق ← البيانات والتحديثات: البحث عن تحديثات ومسح التخزين المؤقت وإعادة الضبط وتصدير الإعدادات أو استيرادها وإنشاء تقرير مشكلة. يعيدك الرجوع إلى إعدادات التطبيق.',
 ),
 'tr': (
    'Uygulama: başlangıç, geçmişler, ipuçları, güncellemeler, arayüz dili, ölçek ve sonuç yazısı boyutu. Bakım ve yedekler Veriler ve güncellemeler içindedir.',
    'Çeviri: çevirmen, sonuç penceresi, kopyalama ve değiştirme. OCR: tanıma, satırları paragraflarda birleştirme ve ekran yakalama. Çevrimdışı paket ve API düğmeleri ilgili bölümün altındadır.',
    'Uygulama bölümünde Sonuç metni okları çeviri yazı tipini ve örneği hemen değiştirir. Ölçek tüm arayüzü ayrı ayarlar.',
    'Dışarı tıklanınca sonucu kapat, Çeviri bölümündedir. Başka uygulama kullanırken sonuç penceresini kapatmak için açın. Varsayılan olarak kapalıdır.',
    'Uygulama → Veriler ve güncellemeler: güncelleme ara, önbelleği temizle, ayarları sıfırla, dışa veya içe aktar ve hata raporu oluştur. Geri, uygulama ayarlarına döner.',
 ),
 'hi': (
    'ऐप: शुरुआत, इतिहास, संकेत, अपडेट जाँच, इंटरफ़ेस भाषा, स्केल और परिणाम टेक्स्ट का आकार। रखरखाव और बैकअप डेटा और अपडेट में हैं।',
    'अनुवाद: अनुवादक, परिणाम विंडो, कॉपी और बदलना। OCR: पहचान, पंक्तियाँ अनुच्छेद में जोड़ना और स्क्रीन कैप्चर। ऑफ़लाइन पैकेज और API के बटन संबंधित अनुभाग के नीचे हैं।',
    'ऐप में परिणाम टेक्स्ट के तीर अनुवाद का फ़ॉन्ट बदलते हैं और उदाहरण तुरंत बदलता है। स्केल पूरे इंटरफ़ेस को अलग बदलता है।',
    'बाहर क्लिक पर परिणाम बंद करें अनुवाद में है। दूसरे ऐप का उपयोग करते समय परिणाम बंद करने के लिए चालू करें। डिफ़ॉल्ट में बंद है।',
    'ऐप → डेटा और अपडेट: अपडेट जाँचें, कैश साफ़ करें, सेटिंग्स रीसेट, निर्यात या आयात करें और समस्या रिपोर्ट बनाएँ। वापस से ऐप की सेटिंग्स खुलती हैं।',
 ),
 'id': (
    'Aplikasi: mulai, riwayat, petunjuk, pembaruan, bahasa antarmuka, skala dan ukuran teks hasil. Pemeliharaan dan cadangan ada di Data dan pembaruan.',
    'Terjemahan: penerjemah, jendela hasil, penyalinan dan penggantian teks. OCR: pengenalan, penggabungan baris menjadi paragraf dan tangkapan layar. Tombol paket offline dan API ada di bawah bagian terkait.',
    'Di Aplikasi, panah Teks hasil mengubah font terjemahan dan langsung memperbarui contoh. Skala mengubah seluruh antarmuka secara terpisah.',
    'Tutup hasil saat klik di luar ada di Terjemahan. Aktifkan untuk menutup hasil ketika memakai aplikasi lain. Bawaan nonaktif.',
    'Aplikasi → Data dan pembaruan: periksa versi, bersihkan cache, reset, ekspor atau impor pengaturan dan buat laporan masalah. Kembali membuka pengaturan aplikasi.',
 ),
}

for _locale, _layout_copy in LAYOUT_COPY.items():
    _copy = list(COPY[_locale])
    for _index, _value in zip((1, 2, 6, 8), _layout_copy):
        _copy[_index] = _value
    _copy.append(_layout_copy[4])
    COPY[_locale] = tuple(_copy)


def guide_updates(language):
    from settings_sections import PAGE_APPLICATION, PAGE_TRANSLATION, page_caption, section_text
    c = COPY.get(language, COPY['en'])
    entries = {key: (c[i], c[i+1]) for key, i in (
        ('result_text', 5), ('result_behavior', 7), ('selection_behavior', 9))}
    entries.update({
        'api_connections': (page_caption(language, PAGE_TRANSLATION) + ' → ' + section_text(language, 'api'), c[4]),
        'settings_page_main': (page_caption(language, PAGE_APPLICATION), c[1]),
        'settings_page_updates': (page_caption(language, PAGE_TRANSLATION), c[2]),
        'actions_panel': (section_text(language, 'maintenance'), c[12]),
    })
    return entries


def update_help(content):
    from selection_options import TEXT
    for lang, sections in content.items():
        c = COPY.get(lang, COPY['en'])
        for index, (title, items) in enumerate(sections):
            if any("OCR</span>" in item for item in items) and any('span' in item for item in items[2:]):
                sections[index] = (c[0], [c[1], c[2], *items])
        from settings_sections import section_text
        sections.append((guide_updates(lang)['api_connections'][0], [c[4], c[11]]))
        sections.append((c[5], [c[6]]))
        sections.append((c[7], [c[8]]))
        sections.append((c[9], [c[10], TEXT.get(lang, TEXT['en'])[5]]))
        sections.append((section_text(lang, 'maintenance'), [c[12]]))
        from image_input import image_text
        sections.append((image_text(lang, 'open'), [image_text(lang, 'hint')]))
