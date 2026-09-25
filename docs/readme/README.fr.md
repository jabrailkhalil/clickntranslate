# Click'n'Translate

OCR et traduction d’écran gratuits et open source pour **Windows, Linux et macOS**. Extrayez le texte des applications, images et jeux, traduisez une sélection ou suivez le texte qui change dans plusieurs zones de l’écran.

[English](../../README.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · [Español](README.es.md) · **Français**

![Trois façons d’utiliser Click'n'Translate](../images/how-it-works.png)

## Télécharger la version 1.8.1

| Système | Téléchargement | Utilisation |
| --- | --- | --- |
| Windows x64 | [Installateur (.exe)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.1/Click-n-Translate-1.8.1-windows-x64-installer.exe) | Installation classique sur Windows 10/11, x64. |
| Windows x64 | [Portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.1/Click-n-Translate-1.8.1-windows-portable-x64.zip) | Sans installation ; extrayez l’archive entière. |
| Linux x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.1/Click-n-Translate-1.8.1-linux-x86_64.AppImage) | Application en un fichier pour Linux x86_64 ; autorisez son exécution. |
| Mac — Apple Silicon | [DMG (M1+)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.1/Click-n-Translate-1.8.1-macos-arm64.dmg) | Installation sur Apple Silicon (M1 ou plus récent), avec macOS 13.4 ou plus récent. |
| Mac — Intel | [DMG (Intel)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.1/Click-n-Translate-1.8.1-macos-x86_64.dmg) | Installation sur Mac Intel (x86_64), avec macOS 13.4 ou plus récent. |

[Tous les téléchargements, sommes SHA-256 et signatures](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.1).

Les versions Windows et macOS utilisent actuellement un **certificat autosigné nommé `jabrailkhalil`**. Windows peut afficher un avertissement SmartScreen. L’application Mac ne dispose pas encore d’un Developer ID Apple ni de notarisation ; Gatekeeper peut donc bloquer son premier lancement. Des signatures OpenPGP séparées sont disponibles pour Linux. Choisissez **Apple Silicon** pour les puces M1 ou plus récentes, ou **Intel** pour les Mac Intel.

**Mises à jour :** Windows se met à jour depuis l’application. Sur macOS et Linux, téléchargez le nouveau DMG/AppImage et remplacez l’application manuellement, en conservant vos données.

## Fonctionnalités

- OCR à l’écran, traduction de sélection, superposition plein écran et traduction dynamique de plusieurs zones.
- Traduction en ligne et OCR local ; traduction hors ligne après téléchargement des modèles linguistiques.
- Traduction de documents, raccourcis personnalisables et compagnon de bureau.
- Thèmes clair et sombre, six langues d’interface et préférences de fenêtre propres à chaque mode.
- **1.8.0 :** accueil commun, menus de langues plus clairs, superpositions dynamiques améliorées, aide aux autorisations Mac et barres de défilement fines dans toute l’application.

L’espace de documents ouvre `.txt`, `.md`, `.docx`, `.pdf`, `.html`, `.htm` et `.rtf`. Modifiez l’original et la traduction côte à côte, ou masquez l’original pour réduire la fenêtre. Les paramètres proposent l’import/export des préférences et des historiques locaux facultatifs.

## Démonstration

### Traduire le texte des jeux

![Traduire le texte des jeux](../images/translation-demo-v2.gif)

### Copier le texte de n’importe quelle zone

![Copier le texte de n’importe quelle zone](../images/area-ocr-demo-v2.gif)

### Traduire une sélection dans une application

![Traduire une sélection dans une application](../images/selected-text-demo-v2.gif)

### Traduire tout l’écran

![Traduire tout l’écran](../images/fullscreen-translation-demo-v2.gif)

### Mettre à jour en un clic (Windows)

![Mettre à jour en un clic (Windows)](../images/update-demo.gif)

## Compagnon de bureau

Vous préférez cliquer plutôt que mémoriser des raccourcis ? Cliquez sur la mascotte pour traduire une zone ou tout l’écran, reconnaître et copier du texte, ouvrir le traducteur, lancer la traduction dynamique ou traduire un document. Vous pouvez la masquer quand vous n’en avez pas besoin.

| Thème clair | Thème sombre |
| --- | --- |
| ![Thème clair](../images/mascot-light.png) | ![Thème sombre](../images/mascot-dark.png) |

## Traduction dynamique

Sélectionnez une ou plusieurs zones de l’écran et les langues. La traduction suit les changements du texte et s’affiche sur l’original ou dans une zone séparée.

Exemple de configuration : le cadre violet délimite la zone à lire, le cadre vert une zone séparée pour la traduction.

<img src="../images/dynamic-translation-regions.png" alt="Exemple de configuration : le cadre violet délimite la zone à lire, le cadre vert une zone séparée pour la traduction." width="760">

## Raccourcis clavier

| Raccourci par défaut | Action |
| --- | --- |
| `Ctrl + Alt + C` | Extraire le texte d'une zone et le copier |
| `Ctrl + Alt + T` | Capturer une zone, reconnaître le texte et le traduire |
| `Ctrl + Alt + F` | Traduire l'écran entier |
| `Ctrl + Alt + Q` | Traduire le texte sélectionné dans l'application active |
| `Ctrl + Shift + Q` | Remplacer le texte sélectionné par sa traduction |
| `Ctrl + Shift + Space` | Afficher ou masquer Click'n'Translate |
| `Ctrl + Alt + G` | Démarrer ou arrêter la traduction dynamique des zones choisies |

Tous les raccourcis peuvent être modifiés ou effacés dans **Paramètres → Configurer les raccourcis**. Les paires de langues sont mémorisées séparément pour l'OCR, la sélection, le remplacement, le plein écran et la traduction dynamique.

Le tableau indique les raccourcis Windows. Sur **macOS**, utilisez **Command** à la place de Ctrl et **Option** à la place de Alt. Sur **Linux**, associez les commandes dans les paramètres du bureau : [guide Linux](../LINUX.md).

## Moteurs de traduction et d’OCR

| Type | Moteurs | Idéal pour |
| --- | --- | --- |
| Traduction en ligne | Google, MyMemory, Lingva, LibreTranslate | Traduction rapide sans télécharger de modèle |
| Traduction hors ligne | Argos Translate, Hy-MT | Traduction privée après l'installation des paquets choisis |
| OCR | Windows OCR / Apple Vision, Tesseract, RapidOCR, EasyOCR | Extraction de texte pour différents alphabets et types d'images |

Dans **Paramètres → Paquets de langues**, installez ou supprimez moteurs OCR, langues et modèles de traduction hors ligne. Seuls les paquets choisis sont téléchargés ; les moteurs locaux installés fonctionnent sans internet. L’OCR natif utilise Windows OCR sur Windows et Apple Vision sur macOS. La disponibilité des traducteurs en ligne dépend du service.

## Premiers pas

1. Téléchargez le fichier adapté à votre système et ouvrez l’application. Python est inclus.
2. Choisissez le moteur OCR, le service de traduction et les langues dans les paramètres. Téléchargez des modèles pour la traduction hors ligne.
3. Choisissez une capture ou une traduction. Sur Mac, suivez les indications pour autoriser l’**enregistrement de l’écran** et l’**accessibilité**. Sur Linux, configurez les raccourcis du bureau avec le [guide Linux](../LINUX.md).

L’OCR fonctionne localement. La traduction en ligne envoie le texte au service choisi ; utilisez un moteur hors ligne pour une traduction locale. Voir [Confidentialité](../../PRIVACY.md).

## Aide et développement

[Linux](../LINUX.md) · [macOS et compilation](../MACOS.md) · [Signaler un problème](https://github.com/jabrailkhalil/clickntranslate/issues) · [Licence GPL-3.0](../../LICENSE)

Pour un diagnostic, ouvrez **Aide → Rapport de bug** et joignez le ZIP créé au signalement. Il exclut le texte du presse-papiers, le contenu des documents, les historiques et les identifiants.

Click’n’Translate est gratuit. S’il vous aide, merci de [mettre une étoile au projet sur GitHub](https://github.com/jabrailkhalil/clickntranslate) et de [nous rejoindre sur Telegram](https://t.me/jabrail_digital).
