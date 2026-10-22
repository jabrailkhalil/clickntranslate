<p align="center">
  <img src="src/icons/icon.png" alt="" width="72" height="72">
</p>

<h1 align="center">Click’n’Translate</h1>

<p align="center"><strong>Your screen. Your language.</strong></p>
<p align="center">Windows · macOS · Linux · Android</p>

<p align="center">
  <a href="https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.2"><img src="https://img.shields.io/github/v/release/jabrailkhalil/clickntranslate?style=flat&amp;label=release&amp;color=73529a" alt="Latest release"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/jabrailkhalil/clickntranslate/releases"><img src="https://img.shields.io/github/downloads/jabrailkhalil/clickntranslate/total?style=flat&amp;label=downloads&amp;color=73529a" alt="GitHub release downloads"></a>
</p>

<p align="center">
  <strong><a href="#download">Download</a></strong>
  &nbsp; · &nbsp;
  <a href="https://translate.clickn.dev/en/">Website</a>
  &nbsp; · &nbsp;
  <a href="https://t.me/jabrail_digital">Telegram</a>
  &nbsp; · &nbsp;
  <a href="#readme-languages">Languages</a>
</p>

**Translate text from games, images and any app — without retyping it.** Capture an area, translate a selection, or follow changing text. Free and open source.

<p align="center">
  <img src="docs/images/translation-demo-v2.gif" alt="Your screen. Your language." width="640">
</p>

<a name="download"></a>

## Download 1.8.2

| Platform | Install | Portable |
| --- | --- | --- |
| **Windows** 10/11 · x64 | [EXE](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-x64-installer.exe) | [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-portable-x64.zip) |
| **macOS** 13.4+ · Apple Silicon (M1+) | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-arm64.dmg) | — |
| **macOS** 13.4+ · Intel | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-x86_64.dmg) | — |
| **Linux** · x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.AppImage) | [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.tar.gz) |
| **Android** 8.0+ · ARM64 | [APK](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/ClicknTranslate-1.8.2-arm64.apk) | — |

[All downloads](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.2)

## Translate where you already are

- **Games, screenshots and apps:** draw a rectangle to recognize and translate text you cannot select.
- **Messages and documents:** translate a selection, replace a draft with its translation, or edit original and result side by side.
- **Changing text:** follow one or more screen regions with dynamic translation. Read results over the original or in a separate area.
- **Just need the text?** Copy recognized text from any screen area straight to the clipboard.

The desktop document workspace opens TXT, Markdown, DOCX, text-based PDF, HTML and RTF. Android has a dedicated [screen, text and photo translation interface](https://github.com/jabrailkhalil/clickntranslate/tree/android#readme).

## More ways to use it

### Copy text from an image

![Copy text from an image](docs/images/area-ocr-demo-v2.gif)

### Translate selected text

![Translate selected text](docs/images/selected-text-demo-v2.gif)

### Translate the full screen

![Translate the full screen](docs/images/fullscreen-translation-demo-v2.gif)

<sub>Desktop workflow recordings; the current window design may differ.</sub>


## Online, offline, or your own API

**Start online** with Google, MyMemory, Lingva or LibreTranslate. **Work offline** with Argos Translate or Hy-MT after installing models. Recognize text locally with Windows OCR, Apple Vision, Tesseract, RapidOCR or EasyOCR, depending on your system.

**Bring your own key** for OpenAI, Gemini, Claude, DeepL, LibreTranslate or a compatible custom API. Supported vision models can recognize and translate an image in one request when image input is enabled.

Set up engines, models and API connections in **Settings → Translation and OCR → Language packages**. Choose **OCR**, **Translators** or **API**. Missing local components link directly to installation.

Local OCR processes images on your device. Online services receive text; an enabled vision API also receives the selected image. Offline translation stays local after model downloads. Provider fees and limits apply. [Privacy](PRIVACY.md).

## Make it comfortable

Eight interface languages, light and dark themes, adjustable interface scale and a separate result-text size. Customize shortcuts and language pairs for each mode; keep optional local histories or export your settings. An optional desktop companion puts translation actions a click away.

<details>
<summary>Default desktop shortcuts</summary>

| Windows shortcut | Action |
| --- | --- |
| `Ctrl + Alt + T` | Translate an area |
| `Ctrl + Alt + C` | Copy text from an area |
| `Ctrl + Alt + F` | Translate the full screen |
| `Ctrl + Alt + Q` | Translate selected text |
| `Ctrl + Shift + Q` | Replace with translation |
| `Ctrl + Alt + G` | Start or stop dynamic translation |
| `Ctrl + Shift + Space` | Show or hide the app |

Change them in **Settings → Configure hotkeys**. On Mac, use Command for Ctrl and Option for Alt. On Linux, configure the commands in your desktop environment; support depends on X11/Wayland and the compositor. [Linux guide](docs/LINUX.md).

</details>

## Get started

1. **Install your build.** Python is included. Extract the whole archive if you choose Windows portable.
2. **Choose a service and your languages.** For offline use, install the engine and language direction in Language packages.
3. **Capture, select or type.** Use a shortcut or the companion, or type into the main window.

Windows and Mac builds use a self-signed `jabrailkhalil` certificate. SmartScreen or Gatekeeper may prompt on first launch; the Mac app is not Apple-notarized. The [setup guide](docs/guides/setup.en.md) covers first launch and Mac Screen Recording / Accessibility permissions.

Desktop 1.8.2 downloads GitHub Releases updates inside the app. Mac/Linux 1.8.1 and earlier need this first upgrade installed manually. Protected installation locations may require manual replacement; Microsoft Store editions update through the Store.

## Help and contribute

[Report a problem](https://github.com/jabrailkhalil/clickntranslate/issues) · [Telegram](https://t.me/jabrail_digital) · [Setup guide](docs/guides/setup.en.md) · [Source and builds](docs/REPOSITORY_LAYOUT.md)

For troubleshooting, attach the ZIP from **Settings → Bug report**. It excludes clipboard contents, documents, histories and credentials. Source code is available under [GPL-3.0](LICENSE); Android development lives in the [android branch](https://github.com/jabrailkhalil/clickntranslate/tree/android).

<details>
<summary>Checksums, signatures and the download counter</summary>

The small `.sha256` release files are used automatically by desktop updates to check downloaded packages. You do not need to download them yourself. The optional [verification archive](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-verification.zip) contains checksums, signatures and public certificates for manual verification. [Signing identities](docs/SIGNING_IDENTITIES.md).

The download badge counts release-file downloads, including update files; it does not count unique users.

</details>

---

<a name="readme-languages"></a>

Read in your language:

**English** · [Русский](docs/readme/README.ru.md) · [Español](docs/readme/README.es.md) · [Deutsch](docs/readme/README.de.md) · [Français](docs/readme/README.fr.md) · [简体中文](docs/readme/README.zh-CN.md) · [Português](docs/readme/README.pt.md) · [Italiano](docs/readme/README.it.md)
