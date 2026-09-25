# Click'n'Translate

OCR et traduction d’écran gratuits et open source pour **Windows, Linux et macOS**. Extrayez le texte des applications, images et jeux, traduisez une sélection ou suivez le texte qui change dans plusieurs zones de l’écran.

[English](../../README.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · [Español](README.es.md) · **Français**

## Télécharger la version 1.8.0

| Système | Téléchargement | Utilisation |
| --- | --- | --- |
| Windows x64 | [Installateur (.exe)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-windows-x64-installer.exe) | Installation classique sur Windows 10/11, x64. |
| Windows x64 | [Portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-windows-portable-x64.zip) | Sans installation ; extrayez l’archive entière. |
| Linux x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-linux-x86_64.AppImage) | Application en un fichier pour Linux x86_64 ; autorisez son exécution. |
| Linux x86_64 | [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-linux-x86_64.tar.gz) | Dossier de l’application pour Linux x86_64 ; à extraire avant utilisation. |
| macOS arm64 | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-macos-arm64.dmg) | Installation sur Apple Silicon (M1 ou plus récent), avec macOS 13.4 ou plus récent. |
| macOS arm64 | [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-macos-arm64.zip) | La même application Apple Silicon dans une archive ZIP. |

[Tous les téléchargements, sommes SHA-256 et signatures](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.0).

Les versions Windows et macOS utilisent actuellement un **certificat autosigné nommé `jabrailkhalil`**. Windows peut afficher un avertissement SmartScreen. L’application Mac ne dispose pas encore d’un Developer ID Apple ni de notarisation ; Gatekeeper peut donc bloquer son premier lancement. Des signatures OpenPGP séparées sont disponibles pour Linux. Cette version ne comprend pas de compilation pour Mac Intel.

## Fonctionnalités

- OCR à l’écran, traduction de sélection, superposition plein écran et traduction dynamique de plusieurs zones.
- Traduction en ligne et OCR local ; traduction hors ligne après téléchargement des modèles linguistiques.
- Traduction de documents, raccourcis personnalisables et compagnon de bureau.
- Thèmes clair et sombre, six langues d’interface et préférences de fenêtre propres à chaque mode.
- **1.8.0 :** accueil commun, menus de langues plus clairs, superpositions dynamiques améliorées, aide aux autorisations Mac et barres de défilement fines dans toute l’application.

## Premiers pas

1. Téléchargez le fichier adapté à votre système et ouvrez l’application. Python est inclus.
2. Choisissez le moteur OCR, le service de traduction et les langues dans les paramètres. Téléchargez des modèles pour la traduction hors ligne.
3. Choisissez une capture ou une traduction. Sur Mac, suivez les indications pour autoriser l’**enregistrement de l’écran** et l’**accessibilité**. Sur Linux, configurez les raccourcis du bureau avec le [guide Linux](../../docs/LINUX.md).

L’OCR fonctionne localement. La traduction en ligne envoie le texte au service choisi ; utilisez un moteur hors ligne pour une traduction locale. Voir [Confidentialité](../../PRIVACY.md).

## Aide et développement

[Linux](../../docs/LINUX.md) · [macOS et compilation](../../docs/MACOS.md) · [Signaler un problème](https://github.com/jabrailkhalil/clickntranslate/issues) · [Licence GPL-3.0](../../LICENSE)

Click’n’Translate est gratuit. S’il vous aide, merci de [mettre une étoile au projet sur GitHub](https://github.com/jabrailkhalil/clickntranslate) et de [nous rejoindre sur Telegram](https://t.me/jabrail_digital).
