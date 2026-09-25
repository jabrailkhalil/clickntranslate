# Click'n'Translate

Free, open-source screen OCR and translation for **Windows, Linux and macOS**. Capture text from apps, images and games, translate selected text, or follow changing text in one or more screen regions.

**English** · [Русский](docs/readme/README.ru.md) · [简体中文](docs/readme/README.zh-CN.md) · [Español](docs/readme/README.es.md) · [Français](docs/readme/README.fr.md)

## Download 1.8.0

| System | Download | Choose this for |
| --- | --- | --- |
| Windows x64 | [Installer (.exe)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-windows-x64-installer.exe) | A regular installation on Windows 10/11, x64. |
| Windows x64 | [Portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-windows-portable-x64.zip) | Running without installation; extract the entire archive. |
| Linux x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-linux-x86_64.AppImage) | A single-file application for Linux x86_64; make it executable before opening. |
| Linux x86_64 | [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-linux-x86_64.tar.gz) | An unpacked application folder for Linux x86_64. |
| macOS arm64 | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-macos-arm64.dmg) | Installing on Apple Silicon (M1 and newer), macOS 13.4 or later. |
| macOS arm64 | [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-macos-arm64.zip) | The same Apple Silicon app in a ZIP archive. |

[All downloads, SHA-256 checksums and signature files](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.0).

Windows and macOS builds currently use a **self-signed certificate named `jabrailkhalil`**. Windows may show a SmartScreen warning; the Mac app has no Apple Developer ID or notarization, so Gatekeeper may block its first launch. Linux downloads have separate OpenPGP signatures. This release does not include an Intel Mac build.

## What is included

- Screen OCR, selected-text translation, full-screen overlays and dynamic translation of multiple regions.
- Online translation and local OCR; optional offline translation with downloaded language models.
- Document translation, configurable shortcuts and a desktop companion.
- Light and dark themes, six interface languages, and separate window preferences for each mode.
- **1.8.0:** a shared welcome screen, clearer language menus, improved dynamic overlays, Mac permission guidance and thin scrollbars throughout the app.

## Get started

1. Download the file for your system and open the app. The Python runtime is included.
2. Choose your OCR engine, translation provider and languages in Settings. Download language models if you want offline translation.
3. Choose a capture or translation action. On Mac, follow the app’s prompts to grant **Screen Recording** and **Accessibility** permissions. On Linux, configure desktop shortcuts using the [Linux guide](docs/LINUX.md).

OCR runs locally. Online translation sends the text to your selected provider; use an offline engine to keep translation local. See [Privacy](PRIVACY.md).

## Help and development

[Linux setup](docs/LINUX.md) · [macOS setup and builds](docs/MACOS.md) · [Report a problem](https://github.com/jabrailkhalil/clickntranslate/issues) · [License: GPL-3.0](LICENSE)

Click’n’Translate is free. If it helps you, please [star the project on GitHub](https://github.com/jabrailkhalil/clickntranslate) and [join us on Telegram](https://t.me/jabrail_digital).
