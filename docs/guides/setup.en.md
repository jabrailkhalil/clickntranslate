<!-- Generated from docs/landing/tools/setup-content.mjs. -->
# Install and start translating

**English** · [Русский](setup.ru.md) · [Español](setup.es.md) · [Deutsch](setup.de.md) · [Français](setup.fr.md) · [中文](setup.zh-CN.md)

First launch on Windows and Mac, step by step.

Current builds use the self-signed jabrailkhalil identity. It is not a publicly trusted Windows certificate or an Apple Developer ID; the Mac app is not notarized. You do not need to install the author's certificate or sign the app yourself.

[Official downloads and checksums](https://github.com/jabrailkhalil/clickntranslate/releases/latest)

<a id="windows"></a>

## Windows: installation, SmartScreen and Defender

### 1. Install or extract

Download from this site or jabrailkhalil/clickntranslate on GitHub. Run the installer, or extract the entire Portable ZIP into its own folder and open ClicknTranslate.exe. Keep the app folder beside it. Python is included.

### 2. If SmartScreen blocks the first launch

For the expected official file that you trust, choose More info → Run anyway in the Windows protected your PC dialog, if available. This reputation warning is different from an antivirus detection.

### 3. If Defender quarantined a file

Open Windows Security → Virus & threat protection → Protection history. Check the detected file's path and threat name. Update security intelligence and scan again. Only if you have verified the official file and are confident it is a false positive, choose Restore. If Defender detects it again, open that event and choose Allow on device. These actions can require administrator approval.

### 4. If you cannot allow the app

Smart App Control or an organisation's policy may prevent an exception. Contact your administrator or report the block to the project. Keep antivirus protection enabled; do not exclude Downloads, a whole drive or all applications.

A self-signed certificate or a matching checksum does not prove that a malware alert is false. Report recurring detections with the app version, filename, SHA-256 and exact threat name so the affected build can be investigated.

<a id="macos"></a>

## Mac: first launch and permissions

### 1. Choose your Mac and install

In Apple menu → About This Mac, check the chip or processor. Choose Apple Silicon for M1 and newer, or Intel for Intel Macs. Open the DMG and drag ClicknTranslate.app into Applications. Launch that copy, not the copy inside the DMG.

### 2. Try opening the app once

If macOS says the developer cannot be verified or Apple cannot check the app, dismiss the warning with Done or Cancel. This attempt makes the approval control available in Settings.

### 3. Approve this app

Open System Settings → Privacy & Security, scroll to Security and choose Open Anyway for ClicknTranslate. Authenticate if asked, then confirm Open in the next warning. Only approve the official download you trust.

### 4. Allow screen capture

After the welcome screen, use Enable beside Screen Recording in the app's Mac setup dialog. In Privacy & Security → Screen Recording (or Screen & System Audio Recording), enable ClicknTranslate. This allows OCR to read the screen. If needed, use + to select /Applications/ClicknTranslate.app; otherwise trigger a screen capture to request access.

### 5. Allow selected-text actions

Use Enable beside Accessibility, or open Privacy & Security → Accessibility. Enable the same installed ClicknTranslate.app so the app can copy and replace text in other applications. This is a separate permission from screen recording.

### 6. Restart and return

Accept Quit & Reopen if macOS offers it. Otherwise choose Quit from the app's menu-bar icon, then reopen it from Applications. Closing only the window can leave it running. Return to the setup dialog and click Check again → Continue.

An old copy can remain in the permission list after replacement. If access still fails, quit the app, remove only its outdated entry with − where available, then add the copy in Applications with + and enable it. Do not remove permissions for other apps.

If macOS says the app is damaged or will damage your computer, do not treat that as an unidentified-developer warning. Download it again from the official release, compare its checksum and report the exact message. This guide does not require disabling Gatekeeper, clearing quarantine in Terminal or re-signing the app.

## Your first translation

Choose the source and target languages, then click the companion → Translate area and draw a box around text. Or press Ctrl + Alt + T on Windows, Command + Option + T on Mac. Enable the companion in Settings if it is hidden. Online translation needs internet; offline translation needs language models downloaded beforehand.

## Check the file before allowing it

Compare the downloaded file's SHA-256 with the checksum for that exact file and version in the official release's verification archive or .sha256 file. A match checks file integrity, not antivirus approval. Replace the example path below with your downloaded installer or DMG.

Windows · PowerShell:

```powershell
Get-FileHash -LiteralPath "C:\path\to\installer.exe" -Algorithm SHA256
```

macOS · Terminal:

```sh
shasum -a 256 "/path/to/Click-n-Translate.dmg"
```

[Still blocked? Report the exact message](https://github.com/jabrailkhalil/clickntranslate/issues)

## Apple and Microsoft instructions

- [Opening an unverified Mac app](https://support.apple.com/en-us/102445)
- [Mac screen recording permission](https://support.apple.com/guide/mac-help/mchld6aa7d23/mac)
- [Mac Accessibility permission](https://support.apple.com/guide/mac-help/mh43185/mac)
- [Windows protection history](https://support.microsoft.com/en-us/windows/security/windows-security/protection-history-in-the-windows-security-app)
- [Windows SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
