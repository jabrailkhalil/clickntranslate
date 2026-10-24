# Press kit copy

Updated **25 October 2026**. Current published release: **1.8.2**. The next update
is planned in about two weeks; announcement copy must distinguish that plan from
features already available.

## Product facts

| Field | Value |
| --- | --- |
| Name | Click’n’Translate |
| Developer | Dzhabrail Khalilov / Jabrail Digital |
| Category | Screen OCR and translation |
| Windows | Windows 10/11 x64; EXE installer and portable ZIP |
| macOS | macOS 13.4+; Apple Silicon and Intel DMGs |
| Linux | x86_64 AppImage and portable tar.gz |
| Android | Android 8.0+ ARM64 APK |
| License / price | GPL-3.0-only / free |
| Account | No required Click’n’Translate account |
| Product website | https://translate.clickn.dev/ |
| Author’s projects | https://clickn.dev/ |
| Source | https://github.com/jabrailkhalil/clickntranslate |
| Downloads | https://github.com/jabrailkhalil/clickntranslate/releases/latest |
| Contact | jabrailkhalil@gmail.com / https://t.me/jabrail_digital |

## English boilerplate

### Short

Click’n’Translate is a free, open-source screen translator and OCR app for Windows,
macOS, Linux and Android, with online services and optional offline models.

### Extended

Click’n’Translate turns visible text into something you can read or copy. The desktop
app translates a screen region, the full screen or selected text, replaces a selection,
follows changing regions and opens common documents side by side. Android provides
screen translation through a floating button, text and photo translation, Share actions
and local text history. Users choose local engines, online services or their own API
connections. Supported offline models are downloaded separately. Recognition and
translation accuracy depend on the engine, language, font and source image.

## Описание на русском

Click’n’Translate — бесплатный переводчик экрана с открытым кодом для Windows,
macOS, Linux и Android. На компьютере он переводит области экрана, выделенный
текст и документы, заменяет выделение переводом и следит за меняющимся текстом.
На Android есть плавающая кнопка поверх приложений, перевод текста и фотографий,
меню «Поделиться» и локальная история. Доступны онлайн-сервисы, офлайн-модели и
подключения со своими API-ключами. Набор языков зависит от выбранного движка.

## Feature bullets

- Desktop area OCR, full-screen overlays and copy-to-clipboard.
- Desktop selected-text translation and replacement.
- Desktop Dynamic translation of multiple chosen regions.
- Desktop side-by-side TXT, Markdown, DOCX, text-based PDF, HTML and RTF workspaces.
- Optional desktop companion, customizable shortcuts, themes and per-mode language pairs.
- Android floating screen translation, text, photos, sharing and local text history.
- Eight desktop UI languages and six Android UI languages.
- 63 named desktop translation languages, subject to engine/model availability.
- Native Windows OCR/Apple Vision, Tesseract, RapidOCR and optional EasyOCR on desktop.
- Online services, optional offline models and user-configured API providers.

## Media

Use current repository screenshots and real recordings. The desktop GIFs under
`gifs/` demonstrate their stated workflows; some show an older window design.
Current desktop and Android 1.8.2 screenshots are under `../images/`.
Keep phone screenshots separate from desktop hotkey demos. The unused generated
`gallery/` and `video/` drafts are not approved publication assets.

## Processing answer

Local OCR and installed offline models process on the device. Online services
receive the requested text; a selected cloud OCR or image-capable API also receives
the image. Desktop histories are optional and local; Android text history is local
and can be cleared. See [desktop policy](../../PRIVACY.md), [Android guide](../ANDROID.md)
and the separate [website policy](https://clickn.dev/en/privacy/).

## First-launch answer

Windows and macOS packages use the self-signed `jabrailkhalil` identity. They are
not signed by a publicly trusted Windows CA or Apple Developer ID; the Mac app is
not notarized. Follow the [official setup guide](../guides/setup.en.md). Investigate
antivirus detections rather than treating them as automatically false positives.
