<!-- Generated from docs/landing/tools/setup-content.mjs. -->
# Installation und erster Start

[English](setup.en.md) · [Русский](setup.ru.md) · [Español](setup.es.md) · **Deutsch** · [Français](setup.fr.md) · [中文](setup.zh-CN.md)

Windows und Mac Schritt für Schritt einrichten.

Die aktuellen Builds sind mit der selbst signierten Identität jabrailkhalil signiert. Sie ist weder ein öffentlich vertrauenswürdiges Windows-Zertifikat noch eine Apple Developer ID; die Mac-App ist nicht notarisiert. Sie müssen weder das Zertifikat des Autors installieren noch die App selbst signieren.

[Offizielle Downloads und Prüfsummen](https://github.com/jabrailkhalil/clickntranslate/releases/latest)

<a id="windows"></a>

## Windows: Installation, SmartScreen und Defender

### 1. Installieren oder entpacken

Laden Sie die App hier oder aus jabrailkhalil/clickntranslate auf GitHub herunter. Starten Sie den Installer oder entpacken Sie das gesamte Portable-ZIP in einen eigenen Ordner und öffnen Sie ClicknTranslate.exe. Der Ordner app muss daneben bleiben. Python ist enthalten.

### 2. SmartScreen blockiert den Start

Wenn Sie der offiziellen Datei vertrauen, wählen Sie in der SmartScreen-Warnung Weitere Informationen → Trotzdem ausführen, sofern verfügbar. Eine Reputationswarnung ist keine Virenerkennung.

### 3. Defender hat eine Datei isoliert

Öffnen Sie Windows-Sicherheit → Viren- & Bedrohungsschutz → Schutzverlauf. Prüfen Sie Dateipfad und Bedrohungsname, aktualisieren Sie die Schutzdefinitionen und scannen Sie erneut. Nur wenn Sie die offizielle Datei überprüft haben und von einem Fehlalarm überzeugt sind, wählen Sie Wiederherstellen. Bei erneuter Erkennung öffnen Sie den neuen Eintrag und wählen Auf Gerät zulassen. Administratorrechte können erforderlich sein.

### 4. Keine Ausnahme möglich

Smart App Control oder Unternehmensrichtlinien können den Start verhindern. Wenden Sie sich an den Administrator oder melden Sie die Blockierung. Lassen Sie den Virenschutz aktiv; nehmen Sie nicht den Downloadordner, ganze Laufwerke oder alle Apps von Prüfungen aus.

Eine selbst signierte Datei oder passende Prüfsumme beweist keinen Fehlalarm. Melden Sie wiederholte Erkennungen mit Version, Dateiname, SHA-256 und genauem Bedrohungsnamen.

<a id="macos"></a>

## Mac: Start erlauben und Zugriffsrechte

### 1. Passende Version installieren

Prüfen Sie Chip oder Prozessor unter Apple → Über diesen Mac. Wählen Sie Apple Silicon für M1 und neuer, sonst Intel für Intel-Macs. Öffnen Sie das DMG und ziehen Sie ClicknTranslate.app nach Programme. Starten Sie diese Kopie, nicht die im DMG.

### 2. Einmal zu öffnen versuchen

Wenn macOS den Entwickler oder die App nicht überprüfen kann, schließen Sie die Warnung mit Fertig oder Abbrechen. Erst nach diesem Versuch erscheint die Freigabe in den Einstellungen.

### 3. Diese App freigeben

Öffnen Sie Systemeinstellungen → Datenschutz & Sicherheit, scrollen Sie zu Sicherheit und wählen Sie Dennoch öffnen (Open Anyway) für ClicknTranslate. Bestätigen Sie gegebenenfalls mit Passwort oder Touch ID und anschließend mit Öffnen. Geben Sie nur den vertrauenswürdigen offiziellen Download frei.

### 4. Bildschirmaufnahme erlauben

Klicken Sie nach dem Willkommensfenster im Einrichtungsdialog bei Bildschirmaufnahme auf Aktivieren. Schalten Sie ClicknTranslate unter Datenschutz & Sicherheit → Bildschirmaufnahme bzw. Bildschirm- & Systemaudioaufnahme ein. Wählen Sie bei Bedarf über + die Datei /Applications/ClicknTranslate.app; falls das nicht angeboten wird, starten Sie eine Bildschirmaufnahme in der App, um Zugriff anzufordern.

### 5. Bedienungshilfen erlauben

Klicken Sie im Dialog bei Bedienungshilfen auf Aktivieren oder öffnen Sie Datenschutz & Sicherheit → Bedienungshilfen. Aktivieren Sie dieselbe installierte App. Diese separate Berechtigung ermöglicht das Kopieren und Ersetzen ausgewählten Texts in anderen Apps.

### 6. Neu starten

Bestätigen Sie Beenden & erneut öffnen, wenn macOS dies anbietet. Sonst beenden Sie die App über ihr Menüleistensymbol und öffnen sie erneut aus Programme. Nur das Fenster zu schließen reicht möglicherweise nicht. Klicken Sie im Dialog auf Erneut prüfen → Weiter.

Nach einem Update kann eine alte Kopie in der Berechtigungsliste stehen. Beenden Sie die App, entfernen Sie bei weiterhin fehlendem Zugriff nur ihren veralteten Eintrag mit −, sofern verfügbar, und fügen Sie die Kopie aus Programme mit + hinzu. Aktivieren Sie sie erneut.

Bei Meldungen wie beschädigt oder wird deinen Computer beschädigen laden Sie die offizielle Datei erneut herunter, vergleichen die Prüfsumme und melden den genauen Text. Das ist keine einfache Entwicklerwarnung. Gatekeeper muss für diese Anleitung nicht deaktiviert, die Quarantäne nicht im Terminal entfernt und die App nicht neu signiert werden.

## Die erste Übersetzung

Wählen Sie Ausgangs- und Zielsprache, klicken Sie auf das Maskottchen → Bereich übersetzen und markieren Sie Text. Alternativ: Ctrl + Alt + T unter Windows, Command + Option + T auf dem Mac. Ein ausgeblendetes Maskottchen lässt sich in den Einstellungen aktivieren. Online-Übersetzung braucht Internet; offline müssen Sprachmodelle vorher geladen sein.

## Datei vor der Freigabe prüfen

Vergleichen Sie SHA-256 mit dem Wert für genau diese Datei und Version im offiziellen Verification-Archiv oder der .sha256-Datei. Die Übereinstimmung bestätigt Integrität, keine Virenschutzfreigabe. Ersetzen Sie den Beispielpfad durch Ihren Installer oder Ihr DMG.

Windows · PowerShell:

```powershell
Get-FileHash -LiteralPath "C:\path\to\installer.exe" -Algorithm SHA256
```

macOS · Terminal:

```sh
shasum -a 256 "/path/to/Click-n-Translate.dmg"
```

[Blockierung mit genauer Meldung melden](https://github.com/jabrailkhalil/clickntranslate/issues)

## Anleitungen von Apple und Microsoft

- [Nicht verifizierte Mac-App öffnen](https://support.apple.com/en-us/102445)
- [Bildschirmaufnahme auf dem Mac](https://support.apple.com/guide/mac-help/mchld6aa7d23/mac)
- [Bedienungshilfen auf dem Mac](https://support.apple.com/guide/mac-help/mh43185/mac)
- [Windows-Schutzverlauf](https://support.microsoft.com/en-us/windows/security/windows-security/protection-history-in-the-windows-security-app)
- [Windows-SmartScreen-Reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
