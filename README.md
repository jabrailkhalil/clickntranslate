# Click’n’Translate

**Read what is on your screen. In your language.**

Translate a game, copy text from an image, understand a document, or replace a message with its translation. A free, open-source desktop app for **Windows, macOS and Linux**, with an **Android edition** too.

[![Downloads](https://img.shields.io/github/downloads/jabrailkhalil/clickntranslate/total?style=for-the-badge&label=Downloads&color=8b6bb1)](https://github.com/jabrailkhalil/clickntranslate/releases)
[![Release](https://img.shields.io/github/v/release/jabrailkhalil/clickntranslate?style=for-the-badge&color=674586)](https://github.com/jabrailkhalil/clickntranslate/releases/latest)
[![Stars](https://img.shields.io/github/stars/jabrailkhalil/clickntranslate?style=for-the-badge&color=8b6bb1)](https://github.com/jabrailkhalil/clickntranslate/stargazers)
[![License](https://img.shields.io/github/license/jabrailkhalil/clickntranslate?style=for-the-badge&color=674586)](LICENSE)

**English** · [Русский](docs/readme/README.ru.md) · [Español](docs/readme/README.es.md) · [Deutsch](docs/readme/README.de.md) · [Français](docs/readme/README.fr.md) · [简体中文](docs/readme/README.zh-CN.md) · [Português](docs/readme/README.pt.md) · [Italiano](docs/readme/README.it.md)

[Website](https://translate.clickn.dev/en/) · [Setup guide](docs/guides/setup.en.md) · [Telegram](https://t.me/jabrail_digital) · [Report an issue](https://github.com/jabrailkhalil/clickntranslate/issues)

![Click’n’Translate 1.8.2 — the actual Windows desktop app](docs/images/desktop-1.8.2.png)

## Download 1.8.2

The desktop packages include Python and the application runtime. You do not need to install Python.

| Platform | Download | Requirements |
| --- | --- | --- |
| Windows | [Installer](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-x64-installer.exe) · [Portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-portable-x64.zip) | Windows 10/11, x64. Extract the entire portable ZIP. |
| macOS, Apple Silicon | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-arm64.dmg) · [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-arm64.zip) | macOS 13.4+, M1 or newer |
| macOS, Intel | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-x86_64.dmg) · [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-x86_64.zip) | macOS 13.4+, Intel x86_64 |
| Linux | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.AppImage) · [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.tar.gz) | Linux x86_64; [setup and shortcuts](docs/LINUX.md) |
| Android | [Signed APK](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/ClicknTranslate-1.8.2-arm64.apk) | Android 8.0+, ARM64; [Android features and guide](https://github.com/jabrailkhalil/clickntranslate/tree/android#readme) |

[All files, checksums and signature bundle](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.2). The download badge counts release-file downloads on GitHub, not unique people.

Windows and Mac builds use the existing self-signed **jabrailkhalil** certificate. Windows may show SmartScreen; the Mac app is not Apple-notarized. See the [first-launch guide](docs/guides/setup.en.md) and [signing identities](docs/SIGNING_IDENTITIES.md).

## Pick the way you work

| When you want to… | Use… |
| --- | --- |
| Read text you cannot select | **Translate area** — draw a rectangle over an app, image or game |
| Grab a quote from a screenshot | **Copy text** — recognize an area and copy the text |
| Translate a passage in another app | **Translate selection** — use your own shortcut and language pair |
| Write a message in another language | **Replace with translation** — optionally select the whole input first |
| Follow changing text | **Dynamic translation** — watch multiple regions, with an overlay or separate output |
| Read a whole screen | **Translate screen** — show translated text over the captured screen |
| Work with a longer text or file | **Text and document translation** — edit original and result side by side |

The examples show the desktop edition. Android has its own screen, text, photo and history views.

### Text in, translation out

![Live translation in Click’n’Translate 1.8.2](docs/images/translate-text-1.8.2.gif)

Keep the result beside your draft, expand it into a workspace, or copy it. Documents open from `.txt`, `.md`, `.docx`, `.pdf`, `.html`, `.htm` and `.rtf`; scanned PDFs require an OCR workflow.

### Your engines, your settings

![Translation, OCR and API settings in 1.8.2](docs/images/settings-api-1.8.2.gif)

| Option | Available engines | How it works |
| --- | --- | --- |
| Everyday online translation | Google, MyMemory, Lingva, LibreTranslate | Send text to your chosen service |
| Offline translation | Argos Translate, Hy-MT | Install the required models, then translate locally |
| Local text recognition | Windows OCR, Apple Vision, Tesseract, RapidOCR, EasyOCR | Native engines depend on your OS; optional engines and languages install separately |
| Your own API connection | OpenAI, Gemini, Claude, DeepL, LibreTranslate, Custom API | Bring your own key; choose the model and endpoint where supported |
| Image-aware API translation | OpenAI, Gemini, Claude, compatible vision models | Explicitly enable image input to recognize and translate with one provider |

Open **Settings → Translation and OCR → Language packages**. Install engines and models in **OCR** or **Translators**, and configure keys in **API**. If an offline direction or engine is missing, the app offers installation or an available provider.

**Local OCR keeps images on your device.** Online translation sends text to the selected service; an enabled vision API also receives the selected image. Offline engines keep translation local after model downloads. API services have their own pricing and limits. [Privacy](PRIVACY.md).

### A companion when you need a click

![The current desktop companion and its settings](docs/images/companion-1.8.2.gif)

Choose a character, adjust size and opacity, and click it for translation actions. Reactions follow your actions. Prefer an empty desktop? Hide the companion and keep using shortcuts.

## Make it yours

- **Eight desktop interface languages:** English, Russian, Spanish, German, French, Chinese, Portuguese and Italian, including hints and the in-app guide.
- **Light or dark**, adjustable interface scale, and a separate result-text size with a live preview.
- **Separate language pairs** for screen OCR, selection, replacement, full-screen and dynamic translation.
- **Optional local histories**, settings import/export, and a diagnostic ZIP for troubleshooting.
- **Optional result dismissal by outside click**, in the translation settings.

### Default desktop shortcuts

| Windows default | Action |
| --- | --- |
| `Ctrl + Alt + T` | Translate an area |
| `Ctrl + Alt + C` | Copy text from an area |
| `Ctrl + Alt + F` | Translate the screen |
| `Ctrl + Alt + Q` | Translate selected text |
| `Ctrl + Shift + Q` | Replace with translation |
| `Ctrl + Alt + G` | Start or stop dynamic translation |
| `Ctrl + Shift + Space` | Show or hide the app |

Change or clear bindings in **Settings → Configure hotkeys**. On **Mac**, use Command for Ctrl and Option for Alt. On **Linux**, configure the commands in your desktop environment; behavior depends on X11/Wayland and the compositor. [Linux guide](docs/LINUX.md).

## Start in three steps

1. Download your build and open it. On Mac, grant **Screen Recording** and **Accessibility** when the feature requires them. On Android, grant capture and overlay access when starting screen translation.
2. Choose a translation service and language pair. For offline use, install the selected engine and language direction first.
3. Type a text, use a shortcut, or click the companion. Reopen the built-in guide from Help whenever you need it.

### Updates

Desktop 1.8.2 checks GitHub Releases and downloads compatible update files **inside the app**. The update page shows progress; the native helper replaces the application and restarts it. Mac and Linux versions 1.8.1 and earlier need this first upgrade installed manually. Protected installation locations can require manual replacement; Microsoft Store builds update through the Store. [Update behavior and checks](docs/UPDATES_1.8.2_DEVELOPMENT.md).

## Help, source and community

Use **Settings → Bug report** and attach the generated ZIP to a [GitHub issue](https://github.com/jabrailkhalil/clickntranslate/issues). The report excludes clipboard contents, documents, histories and credentials.

[First launch](docs/guides/setup.en.md) · [Linux setup](docs/LINUX.md) · [Mac setup and builds](docs/MACOS.md) · [Source layout](docs/REPOSITORY_LAYOUT.md) · [GPL-3.0 license](LICENSE)

Android development lives in the [`android` branch](https://github.com/jabrailkhalil/clickntranslate/tree/android); desktop development lives in `main`.

If Click’n’Translate makes your day easier, [star the project](https://github.com/jabrailkhalil/clickntranslate) or [join us on Telegram](https://t.me/jabrail_digital).
