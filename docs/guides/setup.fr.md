<!-- Generated from docs/landing/tools/setup-content.mjs. -->
# Installation et premier lancement

[English](setup.en.md) · [Русский](setup.ru.md) · [Español](setup.es.md) · [Deutsch](setup.de.md) · **Français** · [中文](setup.zh-CN.md)

Configurer Windows et Mac, étape par étape.

Les versions actuelles utilisent l’identité autosignée jabrailkhalil. Ce n’est ni un certificat Windows publiquement reconnu ni un Apple Developer ID ; l’app Mac n’est pas notariée. Vous n’avez pas à installer le certificat de l’auteur ni à signer vous-même l’app.

[Téléchargements officiels et sommes de contrôle](https://github.com/jabrailkhalil/clickntranslate/releases/latest)

<a id="windows"></a>

## Windows : installation, SmartScreen et Defender

### 1. Installer ou extraire

Téléchargez depuis ce site ou jabrailkhalil/clickntranslate sur GitHub. Lancez l’installateur ou extrayez entièrement le ZIP portable dans son propre dossier, puis ouvrez ClicknTranslate.exe. Gardez le dossier app à côté. Python est inclus.

### 2. Si SmartScreen bloque le lancement

Pour le fichier officiel auquel vous faites confiance, choisissez Informations complémentaires → Exécuter quand même dans l’avertissement SmartScreen, si cette option existe. Une alerte de réputation est différente d’une détection antivirus.

### 3. Si Defender a mis un fichier en quarantaine

Ouvrez Sécurité Windows → Protection contre les virus et menaces → Historique de protection. Vérifiez le chemin et le nom de la menace, actualisez les définitions et relancez l’analyse. Seulement après avoir vérifié le fichier officiel et si vous êtes certain d’un faux positif, choisissez Restaurer. En cas de nouvelle détection, ouvrez l’événement et choisissez Autoriser sur l’appareil. Un accord administrateur peut être nécessaire.

### 4. Si aucune exception n’est possible

Smart App Control ou une politique d’entreprise peut bloquer l’app. Contactez l’administrateur ou signalez le blocage au projet. Gardez l’antivirus actif ; n’excluez pas Téléchargements, un disque entier ou toutes les applications.

Une signature autosignée ou une somme identique ne prouve pas qu’une alerte est fausse. Signalez les détections répétées avec la version, le fichier, SHA-256 et le nom exact de la menace.

<a id="macos"></a>

## Mac : autoriser le lancement et les accès

### 1. Choisir la version et installer

Vérifiez la puce ou le processeur dans Apple → À propos de ce Mac. Choisissez Apple Silicon pour M1 et plus récent, ou Intel pour les Mac Intel. Ouvrez le DMG et glissez ClicknTranslate.app dans Applications. Lancez cette copie, pas celle du DMG.

### 2. Essayer de l’ouvrir une fois

Si macOS ne peut pas vérifier le développeur ou contrôler l’app, fermez l’alerte avec Terminé ou Annuler. Cette tentative fait apparaître l’autorisation dans les réglages.

### 3. Autoriser cette app

Ouvrez Réglages Système → Confidentialité et sécurité, descendez jusqu’à Sécurité et choisissez Ouvrir quand même (Open Anyway) pour ClicknTranslate. Authentifiez-vous si nécessaire, puis confirmez Ouvrir. N’autorisez que le téléchargement officiel auquel vous faites confiance.

### 4. Autoriser l’enregistrement de l’écran

Après l’accueil, cliquez sur Activer à côté d’Enregistrement de l’écran dans le dialogue de configuration. Activez ClicknTranslate dans Confidentialité et sécurité → Enregistrement de l’écran ou Enregistrement de l’écran et de l’audio du système. Au besoin, ajoutez /Applications/ClicknTranslate.app avec + ; sinon, lancez une capture depuis l’app pour demander l’accès.

### 5. Autoriser l’accessibilité

Cliquez sur Activer à côté d’Accessibilité, ou ouvrez Confidentialité et sécurité → Accessibilité. Activez la même app installée. Cette autorisation distincte sert à copier et remplacer du texte sélectionné dans d’autres apps.

### 6. Redémarrer et revenir

Acceptez Quitter et rouvrir si macOS le propose. Sinon, quittez via l’icône de l’app dans la barre des menus, puis rouvrez-la depuis Applications. Fermer seulement la fenêtre peut la laisser active. Cliquez sur Vérifier à nouveau → Continuer dans le dialogue.

Après une mise à jour, une ancienne copie peut rester dans la liste. Si l’accès échoue encore, quittez l’app, supprimez uniquement son ancienne entrée avec − si disponible, puis ajoutez la copie d’Applications avec + et activez-la.

Si macOS indique que l’app est endommagée ou endommagera votre ordinateur, téléchargez à nouveau la version officielle, comparez la somme et signalez le message exact. Ce n’est pas une simple alerte de développeur. Ce guide ne demande ni de désactiver Gatekeeper, ni de supprimer la quarantaine dans Terminal, ni de signer à nouveau l’app.

## Votre première traduction

Choisissez les langues, cliquez sur la mascotte → Traduire une zone et encadrez le texte. Ou utilisez Ctrl + Alt + T sous Windows, Command + Option + T sur Mac. Activez la mascotte dans les réglages si elle est masquée. La traduction en ligne nécessite internet ; hors ligne, téléchargez d’abord les modèles linguistiques.

## Vérifier le fichier avant de l’autoriser

Comparez SHA-256 avec la valeur de ce fichier et de cette version dans l’archive verification ou le fichier .sha256 officiel. Cela vérifie l’intégrité, pas une approbation antivirus. Remplacez le chemin d’exemple par celui de votre installateur ou DMG.

Windows · PowerShell:

```powershell
Get-FileHash -LiteralPath "C:\path\to\installer.exe" -Algorithm SHA256
```

macOS · Terminal:

```sh
shasum -a 256 "/path/to/Click-n-Translate.dmg"
```

[Signaler le blocage avec son message exact](https://github.com/jabrailkhalil/clickntranslate/issues)

## Instructions Apple et Microsoft

- [Ouvrir une app Mac non vérifiée](https://support.apple.com/en-us/102445)
- [Enregistrement de l’écran sur Mac](https://support.apple.com/guide/mac-help/mchld6aa7d23/mac)
- [Accessibilité sur Mac](https://support.apple.com/guide/mac-help/mh43185/mac)
- [Historique de protection Windows](https://support.microsoft.com/en-us/windows/security/windows-security/protection-history-in-the-windows-security-app)
- [Réputation Windows SmartScreen](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
