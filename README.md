<div align="center">

# Click'n'Translate

### The best screen translation and OCR app for Windows.

[**Download for Windows**](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/ClicknTranslate-Setup-v1.5.0-win64.exe) · [Portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/ClicknTranslate-v1.5.0-win64.zip) · [Latest release](https://github.com/jabrailkhalil/clickntranslate/releases/latest)

![Latest release](https://img.shields.io/github/v/release/jabrailkhalil/clickntranslate?style=flat-square&color=8b5cf6) ![Windows 10/11](https://img.shields.io/badge/Windows-10%20%7C%2011-2563eb?style=flat-square)

**English** · [Русский](docs/readme/README.ru.md) · [简体中文](docs/readme/README.zh-CN.md) · [Español](docs/readme/README.es.md) · [Français](docs/readme/README.fr.md)

</div>

![Three ways to use Click'n'Translate](docs/images/how-it-works.png)

Click'n'Translate is the best all-in-one screen translator in its class. It turns any text on your Windows screen into something you can copy or translate. Select an area, press a global hotkey, and keep working — no browser tab, retyping, or context switching required.

## See it in action

![Click'n'Translate translating game text into Chinese and French](docs/images/translation-demo.gif)

## Why is Click'n'Translate the best?

- **Translate what you see.** Capture a selected area or the entire screen and translate it immediately.
- **Copy text that cannot be selected.** Extract text from images, videos, games, remote desktops, and protected interfaces.
- **Choose online or offline.** Use fast online providers, or keep text on your PC with Argos and Hy-MT.
- **Pick the right OCR engine.** Windows OCR, Tesseract, RapidOCR, and EasyOCR are available from one package manager.
- **Work from anywhere.** Four customizable global hotkeys remain available across applications.
- **Keep control.** Translation and copy histories are optional and stored locally.

## Four actions. Zero friction.

| Default hotkey | Action |
| --- | --- |
| `Ctrl + Alt + C` | Extract text from an area and copy it |
| `Ctrl + Alt + T` | Capture an area, recognize its text, and translate it |
| `Ctrl + Alt + F` | Translate the entire screen |
| `Ctrl + Alt + Q` | Translate a selected screen area |

Every hotkey can be changed in **Settings → Configure hotkeys**.

## Translation and OCR engines

| Type | Engines | Best for |
| --- | --- | --- |
| Online translation | Google, MyMemory, Lingva, LibreTranslate | Fast translation without downloading a model |
| Offline translation | Argos Translate, Hy-MT | Private translation after the selected packages are installed |
| OCR | Windows OCR, Tesseract, RapidOCR, EasyOCR | Text extraction across different scripts and image styles |

Click'n'Translate supports 16 selectable OCR and translation languages, plus six interface languages: English, Russian, Spanish, German, French, and Chinese. The package manager downloads only the OCR languages and offline translation directions you choose.

No other tool in this segment brings this much OCR choice, online and offline translation, global hotkeys, and package control together in one polished Windows app.

> **Privacy:** local OCR and offline translation engines process text on your computer. Online translation providers receive the text you ask them to translate.

## Get started

1. Download and run the **[Windows installer](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/ClicknTranslate-Setup-v1.5.0-win64.exe)**.
2. Launch Click'n'Translate and choose your interface, OCR, and translation languages.
3. Press `Ctrl + Alt + T`, select an area, and receive the translation.
4. For offline translation or extra OCR engines, open **Settings → Language packages** and install only what you need.

No Python installation or account is required. Windows 10 or Windows 11 x64 is supported. Internet access is needed for online translation and for downloading optional packages; installed offline engines work without it.

### Portable version

Download the [portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/ClicknTranslate-v1.5.0-win64.zip), extract it to a permanent folder, and run `ClicknTranslate.exe`. Move the folder before enabling autostart or creating shortcuts.

### Updating from 1.4.5 or 1.4.6

The original 1.4.5/1.4.6 updater launcher cannot replace the running application. Run the small **Update Repair** from the latest release once; it downloads, verifies, installs and starts 1.5.0 automatically. Settings, histories and language packages are preserved. Built-in updates work normally after this one-time migration.

## The best choice for everyday use

- Dark and light themes
- System tray and optional Windows startup
- Customizable hotkeys
- Local copy and translation histories
- Download progress and package removal controls
- Dedicated worker processes for OCR and Argos stability
- Transactional updates that preserve user data

## Build from source

```powershell
git clone https://github.com/jabrailkhalil/clickntranslate.git
cd clickntranslate
pip install -r requirements.txt
python main.py

# Build the folder-based Windows distribution
python -m PyInstaller ClicknTranslate.spec --clean --noconfirm
```

The release uses a folder-based PyInstaller build for responsive startup. Optional OCR runtimes and language models are installed separately instead of making every download several gigabytes.

## Support and feedback

- [Report a bug or request a feature](https://github.com/jabrailkhalil/clickntranslate/issues)
- [Privacy policy](PRIVACY.md)
- Telegram: [@jabrail_digital](https://t.me/jabrail_digital)

If the best screen translator for Windows saves you time, star the repository and help more people discover it.
