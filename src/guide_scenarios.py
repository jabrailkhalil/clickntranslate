"""Task-oriented first-run tour. No setting changes just by opening a card."""

ORDER = (
    'language', 'theme', 'replace_selection_select_all', 'chat_languages',
    'shortcut_replace', 'shortcut_ocr', 'shortcut_fullscreen',
    'shortcut_selection', 'game_controls', 'document_translation',
    'language_packages', 'companion_settings', 'hotkeys', 'back_home',
)
CHAT_STEPS = ('replace_selection_select_all', 'chat_languages', 'shortcut_replace')

INTRO = {
    'ru': 'Выберем язык и тему, настроим перевод сообщений одной клавишей и познакомимся с переводом экрана, файлов и офлайн-пакетами. Вы сами решаете, что включать.',
    'en': 'Choose a language and theme, set up one-shortcut chat translation, and discover screen translation, files and offline packs. You decide what to enable.',
    'es': 'Elige idioma y tema, configura la traducción de mensajes con un atajo y conoce la traducción de pantalla, archivos y paquetes sin conexión. Tú decides qué activar.',
    'de': 'Wählen Sie Sprache und Design, richten Sie Chat-Übersetzung per Kürzel ein und entdecken Sie Bildschirmübersetzung, Dateien und Offline-Pakete. Sie entscheiden, was aktiv wird.',
    'fr': 'Choisissez la langue et le thème, configurez la traduction des messages par raccourci et découvrez la traduction d’écran, les fichiers et les packs hors ligne. Vous choisissez quoi activer.',
    'zh': '选择语言和主题，设置一键翻译聊天消息，了解屏幕翻译、文件与离线语言包。启用哪些功能，由你决定。',
    'pt': 'Escolha idioma e tema, configure a tradução de mensagens com um atalho e conheça a tradução da tela, arquivos e pacotes offline. Você decide o que ativar.',
    'it': 'Scegli lingua e tema, configura la traduzione dei messaggi con una scorciatoia e scopri traduzione dello schermo, file e pacchetti offline. Decidi tu cosa attivare.',
    'ar': 'اختر اللغة والمظهر واضبط ترجمة الرسائل باختصار واحد، ثم تعرّف على ترجمة الشاشة والملفات والحزم دون اتصال. أنت تختار ما تفعّله.',
    'tr': 'Dil ve temayı seçin, tek kısayolla sohbet çevirisini ayarlayın; ekran çevirisini, dosyaları ve çevrimdışı paketleri keşfedin. Neyi açacağınıza siz karar verin.',
    'hi': 'भाषा और थीम चुनें, एक शॉर्टकट से चैट अनुवाद सेट करें और स्क्रीन, फ़ाइल व ऑफ़लाइन पैकेज जानें। क्या चालू करना है, आप तय करें।',
    'id': 'Pilih bahasa dan tema, siapkan terjemahan pesan dengan satu pintasan, lalu kenali terjemahan layar, berkas dan paket offline. Anda menentukan fitur yang diaktifkan.',
}
APPEARANCE_CHAPTER = dict(zip(
    ('ru', 'en', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id'),
    ('Ваше приложение', 'Your app', 'Tu aplicación', 'Ihre App', 'Votre application', '你的应用',
     'Seu aplicativo', 'La tua app', 'تطبيقك', 'Uygulamanız', 'आपका ऐप', 'Aplikasi Anda')))

ENGINES = {
    'ru': ('Онлайн, офлайн или свой API?', 'Google работает через интернет. Для перевода без сети откройте «Офлайн-перевод» и заранее скачайте движок и модели. В том же окне на вкладке API можно подключить свой сервис и ключ. Скачивание начинается только по вашей команде.'),
    'en': ('Online, offline or your own API?', 'Google uses the internet. For offline translation, open Offline translation and download the engine and models first. The API tab in the same window connects your own service and key. Nothing downloads until you request it.'),
    'es': ('¿En línea, sin conexión o API propia?', 'Google usa Internet. Para traducir sin conexión, abre Traducción sin conexión y descarga primero el motor y los modelos. En la pestaña API de esa ventana conecta tu servicio y clave. Nada se descarga sin que lo pidas.'),
    'de': ('Online, offline oder eigene API?', 'Google benötigt Internet. Öffnen Sie Offline-Übersetzung und laden Sie zuerst Engine und Modelle herunter, um offline zu übersetzen. Im API-Tab desselben Fensters verbinden Sie Ihren Dienst und Schlüssel. Downloads starten nur auf Ihren Wunsch.'),
    'fr': ('En ligne, hors ligne ou votre API ?', 'Google utilise Internet. Pour traduire hors ligne, ouvrez Traduction hors ligne et téléchargez d’abord le moteur et les modèles. L’onglet API de la même fenêtre permet de connecter votre service et votre clé. Aucun téléchargement sans votre accord.'),
    'zh': ('在线、离线还是自己的 API？', 'Google 需要联网。离线翻译前，请打开离线翻译并下载引擎和模型。同一窗口的 API 标签页可连接自己的服务和密钥。只有你点击下载才会下载。'),
    'pt': ('Online, offline ou sua própria API?', 'O Google usa a internet. Para traduzir offline, abra Tradução offline e baixe primeiro o motor e os modelos. Na aba API da mesma janela, conecte seu serviço e chave. Nada é baixado sem sua solicitação.'),
    'it': ('Online, offline o la tua API?', 'Google usa Internet. Per tradurre offline, apri Traduzione offline e scarica prima motore e modelli. Nella scheda API della stessa finestra puoi collegare servizio e chiave. Nessun download parte senza una tua richiesta.'),
    'ar': ('عبر الإنترنت أم دونه أم عبر API؟', 'يحتاج Google إلى الإنترنت. للترجمة دون اتصال، افتح الترجمة دون اتصال ونزّل المحرك والنماذج أولًا. تبويب API في النافذة نفسها يتيح ربط خدمتك ومفتاحك. لا يبدأ أي تنزيل إلا بطلبك.'),
    'tr': ('Çevrimiçi, çevrimdışı veya kendi API’niz?', 'Google internet kullanır. Çevrimdışı çeviri için Çevrimdışı çeviri’yi açıp önce motor ve modelleri indirin. Aynı penceredeki API sekmesinde kendi servis ve anahtarınızı bağlayın. İndirmeler yalnız isteğinizle başlar.'),
    'hi': ('ऑनलाइन, ऑफ़लाइन या अपनी API?', 'Google को इंटरनेट चाहिए। ऑफ़लाइन अनुवाद के लिए ऑफ़लाइन अनुवाद खोलकर पहले इंजन और मॉडल डाउनलोड करें। उसी विंडो के API टैब में अपनी सेवा और कुंजी जोड़ें। डाउनलोड केवल आपके कहने पर शुरू होता है।'),
    'id': ('Online, offline atau API sendiri?', 'Google memakai internet. Untuk terjemahan offline, buka Terjemahan offline dan unduh mesin serta model terlebih dahulu. Tab API pada jendela yang sama menghubungkan layanan dan kunci Anda. Unduhan hanya dimulai saat Anda meminta.'),
}
DYNAMIC = {
    'ru': 'Выберите языки справа, интервал проверки и непрозрачность фона. Сочетание ниже открывает выбор одной или нескольких областей. Выделите текст и нажмите «Старт» — перевод будет обновляться сам. Повторное сочетание останавливает режим. Расположение областей можно сохранить в шаблон.',
    'en': 'Choose languages, scan interval and background opacity on the right. The shortcut below opens the area picker. Select one or more text areas and click Start: translations keep updating. Press the shortcut again to stop. Save the area layout as a template to reuse it.',
    'es': 'Elige idiomas, intervalo y opacidad a la derecha. El atajo de abajo abre el selector de áreas. Selecciona una o varias zonas y pulsa Iniciar: la traducción se actualizará sola. Pulsa el atajo de nuevo para parar. Guarda la distribución como plantilla para reutilizarla.',
    'de': 'Wählen Sie rechts Sprachen, Scanintervall und Hintergrunddeckkraft. Das Kürzel unten öffnet die Bereichsauswahl. Markieren Sie einen oder mehrere Textbereiche und klicken Sie auf Start. Übersetzungen werden laufend aktualisiert. Erneutes Drücken stoppt den Modus. Speichern Sie das Layout als Vorlage.',
    'fr': 'Choisissez les langues, l’intervalle et l’opacité à droite. Le raccourci ci-dessous ouvre la sélection de zones. Sélectionnez une ou plusieurs zones et cliquez sur Démarrer : la traduction se met à jour. Réutilisez le raccourci pour arrêter. Enregistrez les zones comme modèle pour les réutiliser.',
    'zh': '在右侧选择语言、扫描间隔和背景不透明度。下方快捷键打开区域选择器。选择一处或多处文字区域并点击开始，译文就会自动更新。再次按快捷键停止。可以将区域布局保存为模板，以便下次使用。',
    'pt': 'Escolha idiomas, intervalo e opacidade à direita. O atalho abaixo abre a seleção de áreas. Selecione uma ou mais áreas e clique em Iniciar: a tradução será atualizada. Use o atalho novamente para parar. Salve a disposição como modelo para reutilizá-la.',
    'it': 'Scegli lingue, intervallo e opacità a destra. La scorciatoia sotto apre la selezione delle aree. Seleziona una o più aree e premi Avvia: la traduzione si aggiorna da sola. Premi di nuovo la scorciatoia per fermare. Salva la disposizione come modello per riutilizzarla.',
    'ar': 'اختر اللغتين والفاصل وعتامة الخلفية على اليمين. يفتح الاختصار أدناه اختيار المناطق. حدد منطقة نص أو أكثر واضغط بدء لتتجدد الترجمة تلقائيًا. اضغط الاختصار مرة أخرى للإيقاف. يمكنك حفظ ترتيب المناطق كقالب لاستخدامه لاحقًا.',
    'tr': 'Sağdan dilleri, tarama aralığını ve arka plan opaklığını seçin. Aşağıdaki kısayol alan seçimini açar. Bir veya birkaç metin alanı seçip Başlat’a basın; çeviri güncellenir. Durdurmak için kısayola tekrar basın. Alan düzenini yeniden kullanmak için şablon olarak kaydedin.',
    'hi': 'दाईं ओर भाषा, जाँच अंतराल और पृष्ठभूमि की अपारदर्शिता चुनें। नीचे का शॉर्टकट क्षेत्र चयन खोलता है। एक या कई टेक्स्ट क्षेत्र चुनकर शुरू दबाएँ: अनुवाद अपने आप बदलता रहेगा। रोकने के लिए शॉर्टकट दोबारा दबाएँ। क्षेत्रों को टेम्पलेट में सहेजकर फिर इस्तेमाल करें।',
    'id': 'Pilih bahasa, interval dan opasitas di kanan. Pintasan di bawah membuka pemilih area. Pilih satu atau beberapa area teks lalu klik Mulai: terjemahan terus diperbarui. Tekan pintasan lagi untuk berhenti. Simpan susunan area sebagai templat untuk dipakai lagi.',
}

# language title/body, theme title/body, chat title/body, direction title/body,
# companion title/body, completion, yes, no, continue, intro.
COPY = {
    'ru': (
        'На каком языке общаемся?', 'Нажмите флаг слева сверху и выберите язык меню, подсказок и этого гайда. Или оставьте текущий язык и нажмите «Далее».',
        'Светлая или тёмная?', 'Нажмите солнце или луну рядом с флагом. Тема сразу изменится во всём приложении. Нравится текущая? Идём дальше.',
        'Хотите писать в чате на другом языке?', 'Включите «Выделять всё перед заменой» здесь или кнопкой ниже. Тогда команда замены переведёт всё сообщение в активном поле ввода. Сообщение не отправляется. Если не нужно — нажмите «Не сейчас».',
        'Откуда и на какой язык?', 'Выбран режим замены. В двух списках выберите язык вашего сообщения и язык собеседника. Это отдельная пара для замены; остальные режимы сохраняют свои языки.',
        'Клик всегда рядом', 'Здесь можно включить компаньона на рабочем столе, выбрать героя и настроить его кнопки: открыть приложение, перевести экран и другие действия.',
        'Готово! Пишите, переводите экран и открывайте файлы. Все настройки можно изменить позже; этот гайд снова доступен в справке.',
        'Да, настроить', 'Не сейчас', 'Далее', 'Давайте попробуем'),
    'en': (
        'Which language feels like home?', 'Click the flag at the top left to choose the language of menus, hints and this guide. Or keep your current language and click Next.',
        'Light or dark?', 'Click the sun or moon beside the flag. The theme changes throughout the app. Happy with this one? Continue.',
        'Want to chat in another language?', 'Enable Select all before replacing here or with the button below. The replace command will translate the whole message in the active input. It does not send the message. Choose Not now to skip.',
        'From your language to theirs', 'Replace mode is selected. Use the two lists to choose your message language and the recipient’s language. This pair belongs to replacement; other modes keep their own languages.',
        'Keep Click nearby', 'Enable the desktop companion here, choose a character and customize its buttons: open the app, translate the screen and more.',
        'You’re ready! Write messages, translate your screen and open files. Change settings any time and reopen this guide from Help.',
        'Yes, set it up', 'Not now', 'Next', 'Let’s try it'),
    'es': (
        '¿En qué idioma hablamos?', 'Pulsa la bandera de arriba a la izquierda para elegir el idioma de menús, ayudas y esta guía. O conserva el actual y pulsa Siguiente.',
        '¿Claro u oscuro?', 'Pulsa el sol o la luna junto a la bandera. El tema cambia en toda la aplicación. Si te gusta el actual, continúa.',
        '¿Quieres chatear en otro idioma?', 'Activa Seleccionar todo al reemplazar aquí o con el botón inferior. La orden traducirá el mensaje completo del campo activo. No lo envía. Pulsa Ahora no para omitirlo.',
        'De tu idioma al de tu interlocutor', 'El modo Reemplazar está seleccionado. Elige en las dos listas el idioma de tu mensaje y el del destinatario. Los otros modos conservan sus propios idiomas.',
        'Click siempre cerca', 'Activa el compañero de escritorio, elige un personaje y configura sus botones para abrir la aplicación, traducir la pantalla y más.',
        '¡Listo! Escribe mensajes, traduce la pantalla y abre archivos. Puedes cambiar los ajustes y volver a esta guía desde Ayuda.',
        'Sí, configurar', 'Ahora no', 'Siguiente', 'Vamos a probar'),
    'de': (
        'Welche Sprache passt zu Ihnen?', 'Klicken Sie oben links auf die Flagge und wählen Sie die Sprache für Menüs, Hinweise und diese Anleitung. Oder behalten Sie die aktuelle Sprache und klicken Sie auf Weiter.',
        'Hell oder dunkel?', 'Klicken Sie neben der Flagge auf Sonne oder Mond. Das Design ändert sich in der ganzen App. Gefällt Ihnen das aktuelle? Dann weiter.',
        'In einer anderen Sprache chatten?', 'Aktivieren Sie hier oder unten Vor Ersetzen alles auswählen. Der Ersetzen-Befehl übersetzt die ganze Nachricht im aktiven Eingabefeld. Er sendet sie nicht ab. Mit Jetzt nicht überspringen Sie diesen Schritt.',
        'Von Ihrer Sprache zur Zielsprache', 'Der Modus Ersetzen ist ausgewählt. Wählen Sie in den beiden Listen Ihre Sprache und die des Empfängers. Andere Modi behalten ihre eigenen Sprachen.',
        'Click an Ihrer Seite', 'Aktivieren Sie den Desktop-Begleiter, wählen Sie eine Figur und passen Sie seine Schaltflächen an: App öffnen, Bildschirm übersetzen und mehr.',
        'Bereit! Schreiben Sie Nachrichten, übersetzen Sie den Bildschirm und öffnen Sie Dateien. Einstellungen lassen sich jederzeit ändern; die Anleitung finden Sie in der Hilfe.',
        'Ja, einrichten', 'Jetzt nicht', 'Weiter', 'Ausprobieren'),
    'fr': (
        'Dans quelle langue discuter ?', 'Cliquez sur le drapeau en haut à gauche pour choisir la langue des menus, des infobulles et du guide. Ou gardez la langue actuelle et cliquez sur Suivant.',
        'Clair ou sombre ?', 'Cliquez sur le soleil ou la lune à côté du drapeau. Le thème change dans toute l’application. Le thème actuel vous plaît ? Continuez.',
        'Envie de discuter dans une autre langue ?', 'Activez Tout sélectionner avant remplacement ici ou avec le bouton ci-dessous. La commande traduira tout le message du champ actif. Elle ne l’envoie pas. Choisissez Pas maintenant pour passer.',
        'De votre langue à la sienne', 'Le mode Remplacer est sélectionné. Choisissez votre langue et celle du destinataire dans les deux listes. Les autres modes gardent leurs propres langues.',
        'Gardez Click à vos côtés', 'Activez le compagnon de bureau, choisissez un personnage et personnalisez ses boutons : ouvrir l’application, traduire l’écran et plus encore.',
        'Tout est prêt ! Écrivez, traduisez l’écran et ouvrez des fichiers. Les réglages restent modifiables et le guide est disponible dans l’aide.',
        'Oui, configurer', 'Pas maintenant', 'Suivant', 'Essayons'),
    'zh': (
        '用哪种语言交流？', '点击左上角的国旗，选择菜单、提示和本指南的语言。也可以保留当前语言，点击下一步。',
        '浅色还是深色？', '点击国旗旁的太阳或月亮，整个应用会立即切换主题。喜欢当前主题？直接继续。',
        '想用其他语言聊天吗？', '在这里或通过下方按钮启用替换前全选文本。替换命令会翻译当前输入框中的整条消息，但不会发送。选择暂不设置可跳过。',
        '从你的语言到对方的语言', '已选择替换模式。在两个列表中选择消息原文语言和对方的语言。这一语言对仅用于替换，其他模式保留各自的语言。',
        '让 Click 陪伴你', '在这里启用桌面伙伴，选择角色，并设置打开应用、翻译屏幕等菜单按钮。',
        '准备好了！现在可以聊天、翻译屏幕和打开文件。随时更改设置，也可从帮助中重新打开指南。',
        '开始设置', '暂不设置', '下一步', '一起试试'),
    'pt': (
        'Em que idioma vamos conversar?', 'Clique na bandeira no canto superior esquerdo para escolher o idioma dos menus, dicas e deste guia. Ou mantenha o idioma atual e clique em Avançar.',
        'Claro ou escuro?', 'Clique no sol ou na lua ao lado da bandeira. O tema muda em todo o aplicativo. Gostou do atual? Continue.',
        'Quer conversar em outro idioma?', 'Ative Selecione tudo antes de substituir aqui ou no botão abaixo. O comando traduzirá toda a mensagem no campo ativo. Ele não envia a mensagem. Escolha Agora não para pular.',
        'Do seu idioma para o da outra pessoa', 'O modo Substituir está selecionado. Escolha nas duas listas o idioma da mensagem e o do destinatário. Os outros modos mantêm seus próprios idiomas.',
        'Deixe o Click por perto', 'Ative o companheiro na área de trabalho, escolha um personagem e personalize seus botões: abrir o aplicativo, traduzir a tela e mais.',
        'Tudo pronto! Escreva mensagens, traduza a tela e abra arquivos. Altere os ajustes quando quiser e reabra este guia na Ajuda.',
        'Sim, configurar', 'Agora não', 'Avançar', 'Vamos experimentar'),
    'it': (
        'In che lingua parliamo?', 'Fai clic sulla bandiera in alto a sinistra per scegliere la lingua di menu, suggerimenti e guida. Oppure mantieni quella attuale e premi Avanti.',
        'Chiaro o scuro?', 'Fai clic sul sole o sulla luna accanto alla bandiera. Il tema cambia in tutta l’app. Ti piace quello attuale? Prosegui.',
        'Vuoi chattare in un’altra lingua?', 'Attiva Seleziona tutto prima di sostituire qui o con il pulsante sotto. Il comando tradurrà tutto il messaggio nel campo attivo. Non lo invia. Scegli Non ora per saltare.',
        'Dalla tua lingua alla sua', 'La modalità Sostituisci è selezionata. Scegli nelle due liste la lingua del messaggio e quella del destinatario. Le altre modalità mantengono le proprie lingue.',
        'Tieni Click vicino', 'Attiva il compagno sul desktop, scegli un personaggio e personalizza i pulsanti per aprire l’app, tradurre lo schermo e altro.',
        'Tutto pronto! Scrivi messaggi, traduci lo schermo e apri file. Puoi cambiare le impostazioni e riaprire questa guida dall’Aiuto.',
        'Sì, configura', 'Non ora', 'Avanti', 'Proviamo'),
    'ar': (
        'بأي لغة نتحدث؟', 'انقر على العلم أعلى اليسار لاختيار لغة القوائم والتلميحات وهذا الدليل. أو احتفظ باللغة الحالية وانقر على التالي.',
        'فاتح أم داكن؟', 'انقر على الشمس أو القمر بجانب العلم. يتغير المظهر في التطبيق كله. هل يعجبك المظهر الحالي؟ تابع.',
        'هل تريد الدردشة بلغة أخرى؟', 'فعّل تحديد الكل قبل الاستبدال هنا أو بالزر أدناه. سيترجم أمر الاستبدال الرسالة كاملة في حقل الإدخال النشط. لا يرسل الرسالة. اختر ليس الآن للتخطي.',
        'من لغتك إلى لغة الطرف الآخر', 'تم اختيار وضع الاستبدال. اختر لغة رسالتك ولغة المستلم من القائمتين. يحتفظ كل وضع آخر بلغاته الخاصة.',
        'اجعل Click رفيقك', 'فعّل رفيق سطح المكتب واختر شخصية وخصص أزرارها لفتح التطبيق وترجمة الشاشة وغيرها.',
        'كل شيء جاهز! اكتب الرسائل وترجم الشاشة وافتح الملفات. يمكنك تعديل الإعدادات وإعادة فتح هذا الدليل من المساعدة.',
        'نعم، لنضبطه', 'ليس الآن', 'التالي', 'لنجرب معًا'),
    'tr': (
        'Hangi dilde konuşalım?', 'Menülerin, ipuçlarının ve bu rehberin dilini seçmek için sol üstteki bayrağa tıklayın. Ya da mevcut dili koruyup İleri’ye basın.',
        'Açık mı koyu mu?', 'Bayrağın yanındaki güneşe veya aya tıklayın. Tema tüm uygulamada değişir. Mevcut temayı beğendiyseniz devam edin.',
        'Başka bir dilde sohbet etmek ister misiniz?', 'Buradan veya aşağıdaki düğmeyle Değiştirmeden önce tümünü seç’i açın. Değiştir komutu etkin alandaki tüm mesajı çevirir. Mesajı göndermez. Atlamak için Şimdi değil’i seçin.',
        'Sizin dilinizden karşı tarafın diline', 'Değiştir modu seçili. İki listeden mesajınızın ve alıcının dilini seçin. Diğer modlar kendi dil çiftlerini korur.',
        'Click yanınızda olsun', 'Masaüstü yoldaşını açın, bir karakter seçin ve uygulamayı açma, ekranı çevirme gibi düğmelerini özelleştirin.',
        'Hazırsınız! Mesaj yazın, ekranı çevirin ve dosya açın. Ayarları sonra değiştirebilir ve rehberi Yardım’dan açabilirsiniz.',
        'Evet, ayarla', 'Şimdi değil', 'İleri', 'Birlikte deneyelim'),
    'hi': (
        'किस भाषा में बात करें?', 'मेनू, सुझाव और गाइड की भाषा चुनने के लिए ऊपर बाएँ झंडे पर क्लिक करें। या मौजूदा भाषा रखकर आगे दबाएँ।',
        'हल्का या गहरा?', 'झंडे के पास सूरज या चाँद पर क्लिक करें। पूरे ऐप की थीम बदल जाएगी। मौजूदा थीम पसंद है तो आगे बढ़ें।',
        'दूसरी भाषा में चैट करना चाहते हैं?', 'यहाँ या नीचे के बटन से बदलने से पहले सब चुनें चालू करें। बदलने का आदेश सक्रिय बॉक्स के पूरे संदेश का अनुवाद करेगा। संदेश भेजा नहीं जाता। छोड़ने के लिए अभी नहीं चुनें।',
        'आपकी भाषा से उनकी भाषा में', 'बदलने का मोड चुना है। दोनों सूचियों में अपने संदेश और प्राप्तकर्ता की भाषा चुनें। बाकी मोड अपनी भाषाएँ बनाए रखते हैं।',
        'Click को अपने पास रखें', 'डेस्कटॉप साथी चालू करें, पात्र चुनें और ऐप खोलने व स्क्रीन अनुवाद जैसे मेनू बटन तय करें।',
        'तैयार हैं! संदेश लिखें, स्क्रीन का अनुवाद करें और फ़ाइल खोलें। सेटिंग बाद में बदल सकते हैं; गाइड मदद में मिलेगी।',
        'हाँ, सेट करें', 'अभी नहीं', 'आगे', 'साथ में आज़माएँ'),
    'id': (
        'Mau memakai bahasa apa?', 'Klik bendera di kiri atas untuk memilih bahasa menu, petunjuk dan panduan ini. Atau pertahankan bahasa saat ini lalu klik Berikutnya.',
        'Terang atau gelap?', 'Klik matahari atau bulan di samping bendera. Tema berubah di seluruh aplikasi. Suka tema saat ini? Lanjutkan.',
        'Ingin mengobrol dalam bahasa lain?', 'Aktifkan Pilih semua sebelum mengganti di sini atau lewat tombol di bawah. Perintah ganti akan menerjemahkan seluruh pesan pada kolom aktif. Pesan tidak dikirim. Pilih Nanti saja untuk melewati.',
        'Dari bahasa Anda ke bahasa mereka', 'Mode Ganti sudah dipilih. Pilih bahasa pesan dan bahasa penerima di dua daftar. Mode lain mempertahankan pasangan bahasanya sendiri.',
        'Biarkan Click menemani Anda', 'Aktifkan pendamping desktop, pilih karakter dan atur tombolnya untuk membuka aplikasi, menerjemahkan layar dan lainnya.',
        'Siap! Tulis pesan, terjemahkan layar dan buka berkas. Ubah pengaturan kapan saja dan buka panduan ini lagi dari Bantuan.',
        'Ya, siapkan', 'Nanti saja', 'Berikutnya', 'Mari mencoba'),
}


def copy(language):
    return COPY.get(language, COPY['en'])


_CHAT_SHORTCUT = {
    'ru': 'Теперь откройте чат и напишите сообщение на своём языке. Нажмите назначенную клавишу замены — текст в поле станет переводом. Если сочетание не задано, нажмите на выделенную строку и назначьте его в настройках. Сообщение отправляете вы сами.',
    'en': 'Now open a chat and write in your own language. Press your assigned replace shortcut: the text in the input becomes its translation. If no shortcut is set, click the highlighted row to assign one in Settings. You send the message yourself.',
    'es': 'Abre un chat y escribe en tu idioma. Pulsa el atajo asignado para reemplazar: el texto del campo se convierte en su traducción. Si no hay atajo, pulsa la fila resaltada para asignarlo en Ajustes. Tú envías el mensaje.',
    'de': 'Öffnen Sie einen Chat und schreiben Sie in Ihrer Sprache. Das zugewiesene Ersetzen-Kürzel ersetzt den Text durch die Übersetzung. Ohne Kürzel klicken Sie auf die markierte Zeile und weisen eines in den Einstellungen zu. Die Nachricht senden Sie selbst.',
    'fr': 'Ouvrez un chat et écrivez dans votre langue. Le raccourci de remplacement attribué remplace le texte par sa traduction. Si aucun raccourci n’est défini, cliquez sur la ligne surlignée pour en attribuer un dans les réglages. Vous envoyez le message vous-même.',
    'zh': '现在打开聊天窗口，用你的语言写消息。按下已分配的替换快捷键，输入框中的文字就会变成译文。若尚未设置快捷键，点击高亮行并在设置中分配。消息由你手动发送。',
    'pt': 'Abra um chat e escreva no seu idioma. Use o atalho de substituição atribuído: o texto será trocado pela tradução. Se não houver atalho, clique na linha destacada para defini-lo nas configurações. Você envia a mensagem.',
    'it': 'Apri una chat e scrivi nella tua lingua. Premi la scorciatoia di sostituzione assegnata: il testo diventa la traduzione. Se manca, fai clic sulla riga evidenziata per assegnarla nelle impostazioni. Invii tu il messaggio.',
    'ar': 'افتح دردشة واكتب بلغتك. اضغط اختصار الاستبدال المعيّن ليتحول النص في الحقل إلى ترجمته. إن لم يوجد اختصار، انقر على السطر المميز لتعيينه في الإعدادات. أنت من يرسل الرسالة.',
    'tr': 'Bir sohbet açıp kendi dilinizde yazın. Atanmış değiştirme kısayoluna basınca metin çevirisiyle değişir. Kısayol yoksa vurgulanan satıra tıklayıp Ayarlar’da atayın. Mesajı siz gönderirsiniz.',
    'hi': 'चैट खोलें और अपनी भाषा में लिखें। तय किया गया बदलने का शॉर्टकट दबाएँ: बॉक्स का टेक्स्ट अनुवाद से बदल जाएगा। शॉर्टकट न हो तो हाइलाइट की पंक्ति पर क्लिक करके सेटिंग में तय करें। संदेश आप खुद भेजते हैं।',
    'id': 'Buka obrolan dan tulis dalam bahasa Anda. Tekan pintasan ganti yang ditetapkan: teks menjadi terjemahan. Jika belum ada pintasan, klik baris yang disorot untuk menetapkannya di Pengaturan. Anda sendiri yang mengirim pesan.',
}


def chat_shortcut_body(language):
    return _CHAT_SHORTCUT.get(language, _CHAT_SHORTCUT['en'])


def steps(language, reference):
    c = copy(language)
    existing = {action: (action, title, body) for action, title, body in reference}
    overrides = dict(zip(
        ('language', 'theme', 'replace_selection_select_all', 'chat_languages', 'companion_settings'),
        ((c[i], c[i + 1]) for i in range(0, 10, 2))))
    overrides['language_packages'] = ENGINES.get(language, ENGINES['en'])
    from engine_center import text as center_text
    overrides['language_packages'] = (center_text(language, 'title'),
        center_text(language, 'intro') + ' ' + center_text(language, 'base'))
    overrides['game_controls'] = (existing['game_controls'][1], DYNAMIC.get(language, DYNAMIC['en']))
    from image_input import attachment_text
    overrides['document_translation'] = (attachment_text(language, 'browse'), attachment_text(language, 'hint'))
    return [(action, *overrides[action]) if action in overrides else existing[action]
            for action in ORDER]
