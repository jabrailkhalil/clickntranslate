// Shared by the website and the generated installation guides in docs/guides.
export const setup = {
  en: {
    title: "Install and start translating",
    lead: "First launch on Windows and Mac, step by step.",
    trust:
      "Current builds use the self-signed jabrailkhalil identity. It is not a publicly trusted Windows certificate or an Apple Developer ID; the Mac app is not notarized. You do not need to install the author's certificate or sign the app yourself.",
    official: "Official downloads and checksums",
    windows: "Windows: installation, SmartScreen and Defender",
    windowsSteps: [
      [
        "Install or extract",
        "Download from this site or jabrailkhalil/clickntranslate on GitHub. Run the installer, or extract the entire Portable ZIP into its own folder and open ClicknTranslate.exe. Keep the app folder beside it. Python is included.",
      ],
      [
        "If SmartScreen blocks the first launch",
        "For the expected official file that you trust, choose More info → Run anyway in the Windows protected your PC dialog, if available. This reputation warning is different from an antivirus detection.",
      ],
      [
        "If Defender quarantined a file",
        "Open Windows Security → Virus & threat protection → Protection history. Check the detected file's path and threat name. Update security intelligence and scan again. Only if you have verified the official file and are confident it is a false positive, choose Restore. If Defender detects it again, open that event and choose Allow on device. These actions can require administrator approval.",
      ],
      [
        "If you cannot allow the app",
        "Smart App Control or an organisation's policy may prevent an exception. Contact your administrator or report the block to the project. Keep antivirus protection enabled; do not exclude Downloads, a whole drive or all applications.",
      ],
    ],
    windowsNote:
      "A self-signed certificate or a matching checksum does not prove that a malware alert is false. Report recurring detections with the app version, filename, SHA-256 and exact threat name so the affected build can be investigated.",
    macos: "Mac: first launch and permissions",
    macSteps: [
      [
        "Choose your Mac and install",
        "In Apple menu → About This Mac, check the chip or processor. Choose Apple Silicon for M1 and newer, or Intel for Intel Macs. Open the DMG and drag ClicknTranslate.app into Applications. Launch that copy, not the copy inside the DMG.",
      ],
      [
        "Try opening the app once",
        "If macOS says the developer cannot be verified or Apple cannot check the app, dismiss the warning with Done or Cancel. This attempt makes the approval control available in Settings.",
      ],
      [
        "Approve this app",
        "Open System Settings → Privacy & Security, scroll to Security and choose Open Anyway for ClicknTranslate. Authenticate if asked, then confirm Open in the next warning. Only approve the official download you trust.",
      ],
      [
        "Allow screen capture",
        "After the welcome screen, use Enable beside Screen Recording in the app's Mac setup dialog. In Privacy & Security → Screen Recording (or Screen & System Audio Recording), enable ClicknTranslate. This allows OCR to read the screen. If needed, use + to select /Applications/ClicknTranslate.app; otherwise trigger a screen capture to request access.",
      ],
      [
        "Allow selected-text actions",
        "Use Enable beside Accessibility, or open Privacy & Security → Accessibility. Enable the same installed ClicknTranslate.app so the app can copy and replace text in other applications. This is a separate permission from screen recording.",
      ],
      [
        "Restart and return",
        "Accept Quit & Reopen if macOS offers it. Otherwise choose Quit from the app's menu-bar icon, then reopen it from Applications. Closing only the window can leave it running. Return to the setup dialog and click Check again → Continue.",
      ],
    ],
    macNote:
      "An old copy can remain in the permission list after replacement. If access still fails, quit the app, remove only its outdated entry with − where available, then add the copy in Applications with + and enable it. Do not remove permissions for other apps.",
    macWarning:
      "If macOS says the app is damaged or will damage your computer, do not treat that as an unidentified-developer warning. Download it again from the official release, compare its checksum and report the exact message. This guide does not require disabling Gatekeeper, clearing quarantine in Terminal or re-signing the app.",
    use: "Your first translation",
    useText:
      "Choose the source and target languages, then click the companion → Translate area and draw a box around text. Or press Ctrl + Alt + T on Windows, Command + Option + T on Mac. Enable the companion in Settings if it is hidden. Online translation needs internet; offline translation needs language models downloaded beforehand.",
    verify: "Check the file before allowing it",
    verifyText:
      "Compare the downloaded file's SHA-256 with the checksum for that exact file and version in the official release's verification archive or .sha256 file. A match checks file integrity, not antivirus approval. Replace the example path below with your downloaded installer or DMG.",
    help: "Still blocked? Report the exact message",
    sources: "Apple and Microsoft instructions",
    sourceLabels: [
      "Opening an unverified Mac app",
      "Mac screen recording permission",
      "Mac Accessibility permission",
      "Windows protection history",
      "Windows SmartScreen reputation",
    ],
  },
  ru: {
    title: "Установка и первый запуск",
    lead: "Что нажать в Windows и на Mac — по порядку.",
    trust:
      "В текущих сборках используется самоподписанная подпись jabrailkhalil. Это не общедоверенный сертификат Windows и не Apple Developer ID; нотариализации Apple пока нет. Устанавливать сертификат автора или самостоятельно подписывать приложение не нужно.",
    official: "Официальные загрузки и контрольные суммы",
    windows: "Windows: установка, SmartScreen и Defender",
    windowsSteps: [
      [
        "Установите или распакуйте",
        "Скачайте приложение с этого сайта или из jabrailkhalil/clickntranslate на GitHub. Запустите установщик либо полностью распакуйте Portable ZIP в отдельную папку и откройте ClicknTranslate.exe. Папка app должна оставаться рядом. Python уже включён.",
      ],
      [
        "Если SmartScreen не даёт запустить",
        "Для ожидаемого официального файла, которому вы доверяете, в окне «Система Windows защитила ваш компьютер» нажмите «Подробнее» → «Выполнить в любом случае», если эта кнопка доступна. Предупреждение о репутации и обнаружение угрозы антивирусом — разные ситуации.",
      ],
      [
        "Если Defender поместил файл в карантин",
        "Откройте «Безопасность Windows» → «Защита от вирусов и угроз» → «Журнал защиты». Проверьте путь к файлу и название угрозы. Обновите базы защиты и повторите проверку. Только если вы проверили официальный файл и уверены в ложном срабатывании, выберите «Восстановить». Если Defender снова обнаружит его, откройте новое событие и выберите «Разрешить на устройстве». Может потребоваться подтверждение администратора.",
      ],
      [
        "Если разрешить запуск не получается",
        "Smart App Control или политика организации могут запрещать исключение. Обратитесь к администратору или сообщите о блокировке в проект. Оставьте антивирус включённым; не исключайте из проверки «Загрузки», весь диск или все приложения.",
      ],
    ],
    windowsNote:
      "Самоподписанный сертификат и совпадение контрольной суммы не доказывают, что обнаружение угрозы ложное. При повторной блокировке пришлите версию приложения, имя файла, SHA-256 и точное название угрозы — это поможет проверить конкретную сборку.",
    macos: "Mac: разрешение запуска и доступ к экрану",
    macSteps: [
      [
        "Выберите свою версию и установите",
        "В меню Apple → «Об этом Mac» посмотрите чип или процессор. Для M1 и новее скачайте Apple Silicon, для Intel — Intel. Откройте DMG и перетащите ClicknTranslate.app в «Программы» (Applications). Запускайте эту копию, а не приложение внутри DMG.",
      ],
      [
        "Один раз попробуйте открыть приложение",
        "Если macOS сообщает, что разработчик не проверен или Apple не может проверить приложение, закройте предупреждение кнопкой «Готово» или «Отмена». После попытки запуска в настройках появляется возможность его разрешить.",
      ],
      [
        "Подтвердите запуск этого приложения",
        "Откройте «Системные настройки» → «Конфиденциальность и безопасность», прокрутите до раздела «Безопасность» и нажмите «Всё равно открыть» / «Подтвердить вход» (Open Anyway) для ClicknTranslate. При необходимости введите пароль или используйте Touch ID, затем в следующем предупреждении нажмите «Открыть». Разрешайте только официальный файл, которому доверяете.",
      ],
      [
        "Включите запись экрана",
        "После приветственного окна нажмите «Включить» рядом с «Запись экрана» в окне «Подготовим перевод на Mac». В разделе «Конфиденциальность и безопасность» → «Запись экрана» или «Запись экрана и системного аудио» включите ClicknTranslate. Это нужно OCR для чтения экрана. При необходимости через + выберите /Applications/ClicknTranslate.app; если добавить вручную нельзя, запустите захват экрана для запроса доступа.",
      ],
      [
        "Включите универсальный доступ",
        "Нажмите «Включить» рядом с «Универсальный доступ» либо откройте «Конфиденциальность и безопасность» → «Универсальный доступ». Включите тот же установленный ClicknTranslate.app: это разрешение нужно для копирования и замены выделенного текста в других приложениях. Оно выдаётся отдельно от записи экрана.",
      ],
      [
        "Перезапустите и вернитесь в приложение",
        "Если macOS предлагает «Завершить и открыть снова», согласитесь. Иначе выберите «Выйти» в меню значка приложения в верхней строке Mac и снова откройте его из «Программ». Закрытие одного окна может оставить приложение работающим. В окне настройки нажмите «Проверить снова» → «Продолжить».",
      ],
    ],
    macNote:
      "После замены версии в списке разрешений может остаться старая копия. Если доступ всё ещё не работает, завершите приложение, удалите только его устаревшую запись кнопкой −, если она доступна, и через + добавьте копию из «Программ», включив переключатель. Разрешения других приложений не меняйте.",
    macWarning:
      "Сообщения «приложение повреждено» и «повредит ваш компьютер» не равнозначны предупреждению о непроверенном разработчике. Скачайте файл заново из официального релиза, сравните контрольную сумму и сообщите точный текст ошибки. Отключать Gatekeeper, снимать карантин через Терминал или заново подписывать приложение для этого гайда не требуется.",
    use: "Первый перевод",
    useText:
      "Выберите языки оригинала и перевода, нажмите на маскота → «Перевести область» и обведите текст. Или используйте Ctrl + Alt + T в Windows, Command + Option + T на Mac. Если маскот скрыт, включите его в настройках. Для онлайн-перевода нужен интернет, для офлайн-перевода — заранее загруженные языковые модели.",
    verify: "Проверка файла перед разрешением запуска",
    verifyText:
      "Сравните SHA-256 скачанного файла с суммой именно для этого файла и версии в verification-архиве или .sha256 официального релиза. Совпадение подтверждает целостность файла, а не одобрение антивирусом. В командах ниже подставьте путь к своему установщику или DMG.",
    help: "Не запускается? Сообщить точный текст ошибки",
    sources: "Инструкции Apple и Microsoft",
    sourceLabels: [
      "Запуск непроверенного приложения на Mac",
      "Разрешение записи экрана на Mac",
      "Универсальный доступ на Mac",
      "Журнал защиты Windows",
      "Репутация Windows SmartScreen",
    ],
  },
  de: {
    title: "Installation und erster Start",
    lead: "Windows und Mac Schritt für Schritt einrichten.",
    trust:
      "Die aktuellen Builds sind mit der selbst signierten Identität jabrailkhalil signiert. Sie ist weder ein öffentlich vertrauenswürdiges Windows-Zertifikat noch eine Apple Developer ID; die Mac-App ist nicht notarisiert. Sie müssen weder das Zertifikat des Autors installieren noch die App selbst signieren.",
    official: "Offizielle Downloads und Prüfsummen",
    windows: "Windows: Installation, SmartScreen und Defender",
    windowsSteps: [
      [
        "Installieren oder entpacken",
        "Laden Sie die App hier oder aus jabrailkhalil/clickntranslate auf GitHub herunter. Starten Sie den Installer oder entpacken Sie das gesamte Portable-ZIP in einen eigenen Ordner und öffnen Sie ClicknTranslate.exe. Der Ordner app muss daneben bleiben. Python ist enthalten.",
      ],
      [
        "SmartScreen blockiert den Start",
        "Wenn Sie der offiziellen Datei vertrauen, wählen Sie in der SmartScreen-Warnung Weitere Informationen → Trotzdem ausführen, sofern verfügbar. Eine Reputationswarnung ist keine Virenerkennung.",
      ],
      [
        "Defender hat eine Datei isoliert",
        "Öffnen Sie Windows-Sicherheit → Viren- & Bedrohungsschutz → Schutzverlauf. Prüfen Sie Dateipfad und Bedrohungsname, aktualisieren Sie die Schutzdefinitionen und scannen Sie erneut. Nur wenn Sie die offizielle Datei überprüft haben und von einem Fehlalarm überzeugt sind, wählen Sie Wiederherstellen. Bei erneuter Erkennung öffnen Sie den neuen Eintrag und wählen Auf Gerät zulassen. Administratorrechte können erforderlich sein.",
      ],
      [
        "Keine Ausnahme möglich",
        "Smart App Control oder Unternehmensrichtlinien können den Start verhindern. Wenden Sie sich an den Administrator oder melden Sie die Blockierung. Lassen Sie den Virenschutz aktiv; nehmen Sie nicht den Downloadordner, ganze Laufwerke oder alle Apps von Prüfungen aus.",
      ],
    ],
    windowsNote:
      "Eine selbst signierte Datei oder passende Prüfsumme beweist keinen Fehlalarm. Melden Sie wiederholte Erkennungen mit Version, Dateiname, SHA-256 und genauem Bedrohungsnamen.",
    macos: "Mac: Start erlauben und Zugriffsrechte",
    macSteps: [
      [
        "Passende Version installieren",
        "Prüfen Sie Chip oder Prozessor unter Apple → Über diesen Mac. Wählen Sie Apple Silicon für M1 und neuer, sonst Intel für Intel-Macs. Öffnen Sie das DMG und ziehen Sie ClicknTranslate.app nach Programme. Starten Sie diese Kopie, nicht die im DMG.",
      ],
      [
        "Einmal zu öffnen versuchen",
        "Wenn macOS den Entwickler oder die App nicht überprüfen kann, schließen Sie die Warnung mit Fertig oder Abbrechen. Erst nach diesem Versuch erscheint die Freigabe in den Einstellungen.",
      ],
      [
        "Diese App freigeben",
        "Öffnen Sie Systemeinstellungen → Datenschutz & Sicherheit, scrollen Sie zu Sicherheit und wählen Sie Dennoch öffnen (Open Anyway) für ClicknTranslate. Bestätigen Sie gegebenenfalls mit Passwort oder Touch ID und anschließend mit Öffnen. Geben Sie nur den vertrauenswürdigen offiziellen Download frei.",
      ],
      [
        "Bildschirmaufnahme erlauben",
        "Klicken Sie nach dem Willkommensfenster im Einrichtungsdialog bei Bildschirmaufnahme auf Aktivieren. Schalten Sie ClicknTranslate unter Datenschutz & Sicherheit → Bildschirmaufnahme bzw. Bildschirm- & Systemaudioaufnahme ein. Wählen Sie bei Bedarf über + die Datei /Applications/ClicknTranslate.app; falls das nicht angeboten wird, starten Sie eine Bildschirmaufnahme in der App, um Zugriff anzufordern.",
      ],
      [
        "Bedienungshilfen erlauben",
        "Klicken Sie im Dialog bei Bedienungshilfen auf Aktivieren oder öffnen Sie Datenschutz & Sicherheit → Bedienungshilfen. Aktivieren Sie dieselbe installierte App. Diese separate Berechtigung ermöglicht das Kopieren und Ersetzen ausgewählten Texts in anderen Apps.",
      ],
      [
        "Neu starten",
        "Bestätigen Sie Beenden & erneut öffnen, wenn macOS dies anbietet. Sonst beenden Sie die App über ihr Menüleistensymbol und öffnen sie erneut aus Programme. Nur das Fenster zu schließen reicht möglicherweise nicht. Klicken Sie im Dialog auf Erneut prüfen → Weiter.",
      ],
    ],
    macNote:
      "Nach einem Update kann eine alte Kopie in der Berechtigungsliste stehen. Beenden Sie die App, entfernen Sie bei weiterhin fehlendem Zugriff nur ihren veralteten Eintrag mit −, sofern verfügbar, und fügen Sie die Kopie aus Programme mit + hinzu. Aktivieren Sie sie erneut.",
    macWarning:
      "Bei Meldungen wie beschädigt oder wird deinen Computer beschädigen laden Sie die offizielle Datei erneut herunter, vergleichen die Prüfsumme und melden den genauen Text. Das ist keine einfache Entwicklerwarnung. Gatekeeper muss für diese Anleitung nicht deaktiviert, die Quarantäne nicht im Terminal entfernt und die App nicht neu signiert werden.",
    use: "Die erste Übersetzung",
    useText:
      "Wählen Sie Ausgangs- und Zielsprache, klicken Sie auf das Maskottchen → Bereich übersetzen und markieren Sie Text. Alternativ: Ctrl + Alt + T unter Windows, Command + Option + T auf dem Mac. Ein ausgeblendetes Maskottchen lässt sich in den Einstellungen aktivieren. Online-Übersetzung braucht Internet; offline müssen Sprachmodelle vorher geladen sein.",
    verify: "Datei vor der Freigabe prüfen",
    verifyText:
      "Vergleichen Sie SHA-256 mit dem Wert für genau diese Datei und Version im offiziellen Verification-Archiv oder der .sha256-Datei. Die Übereinstimmung bestätigt Integrität, keine Virenschutzfreigabe. Ersetzen Sie den Beispielpfad durch Ihren Installer oder Ihr DMG.",
    help: "Blockierung mit genauer Meldung melden",
    sources: "Anleitungen von Apple und Microsoft",
    sourceLabels: [
      "Nicht verifizierte Mac-App öffnen",
      "Bildschirmaufnahme auf dem Mac",
      "Bedienungshilfen auf dem Mac",
      "Windows-Schutzverlauf",
      "Windows-SmartScreen-Reputation",
    ],
  },
  es: {
    title: "Instalación y primer inicio",
    lead: "Configura Windows y Mac paso a paso.",
    trust:
      "Las versiones actuales usan la identidad autofirmada jabrailkhalil. No es un certificado de confianza pública de Windows ni un Apple Developer ID; la app de Mac no está notarizada. No necesitas instalar el certificado del autor ni firmar la app por tu cuenta.",
    official: "Descargas oficiales y sumas de comprobación",
    windows: "Windows: instalación, SmartScreen y Defender",
    windowsSteps: [
      [
        "Instala o extrae",
        "Descarga desde este sitio o jabrailkhalil/clickntranslate en GitHub. Ejecuta el instalador o extrae todo el ZIP portable en una carpeta propia y abre ClicknTranslate.exe. Conserva la carpeta app a su lado. Python está incluido.",
      ],
      [
        "Si SmartScreen bloquea el inicio",
        "Para el archivo oficial en el que confías, elige Más información → Ejecutar de todas formas en la advertencia de SmartScreen, si aparece esa opción. Esta advertencia de reputación es distinta de una detección del antivirus.",
      ],
      [
        "Si Defender puso un archivo en cuarentena",
        "Abre Seguridad de Windows → Protección contra virus y amenazas → Historial de protección. Comprueba la ruta y el nombre de la amenaza, actualiza las definiciones y vuelve a analizar. Solo si verificaste el archivo oficial y estás seguro de que es un falso positivo, elige Restaurar. Si vuelve a detectarlo, abre el nuevo evento y elige Permitir en el dispositivo. Puede requerir autorización de administrador.",
      ],
      [
        "Si no puedes permitir la app",
        "Smart App Control o una política de tu organización pueden impedir una excepción. Consulta al administrador o informa del bloqueo al proyecto. Mantén activo el antivirus; no excluyas Descargas, unidades completas ni todas las aplicaciones.",
      ],
    ],
    windowsNote:
      "Una firma autofirmada o una suma coincidente no prueban que una alerta sea falsa. Comunica detecciones repetidas con la versión, nombre del archivo, SHA-256 y nombre exacto de la amenaza.",
    macos: "Mac: aprobar el inicio y los permisos",
    macSteps: [
      [
        "Elige tu versión e instala",
        "Mira el chip o procesador en Apple → Acerca de este Mac. Elige Apple Silicon para M1 o posterior, o Intel para Mac Intel. Abre el DMG y arrastra ClicknTranslate.app a Aplicaciones. Ejecuta esa copia, no la del DMG.",
      ],
      [
        "Intenta abrirla una vez",
        "Si macOS no puede verificar al desarrollador o comprobar la app, cierra el aviso con Aceptar o Cancelar. Ese intento permite que aparezca la opción de autorización en los ajustes.",
      ],
      [
        "Autoriza esta aplicación",
        "Ve a Ajustes del Sistema → Privacidad y seguridad, baja hasta Seguridad y pulsa Abrir igualmente (Open Anyway) para ClicknTranslate. Autentícate si se solicita y confirma Abrir en el siguiente aviso. Autoriza solo la descarga oficial en la que confías.",
      ],
      [
        "Permite grabar la pantalla",
        "Tras la bienvenida, pulsa Activar junto a Grabación de pantalla en el diálogo de configuración. En Privacidad y seguridad → Grabación de pantalla o Grabación de pantalla y audio del sistema, activa ClicknTranslate. Si hace falta, añade /Applications/ClicknTranslate.app con +; si no se ofrece esa opción, inicia una captura desde la app para solicitar acceso.",
      ],
      [
        "Permite accesibilidad",
        "Pulsa Activar junto a Accesibilidad o abre Privacidad y seguridad → Accesibilidad. Activa la misma app instalada. Este permiso independiente permite copiar y reemplazar texto seleccionado en otras aplicaciones.",
      ],
      [
        "Reinicia y vuelve",
        "Acepta Salir y volver a abrir si macOS lo ofrece. Si no, sal mediante el icono de la app en la barra de menús y ábrela desde Aplicaciones. Cerrar solo la ventana puede dejarla en ejecución. Pulsa Comprobar de nuevo → Continuar en el diálogo.",
      ],
    ],
    macNote:
      "Tras actualizar puede quedar una copia antigua en la lista. Si el acceso sigue fallando, cierra la app, elimina únicamente su entrada antigua con − cuando esté disponible y añade con + la copia de Aplicaciones. Activa el permiso otra vez.",
    macWarning:
      "Si aparece que la app está dañada o dañará tu ordenador, vuelve a descargarla del lanzamiento oficial, compara la suma y comunica el mensaje exacto. No es una simple advertencia de desarrollador. Esta guía no requiere desactivar Gatekeeper, quitar la cuarentena en Terminal ni volver a firmar la app.",
    use: "Tu primera traducción",
    useText:
      "Elige los idiomas, pulsa la mascota → Traducir área y marca el texto. También puedes usar Ctrl + Alt + T en Windows o Command + Option + T en Mac. Activa la mascota en Ajustes si está oculta. La traducción en línea requiere internet; sin conexión, descarga antes los modelos de idiomas.",
    verify: "Comprueba el archivo antes de permitirlo",
    verifyText:
      "Compara SHA-256 con el valor de ese archivo y versión en el archivo verification o .sha256 del lanzamiento oficial. La coincidencia comprueba integridad, no aprobación del antivirus. Sustituye la ruta de ejemplo por tu instalador o DMG.",
    help: "Comunicar el bloqueo y el mensaje exacto",
    sources: "Instrucciones de Apple y Microsoft",
    sourceLabels: [
      "Abrir una app no verificada en Mac",
      "Grabación de pantalla en Mac",
      "Accesibilidad en Mac",
      "Historial de protección de Windows",
      "Reputación de Windows SmartScreen",
    ],
  },
  fr: {
    title: "Installation et premier lancement",
    lead: "Configurer Windows et Mac, étape par étape.",
    trust:
      "Les versions actuelles utilisent l’identité autosignée jabrailkhalil. Ce n’est ni un certificat Windows publiquement reconnu ni un Apple Developer ID ; l’app Mac n’est pas notariée. Vous n’avez pas à installer le certificat de l’auteur ni à signer vous-même l’app.",
    official: "Téléchargements officiels et sommes de contrôle",
    windows: "Windows : installation, SmartScreen et Defender",
    windowsSteps: [
      [
        "Installer ou extraire",
        "Téléchargez depuis ce site ou jabrailkhalil/clickntranslate sur GitHub. Lancez l’installateur ou extrayez entièrement le ZIP portable dans son propre dossier, puis ouvrez ClicknTranslate.exe. Gardez le dossier app à côté. Python est inclus.",
      ],
      [
        "Si SmartScreen bloque le lancement",
        "Pour le fichier officiel auquel vous faites confiance, choisissez Informations complémentaires → Exécuter quand même dans l’avertissement SmartScreen, si cette option existe. Une alerte de réputation est différente d’une détection antivirus.",
      ],
      [
        "Si Defender a mis un fichier en quarantaine",
        "Ouvrez Sécurité Windows → Protection contre les virus et menaces → Historique de protection. Vérifiez le chemin et le nom de la menace, actualisez les définitions et relancez l’analyse. Seulement après avoir vérifié le fichier officiel et si vous êtes certain d’un faux positif, choisissez Restaurer. En cas de nouvelle détection, ouvrez l’événement et choisissez Autoriser sur l’appareil. Un accord administrateur peut être nécessaire.",
      ],
      [
        "Si aucune exception n’est possible",
        "Smart App Control ou une politique d’entreprise peut bloquer l’app. Contactez l’administrateur ou signalez le blocage au projet. Gardez l’antivirus actif ; n’excluez pas Téléchargements, un disque entier ou toutes les applications.",
      ],
    ],
    windowsNote:
      "Une signature autosignée ou une somme identique ne prouve pas qu’une alerte est fausse. Signalez les détections répétées avec la version, le fichier, SHA-256 et le nom exact de la menace.",
    macos: "Mac : autoriser le lancement et les accès",
    macSteps: [
      [
        "Choisir la version et installer",
        "Vérifiez la puce ou le processeur dans Apple → À propos de ce Mac. Choisissez Apple Silicon pour M1 et plus récent, ou Intel pour les Mac Intel. Ouvrez le DMG et glissez ClicknTranslate.app dans Applications. Lancez cette copie, pas celle du DMG.",
      ],
      [
        "Essayer de l’ouvrir une fois",
        "Si macOS ne peut pas vérifier le développeur ou contrôler l’app, fermez l’alerte avec Terminé ou Annuler. Cette tentative fait apparaître l’autorisation dans les réglages.",
      ],
      [
        "Autoriser cette app",
        "Ouvrez Réglages Système → Confidentialité et sécurité, descendez jusqu’à Sécurité et choisissez Ouvrir quand même (Open Anyway) pour ClicknTranslate. Authentifiez-vous si nécessaire, puis confirmez Ouvrir. N’autorisez que le téléchargement officiel auquel vous faites confiance.",
      ],
      [
        "Autoriser l’enregistrement de l’écran",
        "Après l’accueil, cliquez sur Activer à côté d’Enregistrement de l’écran dans le dialogue de configuration. Activez ClicknTranslate dans Confidentialité et sécurité → Enregistrement de l’écran ou Enregistrement de l’écran et de l’audio du système. Au besoin, ajoutez /Applications/ClicknTranslate.app avec + ; sinon, lancez une capture depuis l’app pour demander l’accès.",
      ],
      [
        "Autoriser l’accessibilité",
        "Cliquez sur Activer à côté d’Accessibilité, ou ouvrez Confidentialité et sécurité → Accessibilité. Activez la même app installée. Cette autorisation distincte sert à copier et remplacer du texte sélectionné dans d’autres apps.",
      ],
      [
        "Redémarrer et revenir",
        "Acceptez Quitter et rouvrir si macOS le propose. Sinon, quittez via l’icône de l’app dans la barre des menus, puis rouvrez-la depuis Applications. Fermer seulement la fenêtre peut la laisser active. Cliquez sur Vérifier à nouveau → Continuer dans le dialogue.",
      ],
    ],
    macNote:
      "Après une mise à jour, une ancienne copie peut rester dans la liste. Si l’accès échoue encore, quittez l’app, supprimez uniquement son ancienne entrée avec − si disponible, puis ajoutez la copie d’Applications avec + et activez-la.",
    macWarning:
      "Si macOS indique que l’app est endommagée ou endommagera votre ordinateur, téléchargez à nouveau la version officielle, comparez la somme et signalez le message exact. Ce n’est pas une simple alerte de développeur. Ce guide ne demande ni de désactiver Gatekeeper, ni de supprimer la quarantaine dans Terminal, ni de signer à nouveau l’app.",
    use: "Votre première traduction",
    useText:
      "Choisissez les langues, cliquez sur la mascotte → Traduire une zone et encadrez le texte. Ou utilisez Ctrl + Alt + T sous Windows, Command + Option + T sur Mac. Activez la mascotte dans les réglages si elle est masquée. La traduction en ligne nécessite internet ; hors ligne, téléchargez d’abord les modèles linguistiques.",
    verify: "Vérifier le fichier avant de l’autoriser",
    verifyText:
      "Comparez SHA-256 avec la valeur de ce fichier et de cette version dans l’archive verification ou le fichier .sha256 officiel. Cela vérifie l’intégrité, pas une approbation antivirus. Remplacez le chemin d’exemple par celui de votre installateur ou DMG.",
    help: "Signaler le blocage avec son message exact",
    sources: "Instructions Apple et Microsoft",
    sourceLabels: [
      "Ouvrir une app Mac non vérifiée",
      "Enregistrement de l’écran sur Mac",
      "Accessibilité sur Mac",
      "Historique de protection Windows",
      "Réputation Windows SmartScreen",
    ],
  },
  "zh-CN": {
    title: "安装与首次启动",
    lead: "按步骤设置 Windows 和 Mac。",
    trust:
      "当前版本使用 jabrailkhalil 自签名身份。它不是 Windows 公开信任的证书，也不是 Apple Developer ID；Mac 应用尚未经过 Apple 公证。你不需要安装作者的证书，也不需要自行给应用签名。",
    official: "官方下载与校验和",
    windows: "Windows：安装、SmartScreen 与 Defender",
    windowsSteps: [
      [
        "安装或完整解压",
        "从本网站或 GitHub 的 jabrailkhalil/clickntranslate 下载。运行安装程序，或将 Portable ZIP 完整解压到单独文件夹后打开 ClicknTranslate.exe。保留旁边的 app 文件夹。已包含 Python。",
      ],
      [
        "SmartScreen 阻止启动时",
        "确认是你信任的官方文件后，在“Windows 已保护你的电脑”提示中选择“更多信息”→“仍要运行”（如果提供）。信誉警告与杀毒软件检测到威胁是两回事。",
      ],
      [
        "Defender 隔离了文件时",
        "打开“Windows 安全中心”→“病毒和威胁防护”→“保护历史记录”。核对文件路径和威胁名称，更新安全情报后重新扫描。只有验证了官方文件并确信是误报时，才选择“还原”。如果再次检测到它，打开新的记录并选择“允许在设备上”。可能需要管理员授权。",
      ],
      [
        "无法允许应用时",
        "智能应用控制或组织策略可能不允许例外。联系管理员或向项目报告阻止信息。保持杀毒防护开启，不要排除整个“下载”文件夹、磁盘或所有应用。",
      ],
    ],
    windowsNote:
      "自签名证书或相同校验和不能证明威胁检测是误报。请提供应用版本、文件名、SHA-256 和准确的威胁名称，以便调查反复出现的检测。",
    macos: "Mac：允许启动并授予权限",
    macSteps: [
      [
        "选择版本并安装",
        "在 Apple 菜单→“关于本机”中查看芯片或处理器。M1 及更新芯片选择 Apple Silicon，Intel Mac 选择 Intel。打开 DMG，将 ClicknTranslate.app 拖入“应用程序”。启动安装后的副本，不要运行 DMG 内的副本。",
      ],
      [
        "先尝试打开一次",
        "如果 macOS 提示无法验证开发者或 Apple 无法检查应用，请点“完成”或“取消”关闭提示。尝试打开后，设置中才会出现允许打开的选项。",
      ],
      [
        "允许此应用启动",
        "打开“系统设置”→“隐私与安全性”，向下滚动至“安全性”，为 ClicknTranslate 选择“仍要打开”（Open Anyway）。按提示验证身份，并在下一次提示中点“打开”。只允许你信任的官方下载文件。",
      ],
      [
        "允许屏幕录制",
        "欢迎窗口之后，在 Mac 设置对话框中点击“屏幕录制”旁的“启用”。在“隐私与安全性”→“屏幕录制”或“屏幕与系统音频录制”中启用 ClicknTranslate，以便 OCR 读取屏幕。必要时用 + 添加 /Applications/ClicknTranslate.app；如果无法手动添加，在应用中启动屏幕捕获以请求权限。",
      ],
      [
        "允许辅助功能",
        "点击“辅助功能”旁的“启用”，或进入“隐私与安全性”→“辅助功能”。启用同一个已安装的应用，以便复制、替换其他应用中的选中文本。这与屏幕录制是两个独立权限。",
      ],
      [
        "重启并返回",
        "如果 macOS 提示“退出并重新打开”，请确认。否则从菜单栏中的应用图标选择退出，再从“应用程序”打开。只关闭窗口可能不会退出应用。回到设置对话框，点击“重新检查”→“继续”。",
      ],
    ],
    macNote:
      "升级后权限列表可能仍有旧副本。若权限仍无效，退出应用，仅用 − 移除它的旧条目（如可用），再用 + 添加“应用程序”中的副本并启用。不要修改其他应用的权限。",
    macWarning:
      "如果提示应用已损坏或将损坏电脑，不要当作普通开发者警告忽略。重新从官方发布页下载、核对校验和并报告完整提示。本指南不需要禁用 Gatekeeper、通过终端移除隔离属性或重新签名。",
    use: "开始第一次翻译",
    useText:
      "选择源语言和目标语言，点击吉祥物→翻译区域，再框选文字。也可使用 Windows 的 Ctrl + Alt + T 或 Mac 的 Command + Option + T。如果吉祥物隐藏了，可在设置中启用。在线翻译需要网络，离线翻译需要事先下载语言模型。",
    verify: "允许之前核对文件",
    verifyText:
      "将下载文件的 SHA-256 与官方发布的 verification 压缩包或 .sha256 文件中相同版本、相同文件的值比较。匹配仅确认完整性，不代表杀毒软件认可。请将示例路径替换为你的安装程序或 DMG 路径。",
    help: "仍被阻止？报告完整提示",
    sources: "Apple 与 Microsoft 说明",
    sourceLabels: [
      "打开未经验证的 Mac 应用",
      "Mac 屏幕录制权限",
      "Mac 辅助功能权限",
      "Windows 保护历史记录",
      "Windows SmartScreen 信誉",
    ],
  },
};

export const setupSources = [
  "https://support.apple.com/en-us/102445",
  "https://support.apple.com/guide/mac-help/mchld6aa7d23/mac",
  "https://support.apple.com/guide/mac-help/mh43185/mac",
  "https://support.microsoft.com/en-us/windows/security/windows-security/protection-history-in-the-windows-security-app",
  "https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation",
];
