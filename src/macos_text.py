"""Messages for the native macOS features in every supported interface language."""

TEXT = {
    'en': {
        'title': 'macOS permission', 'open': 'Open Settings', 'later': 'Later',
        'screen': 'Allow Click’n’Translate in System Settings → Privacy & Security → Screen Recording. This is needed to recognize text on your screen.',
        'accessibility': 'Allow Click’n’Translate in System Settings → Privacy & Security → Accessibility. This is needed to copy and replace selected text in other apps.',
        'retry': 'Then retry the action. Restart the app if macOS asks you to.',
        'python': 'When running the Python version, macOS may list Python or Terminal instead of the app.',
        'vision_note': 'Built into macOS. Languages are managed by the system; no package download is needed.',
    },
    'ru': {
        'title': 'Разрешение macOS', 'open': 'Открыть настройки', 'later': 'Позже',
        'screen': 'Разрешите Click’n’Translate запись экрана в настройках macOS → Конфиденциальность и безопасность. Это нужно для распознавания текста на экране.',
        'accessibility': 'Разрешите Click’n’Translate универсальный доступ в настройках macOS → Конфиденциальность и безопасность. Это нужно для копирования и замены выделенного текста в других приложениях.',
        'retry': 'После разрешения повторите действие. Если macOS попросит — перезапустите приложение.',
        'python': 'При запуске Python-версии в списке macOS может быть Python или Terminal вместо названия приложения.',
        'vision_note': 'Встроенное распознавание macOS. Языки обслуживаются системой; скачивать пакеты не нужно.',
    },
    'de': {
        'title': 'macOS-Berechtigung', 'open': 'Einstellungen öffnen', 'later': 'Später',
        'screen': 'Erlauben Sie Click’n’Translate die Bildschirmaufnahme unter Systemeinstellungen → Datenschutz & Sicherheit. Sie wird benötigt, um Bildschirmtext zu erkennen.',
        'accessibility': 'Erlauben Sie Click’n’Translate die Bedienungshilfen unter Systemeinstellungen → Datenschutz & Sicherheit, um ausgewählten Text in anderen Apps zu kopieren und zu ersetzen.',
        'retry': 'Versuchen Sie die Aktion danach erneut. Starten Sie die App neu, falls macOS Sie dazu auffordert.',
        'python': 'Bei der Python-Version kann macOS stattdessen Python oder Terminal anzeigen.',
        'vision_note': 'In macOS integriert. Die Sprachen werden vom System verwaltet; kein Paketdownload nötig.',
    },
    'es': {
        'title': 'Permiso de macOS', 'open': 'Abrir ajustes', 'later': 'Más tarde',
        'screen': 'Permite la grabación de pantalla a Click’n’Translate en Ajustes del Sistema → Privacidad y seguridad para reconocer el texto de la pantalla.',
        'accessibility': 'Permite el acceso de accesibilidad a Click’n’Translate en Ajustes del Sistema → Privacidad y seguridad para copiar y reemplazar texto seleccionado en otras apps.',
        'retry': 'Después, repite la acción. Reinicia la app si macOS lo solicita.',
        'python': 'Con la versión Python, macOS puede mostrar Python o Terminal en lugar de la app.',
        'vision_note': 'Integrado en macOS. El sistema gestiona los idiomas; no hay que descargar paquetes.',
    },
    'fr': {
        'title': 'Autorisation macOS', 'open': 'Ouvrir les réglages', 'later': 'Plus tard',
        'screen': 'Autorisez l’enregistrement de l’écran pour Click’n’Translate dans Réglages Système → Confidentialité et sécurité afin de reconnaître le texte affiché.',
        'accessibility': 'Autorisez l’accessibilité pour Click’n’Translate dans Réglages Système → Confidentialité et sécurité afin de copier et remplacer le texte sélectionné dans d’autres apps.',
        'retry': 'Réessayez ensuite. Redémarrez l’app si macOS le demande.',
        'python': 'Avec la version Python, macOS peut afficher Python ou Terminal à la place de l’app.',
        'vision_note': 'Intégré à macOS. Les langues sont gérées par le système ; aucun téléchargement de module requis.',
    },
    'zh': {
        'title': 'macOS 权限', 'open': '打开设置', 'later': '稍后',
        'screen': '请在系统设置 → 隐私与安全性中允许 Click’n’Translate 录制屏幕，以识别屏幕上的文字。',
        'accessibility': '请在系统设置 → 隐私与安全性中允许 Click’n’Translate 使用辅助功能，以复制和替换其他应用中选中的文字。',
        'retry': '授权后请重试。如果 macOS 提示，请重启应用。',
        'python': '运行 Python 版本时，macOS 可能会显示 Python 或 Terminal，而不是应用名称。',
        'vision_note': 'macOS 内置识别。语言由系统管理，无需下载语言包。',
    },
}


def macos_text(language, key):
    return TEXT.get(language, TEXT['en'])[key]
