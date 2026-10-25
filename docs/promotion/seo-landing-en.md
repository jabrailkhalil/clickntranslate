# English SEO landing page copy

Updated 25 October 2026 for published 1.8.2. This is an editorial copy bank for
the existing site, https://translate.clickn.dev/, rather than a new deployment.
The next update is planned in about two weeks and is not released yet.

## Metadata

**Published page:** `https://translate.clickn.dev/en/`

**Title:** Free Screen Translator & OCR | Click'n'Translate

**Meta description:** Copy or translate text from games, images, videos, apps,
and documents. Free open-source screen OCR with hotkeys and online or offline
engines.

**Canonical:** `https://translate.clickn.dev/en/`

**Open Graph title:** Translate any text on your screen with one hotkey

**Open Graph description:** Free, open-source screen OCR and translation for
Windows, macOS, Linux and Android. Desktop includes selected text, documents,
full-screen and multi-area translation; Android has its own floating-button,
text and photo workflows.

## Hero

### Eyebrow

Free and open source · Windows · macOS · Linux · Android

# Translate any text on your screen

On desktop, copy text that cannot be selected. Translate a game, image, video, application,
or document. Replace highlighted text in place or keep several screen regions
translated as they change — all with configurable hotkeys.

**Primary CTA:** Download for your device

**Secondary CTA:** View source on GitHub

**Tertiary links:** Windows · macOS · Linux · Android APK · Release notes

Microcopy below CTA:

> Latest release: detected automatically from GitHub. The app is free under
> GPL-3.0, with no required Click’n’Translate account or app advertising.

## Demo caption

Select one or several important regions. Click'n'Translate recognizes the text
with your chosen OCR engine and updates translated overlays when it changes.

## Problem section

## Stop retyping text you can already see

Some text refuses to behave like text. It is trapped inside a screenshot,
subtitle, game, remote desktop, video, scanned page, or old interface. Copying it
often means taking a screenshot and moving through several tools.

Click'n'Translate makes the screen itself the input. Press a hotkey, select what
matters, and continue where you were.

| You need to… | Use… | You get… |
| --- | --- | --- |
| Copy unselectable text | Area OCR | Recognized text in your clipboard |
| Translate part of the screen | OCR translation | A focused result window |
| Understand an interface | Full-screen translation | Translation over the original regions |
| Translate highlighted text | Selection translation | Your saved language pair |
| Write in another language | Selection replacement | Translated text in the same field |
| Follow subtitles or dialogue | Dynamic translation | Updating overlays over chosen regions |
| Translate a file | Document workspace | Original and translation side by side |

## Dynamic translation section

## Translate changing text without translating the entire desktop

Draw one or several regions around the text you care about. Dynamic translation
checks those regions at your chosen interval, skips unchanged frames, and
updates the overlays when the text changes. Press the same shortcut again to
stop.

You control refresh frequency, overlay opacity, whether the original remains
visible, and whether the mode pauses when its application is inactive.

**CTA:** See Dynamic translation on GitHub

## Engines section

## Use the engine that fits the screen

Different fonts, scripts, backgrounds, and image quality need different tools.
Click'n'Translate does not lock you into one OCR or translation route.

### OCR on your computer

- Windows OCR / Apple Vision, on their respective platforms
- Tesseract
- RapidOCR
- EasyOCR

### Fast online translation

- Google
- MyMemory
- Lingva
- LibreTranslate

### Optional offline translation

- Argos Translate
- Hy-MT

Install only the language data and offline models you need from the built-in
package manager.

## Privacy section

## Know where your text goes

Local OCR processes on the device. Desktop Argos Translate and Hy-MT translate
locally after model installation; Android offers supported ML Kit offline models.
Online translation sends text to the selected service. If cloud OCR or an
image-capable API is enabled, it can receive the selected image too. Desktop
histories are local and optional; Android has clearable local text history.
Website privacy has a separate scope: https://clickn.dev/en/privacy/.

**CTA:** Read the privacy policy

## Documents section

## Screen translation when you need it, a workspace when you do not

On desktop, open `.txt`, `.md`, `.docx`, text-based `.pdf`, `.html`, `.htm`, or `.rtf`. Work with the
original and translation side by side, translate a selection or complete text,
and save the result as text, Markdown, or a reopenable local session.

## Trust section

## Open code, visible trade-offs

- GPL-3.0 source code and public issue tracker.
- Versioned Windows, macOS, Linux and Android downloads.
- SHA-256 hashes published with releases.
- Dated validation reports with their actual checks and platform limitations.
- Privacy-safe diagnostic reports that exclude clipboard contents, documents,
  histories, credentials, and OCR logs.

### A note about Windows antivirus warnings

Windows and macOS packages use the self-signed `jabrailkhalil` identity. This is
not publicly trusted Windows CA signing or Apple Developer ID signing; the Mac
app is not notarized. System warnings can appear on first launch. Follow the
official setup guide and investigate antivirus detections instead of treating
them as automatically false positives. Use only official downloads.

## FAQ

### Is Click'n'Translate free?

Yes. It is open-source software distributed under GPL-3.0, with no account,
advertising, or paid tier.

### Does it work offline?

Yes, after installing the required OCR language data and an Argos Translate or
Hy-MT package. Online translation providers still require a connection.

### Can it translate games and videos?

Yes. OCR reads pixels from a selected region, so the source does not need to be
selectable. Results depend on the font, size, contrast, language data, and chosen
OCR engine.

### Does it support Linux?

Yes. The release page provides an x86_64 AppImage and a portable TAR archive.
Some desktop integration and capture behavior can depend on the Linux session.

### What about Mac and Android?

Mac packages support macOS 13.4+ with separate Apple Silicon and Intel downloads.
Android 8.0+ ARM64 has its own floating button, text, photo, Share and history
workflows. Basic capture needs Android screen-sharing consent and overlay
permission, not root access. See https://translate.clickn.dev/en/#android.

### Can it replace selected text?

Yes. Highlight text in another application and use the replacement shortcut.
Click'n'Translate translates it with that mode's saved language pair and inserts
the result in place.

### Is text sent to the developer?

No developer-operated telemetry or history upload is built in. Online
translation text is sent to the provider the user selects. Optional histories
remain local.

## Final CTA

## See it. Select it. Understand it.

Download Click'n'Translate, press `Ctrl + Alt + T`, and translate the first piece
of screen text that gets in your way.

**Primary CTA:** Download the latest Click'n'Translate

**Secondary CTA:** Browse the source

**Support links:** Report a bug · Telegram · Privacy · License

## Structured data draft

Align these fields with the current visible page and actual release assets.

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Click'n'Translate",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Windows 10, Windows 11, macOS 13.4+, Linux x86_64, Android 8.0+ ARM64",
  "isAccessibleForFree": true,
  "license": "https://github.com/jabrailkhalil/clickntranslate/blob/main/LICENSE",
  "url": "https://translate.clickn.dev/en/",
  "downloadUrl": "https://github.com/jabrailkhalil/clickntranslate/releases/latest",
  "codeRepository": "https://github.com/jabrailkhalil/clickntranslate",
  "description": "Free open-source screen OCR and translation for Windows, macOS, Linux and Android, with online services and optional offline models.",
  "author": {
    "@type": "Person",
    "name": "Dzhabrail Khalilov"
  },
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  }
}
```

Do not add ratings or review markup until genuine, visible reviews exist on the
page.
