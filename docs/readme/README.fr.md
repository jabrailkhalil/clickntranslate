<p align="center">
  <img src="../../src/icons/icon.png" alt="" width="72" height="72">
</p>

<h1 align="center">Click’n’Translate</h1>

<a name="readme-languages"></a>

<p align="center">
  <a href="../../README.md">English</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <strong>Français</strong> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.pt.md">Português</a> ·
  <a href="README.it.md">Italiano</a>
</p>

<p align="center"><strong>Lisez le texte à l’écran dans votre langue.</strong></p>
<p align="center">Windows · macOS · Linux · <a href="#android">Android</a></p>

<p align="center">
  <a href="https://github.com/jabrailkhalil/clickntranslate/releases/latest"><img src="https://img.shields.io/github/v/release/jabrailkhalil/clickntranslate?style=flat&amp;label=release&amp;color=73529a" alt="Latest release"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/jabrailkhalil/clickntranslate/releases"><img src="https://img.shields.io/github/downloads/jabrailkhalil/clickntranslate/total?style=flat&amp;label=downloads&amp;color=73529a" alt="GitHub release downloads"></a>
</p>

<p align="center">
  <strong><a href="#download">Télécharger</a></strong>
  &nbsp;&nbsp;&nbsp;
  <a href="https://translate.clickn.dev/en/">Site web</a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://t.me/jabrail_digital">Telegram</a>
</p>

Traduisez un jeu, copiez le texte d’une image, lisez un document ou remplacez un message par sa traduction. Une application gratuite et libre pour **Windows, macOS et Linux**, avec une édition **Android** distincte.

<p align="center">
  <img src="../../docs/images/translation-demo-v2.gif" alt="Lisez le texte à l’écran dans votre langue." width="640">
</p>

<a name="download"></a>

## Télécharger 1.8.2

| Système | Installer | Portable |
| --- | --- | --- |
| **Windows** 10/11 · x64 | [EXE](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-x64-installer.exe) | [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-portable-x64.zip) |
| **macOS** 13.4+ · Apple Silicon (M1+) | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-arm64.dmg) | — |
| **macOS** 13.4+ · Intel | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-x86_64.dmg) | — |
| **Linux** · x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.AppImage) | [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.tar.gz) |
| **Android** 8.0+ · ARM64 | [APK](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/ClicknTranslate-1.8.2-arm64.apk) | — |

[Tous les téléchargements](https://github.com/jabrailkhalil/clickntranslate/releases/latest)

<a name="android"></a>

## Sur Android : traduisez sans quitter votre application

**Un bouton flottant pour les jeux et applications, ainsi que la traduction de texte et de photos.** Tout fonctionne sur le téléphone, sans ordinateur ni accès root.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../images/android-home-dark-1.8.2.png">
    <img src="../images/android-home-light-1.8.2.png" alt="Accueil Android avec langues et actions de traduction de l’écran, d’images et de texte" width="280">
  </picture>
</p>

<p align="center"><sub>Interface Android 1.8.2, présentée en russe. Six langues sont disponibles, dont le français.</sub></p>

1. **Installez l’APK** sur un appareil Android 8.0+ ARM64. Choisissez la langue de l’interface, le thème et les langues de traduction.
2. **Lancez la traduction de l’écran.** Autorisez l’affichage par-dessus les applications et acceptez la capture. À partir d’Android 14, partagez tout l’écran pour traduire dans d’autres applications.
3. **Ouvrez votre jeu ou application et touchez le bouton flottant.** La traduction apparaît sur l’écran. Maintenez le bouton pour choisir une zone ou un autre mode dans son menu.

Vous pouvez aussi saisir ou coller du texte, le partager vers **Clickn** depuis une autre application et traduire une photo ou capture de la galerie. Copiez ou partagez les résultats et retrouvez l’historique local des textes. Google fonctionne sans clé ; ML Kit traduit hors ligne après téléchargement des modèles compatibles. Les services API supplémentaires utilisent vos propres identifiants.

[Guide Android (anglais)](../ANDROID.md) · [Code Android](https://github.com/jabrailkhalil/clickntranslate/tree/android)

## Sur ordinateur : du texte au résultat

Traduisez une zone, l’écran entier ou une sélection dans une autre application. Le remplacement peut sélectionner tout le champ avant de coller la traduction. Le mode dynamique suit plusieurs zones. Le lecteur de documents affiche et permet de modifier original et traduction côte à côte.

## Choisissez vos moteurs

Google, MyMemory, Lingva et LibreTranslate en ligne ; Argos Translate et Hy-MT hors ligne après téléchargement des modèles. OCR local : Windows OCR, Apple Vision, Tesseract, RapidOCR et EasyOCR, selon le système.

Dans **Settings → Translation and OCR → Language packages → API**, configurez votre clé OpenAI, Gemini, Claude, DeepL, LibreTranslate ou Custom API. Une entrée d’image explicitement activée permet aux modèles de vision compatibles de reconnaître et traduire avec un seul fournisseur.

L’OCR local conserve les images sur l’appareil. Les services en ligne reçoivent le texte ; une API de vision activée reçoit aussi l’image choisie. Les tarifs et limites du fournisseur s’appliquent. [Confidentialité](../../PRIVACY.md).

## À votre façon

Huit langues d’interface avec aide et infobulles, thèmes clair et sombre, échelle d’interface et taille du texte distinctes, raccourcis personnalisables, import/export et historiques locaux facultatifs. Cliquez sur le compagnon pour ouvrir les actions, ou masquez-le.

Python est inclus. Windows et Mac utilisent le certificat autosigné jabrailkhalil ; SmartScreen peut apparaître et l’app Mac n’est pas notariée. [Premier lancement](../guides/setup.fr.md). Accordez les autorisations d’enregistrement d’écran et d’accessibilité sur Mac pour les fonctions concernées. [Linux et raccourcis](../LINUX.md).

La version de bureau 1.8.2 télécharge les mises à jour GitHub Releases dans l’app. Mac/Linux 1.8.1 et antérieurs nécessitent une première installation manuelle ; certains emplacements protégés exigent un remplacement manuel. Les éditions Microsoft Store passent par Store.

Android propose ses propres vues écran, texte, photos et historique : [guide](https://github.com/jabrailkhalil/clickntranslate/tree/android#readme).

[Guide complet en anglais](../../README.md) · [Signaler un problème](https://github.com/jabrailkhalil/clickntranslate/issues) · [GPL-3.0](../../LICENSE)

## Autres exemples

### Copier le texte d’une image

![Copier le texte d’une image](../images/area-ocr-demo-v2.gif)

### Traduire le texte sélectionné

![Traduire le texte sélectionné](../images/selected-text-demo-v2.gif)

### Traduire tout l’écran

![Traduire tout l’écran](../images/fullscreen-translation-demo-v2.gif)

<sub>Enregistrements de la version de bureau ; l’apparence actuelle peut différer.</sub>
